"""`goga_tool_pybuggy.web` — the web test kind library (browser UI tests as step sentences).

Exposes the classes ``AllureStepHooks``, ``EventLogFormatter`` and ``WebConfigKeys`` and the
routines ``build_pretty_config``, ``install_event_log_formatter`` and ``validate_web_config``.
The document model is the library ``PrettyConfig`` — imported from prettyplay, not re-exported;
the ``WebPlugin`` lives in the plugins cell (`goga_tool_pybuggy.plugins`) and joins pytest only
through its presence-gated installation.
"""

from .allure_hooks import AllureStepHooks
from .config import validate_web_config
from .keys import WebConfigKeys
from .logging_setup import EventLogFormatter, install_event_log_formatter
from .pretty import build_pretty_config

__all__ = [
    "AllureStepHooks",
    "EventLogFormatter",
    "WebConfigKeys",
    "build_pretty_config",
    "install_event_log_formatter",
    "validate_web_config",
]
