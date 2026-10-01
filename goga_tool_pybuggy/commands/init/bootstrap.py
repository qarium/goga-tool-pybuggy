"""Post-session bootstrap writers — the files the onboarding session does not carry.

Six pure writers with round-trip guarantees: the test-convention slot
(``write_test_convention``), the ``build.review.skip`` enforcement
(``ensure_review_skip``), the version-derived Dockerfile install line
(``install_pybuggy``), the codemanifest registrations (``register_usages`` /
``register_annotations``), and the root ``conftest.py``
(``write_pybuggy_conftest``). They are orchestrated by
:func:`goga_tool_pybuggy.commands.init.run_bootstrap`.
"""

import importlib.metadata
import importlib.resources
import logging
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import LiteralScalarString

logger = logging.getLogger(__name__)


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


# Fixed root conftest.py template of the target project: the sole source of the emitted
# text, hardcoded verbatim — no parameterization, no placeholders, no version resolution.
# load_dotenv() must run before the plugin import/install because the plugin options
# resolve from os.environ, so .env has to be loaded first; the argumentless load_dotenv()
# keeps override=False, letting CI/operator-exported variables win.
_CONFTEST_TEMPLATE = (
    "from dotenv import load_dotenv\n\nload_dotenv()\n\nfrom goga_tool_pybuggy import plugin\n\nplugin.install()\n"
)


def write_test_convention(path: Path) -> None:
    """Occupy the consumer's ``conventions`` slot with the packaged pybuggy test convention.

    Pure writer: reads the packaged asset
    ``importlib.resources.files("goga_tool_pybuggy") / "assets" / "conventions.md"``
    (never the cwd checkout, never the network — the ``/`` traversal keeps Python 3.10
    compatibility), creates the parent directory tree, and always overwrites ``path``.
    No TTY, no existence check, no logging — the delivery decision and its logging live
    in the bootstrap orchestrator.

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


def ensure_review_skip(config_path: Path) -> bool:
    """Ensure ``build.review.skip: true`` in the consumer ``.goga/config.yml``.

    Round-trip edits the file with ``ruamel.yaml`` (``preserve_quotes=True``) so comments,
    key order, quotes, anchors, and block-scalars are preserved. The nested ``build``/
    ``review`` mappings are created when missing (each level via ``_ensure_map``; a
    present non-mapping level raises ``ValueError`` — user data is never overwritten).
    Idempotent: when ``skip`` already holds ``True`` the file is not written at all. Any
    other ``build`` content (e.g. ``task_executor``) is preserved verbatim; a present
    ``skip: false`` is corrected to ``true``.

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
    """Append the pybuggy-install ``RUN`` line, derived from the installed package version.

    The line is derived dynamically — ``version =
    importlib.metadata.version("goga-tool-pybuggy")`` → ``minor =
    ".".join(version.split(".")[:2])`` → ``RUN goga install pybuggy -v {minor}.x`` (the
    minor x-range is a valid ``goga install`` version form, ``N.M.x`` → ``~=N.M.0``; a
    dev/pre tail like ``1.1.1.dev4+gabc`` still yields ``1.1.x``). A no-op when
    ``dockerfile_path`` does not exist (the file is never created here) or the line is
    already present; otherwise a trailing newline is ensured, the line appended, and the
    file written — only the install line is ever appended.

    Args:
        dockerfile_path: Path to the project Dockerfile (resolved from the consumer
            config ``dockerfile`` field by the bootstrap).

    Returns:
        The appended ``RUN`` line text, or ``None`` when nothing was appended (file
        absent or line already present).
    """
    if not dockerfile_path.exists():
        return None

    version = importlib.metadata.version("goga-tool-pybuggy")
    minor = ".".join(version.split(".")[:2])
    line = f"RUN goga install pybuggy -v {minor}.x"

    content = dockerfile_path.read_text(encoding="utf-8")
    if line in content:
        return None

    if content and not content.endswith("\n"):
        content += "\n"

    dockerfile_path.write_text(content + line + "\n", encoding="utf-8")
    logger.info("pybuggy install line added to Dockerfile", extra={"line": line, "path": str(dockerfile_path)})

    return line


def register_usages(config_path: Path, usage_keys: dict[str, str]) -> list[str]:
    """Register ``usage_keys`` in the consumer ``.goga/config.yml`` under ``codemanifest.usages``.

    Round-trip edits the file with ``ruamel.yaml`` so comments, key order, quotes, and
    block-scalars are preserved. Existing keys (including user-defined ones outside this
    tool) are never overwritten, which makes the run idempotent. A minimal file carrying
    the ``codemanifest.usages`` block is created when no file exists; the ruamel
    ``load → None`` gotcha (empty file) is handled by starting from an empty
    ``CommentedMap``.

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

    Each entry maps a usage key to one annotation line. For every key the first existing
    line carrying its backtick reference (`` `key` ``) is located: an identical line is a
    no-op, a differing one is replaced in place (migrating legacy text instead of
    duplicating it), and a missing reference is appended. Lines without a registered
    reference are preserved verbatim. The value is written back as a
    ``LiteralScalarString`` (literal block scalar ``|``), created when absent.

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

    Pure, TTY-free, deterministic writer wiring the pybuggy plugin into the consumer's
    pytest run. No existence check and no overwrite confirmation — ``path`` is always
    (over)written on every call; the overwrite gate lives in the bootstrap orchestrator.
    Nothing is logged.

    Args:
        path: Destination conftest path (``<cwd>/conftest.py``); the parent directory is
            created when missing.

    Raises:
        OSError: Forwarded unchanged to the caller on a write failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(_CONFTEST_TEMPLATE, encoding="utf-8")
