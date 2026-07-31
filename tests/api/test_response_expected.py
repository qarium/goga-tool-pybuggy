"""Tests for ``pybuggy.api.asserts.expected`` and ``pybuggy.api.response``.

Covers the response-level ``Expected`` checks (matchcrest-backed), the
``ResponseWrapper.expected`` lazy build + memoized autocheck, and the autocheck
positive/negative paths with their skip conditions. The network is not involved:
a ``FakeResponse`` stands in for ``resq.http.Response``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pybuggy.api.asserts.config import AssertConfig
from pybuggy.api.asserts.expected import Expected
from pybuggy.api.response import ResponseWrapper

from tests.api.conftest import FakeResponse


class TestResponseStatusChecks:
    """``has_status_code`` over a ``ResponseContext``."""

    def test_matching_status_passes(self) -> None:
        """An equal status code does not raise and chains."""
        response = FakeResponse(status_code=200)

        assert Expected(response, AssertConfig(status=200)).has_status_code(200) is not None

    def test_mismatching_status_raises(self) -> None:
        """A different status code raises AssertionError."""
        response = FakeResponse(status_code=404)

        with pytest.raises(AssertionError):
            Expected(response, AssertConfig(status=200)).has_status_code(200)


class TestResponseHeaderChecks:
    """``has_header`` presence/value/substring checks (case-insensitive key)."""

    def test_header_present_by_key_any_case(self) -> None:
        """A header is found by key regardless of the passed case."""
        response = FakeResponse(headers={"Content-Type": "application/json"})

        Expected(response, AssertConfig(status=200)).has_header("Content-Type")
        Expected(response, AssertConfig(status=200)).has_header("content-type")

    def test_header_value_equal(self) -> None:
        """The header value matches exactly."""
        response = FakeResponse(headers={"X-Trace": "id-123"})

        Expected(response, AssertConfig(status=200)).has_header("X-Trace", "id-123")

    def test_header_value_startswith(self) -> None:
        """The header value matches a ``startswith`` filter."""
        response = FakeResponse(headers={"X-Trace": "id-123"})

        Expected(response, AssertConfig(status=200)).has_header("X-Trace", "id", startswith=True)

    def test_header_absent_raises(self) -> None:
        """A missing header raises AssertionError."""
        response = FakeResponse(headers={"X-Trace": "id-123"})

        with pytest.raises(AssertionError):
            Expected(response, AssertConfig(status=200)).has_header("X-Absent")

    def test_count_with_value_is_rejected(self) -> None:
        """``count`` and ``value`` together raise ValueError."""
        response = FakeResponse(headers={"X-Trace": "id-123"})

        with pytest.raises(ValueError, match="count"):
            Expected(response, AssertConfig(status=200)).has_header("X-Trace", "id-123", count=1)


class TestResponseJsonChecks:
    """``json_has_data_by_key`` / ``json_has_not_data_by_key`` / ``json_contains_key``."""

    def test_json_has_data_by_key_present(self) -> None:
        """A present, non-None body key passes."""
        response = FakeResponse(body={"data": [1, 2, 3]})

        Expected(response, AssertConfig(status=200)).json_has_data_by_key("data")

    def test_json_has_data_by_key_absent_raises(self) -> None:
        """A missing body key raises."""
        response = FakeResponse(body={"other": 1})

        with pytest.raises(AssertionError):
            Expected(response, AssertConfig(status=200)).json_has_data_by_key("data")

    def test_json_has_not_data_by_key_absent(self) -> None:
        """An absent body key passes the not-check."""
        response = FakeResponse(body={"other": 1})

        Expected(response, AssertConfig(status=200)).json_has_not_data_by_key("data")

    def test_json_contains_key_nested(self) -> None:
        """A nested key path resolves through the body."""
        response = FakeResponse(body={"data": {"items": []}})

        Expected(response, AssertConfig(status=200)).json_contains_key(["data", "items"])

    def test_json_contains_key_nested_missing_raises(self) -> None:
        """A broken nested path raises."""
        response = FakeResponse(body={"data": {"other": 1}})

        with pytest.raises(AssertionError):
            Expected(response, AssertConfig(status=200)).json_contains_key(["data", "items"])


class TestResponseSchemaChecks:
    """``jsonschema_is_valid`` / ``jsonschemas_is_valid``."""

    def test_valid_schema_passes(self) -> None:
        """A body conforming to the schema passes."""
        response = FakeResponse(body={"a": 1})

        Expected(response, AssertConfig(status=200)).jsonschema_is_valid({"type": "object", "required": ["a"]})

    def test_invalid_schema_raises(self) -> None:
        """A body violating the schema raises."""
        response = FakeResponse(body={"a": 1})

        with pytest.raises(AssertionError):
            Expected(response, AssertConfig(status=200)).jsonschema_is_valid({"type": "object", "required": ["b"]})

    def test_schema_loaded_from_file(self, tmp_path: Path) -> None:
        """A schema given as a path is read and applied."""
        schema_file = tmp_path / "200.json"
        schema_file.write_text(json.dumps({"type": "object", "required": ["a"]}), encoding="utf-8")
        response = FakeResponse(body={"a": 1})

        Expected(response, AssertConfig(status=200)).jsonschema_is_valid(str(schema_file))

    def test_schemas_dir_matching_status(self, tmp_path: Path) -> None:
        """``jsonschemas_is_valid`` picks the first ``<status>*`` file."""
        (tmp_path / "200.json").write_text(json.dumps({"type": "object", "required": ["a"]}), encoding="utf-8")
        response = FakeResponse(body={"a": 1})

        Expected(response, AssertConfig(status=200)).jsonschemas_is_valid(tmp_path, 200)

    def test_schemas_dir_no_match_is_silent_skip(self, tmp_path: Path) -> None:
        """No matching schema file is a silent skip (no raise)."""
        response = FakeResponse(body={"a": 1})

        Expected(response, AssertConfig(status=200)).jsonschemas_is_valid(tmp_path, 500)


class TestExpectedCallFieldDispatch:
    """``Expected.__call__`` produces an ``AssertField``."""

    def test_call_returns_assert_field(self) -> None:
        """Calling the dispatcher yields an AssertField over the body."""
        from pybuggy.api import AssertField

        response = FakeResponse(body={"data": {"name": "abc"}})

        field = Expected(response, AssertConfig(status=200, data_key="data"))("name")

        assert isinstance(field, AssertField)
        field.equal_to("abc")

    def test_call_non_callable_hook_raises(self) -> None:
        """A non-callable hook raises TypeError before any search."""
        response = FakeResponse(body={})

        with pytest.raises(TypeError):
            Expected(response, AssertConfig(status=200))("a", hook=123)


class TestAutocheckPositive:
    """Autocheck positive path: status, error absent, data present, schema."""

    def test_full_positive_passes(self) -> None:
        """Status match + error absent + data present all pass."""
        response = FakeResponse(
            status_code=200,
            body={"data": {"x": 1}, "error": None},
        )

        wrapper = ResponseWrapper(
            response,
            AssertConfig(status=200, data_key="data", error_key="error"),
            use_autocheck=True,
        )
        wrapper.expected  # noqa: B018 — triggers autocheck

    def test_positive_status_mismatch_raises(self) -> None:
        """A status mismatch fails the autocheck."""
        response = FakeResponse(status_code=500, body={"data": 1})

        wrapper = ResponseWrapper(response, AssertConfig(status=200, data_key="data"), use_autocheck=True)

        with pytest.raises(AssertionError):
            _ = wrapper.expected

    def test_positive_error_present_raises(self) -> None:
        """A present error_key fails the positive autocheck."""
        response = FakeResponse(status_code=200, body={"data": 1, "error": "boom"})

        wrapper = ResponseWrapper(
            response,
            AssertConfig(status=200, data_key="data", error_key="error"),
            use_autocheck=True,
        )

        with pytest.raises(AssertionError):
            _ = wrapper.expected

    def test_positive_data_absent_raises(self) -> None:
        """An absent data_key fails the positive autocheck."""
        response = FakeResponse(status_code=200, body={"other": 1})

        wrapper = ResponseWrapper(
            response,
            AssertConfig(status=200, data_key="data", error_key="error"),
            use_autocheck=True,
        )

        with pytest.raises(AssertionError):
            _ = wrapper.expected

    def test_positive_schema_validated(self, tmp_path: Path) -> None:
        """The matching status schema is applied on the positive path."""
        (tmp_path / "200.json").write_text(json.dumps({"type": "object", "required": ["data"]}), encoding="utf-8")
        response = FakeResponse(status_code=200, body={"data": 1})

        wrapper = ResponseWrapper(
            response,
            AssertConfig(status=200, data_key="data", schemas_dir=tmp_path),
            use_autocheck=True,
        )
        wrapper.expected  # noqa: B018

    def test_positive_schema_violation_raises(self, tmp_path: Path) -> None:
        """A body violating the matching schema fails the positive autocheck."""
        (tmp_path / "200.json").write_text(json.dumps({"type": "object", "required": ["missing"]}), encoding="utf-8")
        response = FakeResponse(status_code=200, body={"data": 1})

        wrapper = ResponseWrapper(
            response,
            AssertConfig(status=200, data_key="data", schemas_dir=tmp_path),
            use_autocheck=True,
        )

        with pytest.raises(AssertionError):
            _ = wrapper.expected

    def test_positive_status_none_skips_status(self) -> None:
        """``status=None`` skips the status check in autocheck."""
        response = FakeResponse(status_code=500, body={"data": 1})

        wrapper = ResponseWrapper(response, AssertConfig(data_key="data"), use_autocheck=True)
        wrapper.expected  # noqa: B018 — no raise despite 500


class TestAutocheckNegative:
    """Autocheck negative path: no status/schema; data absent, error present."""

    def test_full_negative_passes(self) -> None:
        """data_key absent + error_key present pass the negative autocheck."""
        response = FakeResponse(status_code=400, body={"error": {"msg": "bad"}})

        wrapper = ResponseWrapper(
            response,
            AssertConfig(status=400, data_key="data", error_key="error"),
            use_autocheck=True,
            is_negative=True,
        )
        wrapper.expected  # noqa: B018

    def test_negative_data_present_raises(self) -> None:
        """A present data_key fails the negative autocheck."""
        response = FakeResponse(status_code=400, body={"data": 1, "error": {"msg": "bad"}})

        wrapper = ResponseWrapper(
            response,
            AssertConfig(status=400, data_key="data", error_key="error"),
            use_autocheck=True,
            is_negative=True,
        )

        with pytest.raises(AssertionError):
            _ = wrapper.expected

    def test_negative_does_not_check_status(self) -> None:
        """The negative path ignores the status code."""
        response = FakeResponse(status_code=200, body={"error": {"msg": "bad"}})

        wrapper = ResponseWrapper(
            response,
            AssertConfig(status=400, data_key="data", error_key="error"),
            use_autocheck=True,
            is_negative=True,
        )
        wrapper.expected  # noqa: B018 — 200 != 400 but negative skips status


class TestResponseWrapperWiring:
    """``ResponseWrapper.expected`` lazy build and autocheck gating."""

    def test_expected_is_lazy_and_memoized(self) -> None:
        """``expected`` builds once and returns the same ``Expected``."""
        response = FakeResponse(status_code=200, body={"data": 1})
        wrapper = ResponseWrapper(response, AssertConfig(status=200, data_key="data"), use_autocheck=False)

        first = wrapper.expected
        second = wrapper.expected

        assert first is second

    def test_use_autocheck_false_skips_autocheck(self) -> None:
        """``use_autocheck=False`` never runs the autocheck (even on failure)."""
        response = FakeResponse(status_code=500, body={})

        wrapper = ResponseWrapper(response, AssertConfig(status=200, data_key="data"), use_autocheck=False)
        wrapper.expected  # noqa: B018 — no raise; autocheck skipped

    def test_context_manager_returns_self_and_propagates(self) -> None:
        """``__enter__`` returns the wrapper; ``__exit__`` does not suppress."""
        response = FakeResponse(status_code=200, body={"data": 1})
        wrapper = ResponseWrapper(response, AssertConfig(status=200, data_key="data"), use_autocheck=False)

        with wrapper as ctx:
            assert ctx is wrapper

        with pytest.raises(ValueError, match="boom"), wrapper:
            raise ValueError("boom")

    def test_autocheck_runs_once_per_wrapper(self) -> None:
        """Repeated ``expected`` access runs the autocheck exactly once."""
        response = FakeResponse(status_code=200, body={"data": 1, "error": None})
        wrapper = ResponseWrapper(
            response,
            AssertConfig(status=200, data_key="data", error_key="error"),
            use_autocheck=True,
        )

        _ = wrapper.expected
        _ = wrapper.expected

        # flip the body so a second autocheck would now fail; it must not re-run
        response._body = {"data": 1, "error": "now-present"}
        _ = wrapper.expected  # no raise; autocheck did not re-run
