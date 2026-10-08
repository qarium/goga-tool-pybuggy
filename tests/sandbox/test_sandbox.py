"""Contract and logic tests for the ``Sandbox`` entity."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox import sandbox as sandbox_module
from goga_tool_pybuggy.sandbox.config import (
    InstanceConfig,
    SandboxConfig,
    ServiceConfig,
    StartupData,
    TopicConfig,
)
from goga_tool_pybuggy.sandbox.data import PostgresInstance
from goga_tool_pybuggy.sandbox.engines import DataOperation, InstanceAddress

from .conftest import FakeEngine, FakeNetwork, FakeService


def sandbox_config() -> SandboxConfig:
    """Build the sample sandbox configuration of the harness scenario.

    The scenario carries one service of every kind — vault, http, kafka with inline topics,
    postgresql — each of the data-carrying kinds with its startup data — and one instance
    env placeholder per service, so start exercises the startup-op assembly, the address
    render and the env hand-off end to end.

    Returns:
        A ``SandboxConfig`` declaring the ``secrets``, ``payments``, ``events`` and ``db``
        services and one instance under test.
    """
    return SandboxConfig(
        instance=InstanceConfig(
            image="my-service:latest",
            env={
                "VAULT_ADDR": "http://{{secrets.host}}:{{secrets.port}}",
                "PAYMENTS_URL": "http://{{payments.host}}:{{payments.port}}/pay",
                "KAFKA_BOOTSTRAP": "{{events.host}}:{{events.port}}",
                "DATABASE_URL": "postgres://{{db.host}}:{{db.port}}/x",
            },
            port=8080,
        ),
        services={
            "secrets": ServiceConfig(name="secrets", kind="vault"),
            "payments": ServiceConfig(name="payments", kind="http"),
            "events": ServiceConfig(name="events", kind="kafka", topics=[TopicConfig(name="orders.events")]),
            "db": ServiceConfig(name="db", kind="postgresql"),
        },
        data=StartupData(
            vault={"secrets": [{"path": "kv/app", "data": {"token": "abc"}}]},
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

        raise RuntimeError(f"service '{self.name}': stop failed: fake refused to stop")


class SandboxHarness:
    """The sample sandbox scenario wired over recording fakes.

    Attributes:
        config: The sample configuration the sandbox was built from.
        engines: The fake engines injected through the ``build_engine`` seam, keyed by name.
        service: The fake instance container injected through the ``ServiceContainer`` seam.
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
            service_alive: The liveness every ``alive()`` probe of the fake instance reports.
            service_logs: The diagnostic output every ``logs()`` call of the fake instance
                reports.
            fail_db_stop: Make the db engine's ``stop`` raise — the guarded-teardown scenario.
        """
        self.events: list[str] = []
        self.config = sandbox_config()
        db_engine = RefusingStopEngine if fail_db_stop else FakeEngine
        self.engines: dict[str, FakeEngine] = {
            "secrets": FakeEngine(
                name="secrets",
                kind="vault",
                address=InstanceAddress(host="127.0.0.4", port=8200),
                events=self.events,
            ),
            "payments": FakeEngine(
                name="payments",
                kind="http",
                address=InstanceAddress(host="127.0.0.3", port=8080),
                events=self.events,
                fail_start=fail_payments_start,
            ),
            "events": FakeEngine(
                name="events",
                kind="kafka",
                address=InstanceAddress(host="127.0.0.5", port=9092),
                events=self.events,
            ),
            "db": db_engine(
                name="db",
                kind="postgresql",
                address=InstanceAddress(host="127.0.0.2", port=5432),
                events=self.events,
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
        monkeypatch.setattr(sandbox_module, "build_engine", lambda service_config: self.engines[service_config.name])
        monkeypatch.setattr(sandbox_module, "ServiceContainer", lambda _instance_config: self.service)
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
        """``base_url`` resolves from the started instance address right after start."""
        assert started.sandbox.base_url == "http://127.0.0.9:9000"


class TestSandboxStart:
    """Startup composition of the session runtime."""

    def test_start_runs_runtime_check_then_engines_then_instance(self, started: SandboxHarness):
        """Start probes the runtime, starts the engines in declaration order, then the instance."""
        assert started.events == [
            "runtime-check",
            "engine:secrets:start",
            "engine:payments:start",
            "engine:events:start",
            "engine:db:start",
            "instance:start",
        ]

    def test_start_passes_startup_operations_assembled_from_startup_data(self, started: SandboxHarness):
        """Each engine starts with its startup data converted to operations per the section mapping."""
        assert started.engines["secrets"].journaled == [
            DataOperation(
                instance="secrets",
                kind="vault",
                action="put",
                payload={"path": "kv/app", "data": {"token": "abc"}},
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
        assert started.engines["db"].journaled == [
            DataOperation(
                instance="db",
                kind="postgresql",
                action="insert",
                payload={"sql": "CREATE TABLE orders (id int PRIMARY KEY)"},
            )
        ]

    def test_sandbox_start_applies_startup_data_in_fixed_order(self, monkeypatch: pytest.MonkeyPatch):
        """Startup data reaches each engine in the fixed vault -> http -> postgres order.

        The kafka engine's startup list is empty — its topology comes from the inline topic
        declaration at container build; the render consumes the mapped service addresses;
        the instance container starts last with the rendered env.
        """
        harness = SandboxHarness()
        captured: list[dict[str, InstanceAddress]] = []
        real_render = sandbox_module.render_service_env

        def recording_render(env: dict[str, str], addresses: dict[str, InstanceAddress]) -> dict[str, str]:
            captured.append(addresses)

            return real_render(env, addresses)

        monkeypatch.setattr(sandbox_module, "render_service_env", recording_render)

        harness.wire(monkeypatch).start()

        assert captured == [
            {
                "secrets": InstanceAddress(host="127.0.0.4", port=8200),
                "payments": InstanceAddress(host="127.0.0.3", port=8080),
                "events": InstanceAddress(host="127.0.0.5", port=9092),
                "db": InstanceAddress(host="127.0.0.2", port=5432),
            }
        ]
        assert [(op.action, op.kind) for op in harness.engines["secrets"].journaled] == [("put", "vault")]
        assert [(op.action, op.kind) for op in harness.engines["payments"].journaled] == [("stub", "http")]
        assert [(op.action, op.kind) for op in harness.engines["db"].journaled] == [("insert", "postgresql")]
        assert harness.engines["events"].journaled == []
        assert harness.events[-1] == "instance:start"
        assert harness.service.started_env == {
            "VAULT_ADDR": "http://127.0.0.4:8200",
            "PAYMENTS_URL": "http://127.0.0.3:8080/pay",
            "KAFKA_BOOTSTRAP": "127.0.0.5:9092",
            "DATABASE_URL": "postgres://127.0.0.2:5432/x",
        }

    def test_startup_operations_assemble_put_stub_sql_within_one_service(self):
        """One service name under all three data sections assembles put -> stub -> sql."""
        config = SandboxConfig(
            instance=InstanceConfig(image="my-service:latest", env={}, port=8080),
            services={"multi": ServiceConfig(name="multi", kind="vault")},
            data=StartupData(
                vault={"multi": [{"path": "kv/a", "data": {"x": 1}}]},
                http={"multi": [{"request": {"method": "GET", "url": "/a"}, "response": {"status": 200}}]},
                postgres={"multi": ["SELECT 1"]},
            ),
        )

        operations = sandbox_module.Sandbox(config)._startup_operations("multi")

        assert [(op.action, op.kind) for op in operations] == [
            ("put", "vault"),
            ("stub", "http"),
            ("insert", "postgresql"),
        ]

    def test_sandbox_uses_instance_and_services_keys(self, monkeypatch: pytest.MonkeyPatch):
        """The constructor builds the engines from ``config.services`` and the container from
        ``config.instance``; the view factories resolve names against the services."""
        harness = SandboxHarness()
        built_from: list[str] = []
        built_container_configs: list[InstanceConfig] = []

        def build_spy(service_config: ServiceConfig) -> FakeEngine:
            built_from.append(service_config.name)

            return harness.engines[service_config.name]

        def container_spy(instance_config: InstanceConfig) -> FakeService:
            built_container_configs.append(instance_config)

            return harness.service

        monkeypatch.setattr(sandbox_module, "build_engine", build_spy)
        monkeypatch.setattr(sandbox_module, "ServiceContainer", container_spy)
        monkeypatch.setattr(sandbox_module, "check_runtime", lambda: None)
        monkeypatch.setattr(sandbox_module, "Network", FakeNetwork)

        sandbox = sandbox_module.Sandbox(harness.config)
        sandbox.start()

        assert built_from == ["secrets", "payments", "events", "db"]
        assert built_container_configs == [harness.config.instance]

        view = sandbox.postgresql("db")

        assert isinstance(view, PostgresInstance)
        assert (view.name, view.host, view.port) == ("db", "127.0.0.2", 5432)

        view.insert("orders", [{"id": 3}])
        sandbox.apply_pending()

        assert harness.engines["db"].applied[-1].payload == {"table": "orders", "rows": [{"id": 3}]}

    def test_start_renders_env_and_hands_it_to_the_instance(self, started: SandboxHarness):
        """The instance env placeholders render against the started service addresses."""
        assert started.service.started_env == {
            "VAULT_ADDR": "http://127.0.0.4:8200",
            "PAYMENTS_URL": "http://127.0.0.3:8080/pay",
            "KAFKA_BOOTSTRAP": "127.0.0.5:9092",
            "DATABASE_URL": "postgres://127.0.0.2:5432/x",
        }

    def test_start_creates_one_labeled_network_and_hands_it_to_the_instance(self, started: SandboxHarness):
        """One labeled network per session: created at start, carried into the instance start."""
        [network] = FakeNetwork.created

        assert network.docker_network_kw == {"labels": {"pybuggy-sandbox": "true"}}
        assert started.sandbox._network is network
        assert started.service.started_network is network

    def test_start_failure_stops_started_parts_and_reraises(self, monkeypatch: pytest.MonkeyPatch):
        """A failing service start propagates and removes everything started so far."""
        harness = SandboxHarness(fail_payments_start=True)
        sandbox = harness.wire(monkeypatch)

        with pytest.raises(RuntimeError, match="refused to start"):
            sandbox.start()

        assert harness.events == [
            "runtime-check",
            "engine:secrets:start",
            "engine:payments:start",
            "instance:stop",
            "engine:db:stop",
            "engine:events:stop",
            "engine:payments:stop",
            "engine:secrets:stop",
        ]


class TestSandboxApplyPending:
    """Batch draining of the session runtime."""

    def test_apply_pending_groups_by_service_preserving_order(self, started: SandboxHarness):
        """Declared operations apply per service, in accumulation order."""
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
        """A view carries the service identity and address, and declares into the live batch."""
        view = started.sandbox.postgresql("db")

        assert isinstance(view, PostgresInstance)
        assert (view.name, view.host, view.port) == ("db", "127.0.0.2", 5432)

        view.insert("orders", [{"id": 3}])
        started.sandbox.apply_pending()

        assert started.engines["db"].applied[-1].payload == {"table": "orders", "rows": [{"id": 3}]}

    def test_sandbox_view_kind_mismatch_lists_configured(self, started: SandboxHarness):
        """A factory of another kind fails fast naming the service and the configured ones."""
        with pytest.raises(ValueError, match=r"no kafka service named 'db'"):
            started.sandbox.kafka("db")

    def test_sandbox_view_unknown_name_lists_configured(self, started: SandboxHarness):
        """An unknown service name fails fast listing the configured services."""
        with pytest.raises(ValueError, match=r"no postgresql service named 'ghost'.*db \(postgresql\)"):
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

    def test_clear_resets_every_engine_and_never_touches_the_instance(self, started: SandboxHarness):
        """Clear resets every engine in declaration order; the instance keeps running."""
        started.events.clear()

        started.sandbox.clear()

        assert started.events == [
            "engine:secrets:reset",
            "engine:payments:reset",
            "engine:events:reset",
            "engine:db:reset",
        ]
        assert started.service.stopped is False
        assert started.service.started is True

    def test_stop_removes_the_network_after_the_containers(self, started: SandboxHarness):
        """Tearing the session down removes the sandbox network after the containers left it."""
        [network] = FakeNetwork.created

        started.sandbox.stop()

        assert FakeNetwork.removed == [network]
        assert started.sandbox._network is None

    def test_stop_stops_instance_then_engines_in_reverse_order_and_is_idempotent(self, started: SandboxHarness):
        """Stop removes the instance first, then the engines in reverse start order; twice is safe."""
        started.events.clear()

        started.sandbox.stop()

        assert started.events == [
            "instance:stop",
            "engine:db:stop",
            "engine:events:stop",
            "engine:payments:stop",
            "engine:secrets:stop",
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

        assert harness.events == [
            "instance:stop",
            "engine:db:stop",
            "engine:events:stop",
            "engine:payments:stop",
            "engine:secrets:stop",
        ]
        assert harness.service.stopped is True
        assert harness.engines["payments"].stopped is True

        harness.sandbox.stop()  # still idempotent after the failed removal


class TestSandboxEnsureService:
    """Died-instance guard of the session runtime."""

    def test_ensure_service_raises_naming_instance_and_logs_when_died(self, monkeypatch: pytest.MonkeyPatch):
        """A died instance fails fast naming the instance image and attaching its output."""
        harness = SandboxHarness(service_alive=False, service_logs="OOMKilled after 3s")

        harness.wire(monkeypatch).start()

        with pytest.raises(RuntimeError, match="died") as excinfo:
            harness.sandbox.ensure_service()

        assert "my-service:latest" in str(excinfo.value)
        assert "OOMKilled after 3s" in str(excinfo.value)

    def test_ensure_service_is_noop_while_alive(self, started: SandboxHarness):
        """While the instance runs the guard returns without raising."""
        assert started.sandbox.ensure_service() is None
