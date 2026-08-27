"""Contract and logic tests for render_list and render_status_list output formatters."""

import goga_tool_pybuggy.output
from goga_tool_pybuggy.output import render_list, render_status_list
from goga_tool_pybuggy.spec import Endpoint


def test_render_list_facade_import():
    """Contract test: render_list is importable from goga_tool_pybuggy.output facade."""
    import importlib

    output_module = importlib.import_module("goga_tool_pybuggy.output")
    assert hasattr(output_module, "render_list")
    assert callable(output_module.render_list)


def test_render_list_signature():
    """Contract test: render_list has correct signature."""
    import inspect

    sig = inspect.signature(render_list)
    params = list(sig.parameters.keys())
    # Should have parameters: name, location, endpoints
    assert "name" in params
    assert "location" in params
    assert "endpoints" in params
    assert len(params) == 3
    # Return type should be str (or at least return string)
    result = render_list(name="test", location="test.yaml", endpoints=[])
    assert isinstance(result, str)


def test_render_list_format():
    """Logic test: render_list produces correct format with endpoints."""
    # Create two endpoints with known ids
    # clients_profile_delete and clients_startup_get
    ep1 = Endpoint(
        method="delete",
        path="/clients/profile",
        request={},
        response={"204": {}},
        query_params={},
        description="Delete profile",
    )
    ep2 = Endpoint(
        method="get",
        path="/clients/startup",
        request={},
        response={"200": {}},
        query_params={},
        description="Get startup info",
    )

    # Verify computed ids
    assert ep1.id == "clients_profile_delete"
    assert ep2.id == "clients_startup_get"

    result = render_list(
        name="client",
        location=".specs/x.yaml",
        endpoints=[ep1, ep2],
    )

    expected = """client (.specs/x.yaml)
* clients_profile_delete -> [DELETE] /clients/profile
* clients_startup_get -> [GET] /clients/startup"""

    assert result == expected


def test_render_list_empty_endpoints():
    """Logic test: render_list with empty endpoints produces only header."""
    result = render_list(
        name="empty_spec",
        location="specs/empty.yaml",
        endpoints=[],
    )

    expected = "empty_spec (specs/empty.yaml)"
    assert result == expected


def test_render_list_sorts_by_id():
    """Logic test: render_list sorts endpoints by id."""
    # Create endpoints in reverse order of id
    ep1 = Endpoint(
        method="get",
        path="/z",
        request={},
        response={},
        query_params={},
        description="",
    )
    ep2 = Endpoint(
        method="get",
        path="/a",
        request={},
        response={},
        query_params={},
        description="",
    )
    ep3 = Endpoint(
        method="post",
        path="/m",
        request={},
        response={},
        query_params={},
        description="",
    )

    # ids should be: z_get, a_get, m_post
    # sorted order: a_get, m_post, z_get
    result = render_list(
        name="test",
        location="test.yaml",
        endpoints=[ep1, ep2, ep3],  # Unsorted input
    )

    lines = result.split("\n")
    assert lines[0] == "test (test.yaml)"
    # Should be sorted by id
    assert "* a_get -> [GET] /a" in lines[1]
    assert "* m_post -> [POST] /m" in lines[2]
    assert "* z_get -> [GET] /z" in lines[3]


def test_render_status_list_facade_import_and_signature():
    """Contract test: render_status_list is exported from the facade with the declared signature."""
    import inspect

    assert "render_status_list" in goga_tool_pybuggy.output.__all__
    assert goga_tool_pybuggy.output.__all__ == sorted(goga_tool_pybuggy.output.__all__)

    params = list(inspect.signature(render_status_list).parameters)
    assert params == ["name", "location", "endpoints", "statuses", "removed"]
    assert render_status_list.__annotations__["return"] is str


def test_render_status_list_format_endpoint_lines():
    """Logic test: endpoint lines carry uppercase METHOD, raw path, and the em dash separator."""
    ep1 = Endpoint(
        method="delete",
        path="/clients/profile",
        request={},
        response={"204": {}},
        query_params={},
        description="Delete profile",
    )
    ep2 = Endpoint(
        method="get",
        path="/clients/startup",
        request={},
        response={"200": {}},
        query_params={},
        description="Get startup info",
    )

    assert ep1.id == "clients_profile_delete"
    assert ep2.id == "clients_startup_get"

    result = render_status_list(
        name="client",
        location=".specs/x.yaml",
        endpoints=[ep1, ep2],
        statuses={"clients_profile_delete": "OK", "clients_startup_get": "ADD"},
        removed=[],
    )

    expected = (
        "client (.specs/x.yaml)\n"
        "* clients_profile_delete -> [DELETE] /clients/profile — STATUS: OK\n"
        "* clients_startup_get -> [GET] /clients/startup — STATUS: ADD"
    )

    assert result == expected


def test_render_status_list_merges_and_sorts_by_line_name():
    """Logic test: endpoint and removed lines form one list sorted by line name."""
    ep1 = Endpoint(
        method="get",
        path="/z",
        request={},
        response={},
        query_params={},
        description="",
    )
    ep2 = Endpoint(
        method="get",
        path="/a",
        request={},
        response={},
        query_params={},
        description="",
    )

    result = render_status_list(
        name="test",
        location="test.yaml",
        endpoints=[ep1, ep2],
        statuses={"z_get": "OK", "a_get": "OK"},
        removed=["m_post"],
    )

    assert result.split("\n")[1:] == [
        "* a_get -> [GET] /a — STATUS: OK",
        "* m_post — STATUS: REMOVED",
        "* z_get -> [GET] /z — STATUS: OK",
    ]


def test_render_status_list_header_only_when_no_lines():
    """Logic test: no endpoints and no removed segments yield the header-only block."""
    result = render_status_list(
        name="empty",
        location="e.yaml",
        endpoints=[],
        statuses={},
        removed=[],
    )

    assert result == "empty (e.yaml)"
