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

from ...config import GitEntry, SpecEntry
from ...plugin import PluginConfigKeys

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


# Commented example blocks for the complex ``headers``/``loader`` plugin members. These members
# cannot be captured as plain scalars by the interactive build, so their shape is emitted as a
# ``# ``-prefixed example (pinned to the next active key via the ruamel ``before`` comment) instead
# of an active key — documenting the full option surface without producing schema keys (``Config``
# ignores extra scalars).
_HEADERS_BLOCK = (
    "headers: example (skipped complex member)\n"
    "  X-Example: value\n"
    "  default request headers dict"
)
_LOADER_BLOCK = (
    "loader: example (skipped complex member)\n"
    "  packages:\n"
    "    - api\n"
    "  modules: []"
)

# Complex plugin members never captured as scalars; emitted as the commented example blocks above.
_COMPLEX_MEMBERS = frozenset({PluginConfigKeys.HEADERS, PluginConfigKeys.LOADER})


def _git_entry_to_map(git: GitEntry) -> CommentedMap:
    """Render a ``GitEntry`` as a round-trip ``CommentedMap`` preserving field order.

    Args:
        git: The remote git source to render.

    Returns:
        A ``CommentedMap`` with ``url``/``location``/``ref`` in declaration order.
    """
    g = CommentedMap()
    g["url"] = git.url
    g["location"] = git.location
    g["ref"] = git.ref
    return g


def write_pybuggy_config(
    path: Path, scalar_values: dict[str, str | None], specs: dict[str, SpecEntry]
) -> None:
    """Emit ``.goga/tools/pybuggy/config.yml`` from answered scalars and specs.

    Pure, TTY-free, deterministic round-trip emitter. Active scalar values
    (``scalar_values[member.value]`` not None) are written as ``key: value``; skipped optional
    scalars (``None``) and the complex ``HEADERS``/``LOADER`` members are emitted as commented
    records (``# key:``) pinned to the next active key via the ruamel ``before`` comment, so they
    document the full option surface without becoming schema keys (``Config`` ignores extra scalars
    via ``extra="ignore"``). ``base_url`` additionally carries an end-of-line
    ``# required, Jinja2 template`` marker. ``specs`` is emitted as an active section per the
    ``SpecEntry``/``GitEntry`` form and acts as the terminal anchor for any trailing commented
    buffer.

    The canonical key order is the ``PluginConfigKeys`` declaration order (no hardcoded keys); the
    ``HEADERS``/``LOADER`` members are filtered out of the scalar walk.

    Args:
        path: Destination config path; the parent directory is created when missing.
        scalar_values: Mapping of ``PluginConfigKeys.<member>.value`` to the answered string, or
            ``None`` for a skipped optional scalar.
        specs: Ordered mapping of spec name to ``SpecEntry`` (always non-empty by caller contract).

    Raises:
        YAMLError: Forwarded unchanged from ruamel if raised during emission (not expected).
    """
    yaml = YAML()
    yaml.preserve_quotes = True

    doc = CommentedMap()
    pending: list[str] = []

    def _flush(key: str) -> None:
        if pending:
            doc.yaml_set_comment_before_after_key(key, before="\n".join(pending))
            pending.clear()

    for member in PluginConfigKeys:
        if member in _COMPLEX_MEMBERS:
            pending.append(_HEADERS_BLOCK if member is PluginConfigKeys.HEADERS else _LOADER_BLOCK)
            continue

        value = scalar_values.get(member.value)
        if value is None:
            pending.append(f"{member.value}: (skipped optional scalar)")
            continue

        doc[member.value] = value
        _flush(member.value)
        if member is PluginConfigKeys.BASE_URL:
            doc.yaml_add_eol_comment("required, Jinja2 template", PluginConfigKeys.BASE_URL.value)

    specs_map = CommentedMap()
    for name, entry in specs.items():
        spec_map = CommentedMap()
        spec_map["type"] = entry.type
        spec_map["location"] = entry.location
        if entry.git is not None:
            spec_map["git"] = _git_entry_to_map(entry.git)
        specs_map[name] = spec_map

    doc["specs"] = specs_map
    _flush("specs")

    path.parent.mkdir(parents=True, exist_ok=True)
    yaml.dump(doc, path)


def _ask_scalar_values() -> dict[str, str | None]:
    """Interactively collect the scalar ``PluginConfigKeys`` (skipping complex members).

    ``base_url`` is required and re-prompted when empty; the remaining scalars are optional and an
    empty answer maps to ``None`` (a skipped commented record in the emitted config). The canonical
    order is the ``PluginConfigKeys`` declaration order; ``HEADERS``/``LOADER`` are skipped (complex).

    Returns:
        A mapping of ``PluginConfigKeys.<member>.value`` to the answered string or ``None``.

    Raises:
        click.Abort: Forwarded unchanged from any cancelled ``click`` prompt.
    """
    scalar_values: dict[str, str | None] = {}
    for member in PluginConfigKeys:
        if member in _COMPLEX_MEMBERS:
            continue
        if member is PluginConfigKeys.BASE_URL:
            while not (
                val := click.prompt("base_url (required, Jinja2 template)", default="", show_default=False).strip()
            ):
                click.echo("base_url is required")
            scalar_values[member.value] = val
        else:
            val = click.prompt(member.value, default="", show_default=False).strip()
            scalar_values[member.value] = val or None
    return scalar_values


def _ask_spec() -> SpecEntry:
    """Interactively collect one ``SpecEntry`` (its name is validated by the caller).

    ``type`` is restricted to ``swagger``/``openapi`` via ``click.Choice``; ``location`` is required
    (re-prompted when empty); the git source is optional and confirmed first.

    Returns:
        The collected ``SpecEntry``.

    Raises:
        click.Abort: Forwarded unchanged from any cancelled ``click`` prompt.
    """
    t = click.prompt("type", type=click.Choice(["swagger", "openapi"]))
    location = click.prompt("location", default="", show_default=False).strip()
    while not location:
        location = click.prompt("location (required)", default="", show_default=False).strip()
    git = None
    if click.confirm("Add git source?", default=False):
        g_url = click.prompt("git url", default="", show_default=False).strip()
        while not g_url:
            g_url = click.prompt("git url (required)", default="", show_default=False).strip()
        g_loc = click.prompt("git location", default="", show_default=False).strip()
        while not g_loc:
            g_loc = click.prompt("git location (required)", default="", show_default=False).strip()
        g_ref = click.prompt("git ref (optional)", default="").strip() or None
        git = GitEntry(url=g_url, location=g_loc, ref=g_ref)
    return SpecEntry(type=t, location=location, git=git)


def build_pybuggy_config() -> int:
    """Interactively build ``.goga/tools/pybuggy/config.yml`` from prompted answers.

    Testable-seam target: prompts the scalar ``PluginConfigKeys`` (skipping the complex
    ``HEADERS``/``LOADER`` members) and at least one spec, then delegates emission to
    :func:`write_pybuggy_config`. The destination is ``<cwd>/.goga/tools/pybuggy/config.yml``; when it
    already exists a ``y/N`` overwrite confirmation is asked — answering ``no`` skips the build and
    preserves the file (exit code ``0``). ``base_url`` is required (re-prompted when empty); the
    remaining scalars are optional (empty → ``None``, i.e. a skipped commented record). The first
    spec name is required (at least one spec is mandatory); subsequent prompts accept an empty name
    to finish.

    Mirrors :func:`run_goga_init`: it returns an exit code and never raises — a ``click.Abort`` (user
    cancellation) or any other ``Exception`` is logged and echoed, returning ``1``. ``run_init``
    relies on this never-raises contract (it calls this step outside its own try/except).

    Returns:
        0 on success or on a user-declined overwrite (file preserved); 1 on cancellation or failure.
    """
    config_path = Path.cwd() / ".goga" / "tools" / "pybuggy" / "config.yml"
    try:
        if config_path.exists() and not click.confirm("Overwrite existing config?", default=False):
            logger.info("config build skipped", extra={"path": str(config_path)})
            return 0

        scalar_values = _ask_scalar_values()

        specs: dict[str, SpecEntry] = {}
        first = True
        while True:
            name = click.prompt(
                "spec name" + ("" if first else " (empty to finish)"),
                default="",
                show_default=False,
            ).strip()
            if first:
                while not name:
                    name = click.prompt("spec name (required)", default="", show_default=False).strip()
            elif not name:
                break
            specs[name] = _ask_spec()
            first = False

        write_pybuggy_config(config_path, scalar_values, specs)
        return 0
    except click.Abort:
        return 1
    except Exception as exc:
        logger.error("config build failed", extra={"error": str(exc)})
        click.echo(f"Error: {exc}", err=True)
        return 1


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
    """Initialize the goga-project, build the pybuggy tool config, then bootstrap the api usages.

    Algorithm (9 steps):

    1. Resolve the output root as the current working directory.
    2. When ``<cwd>/.goga/config.yml`` does NOT exist, run the interactive goga-project
       initialization in-process via :func:`run_goga_init`; a non-zero exit code is returned
       immediately (no usages are registered).
    3. Build the pybuggy tool config on every call via :func:`build_pybuggy_config`
       (``<cwd>/.goga/tools/pybuggy/config.yml``); a non-zero exit code is returned immediately. On
       success the file is written or, when the user declines the overwrite, skipped and preserved;
       either way init continues.
    4. Discover every ``.usages/*.md`` under the installed ``goga_tool_pybuggy.api`` package
       (including its subcells such as ``asserts``).
    5. Copy each discovered file to ``<cwd>/.goga/usages/cooks/pybuggy/<stem>.md``.
    6. Register the ``pybuggy-<stem>`` keys in ``<cwd>/.goga/config.yml`` under
       ``codemanifest.usages`` via :func:`register_usages` (idempotent, skip-existing).
    7. Append a referencing annotation line per registered usage under ``codemanifest.annotations``
       via :func:`register_annotations` (idempotent by backtick reference, existing text preserved).
    8. Log INFO for added keys/annotations and WARNING for skipped ones.
    9. Return 0.

    Idempotent: repeated runs overwrite the copied files and skip already-registered keys and
    already-referenced annotations, and goga init is skipped on already-initialized projects. Step 3
    is called outside this routine's own try/except — it relies on :func:`build_pybuggy_config`
    never raising (it returns a code on cancellation/failure).

    Returns:
        0 on success; a non-zero exit code when goga init or the config build fails or is cancelled.

    Raises:
        click.ClickException: On a file-write, YAML, or navigation failure during the bootstrap.
    """
    cwd = Path.cwd()

    if not (cwd / ".goga" / "config.yml").exists():
        rc = run_goga_init()
        if rc != 0:
            return rc

    rc = build_pybuggy_config()
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
    """Initialize the goga-project, build .goga/tools/pybuggy/config.yml, then bootstrap the api usages."""
    ctx.exit(run_init())
