"""list command handler - display endpoints from specs."""

import logging
from pathlib import Path
from typing import Optional

import click
from deepdiff import DeepDiff

from ...config import load_config
from ...output import render_list
from ...spec import Endpoint, extract_endpoints, load_spec
from ..diff import artifact_contract, orphan_artifact_dirs, sanitize_id, spec_contract

logger = logging.getLogger(__name__)


def endpoint_statuses(api_spec_dir: Path, endpoints: list[Endpoint]) -> tuple[dict[str, str], list[str]]:
    """Classify one spec's endpoints against its artifact tree into sync statuses.

    Per endpoint (extraction order): derive the artifact directory segment via
    ``sanitize_id``; an absent directory means the endpoint was never generated
    (``ADD``); an existing one is compared — the generated side from
    ``artifact_contract`` first, the spec side from ``spec_contract`` second,
    under one strict ``DeepDiff`` — a non-empty result means drift (``UPD``),
    an empty one means ``OK``. The removed side discovers, over the FULL
    endpoint list, the artifact directories matching no endpoint; each is read
    through ``artifact_contract`` as a validation gate before its segment is
    reported. The function is read-only: nothing is written, created or deleted.

    Args:
        api_spec_dir: The spec's artifact tree directory (``api/<spec>``);
            may be absent — every endpoint then reports ``ADD``.
        endpoints: Every endpoint of the spec (the full list).

    Returns:
        ``(statuses, removed)`` — raw endpoint ids mapped to ``ADD``/``UPD``/
        ``OK``, plus the sorted orphan segments (the ``REMOVED`` side).

    Raises:
        click.ClickException: If an artifact ``meta.json`` or schema file of an
            existing directory is missing, unreadable or corrupt.
    """
    statuses: dict[str, str] = {}
    for endpoint in endpoints:
        endpoint_dir = api_spec_dir / sanitize_id(endpoint.id)
        if not endpoint_dir.is_dir():
            statuses[endpoint.id] = "ADD"
            continue
        # The comparison direction is fixed — generated side first, spec side
        # second (the spec is the current truth) — and strict, so the statuses
        # agree with the endpoint diff verdicts by construction.
        generated_side = artifact_contract(endpoint_dir)
        spec_side = spec_contract(endpoint)
        statuses[endpoint.id] = "UPD" if DeepDiff(generated_side, spec_side) else "OK"

    removed: list[str] = []
    for orphan in orphan_artifact_dirs(api_spec_dir, endpoints):
        # Validation gate: reading is required by contract even though only the
        # segment name is reported — a corrupt orphan fails the run.
        artifact_contract(orphan)
        removed.append(orphan.name)

    return statuses, removed


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
        # Validate spec has the required structure — the key alone is not
        # enough: `paths:` with no value parses to None, and an empty or
        # list/str document is equally not a spec mapping; all three would
        # crash extract_endpoints.
        if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict):
            raise click.ClickException(f"invalid spec file (missing 'paths'): {entry.location}")
        try:
            endpoints = extract_endpoints(spec)
        except ValueError as error:
            # extract_endpoints raises ValueError on an invalid spec — no
            # openapi/swagger version key, or a response key outside the shapes
            # the specifications allow. An invalid spec is a CLI error, not a
            # traceback (mirrors generate/diff).
            raise click.ClickException(f"invalid spec file ({error}): {entry.location}") from error
        if not endpoints:
            logger.warning(f"no endpoints found in spec: {name}")

        print(render_list(name, entry.location, endpoints))


@click.command("list")
@click.option("--spec", "spec_name", default=None, help="Spec name to list")
def list_cmd(spec_name: Optional[str]) -> None:
    """List endpoints from specs."""
    run_list(spec_name)
