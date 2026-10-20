"""Contract and logic tests for the ``SandboxPlugin`` entity."""

import inspect
from typing import Any

import pytest
from goga_tool_pybuggy.plugin import SandboxPlugin
from goga_tool_pybuggy.plugin import sandbox_plugin as sandbox_plugin_module
from goga_tool_pybuggy.sandbox.config import SandboxConfig
from yaml import YAMLError

VALID_DOCUMENT = {
    "instance": {
        "image": "my-service:latest",
        "port": 8080,
        "env": {"DATABASE_URL": "postgres://{{db.host}}:{{db.port}}/x"},
    },
    "services": {"db": {"kind": "postgresql"}},
}


class _FakePytestConfig:
    """Config double collecting ``addinivalue_line`` registrations.

    Attributes:
        lines: The ``(name, line)`` pairs every call registered, in call order.
    """

    def __init__(self) -> None:
        self.lines: list[tuple[str, str]] = []

    def addinivalue_line(self, name: str, line: str) -> None:
        """Record one ini value registration."""
        self.lines.append((name, line))


class _RecordingSandbox:
    """Sandbox double recording the lifecycle the fixtures drive.

    Attributes:
        activation: The activation the constructor received.
        calls: The lifecycle call labels, in call order.
        started: Whether ``start`` ran.
        stopped: Whether ``stop`` ran.
        enqueued: The presets payloads ``enqueue_presets`` received, in call order.
    """

    def __init__(self, activation: SandboxConfig, fail_start: bool = False) -> None:
        self.activation = activation
        self.fail_start = fail_start
        self.calls: list[str] = []
        self.enqueued: list[dict[str, Any]] = []
        self.started = False
        self.stopped = False

    def start(self) -> None:
        """Record a start; refuse when configured to."""
        self.calls.append("start")

        if self.fail_start:
            raise RuntimeError("fake refused to start")

        self.started = True

    @property
    def base_url(self) -> str:
        """The mapped service address the api fixture would resolve."""
        return "http://sandbox.test:9000"

    def stop(self) -> None:
        """Record a stop."""
        self.calls.append("stop")
        self.stopped = True

    def clear(self) -> None:
        """Record a baseline reset."""
        self.calls.append("clear")

    def new_test_batch(self) -> None:
        """Record a batch replacement."""
        self.calls.append("new_test_batch")

    def enqueue_presets(self, presets: dict[str, Any]) -> int:
        """Record one preset enqueue; report its declaration count."""
        self.calls.append("enqueue_presets")
        self.enqueued.append(presets)

        return sum(len(declarations) for targets in presets.values() for declarations in targets.values())


class _FakeNode:
    """Node double carrying the markers ``iter_markers`` filters by name.

    Attributes:
        name: The node name the batch fixture logs.
        _markers: The carried markers.
    """

    def __init__(self, markers: list[pytest.Mark], name: str = "test_sample") -> None:
        self.name = name
        self._markers = markers

    def iter_markers(self, name: str):
        """Yield the carried markers of the requested name, in order."""
        return iter(marker for marker in self._markers if marker.name == name)


class _FakeRequest:
    """Request double exposing the fixturenames guard and the sandbox lookup.

    Attributes:
        fixturenames: The item fixture closure the guard reads.
        node: The node whose markers the batch fixture reads.
        lookups: The fixture names ``getfixturevalue`` was asked for.
        sandbox: The sandbox ``getfixturevalue`` returns.
    """

    def __init__(self, fixturenames: list[str], node: _FakeNode | None = None, sandbox: Any = None) -> None:
        self.fixturenames = list(fixturenames)
        self.node = node if node is not None else _FakeNode([])
        self.lookups: list[str] = []
        self._sandbox = sandbox

    def getfixturevalue(self, name: str) -> Any:
        """Record the lookup and return the carried sandbox."""
        self.lookups.append(name)

        return self._sandbox


def _configured_plugin(monkeypatch: pytest.MonkeyPatch, document: dict | None = None) -> SandboxPlugin:
    """Build a plugin driven through ``configure`` with a document of the test's choosing.

    Args:
        monkeypatch: The pytest monkeypatch fixture carrying the ``plugin_config`` override.
        document: The parsed document ``plugin_config`` reports; ``None`` keeps a valid one.

    Returns:
        The configured plugin — ``configure`` ran, ``activation`` is set.
    """
    plugin = SandboxPlugin()
    monkeypatch.setattr(
        type(plugin), "plugin_config", document if document is not None else VALID_DOCUMENT, raising=False
    )
    plugin.init_pytest_config(_FakePytestConfig())
    plugin.configure()

    return plugin


def _wire_recording_sandbox(monkeypatch: pytest.MonkeyPatch, fail_start: bool = False) -> list[_RecordingSandbox]:
    """Patch the module's ``Sandbox`` seam to the recording double.

    Args:
        monkeypatch: The pytest monkeypatch fixture replacing the seam.
        fail_start: Make the double's ``start`` raise.

    Returns:
        The list the seam appends every constructed double to — ``[0]`` after one build.
    """
    made: list[_RecordingSandbox] = []

    def factory(activation: SandboxConfig) -> _RecordingSandbox:
        double = _RecordingSandbox(activation, fail_start=fail_start)
        made.append(double)

        return double

    monkeypatch.setattr(sandbox_plugin_module, "Sandbox", factory)

    return made


class TestSandboxPluginContract:
    """Declared API of the ``SandboxPlugin`` entity."""

    def test_sandbox_plugin_is_importable_from_plugin_facade(self):
        """``SandboxPlugin`` is re-exported by the ``goga_tool_pybuggy.plugin`` facade."""
        from goga_tool_pybuggy import plugin

        assert inspect.isclass(plugin.SandboxPlugin)
        assert "SandboxPlugin" in plugin.__all__

    def test_sandbox_plugin_constructor_takes_no_arguments(self):
        """The constructor takes nothing — the activation arrives with ``configure``."""
        parameters = list(inspect.signature(SandboxPlugin.__init__).parameters)

        assert parameters == ["self"]

    def test_sandbox_plugin_meta_declares_the_name_and_the_document(self):
        """The plugin name is ``pybuggy-sandbox``; its config file is the sandbox document."""
        plugin = SandboxPlugin()

        assert plugin.meta.name == "pybuggy-sandbox"
        assert plugin.meta.config_file == ".goga/tools/pybuggy/sandbox.yml"

    def test_sandbox_plugin_declares_no_options(self):
        """The plugin carries zero ``define.option`` members."""
        plugin = SandboxPlugin()

        assert list(plugin.plugin_options) == []

    def test_sandbox_plugin_activation_defaults_to_none(self):
        """A fresh plugin is unconfigured — ``activation`` is ``None`` until ``configure``."""
        assert SandboxPlugin().activation is None


class TestSandboxPluginConfigure:
    """Configphase behavior: the marker registration and the document validation."""

    def test_configure_registers_the_marker_line(self, monkeypatch: pytest.MonkeyPatch):
        """``configure`` registers ``pybuggy_services`` pre-collection, warning-free."""
        plugin = SandboxPlugin()
        monkeypatch.setattr(type(plugin), "plugin_config", VALID_DOCUMENT, raising=False)
        config = _FakePytestConfig()
        plugin.init_pytest_config(config)

        plugin.configure()

        assert len(config.lines) == 1
        assert config.lines[0][0] == "markers"
        assert config.lines[0][1].startswith("pybuggy_services:")

    def test_configure_builds_the_activation_from_the_document(self, monkeypatch: pytest.MonkeyPatch):
        """A valid document validates into the activation the fixtures consume."""
        plugin = _configured_plugin(monkeypatch)

        assert isinstance(plugin.activation, SandboxConfig)
        assert plugin.activation.instance.image == "my-service:latest"
        assert plugin.activation.services["db"].kind == "postgresql"

    def test_configure_fails_on_the_empty_document(self, monkeypatch: pytest.MonkeyPatch):
        """A present-but-empty document is an invalid document — the run stops at configphase."""
        plugin = SandboxPlugin()
        monkeypatch.setattr(type(plugin), "plugin_config", {}, raising=False)
        plugin.init_pytest_config(_FakePytestConfig())

        with pytest.raises(ValueError, match=r"sandbox\.yml.*must carry the instance entry"):
            plugin.configure()

        assert plugin.activation is None

    def test_configure_wraps_the_parse_error_naming_the_document(self, monkeypatch: pytest.MonkeyPatch):
        """A document the config reader cannot parse fails naming the location, not a raw
        parser traceback."""

        class _RefusingPlugin(SandboxPlugin):
            @property
            def plugin_config(self) -> dict:
                raise YAMLError("bad indentation")

        plugin = _RefusingPlugin()
        plugin.init_pytest_config(_FakePytestConfig())

        with pytest.raises(ValueError, match=r"sandbox\.yml: unparsable document.*bad indentation"):
            plugin.configure()

    def test_configure_fails_on_the_invalid_document_before_any_container(self, monkeypatch: pytest.MonkeyPatch):
        """An invalid document surfaces the validation error of the config cell."""
        plugin = SandboxPlugin()
        monkeypatch.setattr(
            type(plugin),
            "plugin_config",
            {"instance": {"image": "i", "port": 1, "env": {}}, "services": {"db": {"kind": "mysql"}}},
            raising=False,
        )
        plugin.init_pytest_config(_FakePytestConfig())

        with pytest.raises(
            ValueError, match=r"mysql.*not one of the supported kinds \(postgresql, kafka, vault, http, redis\)"
        ):
            plugin.configure()


class TestSandboxPluginSessionFixture:
    """The session-scoped ``sandbox`` fixture: lazy start, finalization stop."""

    def test_sandbox_starts_on_first_use_and_stops_on_exhaustion(self, monkeypatch: pytest.MonkeyPatch):
        """``next`` starts the sandbox; exhausting the generator stops it."""
        plugin = _configured_plugin(monkeypatch)
        made = _wire_recording_sandbox(monkeypatch)

        generator = SandboxPlugin.sandbox.__wrapped__(plugin)
        sandbox = next(generator)

        assert sandbox is made[0]
        assert made[0].started
        assert made[0].calls == ["start"]

        with pytest.raises(StopIteration):
            next(generator)

        assert made[0].stopped
        assert made[0].calls == ["start", "stop"]

    def test_sandbox_constructs_the_sandbox_with_the_activation(self, monkeypatch: pytest.MonkeyPatch):
        """The session sandbox is built from the activation ``configure`` validated."""
        plugin = _configured_plugin(monkeypatch)
        made = _wire_recording_sandbox(monkeypatch)

        generator = SandboxPlugin.sandbox.__wrapped__(plugin)
        next(generator)

        assert made[0].activation is plugin.activation

    def test_sandbox_fails_fast_when_the_plugin_is_not_configured(self):
        """Driving the fixture on an unconfigured plugin names the missing configure step."""
        with pytest.raises(RuntimeError, match=r"configure\(\) did not run"):
            next(SandboxPlugin.sandbox.__wrapped__(SandboxPlugin()))

    def test_sandbox_propagates_a_failed_start(self, monkeypatch: pytest.MonkeyPatch):
        """A failing start surfaces on the first use — the run fails before any test body."""
        plugin = _configured_plugin(monkeypatch)
        _wire_recording_sandbox(monkeypatch, fail_start=True)

        with pytest.raises(RuntimeError, match="refused to start"):
            next(SandboxPlugin.sandbox.__wrapped__(plugin))


class TestSandboxPluginTestBatchFixture:
    """The autouse per-test batch fixture: reset, fresh batch, preset enqueue."""

    def test_batch_fixture_is_inert_without_the_sandbox_in_the_closure(self):
        """A test that does not use the sandbox never triggers the lookup."""
        plugin = SandboxPlugin()
        request = _FakeRequest(fixturenames=["api"])

        SandboxPlugin._sandbox_test_batch.__wrapped__(plugin, request)

        assert request.lookups == []

    def test_batch_fixture_resets_then_enqueues_the_marked_presets(self, monkeypatch: pytest.MonkeyPatch):
        """The order is ``clear`` -> ``new_test_batch`` -> one enqueue per marked preset."""
        plugin = SandboxPlugin()
        double = _RecordingSandbox(plugin.activation)
        marker = pytest.mark.pybuggy_services(presets={"postgresql": {"db": [{"table": "t", "rows": []}]}})
        request = _FakeRequest(fixturenames=["api", "sandbox"], node=_FakeNode([marker]), sandbox=double)

        SandboxPlugin._sandbox_test_batch.__wrapped__(plugin, request)

        assert double.calls == ["clear", "new_test_batch", "enqueue_presets"]
        assert double.enqueued == [{"postgresql": {"db": [{"table": "t", "rows": []}]}}]

    def test_batch_fixture_enqueues_every_marker_in_carried_order(self):
        """Several ``pybuggy_services`` markers enqueue in the order the item carries them."""
        plugin = SandboxPlugin()
        double = _RecordingSandbox(plugin.activation)
        first = pytest.mark.pybuggy_services(presets={"postgresql": {"db": [{"table": "a", "rows": []}]}})
        second = pytest.mark.pybuggy_services(presets={"http": {"payments": [{"request": {}}]}})
        request = _FakeRequest(fixturenames=["sandbox"], node=_FakeNode([first, second]), sandbox=double)

        SandboxPlugin._sandbox_test_batch.__wrapped__(plugin, request)

        assert double.enqueued == [
            {"postgresql": {"db": [{"table": "a", "rows": []}]}},
            {"http": {"payments": [{"request": {}}]}},
        ]

    def test_batch_fixture_skips_a_marker_without_presets(self):
        """A marker carrying no ``presets`` kwarg enqueues an empty mapping — a no-op."""
        plugin = SandboxPlugin()
        double = _RecordingSandbox(plugin.activation)
        bare = pytest.mark.pybuggy_services()
        request = _FakeRequest(fixturenames=["sandbox"], node=_FakeNode([bare]), sandbox=double)

        SandboxPlugin._sandbox_test_batch.__wrapped__(plugin, request)

        assert double.calls == ["clear", "new_test_batch", "enqueue_presets"]
        assert double.enqueued == [{}]
