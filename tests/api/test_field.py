"""Tests for ``goga_tool_pybuggy.api.asserts.field.AssertField``.

Covers the field-level assert entry produced by ``Expect.__call__``: dotted and
jsonpath search against the body root, drill-down (``index``/``hook``),
``in_array`` element-wise mode, a representative set of matchcrest matchers,
the ``value`` property, and the ``raise_exc``/``not_raise_exc`` context
managers. A ``FakeResponse`` stands in for ``resq.http.Response``.
"""

from __future__ import annotations

from datetime import date

import pytest
from goga_tool_pybuggy.api import Expect
from goga_tool_pybuggy.api.asserts.config import AssertConfig

from tests.api.conftest import FakeResponse

_DEFAULT_BODY = {
    "data": {"items": [1, 2, 3], "name": "abc", "tags": ["xx", "yy"], "obj": {"k": "v"}},
    "error": None,
}


def _expect(body: dict | None = None, *, is_negative: bool = False) -> Expect:
    """Build an ``Expect`` over a canned body (paths resolve from the root)."""
    body = _DEFAULT_BODY if body is None else body

    return Expect(
        FakeResponse(status_code=200, body=body),
        AssertConfig(expected_status=200),
        is_negative=is_negative,
    )


class TestFieldSearchModes:
    """Dotted path vs jsonpath, both against the body root."""

    def test_dotted_path_resolves_from_root(self) -> None:
        """A dotted search includes the envelope key and resolves from the root."""
        _expect()("data.name").equal_to("abc")
        _expect()("data.items").has_length(3)

    def test_jsonpath_search(self) -> None:
        """A jsonpath expression resolves through jsonpath_ng."""
        _expect()("$.data.items[*]", in_array=True).equal_to(2, any=True)

    def test_no_search_targets_whole_body(self) -> None:
        """No search targets the whole body from the root."""
        body = {"data": {"items": [1, 2, 3]}}

        _expect(body)().contains_dict({"data": {"items": [1, 2, 3]}})

    def test_missing_dotted_path_raises(self) -> None:
        """A missing dotted path raises AssertionError."""
        with pytest.raises(AssertionError):
            _expect()("missing.path").equal_to(1)

    def test_missing_jsonpath_raises(self) -> None:
        """A missing jsonpath raises AssertionError."""
        with pytest.raises(AssertionError):
            _expect()("$.nope").equal_to(1)


class TestFieldDrillDown:
    """``AssertField.__call__`` index/hook drill-down."""

    def test_index_drill_down(self) -> None:
        """``field(index=n)`` selects a list element."""
        _expect()("data.items")(index=0).equal_to(1)
        _expect()("data.items")(index=2).equal_to(3)

    def test_hook_applied(self) -> None:
        """A hook transforms the resolved value before asserting."""
        _expect()("data.name")(hook=lambda value: value.upper()).equal_to("ABC")

    def test_drill_returns_new_assert_field(self) -> None:
        """Drilling returns a distinct AssertField and leaves the parent field intact."""
        from goga_tool_pybuggy.api import AssertField

        base = _expect()("data.items")
        drilled = base(index=0)

        assert isinstance(drilled, AssertField)
        assert drilled is not base
        assert base.value == [1, 2, 3]
        base.has_length(3)
        assert drilled.value == 1


class TestFieldRootIsBodyRoot:
    """Path polarity does not change the root — it is always the body root."""

    def test_negative_path_uses_same_root(self) -> None:
        """The negative path resolves the same root as the positive one."""
        body = {"data": None, "error": {"msg": "bad", "code": 42}}
        expect = _expect(body, is_negative=True)

        expect("error.msg").equal_to("bad")
        expect("error.code").equal_to(42)


class TestFieldMatchers:
    """Representative matchcrest matchers through AssertField."""

    def test_equal_to_and_not_equal_to(self) -> None:
        """``equal_to`` passes/fails; ``not_equal_to`` inverts."""
        _expect()("data.name").equal_to("abc")
        with pytest.raises(AssertionError):
            _expect()("data.name").equal_to("zzz")
        _expect()("data.name").not_equal_to("zzz")

    def test_greater_and_lesser(self) -> None:
        """Numeric comparisons with ``or_equal``."""
        _expect()("data.items")(index=0).lesser_than(2)
        _expect()("data.items")(index=0).lesser_than(1, or_equal=True)
        _expect()("data.items")(index=2).greater_than(2)
        _expect()("data.items")(index=2).greater_than(3, or_equal=True)

    def test_starts_ends_contains(self) -> None:
        """String prefix/suffix/substring matchers."""
        _expect()("data.name").startswith("ab")
        _expect()("data.name").endswith("bc")
        _expect()("data.name").contains("b")

    def test_match_regex(self) -> None:
        """A compiled regex matches the value."""
        _expect()("data.name").match_regex(r"^a.c$")
        with pytest.raises(AssertionError):
            _expect()("data.name").match_regex(r"^z")

    def test_contains_dict(self) -> None:
        """``contains_dict`` checks key/value membership in a dict field."""
        _expect()("data.obj").contains_dict({"k": "v"})
        with pytest.raises(AssertionError):
            _expect()("data.obj").contains_dict({"k": "other"})

    def test_is_in_and_is_not_in(self) -> None:
        """Membership of the value in a collection."""
        _expect()("data.name").is_in(["abc", "zzz"])
        _expect()("data.name").is_not_in(["zzz"])

    def test_is_intersect(self) -> None:
        """``is_intersect`` passes when the field shares an element with ``value``."""
        _expect()("data.tags").is_intersect({"xx", "zz"})
        with pytest.raises(AssertionError):
            _expect()("data.tags").is_intersect({"zz"})

    def test_is_intersect_in_array(self) -> None:
        """``is_intersect`` element-wise over a list of lists with ``any``."""
        body = {"data": {"rows": [[1, 2], [2, 3]]}, "error": None}
        expect = Expect(FakeResponse(status_code=200, body=body), AssertConfig(expected_status=200))

        expect("data.rows", in_array=True).is_intersect({2}, any=True)
        expect("data.rows", in_array=True).is_intersect({2})
        with pytest.raises(AssertionError):
            expect("data.rows", in_array=True).is_intersect({9}, any=True)

    def test_empty_and_not_empty(self) -> None:
        """``empty``/``not_empty`` on falsy/truthy values."""
        body = {"data": {"blank": "", "filled": "x"}, "error": None}
        Expect(FakeResponse(body=body), AssertConfig(expected_status=200))("data.blank").empty()
        _expect()("data.name").not_empty()


class TestFieldInArray:
    """``in_array`` element-wise mode with ``any``."""

    def test_in_array_any_matches_an_element(self) -> None:
        """``equal_to`` with ``in_array``+``any`` matches one list element."""
        _expect()("data.items", in_array=True).equal_to(2, any=True)

    def test_in_array_any_no_match_raises(self) -> None:
        """No element matching raises."""
        with pytest.raises(AssertionError):
            _expect()("data.items", in_array=True).equal_to(99, any=True)

    def test_in_array_string_contains(self) -> None:
        """``contains`` over a list of strings checks each element."""
        _expect()("data.tags", in_array=True).contains("x", any=True)


class TestFieldValueAndDate:
    """``value`` property and date matchers."""

    def test_value_property_returns_resolved(self) -> None:
        """``value`` exposes the resolved field value without asserting."""
        assert _expect()("data.name").value == "abc"

    def test_has_date(self) -> None:
        """``has_date`` compares dates by timestamp."""
        body = {"data": {"d": date(2024, 1, 15)}, "error": None}
        expect = Expect(FakeResponse(body=body), AssertConfig(expected_status=200))

        expect("data.d").has_date(date(2024, 1, 15))
        expect("data.d").has_date_greater(date(2024, 1, 1))
        expect("data.d").has_date_lesser(date(2024, 2, 1))


class TestFieldExceptionMatchers:
    """``raise_exc``/``not_raise_exc`` context managers."""

    def test_not_raise_exc_when_value_resolves(self) -> None:
        """Accessing a resolvable value raises nothing → not_raise_exc passes."""
        with _expect()("data.name").not_raise_exc() as value:
            assert value == "abc"

    def test_raise_exc_propagates_unexpected(self) -> None:
        """``raise_exc`` fails when no exception is raised."""
        with pytest.raises(AssertionError), _expect()("data.name").raise_exc(KeyError):
            pass  # value resolves, nothing raised
