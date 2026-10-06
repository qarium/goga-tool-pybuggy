"""Contract and logic tests for the ``BaselineBoundary`` entity."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox import sandbox as sandbox_module
from goga_tool_pybuggy.sandbox.config import InstanceConfig, SandboxConfig, ServiceConfig, StartupData
from goga_tool_pybuggy.sandbox.engines import DataOperation, InstanceAddress

from .conftest import FakeEngine, FakeService


@pytest.fixture
def started(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[sandbox_module.Sandbox, FakeEngine, FakeService, list[str]]:
    """A started sandbox over one recording postgresql engine and one recording service.

    The scenario carries no startup data, so the engine journal starts empty — every
    journaled entry a test observes was declared inside a baseline boundary.

    Returns:
        The started sandbox, its recording engine, its recording service, and the shared
        lifecycle event sink of the fakes.
    """
    events: list[str] = []
    engine = FakeEngine(
        name="db",
        kind="postgresql",
        address=InstanceAddress(host="127.0.0.2", port=5432),
        events=events,
    )
    service = FakeService(host="127.0.0.9", port=9000, events=events)

    monkeypatch.setattr(sandbox_module, "build_engine", lambda _instance_config: engine)
    monkeypatch.setattr(sandbox_module, "ServiceContainer", lambda _service_config: service)
    monkeypatch.setattr(sandbox_module, "check_runtime", lambda: None)

    config = SandboxConfig(
        service=ServiceConfig(image="my-service:latest", env={}, port=8080, health=None),
        instances={"db": InstanceConfig(name="db", kind="postgresql", image=None)},
        data=StartupData(),
    )

    sandbox = sandbox_module.Sandbox(config)
    sandbox.start()

    return sandbox, engine, service, events


def declared(table: str, row_id: int) -> DataOperation:
    """Build the insert operation one view declaration of ``table`` produces.

    Args:
        table: The target table of the declaration.
        row_id: The id carried by the single declared row.

    Returns:
        The operation the postgresql view declares for one row.
    """
    return DataOperation(
        instance="db",
        kind="postgresql",
        action="insert",
        payload={"table": table, "rows": [{"id": row_id}]},
    )


class TestBaselineBoundaryContract:
    """Declared API of the ``BaselineBoundary`` entity."""

    def test_baseline_boundary_is_importable_from_baseline_module(self):
        """``BaselineBoundary`` lives in ``goga_tool_pybuggy.sandbox.baseline``."""
        from goga_tool_pybuggy.sandbox.baseline import BaselineBoundary

        assert inspect.isclass(BaselineBoundary)

    def test_baseline_boundary_constructor_takes_the_sandbox(self):
        """The constructor takes exactly ``sandbox`` — the boundary's owning sandbox."""
        from goga_tool_pybuggy.sandbox.baseline import BaselineBoundary

        parameters = list(inspect.signature(BaselineBoundary.__init__).parameters)

        assert parameters == ["self", "sandbox"]

    def test_baseline_boundary_exposes_open_close_and_context_protocol(self):
        """``open``/``close`` and the dunder pair of the ``with`` form exist."""
        from goga_tool_pybuggy.sandbox.baseline import BaselineBoundary

        for name in ("open", "close", "__enter__", "__exit__"):
            assert callable(getattr(BaselineBoundary, name)), name

    def test_sandbox_baseline_factory_returns_the_boundary(self, started: tuple):
        """``Sandbox.baseline()`` hands out the boundary of this sandbox."""
        from goga_tool_pybuggy.sandbox.baseline import BaselineBoundary

        sandbox, _, _, _ = started

        assert isinstance(sandbox.baseline(), BaselineBoundary)


class TestBaselineBoundaryBehavior:
    """Immediate-apply routing of the open baseline boundary."""

    def test_baseline_boundary_applies_immediately_and_journals(self, started: tuple):
        """A declaration inside the boundary applies and journals at declaration time."""
        sandbox, engine, _, _ = started

        with sandbox.baseline():
            sandbox.postgresql("db").insert("customers", [{"id": 1}])

        assert engine.applied == [declared("customers", 1)]
        assert engine.journaled == [declared("customers", 1)]

    def test_boundary_declaration_leaves_the_lazy_batch_untouched(self, started: tuple):
        """The per-test lazy batch stays empty; ``apply_pending`` afterwards applies nothing."""
        sandbox, engine, _, _ = started

        with sandbox.baseline():
            sandbox.postgresql("db").insert("customers", [{"id": 1}])

        sandbox.apply_pending()

        assert engine.applied == [declared("customers", 1)]

    def test_boundary_applies_before_it_journals(self, started: tuple):
        """The boundary routes each declaration through apply first, then record."""
        sandbox, _, _, events = started
        events.clear()

        with sandbox.baseline():
            sandbox.postgresql("db").insert("customers", [{"id": 1}])

        assert events == ["engine:db:apply", "engine:db:record"]

    def test_close_freezes_journals_and_restores_lazy_declaration(self, started: tuple):
        """After ``close`` the journals stop growing and views declare lazily again."""
        sandbox, engine, _, _ = started
        boundary = sandbox.baseline()

        with boundary:
            sandbox.postgresql("db").insert("customers", [{"id": 1}])

        sandbox.postgresql("db").insert("orders", [{"id": 2}])

        assert engine.applied == [declared("customers", 1)]
        assert engine.journaled == [declared("customers", 1)]

        sandbox.apply_pending()

        assert engine.applied == [declared("customers", 1), declared("orders", 2)]
        assert engine.journaled == [declared("customers", 1)]

    def test_exception_inside_boundary_propagates_and_closes_the_boundary(self, started: tuple):
        """An exception inside the ``with`` block propagates and the routing is restored."""
        sandbox, engine, _, _ = started

        with pytest.raises(RuntimeError, match="boom"), sandbox.baseline():
            raise RuntimeError("boom")

        sandbox.postgresql("db").insert("orders", [{"id": 3}])

        assert engine.applied == []

        sandbox.apply_pending()

        assert engine.applied == [declared("orders", 3)]
