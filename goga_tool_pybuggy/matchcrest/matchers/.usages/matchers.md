# matchcrest/matchers — Matcher Mechanics

## Domain

The `matchcrest/matchers` cell contains the matcher foundation and concrete matchers. Foundation entities:
`BaseContext` (data source contract), `BaseMatcher` (base class), `MatchResult` (check outcome). Concrete matchers
cover values, HTTP responses, and exceptions. The document serves two audiences: direct matcher consumers and
custom matcher authors. It explains three actions: feed data into a matcher via a context, apply the matcher
through `assert_that`, and extend `BaseMatcher` with a custom matcher.

Every matcher builds on PyHamcrest: `BaseMatcher` inherits `hamcrest.core.base_matcher.BaseMatcher`,
and `assert_that(actual, matcher)` executes the check.

---

## Facade

```python
from goga_tool_pybuggy.matchcrest.matchers import (
    BaseContext,
    BaseMatcher,
    MatchResult,
    ValueIsEqualMatcher,
    ResponseCodeMatcher,
    RaisedExceptionMatcher,  # ...and so on
)
```

---

## Data Source Contract — BaseContext

A matcher is decoupled from HTTP and `requests`: it reads the value only from the `item` context. The consumer
implements `BaseContext`, exposing `value`, `key`, and `update()`:

```python
from goga_tool_pybuggy.matchcrest.matchers import BaseContext


class ResponseContext(BaseContext):
    def __init__(self, response):
        self._response = response

    @property
    def value(self):
        return self._response.status_code

    @property
    def key(self):
        return self._response.url

    def update(self):
        self._response = refetch(self._response.url)  # refresh the source between retry attempts
```

- `value` — the value under test; `key` — the source label; the engine includes `key` in report messages.
- The engine calls `update()` between retry attempts (when `proofs > 1` or `timeout` is set).

---

## Applying a Matcher via assert_that

```python
from hamcrest import assert_that
from goga_tool_pybuggy.matchcrest.matchers import ResponseCodeMatcher

assert_that(ResponseContext(response), ResponseCodeMatcher(200, timeout=10))
```

- Matcher construction: `(expected_value, *, proofs, timeout, delay)` plus matcher-specific options.
- `timeout`/`proofs`/`delay` drive the retry loop: the check repeats until it passes or the timeout expires.

---

## Value Matchers — any / in_array Modifiers

Value matchers accept `any` and `in_array` (both default to `False`):

- `in_array=True` — the matcher treats `item.value` as a collection and checks every element.
- `any=True` (valid only together with `in_array`) — the first successful element suffices.

```python
from goga_tool_pybuggy.matchcrest.matchers import ValueIsEqualMatcher

ValueIsEqualMatcher("admin", any=True, in_array=True)  # at least one element == "admin"
```

---

## Custom Matcher — Extending BaseMatcher

Implement the single hook `_assert(item) -> MatchResult`:

```python
from goga_tool_pybuggy.matchcrest.matchers import BaseMatcher, MatchResult


class StatusCodeInRange(BaseMatcher):
    def _assert(self, item) -> MatchResult:
        code = item.value
        ok = 200 <= code < 300
        return MatchResult(
            ok,
            expectations=[f'"{item.key}" code should be 2xx'],
            errors=None if ok else [f"{code} is not 2xx"],
        )
```

- The `BaseMatcher._matches` engine invokes `_assert` and owns retry, timeout, and reporting.
- On failure, return `MatchResult(False, errors=..., expectations=...)` — both lists are mandatory.
