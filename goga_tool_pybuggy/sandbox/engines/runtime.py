"""Runtime probe and engine factory: ``check_runtime`` and ``build_engine``."""

import logging

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
        override, the topic declarations, and the readiness declaration reach the engine
        via ``config``.

    Raises:
        EngineError: The service kind has no engine; the message lists the supported kinds.
    """
    engine_class = KIND_ENGINES.get(config.kind)

    if engine_class is None:
        supported = ", ".join(KIND_ENGINES)

        raise EngineError(f"service '{config.name}': kind '{config.kind}' has no engine; supported kinds: {supported}")

    logger.debug("engine built", extra={"service": config.name, "kind": config.kind})

    return engine_class(config)
