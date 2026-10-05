"""list command handler - display endpoints from specs."""

import logging
from pathlib import Path
from typing import Optional

import click
from deepdiff import DeepDiff

from ...config import SpecEntry, load_config
from ...output import render_list, render_status_list
from ...spec import Endpoint, extract_endpoints, load_spec
from ..diff import artifact_contract, orphan_artifact_dirs, sanitize_id, spec_contract

logger = logging.getLogger(__name__)


def endpoint_statuses(api_spec_dir: Path, endpoints: list[Endpoint]) -> tuple[dict[str, str], list[str]]:
    """Classify one spec's endpoints against its artifact tree into sync statuses.

    Read-only: absent artifact dirs report ``ADD``, contract drift ``UPD``, orphans ``REMOVED``.

    Args:
        api_spec_dir: The spec's artifact tree directory (``api/<spec>``); may be absent.
        endpoints: Every endpoint of the spec (the full list).

    Returns:
        ``(statuses, removed)`` — raw endpoint ids mapped to ``ADD``/``UPD``/``OK``, plus the
        sorted orphan segments.

    Raises:
        click.ClickException: If an artifact ``meta.json``/schema file of an existing directory
            is missing, unreadable or corrupt; or two endpoints share a raw id (the id-keyed
            report would silently misreport one of them).
    """
    # build_endpoint_id collapses both "-" and "/", so distinct paths can collide on one id;
    # refuse the spec instead of silently misreporting one of the two lines.
    owners: dict[str, str] = {}
    for endpoint in endpoints:
        if endpoint.id in owners:
            raise click.ClickException(
                f"paths {owners[endpoint.id]!r} and {endpoint.path!r} both map to "
                f"endpoint id {endpoint.id!r}; rename one path"
            )
        owners[endpoint.id] = endpoint.path

    statuses: dict[str, str] = {}
    for endpoint in endpoints:
        endpoint_dir = api_spec_dir / sanitize_id(endpoint.id)
        if not endpoint_dir.is_dir():
            statuses[endpoint.id] = "ADD"
            continue
        # Strict fixed-order comparison (generated side first): statuses agree with diff verdicts.
        generated_side = artifact_contract(endpoint_dir)
        spec_side = spec_contract(endpoint)
        statuses[endpoint.id] = "UPD" if DeepDiff(generated_side, spec_side) else "OK"

    removed: list[str] = []
    for orphan in orphan_artifact_dirs(api_spec_dir, endpoints):
        # Validation gate: a corrupt orphan fails the run even though only its name is reported.
        artifact_contract(orphan)
        removed.append(orphan.name)

    return statuses, removed


def _load_endpoints(entry: SpecEntry, cwd: Path) -> list[Endpoint]:
    """Parse, validate and extract the endpoints of one spec file.

    Args:
        entry: The config entry of the spec (its ``location`` is resolved
            against ``cwd``).
        cwd: Working directory used to resolve the spec location.

    Returns:
        The spec's endpoints in extraction order.

    Raises:
        click.ClickException: If the spec is not a mapping with a "paths" mapping, or
            ``extract_endpoints`` rejects it (no openapi/swagger version key or a response
            key outside the allowed shapes).
    """
    spec = load_spec(cwd / entry.location)
    if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict):
        raise click.ClickException(f"invalid spec file (missing 'paths'): {entry.location}")
    try:
        return extract_endpoints(spec)
    except ValueError as error:
        # An invalid spec is a CLI error, not a traceback (mirrors generate/diff).
        raise click.ClickException(f"invalid spec file ({error}): {entry.location}") from error


def run_list(spec_name: Optional[str], with_status: bool = False) -> None:
    """List endpoints from OpenAPI specs, optionally with sync statuses.

    With ``with_status``, lines gain a sync status and removed artifact dirs join the listing.

    Args:
        spec_name: Optional spec name to list; if None, lists all specs
        with_status: Flag annotating every line with its artifact synchronization status
            (``ADD``/``UPD``/``OK``/``REMOVED``).

    Raises:
        click.ClickException: If spec_name not found, spec parse fails, or — status mode
            only — an artifact ``meta.json``/schema file is missing, unreadable or corrupt
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

    cwd = Path.cwd()

    # Process each spec
    for name, entry in specs.items():
        endpoints = _load_endpoints(entry, cwd)
        if not endpoints:
            logger.warning(f"no endpoints found in spec: {name}")
        if not with_status:
            print(render_list(name, entry.location, endpoints))
            continue
        statuses, removed = endpoint_statuses(cwd / "api" / name, endpoints)
        # Print a block only when it has at least one line; removed segments count as lines.
        if endpoints or removed:
            print(render_status_list(name, entry.location, endpoints, statuses, removed))


@click.command("list", help="List endpoints from specs")
@click.option("--spec", "spec_name", default=None, help="Spec name to list")
@click.option(
    "--status",
    "with_status",
    is_flag=True,
    default=False,
    help="Show the artifact synchronization status of every line",
)
def list_cmd(spec_name: Optional[str], with_status: bool) -> None:
    """Click wrapper for the endpoint list subcommand; delegates to run_list."""
    run_list(spec_name, with_status)
