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
        """The model declares the ``instance``, ``services`` and ``data`` fields only."""
        assert set(SandboxConfig.model_fields) == {"instance", "services", "data"}

    def test_sandbox_config_properties_return_declared_types(self):
        """Construction with sample data exposes the declared property types."""
        config = SandboxConfig(
            instance=InstanceConfig(image="my-service:latest", env={}, port=8080),
            services={"db": ServiceConfig(name="db", kind="postgresql", image=None)},
            data=StartupData(postgres={"db": ["CREATE TABLE orders (id int)"]}),
        )

        assert isinstance(config.instance, InstanceConfig)
        assert isinstance(config.services, dict)
        assert all(isinstance(key, str) and isinstance(value, ServiceConfig) for key, value in config.services.items())
        assert isinstance(config.data, StartupData)


class TestSandboxConfigLogic:
    """Construction and behavior of ``SandboxConfig``."""

    def test_sandbox_config_positional_construction_raises_type_error(self):
        """Positional construction is rejected — keyword arguments only."""
        with pytest.raises(TypeError):
            SandboxConfig(InstanceConfig(image="x", port=1), {}, StartupData())  # type: ignore[misc]

    def test_sandbox_config_instance_entry_is_required(self):
        """The instance entry has no default — it is required."""
        instance_field = SandboxConfig.model_fields["instance"]

        assert instance_field.is_required() is True

    def test_sandbox_config_services_default_to_empty_dict(self):
        """``services`` defaults to an empty mapping."""
        config = SandboxConfig(instance=InstanceConfig(image="my-service:latest", port=8080))

        assert config.services == {}

    def test_sandbox_config_data_defaults_to_empty_startup_data(self):
        """``data`` defaults to an empty startup data layer."""
        config = SandboxConfig(instance=InstanceConfig(image="my-service:latest", port=8080))

        assert isinstance(config.data, StartupData)
        assert config.data == StartupData()

    def test_sandbox_config_allows_several_services_of_one_kind(self):
        """Several dependency services of one kind coexist under distinct names."""
        config = SandboxConfig(
            instance=InstanceConfig(image="my-service:latest", port=8080),
            services={
                "db": ServiceConfig(name="db", kind="postgresql", image=None),
                "audit": ServiceConfig(name="audit", kind="postgresql", image="postgres:17-alpine"),
            },
        )

        assert set(config.services) == {"db", "audit"}
        assert config.services["db"].kind == "postgresql"
        assert config.services["audit"].kind == "postgresql"
        assert config.services["audit"].image == "postgres:17-alpine"
