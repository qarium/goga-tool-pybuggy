# matchcrest — Overview & `assert_that`

matchcrest is a Hamcrest-style matcher library for asserting HTTP responses, values, and
exceptions. You feed data into a matcher **context**, select a matcher from the catalog,
and apply it via `assert_that`.

```python
from goga_tool_pybuggy.matchcrest import assert_that, ResponseCodeMatcher, ValueIsEqualMatcher
```

matchcrest depends on PyHamcrest: every matcher inherits `BaseMatcher`;
`assert_that(actual, matcher)` runs the check.

## Assertion model

A matcher is agnostic of HTTP and `requests` — it reads the value only from a
`BaseContext` context:

```python
from goga_tool_pybuggy.matchcrest import assert_that, BaseContext, ResponseCodeMatcher


class Ctx(BaseContext):
    def __init__(self, response):
        self._r = response

    @property
    def value(self):
        return self._r.status_code      # the value under check

    @property
    def key(self):
        return self._r.url              # the source label (used in messages)

    def update(self):
        self._r = refetch(self._r.url)  # refetch between retry attempts


assert_that(Ctx(response), ResponseCodeMatcher(200))
```

In pybuggy tests you rarely touch this layer directly — the
[assert facade](../api/asserts.md) wraps it end to end.

## Catalog overview

The full catalog with constructor options lives in
[Matcher Catalog](matchers.md). Summary:

- **Responses**: status code, headers by key/value, body equality, JSON-schema
  validation, data-by-key presence/absence, nested key paths.
- **Values**: equality, comparison, containment, membership, length, prefix/suffix,
  regex, emptiness, URL validity (with optional liveness), dates, subset/disjoint.
- **Exceptions**: raised-exception type membership, no-exception-raised.

## Retry

Every matcher accepts `proofs`/`timeout`/`delay` — the engine re-runs the check, calling
`item.update()` between attempts, until it passes or the timeout expires:

```python
assert_that(Ctx(response), ResponseCodeMatcher(200, timeout=10, delay=0.5))
```

## `any` / `in_array`

Value matchers accept `any` and `in_array` (both default `False`):

- `in_array=True` — the matcher treats `item.value` as a collection and checks every
  element.
- `any=True` (valid only with `in_array`) — the first successful element suffices.

```python
assert_that(ValCtx(tags), ValueIsEqualMatcher("admin", any=True, in_array=True))
```

## Helpers

The library also ships utility routines — a retry loop, URL helpers, date conversion,
and the `allow_failure` decorator: [Helpers](helpers.md).
