"""Contract and logic tests for Endpoint entity."""

import pytest
from pybuggy.spec import Endpoint
from pydantic import ValidationError


class TestEndpointContract:
    """Contract tests for Endpoint entity."""

    def test_endpoint_importable_from_facade(self) -> None:
        """Endpoint should be importable from pybuggy.spec facade."""
        from pybuggy.spec import Endpoint

        assert Endpoint is not None

    def test_endpoint_signature_kw_only(self) -> None:
        """Endpoint constructor should require keyword-only arguments."""
        # Should work with keyword arguments
        endpoint = Endpoint(
            method="get",
            path="/clients/{id}",
            request={},
            response={"200": {}},
            query_params={},
            description="",
        )
        assert endpoint.method == "get"

        # Should fail with positional arguments (kw_only=True)
        with pytest.raises(TypeError):
            Endpoint(
                "get",  # type: ignore
                "/clients/{id}",
                {},
                {"200": {}},
                {},
                "",
            )

    def test_endpoint_is_pydantic_model(self) -> None:
        """Endpoint should be a pydantic BaseModel."""
        from pydantic import BaseModel

        assert issubclass(Endpoint, BaseModel)

    def test_endpoint_has_id_property(self) -> None:
        """Endpoint should have an `id` property (str)."""
        endpoint = Endpoint(
            method="get",
            path="/clients/{id}",
            request={},
            response={"200": {}},
            query_params={},
            description="",
        )
        assert hasattr(endpoint, "id")
        assert isinstance(endpoint.id, str)

    def test_endpoint_id_is_not_constructor_field(self) -> None:
        """Endpoint `id` should NOT be a constructor field."""
        # Passing id explicitly should be rejected by pydantic (computed field)
        with pytest.raises(ValidationError):
            Endpoint(
                method="get",
                path="/clients/{id}",
                request={},
                response={"200": {}},
                query_params={},
                description="",
                id="custom_id",  # type: ignore
            )


class TestEndpointLogic:
    """Logic tests for Endpoint entity."""

    def test_endpoint_constructs_with_all_fields(self) -> None:
        """Endpoint should construct with all fields and return correct values."""
        request_schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        response_schema = {"200": {"type": "object"}}
        query_schema = {"limit": {"type": "integer"}}

        endpoint = Endpoint(
            method="get",
            path="/clients/{id}",
            request=request_schema,
            response=response_schema,
            query_params=query_schema,
            description="Get client by ID",
        )

        assert endpoint.method == "get"
        assert endpoint.path == "/clients/{id}"
        assert endpoint.request == request_schema
        assert endpoint.response == response_schema
        assert endpoint.query_params == query_schema
        assert endpoint.description == "Get client by ID"

    def test_endpoint_id_computed_from_method_and_path(self) -> None:
        """Endpoint.id should be computed via build_endpoint_id."""
        endpoint = Endpoint(
            method="get",
            path="/clients/{id}",
            request={},
            response={"200": {}},
            query_params={},
            description="",
        )
        assert endpoint.id == "clients_id_get"

    def test_endpoint_id_with_post_method(self) -> None:
        """Endpoint.id should work with POST method."""
        endpoint = Endpoint(
            method="POST",
            path="/v1/API/{name}",
            request={},
            response={"201": {}},
            query_params={},
            description="",
        )
        assert endpoint.id == "v1_api_name_post"

    def test_endpoint_with_empty_schemas(self) -> None:
        """Endpoint should allow empty request/response/query_params."""
        endpoint = Endpoint(
            method="delete",
            path="/clients/profile",
            request={},
            response={},
            query_params={},
            description="",
        )
        assert endpoint.request == {}
        assert endpoint.response == {}
        assert endpoint.query_params == {}
        assert endpoint.description == ""
        assert endpoint.id == "clients_profile_delete"

    def test_endpoint_id_with_multiple_path_params(self) -> None:
        """Endpoint.id should handle multiple path parameters."""
        endpoint = Endpoint(
            method="get",
            path="/clients/{a}/{b}",
            request={},
            response={},
            query_params={},
            description="",
        )
        assert endpoint.id == "clients_a_b_get"

    def test_endpoint_id_with_no_leading_slash(self) -> None:
        """Endpoint.id should handle paths without leading slash."""
        endpoint = Endpoint(
            method="post",
            path="x",
            request={},
            response={},
            query_params={},
            description="",
        )
        assert endpoint.id == "x_post"

    def test_endpoint_id_lowercases_method(self) -> None:
        """Endpoint.id should lowercase the method."""
        endpoint = Endpoint(
            method="DELETE",
            path="/clients/profile",
            request={},
            response={},
            query_params={},
            description="",
        )
        assert endpoint.id == "clients_profile_delete"

    def test_endpoint_allows_any_dict_fields(self) -> None:
        """Endpoint request/response/query_params should accept any dict content."""
        complex_request = {
            "type": "object",
            "properties": {"nested": {"type": "object", "properties": {"x": {"type": "string"}}}},
        }
        complex_response = {"200": {"type": "object"}, "404": {"type": "object"}}
        complex_query = {"filter": {"type": "array", "items": {"type": "string"}}}

        endpoint = Endpoint(
            method="get",
            path="/search",
            request=complex_request,
            response=complex_response,
            query_params=complex_query,
            description="Search endpoint",
        )

        assert endpoint.request == complex_request
        assert endpoint.response == complex_response
        assert endpoint.query_params == complex_query
