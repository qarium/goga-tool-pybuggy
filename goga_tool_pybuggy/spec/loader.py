"""load_spec routine for parsing OpenAPI/Swagger specifications."""

from pathlib import Path
from typing import Any

import click
from swax.openapi import SpecParseError, parse_spec


def load_spec(spec_path: Path) -> dict[str, Any]:
    """Parse an OpenAPI/Swagger spec file into a resolved dict.

    Uses swax.openapi.parse_spec which resolves all $ref references via Prance.
    Maps SpecParseError to click.ClickException for consistent CLI error handling.

    Args:
        spec_path: Path to the spec file (YAML or JSON).

    Returns:
        A dict representing the parsed spec with all $ref references resolved.

    Raises:
        click.ClickException: If the spec file cannot be parsed.
    """
    try:
        return parse_spec(spec_path)
    except SpecParseError as exc:
        raise click.ClickException(f"failed to parse spec {exc.path}: {exc.reason}") from exc
