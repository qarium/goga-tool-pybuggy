"""Contract and logic tests for the ``BaseEngine`` entity and ``EngineError``."""

import inspect
import socket
import time

import pytest
from goga_tool_pybuggy.sandbox.config import ProbeConfig, ServiceConfig
from goga_tool_pybuggy.sandbox.engines import BaseEngine, DataOperation, EngineError, InstanceAddress
from goga_tool_pybuggy.sandbox.engines import base as base_module


class FakeContainer:
    """Container double exposing the testcontainers accessors ``BaseEngine`` reads."""

    def __init__(self, host: str = "127.0.0.2", port: int = 5432) -> None:
        self.host = host
        self.port = port
        self.stops = 0
        self.network: object | None = None
        self.network_aliases: list[str] = []

    def start(self) -> "FakeContainer":
        return self

    def stop(self, force: bool = True, delete_volume: bool = True) -> None:
        self.stops += 1

    def with_network(self, network: object) -> "FakeContainer":
        """Record the network join.

        Args:
            network: The sandbox network handed to the container.
        """
        self.network = network

        return self

    def with_network_aliases(self, *aliases: str) -> "FakeContainer":
        """Record the network aliases.

        Args:
            aliases: The aliases the container joins the network under.
        """
        self.network_aliases.extend(aliases)

        return self

    def get_container_host_ip(self) -> str:
        return self.host

    def get_exposed_port(self, port: int) -> str:
        return str(self.port)


class FakeEngine(BaseEngine):
    """Recording engine double — kind hooks record calls instead of touching containers."""

    _container_port = 5432

    def __init__(self, name: str = "db", kind: str = "postgresql", probe: ProbeConfig | None = None) -> None:
        super().__init__(ServiceConfig(name=name, kind=kind, probe=probe))
        self.calls: list[str] = []
        self.executed: list[DataOperation] = []
        self.containers: list[FakeContainer] = []
        self.fail_execute: str | None = None
        self.fail_open_plane = False
        self.readiness_failure: str | None = None
        self.wipe_failure: str | None = None

    def _build_container(self) -> FakeContainer:
        self.calls.append("build")
        container = FakeContainer()
        self.containers.append(container)

        return container

    def _wait_ready(self) -> None:
        self.calls.append("ready")

        if self.readiness_failure is not None:
            self._probe_until(0.1, 0.02, attempt=lambda: False, failure=self.readiness_failure)

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

        if self.wipe_failure is not None:
            self._probe_until(0.1, 0.02, attempt=lambda: False, failure=self.wipe_failure)

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
        A sample ``DataOperation`` targeted at the ``db`` service.
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

    def test_base_engine_constructs_with_the_service_config(self):
        """``BaseEngine`` takes the service config and keeps it as ``config``."""
        config = ServiceConfig(name="db", kind="postgresql")
        engine = BaseEngine(config)

        assert engine.config is config

    def test_base_engine_declares_the_contract_constructor(self):
        """The constructor signature is ``__init__(self, config: ServiceConfig)``."""
        signature = inspect.signature(BaseEngine.__init__)

        assert list(signature.parameters) == ["self", "config"]
        assert signature.parameters["config"].annotation is ServiceConfig

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

    def test_base_engine_declares_the_readiness_bounds_property(self):
        """``_readiness_bounds`` is a property returning a ``(float, float)`` tuple."""
        bounds = inspect.getattr_static(BaseEngine, "_readiness_bounds")

        assert isinstance(bounds, property)
        assert inspect.signature(bounds.fget).return_annotation == tuple[float, float]

    def test_base_engine_declares_the_bounded_probe_loop(self):
        """``_probe_until`` takes the declared bounds, the attempt and the failure fragment."""
        signature = inspect.signature(BaseEngine._probe_until)

        assert list(signature.parameters) == ["self", "timeout", "interval", "attempt", "failure"]
        assert signature.parameters["timeout"].annotation is float
        assert signature.parameters["interval"].annotation is float
        assert signature.return_annotation is None


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

    def test_base_readiness_bounds_default_and_override(self):
        """Without a probe the bounds are the 30.0/0.5 defaults; a probe overrides both (D6)."""
        default_engine = FakeEngine(name="db", kind="postgresql")
        declared_engine = FakeEngine(name="db", kind="postgresql", probe=ProbeConfig(timeout=45.0, interval=1.0))

        assert default_engine._readiness_bounds == (30.0, 0.5)
        assert declared_engine._readiness_bounds == (45.0, 1.0)

    def test_probe_until_expires_naming_the_failure_and_deadline(self):
        """An always-failing attempt expires at the deadline naming the check and ``{timeout:g}s``."""
        engine = FakeEngine()
        started = time.monotonic()

        with pytest.raises(RuntimeError, match=r"db did not become ready within 0\.2s"):
            engine._probe_until(0.2, 0.05, attempt=lambda: False, failure="db did not become ready")

        elapsed = time.monotonic() - started
        assert elapsed >= 0.2
        assert elapsed < 1.0

    def test_probe_until_returns_on_the_first_successful_attempt(self):
        """The first successful attempt returns immediately — no interval sleep after success."""
        engine = FakeEngine()
        attempts: list[int] = []

        def attempt() -> bool:
            attempts.append(1)

            return True

        engine._probe_until(30.0, 0.5, attempt=attempt, failure="never ready")

        assert attempts == [1]

    def test_probe_until_honors_the_declared_interval(self, monkeypatch: pytest.MonkeyPatch):
        """One interval sleep follows every failed attempt until one succeeds."""
        sleeps: list[float] = []
        monkeypatch.setattr(base_module, "sleep", sleeps.append)
        attempts: list[int] = []

        def attempt() -> bool:
            attempts.append(1)

            return len(attempts) == 3

        engine = FakeEngine()
        engine._probe_until(30.0, 0.05, attempt=attempt, failure="never ready")

        assert len(attempts) == 3
        assert sleeps == [0.05, 0.05]


class TestAttachNetwork:
    """The sandbox-network join of the built container — the shared helper of the kind engines."""

    def test_attach_joins_the_network_under_the_service_name_alias(self):
        """A built container joins the network under its service-name alias — the in-network
        DNS name the sandbox network hands it."""
        engine = FakeEngine(name="db")
        container = FakeContainer()
        network = object()

        engine._network = network
        engine._attach_network(container)

        assert container.network is network
        assert container.network_aliases == ["db"]

    def test_attach_without_a_network_is_a_no_op(self):
        """Without a network the container stays unjoined — engines stay usable standalone."""
        engine = FakeEngine()
        container = FakeContainer()

        engine._attach_network(container)

        assert container.network is None
        assert container.network_aliases == []


class TestReservePort:
    """The free-port reservation probe of the restart-stable engines."""

    def test_reserve_port_returns_a_free_tcp_port(self):
        """The reserved port is a bindable int in the TCP range — the reservation contract."""
        port = base_module.reserve_port()

        assert isinstance(port, int)
        assert 0 < port < 65536

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as bind:
            bind.bind(("", port))

    def test_readiness_expiry_surfaces_as_engine_error_through_the_start_wrapper(self):
        """A readiness deadline expiry wraps into ``EngineError`` naming service, step and check."""
        engine = FakeEngine()
        engine.readiness_failure = "the port did not accept connections"

        with pytest.raises(
            EngineError,
            match=r"service 'db': start failed at readiness wait: the port did not accept connections within 0\.1s",
        ):
            engine.start([])

        assert engine.containers[0].stops == 1
        assert engine.started is False

    def test_wipe_expiry_surfaces_as_engine_error_through_the_reset_wrapper(self):
        """A wipe deadline expiry wraps into ``EngineError`` naming service, step and check."""
        engine = FakeEngine()
        engine.start([])
        engine.wipe_failure = "the container did not restart"

        with pytest.raises(
            EngineError,
            match=r"service 'db': reset failed at wipe: the container did not restart within 0\.1s",
        ):
            engine.reset()

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
        """Stopping a stopped service is safe and stops the container exactly once."""
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
        """A raising ``_execute`` wraps into ``EngineError`` naming service, action and cause."""
        engine = FakeEngine()
        engine.fail_execute = "insert"
        engine.start([])

        with pytest.raises(EngineError, match=r"service 'db': insert failed: boom") as excinfo:
            engine.apply([operation()])

        assert isinstance(excinfo.value.__cause__, RuntimeError)
        assert excinfo.value.__cause__.args == ("boom",)

    def test_failing_execute_during_start_calls_stop_and_reraises(self):
        """A failed startup operation stops the container, journals nothing and re-raises."""
        engine = FakeEngine()
        engine.fail_execute = "insert"

        with pytest.raises(EngineError, match=r"service 'db': insert failed: boom"):
            engine.start([operation()])

        assert engine.containers[0].stops == 1
        assert engine.journal == []
        assert engine.started is False

    def test_failing_lifecycle_step_names_the_start_step(self):
        """A failed lifecycle step wraps into ``EngineError`` appending the failed step."""
        engine = FakeEngine()
        engine.fail_open_plane = True

        with pytest.raises(EngineError, match=r"service 'db': start failed at data-plane open: plane refused"):
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
        """Reading the address before start names the service and the state."""
        engine = FakeEngine()

        with pytest.raises(EngineError, match="before start"):
            assert engine.address

    def test_operations_before_start_fail(self):
        """Executing operations before start completes fails with a readable error."""
        engine = FakeEngine()

        with pytest.raises(EngineError, match=r"service 'db': apply failed: .*not started"):
            engine.apply([operation()])

        with pytest.raises(EngineError, match=r"service 'db': reset failed: .*not started"):
            engine.reset()
