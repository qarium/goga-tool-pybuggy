"""generate command handler - scaffold api/ schema files, meta.json contracts, api.py fixtures and tests/ dirs."""

import json
import math
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional

import click
from datamodel_code_generator import (
    DataModelType,
    DatetimeClassType,
    Formatter,
    InputFileType,
    LiteralType,
    generate,
)

from ...config import Config, SpecEntry, load_config
from ...spec import Endpoint, extract_endpoints, load_spec

# JSON-Schema draft id stamped on the request-body fragment before model generation.
_JSON_SCHEMA_DRAFT = "http://json-schema.org/draft-07/schema#"

# Ruff invocation options — match the project's pyproject.toml so generated api.py
# modules are aligned the same way as the pybuggy source (line-length 120, py310).
_RUFF_LINE_LENGTH = "120"
_RUFF_TARGET_VERSION = "py310"

# Help text of -f/--force — names the full artifact set the flag regenerates.
_FORCE_HELP = "Overwrite existing response schema files, meta.json, api.py and __init__.py markers"

# Matches an OpenAPI path parameter "{name}" (name kept verbatim, incl. case).
_PATH_PARAM_RE = re.compile(r"\{([^}]*)\}")

# build_endpoint_id normalizes "/" and "-" but not other punctuation (e.g. the dot in
# "/v1.0/clients"); leftover characters become "_" so the generated module stays importable.
_NON_IDENT_RE = re.compile(r"\W")


def _safe_identifier(text: str) -> str:
    """Make ``text`` usable as a Python identifier segment (package dir or def name).

    Applied identically to the endpoint directory name and the fixture name, so the two never disagree.

    Args:
        text: Lowercased identifier candidate (typically an endpoint id).

    Returns:
        Text safe for use as a package directory name and a ``def`` name.
    """
    ident = _NON_IDENT_RE.sub("_", text)
    return f"_{ident}" if ident[:1].isdigit() else ident


def _json_default(obj: object) -> object:
    """Serialize non-JSON-native objects carried in resolved specs.

    Dates render as ISO 8601 strings, the same convention as ``output.render_info``.

    Args:
        obj: Object that ``json.dumps`` could not encode natively.

    Returns:
        ISO 8601 string for date/datetime values.

    Raises:
        TypeError: For any unhandled type, so ``json.dumps`` reports it with its standard message.
    """
    if isinstance(obj, date):
        return obj.isoformat()

    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def _json_native(value: Any) -> Any:
    """Normalize a resolved spec value to strict-JSON-native form.

    Non-finite floats become ``None`` — ``json.dumps`` would emit the invalid tokens ``NaN``/``Infinity``.

    Args:
        value: A resolved schema fragment (mapping, list or scalar).

    Returns:
        The fragment with every non-finite float replaced by ``None``.
    """
    if isinstance(value, dict):
        return {key: _json_native(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_native(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _find_ruff() -> str:
    """Locate the ruff executable, preferring PATH then the interpreter's venv.

    Args:
        none.

    Returns:
        Absolute path to the ruff executable.

    Raises:
        click.ClickException: If ruff is neither on PATH nor next to the interpreter.
    """
    found = shutil.which("ruff")
    if found:
        return found

    # When run as `.venv/bin/pytest` the venv may not be on PATH; fall back to the
    # ruff installed alongside the running interpreter.
    candidate = Path(sys.executable).parent / "ruff"
    if candidate.exists():
        return str(candidate)

    raise click.ClickException("ruff executable not found; install ruff to generate api.py fixtures")


def _apply_ruff(source: str) -> str:
    """Align a Python source string with ruff: sort imports then format.

    Deterministic: identical input yields identical output — no timestamps or environment-dependent state.

    Args:
        source: Python source text to align.

    Returns:
        ruff-aligned Python source text (trailing newline included).

    Raises:
        click.ClickException: If any ruff invocation fails.
    """
    ruff = _find_ruff()
    options = ["--line-length", _RUFF_LINE_LENGTH, "--target-version", _RUFF_TARGET_VERSION]

    try:
        linted = subprocess.run(
            [ruff, "check", "--fix", "--exit-zero", "--select", "I", *options, "-"],
            input=source,
            capture_output=True,
            check=True,
            text=True,
        )
        formatted = subprocess.run(
            [ruff, "format", *options, "-"],
            input=linted.stdout,
            capture_output=True,
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        # Map the subprocess failure to the CLI error, carrying ruff's own diagnostics.
        raise click.ClickException(f"ruff failed: {error.stderr or error}") from error
    return formatted.stdout


def _strip_generator_header(source: str) -> str:
    """Drop the leading ``# generated by datamodel-codegen`` comment header.

    The header appears even with ``disable_timestamp=True``; every leading comment/blank line is removed.

    Args:
        source: Raw module text produced by ``datamodel_code_generator.generate``.

    Returns:
        Module text without the leading comment header.
    """
    lines = source.splitlines()
    index = 0
    while index < len(lines) and (not lines[index].strip() or lines[index].lstrip().startswith("#")):
        index += 1
    return "\n".join(lines[index:]).strip()


def _collect_request_properties(request: dict) -> dict | None:
    """Return sanitized property schemas for model generation, or None to skip models.

    Non-dict/non-bool fragments become ``True`` (any-type schema) so rendering never raises.

    Args:
        request: Resolved JSON-Schema of the request body.

    Returns:
        Mapping of property name to a valid JSON-Schema fragment, or ``None``.
    """
    properties = request.get("properties")
    if not isinstance(properties, dict) or not properties:
        return None
    return {name: sub if isinstance(sub, (dict, bool)) else True for name, sub in properties.items()}


def _render_request_models(request: dict, properties: dict) -> str:
    """Render pydantic model classes for an endpoint request body via datamodel-code-generator.

    No disk I/O — the schema is fed to the generator as a JSON string and the module text returned.

    Args:
        request: Resolved JSON-Schema of the request body (may carry ``type``,
            ``required``, and nested object/array schemas).
        properties: Sanitized property schemas (see ``_collect_request_properties``).

    Returns:
        Model-class source text (header-stripped), deterministic for a given schema.
    """
    schema = {**request, "properties": properties, "$schema": _JSON_SCHEMA_DRAFT}
    source = generate(
        snake_case_field=True,
        capitalise_enum_members=True,
        input_=json.dumps(_json_native(schema), default=_json_default),
        input_file_type=InputFileType.JsonSchema,
        disable_future_imports=True,
        disable_timestamp=True,
        class_name="Request",
        output_model_type=DataModelType.PydanticV2BaseModel,
        use_standard_collections=True,
        enum_field_as_literal=LiteralType.All,
        use_union_operator=True,
        output_datetime_class=DatetimeClassType.Datetime,
        formatters=[Formatter.BUILTIN],
    )
    return _strip_generator_header(source)


def _write_package_markers(bottom: Path, top: Path, force: bool) -> None:
    """Write an empty ``__init__.py`` in every directory from ``bottom`` up to (including) ``top``.

    Marker skip/overwrite follows ``force``, mirroring the schema and ``api.py`` semantics.

    Args:
        bottom: deepest directory on the package path (the per-endpoint ``api`` dir).
        top: top-most directory on the package path (the ``api`` root); must be an ancestor of ``bottom``.
        force: when true, overwrite an existing ``__init__.py``; when false, skip existing markers.

    Raises:
        none.
    """
    current = bottom
    while True:
        init_file = current / "__init__.py"
        if force or not init_file.exists():
            init_file.write_text("", encoding="utf-8")
        if current == top:
            break
        current = current.parent


def _convert_route(path: str) -> str:
    """Convert OpenAPI ``{param}`` path segments to Express-style ``:param``.

    The parameter name and its case are preserved, e.g. ``{orderID}`` -> ``:orderID``.

    Args:
        path: OpenAPI path template with parameters in braces.

    Returns:
        Route string with parameters rewritten to ``:name`` form.
    """
    return _PATH_PARAM_RE.sub(r":\1", path)


def render_api_module(endpoint: Endpoint) -> str:
    """Render the full source text of an ``api.py`` module for a single endpoint.

    The text is ruff-aligned and deterministic: identical ``Endpoint`` input yields identical output.

    Args:
        endpoint: Endpoint to render the ``api.py`` module for.

    Returns:
        Full source text of the ``api.py`` module (trailing newline included).
    """
    # endpoint.id lowercases the method in its ``_<method>`` suffix, so normalize here too.
    method = endpoint.method.lower()

    # 1. Fixture name: <method>_<id with the trailing "_<method>" removed>, sanitized
    #    via _safe_identifier like the directory name, so the two can never disagree.
    fixture_name = _safe_identifier(f"{method}_{endpoint.id.removesuffix('_' + method)}")

    # 2. Route: rewrite each {param} as :param (preserve case)
    route = _convert_route(endpoint.path)

    # repr() keeps the literal valid Python — a path key may legally carry a quote.
    fixture_block = (
        "@pytest.fixture(scope='function')\n"
        f"def {fixture_name}(api: Api) -> Endpoint:\n"
        f"    return Endpoint(api, {route!r}, method={method.upper()!r})"
    )

    # 3. Optional request-body models — only when the body declares usable properties
    properties = _collect_request_properties(endpoint.request)

    # 4. Assemble the module sections, then align the whole text with ruff (merges
    #    the pytest/pybuggy.api imports with the model imports and formats it).
    sections: list[str] = ["import pytest", "from goga_tool_pybuggy.api import Endpoint, Api"]
    if properties:
        sections.append(_render_request_models(endpoint.request, properties))
    sections.append(fixture_block)

    return _apply_ruff("\n\n".join(sections))


def _collect_specs(
    specs: dict[str, SpecEntry], endpoint_filter: set[str] | None, cwd: Path
) -> tuple[list[tuple[str, list[Endpoint]]], set[str]]:
    """Phase 1 — parse, extract and filter the selected specs without writing to disk.

    A spec with no operations is silently skipped (pre-filter, so not an empty filter result).

    Args:
        specs: selected spec entries (name -> SpecEntry).
        endpoint_filter: optional set of endpoint ids to keep; ``None`` means keep all.
        cwd: working directory used to resolve each spec location.

    Returns:
        ``(to_generate, matched_ids)`` — ``(name, endpoints)`` pairs plus ids matched by the filter.

    Raises:
        click.ClickException: If a spec has no "paths" (absent, present with a
            null value, or the document is not a mapping at all) or is invalid
            (no version key, or an illegal response status key).
    """
    to_generate: list[tuple[str, list[Endpoint]]] = []
    matched_ids: set[str] = set()
    for name, entry in specs.items():
        spec = load_spec(cwd / entry.location)

        # The key alone is not enough: a null `paths:` or non-mapping document would crash extract_endpoints.
        if not isinstance(spec, dict) or not isinstance(spec.get("paths"), dict):
            raise click.ClickException(f"spec has no paths: {entry.location}")

        try:
            endpoints = extract_endpoints(spec)
        except ValueError as error:
            # ValueError marks an invalid spec (no version key, illegal response key); ValidationError is a subclass.
            raise click.ClickException(f"invalid spec file ({error}): {entry.location}") from error

        # No endpoints: skip artifact creation for this spec silently (pre-filter check,
        # so the skip reflects a spec with no operations, not an empty filter result).
        if not endpoints:
            continue

        # Apply the optional endpoint-id filter
        if endpoint_filter is not None:
            endpoints = [endpoint for endpoint in endpoints if endpoint.id in endpoint_filter]
            matched_ids |= {endpoint.id for endpoint in endpoints}

        to_generate.append((name, endpoints))

    return to_generate, matched_ids


def _endpoint_meta(endpoint: Endpoint) -> dict[str, Any]:
    """Build the per-endpoint ``meta.json`` input-contract payload.

    All three keys are always present, exactly as extracted, with no re-normalization.

    Args:
        endpoint: Endpoint whose input contract is described.

    Returns:
        Mapping with exactly the keys ``parameters``, ``request_body`` and ``vars``.
    """
    return {
        "parameters": endpoint.query_params,
        "request_body": endpoint.request,
        "vars": endpoint.path_params,
    }


def _write_artifacts(to_generate: list[tuple[str, list[Endpoint]]], force: bool, cwd: Path) -> None:
    """Phase 2 — write response schemas, meta.json, api.py fixtures, package markers and test dirs.

    Args:
        to_generate: ``(name, endpoints)`` pairs to scaffold.
        force: when false, existing schema/meta.json/api.py files and ``__init__.py`` markers are
            skipped silently; when true, they are overwritten.
        cwd: working directory under which the ``api/`` and ``tests/`` trees are written.

    Raises:
        click.ClickException: If rendering an endpoint's api.py fails (ruff not found or ruff
            exits non-zero). Writes are sequential per endpoint, so endpoints before the failing
            one are already on disk.
        OSError: If any schema/meta.json/api.py/``__init__.py`` write fails.
    """
    for name, endpoints in to_generate:
        for endpoint in endpoints:
            # One sanitized id drives both the directory and the fixture name, so the two never disagree.
            safe_id = _safe_identifier(endpoint.id)
            endpoint_dir = cwd / "api" / name / safe_id
            schemas_dir = endpoint_dir / "schemas"
            schemas_dir.mkdir(parents=True, exist_ok=True)

            test_dir = cwd / "tests" / name / safe_id
            test_dir.mkdir(parents=True, exist_ok=True)

            # Empty __init__.py markers on every directory of the api.py path
            # (api/, api/<name>/, api/<name>/<id>/) so the fixture tree is an importable package.
            _write_package_markers(endpoint_dir, cwd / "api", force)

            for status_code, schema in endpoint.response.items():
                schema_file = schemas_dir / f"{status_code}.json"
                if schema_file.exists() and not force:
                    continue
                schema_file.write_text(
                    json.dumps(_json_native(schema), indent=2, ensure_ascii=False, default=_json_default),
                    encoding="utf-8",
                )

            # write the per-endpoint api.py fixture module (force semantics match the schemas)
            api_file = endpoint_dir / "api.py"
            if force or not api_file.exists():
                api_file.write_text(render_api_module(endpoint), encoding="utf-8")

            # write the per-endpoint meta.json input contract (force semantics match the schemas)
            meta_file = endpoint_dir / "meta.json"
            if force or not meta_file.exists():
                meta = json.dumps(
                    _json_native(_endpoint_meta(endpoint)), indent=2, ensure_ascii=False, default=_json_default
                )
                meta_file.write_text(meta, encoding="utf-8")


def run_generate(spec_name: Optional[str], force: bool, endpoint_ids: Optional[list[str]] = None) -> None:
    """Scaffold api/ response-schema files, meta.json contracts, api.py fixture modules and empty tests/ directories.

    Two phases — collect (no disk writes) then write — so unknown ids raise before any artifact is written.

    Args:
        spec_name: Optional spec filter; when set generate only that spec, otherwise generate all specs.
        force: When false, existing schema, meta.json and api.py files are skipped silently; when
            true, overwritten.
        endpoint_ids: Optional filter (as produced by ``build_endpoint_id``); ``None`` or empty
            generates every endpoint of the selected specs.

    Raises:
        click.ClickException: If spec_name is set but not found in config specs; a selected spec has
            no "paths"; a selected spec is invalid (not a mapping, or a response key outside the
            legal status-key shapes); endpoint_ids contains an id not found in any selected spec;
            or two endpoint ids of one spec map to the same directory name.
    """
    # Step 1: Load the config from the fixed path
    config: Config = load_config()

    # Step 2: Validate the optional spec filter
    if spec_name is not None and spec_name not in config.specs:
        raise click.ClickException(f"spec not found: {spec_name}")

    # Step 3: Select specs (all, or only the filtered one)
    specs: dict[str, SpecEntry] = config.specs if spec_name is None else {spec_name: config.specs[spec_name]}

    # Normalize the endpoint-id filter: an empty filter means "no filter" (all endpoints), so a
    # variadic CLI argument passed with no values behaves identically to the unfiltered command.
    endpoint_filter: set[str] | None = set(endpoint_ids) if endpoint_ids else None

    cwd = Path.cwd()

    # Step 4: Phase 1 — parse, extract, filter and collect (no disk writes yet)
    to_generate, matched_ids = _collect_specs(specs, endpoint_filter, cwd)

    # Step 5: Validate the endpoint-id filter — every requested id must match at least one selected spec
    if endpoint_filter is not None:
        missing = sorted(endpoint_filter - matched_ids)
        if missing:
            raise click.ClickException(f"endpoint not found: {', '.join(missing)}")

    # Step 5.5: Reject sanitized-id collisions before any write; colliding endpoints would mix artifacts.
    for name, endpoints in to_generate:
        owners: dict[str, tuple[str, str]] = {}
        for endpoint in endpoints:
            safe_id = _safe_identifier(endpoint.id)
            if safe_id in owners:
                first_id, first_path = owners[safe_id]
                raise click.ClickException(
                    f"paths {first_path!r} and {endpoint.path!r} under spec {name!r} both map to "
                    f"directory {safe_id!r} (endpoint id {first_id!r} vs {endpoint.id!r}); "
                    f"rename one path"
                )
            owners[safe_id] = (endpoint.id, endpoint.path)

    # Step 6: Phase 2 — scaffold artifacts for each selected spec/endpoint
    _write_artifacts(to_generate, force, cwd)


@click.command("generate")
@click.option("-s", "--spec", "spec_name", default=None, help="Spec name to generate")
@click.option("-f", "--force", is_flag=True, default=False, help=_FORCE_HELP)
@click.argument("endpoint-ids", nargs=-1, default=None)
def generate_cmd(spec_name: Optional[str], force: bool, endpoint_ids: tuple[str, ...]) -> None:
    """Click wrapper for the endpoint generate subcommand.

    Binds --spec/--force and the positional endpoint-ids filter, then delegates to run_generate.
    """
    run_generate(spec_name, force, list(endpoint_ids) if endpoint_ids else None)
