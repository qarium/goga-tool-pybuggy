"""Web config validation: the raw ``web.yml`` parse validated into the library model.

The document model is the prettyplay ``PrettyConfig`` itself — no mirror. ``validate_web_config``
turns the raw document parse into the validated library model, wrapping violations into a clean
error naming the document; the library validators run here, so a semantic violation (an off-matrix
browser name, a non-ws endpoint, an out-of-range speed) fails the run at configphase.
"""

from prettyplay import PrettyConfig
from pydantic import ValidationError

from .keys import CONFIG_FILE


def validate_web_config(data: dict[str, object]) -> PrettyConfig:
    """Validate the raw parse of the web config document into a ``PrettyConfig``.

    Args:
        data: The raw mapping of ``web.yml`` (the plugin-config parse of the document).

    Returns:
        The validated web config — the library model, an omitted key filling from the library
        default.

    Raises:
        ValueError: On a document violation — a non-mapping root, an empty mapping, or a document
            not validatable into :class:`PrettyConfig`, structural and semantic alike (the pydantic
            detail chained).
    """
    if not isinstance(data, dict):
        raise ValueError(f"{CONFIG_FILE}: the document must parse to a mapping")

    if not data:
        raise ValueError(
            f"{CONFIG_FILE}: the document is empty — it must carry at least the provider and the browser name"
        )

    try:
        return PrettyConfig.model_validate(data)
    except ValidationError as err:
        raise ValueError(f"{CONFIG_FILE}: invalid web config document") from err
