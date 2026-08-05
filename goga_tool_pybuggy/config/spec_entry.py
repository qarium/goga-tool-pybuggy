"""SpecEntry config entity: one spec configuration record."""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from .git_entry import GitEntry


class SpecEntry(BaseModel):
    """A single spec entry in the pybuggy configuration.

    Declares the spec format, its local path (relative to the project root) and
    an optional remote git source. The ``type`` field only declares the format
    — it does not drive parsing, since Prance auto-detects the version on parse.

    Attributes:
        type: Spec format — restricted to ``swagger`` or ``openapi``; pydantic
            rejects any other value on validation.
        location: Local path (from the project root) to the spec file. Surfaced
            in the ``list`` header and is the copy target of ``pull``.
        git: Optional remote source; when absent the spec is treated as
            local-only and ``pull`` skips it silently.
    """

    model_config = ConfigDict(kw_only=True)

    type: Literal["swagger", "openapi"]
    location: str
    git: Optional[GitEntry] = None
