"""Integration tests for the `goga_tool_pybuggy.plugin` cell (end-to-end).

Mirrors the source layout (``tests/plugin/test_integration.py``). Covers the
cross-cell and end-to-end acceptance scenarios from the design's Test Stack
Trace:

- the wiring chain (``install`` -> ``ApiPlugin`` ->
  ``install_pytest_plugins`` + ``_load_plugins``); and
- the full ``goga_tool_pybuggy.plugin.install()`` enablement run as a real pytest subprocess
  (hook injection, ``--api-url`` CLI registration, recursive generated-fixture
  loading, and the ``api`` fixture resolving into a working ``Api``).

Environment notes (the plugin under test is unchanged against the real packages):

- ``goga_tool_pybuggy`` is not pip-installed here — it imports only off its source root —
  so the subprocess is given the source root via ``PYTHONPATH``.
- the env ships an empty ``resq`` stub (no ``Session``); constructing an ``Api``
  performs no network I/O, so the generated project's ``conftest.py`` provides a
  minimal ``Session`` stand-in (the real ``resq`` provides one).
"""

import os
import pathlib
import subprocess
import sys
import types

import goga_tool_pybuggy
import pytest
from goga_tool_pybuggy.plugin import install

# Source root that makes `goga_tool_pybuggy` importable in the subprocess.
_PROJECT_ROOT = str(pathlib.Path(goga_tool_pybuggy.__file__).resolve().parent.parent)

# A `@pytest.fixture` so the trial-import probe recognizes the module as a pytest
# plugin. Used for the in-process wiring test where the body is never invoked, so
# it carries no Api/Endpoint dependency.
_PLUGIN_MODULE_SOURCE = """\
import pytest


@pytest.fixture
def get_orders():
    return 1
"""

# The canonical generated-fixture module from `enable.md`: `get_orders` depends
# on the `api` fixture and returns an `Endpoint`.
_GENERATED_FIXTURE_SOURCE = """\
import pytest

from goga_tool_pybuggy.api import Api, Endpoint


@pytest.fixture
def get_orders(api: Api) -> Endpoint:
    return Endpoint(api, "/orders", method="GET")
"""

# conftest.py for the end-to-end subprocess project — enables the plugin exactly
# as documented in `enable.md` (an explicit `install()` call; there is no
# import-time auto-wiring), plus the `resq` env shim described above.
_CONFTEST_SOURCE = """\
import resq

if not hasattr(resq, "Session"):

    class _Session:
        def __init__(self, base_url, timeout=None):
            self.base_url = base_url
            self.timeout = timeout

    resq.Session = _Session

import goga_tool_pybuggy.plugin

goga_tool_pybuggy.plugin.install()
"""

# A consumer test: uses the discovered `get_orders` fixture (exercising the full
# recursive-loading + `api`-fixture chain) and asserts the `--api-url` CLI option
# was registered by the plugin's `pytest_addoption` hook.
_TEST_SOURCE = """\
def test_get_orders_fixture_resolves(get_orders):
    # Resolving the generated fixture proves recursive pytest_plugins loading
    # worked and the `api` fixture resolved into a working Api/Endpoint.
    assert get_orders is not None
    assert get_orders.url_path == "/orders"


def test_api_url_option_registered(pytestconfig):
    # `--api-url` was registered by the plugin's pytest_addoption hook; getoption
    # raises ValueError for an unknown option.
    pytestconfig.getoption("--api-url")
"""


def _make_api_tree(base):
    """Create a one-fixture `api/orders/get_orders/api.py` package tree under `base`."""
    pkg = base / "api"
    (pkg / "orders" / "get_orders").mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "orders" / "__init__.py").write_text("")
    (pkg / "orders" / "get_orders" / "__init__.py").write_text("")
    return pkg / "orders" / "get_orders" / "api.py"


@pytest.fixture(autouse=True)
def _isolate_sys_modules():
    """Snapshot and restore sys.modules so trial imports never leak across tests."""
    snapshot = sys.modules.copy()
    yield
    extra = set(sys.modules) - set(snapshot)
    for key in extra:
        del sys.modules[key]


class TestPluginIntegration:
    """Cross-cell integration: the import-time wiring chain."""

    def test_install_wires_hooks_into_namespace(self, tmp_path, monkeypatch):
        # The api/ tree makes _load_plugins (goga_tool_pybuggy.plugin -> goga_tool_pybuggy.plugin.loaders)
        # discover a real generated-fixture module into the namespace.
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)
        _make_api_tree(tmp_path).write_text(_PLUGIN_MODULE_SOURCE)

        namespace = types.ModuleType("ctx")
        install(context=namespace.__dict__)

        # install_pytest_plugins injected the pytest hooks into the namespace.
        assert callable(namespace.pytest_addoption)
        assert callable(namespace.pytest_configure)
        # _load_plugins populated pytest_plugins synchronously from the api/ tree
        # (cross-entity: install -> ApiPlugin -> install_pytest_plugins + _load_plugins).
        assert "pytest_plugins" in namespace.__dict__
        assert namespace.pytest_plugins == ["api.orders.get_orders.api"]


class TestPluginEndToEnd:
    """End-to-end: a real pytest subprocess enabling the plugin."""

    def test_plugin_end_to_end_pytest_loads_generated_fixture(self, tmp_path):
        # --- the generated-fixture project, as documented in `enable.md` ---
        _make_api_tree(tmp_path).write_text(_GENERATED_FIXTURE_SOURCE)
        (tmp_path / "conftest.py").write_text(_CONFTEST_SOURCE)

        config_dir = tmp_path / ".goga" / "tools" / "pybuggy"
        config_dir.mkdir(parents=True)
        (config_dir / "config.yml").write_text("base_url: https://x.example\n")

        (tmp_path / "test_generated_fixtures.py").write_text(_TEST_SOURCE)

        env = {**os.environ, "PYTHONPATH": _PROJECT_ROOT}

        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(tmp_path), "-v", "-p", "no:cacheprovider"],
            cwd=str(tmp_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        output = result.stdout + result.stderr
        assert result.returncode == 0, output
        # The generated fixture was collected & resolved (recursive loading) and
        # the --api-url option was registered.
        assert "test_get_orders_fixture_resolves" in output
        assert "test_api_url_option_registered" in output
