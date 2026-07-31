"""Contract and logic tests for extract_endpoints routine."""

from pybuggy.spec import Endpoint, build_endpoint_id, extract_endpoints


def test_extract_endpoints_import_from_facade() -> None:
    """Test that extract_endpoints is importable from pybuggy.spec facade."""
    from pybuggy.spec import extract_endpoints as extract_endpoints_facade

    assert extract_endpoints_facade is extract_endpoints


def test_extract_endpoints_signature() -> None:
    """Test extract_endpoints has correct signature: (spec: dict[str, Any]) -> list[Endpoint]."""
    import inspect

    sig = inspect.signature(extract_endpoints)
    params = list(sig.parameters.keys())

    assert len(params) == 1, f"Expected 1 parameter, got {len(params)}"
    assert params[0] == "spec", f"Expected parameter 'spec', got '{params[0]}'"
    assert sig.return_annotation == list[Endpoint] or str(sig.return_annotation) in (
        "list[pybuggy.spec.Endpoint.Endpoint]",
        "list[__main__.Endpoint]",
    ), f"Expected return annotation list[Endpoint], got {sig.return_annotation}"


def test_extract_endpoints_builds_endpoint_per_operation() -> None:
    """Test extract_endpoints builds endpoint per operation with correct field extraction."""
    spec = {
        "paths": {
            "/clients/{id}": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object", "properties": {"id": {"type": "string"}}}
                                }
                            }
                        }
                    },
                    "parameters": [{"name": "verbose", "in": "query", "schema": {"type": "boolean"}}],
                }
            }
        }
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    endpoint = endpoints[0]

    # Check query_params from operation-level parameters
    assert "verbose" in endpoint.query_params
    assert endpoint.query_params["verbose"]["type"] == "boolean"

    # Check computed id
    expected_id = build_endpoint_id("get", "/clients/{id}")
    assert endpoint.id == expected_id


def test_extract_endpoints_skips_non_method_keys() -> None:
    """Test extract_endpoints skips non-method keys like 'parameters' and 'summary'."""
    spec = {
        "paths": {
            "/items": {
                "summary": "Items endpoint",
                "parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer"}}],
                "get": {"responses": {"200": {"content": {"application/json": {"schema": {}}}}}},
            }
        }
    }

    endpoints = extract_endpoints(spec)

    # Only the GET operation should be extracted, not 'summary' or 'parameters'
    assert len(endpoints) == 1
    assert endpoints[0].method == "get"
    assert endpoints[0].path == "/items"


def test_extract_endpoints_empty_paths_returns_empty_list() -> None:
    """Test extract_endpoints returns empty list when spec has no 'paths' key."""
    spec = {"openapi": "3.0.0", "info": {"title": "Test", "version": "1.0"}}
    endpoints = extract_endpoints(spec)
    assert endpoints == []


def test_extract_endpoints_skips_non_dict_path_item() -> None:
    """Test extract_endpoints skips malformed (non-dict/null) path-items without crashing."""
    spec = {
        "paths": {
            "/null": None,
            "/valid": {"get": {"responses": {"200": {"content": {"application/json": {"schema": {}}}}}}},
        }
    }

    endpoints = extract_endpoints(spec)

    # Only the well-formed /valid path-item yields an endpoint
    assert len(endpoints) == 1
    assert endpoints[0].path == "/valid"


def test_extract_endpoints_no_application_json_returns_empty_fields() -> None:
    """Test extract_endpoints returns empty schemas when no application/json content."""
    spec = {
        "paths": {
            "/data": {
                "post": {
                    "requestBody": {"content": {"text/plain": {"schema": {"type": "string"}}}},
                    "responses": {"200": {"content": {"text/plain": {"schema": {}}}}},
                }
            }
        }
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    assert endpoints[0].request == {}
    assert endpoints[0].response == {"200": {}}


def test_extract_endpoints_inherits_shared_path_item_parameters() -> None:
    """Test extract_endpoints inherits shared parameters from path-item level."""
    spec = {
        "paths": {
            "/clients/{id}": {
                "parameters": [{"name": "shared_param", "in": "query", "schema": {"type": "string"}}],
                "get": {
                    "parameters": [{"name": "op_param", "in": "query", "schema": {"type": "integer"}}],
                    "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                },
            }
        }
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    # Both shared and operation-level parameters should be present
    assert "shared_param" in endpoints[0].query_params
    assert "op_param" in endpoints[0].query_params
    assert endpoints[0].query_params["shared_param"]["type"] == "string"
    assert endpoints[0].query_params["op_param"]["type"] == "integer"


def test_extract_endpoints_description_default_empty_string() -> None:
    """Test extract_endpoints uses empty string when description is missing."""
    spec = {
        "paths": {"/nodescription": {"get": {"responses": {"200": {"content": {"application/json": {"schema": {}}}}}}}}
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    assert endpoints[0].description == ""


def test_extract_endpoints_with_description() -> None:
    """Test extract_endpoints extracts description when present."""
    spec = {
        "paths": {
            "/withdesc": {
                "get": {
                    "description": "This is a test endpoint",
                    "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                }
            }
        }
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    assert endpoints[0].description == "This is a test endpoint"
