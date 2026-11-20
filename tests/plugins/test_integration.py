"""Integration tests for the `goga_tool_pybuggy.plugins` cell (end-to-end).

Covers the wiring chain and a real pytest subprocess run (source root via ``PYTHONPATH``; conftest shims ``resq``).
"""

import os
import pathlib
import subprocess
import sys
import types

import goga_tool_pybuggy
import pytest
from goga_tool_pybuggy.plugins import install

# Source root that makes `goga_tool_pybuggy` importable in the subprocess.
_PROJECT_ROOT = str(pathlib.Path(goga_tool_pybuggy.__file__).resolve().parent.parent)

# Fixture-only module for the in-process wiring test (the body is never invoked).
_PLUGIN_MODULE_SOURCE = """\
import pytest


@pytest.fixture
def get_orders():
    return 1
"""

# The canonical generated-fixture module from `enable.md`: `get_orders` returns an `Endpoint`.
_GENERATED_FIXTURE_SOURCE = """\
import pytest

from goga_tool_pybuggy.api import Api, Endpoint


@pytest.fixture
def get_orders(api: Api) -> Endpoint:
    return Endpoint(api, "/orders", method="GET")
"""

# conftest.py for the subprocess project: an explicit `install()` call plus the `resq` shim.
_CONFTEST_SOURCE = """\
import resq

if not hasattr(resq, "Session"):

    class _Session:
        def __init__(self, base_url, adapter, timeout=None):
            self.base_url = base_url
            self.adapter = adapter
            self.timeout = timeout

        def close(self):
            # No-op stand-in for resq.Session.close() (sync mode is a no-op).
            pass

    resq.Session = _Session

import goga_tool_pybuggy.plugins

goga_tool_pybuggy.plugins.install()
"""

# Consumer test: resolves the discovered fixture and checks `--base-url` registration/override.
_TEST_SOURCE = """\
def test_get_orders_fixture_resolves(get_orders):
    # Resolving the generated fixture proves recursive pytest_plugins loading
    # worked and the `api` fixture resolved into a working Api/Endpoint.
    assert get_orders is not None
    assert get_orders.url_path == "/orders"


def test_base_url_option_registered(pytestconfig):
    # `--base-url` was registered by the plugin's pytest_addoption hook; getoption
    # raises ValueError for an unknown option.
    pytestconfig.getoption("--base-url")


def test_base_url_cli_overrides_config(api):
    # api.yml sets base_url: https://x.example; the run passes
    # --base-url https://cli.example -> the typed CLI value wins.
    assert api.base_url == "https://cli.example"
"""

# The consumer conftest of the web kind exactly as the bootstrap delivers it (the fixed template).
_BOOTSTRAP_CONFTEST_SOURCE = """\
from dotenv import load_dotenv

load_dotenv()

from goga_tool_pybuggy import plugins

plugins.install()
"""

# The surveyed-minimum web document a kind=web session writes.
_WEB_CONFIG_SOURCE = """\
provider: openai
generation_model: g
classification_model: c
browser:
  name: chromium
  headless: true
strict: false
interactive: false
"""

# The surveyed minimum plus a document-level generation prompt — the per-test extras of the
# stacked decorators must append after the document text.
_WEB_PROMPT_CONFIG_SOURCE = _WEB_CONFIG_SOURCE + "generation_prompt: global instructions\n"

# Consumer test of the web kind: the web fixture resolves, both CLI options registered,
# and no api surface exists (the api plugin gated off registers nothing).
_WEB_TEST_SOURCE = """\
import pytest


def test_web_fixture_resolves(web):
    assert web is not None


def test_web_options_registered(pytestconfig):
    # getoption raises ValueError for an unknown option — both flags were registered.
    pytestconfig.getoption("--strict-mode")
    pytestconfig.getoption("--interactive")


def test_web_only_run_registers_no_api_options(pytestconfig):
    # No api.yml and no BASE_URL — the api plugin never installs, so its option never registers.
    with pytest.raises(ValueError):
        pytestconfig.getoption("--base-url")
"""

# Consumer test of the per-test generation-prompt decorator: stacked applications compose through
# real pytest marker iteration — the bottom decorator's marker lands first in the item's mark
# list, the fixture reverses to written order and appends after the document prompt. The module
# wraps the plugin cell's `build_pretty_config` with a delegating recorder (the runtime exposes
# no config surface), so the real routine still builds the value the test asserts. The decorator
# comes from the root facade; an unregistered marker fails the run via -W error.
_WEB_PROMPT_TEST_SOURCE = """\
from pathlib import Path

import goga_tool_pybuggy.plugins.web_plugin as web_plugin_module
from goga_tool_pybuggy import generation_prompt

_real_build_pretty_config = web_plugin_module.build_pretty_config


def _recording_build_pretty_config(config, strict_flag, interactive_flag, prompt_extra=""):
    built = _real_build_pretty_config(config, strict_flag, interactive_flag, prompt_extra=prompt_extra)
    Path("recorded_prompt.txt").write_text(built.generation_prompt, encoding="utf-8")

    return built


web_plugin_module.build_pretty_config = _recording_build_pretty_config


@generation_prompt("top text")
@generation_prompt("bottom text")
def test_stacked_generation_prompt_composes_in_written_order(web):
    assert web is not None
    assert Path("recorded_prompt.txt").read_text(encoding="utf-8") == "global instructions\\ntop text\\nbottom text"
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
        # The api/ tree lets _load_plugins discover a real generated-fixture module;
        # the api document opens the installation gate.
        monkeypatch.syspath_prepend(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("BASE_URL", raising=False)
        _make_api_tree(tmp_path).write_text(_PLUGIN_MODULE_SOURCE)

        config_dir = tmp_path / ".goga" / "tools" / "pybuggy"
        config_dir.mkdir(parents=True)
        (config_dir / "api.yml").write_text("base_url: https://x.example\n")

        namespace = types.ModuleType("ctx")
        install(context=namespace.__dict__)

        # install_pytest_plugins injected the pytest hooks into the namespace.
        assert callable(namespace.pytest_addoption)
        assert callable(namespace.pytest_configure)
        # _load_plugins populated pytest_plugins synchronously from the api/ tree.
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
        (config_dir / "api.yml").write_text("base_url: https://x.example\n")

        (tmp_path / "test_generated_fixtures.py").write_text(_TEST_SOURCE)

        env = {**os.environ, "PYTHONPATH": _PROJECT_ROOT}

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(tmp_path),
                "-v",
                "-p",
                "no:cacheprovider",
                "--base-url",
                "https://cli.example",
            ],
            cwd=str(tmp_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        output = result.stdout + result.stderr
        assert result.returncode == 0, output
        # The fixture resolved, --base-url was registered, and the typed value overrode the config.
        assert "test_get_orders_fixture_resolves" in output
        assert "test_base_url_option_registered" in output
        assert "test_base_url_cli_overrides_config" in output


class TestWebPluginEndToEnd:
    """End-to-end: a real pytest subprocess enabling the web plugin through ``plugins.install()``.

    Pins the seam no in-process double reaches: the installation gate appending the real
    ``WebPlugin``, pluginator binding it to ``web.yml``, ``configure`` running at configphase, the
    ``web`` fixture resolving by its consumer-facing name, and the stacked
    ``@generation_prompt`` decorators composing through real pytest marker iteration in written
    order — warning-free under the configphase-registered marker.
    """

    def test_web_kind_end_to_end_pytest_resolves_web_fixture(self, tmp_path):
        """A ``web.yml`` project with the bootstrap conftest runs pytest and resolves the fixture."""
        # Deliberately no pyproject.toml: the web fixture passes the explicit config, which
        # prettyplay adopts verbatim — the pyproject auto-search (and its FileNotFoundError)
        # never runs for it.

        config_dir = tmp_path / ".goga" / "tools" / "pybuggy"
        config_dir.mkdir(parents=True)
        (config_dir / "web.yml").write_text(_WEB_CONFIG_SOURCE, encoding="utf-8")
        (tmp_path / "conftest.py").write_text(_BOOTSTRAP_CONFTEST_SOURCE, encoding="utf-8")
        (tmp_path / "test_search.py").write_text(_WEB_TEST_SOURCE, encoding="utf-8")

        # The web-only kind activates nothing api-related: no api.yml and no BASE_URL, so the
        # api gate stays shut and the run needs no api base_url — the closed contract gap.
        env = {key: value for key, value in os.environ.items() if key != "BASE_URL"}
        env["PYTHONPATH"] = _PROJECT_ROOT

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
        assert "test_web_fixture_resolves" in output
        assert "test_web_options_registered" in output

    def test_web_kind_stacked_generation_prompts_compose_in_written_order(self, tmp_path):
        """Real pytest run: stacked ``@generation_prompt`` decorators join top-first after the document prompt.

        The decorator's markers land on the collected item in application order (bottom
        decorator first) — the fixture's reversal restores written order, and the composed
        runtime config carries the document prompt plus the extras. The ``-W error`` filter
        fails the run on an unregistered-marker warning, pinning the warning-free use.
        """
        config_dir = tmp_path / ".goga" / "tools" / "pybuggy"
        config_dir.mkdir(parents=True)
        (config_dir / "web.yml").write_text(_WEB_PROMPT_CONFIG_SOURCE, encoding="utf-8")
        (tmp_path / "conftest.py").write_text(_BOOTSTRAP_CONFTEST_SOURCE, encoding="utf-8")
        (tmp_path / "test_prompts.py").write_text(_WEB_PROMPT_TEST_SOURCE, encoding="utf-8")

        env = {key: value for key, value in os.environ.items() if key != "BASE_URL"}
        env["PYTHONPATH"] = _PROJECT_ROOT

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(tmp_path),
                "-v",
                "-p",
                "no:cacheprovider",
                "-W",
                "error::pytest.PytestUnknownMarkWarning",
            ],
            cwd=str(tmp_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        output = result.stdout + result.stderr
        assert result.returncode == 0, output
        assert "test_stacked_generation_prompt_composes_in_written_order" in output
        assert "PytestUnknownMarkWarning" not in output
