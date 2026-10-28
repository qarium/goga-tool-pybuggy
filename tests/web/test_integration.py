"""Tests for the `goga_tool_pybuggy.web` facade and the cross-entity prettyplay layering pin.

Covers the facade contract: the exact ten contract names in the design order and the
importability of every name from the package. The layering pin holds the real prettyplay
construction against a `WebConfig`-built config — explicit fields win over the env layer,
empty fields fall through to it, and the runtime constructs and closes lazily (no browser,
no LLM calls). The end-to-end class runs a real pytest subprocess through the installation
gate, pinning the pluginator seam no in-process double reaches.
"""

import os
import pathlib
import subprocess
import sys
import typing as t

import goga_tool_pybuggy
import goga_tool_pybuggy.web as web_module
import pytest
from goga_tool_pybuggy.web.config import WebConfig
from goga_tool_pybuggy.web.pretty import build_pretty_config
from prettyplay import PrettyPlay

# The contract facade: classes first, then routines, alphabetical within each group.
_CONTRACT_NAMES: t.Final[list[str]] = [
    "AllureStepHooks",
    "BrowserSettings",
    "EventLogFormatter",
    "WebConfig",
    "WebConfigKeys",
    "WebPlugin",
    "build_pretty_config",
    "install_event_log_formatter",
    "validate_web_config",
    "web_cache_path",
]

# Source root that makes `goga_tool_pybuggy` importable in the subprocess.
_PROJECT_ROOT = str(pathlib.Path(goga_tool_pybuggy.__file__).resolve().parent.parent)

# The consumer conftest exactly as the bootstrap delivers it (the fixed template).
_CONFTEST_SOURCE = """\
from dotenv import load_dotenv

load_dotenv()

from goga_tool_pybuggy import plugin

plugin.install()
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

# Consumer test: the web fixture resolves and both CLI options registered.
_TEST_SOURCE = """\
def test_web_fixture_resolves(web):
    assert web is not None


def test_web_options_registered(pytestconfig):
    # getoption raises ValueError for an unknown option — both flags were registered.
    pytestconfig.getoption("--strict-mode")
    pytestconfig.getoption("--interactive")
"""


class TestWebFacadeContract:
    """Contract tests for the `goga_tool_pybuggy.web` package facade."""

    def test_facade_exports_exactly_ten_names(self):
        """`__all__` is exactly the ten contract names and every name is importable from the facade."""
        from goga_tool_pybuggy.web import WebPlugin

        assert WebPlugin is web_module.WebPlugin
        assert sorted(web_module.__all__) == sorted(_CONTRACT_NAMES)

        for name in _CONTRACT_NAMES:
            assert getattr(web_module, name, None) is not None, name


class TestPrettyplayLayeringPin:
    """Integration tests pinning the per-field merge between `WebConfig` and the real runtime."""

    def test_prettyplay_construction_honors_web_config(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        """Explicit `WebConfig` fields win over the env layer; an empty field falls through to it.

        The pin documents why `WebPlugin.configure` scrubs `PRETTYPLAY_*`: without the scrub the
        fall-through below is a live channel from the environment into the effective settings.
        """
        monkeypatch.setenv("PRETTYPLAY_STRICT", "true")
        monkeypatch.setenv("PRETTYPLAY_GENERATION_ATTEMPTS", "9")

        web_config = WebConfig(provider="anthropic", generation_attempts=7, cache_root=str(tmp_path))
        pretty = build_pretty_config(web_config, False, False)

        runtime = PrettyPlay("k", "sub", cleanup=False, config=pretty)

        try:
            effective = runtime._runtime.config

            assert effective.generation_attempts == 7
            assert effective.strict is False
            assert effective.cache_root == str(tmp_path)

            monkeypatch.setenv("PRETTYPLAY_BASE_URL", "https://env.example")

            empty_pretty = build_pretty_config(WebConfig(), False, False)
            empty_field = PrettyPlay("k2", "sub", cleanup=False, config=empty_pretty)

            try:
                assert empty_field._runtime.config.base_url == "https://env.example"
            finally:
                empty_field.close()
        finally:
            runtime.close()

    def test_prettyplay_runtime_closes_cleanly_without_browser(self, tmp_path: pathlib.Path):
        """The `with runtime` block constructs and exits without touching a browser or an LLM client."""
        web_config = WebConfig(cache_root=str(tmp_path))
        pretty = build_pretty_config(web_config, False, False)

        with PrettyPlay("k", "sub", cleanup=False, config=pretty) as play:
            assert play.cache_key == "k"

        assert play._page is None
        assert play._runtime._driver is None


class TestWebPluginEndToEnd:
    """End-to-end: a real pytest subprocess enabling the web plugin through ``plugin.install()``.

    Pins the seam no in-process double reaches: the installation gate appending the real
    ``WebPlugin``, pluginator binding it to ``web.yml``, ``configure`` running at configphase, and
    the ``web`` fixture resolving by its consumer-facing name.
    """

    def test_web_kind_end_to_end_pytest_resolves_web_fixture(self, tmp_path: pathlib.Path):
        """A ``web.yml`` project with the bootstrap conftest runs pytest and resolves the fixture."""
        # prettyplay 0.0.x always auto-searches a pyproject.toml upward from the cwd — without one
        # the runtime construction raises FileNotFoundError at fixture setup.
        (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")

        config_dir = tmp_path / ".goga" / "tools" / "pybuggy"
        config_dir.mkdir(parents=True)
        (config_dir / "web.yml").write_text(_WEB_CONFIG_SOURCE, encoding="utf-8")
        (tmp_path / "conftest.py").write_text(_CONFTEST_SOURCE, encoding="utf-8")
        (tmp_path / "test_search.py").write_text(_TEST_SOURCE, encoding="utf-8")

        # The same install call constructs the ApiPlugin unconditionally (the plugin contract
        # pins it), so the subprocess satisfies its required base_url through the documented
        # env source — the web-only kind's own resolution is tracked as a contract gap.
        env = {**os.environ, "PYTHONPATH": _PROJECT_ROOT, "BASE_URL": "https://api.example"}

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
