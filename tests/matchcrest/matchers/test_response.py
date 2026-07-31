"""Contract, branch, and boundary tests for the response/error-body matchers."""

from enum import Enum

import pytest
from goga_tool_pybuggy.matchcrest.matchers import (
    JsonContainsKeyMatcher,
    JsonHasDataByKeyMatcher,
    JsonHasNotDataByKeyMatcher,
    JsonschemaMatcher,
    ResponseBodyMatcher,
    ResponseCodeMatcher,
    ResponseHeadersByKeyMatcher,
    ResponseHeadersByValueMatcher,
)


def _ok(matcher, ctx, value):
    return matcher._matches(ctx(value)) is True


def _bad(matcher, ctx, value):
    return matcher._matches(ctx(value)) is False


class _Code(Enum):
    OK = 200


class TestResponseCodeMatcher:
    def test_int_code_equal_passes(self, ctx):
        assert _ok(ResponseCodeMatcher(200), ctx, 200)

    def test_int_code_not_equal_fails(self, ctx):
        assert _bad(ResponseCodeMatcher(200), ctx, 404)

    def test_enum_code_normalized(self, ctx):
        """An Enum expected value is normalized to its value."""
        assert _ok(ResponseCodeMatcher(_Code.OK), ctx, 200)

    def test_string_code_name_resolved(self, ctx):
        """A ``requests.codes`` name string is resolved to its numeric code."""
        assert _ok(ResponseCodeMatcher("ok"), ctx, 200)

    def test_non_int_code_raises_value_error(self):
        """A code that is neither int, Enum, nor a known name raises ValueError."""
        with pytest.raises(ValueError, match="Code is expected"):
            ResponseCodeMatcher(1.5)


class TestResponseHeadersByValueMatcher:
    def test_value_matches_case_insensitively(self, ctx):
        assert _ok(
            ResponseHeadersByValueMatcher("application/json", key="content-type"),
            ctx,
            {"Content-Type": "application/json"},
        )

    def test_value_mismatch_fails(self, ctx):
        assert _bad(
            ResponseHeadersByValueMatcher("text/plain", key="content-type"),
            ctx,
            {"Content-Type": "application/json"},
        )

    def test_contains_mode(self, ctx):
        assert _ok(
            ResponseHeadersByValueMatcher("json", key="content-type", contains=True),
            ctx,
            {"Content-Type": "application/json"},
        )

    def test_missing_key_fails(self, ctx):
        assert _bad(
            ResponseHeadersByValueMatcher("x", key="absent"),
            ctx,
            {"Content-Type": "application/json"},
        )

    def test_startswith_mode(self, ctx):
        assert _ok(
            ResponseHeadersByValueMatcher("app", key="content-type", startswith=True),
            ctx,
            {"Content-Type": "application/json"},
        )

    def test_endswith_mode(self, ctx):
        assert _ok(
            ResponseHeadersByValueMatcher("json", key="content-type", endswith=True),
            ctx,
            {"Content-Type": "application/json"},
        )

    def test_relaxation_mismatch_fails(self, ctx):
        """A relaxation flag that the value does not satisfy fails."""
        assert _bad(
            ResponseHeadersByValueMatcher("xml", key="content-type", contains=True),
            ctx,
            {"Content-Type": "application/json"},
        )
        assert _bad(
            ResponseHeadersByValueMatcher("app", key="content-type", startswith=True),
            ctx,
            {"Content-Type": "text/plain"},
        )
        assert _bad(
            ResponseHeadersByValueMatcher("json", key="content-type", endswith=True),
            ctx,
            {"Content-Type": "text/plain"},
        )


class TestResponseHeadersByKeyMatcher:
    def test_key_present_passes(self, ctx):
        assert _ok(
            ResponseHeadersByKeyMatcher("content-type"),
            ctx,
            {"Content-Type": "application/json"},
        )

    def test_key_absent_fails(self, ctx):
        assert _bad(
            ResponseHeadersByKeyMatcher("x-trace"),
            ctx,
            {"Content-Type": "application/json"},
        )

    def test_count_constraint(self, ctx):
        """``count`` requires exactly that many matching headers (substring mode)."""
        assert _ok(
            ResponseHeadersByKeyMatcher("x", contains=True, count=2),
            ctx,
            {"x-1": "1", "x-2": "2"},
        )
        assert _bad(
            ResponseHeadersByKeyMatcher("x", contains=True, count=2),
            ctx,
            {"x-1": "1"},
        )

    def test_exact_key_mode_without_relaxation(self, ctx):
        """Without relaxation flags, only an exact (case-insensitive) key matches."""
        assert _ok(
            ResponseHeadersByKeyMatcher("content-type"),
            ctx,
            {"Content-Type": "application/json"},
        )
        assert _bad(
            ResponseHeadersByKeyMatcher("content-type"),
            ctx,
            {"x-content-type": "application/json"},
        )

    def test_startswith_mode(self, ctx):
        assert _ok(
            ResponseHeadersByKeyMatcher("x-", startswith=True),
            ctx,
            {"x-trace": "1"},
        )
        assert _bad(
            ResponseHeadersByKeyMatcher("y-", startswith=True),
            ctx,
            {"x-trace": "1"},
        )

    def test_endswith_mode(self, ctx):
        assert _ok(
            ResponseHeadersByKeyMatcher("trace", endswith=True),
            ctx,
            {"x-trace": "1"},
        )
        assert _bad(
            ResponseHeadersByKeyMatcher("id", endswith=True),
            ctx,
            {"x-trace": "1"},
        )


class TestResponseBodyMatcher:
    def test_equal_body_passes(self, ctx):
        assert _ok(ResponseBodyMatcher("hello"), ctx, "hello")

    def test_not_equal_body_fails(self, ctx):
        assert _bad(ResponseBodyMatcher("hello"), ctx, "world")

    def test_truncates_long_body_in_error(self, ctx):
        """Mismatch messages truncate bodies to MAX_BODY_LEN (75)."""
        long_body = "x" * 200
        matcher = ResponseBodyMatcher("y")
        assert matcher._matches(ctx(long_body)) is False
        joined = " ".join(matcher.result.errors)
        assert "x" * 76 not in joined


class TestJsonschemaMatcher:
    def test_valid_body_passes(self, ctx):
        schema = {"type": "object", "required": ["a"]}
        assert _ok(JsonschemaMatcher(schema), ctx, {"a": 1})

    def test_invalid_body_fails_with_json_path(self, ctx):
        schema = {"type": "object", "required": ["a"]}
        matcher = JsonschemaMatcher(schema)
        assert matcher._matches(ctx({})) is False
        # the error carries the failing json_path (always starts with '$') and a message
        joined = " ".join(str(e) for e in matcher.result.errors)
        assert "$" in joined


class TestJsonHasDataByKeyMatcher:
    def test_present_data_passes(self, ctx):
        assert _ok(JsonHasDataByKeyMatcher("a"), ctx, {"a": 1})

    def test_none_data_fails(self, ctx):
        assert _bad(JsonHasDataByKeyMatcher("a"), ctx, {"a": None})

    def test_non_dict_treated_as_empty(self, ctx):
        assert _bad(JsonHasDataByKeyMatcher("a"), ctx, "not a dict")


class TestJsonHasNotDataByKeyMatcher:
    def test_absent_data_passes(self, ctx):
        assert _ok(JsonHasNotDataByKeyMatcher("a"), ctx, {"a": None})

    def test_present_data_fails(self, ctx):
        assert _bad(JsonHasNotDataByKeyMatcher("a"), ctx, {"a": 1})


class TestJsonContainsKeyMatcher:
    def test_scalar_key_present(self, ctx):
        assert _ok(JsonContainsKeyMatcher("a"), ctx, {"a": 1})

    def test_scalar_key_wrapped_into_path(self, ctx):
        """A scalar expected value is wrapped into a single-element path."""
        assert _bad(JsonContainsKeyMatcher("z"), ctx, {"a": 1})

    def test_nested_path_present(self, ctx):
        assert _ok(JsonContainsKeyMatcher(["a", "b"]), ctx, {"a": {"b": 2}})

    def test_nested_path_missing_key(self, ctx):
        assert _bad(JsonContainsKeyMatcher(["a", "c"]), ctx, {"a": {"b": 2}})
