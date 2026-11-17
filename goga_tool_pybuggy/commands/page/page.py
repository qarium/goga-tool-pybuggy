"""page generate command handler - scaffold pages/ page-object modules (a BasePage subclass and its fixture)."""

import re
from pathlib import Path
from typing import Optional

import click

# Help text of -f/--force — names the artifact the flag regenerates; the package markers are
# deliberately outside its scope (they are created only when missing, never overwritten).
_FORCE_HELP = "Overwrite an existing page-object module; __init__.py markers are created only when missing"

# The page generate sibling of the api-side rule: leftover non-word characters become "_" so
# every directory of the pages/ tree and every generated name stays a valid identifier.
_NON_IDENT_RE = re.compile(r"\W")


def _safe_identifier(text: str) -> str:
    """Make ``text`` usable as a Python identifier segment (package dir, def name or class stem).

    Applied identically to the path directories, the module file name, the fixture name and the
    class stem, so every part of the artifact path is importable and the names never disagree.

    Args:
        text: Identifier candidate (a path segment or the given name).

    Returns:
        Text safe for use as a package directory name, a ``def`` name and a class stem.
    """
    ident = _NON_IDENT_RE.sub("_", text)
    return f"_{ident}" if ident[:1].isdigit() else ident


def _string_literal(text: str) -> str:
    """Render ``text`` as a double-quoted Python string literal.

    Args:
        text: The string to render (the tested-site path).

    Returns:
        The literal text — double-quoted when the value carries no double quote; the
        single-quoted ``repr`` form otherwise, so a value with any quote combination stays
        a valid literal (the path attribute keeps the path verbatim either way).
    """
    if '"' not in text:
        return f'"{text}"'

    return repr(text)


def _class_name(base: str) -> str:
    """Build the page class name — the ``base`` stem in CamelCase plus the ``Page`` suffix.

    Args:
        base: The sanitized stem (the given name or the last path segment).

    Returns:
        The CamelCase class name; an empty split part keeps a single underscore, so a
        leading-digit sanitization prefix survives (``_2fa`` -> ``_2faPage``).
    """
    camel = "".join((part[:1].upper() + part[1:]) if part else "_" for part in base.split("_"))

    return f"{camel}Page"


def _write_package_markers(bottom: Path, top: Path) -> None:
    """Write an empty ``__init__.py`` in every directory from ``bottom`` up to (including) ``top``.

    Unlike the api-side generate, a marker is created only when missing and is never overwritten —
    even with --force: a consumer project may keep real re-exports in its ``pages/__init__.py``.

    Args:
        bottom: deepest directory on the package path (the page module directory).
        top: top-most directory on the package path (the ``pages`` root); must be an ancestor of ``bottom``.

    Raises:
        none.
    """
    current = bottom
    while True:
        init_file = current / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8")
        if current == top:
            break
        current = current.parent


def render_page_module(path: str, class_name: str, fixture_name: str) -> str:
    """Render the full source text of a page-object module for one tested-site path.

    The text is a fixed-shape literal and deterministic: identical input yields identical output —
    no formatter runs over it (the shape never varies, unlike the api-side modules with generated
    request models).

    Args:
        path: The tested-site path carried by the class ``path`` attribute, verbatim.
        class_name: The page class name (CamelCase stem plus ``Page``).
        fixture_name: The pytest fixture name (``page_`` prefix plus the stem).

    Returns:
        Full source text of the page-object module (trailing newline included).
    """
    # The double-quoted literal keeps the module aligned with the repo convention; a path
    # carrying a double quote falls back to the escaped repr form (see _string_literal).
    return (
        "import pytest\n"
        "\n"
        "from goga_tool_pybuggy.web import BasePage\n"
        "from prettyplay import PrettyPlay\n"
        "\n"
        "\n"
        f"class {class_name}(BasePage):\n"
        "    pass\n"
        "\n"
        "\n"
        '@pytest.fixture(scope="function")\n'
        f"def {fixture_name}(web: PrettyPlay) -> {class_name}:\n"
        f"    return {class_name}(web, {_string_literal(path)})\n"
    )


def run_page_generate(path: Optional[str], name: Optional[str] = None, force: bool = False) -> None:
    """Scaffold one page-object module under ``pages/`` of the current working directory.

    Args:
        path: The tested-site page path; must start with "/" and carry at least one non-empty
            segment.
        name: The optional page name driving the fixture and class names; ``None`` derives them
            from the path segments.
        force: When true, overwrite an existing page-object module; when false, skip it silently.

    Raises:
        click.ClickException: If ``path`` carries no leading slash or no non-empty segment, or
            ``name`` is given but blank — always before any write, so a rejected input leaves no
            ``pages/`` tree behind.
    """
    if not path or not path.startswith("/"):
        raise click.ClickException(f"path must start with '/': {path!r}")

    segments = [segment for segment in path.split("/") if segment]

    if not segments:
        raise click.ClickException(f"path carries no non-empty segment: {path!r}")

    if name is not None and not name.strip():
        raise click.ClickException("name must not be blank")

    # The naming derivation: directories from the path segments minus the last one; the file and
    # the names from the given name (whole) or the last path segment.
    safe_segments = [_safe_identifier(segment) for segment in segments]
    safe_name = _safe_identifier(name.strip()) if name is not None else None
    short = safe_name if safe_name is not None else safe_segments[-1]
    fixture_name = "page_" + (safe_name if safe_name is not None else "_".join(safe_segments))
    class_name = _class_name(short)
    module = render_page_module(path, class_name, fixture_name)

    target_dir = Path.cwd() / "pages" / Path(*safe_segments[:-1])
    target_dir.mkdir(parents=True, exist_ok=True)
    _write_package_markers(target_dir, Path.cwd() / "pages")

    target_file = target_dir / f"{short}_page.py"
    if force or not target_file.exists():
        target_file.write_text(module, encoding="utf-8")


@click.command("generate")
@click.option("-f", "--force", is_flag=True, default=False, help=_FORCE_HELP)
@click.argument("path")
@click.argument("name", required=False, default=None)
def page_generate_cmd(path: str, name: Optional[str], force: bool) -> None:
    """Click wrapper for the page generate subcommand; delegates to run_page_generate."""
    run_page_generate(path, name, force)
