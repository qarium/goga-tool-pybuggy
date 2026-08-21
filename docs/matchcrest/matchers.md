# Matcher Catalog

The `matchcrest.matchers` module contains the matcher foundation and the concrete
matchers. Foundation entities: `BaseContext` (data source contract), `BaseMatcher` (base
class), `MatchResult` (check outcome).

```python
from goga_tool_pybuggy.matchcrest.matchers import (
    BaseContext, BaseMatcher, MatchResult,
    ValueIsEqualMatcher, ResponseCodeMatcher, RaisedExceptionMatcher,  # ... and so on
)
```

## Data source contract — `BaseContext`

A matcher reads the value only from the `item` context. Implement `BaseContext`,
exposing `value`, `key`, and `update()`:

```python
from goga_tool_pybuggy.matchcrest.matchers import BaseContext


class ResponseContext(BaseContext):
    def __init__(self, response):
        self._response = response

    @property
    def value(self):
        return self._response.status_code   # the value under test

    @property
    def key(self):
        return self._response.url           # the source label for report messages

    def update(self):
        self._response = refetch(self._response.url)  # refresh between retry attempts
```

The engine calls `update()` between retry attempts (when `proofs > 1` or `timeout` is
set).

## Applying a matcher

```python
from hamcrest import assert_that
from goga_tool_pybuggy.matchcrest.matchers import ResponseCodeMatcher

assert_that(ResponseContext(response), ResponseCodeMatcher(200, timeout=10))
```

Matcher construction: `(expected_value, *, proofs, timeout, delay)` plus matcher-specific
options; `timeout`/`proofs`/`delay` drive the retry loop.

## Response matchers

| Matcher | Assertion |
|---------|-----------|
| `ResponseCodeMatcher(code)` | Status code (int/Enum/`"ok"` from `requests.codes`) |
| `ResponseHeadersByKeyMatcher(key, *, contains/startswith/endswith, count)` | Header presence by key |
| `ResponseHeadersByValueMatcher(value, *, key, contains/startswith/endswith)` | Header value by key |
| `ResponseBodyMatcher(body)` | Body equality |
| `JsonschemaMatcher(schema)` | JSON body conforms to a jsonschema |
| `JsonHasDataByKeyMatcher(key)` / `JsonHasNotDataByKeyMatcher(key)` | (No) data by key |
| `JsonContainsKeyMatcher(path)` | Nested key path exists |

## Value matchers

The options `any`/`in_array` control collection handling (see
[Overview](index.md#any-in_array)).

| Matcher | Assertion | Additional options |
|---------|-----------|--------------------|
| `ValueIsEqualMatcher(v)` / `ValueIsNotEqualMatcher(v)` | (Not) equal | `strict` (via `is`) |
| `ValueIsGreaterMatcher(v)` / `ValueIsLesserMatcher(v)` | Greater/less | `or_equal` |
| `ValueContainsMatcher(v)` / `ValueNotContainsMatcher(v)` | (Does not) contain | — |
| `ValueIsInMatcher(c)` / `ValueIsNotInMatcher(c)` | (Not) in a collection | — |
| `ValueLengthEqualMatcher(n)` / `Greater` / `Lesser` | Length equal/greater/less | — |
| `ValueContainsDictMatcher(d)` | Dict contains key/value pairs | — |
| `ValueStartsWithMatcher(s)` / `ValueEndsWithMatcher(s)` | Prefix/suffix | — |
| `ValueRegexMatcher(pattern)` | Regex match | — |
| `ValueIsEmpty()` / `ValueIsNotEmpty()` | Empty/not empty | — |
| `ValueIsUrlMatcher(*, is_live, allowed_protocols)` | Valid URL (+ optional liveness) | `is_live`, protocols |
| `ValueDateEqualMatcher(d)` / `Greater` / `Lesser` | Date equal/greater/less (via timestamp) | — |
| `ValueIsSubsetMatcher(s)` / `ValueIsDisjointMatcher(s)` | Subset/disjoint | — |

## Exception matchers

| Matcher | Assertion |
|---------|-----------|
| `RaisedExceptionMatcher((expected_types, raised_exc))` | The raised exception belongs to `expected_types` |
| `NotRaisedExceptionMatcher(raised_exc_or_None)` | No exception raised |

```python
assert_that(ExcCtx(call_result), RaisedExceptionMatcher(((ValueError,), raised_exc)))
```

## Writing a custom matcher

Extend `BaseMatcher` and implement the single hook `_assert(item) -> MatchResult`:

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

- The `BaseMatcher._matches` engine invokes `_assert` and owns retry, timeout, and
  reporting.
- On failure return `MatchResult(False, errors=..., expectations=...)` — both lists are
  mandatory.
