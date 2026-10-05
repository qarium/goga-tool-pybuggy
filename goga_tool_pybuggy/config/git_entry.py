"""GitEntry config entity: a remote git source of a spec."""

from typing import Optional

from pydantic import BaseModel, ConfigDict


class GitEntry(BaseModel):
    """Remote source of a spec for the endpoint pull command.

    The pull command shallow-clones the URL and copies ``location`` into the project.

    Attributes:
        url: Clone URL consumed by shallow-clone; no embedded credentials/tokens —
            rely on git credential helpers.
        location: Path inside the repository (file or subdirectory) to copy from.
        ref: Optional branch or tag to clone (``None``: remote default branch); a
            bare commit SHA is not guaranteed to resolve in a shallow clone
            (git ``--branch`` semantics).
    """

    model_config = ConfigDict(kw_only=True)

    url: str = ""
    location: str = ""
    ref: Optional[str] = None
