"""`goga_tool_pybuggy.web` — the web test kind (browser UI tests as step sentences).

Exposes the classes ``AllureStepHooks``, ``BrowserSettings``, ``EventLogFormatter``,
``WebConfig``, ``WebConfigKeys`` and ``WebPlugin`` and the routines ``build_pretty_config``,
``install_event_log_formatter``, ``validate_web_config`` and ``web_cache_path``; the plugin
joins pytest only through the plugin cell's presence-gated installation.
"""

from .allure_hooks import AllureStepHooks
from .config import BrowserSettings, WebConfig, validate_web_config
from .keys import WebConfigKeys
from .logging_setup import EventLogFormatter, install_event_log_formatter
from .plugin import WebPlugin, web_cache_path
from .pretty import build_pretty_config

__all__ = [
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
