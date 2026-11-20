"""Contract and logic tests for the root facade re-exports (services, install, generation_prompt)."""

# Contract tests — facade surface and shapes.


def test_facade_exports_capability_surface() -> None:
    """The root facade should re-export the sandbox capability surface."""
    import goga_tool_pybuggy
    from goga_tool_pybuggy import services

    assert callable(services)
    assert "services" in goga_tool_pybuggy.__all__
    assert "active_sandbox" not in goga_tool_pybuggy.__all__
    assert not hasattr(goga_tool_pybuggy, "active_sandbox")


def test_facade_reexports_resolve_to_cell_entities() -> None:
    """The re-exported names should resolve to the sandbox cell entities, not copies."""
    from goga_tool_pybuggy import services
    from goga_tool_pybuggy.sandbox.data import services as cell_services

    assert services is cell_services


def test_facade_install_reexports_lifecycle_install() -> None:
    """The facade install slot should resolve to the lifecycle cell hook entity."""
    import goga_tool_pybuggy
    from goga_tool_pybuggy.lifecycle import install as lifecycle_install

    assert goga_tool_pybuggy.install is lifecycle_install
    assert "install" in goga_tool_pybuggy.__all__


def test_facade_install_is_not_the_plugins_install() -> None:
    """The plugins cell keeps its own install — consumers call it via the submodule path."""
    import goga_tool_pybuggy
    from goga_tool_pybuggy.plugins import install as plugins_install

    assert goga_tool_pybuggy.install is not plugins_install


def test_facade_reexports_generation_prompt() -> None:
    """The facade should re-export the web cell's per-test generation-prompt decorator."""
    import goga_tool_pybuggy
    from goga_tool_pybuggy import generation_prompt
    from goga_tool_pybuggy.web.pretty import generation_prompt as cell_entity

    assert callable(generation_prompt)
    assert generation_prompt is cell_entity
    assert "generation_prompt" in goga_tool_pybuggy.__all__
    assert "generation_prompt" in goga_tool_pybuggy.web.__all__


def test_facade_keeps_existing_exports() -> None:
    """The root facade should keep the pre-existing exports unchanged."""
    import goga_tool_pybuggy

    for name in ("EnvContext", "install", "load_env", "main", "register_hooks", "retries"):
        assert name in goga_tool_pybuggy.__all__
        assert getattr(goga_tool_pybuggy, name) is not None
