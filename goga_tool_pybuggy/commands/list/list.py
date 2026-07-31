"""list command handler - display endpoints from specs."""

import logging
from pathlib import Path
from typing import Optional

import click

from ...config import load_config
from ...output import render_list
from ...spec import extract_endpoints, load_spec

logger = logging.getLogger(__name__)


def run_list(spec_name: Optional[str]) -> None:
    """List endpoints from OpenAPI specs.

    Loads config from the fixed config path and for each spec: parses, extracts
    endpoints, renders formatted output, and prints it.

    Args:
        spec_name: Optional spec name to list; if None, lists all specs

    Raises:
        click.ClickException: If spec_name not found or spec parse fails
    """
    # Load config from the fixed path
    config = load_config()

    # Select specs
    if spec_name is not None:
        if spec_name not in config.specs:
            raise click.ClickException(f"spec not found: {spec_name}")
        specs = {spec_name: config.specs[spec_name]}
    else:
        specs = config.specs

    # Process each spec
    for name, entry in specs.items():
        spec_path = Path.cwd() / entry.location
        spec = load_spec(spec_path)
        # Validate spec has required structure
        if not spec or "paths" not in spec:
            raise click.ClickException(f"invalid spec file (missing 'paths'): {entry.location}")
        endpoints = extract_endpoints(spec)
        if not endpoints:
            logger.warning(f"no endpoints found in spec: {name}")

        print(render_list(name, entry.location, endpoints))


@click.command("list")
@click.option("--spec", "spec_name", default=None, help="Spec name to list")
def list_cmd(spec_name: Optional[str]) -> None:
    """List endpoints from specs."""
    run_list(spec_name)
