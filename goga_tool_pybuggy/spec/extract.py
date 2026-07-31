"""Extract endpoints from OpenAPI spec."""

from typing import Any

from .endpoint import Endpoint

HTTP_METHODS = ("get", "post", "put", "delete", "patch", "options", "head")


def extract_endpoints(spec: dict[str, Any]) -> list[Endpoint]:
    """Extract endpoint information from an OpenAPI spec dictionary.

    Iterates through spec["paths"], extracting operations for each HTTP method.
    Path-item parameters are inherited by all operations.

    Args:
        spec: Parsed OpenAPI spec dict with resolved $ref (from swax).

    Returns:
        List of Endpoint objects, one per operation found in the spec.
        Returns empty list if spec has no "paths" key.

    Examples:
        >>> spec = {"paths": {"/clients/{id}": {"get": {...}}}}
        >>> endpoints = extract_endpoints(spec)
        >>> len(endpoints)
        1
    """
    result: list[Endpoint] = []

    # Step 1: Read spec["paths"]
    paths = spec.get("paths", {})

    # Step 2: For each path-item, for each HTTP method
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

            # Step 3: Build an Endpoint from the operation

            # Merge shared params with operation params
            all_params = [*shared_params, *operation.get("parameters", [])]

            # Extract request schema (primary JSON content)
            request_body = operation.get("requestBody", {})
            request_content = request_body.get("content", {})
            json_content = request_content.get("application/json", {})
            request = json_content.get("schema", {})

            # Extract response schemas
            responses = operation.get("responses", {})
            response: dict[str, Any] = {}
            for code, resp in responses.items():
                resp_content = resp.get("content", {})
                json_content = resp_content.get("application/json", {})
                response[code] = json_content.get("schema", {})

            # Extract query parameters
            query_params: dict[str, Any] = {}
            for param in all_params:
                if param.get("in") == "query":
                    name = param.get("name")
                    if not name:
                        # Skip parameters without names (malformed spec)
                        continue
                    schema = param.get("schema", {})
                    query_params[name] = schema

            # Extract description
            description = operation.get("description", "")

            # Build Endpoint with kw_only fields
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
