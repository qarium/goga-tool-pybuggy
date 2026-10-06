"""Contract and logic tests for the ``ServiceConfig`` entity."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox.config import ServiceConfig
from pydantic import BaseModel


class TestServiceConfigContract:
    """Declared API of the ``ServiceConfig`` entity."""

    def test_service_config_is_importable_from_config_facade(self):
        """``ServiceConfig`` is re-exported by the ``goga_tool_pybuggy.sandbox.config`` facade."""
        assert ServiceConfig is not None

    def test_service_config_is_a_pydantic_model(self):
        """``ServiceConfig`` subclasses ``pydantic.BaseModel``."""
        assert issubclass(ServiceConfig, BaseModel)

    def test_service_config_constructor_is_kw_only(self):
        """All constructor parameters are keyword-only (no positional args)."""
        signature = inspect.signature(ServiceConfig)

        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_service_config_declares_the_contract_fields(self):
        """The model declares the ``image``, ``env``, ``port`` and ``health`` fields only."""
        assert set(ServiceConfig.model_fields) == {"image", "env", "port", "health"}

    def test_service_config_properties_return_declared_types(self):
        """Construction with sample data exposes the declared property types."""
        service = ServiceConfig(image="my-service:latest", env={"A": "b"}, port=8080, health="/health")

        assert isinstance(service.image, str)
        assert isinstance(service.env, dict)
        assert all(isinstance(key, str) and isinstance(value, str) for key, value in service.env.items())
        assert isinstance(service.port, int)
        assert isinstance(service.health, str)

    def test_service_config_health_accepts_none(self):
        """``health`` carries the explicit absence of a health path as ``None``."""
        service = ServiceConfig(image="my-service:latest", env={}, port=8080, health=None)

        assert service.health is None


class TestServiceConfigLogic:
    """Construction and behavior of ``ServiceConfig``."""

    def test_service_config_positional_construction_raises_type_error(self):
        """Positional construction is rejected — keyword arguments only."""
        with pytest.raises(TypeError):
            ServiceConfig("my-service:latest", {}, 8080, None)  # type: ignore[misc]

    def test_service_config_env_defaults_to_empty_dict(self):
        """``env`` defaults to an empty mapping."""
        service = ServiceConfig(image="my-service:latest", port=8080)

        assert service.env == {}

    def test_service_config_health_defaults_to_none(self):
        """``health`` defaults to ``None`` (port readiness only)."""
        service = ServiceConfig(image="my-service:latest", port=8080)

        assert service.health is None
