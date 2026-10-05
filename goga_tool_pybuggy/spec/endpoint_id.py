"""Endpoint ID generation routine."""


def build_endpoint_id(method: str, path: str) -> str:
    """Build a stable endpoint identifier from HTTP method and path.

    The id is not guaranteed a valid Python identifier; `generate` sanitizes it further.

    Args:
        method: HTTP method (e.g., "GET", "POST", "DELETE").
        path: Path template with parameters in braces, e.g., "/clients/{id}".

    Returns:
        Stable endpoint identifier string.

    Examples:
        >>> build_endpoint_id("POST", "/v1/API/{name}")
        'v1_api_name_post'
        >>> build_endpoint_id("GET", "/clients/startup")
        'clients_startup_get'
        >>> build_endpoint_id("DELETE", "/clients/profile")
        'clients_profile_delete'
        >>> build_endpoint_id("GET", "/clients/payment-details")
        'clients_payment_details_get'
    """
    # Step 1: Drop a single leading "/" from path
    p = path[1:] if path.startswith("/") else path

    # Step 2: Remove "{" and "}" from the path (keep the parameter name)
    p = p.replace("{", "").replace("}", "")

    # Step 3: Lowercase the result
    p = p.lower()

    # Step 4: Replace every "/" with "_"
    p = p.replace("/", "_")

    # Step 5: Replace every "-" with "_" — the id must stay a valid identifier.
    p = p.replace("-", "_")

    # Step 6: Append "_" + method.lower()
    result = p + "_" + method.lower()

    return result
