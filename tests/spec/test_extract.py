"""Contract and logic tests for extract_endpoints routine."""

import pytest
from goga_tool_pybuggy import spec as spec_module
from goga_tool_pybuggy.spec import (
    Endpoint,
    build_endpoint_id,
    detect_spec_version,
    extract_endpoints,
)


def test_detect_spec_version_import_from_facade() -> None:
    """Test detect_spec_version is re-exported from the spec facade."""
    from goga_tool_pybuggy.spec import detect_spec_version as facade
    from goga_tool_pybuggy.spec.extract import detect_spec_version as source_routine

    # The facade symbol must be the exact routine defined in extract.py
    # (compared against the source module's object, not a second facade binding).
    assert facade is source_routine

    # Re-export obligation: declared in the facade __all__.
    assert "detect_spec_version" in spec_module.__all__


def test_detect_spec_version_signature() -> None:
    """Test detect_spec_version has signature (spec: dict[str, Any]) -> str."""
    import inspect

    sig = inspect.signature(detect_spec_version)
    params = list(sig.parameters.keys())

    assert params == ["spec"], f"Expected single parameter 'spec', got {params}"
    assert sig.return_annotation is str, f"Expected return annotation str, got {sig.return_annotation}"


def test_detect_spec_version_swagger() -> None:
    """Test detect_spec_version returns 'swagger' for a Swagger 2.0 spec."""
    assert detect_spec_version({"swagger": "2.0", "paths": {}}) == "swagger"


def test_detect_spec_version_openapi() -> None:
    """Test detect_spec_version returns 'openapi' for an OpenAPI 3.x spec."""
    assert detect_spec_version({"openapi": "3.1.0", "paths": {}}) == "openapi"


def test_detect_spec_version_both_keys_swagger_wins() -> None:
    """Test a malformed spec carrying both keys resolves to 'swagger' (checked first)."""
    assert detect_spec_version({"swagger": "2.0", "openapi": "3.0.0"}) == "swagger"


def test_detect_spec_version_neither_key_raises_value_error() -> None:
    """Test detect_spec_version raises ValueError when neither version key is present."""
    # A spec with content but no version key is invalid.
    with pytest.raises(ValueError, match="declares neither"):
        detect_spec_version({"info": {"title": "T"}, "paths": {}})

    # An empty dict is likewise invalid.
    with pytest.raises(ValueError, match="declares neither"):
        detect_spec_version({})


def test_extract_endpoints_import_from_facade() -> None:
    """Test that extract_endpoints is importable from goga_tool_pybuggy.spec facade."""
    from goga_tool_pybuggy.spec import extract_endpoints as extract_endpoints_facade

    assert extract_endpoints_facade is extract_endpoints


def test_extract_endpoints_signature() -> None:
    """Test extract_endpoints has correct signature: (spec: dict[str, Any]) -> list[Endpoint]."""
    import inspect

    sig = inspect.signature(extract_endpoints)
    params = list(sig.parameters.keys())

    assert len(params) == 1, f"Expected 1 parameter, got {len(params)}"
    assert params[0] == "spec", f"Expected parameter 'spec', got '{params[0]}'"
    assert sig.return_annotation == list[Endpoint] or str(sig.return_annotation) in (
        "list[goga_tool_pybuggy.spec.Endpoint.Endpoint]",
        "list[__main__.Endpoint]",
    ), f"Expected return annotation list[Endpoint], got {sig.return_annotation}"


def test_extract_endpoints_builds_endpoint_per_operation() -> None:
    """Test extract_endpoints builds endpoint per operation with correct field extraction."""
    spec = {
        "openapi": "3.0.0",
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
        },
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
        "openapi": "3.0.0",
        "paths": {
            "/items": {
                "summary": "Items endpoint",
                "parameters": [{"name": "limit", "in": "query", "schema": {"type": "integer"}}],
                "get": {"responses": {"200": {"content": {"application/json": {"schema": {}}}}}},
            }
        },
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
        "openapi": "3.0.0",
        "paths": {
            "/null": None,
            "/valid": {"get": {"responses": {"200": {"content": {"application/json": {"schema": {}}}}}}},
        },
    }

    endpoints = extract_endpoints(spec)

    # Only the well-formed /valid path-item yields an endpoint
    assert len(endpoints) == 1
    assert endpoints[0].path == "/valid"


def test_extract_endpoints_no_application_json_returns_empty_fields() -> None:
    """Test extract_endpoints returns empty schemas when no application/json content."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/data": {
                "post": {
                    "requestBody": {"content": {"text/plain": {"schema": {"type": "string"}}}},
                    "responses": {"200": {"content": {"text/plain": {"schema": {}}}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    assert endpoints[0].request == {}
    assert endpoints[0].response == {"200": {}}


def test_extract_endpoints_inherits_shared_path_item_parameters() -> None:
    """Test extract_endpoints inherits shared parameters from path-item level."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/clients/{id}": {
                "parameters": [{"name": "shared_param", "in": "query", "schema": {"type": "string"}}],
                "get": {
                    "parameters": [{"name": "op_param", "in": "query", "schema": {"type": "integer"}}],
                    "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                },
            }
        },
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
        "openapi": "3.0.0",
        "paths": {"/nodescription": {"get": {"responses": {"200": {"content": {"application/json": {"schema": {}}}}}}}},
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    assert endpoints[0].description == ""


def test_extract_endpoints_with_description() -> None:
    """Test extract_endpoints extracts description when present."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/withdesc": {
                "get": {
                    "description": "This is a test endpoint",
                    "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    assert endpoints[0].description == "This is a test endpoint"


def test_extract_endpoints_rewrites_openapi_nullable_to_jsonschema_union() -> None:
    """Test extract_endpoints rewrites OpenAPI 3.0 nullable: true into JSON-Schema union types.

    Nullability is normalized at the OpenAPI → JSON-Schema boundary so every command
    (generate, info, …) sees one consistent shape — the jsonschema validator used at
    runtime ignores the OpenAPI ``nullable`` keyword. Each nullable fragment becomes
    ``type: [<types...>, "null"]`` with ``nullable`` dropped, recursing into nested
    request/response/query schemas (incl. array items).
    """
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/nullable": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"ref": {"type": "string", "nullable": True}},
                                }
                            }
                        }
                    },
                    "parameters": [{"name": "tag", "in": "query", "schema": {"type": "integer", "nullable": True}}],
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "data": {
                                                "type": "array",
                                                "items": {"type": "object", "nullable": True},
                                            },
                                            "error": {"type": "object", "nullable": True},
                                        },
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    endpoint = endpoints[0]

    # request: nullable string → union, no nullable key
    assert endpoint.request == {
        "type": "object",
        "properties": {"ref": {"type": ["string", "null"]}},
    }

    # query param: nullable integer → union
    assert endpoint.query_params["tag"] == {"type": ["integer", "null"]}

    # response: nested nullable (array items + property) normalized recursively
    assert endpoint.response["200"] == {
        "type": "object",
        "properties": {
            "data": {"type": "array", "items": {"type": ["object", "null"]}},
            "error": {"type": ["object", "null"]},
        },
    }


def test_extract_endpoints_normalizes_nullable_without_type_via_anyof() -> None:
    """Test extract_endpoints normalizes a nullable schema that has no ``type``.

    When ``nullable: true`` appears on a fragment without a ``type`` (a valid
    OpenAPI 3.0 form, e.g. a schema built purely from composition), the normalizer
    cannot form a ``type`` union and falls back to expressing nullability as an
    ``anyOf`` branch. This covers both fallback sub-cases: an existing ``anyOf``
    (appends ``{"type": "null"}``) and a bare nullable (synthesizes
    ``[{"type": "null"}]``).
    """
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/nullable-anyof": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                # bare nullable, no type, no anyOf
                                "schema": {"nullable": True}
                            }
                        }
                    },
                    "parameters": [
                        {
                            "name": "filter",
                            "in": "query",
                            # nullable, no type, existing anyOf
                            "schema": {"nullable": True, "anyOf": [{"type": "object"}]},
                        }
                    ],
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            # nullable nested, no type, existing anyOf
                                            "meta": {"nullable": True, "anyOf": [{"type": "string"}]},
                                        },
                                    }
                                }
                            }
                        }
                    },
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    endpoint = endpoints[0]

    # bare nullable (no type, no anyOf) -> synthesized single-null anyOf
    assert endpoint.request == {"anyOf": [{"type": "null"}]}

    # query param: nullable without type + existing anyOf -> null branch appended
    assert endpoint.query_params["filter"] == {
        "anyOf": [{"type": "object"}, {"type": "null"}],
    }

    # response: nullable nested property without type -> anyOf fallback recurses
    assert endpoint.response["200"] == {
        "type": "object",
        "properties": {
            "meta": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        },
    }


def test_extract_endpoints_nullable_dedup_when_type_list_already_has_null() -> None:
    """A nullable fragment whose ``type`` is already a list including ``"null"`` is not duplicated."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/dedup": {
                "post": {
                    "requestBody": {
                        "content": {"application/json": {"schema": {"type": ["string", "null"], "nullable": True}}}
                    },
                    "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    # The existing "null" must not be appended a second time.
    assert endpoints[0].request == {"type": ["string", "null"]}


def test_extract_endpoints_nullable_recurses_into_composition_and_additional_properties() -> None:
    """Nullable normalization recurses into ``additionalProperties`` and ``oneOf``/``allOf`` arrays."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/recurse": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "additionalProperties": {"type": "string", "nullable": True},
                                    "oneOf": [{"type": "integer", "nullable": True}],
                                    "allOf": [{"type": "object", "nullable": True}],
                                }
                            }
                        }
                    },
                    "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].request == {
        "additionalProperties": {"type": ["string", "null"]},
        "oneOf": [{"type": ["integer", "null"]}],
        "allOf": [{"type": ["object", "null"]}],
    }


# --- Swagger 2.0 support (Task 2) --------------------------------------------


def test_extract_endpoints_swagger_body_request() -> None:
    """Test Swagger 2.0 POST: body schema → request, responses[code].schema → response, inlined query."""
    spec = {
        "swagger": "2.0",
        "paths": {
            "/clients": {
                "post": {
                    "parameters": [
                        {"name": "limit", "in": "query", "type": "integer"},
                        {
                            "name": "body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                            },
                        },
                    ],
                    "responses": {"201": {"description": "created", "schema": {"type": "object"}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    ep = endpoints[0]

    assert ep.request == {"type": "object", "properties": {"name": {"type": "string"}}}
    assert ep.response == {"201": {"type": "object"}}
    assert ep.query_params == {"limit": {"type": "integer"}}
    assert ep.id == build_endpoint_id("post", "/clients")


def test_extract_endpoints_swagger_query_inlined_fields() -> None:
    """Test Swagger query params keep only the canonical _TYPE_FIELDS (drop required/extra)."""
    spec = {
        "swagger": "2.0",
        "paths": {
            "/things": {
                "get": {
                    "parameters": [
                        {
                            "name": "color",
                            "in": "query",
                            "type": "string",
                            "format": "hex",
                            "enum": ["red", "green"],
                            "default": "red",
                            "description": "pick a color",
                            "required": True,
                            "collectionFormat": "multi",
                        }
                    ],
                    "responses": {"200": {"description": "ok", "schema": {}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    ep = endpoints[0]

    assert ep.query_params["color"] == {
        "type": "string",
        "format": "hex",
        "enum": ["red", "green"],
        "default": "red",
        "description": "pick a color",
    }


def test_extract_endpoints_rewrites_swagger_x_nullable_to_jsonschema_union() -> None:
    """Test Swagger x-nullable: true is normalized to a JSON-Schema union (review-fix regression).

    ``x-nullable`` must survive ``_TYPE_FIELDS`` filtering on the Swagger query
    param and reach ``_normalize_nullable`` on every extracted schema, becoming a
    ``type`` union including ``"null"`` with the originating key dropped.
    """
    spec = {
        "swagger": "2.0",
        "paths": {
            "/xnullable": {
                "post": {
                    "parameters": [
                        {"name": "tag", "in": "query", "type": "integer", "x-nullable": True},
                        {
                            "name": "body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {"ref": {"type": "string", "x-nullable": True}},
                            },
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "schema": {
                                "type": "object",
                                "properties": {"err": {"type": "object", "x-nullable": True}},
                            },
                        }
                    },
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    ep = endpoints[0]

    assert ep.request == {
        "type": "object",
        "properties": {"ref": {"type": ["string", "null"]}},
    }
    assert ep.query_params["tag"] == {"type": ["integer", "null"]}
    assert ep.response["200"] == {
        "type": "object",
        "properties": {"err": {"type": ["object", "null"]}},
    }


def test_extract_endpoints_nullable_false_drops_key_without_union() -> None:
    """Test nullable:false / x-nullable:false drops the key without forming a union."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/nf": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "a": {"type": "string", "nullable": False},
                                        "b": {"type": "integer", "x-nullable": False},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    ep = endpoints[0]

    assert ep.request == {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
    }
    assert "nullable" not in ep.request["properties"]["a"]
    assert "x-nullable" not in ep.request["properties"]["b"]


def test_extract_endpoints_swagger_no_body_parameter_request_empty() -> None:
    """Test Swagger POST with no in: body param yields an empty request and empty response schema."""
    spec = {
        "swagger": "2.0",
        "paths": {
            "/nobody": {
                "post": {
                    "parameters": [{"name": "limit", "in": "query", "type": "integer"}],
                    "responses": {"201": {"description": "created"}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    ep = endpoints[0]

    assert ep.request == {}
    assert ep.response == {"201": {}}


def test_extract_endpoints_swagger_inherits_shared_path_item_parameters() -> None:
    """Test Swagger inherits shared path-item query params alongside operation-level ones."""
    spec = {
        "swagger": "2.0",
        "paths": {
            "/things/{id}": {
                "parameters": [{"name": "shared", "in": "query", "type": "string"}],
                "get": {
                    "parameters": [{"name": "op", "in": "query", "type": "integer"}],
                    "responses": {"200": {"description": "ok", "schema": {}}},
                },
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert len(endpoints) == 1
    ep = endpoints[0]

    assert ep.query_params == {"shared": {"type": "string"}, "op": {"type": "integer"}}


# --- URL path variables: path_params extraction (Task 2) ----------------------


def test_extract_endpoints_path_params_equivalent_across_formats() -> None:
    """Equivalent Swagger 2.0 and OpenAPI 3.x operations yield the same path_params.

    The format-equivalence contract invariant extended to the new field: both
    dialects declare the same ``GET /orders/{id}`` with a path ``id`` (string)
    and a query ``verbose`` (boolean); extraction routes by the detected version
    (nested ``schema`` for OpenAPI, ``_TYPE_FIELDS``-filtered inlined fields for
    Swagger) yet reduces to the same normalized shape on ``Endpoint``.
    """
    swagger_spec = {
        "swagger": "2.0",
        "paths": {
            "/orders/{id}": {
                "get": {
                    "parameters": [
                        {"name": "id", "in": "path", "type": "string"},
                        {"name": "verbose", "in": "query", "type": "boolean"},
                    ],
                    "responses": {"200": {"description": "ok", "schema": {}}},
                }
            }
        },
    }
    openapi_spec = {
        "openapi": "3.0.0",
        "paths": {
            "/orders/{id}": {
                "get": {
                    "parameters": [
                        {"name": "id", "in": "path", "schema": {"type": "string"}},
                        {"name": "verbose", "in": "query", "schema": {"type": "boolean"}},
                    ],
                    "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                }
            }
        },
    }

    sw = extract_endpoints(swagger_spec)
    oa = extract_endpoints(openapi_spec)

    assert len(sw) == len(oa) == 1
    assert sw[0].path_params == oa[0].path_params == {"id": {"type": "string"}}
    assert sw[0].query_params == oa[0].query_params == {"verbose": {"type": "boolean"}}
    assert sw[0].id == oa[0].id == build_endpoint_id("get", "/orders/{id}")


def test_extract_endpoints_openapi_path_params_nested_schema() -> None:
    """OpenAPI path variables come from the nested ``schema``; locations never mix."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/clients/{id}": {
                "get": {
                    "parameters": [
                        {"name": "id", "in": "path", "schema": {"type": "string"}},
                        {"name": "verbose", "in": "query", "schema": {"type": "boolean"}},
                    ],
                    "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].path_params == {"id": {"type": "string"}}
    assert endpoints[0].query_params == {"verbose": {"type": "boolean"}}


def test_extract_endpoints_swagger_path_params_inlined_fields() -> None:
    """Swagger path variables keep only the canonical ``_TYPE_FIELDS`` (drop required)."""
    spec = {
        "swagger": "2.0",
        "paths": {
            "/things/{id}": {
                "get": {
                    "parameters": [
                        {"name": "id", "in": "path", "type": "string", "required": True, "description": "record id"}
                    ],
                    "responses": {"200": {"description": "ok", "schema": {}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].path_params == {"id": {"type": "string", "description": "record id"}}
    assert "required" not in endpoints[0].path_params["id"]


def test_extract_endpoints_skips_path_param_without_name() -> None:
    """Path parameters missing a (non-empty) ``name`` are skipped, not keyed under a falsy value."""
    spec = {
        "swagger": "2.0",
        "paths": {
            "/x": {
                "get": {
                    "parameters": [
                        {"in": "path", "type": "string"},
                        {"name": "id", "in": "path", "type": "string"},
                    ],
                    "responses": {"200": {"description": "ok", "schema": {}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].path_params == {"id": {"type": "string"}}


def test_extract_endpoints_skips_non_dict_param_entries() -> None:
    """Malformed non-dict parameter entries (e.g. null) are skipped, not AttributeError."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/x": {
                "get": {
                    "parameters": [
                        None,
                        {"name": "id", "in": "path", "schema": {"type": "string"}},
                    ],
                    "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].path_params == {"id": {"type": "string"}}


def test_extract_endpoints_skips_non_dict_body_param_entries_swagger() -> None:
    """Malformed non-dict entries in a Swagger body-parameter list are skipped too.

    ``_extract_request`` walks the same ``parameters`` list as ``_extract_params``;
    a null entry must not raise AttributeError there either.
    """
    spec = {
        "swagger": "2.0",
        "paths": {
            "/x": {
                "post": {
                    "parameters": [
                        None,
                        {"name": "payload", "in": "body", "schema": {"type": "object"}},
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].request == {"type": "object"}


def test_extract_endpoints_path_item_path_params_inherited_by_operations() -> None:
    """A path-level ``in: path`` parameter is inherited by every operation of the path-item."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/orders/{id}": {
                "parameters": [{"name": "id", "in": "path", "schema": {"type": "string"}}],
                "get": {"responses": {"200": {"content": {"application/json": {"schema": {}}}}}},
                "post": {"responses": {"201": {"content": {"application/json": {"schema": {}}}}}},
            }
        },
    }

    endpoints = extract_endpoints(spec)
    eps = {ep.method: ep for ep in endpoints}

    assert set(eps) == {"get", "post"}
    assert eps["get"].path_params == {"id": {"type": "string"}}
    assert eps["post"].path_params == {"id": {"type": "string"}}


def test_extract_endpoints_path_params_no_path_params_yields_empty() -> None:
    """An operation with no ``in: path`` parameters yields an empty ``path_params`` mapping."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/clients/startup": {
                "get": {
                    "parameters": [{"name": "verbose", "in": "query", "schema": {"type": "boolean"}}],
                    "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].path_params == {}
    assert endpoints[0].query_params == {"verbose": {"type": "boolean"}}


@pytest.mark.parametrize(
    "spec",
    [
        {
            "openapi": "3.0.0",
            "paths": {
                "/p/{id}": {
                    "get": {
                        "parameters": [{"name": "id", "in": "path", "schema": {"type": "string", "nullable": True}}],
                        "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                    }
                }
            },
        },
        {
            "swagger": "2.0",
            "paths": {
                "/p/{id}": {
                    "get": {
                        "parameters": [{"name": "id", "in": "path", "type": "string", "x-nullable": True}],
                        "responses": {"200": {"description": "ok", "schema": {}}},
                    }
                }
            },
        },
    ],
    ids=["openapi-nullable", "swagger-x-nullable"],
)
def test_extract_endpoints_path_param_nullable_normalized_both_formats(spec: dict) -> None:
    """Nullable path variables normalize to the JSON-Schema union form in both formats.

    ``nullable`` (OpenAPI) and ``x-nullable`` (Swagger, kept alive by
    ``_TYPE_FIELDS``) both reach ``_normalize_nullable`` on the path location and
    become a ``type`` union including ``"null"`` with the originating key dropped.
    """
    endpoints = extract_endpoints(spec)

    assert endpoints[0].path_params == {"id": {"type": ["string", "null"]}}


def test_extract_endpoints_does_not_validate_path_template() -> None:
    """A declared path variable absent from the path template is still extracted (template trusted)."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/fixed": {
                "get": {
                    "parameters": [{"name": "ghost", "in": "path", "schema": {"type": "string"}}],
                    "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].path_params == {"ghost": {"type": "string"}}


def test_extract_endpoints_openapi_path_param_null_schema_degrades_to_empty() -> None:
    """An OpenAPI path param with an explicit ``schema: null`` degrades to ``{}``.

    ``Endpoint.path_params`` values feed ``json.dumps`` in meta.json; storing
    ``None`` would break serialization, so the null schema coerces to an empty
    mapping exactly like the query location.
    """
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/items/{id}": {
                "get": {
                    "parameters": [{"name": "id", "in": "path", "schema": None}],
                    "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].path_params == {"id": {}}


# --- Integration tests (Task 3): format equivalence + invalid-spec + path-less ---


def test_extract_endpoints_equivalent_operations_same_normalized_shape() -> None:
    """Equivalent Swagger 2.0 and OpenAPI 3.x operations yield the same Endpoint shape.

    The format-equivalence contract invariant: ``extract_endpoints`` routes by the
    detected version, but both formats reduce to the same normalized JSON-Schema
    shape (no nullable here, so normalization is a no-op). One GET + one POST are
    declared on the same path so the result order is fixed by ``HTTP_METHODS``
    (``get`` before ``post``).
    """
    swagger_spec = {
        "swagger": "2.0",
        "paths": {
            "/r/{id}": {
                "get": {
                    "parameters": [{"name": "verbose", "in": "query", "type": "boolean"}],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "schema": {
                                "type": "object",
                                "properties": {"id": {"type": "string"}},
                            },
                        }
                    },
                },
                "post": {
                    "parameters": [
                        {
                            "name": "body",
                            "in": "body",
                            "schema": {
                                "type": "object",
                                "properties": {"name": {"type": "string"}},
                            },
                        }
                    ],
                    "responses": {"201": {"description": "created", "schema": {"type": "object"}}},
                },
            }
        },
    }
    openapi_spec = {
        "openapi": "3.0.0",
        "paths": {
            "/r/{id}": {
                "get": {
                    "parameters": [{"name": "verbose", "in": "query", "schema": {"type": "boolean"}}],
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"id": {"type": "string"}},
                                    }
                                }
                            }
                        }
                    },
                },
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"name": {"type": "string"}},
                                }
                            }
                        }
                    },
                    "responses": {"201": {"content": {"application/json": {"schema": {"type": "object"}}}}},
                },
            }
        },
    }

    sw = extract_endpoints(swagger_spec)
    oa = extract_endpoints(openapi_spec)

    assert len(sw) == len(oa) == 2

    # GET row (index 0): no request body, 200 object-with-id, verbose boolean query.
    assert sw[0].request == oa[0].request == {}
    assert sw[0].response == oa[0].response == {"200": {"type": "object", "properties": {"id": {"type": "string"}}}}
    assert sw[0].query_params == oa[0].query_params == {"verbose": {"type": "boolean"}}

    # POST row (index 1): object-with-name request, 201 object response, no query.
    assert (
        sw[1].request
        == oa[1].request
        == {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
    )
    assert sw[1].response == oa[1].response == {"201": {"type": "object"}}
    assert sw[1].query_params == oa[1].query_params == {}

    # The format-equivalence contract invariant: identical endpoint ids across formats.
    assert [e.id for e in sw] == [e.id for e in oa]


def test_extract_endpoints_invalid_spec_raises_value_error() -> None:
    """extract_endpoints propagates ValueError from detect_spec_version without swallowing.

    A spec with paths but no top-level version key is invalid; the version error
    must surface unchanged (Constraints bullet 3 — no swallowing).
    """
    with pytest.raises(ValueError, match="declares neither"):
        extract_endpoints({"paths": {"/x": {"get": {"responses": {}}}}})


def test_extract_endpoints_swagger_empty_paths_returns_empty_list() -> None:
    """A valid Swagger spec with no paths returns an empty list (no ValueError).

    Path-lessness is ``extract_endpoints``' concern, not the version detector's:
    a Swagger spec with a top-level ``swagger`` key but no ``paths`` detects the
    version normally and yields no endpoints.
    """
    assert extract_endpoints({"swagger": "2.0", "info": {"title": "T", "version": "1"}}) == []


# --- Robustness / additional edge cases (review) -----------------------------


def test_extract_endpoints_explicit_null_schema_degrades_to_empty() -> None:
    """An explicit ``schema: null`` degrades to ``{}`` instead of crashing.

    ``Endpoint.request`` is a non-optional dict, so a null schema must not reach
    it; the same coercion applies to response schemas and OpenAPI query schemas.
    """
    swagger_spec = {
        "swagger": "2.0",
        "paths": {
            "/n": {
                "post": {
                    "parameters": [{"name": "b", "in": "body", "schema": None}],
                    "responses": {"201": {"description": "ok", "schema": None}},
                }
            }
        },
    }
    openapi_spec = {
        "openapi": "3.0.0",
        "paths": {
            "/n": {
                "post": {
                    "requestBody": {"content": {"application/json": {"schema": None}}},
                    "responses": {"201": {"content": {"application/json": {"schema": None}}}},
                }
            }
        },
    }

    for spec in (swagger_spec, openapi_spec):
        endpoints = extract_endpoints(spec)
        assert len(endpoints) == 1
        assert endpoints[0].request == {}
        assert endpoints[0].response == {"201": {}}


def test_extract_endpoints_skips_query_param_without_name() -> None:
    """Query parameters missing a (non-empty) ``name`` are skipped, not keyed under a falsy value."""
    spec = {
        "swagger": "2.0",
        "paths": {
            "/q": {
                "get": {
                    "parameters": [
                        {"in": "query", "type": "string"},  # no name key
                        {"name": "", "in": "query", "type": "integer"},  # empty name
                        {"name": "ok", "in": "query", "type": "boolean"},
                    ],
                    "responses": {"200": {"description": "ok", "schema": {}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].query_params == {"ok": {"type": "boolean"}}


def test_extract_endpoints_operation_param_overrides_shared_same_name() -> None:
    """When path-item and operation share a query-param name, the operation-level schema wins.

    Operation parameters are merged after shared path-item parameters, so the
    last occurrence wins in the resulting dict.
    """
    spec = {
        "swagger": "2.0",
        "paths": {
            "/dup": {
                "parameters": [{"name": "limit", "in": "query", "type": "string"}],
                "get": {
                    "parameters": [{"name": "limit", "in": "query", "type": "integer"}],
                    "responses": {"200": {"description": "ok", "schema": {}}},
                },
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].query_params == {"limit": {"type": "integer"}}


def test_extract_endpoints_openapi_query_null_schema_degrades_to_empty() -> None:
    """An OpenAPI query param with an explicit ``schema: null`` degrades to ``{}``."""
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/q": {
                "get": {
                    "parameters": [{"name": "t", "in": "query", "schema": None}],
                    "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].query_params == {"t": {}}


def test_extract_endpoints_swagger_query_array_items_preserved() -> None:
    """A Swagger array query param keeps its ``items`` element (pinned via _TYPE_FIELDS).

    ``items`` is part of the canonical ``_TYPE_FIELDS`` whitelist. Without a test
    pinning it, a future edit dropping ``items`` would silently strip the item
    schema from every array-typed Swagger query param.
    """
    spec = {
        "swagger": "2.0",
        "paths": {
            "/tags": {
                "get": {
                    "parameters": [{"name": "tags", "in": "query", "type": "array", "items": {"type": "string"}}],
                    "responses": {"200": {"description": "ok", "schema": {}}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].query_params == {"tags": {"type": "array", "items": {"type": "string"}}}


def test_extract_endpoints_swagger_excludes_formdata_and_file_params() -> None:
    """Swagger ``in: formData``/file/body params never reach ``query_params``.

    CODEMANIFEST constraint: "Do not extract formData or file-upload parameters."
    Only ``in: query`` params are extracted; formData (Swagger's POST body vehicle),
    file-upload and body params must be excluded so form fields don't pollute query.
    """
    spec = {
        "swagger": "2.0",
        "paths": {
            "/upload": {
                "post": {
                    "parameters": [
                        {"name": "q", "in": "query", "type": "string"},
                        {"name": "field1", "in": "formData", "type": "string"},
                        {"name": "upload", "in": "formData", "type": "file"},
                        {"name": "body", "in": "body", "schema": {"type": "object"}},
                    ],
                    "responses": {"201": {"description": "created"}},
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)

    # Only the query param is extracted; formData/file/body params are excluded.
    assert endpoints[0].query_params == {"q": {"type": "string"}}


def test_extract_endpoints_swagger_x_nullable_without_type_uses_anyof_fallback() -> None:
    """A type-less Swagger fragment with ``x-nullable: true`` synthesizes an anyOf.

    Mirrors the OpenAPI ``nullable``-without-``type`` fallback on the Swagger entry
    path: when ``x-nullable: true`` reaches ``_normalize_nullable`` on a fragment
    with no ``type``, nullability is expressed as a synthesized ``anyOf`` branch
    (no ``type`` to host the union).
    """
    spec = {
        "swagger": "2.0",
        "paths": {
            "/xn": {
                "get": {
                    "parameters": [
                        # type-less query param carrying x-nullable (Swagger inlines fields)
                        {"name": "tag", "in": "query", "x-nullable": True}
                    ],
                    "responses": {
                        "200": {
                            "description": "ok",
                            "schema": {
                                "type": "object",
                                "properties": {"err": {"x-nullable": True}},
                            },
                        }
                    },
                }
            }
        },
    }

    endpoints = extract_endpoints(spec)
    ep = endpoints[0]

    assert ep.query_params["tag"] == {"anyOf": [{"type": "null"}]}
    assert ep.response["200"] == {
        "type": "object",
        "properties": {"err": {"anyOf": [{"type": "null"}]}},
    }


def test_extract_endpoints_preserves_property_named_nullable() -> None:
    """A property literally named ``nullable``/``x-nullable`` is not dropped.

    Regression: ``_normalize_nullable`` pops the ``nullable``/``x-nullable``
    keys from every dict it visits. A JSON-Schema ``properties`` map is keyed by
    property *name*, not by keyword, so a property literally named
    ``nullable``/``x-nullable`` was mistaken for the nullability keyword and
    silently deleted (data corruption). The fix treats ``properties``/
    ``patternProperties`` as containers and recurses into each property's schema
    without popping on the container. This pins the fix end-to-end for both
    formats and for boolean-schema properties.
    """
    spec = {
        "swagger": "2.0",
        "paths": {
            "/meta": {
                "post": {
                    "parameters": [
                        {
                            "in": "body",
                            "name": "body",
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    # property whose NAME collides with the keyword
                                    "nullable": {"type": "integer"},
                                    "x-nullable": {"type": "boolean"},
                                    # a property name collision whose own schema is
                                    # the boolean `true` (must not corrupt the map)
                                    "flag": True,
                                },
                            },
                        }
                    ],
                    "responses": {"201": {"description": "created"}},
                }
            }
        },
    }

    ep = extract_endpoints(spec)[0]

    assert ep.request == {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "nullable": {"type": "integer"},
            "x-nullable": {"type": "boolean"},
            "flag": True,
        },
    }
    assert "nullable" in ep.request["properties"]
    assert "x-nullable" in ep.request["properties"]
    assert "flag" in ep.request["properties"]


def test_extract_endpoints_rejects_illegal_response_status_key() -> None:
    """A response key outside the legal shapes raises ValueError, not a file write.

    Response keys become artifact filenames (``schemas/<status_code>.json`` in
    generate), so a key carrying path content — ``../..`` — must never reach a
    write path. Both formats validate the key set before any extraction.
    """
    openapi_spec = {
        "openapi": "3.0.0",
        "paths": {"/a": {"get": {"responses": {"../../evil": {"description": "d"}}}}},
    }
    swagger_spec = {
        "swagger": "2.0",
        "paths": {"/a": {"get": {"responses": {"200": {"schema": {}}, "a/b": {"schema": {}}}}}},
    }

    with pytest.raises(ValueError, match="invalid response status key"):
        extract_endpoints(openapi_spec)
    with pytest.raises(ValueError, match="invalid response status key"):
        extract_endpoints(swagger_spec)


@pytest.mark.parametrize(
    "key",
    ["200", "404", "default", "2XX", "5xx"],
)
def test_extract_endpoints_accepts_legal_response_status_keys(key: str) -> None:
    """Every status-key shape the specifications allow extracts without raising."""
    spec = {
        "openapi": "3.0.0",
        "paths": {"/a": {"get": {"responses": {key: {"description": "d"}}}}},
    }

    endpoints = extract_endpoints(spec)

    assert list(endpoints[0].response.keys()) == [key]


def test_extract_endpoints_null_path_item_parameters_normalized() -> None:
    """`parameters:` with no value parses to None and means no parameters.

    The merge site unpacks both lists — a raw None would raise TypeError.
    """
    spec = {
        "openapi": "3.0.0",
        "paths": {
            "/x": {
                "parameters": None,
                "get": {
                    "parameters": None,
                    "responses": {"200": {"description": "ok"}},
                },
            }
        },
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].query_params == {}
    assert endpoints[0].path_params == {}


def test_extract_endpoints_null_response_entry_degrades_to_empty_schema() -> None:
    """A `'200':` entry with no body yields an empty schema, not AttributeError."""
    spec = {
        "openapi": "3.0.0",
        "paths": {"/x": {"get": {"responses": {"200": None}}}},
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].response == {"200": {}}


def test_extract_endpoints_null_response_entry_swagger_degrades_to_empty_schema() -> None:
    """A null Swagger response entry degrades the same way as the OpenAPI one."""
    spec = {
        "swagger": "2.0",
        "paths": {"/x": {"get": {"responses": {"200": None}}}},
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].response == {"200": {}}


def test_extract_endpoints_null_operation_parameters_swagger_normalized() -> None:
    """A null operation-level `parameters:` in a Swagger spec means no parameters.

    The Swagger branch of `_extract_request` reads the field itself to find the
    `in: body` parameter — a raw None there would raise TypeError.
    """
    spec = {
        "swagger": "2.0",
        "paths": {"/x": {"post": {"parameters": None, "responses": {"200": {"description": "ok"}}}}},
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].request == {}


def test_extract_endpoints_null_responses_degrades_to_no_responses() -> None:
    """`responses:` with no value means no declared responses, in both formats."""
    openapi_spec = {"openapi": "3.0.0", "paths": {"/x": {"get": {"responses": None}}}}
    swagger_spec = {"swagger": "2.0", "paths": {"/x": {"get": {"responses": None}}}}

    assert extract_endpoints(openapi_spec)[0].response == {}
    assert extract_endpoints(swagger_spec)[0].response == {}


def test_extract_endpoints_null_request_body_levels_degrade_to_empty() -> None:
    """Every null level of the requestBody chain yields an empty request schema."""
    specs = [
        {"openapi": "3.0.0", "paths": {"/x": {"post": {"requestBody": None, "responses": {"200": {}}}}}},
        {"openapi": "3.0.0", "paths": {"/x": {"post": {"requestBody": {"content": None}, "responses": {"200": {}}}}}},
        {
            "openapi": "3.0.0",
            "paths": {
                "/x": {"post": {"requestBody": {"content": {"application/json": None}}, "responses": {"200": {}}}}
            },
        },
    ]

    for spec in specs:
        assert extract_endpoints(spec)[0].request == {}


def test_extract_endpoints_null_response_content_degrades_to_empty_schema() -> None:
    """A null `content:` inside a response entry yields an empty schema, not AttributeError."""
    spec = {
        "openapi": "3.0.0",
        "paths": {"/x": {"get": {"responses": {"200": {"content": None}}}}},
    }

    endpoints = extract_endpoints(spec)

    assert endpoints[0].response == {"200": {}}
