"""Contract and logic tests for the ``KafkaEngine`` entity."""

import inspect
import json
from typing import ClassVar

import pytest
import requests
from goga_tool_pybuggy.sandbox.config import ProbeConfig, ServiceConfig, TopicConfig
from goga_tool_pybuggy.sandbox.engines import BaseEngine, DataOperation, EngineError, KafkaEngine
from goga_tool_pybuggy.sandbox.engines import base as base_module
from goga_tool_pybuggy.sandbox.engines import kafka as kafka_module
from goga_tool_pybuggy.sandbox.engines.kafka import _generate_document, _serialize_value
from kafka import KafkaConsumer
from kafka.serializer import Serializer
from ruamel.yaml import YAML

from ..conftest import requires_docker


def sample_topics() -> list[TopicConfig]:
    """The sample topic declarations of the ``events`` kafka service entry.

    Returns:
        Two declarations — one carrying the partition default, one overriding it.
    """
    return [
        TopicConfig(name="orders.events"),
        TopicConfig(name="payments.events", partitions=6),
    ]


def events_engine(
    image: str | None = None,
    probe: ProbeConfig | None = None,
    topics: list[TopicConfig] | None = None,
) -> KafkaEngine:
    """Build a kafka engine of the sample ``events`` service.

    Args:
        image: The optional image override of the service declaration.
        probe: The optional readiness declaration of the service entry.
        topics: The topic declarations of the service entry; the sample set when omitted.

    Returns:
        The engine of a service named ``events`` of kind ``kafka``.
    """
    return KafkaEngine(
        ServiceConfig(
            name="events",
            kind="kafka",
            image=image,
            topics=topics if topics is not None else sample_topics(),
            probe=probe,
        )
    )


def produce_op(topic: str, value: object, key: str | None = None) -> DataOperation:
    """Build one kafka produce operation.

    Args:
        topic: The target topic of the declared topology.
        value: The message value — a JSON mapping or a plain string.
        key: The optional partitioning key.

    Returns:
        A sample ``produce`` operation targeted at the ``events`` service.
    """
    return DataOperation(
        instance="events",
        kind="kafka",
        action="produce",
        payload={"topic": topic, "value": value, "key": key},
    )


class FakeResponse:
    """Response double of the health probe."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeRequests:
    """Namespace double of ``requests`` recording probes and serving scripted responses."""

    RequestException = requests.RequestException

    def __init__(self, statuses: list[int] | None = None) -> None:
        self.statuses = list(statuses or [])
        self.probes: list[tuple[str, int]] = []

    def get(self, url: str, timeout: int) -> FakeResponse:
        self.probes.append((url, timeout))
        status = self.statuses.pop(0) if self.statuses else 200

        return FakeResponse(status)


class FakeClock:
    """Clock double of the probe loop — instant monotonic, sleeps advance the clock."""

    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def install_fake_clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    """Patch the probe-loop clock of the engines base — no wall-clock waiting in unit tests.

    Args:
        monkeypatch: The pytest monkeypatch fixture swapping the base seams.

    Returns:
        The installed clock double recording the interval sleeps.
    """
    clock = FakeClock()
    monkeypatch.setattr(base_module, "monotonic", clock.monotonic)
    monkeypatch.setattr(base_module, "sleep", clock.sleep)

    return clock


class FakeFuture:
    """Future double of one buffered send."""

    def __init__(self, producer: "FakeProducer", topic: str, key: str | None, value: object) -> None:
        self._producer = producer
        self.topic = topic
        self.key = key
        self.value = value

    def get(self, timeout: int | None = None) -> None:
        self._producer.delivered.append((self.topic, self.key, self.value, timeout))


class FakeProducer:
    """Producer double of the kafka data plane recording the send/flush/close calls."""

    built: ClassVar[list["FakeProducer"]] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs
        self.sent: list[tuple[str, str | None, object]] = []
        self.delivered: list[tuple[str, str | None, object, int | None]] = []
        self.flushes: list[int | None] = []
        self.close_timeouts: list[int | None] = []
        FakeProducer.built.append(self)

    def send(self, topic: str, key: str | None = None, value: object = None) -> FakeFuture:
        self.sent.append((topic, key, value))

        return FakeFuture(self, topic, key, value)

    def flush(self, timeout: int | None = None) -> None:
        self.flushes.append(timeout)

    def close(self, timeout: int | None = None) -> None:
        self.close_timeouts.append(timeout)


class FakeWrappedContainer:
    """Double of the docker SDK container object recording restarts."""

    def __init__(self) -> None:
        self.restarts: list[int | None] = []

    def restart(self, timeout: int = 10) -> None:
        self.restarts.append(timeout)


class FakeDockerClient:
    """Double of the testcontainers docker client answering the fixed mapped host."""

    def host(self) -> str:
        return "127.0.0.2"


class FakeDockerContainer:
    """Container double recording the build configuration and the mapped address."""

    def __init__(self, image: str, **kwargs: object) -> None:
        self.image = image
        self.kwargs = kwargs
        self.exposed_ports: list[int] = []
        self.bind_ports: list[tuple[int, int]] = []
        self.transfers: list[tuple[bytes, str]] = []
        self.command: str | list[str] | None = None
        self.network: object | None = None
        self.network_aliases: list[str] = []
        self.wrapped = FakeWrappedContainer()
        self.stops = 0
        self.starts = 0

    def with_network(self, network: object) -> "FakeDockerContainer":
        self.network = network

        return self

    def with_network_aliases(self, *aliases: str) -> "FakeDockerContainer":
        self.network_aliases.extend(aliases)

        return self

    def start(self) -> "FakeDockerContainer":
        self.starts += 1

        return self

    def with_exposed_ports(self, *ports: int) -> "FakeDockerContainer":
        self.exposed_ports.extend(ports)

        return self

    def with_bind_ports(self, container: int, host: int | None = None) -> "FakeDockerContainer":
        self.bind_ports.append((container, host))

        return self

    def with_copy_into_container(self, transferable: bytes, destination: str) -> "FakeDockerContainer":
        self.transfers.append((transferable, destination))

        return self

    def with_command(self, command: str | list[str]) -> "FakeDockerContainer":
        self.command = command

        return self

    def get_container_host_ip(self) -> str:
        return "127.0.0.2"

    def get_exposed_port(self, port: int) -> str:
        return {8080: "18080"}.get(port, str(port))

    def get_wrapped_container(self) -> FakeWrappedContainer:
        return self.wrapped

    def stop(self) -> None:
        self.stops += 1


def fake_build(monkeypatch: pytest.MonkeyPatch) -> None:
    """Determinize the container build: fixed mapped host, fixed reserved port, fake container.

    Args:
        monkeypatch: The test patcher the build doubles land in.
    """
    monkeypatch.setattr(kafka_module, "DockerContainer", FakeDockerContainer)
    monkeypatch.setattr(kafka_module, "DockerClient", FakeDockerClient)
    monkeypatch.setattr(kafka_module, "reserve_port", lambda: 19092)


def armed_engine(monkeypatch: pytest.MonkeyPatch, fake_requests: FakeRequests) -> KafkaEngine:
    """Build a kafka engine whose container, requests and producer seams are faked.

    Args:
        monkeypatch: The pytest monkeypatch fixture swapping the module seams.
        fake_requests: The recording requests double serving the health probes.

    Returns:
        A kafka engine driven entirely over the fakes — no daemon, no network.
    """
    fake_build(monkeypatch)
    monkeypatch.setattr(kafka_module, "requests", fake_requests)
    monkeypatch.setattr(kafka_module, "KafkaProducer", FakeProducer)
    install_fake_clock(monkeypatch)

    return events_engine()


def parse_document(content: bytes) -> dict[str, object]:
    """Parse the serialized AsyncAPI document back into a mapping.

    Args:
        content: The UTF-8 YAML bytes of a generated document.

    Returns:
        The parsed document mapping.
    """
    return YAML().load(content.decode("utf-8"))


class TestKafkaEngineContract:
    """Declared API of the ``KafkaEngine`` entity."""

    def test_kafka_engine_is_importable_from_engines_facade(self):
        """``KafkaEngine`` is re-exported by the ``goga_tool_pybuggy.sandbox.engines`` facade."""
        assert KafkaEngine is not None

    def test_kafka_engine_subclasses_base_engine(self):
        """The kind engine inherits the base contract."""
        assert issubclass(KafkaEngine, BaseEngine)

    def test_kafka_engine_declares_the_contract_constructor(self):
        """The constructor signature is ``__init__(self, config)`` over ``ServiceConfig``."""
        signature = inspect.signature(KafkaEngine.__init__)

        assert list(signature.parameters) == ["self", "config"]
        assert signature.parameters["config"].annotation is ServiceConfig

    def test_kafka_engine_constructs_over_a_topics_carrying_service_config(self):
        """The engine carries the service declaration — name, kind, image override, topics."""
        topics = sample_topics()
        engine = KafkaEngine(ServiceConfig(name="events", kind="kafka", topics=topics))

        assert engine.config.name == "events"
        assert engine.config.kind == "kafka"
        assert engine.config.topics == topics

    def test_kafka_engine_inherits_the_contract_methods(self):
        """``start`` / ``apply`` / ``record`` / ``reset`` / ``stop`` resolve with declared parameters."""
        expected = {
            "start": ["self", "startup", "network"],
            "apply": ["self", "operations"],
            "record": ["self", "operations"],
            "reset": ["self"],
            "stop": ["self"],
        }

        for method, parameters in expected.items():
            assert list(inspect.signature(getattr(KafkaEngine, method)).parameters) == parameters

    def test_kafka_engine_inherits_the_address_property(self):
        """The ``address`` property of the base resolves on the kind engine."""
        address = inspect.getattr_static(KafkaEngine, "address")

        assert isinstance(address, property)

    def test_kafka_engine_declares_the_engine_owned_readiness_wait(self):
        """The kind engine overrides ``_wait_ready`` — readiness probing is engine-owned."""
        assert KafkaEngine._wait_ready is not BaseEngine._wait_ready


class TestKafkaEngineBuild:
    """Container build arguments of the kafka engine, driven through the patched constructor."""

    def test_build_uses_the_pinned_image_labels_and_the_fixed_data_port(self, monkeypatch: pytest.MonkeyPatch):
        """Without an image override the build uses the pinned mokapi image, labels, fixed port."""
        fake_build(monkeypatch)
        engine = events_engine()

        container = engine._build_container()

        assert container.image == "mokapi/mokapi:0.52.0"
        assert container.kwargs["labels"] == {"pybuggy-sandbox": "true"}
        assert container.exposed_ports == [8080]
        assert container.bind_ports == [(19092, 19092)]

    def test_build_honors_the_image_override(self, monkeypatch: pytest.MonkeyPatch):
        """The image override of the service declaration reaches the container build."""
        fake_build(monkeypatch)
        engine = events_engine(image="mokapi/mokapi:0.53.0")

        container = engine._build_container()

        assert container.image == "mokapi/mokapi:0.53.0"

    def test_build_generates_the_document_and_transfers_it_as_command(self, monkeypatch: pytest.MonkeyPatch):
        """The generated document carries the mapped address and rides the docker API, not a mount."""
        fake_build(monkeypatch)
        engine = events_engine()

        container = engine._build_container()

        assert [target for _, target in container.transfers] == ["/data/sandbox.asyncapi.yaml"]
        document = parse_document(container.transfers[0][0])
        assert document["servers"] == {"kafka": {"protocol": "kafka", "host": "127.0.0.2:19092"}}
        addresses = {channel["address"] for channel in document["channels"].values()}
        assert addresses == {"orders.events", "payments.events"}
        assert container.command == ["/data/sandbox.asyncapi.yaml"]

    def test_start_consumes_the_declared_topics_and_opens_the_producer(self, monkeypatch: pytest.MonkeyPatch):
        """A started engine probes health and bootstraps the producer at the mapped address."""
        fake_requests = FakeRequests()
        FakeProducer.built.clear()
        engine = armed_engine(monkeypatch, fake_requests)

        engine.start([produce_op("orders.events", {"id": 1})])

        try:
            container = engine._container
            assert container is not None
            assert container.starts == 1
            assert fake_requests.probes[0] == ("http://127.0.0.2:18080/health", 5)
            producer = engine._producer
            assert isinstance(producer, FakeProducer)
            assert producer.kwargs["bootstrap_servers"] == "127.0.0.2:19092"
            assert producer.delivered == [("orders.events", None, {"id": 1}, 10)]
        finally:
            engine.stop()

    def test_start_fails_fast_without_topics_before_any_docker_call(self, monkeypatch: pytest.MonkeyPatch):
        """Scenario 19: an empty topic declaration fails start before any docker call."""
        builds: list[str] = []

        def build_spy(image: str, **kwargs: object) -> FakeDockerContainer:
            builds.append(image)

            return FakeDockerContainer(image, **kwargs)

        monkeypatch.setattr(kafka_module, "DockerContainer", build_spy)
        monkeypatch.setattr(kafka_module, "DockerClient", FakeDockerClient)
        monkeypatch.setattr(kafka_module, "reserve_port", lambda: 19092)
        engine = events_engine(topics=[])

        with pytest.raises(
            EngineError,
            match=r"service 'events': no topics declared.*mock opens no kafka listener",
        ):
            engine.start([produce_op("orders.events", {"id": 1})])

        assert builds == []
        assert engine._container is None


class TestGeneratedDocument:
    """Scenario 17: the in-memory AsyncAPI document of the declared topology."""

    def test_kafka_generated_document_shape(self):
        """The generated document carries the mapped server, declared channels, no messages.

        The document is AsyncAPI 3.0 — the grammar the pinned mokapi parses (the channel
        ``address`` carries the topic name; the 2.6 channel-key form was verified live to
        bind the default port and declare no topics).
        """
        content = _generate_document("events", sample_topics(), "localhost", 9093)
        document = parse_document(content)

        assert document["asyncapi"] == "3.0.0"
        assert document["info"] == {"title": "events", "version": "1.0.0"}
        assert document["servers"] == {"kafka": {"protocol": "kafka", "host": "localhost:9093"}}

        by_address = {channel["address"]: channel for channel in document["channels"].values()}
        assert set(by_address) == {"orders.events", "payments.events"}
        assert by_address["orders.events"]["bindings"]["kafka"]["partitions"] == 1
        assert by_address["payments.events"]["bindings"]["kafka"]["partitions"] == 6
        assert b"messages" not in content

    def test_generated_document_is_never_written_to_disk(self, monkeypatch: pytest.MonkeyPatch, tmp_path):
        """The generator touches no filesystem path — the document stays in memory."""
        written: list[str] = []
        real_open = open

        def spying_open(file: object, mode: str = "r", *args: object, **kwargs: object) -> object:
            if any(flag in mode for flag in ("w", "a", "x", "+")):
                written.append(str(file))

            return real_open(file, mode, *args, **kwargs)

        monkeypatch.setattr("builtins.open", spying_open)
        monkeypatch.chdir(tmp_path)

        content = _generate_document("events", sample_topics(), "localhost", 9093)

        assert content
        assert written == []


class TestKafkaEngineReadiness:
    """Health probing of the kafka engine, driven over the fake requests namespace."""

    def test_wait_ready_probes_health_until_success(self, monkeypatch: pytest.MonkeyPatch):
        """The probe polls the mapped HTTP health endpoint on the declared interval."""
        fake_requests = FakeRequests(statuses=[503, 503])
        clock = install_fake_clock(monkeypatch)
        monkeypatch.setattr(kafka_module, "requests", fake_requests)
        engine = events_engine()
        engine._container = FakeDockerContainer("mokapi/mokapi:0.52.0")

        engine._wait_ready()

        assert fake_requests.probes == [("http://127.0.0.2:18080/health", 5)] * 3
        assert clock.slept == [0.5, 0.5]

    def test_wait_ready_fails_past_the_declared_deadline(self, monkeypatch: pytest.MonkeyPatch):
        """A health endpoint that never answers fails when the declared deadline expires."""
        fake_requests = FakeRequests(statuses=[503] * 8)
        clock = install_fake_clock(monkeypatch)
        monkeypatch.setattr(kafka_module, "requests", fake_requests)
        engine = events_engine(probe=ProbeConfig(timeout=0.2, interval=0.05))
        engine._container = FakeDockerContainer("mokapi/mokapi:0.52.0")

        with pytest.raises(RuntimeError, match=r"health endpoint .*did not succeed within 0\.2s"):
            engine._wait_ready()

        assert clock.slept == [0.05] * len(clock.slept)
        assert len(clock.slept) >= 4
        assert fake_requests.probes[0] == ("http://127.0.0.2:18080/health", 5)

    def test_wait_ready_without_a_probe_uses_the_default_bounds(self):
        """No probe declared — the readiness bounds reproduce the established 30.0/0.5 wait."""
        assert events_engine()._readiness_bounds == (30.0, 0.5)


class TestKafkaEnginePlane:
    """Producer plane, execution and wipe of the kafka engine, driven over the fakes."""

    def test_open_plane_builds_the_producer_against_the_mapped_kafka_port(self, monkeypatch: pytest.MonkeyPatch):
        """The producer bootstraps against the mapped address with Serializer-interface serializers."""
        monkeypatch.setattr(kafka_module, "KafkaProducer", FakeProducer)
        engine = events_engine()
        engine._container = FakeDockerContainer("mokapi/mokapi:0.52.0")
        engine._container_port = 19092

        engine._open_plane()

        producer = engine._producer
        assert isinstance(producer, FakeProducer)
        assert producer.kwargs["bootstrap_servers"] == "127.0.0.2:19092"
        assert producer.kwargs["acks"] == "all"
        assert producer.kwargs["retries"] == 3
        assert isinstance(producer.kwargs["value_serializer"], Serializer)
        assert isinstance(producer.kwargs["key_serializer"], Serializer)

    def test_serialize_value_json_encodes_mappings_and_utf8_encodes_strings(self):
        """Mapping values serialize as JSON; plain strings encode as UTF-8 directly."""
        assert _serialize_value({"id": 1, "ok": True}) == b'{"id": 1, "ok": true}'
        assert _serialize_value("plain") == b"plain"

    def test_serialize_key_utf8_encodes_keys_and_keeps_keyless_messages_keyless(self):
        """Keys encode as UTF-8; a keyless message stays keyless — the wire contract."""
        assert kafka_module._serialize_key("order-1") == b"order-1"
        assert kafka_module._serialize_key(None) is None

    def test_value_serializer_implements_the_serializer_interface_dispatch(self):
        """The ``Serializer`` adapter carries the mapping/string encoding through the ABI."""
        serializer = kafka_module._ValueSerializer()

        assert isinstance(serializer, Serializer)
        assert serializer.serialize("orders.events", [], {"id": 1}) == b'{"id": 1}'
        assert serializer.serialize("orders.events", [], "plain") == b"plain"

    def test_key_serializer_implements_the_serializer_interface_dispatch(self):
        """The key ``Serializer`` adapter carries the UTF-8/keyless encoding through the ABI."""
        serializer = kafka_module._KeySerializer()

        assert isinstance(serializer, Serializer)
        assert serializer.serialize("orders.events", [], "order-1") == b"order-1"
        assert serializer.serialize("orders.events", [], None) is None

    def test_execute_produce_sends_and_awaits_delivery(self):
        """A ``produce`` operation sends the message and awaits the delivery future."""
        engine = events_engine()
        producer = FakeProducer()
        engine._producer = producer

        engine._execute(produce_op("orders.events", {"id": 1}, key="order-1"))

        assert producer.sent == [("orders.events", "order-1", {"id": 1})]
        assert producer.delivered == [("orders.events", "order-1", {"id": 1}, 10)]

    def test_execute_produce_into_undeclared_topic_fails_naming_the_declared_topics(self):
        """A produce for an undeclared topic fails without touching the producer (D9)."""
        engine = events_engine()
        producer = FakeProducer()
        engine._producer = producer

        with pytest.raises(
            EngineError,
            match=r"service 'events': topic 'nope\.topic' is not declared on the kafka service entry "
            r"\(declared topics: orders\.events, payments\.events\)",
        ):
            engine._execute(produce_op("nope.topic", {"id": 1}))

        assert producer.sent == []

    def test_apply_flushes_once_after_the_group(self):
        """The apply group boundary flushes the producer once with the batch timeout."""
        engine = events_engine()
        producer = FakeProducer()
        engine._producer = producer
        engine._started = True

        engine.apply([produce_op("orders.events", {"id": 1}), produce_op("orders.events", {"id": 2})])

        assert len(producer.sent) == 2
        assert producer.flushes == [30]

    def test_apply_with_no_operations_flushes_nothing(self):
        """An empty apply group is a no-op — no flush, no send."""
        engine = events_engine()
        producer = FakeProducer()
        engine._producer = producer
        engine._started = True

        engine.apply([])

        assert producer.flushes == []

    def test_wipe_restarts_the_same_container_rewaits_health_and_rebuilds_the_producer(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Reset-wipe restarts the wrapped SDK container, re-probes health, rebuilds the producer."""
        fake_requests = FakeRequests()
        monkeypatch.setattr(kafka_module, "requests", fake_requests)
        install_fake_clock(monkeypatch)
        monkeypatch.setattr(kafka_module, "KafkaProducer", FakeProducer)
        FakeProducer.built.clear()
        engine = events_engine()
        engine._container = FakeDockerContainer("mokapi/mokapi:0.52.0")
        engine._container_port = 19092
        stale = FakeProducer()
        engine._producer = stale

        address_before = engine.address
        engine._wipe()

        assert engine._container.wrapped.restarts == [10]
        assert fake_requests.probes == [("http://127.0.0.2:18080/health", 5)]
        assert len(FakeProducer.built) == 2
        assert engine._producer is FakeProducer.built[-1]
        assert stale.close_timeouts == [30]
        assert engine.address == address_before

    def test_close_plane_closes_the_producer_and_is_safe_twice(self):
        """Stop closes the bounded producer; a second close touches nothing."""
        engine = events_engine()
        producer = FakeProducer()
        engine._producer = producer

        engine._close_plane()
        engine._close_plane()

        assert producer.close_timeouts == [30]
        assert engine._producer is None


class TestKafkaEngineLifecycle:
    """Full lifecycle of the kafka engine over the fakes — start, journal, reset, stop."""

    def test_start_applies_startup_produces_and_journals_them(self, monkeypatch: pytest.MonkeyPatch):
        """Startup produces execute in order and join the journal as the initial baseline."""
        fake_requests = FakeRequests()
        engine = armed_engine(monkeypatch, fake_requests)
        startup = [produce_op("orders.events", {"id": 1}), produce_op("payments.events", {"id": 2})]

        engine.start(startup)

        try:
            producer = engine._producer
            assert isinstance(producer, FakeProducer)
            assert producer.sent == [
                ("orders.events", None, {"id": 1}),
                ("payments.events", None, {"id": 2}),
            ]
            assert engine._journal == startup
        finally:
            engine.stop()

        assert engine._container is None

    def test_reset_replays_the_journal_after_the_restart(self, monkeypatch: pytest.MonkeyPatch):
        """Reset restarts the container empty and replays the journaled baseline produces."""
        fake_requests = FakeRequests(statuses=[503, 503, 200, 200])
        engine = armed_engine(monkeypatch, fake_requests)
        engine._container = FakeDockerContainer("mokapi/mokapi:0.52.0")
        engine._container_port = 19092
        engine._started = True
        baseline = [produce_op("orders.events", {"id": 0}, key="baseline")]
        engine._journal = list(baseline)

        engine.reset()

        producer = engine._producer
        assert isinstance(producer, FakeProducer)
        assert engine._container is not None
        assert engine._container.wrapped.restarts == [10]
        assert producer.sent == [("orders.events", "baseline", {"id": 0})]
        assert producer.flushes[-1] == 30

    def test_stop_is_safe_twice(self, monkeypatch: pytest.MonkeyPatch):
        """A second stop touches nothing — the container is removed exactly once."""
        engine = armed_engine(monkeypatch, FakeRequests())
        engine.start([])

        container = engine._container
        engine.stop()
        engine.stop()

        assert container is not None
        assert container.stops == 1


@requires_docker
class TestKafkaEngineContainer:
    """Live behavior of the kafka engine against a real container (docker-gated)."""

    @staticmethod
    def _consumed_values(engine: KafkaEngine, topic: str) -> list[object]:
        """Read every message currently on ``topic``, from the beginning.

        Args:
            engine: The started kafka engine owning the mapped broker address.
            topic: A topic declared on the service entry.

        Returns:
            The JSON-deserialized message values currently held by the topic.
        """
        address = engine.address
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=f"{address.host}:{address.port}",
            auto_offset_reset="earliest",
            enable_auto_commit=False,
            consumer_timeout_ms=5000,
        )

        try:
            return [json.loads(message.value.decode("utf-8")) for message in consumer]
        finally:
            consumer.close()

    def test_kafka_engine_produce_into_undeclared_topic_fails(self):
        """Scenario 18: a produce for an undeclared topic fails listing the declared ones."""
        engine = events_engine()
        engine.start([])

        try:
            with pytest.raises(
                EngineError,
                match=r"service 'events': topic 'nope\.topic' is not declared.*orders\.events",
            ):
                engine.apply([produce_op("nope.topic", {"id": 1})])
        finally:
            engine.stop()

        engine.stop()

    def test_kafka_engine_inline_topics_and_restart_reset(self):
        """Declared topics boot the topology with partitions; reset restarts and replays."""
        engine = events_engine()
        engine.start([])

        try:
            address_before = engine.address
            probe = KafkaConsumer(bootstrap_servers=f"{address_before.host}:{address_before.port}")

            try:
                assert probe.partitions_for_topic("orders.events") is not None
                assert len(probe.partitions_for_topic("payments.events")) == 6
            finally:
                probe.close()

            engine.apply([produce_op("orders.events", {"id": 1})])

            # record journals without applying — the baseline boundary is the applying seam.
            engine.record([produce_op("orders.events", {"id": 0}, key="baseline")])
            engine.apply([produce_op("orders.events", {"id": 2})])

            assert self._consumed_values(engine, "orders.events") == [{"id": 1}, {"id": 2}]

            engine.reset()

            assert engine.address == address_before
            # The restart wiped the in-memory state: only the replayed baseline remains.
            assert self._consumed_values(engine, "orders.events") == [{"id": 0}]

            engine.apply([produce_op("orders.events", {"id": 3})])

            assert self._consumed_values(engine, "orders.events") == [{"id": 0}, {"id": 3}]
        finally:
            engine.stop()

        engine.stop()
