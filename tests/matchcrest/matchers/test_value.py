"""Contract, branch, and boundary tests for the value matchers."""

import re
from datetime import date

import pytest
from pybuggy.matchcrest.matchers import (
    ValueContainsDictMatcher,
    ValueContainsMatcher,
    ValueDateEqualMatcher,
    ValueDateGreaterMatcher,
    ValueDateLesserMatcher,
    ValueEndsWithMatcher,
    ValueIsDisjointMatcher,
    ValueIsEmpty,
    ValueIsEqualMatcher,
    ValueIsGreaterMatcher,
    ValueIsInMatcher,
    ValueIsLesserMatcher,
    ValueIsNotEmpty,
    ValueIsNotEqualMatcher,
    ValueIsNotInMatcher,
    ValueIsSubsetMatcher,
    ValueIsUrlMatcher,
    ValueLengthEqualMatcher,
    ValueLengthGreaterMatcher,
    ValueLengthLesserMatcher,
    ValueNotContainsMatcher,
    ValueRegexMatcher,
    ValueStartsWithMatcher,
)


def _ok(matcher, ctx, value):
    """Build a context for ``value`` and assert the matcher passes it."""
    return matcher._matches(ctx(value)) is True


def _bad(matcher, ctx, value):
    """Build a context for ``value`` and assert the matcher fails it."""
    return matcher._matches(ctx(value)) is False


class TestBaseModifiers:
    """Internal base contract: any/in_array rule and iterable validation."""

    def test_any_without_in_array_raises(self):
        """``any`` may be combined with ``in_array`` only."""
        with pytest.raises(ValueError, match="Invalid parameters combination"):
            ValueIsEqualMatcher("a", any=True)

    def test_set_matcher_rejects_non_iterable_expected(self):
        """Set-theory matchers require an iterable ``expected_value``."""
        with pytest.raises(ValueError, match="iterable values"):
            ValueIsSubsetMatcher(123)


class TestValueIsEqualMatcher:
    def test_equal_passes(self, ctx):
        assert _ok(ValueIsEqualMatcher("admin"), ctx, "admin")

    def test_not_equal_fails(self, ctx):
        assert _bad(ValueIsEqualMatcher("admin"), ctx, "user")

    def test_strict_compares_by_identity(self, ctx):
        """``strict`` uses ``is``: equal-by-value but distinct identity fails."""
        assert _bad(ValueIsEqualMatcher([1], strict=True), ctx, [1])
        assert _ok(ValueIsEqualMatcher([1]), ctx, [1])

    def test_any_short_circuits_in_array(self, ctx):
        assert _ok(ValueIsEqualMatcher("a", any=True, in_array=True), ctx, ["a", "b"])
        assert _bad(ValueIsEqualMatcher("a", any=True, in_array=True), ctx, ["b", "c"])

    def test_in_array_requires_all_equal_without_any(self, ctx):
        assert _ok(ValueIsEqualMatcher("a", in_array=True), ctx, ["a", "a"])
        assert _bad(ValueIsEqualMatcher("a", in_array=True), ctx, ["a", "b"])


class TestValueIsNotEqualMatcher:
    def test_not_equal_passes(self, ctx):
        assert _ok(ValueIsNotEqualMatcher("admin"), ctx, "user")

    def test_equal_fails(self, ctx):
        assert _bad(ValueIsNotEqualMatcher("admin"), ctx, "admin")


class TestValueIsGreaterMatcher:
    def test_greater_passes(self, ctx):
        assert _ok(ValueIsGreaterMatcher(5), ctx, 10)

    def test_not_greater_fails(self, ctx):
        assert _bad(ValueIsGreaterMatcher(5), ctx, 3)

    def test_or_equal_allows_equality(self, ctx):
        assert _ok(ValueIsGreaterMatcher(5, or_equal=True), ctx, 5)
        assert _bad(ValueIsGreaterMatcher(5), ctx, 5)


class TestValueIsLesserMatcher:
    def test_lesser_passes(self, ctx):
        assert _ok(ValueIsLesserMatcher(5), ctx, 3)

    def test_not_lesser_fails(self, ctx):
        assert _bad(ValueIsLesserMatcher(5), ctx, 10)

    def test_or_equal_allows_equality(self, ctx):
        assert _ok(ValueIsLesserMatcher(5, or_equal=True), ctx, 5)
        assert _bad(ValueIsLesserMatcher(5), ctx, 5)


class TestValueContainsMatcher:
    def test_contains_passes(self, ctx):
        assert _ok(ValueContainsMatcher("a"), ctx, "abc")

    def test_not_contains_fails(self, ctx):
        assert _bad(ValueContainsMatcher("z"), ctx, "abc")


class TestValueNotContainsMatcher:
    def test_not_contains_passes(self, ctx):
        assert _ok(ValueNotContainsMatcher("z"), ctx, "abc")

    def test_contains_fails(self, ctx):
        assert _bad(ValueNotContainsMatcher("a"), ctx, "abc")


class TestValueLengthMatchers:
    def test_length_equal(self, ctx):
        assert _ok(ValueLengthEqualMatcher(3), ctx, "abc")
        assert _bad(ValueLengthEqualMatcher(3), ctx, "ab")

    def test_length_greater(self, ctx):
        assert _ok(ValueLengthGreaterMatcher(2), ctx, "abc")
        assert _bad(ValueLengthGreaterMatcher(2), ctx, "ab")

    def test_length_lesser(self, ctx):
        assert _ok(ValueLengthLesserMatcher(3), ctx, "ab")
        assert _bad(ValueLengthLesserMatcher(3), ctx, "abcd")


class TestValueRegexMatcher:
    def test_match_passes(self, ctx):
        assert _ok(ValueRegexMatcher(re.compile(r"\d+")), ctx, "12345")

    def test_no_match_fails(self, ctx):
        assert _bad(ValueRegexMatcher(re.compile(r"\d+")), ctx, "abc")


class TestValueContainsDictMatcher:
    def test_dict_contains_pairs_passes(self, ctx):
        assert _ok(ValueContainsDictMatcher({"a": 1}), ctx, {"a": 1, "b": 2})

    def test_dict_missing_pair_fails(self, ctx):
        assert _bad(ValueContainsDictMatcher({"a": 1}), ctx, {"a": 2})

    def test_non_dict_fails(self, ctx):
        assert _bad(ValueContainsDictMatcher({"a": 1}), ctx, "not a dict")


class TestValueEndsWithMatcher:
    def test_ends_with_passes(self, ctx):
        assert _ok(ValueEndsWithMatcher(".json"), ctx, "file.json")

    def test_not_ends_with_fails(self, ctx):
        assert _bad(ValueEndsWithMatcher(".json"), ctx, "file.txt")

    def test_non_string_fails(self, ctx):
        assert _bad(ValueEndsWithMatcher(".json"), ctx, 123)


class TestValueStartsWithMatcher:
    def test_starts_with_passes(self, ctx):
        assert _ok(ValueStartsWithMatcher("https://"), ctx, "https://example.com")

    def test_not_starts_with_fails(self, ctx):
        assert _bad(ValueStartsWithMatcher("https://"), ctx, "http://example.com")

    def test_non_string_fails(self, ctx):
        assert _bad(ValueStartsWithMatcher("https://"), ctx, [])


class TestValueIsEmpty:
    def test_empty_string_passes(self, ctx):
        assert _ok(ValueIsEmpty(), ctx, "")

    def test_empty_collection_passes(self, ctx):
        assert _ok(ValueIsEmpty(), ctx, [])

    def test_non_empty_fails(self, ctx):
        assert _bad(ValueIsEmpty(), ctx, "x")


class TestValueIsNotEmpty:
    def test_non_empty_passes(self, ctx):
        assert _ok(ValueIsNotEmpty(), ctx, "x")

    def test_empty_fails(self, ctx):
        assert _bad(ValueIsNotEmpty(), ctx, "")


class TestValueIsInMatcher:
    def test_member_passes(self, ctx):
        assert _ok(ValueIsInMatcher(["a", "b"]), ctx, "a")

    def test_non_member_fails(self, ctx):
        assert _bad(ValueIsInMatcher(["a", "b"]), ctx, "c")


class TestValueIsNotInMatcher:
    def test_non_member_passes(self, ctx):
        assert _ok(ValueIsNotInMatcher(["a", "b"]), ctx, "c")

    def test_member_fails(self, ctx):
        assert _bad(ValueIsNotInMatcher(["a", "b"]), ctx, "a")


class TestValueIsSubsetMatcher:
    def test_subset_passes(self, ctx):
        assert _ok(ValueIsSubsetMatcher({1, 2, 3}), ctx, [1, 2])

    def test_not_subset_fails(self, ctx):
        assert _bad(ValueIsSubsetMatcher({1, 2}), ctx, [1, 2, 3])

    def test_non_iterable_value_raises(self, ctx):
        """A non-iterable value violates the set-matcher precondition (ValueError)."""
        with pytest.raises(ValueError, match="iterable values"):
            ValueIsSubsetMatcher({1, 2})._matches(ctx(5))


class TestValueIsDisjointMatcher:
    def test_disjoint_passes(self, ctx):
        assert _ok(ValueIsDisjointMatcher({1, 2}), ctx, [3, 4])

    def test_not_disjoint_fails(self, ctx):
        assert _bad(ValueIsDisjointMatcher({1, 2}), ctx, [1, 3])


class TestValueIsUrlMatcher:
    def test_valid_url_passes(self, ctx):
        assert _ok(ValueIsUrlMatcher(), ctx, "https://example.com")

    def test_bare_host_fails(self, ctx):
        assert _bad(ValueIsUrlMatcher(), ctx, "example.com")


class TestValueDateMatchers:
    def test_date_equal(self, ctx):
        assert _ok(ValueDateEqualMatcher(date(2026, 7, 14)), ctx, date(2026, 7, 14))
        assert _bad(ValueDateEqualMatcher(date(2026, 7, 14)), ctx, date(2026, 7, 13))

    def test_date_greater(self, ctx):
        assert _ok(ValueDateGreaterMatcher(date(2026, 7, 14)), ctx, date(2026, 7, 15))
        assert _bad(ValueDateGreaterMatcher(date(2026, 7, 14)), ctx, date(2026, 7, 13))

    def test_date_lesser(self, ctx):
        assert _ok(ValueDateLesserMatcher(date(2026, 7, 14)), ctx, date(2026, 7, 13))
        assert _bad(ValueDateLesserMatcher(date(2026, 7, 14)), ctx, date(2026, 7, 15))

    def test_non_date_fails(self, ctx):
        assert _bad(ValueDateEqualMatcher(date(2026, 7, 14)), ctx, "not a date")
