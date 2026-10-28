"""Tests for the `goga_tool_pybuggy.web` facade and the cross-entity prettyplay layering pin.

Covers the facade contract: the exact ten contract names in the design order and the
importability of every name from the package. The layering pin holds the real prettyplay
construction against a `WebConfig`-built config — explicit fields win over the env layer,
empty fields fall through to it, and the runtime constructs and closes lazily (no browser,
no LLM calls).
"""

import pathlib
import typing as t

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
