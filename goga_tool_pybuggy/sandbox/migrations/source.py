"""check_local_migrations and check_git_url: the load-time source shape checks."""

import urllib.parse
from pathlib import Path

from .errors import MigrationError
from .goose import version_prefix

ALLOWED_URL_SCHEMES = ("git", "http", "https", "ssh")


def check_local_migrations(folder: Path) -> None:
    """Run the load-time shape checks of a declared local migrations folder.

    The path must exist and be a folder holding at least one ``.sql`` file whose names
    follow the shared naming grammar with unique numeric version prefixes. Shape checks
    only — file contents are never read here.

    Args:
        folder: The resolved folder path — the caller resolves the declared location
            against the current working directory.

    Raises:
        MigrationError: The folder is missing, empty or holds no ``.sql`` files, a name
            violates the naming grammar, or two files share a numeric version prefix;
            the message names the folder and the failed check.
    """
    if not folder.is_dir():
        raise MigrationError(f"{folder}: the migrations source must be an existing folder")

    entries = list(folder.iterdir())

    if not entries:
        raise MigrationError(f"{folder}: the migrations folder is empty")

    sql_files = sorted(path for path in entries if path.is_file() and path.suffix == ".sql")

    if not sql_files:
        raise MigrationError(f"{folder}: the migrations folder holds no .sql files")

    _check_names(folder, sql_files)


def check_git_url(url: str) -> None:
    """Validate the shape of a declared git clone URL.

    The scheme must be one of git, http, https or ssh — an scp-style URL such as
    ``git@github.com:acme/r.git`` parses with an empty scheme and is rejected; authors
    rewrite it as ``ssh://git@host/path``. The URL must not embed credentials; an ssh
    username is not a credential — a password always is, in every scheme.

    Args:
        url: The clone URL of the declared remote migrations source.

    Raises:
        MigrationError: The scheme is outside the allowlist or the URL embeds
            credentials; the message names the URL and the rule.
    """
    parsed = urllib.parse.urlparse(url)

    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        raise MigrationError(
            f"{url}: disallowed git URL scheme '{parsed.scheme}' (allowed: {', '.join(ALLOWED_URL_SCHEMES)})"
        )

    if parsed.password is not None or ("@" in parsed.netloc and parsed.scheme != "ssh"):
        raise MigrationError(f"{url}: the git URL must not embed credentials")


def _check_names(folder: Path, sql_files: list[Path]) -> None:
    """Check the naming grammar and version-prefix uniqueness of the listed files.

    Args:
        folder: The source folder — carried into every error message.
        sql_files: The listed `.sql` files.

    Raises:
        MigrationError: A name violates the naming grammar or two files share a numeric
            version prefix — numeric comparison, so ``00001`` and ``1`` collide.
    """
    seen: dict[int, str] = {}

    for path in sql_files:
        version = version_prefix(path.name)

        if version is None:
            raise MigrationError(
                f"{folder}: {path.name}: invalid migration filename — expected <version>_<description>.sql"
            )

        if version in seen:
            raise MigrationError(f"{folder}: duplicate migration version {version}: {seen[version]} and {path.name}")

        seen[version] = path.name
