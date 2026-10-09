"""Runtime probe and engine factory: ``check_runtime``, ``normalize_container_host``, ``build_engine``."""

import logging
import os
import socket
from pathlib import Path

import requests
from docker.errors import DockerException
from testcontainers.core.docker_client import DockerClient

from ..config.service import ServiceConfig
from .base import BaseEngine, EngineError
from .http import HttpEngine
from .kafka import KafkaEngine
from .postgres import PostgresEngine
from .vault import VaultEngine

logger = logging.getLogger(__name__)

RUNTIME_REQUIREMENT = "a docker-compatible container runtime must be available in the environment running the tests"

KIND_ENGINES: dict[str, type[BaseEngine]] = {
    "postgresql": PostgresEngine,
    "kafka": KafkaEngine,
    "vault": VaultEngine,
    "http": HttpEngine,
}

# The testcontainers env knob rewriting the host every container address resolves through —
# the seam that gives the sandbox one address space shared by the runner and the containers.
CONTAINER_HOST_OVERRIDE: str = "TESTCONTAINERS_HOST_OVERRIDE"

# The Docker-in-Docker / sibling marker: present inside a container, absent on a host.
_DOCKER_ENV_MARKER = Path("/.dockerenv")


def normalize_container_host() -> None:
    """Default the container-host override to the one address every consumer can reach.

    The sandbox's addresses must resolve for the runner AND for the instance container — the
    kafka mock advertises a single address to both. Inside a container that address is
    ``host.docker.internal`` (the Docker Desktop name); on a host run the mapped ``localhost``
    is unreachable from sibling containers, but the host's own routable IP is reachable from
    both sides. The routine sets the override through ``setdefault`` only: an explicit value
    in the environment always wins, and a failed detection is a no-op (the mapped-localhost
    behavior of a plain host run).

    Algorithm:
    1. ``TESTCONTAINERS_HOST_OVERRIDE`` already set — return; the explicit value wins.
    2. The ``/.dockerenv`` marker exists (the runner is itself a container) — default the
    override to ``host.docker.internal``.
    3. Otherwise (a host run) — resolve the host's routable IP through a routing-table-only
    UDP connect (no packet leaves the machine) and default the override to it.
    4. Any detection failure — log at debug and change nothing.
    """
    if CONTAINER_HOST_OVERRIDE in os.environ:
        logger.debug("container host override explicit", extra={"value": os.environ[CONTAINER_HOST_OVERRIDE]})
        return

    if _DOCKER_ENV_MARKER.exists():
        os.environ.setdefault(CONTAINER_HOST_OVERRIDE, "host.docker.internal")
        logger.debug("container host override defaulted", extra={"value": "host.docker.internal"})

        return

    host_ip = _routable_host_ip()

    if host_ip:
        os.environ.setdefault(CONTAINER_HOST_OVERRIDE, host_ip)
        logger.debug("container host override defaulted", extra={"value": host_ip})
    else:
        logger.debug("container host override not detected — keeping the mapped localhost")


def _routable_host_ip() -> str:
    """The host's own routable IPv4 address, or an empty string when it cannot be determined.

    The UDP connect performs no I/O — the kernel answers ``getsockname`` from the routing
    table, so the address of the default-route interface (the LAN/WLAN IP) comes back without
    a network round trip.

    Returns:
        The routable IPv4 address of the host, or ``""`` when no route answers.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.settimeout(0.0)
            probe.connect(("8.8.8.8", 80))

            return probe.getsockname()[0]
    except OSError:
        return ""


def check_runtime() -> None:
    """Probe the container-runtime availability before anything starts.

    Pings the daemon through the testcontainers docker client — the same client every engine
    drives. The probe itself starts nothing; an unreachable daemon fails immediately with an
    actionable error naming the requirement, so a session never hangs on a silent connection
    timeout.

    Raises:
        RuntimeError: No docker-compatible container runtime answers the probe — the message
            names the requirement and the underlying cause.
    """
    try:
        DockerClient().client.ping()
    except (DockerException, requests.RequestException) as exc:
        raise RuntimeError(f"{RUNTIME_REQUIREMENT} (probe failed: {exc})") from exc

    logger.info("container runtime available")


def build_engine(config: ServiceConfig) -> BaseEngine:
    """Build the engine of the configured service kind.

    Args:
        config: The service declaration — name, kind, image override, topics, probe.

    Returns:
        The engine of the service's kind, constructed with the declaration — the image
        override, the topic declarations, the readiness declaration, and the migrations
        declaration reach the engine via ``config``.

    Raises:
        EngineError: The service kind has no engine; the message lists the supported kinds.
    """
    engine_class = KIND_ENGINES.get(config.kind)

    if engine_class is None:
        supported = ", ".join(KIND_ENGINES)

        raise EngineError(f"service '{config.name}': kind '{config.kind}' has no engine; supported kinds: {supported}")

    logger.debug("engine built", extra={"service": config.name, "kind": config.kind})

    return engine_class(config)
