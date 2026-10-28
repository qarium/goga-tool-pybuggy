"""Web config entities: the settings models validated from ``web.yml``.

``BrowserSettings`` and ``WebConfig`` mirror the prettyplay defaults exactly — an omitted key
behaves as the library default — and ``validate_web_config`` turns the raw document parse into
the validated model, wrapping structural violations into a clean error naming the document.
"""

import typing as t

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .keys import CONFIG_FILE


class BrowserSettings(BaseModel):
    """Nested browser section of the web config — the settings mapping onto the browser config.

    Attributes:
        name: The browser or channel name; the default chromium.
        headless: Whether the browser runs without a visible window; the default True.
        screen: The screen mode; empty keeps the runtime default.
        endpoint: The remote Playwright endpoint; empty runs locally.
        accept_dialogs: Whether dialogs are auto-accepted; the default False.
        speed: The execution speed in percent; the default 100.
        timeout: The default page timeout in seconds; the default 30.
    """

    model_config = ConfigDict(kw_only=True, extra="forbid")

    name: str = "chromium"
    headless: bool = True
    screen: str = ""
    endpoint: str = ""
    accept_dialogs: bool = False
    speed: int = 100
    timeout: float = 30


class WebConfig(BaseModel):
    """Validated model of the web config document ``web.yml`` — the web-test settings.

    Attributes:
        provider: The LLM provider — openai or anthropic; the default openai.
        base_url: The optional LLM API proxy endpoint; empty uses the provider default.
        model: The shared model override; empty means no override.
        generation_model: The model for step-code generation.
        classification_model: The model for step classification.
        generation_prompt: Extra instructions appended to the generation prompt.
        classification_prompt: Extra instructions appended to the classification prompt.
        strict: The replay-only default — zero LLM calls, a cache miss fails; the default False.
        interactive: The interactive step healing default; the default False.
        polling_timeout: The assertion polling timeout; None keeps the runtime default.
        polling_delay: The delay between polling attempts in seconds; the default 0.5.
        generation_attempts: Blind generation attempts before diagnosis; the default 3.
        healing_attempts: Healing attempts for a failing step; the default 2.
        llm_request_attempts: Retries of a failed LLM request; the default 3.
        send_screenshots: Whether screenshots are attached to LLM requests; the default False.
        generation_approve: Whether generated code is confirmed before caching; the default True.
        probe_timeout: The locator probe timeout in seconds; 0 keeps the page default.
        cache_root: The root directory of the step cache; empty selects the per-test default.
        browser: The nested browser settings; an omitted key defaults to ``BrowserSettings``.
    """

    model_config = ConfigDict(kw_only=True, extra="forbid")

    provider: t.Literal["openai", "anthropic"] = "openai"
    base_url: str = ""
    model: str = ""
    generation_model: str = ""
    classification_model: str = ""
    generation_prompt: str = ""
    classification_prompt: str = ""
    strict: bool = False
    interactive: bool = False
    polling_timeout: float | None = None
    polling_delay: float = 0.5
    generation_attempts: int = 3
    healing_attempts: int = 2
    llm_request_attempts: int = 3
    send_screenshots: bool = False
    generation_approve: bool = True
    probe_timeout: float = 0
    cache_root: str = ""
    browser: BrowserSettings = Field(default_factory=BrowserSettings)


def validate_web_config(data: dict[str, object]) -> WebConfig:
    """Validate the raw parse of the web config document into a ``WebConfig``.

    Args:
        data: The raw mapping of ``web.yml`` (the plugin-config parse of the document).

    Returns:
        The validated web config.

    Raises:
        ValueError: On a structural violation — a non-mapping root, an empty mapping, or a
            document not validatable into :class:`WebConfig` (the pydantic detail chained).
    """
    if not isinstance(data, dict):
        raise ValueError(f"{CONFIG_FILE}: the document must parse to a mapping")

    if not data:
        raise ValueError(
            f"{CONFIG_FILE}: the document is empty — it must carry at least the provider and the browser name"
        )

    try:
        return WebConfig.model_validate(data)
    except ValidationError as err:
        raise ValueError(f"{CONFIG_FILE}: invalid web config document") from err
