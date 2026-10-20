"""Runtime probe and engine factory: ``check_runtime``, ``normalize_container_host``, ``build_engine``."""

import logging
import os
import socket
from pathlib import Path

import requests
from docker.errors import DockerException
from testcontainers.core.config import testcontainers_config
from testcontainers.core.docker_client import DockerClient

from ..config.service import ServiceConfig
from .base import BaseEngine, EngineError
from .http import HttpEngine
from .kafka import KafkaEngine
from .postgres import PostgresEngine
from .redis import RedisEngine
from .vault import VaultEngine

logger = logging.getLogger(__name__)

RUNTIME_REQUIREMENT = "a docker-compatible container runtime must be available in the environment running the tests"

KIND_ENGINES: dict[str, type[BaseEngine]] = {
    "postgresql": PostgresEngine,
    "kafka": KafkaEngine,
    "vault": VaultEngine,
    "http": HttpEngine,
    "redis": RedisEngine,
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
    both sides.

    The routine applies the value through ``setdefault`` semantics only: an explicit
    ``TESTCONTAINERS_HOST_OVERRIDE`` in the environment always wins, and a failed detection is
    a no-op (the mapped-localhost behavior of a plain host run). The value reaches testcontainers
    twice — the environment variable, and the module-level ``testcontainers_config`` singleton:
    testcontainers freezes ``tc_host_override`` at ITS import (which this package's own import
    chain triggers before ``install()`` runs) and ``DockerClient.host()`` reads the frozen
    singleton, never the environment — so the singleton is patched too whenever it is empty.

    Algorithm:
    1. ``TESTCONTAINERS_HOST_OVERRIDE`` already set — the explicit value is the effective one.
    2. Otherwise the ``/.dockerenv`` marker exists (the runner is itself a container) — default
    the override to ``host.docker.internal``.
    3. Otherwise (a host run) — resolve the host's routable IP through a routing-table-only
    UDP connect (no packet leaves the machine) and default the override to it.
    4. An effective value exists — apply it to the empty ``testcontainers_config.tc_host_override``;
    a non-empty entry (an explicit ``TC_HOST`` frozen at import) stays untouched.
    5. No effective value — log at debug and change nothing.
    """
    detected = _detect_override()

    if detected is not None:
        os.environ.setdefault(CONTAINER_HOST_OVERRIDE, detected)

    effective = os.environ.get(CONTAINER_HOST_OVERRIDE)

    if effective is None:
        logger.debug(
            "container host override not detected — keeping the mapped localhost",
            extra={"override": CONTAINER_HOST_OVERRIDE},
        )
        return

    if testcontainers_config.tc_host_override is None:
        testcontainers_config.tc_host_override = effective

    logger.debug(
        "container host override applied",
        extra={"value": effective, "source": "explicit" if detected is None else "detected"},
    )


def _detect_override() -> str | None:
    """Resolve the topology-based override candidate.

    Returns:
        ``host.docker.internal`` inside a container, the host's routable IP on a host run,
        ``None`` when the environment already carries an explicit override or detection fails.
    """
    if CONTAINER_HOST_OVERRIDE in os.environ:
        logger.debug("container host override explicit", extra={"value": os.environ[CONTAINER_HOST_OVERRIDE]})
        return None

    if _DOCKER_ENV_MARKER.exists():
        return "host.docker.internal"

    return _routable_host_ip() or None


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
        override, the topic declarations, the readiness declaration, the migrations
        declaration, and the redis password and db declarations reach the engine via
        ``config``.

    Raises:
        EngineError: The service kind has no engine; the message lists the supported kinds.
    """
    engine_class = KIND_ENGINES.get(config.kind)

    if engine_class is None:
        supported = ", ".join(KIND_ENGINES)

        raise EngineError(f"service '{config.name}': kind '{config.kind}' has no engine; supported kinds: {supported}")

    logger.debug("engine built", extra={"service": config.name, "kind": config.kind})

    return engine_class(config)
