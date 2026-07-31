"""Integration tests for top-level CLI command registration (cli.py composition root)."""

from pybuggy import main


def test_init_registered_top_level_not_under_endpoint() -> None:
    """init_cmd is registered on the root group directly, not under the endpoint subgroup.

    Mirrors the ``main()`` Algorithm steps 5-6 in ``pybuggy/CODEMANIFEST``: ``init_cmd`` is attached
    to ``main`` top-level, while pull/list/info/generate remain under the ``endpoint`` subgroup.
    """
    assert "endpoint" in main.commands
    assert "init" in main.commands

    endpoint = main.commands["endpoint"]
    assert {"pull", "list", "info", "generate"} <= set(endpoint.commands)
    assert "init" not in endpoint.commands
