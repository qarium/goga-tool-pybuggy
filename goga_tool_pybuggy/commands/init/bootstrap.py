"""Post-session bootstrap writers — the files the onboarding session does not carry.

Six pure writers orchestrated by :func:`goga_tool_pybuggy.commands.init.run_bootstrap`.
"""

import importlib.resources
import logging
import re
from io import StringIO
from pathlib import Path

from prettyplay import PrettyConfig
from ruamel.yaml import YAML, YAMLError
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import LiteralScalarString

from ...plugins import PluginConfigKeys, WebConfigKeys

logger = logging.getLogger(__name__)

# The root-user install block written into the consumer Dockerfile. The bulk ``goga install`` reads the
# ``tools:`` record of the copied project's .goga/config.yml (the session's amendment pins pybuggy there),
# so no version lives in the block — the project config is the single version source.
_INSTALL_RUN_LINE = "RUN cd /tmp/project && goga install && rm -rf /tmp/project"
_INSTALL_BLOCK = f"USER root\nCOPY . /tmp/project\n{_INSTALL_RUN_LINE}\nUSER goga"

# Any single-line pybuggy install step a previous release of this writer may have pinned (the spec
# shape changed with the x-range pin — e.g. the concrete ``-v 2.0`` before it). Matching the
# command prefix, not the exact current line text, keeps re-running the bootstrap
# idempotent across releases: the found line is replaced by the install block, never joined by a
# second install step.
_INSTALL_LINE = re.compile(r"^[ \t]*RUN goga install pybuggy\b[^\n]*$", re.MULTILINE)

# Any playwright install line a previous run may have pinned to a different browser. Matching the
# command prefix, not the exact line text, keeps the writer idempotent across browser changes: the
# found line is repinned, never joined by a second one.
_PLAYWRIGHT_LINE = re.compile(r"^[ \t]*RUN playwright install\b[^\n]*$", re.MULTILINE)


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


# Fixed root conftest.py template — hardcoded verbatim, no parameterization.
# load_dotenv() precedes plugins.install() and keeps override=False (exported variables win).
_CONFTEST_TEMPLATE = (
    "from dotenv import load_dotenv\n\nload_dotenv()\n\nfrom goga_tool_pybuggy import plugins\n\nplugins.install()\n"
)

# Commented example records for plugin members the session never captures (1.x texts).
# Ruamel writes each before-comment line with the ``# `` prefix, matching the 1.x layout.
_HEADERS_BLOCK = "headers: example (skipped complex member)\n  X-Example: value\n  default request headers dict"
_LOADER_BLOCK = "loader: example (skipped complex member)\n  packages:\n    - api\n  modules: []"

# The web defaults the example records carry — computed from the library model, the single default
# source (the same resolution the plugin's own ``_default_*`` constants perform); a library default
# change re-renders every record without touching this cell. The browser entry is the nested
# BrowserConfig default in field order.
_WEB_DEFAULTS = PrettyConfig().model_dump()

# The scalar shapes that render bare — identifier-like strings (chromium, openai); every other
# string (the empty defaults included) renders as a quoted '' scalar.
_BARE_TEXT = re.compile(r"[A-Za-z_][A-Za-z0-9_./-]*")


def _scalar_text(value: object) -> str:
    """Return the YAML scalar text of one default ``value`` — type-faithful and uncommentable.

    ``None`` renders as ``null``, booleans and numbers verbatim, identifier-like strings bare,
    every other string (the empty defaults included) as a quoted ``''`` scalar — so an uncommented
    record parses back to exactly the library default of its key.

    Args:
        value: The default value of one config key (or nested browser key).

    Returns:
        The YAML scalar text of the value.
    """
    if value is None:
        return "null"

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (int, float)):
        return str(value)

    text = str(value)

    return text if _BARE_TEXT.fullmatch(text) else "''"


# The commented browser record of a fully absent browser group — the group with every nested key
# at its library default.
_BROWSER_BLOCK = "\n".join(
    [
        f"{WebConfigKeys.BROWSER.value}:",
        *(f"  {key}: {_scalar_text(value)}" for key, value in _WEB_DEFAULTS[WebConfigKeys.BROWSER.value].items()),
    ]
)


def write_test_convention(path: Path) -> None:
    """Occupy the consumer's ``conventions`` slot with the packaged pybuggy test convention.

    Pure writer — reads the packaged asset (never the cwd checkout or the network) and always overwrites ``path``.

    Args:
        path: Destination convention slot path (``<cwd>/.goga/usages/conventions.md``).

    Raises:
        OSError: Forwarded unchanged on a read/write failure (including
            ``FileNotFoundError`` from a broken installation without the packaged asset).
    """
    asset_text = (importlib.resources.files("goga_tool_pybuggy") / "assets" / "conventions.md").read_text(
        encoding="utf-8"
    )

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(asset_text, encoding="utf-8")


def _example_record(member: PluginConfigKeys) -> str:
    """Return the commented example record text of one plugin member.

    Complex members resolve to their example blocks; scalars to the ``(skipped optional scalar)`` record.

    Args:
        member: The plugin config key to document.

    Returns:
        The record text emitted as ``# ``-prefixed comment lines.
    """
    if member is PluginConfigKeys.HEADERS:
        return _HEADERS_BLOCK

    if member is PluginConfigKeys.LOADER:
        return _LOADER_BLOCK

    return f"{member.value}: (skipped optional scalar)"


def _web_example_record(member: WebConfigKeys) -> str:
    """Return the commented example record text of one web config key — the key with its default.

    The browser group resolves to its full nested block; every other key to the one-line
    ``key: default`` record the user uncomments to activate the default.

    Args:
        member: The web config key to document.

    Returns:
        The record text emitted as ``# ``-prefixed comment lines.
    """
    if member is WebConfigKeys.BROWSER:
        return _BROWSER_BLOCK

    return f"{member.value}: {_scalar_text(_WEB_DEFAULTS[member.value])}"


def document_config_examples(config_path: Path) -> list[str]:
    """Document the absent plugin members of the tool config as commented example records.

    Idempotent comment-only edit: records are pinned in plugin key order, and active keys are never modified.

    Args:
        config_path: Path to the tool config file (``<cwd>/.goga/tools/pybuggy/api.yml``).

    Returns:
        The record texts added; empty when the file is absent, holds no mapping, or every
        absent member is already documented.

    Raises:
        YAMLError: If the existing file contains invalid YAML.
    """
    if not config_path.exists():
        return []

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096

    data = yaml.load(config_path)

    if not isinstance(data, CommentedMap):
        return []

    text = config_path.read_text(encoding="utf-8")
    pending: list[str] = []
    documented: list[str] = []

    for member in PluginConfigKeys:
        record = _example_record(member)
        # The marker is the emitted comment line — carrying the ``# `` prefix keeps a sibling's
        # record line (``timeout`` inside ``assert_timeout``'s) from matching.
        marker = f"# {record.splitlines()[0]}"

        if member.value in data:
            if pending:
                data.yaml_set_comment_before_after_key(member.value, before="\n".join(pending))
                documented.extend(pending)
                pending = []
        elif marker not in text:
            pending.append(record)

    if pending and "specs" in data:
        data.yaml_set_comment_before_after_key("specs", before="\n".join(pending))
        documented.extend(pending)

    if documented:
        yaml.dump(data, config_path)

    return documented


def _document_browser_defaults(yaml: YAML, data: CommentedMap, text: str) -> list[str]:
    """Document the absent nested keys of the browser group as commented default records.

    The records pin above the group's last active nested key — before-comments of a nested map
    emit above the key line — at the group's own emitted indentation (the probe-measured token
    column), so an uncommented nested line lands inside the browser mapping as a valid active key.

    Args:
        yaml: The round-trip YAML instance the caller dumps with.
        data: The round-trip web config document.
        text: The current file text — the marker detection source.

    Returns:
        The record texts added; empty when the group is absent, empty, flow-style, or fully active.
    """
    browser = data.get(WebConfigKeys.BROWSER.value)

    if not isinstance(browser, CommentedMap) or not browser:
        return []

    defaults = _WEB_DEFAULTS[WebConfigKeys.BROWSER.value]
    records = [
        f"{key}: {_scalar_text(value)}"
        for key, value in defaults.items()
        if key not in browser and f"# {key}: {_scalar_text(value)}" not in text
    ]

    if not records:
        return []

    # Probe-dump to measure the group's emitted indentation — the token column the new lines must
    # carry to sit inside the block (the default column 0 would land them at the top level).
    probe = StringIO()
    yaml.dump(data, probe)
    block = re.search(rf"(?m)^{WebConfigKeys.BROWSER.value}:\n([ \t]+)\S", probe.getvalue())

    if block is None:  # a flow-style or single-line group — nothing to pin into
        return []

    anchor = list(browser)[-1]
    known = len((browser.ca.items.get(anchor) or [None, []])[1] or [])
    browser.yaml_set_comment_before_after_key(anchor, before="\n".join(records))

    for token in browser.ca.items[anchor][1][known:]:
        token.start_mark.column = len(block.group(1))

    return records


def document_web_config_examples(config_path: Path) -> list[str]:
    """Document the absent web config keys of ``web.yml`` as commented default records.

    Idempotent comment-only edit: top-level records are pinned in ``WebConfigKeys`` walk order
    before the next active key (``browser`` is the terminal anchor), the absent nested keys of the
    browser group above its last active nested key; every record carries its library default, and
    active keys are never modified.

    Args:
        config_path: Path to the web config file (``<cwd>/.goga/tools/pybuggy/web.yml``).

    Returns:
        The record texts added; empty when the file is absent, holds no mapping, or every
        absent key is already documented.

    Raises:
        YAMLError: If the existing file contains invalid YAML.
    """
    if not config_path.exists():
        return []

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096

    data = yaml.load(config_path)

    if not isinstance(data, CommentedMap):
        return []

    text = config_path.read_text(encoding="utf-8")
    pending: list[str] = []
    documented: list[str] = []

    for member in WebConfigKeys:
        if member is WebConfigKeys.FILENAME:
            continue

        record = _web_example_record(member)
        # The marker is the emitted comment line — carrying the ``# `` prefix keeps a sibling's
        # record line (``model`` inside ``generation_model``'s) from matching.
        marker = f"# {record.splitlines()[0]}"

        if member.value in data:
            if pending:
                data.yaml_set_comment_before_after_key(member.value, before="\n".join(pending))
                documented.extend(pending)
                pending = []
        elif marker not in text:
            pending.append(record)

    documented.extend(_document_browser_defaults(yaml, data, text))

    if documented:
        yaml.dump(data, config_path)

    return documented


def ensure_review_skip(config_path: Path) -> bool:
    """Ensure ``build.review.skip: true`` in the consumer ``.goga/config.yml``.

    Idempotent round-trip edit — comments, key order, and unrelated ``build`` content are preserved.

    Args:
        config_path: Path to the consumer ``.goga/config.yml``.

    Returns:
        ``True`` when the flag was added or corrected (file written); ``False`` when it
        already held ``True`` (no write).

    Raises:
        ValueError: If ``build`` or ``build.review`` exists but is not a mapping.
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
    review = _ensure_map(build, "review")

    if review.get("skip") is True:
        return False

    review["skip"] = True

    config_path.parent.mkdir(parents=True, exist_ok=True)
    yaml.dump(data, config_path)
    logger.info("review executor skip enabled", extra={"path": str(config_path)})

    return True


def install_pybuggy(dockerfile_path: Path) -> str | None:
    """Write the pybuggy-install block — the root-user project-copy install step of the Dockerfile.

    The block copies the project into the image and runs the bulk ``goga install`` from it, which
    reads the ``tools:`` record of the copied ``.goga/config.yml`` (the session's amendment pins
    pybuggy there) — the block carries no version, the project config is the single version source.
    An install line written by an older release of this writer (the single ``RUN goga install
    pybuggy -v …`` shape) is replaced in place by the block — never joined by a second install
    step — so re-running the bootstrap stays idempotent across releases.

    Args:
        dockerfile_path: Path to the project Dockerfile (resolved from the consumer
            config ``dockerfile`` field by the bootstrap).

    Returns:
        The written install block text, or ``None`` when nothing was written (file absent or
        block already present).

    Raises:
        OSError: Forwarded unchanged on a Dockerfile read/write failure.
    """
    if not dockerfile_path.exists():
        return None

    content = dockerfile_path.read_text(encoding="utf-8")

    if _INSTALL_RUN_LINE in content:
        return None

    existing = _INSTALL_LINE.search(content)

    if existing is not None:
        dockerfile_path.write_text(
            content[: existing.start()] + _INSTALL_BLOCK + content[existing.end() :], encoding="utf-8"
        )
        logger.info("pybuggy install block replaced in Dockerfile", extra={"path": str(dockerfile_path)})

        return _INSTALL_BLOCK

    if content and not content.endswith("\n"):
        content += "\n"

    dockerfile_path.write_text(content + _INSTALL_BLOCK + "\n", encoding="utf-8")
    logger.info("pybuggy install block added to Dockerfile", extra={"path": str(dockerfile_path)})

    return _INSTALL_BLOCK


def _read_surveyed_browser_name() -> str | None:
    """Read the surveyed browser name leniently from the written ``web.yml`` (cwd-relative).

    Returns:
        The ``browser.name`` string, or ``None`` when the document is absent, unreadable,
        or carries no usable browser name.
    """
    web_config = Path(".goga/tools/pybuggy/web.yml")

    if not web_config.exists():
        return None

    try:
        data = YAML().load(web_config)
    except YAMLError:
        return None

    browser = data.get("browser") if isinstance(data, CommentedMap) else None
    name = browser.get("name") if isinstance(browser, CommentedMap) else None

    if not isinstance(name, str) or not name:
        return None

    return name


def _root_section_anchor(lines: list[str]) -> int | None:
    """Return the index of the install block's closing ``USER goga`` line.

    Args:
        lines: The Dockerfile lines (the ``str.split("\\n")`` view of the file).

    Returns:
        The index of the ``USER goga`` line that follows the install block's ``RUN`` line, or
        ``None`` when the file carries no install block.
    """
    run_idx = next((i for i, text in enumerate(lines) if _INSTALL_RUN_LINE in text), None)

    if run_idx is None:
        return None

    return next((i for i in range(run_idx + 1, len(lines)) if lines[i].strip() == "USER goga"), None)


def install_playwright(dockerfile_path: Path) -> str | None:
    """Write the playwright browser-install ``RUN`` line inside the Dockerfile root section.

    The browser comes from the written ``web.yml`` (the surveyed ``browser.name``); an absent or
    unreadable document is a lenient no-op with a WARNING. The line anchors immediately before the
    install block's closing ``USER goga`` — ``--with-deps`` installs OS packages, so it must run as
    root. A playwright line pinned to a different browser is repinned, and a line left outside the
    root section by a previous layout is relocated there — never joined by a second, conflicting
    line — so re-running the bootstrap stays idempotent across browser changes and repairs the
    pre-fix layout in place. Without an install block (the defensive path) the line appends at the
    end of the file.

    Args:
        dockerfile_path: Path to the project Dockerfile (resolved from the consumer config
            ``dockerfile`` field by the bootstrap).

    Returns:
        The written ``RUN`` line text, or ``None`` when nothing was written (file absent, web
        config unreadable, or line already present at the current browser inside the root section).

    Raises:
        OSError: Forwarded unchanged on a Dockerfile read/write failure.
    """
    if not dockerfile_path.exists():
        return None

    browser = _read_surveyed_browser_name()

    if browser is None:
        logger.warning(
            "web config unreadable — playwright install line skipped", extra={"document": ".goga/tools/pybuggy/web.yml"}
        )

        return None

    line = f"RUN playwright install --with-deps {browser}"

    lines = dockerfile_path.read_text(encoding="utf-8").split("\n")
    existing_idx = next((i for i, text in enumerate(lines) if _PLAYWRIGHT_LINE.match(text)), None)

    if existing_idx is not None:
        anchor = _root_section_anchor(lines)

        if lines[existing_idx].strip() == line and (anchor is None or anchor == existing_idx + 1):
            return None

        del lines[existing_idx]

    anchor = _root_section_anchor(lines)

    if anchor is None:
        # No install block — the defensive path keeps the legacy end-of-file append.
        if lines and lines[-1] == "":
            lines.insert(len(lines) - 1, line)
        else:
            lines.extend((line, ""))
    else:
        lines.insert(anchor, line)

    dockerfile_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("playwright install line added to Dockerfile", extra={"line": line, "path": str(dockerfile_path)})

    return line


def register_usages(config_path: Path, usage_keys: dict[str, str]) -> list[str]:
    """Register ``usage_keys`` in the consumer ``.goga/config.yml`` under ``codemanifest.usages``.

    Idempotent round-trip edit — existing keys (including user-defined ones) are never overwritten.

    Args:
        config_path: Path to the consumer ``.goga/config.yml``.
        usage_keys: Mapping of usage key to the relative path of the usage file to
            register (``pybuggy-<stem>`` → ``.goga/usages/cooks/pybuggy/<stem>.md``;
            ``conventions`` → ``.goga/usages/conventions.md``).

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


def register_annotations(config_path: Path, annotation_lines: dict[str, str]) -> list[str]:
    """Round-trip edit ``codemanifest.annotations`` by backtick reference.

    The first line carrying a key's backtick reference is replaced in place or appended; other lines are preserved.

    Args:
        config_path: Path to the consumer ``.goga/config.yml``.
        annotation_lines: Mapping of usage key to the annotation line to register.

    Returns:
        The keys whose annotation line was appended or replaced; identical lines are excluded.

    Raises:
        ValueError: If ``codemanifest`` is not a mapping, or ``annotations`` exists but is
            not a scalar.
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


def write_pybuggy_conftest(path: Path) -> None:
    """Emit the target project's root ``conftest.py`` from the fixed ``_CONFTEST_TEMPLATE``.

    Always (over)writes ``path`` — the overwrite gate lives in the bootstrap orchestrator.

    Args:
        path: Destination conftest path (``<cwd>/conftest.py``); the parent directory is
            created when missing.

    Raises:
        OSError: Forwarded unchanged to the caller on a write failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(_CONFTEST_TEMPLATE, encoding="utf-8")
