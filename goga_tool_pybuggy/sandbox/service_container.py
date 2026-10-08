"""ServiceContainer entity: the container of the instance under test."""

import logging
import socket
import time

import requests
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network

from .config import InstanceConfig, ProbeConfig
from .engines import EngineError

logger = logging.getLogger(__name__)

SANDBOX_LABELS = {"pybuggy-sandbox": "true"}
PROBE_TIMEOUT = 1.0
HTTP_TIMEOUT = 5
HEALTHY_MIN_STATUS = 200
HEALTHY_MAX_STATUS = 299
RUNNING_STATUS = "running"


class ServiceContainer:
    """The instance under test: container lifecycle, readiness, liveness and output.

    The container runs the declared image with the rendered env and the sandbox labels;
    readiness completes before ``start`` returns — a plain TCP port probe when the readiness
    declaration carries no health path, the health endpoint otherwise — within the declared
    deadline at the declared interval. The container is removed on ``stop`` and is never
    restarted: ``clear`` resets the dependency services only, the instance keeps running for
    the whole session.

    Attributes:
        config: The instance-under-test declaration — image, env, port, readiness declaration.
    """

    def __init__(self, config: InstanceConfig) -> None:
        """Initialize the instance container of one instance-under-test declaration.

        Args:
            config: The instance-under-test declaration — image, env, port, readiness
                declaration.
        """
        self.config = config
        self._container: DockerContainer | None = None
        self._network: Network | None = None

    @property
    def host(self) -> str:
        """The mapped host of the started instance.

        Returns:
            The host the instance is reachable on, read back from the container engine.

        Raises:
            RuntimeError: The instance is not started — there is no mapped host to read.
        """
        if self._container is None:
            raise RuntimeError("instance host requested before start")

        return self._container.get_container_host_ip()

    @property
    def port(self) -> int:
        """The mapped host-side port of the started instance.

        Returns:
            The published host-side port the instance is reachable on.

        Raises:
            RuntimeError: The instance is not started — there is no mapped port to read.
        """
        if self._container is None:
            raise RuntimeError("instance port requested before start")

        return int(self._container.get_exposed_port(self.config.port))

    def start(self, env: dict[str, str], network: Network | None = None) -> None:
        """Start the instance container with the rendered env and bring it to readiness.

        The container runs the declared image with the sandbox labels, publishes the declared
        port and receives the rendered env values; with a network it joins it, side by side
        with the dependency services of the same sandbox. Readiness runs within the declared
        deadline at the declared interval — a TCP port probe loop when the readiness
        declaration carries no health path, the health endpoint until it answers 2xx
        otherwise — and completes before the call returns.

        Args:
            env: The rendered instance environment, placeholder values resolved.
            network: The sandbox network the container joins.

        Raises:
            EngineError: The instance did not become ready within the declared deadline — the
                message names the instance image, the waited check and the expired deadline.
        """
        self._network = network

        logger.info("instance starting", extra={"image": self.config.image, "port": self.config.port})

        container = self._build_container(env)
        self._container = container
        container.start()

        for key in env:
            logger.debug("instance env value applied", extra={"env_key": key})

        self._wait_ready()
        logger.info("instance ready", extra={"image": self.config.image, "host": self.host, "port": self.config.port})

    def stop(self) -> None:
        """Remove the instance container.

        Safe on an already-stopped instance — a second stop touches nothing.

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
            logger.error("instance stop failed", extra={"image": self.config.image})

            return

        logger.info("instance stopped", extra={"image": self.config.image})

    def alive(self) -> bool:
        """Report whether the instance container is running.

        Reloads the container status through the docker SDK — a stopped, removed or died
        instance answers False, so the died-instance guard of the session runtime can act.

        Returns:
            True while the instance container status is ``running``, False otherwise.
        """
        if self._container is None:
            return False

        wrapped = self._container.get_wrapped_container()

        try:
            wrapped.reload()
        except Exception:
            logger.debug("instance status unavailable", extra={"image": self.config.image})

            return False

        return wrapped.status == RUNNING_STATUS

    def logs(self) -> str:
        """Read the instance container output — the died-instance diagnostic payload.

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
            logger.debug("instance logs unavailable", extra={"image": self.config.image})

            return ""

        return output.decode("utf-8", errors="replace")

    def _build_container(self, env: dict[str, str]) -> DockerContainer:
        """Build the instance container — declared image, labels, port, rendered env.

        Args:
            env: The rendered instance environment, placeholder values resolved.

        Returns:
            The built, not yet started, instance container.
        """
        container = DockerContainer(self.config.image, labels=SANDBOX_LABELS)
        container.with_exposed_ports(self.config.port)

        for key, value in env.items():
            container.with_env(key, value)

        if self._network is not None:
            container.with_network(self._network)

        return container

    def _wait_ready(self) -> None:
        """Wait for instance readiness in the declared mode and bounds.

        The readiness declaration of the instance entry names the wait bounds and the optional
        health path; an absent declaration keeps the default wait — the port at the 30.0s
        deadline and 0.5s interval. The port mode probes the mapped address with TCP connects;
        the health mode requests the health endpoint until it answers 2xx.

        Raises:
            EngineError: The instance did not become ready within the declared deadline.
        """
        probe = self.config.probe or ProbeConfig()
        host = self._container.get_container_host_ip()
        port = int(self._container.get_exposed_port(self.config.port))

        if probe.path is None:
            self._wait_port_ready(host, port, probe.timeout, probe.interval)

            return

        self._wait_health_ready(host, port, probe.path, probe.timeout, probe.interval)

    def _wait_port_ready(self, host: str, port: int, timeout: float, interval: float) -> None:
        """Wait until the mapped instance port accepts TCP connections.

        Args:
            host: The mapped host of the instance.
            port: The mapped host-side port of the instance.
            timeout: The readiness deadline in seconds.
            interval: The seconds between readiness attempts.

        Raises:
            EngineError: The port did not accept connections within the deadline — the message
                names the instance image, the port check and the expired deadline.
        """
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            if _tcp_port_open(host, port):
                logger.debug("instance port ready", extra={"host": host, "port": port})

                return

            time.sleep(interval)

        raise EngineError(
            f"the instance under test (image {self.config.image}) did not become ready: "
            f"port {host}:{port} did not accept connections within {timeout:g}s"
        )

    def _wait_health_ready(self, host: str, port: int, path: str, timeout: float, interval: float) -> None:
        """Wait until the instance health endpoint answers 2xx.

        Args:
            host: The mapped host of the instance.
            port: The mapped host-side port of the instance.
            path: The health path of the readiness declaration.
            timeout: The readiness deadline in seconds.
            interval: The seconds between readiness attempts.

        Raises:
            EngineError: The health endpoint did not answer 2xx within the deadline — the
                message names the instance image, the health check and the expired deadline.
        """
        url = f"http://{host}:{port}{path}"
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            try:
                response = requests.get(url, timeout=HTTP_TIMEOUT)

                if HEALTHY_MIN_STATUS <= response.status_code <= HEALTHY_MAX_STATUS:
                    logger.debug("instance health ready", extra={"health": url})

                    return
            except requests.RequestException:
                logger.debug("instance health probe retry", extra={"health": url})

            time.sleep(interval)

        raise EngineError(
            f"the instance under test (image {self.config.image}) did not become ready: "
            f"health endpoint {url} did not succeed within {timeout:g}s"
        )


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
