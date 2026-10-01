"""init command handler — initializes the pybuggy test environment in three modes.

``run_init`` dispatches on the mode resolved from the CLI flags: **bare** (``pybuggy
init``) guards on ``.goga`` directory existence, then runs the engine-owned onboarding
session (:func:`run_session`) followed by the pybuggy bootstrap (:func:`run_bootstrap`)
with confirm gates; **template** (``pybuggy init <tpl> [--ref R]``) scaffolds a copier
template through the engine first, then runs the session and the bootstrap with
silent-skip gates; **upgrade** (``pybuggy init --upgrade [--ref R]``) migrates a
previously scaffolded project through the engine alone — no session, no bootstrap.
"""

import logging
from pathlib import Path
from typing import Any

import click
from goga.scaffold import Scaffold

from .session import run_session

logger = logging.getLogger(__name__)


def _walk(directory: Any, discovered: list[tuple[str, str]]) -> None:
    """Recurse into ``directory`` collecting ``.usages/*.md`` files as ``(stem, text)``.

    A directory named ``.usages`` is treated as a leaf: its ``*.md`` files are collected and it is
    not descended into further. Any other directory is recursed into so future api subcells are
    picked up without editing this command.
    """
    for entry in directory.iterdir():
        if not entry.is_dir():
            continue

        if entry.name == ".usages":
            for item in entry.iterdir():
                if item.is_file() and item.name.endswith(".md"):
                    discovered.append((item.name[:-3], item.read_text(encoding="utf-8")))
        else:
            _walk(entry, discovered)


def _discover_usages(root: Any) -> list[tuple[str, str]]:
    """Recursively discover ``.usages/*.md`` files under ``root`` (the installed goga_tool_pybuggy.api package)."""
    discovered: list[tuple[str, str]] = []

    _walk(root, discovered)

    return discovered


# Hand-authored annotation line per registered pybuggy usage stem (key without the ``pybuggy-``
# prefix). Unknown stems fall back to a bare backtick reference so future api subcells are still
# bound to the contract — the DSL requires every connected usage to be referenced in an annotation.
PYBUGGY_ANNOTATIONS: dict[str, str] = {
    "api": ("Use `pybuggy-api` for executing HTTP requests from test fixtures and checking responses."),
    "asserts": ("Use `pybuggy-asserts` for response-level and field-level assertions on HTTP responses."),
}

# Annotation line for the ``conventions`` usage key — the test-convention slot occupied by
# ``write_test_convention``. Like ``PYBUGGY_ANNOTATIONS`` above, it is the sole source of the
# line registered under ``codemanifest.annotations`` (the bootstrap registration step).
_CONVENTION_LINE = "Use `conventions` for test code: pytest configuration, logging, and Allure reporting."


def _annotation_for(stem: str) -> str:
    """Return the annotation line for a discovered pybuggy usage ``stem``.

    Known stems resolve to a hand-authored description; unknown stems fall back to a bare backtick
    reference (`` `pybuggy-<stem>` ``) so every connected usage is still bound to the contract.
    """
    return PYBUGGY_ANNOTATIONS.get(stem, f"`pybuggy-{stem}`")


def _log_registration(
    usage_keys: dict[str, str],
    added_usage_keys: list[str],
    annotation_lines: dict[str, str],
    changed_annotation_keys: list[str],
) -> None:
    """Log INFO for newly-registered usages/annotations and WARNING for already-present (skipped) ones.

    Extracted from :func:`run_bootstrap` to keep it under the cyclomatic-complexity cap. A usage
    key counts as added when it appears in the ``added_usage_keys`` list returned by
    :func:`register_usages`; an annotation key counts as registered when it appears in the
    ``changed_annotation_keys`` list returned by :func:`register_annotations` (appended or
    replaced — an identical line is a no-op and logs as skipped).

    Args:
        usage_keys: Full mapping of usage key to the usage path (``pybuggy-<stem>`` and ``conventions``).
        added_usage_keys: Keys actually added by :func:`register_usages` (pre-existing ones excluded).
        annotation_lines: Full mapping of usage key to its annotation line.
        changed_annotation_keys: Keys whose annotation line was appended or replaced by
            :func:`register_annotations` (identical lines excluded).
    """
    for key, path in usage_keys.items():
        if key in added_usage_keys:
            logger.info("usage registered", extra={"key": key, "path": path})
        else:
            logger.warning("usage already registered, skipped", extra={"key": key})

    for key in annotation_lines:
        if key in changed_annotation_keys:
            logger.info("annotation registered", extra={"key": key})
        else:
            logger.warning("annotation already registered, skipped", extra={"key": key})


# The three init modes (the contract fixes the literal strings) — bare onboarding, template
# scaffolding, and template migration. Module-level constants so each mode value has a single
# source: resolve_init_mode returns them, run_init dispatches on them.
_BARE = "bare"
_TEMPLATE = "template"
_UPGRADE = "upgrade"

# Fallback Dockerfile path when the consumer config carries no ``dockerfile`` field (a
# declined-Dockerfile session leaves the field unset). The bootstrap resolves the actual
# path from the config first so the install line lands in the project's real Dockerfile;
# this constant is the default that matches the engine's own prompt default.
_DOCKERFILE_DEFAULT = Path(".goga") / "Dockerfile"


def _resolve_dockerfile_path(config: Path) -> Path:
    """Resolve the project's Dockerfile path from the consumer config.

    Reads the ``dockerfile`` field of the consumer ``.goga/config.yml`` so the install line
    lands in the project's actual Dockerfile (a custom session answer wins); a missing config
    or a missing/empty field falls back to ``_DOCKERFILE_DEFAULT`` (``.goga/Dockerfile``).
    The routine never creates the file and reads nothing beyond the config.

    Args:
        config: Path to the consumer ``.goga/config.yml``.

    Returns:
        The resolved Dockerfile path (existing or not).
    """
    raise NotImplementedError


def resolve_init_mode(tpl: str | None, ref: str | None, upgrade: bool) -> str:
    """Resolve the init mode from the CLI flags — pure validation and mapping.

    Validates the flag combination and maps it to exactly one mode, mirroring the flag rules of
    the goga init command: ``<tpl>`` and ``--upgrade`` are mutually exclusive, and ``--ref`` is
    meaningful only with a template source or an upgrade. Invalid combinations raise
    ``click.ClickException`` (click prints the message and exits 1); valid input never raises.
    Pure — no TTY, no I/O, no side effects: the empty-string normalization of ``ref``/URL
    fragments is the scaffold engine's concern, so ``None`` vs ``""`` reaches the engine verbatim.

    Args:
        tpl: Template source (local path or git URL, optionally with a ``#ref`` fragment) from
            the positional argument; ``None`` when absent.
        ref: Git ref override from ``--ref``; ``None`` when absent.
        upgrade: Whether ``--upgrade`` is set.

    Returns:
        The resolved mode: ``_UPGRADE`` when ``upgrade`` is set, ``_TEMPLATE`` when ``tpl`` is
        given, ``_BARE`` otherwise.

    Raises:
        click.ClickException: If ``tpl`` is combined with ``upgrade``, or ``ref`` is given
            without ``tpl`` and without ``upgrade``.
    """
    if tpl is not None and upgrade:
        raise click.ClickException(
            "<tpl> and --upgrade are mutually exclusive "
            "(--upgrade updates existing state tied to a specific repository)"
        )

    if ref is not None and tpl is None and not upgrade:
        raise click.ClickException("--ref requires <tpl> or --upgrade")

    if upgrade:
        return _UPGRADE

    return _TEMPLATE if tpl is not None else _BARE


def run_init(tpl: str | None, ref: str | None, upgrade: bool) -> int:
    """Initialize the project in one of the three modes resolved from the CLI flags.

    Mode dispatch with exactly one branch per mode (resolved purely by
    :func:`resolve_init_mode`): **bare** refuses first when the current directory holds a
    ``.goga`` directory (``Project already initialized`` on stderr, exit code 1, zero prompts
    and zero writes), then runs the engine-owned onboarding session (:func:`run_session`) and —
    only on a zero session code — the pybuggy bootstrap (:func:`run_bootstrap`) with confirm
    gates; **template** first scaffolds through the engine (``Scaffold().generate(tpl, ref)``)
    — a non-zero engine code stops the command with no onboarding side effect — then runs the
    session and the bootstrap in template mode (silent-skip gates); **upgrade** delegates to
    ``Scaffold().upgrade(ref)`` alone and returns its code without any session or bootstrap
    side effect.

    The scaffold engine and the session own their error handling: returned non-zero codes are
    propagated unchanged (never normalized to 1, never wrapped), and the bare guard sits before
    the session call — a refused or failed run leaves the target directory exactly as it was.

    Args:
        tpl: Template source (local path or git URL, optionally with a ``#ref`` fragment)
            from the positional argument; ``None`` in bare and upgrade modes.
        ref: Git ref override from ``--ref``; ``None`` when absent.
        upgrade: Whether ``--upgrade`` is set (template migration mode).

    Returns:
        0 on success; 1 for an already-initialized refusal (bare mode over an existing
        ``.goga/``) or a failed bootstrap step; the engine's or the session's non-zero code
        propagated as-is.

    Raises:
        click.ClickException: On an invalid flag combination (raised by
            :func:`resolve_init_mode`; click prints the message and exits 1).
    """
    mode = resolve_init_mode(tpl, ref, upgrade)

    # Already-initialized guard — bare mode only, mirroring `goga init`: a repeat invocation
    # over an initialized project must not update any file, so it refuses before the session
    # or the bootstrap could write anything. The check is directory existence only — exactly
    # goga's `Path(".goga").is_dir()`; a `.goga` regular file passes (nothing is initialized).
    if mode == _BARE and Path(".goga").is_dir():
        click.echo("Project already initialized", err=True)
        return 1

    if mode == _UPGRADE:
        return Scaffold().upgrade(ref)

    if mode == _TEMPLATE:
        engine_code = Scaffold().generate(tpl, ref)

        if engine_code != 0:
            return engine_code

    session_code = run_session()

    if session_code != 0:
        return session_code

    return run_bootstrap(template_mode=(mode == _TEMPLATE))


def run_bootstrap(template_mode: bool) -> int:
    """Run the 9-step post-session bootstrap with mode-dependent gates.

    The pybuggy-owned delivery of the files the onboarding session does not carry:

    1. Resolve the output root as the current working directory.
    2. Copy every discovered ``.usages/*.md`` of the installed ``goga_tool_pybuggy.api``
       package to ``<cwd>/.goga/usages/cooks/pybuggy/<stem>.md`` — an existing destination is
       kept untouched in template mode (INFO) and overwritten in bare mode.
    3. Deliver the ``conventions`` slot (``<cwd>/.goga/usages/conventions.md``)
       skip-if-exists in BOTH modes; otherwise write the packaged asset.
    4. Always enforce ``build.review.skip: true`` in ``<cwd>/.goga/config.yml`` via
       :func:`ensure_review_skip`.
    5. Resolve the Dockerfile from the consumer config ``dockerfile`` field (fallback
       ``.goga/Dockerfile``) and append the pybuggy install line via
       :func:`install_pybuggy` (a no-op when the file is absent).
    6. Register the usage keys and annotation lines in ``<cwd>/.goga/config.yml`` via
       :func:`register_usages` / :func:`register_annotations` and log the results
       (INFO added, WARNING skipped).
    7. Gate the root ``conftest.py``: absent → write; existing + template mode → INFO skip;
       existing + bare mode → ``click.confirm`` (default no; declining leaves it untouched).
    8. Fail with ERROR ``Dockerfile missing after the session`` and exit code 1 when the
       resolved Dockerfile still does not exist (the declined-Dockerfile session).
    9. Return 0.

    Steps 2-7 are wrapped: an ``(OSError, YAMLError, ValueError)`` is ERROR-logged and maps
    to exit code 1 — never a ``click.ClickException``.

    Args:
        template_mode: Whether the bootstrap runs after template scaffolding — existing
            files are silently skipped with an INFO log instead of an overwrite (usages) or
            an overwrite confirmation (conftest).

    Returns:
        0 on success; 1 on a failed step or a missing Dockerfile after the session.
    """
    raise NotImplementedError


@click.command("init")
@click.argument("tpl", required=False)
@click.option(
    "--upgrade",
    is_flag=True,
    default=False,
    help="Migrate a previously scaffolded project; no session, no bootstrap",
)
@click.option(
    "--ref",
    default=None,
    help="Override the git ref: with <tpl> the URL fragment, with --upgrade the migration target",
)
@click.pass_context
def init_cmd(ctx: click.Context, tpl: str | None, ref: str | None, upgrade: bool) -> None:
    """Initialize the project in one of three modes: bare session, template scaffold, or template migration.

    ``pybuggy init`` runs the engine-owned onboarding session followed by the pybuggy
    bootstrap (confirm gates); ``pybuggy init <tpl> [--ref R]`` scaffolds a copier template
    first, then runs the session and the bootstrap with silent-skip gates;
    ``pybuggy init --upgrade [--ref R]`` migrates a previously scaffolded project
    (no session, no bootstrap).

    Args:
        ctx: Click execution context used to control the process exit code.
        tpl: Template source — local path or git URL; absent in bare and upgrade modes.
        ref: Git ref override; None keeps the template's own ref resolution.
        upgrade: Migrate a previously scaffolded project instead of running the session.
    """
    ctx.exit(run_init(tpl, ref, upgrade))
