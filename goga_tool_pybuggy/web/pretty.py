"""Prettyplay settings construction: the validated config materialized with the resolved modes.

The all-fields construction is load-bearing — the runtime adopts an explicit config verbatim
(prettyplay 0.0.4): pyproject and the ``PRETTYPLAY_*`` env never load for it and never back-fill
an empty field, so this config is the complete effective settings and the web config the single
source. The ``PRETTYPLAY_*`` scrub of the plugin keeps the process env clean on top of it. The
module is pure: the single source is the passed model and the flags. The module also carries the
per-test generation-prompt declaration surface — the ``generation_prompt`` decorator attaching a
test's extra generation instructions.
"""

import typing as t

import pytest
from prettyplay import BrowserConfig, PrettyConfig


def build_pretty_config(
    config: PrettyConfig, strict_flag: bool, interactive_flag: bool, prompt_extra: str = ""
) -> PrettyConfig:
    """Materialize the validated web config with the resolved strict and interactive modes.

    Args:
        config: The validated web config — the activation of the web plugin.
        strict_flag: The effective strict override — True forces strict even when the document
            says false.
        interactive_flag: The effective interactive override — the same form.
        prompt_extra: The per-test extra generation instructions — the non-empty parts of the
            document generation prompt and this text join with a single newline, document
            first.

    Returns:
        The explicitly constructed prettyplay config — the complete effective settings, adopted
        verbatim by the runtime.
    """
    fields = config.model_dump()

    browser = BrowserConfig(**fields.pop("browser"))

    fields["strict"] = config.strict or strict_flag
    fields["interactive"] = config.interactive or interactive_flag

    fields["generation_prompt"] = "\n".join(part for part in (config.generation_prompt, prompt_extra) if part)

    return PrettyConfig(browser=browser, **fields)


def generation_prompt(text: str) -> t.Callable[..., t.Any]:
    """Mark one test with per-test extra generation instructions.

    The text appends to the generation prompt of exactly the marked test — the web config
    document stays the single global source. Each application attaches its own marker, so
    stacked declarations are all preserved (duplicates included) and apply in the order
    written; the requesting test is stamped with the ``web`` fixture, which collects the
    markers at setup time.

    Nothing executes at decoration time beyond the validation — no I/O, no plugin lookup,
    no config read; the marked function itself is returned unchanged.

    Args:
        text: The extra generation instructions of this one test — a non-empty,
            non-whitespace-only string, stripped before it is carried by the marker.

    Returns:
        The decorator attaching the ``pybuggy_generation_prompt`` marker and the
        ``usefixtures("web")`` stamp to a test, returning the function unchanged.

    Raises:
        ValueError: When ``text`` is not a string or its stripped form is empty.
    """
    if not isinstance(text, str) or text.strip() == "":
        raise ValueError("generation_prompt text must be a non-empty, non-whitespace-only string")

    stripped = text.strip()

    def _decorate(item: t.Any) -> t.Any:
        marked = pytest.mark.pybuggy_generation_prompt(text=stripped)(item)

        return pytest.mark.usefixtures("web")(marked)

    return _decorate
