"""Contract and logic tests for the ``ServiceContainer`` entity."""

import inspect
import time

import pytest
import requests
from goga_tool_pybuggy.sandbox.config import ServiceConfig
from goga_tool_pybuggy.sandbox.service_container import ServiceContainer

from .conftest import requires_docker


def service_config(health: str | None = None, port: int = 8080) -> ServiceConfig:
    """Build the service declaration of the sample service under test.

    Args:
        health: The optional health path of the declaration; ``None`` selects port readiness.
        port: The container port the service serves on.

    Returns:
        A ``ServiceConfig`` of the pinned wiremock sample image.
    """
    return ServiceConfig(image="wiremock/wiremock:3.13.0", env={}, port=port, health=health)


class FakeWrappedContainer:
    """Double of the docker SDK container object recording reloads and serving output."""

    def __init__(self, status: str = "running", output: bytes = b"boot ok\n") -> None:
        self.status = status
        self.output = output
        self.reloads = 0

    def reload(self) -> None:
        self.reloads += 1

    def logs(self, **kwargs: object) -> bytes:
        return self.output


class FakeDockerContainer:
    """Container double recording the build configuration and the mapped address."""

    def __init__(self, image: str, **kwargs: object) -> "FakeDockerContainer":
        self.image = image
        self.kwargs = kwargs
        self.exposed_ports: list[int] = []
        self.env: dict[str, str] = {}
        self.wrapped = FakeWrappedContainer()
        self.stops = 0
        self.starts = 0

    def start(self) -> "FakeDockerContainer":
        self.starts += 1

        return self

    def with_exposed_ports(self, *ports: int) -> "FakeDockerContainer":
        self.exposed_ports.extend(ports)

        return self

    def with_env(self, key: str, value: str) -> "FakeDockerContainer":
        self.env[key] = value

        return self

    def get_container_host_ip(self) -> str:
        return "127.0.0.2"

    def get_exposed_port(self, port: int) -> str:
        return {8080: "18080"}[port]

    def get_wrapped_container(self) -> FakeWrappedContainer:
        return self.wrapped

    def stop(self) -> None:
        self.stops += 1


class FakeResponse:
    """Response double carrying a status code."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeRequests:
    """Namespace double of ``requests`` recording probes, serving scripted statuses."""

    RequestException = requests.RequestException

    def __init__(self, statuses: list[int] | None = None) -> None:
        self.statuses = list(statuses or [])
        self.probes: list[tuple[str, int | None]] = []

    def get(self, url: str, timeout: int | None = None) -> FakeResponse:
        self.probes.append((url, timeout))
        status = self.statuses.pop(0) if self.statuses else 200

        return FakeResponse(status)


class FakeTime:
    """Namespace double of ``time`` — instant monotonic, no sleeping."""

    def __init__(self) -> None:
        self.now = 100.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class FakePortProbe:
    """Port-probe double answering scripted open/closed results, recording targets."""

    def __init__(self, results: list[bool]) -> None:
        self.results = list(results)
        self.targets: list[tuple[str, int]] = []

    def __call__(self, host: str, port: int, timeout: float = 1.0) -> bool:
        self.targets.append((host, port))
        result = self.results.pop(0) if self.results else True

        return result


def started_container(
    monkeypatch: pytest.MonkeyPatch,
    fake_requests: FakeRequests | None = None,
    fake_probe: FakePortProbe | None = None,
    config: ServiceConfig | None = None,
) -> tuple[ServiceContainer, FakeDockerContainer]:
    """Build a service container whose container, probe and HTTP seams are faked and start it.

    Args:
        monkeypatch: The pytest monkeypatch fixture swapping the module seams.
        fake_requests: The recording requests double serving the health probes.
        fake_probe: The recording port-probe double answering the port probes.
        config: The service declaration; defaults to the port-readiness sample.

    Returns:
        The started service container and its fake container double.
    """
    from goga_tool_pybuggy.sandbox import service_container as module

    monkeypatch.setattr(module, "DockerContainer", FakeDockerContainer)
    monkeypatch.setattr(module, "time", FakeTime())
    monkeypatch.setattr(module, "_tcp_port_open", fake_probe if fake_probe is not None else FakePortProbe([True]))

    if fake_requests is not None:
        monkeypatch.setattr(module, "requests", fake_requests)

    container = ServiceContainer(config if config is not None else service_config())
    container.start({"K": "v"})

    wrapped = container._container

    return container, wrapped


class TestServiceContainerContract:
    """Declared API of the ``ServiceContainer`` entity."""

    def test_service_container_is_importable_from_service_container_module(self):
        """``ServiceContainer`` lives in ``goga_tool_pybuggy.sandbox.service_container``."""
        assert ServiceContainer is not None

    def test_service_container_declares_the_contract_constructor(self):
        """The constructor signature is ``__init__(self, config)``."""
        signature = inspect.signature(ServiceContainer.__init__)

        assert list(signature.parameters) == ["self", "config"]

    def test_service_container_declares_the_contract_methods(self):
        """``start`` / ``stop`` / ``alive`` / ``logs`` resolve with declared parameters."""
        expected = {
            "start": ["self", "env", "network"],
            "stop": ["self"],
            "alive": ["self"],
            "logs": ["self"],
        }

        for method, parameters in expected.items():
            assert list(inspect.signature(getattr(ServiceContainer, method)).parameters) == parameters

    def test_service_container_declares_the_address_properties(self):
        """``host`` / ``port`` resolve as properties."""
        for name in ("host", "port"):
            attribute = inspect.getattr_static(ServiceContainer, name)

            assert isinstance(attribute, property), name


class TestServiceContainerStart:
    """Container build and readiness of the service container, driven over the fakes."""

    def test_start_builds_image_labels_port_and_env_then_starts(self, monkeypatch: pytest.MonkeyPatch):
        """The build carries the declared image, the sandbox labels, the port and the rendered env."""
        from goga_tool_pybuggy.sandbox import service_container as module

        monkeypatch.setattr(module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(module, "time", FakeTime())
        monkeypatch.setattr(module, "_tcp_port_open", FakePortProbe([True]))
        container = ServiceContainer(service_config())

        container.start({"K": "v", "DATABASE_URL": "postgres://h:1/x"})

        wrapped = container._container
        assert wrapped is not None
        assert wrapped.image == "wiremock/wiremock:3.13.0"
        assert wrapped.kwargs["labels"] == {"pybuggy-sandbox": "true"}
        assert wrapped.exposed_ports == [8080]
        assert wrapped.env == {"K": "v", "DATABASE_URL": "postgres://h:1/x"}
        assert wrapped.starts == 1

    def test_start_waits_for_the_mapped_port_when_health_is_none(self, monkeypatch: pytest.MonkeyPatch):
        """Without a health path readiness polls the mapped port until it accepts connections."""
        probe = FakePortProbe([False, False, True])
        _, wrapped = started_container(monkeypatch, fake_probe=probe)

        assert wrapped is not None
        assert probe.targets == [("127.0.0.2", 18080)] * 3

    def test_start_probes_the_health_path_until_2xx(self, monkeypatch: pytest.MonkeyPatch):
        """With a health path readiness polls the mapped health endpoint until it answers 2xx."""
        fake_requests = FakeRequests(statuses=[503, 500, 200])
        config = service_config(health="/__admin/health")

        _, wrapped = started_container(monkeypatch, fake_requests=fake_requests, config=config)

        assert wrapped is not None
        assert fake_requests.probes == [("http://127.0.0.2:18080/__admin/health", 5)] * 3

    def test_start_port_readiness_fails_past_the_deadline(self, monkeypatch: pytest.MonkeyPatch):
        """A port that never accepts connections fails within the deadline."""
        from goga_tool_pybuggy.sandbox import service_container as module

        monkeypatch.setattr(module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(module, "time", FakeTime())
        monkeypatch.setattr(module, "_tcp_port_open", FakePortProbe([False] * 100))
        container = ServiceContainer(service_config())

        with pytest.raises(RuntimeError, match=r"port.*did not accept.*30s"):
            container.start({})

    def test_start_health_readiness_fails_past_the_deadline(self, monkeypatch: pytest.MonkeyPatch):
        """A health endpoint that never answers 2xx fails within the deadline."""
        from goga_tool_pybuggy.sandbox import service_container as module

        monkeypatch.setattr(module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(module, "time", FakeTime())
        fake_requests = FakeRequests(statuses=[503] * 100)
        monkeypatch.setattr(module, "requests", fake_requests)
        container = ServiceContainer(service_config(health="/healthz"))

        with pytest.raises(RuntimeError, match=r"health.*did not succeed.*30s"):
            container.start({})

    def test_host_and_port_read_back_from_the_container_engine(self, monkeypatch: pytest.MonkeyPatch):
        """``host`` / ``port`` carry the mapped values, port as an ``int``."""
        container, wrapped = started_container(monkeypatch)

        assert wrapped is not None
        assert container.host == "127.0.0.2"
        assert container.port == 18080
        assert isinstance(container.port, int)

    def test_host_and_port_fail_before_start(self):
        """Reading the mapped address before start fails — there is nothing mapped yet."""
        container = ServiceContainer(service_config())

        with pytest.raises(RuntimeError, match=r"before start"):
            assert container.host

        with pytest.raises(RuntimeError, match=r"before start"):
            assert container.port


class TestServiceContainerLiveness:
    """Liveness and diagnostics of the service container, driven over the fakes."""

    def test_alive_reloads_and_reports_a_running_service(self, monkeypatch: pytest.MonkeyPatch):
        """``alive`` reloads the SDK status and reports True while the service runs."""
        container, wrapped = started_container(monkeypatch)

        assert wrapped is not None
        assert container.alive() is True
        assert wrapped.wrapped.reloads == 1

    def test_alive_reports_a_dead_service(self, monkeypatch: pytest.MonkeyPatch):
        """A non-running SDK status reports False — the died service is detectable."""
        container, wrapped = started_container(monkeypatch)

        assert wrapped is not None
        wrapped.wrapped.status = "exited"

        assert container.alive() is False

    def test_alive_is_false_before_start_and_after_stop(self, monkeypatch: pytest.MonkeyPatch):
        """Without a started container liveness is False — before start and after stop alike."""
        from goga_tool_pybuggy.sandbox import service_container as module

        assert ServiceContainer(service_config()).alive() is False

        monkeypatch.setattr(module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(module, "time", FakeTime())
        monkeypatch.setattr(module, "_tcp_port_open", FakePortProbe([True]))
        container = ServiceContainer(service_config())
        container.start({})

        container.stop()

        assert container.alive() is False

    def test_logs_return_the_container_output_as_str(self, monkeypatch: pytest.MonkeyPatch):
        """``logs`` decodes the container output — the died-service diagnostic payload."""
        config = service_config()
        from goga_tool_pybuggy.sandbox import service_container as module

        monkeypatch.setattr(module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(module, "time", FakeTime())
        monkeypatch.setattr(module, "_tcp_port_open", FakePortProbe([True]))
        container = ServiceContainer(config)
        container.start({})

        container._container.wrapped.output = b"OOMKilled after boot\n\xff\xfe"

        assert container.logs() == "OOMKilled after boot\n��"

    def test_logs_of_a_stopped_service_are_empty(self, monkeypatch: pytest.MonkeyPatch):
        """A stopped service has no readable output — ``logs`` answers an empty string."""
        container, wrapped = started_container(monkeypatch)

        assert wrapped is not None
        container.stop()

        assert container.logs() == ""


class TestServiceContainerStop:
    """Teardown of the service container, driven over the fakes."""

    def test_stop_removes_the_container(self, monkeypatch: pytest.MonkeyPatch):
        """``stop`` removes the started container exactly once."""
        container, wrapped = started_container(monkeypatch)

        container.stop()

        assert wrapped is not None
        assert wrapped.stops == 1
        assert container._container is None

    def test_stop_is_safe_twice(self, monkeypatch: pytest.MonkeyPatch):
        """A second stop touches nothing — the container was already removed."""
        container, wrapped = started_container(monkeypatch)

        container.stop()
        container.stop()

        assert wrapped is not None
        assert wrapped.stops == 1

    def test_stop_removes_the_container_even_when_start_failed(self, monkeypatch: pytest.MonkeyPatch):
        """A container whose ``start`` raised is still reachable for the failed-start cleanup."""
        from goga_tool_pybuggy.sandbox import service_container as module

        class RefusingContainer(FakeDockerContainer):
            """Container double whose ``start`` always raises."""

            def start(self) -> "RefusingContainer":
                raise RuntimeError("port bind conflict")

        monkeypatch.setattr(module, "DockerContainer", RefusingContainer)
        container = ServiceContainer(service_config())

        with pytest.raises(RuntimeError, match="port bind conflict"):
            container.start({})

        built = container._container

        assert built is not None  # the failed start kept the created container reachable

        container.stop()

        assert built.stops == 1
        assert container._container is None

    def test_stop_swallows_a_failing_container_removal(self, monkeypatch: pytest.MonkeyPatch):
        """A failing container removal is logged, never raised — teardown of the rest proceeds."""
        container, wrapped = started_container(monkeypatch)

        def refusing_stop() -> None:
            raise RuntimeError("docker daemon gone")

        assert wrapped is not None
        wrapped.stop = refusing_stop

        container.stop()  # must not raise

        assert container._container is None

        container.stop()  # idempotent even after the failed removal


@requires_docker
class TestServiceContainerContainer:
    """Live behavior of the service container against a real container (docker-gated)."""

    @staticmethod
    def _get_until_answer(url: str) -> requests.Response:
        """GET until any answer arrives — TCP readiness can precede HTTP by a moment.

        The port branch waits only for a TCP accept; the first HTTP request may still hit
        a booting server or a resetting port proxy of the docker host.

        Args:
            url: The URL to request.

        Returns:
            The first response the endpoint answers with.

        Raises:
            requests.RequestException: The endpoint answered nothing within the deadline.
        """
        deadline = time.monotonic() + 10.0

        while True:
            try:
                return requests.get(url, timeout=5)
            except requests.RequestException:
                if time.monotonic() >= deadline:
                    raise

                time.sleep(0.5)

    def test_service_container_readiness_and_liveness_port_branch(self):
        """Variant A — port readiness: mapped address, liveness, output, stop safety."""
        container = ServiceContainer(service_config(health=None))

        container.start({"K": "v"})

        try:
            assert int(container.port) > 0
            assert len(container.host) > 0
            health = self._get_until_answer(f"http://{container.host}:{container.port}/__admin/health")
            assert health.status_code == 200
            assert container.alive() is True
            assert isinstance(container.logs(), str)
        finally:
            container.stop()

        container.stop()

        assert container.alive() is False

    def test_service_container_readiness_and_liveness_health_branch(self):
        """Variant B — health-path readiness against the wiremock admin health endpoint."""
        container = ServiceContainer(service_config(health="/__admin/health"))

        container.start({"K": "v"})

        try:
            assert int(container.port) > 0
            assert len(container.host) > 0
            health = requests.get(f"http://{container.host}:{container.port}/__admin/health", timeout=5)
            assert health.status_code == 200
            assert container.alive() is True
            assert isinstance(container.logs(), str)
        finally:
            container.stop()

        container.stop()

        assert container.alive() is False
