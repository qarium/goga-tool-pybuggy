"""Extract endpoints from OpenAPI/Swagger specs."""

from typing import Any

from .endpoint import Endpoint

HTTP_METHODS = ("get", "post", "put", "delete", "patch", "options", "head")

# Whitelist of inlined type fields used to filter Swagger 2.0 query params.
# `x-nullable` is intentionally included so the Swagger nullable keyword reaches
# `_normalize_nullable`; without it the keyword is dropped before normalization
# and the query param's nullability is silently lost (review fix).
_TYPE_FIELDS = (
    "type",
    "format",
    "items",
    "enum",
    "default",
    "description",
    "x-nullable",
)

# JSON-Schema keywords whose value is a {property-name: schema} map rather than a
# schema fragment. When recursing, ``_normalize_nullable`` treats these as
# containers, not schemas — so a property literally named ``nullable`` /
# ``x-nullable`` is not mistaken for the nullability keyword and dropped.
_PROPERTY_MAP_KEYS = ("properties", "patternProperties")


def detect_spec_version(spec: dict[str, Any]) -> str:
    """Classify a parsed spec by its content as ``"swagger"`` or ``"openapi"``.

    The format is determined from the spec's **content** — the presence of a
    top-level ``swagger`` key (Swagger 2.0) or ``openapi`` key (OpenAPI 3.x) —
    independently of any declarative config type field. A spec declaring neither
    top-level key contradicts both specifications and is invalid.

    Pure function — no I/O, no parsing.

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

    OpenAPI 3.x reads the schema from ``requestBody.content.application/json``;
    Swagger 2.0 reads it from the ``in: body`` parameter's root ``schema``.

    Args:
        operation: a single operation dict (``paths[path][method]``).
        version: the detected spec version (``"openapi"`` or ``"swagger"``).

    Returns:
        The resolved request schema, or ``{}`` when absent or explicitly null
        (a ``schema: null`` fragment has no usable schema and degrades to ``{}``).
    """
    if version == "openapi":
        return (
            operation.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema") or {}
        )
    for param in operation.get("parameters", []):
        if param.get("in") == "body":
            return param.get("schema") or {}
    return {}


def _extract_responses(operation: dict[str, Any], version: str) -> dict[str, Any]:
    """Extract response schemas from an operation in a format-aware way.

    OpenAPI 3.x unwraps ``content.application/json.schema``; Swagger 2.0 reads
    ``schema`` directly (no ``content`` wrapper).

    Args:
        operation: a single operation dict (``paths[path][method]``).
        version: the detected spec version (``"openapi"`` or ``"swagger"``).

    Returns:
        ``{status_code: schema}`` for each declared response.
    """
    responses = operation.get("responses", {})
    if version == "openapi":
        return {
            code: resp.get("content", {}).get("application/json", {}).get("schema") or {}
            for code, resp in responses.items()
        }
    return {code: resp.get("schema") or {} for code, resp in responses.items()}


def _extract_query_params(
    all_params: list[dict[str, Any]], version: str
) -> dict[str, Any]:
    """Extract query-parameter schemas in a format-aware way.

    OpenAPI 3.x reads each query param's nested ``schema``; Swagger 2.0 reads the
    inlined type fields, filtered by ``_TYPE_FIELDS`` (which keeps
    ``x-nullable`` so it reaches ``_normalize_nullable``).

    Args:
        all_params: merged path-item + operation parameters.
        version: the detected spec version (``"openapi"`` or ``"swagger"``).

    Returns:
        ``{param_name: schema}`` for each named query parameter.
    """
    result: dict[str, Any] = {}
    for param in all_params:
        if param.get("in") != "query":
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

    ``nullable`` (OpenAPI 3.0) and ``x-nullable`` (Swagger 2.0) are extensions,
    not part of JSON Schema; the ``jsonschema`` validator used at runtime ignores
    both, so a schema fragment with ``{"type": "object", "nullable": true}``
    rejects a ``null`` value. This rewrites every nullable fragment to the
    JSON-Schema equivalent — ``{"type": [<types...>, "null"]}`` — and drops the
    originating key, recursing through ``properties``, ``items``,
    ``additionalProperties`` and the ``anyOf``/``oneOf``/``allOf`` composition
    arrays. Non-container fragments are returned unchanged.

    Applied at the spec → internal JSON-Schema boundary so every consumer of
    ``Endpoint`` (generate, info, list, …) sees one consistent schema shape.

    Args:
        node: a resolved schema fragment (dict / list / scalar).

    Returns:
        A normalized copy where nullability is expressed as a union type.
    """
    if isinstance(node, dict):
        result = {}
        for key, value in node.items():
            if key in _PROPERTY_MAP_KEYS and isinstance(value, dict):
                # `properties`/`patternProperties` map property names to their
                # schemas; the container is NOT itself a schema fragment. Recurse
                # into each property's schema without popping on the container, so
                # a property literally named "nullable"/"x-nullable" survives.
                result[key] = {
                    name: _normalize_nullable(schema) for name, schema in value.items()
                }
            else:
                result[key] = _normalize_nullable(value)

        # Both originating keys are dropped unconditionally; the union is formed
        # when either is literally ``True``. A `false` value drops the key
        # without forming a union.
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

    Detects the spec format via :func:`detect_spec_version` and routes field
    extraction accordingly, then normalizes every extracted schema to the
    JSON-Schema union nullable form. Iterates ``spec["paths"]``, extracting
    operations for each HTTP method; path-item parameters are inherited by all
    operations.

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

        # Get shared parameters from path-item (inherited by all operations)
        shared_params = path_item.get("parameters", [])

        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if operation is None:
                continue

            # Merge shared params with operation params
            all_params = [*shared_params, *operation.get("parameters", [])]

            # Route field extraction by the detected version, then normalize
            request = _normalize_nullable(_extract_request(operation, version))
            response = {
                code: _normalize_nullable(schema)
                for code, schema in _extract_responses(operation, version).items()
            }
            query_params = {
                name: _normalize_nullable(schema)
                for name, schema in _extract_query_params(all_params, version).items()
            }

            description = operation.get("description", "")

            endpoint = Endpoint(
                method=method,
                path=path,
                request=request,
                response=response,
                query_params=query_params,
                description=description,
            )
            result.append(endpoint)

    return result
