"""Contract and logic tests for the ``InstanceConfig`` entity."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox.config import InstanceConfig, ProbeConfig
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
        """The model declares the ``image``, ``env``, ``port`` and ``probe`` fields only."""
        assert set(InstanceConfig.model_fields) == {"image", "env", "port", "probe"}

    def test_instance_config_properties_return_declared_types(self):
        """Construction with sample data exposes the declared property types."""
        instance = InstanceConfig(image="my-service:latest", env={"A": "{{db.host}}"}, port=8080)

        assert isinstance(instance.image, str)
        assert isinstance(instance.env, dict)
        assert all(isinstance(key, str) and isinstance(value, str) for key, value in instance.env.items())
        assert isinstance(instance.port, int)
        assert instance.probe is None

    def test_instance_config_accepts_a_probe_with_path(self):
        """The probe path applies only here — the single readiness check with a configurable path."""
        instance = InstanceConfig(
            image="my-service:latest",
            env={},
            port=8080,
            probe=ProbeConfig(path="/healthz", timeout=45.0),
        )

        assert isinstance(instance.probe, ProbeConfig)
        assert instance.probe.path == "/healthz"
        assert instance.probe.timeout == 45.0


class TestInstanceConfigLogic:
    """Construction and behavior of ``InstanceConfig``."""

    def test_instance_config_positional_construction_raises_type_error(self):
        """Positional construction is rejected — keyword arguments only."""
        with pytest.raises(TypeError):
            InstanceConfig("my-service:latest", {}, 8080, None)  # type: ignore[misc]

    def test_instance_config_env_defaults_to_empty_dict(self):
        """``env`` defaults to an empty mapping."""
        instance = InstanceConfig(image="my-service:latest", port=8080)

        assert instance.env == {}

    def test_instance_config_probe_defaults_to_none(self):
        """``probe`` defaults to ``None`` — the default wait: port readiness, default bounds."""
        instance = InstanceConfig(image="my-service:latest", port=8080)

        assert instance.probe is None

    def test_instance_config_probe_accepts_none_explicitly(self):
        """``probe`` carries the explicit absence of a readiness declaration as ``None``."""
        instance = InstanceConfig(image="my-service:latest", port=8080, probe=None)

        assert instance.probe is None

    def test_instance_config_probe_without_path_keeps_port_readiness(self):
        """A path-free probe declares wait bounds only — port readiness stays."""
        instance = InstanceConfig(image="my-service:latest", port=8080, probe=ProbeConfig(timeout=10.0))

        assert instance.probe is not None
        assert instance.probe.path is None
        assert instance.probe.timeout == 10.0
