"""MigrationFile entity, parse_migration_file and load_migration_set: the goose-SQL parsing plane."""

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from .errors import MigrationError

FILENAME_GRAMMAR = re.compile(r"^(\d+)_(.+)\.sql$")
ANNOTATION_GRAMMAR = re.compile(r"^--\s*\+goose\s+(.+?)\s*$")


class MigrationFile(BaseModel):
    """One parsed goose-format migration file — the apply-ready unit of the set.

    Attributes:
        version: The numeric prefix of the filename, compared and applied numerically.
        filename: The source file name — the identity used in progress output and error
            messages.
        statements: The ordered statement bodies of the Up section, ready to execute as
            given.
        no_transaction: Whether the file declared ``-- +goose NO TRANSACTION`` and must run
            statement-by-statement in autocommit.
    """

    model_config = ConfigDict(kw_only=True)

    version: int
    filename: str
    statements: list[str] = []
    no_transaction: bool = False


def version_prefix(filename: str) -> int | None:
    """Extract the numeric version prefix of a migration filename.

    The single extraction point of the naming grammar — the load-time shape checks import
    it instead of duplicating the rule.

    Args:
        filename: The migration file name.

    Returns:
        The numeric version prefix, or ``None`` when the name does not follow the
        ``<version>_<description>.sql`` grammar.
    """
    match = FILENAME_GRAMMAR.match(filename)

    return int(match.group(1)) if match else None


def parse_migration_file(filename: str, text: str) -> MigrationFile:
    """Parse one goose-format migration file into its apply-ready form — pure text processing.

    The supported annotation subset is Up, Down, StatementBegin, StatementEnd and NO
    TRANSACTION; the Down section is skipped, anything else and any ``{{...}}``
    interpolation raise rather than misapply silently.

    Args:
        filename: The source file name — carried into the result and every error message.
        text: The file content.

    Returns:
        The parsed migration.

    Raises:
        MigrationError: The filename or the content violates the supported goose subset; the
            message names the file.
    """
    version = version_prefix(filename)

    if version is None:
        raise MigrationError(f"{filename}: invalid migration filename — expected <version>_<description>.sql")

    no_transaction, header, up_lines = _scan_sections(filename, text.splitlines())
    statements = _split_up_statements(filename, up_lines)
    _reject_interpolation(filename, header + up_lines)

    return MigrationFile(
        version=version,
        filename=filename,
        statements=statements,
        no_transaction=no_transaction,
    )


def load_migration_set(folder: Path) -> list[MigrationFile]:
    """Load a migrations folder into the ordered apply-ready set.

    Non-`.sql` entries are ignored; the set rejects folders without `.sql` files and files
    sharing a numeric version prefix; the parsed migrations return in ascending version
    order.

    Args:
        folder: The source folder — a local folder or a path inside a resolved clone.

    Returns:
        The parsed migrations in ascending version order — the apply order is exactly the
        returned order.

    Raises:
        MigrationError: The folder is missing, holds no `.sql` files, a name violates the
            naming grammar, or two files share a version prefix; the message names the
            folder and the offending files.
    """
    if not folder.is_dir():
        raise MigrationError(f"{folder}: the migrations folder is missing")

    sql_files = sorted(path for path in folder.iterdir() if path.is_file() and path.suffix == ".sql")

    if not sql_files:
        raise MigrationError(f"{folder}: the migrations folder holds no .sql files")

    _reject_version_conflicts(folder, sql_files)

    migrations = [parse_migration_file(path.name, path.read_text(encoding="utf-8")) for path in sql_files]
    migrations.sort(key=lambda migration: migration.version)

    return migrations


def _annotation_token(line: str) -> str | None:
    """Read the +goose annotation token of a line, if the line is one.

    Args:
        line: The raw file line.

    Returns:
        The annotation token — the text after ``+goose`` — or ``None`` for a plain line.
    """
    match = ANNOTATION_GRAMMAR.match(line.strip())

    return match.group(1) if match else None


def _scan_sections(filename: str, lines: list[str]) -> tuple[bool, list[str], list[str]]:
    """Scan the header and Up regions of the file, stopping at the Down section.

    Args:
        filename: The migration file name — carried into every error message.
        lines: The file lines.

    Returns:
        The ``(no_transaction, header, up_lines)`` triple — the NO TRANSACTION flag, the
        non-annotation header lines, and the Up-section lines (annotation lines included,
        Down section excluded).

    Raises:
        MigrationError: An unsupported annotation appears in the header, or the file has no
            Up section.
    """
    no_transaction = False
    header: list[str] = []
    up_lines: list[str] | None = None

    for line in lines:
        token = _annotation_token(line)

        if up_lines is None:
            if token is None:
                header.append(line)
            elif token == "NO TRANSACTION":
                no_transaction = True
            elif token == "Up":
                up_lines = []
            elif token == "Down":
                raise MigrationError(f"{filename}: no +goose Up section")
            else:
                raise MigrationError(f"{filename}: unsupported +goose annotation '{token}'")
        elif token == "Down":
            break
        else:
            up_lines.append(line)

    if up_lines is None:
        raise MigrationError(f"{filename}: no +goose Up section")

    return no_transaction, header, up_lines


def _split_up_statements(filename: str, lines: list[str]) -> list[str]:
    """Split the Up section into statement bodies.

    Fragment runs flush through the semicolon split before a statement body opens and once
    after the scan; a StatementBegin/StatementEnd body becomes one statement as-is —
    interior semicolons never split it.

    Args:
        filename: The migration file name — carried into every error message.
        lines: The Up-section lines, annotation lines included.

    Returns:
        The ordered statement bodies.

    Raises:
        MigrationError: The section misuses the annotation subset — a stray or unclosed
            statement body, a duplicate Up, a late NO TRANSACTION, or an unsupported
            annotation.
    """
    statements: list[str] = []
    fragments: list[str] = []
    body: list[str] | None = None

    for line in lines:
        token = _annotation_token(line)

        if body is not None:
            if token == "StatementEnd":
                statements.append("\n".join(body).strip())
                body = None
            else:
                body.append(line)

            continue

        if token is None:
            fragments.append(line)
        elif token == "StatementBegin":
            statements.extend(_split_fragments(fragments))
            fragments = []
            body = []
        elif token == "StatementEnd":
            raise MigrationError(f"{filename}: '+goose StatementEnd' without a matching '+goose StatementBegin'")
        elif token == "Up":
            raise MigrationError(f"{filename}: duplicate '+goose Up' annotation")
        elif token == "NO TRANSACTION":
            raise MigrationError(f"{filename}: '+goose NO TRANSACTION' must precede '+goose Up'")
        else:
            raise MigrationError(f"{filename}: unsupported +goose annotation '{token}'")

    if body is not None:
        raise MigrationError(f"{filename}: unclosed '+goose StatementBegin'")

    statements.extend(_split_fragments(fragments))

    return statements


def _split_fragments(lines: list[str]) -> list[str]:
    """Split buffered Up-section lines into statements on the terminating semicolon.

    A semicolon terminates a statement only outside a single-quoted literal and outside a
    ``--`` comment — semicolons inside either ride along in the statement text, as goose
    itself treats them. Pieces that are empty or comment-only are dropped; the kept pieces
    return stripped.

    Args:
        lines: The buffered non-annotation lines of one fragment run.

    Returns:
        The finished statement bodies, in buffer order.
    """
    statements: list[str] = []
    text = ""
    in_literal = False

    for line in lines:
        endings, in_literal = _statement_endings(line, in_literal)
        start = 0

        for ending in endings:
            finished = (text + line[start:ending]).strip()

            if not _is_comment_only(finished):
                statements.append(finished)

            text = ""
            start = ending + 1

        text += line[start:] + "\n"

    tail = text.strip()

    if not _is_comment_only(tail):
        statements.append(tail)

    return statements


def _statement_endings(line: str, in_literal: bool) -> tuple[list[int], bool]:
    """Locate the terminating semicolons of one Up-section line.

    A semicolon terminates a statement only outside a single-quoted literal and before any
    ``--`` comment — the rest of a comment line never terminates. A literal spanning lines
    carries its open state to the next line.

    Args:
        line: The scanned Up-section line.
        in_literal: Whether the line opens inside a single-quoted literal.

    Returns:
        The ``(endings, in_literal)`` pair — the indexes of the terminating semicolons and
        whether the line ends inside a literal.
    """
    endings: list[int] = []
    index = 0

    while index < len(line):
        char = line[index]

        if in_literal:
            in_literal = char != "'"
        elif char == "'":
            in_literal = True
        elif line[index : index + 2] == "--":
            return endings, in_literal
        elif char == ";":
            endings.append(index)

        index += 1

    return endings, in_literal


def _is_comment_only(text: str) -> bool:
    """Check whether a text piece carries no executable statement text.

    Args:
        text: The stripped text piece.

    Returns:
        True when the piece is empty or every one of its lines is a ``--`` SQL comment.
    """
    if not text:
        return True

    return all(line.strip().startswith("--") for line in text.splitlines())


def _reject_interpolation(filename: str, lines: list[str]) -> None:
    """Reject goose variable interpolation inside the header and Up text.

    Args:
        filename: The migration file name — carried into the error message.
        lines: The header and Up lines.

    Raises:
        MigrationError: The text contains a ``{{`` opening — migration statements apply as
            given, never interpolated.
    """
    if "{{" in "\n".join(lines):
        raise MigrationError(
            f"{filename}: goose {{{{...}}}} interpolation is not supported — migration statements apply as given"
        )


def _reject_version_conflicts(folder: Path, sql_files: list[Path]) -> None:
    """Check the naming grammar and version-prefix uniqueness of the listed migration files.

    Args:
        folder: The source folder — carried into every error message.
        sql_files: The listed `.sql` files.

    Raises:
        MigrationError: A name violates the naming grammar or two files share a numeric
            version prefix.
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
