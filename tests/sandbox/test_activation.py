"""Contract and logic tests for the ``activate_sandbox`` / ``active_sandbox`` routines."""

import inspect
import pathlib

import pytest
from goga_tool_pybuggy.sandbox import activation as activation_module
from goga_tool_pybuggy.sandbox import sandbox as sandbox_module
from goga_tool_pybuggy.sandbox.config import InstanceConfig, SandboxConfig, ServiceConfig, StartupData
from goga_tool_pybuggy.sandbox.engines import DataOperation

from .conftest import FakeEngine, FakeNetwork, FakeService

MINIMAL_DOCUMENT = """\
instance:
  image: my-service:latest
  env: {}
  port: 8080
services:
  db:
    kind: postgresql
"""

STALE_ROOT_DOCUMENT = """\
service:
  image: former-service:latest
  env: {}
  port: 9000
instances:
  db:
    kind: postgresql
"""

HOOK_NAMES = ("pytest_sessionstart", "pytest_sessionfinish", "pytest_runtest_setup")
MARKER_LINE_PREFIX = "pybuggy_services:"


@pytest.fixture(autouse=True)
def reset_module_state():
    """Reset the activation module state around every test."""
    activation_module._ACTIVE = None
    activation_module._ARMED = None

    yield

    activation_module._ACTIVE = None
    activation_module._ARMED = None


class ConfigStub:
    """Session config double recording ini registrations into an optional shared sink."""

    def __init__(self, calls: list[str] | None = None) -> None:
        """Initialize the config double.

        Args:
            calls: An optional shared sink recording every registration, for ordering.
        """
        self.rootpath = pathlib.Path()
        self.lines: list[tuple[str, str]] = []
        self._calls = calls

    def addinivalue_line(self, section: str, value: str) -> None:
        """Record one ini registration line.

        Args:
            section: The ini section of the registration.
            value: The registered line.
        """
        self.lines.append((section, value))

        if self._calls is not None:
            self._calls.append("markers")


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


def stub_sandbox(calls: list[str], constructed: list[SandboxConfig], start_label: str = "sandbox:start") -> type:
    """Build a recording ``Sandbox`` double observing the hook-driven lifecycle.

    Args:
        calls: The shared sink recording the lifecycle labels.
        constructed: The sink collecting every construction's configuration.
        start_label: The label a ``start`` call records.

    Returns:
        The recording ``Sandbox`` double class.
    """

    class StubSandbox:
        """Recording sandbox double; the hooks drive it instead of containers."""

        def __init__(self, config: SandboxConfig) -> None:
            """Record the construction and keep the configuration.

            Args:
                config: The configuration the hook constructed the sandbox with.
            """
            self.config = config
            self.base_url = "http://127.0.0.9:9000"
            constructed.append(config)

        def start(self) -> None:
            """Record a start."""
            calls.append(start_label)

        def new_test_batch(self) -> None:
            """Record a per-test batch refresh."""
            calls.append("sandbox:batch")

        def stop(self) -> None:
            """Record a stop."""
            calls.append("sandbox:stop")

    return StubSandbox


def fake_sandbox(monkeypatch: pytest.MonkeyPatch) -> sandbox_module.Sandbox:
    """Build a real sandbox over one recording postgresql engine, unstarted.

    Args:
        monkeypatch: The pytest monkeypatch fixture replacing the module-level seams.

    Returns:
        The sandbox whose ``db`` engine is a recording fake.
    """
    engine = FakeEngine(name="db", kind="postgresql")
    monkeypatch.setattr(sandbox_module, "build_engine", lambda _service_config: engine)
    monkeypatch.setattr(sandbox_module, "ServiceContainer", lambda _instance_config: FakeService())
    monkeypatch.setattr(sandbox_module, "check_runtime", lambda: None)
    monkeypatch.setattr(sandbox_module, "Network", FakeNetwork)

    return sandbox_module.Sandbox(
        SandboxConfig(
            instance=InstanceConfig(image="my-service:latest", env={}, port=8080),
            services={"db": ServiceConfig(name="db", kind="postgresql")},
            data=StartupData(),
        )
    )


class TestActivationContract:
    """Declared API of the activation routines."""

    def test_activate_sandbox_is_importable_from_the_facade(self):
        """``activate_sandbox`` is importable from ``goga_tool_pybuggy.sandbox``."""
        from goga_tool_pybuggy.sandbox import activate_sandbox

        assert activate_sandbox is activation_module.activate_sandbox

    def test_active_sandbox_is_importable_from_the_facade(self):
        """``active_sandbox`` is importable from ``goga_tool_pybuggy.sandbox``."""
        from goga_tool_pybuggy.sandbox import active_sandbox

        assert active_sandbox is activation_module.active_sandbox

    def test_activate_sandbox_takes_exactly_the_context(self):
        """The signature takes exactly ``context``."""
        parameters = list(inspect.signature(activation_module.activate_sandbox).parameters)

        assert parameters == ["context"]

    def test_active_sandbox_takes_no_arguments(self):
        """The signature takes no arguments."""
        parameters = list(inspect.signature(activation_module.active_sandbox).parameters)

        assert parameters == []


class TestActivationBehavior:
    """Presence gating, hook registration, and the preset enqueue of the activation."""

    def test_activation_inert_without_document(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
        """Without the document nothing is registered and the lookup stays None."""
        monkeypatch.chdir(tmp_path)

        context: dict[str, object] = {}

        assert activation_module.activate_sandbox(context) is None
        assert not any(name in context for name in HOOK_NAMES)
        assert activation_module.active_sandbox() is None

    def test_activation_arms_from_new_document_path(self, sandbox_yaml):
        """Scenario 28: arming reads the tools-home document; without it the call is inert.

        A stale root ``.sandbox.yml`` is never read — with one present the call stays
        inert, and only the document under ``.goga/tools/pybuggy/sandbox.yml`` arms the
        three hooks.
        """
        context: dict[str, object] = {}

        assert activation_module.activate_sandbox(context) is None
        assert context == {}

        pathlib.Path(".sandbox.yml").write_text(STALE_ROOT_DOCUMENT, encoding="utf-8")

        assert activation_module.activate_sandbox(context) is None
        assert context == {}
        assert activation_module.active_sandbox() is None

        sandbox_yaml(MINIMAL_DOCUMENT)

        config = activation_module.activate_sandbox(context)

        assert isinstance(config, SandboxConfig)
        assert config.instance.image == "my-service:latest"
        assert list(config.services) == ["db"]

        for name in HOOK_NAMES:
            assert callable(context[name]), name

    def test_activation_registers_hooks_with_document(self, sandbox_yaml, monkeypatch: pytest.MonkeyPatch):
        """A valid document arms the three hooks; nothing starts until sessionstart runs."""
        sandbox_yaml(MINIMAL_DOCUMENT)

        calls: list[str] = []
        constructed: list[SandboxConfig] = []
        stub_class = stub_sandbox(calls, constructed)
        monkeypatch.setattr(activation_module, "Sandbox", stub_class)

        context: dict[str, object] = {}
        config = activation_module.activate_sandbox(context)

        assert isinstance(config, SandboxConfig)
        assert calls == []
        assert not constructed

        for name in HOOK_NAMES:
            assert callable(context[name]), name

        session = SessionStub(ConfigStub(calls))
        context["pytest_sessionstart"](session)

        assert calls == ["markers", "sandbox:start"]
        assert constructed == [config]

        section, line = session.config.lines[0]

        assert section == "markers"
        assert line.startswith(MARKER_LINE_PREFIX)
        assert "presets" in line

        active = activation_module.active_sandbox()

        assert isinstance(active, stub_class)
        assert activation_module.active_sandbox() is active
        assert active.config is config

    def test_activation_invalid_document_fails_fast_registering_nothing(self, sandbox_yaml):
        """An invalid document fails before anything is registered or armed."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\nservices:\n  cache: { kind: redis }\n"
        )

        context: dict[str, object] = {}

        with pytest.raises(ValueError, match=r"redis"):
            activation_module.activate_sandbox(context)

        assert context == {}
        assert activation_module.active_sandbox() is None
        assert activation_module._ARMED is None

    def test_activation_wraps_preexisting_hook(self, sandbox_yaml, monkeypatch: pytest.MonkeyPatch):
        """A pre-existing same-name callable runs first, the sandbox body second."""
        sandbox_yaml(MINIMAL_DOCUMENT)

        calls: list[str] = []
        constructed: list[SandboxConfig] = []
        monkeypatch.setattr(activation_module, "Sandbox", stub_sandbox(calls, constructed, start_label="sandbox"))

        def prior(session: SessionStub) -> None:
            """Record the prior hook invocation."""
            calls.append("prior")

        context: dict[str, object] = {"pytest_sessionstart": prior}
        config = activation_module.activate_sandbox(context)

        context["pytest_sessionstart"](SessionStub(ConfigStub(calls)))

        assert calls == ["prior", "markers", "sandbox"]
        assert calls.count("prior") == 1
        assert constructed == [config]

    def test_activation_wraps_preexisting_sessionfinish_hook(self, sandbox_yaml, monkeypatch: pytest.MonkeyPatch):
        """A pre-existing ``pytest_sessionfinish`` runs first, both arguments forwarded."""
        sandbox_yaml(MINIMAL_DOCUMENT)

        calls: list[str] = []
        monkeypatch.setattr(activation_module, "Sandbox", stub_sandbox(calls, []))

        def prior(session: SessionStub, exitstatus: int) -> None:
            """Record the prior hook invocation with its exit status."""
            calls.append(("prior", exitstatus))

        context: dict[str, object] = {"pytest_sessionfinish": prior}
        activation_module.activate_sandbox(context)
        context["pytest_sessionstart"](SessionStub(ConfigStub(calls)))

        context["pytest_sessionfinish"](SessionStub(), 5)

        assert calls == ["markers", "sandbox:start", ("prior", 5), "sandbox:stop"]
        assert activation_module.active_sandbox() is None

    def test_activation_wraps_preexisting_runtest_setup_hook(self, sandbox_yaml, monkeypatch: pytest.MonkeyPatch):
        """A pre-existing ``pytest_runtest_setup`` runs first, the sandbox body second."""
        sandbox_yaml(MINIMAL_DOCUMENT)

        calls: list[str] = []
        monkeypatch.setattr(activation_module, "Sandbox", stub_sandbox(calls, []))

        def prior(item: ItemStub) -> None:
            """Record the prior hook invocation."""
            calls.append("prior")

        context: dict[str, object] = {"pytest_runtest_setup": prior}
        activation_module.activate_sandbox(context)
        context["pytest_sessionstart"](SessionStub(ConfigStub(calls)))

        context["pytest_runtest_setup"](ItemStub([]))

        assert calls == ["markers", "sandbox:start", "prior", "sandbox:batch"]

    def test_sessionfinish_stops_the_active_sandbox_and_clears_the_lookup(
        self, sandbox_yaml, monkeypatch: pytest.MonkeyPatch
    ):
        """The finish hook stops the active sandbox once and clears the lookup seam."""
        sandbox_yaml(MINIMAL_DOCUMENT)

        calls: list[str] = []
        constructed: list[SandboxConfig] = []
        monkeypatch.setattr(activation_module, "Sandbox", stub_sandbox(calls, constructed))

        context: dict[str, object] = {}
        activation_module.activate_sandbox(context)
        context["pytest_sessionstart"](SessionStub(ConfigStub(calls)))

        context["pytest_sessionfinish"](SessionStub(), 0)

        assert calls == ["markers", "sandbox:start", "sandbox:stop"]
        assert activation_module.active_sandbox() is None

        context["pytest_sessionfinish"](SessionStub(), 1)

        assert calls == ["markers", "sandbox:start", "sandbox:stop"]

    def test_sessionfinish_clears_the_lookup_when_stop_raises(self, sandbox_yaml, monkeypatch: pytest.MonkeyPatch):
        """A failing sandbox stop still clears the lookup seam and the error propagates."""
        sandbox_yaml(MINIMAL_DOCUMENT)

        class RefusingSandbox:
            """Sandbox double whose stop always raises."""

            def __init__(self, config: SandboxConfig) -> None:
                """Accept the armed configuration."""

            def start(self) -> None:
                """Start without containers."""

            base_url = "http://127.0.0.9:9000"

            def stop(self) -> None:
                """Refuse the stop."""
                raise RuntimeError("fake refused to stop")

        monkeypatch.setattr(activation_module, "Sandbox", RefusingSandbox)

        context: dict[str, object] = {}
        activation_module.activate_sandbox(context)
        context["pytest_sessionstart"](SessionStub(ConfigStub()))

        with pytest.raises(RuntimeError, match="refused to stop"):
            context["pytest_sessionfinish"](SessionStub(), 1)

        assert activation_module.active_sandbox() is None

    def test_preset_enqueue_fails_unknown_service_listing_configured(
        self, sandbox_yaml, monkeypatch: pytest.MonkeyPatch
    ):
        """A preset targeting an unknown service fails listing the configured ones."""
        sandbox_yaml(MINIMAL_DOCUMENT)

        context: dict[str, object] = {}
        activation_module.activate_sandbox(context)

        activation_module._ACTIVE = fake_sandbox(monkeypatch)

        marker = pytest.mark.pybuggy_services(presets={"postgresql": {"ghost": [{"table": "t", "rows": []}]}})

        with pytest.raises(ValueError, match=r"no postgresql service named 'ghost'.*db \(postgresql\)"):
            context["pytest_runtest_setup"](ItemStub([marker]))

    def test_preset_enqueue_prepends_marker_presets_into_fresh_batch(
        self, sandbox_yaml, monkeypatch: pytest.MonkeyPatch
    ):
        """Valid presets enqueue into the fresh batch ahead of in-test declarations."""
        sandbox_yaml(MINIMAL_DOCUMENT)

        context: dict[str, object] = {}
        activation_module.activate_sandbox(context)

        sandbox = fake_sandbox(monkeypatch)
        engine = sandbox.engines["db"]
        activation_module._ACTIVE = sandbox

        marker = pytest.mark.pybuggy_services(
            presets={"postgresql": {"db": [{"table": "customers", "rows": [{"id": 1}]}]}}
        )

        context["pytest_runtest_setup"](ItemStub([marker]))
        sandbox.postgresql("db").insert("orders", [{"id": 2}])
        sandbox.apply_pending()

        assert engine.applied == [
            DataOperation(
                instance="db", kind="postgresql", action="insert", payload={"table": "customers", "rows": [{"id": 1}]}
            ),
            DataOperation(
                instance="db", kind="postgresql", action="insert", payload={"table": "orders", "rows": [{"id": 2}]}
            ),
        ]
