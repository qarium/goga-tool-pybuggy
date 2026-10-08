"""Tests for `install` in the `goga_tool_pybuggy.plugin` cell.

Covers the contract surface and the import-time wiring (hook injection + synchronous ``pytest_plugins`` population).
"""

import importlib
import inspect
import sys
import types
from unittest import mock

import goga_tool_pybuggy.plugin
import pytest


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

    def test_install_arms_sandbox_with_defaulted_context(self, tmp_path, monkeypatch):
        """`install()` calls `activate_sandbox` with the defaulted context before constructing the plugin."""
        monkeypatch.chdir(tmp_path)

        context: dict[str, object] = {}
        fake_activate = mock.Mock(return_value=None)
        monkeypatch.setattr(goga_tool_pybuggy.plugin, "activate_sandbox", fake_activate)

        goga_tool_pybuggy.plugin.install(context=context)

        fake_activate.assert_called_once_with(context)


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
        # Without an `api/` tree the import-time `install()` must not raise (the default package is optional).
        monkeypatch.chdir(tmp_path)

        # Re-execute the module body so the top-level `install()` runs against this cwd.
        importlib.reload(goga_tool_pybuggy.plugin)

        assert getattr(goga_tool_pybuggy.plugin, "pytest_plugins", []) == []

    def test_install_arms_sandbox_and_keeps_activation_on_plugin(self, tmp_path, monkeypatch):
        """The activation returned by `activate_sandbox` is kept on the constructed plugin."""
        monkeypatch.chdir(tmp_path)

        context: dict[str, object] = {}
        sentinel = object()
        captured: dict[str, object] = {}

        def fake_install(plugin: object, context: dict[str, object] | None = None) -> None:
            captured["plugin"] = plugin

        fake_activate = mock.Mock(return_value=sentinel)
        monkeypatch.setattr(goga_tool_pybuggy.plugin, "activate_sandbox", fake_activate)
        monkeypatch.setattr(goga_tool_pybuggy.plugin, "install_pytest_plugins", fake_install)

        goga_tool_pybuggy.plugin.install(context=context)

        fake_activate.assert_called_once_with(context)
        assert captured["plugin"].sandbox_activation is sentinel

    def test_install_without_document_leaves_plugin_unarmed(self, tmp_path, monkeypatch):
        """Without the tools-home document the arming is inert and the plugin stays unarmed."""
        monkeypatch.chdir(tmp_path)  # no .goga/tools/pybuggy/sandbox.yml in the empty cwd

        context: dict[str, object] = {}
        captured: dict[str, object] = {}

        def fake_install(plugin: object, context: dict[str, object] | None = None) -> None:
            captured["plugin"] = plugin

        monkeypatch.setattr(goga_tool_pybuggy.plugin, "install_pytest_plugins", fake_install)

        goga_tool_pybuggy.plugin.install(context=context)

        assert captured["plugin"].sandbox_activation is None

    def test_install_arms_sandbox_through_new_path(self, tmp_path, monkeypatch):
        """A document under the pybuggy tools home arms the plugin; without it the arming is inert.

        The armed leg pins the new resolution path (``.goga/tools/pybuggy/sandbox.yml`` under
        the CWD): ``install`` composes the real activation — the lifecycle hooks land in the
        context, the plugin is constructed with ``sandbox_activation`` set. The negative leg
        pins full inertness: no document, no hooks, unarmed plugin.
        """
        from goga_tool_pybuggy.sandbox import activation as activation_module
        from goga_tool_pybuggy.sandbox.config import SandboxConfig

        document = tmp_path / ".goga" / "tools" / "pybuggy" / "sandbox.yml"
        document.parent.mkdir(parents=True)
        document.write_text(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\nservices:\n  db: { kind: postgresql }\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)

        context: dict[str, object] = {}
        captured: dict[str, object] = {}

        def fake_install(plugin: object, context: dict[str, object] | None = None) -> None:
            captured["plugin"] = plugin

        monkeypatch.setattr(goga_tool_pybuggy.plugin, "install_pytest_plugins", fake_install)

        try:
            goga_tool_pybuggy.plugin.install(context=context)
        finally:
            activation_module._ARMED = None  # do not leak the armed state into other tests

        for hook in ("pytest_sessionstart", "pytest_sessionfinish", "pytest_runtest_setup"):
            assert callable(context[hook]), hook

        activation = captured["plugin"].sandbox_activation

        assert isinstance(activation, SandboxConfig)
        assert activation.instance.image == "my-service:latest"

        context = {}
        captured.clear()
        inert_cwd = tmp_path / "inert-cwd"
        inert_cwd.mkdir()
        monkeypatch.chdir(inert_cwd)

        goga_tool_pybuggy.plugin.install(context=context)

        assert captured["plugin"].sandbox_activation is None
        for hook in ("pytest_sessionstart", "pytest_sessionfinish", "pytest_runtest_setup"):
            assert hook not in context, hook
