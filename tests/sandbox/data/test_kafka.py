"""Contract and logic tests for the ``KafkaInstance`` view."""

import inspect

from goga_tool_pybuggy.sandbox.data import DataBatch, KafkaInstance
from goga_tool_pybuggy.sandbox.engines import InstanceAddress

from .conftest import RecordingBatch


class TestKafkaInstanceContract:
    """Declared API of the ``KafkaInstance`` entity."""

    def test_kafka_instance_is_importable_from_data_facade(self):
        """``KafkaInstance`` is re-exported by the ``goga_tool_pybuggy.sandbox.data`` facade."""
        assert KafkaInstance is not None

    def test_kafka_instance_constructor_declares_the_contract_parameters(self):
        """The constructor takes ``name``, ``address`` and ``batch`` with the declared types."""
        parameters = inspect.signature(KafkaInstance.__init__).parameters

        assert list(parameters) == ["self", "name", "address", "batch"]
        assert parameters["name"].annotation is str
        assert parameters["address"].annotation is InstanceAddress
        assert parameters["batch"].annotation is DataBatch

    def test_kafka_instance_declares_the_contract_properties(self):
        """The class exposes ``name``, ``host`` and ``port`` as read-only properties."""
        for property_name in ("name", "host", "port"):
            attribute = inspect.getattr_static(KafkaInstance, property_name)

            assert isinstance(attribute, property), property_name

    def test_kafka_instance_declares_the_one_declaring_method(self):
        """The class exposes exactly one declaring method — ``produce(topic, value, key)``."""
        parameters = inspect.signature(KafkaInstance.produce).parameters

        assert list(parameters) == ["self", "topic", "value", "key"]
        assert parameters["topic"].annotation is str
        assert parameters["value"].annotation == dict[str, object] | str
        assert parameters["key"].annotation == str | None
        assert parameters["key"].default is None


class TestKafkaInstanceLogic:
    """Declaration behavior of the ``KafkaInstance`` view."""

    def test_produce_appends_exactly_one_operation_with_the_payload_table_shape(
        self, recording_batch: RecordingBatch, address: InstanceAddress
    ):
        """One ``produce`` call declares one kafka produce operation carrying topic, value, key."""
        view = KafkaInstance(name="events", address=address, batch=recording_batch)

        view.produce("orders.events", {"id": 1}, key="1")

        assert len(recording_batch.added) == 1

        operation = recording_batch.added[0]

        assert operation.instance == "events"
        assert operation.kind == "kafka"
        assert operation.action == "produce"
        assert operation.payload == {"topic": "orders.events", "value": {"id": 1}, "key": "1"}

    def test_produce_defaults_the_key_to_none(self, recording_batch: RecordingBatch, address: InstanceAddress):
        """A keyless produce declares ``key=None`` — the optional partition key."""
        view = KafkaInstance(name="events", address=address, batch=recording_batch)

        view.produce("orders.events", "plain message")

        assert recording_batch.added[0].payload == {"topic": "orders.events", "value": "plain message", "key": None}

    def test_properties_read_from_name_and_address(self, recording_batch: RecordingBatch, address: InstanceAddress):
        """``name`` comes from construction; ``host`` and ``port`` read through the address."""
        view = KafkaInstance(name="events", address=address, batch=recording_batch)

        assert view.name == "events"
        assert view.host == "127.0.0.5"
        assert view.port == 5432

    def test_produce_declares_only_the_batch_executes_nothing(
        self, recording_batch: RecordingBatch, address: InstanceAddress
    ):
        """The declaration only accumulates — the batch still holds it for a later drain."""
        view = KafkaInstance(name="events", address=address, batch=recording_batch)

        view.produce("orders.events", {"id": 1}, key="1")

        assert recording_batch.take() == recording_batch.added
        assert recording_batch.take() == []

    def test_repeated_produces_accumulate_in_call_order(
        self, recording_batch: RecordingBatch, address: InstanceAddress
    ):
        """Several declarations accumulate in call order — one operation each."""
        view = KafkaInstance(name="events", address=address, batch=recording_batch)

        view.produce("orders.events", {"id": 1}, key="1")
        view.produce("orders.events", {"id": 2})

        assert [operation.payload["value"] for operation in recording_batch.added] == [{"id": 1}, {"id": 2}]
