"""Contract and logic tests for the ``GitEntry`` config entity."""

import inspect

import pytest
from goga_tool_pybuggy.config import GitEntry
from pydantic import BaseModel, ValidationError


class TestGitEntryContract:
    """Declared API of the ``GitEntry`` entity."""

    def test_git_entry_is_importable_from_config_facade(self):
        """``GitEntry`` is re-exported by the ``goga_tool_pybuggy.config`` facade."""
        assert GitEntry is not None

    def test_git_entry_is_a_pydantic_model(self):
        """``GitEntry`` subclasses ``pydantic.BaseModel``."""
        assert issubclass(GitEntry, BaseModel)

    def test_git_entry_constructor_fields_are_url_location_and_ref(self):
        """The model declares the ``url``, ``location`` and ``ref`` fields only."""
        fields = set(GitEntry.model_fields)

        assert fields == {"url", "location", "ref"}

    def test_git_entry_constructor_is_kw_only(self):
        """All constructor parameters are keyword-only (no positional args)."""
        signature = inspect.signature(GitEntry)

        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_git_entry_signature_has_url_location_and_ref_parameters(self):
        """The constructor signature exposes ``url``, ``location`` and ``ref``."""
        signature = inspect.signature(GitEntry)

        assert set(signature.parameters) == {"url", "location", "ref"}


class TestGitEntryLogic:
    """Construction and behavior of ``GitEntry``."""

    def test_git_entry_returns_declared_field_values(self):
        """Constructing ``GitEntry`` stores the provided field values."""
        entry = GitEntry(url="https://example.com/repo.git", location="specs/client.yaml")

        assert entry.url == "https://example.com/repo.git"
        assert entry.location == "specs/client.yaml"

    def test_git_entry_rejects_positional_arguments(self):
        """Positional construction is forbidden by ``kw_only=True``."""
        with pytest.raises(TypeError):
            GitEntry("https://example.com/repo.git", "specs/client.yaml")

    def test_git_entry_requires_url_and_location(self):
        """Omitting a required field raises a validation error."""
        with pytest.raises(ValidationError):
            GitEntry(url="https://example.com/repo.git")


class TestGitEntryRef:
    """``ref`` field behavior of the ``GitEntry`` entity."""

    def test_ref_defaults_to_none_when_omitted(self):
        """``ref`` is optional and defaults to ``None`` (remote default branch)."""
        entry = GitEntry(url="https://example.com/repo.git", location="specs/client.yaml")

        assert entry.ref is None

    def test_ref_stores_branch_or_tag_value(self):
        """Constructing with ``ref`` stores the provided ref value."""
        entry = GitEntry(url="https://example.com/repo.git", location="specs/client.yaml", ref="v1")

        assert entry.ref == "v1"
