"""Integration tests for top-level CLI command registration (cli.py composition root)."""

from goga_tool_pybuggy import main


def test_init_registered_top_level_not_under_endpoint() -> None:
    """init_cmd is registered on the root group directly, not under the endpoint subgroup.

    ``init_cmd`` is top-level per ``main()`` Algorithm steps 5-6; the endpoint commands stay grouped.
    """
    assert "endpoint" in main.commands
    assert "init" in main.commands

    endpoint = main.commands["endpoint"]
    assert {"pull", "list", "info", "generate"} <= set(endpoint.commands)
    assert "init" not in endpoint.commands


def test_cli_registers_diff_on_endpoint_subgroup() -> None:
    """diff_cmd is registered on the endpoint subgroup after generate_cmd.

    ``diff_cmd`` joins the ``endpoint`` subgroup (order pull, list, info, generate, diff) per ``main()`` step 5.
    """
    assert "endpoint" in main.commands

    endpoint = main.commands["endpoint"]
    assert {"pull", "list", "info", "generate", "diff"} <= set(endpoint.commands)
    assert "init" not in endpoint.commands
