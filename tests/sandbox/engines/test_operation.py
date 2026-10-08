"""Contract and logic tests for the ``DataOperation`` entity."""

import ast
import inspect
from pathlib import Path

import pytest
from goga_tool_pybuggy.sandbox.engines import DataOperation
from pydantic import BaseModel

ENGINES_PACKAGE_DIR = Path(inspect.getsourcefile(DataOperation)).parent


def spec_dispatch_findings() -> list[str]:
    """Locate ``spec`` dispatch branches inside every ``_execute`` method of the engines package.

    A raw substring scan does not work — the package legitimately carries the word ``spec`` in
    the retained ``SPEC_MOUNT_DIR`` constant and migration-note docstrings. The dispatch level
    is precise: an equality comparison against the ``"spec"`` constant or a ``"spec"`` entry of
    a dict dispatch, inside an ``_execute`` method body.

    Returns:
        The ``file:line`` location of every ``spec`` dispatch finding; empty when none exist.
    """
    findings: list[str] = []

    for source_path in sorted(ENGINES_PACKAGE_DIR.glob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name != "_execute":
                continue

            for inner in ast.walk(node):
                if isinstance(inner, ast.Compare):
                    operands = [inner.left, *inner.comparators]

                    if any(isinstance(operand, ast.Constant) and operand.value == "spec" for operand in operands):
                        findings.append(f"{source_path.name}:{inner.lineno}")

                if isinstance(inner, ast.Dict):
                    keys = [key for key in inner.keys if key is not None]

                    if any(isinstance(key, ast.Constant) and key.value == "spec" for key in keys):
                        findings.append(f"{source_path.name}:{inner.lineno}")

    return findings


def execute_method_count() -> int:
    """Count the ``_execute`` method definitions across the engines package source.

    Returns:
        The number of ``_execute`` definitions found — the dispatch-scan coverage guard.
    """
    count = 0

    for source_path in ENGINES_PACKAGE_DIR.glob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))

        count += sum(isinstance(node, ast.FunctionDef) and node.name == "_execute" for node in ast.walk(tree))

    return count


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

    def test_operation_has_no_spec_action(self):
        """The documented action set is exactly insert/produce/put/stub — no ``spec`` anywhere.

        Asserted at the dispatch level: no ``action == "spec"`` branch and no ``"spec"`` entry
        of an ``_execute`` dispatch mapping anywhere in the engines package source.
        """
        assert execute_method_count() >= 1, "the engines package defines _execute methods"
        assert spec_dispatch_findings() == []

    def test_data_operation_documents_the_four_actions_only(self):
        """The class docstring names exactly the four documented actions."""
        documented = DataOperation.__doc__ or ""

        for action in ("insert", "produce", "put", "stub"):
            assert action in documented

        assert "spec" not in documented

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
