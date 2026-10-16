"""Contract and logic tests for the ``GitSource`` and ``MigrationsConfig`` entities."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox.config import GitSource, MigrationsConfig
from pydantic import BaseModel, ValidationError


class TestMigrationsModelsContract:
    """Declared API of the migrations declaration models."""

    def test_migrations_models_are_importable_from_config_facade(self):
        """``GitSource`` and ``MigrationsConfig`` are re-exported by the config facade."""
        assert GitSource is not None
        assert MigrationsConfig is not None

    def test_migrations_models_are_pydantic_models(self):
        """Both models subclass ``pydantic.BaseModel``."""
        assert issubclass(GitSource, BaseModel)
        assert issubclass(MigrationsConfig, BaseModel)

    def test_git_source_constructor_is_kw_only(self):
        """All ``GitSource`` constructor parameters are keyword-only (no positional args)."""
        signature = inspect.signature(GitSource)

        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_migrations_config_constructor_is_kw_only(self):
        """All ``MigrationsConfig`` constructor parameters are keyword-only (no positional args)."""
        signature = inspect.signature(MigrationsConfig)

        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_git_source_declares_the_contract_fields(self):
        """``GitSource`` declares the ``url`` and ``ref`` fields only."""
        assert set(GitSource.model_fields) == {"url", "ref"}

    def test_migrations_config_declares_the_contract_fields(self):
        """``MigrationsConfig`` declares the ``location`` and ``git`` fields only."""
        assert set(MigrationsConfig.model_fields) == {"location", "git"}

    def test_git_source_properties_return_declared_types(self):
        """Construction with sample data exposes the declared property types."""
        source = GitSource(url="https://gitlab.example/acme/service.git", ref="release-branch")

        assert isinstance(source.url, str)
        assert isinstance(source.ref, str)

    def test_migrations_config_properties_return_declared_types(self):
        """Construction with sample data exposes the declared property types."""
        declaration = MigrationsConfig(location="db/migrations", git=GitSource(url="https://h/r.git"))

        assert isinstance(declaration.location, str)
        assert isinstance(declaration.git, GitSource)


class TestMigrationsModelsLogic:
    """Construction and behavior of the migrations declaration models."""

    def test_git_source_positional_construction_raises_type_error(self):
        """Positional construction of ``GitSource`` is rejected — keyword arguments only."""
        with pytest.raises(TypeError):
            GitSource("https://h/r.git", "main")  # type: ignore[misc]

    def test_migrations_config_positional_construction_raises_type_error(self):
        """Positional construction of ``MigrationsConfig`` is rejected — keyword arguments only."""
        with pytest.raises(TypeError):
            MigrationsConfig("db/migrations", None)  # type: ignore[misc]

    def test_git_source_ref_defaults_to_none(self):
        """``ref`` defaults to ``None`` — the remote default branch is cloned."""
        source = GitSource(url="https://gitlab.example/acme/service.git")

        assert source.url == "https://gitlab.example/acme/service.git"
        assert source.ref is None

    def test_migrations_config_git_defaults_to_none(self):
        """``git`` defaults to ``None`` — the source stays local."""
        declaration = MigrationsConfig(location="db/migrations")

        assert declaration.location == "db/migrations"
        assert declaration.git is None

    def test_git_source_requires_url(self):
        """``url`` is required — a missing URL fails validation naming the field."""
        with pytest.raises(ValidationError, match="url"):
            GitSource()

    def test_migrations_config_requires_location(self):
        """``location`` is required — a missing location fails validation naming the field."""
        with pytest.raises(ValidationError, match="location"):
            MigrationsConfig()

    def test_migrations_models_reject_unknown_keys(self):
        """Unknown keys fail validation — the apply semantics are fixed (no journaling options)."""
        with pytest.raises(ValidationError, match="journal"):
            MigrationsConfig(location="db/migrations", journal=True)  # type: ignore[call-arg]

    def test_git_source_rejects_unknown_keys(self):
        """Unknown keys on ``GitSource`` fail validation naming the offending key."""
        with pytest.raises(ValidationError, match="token"):
            GitSource(url="https://h/r.git", token="secret")  # type: ignore[call-arg]

    def test_migrations_config_coerces_a_raw_git_mapping(self):
        """A raw ``git`` mapping coerces into the typed ``GitSource`` model."""
        declaration = MigrationsConfig(location="db/migrations", git={"url": "https://h/r.git", "ref": "rel"})

        assert isinstance(declaration.git, GitSource)
        assert declaration.git.url == "https://h/r.git"
        assert declaration.git.ref == "rel"
