"""init command handler — bootstrap consumer-usages of the api cell."""

import importlib.resources
import logging
from pathlib import Path
from typing import Any

import click
from goga.init import FileGenerator, GogaConfigAnswers, InitAnswers, Questionnaire
from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import CommentMark
from ruamel.yaml.scalarstring import LiteralScalarString
from ruamel.yaml.tokens import CommentToken

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

# Numeric plugin members emitted as YAML numbers, matching their ``ApiPlugin`` option types, instead
# of the plain string captured by the interactive prompt. All other scalar members stay plain
# strings. An empty answer (``None``) still becomes a skipped commented record.
_NUMERIC_MEMBERS: dict[PluginConfigKeys, type] = {
    PluginConfigKeys.TIMEOUT: float,
    PluginConfigKeys.RETRIES: int,
    PluginConfigKeys.ASSERT_TIMEOUT: int,
    PluginConfigKeys.ASSERT_DELAY: float,
}


# Column of the ``url``/``location``/``ref`` keys inside a rendered ``git`` block. The git block is
# always nested three mappings deep (``specs -> <name> -> git``) and ruamel's default indent is 2,
# so its child keys sit at column 6. The commented ``# ref:`` line (when ``ref`` is None) must be
# indented to this same column to line up with the active keys.
_GIT_CHILD_INDENT = 6


def _git_entry_to_map(git: GitEntry) -> CommentedMap:
    """Render a ``GitEntry`` as a round-trip ``CommentedMap`` preserving field order.

    ``url``/``location`` are always active keys. ``ref`` is active when set; when ``None`` it is
    emitted as a commented record (``# ref:``) on its own line instead of an empty active key, so the
    option stays documented without producing a schema key (``GitEntry`` defaults ``ref`` to
    ``None``). ruamel drops the ``after`` comment on the last key of a block mapping on emit, but the
    post-value comment slot (``items[key][2]`` — the slot its own loader uses for trailing comments)
    survives, so the commented ``ref`` is attached there on ``location`` — the field immediately
    preceding it — keeping it at the position where ``ref`` would otherwise appear, on its own line.

    Args:
        git: The remote git source to render.

    Returns:
        A ``CommentedMap`` with ``url``/``location`` (and ``ref`` when set) in declaration order.
    """
    g = CommentedMap()
    g["url"] = git.url
    g["location"] = git.location
    if git.ref is not None:
        g["ref"] = git.ref
    else:
        indent = " " * _GIT_CHILD_INDENT
        token = CommentToken(f"\n{indent}# ref:\n", CommentMark(_GIT_CHILD_INDENT))
        g.ca.items.setdefault("location", [None, None, None, None])[2] = token
    return g


def write_pybuggy_config(
    path: Path, scalar_values: dict[str, str | None], specs: dict[str, SpecEntry]
) -> None:
    """Emit ``.goga/tools/pybuggy/config.yml`` from answered scalars and specs.

    Pure, TTY-free, deterministic round-trip emitter. Active scalar values
    (``scalar_values[member.value]`` not None) are written as ``key: value`` — numeric members
    (``timeout``/``retries``/``assert_timeout``/``assert_delay``) are coerced to their ``ApiPlugin``
    option type (``float``/``int``) so the scalar is a number, not a quoted string; skipped optional
    scalars (``None``) and the complex ``HEADERS``/``LOADER`` members are emitted as commented
    records (``# key:``) pinned to the next active key via the ruamel ``before`` comment, so they
    document the full option surface without becoming schema keys (``Config`` ignores extra scalars
    via ``extra="ignore"``). ``base_url`` is always a Jinja2 template, so it is always emitted as a
    literal block scalar with the clip indicator (``|``) — a long plain scalar would be line-wrapped
    by ruamel and mangle the template. A trailing newline is appended so ruamel emits ``|`` rather
    than ``|-`` (harmless: ``render_base_url`` strips all whitespace); the ``# required, Jinja2
    template`` marker sits on its own line above the key. ``specs`` is emitted as an active section
    per the ``SpecEntry``/``GitEntry`` form and acts as the terminal anchor for any trailing
    commented buffer.

    The canonical key order is the ``PluginConfigKeys`` declaration order (no hardcoded keys); the
    ``HEADERS``/``LOADER`` members are filtered out of the scalar walk.

    Args:
        path: Destination config path; the parent directory is created when missing.
        scalar_values: Mapping of ``PluginConfigKeys.<member>.value`` to the answered string, or
            ``None`` for a skipped optional scalar.
        specs: Ordered mapping of spec name to ``SpecEntry`` (always non-empty by caller contract).

    Raises:
        ValueError: If a numeric member's answer cannot coerce to its target type.
        YAMLError: Forwarded unchanged from ruamel if raised during emission (not expected).
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    # ruamel's default ``best_width`` (80) folds long plain scalars — e.g. a git SSH clone URL — onto
    # a continuation line, breaking ``url: <value>`` across two lines. Raise the width so plain
    # scalars (the git ``url``) stay on one line; block scalars (``base_url``) are unaffected.
    yaml.width = 4096

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

        # base_url is always a Jinja2 template that must survive round-trip verbatim, so it is
        # always emitted as a literal block scalar (``|``): a long plain scalar would be line-wrapped
        # by ruamel and mangle the template, and a multi-line template must keep its line breaks. The
        # ``# required, Jinja2 template`` marker sits on its own line above the key (a same-line
        # comment lands awkwardly after the block). Other scalars stay plain.
        if member is PluginConfigKeys.BASE_URL:
            # Append a trailing newline so ruamel emits the clip indicator (``|``) instead of the
            # strip indicator (``|-``); render_base_url strips all whitespace, so the added newline
            # is harmless and the template still renders to the same URL.
            doc[member.value] = LiteralScalarString(value + "\n")
            _flush(member.value)
            doc.yaml_set_comment_before_after_key(
                PluginConfigKeys.BASE_URL.value, before="required, Jinja2 template"
            )
        else:
            # Numeric members (timeout/retries/assert_timeout/assert_delay) are coerced to their
            # ``ApiPlugin`` option type so the emitted scalar is a number, not a quoted string — a
            # non-numeric answer raises ValueError (surfaced by build_pybuggy_config as exit code 1).
            target_type = _NUMERIC_MEMBERS.get(member)
            doc[member.value] = target_type(value) if target_type is not None else value
            _flush(member.value)

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


# Human-readable prompt text for each optional scalar plugin key — mirrors the
# ``ApiPlugin`` option docstrings so the user knows what every field is for.
# ``BASE_URL`` is collected separately as a (possibly multi-line) Jinja2 template;
# ``HEADERS``/``LOADER`` are complex members and never surveyed here.
_SCALAR_PROMPTS: dict[PluginConfigKeys, str] = {
    PluginConfigKeys.TIMEOUT: (
        "timeout — request timeout in seconds for HTTP calls (optional). Enter to skip"
    ),
    PluginConfigKeys.DATA_KEY: (
        "data_key — response body key treated as the success payload (optional). Enter to skip"
    ),
    PluginConfigKeys.ERROR_KEY: (
        "error_key — response body key treated as the error payload (optional). Enter to skip"
    ),
    PluginConfigKeys.RETRIES: (
        "retries — flaky rerun count for failing tests across the suite (optional). Enter to skip"
    ),
    PluginConfigKeys.ASSERT_TIMEOUT: (
        "assert_timeout — baseline polling timeout in seconds for retrying assertions "
        "(optional). Enter to skip"
    ),
    PluginConfigKeys.ASSERT_DELAY: (
        "assert_delay — seconds between assertion polling attempts (optional). Enter to skip"
    ),
    PluginConfigKeys.ASSERT_FIELD_CLASS: (
        'assert_field_class — dotted "module:Class" of a custom AssertField subclass '
        "(optional). Enter to skip"
    ),
    PluginConfigKeys.ASSERT_RESPONSE_CLASS: (
        'assert_response_class — dotted "module:Class" of a custom Expected subclass '
        "(optional). Enter to skip"
    ),
}


def _ask_scalar_values() -> dict[str, str | None]:
    """Interactively collect the scalar ``PluginConfigKeys`` (skipping complex members).

    ``base_url`` is required and re-prompted when empty; the remaining scalars are optional and an
    empty answer maps to ``None`` (a skipped commented record in the emitted config). Each prompt
    carries a descriptive text stating what the field is for. The canonical order is the
    ``PluginConfigKeys`` declaration order; ``HEADERS``/``LOADER`` are skipped (complex).

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
                val := click.prompt(
                    "base_url — service base URL as a Jinja2 template (required)",
                    default="",
                    show_default=False,
                ).strip()
            ):
                click.echo("base_url is required")
            scalar_values[member.value] = val
        else:
            val = click.prompt(_SCALAR_PROMPTS[member], default="", show_default=False).strip()
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
    t = click.prompt("spec type — format of the spec file", type=click.Choice(["swagger", "openapi"]))
    location = click.prompt(
        "location — path from the project root to the spec file",
        default="",
        show_default=False,
    ).strip()
    while not location:
        location = click.prompt(
            "location — path from the project root to the spec file (required)",
            default="",
            show_default=False,
        ).strip()
    git = None
    if click.confirm("Add a git source for this spec?", default=False):
        g_url = click.prompt(
            "git url — clone URL of the repository holding the spec",
            default="",
            show_default=False,
        ).strip()
        while not g_url:
            g_url = click.prompt(
                "git url — clone URL of the repository holding the spec (required)",
                default="",
                show_default=False,
            ).strip()
        g_loc = click.prompt(
            "git location — path inside the repository to the spec file",
            default="",
            show_default=False,
        ).strip()
        while not g_loc:
            g_loc = click.prompt(
                "git location — path inside the repository to the spec file (required)",
                default="",
                show_default=False,
            ).strip()
        g_ref = click.prompt(
            "git ref — branch or tag to clone (optional, defaults to the remote default branch)",
            default="",
        ).strip() or None
        git = GitEntry(url=g_url, location=g_loc, ref=g_ref)
    return SpecEntry(type=t, location=location, git=git)


def build_pybuggy_config() -> int:
    """Interactively build ``.goga/tools/pybuggy/config.yml`` from prompted answers.

    Testable-seam target: prompts the scalar ``PluginConfigKeys`` (skipping the complex
    ``HEADERS``/``LOADER`` members) and at least one spec, then delegates emission to
    :func:`write_pybuggy_config`. The destination ``<cwd>/.goga/tools/pybuggy/config.yml`` is always
    (over)written — no existence check and no overwrite confirmation — so every run regenerates it.
    ``base_url`` is required (re-prompted when empty); the remaining scalars are optional (empty →
    ``None``, i.e. a skipped commented record). The first spec name is required (at least one spec
    is mandatory); subsequent prompts accept an empty name to finish.

    Mirrors :func:`run_goga_init`: it returns an exit code and never raises — a ``click.Abort`` (user
    cancellation) or any other ``Exception`` is logged and echoed, returning ``1``. ``run_init``
    relies on this never-raises contract (it calls this step outside its own try/except).

    Returns:
        0 on success; 1 on cancellation or failure.
    """
    config_path = Path.cwd() / ".goga" / "tools" / "pybuggy" / "config.yml"
    try:
        scalar_values = _ask_scalar_values()

        specs: dict[str, SpecEntry] = {}
        first = True
        while True:
            name = click.prompt(
                "spec name — unique name for this spec (the list/info commands use it as a key)"
                + ("" if first else " (empty to finish)"),
                default="",
                show_default=False,
            ).strip()
            if first:
                while not name:
                    name = click.prompt(
                        "spec name — unique name for this spec (required)",
                        default="",
                        show_default=False,
                    ).strip()
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


# Mandatory Dockerfile path. goga's ``ask_dockerfile_path`` is optional (the user may decline and
# skip Dockerfile creation); pybuggy mandates the Dockerfile — it is always created at this path and
# the top-level ``dockerfile`` field is always emitted into ``.goga/config.yml``. The value matches
# goga's own prompt default so the on-disk result is what the user would have accepted anyway.
_DOCKERFILE_PATH = ".goga/Dockerfile"


# Pybuggy install line appended to the goga-generated Dockerfile. The consumer installs pybuggy via
# the ``goga`` installer (not pip), pinned to the hardcoded ``0.1.x`` version line.
_INSTALL_LINE = "RUN goga install pybuggy -v 0.1.x\n"


def install_pybuggy(dockerfile_path: Path) -> str | None:
    """Append the pybuggy-install ``RUN`` line to the goga-generated Dockerfile.

    goga ``FileGenerator.generate`` writes the Dockerfile as ``FROM {dockerfile_base_image}\\n`` (the
    FROM baseline, distinct from the top-level built ``image`` name); this routine appends
    ``RUN goga install pybuggy -v 0.1.x`` so the consumer's test image installs pybuggy via the goga
    installer, pinned to the hardcoded ``0.1.x`` version line.

    No-op when ``dockerfile_path`` does not exist (e.g. ``FileGenerator`` is mocked in tests, so the
    goga step wrote no file). Idempotent — skips when the install line is already present.

    Args:
        dockerfile_path: Path to the Dockerfile created by goga ``FileGenerator`` (cwd-relative,
            matching ``_DOCKERFILE_PATH``).

    Returns:
        The appended ``RUN`` line text, or ``None`` when nothing was appended (file absent or the line
        already present).
    """
    if not dockerfile_path.exists():
        return None

    content = dockerfile_path.read_text(encoding="utf-8")
    if _INSTALL_LINE in content:
        return None

    if content and not content.endswith("\n"):
        content += "\n"

    dockerfile_path.write_text(content + _INSTALL_LINE, encoding="utf-8")
    logger.info("pybuggy install line added to Dockerfile")
    return _INSTALL_LINE


def run_goga_init() -> int:
    """Initialize the goga-project in-process, tailored for a Python project.

    Drives the per-field ``Questionnaire`` methods individually (instead of goga's universal
    ``InitLogic`` flow) so the language is fixed to ``"python"`` (pybuggy is a Python project). The
    Dockerfile is mandatory, so the image is split: ``ask_image_name("python")`` captures the name
    of the image built from the Dockerfile (top-level ``image`` field), and ``ask_base_image("python")``
    captures the ``FROM`` baseline (``dockerfile_base_image`` field). goga's pre-built-pull
    ``ask_image`` is NOT used (that is the no-Dockerfile case). The collected answers are assembled
    into a ``GogaConfigAnswers`` and file generation is delegated to
    ``FileGenerator().generate(InitAnswers(...))``.

    The Dockerfile is mandatory: ``dockerfile_path`` is hardcoded to ``_DOCKERFILE_PATH``
    (``.goga/Dockerfile``) instead of goga's optional ``ask_dockerfile_path`` (which may return
    ``None`` and skip creation), so ``FileGenerator`` always creates the Dockerfile (``FROM
    {dockerfile_base_image}``) and always emits the top-level ``dockerfile`` field into
    ``.goga/config.yml``.

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
        # Dockerfile is mandatory → ask for the built-image NAME (top-level `image`) and the FROM
        # baseline separately; goga's ``ask_image`` (pre-built pull image) is the no-Dockerfile case.
        image = questionnaire.ask_image_name(language)
        dockerfile_base_image = questionnaire.ask_base_image(language)
        # Hardcoded mandatory path instead of goga's optional ``ask_dockerfile_path`` (which can
        # return None and skip creation); ``FileGenerator`` always creates it from here.
        dockerfile_path = _DOCKERFILE_PATH
        env = questionnaire.ask_env(agent)
        pipeline_agent = questionnaire.ask_pipeline_agent()
        pipeline_env = questionnaire.ask_pipeline_env(pipeline_agent)

        config = GogaConfigAnswers(
            language=language,
            agent=agent,
            image=image,
            dockerfile_base_image=dockerfile_base_image,
            pipeline_agent=pipeline_agent,
            pipeline_env=pipeline_env,
            env=env,
            dockerfile_path=dockerfile_path,
            codemanifest_usages=codemanifest_usages,
            codemanifest_annotations=codemanifest_annotations,
        )

        generator.generate(InitAnswers(goga_config=config))
        # Append the hardcoded pybuggy install line to the Dockerfile goga just generated.
        install_pybuggy(Path(_DOCKERFILE_PATH))
        return 0
    except click.Abort:
        return 1
    except Exception as exc:
        logger.error("goga init flow failed", extra={"error": str(exc)})
        click.echo(f"Error: {exc}", err=True)
        return 1


def _should_rebuild(path: Path, prompt: str) -> bool:
    """Decide whether to (re)build the config at ``path`` during ``init``.

    Builds unconditionally when the file is absent (nothing to recreate); when it exists, asks the user via
    ``click.confirm`` (default ``no``) and rebuilds only on an explicit ``yes``. Isolating this decision keeps
    :func:`run_init` under the cyclomatic-complexity cap.

    Args:
        path: The config file whose existence gates the rebuild.
        prompt: The confirmation question shown when ``path`` already exists.

    Returns:
        ``True`` when the config should be (re)built; ``False`` when it exists and the user declined.
    """
    return not path.exists() or click.confirm(prompt, default=False)


def _log_registration(
    usage_keys: dict[str, str],
    added_usage_keys: list[str],
    annotation_lines: dict[str, str],
    added_annotation_keys: list[str],
) -> None:
    """Log INFO for newly-registered usages/annotations and WARNING for already-present (skipped) ones.

    Extracted from :func:`run_init` to keep it under the cyclomatic-complexity cap. A key counts as added when it
    appears in the corresponding ``added_*`` list returned by :func:`register_usages`/:func:`register_annotations`.

    Args:
        usage_keys: Full mapping of ``pybuggy-<stem>`` to the copied usage path.
        added_usage_keys: Keys actually added by :func:`register_usages` (pre-existing ones excluded).
        annotation_lines: Full mapping of ``pybuggy-<stem>`` to its annotation line.
        added_annotation_keys: Keys whose annotation line was actually appended by :func:`register_annotations`.
    """
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


def run_init() -> int:
    """Initialize the goga-project, build the pybuggy tool config, then bootstrap the api usages.

    Algorithm (9 steps):

    1. Resolve the output root as the current working directory.
    2. Goga-project config: when ``<cwd>/.goga/config.yml`` does NOT exist, run the interactive
       goga-project initialization in-process via :func:`run_goga_init`; when it DOES exist, ask
       (``click.confirm``, default ``no``) whether to re-run goga init and overwrite it, and only
       re-run on ``yes``. A non-zero exit code is returned immediately (no usages are registered).
    3. Pybuggy tool config: when ``<cwd>/.goga/tools/pybuggy/config.yml`` does NOT exist, build it
       via :func:`build_pybuggy_config`; when it DOES exist, ask (``click.confirm``, default ``no``)
       whether to rebuild it, and only rebuild on ``yes``. A non-zero exit code is returned
       immediately. :func:`build_pybuggy_config` itself neither checks for nor confirms an existing
       file (always overwrites) — the recreate decision lives here, in the orchestrator.
    4. Discover every ``.usages/*.md`` under the installed ``goga_tool_pybuggy.api`` package
       (including its subcells such as ``asserts``).
    5. Copy each discovered file to ``<cwd>/.goga/usages/cooks/pybuggy/<stem>.md``.
    6. Register the ``pybuggy-<stem>`` keys in ``<cwd>/.goga/config.yml`` under
       ``codemanifest.usages`` via :func:`register_usages` (idempotent, skip-existing).
    7. Append a referencing annotation line per registered usage under ``codemanifest.annotations``
       via :func:`register_annotations` (idempotent by backtick reference, existing text preserved).
    8. Log INFO for added keys/annotations and WARNING for skipped ones.
    9. Return 0.

    Each config is created when absent and only recreated on explicit confirmation when present, so a
    plain repeat run (both confirms declined) just re-copies the usages and skips already-registered
    keys/annotations — idempotent. Steps 2 and 3 are called outside this routine's own try/except —
    they rely on :func:`run_goga_init`/:func:`build_pybuggy_config` never raising (they return a code
    on cancellation/failure).

    Returns:
        0 on success; a non-zero exit code when goga init or the config build fails or is cancelled.

    Raises:
        click.ClickException: On a file-write, YAML, or navigation failure during the bootstrap.
    """
    cwd = Path.cwd()
    goga_config = cwd / ".goga" / "config.yml"
    pybuggy_config = cwd / ".goga" / "tools" / "pybuggy" / "config.yml"

    # Goga-project config: create when absent; recreate only on explicit confirmation (overwriting it
    # can discard user-customized codemanifest entries beyond pybuggy's own).
    if _should_rebuild(
        goga_config, ".goga/config.yml exists — re-run goga init and overwrite it?"
    ):
        rc = run_goga_init()
        if rc != 0:
            return rc

    # Pybuggy tool config: build when absent; rebuild only on explicit confirmation.
    if _should_rebuild(
        pybuggy_config, ".goga/tools/pybuggy/config.yml exists — rebuild it from the survey?"
    ):
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

    _log_registration(usage_keys, added_usage_keys, annotation_lines, added_annotation_keys)

    return 0


@click.command("init")
@click.pass_context
def init_cmd(ctx: click.Context) -> None:
    """Initialize the goga-project, build .goga/tools/pybuggy/config.yml, then bootstrap the api usages."""
    ctx.exit(run_init())
