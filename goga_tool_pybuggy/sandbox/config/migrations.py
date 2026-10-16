"""GitSource and MigrationsConfig entities: the migrations declaration of the sandbox configuration."""

from pydantic import BaseModel, ConfigDict


class GitSource(BaseModel):
    """The optional remote source of a service's migrations.

    A bare commit SHA is not a valid ref — shallow clones resolve branch and tag names only.

    Attributes:
        url: Clone URL of the repository holding the migration folder — no embedded credentials;
            access relies on ambient git credentials.
        ref: Branch or tag to clone; ``None`` clones the remote default branch.
    """

    model_config = ConfigDict(kw_only=True, extra="forbid")

    url: str
    ref: str | None = None


class MigrationsConfig(BaseModel):
    """The migrations declaration of one postgresql service — the schema source applied once per
    session by the sandbox.

    Valid only on a postgresql service entry — placement is checked at document load. No
    version-tracking or journaling options exist here — the apply semantics are fixed.

    Attributes:
        location: Migrations folder — cwd-relative when ``git`` is absent; a path inside the
            repository when ``git`` is set.
        git: Optional remote source; ``None`` keeps the source local.
    """

    model_config = ConfigDict(kw_only=True, extra="forbid")

    location: str
    git: GitSource | None = None
