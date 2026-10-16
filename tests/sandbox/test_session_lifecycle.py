"""Integration tests for the configured sandbox plugin session lifecycle.

Cross-entity scenarios spanning the plugin fixtures, the session runtime, the per-test data
batch, the service views, and the preset enqueue: the configured flow from the lazy session
start to the finalization stop over the relocated document with inline kafka topics and probe
declarations, the failure-cleanup guarantee of a failed start, the readable surfacing of a
failing operation, the reset-then-preset ordering within one service group, and —
docker-gated — the live session over the pinned mocks.
"""

import json
import pathlib
from collections.abc import Callable
from typing import Any

import pytest
import requests
from goga_tool_pybuggy.plugin import SandboxPlugin
from goga_tool_pybuggy.sandbox import sandbox as sandbox_module
from goga_tool_pybuggy.sandbox.engines import DataOperation, EngineError, InstanceAddress
from kafka import KafkaConsumer
from yaml import full_load

from .conftest import FakeEngine, FakeNetwork, FakeService, requires_docker

SESSION_DOCUMENT = """\
instance:
  image: my-service:latest
  port: 8080
  probe:
    path: /healthz
  env:
    VAULT_ADDR: "http://{{secrets.host}}:{{secrets.port}}"
    PAYMENTS_URL: "http://{{payments.host}}:{{payments.port}}/pay"
    KAFKA_BOOTSTRAP: "{{events.host}}:{{events.port}}"
    DATABASE_URL: "postgres://{{db.host}}:{{db.port}}/x"
services:
  secrets:
    kind: vault
    probe:
      timeout: 45.0
      interval: 1.0
  payments:
    kind: http
  events:
    kind: kafka
    topics:
      - name: orders.events
      - name: payments.events
        partitions: 6
  db:
    kind: postgresql
data:
  vault:
    secrets:
      - path: kv/app
        data:
          token: abc
  http:
    payments:
      - request:
          method: GET
          url: /pay
        response:
          status: 200
  postgres:
    db:
      - CREATE TABLE IF NOT EXISTS orders (id bigint PRIMARY KEY)
"""

SINGLE_SERVICE_DOCUMENT = """\
instance:
  image: my-service:latest
  port: 8080
  env:
    DATABASE_URL: "postgres://{{db.host}}:{{db.port}}/x"
services:
  db:
    kind: postgresql
"""

LIVE_DOCUMENT = """\
instance:
  image: wiremock/wiremock:3.13.0
  port: 8080
  probe:
    path: /__admin/health
  env:
    KAFKA_BOOTSTRAP: "{{events.host}}:{{events.port}}"
services:
  events:
    kind: kafka
    probe:
      timeout: 45.0
    topics:
      - name: orders.events
      - name: payments.events
        partitions: 6
"""

MARKER_LINE_PREFIX = "pybuggy_services:"
STARTUP_SQL = "CREATE TABLE IF NOT EXISTS orders (id bigint PRIMARY KEY)"


class ConfigStub:
    """Session config double recording ini registrations.

    Attributes:
        rootpath: The root path the session reports.
        lines: The ``(section, value)`` pairs every ini registration recorded, in order.
    """

    def __init__(self) -> None:
        """Initialize the config double with an empty registration record."""
        self.rootpath = pathlib.Path()
        self.lines: list[tuple[str, str]] = []

    def addinivalue_line(self, section: str, value: str) -> None:
        """Record one ini registration line.

        Args:
            section: The ini section of the registration.
            value: The registered line.
        """
        self.lines.append((section, value))


class ItemStub:
    """Item double carrying the markers the preset enqueue reads."""

    def __init__(self, markers: list[pytest.MarkDecorator]) -> None:
        """Initialize the item double.

        Args:
            markers: The markers ``iter_markers`` hands back.
        """
        self.name = "test_stub"
        self._markers = markers

    def iter_markers(self, name: str) -> list[pytest.MarkDecorator]:
        """Return the carried markers of the requested name.

        Args:
            name: The marker name to filter by.

        Returns:
            The carried markers named ``name``, in carried order.
        """
        return [marker for marker in self._markers if marker.name == name]


class RequestStub:
    """Request double exposing the fixturenames closure and the sandbox lookup.

    Attributes:
        fixturenames: The fixture closure the per-test guard reads.
        node: The item whose markers the per-test fixture reads.
    """

    def __init__(self, fixturenames: list[str], node: ItemStub, sandbox: Any) -> None:
        """Initialize the request double.

        Args:
            fixturenames: The fixture closure of the test being set up.
            node: The item double of the test being set up.
            sandbox: The sandbox ``getfixturevalue`` returns.
        """
        self.fixturenames = list(fixturenames)
        self.node = node
        self._sandbox = sandbox

    def getfixturevalue(self, name: str) -> Any:
        """Return the carried sandbox.

        Args:
            name: The fixture name being looked up.

        Returns:
            The carried sandbox.
        """
        return self._sandbox


class ArmedSession:
    """One configured sandbox plugin with its fixtures driven over the generator protocol.

    Attributes:
        plugin: The configured plugin — ``configure`` ran, ``activation`` is set.
        config: The config double receiving the marker registration.
        sandbox: The started session sandbox; set by ``start``.
    """

    def __init__(self, plugin: SandboxPlugin, config: ConfigStub) -> None:
        """Initialize the driven session.

        Args:
            plugin: The configured sandbox plugin.
            config: The config double of the session.
        """
        self.plugin = plugin
        self.config = config
        self.sandbox: sandbox_module.Sandbox | None = None
        self._generator = None

    def start(self) -> sandbox_module.Sandbox:
        """Drive the session fixture setup — the lazy start of the first use.

        Returns:
            The started session sandbox.
        """
        self._generator = SandboxPlugin.sandbox.__wrapped__(self.plugin)
        self.sandbox = next(self._generator)

        return self.sandbox

    def finish(self) -> None:
        """Drive the session fixture finalization — the stop of the teardown."""
        import contextlib

        with contextlib.suppress(StopIteration):
            next(self._generator)

        self._generator = None

    def begin_test(self, markers: list[pytest.MarkDecorator] | None = None) -> None:
        """Drive the per-test fixture — the product reset, the fresh batch, the presets.

        Args:
            markers: The ``pybuggy_services`` markers the test carries; none when omitted.
        """
        request = RequestStub(["sandbox"], ItemStub(markers or []), self.sandbox)

        SandboxPlugin._sandbox_test_batch.__wrapped__(self.plugin, request)


class FailingApplyEngine(FakeEngine):
    """Engine double whose apply rejects operations targeting the trigger table.

    The rejection raises the ``EngineError`` shape the real ``BaseEngine`` produces —
    ``service '<name>': <action> failed: <cause>`` — so the integration asserts the
    readable surfacing of a failing operation without containers.
    """

    def __init__(self, name: str, kind: str, trigger_table: str) -> None:
        """Initialize the rejecting engine.

        Args:
            name: The service name the sandbox resolves this engine by.
            kind: The configured service kind.
            trigger_table: The table whose operations fail; every other operation applies.
        """
        super().__init__(name=name, kind=kind)
        self.trigger_table = trigger_table

    def apply(self, operations: list[DataOperation]) -> None:
        """Fail on the first trigger-table operation; apply everything else.

        Args:
            operations: Operations of this service's kind, in application order.

        Raises:
            EngineError: An operation targets the trigger table.
        """
        for operation in operations:
            if operation.payload.get("table") == self.trigger_table:
                raise EngineError(
                    f"service '{self.name}': {operation.action} failed: fake rejected the insert into "
                    f"{self.trigger_table}"
                )

        super().apply(operations)


@pytest.fixture
def configured_plugin(
    sandbox_yaml: Callable[[str], pathlib.Path], monkeypatch: pytest.MonkeyPatch
) -> Callable[[str], tuple[SandboxPlugin, ConfigStub]]:
    """Configure the sandbox plugin for one document over the configphase path.

    Args:
        sandbox_yaml: The document writer fixture placing ``.goga/tools/pybuggy/sandbox.yml``
            under the tmp cwd.
        monkeypatch: The pytest monkeypatch fixture replacing the plugin_config read.

    Returns:
        A factory writing ``document``, driving ``configure``, and returning the configured
        plugin with its config double.
    """

    def _configure(document: str) -> tuple[SandboxPlugin, ConfigStub]:
        """Write ``document`` and drive the plugin's configure step over its parsed mapping.

        Args:
            document: The sandbox document content configuring the plugin.

        Returns:
            The configured plugin and the config double of the session.
        """
        path = sandbox_yaml(document)
        plugin = SandboxPlugin()
        monkeypatch.setattr(type(plugin), "plugin_config", full_load(path.read_text(encoding="utf-8")), raising=False)

        config = ConfigStub()
        plugin.init_pytest_config(config)
        plugin.configure()

        return plugin, config

    return _configure


@pytest.fixture
def armed(
    configured_plugin: Callable[[str], tuple[SandboxPlugin, ConfigStub]],
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[str, dict[str, FakeEngine], FakeService], ArmedSession]:
    """Configure the plugin and wire the container seams to fakes.

    Args:
        configured_plugin: The configphase factory of the plugin.
        monkeypatch: The pytest monkeypatch fixture replacing the module-level seams.

    Returns:
        A factory arming the session for one document over the given fakes.
    """

    def _arm(document: str, engines: dict[str, FakeEngine], service: FakeService) -> ArmedSession:
        """Configure the plugin for ``document`` and wire ``engines`` / ``service``.

        Args:
            document: The sandbox document content configuring the plugin.
            engines: The fake engines the sandbox builds, keyed by service name.
            service: The fake instance container of the session.

        Returns:
            The driven session over the configured plugin.
        """
        plugin, config = configured_plugin(document)

        monkeypatch.setattr(sandbox_module, "build_engine", lambda service_config: engines[service_config.name])
        monkeypatch.setattr(sandbox_module, "ServiceContainer", lambda _instance_config: service)
        monkeypatch.setattr(sandbox_module, "check_runtime", lambda: None)
        monkeypatch.setattr(sandbox_module, "Network", FakeNetwork)

        return ArmedSession(plugin, config)

    return _arm


class TestSessionStartFailure:
    """Failed-start cleanup of the lazy session start."""

    def test_session_start_failure_stops_everything_and_reraises(self, armed):
        """A failing engine start propagates and stops every started engine and the instance."""
        events: list[str] = []
        engine = FakeEngine(name="db", kind="postgresql", fail_start=True, events=events)
        service = FakeService(events=events)

        session = armed(SINGLE_SERVICE_DOCUMENT, {"db": engine}, service)

        with pytest.raises(RuntimeError, match="refused to start"):
            session.start()

        assert events == ["engine:db:start", "instance:stop", "engine:db:stop"]
        assert engine.stopped is True
        assert service.stopped is True


class TestConfiguredSessionFlow:
    """The session lifecycle from the lazy start to the finalization stop."""

    def test_session_flow_runs_start_to_finish_over_fakes(self, armed):
        """Configure, lazy start, per-test reset and preset enqueue, grouped apply, and teardown.

        The engines start in declaration order with their ordered startup lists — the
        kafka engine's list empty, its topology declared inline — the instance container
        starts last with the rendered env, ``base_url`` resolves from the instance address,
        the marker line lands at configphase, and the marked presets apply ahead of the
        in-test operations on top of the product reset.
        """
        events: list[str] = []
        engines: dict[str, FakeEngine] = {
            "secrets": FakeEngine(
                name="secrets",
                kind="vault",
                address=InstanceAddress(host="127.0.0.4", port=8200),
                events=events,
            ),
            "payments": FakeEngine(
                name="payments",
                kind="http",
                address=InstanceAddress(host="127.0.0.3", port=8080),
                events=events,
            ),
            "events": FakeEngine(
                name="events",
                kind="kafka",
                address=InstanceAddress(host="127.0.0.5", port=9092),
                events=events,
            ),
            "db": FakeEngine(
                name="db",
                kind="postgresql",
                address=InstanceAddress(host="127.0.0.2", port=5432),
                events=events,
            ),
        }
        service = FakeService(host="127.0.0.9", port=9000, events=events)

        session = armed(SESSION_DOCUMENT, engines, service)

        section, line = session.config.lines[0]

        assert section == "markers"
        assert line.startswith(MARKER_LINE_PREFIX)

        sandbox = session.start()

        assert isinstance(sandbox, sandbox_module.Sandbox)
        assert session.sandbox is sandbox
        assert sandbox.base_url == "http://127.0.0.9:9000"

        assert engines["secrets"].journaled == [
            DataOperation(
                instance="secrets", kind="vault", action="put", payload={"path": "kv/app", "data": {"token": "abc"}}
            )
        ]
        assert engines["payments"].journaled == [
            DataOperation(
                instance="payments",
                kind="http",
                action="stub",
                payload={"request": {"method": "GET", "url": "/pay"}, "response": {"status": 200}},
            )
        ]
        assert engines["events"].journaled == []
        assert engines["db"].journaled == [
            DataOperation(instance="db", kind="postgresql", action="insert", payload={"sql": STARTUP_SQL})
        ]
        assert service.started_env == {
            "VAULT_ADDR": "http://127.0.0.4:8200",
            "PAYMENTS_URL": "http://127.0.0.3:8080/pay",
            "KAFKA_BOOTSTRAP": "127.0.0.5:9092",
            "DATABASE_URL": "postgres://127.0.0.2:5432/x",
        }

        marker = pytest.mark.pybuggy_services(
            presets={
                "postgresql": {"db": [{"table": "customers", "rows": [{"id": 1}]}]},
                "http": {"payments": [{"request": {"method": "GET", "url": "/pay"}, "response": {"status": 200}}]},
            }
        )

        session.begin_test([marker])
        sandbox.kafka("events").produce("orders.events", {"id": 1})
        sandbox.postgresql("db").insert("orders", [{"id": 2}])
        sandbox.http("payments").stub({"request": {"method": "POST", "url": "/charge"}, "response": {"status": 201}})

        sandbox.apply_pending()
        sandbox.apply_pending()

        assert engines["db"].applied == [
            DataOperation(
                instance="db", kind="postgresql", action="insert", payload={"table": "customers", "rows": [{"id": 1}]}
            ),
            DataOperation(
                instance="db", kind="postgresql", action="insert", payload={"table": "orders", "rows": [{"id": 2}]}
            ),
        ]
        assert engines["payments"].applied == [
            DataOperation(
                instance="payments",
                kind="http",
                action="stub",
                payload={"request": {"method": "GET", "url": "/pay"}, "response": {"status": 200}},
            ),
            DataOperation(
                instance="payments",
                kind="http",
                action="stub",
                payload={"request": {"method": "POST", "url": "/charge"}, "response": {"status": 201}},
            ),
        ]
        assert engines["events"].applied == [
            DataOperation(
                instance="events",
                kind="kafka",
                action="produce",
                payload={"topic": "orders.events", "value": {"id": 1}, "key": None},
            )
        ]

        session.finish()

        assert events == [
            "engine:secrets:start",
            "engine:payments:start",
            "engine:events:start",
            "engine:db:start",
            "instance:start",
            "engine:secrets:reset",
            "engine:payments:reset",
            "engine:events:reset",
            "engine:db:reset",
            "engine:db:apply",
            "engine:payments:apply",
            "engine:events:apply",
            "instance:stop",
            "engine:db:stop",
            "engine:events:stop",
            "engine:payments:stop",
            "engine:secrets:stop",
        ]
        assert all(engine.stopped for engine in engines.values())
        assert service.stopped is True

    def test_session_clear_resets_engines_and_keeps_the_instance_running(self, armed):
        """The reset flow returns every service to its baseline; the instance keeps running."""
        events: list[str] = []
        engine = FakeEngine(name="db", kind="postgresql", events=events)

        session = armed(SINGLE_SERVICE_DOCUMENT, {"db": engine}, FakeService(events=events))
        sandbox = session.start()

        with sandbox.baseline():
            sandbox.postgresql("db").insert("customers", [{"id": 1}])

        events.clear()

        sandbox.clear()

        assert events == ["engine:db:reset"]
        assert engine.reset_count == 1
        assert sandbox.service.stopped is False
        assert sandbox.service.started is True

    def test_session_flow_raising_operation_surfaces_readable_error(self, armed):
        """A failing operation surfaces an error identifying the service, action, and cause."""
        engine = FailingApplyEngine(name="db", kind="postgresql", trigger_table="poison")

        session = armed(SINGLE_SERVICE_DOCUMENT, {"db": engine}, FakeService())
        sandbox = session.start()
        marker = pytest.mark.pybuggy_services(
            presets={"postgresql": {"db": [{"table": "customers", "rows": [{"id": 1}]}]}}
        )

        session.begin_test([marker])
        sandbox.postgresql("db").insert("poison", [{"id": 9}])

        with pytest.raises(EngineError, match=r"service 'db': insert failed:.*poison"):
            sandbox.apply_pending()


class TestSessionEdgeCases:
    """View-name resolution and the died-instance guard of the session."""

    def test_unknown_service_name_on_view_factory_lists_configured_services(self, armed):
        """A view factory of an unknown name fails listing the configured services."""
        session = armed(SINGLE_SERVICE_DOCUMENT, {"db": FakeEngine(name="db", kind="postgresql")}, FakeService())
        sandbox = session.start()

        with pytest.raises(ValueError, match=r"no postgresql service named 'ghost'.*db \(postgresql\)"):
            sandbox.postgresql("ghost")

    def test_died_instance_surfaces_through_ensure_service_with_output(self, armed):
        """A died instance fails fast naming the image and attaching its output."""
        service = FakeService(alive=False, logs="OOMKilled after 3s")

        session = armed(SINGLE_SERVICE_DOCUMENT, {"db": FakeEngine(name="db", kind="postgresql")}, service)
        sandbox = session.start()

        with pytest.raises(RuntimeError, match="died") as excinfo:
            sandbox.ensure_service()

        assert "my-service:latest" in str(excinfo.value)
        assert "OOMKilled after 3s" in str(excinfo.value)


class TestPresetOrdering:
    """Preset placement within one service group."""

    def test_presets_precede_in_test_operations_within_one_service_group(self, armed):
        """Preset operations apply first — in declaration order — then the in-test operation."""
        engine = FakeEngine(name="db", kind="postgresql")

        session = armed(SINGLE_SERVICE_DOCUMENT, {"db": engine}, FakeService())
        sandbox = session.start()
        marker = pytest.mark.pybuggy_services(
            presets={
                "postgresql": {
                    "db": [
                        {"table": "customers", "rows": [{"id": 1}]},
                        {"table": "orders", "rows": [{"id": 2}]},
                    ]
                }
            }
        )

        session.begin_test([marker])
        sandbox.postgresql("db").insert("audit_log", [{"id": 3}])

        sandbox.apply_pending()

        assert [operation.payload["table"] for operation in engine.applied] == [
            "customers",
            "orders",
            "audit_log",
        ]


@requires_docker
class TestLiveSessionLifecycle:
    """Live behavior of the configured plugin session over the pinned mocks (docker-gated)."""

    @staticmethod
    def _consumed_values(host: str, port: int, topic: str) -> list[object]:
        """Read every message currently on ``topic``, from the beginning.

        Args:
            host: The mapped host of the kafka service.
            port: The published port of the kafka service.
            topic: A topic declared on the service entry.

        Returns:
            The JSON-deserialized message values currently held by the topic.
        """
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=f"{host}:{port}",
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            consumer_timeout_ms=5000,
        )

        try:
            return [json.loads(message.value.decode("utf-8")) for message in consumer]
        finally:
            consumer.close()

    def test_live_session_boots_declared_topology_and_resets(self, sandbox_yaml, monkeypatch):
        """A real session over the pinned mocks with declared topics and a probe.

        The instance readiness rides the declared health-path probe, the declared kafka
        topology boots with its partitions, a produce into a declared topic lands, and
        the reset flow restarts the mock and replays the journaled baseline.
        """
        path = sandbox_yaml(LIVE_DOCUMENT)
        plugin = SandboxPlugin()
        monkeypatch.setattr(type(plugin), "plugin_config", full_load(path.read_text(encoding="utf-8")), raising=False)

        config = ConfigStub()
        plugin.init_pytest_config(config)
        plugin.configure()

        assert plugin.activation is not None
        assert plugin.activation.instance.probe is not None
        assert plugin.activation.instance.probe.path == "/__admin/health"
        assert [topic.name for topic in plugin.activation.services["events"].topics] == [
            "orders.events",
            "payments.events",
        ]

        session = ArmedSession(plugin, config)
        sandbox = session.start()

        assert sandbox is not None

        try:
            health = requests.get(f"{sandbox.base_url}/__admin/health", timeout=5)

            assert health.status_code == 200

            view = sandbox.kafka("events")
            probe = KafkaConsumer(bootstrap_servers=f"{view.host}:{view.port}")

            try:
                assert probe.partitions_for_topic("orders.events") is not None
                assert len(probe.partitions_for_topic("payments.events")) == 6
            finally:
                probe.close()

            sandbox.kafka("events").produce("orders.events", {"id": 1})
            sandbox.apply_pending()

            assert self._consumed_values(view.host, view.port, "orders.events") == [{"id": 1}]

            with sandbox.baseline():
                sandbox.kafka("events").produce("orders.events", {"id": 0}, key="baseline")

            sandbox.clear()

            assert self._consumed_values(view.host, view.port, "orders.events") == [{"id": 0}]
        finally:
            session.finish()
