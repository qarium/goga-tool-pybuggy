"""Tests for `install` in the `goga_tool_pybuggy.plugin` cell.

Covers the contract surface and the import-time wiring (hook injection + synchronous ``pytest_plugins`` population)
plus the presence gate of the sandbox plugin.
"""

import importlib
import inspect
import os
import sys
import types
from unittest import mock

import goga_tool_pybuggy.plugin
import pytest
from goga_tool_pybuggy.plugin import SandboxPlugin


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


class TestInstallContract:
    """Contract tests for `install`."""

    def test_install_importable_from_facade(self):
        """The `install` hook is importable from the plugin cell facade."""
        from goga_tool_pybuggy.plugin import install as install_direct

        assert install_direct is goga_tool_pybuggy.plugin.install

    def test_install_is_callable(self):
        """The `install` hook is callable."""
        assert callable(goga_tool_pybuggy.plugin.install)

    def test_install_signature_accepts_kwargs(self):
        """The `install` signature accepts arbitrary keyword arguments via `**kwargs`."""
        signature = inspect.signature(goga_tool_pybuggy.plugin.install)

        var_keyword = [param for param in signature.parameters.values() if param.kind == inspect.Parameter.VAR_KEYWORD]
        assert len(var_keyword) == 1
        assert var_keyword[0].name == "kwargs"


class TestInstallLogic:
    """Behavioral logic tests for `install`."""

    def test_install_wires_hooks_into_namespace(self, tmp_path, monkeypatch):
        # No `api/` tree so the default loader package is a no-op.
        monkeypatch.chdir(tmp_path)

        namespace = types.ModuleType("ctx")
        goga_tool_pybuggy.plugin.install(context=namespace.__dict__)

        assert callable(namespace.pytest_addoption)
        assert callable(namespace.pytest_configure)
        assert "pytest_plugins" in namespace.__dict__

    def test_install_outside_api_tree_does_not_raise(self, tmp_path, monkeypatch):
        # Without an `api/` tree the default package loader is optional — `install()` must not raise.
        monkeypatch.chdir(tmp_path)

        # Re-import the module against this cwd, then run a real install into a fresh namespace.
        importlib.reload(goga_tool_pybuggy.plugin)

        namespace = types.ModuleType("ctx")
        goga_tool_pybuggy.plugin.install(context=namespace.__dict__)

        assert callable(namespace.pytest_addoption)
        assert callable(namespace.pytest_configure)
        assert namespace.__dict__["pytest_plugins"] == []

    def test_install_appends_the_sandbox_plugin_when_the_document_is_present(self, tmp_path, monkeypatch):
        """With the document, one installation call carries both plugins — the sandbox plugin
        unconfigured (its activation is built at configphase, not here)."""
        write_document(tmp_path)
        monkeypatch.chdir(tmp_path)

        context: dict[str, object] = {}
        captured: dict[str, object] = {}

        def fake_install(*plugins: object, context: dict[str, object] | None = None) -> None:
            captured["plugins"] = list(plugins)

        monkeypatch.setattr(goga_tool_pybuggy.plugin, "install_pytest_plugins", fake_install)

        goga_tool_pybuggy.plugin.install(context=context)

        plugins = captured["plugins"]

        assert len(plugins) == 2
        assert isinstance(plugins[0], goga_tool_pybuggy.plugin.ApiPlugin)
        assert isinstance(plugins[1], SandboxPlugin)
        assert plugins[1].activation is None  # configure builds it, not install
        assert not hasattr(plugins[0], "sandbox_activation")

    def test_install_without_document_installs_the_api_plugin_alone(self, tmp_path, monkeypatch):
        """Without the tools-home document no sandbox plugin joins the installation."""
        monkeypatch.chdir(tmp_path)  # no .goga/tools/pybuggy/sandbox.yml in the empty cwd

        context: dict[str, object] = {}
        captured: dict[str, object] = {}

        def fake_install(*plugins: object, context: dict[str, object] | None = None) -> None:
            captured["plugins"] = list(plugins)

        monkeypatch.setattr(goga_tool_pybuggy.plugin, "install_pytest_plugins", fake_install)

        goga_tool_pybuggy.plugin.install(context=context)

        plugins = captured["plugins"]

        assert len(plugins) == 1
        assert isinstance(plugins[0], goga_tool_pybuggy.plugin.ApiPlugin)

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

        monkeypatch.setattr(goga_tool_pybuggy.plugin, "install_pytest_plugins", fake_install)

        goga_tool_pybuggy.plugin.install(context={})

        sandbox_plugin = captured["plugins"][1]

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

        monkeypatch.setattr(goga_tool_pybuggy.plugin, "install_pytest_plugins", fake_install)

        goga_tool_pybuggy.plugin.install(context={})

        assert "TESTCONTAINERS_HOST_OVERRIDE" in os.environ
        assert config.tc_host_override is not None

    def test_install_without_document_leaves_the_environment_untouched(self, tmp_path, monkeypatch):
        """Without the document the container-host normalization never runs — no sandbox,
        no environment changes."""
        monkeypatch.chdir(tmp_path)  # empty cwd — no sandbox document
        monkeypatch.delenv("TESTCONTAINERS_HOST_OVERRIDE", raising=False)

        def unexpected() -> None:
            raise AssertionError("normalization must not run without the sandbox document")

        monkeypatch.setattr(goga_tool_pybuggy.plugin, "normalize_container_host", unexpected)

        def fake_install(*plugins: object, context: dict[str, object] | None = None) -> None:
            pass

        monkeypatch.setattr(goga_tool_pybuggy.plugin, "install_pytest_plugins", fake_install)

        goga_tool_pybuggy.plugin.install(context={})

        assert "TESTCONTAINERS_HOST_OVERRIDE" not in os.environ
