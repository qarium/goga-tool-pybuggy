"""Contract and logic tests for the ``SpecEntry`` config entity."""

import inspect

import pytest
from pybuggy.config import GitEntry, SpecEntry
from pydantic import BaseModel, ValidationError


class TestSpecEntryContract:
    """Declared API of the ``SpecEntry`` entity."""

    def test_spec_entry_is_importable_from_config_facade(self):
        """``SpecEntry`` is re-exported by the ``pybuggy.config`` facade."""
        assert SpecEntry is not None

    def test_spec_entry_is_a_pydantic_model(self):
        """``SpecEntry`` subclasses ``pydantic.BaseModel``."""
        assert issubclass(SpecEntry, BaseModel)

    def test_spec_entry_constructor_fields_are_type_location_git(self):
        """The model declares the ``type``, ``location`` and ``git`` fields only."""
        fields = set(SpecEntry.model_fields)

        assert fields == {"type", "location", "git"}

    def test_spec_entry_constructor_is_kw_only(self):
        """All constructor parameters are keyword-only (no positional args)."""
        signature = inspect.signature(SpecEntry)

        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_spec_entry_signature_has_type_location_git_parameters(self):
        """The constructor signature exposes ``type``, ``location`` and ``git``."""
        signature = inspect.signature(SpecEntry)

        assert set(signature.parameters) == {"type", "location", "git"}

    def test_spec_entry_git_defaults_to_none(self):
        """``git`` is optional and defaults to ``None`` (local-only spec)."""
        git_field = SpecEntry.model_fields["git"]

        assert git_field.is_required() is False
        assert git_field.default is None


class TestSpecEntryLogic:
    """Construction and behavior of ``SpecEntry``."""

    def test_spec_entry_returns_declared_field_values_with_remote_source(self):
        """Constructing ``SpecEntry`` with a ``GitEntry`` stores all field values."""
        entry = SpecEntry(
            type="openapi",
            location="specs/client.yaml",
            git=GitEntry(url="https://example.com/repo.git", location="specs/client.yaml"),
        )

        assert entry.type == "openapi"
        assert entry.location == "specs/client.yaml"
        assert entry.git == GitEntry(url="https://example.com/repo.git", location="specs/client.yaml")

    def test_spec_entry_without_git_is_local_only(self):
        """Omitting ``git`` yields a local-only spec (``git is None``)."""
        entry = SpecEntry(type="swagger", location="specs/client.yaml")

        assert entry.git is None

    def test_spec_entry_rejects_unknown_type(self):
        """A ``type`` outside the declared literal is rejected by pydantic."""
        with pytest.raises(ValidationError):
            SpecEntry(type="raml", location="specs/client.yaml")

    def test_spec_entry_rejects_positional_arguments(self):
        """Positional construction is forbidden by ``kw_only=True``."""
        with pytest.raises(TypeError):
            SpecEntry("openapi", "specs/client.yaml")

    def test_spec_entry_requires_type_and_location(self):
        """Omitting a required field raises a validation error."""
        with pytest.raises(ValidationError):
            SpecEntry(type="openapi")
