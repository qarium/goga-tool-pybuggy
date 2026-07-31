import time
from collections.abc import Callable
from typing import Any

from flaky import flaky


def retries(
    max_runs: int,
    *,
    min_passes: int | None = None,
    delay: int | float | None = None,
) -> Callable[..., Any]:
    """Build a flaky decorator that reruns a test with configurable pass/delay.

    Wraps the flaky library to rerun a test function up to ``max_runs`` times,
    requiring ``min_passes`` successes, with an optional ``delay`` slept between
    reruns. Exposed on the package facade for consumer test suites.

    Args:
        max_runs: Maximum number of test runs (required, positive int).
        min_passes: Minimum successful runs required for the test to pass; when
            None, flaky derives its own default.
        delay: Seconds to sleep between reruns; when None, reruns run
            immediately and no rerun filter is applied.

    Returns:
        The flaky decorator to apply to a test function.

    Constraints:
        The rerun filter always returns True, so reruns are unconditional up to
        ``max_runs``.
    """

    def _rerun_filter(*_, **__):
        time.sleep(delay)

        return True

    rerun_filter = None if delay is None else _rerun_filter

    return flaky(max_runs=max_runs, min_passes=min_passes, rerun_filter=rerun_filter)
