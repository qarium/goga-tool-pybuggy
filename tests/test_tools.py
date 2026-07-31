"""Tests for `retries` in the root `pybuggy` cell.

Mirrors the source layout (``tests/test_tools.py``). Covers the contract surface of
the ``retries`` decorator-factory: it forwards ``max_runs``/``min_passes`` to flaky,
gates the rerun filter on ``delay``, and the filter sleeps ``delay`` and unconditionally
allows a rerun. The flaky library and ``time.sleep`` are external boundaries and are
mocked at the import point.
"""

from unittest import mock

from pybuggy import tools


class TestRetriesContract:
    """Contract tests for `retries`."""

    def test_retries_returns_callable_decorator(self):
        """`retries` forwards flaky's return value (a callable decorator) unchanged."""
        sentinel = mock.MagicMock(name="flaky_decorator")

        with mock.patch.object(tools, "flaky", return_value=sentinel) as flaky_mock:
            result = tools.retries(max_runs=3)

        assert result is sentinel
        assert callable(result)
        flaky_mock.assert_called_once()

    def test_retries_delay_none_passes_no_rerun_filter(self):
        """When delay is None, flaky receives rerun_filter=None (no sleep filter)."""
        with mock.patch.object(tools, "flaky") as flaky_mock:
            tools.retries(max_runs=3)

        _, kwargs = flaky_mock.call_args
        assert kwargs["max_runs"] == 3
        assert kwargs["min_passes"] is None
        assert kwargs["rerun_filter"] is None

    def test_retries_delay_set_sleeps_and_returns_true(self):
        """When delay is set, the rerun filter sleeps `delay` and returns True."""
        captured = {}

        def fake_flaky(**fkwargs):
            captured["rerun_filter"] = fkwargs["rerun_filter"]

            return mock.MagicMock()

        with mock.patch.object(tools, "flaky", side_effect=fake_flaky), \
                mock.patch.object(tools.time, "sleep") as sleep_mock:
            tools.retries(max_runs=3, delay=2)
            result = captured["rerun_filter"]("err", "name", "test", "plugin")

        assert captured["rerun_filter"] is not None
        assert result is True
        sleep_mock.assert_called_once_with(2)

    def test_retries_forwards_max_runs_and_min_passes(self):
        """`max_runs` and `min_passes` are forwarded to flaky verbatim."""
        with mock.patch.object(tools, "flaky") as flaky_mock:
            tools.retries(max_runs=5, min_passes=2, delay=1)

        _, kwargs = flaky_mock.call_args
        assert kwargs["max_runs"] == 5
        assert kwargs["min_passes"] == 2
