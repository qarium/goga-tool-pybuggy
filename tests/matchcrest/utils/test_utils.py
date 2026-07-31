"""Contract, branch, and boundary tests for the matchcrest utils routines."""

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from goga_tool_pybuggy.matchcrest.utils import (
    allow_failure,
    date_to_timestamp,
    join,
    url_is_live,
    url_is_valid,
    waiting_for,
)
from goga_tool_pybuggy.matchcrest.utils.utils import parse_date_iso_string

UTILS = "goga_tool_pybuggy.matchcrest.utils.utils"


def to_none(_value):
    """Waiting-for hook that always returns a falsy value (None)."""
    return None


class TestWaitingFor:
    """Retry-loop contract and branch points."""

    def test_returns_first_truthy_value(self):
        """A truthy return is returned immediately."""
        calls = {"n": 0}

        def f():
            calls["n"] += 1
            return calls["n"]

        assert waiting_for(f, timeout=1, delay=0) == 1

    def test_applies_hook_before_truthiness_check(self):
        """The hook transforms the return value before the truthiness test."""

        def f():
            return "raw"

        assert waiting_for(f, hook=lambda r: f"{r}-hooked", timeout=1, delay=0) == "raw-hooked"

    def test_hook_making_result_falsy_times_out(self):
        """A hook returning a falsy value keeps the loop retrying until timeout."""

        def f():
            return "raw"

        with pytest.raises(TimeoutError):
            waiting_for(f, hook=to_none, timeout=0.05, delay=0)

    def test_raises_timeout_when_never_truthy(self):
        """A callable that never returns truthy raises TimeoutError."""

        def f():
            return None

        with pytest.raises(TimeoutError):
            waiting_for(f, timeout=0.05, delay=0)

    def test_forwards_positional_and_keyword_arguments(self):
        """``args``/``kwargs`` are forwarded to the callable."""

        def f(a, b, c=0):
            return a + b + c

        assert waiting_for(f, args=[1, 2], kwargs={"c": 3}, timeout=1, delay=0) == 6

    def test_defaults_do_not_raise_on_immediate_success(self):
        """Default timeout/delay (5s/0.5s) are acceptable for an instant success."""

        def f():
            return True

        assert waiting_for(f) is True


class TestJoin:
    """URL-join contract and boundary points."""

    def test_strips_trailing_slashes_between_parts(self):
        """Inner trailing slashes are stripped and the parts concatenated."""
        assert join("https://api.example.com/", "/v1/", "/users/") == "https://api.example.com/v1/users/"

    def test_appends_trailing_slash_when_last_part_ends_with_slash(self):
        """A trailing '/' is re-added when the last part originally ended with one."""
        assert join("a", "b/") == "ab/"

    def test_no_trailing_slash_when_last_part_does_not_end_with_slash(self):
        """No trailing '/' is added when the last part has none."""
        assert join("a", "b") == "ab"

    def test_single_part_without_trailing_slash(self):
        """A single slash-less part is returned as-is."""
        assert join("abc") == "abc"

    def test_single_part_with_trailing_slash(self):
        """A single part ending with '/' keeps one trailing slash."""
        assert join("abc/") == "abc/"

    def test_empty_parts_raises_index_error(self):
        """Boundary: with no parts, ``parts[-1]`` access raises IndexError."""
        with pytest.raises(IndexError):
            join()


class TestUrlIsValid:
    """Structural URL validation contract."""

    def test_valid_https_url(self):
        """An absolute https URL with a netloc is valid."""
        assert url_is_valid("https://example.com") is True

    def test_protocol_relative_link_accepted(self):
        """A ``//host`` link has a netloc and is accepted as relative."""
        assert url_is_valid("//example.com") is True

    def test_rejects_url_without_netloc(self):
        """A bare host without ``//`` has no netloc and is rejected."""
        assert url_is_valid("example.com") is False

    def test_rejects_empty_url(self):
        """An empty URL has no netloc and is rejected."""
        assert url_is_valid("") is False

    def test_is_live_false_when_probe_not_live(self):
        """``is_live`` returns False when the liveness probe says not live."""
        with patch(f"{UTILS}.url_is_live", return_value=False):
            assert url_is_valid("https://example.com", is_live=True) is False

    def test_is_live_true_when_probe_live(self):
        """``is_live`` returns True when the liveness probe says live."""
        with patch(f"{UTILS}.url_is_live", return_value=True):
            assert url_is_valid("https://example.com", is_live=True) is True

    def test_is_live_prepends_first_allowed_protocol_for_relative_link(self):
        """For a relative link the first allowed protocol is prepended before probing."""
        with patch(f"{UTILS}.url_is_live", return_value=True) as probe:
            assert url_is_valid("//example.com", is_live=True) is True
            probe.assert_called_once_with("https://example.com")


class TestUrlIsLive:
    """HTTP liveness probe contract."""

    def test_2xx_is_live(self):
        """A 2xx status code is live."""
        with patch(f"{UTILS}.requests.get") as getter:
            getter.return_value = MagicMock(status_code=200)
            assert url_is_live("https://example.com") is True

    def test_404_is_not_live(self):
        """A 404 status code is not live."""
        with patch(f"{UTILS}.requests.get") as getter:
            getter.return_value = MagicMock(status_code=404)
            assert url_is_live("https://example.com") is False

    def test_500_is_not_live(self):
        """A 500 status code is not live."""
        with patch(f"{UTILS}.requests.get") as getter:
            getter.return_value = MagicMock(status_code=500)
            assert url_is_live("https://example.com") is False


class TestDateToTimestamp:
    """Date/datetime -> UNIX timestamp contract."""

    def test_datetime_returns_its_timestamp(self):
        """A datetime returns its own ``.timestamp()``."""
        dt = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
        assert date_to_timestamp(dt) == dt.timestamp()

    def test_date_returns_iso_parsed_timestamp(self):
        """A date is parsed from its ISO string and converted to a timestamp."""
        d = date(2026, 7, 14)
        assert date_to_timestamp(d) == parse_date_iso_string(d.isoformat()).timestamp()

    @pytest.mark.parametrize("value", ["2026-07-14", None, 123, [1, 2, 3]])
    def test_invalid_type_raises_value_error(self, value):
        """Anything other than a date/datetime raises ValueError."""
        with pytest.raises(ValueError, match="not date or datetime"):
            date_to_timestamp(value)


class TestAllowFailure:
    """Swallow-and-log decorator contract."""

    def test_returns_result_on_success(self):
        """A successful call returns its result."""

        @allow_failure
        def add(a, b):
            return a + b

        assert add(1, 2) == 3

    def test_returns_none_and_swallows_exception(self):
        """A raised exception is swallowed and None is returned."""

        @allow_failure
        def boom():
            raise ValueError("bang")

        assert boom() is None

    def test_preserves_wrapped_metadata(self):
        """``functools.wraps`` preserves the wrapped callable's name."""

        @allow_failure
        def named(a, b=2):
            return a + b

        assert named.__name__ == "named"
