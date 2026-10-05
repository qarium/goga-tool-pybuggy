"""init command handler — initializes the pybuggy test environment in three modes.

``run_init`` dispatches on the CLI-flag-resolved mode: bare, template, or upgrade.
"""

import importlib.resources
import logging
from pathlib import Path
from typing import Any

import click
import yaml
from goga.scaffold import Scaffold
from ruamel.yaml import YAMLError

from .bootstrap import (
    document_config_examples,
    ensure_review_skip,
    install_pybuggy,
    register_annotations,
    register_usages,
    write_pybuggy_conftest,
    write_test_convention,
)
from .session import run_session

logger = logging.getLogger(__name__)


def _walk(directory: Any, discovered: list[tuple[str, str]]) -> None:
    """Recurse into ``directory`` collecting ``.usages/*.md`` files as ``(stem, text)``.

    A ``.usages`` directory is a leaf; any other directory is recursed into.
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


# Hand-authored annotation line per usage stem; unknown stems fall back to a bare backtick
# reference — the DSL requires every connected usage to be referenced in an annotation.
PYBUGGY_ANNOTATIONS: dict[str, str] = {
    "api": ("Use `pybuggy-api` for executing HTTP requests from test fixtures and checking responses."),
    "asserts": ("Use `pybuggy-asserts` for response-level and field-level assertions on HTTP responses."),
}

# Annotation line for the ``conventions`` usage key — the sole source registered under ``codemanifest.annotations``.
_CONVENTION_LINE = "Use `conventions` for test code: pytest configuration, logging, and Allure reporting."


def _annotation_for(stem: str) -> str:
    """Return the annotation line for a discovered pybuggy usage ``stem``.

    Known stems resolve to a hand-authored description; unknown stems to a bare backtick reference.
    """
    return PYBUGGY_ANNOTATIONS.get(stem, f"`pybuggy-{stem}`")


def _log_registration(
    usage_keys: dict[str, str],
    added_usage_keys: list[str],
    annotation_lines: dict[str, str],
    changed_annotation_keys: list[str],
) -> None:
    """Log INFO for newly-registered usages/annotations and WARNING for already-present (skipped) ones.

    Extracted from :func:`run_bootstrap` to keep it under the cyclomatic-complexity cap.

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


def _gate_conftest(cwd: Path, template_mode: bool) -> None:
    """Deliver the root ``conftest.py`` through the mode-dependent gate (bootstrap step 7).

    Absent file → written; existing file → INFO skip in template mode, ``click.confirm`` (default no) in bare mode.

    Args:
        cwd: The target project root whose ``conftest.py`` is (re)generated.
        template_mode: Whether the bootstrap runs in template mode (silent skip instead of a prompt).
    """
    conftest = cwd / "conftest.py"

    if not conftest.exists():
        write_pybuggy_conftest(conftest)
    elif template_mode:
        logger.info("existing file kept untouched", extra={"path": str(conftest)})
    elif click.confirm("conftest.py exists — overwrite it?", default=False):
        write_pybuggy_conftest(conftest)


# The three init modes (the contract fixes the literal strings).
# Module-level constants so each mode value has a single source.
_BARE = "bare"
_TEMPLATE = "template"
_UPGRADE = "upgrade"

# Fallback Dockerfile path when the config carries no ``dockerfile`` field; matches the engine's prompt default.
_DOCKERFILE_DEFAULT = Path(".goga") / "Dockerfile"


def _resolve_dockerfile_path(config: Path) -> Path:
    """Resolve the project's Dockerfile path from the consumer config.

    A missing config or a missing/invalid ``dockerfile`` field falls back to ``_DOCKERFILE_DEFAULT``.

    Args:
        config: Path to the consumer ``.goga/config.yml``.

    Returns:
        The resolved Dockerfile path (existing or not).
    """
    if config.exists():
        try:
            document = yaml.safe_load(config.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            document = None

        if isinstance(document, dict):
            field = document.get("dockerfile")

            if isinstance(field, str) and field:
                return Path(field)

    return _DOCKERFILE_DEFAULT


def resolve_init_mode(tpl: str | None, ref: str | None, upgrade: bool) -> str:
    """Resolve the init mode from the CLI flags — pure validation and mapping.

    Flag values reach the engine verbatim — empty-string normalization is the engine's concern.

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

    The engine's and the session's non-zero codes are propagated unchanged; the bare guard precedes every write.

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

    # Already-initialized guard — bare mode only, mirroring `goga init`: refuses before
    # any session or bootstrap write.
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
    """Run the 10-step post-session bootstrap with mode-dependent gates.

    Steps 2-8 are wrapped: an ``(OSError, YAMLError, ValueError)`` is ERROR-logged and mapped to exit code 1.

    Args:
        template_mode: Whether the bootstrap runs after template scaffolding (silent-skip gates
            instead of overwrite or confirmation prompts).

    Returns:
        0 on success; 1 on a failed step or a missing Dockerfile after the session.
    """
    cwd = Path.cwd()
    config = cwd / ".goga" / "config.yml"

    try:
        discovered = _discover_usages(importlib.resources.files("goga_tool_pybuggy.api"))

        for stem, text in discovered:
            dest = cwd / ".goga" / "usages" / "cooks" / "pybuggy" / f"{stem}.md"

            if dest.exists() and template_mode:
                logger.info("existing file kept untouched", extra={"path": str(dest)})
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")

        documented = document_config_examples(cwd / ".goga" / "tools" / "pybuggy" / "config.yml")

        if documented:
            logger.info("tool config examples documented", extra={"count": len(documented)})

        # The conventions slot is delivered skip-if-exists in BOTH modes — never overwritten, never prompted.
        slot = cwd / ".goga" / "usages" / "conventions.md"

        if slot.exists():
            logger.info("existing file kept untouched", extra={"path": str(slot)})
        else:
            write_test_convention(slot)

        # Always-run augmentations — they apply to whatever the target directory already contains.
        ensure_review_skip(config)

        dockerfile = _resolve_dockerfile_path(config)
        install_pybuggy(dockerfile)

        usage_keys = {f"pybuggy-{stem}": f".goga/usages/cooks/pybuggy/{stem}.md" for stem, _ in discovered}
        usage_keys["conventions"] = ".goga/usages/conventions.md"
        annotation_lines = {f"pybuggy-{stem}": _annotation_for(stem) for stem, _ in discovered}
        annotation_lines["conventions"] = _CONVENTION_LINE

        added_usage_keys = register_usages(config, usage_keys)
        changed_annotation_keys = register_annotations(config, annotation_lines)
        _log_registration(usage_keys, added_usage_keys, annotation_lines, changed_annotation_keys)

        _gate_conftest(cwd, template_mode)
    except (OSError, YAMLError, ValueError) as e:
        logger.error("onboarding bootstrap failed", extra={"error": str(e)})
        return 1

    # The mandatory-Dockerfile invariant — a declined-Dockerfile session fails the command.
    if not dockerfile.exists():
        logger.error("Dockerfile missing after the session", extra={"path": str(dockerfile)})
        return 1

    return 0


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

    The gates differ by mode: confirm (bare), silent-skip (template), none (upgrade).

    Args:
        ctx: Click execution context used to control the process exit code.
        tpl: Template source — local path or git URL; absent in bare and upgrade modes.
        ref: Git ref override; None keeps the template's own ref resolution.
        upgrade: Migrate a previously scaffolded project instead of running the session.
    """
    ctx.exit(run_init(tpl, ref, upgrade))
