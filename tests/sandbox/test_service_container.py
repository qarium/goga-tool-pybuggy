"""Contract and logic tests for the ``ServiceContainer`` entity."""

import inspect
import re
import time

import pytest
import requests
from goga_tool_pybuggy.sandbox.config import InstanceConfig, ProbeConfig
from goga_tool_pybuggy.sandbox.engines import EngineError
from goga_tool_pybuggy.sandbox.service_container import ServiceContainer

from .conftest import requires_docker

SAMPLE_IMAGE = "wiremock/wiremock:3.13.0"


def instance_config(probe: ProbeConfig | None = None, port: int = 8080) -> InstanceConfig:
    """Build the instance-under-test declaration of the sample instance.

    Args:
        probe: The readiness declaration of the entry; ``None`` keeps the default wait — port
            readiness at the 30.0s deadline and 0.5s interval.
        port: The container port the instance serves on.

    Returns:
        An ``InstanceConfig`` of the pinned wiremock sample image.
    """
    return InstanceConfig(image=SAMPLE_IMAGE, env={}, port=port, probe=probe)


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
    """Namespace double of ``time`` — instant monotonic, sleeps recorded and applied."""

    def __init__(self) -> None:
        self.now = 100.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
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
    config: InstanceConfig | None = None,
) -> tuple[ServiceContainer, FakeDockerContainer]:
    """Build an instance container whose container, probe and HTTP seams are faked and start it.

    Args:
        monkeypatch: The pytest monkeypatch fixture swapping the module seams.
        fake_requests: The recording requests double serving the health probes.
        fake_probe: The recording port-probe double answering the port probes.
        config: The instance declaration; defaults to the port-readiness sample.

    Returns:
        The started instance container and its fake container double.
    """
    from goga_tool_pybuggy.sandbox import service_container as module

    monkeypatch.setattr(module, "DockerContainer", FakeDockerContainer)
    monkeypatch.setattr(module, "time", FakeTime())
    monkeypatch.setattr(module, "_tcp_port_open", fake_probe if fake_probe is not None else FakePortProbe([True]))

    if fake_requests is not None:
        monkeypatch.setattr(module, "requests", fake_requests)

    container = ServiceContainer(config if config is not None else instance_config())
    container.start({"K": "v"})

    wrapped = container._container

    return container, wrapped


class TestServiceContainerContract:
    """Declared API of the ``ServiceContainer`` entity."""

    def test_service_container_is_importable_from_service_container_module(self):
        """``ServiceContainer`` lives in ``goga_tool_pybuggy.sandbox.service_container``."""
        assert ServiceContainer is not None

    def test_service_container_declares_the_contract_constructor(self):
        """The constructor signature is ``__init__(self, config: InstanceConfig)``."""
        signature = inspect.signature(ServiceContainer.__init__)

        assert list(signature.parameters) == ["self", "config"]
        assert signature.parameters["config"].annotation is InstanceConfig

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

    def test_engine_error_is_importable_and_the_engine_failure_type(self):
        """Readiness expiry fails as ``EngineError`` — importable from the engines facade."""
        import goga_tool_pybuggy.sandbox.engines as engines_facade

        assert engines_facade.EngineError is EngineError
        assert issubclass(engines_facade.EngineError, RuntimeError)


class TestServiceContainerStart:
    """Container build and readiness of the instance container, driven over the fakes."""

    def test_start_builds_image_labels_port_and_env_then_starts(self, monkeypatch: pytest.MonkeyPatch):
        """The build carries the declared image, the sandbox labels, the port and the rendered env."""
        from goga_tool_pybuggy.sandbox import service_container as module

        monkeypatch.setattr(module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(module, "time", FakeTime())
        monkeypatch.setattr(module, "_tcp_port_open", FakePortProbe([True]))
        container = ServiceContainer(instance_config())

        container.start({"K": "v", "DATABASE_URL": "postgres://h:1/x"})

        wrapped = container._container
        assert wrapped is not None
        assert wrapped.image == SAMPLE_IMAGE
        assert wrapped.kwargs["labels"] == {"pybuggy-sandbox": "true"}
        assert wrapped.exposed_ports == [8080]
        assert wrapped.env == {"K": "v", "DATABASE_URL": "postgres://h:1/x"}
        assert wrapped.starts == 1

    def test_start_waits_for_the_mapped_port_when_no_probe_path_is_declared(self, monkeypatch: pytest.MonkeyPatch):
        """Without a probe path readiness polls the mapped port until it accepts connections."""
        probe = FakePortProbe([False, False, True])
        _, wrapped = started_container(monkeypatch, fake_probe=probe)

        assert wrapped is not None
        assert probe.targets == [("127.0.0.2", 18080)] * 3

    def test_start_probes_the_health_path_until_2xx(self, monkeypatch: pytest.MonkeyPatch):
        """With a probe path readiness polls the mapped health endpoint until it answers 2xx."""
        fake_requests = FakeRequests(statuses=[503, 500, 200])
        config = instance_config(probe=ProbeConfig(path="/__admin/health"))

        _, wrapped = started_container(monkeypatch, fake_requests=fake_requests, config=config)

        assert wrapped is not None
        assert fake_requests.probes == [("http://127.0.0.2:18080/__admin/health", 5)] * 3

    def test_service_container_port_only_default_and_health_path(self, monkeypatch: pytest.MonkeyPatch):
        """Scenario 26 — no probe keeps the TCP loop at 30.0/0.5; a probe path drives the GET loop."""
        from goga_tool_pybuggy.sandbox import service_container as module

        monkeypatch.setattr(module, "DockerContainer", FakeDockerContainer)

        # No probe: the port loop expires at the default 30.0s deadline, sleeping the default
        # 0.5s interval after every failed attempt.
        fake_time = FakeTime()
        monkeypatch.setattr(module, "time", fake_time)
        monkeypatch.setattr(module, "_tcp_port_open", FakePortProbe([False] * 100))
        container = ServiceContainer(instance_config())

        with pytest.raises(EngineError, match=r"within 30s"):
            container.start({})

        assert fake_time.sleeps == [0.5] * 60

        # No probe, success path: attempts spaced by the default interval.
        fake_time = FakeTime()
        port_probe = FakePortProbe([False, False, True])
        monkeypatch.setattr(module, "time", fake_time)
        monkeypatch.setattr(module, "_tcp_port_open", port_probe)
        container = ServiceContainer(instance_config())

        container.start({})

        assert port_probe.targets == [("127.0.0.2", 18080)] * 3
        assert fake_time.sleeps == [0.5, 0.5]

        # Declared probe with a path: the GET loop runs at the declared bounds.
        fake_time = FakeTime()
        fake_requests = FakeRequests(statuses=[503, 500, 200])
        monkeypatch.setattr(module, "time", fake_time)
        monkeypatch.setattr(module, "requests", fake_requests)
        container = ServiceContainer(instance_config(probe=ProbeConfig(path="/healthz", timeout=45.0, interval=1.0)))

        container.start({})

        assert fake_requests.probes == [("http://127.0.0.2:18080/healthz", 5)] * 3
        assert fake_time.sleeps == [1.0, 1.0]

    def test_service_container_deadline_expires_as_engine_error(self, monkeypatch: pytest.MonkeyPatch):
        """Scenario 27 — expiry fails as ``EngineError`` naming image, check and deadline."""
        from goga_tool_pybuggy.sandbox import service_container as module

        monkeypatch.setattr(module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(module, "_tcp_port_open", FakePortProbe([False] * 100))
        container = ServiceContainer(instance_config(probe=ProbeConfig(timeout=0.2, interval=0.05)))
        started = time.monotonic()

        message = re.escape(
            f"the instance under test (image {SAMPLE_IMAGE}) did not become ready: "
            "port 127.0.0.2:18080 did not accept connections within 0.2s"
        )

        with pytest.raises(EngineError, match=message) as excinfo:
            container.start({})

        assert isinstance(excinfo.value, EngineError)
        assert type(excinfo.value) is EngineError
        assert 0.2 <= time.monotonic() - started < 2.0

    def test_start_port_readiness_fails_past_the_deadline(self, monkeypatch: pytest.MonkeyPatch):
        """A port that never accepts connections fails at the declared deadline and interval."""
        from goga_tool_pybuggy.sandbox import service_container as module

        fake_time = FakeTime()
        monkeypatch.setattr(module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(module, "time", fake_time)
        monkeypatch.setattr(module, "_tcp_port_open", FakePortProbe([False] * 100))
        container = ServiceContainer(instance_config(probe=ProbeConfig(timeout=0.3, interval=0.25)))

        with pytest.raises(EngineError, match=r"port 127\.0\.0\.2:18080 did not accept connections within 0\.3s"):
            container.start({})

        assert fake_time.sleeps == [0.25, 0.25]

    def test_start_health_readiness_fails_past_the_deadline(self, monkeypatch: pytest.MonkeyPatch):
        """A health endpoint that never answers 2xx fails at the declared deadline."""
        from goga_tool_pybuggy.sandbox import service_container as module

        fake_time = FakeTime()
        monkeypatch.setattr(module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(module, "time", fake_time)
        monkeypatch.setattr(module, "requests", FakeRequests(statuses=[503] * 100))
        container = ServiceContainer(instance_config(probe=ProbeConfig(path="/healthz", timeout=0.25, interval=0.125)))

        with pytest.raises(EngineError, match=r"health endpoint http://127\.0\.0\.2:18080/healthz.*within 0\.25s"):
            container.start({})

        assert fake_time.sleeps == [0.125, 0.125]

    def test_start_health_probe_exception_is_one_failed_attempt(self, monkeypatch: pytest.MonkeyPatch):
        """A refused health probe is one failed attempt, not an error — the loop retries."""

        class RefusingRequests(FakeRequests):
            """Requests double refusing once, then answering 200."""

            def __init__(self) -> None:
                super().__init__(statuses=[200])
                self.calls = 0

            def get(self, url: str, timeout: int | None = None) -> FakeResponse:
                self.calls += 1

                if self.calls == 1:
                    raise requests.RequestException("connection refused")

                return super().get(url, timeout=timeout)

        fake_requests = RefusingRequests()
        config = instance_config(probe=ProbeConfig(path="/healthz"))
        _, wrapped = started_container(monkeypatch, fake_requests=fake_requests, config=config)

        assert wrapped is not None
        assert fake_requests.calls == 2

    def test_host_and_port_read_back_from_the_container_engine(self, monkeypatch: pytest.MonkeyPatch):
        """``host`` / ``port`` carry the mapped values, port as an ``int``."""
        container, wrapped = started_container(monkeypatch)

        assert wrapped is not None
        assert container.host == "127.0.0.2"
        assert container.port == 18080
        assert isinstance(container.port, int)

    def test_host_and_port_fail_before_start(self):
        """Reading the mapped address before start fails — there is nothing mapped yet."""
        container = ServiceContainer(instance_config())

        with pytest.raises(RuntimeError, match=r"before start"):
            assert container.host

        with pytest.raises(RuntimeError, match=r"before start"):
            assert container.port


class TestServiceContainerLiveness:
    """Liveness and diagnostics of the instance container, driven over the fakes."""

    def test_alive_reloads_and_reports_a_running_instance(self, monkeypatch: pytest.MonkeyPatch):
        """``alive`` reloads the SDK status and reports True while the instance runs."""
        container, wrapped = started_container(monkeypatch)

        assert wrapped is not None
        assert container.alive() is True
        assert wrapped.wrapped.reloads == 1

    def test_alive_reports_a_dead_instance(self, monkeypatch: pytest.MonkeyPatch):
        """A non-running SDK status reports False — the died instance is detectable."""
        container, wrapped = started_container(monkeypatch)

        assert wrapped is not None
        wrapped.wrapped.status = "exited"

        assert container.alive() is False

    def test_alive_is_false_before_start_and_after_stop(self, monkeypatch: pytest.MonkeyPatch):
        """Without a started container liveness is False — before start and after stop alike."""
        from goga_tool_pybuggy.sandbox import service_container as module

        assert ServiceContainer(instance_config()).alive() is False

        monkeypatch.setattr(module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(module, "time", FakeTime())
        monkeypatch.setattr(module, "_tcp_port_open", FakePortProbe([True]))
        container = ServiceContainer(instance_config())
        container.start({})

        container.stop()

        assert container.alive() is False

    def test_logs_return_the_container_output_as_str(self, monkeypatch: pytest.MonkeyPatch):
        """``logs`` decodes the container output — the died-instance diagnostic payload."""
        config = instance_config()
        from goga_tool_pybuggy.sandbox import service_container as module

        monkeypatch.setattr(module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(module, "time", FakeTime())
        monkeypatch.setattr(module, "_tcp_port_open", FakePortProbe([True]))
        container = ServiceContainer(config)
        container.start({})

        container._container.wrapped.output = b"OOMKilled after boot\n\xff\xfe"

        assert container.logs() == "OOMKilled after boot\n��"

    def test_logs_of_a_stopped_instance_are_empty(self, monkeypatch: pytest.MonkeyPatch):
        """A stopped instance has no readable output — ``logs`` answers an empty string."""
        container, wrapped = started_container(monkeypatch)

        assert wrapped is not None
        container.stop()

        assert container.logs() == ""


class TestServiceContainerStop:
    """Teardown of the instance container, driven over the fakes."""

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
        container = ServiceContainer(instance_config())

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
    """Live behavior of the instance container against a real container (docker-gated)."""

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
        """Variant A — default port readiness: mapped address, liveness, output, stop safety."""
        container = ServiceContainer(instance_config())

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
        container = ServiceContainer(instance_config(probe=ProbeConfig(path="/__admin/health")))

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
