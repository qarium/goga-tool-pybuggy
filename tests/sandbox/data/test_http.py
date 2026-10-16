"""Contract and logic tests for the ``HttpInstance`` view."""

import inspect

from goga_tool_pybuggy.sandbox.data import DataBatch, HttpInstance
from goga_tool_pybuggy.sandbox.engines import InstanceAddress

from .conftest import RecordingBatch


class TestHttpInstanceContract:
    """Declared API of the ``HttpInstance`` entity."""

    def test_http_instance_is_importable_from_data_facade(self):
        """``HttpInstance`` is re-exported by the ``goga_tool_pybuggy.sandbox.data`` facade."""
        assert HttpInstance is not None

    def test_http_instance_constructor_declares_the_contract_parameters(self):
        """The constructor takes ``name``, ``address`` and ``batch`` with the declared types."""
        parameters = inspect.signature(HttpInstance.__init__).parameters

        assert list(parameters) == ["self", "name", "address", "batch"]
        assert parameters["name"].annotation is str
        assert parameters["address"].annotation is InstanceAddress
        assert parameters["batch"].annotation is DataBatch

    def test_http_instance_declares_the_contract_properties(self):
        """The class exposes ``name``, ``host`` and ``port`` as read-only properties."""
        for property_name in ("name", "host", "port"):
            attribute = inspect.getattr_static(HttpInstance, property_name)

            assert isinstance(attribute, property), property_name

    def test_http_instance_declares_the_one_declaring_method(self):
        """The class exposes exactly one declaring method — ``stub(mapping)``."""
        parameters = inspect.signature(HttpInstance.stub).parameters

        assert list(parameters) == ["self", "mapping"]
        assert parameters["mapping"].annotation == dict[str, object]


class TestHttpInstanceLogic:
    """Declaration behavior of the ``HttpInstance`` view."""

    def test_stub_appends_exactly_one_operation_with_mapping_passthrough(
        self, recording_batch: RecordingBatch, address: InstanceAddress
    ):
        """One ``stub`` call declares one http stub operation whose payload is the mapping."""
        mapping = {
            "request": {"method": "POST", "urlPath": "/v1/charge", "priority": 2},
            "response": {"status": 200, "jsonBody": {"status": "captured"}, "fixedDelayMilliseconds": 50},
        }
        view = HttpInstance(name="payments", address=address, batch=recording_batch)

        view.stub(mapping)

        assert len(recording_batch.added) == 1

        operation = recording_batch.added[0]

        assert operation.instance == "payments"
        assert operation.kind == "http"
        assert operation.action == "stub"
        assert operation.payload == mapping

    def test_properties_read_from_name_and_address(self, recording_batch: RecordingBatch, address: InstanceAddress):
        """``name`` comes from construction; ``host`` and ``port`` read through the address."""
        view = HttpInstance(name="payments", address=address, batch=recording_batch)

        assert view.name == "payments"
        assert view.host == "127.0.0.5"
        assert view.port == 5432

    def test_stub_declares_only_the_batch_executes_nothing(
        self, recording_batch: RecordingBatch, address: InstanceAddress
    ):
        """The declaration only accumulates — the batch still holds it for a later drain."""
        view = HttpInstance(name="payments", address=address, batch=recording_batch)

        view.stub({"request": {"method": "GET", "urlPath": "/v1/rate"}, "response": {"status": 200}})

        assert recording_batch.take() == recording_batch.added
        assert recording_batch.take() == []

    def test_stub_passes_mapping_features_through_untouched(
        self, recording_batch: RecordingBatch, address: InstanceAddress
    ):
        """Matching, priority, delays and faults stay available — nothing is stripped."""
        mapping: dict[str, object] = {
            "name": "charge",
            "priority": 3,
            "request": {"method": "POST", "urlPath": "/v1/charge"},
            "response": {"status": 500, "fault": "CONNECTION_RESET_BY_PEER"},
        }
        view = HttpInstance(name="payments", address=address, batch=recording_batch)

        view.stub(mapping)

        assert recording_batch.added[0].payload == mapping

    def test_repeated_stubs_accumulate_in_call_order(self, recording_batch: RecordingBatch, address: InstanceAddress):
        """Several declarations accumulate in call order — one operation each."""
        view = HttpInstance(name="payments", address=address, batch=recording_batch)

        view.stub({"request": {"method": "GET", "urlPath": "/a"}, "response": {"status": 200}})
        view.stub({"request": {"method": "GET", "urlPath": "/b"}, "response": {"status": 201}})

        assert [operation.payload["response"]["status"] for operation in recording_batch.added] == [200, 201]
