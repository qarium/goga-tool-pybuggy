"""Contract and logic tests for the ``HttpEngine`` entity."""

import inspect

import pytest
import requests
from goga_tool_pybuggy.sandbox.config import InstanceConfig
from goga_tool_pybuggy.sandbox.engines import BaseEngine, DataOperation, EngineError, HttpEngine
from goga_tool_pybuggy.sandbox.engines import http as http_module

from ..conftest import requires_docker


def payments_engine(image: str | None = None) -> HttpEngine:
    """Build an http engine of the sample ``payments`` instance.

    Args:
        image: The optional image override of the instance declaration.

    Returns:
        The engine of an instance named ``payments`` of kind ``http``.
    """
    return HttpEngine(InstanceConfig(name="payments", kind="http", image=image))


def stub_op(mapping: dict[str, object]) -> DataOperation:
    """Build one http stub operation.

    Args:
        mapping: The mapping declaration the stub operation carries.

    Returns:
        A sample ``stub`` operation targeted at the ``payments`` instance.
    """
    return DataOperation(instance="payments", kind="http", action="stub", payload=mapping)


def charge_mapping(name: str = "payment-provider-charge") -> dict[str, object]:
    """Build the sample mapping declaration — priority and delay ride along untouched.

    Args:
        name: The name carried by the mapping declaration.

    Returns:
        A wiremock mapping declaration with matcher, priority and fixed delay.
    """
    return {
        "name": name,
        "priority": 1,
        "request": {"method": "POST", "urlPath": "/v1/charge", "headers": {"X-Api-Key": {"equalTo": "secret"}}},
        "response": {"status": 200, "jsonBody": {"status": "captured"}, "fixedDelayMilliseconds": 50},
    }


def status_mapping() -> dict[str, object]:
    """Build the unnamed sample mapping declaration matching a status path.

    Returns:
        A wiremock mapping declaration without a name — the matched path identifies it.
    """
    return {"request": {"method": "GET", "urlPath": "/v1/status"}, "response": {"status": 200}}


class FakeResponse:
    """Response double carrying a status and a JSON body."""

    def __init__(self, status_code: int, body: dict[str, object] | None = None) -> None:
        self.status_code = status_code
        self.body = body if body is not None else {}

    def json(self) -> dict[str, object]:
        return self.body


class FakeRequests:
    """Namespace double of ``requests`` recording probes and posts, serving scripted responses."""

    RequestException = requests.RequestException

    def __init__(
        self,
        statuses: list[int] | None = None,
        post_responses: list[FakeResponse] | None = None,
        probe_errors: int = 0,
    ) -> None:
        self.statuses = list(statuses or [])
        self.post_responses = list(post_responses or [])
        self.probe_errors = probe_errors
        self.probes: list[tuple[str, int | None]] = []
        self.posts: list[tuple[str, object, int | None]] = []

    def get(self, url: str, timeout: int | None = None) -> FakeResponse:
        self.probes.append((url, timeout))

        if self.probe_errors:
            self.probe_errors -= 1
            raise self.RequestException(url)

        status = self.statuses.pop(0) if self.statuses else 200

        return FakeResponse(status)

    def post(self, url: str, json: object = None, timeout: int | None = None) -> FakeResponse:
        self.posts.append((url, json, timeout))

        if self.post_responses:
            return self.post_responses.pop(0)

        return FakeResponse(200, {"id": "fake"})


class FakeTime:
    """Namespace double of ``time`` — instant monotonic, no sleeping."""

    def __init__(self) -> None:
        self.now = 100.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakeDockerContainer:
    """Container double recording the build configuration and the mapped address."""

    def __init__(self, image: str, **kwargs: object) -> "FakeDockerContainer":
        self.image = image
        self.kwargs = kwargs
        self.exposed_ports: list[int] = []
        self.env: dict[str, str] = {}
        self.command: str | list[str] | None = None
        self.network: object | None = None
        self.network_aliases: list[str] = []
        self.stops = 0
        self.starts = 0

    def with_network(self, network: object) -> "FakeDockerContainer":
        self.network = network

        return self

    def with_network_aliases(self, *aliases: str) -> "FakeDockerContainer":
        self.network_aliases.extend(aliases)

        return self

    def start(self) -> "FakeDockerContainer":
        self.starts += 1

        return self

    def with_exposed_ports(self, *ports: int) -> "FakeDockerContainer":
        self.exposed_ports.extend(ports)

        return self

    def with_env(self, key: str, value: str) -> "FakeDockerContainer":
        self.env[key] = value

        return self

    def with_command(self, command: str | list[str]) -> "FakeDockerContainer":
        self.command = command

        return self

    def get_container_host_ip(self) -> str:
        return "127.0.0.2"

    def get_exposed_port(self, port: int) -> str:
        return {8080: "18080"}[port]

    def stop(self) -> None:
        self.stops += 1


def armed_engine(monkeypatch: pytest.MonkeyPatch, fake_requests: FakeRequests) -> HttpEngine:
    """Build an http engine whose container and requests seams are faked.

    Args:
        monkeypatch: The pytest monkeypatch fixture swapping the module seams.
        fake_requests: The recording requests double serving the probes and posts.

    Returns:
        An http engine driven entirely over the fakes — no daemon, no network.
    """
    monkeypatch.setattr(http_module, "DockerContainer", FakeDockerContainer)
    monkeypatch.setattr(http_module, "requests", fake_requests)
    monkeypatch.setattr(http_module, "time", FakeTime())

    return payments_engine()


class TestHttpEngineContract:
    """Declared API of the ``HttpEngine`` entity."""

    def test_http_engine_is_importable_from_engines_facade(self):
        """``HttpEngine`` is re-exported by the ``goga_tool_pybuggy.sandbox.engines`` facade."""
        assert HttpEngine is not None

    def test_http_engine_subclasses_base_engine(self):
        """The kind engine inherits the base contract."""
        assert issubclass(HttpEngine, BaseEngine)

    def test_http_engine_declares_the_contract_constructor(self):
        """The constructor signature is ``__init__(self, config)``."""
        signature = inspect.signature(HttpEngine.__init__)

        assert list(signature.parameters) == ["self", "config"]

    def test_http_engine_inherits_the_contract_methods(self):
        """``start`` / ``apply`` / ``record`` / ``reset`` / ``stop`` resolve with declared parameters."""
        expected = {
            "start": ["self", "startup", "network"],
            "apply": ["self", "operations"],
            "record": ["self", "operations"],
            "reset": ["self"],
            "stop": ["self"],
        }

        for method, parameters in expected.items():
            assert list(inspect.signature(getattr(HttpEngine, method)).parameters) == parameters

    def test_http_engine_inherits_the_address_property(self):
        """The ``address`` property of the base resolves on the kind engine."""
        address = inspect.getattr_static(HttpEngine, "address")

        assert isinstance(address, property)


class TestHttpEngineBuild:
    """Container build arguments of the http engine, driven through the patched constructor."""

    def test_build_uses_the_pinned_image_labels_and_port(self, monkeypatch: pytest.MonkeyPatch):
        """Without an image override the build uses the pinned image, labels, the admin port."""
        monkeypatch.setattr(http_module, "DockerContainer", FakeDockerContainer)
        engine = payments_engine()

        container = engine._build_container()

        assert container.image == "wiremock/wiremock:3.13.0"
        assert container.kwargs["labels"] == {"pybuggy-sandbox": "true"}
        assert container.exposed_ports == [8080]

    def test_build_honors_the_image_override(self, monkeypatch: pytest.MonkeyPatch):
        """The image override of the instance config reaches the container build."""
        monkeypatch.setattr(http_module, "DockerContainer", FakeDockerContainer)
        engine = payments_engine(image="wiremock/wiremock:3.14.0")

        container = engine._build_container()

        assert container.image == "wiremock/wiremock:3.14.0"


class TestHttpEngineReadiness:
    """Admin-endpoint probing of the http engine, driven over the fake requests namespace."""

    def test_wait_ready_probes_health_until_success(self, monkeypatch: pytest.MonkeyPatch):
        """The probe polls the mapped 3.x health endpoint on the readiness interval."""
        fake_requests = FakeRequests(statuses=[503, 503])
        monkeypatch.setattr(http_module, "requests", fake_requests)
        monkeypatch.setattr(http_module, "time", FakeTime())
        engine = payments_engine()
        engine._container = FakeDockerContainer("wiremock/wiremock:3.13.0")

        engine._wait_ready()

        assert fake_requests.probes == [("http://127.0.0.2:18080/__admin/health", 5)] * 3

    def test_wait_ready_falls_back_to_mappings_on_missing_health(self, monkeypatch: pytest.MonkeyPatch):
        """A 404 health answer falls back to the mappings endpoint of older versions."""
        fake_requests = FakeRequests(statuses=[404, 200])
        monkeypatch.setattr(http_module, "requests", fake_requests)
        monkeypatch.setattr(http_module, "time", FakeTime())
        engine = payments_engine()
        engine._container = FakeDockerContainer("wiremock/wiremock:3.13.0")

        engine._wait_ready()

        assert fake_requests.probes == [
            ("http://127.0.0.2:18080/__admin/health", 5),
            ("http://127.0.0.2:18080/__admin/mappings", 5),
        ]

    def test_wait_ready_retries_connection_failures(self, monkeypatch: pytest.MonkeyPatch):
        """A refused connection keeps the loop probing until the endpoint answers."""
        fake_requests = FakeRequests(statuses=[200], probe_errors=1)
        monkeypatch.setattr(http_module, "requests", fake_requests)
        monkeypatch.setattr(http_module, "time", FakeTime())
        engine = payments_engine()
        engine._container = FakeDockerContainer("wiremock/wiremock:3.13.0")

        engine._wait_ready()

        assert fake_requests.probes == [("http://127.0.0.2:18080/__admin/health", 5)] * 2

    def test_wait_ready_fails_past_the_deadline(self, monkeypatch: pytest.MonkeyPatch):
        """An admin endpoint that never answers fails within the 30s deadline."""
        fake_requests = FakeRequests(statuses=[404, 500] * 100)
        monkeypatch.setattr(http_module, "requests", fake_requests)
        monkeypatch.setattr(http_module, "time", FakeTime())
        engine = payments_engine()
        engine._container = FakeDockerContainer("wiremock/wiremock:3.13.0")

        with pytest.raises(RuntimeError, match=r"admin endpoint.*did not succeed"):
            engine._wait_ready()

        assert fake_requests.probes[0] == ("http://127.0.0.2:18080/__admin/health", 5)


class TestHttpEnginePlane:
    """Admin plane, execution and wipe of the http engine, driven over the fakes."""

    def test_execute_stub_posts_the_mapping_through_untouched(self, monkeypatch: pytest.MonkeyPatch):
        """A ``stub`` posts the mapping object as given — priority and delay ride along."""
        fake_requests = FakeRequests()
        monkeypatch.setattr(http_module, "requests", fake_requests)
        engine = payments_engine()
        engine._container = FakeDockerContainer("wiremock/wiremock:3.13.0")
        mapping = charge_mapping()

        engine._execute(stub_op(mapping))

        assert fake_requests.posts == [("http://127.0.0.2:18080/__admin/mappings", mapping, 5)]

    def test_execute_failed_post_names_the_mapping(self, monkeypatch: pytest.MonkeyPatch):
        """A rejected mapping post surfaces as a readable error naming the mapping and status."""
        fake_requests = FakeRequests(post_responses=[FakeResponse(400, {"detail": "invalid mapping"})])
        monkeypatch.setattr(http_module, "requests", fake_requests)
        engine = payments_engine()
        engine._container = FakeDockerContainer("wiremock/wiremock:3.13.0")

        with pytest.raises(RuntimeError, match=r"payment-provider-charge.*400.*invalid mapping"):
            engine._execute(stub_op(charge_mapping()))

    def test_execute_failed_post_names_the_matched_path_without_name(self, monkeypatch: pytest.MonkeyPatch):
        """An unnamed mapping is identified by its matched request path in the failure."""
        fake_requests = FakeRequests(post_responses=[FakeResponse(400, {"detail": "invalid mapping"})])
        monkeypatch.setattr(http_module, "requests", fake_requests)
        engine = payments_engine()
        engine._container = FakeDockerContainer("wiremock/wiremock:3.13.0")

        with pytest.raises(RuntimeError, match=r"/v1/status.*400"):
            engine._execute(stub_op(status_mapping()))

    def test_execute_failed_post_wraps_into_engine_error_through_apply(self, monkeypatch: pytest.MonkeyPatch):
        """Through the base apply path the failed post names the instance and the action."""
        fake_requests = FakeRequests(post_responses=[FakeResponse(400, {"detail": "invalid mapping"})])
        monkeypatch.setattr(http_module, "requests", fake_requests)
        engine = payments_engine()
        engine._container = FakeDockerContainer("wiremock/wiremock:3.13.0")
        engine._started = True

        with pytest.raises(EngineError, match=r"instance 'payments': stub failed.*payment-provider-charge"):
            engine.apply([stub_op(charge_mapping())])

    def test_wipe_posts_the_admin_mappings_reset(self, monkeypatch: pytest.MonkeyPatch):
        """Reset-wipe drops the API-created mappings over the admin reset endpoint."""
        fake_requests = FakeRequests()
        monkeypatch.setattr(http_module, "requests", fake_requests)
        engine = payments_engine()
        engine._container = FakeDockerContainer("wiremock/wiremock:3.13.0")

        engine._wipe()

        assert fake_requests.posts == [("http://127.0.0.2:18080/__admin/mappings/reset", None, 5)]

    def test_wipe_failure_names_the_reset(self, monkeypatch: pytest.MonkeyPatch):
        """A rejected reset post surfaces as a readable error naming the reset and status."""
        fake_requests = FakeRequests(post_responses=[FakeResponse(500, {"detail": "broken"})])
        monkeypatch.setattr(http_module, "requests", fake_requests)
        engine = payments_engine()
        engine._container = FakeDockerContainer("wiremock/wiremock:3.13.0")

        with pytest.raises(RuntimeError, match=r"mappings reset failed with status 500"):
            engine._wipe()

    def test_close_plane_is_a_noop_and_safe_twice(self):
        """Stop needs no plane close — requests is stateless; a second close touches nothing."""
        engine = payments_engine()

        engine._close_plane()
        engine._close_plane()


class TestHttpEngineLifecycle:
    """Full lifecycle of the http engine over the fakes — start, journal, reset, stop."""

    def test_start_applies_startup_stubs_and_journals_them(self, monkeypatch: pytest.MonkeyPatch):
        """Startup stubs execute in order and join the journal as the initial baseline."""
        fake_requests = FakeRequests()
        engine = armed_engine(monkeypatch, fake_requests)
        baseline = [stub_op(charge_mapping()), stub_op(status_mapping())]

        engine.start(baseline)

        try:
            container = engine._container
            assert container is not None
            assert container.starts == 1
            assert fake_requests.probes == [("http://127.0.0.2:18080/__admin/health", 5)]
            assert [(post[0], post[1]) for post in fake_requests.posts] == [
                ("http://127.0.0.2:18080/__admin/mappings", charge_mapping()),
                ("http://127.0.0.2:18080/__admin/mappings", status_mapping()),
            ]
            assert engine._journal == baseline
        finally:
            engine.stop()

        assert engine._container is None

    def test_reset_replays_the_journal_after_the_mappings_reset(self, monkeypatch: pytest.MonkeyPatch):
        """Reset drops the API-created mappings and replays the journaled baseline stubs."""
        fake_requests = FakeRequests()
        engine = armed_engine(monkeypatch, fake_requests)
        engine._container = FakeDockerContainer("wiremock/wiremock:3.13.0")
        engine._started = True
        engine._journal = [stub_op(charge_mapping())]

        engine.reset()

        assert [(post[0], post[1]) for post in fake_requests.posts] == [
            ("http://127.0.0.2:18080/__admin/mappings/reset", None),
            ("http://127.0.0.2:18080/__admin/mappings", charge_mapping()),
        ]

    def test_stop_is_safe_twice(self, monkeypatch: pytest.MonkeyPatch):
        """A second stop touches nothing — the container is removed exactly once."""
        fake_requests = FakeRequests()
        engine = armed_engine(monkeypatch, fake_requests)
        engine.start([])

        container = engine._container
        engine.stop()
        engine.stop()

        assert container is not None
        assert container.stops == 1


@requires_docker
class TestHttpEngineContainer:
    """Live behavior of the http engine against a real container (docker-gated)."""

    def test_http_engine_stub_and_admin_reset(self):
        """Reset drops the API-created mappings; only the journaled baseline mappings replay."""
        engine = payments_engine()
        baseline = stub_op(charge_mapping())
        engine.start([baseline])

        try:
            base = f"http://{engine.address.host}:{engine.address.port}"
            engine.apply([stub_op(status_mapping())])

            while_active = requests.get(f"{base}/__admin/mappings", timeout=5).json()
            active_names = {mapping.get("name") for mapping in while_active["mappings"]}
            assert "payment-provider-charge" in active_names
            assert "/v1/status" in {mapping.get("request", {}).get("urlPath") for mapping in while_active["mappings"]}

            engine.reset()

            after_reset = requests.get(f"{base}/__admin/mappings", timeout=5).json()
            reset_names = {mapping.get("name") for mapping in after_reset["mappings"]}
            assert reset_names == {"payment-provider-charge"}
        finally:
            engine.stop()

        engine.stop()
