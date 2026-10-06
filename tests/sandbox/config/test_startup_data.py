"""Contract and logic tests for the ``StartupData`` entity."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox.config import StartupData
from pydantic import BaseModel


class TestStartupDataContract:
    """Declared API of the ``StartupData`` entity."""

    def test_startup_data_is_importable_from_config_facade(self):
        """``StartupData`` is re-exported by the ``goga_tool_pybuggy.sandbox.config`` facade."""
        assert StartupData is not None

    def test_startup_data_is_a_pydantic_model(self):
        """``StartupData`` subclasses ``pydantic.BaseModel``."""
        assert issubclass(StartupData, BaseModel)

    def test_startup_data_constructor_is_kw_only(self):
        """All constructor parameters are keyword-only (no positional args)."""
        signature = inspect.signature(StartupData)

        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_startup_data_declares_the_four_sections(self):
        """The model declares the ``vault``, ``http``, ``kafka`` and ``postgres`` fields only."""
        assert set(StartupData.model_fields) == {"vault", "http", "kafka", "postgres"}

    def test_startup_data_sections_return_declared_types(self):
        """Construction with sample data exposes the declared section types."""
        data = StartupData(
            vault={"secrets": [{"path": "payment/api-key", "data": {"api_key": "k"}}]},
            http={"payments": [{"request": {"method": "GET", "url": "/x"}, "response": {"status": 200}}]},
            kafka={"events": "/tmp/asyncapi.yaml"},
            postgres={"db": ["CREATE TABLE orders (id int PRIMARY KEY)"]},
        )

        vault_section = data.vault["secrets"][0]

        assert isinstance(data.vault, dict)
        assert isinstance(vault_section, dict)
        assert isinstance(data.http, dict)
        assert isinstance(data.http["payments"][0], dict)
        assert isinstance(data.kafka, dict)
        assert data.kafka["events"] == "/tmp/asyncapi.yaml"
        assert isinstance(data.postgres, dict)
        assert data.postgres["db"][0] == "CREATE TABLE orders (id int PRIMARY KEY)"


class TestStartupDataLogic:
    """Construction and behavior of ``StartupData``."""

    def test_startup_data_positional_construction_raises_type_error(self):
        """Positional construction is rejected — keyword arguments only."""
        with pytest.raises(TypeError):
            StartupData({}, {}, {}, {})  # type: ignore[misc]

    def test_startup_data_sections_default_to_empty_dicts(self):
        """All four sections default to empty mappings."""
        data = StartupData()

        assert data.vault == {}
        assert data.http == {}
        assert data.kafka == {}
        assert data.postgres == {}

    def test_startup_data_field_order_is_vault_http_kafka_postgres(self):
        """The field order is the fixed section order: vault, http, kafka, postgres."""
        assert list(StartupData.model_fields) == ["vault", "http", "kafka", "postgres"]

    def test_startup_data_preserves_declaration_order_within_sections(self):
        """List semantics keep the declaration order inside every section."""
        data = StartupData(postgres={"db": ["CREATE TABLE a (id int)", "CREATE TABLE b (id int)"]})

        assert data.postgres["db"] == ["CREATE TABLE a (id int)", "CREATE TABLE b (id int)"]
