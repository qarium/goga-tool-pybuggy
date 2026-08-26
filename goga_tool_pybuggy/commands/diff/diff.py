"""Handler and Click wrapper for the endpoint diff command.

run_diff reports, per compared unit, the drift between the endpoint contract
taken from the current spec and the previously generated artifacts; diff_cmd
binds the CLI options and delegates to run_diff.
"""

import json
from pathlib import Path
from typing import Optional

import click
from deepdiff import DeepDiff

from ...config import Config, SpecEntry, load_config
from ...output import render_diff
from ...spec import Endpoint, extract_endpoints, load_spec
from .artifacts import orphan_artifact_dirs, sanitize_id
from .contract import artifact_contract, spec_contract


def _collect_specs(
    specs: dict[str, SpecEntry], endpoint_filter: Optional[set[str]], cwd: Path
) -> tuple[list[tuple[str, list[Endpoint], list[Endpoint]]], set[str]]:
    """Phase 1 — parse, extract and filter the selected specs without printing anything.

    For each spec (config order): load and validate it (``paths`` required), extract
    endpoints, and — when ``endpoint_filter`` is set — keep only endpoints whose id is
    in the filter. A spec with no operations is NOT silently skipped (unlike generate):
    it simply contributes no per-endpoint documents, while its artifact directories are
    still reported as removed. Returns the per-spec endpoint lists plus the set of
    endpoint ids that matched the filter.

    Args:
        specs: selected spec entries (name -> SpecEntry).
        endpoint_filter: optional set of endpoint ids to keep; ``None`` means keep all.
        cwd: working directory used to resolve each spec location.

    Returns:
        ``(collected, matched_ids)`` — ``(name, endpoints, kept)`` triples plus the ids
        matched by the filter.

    Raises:
        click.ClickException: If a spec has no "paths" mapping (absent, or
            present with a null value), is not a mapping at all, or declares
            no openapi/swagger version key.
    """
    collected: list[tuple[str, list[Endpoint], list[Endpoint]]] = []
    matched_ids: set[str] = set()
    for name, entry in specs.items():
        spec = load_spec(cwd / entry.location)

        # Validate spec has the required structure — the key alone is not
        # enough: `paths:` with no value parses to None, which would crash
        # extract_endpoints on paths.items(). An empty file parses to None and
        # a top-level list/str document is equally not a spec mapping.
        if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict):
            raise click.ClickException(f"invalid spec file (missing 'paths'): {entry.location}")

        try:
            endpoints = extract_endpoints(spec)
        except ValueError as error:
            # extract_endpoints raises ValueError on a spec declaring neither
            # an openapi nor a swagger version key — an invalid spec file, not
            # a traceback (pydantic ValidationError is a ValueError subclass
            # and maps to the same channel).
            raise click.ClickException(f"invalid spec file ({error}): {entry.location}") from error
        kept = [e for e in endpoints if endpoint_filter is None or e.id in endpoint_filter]
        matched_ids |= {e.id for e in kept}
        collected.append((name, endpoints, kept))
    return collected, matched_ids


def _print_comparison(unit: str, generated_side: dict, spec_side: dict) -> None:
    """Compare the two sides of one unit and print its JSON document.

    The comparison direction is fixed — t1 is the generated side, t2 the spec
    side (the spec is the current truth) — and strict: no order-insensitive or
    type-group relaxations. The document is printed for every compared unit,
    with an empty diff value when there is no drift. ``to_json`` is the only
    JSON-native conversion of the result: the mappings of ``to_dict`` hold
    set-like values that ``json.dumps`` cannot serialize.

    Args:
        unit: Identifier key of the compared unit — the raw endpoint id for
            spec-side entries or the sanitized segment for removed directories.
        generated_side: The artifact-side contract (empty when the endpoint has
            no artifact directory).
        spec_side: The spec-side contract (empty for removed directories).
    """
    diff = DeepDiff(generated_side, spec_side)
    print(render_diff(unit, json.loads(diff.to_json())))


def run_diff(spec_name: Optional[str], endpoint_ids: Optional[list[str]] = None) -> None:
    """Report per-endpoint drift between the current spec and the generated artifacts.

    Loads the config from the fixed config path and, for each (optionally filtered)
    spec, parses the spec file, extracts endpoints, optionally filters them by id,
    and prints one JSON document per compared unit: spec-side endpoints keyed by the
    raw endpoint id (an empty diff value when there is no drift) and removed artifact
    directories keyed by their sanitized segment. The endpoint-id filter narrows only
    the spec side — removed-side discovery always scans the whole ``api/<spec>/`` tree
    of every selected spec.

    Two phases — collect/validate (no output) then print — so an unknown endpoint id
    raises before anything is printed. The command is read-only and drift is a result,
    not a failure: a completed run returns without raising.

    Args:
        spec_name: Optional spec filter; when set compare only that spec, otherwise
            compare all specs.
        endpoint_ids: Optional endpoint-id filter keyed on the raw ``Endpoint`` id;
            when set compare only endpoints whose id is in the list. ``None`` or empty
            compares every endpoint of the selected specs. Every requested id must
            match at least one selected spec, otherwise nothing is printed.

    Raises:
        click.ClickException: If spec_name is set but not found in config specs; a
            selected spec is invalid (not a mapping, no "paths", or no
            openapi/swagger version key); endpoint_ids contains an id not found in
            any selected spec; or an artifact ``meta.json``/schema file is missing,
            unreadable or corrupt.
    """
    # Step 1: Load the config from the fixed path
    config: Config = load_config()

    # Step 2: Validate the optional spec filter
    if spec_name is not None and spec_name not in config.specs:
        raise click.ClickException(f"spec not found: {spec_name}")

    # Step 3: Select specs (all, or only the filtered one)
    specs: dict[str, SpecEntry] = config.specs if spec_name is None else {spec_name: config.specs[spec_name]}

    # Step 4: Normalize the endpoint-id filter — an empty filter means "no filter"
    endpoint_filter: Optional[set[str]] = set(endpoint_ids) if endpoint_ids else None

    cwd = Path.cwd()

    # Step 5: Phase 1 — parse, extract, filter and collect (no output yet)
    collected, matched_ids = _collect_specs(specs, endpoint_filter, cwd)

    # Step 6: Validate the endpoint-id filter — before anything is printed
    if endpoint_filter is not None:
        missing = sorted(endpoint_filter - matched_ids)
        if missing:
            raise click.ClickException(f"endpoint not found: {', '.join(missing)}")

    # Step 7: Phase 2 — compare and print each selected spec's units
    for name, endpoints, kept in collected:
        api_spec_dir = cwd / "api" / name
        for endpoint in kept:
            spec_side = spec_contract(endpoint)
            endpoint_dir = api_spec_dir / sanitize_id(endpoint.id)
            # An absent artifact directory compares against an empty contract (added)
            generated_side = artifact_contract(endpoint_dir) if endpoint_dir.is_dir() else {}
            _print_comparison(endpoint.id, generated_side, spec_side)
        # Removed side — discovery over the FULL endpoint list, never the filtered subset
        for orphan in orphan_artifact_dirs(api_spec_dir, endpoints):
            _print_comparison(orphan.name, artifact_contract(orphan), {})


@click.command("diff", help="Report drift between the specs and the generated artifacts")
@click.option("-s", "--spec", "spec_name", default=None, help="Spec name to diff")
@click.argument("endpoint-ids", nargs=-1, default=None)
def diff_cmd(spec_name: Optional[str], endpoint_ids: tuple[str, ...]) -> None:
    """Click wrapper for the endpoint diff subcommand.

    Binds --spec and the positional endpoint-ids filter, then delegates to run_diff.
    """
    run_diff(spec_name, list(endpoint_ids) if endpoint_ids else None)
