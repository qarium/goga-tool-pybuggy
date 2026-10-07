"""KafkaEngine: the kafka kind engine — a mokapi spec-driven kafka mock instance."""

import io
import json
import logging
import pathlib
import time
from collections.abc import Sequence

import requests
from kafka import KafkaProducer
from kafka.serializer import Serializer
from ruamel.yaml import YAML
from testcontainers.core.container import DockerContainer
from testcontainers.core.docker_client import DockerClient
from testcontainers.core.network import Network

from ..config.instance import InstanceConfig
from .base import BaseEngine, EngineError, reserve_port
from .operation import DataOperation

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "mokapi/mokapi:0.52.0"
HTTP_PORT = 8080
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

    The container runs the product-pinned mokapi image unless the instance config overrides it.
    The AsyncAPI spec of the startup operations decides the mocked topology — and mokapi binds
    its kafka listener on, and advertises to clients, the very ``servers.*.host`` the spec
    carries. The engine therefore never mounts the author's document as-is: it reserves a free
    host port, rewrites every kafka server entry of a spec copy to the client-reachable
    ``{host}:{port}``, transfers the copy into the container, and publishes the reserved port on
    both sides. Bootstrap, advertised metadata and the ``{{instance.host}}``/``{{instance.port}}``
    placeholders then name one and the same address. The data plane is one kafka-python producer
    bootstrapped against that address. Reset restarts the same container — the binding and the
    transferred spec survive a restart, the in-memory messages empty, and the journal replay
    re-establishes the declared preconditions.

    Attributes:
        config: The instance declaration — name, kind, image override.
    """

    def __init__(self, config: InstanceConfig) -> None:
        """Initialize the kafka engine of one configured instance.

        Args:
            config: The instance declaration — name, kind, image override.
        """
        super().__init__(config)
        self._producer: KafkaProducer | None = None
        self._spec_paths: list[str] = []
        self._specs: list[tuple[str, bytes]] = []

    def start(self, startup: list[DataOperation], network: Network | None = None) -> None:
        """Start the mokapi container and bring it to readiness.

        The startup spec operations are consumed by the container build — each spec document is
        read, its kafka servers rewritten to the mapped address, and the patched copy handed to
        the container — before the base lifecycle runs. A kafka instance without a spec fails
        here: mokapi opens its kafka listener only for a spec's servers, so there would be
        nothing to produce into.

        Args:
            startup: The startup data of this instance, in declaration order.
            network: The sandbox network the container joins under its instance-name alias.

        Raises:
            EngineError: A lifecycle step or a startup operation failed, or the startup data
                carries no AsyncAPI spec.
        """
        self._spec_paths = [str(op.payload["path"]) for op in startup if op.action == "spec"]

        if not self._spec_paths:
            raise EngineError(
                f"instance '{self.config.name}': no AsyncAPI spec in the startup data — "
                f"declare one under data.kafka.{self.config.name}; without a spec mokapi "
                "serves no kafka listener"
            )

        super().start(startup, network)

    def _build_container(self) -> DockerContainer:
        """Build the mokapi container — pinned image, labels, patched specs, fixed data port.

        Reserves a free host port and rewrites the kafka servers of every spec to the
        client-reachable address, so the port mokapi binds in-container equals the published
        host port and the advertised address equals the bootstrap address. The patched copies
        travel into the container as tar archives through the docker API — not as bind mounts,
        whose host paths resolve on the daemon's filesystem and break when the engine itself
        runs inside a container.

        Returns:
            The built, not yet started, mokapi container.
        """
        host = DockerClient().host()
        port = reserve_port()
        self._container_port = port
        self._specs = _patch_specs(self.config.name, self._spec_paths, host, port)

        image = self.config.image or DEFAULT_IMAGE
        container = DockerContainer(image, labels=SANDBOX_LABELS)
        container.with_exposed_ports(HTTP_PORT)
        container.with_bind_ports(port, port)

        for target, content in self._specs:
            container.with_copy_into_container(content, target)
            logger.debug("kafka spec transferred", extra={"instance": self.config.name, "spec": target})

        if self._specs:
            container.with_command([target for target, _ in self._specs])

        self._attach_network(container)

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
            value_serializer=_ValueSerializer(),
            key_serializer=_KeySerializer(),
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

        The SDK restart preserves the port bindings and the container filesystem, so the fixed
        published address stays valid and the transferred spec stays in place; the in-memory
        messages empty and the topology is re-created from the spec on boot. Readiness is
        re-waited and the producer rebuilt.

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


class _ValueSerializer(Serializer):
    """The producer value serializer — the kafka-python ``Serializer`` interface.

    kafka-python 3 deprecates plain-callable serializers, warning on every producer
    construction; a project's ``filterwarnings = error`` would turn that warning into a
    data-plane bootstrap failure. Implementing the interface keeps the engine silent.
    """

    def serialize(
        self,
        topic: str,  # noqa: ARG002 -- the Serializer ABI carries topic; the encoding ignores it
        headers: Sequence[tuple[str, bytes]],  # noqa: ARG002 -- the ABI carries headers; ignored
        value: object,
    ) -> bytes:
        """Serialize one message value — JSON for mappings, UTF-8 for plain strings.

        Args:
            topic: The destination topic — unused; the encoding is topic-independent.
            headers: The message headers — unused; the encoding is header-independent.
            value: The message value — a JSON-serializable mapping or a plain string.

        Returns:
            The serialized bytes of the value.
        """
        return _serialize_value(value)


class _KeySerializer(Serializer):
    """The producer key serializer — the ``Serializer`` interface over ``_serialize_key``.

    See ``_ValueSerializer`` for why the interface is implemented at all.
    """

    def serialize(
        self,
        topic: str,  # noqa: ARG002 -- the Serializer ABI carries topic; the encoding ignores it
        headers: Sequence[tuple[str, bytes]],  # noqa: ARG002 -- the ABI carries headers; ignored
        key: str | None,
    ) -> bytes | None:
        """Serialize one message key — UTF-8; a keyless message stays keyless.

        Args:
            topic: The destination topic — unused; the encoding is topic-independent.
            headers: The message headers — unused; the encoding is header-independent.
            key: The optional partitioning key.

        Returns:
            The UTF-8 bytes of the key, or None for a keyless message.
        """
        return _serialize_key(key)


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


def _patch_specs(instance: str, paths: list[str], host: str, port: int) -> list[tuple[str, bytes]]:
    """Rewrite the kafka servers of every spec to the client-reachable mapped address.

    Each document is parsed round-trip (author comments survive), every kafka-protocol
    ``servers.*.host`` becomes ``{host}:{port}`` — the address mokapi will both bind its
    listener port from and advertise to kafka clients — and the patched copy is serialized
    back for the transfer into the container.

    Args:
        instance: The instance name — the owner of the specs, for error messages.
        paths: The spec document paths of the startup data, in declaration order.
        host: The client-reachable docker host of the mapped address.
        port: The reserved host port both sides publish.

    Returns:
        The in-container target path and patched content of every spec, in declaration order.

    Raises:
        EngineError: A spec is unreadable, unparsable, or defines no kafka server — the
            message names the instance and the offending document.
    """
    parser = YAML()
    patched: list[tuple[str, bytes]] = []

    for path in paths:
        try:
            document = pathlib.Path(path).read_text(encoding="utf-8")
            data = parser.load(document)
        except (OSError, ValueError) as exc:
            raise EngineError(f"instance '{instance}': cannot read spec '{path}': {exc}") from exc

        servers = (data or {}).get("servers") or {}
        rewritten = 0

        for server in servers.values():
            if str(server.get("protocol", "")).lower() == "kafka":
                server["host"] = f"{host}:{port}"
                rewritten += 1

        if rewritten == 0:
            raise EngineError(f"instance '{instance}': spec '{path}' defines no kafka server")

        stream = io.StringIO()
        parser.dump(data, stream)
        target = f"{SPEC_MOUNT_DIR}/{pathlib.Path(path).name}"
        patched.append((target, stream.getvalue().encode("utf-8")))

        logger.debug("kafka spec patched", extra={"instance": instance, "spec": path, "servers": rewritten})

    return patched
