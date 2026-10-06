"""ServiceContainer entity: the container of the service under test."""

import logging
import socket
import time

import requests
from testcontainers.core.container import DockerContainer

from .config.service import ServiceConfig

logger = logging.getLogger(__name__)

SANDBOX_LABELS = {"pybuggy-sandbox": "true"}
READINESS_TIMEOUT = 30.0
READINESS_INTERVAL = 0.5
PROBE_TIMEOUT = 1.0
HTTP_TIMEOUT = 5
HEALTHY_MIN_STATUS = 200
HEALTHY_MAX_STATUS = 299
RUNNING_STATUS = "running"


class ServiceContainer:
    """The service under test: container lifecycle, readiness, liveness and output.

    The container runs the declared image with the rendered env and the sandbox labels;
    readiness completes before ``start`` returns — a plain TCP port probe when the declaration
    carries no health path, the health endpoint otherwise. The container is removed on ``stop``
    and is never restarted: ``clear`` resets the dependency instances only, the service keeps
    running for the whole session.

    Attributes:
        config: The service-under-test declaration — image, env, port, health path.
    """

    def __init__(self, config: ServiceConfig) -> None:
        """Initialize the service container of one service declaration.

        Args:
            config: The service-under-test declaration — image, env, port, health path.
        """
        self.config = config
        self._container: DockerContainer | None = None

    @property
    def host(self) -> str:
        """The mapped host of the started service.

        Returns:
            The host the service is reachable on, read back from the container engine.

        Raises:
            RuntimeError: The service is not started — there is no mapped host to read.
        """
        if self._container is None:
            raise RuntimeError("service host requested before start")

        return self._container.get_container_host_ip()

    @property
    def port(self) -> int:
        """The mapped host-side port of the started service.

        Returns:
            The published host-side port the service is reachable on.

        Raises:
            RuntimeError: The service is not started — there is no mapped port to read.
        """
        if self._container is None:
            raise RuntimeError("service port requested before start")

        return int(self._container.get_exposed_port(self.config.port))

    def start(self, env: dict[str, str]) -> None:
        """Start the service container with the rendered env and bring it to readiness.

        The container runs the declared image with the sandbox labels, publishes the declared
        port and receives the rendered env values. Readiness is the declared mode — a TCP port
        probe loop when ``config.health`` is ``None``, the health endpoint until it answers 2xx
        otherwise — and completes before the call returns.

        Args:
            env: The rendered service environment, placeholder values resolved.

        Raises:
            RuntimeError: The service did not become ready within the deadline.
        """
        logger.info("service starting", extra={"image": self.config.image, "port": self.config.port})

        container = self._build_container(env)
        container.start()
        self._container = container

        for key in env:
            logger.debug("service env value applied", extra={"env_key": key})

        self._wait_ready()
        logger.info("service ready", extra={"image": self.config.image, "host": self.host, "port": self.port})

    def stop(self) -> None:
        """Remove the service container.

        Safe on an already-stopped service — a second stop touches nothing.

        Raises:
            RuntimeError: Never; a failed removal is logged instead of raising, so teardown of
                the remaining parts never gets blocked.
        """
        if self._container is None:
            return

        container = self._container
        self._container = None

        try:
            container.stop()
        except Exception:
            logger.error("service stop failed", extra={"image": self.config.image})

            return

        logger.info("service stopped", extra={"image": self.config.image})

    def alive(self) -> bool:
        """Report whether the service container is running.

        Reloads the container status through the docker SDK — a stopped, removed or died
        service answers False, so the died-service guard of the session runtime can act.

        Returns:
            True while the service container status is ``running``, False otherwise.
        """
        if self._container is None:
            return False

        wrapped = self._container.get_wrapped_container()

        try:
            wrapped.reload()
        except Exception:
            logger.debug("service status unavailable", extra={"image": self.config.image})

            return False

        return wrapped.status == RUNNING_STATUS

    def logs(self) -> str:
        """Read the service container output — the died-service diagnostic payload.

        Returns:
            The container output as text; an empty string when the container is gone — a
            removed container has no readable output.
        """
        if self._container is None:
            return ""

        wrapped = self._container.get_wrapped_container()

        try:
            output = wrapped.logs()
        except Exception:
            logger.debug("service logs unavailable", extra={"image": self.config.image})

            return ""

        return output.decode("utf-8", errors="replace")

    def _build_container(self, env: dict[str, str]) -> DockerContainer:
        """Build the service container — declared image, labels, port, rendered env.

        Args:
            env: The rendered service environment, placeholder values resolved.

        Returns:
            The built, not yet started, service container.
        """
        container = DockerContainer(self.config.image, labels=SANDBOX_LABELS)
        container.with_exposed_ports(self.config.port)

        for key, value in env.items():
            container.with_env(key, value)

        return container

    def _wait_ready(self) -> None:
        """Wait for service readiness in the declared mode.

        The port mode probes the mapped address with TCP connects; the health mode requests the
        health endpoint until it answers 2xx. Both loops run against a deadline.

        Raises:
            RuntimeError: The service did not become ready within the deadline.
        """
        host = self._container.get_container_host_ip()
        port = int(self._container.get_exposed_port(self.config.port))
        deadline = time.monotonic() + READINESS_TIMEOUT

        if self.config.health is None:
            self._wait_port_ready(host, port, deadline)

            return

        self._wait_health_ready(host, port, self.config.health, deadline)

    def _wait_port_ready(self, host: str, port: int, deadline: float) -> None:
        """Wait until the mapped service port accepts TCP connections.

        Args:
            host: The mapped host of the service.
            port: The mapped host-side port of the service.
            deadline: The monotonic instant the probe loop gives up at.

        Raises:
            RuntimeError: The port did not accept connections within the deadline.
        """
        while time.monotonic() < deadline:
            if _tcp_port_open(host, port):
                logger.debug("service port ready", extra={"host": host, "port": port})

                return

            time.sleep(READINESS_INTERVAL)

        raise RuntimeError(f"service port {host}:{port} did not accept connections within {READINESS_TIMEOUT:.0f}s")

    def _wait_health_ready(self, host: str, port: int, health: str, deadline: float) -> None:
        """Wait until the service health endpoint answers 2xx.

        Args:
            host: The mapped host of the service.
            port: The mapped host-side port of the service.
            health: The health path of the declaration.
            deadline: The monotonic instant the probe loop gives up at.

        Raises:
            RuntimeError: The health endpoint did not answer 2xx within the deadline.
        """
        url = f"http://{host}:{port}{health}"

        while time.monotonic() < deadline:
            try:
                response = requests.get(url, timeout=HTTP_TIMEOUT)

                if HEALTHY_MIN_STATUS <= response.status_code <= HEALTHY_MAX_STATUS:
                    logger.debug("service health ready", extra={"health": url})

                    return
            except requests.RequestException:
                logger.debug("service health probe retry", extra={"health": url})

            time.sleep(READINESS_INTERVAL)

        raise RuntimeError(f"service health endpoint {url} did not succeed within {READINESS_TIMEOUT:.0f}s")


def _tcp_port_open(host: str, port: int, timeout: float = PROBE_TIMEOUT) -> bool:
    """Probe whether a TCP port accepts connections.

    Args:
        host: The host the probe connects to.
        port: The port the probe connects to.
        timeout: The connect timeout of the single probe attempt.

    Returns:
        True when the connect succeeded — the port accepts connections.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False
