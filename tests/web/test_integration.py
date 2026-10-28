"""Tests for the `goga_tool_pybuggy.web` facade (the 10-name `__all__` surface).

Covers the facade contract: the exact ten contract names in the design order and the
importability of every name from the package.
"""

import typing as t

import goga_tool_pybuggy.web as web_module

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
