"""Contract and logic tests for the ``SandboxConfig`` entity."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox.config import InstanceConfig, SandboxConfig, ServiceConfig, StartupData
from pydantic import BaseModel


class TestSandboxConfigContract:
    """Declared API of the ``SandboxConfig`` entity."""

    def test_sandbox_config_is_importable_from_config_facade(self):
        """``SandboxConfig`` is re-exported by the ``goga_tool_pybuggy.sandbox.config`` facade."""
        assert SandboxConfig is not None

    def test_sandbox_config_is_a_pydantic_model(self):
        """``SandboxConfig`` subclasses ``pydantic.BaseModel``."""
        assert issubclass(SandboxConfig, BaseModel)

    def test_sandbox_config_constructor_is_kw_only(self):
        """All constructor parameters are keyword-only (no positional args)."""
        signature = inspect.signature(SandboxConfig)

        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_sandbox_config_declares_the_contract_fields(self):
        """The model declares the ``service``, ``instances`` and ``data`` fields only."""
        assert set(SandboxConfig.model_fields) == {"service", "instances", "data"}

    def test_sandbox_config_properties_return_declared_types(self):
        """Construction with sample data exposes the declared property types."""
        service = ServiceConfig(image="my-service:latest", env={}, port=8080, health=None)
        config = SandboxConfig(
            service=service,
            instances={"db": InstanceConfig(name="db", kind="postgresql", image=None)},
            data=StartupData(postgres={"db": ["CREATE TABLE orders (id int)"]}),
        )

        assert isinstance(config.service, ServiceConfig)
        assert isinstance(config.instances, dict)
        assert all(
            isinstance(key, str) and isinstance(value, InstanceConfig) for key, value in config.instances.items()
        )
        assert isinstance(config.data, StartupData)


class TestSandboxConfigLogic:
    """Construction and behavior of ``SandboxConfig``."""

    def test_sandbox_config_positional_construction_raises_type_error(self):
        """Positional construction is rejected — keyword arguments only."""
        with pytest.raises(TypeError):
            SandboxConfig(ServiceConfig(image="x", port=1), {}, StartupData())  # type: ignore[misc]

    def test_sandbox_config_service_entry_is_required(self):
        """The service entry has no default — it is required."""
        service_field = SandboxConfig.model_fields["service"]

        assert service_field.is_required() is True

    def test_sandbox_config_instances_default_to_empty_dict(self):
        """``instances`` defaults to an empty mapping."""
        config = SandboxConfig(service=ServiceConfig(image="my-service:latest", port=8080))

        assert config.instances == {}

    def test_sandbox_config_data_defaults_to_empty_startup_data(self):
        """``data`` defaults to an empty startup data layer."""
        config = SandboxConfig(service=ServiceConfig(image="my-service:latest", port=8080))

        assert isinstance(config.data, StartupData)
        assert config.data == StartupData()

    def test_sandbox_config_allows_several_instances_of_one_kind(self):
        """Several dependency instances of one kind coexist under distinct names."""
        config = SandboxConfig(
            service=ServiceConfig(image="my-service:latest", port=8080),
            instances={
                "db": InstanceConfig(name="db", kind="postgresql", image=None),
                "audit": InstanceConfig(name="audit", kind="postgresql", image="postgres:17-alpine"),
            },
        )

        assert set(config.instances) == {"db", "audit"}
        assert config.instances["db"].kind == "postgresql"
        assert config.instances["audit"].kind == "postgresql"
        assert config.instances["audit"].image == "postgres:17-alpine"
