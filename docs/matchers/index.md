# Overview

The assertion machinery has two layers: **matchers** — the primitives that know *how* to
check a value — and the **assert facade** — the layer that knows *what* to check in an
HTTP response. They are designed as one system.

## Matchers — the check primitives

A **matcher** is a small object that encapsulates a single check — "the value equals X",
"the status code is 200", "the list contains Y". Instead of writing assert conditions by
hand, you declare the expectation and apply it:

```python
from goga_tool_pybuggy.matchcrest import assert_that, ValueIsEqualMatcher

assert_that(value, ValueIsEqualMatcher("admin"))
```

`assert_that(actual, matcher)` runs the check; on failure it raises `AssertionError`
with a ready-made report — what was expected and what the value actually was.

## Asserts — the facade over a response

In tests you normally do not construct matchers by hand. `response.expected` is the
facade: it resolves **what** to check — a status code, a header, a field in the body —
and exposes every check as a chained method:

```python
with post_clients_startup_get(json=Request(order_id=1)) as response:
    response.expected.has_status_code(200)          # response-level
    response.expected("items").has_length(3)         # field-level (dotted path)
    response.expected("$[0].name").equal_to("abc")   # field-level (jsonpath)
```

The facade handles the plumbing: paths are rooted at `data_key` / `error_key`, the
auto-check fires on first access to `response.expected`, and the polling baseline
(`assert_timeout` / `assert_delay`) comes from the configuration. The full method
catalog: [Assertions](asserts.md).

## How they work together

Every facade method resolves the value, wraps it into a context, and delegates the
judgement to a matcher — under the hood `has_length(3)` ends in
`assert_that(context, ValueLengthEqualMatcher(3))`:

```
response.expected("items").has_length(3)
        │                │
        │                └─ matcher: HOW to check (comparison, messages, retry)
        └─ assert layer: WHAT to check (path resolution, data_key rooting, polling)
```

- the **matcher** never touches HTTP — it only sees a context: `value` (what is
  checked), `key` (its label in messages), `update()` (refresh between retry attempts);
- the **facade** never implements a comparison — it only selects the value and picks
  the matcher.

Consequences in practice:

- **Same vocabulary both ways** — retry (`timeout`/`delay`/`proofs`), failure messages
  and collection modifiers (`any`/`in_array`) behave identically in the facade and in
  direct `assert_that`.
- **Escape hatch** — anything the facade does not cover, check directly:
  `assert_that(ctx, MyMatcher(...))`.
- **Custom matchers plug into the facade too** — one class with a single `_assert` hook
  (see [Writing a custom matcher](matchers.md#writing-a-custom-matcher)).

For direct matchers over arbitrary data, implement the context contract yourself —
`BaseContext` with the example lives in
[Matcher Catalog — data source](matchers.md#data-source-contract-basecontext).

The full contract and the matcher catalog: [Matcher Catalog](matchers.md).

## Retry

Every check accepts `timeout`/`delay` (and matchers additionally `proofs`) — the engine
re-runs the check, calling `update()` between attempts, until it passes or the timeout
expires. `None` (default) runs the check once:

```python
assert_that(ctx, ResponseCodeMatcher(200, timeout=10, delay=0.5))
```

In tests the baseline comes from the configuration (`assert_timeout` / `assert_delay`);
per-call `timeout`/`delay` kwargs override it for a single check. Between attempts the
response is re-fetched by replaying the same request — see
[Assertions — polling](asserts.md#polling).

## `hook` — transform the value before the check

A `hook` is any callable applied to the resolved value **before** the check runs. It is
available on the field entry — `response.expected(search, hook=...)` — and on every
drill-down `field(...)`; the order is fixed: dotted path → `index` → `hook`.

```python
# normalize before comparing
response.expected("name")(hook=str.upper).equal_to("ABC")

# hook as a computed value: derive, then assert
response.expected("price")(hook=lambda cents: cents / 100).equal_to(19.99)
```

The powerful pattern is **lookup by predicate over an array**: select the array root
(`expected()` without search) and let the hook find the element; `None` (no match)
fails the check:

```python
def _find_call(items, test_id):
    for item in items:
        if item["request"]["test_id"] == test_id:
            return item["response"]["body"]
    return None


response.expected()(hook=lambda items: _find_call(items, tid)).equal_to({"owner": "A1"})
```

Notes: a non-callable hook raises `TypeError`; `search`, `index` and `hook` combine in
one call, applied in that fixed order.

## `any` / `in_array`

Collection handling, available on value matchers and on field checks (both default
`False`):

- `in_array=True` — the value is treated as a collection and **every** element is
  checked.
- `any=True` (valid only with `in_array`) — the first successful element suffices;
  without `in_array` it raises `ValueError`.

```python
assert_that(ValCtx(tags), ValueIsEqualMatcher("admin", any=True, in_array=True))
```

```python
response.expected("items", in_array=True).equal_to(2, any=True)   # at least one == 2
```

## Also worth knowing

- **`.value`** — an `AssertField` property returning the resolved value **without** any
  check; useful for pytest's plain `assert` or logging.
- **Drill-down** — call the field again (`field(search=..., index=..., hook=...)`) to
  step deeper instead of writing one long path.
- **`reason`** — every check accepts a message prefix; it heads the failure output, use
  it to name the intent of the check.
- **Exception checks** — `raise_exc(expected_exc)` / `not_raise_exc()` context managers
  over a field: assert that accessing the value raises (or does not raise).
- **jsonpath rooting** — `$` in a jsonpath counts from the root key value
  (`data_key`/`error_key`), not from the whole body.
- **Pluggable assert classes** — `assert_field_class` / `assert_response_class` swap in
  your own `AssertField`/`Expected` subclasses (see
  [Configuration — pluggable assert classes](../configuration.md#pluggable-assert-classes)).
- **Custom matchers** — extend `BaseMatcher`, implement the single `_assert` hook, and
  use it anywhere via `assert_that` (see
  [Writing a custom matcher](matchers.md#writing-a-custom-matcher)).