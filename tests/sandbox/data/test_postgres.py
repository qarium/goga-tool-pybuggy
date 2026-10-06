"""Contract and logic tests for the ``PostgresInstance`` view."""

import inspect

from goga_tool_pybuggy.sandbox.data import DataBatch, PostgresInstance
from goga_tool_pybuggy.sandbox.engines import InstanceAddress

from .conftest import RecordingBatch


class TestPostgresInstanceContract:
    """Declared API of the ``PostgresInstance`` entity."""

    def test_postgres_instance_is_importable_from_data_facade(self):
        """``PostgresInstance`` is re-exported by the ``goga_tool_pybuggy.sandbox.data`` facade."""
        assert PostgresInstance is not None

    def test_postgres_instance_constructor_declares_the_contract_parameters(self):
        """The constructor takes ``name``, ``address`` and ``batch`` with the declared types."""
        parameters = inspect.signature(PostgresInstance.__init__).parameters

        assert list(parameters) == ["self", "name", "address", "batch"]
        assert parameters["name"].annotation is str
        assert parameters["address"].annotation is InstanceAddress
        assert parameters["batch"].annotation is DataBatch

    def test_postgres_instance_declares_the_contract_properties(self):
        """The class exposes ``name``, ``host`` and ``port`` as read-only properties."""
        for property_name in ("name", "host", "port"):
            attribute = inspect.getattr_static(PostgresInstance, property_name)

            assert isinstance(attribute, property), property_name

    def test_postgres_instance_declares_the_one_declaring_method(self):
        """The class exposes exactly one declaring method — ``insert(table, rows)``."""
        parameters = inspect.signature(PostgresInstance.insert).parameters

        assert list(parameters) == ["self", "table", "rows"]
        assert parameters["table"].annotation is str
        assert parameters["rows"].annotation == list[dict[str, object]]


class TestPostgresInstanceLogic:
    """Declaration behavior of the ``PostgresInstance`` view."""

    def test_insert_appends_exactly_one_operation_with_the_payload_table_shape(
        self, recording_batch: RecordingBatch, address: InstanceAddress
    ):
        """One ``insert`` call declares one postgresql insert operation carrying table and rows."""
        view = PostgresInstance(name="db", address=address, batch=recording_batch)

        view.insert("orders", rows=[{"id": 1, "total": 100}, {"id": 2, "total": 5}])

        assert len(recording_batch.added) == 1

        operation = recording_batch.added[0]

        assert operation.instance == "db"
        assert operation.kind == "postgresql"
        assert operation.action == "insert"
        assert operation.payload == {"table": "orders", "rows": [{"id": 1, "total": 100}, {"id": 2, "total": 5}]}

    def test_properties_read_from_name_and_address(self, recording_batch: RecordingBatch, address: InstanceAddress):
        """``name`` comes from construction; ``host`` and ``port`` read through the address."""
        view = PostgresInstance(name="db", address=address, batch=recording_batch)

        assert view.name == "db"
        assert view.host == "127.0.0.5"
        assert view.port == 5432

    def test_insert_declares_only_the_batch_executes_nothing(
        self, recording_batch: RecordingBatch, address: InstanceAddress
    ):
        """The declaration only accumulates — the batch still holds it for a later drain."""
        view = PostgresInstance(name="db", address=address, batch=recording_batch)

        view.insert("orders", rows=[{"id": 1}])

        assert recording_batch.take() == recording_batch.added
        assert recording_batch.take() == []

    def test_repeated_inserts_accumulate_in_call_order(self, recording_batch: RecordingBatch, address: InstanceAddress):
        """Several declarations accumulate in call order — one operation each, parents first."""
        view = PostgresInstance(name="db", address=address, batch=recording_batch)

        view.insert("customers", rows=[{"id": 1}])
        view.insert("orders", rows=[{"id": 100, "customer_id": 1}])

        assert [operation.payload["table"] for operation in recording_batch.added] == ["customers", "orders"]

    def test_insert_passes_rows_through_untouched(self, recording_batch: RecordingBatch, address: InstanceAddress):
        """Rows pass through as given — the payload carries the author's data unchanged."""
        rows: list[dict[str, object]] = [{"id": 1, "labels": ["a", "b"]}, {"id": 2, "labels": []}]
        view = PostgresInstance(name="db", address=address, batch=recording_batch)

        view.insert("orders", rows=rows)

        assert recording_batch.added[0].payload["rows"] == rows

    def test_insert_with_empty_rows_still_declares(self, recording_batch: RecordingBatch, address: InstanceAddress):
        """An empty row list is a valid declaration — the engine treats it as a no-op."""
        view = PostgresInstance(name="db", address=address, batch=recording_batch)

        view.insert("orders", rows=[])

        assert recording_batch.added[0].payload == {"table": "orders", "rows": []}
