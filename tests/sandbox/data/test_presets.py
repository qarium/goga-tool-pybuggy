"""Contract and logic tests for the ``services`` preset decorator."""

import inspect

import pytest
from goga_tool_pybuggy.sandbox.data import services


class TestServicesContract:
    """Declared API of the ``services`` routine."""

    def test_services_is_importable_from_data_facade(self):
        """``services`` is re-exported by the ``goga_tool_pybuggy.sandbox.data`` facade."""
        assert services is not None

    def test_services_declares_the_arbitrary_keyword_presets_signature(self):
        """The routine takes the single documented ``...presets`` arbitrary-keyword form."""
        parameters = inspect.signature(services).parameters

        assert list(parameters) == ["presets"]
        assert parameters["presets"].kind is inspect.Parameter.VAR_KEYWORD

    def test_services_returns_a_decorator_from_keyword_presets(self):
        """Calling with kind keywords returns a callable decorator."""
        decorator = services(postgresql={"db": []})

        assert callable(decorator)

    def test_services_decorator_accepts_a_test_item(self):
        """The returned decorator applies to a test function and returns the marked item."""
        decorator = services(vault={"secrets": []})

        def sample_test() -> int:
            return 42

        marked = decorator(sample_test)

        assert callable(marked)
        assert marked() == 42


class TestServicesLogic:
    """Decoration behavior of the ``services`` routine."""

    def test_presets_decorator_marks_test_and_executes_nothing(self):
        """Decoration attaches the ``pybuggy_services`` marker carrying the presets payload."""
        declarations = {"postgresql": {"db": [{"table": "customers", "rows": [{"id": 1}]}]}}

        @services(**declarations)
        def sample_test() -> int:
            return 42

        matching = [mark for mark in sample_test.pytestmark if mark.name == "pybuggy_services"]

        assert len(matching) == 1
        assert matching[0].kwargs["presets"]["postgresql"]["db"][0]["table"] == "customers"
        assert matching[0].kwargs["presets"] == declarations
        assert sample_test() == 42

    def test_services_rejects_unknown_kind_at_decoration(self):
        """A preset key outside the supported kinds fails at decoration naming the kind."""
        with pytest.raises(ValueError, match="redis"):
            services(redis={"x": []})

    def test_services_unknown_kind_error_lists_supported_kinds(self):
        """The decoration failure names every supported kind."""
        with pytest.raises(ValueError, match=r"postgresql.*kafka.*vault.*http"):
            services(grpc={"events": []})

    def test_services_rejects_kind_value_that_is_not_a_mapping(self):
        """A kind value that is not an ``instance name -> declaration list`` mapping fails."""
        with pytest.raises(ValueError, match=r"postgresql.*must map instance names"):
            services(postgresql="db")

    def test_services_rejects_instance_value_that_is_not_a_list(self):
        """An instance value that is not a declaration list fails at decoration."""
        with pytest.raises(ValueError, match=r"postgresql\.db.*must be a list"):
            services(postgresql={"db": "rows"})

    def test_services_rejects_declaration_that_is_not_a_mapping(self):
        """A declaration that is not a mapping fails at decoration."""
        with pytest.raises(ValueError, match=r"postgresql\.db.*must be a list"):
            services(postgresql={"db": ["oops"]})

    def test_services_accepts_conforming_reference_rows(self):
        """Grammar-conforming ``$ref`` / ``$lookup`` row values reach the marker unchanged."""
        declarations = {
            "postgresql": {"db": [{"table": "orders", "rows": [{"customer_id": {"$ref": "customers.0.id"}}]}]}
        }

        @services(**declarations)
        def sample_test() -> int:
            return 42

        mark = next(mark for mark in sample_test.pytestmark if mark.name == "pybuggy_services")

        assert mark.kwargs["presets"] == declarations

    def test_services_rejects_a_malformed_reference_at_decoration(self):
        """A malformed ``$ref`` in postgresql rows fails at decoration naming the location."""
        with pytest.raises(ValueError, match=r"services preset 'postgresql\.db' rows\[0\]\.customer_id"):
            services(postgresql={"db": [{"table": "orders", "rows": [{"customer_id": {"$ref": "customers.0"}}]}]})

    def test_services_rejects_a_malformed_lookup_at_decoration(self):
        """A malformed ``$lookup`` in postgresql rows fails at decoration naming the location."""
        with pytest.raises(ValueError, match=r"services preset 'postgresql\.db' rows\[0\]\.customer_id"):
            services(postgresql={"db": [{"table": "orders", "rows": [{"customer_id": {"$lookup": {"where": {}}}}]}]})

    def test_services_skips_row_validation_for_other_kinds(self):
        """Non-postgresql declarations never run the row grammar — their shapes are kind-owned."""
        declarations = {"vault": {"secrets": [{"path": "payment/api-key", "data": {"$ref": "anything"}}]}}

        @services(**declarations)
        def sample_test() -> int:
            return 42

        mark = next(mark for mark in sample_test.pytestmark if mark.name == "pybuggy_services")

        assert mark.kwargs["presets"] == declarations

    def test_services_preserves_declaration_order_within_one_instance(self):
        """Declarations under one instance keep the author's list order in the payload."""
        declarations = [{"table": "customers", "rows": []}, {"table": "orders", "rows": []}]

        @services(postgresql={"db": declarations})
        def sample_test() -> int:
            return 0

        mark = sample_test.pytestmark[0]

        assert mark.kwargs["presets"]["postgresql"]["db"] == declarations

    def test_services_allows_several_kinds_in_one_decorator(self):
        """Every supported kind may appear once in one decorator call."""
        declarations = {
            "postgresql": {"db": []},
            "kafka": {"events": []},
            "vault": {"secrets": []},
            "http": {"payments": []},
        }

        @services(**declarations)
        def sample_test() -> int:
            return 0

        mark = sample_test.pytestmark[0]

        assert mark.kwargs["presets"] == declarations

    def test_services_with_no_presets_marks_with_empty_payload(self):
        """An empty decorator call is valid — the marker carries an empty presets mapping."""

        @services()
        def sample_test() -> int:
            return 0

        mark = sample_test.pytestmark[0]

        assert mark.name == "pybuggy_services"
        assert mark.kwargs["presets"] == {}
