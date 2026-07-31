"""Tests for ``pybuggy.api.asserts.field.AssertField``.

Covers the field-level assert entry produced by ``Expected.__call__``: dotted and
jsonpath search, drill-down (``index``/``hook``), the ``data_key``/``error_key``
root prefix, ``in_array`` element-wise mode, a representative set of matchcrest
matchers, the ``value`` property, and the ``raise_exc``/``not_raise_exc`` context
managers. A ``FakeResponse`` stands in for ``resq.http.Response``.
"""

from __future__ import annotations

from datetime import date

import pytest
from pybuggy.api import Expected
from pybuggy.api.asserts.config import AssertConfig

from tests.api.conftest import FakeResponse

_DEFAULT_BODY = {
    "data": {"items": [1, 2, 3], "name": "abc", "tags": ["xx", "yy"], "obj": {"k": "v"}},
    "error": None,
}


def _expected(
    body: dict | None = None,
    *,
    data_key: str = "data",
    error_key: str = "error",
    is_negative: bool = False,
) -> Expected:
    """Build an ``Expected`` over a canned body with data/error keys."""
    body = _DEFAULT_BODY if body is None else body

    return Expected(
        FakeResponse(status_code=200, body=body),
        AssertConfig(status=200, data_key=data_key, error_key=error_key),
        is_negative=is_negative,
    )


class TestFieldSearchModes:
    """Dotted path vs jsonpath vs absolute (no data_key)."""

    def test_dotted_path_relative_to_data_key(self) -> None:
        """A dotted search resolves under the data_key root."""
        _expected()("name").equal_to("abc")
        _expected()("items").has_length(3)

    def test_jsonpath_search(self) -> None:
        """A jsonpath expression resolves through jsonpath_ng."""
        _expected()("$.items[*]", in_array=True).equal_to(2, any=True)

    def test_absolute_path_without_data_key(self) -> None:
        """With no data_key, the search is absolute against the full body."""
        body = {"a": {"b": {"c": 5}}}
        expected = Expected(FakeResponse(body=body), AssertConfig(status=200))

        expected("a.b.c").equal_to(5)

    def test_missing_dotted_path_raises(self) -> None:
        """A missing dotted path raises AssertionError."""
        with pytest.raises(AssertionError):
            _expected()("missing.path").equal_to(1)

    def test_missing_jsonpath_raises(self) -> None:
        """A missing jsonpath raises AssertionError."""
        with pytest.raises(AssertionError):
            _expected()("$.nope").equal_to(1)


class TestFieldDrillDown:
    """``AssertField.__call__`` index/hook drill-down."""

    def test_index_drill_down(self) -> None:
        """``field(index=n)`` selects a list element."""
        _expected()("items")(index=0).equal_to(1)
        _expected()("items")(index=2).equal_to(3)

    def test_hook_applied(self) -> None:
        """A hook transforms the resolved value before asserting."""
        _expected()("name")(hook=lambda value: value.upper()).equal_to("ABC")

    def test_drill_returns_new_assert_field(self) -> None:
        """Drilling returns a distinct AssertField (immutable chain)."""
        from pybuggy.api import AssertField

        base = _expected()("items")
        drilled = base(index=0)

        assert isinstance(drilled, AssertField)
        assert drilled is not base


class TestFieldRootPrefix:
    """``data_key``/``error_key`` root selection by path polarity."""

    def test_positive_roots_at_data_key(self) -> None:
        """Positive path searches under data_key."""
        _expected()("obj.k").equal_to("v")

    def test_negative_roots_at_error_key(self) -> None:
        """Negative path searches under error_key."""
        body = {"data": None, "error": {"msg": "bad", "code": 42}}
        expected = Expected(
            FakeResponse(body=body),
            AssertConfig(status=400, data_key="data", error_key="error"),
            is_negative=True,
        )

        expected("msg").equal_to("bad")
        expected("code").equal_to(42)


class TestFieldMatchers:
    """Representative matchcrest matchers through AssertField."""

    def test_equal_to_and_not_equal_to(self) -> None:
        """``equal_to`` passes/fails; ``not_equal_to`` inverts."""
        _expected()("name").equal_to("abc")
        with pytest.raises(AssertionError):
            _expected()("name").equal_to("zzz")
        _expected()("name").not_equal_to("zzz")

    def test_greater_and_lesser(self) -> None:
        """Numeric comparisons with ``or_equal``."""
        _expected()("items")(index=0).lesser_than(2)
        _expected()("items")(index=0).lesser_than(1, or_equal=True)
        _expected()("items")(index=2).greater_than(2)
        _expected()("items")(index=2).greater_than(3, or_equal=True)

    def test_starts_ends_contains(self) -> None:
        """String prefix/suffix/substring matchers."""
        _expected()("name").startswith("ab")
        _expected()("name").endswith("bc")
        _expected()("name").contains("b")

    def test_match_regex(self) -> None:
        """A compiled regex matches the value."""
        _expected()("name").match_regex(r"^a.c$")
        with pytest.raises(AssertionError):
            _expected()("name").match_regex(r"^z")

    def test_contains_dict(self) -> None:
        """``contains_dict`` checks key/value membership in a dict field."""
        _expected()("obj").contains_dict({"k": "v"})
        with pytest.raises(AssertionError):
            _expected()("obj").contains_dict({"k": "other"})

    def test_is_in_and_is_not_in(self) -> None:
        """Membership of the value in a collection."""
        _expected()("name").is_in(["abc", "zzz"])
        _expected()("name").is_not_in(["zzz"])

    def test_empty_and_not_empty(self) -> None:
        """``empty``/``not_empty`` on falsy/truthy values."""
        body = {"data": {"blank": "", "filled": "x"}, "error": None}
        Expected(FakeResponse(body=body), AssertConfig(status=200, data_key="data", error_key="error"))("blank").empty()
        _expected()("name").not_empty()


class TestFieldInArray:
    """``in_array`` element-wise mode with ``any``."""

    def test_in_array_any_matches_an_element(self) -> None:
        """``equal_to`` with ``in_array``+``any`` matches one list element."""
        _expected()("items", in_array=True).equal_to(2, any=True)

    def test_in_array_any_no_match_raises(self) -> None:
        """No element matching raises."""
        with pytest.raises(AssertionError):
            _expected()("items", in_array=True).equal_to(99, any=True)

    def test_in_array_string_contains(self) -> None:
        """``contains`` over a list of strings checks each element."""
        _expected()("tags", in_array=True).contains("x", any=True)


class TestFieldValueAndDate:
    """``value`` property and date matchers."""

    def test_value_property_returns_resolved(self) -> None:
        """``value`` exposes the resolved field value without asserting."""
        assert _expected()("name").value == "abc"

    def test_has_date(self) -> None:
        """``has_date`` compares dates by timestamp."""
        body = {"data": {"d": date(2024, 1, 15)}, "error": None}
        expected = Expected(FakeResponse(body=body), AssertConfig(status=200, data_key="data", error_key="error"))

        expected("d").has_date(date(2024, 1, 15))
        expected("d").has_date_greater(date(2024, 1, 1))
        expected("d").has_date_lesser(date(2024, 2, 1))


class TestFieldExceptionMatchers:
    """``raise_exc``/``not_raise_exc`` context managers."""

    def test_not_raise_exc_when_value_resolves(self) -> None:
        """Accessing a resolvable value raises nothing → not_raise_exc passes."""
        with _expected()("name").not_raise_exc() as value:
            assert value == "abc"

    def test_raise_exc_propagates_unexpected(self) -> None:
        """``raise_exc`` fails when no exception is raised."""
        with pytest.raises(AssertionError), _expected()("name").raise_exc(KeyError):
            pass  # value resolves, nothing raised
