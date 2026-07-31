"""Contract tests for render_info routine.

These tests verify the contract compliance of render_info:
- Importable from goga_tool_pybuggy.output facade
- Correct signature (endpoints: list[Endpoint]) -> str
"""

import pytest
from goga_tool_pybuggy.output import render_info
from goga_tool_pybuggy.spec import Endpoint


def test_render_info_importable_from_facade() -> None:
    """render_info must be importable from goga_tool_pybuggy.output facade."""
    from goga_tool_pybuggy.output import render_info

    assert callable(render_info)


def test_render_info_signature() -> None:
    """render_info must have signature (endpoints: list[Endpoint]) -> str."""
    from inspect import signature
    from typing import get_type_hints

    sig = signature(render_info)
    params = list(sig.parameters.keys())

    # Should have one parameter 'endpoints'
    assert params == ["endpoints"], f"Expected ['endpoints'], got {params}"

    # Return type should be str
    # Provide namespace for type hint resolution
    hints = get_type_hints(render_info, globalns=globals(), localns=locals())
    assert hints.get("return") is str, f"Expected return type str, got {hints.get('return')}"


def test_render_info_single_object() -> None:
    """Single endpoint should render as JSON object with correct keys."""
    import json

    endpoint = Endpoint(
        method="get",
        path="/clients/{id}",
        request={"type": "object"},
        response={"200": {"type": "object"}},
        query_params={"id": {"type": "string"}},
        description="Get client by ID",
    )

    result = render_info([endpoint])
    parsed = json.loads(result)

    # Should be a dict (single object), not a list
    assert isinstance(parsed, dict), f"Expected dict, got {type(parsed)}"

    # Keys must be exactly PascalCase
    expected_keys = {"Method", "Path", "Request", "Response", "QueryParams", "Description"}
    assert set(parsed.keys()) == expected_keys, f"Expected keys {expected_keys}, got {set(parsed.keys())}"

    # Method should be lowercased
    assert parsed["Method"] == "get"

    # Path should use :param format (braces stripped)
    assert parsed["Path"] == "/clients/:id"


def test_render_info_array_on_collision() -> None:
    """Multiple endpoints should render as JSON array."""
    import json

    endpoint1 = Endpoint(
        method="get",
        path="/clients/{id}",
        request={},
        response={},
        query_params={},
        description="",
    )

    endpoint2 = Endpoint(
        method="post",
        path="/clients",
        request={},
        response={},
        query_params={},
        description="",
    )

    result = render_info([endpoint1, endpoint2])
    parsed = json.loads(result)

    # Should be a list for multiple endpoints
    assert isinstance(parsed, list), f"Expected list, got {type(parsed)}"
    assert len(parsed) == 2, f"Expected 2 items, got {len(parsed)}"


def test_render_info_path_with_multiple_params() -> None:
    """Path with multiple parameters should convert all braces to colons."""
    import json

    endpoint = Endpoint(
        method="get",
        path="/clients/{client_id}/orders/{order_id}",
        request={},
        response={},
        query_params={},
        description="",
    )

    result = render_info([endpoint])
    parsed = json.loads(result)

    # All parameters should use :param format
    assert parsed["Path"] == "/clients/:client_id/orders/:order_id"


def test_render_info_ensure_ascii_false() -> None:
    """Non-ASCII characters in description should be readable (not escaped)."""

    endpoint = Endpoint(
        method="get",
        path="/clients",
        request={},
        response={},
        query_params={},
        description="Получить список клиентов",  # Cyrillic text
    )

    result = render_info([endpoint])

    # Should contain readable Cyrillic, not escaped unicode
    assert "Получить список клиентов" in result
    assert "\\u" not in result  # No unicode escapes


def test_render_info_serializes_date_and_datetime() -> None:
    """date/datetime carried in resolved specs render as ISO 8601 strings.

    swax/Prance convert YAML date examples into ``datetime.date``/
    ``datetime.datetime``; render_info must serialize them instead of raising
    ``TypeError: Object of type datetime is not JSON serializable``.
    """
    import json
    from datetime import date, datetime, timezone

    endpoint = Endpoint(
        method="get",
        path="/orders/history",
        request={},
        response={"200": {}},
        query_params={
            "from": {"type": "string", "format": "date", "example": date(2020, 1, 1)},
            "until": {
                "type": "string",
                "format": "date-time",
                "example": datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc),
            },
        },
        description="orders history",
    )

    result = render_info([endpoint])
    parsed = json.loads(result)

    assert parsed["QueryParams"]["from"]["example"] == "2020-01-01"
    assert parsed["QueryParams"]["until"]["example"] == "2020-01-01T10:00:00+00:00"


def test_render_info_unknown_type_still_raises_typeerror() -> None:
    """Non-JSON-native values other than date/datetime still raise TypeError.

    The serializer must not silently swallow unexpected types; it re-raises so
    genuine encoding bugs stay visible.
    """

    class _Opaque:
        pass

    endpoint = Endpoint(
        method="get",
        path="/x",
        request={"thing": _Opaque()},
        response={},
        query_params={},
        description="",
    )

    with pytest.raises(TypeError):
        render_info([endpoint])
