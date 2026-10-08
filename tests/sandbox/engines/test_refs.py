"""Contract and logic tests for the ``refs`` grammar entity."""

import pytest
from goga_tool_pybuggy.sandbox.engines import refs as refs_module
from goga_tool_pybuggy.sandbox.engines import validate_insert_rows


class TestRefsContract:
    """Declared API of the ``refs`` grammar module."""

    def test_validate_insert_rows_is_importable_from_engines_facade(self):
        """``validate_insert_rows`` is re-exported by the engines facade."""
        assert validate_insert_rows is refs_module.validate_insert_rows

    def test_reference_keys_carry_the_dollar_prefix(self):
        """The reserved reference keys are ``$ref`` and ``$lookup``."""
        assert refs_module.REF_KEY == "$ref"
        assert refs_module.LOOKUP_KEY == "$lookup"


class TestIsReference:
    """Reference recognition of single row values."""

    def test_ref_dict_is_a_reference(self):
        """A dict carrying ``$ref`` is recognized as a reference."""
        assert refs_module.is_reference({"$ref": "customers.0.id"})

    def test_lookup_dict_is_a_reference(self):
        """A dict carrying ``$lookup`` is recognized as a reference."""
        assert refs_module.is_reference({"$lookup": {"table": "customers", "where": {"id": 1}}})

    def test_plain_dict_column_data_is_not_a_reference(self):
        """A dict carrying neither reserved key stays plain column data."""
        assert not refs_module.is_reference({"json": {"$ref": "literal"}})

    def test_scalars_and_collections_are_not_references(self):
        """Every non-dict value passes recognition untouched."""
        assert not refs_module.is_reference("customers.0.id")
        assert not refs_module.is_reference(7)
        assert not refs_module.is_reference([1, 2])


class TestParseRefAddress:
    """Address splitting of the ``table.index.column`` shape."""

    def test_address_splits_into_table_index_column(self):
        """A well-formed address splits into its three parts."""
        assert refs_module.parse_ref_address("customers.0.id") == ("customers", 0, "id")

    @pytest.mark.parametrize(
        "address",
        ["customers.0", "customers.0.id.extra", "customers.first.id", ".0.id", "customers..id", ""],
    )
    def test_malformed_address_fails_naming_the_shape(self, address: str):
        """An address outside ``table.index.column`` fails naming the expected shape."""
        with pytest.raises(ValueError, match=r"must match 'table\.index\.column'"):
            refs_module.parse_ref_address(address)


class TestValidateInsertRows:
    """Declaration-time grammar validation of insert rows."""

    def test_plain_rows_pass_through(self):
        """Rows without references validate — nothing to check beyond the shape."""
        refs_module.validate_insert_rows([{"id": 1, "name": "Ann"}], context="table 'orders'")

    def test_plain_dict_and_list_column_values_pass_through(self):
        """Json-like column values carry no reference grammar inside."""
        refs_module.validate_insert_rows(
            [{"data": {"inner": {"$ref": "literal"}}, "tags": [1, 2]}], context="table 'orders'"
        )

    def test_well_formed_ref_and_lookup_pass(self):
        """Grammar-conforming ``$ref`` and ``$lookup`` values validate."""
        refs_module.validate_insert_rows(
            [
                {"customer_id": {"$ref": "customers.0.id"}},
                {"customer_id": {"$lookup": {"table": "customers", "where": {"email": "a@x.io"}}}},
                {"customer_id": {"$lookup": {"table": "c", "where": {"email": "a"}, "column": "uid"}}},
            ],
            context="table 'orders'",
        )

    def test_non_list_rows_fail(self):
        """Rows must be a list."""
        with pytest.raises(ValueError, match="table 'orders': rows must be a list of mappings"):
            refs_module.validate_insert_rows({"id": 1}, context="table 'orders'")

    def test_non_mapping_row_fails(self):
        """Every row must be a mapping."""
        with pytest.raises(ValueError, match=r"table 'orders' rows\[1\] must be a mapping"):
            refs_module.validate_insert_rows([{"id": 1}, "nope"], context="table 'orders'")

    @pytest.mark.parametrize(
        "value",
        [
            {"$ref": "customers.0"},
            {"$ref": ""},
            {"$ref": 7},
            {"$ref": "customers.0.id", "extra": 1},
            {"$ref": "customers.0.id", "$lookup": {"table": "t", "where": {"a": 1}}},
        ],
    )
    def test_malformed_ref_fails_with_the_location(self, value: object):
        """A malformed ``$ref`` fails naming the declaration location."""
        with pytest.raises(ValueError, match=r"table 'orders' rows\[0\]\.customer_id"):
            refs_module.validate_insert_rows([{"customer_id": value}], context="table 'orders'")

    @pytest.mark.parametrize(
        "value",
        [
            {"$lookup": {"where": {"a": 1}}},
            {"$lookup": {"table": "t"}},
            {"$lookup": {"table": "t", "where": {}}},
            {"$lookup": {"table": "t", "where": {"a": [1]}}},
            {"$lookup": {"table": "t", "where": {"a": {"b": 1}}}},
            {"$lookup": {"table": "t", "where": {"a": 1}, "column": ""}},
            {"$lookup": {"table": "t", "where": {"a": 1}, "extra": 2}},
            {"$lookup": "customers"},
            {"$lookup": {"table": "t", "where": {"a": 1}, "extra": 1, "$ref": "t.0.id"}},
        ],
    )
    def test_malformed_lookup_fails_with_the_location(self, value: object):
        """A malformed ``$lookup`` fails naming the declaration location."""
        with pytest.raises(ValueError, match=r"table 'orders' rows\[0\]\.customer_id"):
            refs_module.validate_insert_rows([{"customer_id": value}], context="table 'orders'")

    def test_the_row_position_reaches_the_error_location(self):
        """The failing row's position names the exact location."""
        with pytest.raises(ValueError, match=r"table 'orders' rows\[2\]\.customer_id"):
            refs_module.validate_insert_rows(
                [{"id": 1}, {"id": 2}, {"customer_id": {"$ref": "broken"}}],
                context="table 'orders'",
            )
