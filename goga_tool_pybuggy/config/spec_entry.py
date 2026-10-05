"""SpecEntry config entity: one spec configuration record."""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from .git_entry import GitEntry


class SpecEntry(BaseModel):
    """A single spec entry in the pybuggy configuration.

    The ``type`` field only declares the format — Prance auto-detects the version on parse.

    Attributes:
        type: Spec format, restricted to ``swagger`` or ``openapi``.
        location: Local path (from the project root); surfaced in the ``list``
            header and is the copy target of ``pull``.
        git: Optional remote source; when absent, ``pull`` skips the spec silently.
    """

    model_config = ConfigDict(kw_only=True)

    type: Optional[Literal["swagger", "openapi"]] = None
    location: str = ""
    git: Optional[GitEntry] = None
