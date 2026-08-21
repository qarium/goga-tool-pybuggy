# pybuggy — test reruns via `retries`

## Domain

Consumption patterns of the `retries` facade function of the root cell `goga_tool_pybuggy/`: a decorator
factory built on the `flaky` library for configurable test reruns. The audience: test suite authors who need
to set the number of runs, the minimum number of successful runs, and an optional delay between reruns.

## Entry point

The facade exports `retries` for programmatic import:

    from goga_tool_pybuggy import retries

## Basic rerun

`retries` returns a decorator. The minimal scenario is `max_runs` (how many times to run the test):

```python
from goga_tool_pybuggy import retries


@retries(max_runs=3)
def test_something(): ...
```

The test is rerun up to `max_runs` times; reruns are unconditional (the filter always permits a repeat).

## Minimum successful runs

The `min_passes` parameter sets how many successful runs out of `max_runs` are sufficient for success:

```python
@retries(max_runs=5, min_passes=2)
def test_flaky_endpoint(): ...
```

If `min_passes` is not passed (`None`), `flaky` derives its own default value.

## Delay between reruns

The `delay` parameter (seconds) adds a sleep between reruns — useful for temporarily unavailable dependencies:

```python
@retries(max_runs=4, delay=1)
def test_with_external_service(): ...
```

If `delay` is not passed (`None`), reruns execute immediately, with no filter and no sleep.

## Preconditions and side effects

- `retries` runs on top of `flaky`; the package must be installed in the test environment (it is a dependency
  of `pybuggy`).
- `delay > 0` slows down the test suite (sleep between reruns) — apply it point-wise.
- Reruns are unconditional: the filter always returns permission; the number of attempts is bounded only by
  `max_runs`.
- `retries` is a manual decorator for a specific test (not a suite-level marker).
