"""Contract tests for build_endpoint_id routine."""

import pytest
from goga_tool_pybuggy.spec import build_endpoint_id


def test_build_endpoint_id_is_importable_from_facade() -> None:
    """Verify build_endpoint_id can be imported from goga_tool_pybuggy.spec facade."""
    from goga_tool_pybuggy.spec import build_endpoint_id as imported_func

    assert imported_func is build_endpoint_id


def test_build_endpoint_id_signature() -> None:
    """Verify build_endpoint_id has correct signature: (method: str, path: str) -> str."""
    import inspect

    sig = inspect.signature(build_endpoint_id)
    params = list(sig.parameters.keys())

    assert len(params) == 2, f"Expected 2 parameters, got {len(params)}"
    assert "method" in params, "Missing 'method' parameter"
    assert "path" in params, "Missing 'path' parameter"

    # Check parameter annotations
    method_param = sig.parameters["method"]
    path_param = sig.parameters["path"]
    assert method_param.annotation is str, f"method annotation should be str, got {method_param.annotation}"
    assert path_param.annotation is str, f"path annotation should be str, got {path_param.annotation}"

    # Check return annotation
    assert sig.return_annotation is str, f"Return annotation should be str, got {sig.return_annotation}"


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("POST", "/v1/API/{name}", "v1_api_name_post"),
        ("GET", "/clients/startup", "clients_startup_get"),
        ("DELETE", "/clients/profile", "clients_profile_delete"),
        ("GET", "/clients/payment-details", "clients_payment_details_get"),
    ],
)
def test_build_endpoint_id_acceptance_cases(method: str, path: str, expected: str) -> None:
    """Test build_endpoint_id with acceptance test cases from the contract."""
    assert build_endpoint_id(method, path) == expected


@pytest.mark.parametrize(
    ("method", "path", "expected"),
    [
        ("GET", "clients/{a}/{b}", "clients_a_b_get"),
        ("POST", "/x", "x_post"),
    ],
)
def test_build_endpoint_id_multiple_params_and_no_leading_slash(method: str, path: str, expected: str) -> None:
    """Test build_endpoint_id with multiple params and paths without leading slash."""
    assert build_endpoint_id(method, path) == expected


def test_build_endpoint_id_lowercases_method_already_lowercase() -> None:
    """Test that method already lowercased is handled correctly."""
    # Method is already lowercase - should still work
    assert build_endpoint_id("get", "/test") == "test_get"


def test_build_endpoint_id_path_without_parameters() -> None:
    """Test build_endpoint_id with path that has no parameters."""
    assert build_endpoint_id("PUT", "/api/v1/users") == "api_v1_users_put"


def test_build_endpoint_id_normalizes_hyphens() -> None:
    """Hyphens in the path are normalized to underscores so the id stays a valid identifier.

    The id is consumed as a pytest fixture name and as a package directory by
    `generate`; a surviving hyphen would render the generated module syntactically
    invalid and abort generation (ruff exit 2).
    """
    assert build_endpoint_id("POST", "/payment-details/{id}") == "payment_details_id_post"
    assert "-" not in build_endpoint_id("GET", "/a-b/c-d")


def test_build_endpoint_id_is_valid_python_identifier() -> None:
    """Every produced id must be a syntactically valid Python identifier."""
    import keyword

    for method, path in [
        ("GET", "/clients/payment-details"),
        ("POST", "/api/v1/billing-invoices/{invoice-id}"),
        ("DELETE", "/x-y/z"),
    ]:
        identifier = build_endpoint_id(method, path)
        assert identifier.isidentifier(), f"not an identifier: {identifier!r}"
        assert not keyword.iskeyword(identifier), f"keyword id: {identifier!r}"
