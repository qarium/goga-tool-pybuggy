# goga_tool_pybuggy.matchcrest — response and value assertions with matchers

## Domain Overview

matchcrest is a Hamcrest matcher library for asserting HTTP responses, values, and exceptions.
The target audience is test authors who want declarative checks via `assert_that(actual, matcher)`.
The library provides ready-made patterns: the test author feeds data into a matcher context, selects the required matcher from the catalog, and applies the matcher via assert_that.

matchcrest depends on PyHamcrest: every matcher inherits `BaseMatcher`; `assert_that` runs the check.

---

## Facade

```python
from goga_tool_pybuggy.matchcrest import assert_that, ResponseCodeMatcher, ValueIsEqualMatcher
```

- `assert_that` — the assertion entry point (re-exported from hamcrest).
- Matchers — construct with `expected_value` (+ options) and apply to a data source.

---

## Assertion Model

A matcher is agnostic of HTTP/requests — it reads the value from a `BaseContext` context. Minimal scenario:

```python
from goga_tool_pybuggy.matchcrest import assert_that, BaseContext, ResponseCodeMatcher


class Ctx(BaseContext):
    def __init__(self, response):
        self._r = response

    @property
    def value(self):
        return self._r.status_code

    @property
    def key(self):
        return self._r.url

    def update(self):
        self._r = refetch(self._r.url)


assert_that(Ctx(response), ResponseCodeMatcher(200))
```

- `value` — the value under check; `key` — the source label (used in messages); `update()` — refetch for retry.

---

## Matcher Catalog — Responses (response)

| Matcher | Assertion |
|---|---|
| `ResponseCodeMatcher(code)` | status code (int/Enum/`"ok"` from requests.codes) |
| `ResponseHeadersByKeyMatcher(key, *, contains/startswith/endswith, count)` | header presence by key |
| `ResponseHeadersByValueMatcher(value, *, key, contains/startswith/endswith)` | header value by key |
| `ResponseBodyMatcher(body)` | body equality |
| `JsonschemaMatcher(schema)` | JSON body conforms to a jsonschema |
| `JsonHasDataByKeyMatcher(key)` / `JsonHasNotDataByKeyMatcher(key)` | (no) data by key |
| `JsonContainsKeyMatcher(path)` | nested key path exists |

```python
assert_that(Ctx(response), ResponseCodeMatcher("ok"))
assert_that(JsonCtx(response), JsonHasDataByKeyMatcher("data"))
```

## Matcher Catalog — Values (value)

The options `any`/`in_array` control collection handling: `in_array=True` makes the matcher treat the value as a collection; `any=True` (with `in_array`) makes the first success sufficient.

| Matcher | Assertion | Additional options |
|---|---|---|
| `ValueIsEqualMatcher(v)` / `ValueIsNotEqualMatcher(v)` | (not) equal | `strict` (via `is`) |
| `ValueIsGreaterMatcher(v)` / `ValueIsLesserMatcher(v)` | greater/less | `or_equal` |
| `ValueContainsMatcher(v)` / `ValueNotContainsMatcher(v)` | (does not) contain | — |
| `ValueIsInMatcher(c)` / `ValueIsNotInMatcher(c)` | (not) in a collection | — |
| `ValueLengthEqualMatcher(n)` / `Greater` / `Lesser` | length equal/greater/less | — |
| `ValueContainsDictMatcher(d)` | dict contains key/value pairs | — |
| `ValueStartsWithMatcher(s)` / `ValueEndsWithMatcher(s)` | prefix/suffix | — |
| `ValueRegexMatcher(pattern)` | regex match | — |
| `ValueIsEmpty()` / `ValueIsNotEmpty()` | empty/not empty | — |
| `ValueIsUrlMatcher(*, is_live, allowed_protocols)` | valid URL (+ optional liveness) | `is_live`, protocols |
| `ValueDateEqualMatcher(d)` / `Greater` / `Lesser` | date equal/greater/less (via timestamp) | — |
| `ValueIsSubsetMatcher(s)` / `ValueIsDisjointMatcher(s)` | subset/disjoint | — |

```python
assert_that(ValCtx(row), ValueIsEqualMatcher("admin"))
assert_that(ValCtx(tags), ValueIsInMatcher(["a", "b"], any=True, in_array=True))
```

## Matcher Catalog — Exceptions (error)

| Matcher | Assertion |
|---|---|
| `RaisedExceptionMatcher((expected_types, raised_exc))` | the raised exception belongs to expected_types |
| `NotRaisedExceptionMatcher(raised_exc_or_None)` | no exception raised |

```python
assert_that(ExcCtx(call_result), RaisedExceptionMatcher(((ValueError,), raised_exc)))
```

---

## Retry

Every matcher accepts `proofs`/`timeout`/`delay` — the `BaseMatcher` engine re-runs `_assert`, calling
`item.update()` between attempts, until the check passes or the timeout expires.

```python
assert_that(Ctx(response), ResponseCodeMatcher(200, timeout=10, delay=0.5))
```
