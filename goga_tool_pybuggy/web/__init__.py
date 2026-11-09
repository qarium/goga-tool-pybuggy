"""`goga_tool_pybuggy.web` — the web test kind library (browser UI tests as step sentences).

Exposes the classes ``AllureStepHooks`` and ``EventLogFormatter`` and the routines
``build_pretty_config`` and ``install_event_log_formatter``. The per-test generation-prompt
declaration surface is the ``generation_prompt`` decorator — the routine a web test applies to
append extra generation instructions to its own runtime prompt. The document model is the library
``PrettyConfig`` — imported from prettyplay, not re-exported; the ``WebPlugin``, the web config
key set, and the document validation live in the plugins cell (`goga_tool_pybuggy.plugins`) and
join pytest only through its presence-gated installation — this cell consumes the already
validated activation in ``build_pretty_config``.
"""

from .allure_hooks import AllureStepHooks
from .logging_setup import EventLogFormatter, install_event_log_formatter
from .pretty import build_pretty_config, generation_prompt

__all__ = [
    "AllureStepHooks",
    "EventLogFormatter",
    "build_pretty_config",
    "generation_prompt",
    "install_event_log_formatter",
]
