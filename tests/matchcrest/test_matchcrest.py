"""Smoke and re-export tests for the matchcrest composition facade."""

import pybuggy.matchcrest as facade
import pytest
from pybuggy.matchcrest import ValueIsEqualMatcher, assert_that
from pybuggy.matchcrest.matchers import __all__ as matchers_all


class TestFacade:
    """The root facade re-exports the full matcher API plus assert_that."""

    def test_assert_that_is_callable(self):
        """``assert_that`` is re-exported and callable."""
        assert callable(assert_that)

    def test_facade_reexports_every_matchers_type(self):
        """Every matchers-cell facade name is present in the root facade."""
        assert set(matchers_all) <= set(facade.__all__)

    def test_facade_adds_assert_that(self):
        """The root facade exposes ``assert_that`` on top of the matcher catalog."""
        assert "assert_that" in facade.__all__
        assert "assert_that" not in matchers_all

    def test_all_facade_names_are_attributes(self):
        """Every ``__all__`` entry is importable from the facade module."""
        for name in facade.__all__:
            assert hasattr(facade, name), f"{name} missing from facade"

    def test_assert_that_passes_on_match(self, ctx):
        """A matching assertion does not raise."""
        assert_that(ctx("admin"), ValueIsEqualMatcher("admin"))

    def test_assert_that_raises_on_mismatch(self, ctx):
        """A mismatching assertion raises AssertionError."""
        with pytest.raises(AssertionError):
            assert_that(ctx("user"), ValueIsEqualMatcher("admin"))
