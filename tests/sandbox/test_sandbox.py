"""Contract and logic tests for the ``Sandbox`` entity."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox import sandbox as sandbox_module
from goga_tool_pybuggy.sandbox.config import InstanceConfig, SandboxConfig, ServiceConfig, StartupData
from goga_tool_pybuggy.sandbox.data import PostgresInstance
from goga_tool_pybuggy.sandbox.engines import DataOperation, InstanceAddress

from .conftest import FakeEngine, FakeNetwork, FakeService


def sandbox_config() -> SandboxConfig:
    """Build the sample sandbox configuration of the harness scenario.

    The scenario carries one postgresql and one http dependency — each with startup data —
    and one service env placeholder per instance, so start exercises the startup-op
    assembly, the address render and the env hand-off end to end.

    Returns:
        A ``SandboxConfig`` declaring the ``db`` and ``payments`` instances and one service.
    """
    return SandboxConfig(
        service=ServiceConfig(
            image="my-service:latest",
            env={
                "DATABASE_URL": "postgres://{{db.host}}:{{db.port}}/x",
                "PAYMENTS_URL": "http://{{payments.host}}:{{payments.port}}/pay",
            },
            port=8080,
            health=None,
        ),
        instances={
            "db": InstanceConfig(name="db", kind="postgresql", image=None),
            "payments": InstanceConfig(name="payments", kind="http", image=None),
        },
        data=StartupData(
            http={"payments": [{"request": {"method": "GET", "url": "/pay"}, "response": {"status": 200}}]},
            postgres={"db": ["CREATE TABLE orders (id int PRIMARY KEY)"]},
        ),
    )


class RefusingStopEngine(FakeEngine):
    """Engine double whose stop always raises — the guarded-teardown scenario.

    The refusal raises after the lifecycle event was recorded, so the teardown-order
    assertions still see the stop attempt.
    """

    def stop(self) -> None:
        """Record the stop attempt, then refuse it.

        Raises:
            RuntimeError: Always — the guarded-teardown scenario.
        """
        self._emit("stop")

        raise RuntimeError(f"instance '{self.name}': stop failed: fake refused to stop")


class SandboxHarness:
    """The sample sandbox scenario wired over recording fakes.

    Attributes:
        config: The sample configuration the sandbox was built from.
        engines: The fake engines injected through the ``build_engine`` seam, keyed by name.
        service: The fake service injected through the ``ServiceContainer`` seam.
        events: The shared sink recording the lifecycle call sequence across the fakes.
        sandbox: The wired session sandbox; set by ``wire``.
    """

    def __init__(
        self,
        fail_payments_start: bool = False,
        service_alive: bool = True,
        service_logs: str = "",
        fail_db_stop: bool = False,
    ) -> None:
        """Initialize the fakes of the sample scenario.

        Args:
            fail_payments_start: Make the payments engine's ``start`` raise — the failed-start
                cleanup scenario.
            service_alive: The liveness every ``alive()`` probe of the fake service reports.
            service_logs: The diagnostic output every ``logs()`` call of the fake service reports.
            fail_db_stop: Make the db engine's ``stop`` raise — the guarded-teardown scenario.
        """
        self.events: list[str] = []
        self.config = sandbox_config()
        db_engine = RefusingStopEngine if fail_db_stop else FakeEngine
        self.engines: dict[str, FakeEngine] = {
            "db": db_engine(
                name="db",
                kind="postgresql",
                address=InstanceAddress(host="127.0.0.2", port=5432),
                events=self.events,
            ),
            "payments": FakeEngine(
                name="payments",
                kind="http",
                address=InstanceAddress(host="127.0.0.3", port=8080),
                events=self.events,
                fail_start=fail_payments_start,
            ),
        }
        self.service = FakeService(
            alive=service_alive, logs=service_logs, host="127.0.0.9", port=9000, events=self.events
        )

    def wire(self, monkeypatch: pytest.MonkeyPatch) -> sandbox_module.Sandbox:
        """Patch the module seams to these fakes and build the sandbox over them.

        Args:
            monkeypatch: The pytest monkeypatch fixture replacing the module-level seams.

        Returns:
            The session sandbox built over the recording fakes.
        """
        monkeypatch.setattr(sandbox_module, "build_engine", lambda instance_config: self.engines[instance_config.name])
        monkeypatch.setattr(sandbox_module, "ServiceContainer", lambda _service_config: self.service)
        monkeypatch.setattr(sandbox_module, "check_runtime", lambda: self.events.append("runtime-check"))
        monkeypatch.setattr(sandbox_module, "Network", FakeNetwork)
        FakeNetwork.created.clear()
        FakeNetwork.removed.clear()

        self.sandbox: sandbox_module.Sandbox = sandbox_module.Sandbox(self.config)

        return self.sandbox


@pytest.fixture
def started(monkeypatch: pytest.MonkeyPatch) -> SandboxHarness:
    """The sample scenario wired and started over the recording fakes."""
    harness = SandboxHarness()

    harness.wire(monkeypatch).start()

    return harness


class TestSandboxContract:
    """Declared API of the ``Sandbox`` entity."""

    def test_sandbox_is_importable_from_sandbox_module(self):
        """``Sandbox`` lives in ``goga_tool_pybuggy.sandbox.sandbox``."""
        from goga_tool_pybuggy.sandbox.sandbox import Sandbox

        assert inspect.isclass(Sandbox)

    def test_sandbox_constructor_takes_the_config(self):
        """The constructor takes exactly ``config`` — the validated sandbox configuration."""
        from goga_tool_pybuggy.sandbox.sandbox import Sandbox

        parameters = list(inspect.signature(Sandbox.__init__).parameters)

        assert parameters == ["self", "config"]

    def test_sandbox_exposes_the_declared_surface(self):
        """Every declared method exists, and ``base_url`` is a property."""
        from goga_tool_pybuggy.sandbox.sandbox import Sandbox

        for name in (
            "start",
            "stop",
            "clear",
            "baseline",
            "apply_pending",
            "ensure_service",
            "new_test_batch",
            "postgresql",
            "kafka",
            "vault",
            "http",
        ):
            assert callable(getattr(Sandbox, name)), name

        assert isinstance(inspect.getattr_static(Sandbox, "base_url"), property)

    def test_sandbox_methods_carry_the_declared_signatures(self):
        """Lifecycle methods take no arguments; the view factories take exactly ``name``."""
        from goga_tool_pybuggy.sandbox.sandbox import Sandbox

        for name in ("start", "stop", "clear", "baseline", "apply_pending", "ensure_service", "new_test_batch"):
            parameters = list(inspect.signature(getattr(Sandbox, name)).parameters)

            assert parameters == ["self"], name

        for name in ("postgresql", "kafka", "vault", "http"):
            parameters = list(inspect.signature(getattr(Sandbox, name)).parameters)

            assert parameters == ["self", "name"], name

    def test_sandbox_base_url_readable_after_start(self, started: SandboxHarness):
        """``base_url`` resolves from the started service address right after start."""
        assert started.sandbox.base_url == "http://127.0.0.9:9000"


class TestSandboxStart:
    """Startup composition of the session runtime."""

    def test_start_runs_runtime_check_then_engines_then_service(self, started: SandboxHarness):
        """Start probes the runtime, starts the engines in declaration order, then the service."""
        assert started.events == [
            "runtime-check",
            "engine:db:start",
            "engine:payments:start",
            "service:start",
        ]

    def test_start_passes_startup_operations_assembled_from_startup_data(self, started: SandboxHarness):
        """Each engine starts with its startup data converted to operations per the section mapping."""
        assert started.engines["db"].journaled == [
            DataOperation(
                instance="db",
                kind="postgresql",
                action="insert",
                payload={"sql": "CREATE TABLE orders (id int PRIMARY KEY)"},
            )
        ]
        assert started.engines["payments"].journaled == [
            DataOperation(
                instance="payments",
                kind="http",
                action="stub",
                payload={"request": {"method": "GET", "url": "/pay"}, "response": {"status": 200}},
            )
        ]

    def test_start_renders_env_and_hands_it_to_the_service(self, started: SandboxHarness):
        """The service env placeholders render against the started instance addresses."""
        assert started.service.started_env == {
            "DATABASE_URL": "postgres://127.0.0.2:5432/x",
            "PAYMENTS_URL": "http://127.0.0.3:8080/pay",
        }

    def test_start_creates_one_labeled_network_and_hands_it_to_the_service(self, started: SandboxHarness):
        """One labeled network per session: created at start, carried into the service start."""
        [network] = FakeNetwork.created

        assert network.docker_network_kw == {"labels": {"pybuggy-sandbox": "true"}}
        assert started.sandbox._network is network
        assert started.service.started_network is network

    def test_start_failure_stops_started_parts_and_reraises(self, monkeypatch: pytest.MonkeyPatch):
        """A failing instance start propagates and removes everything started so far."""
        harness = SandboxHarness(fail_payments_start=True)
        sandbox = harness.wire(monkeypatch)

        with pytest.raises(RuntimeError, match="refused to start"):
            sandbox.start()

        assert harness.events == [
            "runtime-check",
            "engine:db:start",
            "engine:payments:start",
            "service:stop",
            "engine:payments:stop",
            "engine:db:stop",
        ]


class TestSandboxApplyPending:
    """Batch draining of the session runtime."""

    def test_apply_pending_groups_by_instance_preserving_order(self, started: SandboxHarness):
        """Declared operations apply per instance, in accumulation order."""
        started.sandbox.postgresql("db").insert("orders", [{"id": 1}])
        started.sandbox.http("payments").stub({"request": {"method": "GET", "url": "/x"}, "response": {"status": 200}})
        started.sandbox.postgresql("db").insert("customers", [{"id": 7}])

        started.sandbox.apply_pending()

        assert started.engines["db"].applied == [
            DataOperation(
                instance="db", kind="postgresql", action="insert", payload={"table": "orders", "rows": [{"id": 1}]}
            ),
            DataOperation(
                instance="db", kind="postgresql", action="insert", payload={"table": "customers", "rows": [{"id": 7}]}
            ),
        ]
        assert started.engines["payments"].applied == [
            DataOperation(
                instance="payments",
                kind="http",
                action="stub",
                payload={"request": {"method": "GET", "url": "/x"}, "response": {"status": 200}},
            )
        ]

    def test_apply_pending_drains_the_batch(self, started: SandboxHarness):
        """A second apply after the drain applies nothing — the batch is empty."""
        started.sandbox.postgresql("db").insert("orders", [{"id": 1}])

        started.sandbox.apply_pending()
        started.sandbox.apply_pending()

        assert len(started.engines["db"].applied) == 1


class TestSandboxViews:
    """View factories of the session runtime."""

    def test_view_factories_bind_views_to_the_current_batch(self, started: SandboxHarness):
        """A view carries the instance identity and address, and declares into the live batch."""
        view = started.sandbox.postgresql("db")

        assert isinstance(view, PostgresInstance)
        assert (view.name, view.host, view.port) == ("db", "127.0.0.2", 5432)

        view.insert("orders", [{"id": 3}])
        started.sandbox.apply_pending()

        assert started.engines["db"].applied[-1].payload == {"table": "orders", "rows": [{"id": 3}]}

    def test_sandbox_view_kind_mismatch_lists_configured(self, started: SandboxHarness):
        """A factory of another kind fails fast naming the instance and the configured ones."""
        with pytest.raises(ValueError, match=r"kafka.*db"):
            started.sandbox.kafka("db")

    def test_sandbox_view_unknown_name_lists_configured(self, started: SandboxHarness):
        """An unknown instance name fails fast listing the configured instances."""
        with pytest.raises(ValueError, match=r"postgresql.*ghost.*db \(postgresql\)"):
            started.sandbox.postgresql("ghost")


class TestSandboxLifecycle:
    """Per-test and session lifecycle of the session runtime."""

    def test_new_test_batch_replaces_the_batch(self, started: SandboxHarness):
        """Operations declared before the batch replacement never apply."""
        stale = started.sandbox.postgresql("db")

        stale.insert("orders", [{"id": 1}])
        started.sandbox.new_test_batch()
        started.sandbox.postgresql("db").insert("orders", [{"id": 2}])
        started.sandbox.apply_pending()

        assert started.engines["db"].applied == [
            DataOperation(
                instance="db", kind="postgresql", action="insert", payload={"table": "orders", "rows": [{"id": 2}]}
            )
        ]

    def test_clear_resets_every_engine_and_never_touches_the_service(self, started: SandboxHarness):
        """Clear resets every engine in declaration order; the service keeps running."""
        started.events.clear()

        started.sandbox.clear()

        assert started.events == ["engine:db:reset", "engine:payments:reset"]
        assert started.service.stopped is False
        assert started.service.started is True

    def test_stop_removes_the_network_after_the_containers(self, started: SandboxHarness):
        """Tearing the session down removes the sandbox network after the containers left it."""
        [network] = FakeNetwork.created

        started.sandbox.stop()

        assert FakeNetwork.removed == [network]
        assert started.sandbox._network is None

    def test_stop_stops_service_then_engines_in_reverse_order_and_is_idempotent(self, started: SandboxHarness):
        """Stop removes the service first, then the engines in reverse start order; twice is safe."""
        started.events.clear()

        started.sandbox.stop()

        assert started.events == [
            "service:stop",
            "engine:payments:stop",
            "engine:db:stop",
        ]

        started.sandbox.stop()

        assert all(engine.stopped for engine in started.engines.values())
        assert started.service.stopped is True

    def test_stop_survives_a_failing_engine_stop_and_removes_the_rest(self, monkeypatch: pytest.MonkeyPatch):
        """One engine's failing stop never blocks the remaining removals or raises."""
        harness = SandboxHarness(fail_db_stop=True)
        harness.wire(monkeypatch).start()
        harness.events.clear()

        harness.sandbox.stop()  # must not raise although the db engine's stop fails

        assert harness.events == ["service:stop", "engine:payments:stop", "engine:db:stop"]
        assert harness.service.stopped is True
        assert harness.engines["payments"].stopped is True

        harness.sandbox.stop()  # still idempotent after the failed removal


class TestSandboxEnsureService:
    """Died-service guard of the session runtime."""

    def test_ensure_service_raises_naming_service_and_logs_when_died(self, monkeypatch: pytest.MonkeyPatch):
        """A died service fails fast naming the service image and attaching its output."""
        harness = SandboxHarness(service_alive=False, service_logs="OOMKilled after 3s")

        harness.wire(monkeypatch).start()

        with pytest.raises(RuntimeError, match="died") as excinfo:
            harness.sandbox.ensure_service()

        assert "my-service:latest" in str(excinfo.value)
        assert "OOMKilled after 3s" in str(excinfo.value)

    def test_ensure_service_is_noop_while_alive(self, started: SandboxHarness):
        """While the service runs the guard returns without raising."""
        assert started.sandbox.ensure_service() is None
