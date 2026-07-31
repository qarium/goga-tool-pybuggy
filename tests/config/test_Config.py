"""Contract and logic tests for the ``Config`` config entity."""

import inspect

import pytest
from goga_tool_pybuggy.config import Config, SpecEntry
from pydantic import BaseModel, ValidationError


class TestConfigContract:
    """Declared API of the ``Config`` entity."""

    def test_config_is_importable_from_config_facade(self):
        """``Config`` is re-exported by the ``goga_tool_pybuggy.config`` facade."""
        assert Config is not None

    def test_config_is_a_pydantic_model(self):
        """``Config`` subclasses ``pydantic.BaseModel``."""
        assert issubclass(Config, BaseModel)

    def test_config_constructor_has_specs_field_only(self):
        """The model declares the ``specs`` field only."""
        fields = set(Config.model_fields)

        assert fields == {"specs"}

    def test_config_constructor_is_kw_only(self):
        """All constructor parameters are keyword-only (no positional args)."""
        signature = inspect.signature(Config)

        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_config_signature_has_specs_parameter(self):
        """The constructor signature exposes ``specs``."""
        signature = inspect.signature(Config)

        assert set(signature.parameters) == {"specs"}

    def test_config_specs_is_required(self):
        """``specs`` is a required field (config without specs is invalid)."""
        specs_field = Config.model_fields["specs"]

        assert specs_field.is_required() is True


class TestConfigLogic:
    """Construction and behavior of ``Config``."""

    def test_config_returns_declared_field_values(self):
        """Constructing ``Config`` stores the ``specs`` field value."""
        entry = SpecEntry(type="openapi", location="specs/client.yaml")
        config = Config(specs={"client": entry})

        assert "client" in config.specs
        assert config.specs["client"].location == "specs/client.yaml"

    def test_config_allows_empty_specs_dict(self):
        """An empty ``specs`` dict is allowed by type (required field, but empty dict is valid)."""
        config = Config(specs={})

        assert config.specs == {}

    def test_config_rejects_positional_arguments(self):
        """Positional construction is forbidden by ``kw_only=True``."""
        entry = SpecEntry(type="openapi", location="specs/client.yaml")
        with pytest.raises(TypeError):
            Config({"client": entry})

    def test_config_requires_specs_key(self):
        """Omitting the ``specs`` key raises a validation error."""
        with pytest.raises(ValidationError):
            Config()
