"""Comparison-side contract builders for the endpoint diff command.

Both builders yield the same four-key structure, so a no-drift pair compares equal under DeepDiff.
"""

import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import click

from ...spec import Endpoint


class _CorruptArtifactError(ValueError):
    """Signal that a parsed artifact file does not have the expected object shape."""


def _json_default(obj: object) -> object:
    """Serialize non-JSON-native objects carried in resolved specs.

    Dates render as ISO 8601 strings, matching the convention generate wrote the artifact side with.

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

    Non-finite floats become ``None`` (generate writes ``null``), keeping the comparison sides symmetric.

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


def spec_contract(endpoint: Endpoint) -> dict[str, Any]:
    """Assemble the spec side of the comparison for one endpoint.

    The keys mirror ``meta.json`` plus ``schemas``; a JSON round-trip keeps the sides symmetric.

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
    return json.loads(json.dumps(_json_native(contract), ensure_ascii=False, default=_json_default))


def artifact_contract(artifact_dir: Path) -> dict[str, Any]:
    """Read the generated side of the comparison from an artifact directory.

    Reads ``meta.json`` plus ``schemas/*.json`` keyed by file stem; contents pass through verbatim, never validated.

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
            # Valid JSON that is not an object is equally corrupt — key lookups on it raise TypeError, not KeyError.
            raise _CorruptArtifactError(meta_path)
        parameters = meta["parameters"]
        request_body = meta["request_body"]
        vars_ = meta["vars"]
    # UnicodeDecodeError: a non-UTF-8 file is unreadable and maps to the same operational error.
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
