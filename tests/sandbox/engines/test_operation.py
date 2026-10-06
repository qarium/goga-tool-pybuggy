"""Contract and logic tests for the ``DataOperation`` entity."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox.engines import DataOperation
from pydantic import BaseModel


class TestDataOperationContract:
    """Declared API of the ``DataOperation`` entity."""

    def test_data_operation_is_importable_from_engines_facade(self):
        """``DataOperation`` is re-exported by the ``goga_tool_pybuggy.sandbox.engines`` facade."""
        assert DataOperation is not None

    def test_data_operation_is_a_pydantic_model(self):
        """``DataOperation`` subclasses ``pydantic.BaseModel``."""
        assert issubclass(DataOperation, BaseModel)

    def test_data_operation_constructor_is_kw_only(self):
        """All constructor parameters are keyword-only (no positional args)."""
        signature = inspect.signature(DataOperation)

        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_data_operation_declares_the_contract_fields(self):
        """The model declares the ``instance``, ``kind``, ``action`` and ``payload`` fields only."""
        assert set(DataOperation.model_fields) == {"instance", "kind", "action", "payload"}

    def test_data_operation_properties_return_declared_types(self):
        """Construction with sample data exposes the declared property types."""
        operation = DataOperation(
            instance="db",
            kind="postgresql",
            action="insert",
            payload={"table": "orders", "rows": [{"id": 1}]},
        )

        assert isinstance(operation.instance, str)
        assert isinstance(operation.kind, str)
        assert isinstance(operation.action, str)
        assert isinstance(operation.payload, dict)


class TestDataOperationLogic:
    """Construction and payload behavior of ``DataOperation``."""

    def test_data_operation_positional_construction_raises_type_error(self):
        """Positional construction is rejected — keyword arguments only."""
        with pytest.raises(TypeError):
            DataOperation("db", "postgresql", "insert", {})  # type: ignore[misc]

    def test_data_operation_constructs_every_payload_table_row(self):
        """Every row of the common payload table constructs and round-trips its payload."""
        operations = [
            DataOperation(
                instance="db",
                kind="postgresql",
                action="insert",
                payload={"table": "orders", "rows": [{"id": 1, "n": 5}]},
            ),
            DataOperation(
                instance="db",
                kind="postgresql",
                action="insert",
                payload={"sql": "CREATE TABLE orders (id int PRIMARY KEY)"},
            ),
            DataOperation(
                instance="events",
                kind="kafka",
                action="produce",
                payload={"topic": "orders.created", "value": {"id": 1}, "key": "1"},
            ),
            DataOperation(
                instance="events",
                kind="kafka",
                action="spec",
                payload={"path": "/repo/asyncapi.yaml"},
            ),
            DataOperation(
                instance="secrets",
                kind="vault",
                action="put",
                payload={"path": "payment/api-key", "data": {"api_key": "k"}},
            ),
            DataOperation(
                instance="payments",
                kind="http",
                action="stub",
                payload={"request": {"method": "GET", "url": "/pay"}, "response": {"status": 200}},
            ),
        ]

        for operation in operations:
            assert operation.instance
            assert operation.kind
            assert operation.action
            assert operation.payload

    def test_data_operation_payload_round_trips_plain_data(self):
        """Payload values stay plain dicts, lists and strings — no models, no callables."""
        payload = {
            "table": "orders",
            "rows": [{"id": 1, "labels": ["a", "b"]}, {"id": 2, "labels": []}],
            "note": "plain string",
        }
        operation = DataOperation(instance="db", kind="postgresql", action="insert", payload=payload)

        assert operation.payload == payload
        assert isinstance(operation.payload["table"], str)
        assert isinstance(operation.payload["rows"], list)
        assert isinstance(operation.payload["rows"][0], dict)

    def test_data_operation_accepts_empty_payload_dict(self):
        """An empty payload dict is a valid edge value."""
        operation = DataOperation(instance="db", kind="postgresql", action="insert", payload={})

        assert operation.payload == {}
