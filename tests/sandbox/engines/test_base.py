"""Contract and logic tests for the ``BaseEngine`` entity and ``EngineError``."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox.config import InstanceConfig
from goga_tool_pybuggy.sandbox.engines import BaseEngine, DataOperation, EngineError, InstanceAddress


class FakeContainer:
    """Container double exposing the testcontainers accessors ``BaseEngine`` reads."""

    def __init__(self, host: str = "127.0.0.2", port: int = 5432) -> None:
        self.host = host
        self.port = port
        self.stops = 0

    def start(self) -> "FakeContainer":
        return self

    def stop(self, force: bool = True, delete_volume: bool = True) -> None:
        self.stops += 1

    def get_container_host_ip(self) -> str:
        return self.host

    def get_exposed_port(self, port: int) -> str:
        return str(self.port)


class FakeEngine(BaseEngine):
    """Recording engine double — kind hooks record calls instead of touching containers."""

    _container_port = 5432

    def __init__(self, name: str = "db", kind: str = "postgresql") -> None:
        super().__init__(InstanceConfig(name=name, kind=kind, image=None))
        self.calls: list[str] = []
        self.executed: list[DataOperation] = []
        self.containers: list[FakeContainer] = []
        self.fail_execute: str | None = None
        self.fail_open_plane = False

    def _build_container(self) -> FakeContainer:
        self.calls.append("build")
        container = FakeContainer()
        self.containers.append(container)

        return container

    def _wait_ready(self) -> None:
        self.calls.append("ready")

    def _open_plane(self) -> None:
        self.calls.append("plane")

        if self.fail_open_plane:
            raise RuntimeError("plane refused")

    def _execute(self, operation: DataOperation) -> None:
        self.calls.append(f"execute:{operation.action}")
        self.executed.append(operation)

        if self.fail_execute == operation.action:
            raise RuntimeError("boom")

    def _wipe(self) -> None:
        self.calls.append("wipe")

    def _close_plane(self) -> None:
        self.calls.append("close")

    @property
    def journal(self) -> list[DataOperation]:
        return self._journal

    @property
    def started(self) -> bool:
        return self._started


def operation(action: str = "insert") -> DataOperation:
    """Build one sample operation of the postgresql insert shape.

    Args:
        action: The action name carried by the built operation.

    Returns:
        A sample ``DataOperation`` targeted at the ``db`` instance.
    """
    return DataOperation(
        instance="db",
        kind="postgresql",
        action=action,
        payload={"table": "orders", "rows": [{"id": 1}]},
    )


class TestBaseEngineContract:
    """Declared API of the ``BaseEngine`` entity and ``EngineError``."""

    def test_base_engine_is_importable_from_engines_facade(self):
        """``BaseEngine`` is re-exported by the ``goga_tool_pybuggy.sandbox.engines`` facade."""
        assert BaseEngine is not None

    def test_engine_error_is_importable_from_engines_facade(self):
        """``EngineError`` is importable from the engines facade for internal cross-module use."""
        assert EngineError is not None

    def test_engine_error_subclasses_runtime_error(self):
        """``EngineError`` is the engine-specific ``RuntimeError`` subtype."""
        assert issubclass(EngineError, RuntimeError)

    def test_base_engine_constructs_with_the_config(self):
        """``BaseEngine`` takes the instance config and keeps it as ``config``."""
        config = InstanceConfig(name="db", kind="postgresql", image=None)
        engine = BaseEngine(config)

        assert engine.config is config

    def test_base_engine_declares_the_contract_constructor(self):
        """The constructor signature is ``__init__(self, config)``."""
        signature = inspect.signature(BaseEngine.__init__)

        assert list(signature.parameters) == ["self", "config"]

    def test_base_engine_declares_the_five_contract_methods(self):
        """``start`` / ``apply`` / ``record`` / ``reset`` / ``stop`` exist with the declared parameters."""
        expected = {
            "start": ["self", "startup", "network"],
            "apply": ["self", "operations"],
            "record": ["self", "operations"],
            "reset": ["self"],
            "stop": ["self"],
        }

        for method, parameters in expected.items():
            assert list(inspect.signature(getattr(BaseEngine, method)).parameters) == parameters

    def test_base_engine_declares_the_declared_signatures(self):
        """Operation parameters are ``list[DataOperation]``; the methods return ``None``."""
        start = inspect.signature(BaseEngine.start)
        apply_operations = inspect.signature(BaseEngine.apply)
        record = inspect.signature(BaseEngine.record)

        assert start.parameters["startup"].annotation == list[DataOperation]
        assert apply_operations.parameters["operations"].annotation == list[DataOperation]
        assert record.parameters["operations"].annotation == list[DataOperation]
        assert start.return_annotation is None
        assert apply_operations.return_annotation is None
        assert record.return_annotation is None

    def test_base_engine_declares_the_address_property(self):
        """``address`` is a property returning ``InstanceAddress``."""
        address = inspect.getattr_static(BaseEngine, "address")

        assert isinstance(address, property)
        assert inspect.signature(address.fget).return_annotation is InstanceAddress


class TestBaseEngineLogic:
    """Journal, ordering and failure behavior of the base, driven through the recording fake."""

    def test_start_runs_the_lifecycle_steps_in_order(self):
        """Start builds the container, waits readiness, opens the plane, then applies startup."""
        engine = FakeEngine()
        startup = operation()

        engine.start([startup])

        assert engine.calls == ["build", "ready", "plane", "execute:insert"]
        assert engine.journal == [startup]
        assert engine.started is True

    def test_apply_preserves_order_and_never_records(self):
        """Applied operations execute in order and never land in the journal."""
        engine = FakeEngine()
        first = operation()
        second = operation()

        engine.start([])
        engine.apply([first, second])

        assert engine.executed == [first, second]
        assert engine.journal == []

    def test_record_extends_the_journal_without_executing(self):
        """Recorded operations join the journal in order without executing."""
        engine = FakeEngine()
        startup = operation()
        baseline = operation()

        engine.start([startup])
        engine.record([baseline])

        assert engine.journal == [startup, baseline]
        assert engine.executed == [startup]

    def test_reset_wipes_then_replays_the_journal_through_execute(self):
        """Reset wipes first, then replays the journal through the same execution path."""
        engine = FakeEngine()
        startup = operation()
        baseline = operation()
        applied = operation()

        engine.start([startup])
        engine.record([baseline])
        engine.apply([applied])
        engine.calls.clear()
        engine.executed.clear()

        engine.reset()

        assert engine.calls == ["wipe", "execute:insert", "execute:insert"]
        assert engine.executed == [startup, baseline]

    def test_apply_with_empty_list_is_a_noop(self):
        """An empty apply batch executes nothing."""
        engine = FakeEngine()
        engine.start([])
        engine.calls.clear()

        engine.apply([])

        assert engine.calls == []
        assert engine.executed == []

    def test_reset_with_empty_journal_runs_the_wipe_only(self):
        """Reset over an empty journal wipes without replaying anything."""
        engine = FakeEngine()
        engine.start([])
        engine.apply([operation()])
        engine.calls.clear()
        engine.executed.clear()

        engine.reset()

        assert engine.calls == ["wipe"]
        assert engine.executed == []

    def test_stop_is_safe_twice(self):
        """Stopping a stopped instance is safe and stops the container exactly once."""
        engine = FakeEngine()
        engine.start([])

        engine.stop()
        engine.stop()

        assert engine.containers[0].stops == 1
        assert engine.started is False

    def test_stop_is_safe_when_never_started(self):
        """Stopping an engine that never started raises nothing."""
        engine = FakeEngine()

        engine.stop()

        assert engine.started is False

    def test_raising_execute_surfaces_as_engine_error(self):
        """A raising ``_execute`` wraps into ``EngineError`` naming instance, action and cause."""
        engine = FakeEngine()
        engine.fail_execute = "insert"
        engine.start([])

        with pytest.raises(EngineError, match=r"instance 'db': insert failed: boom") as excinfo:
            engine.apply([operation()])

        assert isinstance(excinfo.value.__cause__, RuntimeError)
        assert excinfo.value.__cause__.args == ("boom",)

    def test_failing_execute_during_start_calls_stop_and_reraises(self):
        """A failed startup operation stops the container, journals nothing and re-raises."""
        engine = FakeEngine()
        engine.fail_execute = "insert"

        with pytest.raises(EngineError, match=r"instance 'db': insert failed: boom"):
            engine.start([operation()])

        assert engine.containers[0].stops == 1
        assert engine.journal == []
        assert engine.started is False

    def test_failing_lifecycle_step_names_the_start_step(self):
        """A failed lifecycle step wraps into ``EngineError`` appending the failed step."""
        engine = FakeEngine()
        engine.fail_open_plane = True

        with pytest.raises(EngineError, match=r"instance 'db': start failed at data-plane open: plane refused"):
            engine.start([])

        assert engine.containers[0].stops == 1
        assert engine.started is False

    def test_address_reads_back_from_the_container(self):
        """The address carries the mapped host and the published host-side port as ``int``."""
        engine = FakeEngine()
        engine.start([])

        address = engine.address

        assert isinstance(address, InstanceAddress)
        assert address.host == "127.0.0.2"
        assert address.port == 5432
        assert isinstance(address.port, int)

    def test_address_before_start_fails_readably(self):
        """Reading the address before start names the instance and the state."""
        engine = FakeEngine()

        with pytest.raises(EngineError, match="before start"):
            assert engine.address

    def test_operations_before_start_fail(self):
        """Executing operations before start completes fails with a readable error."""
        engine = FakeEngine()

        with pytest.raises(EngineError, match=r"instance 'db': apply failed: .*not started"):
            engine.apply([operation()])

        with pytest.raises(EngineError, match=r"instance 'db': reset failed: .*not started"):
            engine.reset()
