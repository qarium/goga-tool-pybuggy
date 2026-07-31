"""GitEntry config entity: a remote git source of a spec."""

from typing import Optional

from pydantic import BaseModel, ConfigDict


class GitEntry(BaseModel):
    """Remote source of a spec for the endpoint pull command.

    Carries a clone URL and an in-repo path that the pull command uses to fetch
    a spec from a remote repository via shallow-clone and copy it into the
    project.

    Attributes:
        url: Clone URL consumed by shallow-clone in the pull command. Must be a
            valid clone target for GitPython (no embedded credentials/tokens —
            rely on git credential helpers instead).
        location: Path inside the repository (file or subdirectory) to copy from.
        ref: Optional git ref (branch or tag name) to clone; when None the
            remote default branch is cloned. A bare commit SHA is not guaranteed
            to resolve under a shallow clone (git ``--branch`` semantics).
    """

    model_config = ConfigDict(kw_only=True)

    url: str
    location: str
    ref: Optional[str] = None
