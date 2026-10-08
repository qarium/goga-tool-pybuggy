"""KafkaEngine: the kafka kind engine — a mokapi kafka mock service with inline topics."""

import io
import json
import logging
from collections.abc import Sequence

import requests
from kafka import KafkaProducer
from kafka.serializer import Serializer
from ruamel.yaml import YAML
from testcontainers.core.container import DockerContainer
from testcontainers.core.docker_client import DockerClient
from testcontainers.core.network import Network

from ..config.service import ServiceConfig
from ..config.topic import TopicConfig
from .base import BaseEngine, EngineError, reserve_port
from .operation import DataOperation

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "mokapi/mokapi:0.52.0"
HTTP_PORT = 8080
SPEC_MOUNT_DIR = "/data"
DOCUMENT_NAME = "sandbox.asyncapi.yaml"
ASYNCAPI_VERSION = "3.0.0"
DOCUMENT_VERSION = "1.0.0"
SANDBOX_LABELS = {"pybuggy-sandbox": "true"}

PROBE_TIMEOUT = 5
HEALTHY_STATUS = 200
DELIVERY_TIMEOUT = 10
FLUSH_TIMEOUT = 30
RESTART_TIMEOUT = 10
PRODUCER_RETRIES = 3


class KafkaEngine(BaseEngine):
    """kafka kind engine: mokapi container, producer plane, restart-based wipe.

    The container runs the product-pinned mokapi image unless the service entry overrides it.
    The inline topic declarations of the service entry decide the mocked topology — the engine
    generates the AsyncAPI document in memory from them, its kafka server carries the
    client-reachable mapped address of a reserved fixed port, the document travels into the
    container through the docker API, and its in-container path is the start argument. mokapi
    binds its kafka listener on, and advertises to clients, the very ``servers.*.host`` the
    document carries, so bootstrap, advertised metadata and the
    ``{{<name>.host}}``/``{{<name>.port}}`` instance env placeholders name one and the same
    address. The data plane is one kafka-python producer bootstrapped against that address.
    Reset restarts the same container — the binding and the transferred document survive a
    restart, the in-memory messages empty, and the journal replay re-establishes the declared
    preconditions.

    Attributes:
        config: The service declaration — name, kind, image override, topics, probe.
    """

    def __init__(self, config: ServiceConfig) -> None:
        """Initialize the kafka engine of one configured dependency service.

        Args:
            config: The service declaration — name, kind, image override, topics, probe.
        """
        super().__init__(config)
        self._producer: KafkaProducer | None = None

    def start(self, startup: list[DataOperation], network: Network | None = None) -> None:
        """Start the mokapi container and bring it to readiness.

        The declared topics are consumed by the container build — the AsyncAPI document is
        generated in memory from them and transferred into the container — before the base
        lifecycle runs. A kafka service without topics fails here, before any docker call:
        mokapi opens its kafka listener only for a document's servers, so there would be
        nothing to produce into. Document validation rejects the empty declaration first;
        this check is defense in depth.

        Args:
            startup: The startup data of this service, in declaration order.
            network: The sandbox network the container joins under its service-name alias.

        Raises:
            EngineError: A lifecycle step or a startup operation failed, or the service entry
                declares no topics.
        """
        if not self.config.topics:
            raise EngineError(
                f"service '{self.config.name}': no topics declared on the kafka service entry — "
                "declare topics inline in the sandbox document; without topics the mock opens "
                "no kafka listener"
            )

        super().start(startup, network)

    def _build_container(self) -> DockerContainer:
        """Build the mokapi container — pinned image, labels, generated document, fixed data port.

        Reserves a free host port and generates the AsyncAPI document in memory from the
        declared topics, its kafka server carrying the client-reachable mapped address, so the
        port mokapi binds in-container equals the published host port and the advertised
        address equals the bootstrap address. The document travels into the container through
        the docker API — not as a bind mount, whose host paths resolve on the daemon's
        filesystem and break when the engine itself runs inside a container — and its
        in-container path is passed as the start argument.

        Returns:
            The built, not yet started, mokapi container.
        """
        host = DockerClient().host()
        port = reserve_port()
        self._container_port = port
        target = f"{SPEC_MOUNT_DIR}/{DOCUMENT_NAME}"
        document = _generate_document(self.config.name, self.config.topics, host, port)

        image = self.config.image or DEFAULT_IMAGE
        container = DockerContainer(image, labels=SANDBOX_LABELS)
        container.with_exposed_ports(HTTP_PORT)
        container.with_bind_ports(port, port)
        container.with_copy_into_container(document, target)
        container.with_command([target])
        logger.debug("kafka document transferred", extra={"service": self.config.name, "document": target})

        self._attach_network(container)

        return container

    def _wait_ready(self) -> None:
        """Wait for the mokapi HTTP health endpoint, bounded by the declared deadline.

        A probe loop at the declared bounds — the endpoint answers 200 once the kafka listener
        serves the generated topology.

        Raises:
            RuntimeError: The declared deadline expired; the lifecycle wrappers convert it
                into ``EngineError`` naming the service, the waited check and the deadline.
        """
        host = self._container.get_container_host_ip()
        port = int(self._container.get_exposed_port(HTTP_PORT))
        url = f"http://{host}:{port}/health"
        timeout, interval = self._readiness_bounds

        def attempt() -> bool:
            try:
                response = requests.get(url, timeout=PROBE_TIMEOUT)
            except requests.RequestException:
                logger.debug("kafka health probe retry", extra={"service": self.config.name, "health": url})

                return False

            return response.status_code == HEALTHY_STATUS

        self._probe_until(timeout, interval, attempt, f"health endpoint {url} did not succeed")
        logger.debug("kafka health ready", extra={"service": self.config.name, "health": url})

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
        logger.debug("kafka plane open", extra={"service": self.config.name, "bootstrap": bootstrap})

    def _execute(self, operation: DataOperation) -> None:
        """Execute one kafka operation through the producer.

        A ``produce`` operation validates the topic against the declarations first — a topic
        not declared on the kafka service entry fails with a readable error naming the service
        and its declared topics — then sends the message and awaits its delivery future within
        the per-message deadline.

        Args:
            operation: The ``produce`` operation to execute.

        Raises:
            EngineError: The topic is not declared on the kafka service entry.
        """
        topic = operation.payload["topic"]
        declared = {declared_topic.name for declared_topic in self.config.topics}

        if topic not in declared:
            raise EngineError(
                f"service '{self.config.name}': topic '{topic}' is not declared on the kafka "
                f"service entry (declared topics: {', '.join(sorted(declared))})"
            )

        future = self._producer.send(
            topic,
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
        published address stays valid and the transferred document stays in place; the
        in-memory messages empty and the topology is re-created from the generated document on
        boot. Readiness is re-waited through the bounded health loop and the producer rebuilt.

        Raises:
            RuntimeError: The restart or the post-restart health wait failed.
        """
        wrapped = self._container.get_wrapped_container()
        wrapped.restart(timeout=RESTART_TIMEOUT)
        logger.debug("kafka container restarted", extra={"service": self.config.name})

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
            logger.warning("stale producer close failed after restart", extra={"service": self.config.name})

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


def _generate_document(service: str, topics: list[TopicConfig], host: str, port: int) -> bytes:
    """Generate the in-memory AsyncAPI document of the declared kafka topology.

    The document is AsyncAPI 3.0 — the channel ``address`` carries the topic name, the grammar
    the pinned mokapi parses (verified live: the 2.6 channel-key form binds the default port
    and declares no topics) — with one server ``kafka`` carrying the client-reachable mapped
    address and one channel per declared topic whose kafka channel binding carries the
    partition count. No message payloads are declared: mokapi validates produced messages
    against declared schemas, and the sandbox produces arbitrary test values. The document
    stays internal — it is serialized to UTF-8 bytes in memory and never written to disk
    anywhere.

    Args:
        service: The service name — the document title.
        topics: The declared topics of the kafka service entry.
        host: The client-reachable docker host of the mapped address.
        port: The reserved host port both sides publish.

    Returns:
        The UTF-8 YAML bytes of the generated document.
    """
    channels: dict[str, dict[str, object]] = {}

    for topic in topics:
        channels[topic.name] = {
            "address": topic.name,
            "bindings": {"kafka": {"partitions": topic.partitions}},
        }

    document = {
        "asyncapi": ASYNCAPI_VERSION,
        "info": {"title": service, "version": DOCUMENT_VERSION},
        "servers": {"kafka": {"protocol": "kafka", "host": f"{host}:{port}"}},
        "channels": channels,
    }
    stream = io.StringIO()
    YAML().dump(document, stream)
    logger.debug("kafka document generated", extra={"service": service, "topics": len(topics)})

    return stream.getvalue().encode("utf-8")
