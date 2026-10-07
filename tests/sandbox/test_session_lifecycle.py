"""Integration tests for the armed sandbox session lifecycle over recording fakes.

Cross-entity scenarios spanning the activation hooks, the session runtime, the per-test
data batch, the instance views, and the preset enqueue: the armed flow from
``pytest_sessionstart`` to ``pytest_sessionfinish``, the failure-cleanup guarantee of a
failed start, the readable surfacing of a failing operation, and the preset-before-in-test
ordering within one instance group.
"""

import pathlib
from collections.abc import Callable

import pytest
from goga_tool_pybuggy.sandbox import activation as activation_module
from goga_tool_pybuggy.sandbox import sandbox as sandbox_module
from goga_tool_pybuggy.sandbox.engines import DataOperation, EngineError, InstanceAddress

from .conftest import FakeEngine, FakeNetwork, FakeService

SESSION_DOCUMENT = """\
service:
  image: my-service:latest
  port: 8080
  env:
    DATABASE_URL: "postgres://{{db.host}}:{{db.port}}/x"
    PAYMENTS_URL: "http://{{payments.host}}:{{payments.port}}/pay"
instances:
  db:
    kind: postgresql
  payments:
    kind: http
data:
  postgres:
    db:
      - CREATE TABLE IF NOT EXISTS orders (id bigint PRIMARY KEY)
"""

SINGLE_INSTANCE_DOCUMENT = """\
service:
  image: my-service:latest
  port: 8080
  env:
    DATABASE_URL: "postgres://{{db.host}}:{{db.port}}/x"
instances:
  db:
    kind: postgresql
"""

MARKER_LINE_PREFIX = "pybuggy_services:"
STARTUP_SQL = "CREATE TABLE IF NOT EXISTS orders (id bigint PRIMARY KEY)"


class ConfigStub:
    """Session config double recording ini registrations."""

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


class SessionStub:
    """Session double exposing a config double."""

    def __init__(self, config: ConfigStub | None = None) -> None:
        """Initialize the session double.

        Args:
            config: The config double to expose; a fresh one when omitted.
        """
        self.config = config if config is not None else ConfigStub()


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


class FailingApplyEngine(FakeEngine):
    """Engine double whose apply rejects operations targeting the trigger table.

    The rejection raises the ``EngineError`` shape the real ``BaseEngine`` produces —
    ``instance '<name>': <action> failed: <cause>`` — so the integration asserts the
    readable surfacing of a failing operation without containers.
    """

    def __init__(self, name: str, kind: str, trigger_table: str) -> None:
        """Initialize the rejecting engine.

        Args:
            name: The instance name the sandbox resolves this engine by.
            kind: The configured instance kind.
            trigger_table: The table whose operations fail; every other operation applies.
        """
        super().__init__(name=name, kind=kind)
        self.trigger_table = trigger_table

    def apply(self, operations: list[DataOperation]) -> None:
        """Fail on the first trigger-table operation; apply everything else.

        Args:
            operations: Operations of this instance's kind, in application order.

        Raises:
            EngineError: An operation targets the trigger table.
        """
        for operation in operations:
            if operation.payload.get("table") == self.trigger_table:
                raise EngineError(
                    f"instance '{self.name}': {operation.action} failed: fake rejected the insert into "
                    f"{self.trigger_table}"
                )

        super().apply(operations)


@pytest.fixture(autouse=True)
def reset_activation_state():
    """Reset the activation module state around every test."""
    activation_module._ACTIVE = None
    activation_module._ARMED = None

    yield

    activation_module._ACTIVE = None
    activation_module._ARMED = None


@pytest.fixture
def armed(
    sandbox_yaml: Callable[[str], pathlib.Path], monkeypatch: pytest.MonkeyPatch
) -> Callable[[str, dict[str, FakeEngine], FakeService], dict[str, object]]:
    """Arm the sandbox over fakes: write the document, register the hooks, wire the seams.

    Args:
        sandbox_yaml: The document writer fixture placing ``.sandbox.yml`` in the cwd.
        monkeypatch: The pytest monkeypatch fixture replacing the module-level seams.

    Returns:
        A factory arming the session for one document over the given fakes; it returns
        the context carrying the three registered lifecycle hooks.
    """

    def _arm(document: str, engines: dict[str, FakeEngine], service: FakeService) -> dict[str, object]:
        """Write ``document`` and wire ``engines`` / ``service`` through the seams.

        Args:
            document: The ``.sandbox.yml`` content arming the session.
            engines: The fake engines the sandbox builds, keyed by instance name.
            service: The fake service container of the session.

        Returns:
            The context carrying the three registered lifecycle hooks.
        """
        sandbox_yaml(document)

        context: dict[str, object] = {}
        activation_module.activate_sandbox(context)

        monkeypatch.setattr(sandbox_module, "build_engine", lambda instance_config: engines[instance_config.name])
        monkeypatch.setattr(sandbox_module, "ServiceContainer", lambda _service_config: service)
        monkeypatch.setattr(sandbox_module, "check_runtime", lambda: None)
        monkeypatch.setattr(sandbox_module, "Network", FakeNetwork)

        return context

    return _arm


class TestSessionStartFailure:
    """Failed-start cleanup of the registered session-start hook."""

    def test_sessionstart_failure_stops_everything_and_reraises(self, armed):
        """A failing engine start propagates and stops every started engine and the service."""
        events: list[str] = []
        engine = FakeEngine(name="db", kind="postgresql", fail_start=True, events=events)
        service = FakeService(events=events)

        context = armed(SINGLE_INSTANCE_DOCUMENT, {"db": engine}, service)

        with pytest.raises(RuntimeError, match="refused to start"):
            context["pytest_sessionstart"](SessionStub())

        assert events == ["engine:db:start", "service:stop", "engine:db:stop"]
        assert engine.stopped is True
        assert service.stopped is True
        assert activation_module.active_sandbox() is None


class TestArmedSessionFlow:
    """The armed session lifecycle from session start to session finish."""

    def test_armed_session_flow_runs_start_to_finish_over_fakes(self, armed):
        """Arming, start, preset enqueue, grouped apply, and teardown compose end to end."""
        events: list[str] = []
        engines: dict[str, FakeEngine] = {
            "db": FakeEngine(
                name="db",
                kind="postgresql",
                address=InstanceAddress(host="127.0.0.2", port=5432),
                events=events,
            ),
            "payments": FakeEngine(
                name="payments",
                kind="http",
                address=InstanceAddress(host="127.0.0.3", port=8080),
                events=events,
            ),
        }
        service = FakeService(host="127.0.0.9", port=9000, events=events)

        context = armed(SESSION_DOCUMENT, engines, service)
        session = SessionStub()

        context["pytest_sessionstart"](session)

        sandbox = activation_module.active_sandbox()

        assert isinstance(sandbox, sandbox_module.Sandbox)
        assert activation_module.active_sandbox() is sandbox
        assert sandbox.base_url == "http://127.0.0.9:9000"

        section, line = session.config.lines[0]

        assert section == "markers"
        assert line.startswith(MARKER_LINE_PREFIX)
        assert engines["db"].journaled == [
            DataOperation(instance="db", kind="postgresql", action="insert", payload={"sql": STARTUP_SQL})
        ]
        assert service.started_env == {
            "DATABASE_URL": "postgres://127.0.0.2:5432/x",
            "PAYMENTS_URL": "http://127.0.0.3:8080/pay",
        }

        marker = pytest.mark.pybuggy_services(
            presets={
                "postgresql": {"db": [{"table": "customers", "rows": [{"id": 1}]}]},
                "http": {"payments": [{"request": {"method": "GET", "url": "/pay"}, "response": {"status": 200}}]},
            }
        )

        context["pytest_runtest_setup"](ItemStub([marker]))
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

        context["pytest_sessionfinish"](SessionStub(), 0)

        assert events == [
            "engine:db:start",
            "engine:payments:start",
            "service:start",
            "engine:db:apply",
            "engine:payments:apply",
            "service:stop",
            "engine:payments:stop",
            "engine:db:stop",
        ]
        assert activation_module.active_sandbox() is None
        assert all(engine.stopped for engine in engines.values())
        assert service.stopped is True

    def test_armed_flow_raising_operation_surfaces_readable_error(self, armed):
        """A failing operation surfaces an error identifying the instance, action, and cause."""
        engine = FailingApplyEngine(name="db", kind="postgresql", trigger_table="poison")

        context = armed(SINGLE_INSTANCE_DOCUMENT, {"db": engine}, FakeService())
        context["pytest_sessionstart"](SessionStub())

        sandbox = activation_module.active_sandbox()
        marker = pytest.mark.pybuggy_services(
            presets={"postgresql": {"db": [{"table": "customers", "rows": [{"id": 1}]}]}}
        )

        context["pytest_runtest_setup"](ItemStub([marker]))
        sandbox.postgresql("db").insert("poison", [{"id": 9}])

        with pytest.raises(EngineError, match=r"instance 'db': insert failed:.*poison"):
            sandbox.apply_pending()


class TestPresetOrdering:
    """Preset placement within one instance group."""

    def test_presets_precede_in_test_operations_within_one_instance_group(self, armed):
        """Preset operations apply first — in declaration order — then the in-test operation."""
        engine = FakeEngine(name="db", kind="postgresql")

        context = armed(SINGLE_INSTANCE_DOCUMENT, {"db": engine}, FakeService())
        context["pytest_sessionstart"](SessionStub())

        sandbox = activation_module.active_sandbox()
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

        context["pytest_runtest_setup"](ItemStub([marker]))
        sandbox.postgresql("db").insert("audit_log", [{"id": 3}])

        sandbox.apply_pending()

        assert [operation.payload["table"] for operation in engine.applied] == [
            "customers",
            "orders",
            "audit_log",
        ]
