"""Prettyplay settings construction: the validated config materialized with the resolved modes.

The all-fields construction is load-bearing — the runtime adopts an explicit config verbatim
(prettyplay 0.0.4): pyproject and the ``PRETTYPLAY_*`` env never load for it and never back-fill
an empty field, so this config is the complete effective settings and the web config the single
source. The ``PRETTYPLAY_*`` scrub of the plugin keeps the process env clean on top of it. The
module is pure: the single source is the passed model and the flags.
"""

from prettyplay import BrowserConfig, PrettyConfig


def build_pretty_config(config: PrettyConfig, strict_flag: bool, interactive_flag: bool) -> PrettyConfig:
    """Materialize the validated web config with the resolved strict and interactive modes.

    Args:
        config: The validated web config — the activation of the web plugin.
        strict_flag: The effective strict override — True forces strict even when the document
            says false.
        interactive_flag: The effective interactive override — the same form.

    Returns:
        The explicitly constructed prettyplay config — the complete effective settings, adopted
        verbatim by the runtime.
    """
    fields = config.model_dump()

    browser = BrowserConfig(**fields.pop("browser"))

    fields["strict"] = config.strict or strict_flag
    fields["interactive"] = config.interactive or interactive_flag

    return PrettyConfig(browser=browser, **fields)
