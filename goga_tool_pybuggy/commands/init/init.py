"""init command handler — bootstraps the pybuggy test environment.

The bootstrap covers the test-convention slot, api usages, tool config, and conftest.
"""

import importlib.resources
import logging
from pathlib import Path
from typing import Any

import click
from goga.onboarding import FileGenerator, GogaConfigAnswers, InitAnswers, Questionnaire
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
        usage_keys: Mapping of usage key to the relative path of the usage file to register
            (``pybuggy-<stem>`` → ``.goga/usages/cooks/pybuggy/<stem>.md``; ``conventions`` →
            ``.goga/usages/conventions.md``).

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
    "api": ("Use `pybuggy-api` for executing HTTP requests from test fixtures and checking responses."),
    "asserts": ("Use `pybuggy-asserts` for response-level and field-level assertions on HTTP responses."),
}

# Annotation line for the ``conventions`` usage key — the test-convention slot occupied by
# ``write_test_convention``. Like ``PYBUGGY_ANNOTATIONS`` above, it is the sole source of the
# line registered under ``codemanifest.annotations`` (init step 8).
_CONVENTION_LINE = "Use `conventions` for test code: pytest configuration, logging, and Allure reporting."


def _annotation_for(stem: str) -> str:
    """Return the annotation line for a discovered pybuggy usage ``stem``.

    Known stems resolve to a hand-authored description; unknown stems fall back to a bare backtick
    reference (`` `pybuggy-<stem>` ``) so every connected usage is still bound to the contract.
    """
    return PYBUGGY_ANNOTATIONS.get(stem, f"`pybuggy-{stem}`")


def register_annotations(config_path: Path, annotation_lines: dict[str, str]) -> list[str]:
    """Round-trip edit ``codemanifest.annotations`` by backtick reference.

    Each entry maps a usage key to one annotation line. For every key the first existing line
    carrying its backtick reference (`` `key` ``) is located: an identical line is a no-op, a
    differing one is replaced in place (migrating legacy text instead of duplicating it), and a
    missing reference is appended. Lines without a registered reference are preserved verbatim.
    Round-trips the file with ``ruamel.yaml`` so comments, key order, quotes, and block-scalars are
    preserved, and writes the value back as a literal block scalar (``|``) — created when absent.

    Args:
        config_path: Path to the consumer ``.goga/config.yml``.
        annotation_lines: Mapping of usage key to the annotation line to register.

    Returns:
        The keys whose annotation line was appended or replaced; identical lines are excluded.

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

    lines = text.split("\n")
    changed_keys: list[str] = []
    for key, line in annotation_lines.items():
        needle = f"`{key}`"
        idx = next((i for i, existing in enumerate(lines) if needle in existing), None)

        if idx is None:
            if lines[-1] == "":
                lines.insert(len(lines) - 1, line)  # text with a trailing newline
            else:
                lines.extend([line, ""])  # scalar without one — add the separator
            changed_keys.append(key)
        elif lines[idx] == line:
            continue  # identical line — no-op
        else:
            lines[idx] = line  # replace exactly the first line carrying the reference
            changed_keys.append(key)

        text = "\n".join(lines)  # the trailing "" element keeps the final newline

    if changed_keys:
        codemanifest["annotations"] = LiteralScalarString(text)

    config_path.parent.mkdir(parents=True, exist_ok=True)
    yaml.dump(data, config_path)

    return changed_keys


def ensure_review_executor_skip(config_path: Path) -> bool:
    """Ensure ``build.review_executor.skip: true`` in the consumer ``.goga/config.yml``.

    Round-trip edits the file with ``ruamel.yaml`` so comments, key order, quotes, anchors, and
    block-scalars are preserved. Idempotent: when ``skip`` already holds ``True`` the file is not
    written at all (a repeat run is byte-identical). The nested ``build``/``review_executor``
    mappings are created when missing, so the flag lands even in a config goga emitted without a
    ``build`` block (no build agent configured). Any other ``build`` content (e.g.
    ``task_executor``) is preserved verbatim; a present ``skip: false`` is corrected to ``true``.

    Args:
        config_path: Path to the consumer ``.goga/config.yml``.

    Returns:
        ``True`` when the flag was added or corrected (file written); ``False`` when it already
        held ``True`` (no write).

    Raises:
        ValueError: If ``build`` or ``build.review_executor`` exists but is not a mapping.
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

    build = _ensure_map(data, "build")
    review_executor = _ensure_map(build, "review_executor")

    if review_executor.get("skip") is True:
        return False

    review_executor["skip"] = True

    config_path.parent.mkdir(parents=True, exist_ok=True)
    yaml.dump(data, config_path)
    logger.info("review executor skip enabled", extra={"path": str(config_path)})

    return True


# Commented example blocks for the complex ``headers``/``loader`` plugin members. These members
# cannot be captured as plain scalars by the interactive build, so their shape is emitted as a
# ``# ``-prefixed example (pinned to the next active key via the ruamel ``before`` comment) instead
# of an active key — documenting the full option surface without producing schema keys (``Config``
# ignores extra scalars).
_HEADERS_BLOCK = "headers: example (skipped complex member)\n  X-Example: value\n  default request headers dict"
_LOADER_BLOCK = "loader: example (skipped complex member)\n  packages:\n    - api\n  modules: []"

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


def write_pybuggy_config(path: Path, scalar_values: dict[str, str | None], specs: dict[str, SpecEntry]) -> None:
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
            doc.yaml_set_comment_before_after_key(PluginConfigKeys.BASE_URL.value, before="required, Jinja2 template")
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


# Fixed root conftest.py template of the target project (like _INSTALL_LINE for the Dockerfile
# line): the sole source of the emitted text, hardcoded verbatim — no parameterization, no
# placeholders, no version resolution. load_dotenv() must run before the plugin import/install
# because the plugin options resolve from os.environ, so .env has to be loaded first; the
# argumentless load_dotenv() keeps override=False, letting CI/operator-exported variables win.
_CONFTEST_TEMPLATE = (
    "from dotenv import load_dotenv\n\nload_dotenv()\n\nfrom goga_tool_pybuggy import plugin\n\nplugin.install()\n"
)


def write_pybuggy_conftest(path: Path) -> None:
    """Emit the target project's root ``conftest.py`` from the fixed ``_CONFTEST_TEMPLATE``.

    Pure, TTY-free, deterministic emitter wiring the pybuggy plugin into the consumer's pytest
    run. No existence check and no overwrite confirmation — ``path`` is always (over)written on
    every call; the overwrite gate lives in :func:`run_init`. Nothing is logged (mirrors
    :func:`write_pybuggy_config`).

    Args:
        path: Destination conftest path (``<cwd>/conftest.py``); the parent directory is created
            when missing.

    Raises:
        OSError: Forwarded unchanged to the caller on a write failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(_CONFTEST_TEMPLATE, encoding="utf-8")


def write_test_convention(path: Path) -> None:
    """Occupy the consumer's ``conventions`` slot with the pybuggy test convention.

    Pure writer of the consumer's test convention file — occupies the ``conventions`` slot with
    the pybuggy test convention shipped inside the installed package. No TTY, no existence check,
    no network: always (over)writes ``path`` with the packaged asset text, so a locally modified
    or previously generated slot content is replaced by the package version (package-owned).
    Nothing is logged — the delivery outcome is logged by the orchestrator
    (:func:`run_init`), which owns the delivery gate.

    The asset is read from the installed ``goga_tool_pybuggy`` package (never the cwd checkout,
    never the network) via the same ``importlib.resources`` channel the api-usage discovery uses;
    the source is fixed and never parameterized. The ``/`` traversal (not the multi-arg
    ``joinpath``) keeps the routine compatible with Python 3.10.

    Args:
        path: Destination convention slot path (``<cwd>/.goga/usages/conventions.md``); the
            parent directory tree is created when missing.

    Raises:
        OSError: Forwarded unchanged to the caller on a read/write failure (including
            ``FileNotFoundError`` from a broken installation without the packaged asset).
    """
    asset_text = (importlib.resources.files("goga_tool_pybuggy") / "assets" / "conventions.md").read_text(
        encoding="utf-8"
    )

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(asset_text, encoding="utf-8")


# Human-readable prompt text for each optional scalar plugin key — mirrors the
# ``ApiPlugin`` option docstrings so the user knows what every field is for.
# ``BASE_URL`` is collected separately as a (possibly multi-line) Jinja2 template;
# ``HEADERS``/``LOADER`` are complex members and never surveyed here.
_SCALAR_PROMPTS: dict[PluginConfigKeys, str] = {
    PluginConfigKeys.TIMEOUT: ("timeout — request timeout in seconds for HTTP calls (optional). Enter to skip"),
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
        "assert_timeout — baseline polling timeout in seconds for retrying assertions (optional). Enter to skip"
    ),
    PluginConfigKeys.ASSERT_DELAY: (
        "assert_delay — seconds between assertion polling attempts (optional). Enter to skip"
    ),
    PluginConfigKeys.ASSERT_FIELD_CLASS: (
        'assert_field_class — dotted "module:Class" of a custom AssertField subclass (optional). Enter to skip'
    ),
    PluginConfigKeys.ASSERT_RESPONSE_CLASS: (
        'assert_response_class — dotted "module:Class" of a custom Expected subclass (optional). Enter to skip'
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
        g_ref = (
            click.prompt(
                "git ref — branch or tag to clone (optional, defaults to the remote default branch)",
                default="",
            ).strip()
            or None
        )
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
# the ``goga`` installer (not pip), pinned to the hardcoded ``1.0.x`` version line.
_INSTALL_LINE = "RUN goga install pybuggy -v 1.0.x\n"


def install_pybuggy(dockerfile_path: Path) -> str | None:
    """Append the pybuggy-install ``RUN`` line to the goga-generated Dockerfile.

    goga ``FileGenerator.generate`` writes the Dockerfile as ``FROM {dockerfile_base_image}\\n`` (the
    FROM baseline, distinct from the top-level built ``image`` name); this routine appends
    ``RUN goga install pybuggy -v 1.0.x`` so the consumer's test image installs pybuggy via the goga
    installer, pinned to the hardcoded ``1.0.x`` version line.

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

    The base convention download is NOT part of the flow: ``ask_base_convention`` is never called
    and the codemanifest fields are collected without a prefill, so the ``conventions`` key never
    enters the answers from this flow and goga performs no convention download — initialization is
    fully offline. The consumer's ``conventions`` slot belongs to :func:`write_test_convention`
    (delivered by :func:`run_init`); the residual case of a user manually typing ``conventions``
    into the usages questionnaire is documented in the ``goga`` usage.

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

        # ask_base_convention is NOT called — the `conventions` slot in the consumer belongs to
        # write_test_convention, so the base convention download is not part of this flow and
        # initialization stays offline (the residual manual `conventions` entry is documented in `goga`).
        codemanifest_usages = questionnaire.ask_codemanifest_usages()
        codemanifest_annotations = questionnaire.ask_codemanifest_annotations()
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
    changed_annotation_keys: list[str],
) -> None:
    """Log INFO for newly-registered usages/annotations and WARNING for already-present (skipped) ones.

    Extracted from :func:`run_init` to keep it under the cyclomatic-complexity cap. A usage key counts as added
    when it appears in the ``added_usage_keys`` list returned by :func:`register_usages`; an annotation key counts
    as registered when it appears in the ``changed_annotation_keys`` list returned by
    :func:`register_annotations` (appended or replaced — an identical line is a no-op and logs as skipped).

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


def _write_root_conftest(cwd: Path) -> None:
    """Gate and write the target project's root ``conftest.py`` (init step 10).

    Extracted from :func:`run_init` to keep it under the cyclomatic-complexity cap. When
    ``<cwd>/conftest.py`` does not exist it is written unconditionally; when it exists, the user
    is asked (``click.confirm``, default ``no``) and it is overwritten only on an explicit ``yes``
    — declining logs INFO and leaves the file untouched (the step is skipped, not an error). The
    decision lives here, in the orchestrator's helper: :func:`write_pybuggy_conftest` itself always
    writes without any check.

    Args:
        cwd: The target project root whose ``conftest.py`` is (re)generated.

    Raises:
        click.ClickException: On a conftest write failure, after ERROR-logging it.
    """
    conftest = cwd / "conftest.py"
    try:
        if _should_rebuild(conftest, "conftest.py exists — overwrite it?"):
            write_pybuggy_conftest(conftest)
        else:
            logger.info("conftest overwrite declined, skipped", extra={"path": str(conftest)})
    except OSError as e:
        logger.error("conftest write failed", extra={"path": str(conftest), "error": str(e)})
        raise click.ClickException(str(e)) from e


def run_init() -> int:
    """Initialize the goga-project, occupy the conventions slot, bootstrap the api usages, build the tool
    config, enforce the review-executor skip flag, generate the conftest.

    Algorithm (12 steps):

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
    6. Occupy the ``conventions`` slot: always (over)write ``<cwd>/.goga/usages/conventions.md``
       with the packaged test-convention asset via :func:`write_test_convention` — no existence
       check, no confirmation, so a project with any prior slot content migrates automatically.
    7. Ensure ``build.review_executor.skip: true`` in ``<cwd>/.goga/config.yml`` via
       :func:`ensure_review_executor_skip` — an idempotent round-trip edit creating the nested
       ``build``/``review_executor`` mappings when missing and preserving the rest of ``build``
       (e.g. ``task_executor``) verbatim; a declined goga-config rebuild migrates the flag into
       the existing config all the same.
    8. Register the usage keys in ``<cwd>/.goga/config.yml`` under ``codemanifest.usages`` via
       :func:`register_usages`: the discovered ``pybuggy-<stem>`` keys AND the key ``conventions``
       → ``.goga/usages/conventions.md`` (idempotent, skip-existing).
    9. Register the annotation lines under ``codemanifest.annotations`` via
       :func:`register_annotations`: the ``pybuggy-<stem>`` lines AND the ``conventions`` line
       (``_CONVENTION_LINE``) — idempotent by backtick reference, an existing line carrying the
       reference is replaced.
    10. Log INFO for added/changed keys and WARNING for skipped ones.
    11. Root ``conftest.py``: resolve ``<cwd>/conftest.py``; when absent, write it via
       :func:`write_pybuggy_conftest`; when it exists, ask (``click.confirm``, default ``no``) —
       ``yes`` overwrites it, ``no`` logs INFO (step skipped, file untouched) and continues. The
       decision lives here, in the orchestrator (:func:`_write_root_conftest`); the routine itself
       always writes without any check.
    12. Return 0.

    Each config is created when absent and only recreated on explicit confirmation when present, so a
    plain repeat run (all confirms declined) still re-copies the usages, re-delivers the conventions
    slot (unconditionally), re-checks the review-executor skip flag (a byte-identical no-op when
    already true), and skips already-registered keys/annotation lines — idempotent. Steps 2
    and 3 are called outside this routine's own try/except — they rely on
    :func:`run_goga_init`/:func:`build_pybuggy_config` never raising (they return a code on
    cancellation/failure); a non-zero code from either returns before the bootstrap block, so no
    usages, slot, or annotations are registered and no conftest is written.

    Returns:
        0 on success; a non-zero exit code when goga init or the config build fails or is cancelled.

    Raises:
        click.ClickException: On a file-write, YAML, navigation, bootstrap (including the slot
            delivery), or conftest-write failure.
    """
    cwd = Path.cwd()
    goga_config = cwd / ".goga" / "config.yml"
    pybuggy_config = cwd / ".goga" / "tools" / "pybuggy" / "config.yml"

    # Goga-project config: create when absent; recreate only on explicit confirmation (overwriting it
    # can discard user-customized codemanifest entries beyond pybuggy's own).
    if _should_rebuild(goga_config, ".goga/config.yml exists — re-run goga init and overwrite it?"):
        rc = run_goga_init()
        if rc != 0:
            return rc

    # Pybuggy tool config: build when absent; rebuild only on explicit confirmation.
    if _should_rebuild(pybuggy_config, ".goga/tools/pybuggy/config.yml exists — rebuild it from the survey?"):
        rc = build_pybuggy_config()
        if rc != 0:
            return rc

    try:
        discovered = _discover_usages(importlib.resources.files("goga_tool_pybuggy.api"))

        for stem, text in discovered:
            dest = cwd / ".goga" / "usages" / "cooks" / "pybuggy" / f"{stem}.md"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(text, encoding="utf-8")

        # The conventions slot is package-owned and delivered unconditionally on every successful
        # pass — a project with any prior (legacy or locally modified) slot content migrates here.
        write_test_convention(cwd / ".goga" / "usages" / "conventions.md")

        # The review-executor flag is enforced unconditionally on every successful pass — the
        # block is created in a fresh config and migrated into an existing one alike.
        ensure_review_executor_skip(cwd / ".goga" / "config.yml")

        usage_keys = {f"pybuggy-{stem}": f".goga/usages/cooks/pybuggy/{stem}.md" for stem, _ in discovered}
        usage_keys["conventions"] = ".goga/usages/conventions.md"
        added_usage_keys = register_usages(cwd / ".goga" / "config.yml", usage_keys)

        annotation_lines = {f"pybuggy-{stem}": _annotation_for(stem) for stem, _ in discovered}
        annotation_lines["conventions"] = _CONVENTION_LINE
        changed_annotation_keys = register_annotations(cwd / ".goga" / "config.yml", annotation_lines)
    except (OSError, YAMLError, ValueError) as e:
        raise click.ClickException(str(e)) from e

    _log_registration(usage_keys, added_usage_keys, annotation_lines, changed_annotation_keys)

    # Root conftest.py: create when absent; overwrite only on explicit confirmation (merging into an
    # existing one is never attempted — either a confirmed overwrite or a skip).
    _write_root_conftest(cwd)

    return 0


@click.command("init")
@click.pass_context
def init_cmd(ctx: click.Context) -> None:
    """Initialize the goga-project, occupy the conventions slot, bootstrap usages, generate the conftest."""
    ctx.exit(run_init())
