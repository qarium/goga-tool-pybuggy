"""Contract and logic tests for the ``InstanceConfig`` entity."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox.config import InstanceConfig
from pydantic import BaseModel


class TestInstanceConfigContract:
    """Declared API of the ``InstanceConfig`` entity."""

    def test_instance_config_is_importable_from_config_facade(self):
        """``InstanceConfig`` is re-exported by the ``goga_tool_pybuggy.sandbox.config`` facade."""
        assert InstanceConfig is not None

    def test_instance_config_is_a_pydantic_model(self):
        """``InstanceConfig`` subclasses ``pydantic.BaseModel``."""
        assert issubclass(InstanceConfig, BaseModel)

    def test_instance_config_constructor_is_kw_only(self):
        """All constructor parameters are keyword-only (no positional args)."""
        signature = inspect.signature(InstanceConfig)

        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_instance_config_declares_the_contract_fields(self):
        """The model declares the ``name``, ``kind`` and ``image`` fields only."""
        assert set(InstanceConfig.model_fields) == {"name", "kind", "image"}

    def test_instance_config_properties_return_declared_types(self):
        """Construction with sample data exposes the declared property types."""
        instance = InstanceConfig(name="db", kind="postgresql", image="postgres:16-alpine")

        assert isinstance(instance.name, str)
        assert isinstance(instance.kind, str)
        assert isinstance(instance.image, str)

    def test_instance_config_image_accepts_none(self):
        """``image`` carries the explicit absence of an override as ``None``."""
        instance = InstanceConfig(name="db", kind="postgresql", image=None)

        assert instance.image is None


class TestInstanceConfigLogic:
    """Construction and behavior of ``InstanceConfig``."""

    def test_instance_config_positional_construction_raises_type_error(self):
        """Positional construction is rejected — keyword arguments only."""
        with pytest.raises(TypeError):
            InstanceConfig("db", "postgresql", None)  # type: ignore[misc]

    def test_instance_config_image_defaults_to_none(self):
        """``image`` defaults to ``None`` (the product-pinned kind default)."""
        instance = InstanceConfig(name="db", kind="postgresql")

        assert instance.image is None
