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
            existing directory is missing, unreadable or corrupt; or if two
            endpoints share the same raw id (the report is keyed by id, so one
            of the two would be silently misreported).
    """
    # build_endpoint_id collapses both "-" and "/", so two distinct paths can
    # yield the *identical* raw id. The report is keyed by that id — the second
    # classification would overwrite the first and both lines would print the
    # surviving status. generate refuses such a spec before writing anything;
    # the report refuses it too instead of misreporting (same message shape).
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


def _load_endpoints(entry: SpecEntry, cwd: Path) -> list[Endpoint]:
    """Parse, validate and extract the endpoints of one spec file.

    Args:
        entry: The config entry of the spec (its ``location`` is resolved
            against ``cwd``).
        cwd: Working directory used to resolve the spec location.

    Returns:
        The spec's endpoints in extraction order.

    Raises:
        click.ClickException: If the spec is not a mapping, has no "paths"
            mapping (the key alone is not enough: ``paths:`` with no value
            parses to None, and an empty or list/str document is equally not
            a spec mapping — all three would crash ``extract_endpoints``),
            or declares no openapi/swagger version key or a response key
            outside the shapes the specifications allow.
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

    Loads config from the fixed config path and for each spec: parses, extracts
    endpoints, renders formatted output, and prints it. In the plain mode the
    block lists the endpoints; with ``with_status`` every line is annotated
    with its artifact synchronization status and removed artifact directories
    join the listing, while a spec with no lines at all prints nothing.

    Args:
        spec_name: Optional spec name to list; if None, lists all specs
        with_status: Optional flag annotating every line with its artifact
            synchronization status (``ADD``/``UPD``/``OK``/``REMOVED``);
            defaults to the plain listing

    Raises:
        click.ClickException: If spec_name not found, spec parse fails, or —
            status mode only — an artifact ``meta.json``/schema file is
            missing, unreadable or corrupt
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
        # A spec prints its block only when it has at least one line —
        # removed segments count as lines.
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
    """Click wrapper for the endpoint list subcommand.

    Binds --spec and the --status flag, then delegates to run_list.
    """
    run_list(spec_name, with_status)
