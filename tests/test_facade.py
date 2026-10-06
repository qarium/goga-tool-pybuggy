"""Contract and logic tests for the root facade re-exports (active_sandbox, services)."""

# Contract tests — facade surface and shapes.


def test_facade_exports_capability_surface() -> None:
    """The root facade should re-export the sandbox capability surface."""
    import goga_tool_pybuggy
    from goga_tool_pybuggy import active_sandbox, services

    assert callable(active_sandbox)
    assert callable(services)
    assert "active_sandbox" in goga_tool_pybuggy.__all__
    assert "services" in goga_tool_pybuggy.__all__


def test_facade_reexports_resolve_to_cell_entities() -> None:
    """The re-exported names should resolve to the sandbox cell entities, not copies."""
    from goga_tool_pybuggy import active_sandbox, services
    from goga_tool_pybuggy.sandbox import active_sandbox as cell_active_sandbox
    from goga_tool_pybuggy.sandbox.data import services as cell_services

    assert active_sandbox is cell_active_sandbox
    assert services is cell_services


def test_facade_keeps_existing_exports() -> None:
    """The root facade should keep the pre-existing exports unchanged."""
    import goga_tool_pybuggy

    for name in ("EnvContext", "install", "load_env", "main", "register_hooks", "retries"):
        assert name in goga_tool_pybuggy.__all__
        assert getattr(goga_tool_pybuggy, name) is not None
