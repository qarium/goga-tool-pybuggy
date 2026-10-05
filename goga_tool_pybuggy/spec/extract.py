"""Extract endpoints from OpenAPI/Swagger specs."""

import re
from typing import Any, Literal

from .endpoint import Endpoint

HTTP_METHODS = ("get", "post", "put", "delete", "patch", "options", "head")

# Allowed response keys: 3-digit code, `default`, or `2XX` wildcard — keys become artifact filenames.
# Anchored with `\Z`, not `$` — `$` also matches just before a trailing newline.
_RESPONSE_KEY_RE = re.compile(r"^(?:[0-9]{3}|default|[1-5]XX)\Z", re.IGNORECASE)

# Whitelist of inlined type fields used to filter Swagger 2.0 query and path params.
# `x-nullable` is kept so the Swagger nullable keyword reaches `_normalize_nullable`.
_TYPE_FIELDS = (
    "type",
    "format",
    "items",
    "enum",
    "default",
    "description",
    "x-nullable",
)

# Keywords whose value is a {property-name: schema} map, not a schema itself;
# a property named ``nullable`` must not be mistaken for the nullability keyword.
_PROPERTY_MAP_KEYS = ("properties", "patternProperties")


def detect_spec_version(spec: dict[str, Any]) -> str:
    """Classify a parsed spec by its content as ``"swagger"`` or ``"openapi"``.

    Determined from the spec's content, not from any declarative config type field.

    Args:
        spec: the dereferenced spec dict (output of ``load_spec``).

    Returns:
        ``"swagger"`` if a top-level ``swagger`` key is present, else
        ``"openapi"`` if a top-level ``openapi`` key is present.

    Raises:
        ValueError: if the spec declares neither a ``swagger`` nor an
            ``openapi`` version key.
    """
    if "swagger" in spec:
        return "swagger"
    if "openapi" in spec:
        return "openapi"
    raise ValueError("spec declares neither a swagger nor an openapi version")


def _extract_request(operation: dict[str, Any], version: str) -> dict[str, Any]:
    """Extract the request-body schema from an operation in a format-aware way.

    Args:
        operation: a single operation dict (``paths[path][method]``).
        version: the detected spec version (``"openapi"`` or ``"swagger"``).

    Returns:
        The resolved request schema, or ``{}`` when absent or explicitly null.
    """
    if version == "openapi":
        # Each level may parse to None, so every `.get` is guarded by `or {}`.
        body = operation.get("requestBody") or {}
        content = body.get("content") or {}
        json_content = content.get("application/json") or {}
        return json_content.get("schema") or {}
    for param in operation.get("parameters") or []:
        if not isinstance(param, dict):
            # Skip malformed entries (e.g. null) — mirrors the _extract_params guard
            continue
        if param.get("in") == "body":
            return param.get("schema") or {}
    return {}


def _extract_responses(operation: dict[str, Any], version: str) -> dict[str, Any]:
    """Extract response schemas from an operation in a format-aware way.

    An illegal response key raises — keys become artifact filenames downstream.

    Args:
        operation: a single operation dict (``paths[path][method]``).
        version: the detected spec version (``"openapi"`` or ``"swagger"``).

    Returns:
        ``{status_code: schema}`` for each declared response, keyed by the
        stringified status code (an unquoted YAML ``200:`` parses to an int).

    Raises:
        ValueError: If a response key is not a legal status key.
    """
    # `responses:` with no value parses to None — treated as no declared responses.
    responses = operation.get("responses") or {}
    for code in responses:
        if not _RESPONSE_KEY_RE.match(str(code)):
            raise ValueError(
                f"invalid response status key {code!r} "
                f"(expected a 3-digit code, 'default' or a range wildcard like '2XX')"
            )
    # Keys are stringified: an unquoted YAML `200:` parses to int, and an int
    # key would fail `Endpoint.response` model construction.
    if version == "openapi":
        return {
            str(code): ((resp or {}).get("content") or {}).get("application/json", {}).get("schema") or {}
            for code, resp in responses.items()
        }
    return {str(code): (resp or {}).get("schema") or {} for code, resp in responses.items()}


def _extract_params(
    all_params: list[dict[str, Any]],
    version: str,
    location: Literal["query", "path"],
) -> dict[str, Any]:
    """Extract parameter schemas for one ``in`` location in a format-aware way.

    Args:
        all_params: merged path-item + operation parameters.
        version: the detected spec version (``"openapi"`` or ``"swagger"``).
        location: the parameter location to extract (``"query"`` or ``"path"``).

    Returns:
        ``{param_name: schema}`` for each named parameter at ``location``.
    """
    result: dict[str, Any] = {}
    for param in all_params:
        if not isinstance(param, dict):
            # Skip malformed entries (e.g. null) — mirrors the path-item guard
            continue
        if param.get("in") != location:
            continue
        name = param.get("name")
        if not name:
            # Skip parameters without names (malformed spec)
            continue
        if version == "openapi":
            result[name] = param.get("schema") or {}
        else:  # swagger — inlined type fields
            result[name] = {k: v for k, v in param.items() if k in _TYPE_FIELDS}
    return result


def _normalize_nullable(node: Any) -> Any:
    """Rewrite OpenAPI/Swagger nullability into JSON-Schema union types.

    The ``jsonschema`` validator ignores ``nullable``/``x-nullable``, hence the rewrite.

    Args:
        node: a resolved schema fragment (dict / list / scalar).

    Returns:
        A normalized copy where nullability is expressed as a union type.
    """
    if isinstance(node, dict):
        result = {}
        for key, value in node.items():
            if key in _PROPERTY_MAP_KEYS and isinstance(value, dict):
                # `properties`/`patternProperties` hold {name: schema} maps, not
                # schemas; recurse per property so a property named "nullable" survives.
                result[key] = {name: _normalize_nullable(schema) for name, schema in value.items()}
            else:
                result[key] = _normalize_nullable(value)

        # Both keys are dropped unconditionally; the union forms only when either is ``True``.
        nullable_val = result.pop("nullable", None)
        x_nullable_val = result.pop("x-nullable", None)
        if nullable_val is True or x_nullable_val is True:
            existing = result.get("type")
            if isinstance(existing, str):
                result["type"] = [existing, "null"]
            elif isinstance(existing, list):
                if "null" not in existing:
                    result["type"] = [*existing, "null"]
            else:
                branches = result.get("anyOf")
                if isinstance(branches, list):
                    result["anyOf"] = [*branches, {"type": "null"}]
                else:
                    result["anyOf"] = [{"type": "null"}]
        return result

    if isinstance(node, list):
        return [_normalize_nullable(item) for item in node]

    return node


def extract_endpoints(spec: dict[str, Any]) -> list[Endpoint]:
    """Extract endpoint information from an OpenAPI or Swagger spec dictionary.

    Declared path variables are never cross-validated against the path's ``{name}`` segments.

    Args:
        spec: Parsed OpenAPI/Swagger spec dict with resolved $ref (from swax).

    Returns:
        List of Endpoint objects, one per operation found in the spec.
        Returns an empty list if the spec has no "paths" key.

    Raises:
        ValueError: if the spec declares neither a ``swagger`` nor an ``openapi``
            version (propagated from :func:`detect_spec_version`).

    Examples:
        >>> spec = {"openapi": "3.0.0", "paths": {"/clients/{id}": {"get": {}}}}
        >>> endpoints = extract_endpoints(spec)
        >>> len(endpoints)
        1
    """
    version = detect_spec_version(spec)
    result: list[Endpoint] = []

    paths = spec.get("paths", {})

    for path, path_item in paths.items():
        # Skip malformed path-items (e.g. null) — no operations to extract
        if not isinstance(path_item, dict):
            continue

        # Shared path-item parameters, inherited by all operations.
        # `parameters:` with no value parses to None — treat as no params.
        shared_params = path_item.get("parameters") or []

        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if operation is None:
                continue

            # Merge shared params with operation params
            all_params = [*shared_params, *(operation.get("parameters") or [])]

            # Route field extraction by the detected version.
            request = _normalize_nullable(_extract_request(operation, version))
            response = {
                code: _normalize_nullable(schema) for code, schema in _extract_responses(operation, version).items()
            }
            query_params = {
                name: _normalize_nullable(schema)
                for name, schema in _extract_params(all_params, version, "query").items()
            }
            path_params = {
                name: _normalize_nullable(schema)
                for name, schema in _extract_params(all_params, version, "path").items()
            }

            description = operation.get("description", "")

            endpoint = Endpoint(
                method=method,
                path=path,
                request=request,
                response=response,
                query_params=query_params,
                path_params=path_params,
                description=description,
            )
            result.append(endpoint)

    return result
