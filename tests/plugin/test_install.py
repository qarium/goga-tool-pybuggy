"""Tests for `install` in the `pybuggy.plugin` cell.

Mirrors the source layout (`tests/plugin/test_install.py`). Covers the contract
surface (importability from the facade + the ``**kwargs`` signature) and the
behavioral logic of the import-time wiring (hook injection + synchronous
``pytest_plugins`` population).

The integration-flavored test uses an explicit ``context=`` so it does not depend
on the call stack; the ``call_context()`` stack invariant is exercised separately
by the top-level ``install()`` call that runs on import.
"""

import importlib
import inspect
import sys
import types

import pybuggy.plugin
import pytest


@pytest.fixture(autouse=True)
def isolate_sys_modules():
    """Snapshot and restore sys.modules so import-time trial imports never leak.

    ``test_install_outside_api_tree_does_not_raise`` reloads ``pybuggy.plugin``,
    which re-runs the top-level ``install()`` (and thus ``_load_plugins``); the
    loaders and integration suites already isolate ``sys.modules`` the same way.
    """
    snapshot = sys.modules.copy()

    yield

    extra = set(sys.modules) - set(snapshot)
    for key in extra:
        del sys.modules[key]


class TestInstallContract:
    """Contract tests for `install`."""

    def test_install_importable_from_facade(self):
        from pybuggy.plugin import install as install_direct

        assert install_direct is pybuggy.plugin.install

    def test_install_is_callable(self):
        assert callable(pybuggy.plugin.install)

    def test_install_signature_accepts_kwargs(self):
        signature = inspect.signature(pybuggy.plugin.install)

        var_keyword = [param for param in signature.parameters.values() if param.kind == inspect.Parameter.VAR_KEYWORD]
        assert len(var_keyword) == 1
        assert var_keyword[0].name == "kwargs"


class TestInstallLogic:
    """Behavioral logic tests for `install`."""

    def test_install_wires_hooks_into_namespace(self, tmp_path, monkeypatch):
        # No `api/` tree so the default loader package is a no-op.
        monkeypatch.chdir(tmp_path)

        namespace = types.ModuleType("ctx")
        pybuggy.plugin.install(context=namespace.__dict__)

        assert callable(namespace.pytest_addoption)
        assert callable(namespace.pytest_configure)
        assert "pytest_plugins" in namespace.__dict__

    def test_install_outside_api_tree_does_not_raise(self, tmp_path, monkeypatch):
        # cwd without an `api/` tree: the top-level `install()` (which runs on
        # import) must not raise — the default `api` package is optional.
        monkeypatch.chdir(tmp_path)

        # Force a fresh re-execution of the module body so the top-level
        # `install()` runs against this cwd.
        importlib.reload(pybuggy.plugin)

        assert getattr(pybuggy.plugin, "pytest_plugins", []) == []
