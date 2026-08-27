"""Integration tests for top-level CLI command registration (cli.py composition root)."""

from goga_tool_pybuggy import main


def test_init_registered_top_level_not_under_endpoint() -> None:
    """init_cmd is registered on the root group directly, not under the endpoint subgroup.

    Mirrors the ``main()`` Algorithm steps 5-6 in ``goga_tool_pybuggy/CODEMANIFEST``: ``init_cmd`` is attached
    to ``main`` top-level, while pull/list/info/generate remain under the ``endpoint`` subgroup.
    """
    assert "endpoint" in main.commands
    assert "init" in main.commands

    endpoint = main.commands["endpoint"]
    assert {"pull", "list", "info", "generate"} <= set(endpoint.commands)
    assert "init" not in endpoint.commands


def test_cli_registers_diff_on_endpoint_subgroup() -> None:
    """diff_cmd is registered on the endpoint subgroup after generate_cmd.

    Mirrors the ``main()`` Algorithm step 5 in ``goga_tool_pybuggy/CODEMANIFEST``: ``diff_cmd`` is
    attached to the ``endpoint`` subgroup (final order pull, list, info, generate, diff), while
    ``init`` stays top-level only.
    """
    assert "endpoint" in main.commands

    endpoint = main.commands["endpoint"]
    assert {"pull", "list", "info", "generate", "diff"} <= set(endpoint.commands)
    assert "init" not in endpoint.commands
