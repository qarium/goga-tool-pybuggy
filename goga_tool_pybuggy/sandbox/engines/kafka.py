"""KafkaEngine: the kafka kind engine — a mokapi spec-driven kafka mock instance."""

import json
import logging
import pathlib
import time

import requests
from kafka import KafkaProducer
from testcontainers.core.container import DockerContainer

from ..config.instance import InstanceConfig
from .base import BaseEngine
from .operation import DataOperation

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "mokapi/mokapi:0.28.0"
HTTP_PORT = 8080
KAFKA_PORT = 9092
SPEC_MOUNT_DIR = "/data"
SANDBOX_LABELS = {"pybuggy-sandbox": "true"}

READINESS_TIMEOUT = 30.0
READINESS_INTERVAL = 0.5
PROBE_TIMEOUT = 5
HEALTHY_STATUS = 200
DELIVERY_TIMEOUT = 10
FLUSH_TIMEOUT = 30
RESTART_TIMEOUT = 10
PRODUCER_RETRIES = 3


class KafkaEngine(BaseEngine):
    """kafka kind engine: mokapi container, producer plane, restart-based wipe.

    The container runs the product-pinned mokapi image unless the instance config overrides it;
    the AsyncAPI spec of the startup operations is volume-mounted read-only and passed as the
    command argument, so the mocked topology is re-created from the spec on every boot. The data
    plane is one kafka-python producer bootstrapped against the mapped kafka listener. Reset
    restarts the same container — the published address survives, the in-memory messages empty,
    and the journal replay re-establishes the declared preconditions.

    Attributes:
        config: The instance declaration — name, kind, image override.
    """

    _container_port = KAFKA_PORT

    def __init__(self, config: InstanceConfig) -> None:
        """Initialize the kafka engine of one configured instance.

        Args:
            config: The instance declaration — name, kind, image override.
        """
        super().__init__(config)
        self._producer: KafkaProducer | None = None
        self._spec_paths: list[str] = []

    def start(self, startup: list[DataOperation]) -> None:
        """Start the mokapi container and bring it to readiness.

        The startup spec operations are consumed by the container build — the spec documents are
        mounted and passed as the command arguments — before the base lifecycle runs.

        Args:
            startup: The startup data of this instance, in declaration order.

        Raises:
            EngineError: A lifecycle step or a startup operation failed.
        """
        self._spec_paths = [str(op.payload["path"]) for op in startup if op.action == "spec"]
        super().start(startup)

    def _build_container(self) -> DockerContainer:
        """Build the mokapi container — pinned image, labels, both ports, mounted specs.

        Returns:
            The built, not yet started, mokapi container.
        """
        image = self.config.image or DEFAULT_IMAGE
        container = DockerContainer(image, labels=SANDBOX_LABELS)
        container.with_exposed_ports(HTTP_PORT, KAFKA_PORT)

        mounted = []

        for spec_path in self._spec_paths:
            target = f"{SPEC_MOUNT_DIR}/{pathlib.Path(spec_path).name}"
            container.with_volume_mapping(spec_path, target, mode="ro")
            mounted.append(target)
            logger.debug("kafka spec mounted", extra={"instance": self.config.name, "spec": spec_path})

        if mounted:
            container.with_command(mounted)

        return container

    def _wait_ready(self) -> None:
        """Wait for the mokapi HTTP health endpoint.

        A probe loop with a deadline — the endpoint answers 200 once the kafka listener serves
        the spec-defined topology.

        Raises:
            RuntimeError: The health endpoint did not succeed within the deadline.
        """
        host = self._container.get_container_host_ip()
        port = int(self._container.get_exposed_port(HTTP_PORT))
        url = f"http://{host}:{port}/health"
        deadline = time.monotonic() + READINESS_TIMEOUT

        while time.monotonic() < deadline:
            try:
                response = requests.get(url, timeout=PROBE_TIMEOUT)

                if response.status_code == HEALTHY_STATUS:
                    logger.debug("kafka health ready", extra={"instance": self.config.name, "health": url})

                    return
            except requests.RequestException:
                logger.debug("kafka health probe retry", extra={"instance": self.config.name, "health": url})

            time.sleep(READINESS_INTERVAL)

        raise RuntimeError(f"health endpoint {url} did not succeed within {READINESS_TIMEOUT:.0f}s")

    def _open_plane(self) -> None:
        """Open the producer against the mapped kafka listener.

        Raises:
            EngineError: The producer bootstrap failed — wrapped by the start lifecycle step.
        """
        address = self.address

        self._producer = KafkaProducer(
            bootstrap_servers=f"{address.host}:{address.port}",
            acks="all",
            retries=PRODUCER_RETRIES,
            value_serializer=_serialize_value,
            key_serializer=_serialize_key,
        )
        bootstrap = f"{address.host}:{address.port}"
        logger.debug("kafka plane open", extra={"instance": self.config.name, "bootstrap": bootstrap})

    def _execute(self, operation: DataOperation) -> None:
        """Execute one kafka operation through the producer.

        A ``spec`` operation is a replay-safe no-op — the spec was consumed at container build.
        A ``produce`` operation sends the message and awaits its delivery future within the
        per-message deadline.

        Args:
            operation: The ``spec`` or ``produce`` operation to execute.
        """
        if operation.action == "spec":
            return

        future = self._producer.send(
            operation.payload["topic"],
            key=operation.payload.get("key"),
            value=operation.payload["value"],
        )
        future.get(timeout=DELIVERY_TIMEOUT)

    def _apply_operations(self, operations: list[DataOperation]) -> None:
        """Execute the operation group through the base path, then flush once.

        The flush is the batch boundary — when it returns, every buffered message of the group
        is acknowledged.

        Args:
            operations: Operations to execute, in application order.
        """
        super()._apply_operations(operations)

        if operations:
            self._producer.flush(timeout=FLUSH_TIMEOUT)

    def _wipe(self) -> None:
        """Restart the same container — empty state, unchanged address.

        The SDK restart preserves the port bindings, so the mapped address stays valid; the
        in-memory messages empty and the topology is re-created from the mounted spec on boot.
        Readiness is re-waited and the producer rebuilt.

        Raises:
            RuntimeError: The restart or the post-restart health wait failed.
        """
        wrapped = self._container.get_wrapped_container()
        wrapped.restart(timeout=RESTART_TIMEOUT)
        logger.debug("kafka container restarted", extra={"instance": self.config.name})

        self._wait_ready()
        self._discard_producer()
        self._open_plane()

    def _close_plane(self) -> None:
        """Close the producer with a bounded timeout; safe when nothing is open."""
        if self._producer is None:
            return

        try:
            self._producer.close(timeout=FLUSH_TIMEOUT)
        finally:
            self._producer = None

    def _discard_producer(self) -> None:
        """Drop the stale producer of the restarted broker — best-effort close.

        The old broker is gone after the restart, so a failed close is a recoverable
        abnormality, not a reset failure.
        """
        if self._producer is None:
            return

        try:
            self._producer.close(timeout=FLUSH_TIMEOUT)
        except Exception:
            logger.warning("stale producer close failed after restart", extra={"instance": self.config.name})

        self._producer = None


def _serialize_value(value: object) -> bytes:
    """Serialize one message value — JSON for mappings, UTF-8 for plain strings.

    Args:
        value: The message value — a JSON-serializable mapping or a plain string.

    Returns:
        The serialized bytes of the value.
    """
    if isinstance(value, str):
        return value.encode("utf-8")

    return json.dumps(value).encode("utf-8")


def _serialize_key(key: str | None) -> bytes | None:
    """Serialize one message key — UTF-8; a keyless message stays keyless.

    Args:
        key: The optional partitioning key.

    Returns:
        The UTF-8 bytes of the key, or None for a keyless message.
    """
    if key is None:
        return None

    return key.encode("utf-8")
