"""Contract and logic tests for the ``ServiceConfig`` entity."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox.config import ProbeConfig, ServiceConfig, TopicConfig
from pydantic import BaseModel, ValidationError


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
        """The model declares the ``name``, ``kind``, ``image``, ``topics`` and ``probe`` fields."""
        assert set(ServiceConfig.model_fields) == {"name", "kind", "image", "topics", "probe"}

    def test_service_config_properties_return_declared_types(self):
        """Construction with sample data exposes the declared property types."""
        service = ServiceConfig(
            name="events",
            kind="kafka",
            topics=[TopicConfig(name="orders.events", partitions=6)],
        )

        assert isinstance(service.name, str)
        assert isinstance(service.kind, str)
        assert service.image is None
        assert isinstance(service.topics, list)
        assert all(isinstance(topic, TopicConfig) for topic in service.topics)
        assert service.probe is None

    def test_service_config_accepts_an_image_override(self):
        """``image`` overrides the product-pinned default of the kind."""
        service = ServiceConfig(name="db", kind="postgresql", image="postgres:17-alpine")

        assert service.image == "postgres:17-alpine"


class TestServiceConfigLogic:
    """Construction and behavior of ``ServiceConfig``."""

    def test_service_config_positional_construction_raises_type_error(self):
        """Positional construction is rejected — keyword arguments only."""
        with pytest.raises(TypeError):
            ServiceConfig("db", "postgresql", None, [], None)  # type: ignore[misc]

    def test_service_config_image_defaults_to_none(self):
        """``image`` defaults to ``None`` (the product-pinned kind default)."""
        service = ServiceConfig(name="db", kind="postgresql")

        assert service.image is None

    def test_service_config_topics_default_to_empty_list(self):
        """``topics`` defaults to an empty list."""
        service = ServiceConfig(name="db", kind="postgresql")

        assert service.topics == []

    def test_service_config_probe_defaults_to_none(self):
        """``probe`` defaults to ``None`` — the default wait bounds apply."""
        service = ServiceConfig(name="db", kind="postgresql")

        assert service.probe is None

    def test_service_config_accepts_a_probe_without_path(self):
        """A service probe declares wait bounds only and constructs cleanly."""
        service = ServiceConfig(name="db", kind="postgresql", probe=ProbeConfig(timeout=45.0, interval=1.0))

        assert service.probe is not None
        assert service.probe.timeout == 45.0
        assert service.probe.interval == 1.0
        assert service.probe.path is None

    def test_service_config_rejects_a_probe_path(self):
        """The probe path belongs to the instance-under-test entry only (D1)."""
        with pytest.raises(ValidationError, match="the probe path is accepted only on the instance entry"):
            ServiceConfig(name="v", kind="vault", probe=ProbeConfig(path="/health"))

    def test_service_config_does_not_revalidate_kinds(self):
        """The kind vocabulary is loader-validated — the model carries the field type only."""
        service = ServiceConfig(name="x", kind="made-up-kind")

        assert service.kind == "made-up-kind"
