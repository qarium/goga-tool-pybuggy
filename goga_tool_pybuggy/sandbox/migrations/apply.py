"""apply_migrations and run_migrations: the migrations execution plane and source resolution."""

import logging
import tempfile
from pathlib import Path

import psycopg
from git import Repo
from git.exc import GitCommandError
from psycopg import Connection

from .errors import MigrationError
from .goose import MigrationFile, load_migration_set

logger = logging.getLogger(__name__)


def apply_migrations(conn: Connection, migrations: list[MigrationFile]) -> None:
    """Execute a parsed migration set once over the postgres connection.

    Every migration applies in the given order — the caller's order is preserved. A default
    migration runs inside one transaction — all of its statements commit or roll back
    together; a NO TRANSACTION migration runs statement-by-statement in autocommit. Every
    applied file reports one structured progress line. The first failed statement raises —
    the apply stops and no further file runs.

    Args:
        conn: The per-session postgres connection — autocommit, owned by the caller.
        migrations: The ordered set from ``load_migration_set``.

    Raises:
        MigrationError: A statement failed — the message names the migration file and the
            server-side error; default files roll back fully, already-applied statements of
            a NO TRANSACTION file stay applied.
    """
    for migration in migrations:
        if migration.no_transaction:
            _apply_in_autocommit(conn, migration)
        else:
            _apply_in_transaction(conn, migration)

        logger.info(
            "migration applied",
            extra={"migration": migration.filename, "version": migration.version},
        )


def run_migrations(conn: Connection, location: str, git_url: str | None, git_ref: str | None) -> None:
    """Orchestrate one migration apply: resolve the source, load the set, apply.

    A local source — ``git_url`` None — resolves ``location`` against the current working
    directory; an absolute ``location`` overrides the anchor. A remote source shallow-clones
    ``git_url`` at ``git_ref`` into a fresh temporary folder — ambient credentials only —
    and resolves ``location`` inside the clone; the clone is deleted on every exit path,
    applied or failed, and never cached across sessions.

    Args:
        conn: The per-session postgres connection — autocommit, owned by the caller.
        location: The declared location — cwd-relative for a local source, a path inside
            the repository for a remote source.
        git_url: The clone URL of the remote source; None means the source is local.
        git_ref: The branch or tag to clone; None clones the remote default branch.

    Raises:
        MigrationError: Any step failed — the clone, the location resolution, the set load
            or the apply; the message names the failed step.
    """
    if git_url is None:
        _run_local(conn, location)
        return

    _run_remote(conn, location, git_url, git_ref)


def _run_local(conn: Connection, location: str) -> None:
    """Run one apply of a local migrations source.

    Args:
        conn: The per-session postgres connection.
        location: The declared cwd-relative location — an absolute path overrides the
            anchor.

    Raises:
        MigrationError: The declared folder is missing, or the set load or the apply
            failed; the message names the failed step.
    """
    folder = Path.cwd() / location
    logger.debug("migrations source resolved", extra={"location": str(folder)})

    if not folder.is_dir():
        raise MigrationError(f"{folder}: the migrations folder is missing")

    apply_migrations(conn, load_migration_set(folder))


def _run_remote(conn: Connection, location: str, git_url: str, git_ref: str | None) -> None:
    """Run one apply of a remote migrations source — shallow clone, resolve, apply, delete.

    Args:
        conn: The per-session postgres connection.
        location: The declared path inside the cloned repository.
        git_url: The clone URL — ambient credentials only, nothing embedded.
        git_ref: The branch or tag to clone; None clones the remote default branch.

    Raises:
        MigrationError: The clone, the location resolution, the set load or the apply
            failed — the clone is still deleted on every exit path.
    """
    with tempfile.TemporaryDirectory(prefix="pybuggy-migrations-") as tmp:
        target = Path(tmp)

        _shallow_clone(git_url, target, git_ref)

        folder = _resolve_clone_location(target, location)
        logger.debug("migrations source resolved", extra={"location": str(folder)})

        apply_migrations(conn, load_migration_set(folder))


def _shallow_clone(git_url: str, target: Path, git_ref: str | None) -> None:
    """Shallow-clone the declared repository into the fresh target folder.

    Args:
        git_url: The clone URL — ambient credentials only, nothing embedded.
        target: The fresh clone target folder inside the session's temporary directory.
        git_ref: The branch or tag to clone; None omits ``--branch`` and clones the remote
            default branch.

    Raises:
        MigrationError: The clone failed; the message names the URL and the git failure.
    """
    try:
        Repo.clone_from(git_url, str(target), depth=1, branch=git_ref)
    except GitCommandError as exc:
        raise MigrationError(f"failed to clone {git_url}: {exc}") from exc


def _resolve_clone_location(target: Path, location: str) -> Path:
    """Resolve the declared location inside the cloned repository.

    Args:
        target: The root of the shallow clone.
        location: The declared path inside the repository.

    Returns:
        The resolved migrations folder inside the clone.

    Raises:
        MigrationError: The location escapes the clone root or resolves to no folder; the
            message names the offending location or path.
    """
    folder = target / location

    if not folder.resolve().is_relative_to(target.resolve()):
        raise MigrationError(f"{location}: the migrations location escapes the clone")

    if not folder.is_dir():
        raise MigrationError(f"{folder}: the migrations folder is missing in the cloned repository")

    return folder


def _apply_in_transaction(conn: Connection, migration: MigrationFile) -> None:
    """Apply one migration inside a single transaction — one commit or one rollback.

    Args:
        conn: The per-session autocommit postgres connection — the explicit transaction
            wraps all statements of the file.
        migration: The migration to apply.

    Raises:
        MigrationError: A statement failed — the whole file rolls back; the message names
            the file and the server-side error.
    """
    try:
        with conn.transaction(), conn.cursor() as cursor:
            for statement in migration.statements:
                cursor.execute(statement)
    except psycopg.Error as exc:
        raise MigrationError(f"{migration.filename}: {_server_message(exc)}") from exc


def _apply_in_autocommit(conn: Connection, migration: MigrationFile) -> None:
    """Apply one NO TRANSACTION migration statement-by-statement in autocommit.

    Args:
        conn: The per-session autocommit postgres connection.
        migration: The migration to apply.

    Raises:
        MigrationError: A statement failed — already-applied statements stay applied; the
            message names the file and the server-side error.
    """
    try:
        for statement in migration.statements:
            with conn.cursor() as cursor:
                cursor.execute(statement)
    except psycopg.Error as exc:
        raise MigrationError(f"{migration.filename}: {_server_message(exc)}") from exc


def _server_message(error: psycopg.Error) -> str:
    """Extract the server-side message of a driver error.

    Args:
        error: The driver error raised by a failed statement.

    Returns:
        The server's primary message, or the driver message when the server sent none.
    """
    primary = error.diag.message_primary

    return primary if primary else str(error)
