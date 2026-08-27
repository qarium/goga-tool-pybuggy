"""Contract and logic tests for the render_diff output formatter."""

from typing import Any

import goga_tool_pybuggy.output
from goga_tool_pybuggy.output import render_diff


def test_render_diff_importable_and_signature() -> None:
    """render_diff is importable from the output facade as (endpoint_id, diff) -> str."""
    params = render_diff.__code__.co_varnames[: render_diff.__code__.co_argcount]

    assert params == ("endpoint_id", "diff")
    assert render_diff.__annotations__["return"] is str
    assert render_diff.__annotations__["endpoint_id"] is str
    assert render_diff.__annotations__["diff"] == dict[str, Any]


def test_render_diff_listed_in_facade_all() -> None:
    """The output facade exports render_diff and keeps __all__ sorted."""
    assert "render_diff" in goga_tool_pybuggy.output.__all__
    assert goga_tool_pybuggy.output.__all__ == sorted(goga_tool_pybuggy.output.__all__)


def test_render_diff_wraps_diff_in_single_line_json() -> None:
    """A drift result is wrapped as a single-line JSON document keyed by the compared unit."""
    result = render_diff(
        "clients_startup_get",
        {
            "values_changed": {
                "root['request_body']['properties']['note']['type']": {"old_value": "integer", "new_value": "string"}
            }
        },
    )

    assert result == (
        "{\"clients_startup_get\": {\"values_changed\": {\"root['request_body']['properties']['note']['type']\": "
        '{"old_value": "integer", "new_value": "string"}}}}'
    )
    assert "\n" not in result


def test_render_diff_empty_diff_serializes_empty_object() -> None:
    """A no-drift result serializes the empty mapping as {}."""
    result = render_diff("clients_startup_get", {})

    assert result == '{"clients_startup_get": {}}'


def test_render_diff_pure_no_stdout(capsys: Any) -> None:
    """The formatter is pure — it never writes to stdout; command handlers print."""
    render_diff("e", {})

    assert capsys.readouterr().out == ""
