"""Tests for `install` in the `goga_tool_pybuggy.plugins` cell.

Covers the contract surface and the import-time wiring (hook injection + synchronous ``pytest_plugins`` population)
plus the activation gates of the api, sandbox, and web plugins.
"""

import importlib
import inspect
import os
import sys
import types
from unittest import mock

import goga_tool_pybuggy.plugins
import pytest
from goga_tool_pybuggy.plugins import SandboxPlugin
from goga_tool_pybuggy.plugins.loaders import ModuleLoader
from pluginator import install_pytest_plugins


@pytest.fixture(autouse=True)
def isolate_sys_modules():
    """Snapshot and restore sys.modules so import-time trial imports never leak.

    The reload test re-runs the top-level ``install()`` (and thus ``_load_plugins``).
    """
    snapshot = sys.modules.copy()

    yield

    extra = set(sys.modules) - set(snapshot)
    for key in extra:
        del sys.modules[key]


def write_document(root) -> None:
    """Place a minimal valid sandbox document under the pybuggy tools home of ``root``.

    Args:
        root: The consumer repository root receiving ``.goga/tools/pybuggy/sandbox.yml``.
    """
    document = root / ".goga" / "tools" / "pybuggy" / "sandbox.yml"
    document.parent.mkdir(parents=True)
    document.write_text(
        "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\nservices:\n  db: { kind: postgresql }\n",
        encoding="utf-8",
    )


def write_api_document(root) -> None:
    """Place a minimal api document under the pybuggy tools home of ``root``.

    Args:
        root: The consumer repository root receiving ``.goga/tools/pybuggy/api.yml``.
    """
    document = root / ".goga" / "tools" / "pybuggy" / "api.yml"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text("base_url: https://api.example\n", encoding="utf-8")


class TestInstallContract:
    """Contract tests for `install`."""

    def test_install_importable_from_facade(self):
        """The `install` hook is importable from the plugins cell facade."""
        from goga_tool_pybuggy.plugins import install as install_direct

        assert install_direct is goga_tool_pybuggy.plugins.install

    def test_install_is_callable(self):
        """The `install` hook is callable."""
        assert callable(goga_tool_pybuggy.plugins.install)

    def test_install_signature_accepts_kwargs(self):
        """The `install` signature accepts arbitrary keyword arguments via `**kwargs`."""
        signature = inspect.signature(goga_tool_pybuggy.plugins.install)

        var_keyword = [param for param in signature.parameters.values() if param.kind == inspect.Parameter.VAR_KEYWORD]
        assert len(var_keyword) == 1
        assert var_keyword[0].name == "kwargs"

    def test_web_plugin_reexported_by_the_facade(self):
        """`WebPlugin` is re-exported by the plugins facade alongside the other plugin classes."""
        from goga_tool_pybuggy.plugins.web_plugin import WebPlugin

        assert goga_tool_pybuggy.plugins.WebPlugin is WebPlugin
        assert "WebPlugin" in goga_tool_pybuggy.plugins.__all__


class TestInstallLogic:
    """Behavioral logic tests for `install`."""

    def test_install_wires_hooks_into_namespace(self, tmp_path, monkeypatch):
        # No `api/` tree so the default loader package is a no-op; the api document opens the gate.
        write_api_document(tmp_path)
        monkeypatch.chdir(tmp_path)

        namespace = types.ModuleType("ctx")
        goga_tool_pybuggy.plugins.install(context=namespace.__dict__)

        assert callable(namespace.pytest_addoption)
        assert callable(namespace.pytest_configure)
        assert "pytest_plugins" in namespace.__dict__

    def test_install_outside_api_tree_does_not_raise(self, tmp_path, monkeypatch):
        # Without an `api/` tree the default package loader is optional — `install()` must not raise.
        write_api_document(tmp_path)
        monkeypatch.chdir(tmp_path)

        # Re-import the module against this cwd, then run a real install into a fresh namespace.
        importlib.reload(goga_tool_pybuggy.plugins)

        namespace = types.ModuleType("ctx")
        goga_tool_pybuggy.plugins.install(context=namespace.__dict__)

        assert callable(namespace.pytest_addoption)
        assert callable(namespace.pytest_configure)
        assert namespace.__dict__["pytest_plugins"] == []

    def test_install_appends_the_sandbox_plugin_when_the_document_is_present(self, tmp_path, monkeypatch):
        """With the document, one installation call carries both plugins — the sandbox plugin
        unconfigured (its activation is built at configphase, not here)."""
        write_document(tmp_path)
        write_api_document(tmp_path)
        monkeypatch.chdir(tmp_path)

        context: dict[str, object] = {}
        captured: dict[str, object] = {}

        def fake_install(*plugins: object, context: dict[str, object] | None = None) -> None:
            captured["plugins"] = list(plugins)

        monkeypatch.setattr(goga_tool_pybuggy.plugins, "install_pytest_plugins", fake_install)

        goga_tool_pybuggy.plugins.install(context=context)

        plugins = captured["plugins"]

        assert len(plugins) == 2
        assert isinstance(plugins[0], goga_tool_pybuggy.plugins.ApiPlugin)
        assert isinstance(plugins[1], SandboxPlugin)
        assert plugins[1].activation is None  # configure builds it, not install
        assert not hasattr(plugins[0], "sandbox_activation")

    def test_install_with_only_the_api_document_installs_the_api_plugin_alone(self, tmp_path, monkeypatch):
        """The api document alone opens the api gate and no other plugin joins the installation."""
        write_api_document(tmp_path)
        monkeypatch.chdir(tmp_path)

        context: dict[str, object] = {}
        captured: dict[str, object] = {}

        def fake_install(*plugins: object, context: dict[str, object] | None = None) -> None:
            captured["plugins"] = list(plugins)

        monkeypatch.setattr(goga_tool_pybuggy.plugins, "install_pytest_plugins", fake_install)

        goga_tool_pybuggy.plugins.install(context=context)

        plugins = captured["plugins"]

        assert len(plugins) == 1
        assert isinstance(plugins[0], goga_tool_pybuggy.plugins.ApiPlugin)

    def test_install_gates_the_api_plugin_on_the_document_only(self, tmp_path, monkeypatch):
        """The api document alone gates the api plugin — ``BASE_URL`` is a value source, never
        an activation source — and without the document the hooks still land in the namespace
        (a web-only or sandbox-only project registers nothing api-related)."""
        monkeypatch.chdir(tmp_path)

        captured: dict[str, object] = {}

        def fake_install(*plugins: object, context: dict[str, object] | None = None) -> None:
            captured["plugins"] = list(plugins)

        monkeypatch.setattr(goga_tool_pybuggy.plugins, "install_pytest_plugins", fake_install)

        # Case A: the api document opens the gate (a set BASE_URL is neither required nor an opener).
        write_api_document(tmp_path)
        monkeypatch.setenv("BASE_URL", "https://env.example")

        goga_tool_pybuggy.plugins.install(context={})

        assert len(captured["plugins"]) == 1
        assert isinstance(captured["plugins"][0], goga_tool_pybuggy.plugins.ApiPlugin)

        # Case B: the env var alone does not open the gate (the document removed).
        (tmp_path / ".goga" / "tools" / "pybuggy" / "api.yml").unlink()

        goga_tool_pybuggy.plugins.install(context={})

        assert captured["plugins"] == []

        # Case C: no document and no env — the hooks still injected, nothing api-related set.
        monkeypatch.delenv("BASE_URL", raising=False)
        monkeypatch.setattr(goga_tool_pybuggy.plugins, "install_pytest_plugins", install_pytest_plugins)
        namespace = types.ModuleType("ctx")

        with mock.patch("goga_tool_pybuggy.plugins.ApiPlugin") as api_plugin:
            goga_tool_pybuggy.plugins.install(context=namespace.__dict__)

            api_plugin.assert_not_called()

        assert callable(namespace.pytest_addoption)
        assert callable(namespace.pytest_configure)
        assert "pytest_plugins" not in namespace.__dict__

    def test_install_forwards_the_named_surface_to_every_plugin(self, tmp_path, monkeypatch):
        """Every plugin is constructed by name — the shared context/loaders reach all three, the
        api-specific defaults reach the api plugin alone."""
        write_api_document(tmp_path)
        sandbox_document = tmp_path / ".goga" / "tools" / "pybuggy" / "sandbox.yml"
        web_document = tmp_path / ".goga" / "tools" / "pybuggy" / "web.yml"
        for document in (sandbox_document, web_document):
            document.parent.mkdir(parents=True, exist_ok=True)
        sandbox_document.write_text(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\n", encoding="utf-8"
        )
        web_document.write_text("provider: openai\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        sentinel = ModuleLoader("some.fixtures", required=False)
        context: dict[str, object] = {}

        with (
            mock.patch("goga_tool_pybuggy.plugins.ApiPlugin") as api_plugin,
            mock.patch("goga_tool_pybuggy.plugins.SandboxPlugin") as sandbox_plugin,
            mock.patch("goga_tool_pybuggy.plugins.WebPlugin") as web_plugin,
        ):
            goga_tool_pybuggy.plugins.install(
                context=context, loaders=[sentinel], default_retries=5, default_assert_timeout=9
            )

            # The context dict is later mutated by the hook injection — assert by identity.
            api_plugin.assert_called_once_with(
                context=context,
                loaders=[sentinel],
                default_retries=5,
                default_assert_timeout=9,
                default_assert_delay=None,
            )
            sandbox_plugin.assert_called_once()
            web_plugin.assert_called_once()
            assert sandbox_plugin.call_args.kwargs["context"] is context
            assert sandbox_plugin.call_args.kwargs["loaders"] == [sentinel]
            assert web_plugin.call_args.kwargs["context"] is context
            assert web_plugin.call_args.kwargs["loaders"] == [sentinel]

    def test_install_with_both_documents_carries_the_three_plugins_in_order(self, tmp_path, monkeypatch):
        """A project with all documents (a both-kind session) carries all three plugins in order.

        The three gates are independent: the web append neither disturbs the sandbox
        append nor the leading ApiPlugin, and one installation call carries the trio.
        """
        write_document(tmp_path)
        write_api_document(tmp_path)
        web_document = tmp_path / ".goga" / "tools" / "pybuggy" / "web.yml"
        web_document.write_text("provider: openai\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        captured: dict[str, object] = {}

        def fake_install(*plugins: object, context: dict[str, object] | None = None) -> None:
            captured["plugins"] = list(plugins)

        monkeypatch.setattr(goga_tool_pybuggy.plugins, "install_pytest_plugins", fake_install)

        goga_tool_pybuggy.plugins.install(context={})

        assert [type(plugin) for plugin in captured["plugins"]] == [
            goga_tool_pybuggy.plugins.ApiPlugin,
            SandboxPlugin,
            goga_tool_pybuggy.plugins.WebPlugin,
        ]

    def test_install_gates_web_plugin_on_document_presence(self, tmp_path, monkeypatch):
        """The web document gates the web plugin by presence only — with it ``WebPlugin`` joins
        the installation carrying the namespace and the explicit loaders; without it nothing
        web-related is registered, and the api/sandbox gating stays keyed on their own documents."""
        namespace = types.ModuleType("ctx")
        web_document = tmp_path / ".goga" / "tools" / "pybuggy" / "web.yml"
        web_document.parent.mkdir(parents=True)

        # Case A: the web document present — the web plugin joins, the other gates stay shut.
        web_document.write_text("provider: openai\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch("goga_tool_pybuggy.plugins.ApiPlugin"),
            mock.patch("goga_tool_pybuggy.plugins.WebPlugin") as web_plugin,
            mock.patch("goga_tool_pybuggy.plugins.SandboxPlugin") as sandbox_plugin,
        ):
            goga_tool_pybuggy.plugins.install(context=namespace.__dict__)

            web_plugin.assert_called_once_with(context=namespace.__dict__, loaders=None)
            sandbox_plugin.assert_not_called()  # no sandbox.yml — its own gate decides

        assert callable(namespace.pytest_addoption)  # the hooks land whatever the gates decide
        assert callable(namespace.pytest_configure)

        # Case B: no web document — the web plugin is never constructed.
        web_document.unlink()

        with (
            mock.patch("goga_tool_pybuggy.plugins.ApiPlugin"),
            mock.patch("goga_tool_pybuggy.plugins.WebPlugin") as web_plugin,
            mock.patch("goga_tool_pybuggy.plugins.SandboxPlugin") as sandbox_plugin,
        ):
            goga_tool_pybuggy.plugins.install(context=namespace.__dict__)

            web_plugin.assert_not_called()
            sandbox_plugin.assert_not_called()

    def test_install_web_gate_performs_no_validation(self, tmp_path, monkeypatch):
        """An invalid web document still passes the presence-only gate — structure and
        semantics are validated by the web plugin itself at configphase, never here."""
        document = tmp_path / ".goga" / "tools" / "pybuggy" / "web.yml"
        document.parent.mkdir(parents=True)
        document.write_text("provider: nope\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        namespace = types.ModuleType("ctx")

        with mock.patch("goga_tool_pybuggy.plugins.WebPlugin") as web_plugin:
            goga_tool_pybuggy.plugins.install(context=namespace.__dict__)

        web_plugin.assert_called_once_with(context=namespace.__dict__, loaders=None)

    def test_invalid_document_fails_at_configure_not_at_install(self, tmp_path, monkeypatch):
        """An invalid document passes the presence gate and fails at the configure step —
        still before any container, with the validation error of the config cell."""
        document = tmp_path / ".goga" / "tools" / "pybuggy" / "sandbox.yml"
        document.parent.mkdir(parents=True)
        document.write_text(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\nservices:\n  cache: { kind: mysql }\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        captured: dict[str, object] = {}

        def fake_install(*plugins: object, context: dict[str, object] | None = None) -> None:
            captured["plugins"] = list(plugins)

        monkeypatch.setattr(goga_tool_pybuggy.plugins, "install_pytest_plugins", fake_install)

        goga_tool_pybuggy.plugins.install(context={})

        sandbox_plugin = captured["plugins"][0]

        assert isinstance(sandbox_plugin, SandboxPlugin)
        assert sandbox_plugin.activation is None

        sandbox_plugin.init_pytest_config(mock.Mock())

        with pytest.raises(
            ValueError, match=r"mysql.*not one of the supported kinds \(postgresql, kafka, vault, http, redis\)"
        ):
            sandbox_plugin.configure()

        assert sandbox_plugin.activation is None

    def test_install_normalizes_the_container_host_with_the_document(self, tmp_path, monkeypatch):
        """With the document present, install() defaults the container-host override — the
        sandbox gets its one shared address space before any container or configure step."""
        from goga_tool_pybuggy.sandbox.engines import runtime as runtime_module

        config = types.SimpleNamespace(tc_host_override=None)
        monkeypatch.setattr(runtime_module, "testcontainers_config", config)

        write_document(tmp_path)
        monkeypatch.chdir(tmp_path)

        monkeypatch.delenv("TESTCONTAINERS_HOST_OVERRIDE", raising=False)

        def fake_install(*plugins: object, context: dict[str, object] | None = None) -> None:
            pass

        monkeypatch.setattr(goga_tool_pybuggy.plugins, "install_pytest_plugins", fake_install)

        goga_tool_pybuggy.plugins.install(context={})

        assert "TESTCONTAINERS_HOST_OVERRIDE" in os.environ
        assert config.tc_host_override is not None

    def test_install_without_document_leaves_the_environment_untouched(self, tmp_path, monkeypatch):
        """Without the document the container-host normalization never runs — no sandbox,
        no environment changes."""
        monkeypatch.chdir(tmp_path)  # empty cwd — no sandbox document

        monkeypatch.delenv("TESTCONTAINERS_HOST_OVERRIDE", raising=False)

        def unexpected() -> None:
            raise AssertionError("normalization must not run without the sandbox document")

        monkeypatch.setattr(goga_tool_pybuggy.plugins, "normalize_container_host", unexpected)

        def fake_install(*plugins: object, context: dict[str, object] | None = None) -> None:
            pass

        monkeypatch.setattr(goga_tool_pybuggy.plugins, "install_pytest_plugins", fake_install)

        goga_tool_pybuggy.plugins.install(context={})

        assert "TESTCONTAINERS_HOST_OVERRIDE" not in os.environ
