"""Tests for assert polling and pluggable-class loading in `goga_tool_pybuggy.api.asserts`.

Covers the four ``ApiPlugin`` assert options:

- ``assert_timeout`` / ``assert_delay`` — matchcrest's retry loop, re-fetching
  the response via ``resq.http.Response.reload()`` between attempts (driven by
  ``AssertConfig.timeout``/``delay`` and overridable per check method);
- ``assert_field_class`` / ``assert_response_class`` — dotted-path loading of a
  custom ``AssertField`` / ``Expected`` subclass.

The network is not involved: a ``ReloadableResponse`` stands in for
``resq.http.Response`` (its ``reload()`` advances a queue of canned bodies), and
a fake clock bounds the retry loop so the timeout case is deterministic.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from goga_tool_pybuggy.api.asserts.base import load_assert_class
from goga_tool_pybuggy.api.asserts.config import AssertConfig
from goga_tool_pybuggy.api.asserts.expected import Expected
from goga_tool_pybuggy.api.asserts.field import AssertField
from goga_tool_pybuggy.api.response import ResponseWrapper

from tests.api.conftest import FakeResponse


class _FakeClock:
    """Deterministic stand-in for ``time.time``/``time.sleep``.

    ``sleep`` advances the virtual clock by the requested delay (no real wait);
    ``time`` reports it. Installed onto the real ``time`` module for the polling
    tests so the retry loop is bounded and instant.
    """

    def __init__(self) -> None:
        self.now = 0.0

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def fake_clock(monkeypatch):
    clock = _FakeClock()
    monkeypatch.setattr(time, "time", clock.time)
    monkeypatch.setattr(time, "sleep", clock.sleep)
    return clock


class ReloadableResponse:
    """``resq.http.Response`` stand-in whose ``reload()`` advances the body.

    Args:
        bodies: ordered bodies returned by ``json()``; each ``reload()`` advances
            to the next, sticking on the last.
        status_code: HTTP status code.
    """

    def __init__(self, bodies: list[Any], status_code: int = 200) -> None:
        self._bodies = bodies
        self._idx = 0
        self.status_code = status_code
        self.headers = {"Content-Type": "application/json"}
        self.url = "https://api.example.com/resource"
        self.reload_calls = 0

    def json(self) -> Any:
        return self._bodies[min(self._idx, len(self._bodies) - 1)]

    def reload(self) -> None:
        self.reload_calls += 1
        self._idx += 1


class TestConfigPolling:
    """``AssertConfig.timeout``/``delay`` drive matchcrest's retry loop."""

    def test_retries_until_pass_via_reload(self, fake_clock) -> None:
        """A body that fails then, after one reload, passes — assert succeeds."""
        response = ReloadableResponse([{"other": 1}, {"data": [1, 2, 3]}])
        config = AssertConfig(status=200, data_key="data", timeout=5, delay=1)

        Expected(response, config).json_has_data_by_key("data")

        assert response.reload_calls == 1

    def test_times_out_when_never_satisfied(self, fake_clock) -> None:
        """A body that never satisfies raises AssertionError after the timeout."""
        response = ReloadableResponse([{"other": 1}])
        config = AssertConfig(status=200, data_key="data", timeout=3, delay=1)

        with pytest.raises(AssertionError):
            Expected(response, config).json_has_data_by_key("data")

        assert response.reload_calls >= 1

    def test_no_timeout_does_single_attempt_no_reload(self) -> None:
        """Without a timeout, the matcher runs once and never reloads."""
        response = ReloadableResponse([{"data": [1]}])
        config = AssertConfig(status=200, data_key="data")

        Expected(response, config).json_has_data_by_key("data")

        assert response.reload_calls == 0


class TestPerCheckTimeoutOverride:
    """Per-check ``timeout``/``delay`` kwargs override the config baseline."""

    def test_per_check_timeout_drives_polling_without_config(self, fake_clock) -> None:
        """A check-level timeout polls even when ``AssertConfig.timeout`` is None."""
        response = ReloadableResponse([{"other": 1}, {"data": [1]}])
        config = AssertConfig(status=200, data_key="data")

        Expected(response, config).json_has_data_by_key("data", timeout=5, delay=1)

        assert response.reload_calls == 1

    def test_field_check_timeout_drives_polling(self, fake_clock) -> None:
        """An ``AssertField`` check polls via its per-check ``timeout`` kwarg."""
        response = ReloadableResponse([{"items": [1]}, {"items": [1, 2, 3]}])
        config = AssertConfig(status=200, data_key=None)

        field = Expected(response, config)("items")
        assert isinstance(field, AssertField)
        field.has_length(3, timeout=5, delay=1)

        assert response.reload_calls == 1


class TestPluggableFieldClass:
    """``AssertConfig.assert_field_class`` loads a custom ``AssertField``."""

    def test_custom_field_class_is_loaded(self) -> None:
        """``Expected.__call__`` returns the configured ``AssertField`` subclass."""
        response = FakeResponse(body={"data": [1, 2, 3]})
        config = AssertConfig(
            status=200,
            data_key="data",
            assert_field_class="tests.api.test_assert_polling:CustomAssertField",
        )

        field = Expected(response, config)("data")

        assert isinstance(field, CustomAssertField)
        assert field.marker == "custom-field"

    def test_field_baseline_timeout_propagates_to_loaded_class(self, fake_clock) -> None:
        """A loaded field class inherits the config baseline ``_timeout``."""
        response = ReloadableResponse([{"data": [1]}, {"data": [1, 2, 3]}])
        config = AssertConfig(
            status=200,
            data_key="data",
            timeout=5,
            delay=1,
            assert_field_class="tests.api.test_assert_polling:CustomAssertField",
        )

        field = Expected(response, config)("data")
        assert field._timeout == 5
        assert field._delay == 1


class TestPluggableResponseClass:
    """``AssertConfig.assert_response_class`` loads a custom ``Expected``."""

    def test_custom_response_class_is_loaded_by_wrapper(self) -> None:
        """``ResponseWrapper.expected`` builds the configured ``Expected`` subclass."""
        response = FakeResponse(status_code=200, body={"data": [1]})
        config = AssertConfig(
            status=200,
            data_key="data",
            assert_response_class="tests.api.test_assert_polling:CustomExpected",
        )

        wrapper = ResponseWrapper(response, config)
        expected = wrapper.expected

        assert isinstance(expected, CustomExpected)
        assert expected.marker == "custom-response"


class TestLoadAssertClass:
    """``load_assert_class`` dotted-path resolution and validation."""

    def test_missing_colon_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid import path"):
            load_assert_class("no_colon_here", AssertField)

    def test_unknown_module_raises_import_error(self) -> None:
        with pytest.raises(ImportError, match=r'Module "definitely.no.such.module" not found'):
            load_assert_class("definitely.no.such.module:Cls", AssertField)

    def test_unknown_class_raises_import_error(self) -> None:
        with pytest.raises(ImportError, match='Class "Nope" not found'):
            load_assert_class("tests.api.test_assert_polling:Nope", AssertField)

    def test_non_subclass_raises_type_error(self) -> None:
        """A class that is not a subclass of the base raises TypeError."""
        with pytest.raises(TypeError, match="not a subclass"):
            load_assert_class("tests.api.test_assert_polling:NotAnAssert", AssertField)

    def test_valid_subclass_is_returned(self) -> None:
        cls = load_assert_class("tests.api.test_assert_polling:CustomAssertField", AssertField)

        assert cls is CustomAssertField


# --- Custom pluggable classes referenced by the tests above (dotted import). ---


class CustomAssertField(AssertField):
    """``AssertField`` subclass carrying a marker for load-detection."""

    marker = "custom-field"


class CustomExpected(Expected):
    """``Expected`` subclass carrying a marker for load-detection."""

    marker = "custom-response"


class NotAnAssert:
    """Unrelated class used to assert the subclass check."""
