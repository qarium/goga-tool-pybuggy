"""Comparison-side contract builders for the endpoint diff command.

spec_contract assembles the spec side of the comparison from an Endpoint;
artifact_contract reads the generated side from an endpoint's artifact
directory (meta.json + schemas/*.json). Both yield the same four-key
structure, so a no-drift pair compares equal under DeepDiff.
"""

import json
from datetime import date
from pathlib import Path
from typing import Any

import click

from ...spec import Endpoint


class _CorruptArtifactError(ValueError):
    """Signal that a parsed artifact file does not have the expected object shape."""


def _json_default(obj: object) -> str:
    """Serialize non-JSON-native objects carried in resolved specs.

    swax/Prance convert YAML date-like values (e.g. ``example: 2020-01-01``
    under ``format: date``/``date-time``) into ``datetime.date``/
    ``datetime.datetime`` objects, which ``json.dumps`` cannot encode by
    default. Rendering them as ISO 8601 strings keeps the spec side
    byte-symmetric with the artifact side, which generate wrote through the
    same convention — skipping the normalization would surface as
    ``type_changes`` noise in the diff. ``datetime.datetime`` is a subclass
    of ``date``, so a single ``date`` check covers both.

    Args:
        obj: Object that ``json.dumps`` could not encode natively.

    Returns:
        ISO 8601 string for date/datetime values.

    Raises:
        TypeError: For any type this serializer does not handle, re-raised so
            ``json.dumps`` reports it with its standard message.
    """
    if isinstance(obj, date):
        return obj.isoformat()

    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def spec_contract(endpoint: Endpoint) -> dict[str, Any]:
    """Assemble the spec side of the comparison for one endpoint.

    Builds the unified four-key structure — ``parameters``/``request_body``/
    ``vars`` mirror the keys generate writes to ``meta.json``, ``schemas``
    carries ``{status_code: schema}`` from the endpoint response — then
    normalizes the whole mapping to JSON-native values through a JSON
    round-trip (dates to ISO 8601 strings, tuples to lists, non-string keys
    to strings), making it structurally symmetric with the artifact side.
    Schemas are taken exactly as extracted and never re-normalized. The
    function is pure: no I/O, no filesystem access.

    Args:
        endpoint: Endpoint whose contract the spec side describes.

    Returns:
        JSON-native mapping with exactly the keys ``parameters``,
        ``request_body``, ``vars`` and ``schemas``.
    """
    contract = {
        "parameters": endpoint.query_params,
        "request_body": endpoint.request,
        "vars": endpoint.path_params,
        "schemas": endpoint.response,
    }
    return json.loads(json.dumps(contract, ensure_ascii=False, default=_json_default))


def artifact_contract(artifact_dir: Path) -> dict[str, Any]:
    """Read the generated side of the comparison from an artifact directory.

    Reads ``meta.json`` for the ``parameters``/``request_body``/``vars`` keys
    and every ``schemas/*.json`` file (keyed by file stem, in glob sort
    order). An absent ``schemas/`` subdirectory yields ``schemas: {}`` —
    globbing a missing directory is empty. Contents are passed through
    verbatim: never interpreted, never validated. The directory is only
    read, never written.

    Args:
        artifact_dir: Existing artifact directory ``api/<spec>/<segment>/``
            (or an orphan directory of the same shape).

    Returns:
        Mapping with exactly the keys ``parameters``, ``request_body``,
        ``vars`` and ``schemas``.

    Raises:
        click.ClickException: If ``meta.json`` is missing, unreadable or
            corrupt; if it lacks any of the three mandatory keys; or if any
            schema file is unreadable or corrupt.
    """
    meta_path = artifact_dir / "meta.json"
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            # Valid JSON that is not an object (null, a list, a scalar) is
            # equally corrupt — key lookups on it raise TypeError, not KeyError.
            raise _CorruptArtifactError(meta_path)
        parameters = meta["parameters"]
        request_body = meta["request_body"]
        vars_ = meta["vars"]
    # UnicodeDecodeError: a non-UTF-8 file is unreadable under the declared
    # read convention and maps to the same operational error.
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, _CorruptArtifactError) as error:
        raise click.ClickException(f"unreadable or corrupt artifact meta.json: {meta_path}") from error

    schemas: dict[str, Any] = {}
    for schema_file in sorted((artifact_dir / "schemas").glob("*.json")):
        try:
            schemas[schema_file.stem] = json.loads(schema_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise click.ClickException(f"unreadable or corrupt artifact schema: {schema_file}") from error

    return {
        "parameters": parameters,
        "request_body": request_body,
        "vars": vars_,
        "schemas": schemas,
    }
