"""Contract and logic tests for the ``DataBatch`` entity."""

import inspect

from goga_tool_pybuggy.sandbox.data import DataBatch
from goga_tool_pybuggy.sandbox.engines import DataOperation


class TestDataBatchContract:
    """Declared API of the ``DataBatch`` entity."""

    def test_data_batch_is_importable_from_data_facade(self):
        """``DataBatch`` is re-exported by the ``goga_tool_pybuggy.sandbox.data`` facade."""
        assert DataBatch is not None

    def test_data_batch_constructor_takes_no_arguments(self):
        """The constructor accepts no parameters — one empty batch per construction."""
        signature = inspect.signature(DataBatch.__init__)

        parameters = list(signature.parameters.values())[1:]

        assert parameters == []

    def test_data_batch_declares_the_two_contract_methods(self):
        """The class exposes exactly ``add`` and ``take`` with the declared signatures."""
        add_parameters = inspect.signature(DataBatch.add).parameters
        take_signature = inspect.signature(DataBatch.take)

        assert set(add_parameters) == {"self", "operation"}
        assert add_parameters["operation"].annotation is DataOperation
        assert list(take_signature.parameters) == ["self"]
        assert take_signature.return_annotation == list[DataOperation]


class TestDataBatchLogic:
    """Accumulation and drain behavior of ``DataBatch``."""

    def test_batch_take_drains_and_repeat_is_empty(self):
        """Two added operations come back in order once; a second take is empty."""
        batch = DataBatch()
        first = DataOperation(instance="db", kind="postgresql", action="insert", payload={"sql": "SELECT 1"})
        second = DataOperation(instance="secrets", kind="vault", action="put", payload={"path": "x", "data": {}})

        batch.add(first)
        batch.add(second)

        assert batch.take() == [first, second]
        assert batch.take() == []

    def test_batch_take_on_fresh_batch_returns_empty_list(self):
        """A fresh batch drains to an empty list."""
        batch = DataBatch()

        assert batch.take() == []

    def test_batch_add_only_accumulates_nothing_executes(self):
        """Adding stores the operations untouched — nothing drains or mutates them."""
        batch = DataBatch()
        operation = DataOperation(instance="db", kind="postgresql", action="insert", payload={"table": "t", "rows": []})

        batch.add(operation)
        batch.add(operation)

        drained = batch.take()

        assert drained == [operation, operation]
        assert drained[0] is operation
        assert batch.take() == []

    def test_batch_accumulation_continues_after_a_drain(self):
        """Operations added after a drain accumulate into the fresh batch state."""
        batch = DataBatch()
        first = DataOperation(instance="db", kind="postgresql", action="insert", payload={"sql": "SELECT 1"})
        second = DataOperation(instance="payments", kind="http", action="stub", payload={"request": {}})

        batch.add(first)

        assert batch.take() == [first]

        batch.add(second)

        assert batch.take() == [second]
