"""Tests for the `goga_tool_pybuggy.web` facade and the cross-entity prettyplay layering pin.

Covers the facade contract: the exact six contract names in the design order and the
importability of every name from the package. The layering pin holds the real prettyplay
construction against a validated-config-built runtime config — an explicit config is adopted
verbatim (the library's env layer never loads for it), and the runtime constructs and closes
lazily (no browser, no LLM calls). The plugin end-to-end run lives in the plugins cell tests.
"""

import pathlib
import typing as t

import goga_tool_pybuggy.web as web_module
import pytest
from goga_tool_pybuggy.web.pretty import build_pretty_config
from prettyplay import PrettyConfig, PrettyPlay

# The contract facade: classes first, then routines, alphabetical within each group.
_CONTRACT_NAMES: t.Final[list[str]] = [
    "AllureStepHooks",
    "BasePage",
    "EventLogFormatter",
    "build_pretty_config",
    "generation_prompt",
    "install_event_log_formatter",
]


class TestWebFacadeContract:
    """Contract tests for the `goga_tool_pybuggy.web` package facade."""

    def test_facade_exports_exactly_six_names(self):
        """`__all__` is exactly the six contract names and every name is importable from the facade."""
        assert sorted(web_module.__all__) == sorted(_CONTRACT_NAMES)

        for name in _CONTRACT_NAMES:
            assert getattr(web_module, name, None) is not None, name


class TestPrettyplayLayeringPin:
    """Integration tests pinning the verbatim adoption of the explicit web config by the runtime."""

    def test_prettyplay_construction_honors_web_config(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        """An explicit config is adopted verbatim — the `PRETTYPLAY_*` env layer never loads for it.

        The pin documents the prettyplay 0.0.4 split: the explicit config is the complete
        effective settings (an empty field keeps the model default, never the env or pyproject
        value), and only a config-less construction reads the file layer.
        """
        monkeypatch.setenv("PRETTYPLAY_STRICT", "true")
        monkeypatch.setenv("PRETTYPLAY_GENERATION_ATTEMPTS", "9")

        web_config = PrettyConfig(provider="anthropic", generation_attempts=7, cache_root=str(tmp_path))
        pretty = build_pretty_config(web_config, False, False)

        runtime = PrettyPlay("k", "sub", cleanup=False, config=pretty)

        try:
            effective = runtime._runtime.config

            assert effective.generation_attempts == 7
            assert effective.strict is False
            assert effective.cache_root == str(tmp_path)

            monkeypatch.setenv("PRETTYPLAY_BASE_URL", "https://env.example")

            empty_pretty = build_pretty_config(PrettyConfig(), False, False)
            empty_field = PrettyPlay("k2", "sub", cleanup=False, config=empty_pretty)

            try:
                # Verbatim adoption: the env var never reaches an explicitly configured runtime —
                # the empty field keeps the model default, and only an empty cache_root resolves
                # to the <cwd>/.prettyplay/cache default.
                assert empty_field._runtime.config.base_url == ""
                assert empty_field._runtime.config.cache_root == str(pathlib.Path.cwd() / ".prettyplay" / "cache")
            finally:
                empty_field.close()
        finally:
            runtime.close()

    def test_prettyplay_runtime_closes_cleanly_without_browser(self, tmp_path: pathlib.Path):
        """The `with runtime` block constructs and exits without touching a browser or an LLM client."""
        pretty = build_pretty_config(PrettyConfig(cache_root=str(tmp_path)), False, False)

        with PrettyPlay("k", "sub", cleanup=False, config=pretty) as play:
            assert play.cache_key == "k"

        assert play._page is None
        assert play._runtime._driver is None
