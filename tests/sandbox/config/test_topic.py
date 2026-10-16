"""Contract and logic tests for the ``TopicConfig`` entity."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox.config import TopicConfig
from pydantic import BaseModel, ValidationError


class TestTopicConfigContract:
    """Declared API of the ``TopicConfig`` entity."""

    def test_topic_config_is_importable_from_config_facade(self):
        """``TopicConfig`` is re-exported by the ``goga_tool_pybuggy.sandbox.config`` facade."""
        assert TopicConfig is not None

    def test_topic_config_is_a_pydantic_model(self):
        """``TopicConfig`` subclasses ``pydantic.BaseModel``."""
        assert issubclass(TopicConfig, BaseModel)

    def test_topic_config_constructor_is_kw_only(self):
        """All constructor parameters are keyword-only (no positional args)."""
        signature = inspect.signature(TopicConfig)

        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_topic_config_declares_the_contract_fields(self):
        """The model declares the ``name`` and ``partitions`` fields only."""
        assert set(TopicConfig.model_fields) == {"name", "partitions"}

    def test_topic_config_properties_return_declared_types(self):
        """Construction with sample data exposes the declared property types."""
        topic = TopicConfig(name="payments.events", partitions=6)

        assert isinstance(topic.name, str)
        assert isinstance(topic.partitions, int)


class TestTopicConfigLogic:
    """Construction and behavior of ``TopicConfig``."""

    def test_topic_config_partitions_default_to_one(self):
        """``partitions`` defaults to 1."""
        topic = TopicConfig(name="orders.events")

        assert topic.partitions == 1

    @pytest.mark.parametrize(
        ("fields", "offender"),
        [
            ({"name": ""}, "name"),
            ({"partitions": 0}, "partitions"),
            ({"partitions": -1}, "partitions"),
        ],
    )
    def test_topic_config_rejects_invalid_values(self, fields: dict[str, object], offender: str):
        """An empty topic name and non-positive partition counts fail validation."""
        with pytest.raises(ValidationError, match=offender):
            TopicConfig(**fields)

    def test_topic_config_positional_construction_raises_type_error(self):
        """Positional construction is rejected — keyword arguments only."""
        with pytest.raises(TypeError):
            TopicConfig("orders.events", 1)  # type: ignore[misc]
