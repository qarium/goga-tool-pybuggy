"""Contract and logic tests for the ``KafkaEngine`` entity."""

import inspect
import json
from typing import ClassVar

import pytest
import requests
from goga_tool_pybuggy.sandbox.config import InstanceConfig
from goga_tool_pybuggy.sandbox.engines import BaseEngine, DataOperation, KafkaEngine
from goga_tool_pybuggy.sandbox.engines import kafka as kafka_module
from goga_tool_pybuggy.sandbox.engines.kafka import _serialize_value
from kafka import KafkaConsumer

from ..conftest import requires_docker


def events_engine(image: str | None = None) -> KafkaEngine:
    """Build a kafka engine of the sample ``events`` instance.

    Args:
        image: The optional image override of the instance declaration.

    Returns:
        The engine of an instance named ``events`` of kind ``kafka``.
    """
    return KafkaEngine(InstanceConfig(name="events", kind="kafka", image=image))


def spec_op(path: str) -> DataOperation:
    """Build one kafka startup spec operation.

    Args:
        path: The absolute AsyncAPI document path resolved by the loader.

    Returns:
        A sample startup ``spec`` operation targeted at the ``events`` instance.
    """
    return DataOperation(instance="events", kind="kafka", action="spec", payload={"path": path})


def produce_op(topic: str, value: object, key: str | None = None) -> DataOperation:
    """Build one kafka produce operation.

    Args:
        topic: The target topic of the spec-defined topology.
        value: The message value — a JSON mapping or a plain string.
        key: The optional partitioning key.

    Returns:
        A sample ``produce`` operation targeted at the ``events`` instance.
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


class FakeTime:
    """Namespace double of ``time`` — instant monotonic, no sleeping."""

    def __init__(self) -> None:
        self.now = 100.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


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


class FakeDockerContainer:
    """Container double recording the build configuration and the mapped address."""

    def __init__(self, image: str, **kwargs: object) -> None:
        self.image = image
        self.kwargs = kwargs
        self.exposed_ports: list[int] = []
        self.volume_mounts: list[tuple[str, str, str]] = []
        self.command: str | list[str] | None = None
        self.wrapped = FakeWrappedContainer()
        self.stops = 0
        self.starts = 0

    def start(self) -> "FakeDockerContainer":
        self.starts += 1

        return self

    def with_exposed_ports(self, *ports: int) -> "FakeDockerContainer":
        self.exposed_ports.extend(ports)

        return self

    def with_volume_mapping(self, host: str, container: str, mode: str = "ro") -> "FakeDockerContainer":
        self.volume_mounts.append((host, container, mode))

        return self

    def with_command(self, command: str | list[str]) -> "FakeDockerContainer":
        self.command = command

        return self

    def get_container_host_ip(self) -> str:
        return "127.0.0.2"

    def get_exposed_port(self, port: int) -> str:
        return {8080: "18080", 9092: "19092"}[port]

    def get_wrapped_container(self) -> FakeWrappedContainer:
        return self.wrapped

    def stop(self) -> None:
        self.stops += 1


class TestKafkaEngineContract:
    """Declared API of the ``KafkaEngine`` entity."""

    def test_kafka_engine_is_importable_from_engines_facade(self):
        """``KafkaEngine`` is re-exported by the ``goga_tool_pybuggy.sandbox.engines`` facade."""
        assert KafkaEngine is not None

    def test_kafka_engine_subclasses_base_engine(self):
        """The kind engine inherits the base contract."""
        assert issubclass(KafkaEngine, BaseEngine)

    def test_kafka_engine_declares_the_contract_constructor(self):
        """The constructor signature is ``__init__(self, config)``."""
        signature = inspect.signature(KafkaEngine.__init__)

        assert list(signature.parameters) == ["self", "config"]

    def test_kafka_engine_inherits_the_contract_methods(self):
        """``start`` / ``apply`` / ``record`` / ``reset`` / ``stop`` resolve with declared parameters."""
        expected = {
            "start": ["self", "startup"],
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


class TestKafkaEngineBuild:
    """Container build arguments of the kafka engine, driven through the patched constructor."""

    def test_build_uses_the_pinned_image_labels_and_both_ports(self, monkeypatch: pytest.MonkeyPatch):
        """Without an image override the build uses the pinned mokapi image, labels, both ports."""
        monkeypatch.setattr(kafka_module, "DockerContainer", FakeDockerContainer)
        engine = events_engine()

        container = engine._build_container()

        assert container.image == "mokapi/mokapi:0.28.0"
        assert container.kwargs["labels"] == {"pybuggy-sandbox": "true"}
        assert container.exposed_ports == [8080, 9092]
        assert container.volume_mounts == []
        assert container.command is None

    def test_build_honors_the_image_override(self, monkeypatch: pytest.MonkeyPatch):
        """The image override of the instance config reaches the container build."""
        monkeypatch.setattr(kafka_module, "DockerContainer", FakeDockerContainer)
        engine = events_engine(image="mokapi/mokapi:0.29.0")

        container = engine._build_container()

        assert container.image == "mokapi/mokapi:0.29.0"

    def test_build_mounts_the_startup_spec_and_passes_it_as_command(self, monkeypatch: pytest.MonkeyPatch):
        """The startup spec op is consumed at container build — mounted read-only, command argument."""
        monkeypatch.setattr(kafka_module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(kafka_module, "requests", FakeRequests())
        monkeypatch.setattr(kafka_module, "time", FakeTime())
        monkeypatch.setattr(kafka_module, "KafkaProducer", FakeProducer)
        engine = events_engine()

        engine.start([spec_op("/tmp/docs/asyncapi.yaml")])

        try:
            container = engine._container
            assert container is not None
            assert container.volume_mounts == [("/tmp/docs/asyncapi.yaml", "/data/asyncapi.yaml", "ro")]
            assert container.command == ["/data/asyncapi.yaml"]
        finally:
            engine.stop()

    def test_start_stashes_the_startup_specs_from_the_startup_operations(self, monkeypatch: pytest.MonkeyPatch):
        """Every startup spec path is extracted before the container build consumes them."""
        monkeypatch.setattr(kafka_module, "DockerContainer", FakeDockerContainer)
        monkeypatch.setattr(kafka_module, "requests", FakeRequests())
        monkeypatch.setattr(kafka_module, "time", FakeTime())
        monkeypatch.setattr(kafka_module, "KafkaProducer", FakeProducer)
        engine = events_engine()

        engine.start([produce_op("orders.events", {"id": 1}), spec_op("/tmp/a.yaml"), spec_op("/tmp/b.yml")])

        try:
            container = engine._container
            assert container is not None
            assert container.volume_mounts == [
                ("/tmp/a.yaml", "/data/a.yaml", "ro"),
                ("/tmp/b.yml", "/data/b.yml", "ro"),
            ]
            assert container.command == ["/data/a.yaml", "/data/b.yml"]
        finally:
            engine.stop()


class TestKafkaEngineReadiness:
    """Health probing of the kafka engine, driven over the fake requests namespace."""

    def test_wait_ready_probes_health_until_success(self, monkeypatch: pytest.MonkeyPatch):
        """The probe polls the mapped HTTP health endpoint on the readiness interval."""
        fake_requests = FakeRequests(statuses=[503, 503])
        fake_time = FakeTime()
        monkeypatch.setattr(kafka_module, "requests", fake_requests)
        monkeypatch.setattr(kafka_module, "time", fake_time)
        engine = events_engine()
        engine._container = FakeDockerContainer("mokapi/mokapi:0.28.0")

        engine._wait_ready()

        assert fake_requests.probes == [("http://127.0.0.2:18080/health", 5)] * 3

    def test_wait_ready_fails_past_the_deadline(self, monkeypatch: pytest.MonkeyPatch):
        """A health endpoint that never answers fails within the 30s deadline."""
        fake_requests = FakeRequests(statuses=[503] * 100)
        fake_time = FakeTime()
        monkeypatch.setattr(kafka_module, "requests", fake_requests)
        monkeypatch.setattr(kafka_module, "time", fake_time)
        engine = events_engine()
        engine._container = FakeDockerContainer("mokapi/mokapi:0.28.0")

        with pytest.raises(RuntimeError, match=r"health.*did not succeed"):
            engine._wait_ready()

        assert fake_requests.probes[0] == ("http://127.0.0.2:18080/health", 5)


class TestKafkaEnginePlane:
    """Producer plane, execution and wipe of the kafka engine, driven over the fakes."""

    def test_open_plane_builds_the_producer_against_the_mapped_kafka_port(self, monkeypatch: pytest.MonkeyPatch):
        """The producer bootstraps against the mapped 9092 address with the pinned options."""
        monkeypatch.setattr(kafka_module, "KafkaProducer", FakeProducer)
        engine = events_engine()
        engine._container = FakeDockerContainer("mokapi/mokapi:0.28.0")

        engine._open_plane()

        producer = engine._producer
        assert isinstance(producer, FakeProducer)
        assert producer.kwargs["bootstrap_servers"] == "127.0.0.2:19092"
        assert producer.kwargs["acks"] == "all"
        assert producer.kwargs["retries"] == 3
        assert callable(producer.kwargs["value_serializer"])
        assert callable(producer.kwargs["key_serializer"])

    def test_serialize_value_json_encodes_mappings_and_utf8_encodes_strings(self):
        """Mapping values serialize as JSON; plain strings encode as UTF-8 directly."""
        assert _serialize_value({"id": 1, "ok": True}) == b'{"id": 1, "ok": true}'
        assert _serialize_value("plain") == b"plain"

    def test_execute_spec_operation_is_a_noop(self):
        """A replayed ``spec`` operation executes nothing — it was consumed at container build."""
        engine = events_engine()
        engine._producer = FakeProducer()

        engine._execute(spec_op("/tmp/asyncapi.yaml"))

        assert engine._producer.sent == []

    def test_execute_produce_sends_and_awaits_delivery(self):
        """A ``produce`` operation sends the message and awaits the delivery future."""
        engine = events_engine()
        producer = FakeProducer()
        engine._producer = producer

        engine._execute(produce_op("orders.events", {"id": 1}, key="order-1"))

        assert producer.sent == [("orders.events", "order-1", {"id": 1})]
        assert producer.delivered == [("orders.events", "order-1", {"id": 1}, 10)]

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
        monkeypatch.setattr(kafka_module, "time", FakeTime())
        monkeypatch.setattr(kafka_module, "KafkaProducer", FakeProducer)
        FakeProducer.built.clear()
        engine = events_engine()
        engine._container = FakeDockerContainer("mokapi/mokapi:0.28.0")
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


@requires_docker
class TestKafkaEngineContainer:
    """Live behavior of the kafka engine against a real container (docker-gated)."""

    @staticmethod
    def _consumed_values(engine: KafkaEngine, topic: str) -> list[object]:
        """Read every message currently on ``topic``, from the beginning.

        Args:
            engine: The started kafka engine owning the mapped broker address.
            topic: The spec-defined topic to drain.

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
            value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
        )

        try:
            return [message.value for message in consumer]
        finally:
            consumer.close()

    def test_kafka_engine_spec_mount_and_restart_reset(self, tmp_path: pytest.TempPathFactory):
        """Reset restarts the same container: address stable, messages wiped, baseline replayed."""
        spec = tmp_path / "asyncapi.yaml"
        spec.write_text(
            """
asyncapi: 3.0.0
info:
  title: events sandbox
  version: 1.0.0
servers:
  production:
    host: localhost:9092
    protocol: kafka
channels:
  orders.events:
    bindings:
      kafka:
        topic: orders.events
        partitions: 1
""",
            encoding="utf-8",
        )
        engine = events_engine()
        engine.start([spec_op(str(spec))])

        try:
            address_before = engine.address
            engine.apply([produce_op("orders.events", {"id": 1})])

            engine.record([produce_op("orders.events", {"id": 0}, key="baseline")])
            engine.apply([produce_op("orders.events", {"id": 2})])

            assert self._consumed_values(engine, "orders.events") == [{"id": 1}, {"id": 0}, {"id": 2}]

            engine.reset()

            assert engine.address == address_before
            # The restart wiped the in-memory state: only the replayed baseline remains.
            assert self._consumed_values(engine, "orders.events") == [{"id": 0}]

            engine.apply([produce_op("orders.events", {"id": 3})])

            assert self._consumed_values(engine, "orders.events") == [{"id": 0}, {"id": 3}]
        finally:
            engine.stop()

        engine.stop()
