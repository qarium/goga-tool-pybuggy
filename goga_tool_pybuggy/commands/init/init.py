"""init command handler — bootstrap consumer-usages of the api cell."""

import importlib.resources
import logging
from pathlib import Path
from typing import Any

import click
from goga.init import FileGenerator, GogaConfigAnswers, InitAnswers, Questionnaire
from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import LiteralScalarString

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


def _ensure_map(parent: CommentedMap, key: str) -> CommentedMap:
    """Return ``parent[key]`` as a ``CommentedMap``, creating it when missing or null.

    Args:
        parent: The mapping that may hold ``key``.
        key: The key to resolve or create.

    Returns:
        The existing or freshly created ``CommentedMap`` at ``parent[key]``.

    Raises:
        ValueError: If ``key`` exists but holds a non-mapping value (never overwrites user data).
    """
    if key not in parent or parent[key] is None:
        parent[key] = CommentedMap()

        return parent[key]

    if isinstance(parent[key], CommentedMap):
        return parent[key]

    raise ValueError(f"{key!r} is not a mapping and cannot be extended")


def register_usages(config_path: Path, usage_keys: dict[str, str]) -> list[str]:
    """Register ``usage_keys`` in the consumer ``.goga/config.yml`` under ``codemanifest.usages``.

    Round-trip edits the file with ``ruamel.yaml`` so comments, key order, quotes, and block-scalars
    are preserved. Existing keys (including user-defined ones outside this command) are never
    overwritten, which makes the run idempotent. A minimal file carrying the ``codemanifest.usages``
    block is created when no file exists.

    Args:
        config_path: Path to the consumer ``.goga/config.yml``.
        usage_keys: Mapping of ``pybuggy-<stem>`` to the relative path of the copied usage file.

    Returns:
        The keys actually added; pre-existing keys are skipped and excluded.

    Raises:
        ValueError: If ``codemanifest`` or ``usages`` exists but is not a mapping.
        YAMLError: If an existing file contains invalid YAML.
    """
    yaml = YAML()
    yaml.preserve_quotes = True

    if config_path.exists():
        data = yaml.load(config_path)
        if data is None:
            data = CommentedMap()
    else:
        data = CommentedMap()

    codemanifest = _ensure_map(data, "codemanifest")
    usages = _ensure_map(codemanifest, "usages")

    added_keys: list[str] = []
    for key, value in usage_keys.items():
        if key in usages:
            continue

        usages[key] = value
        added_keys.append(key)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    yaml.dump(data, config_path)

    return added_keys


def _ensure_scalar(parent: CommentedMap, key: str) -> str:
    """Return ``parent[key]`` as a string scalar, empty when missing or null.

    Args:
        parent: The mapping that may hold ``key``.
        key: The key to resolve or read.

    Returns:
        The existing string value, or an empty string when ``key`` is absent or null.

    Raises:
        ValueError: If ``key`` exists but holds a non-scalar value (mapping/list); never
            overwrites user data.
    """
    if key not in parent or parent[key] is None:
        return ""

    value = parent[key]
    if isinstance(value, str):
        return value

    raise ValueError(f"{key!r} is not a scalar and cannot be extended")


# Hand-authored annotation line per registered pybuggy usage stem (key without the ``pybuggy-``
# prefix). Unknown stems fall back to a bare backtick reference so future api subcells are still
# bound to the contract — the DSL requires every connected usage to be referenced in an annotation.
PYBUGGY_ANNOTATIONS: dict[str, str] = {
    "api": (
        "Use `pybuggy-api` for executing HTTP requests from test fixtures and checking responses."
    ),
    "asserts": (
        "Use `pybuggy-asserts` for response-level and field-level assertions on HTTP responses."
    ),
}


def _annotation_for(stem: str) -> str:
    """Return the annotation line for a discovered pybuggy usage ``stem``.

    Known stems resolve to a hand-authored description; unknown stems fall back to a bare backtick
    reference (`` `pybuggy-<stem>` ``) so every connected usage is still bound to the contract.
    """
    return PYBUGGY_ANNOTATIONS.get(stem, f"`pybuggy-{stem}`")


def register_annotations(config_path: Path, annotation_lines: dict[str, str]) -> list[str]:
    """Append ``annotation_lines`` into the consumer ``.goga/config.yml`` under ``codemanifest.annotations``.

    Each entry maps a ``pybuggy-<stem>`` usage key to one annotation line. A line is skipped when its
    backtick reference (`` `pybuggy-<stem>` ``) already appears in the existing annotations, which
    makes the run idempotent. The existing annotation text (e.g. the base convention annotations
    written by goga init) is preserved — only missing lines are appended. Round-trips the file with
    ``ruamel.yaml`` so comments, key order, quotes, and block-scalars are preserved, and writes the
    value back as a literal block scalar (``|``).

    Args:
        config_path: Path to the consumer ``.goga/config.yml``.
        annotation_lines: Mapping of ``pybuggy-<stem>`` to the annotation line to append.

    Returns:
        The keys whose annotation line was actually added; pre-referenced keys are skipped.

    Raises:
        ValueError: If ``codemanifest`` is not a mapping, or ``annotations`` exists but is not a
            scalar.
        YAMLError: If an existing file contains invalid YAML.
    """
    yaml = YAML()
    yaml.preserve_quotes = True

    if config_path.exists():
        data = yaml.load(config_path)
        if data is None:
            data = CommentedMap()
    else:
        data = CommentedMap()

    codemanifest = _ensure_map(data, "codemanifest")
    text = _ensure_scalar(codemanifest, "annotations")

    added_keys: list[str] = []
    for key, line in annotation_lines.items():
        needle = f"`{key}`"
        if needle in text:
            continue

        text = f"{text}{line}\n" if text else f"{line}\n"
        added_keys.append(key)

    if added_keys:
        codemanifest["annotations"] = LiteralScalarString(text)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    yaml.dump(data, config_path)

    return added_keys


def run_goga_init() -> int:
    """Initialize the goga-project in-process, tailored for a Python project.

    Drives the per-field ``Questionnaire`` methods individually (instead of goga's universal
    ``InitLogic`` flow) so the language is fixed to ``"python"`` (pybuggy is a Python project) and
    the Docker image is selected from the python-only set via ``ask_image("python")``. The
    collected answers are assembled into a ``GogaConfigAnswers`` and file generation is delegated
    to ``FileGenerator().generate(InitAnswers(...))``.

    Interactive (TTY prompts via click); callers and tests stub this routine via monkeypatch.

    Returns:
        0 on success; 1 on user cancellation (``click.Abort``) or a generation failure. The
        routine returns a code and never raises, so ``run_init`` — which calls it outside its own
        try/except — can propagate the code cleanly.
    """
    questionnaire = Questionnaire()
    generator = FileGenerator()

    try:
        language = "python"

        usages_prefill, annotations_prefill = questionnaire.ask_base_convention()
        codemanifest_usages = questionnaire.ask_codemanifest_usages(usages_prefill)
        codemanifest_annotations = questionnaire.ask_codemanifest_annotations(annotations_prefill)
        agent = questionnaire.ask_agent()
        image = questionnaire.ask_image(language)
        dockerfile_path = questionnaire.ask_dockerfile_path()
        env = questionnaire.ask_env(agent)
        pipeline_agent = questionnaire.ask_pipeline_agent(agent)
        pipeline_env = questionnaire.ask_pipeline_env(pipeline_agent)

        config = GogaConfigAnswers(
            language=language,
            agent=agent,
            image=image,
            pipeline_agent=pipeline_agent,
            pipeline_env=pipeline_env,
            env=env,
            dockerfile_path=dockerfile_path,
            codemanifest_usages=codemanifest_usages,
            codemanifest_annotations=codemanifest_annotations,
        )

        generator.generate(InitAnswers(goga_config=config))
        return 0
    except click.Abort:
        return 1
    except Exception as exc:
        logger.error("goga init flow failed", extra={"error": str(exc)})
        click.echo(f"Error: {exc}", err=True)
        return 1


def run_init() -> int:
    """Initialize the goga-project (when not yet initialized) and bootstrap the api usages.

    When ``<cwd>/.goga/config.yml`` is absent, the interactive goga-project initialization is run
    in-process via ``run_goga_init``; a non-zero exit code is returned immediately (no usages are
    registered). After that, every ``.usages/*.md`` under the installed ``goga_tool_pybuggy.api`` package
    (including its subcells such as ``asserts``) is copied to
    ``<cwd>/.goga/usages/cooks/pybuggy/<stem>.md`` and the ``pybuggy-<stem>`` keys are registered in
    ``<cwd>/.goga/config.yml`` under ``codemanifest.usages``. A referencing annotation line is also
    appended under ``codemanifest.annotations`` for each registered usage (the existing annotation
    text is preserved). Idempotent: repeated runs overwrite the copied files and skip already-
    registered keys and already-referenced annotations, and goga init is skipped on
    already-initialized projects.

    Returns:
        0 on success; a non-zero goga-init exit code when goga init fails or is cancelled.

    Raises:
        click.ClickException: On a file-write, YAML, or navigation failure during the bootstrap.
    """
    cwd = Path.cwd()

    if not (cwd / ".goga" / "config.yml").exists():
        rc = run_goga_init()
        if rc != 0:
            return rc

    try:
        discovered = _discover_usages(importlib.resources.files("goga_tool_pybuggy.api"))

        for stem, text in discovered:
            dest = cwd / ".goga" / "usages" / "cooks" / "pybuggy" / f"{stem}.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")

        usage_keys = {f"pybuggy-{stem}": f".goga/usages/cooks/pybuggy/{stem}.md" for stem, _ in discovered}
        added_usage_keys = register_usages(cwd / ".goga" / "config.yml", usage_keys)

        annotation_lines = {f"pybuggy-{stem}": _annotation_for(stem) for stem, _ in discovered}
        added_annotation_keys = register_annotations(cwd / ".goga" / "config.yml", annotation_lines)
    except (OSError, YAMLError, ValueError) as e:
        raise click.ClickException(str(e)) from e

    for key, path in usage_keys.items():
        if key in added_usage_keys:
            logger.info("usage registered", extra={"key": key, "path": path})
        else:
            logger.warning("usage already registered, skipped", extra={"key": key})

    for key in annotation_lines:
        if key in added_annotation_keys:
            logger.info("annotation registered", extra={"key": key})
        else:
            logger.warning("annotation already registered, skipped", extra={"key": key})

    return 0


@click.command("init")
@click.pass_context
def init_cmd(ctx: click.Context) -> None:
    """Initialize the goga-project (when not yet initialized), then bootstrap the api cell's consumer-usages."""
    ctx.exit(run_init())
