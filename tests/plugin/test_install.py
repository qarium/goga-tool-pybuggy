"""Tests for `install` in the `goga_tool_pybuggy.plugin` cell.

Covers the contract surface and the import-time wiring (hook injection + synchronous ``pytest_plugins`` population).
"""

import importlib
import inspect
import sys
import types

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
