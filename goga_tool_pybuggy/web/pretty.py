"""Prettyplay settings construction: ``WebConfig`` mapped onto an explicit ``PrettyConfig``.

The all-fields construction is load-bearing — passing every field as a constructor argument puts
each into ``model_fields_set``, which makes an explicit value win over the library's env and
pyproject layer. The module is pure: the single source is the passed model and the flags.
"""

from prettyplay import BrowserConfig, PrettyConfig

from .config import WebConfig


def build_pretty_config(config: WebConfig, strict_flag: bool, interactive_flag: bool) -> PrettyConfig:
    """Map a validated web config onto an explicit prettyplay config.

    Args:
        config: The validated web config — the activation of the web plugin.
        strict_flag: The effective strict override — True forces strict even when the document
            says false.
        interactive_flag: The effective interactive override — the same form.

    Returns:
        The explicitly constructed prettyplay config — every field participates in the library's
        per-field merge.

    Raises:
        ValidationError: When a value violates the prettyplay semantics (the browser matrix, the
            endpoint scheme, the speed range) — prettyplay's actionable per-setting text reaches
            the caller unchanged.
    """
    fields = config.model_dump()

    browser = BrowserConfig(**fields.pop("browser"))

    fields["strict"] = config.strict or strict_flag
    fields["interactive"] = config.interactive or interactive_flag

    return PrettyConfig(browser=browser, **fields)
