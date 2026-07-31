"""info command handler - display endpoint details in JSON format."""

from pathlib import Path
from typing import Optional

import click

from ...config import load_config
from ...output import render_info
from ...spec import extract_endpoints, load_spec


def run_info(endpoint_ids: Optional[list[str]] = None, spec_name: Optional[str] = None) -> None:
    """Display endpoint information in JSON format.

    Loads config from the fixed config path and searches across specs for endpoints
    matching the given endpoint ids (or every endpoint when no filter is given). Prints
    a JSON object (single match) or array (multiple matches). Raises ClickException when
    a requested id is not found in any selected spec.

    Args:
        endpoint_ids: Optional endpoint-id filter (as produced by ``build_endpoint_id``);
            when set, only endpoints whose id is in the list are shown. ``None`` or empty
            shows every endpoint of the selected specs. Every requested id must match at
            least one selected spec, otherwise nothing is printed.
        spec_name: Optional spec name to search; if None, searches all specs

    Raises:
        click.ClickException: If spec_name not found, spec parse fails, or endpoint_ids
            contains an id not found in any selected spec
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

    # Normalize the endpoint-id filter: an empty filter means "no filter" (all endpoints), so a
    # variadic CLI argument passed with no values behaves identically to the unfiltered command.
    endpoint_filter: set[str] | None = set(endpoint_ids) if endpoint_ids else None

    # Collect matches across specs
    matches = []
    for _name, entry in specs.items():
        spec_path = Path.cwd() / entry.location
        spec = load_spec(spec_path)
        # Validate spec has required structure
        if not spec or "paths" not in spec:
            raise click.ClickException(f"invalid spec file (missing 'paths'): {entry.location}")
        endpoints = extract_endpoints(spec)
        if endpoint_filter is not None:
            matches.extend(e for e in endpoints if e.id in endpoint_filter)
        else:
            matches.extend(endpoints)

    # When a filter is set, every requested id must match at least one selected spec
    if endpoint_filter is not None:
        missing = sorted(endpoint_filter - {e.id for e in matches})
        if missing:
            raise click.ClickException(f"endpoint not found: {', '.join(missing)}")

    # Render and print
    print(render_info(matches))


@click.command("info")
@click.option("--spec", "spec_name", default=None, help="Spec name to search")
@click.argument("endpoint-ids", nargs=-1, default=None)
def info_cmd(spec_name: Optional[str], endpoint_ids: tuple[str, ...]) -> None:
    """Display endpoint information in JSON format."""
    run_info(list(endpoint_ids) if endpoint_ids else None, spec_name)
