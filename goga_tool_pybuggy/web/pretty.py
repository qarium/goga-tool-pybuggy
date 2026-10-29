"""Prettyplay settings construction: the validated config materialized with the resolved modes.

The all-fields construction is load-bearing — prettyplay 0.0.3 merges the programmatic layer into
its pyproject+env file layer per field (``model_fields_set``), so passing every field explicitly
makes the web config the single source: an omitted key's default beats the library layers, and the
``PRETTYPLAY_*`` scrub of the plugin closes the env channel of the empty fields. The module is
pure: the single source is the passed model and the flags.
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
        The explicitly constructed prettyplay config — every field participates in the library's
        per-field merge.
    """
    fields = config.model_dump()

    browser = BrowserConfig(**fields.pop("browser"))

    fields["strict"] = config.strict or strict_flag
    fields["interactive"] = config.interactive or interactive_flag

    return PrettyConfig(browser=browser, **fields)
