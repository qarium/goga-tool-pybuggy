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

In tests you normally do not construct matchers by hand. `response.expect` is the
facade: it resolves **what** to check — a status code, a header, a field in the body —
and exposes every check as a chained method:

```python
with post_clients_startup_get(json=Request(order_id=1)) as response:
    response.expect.has_status_code(200)               # response-level
    response.expect("data.items").has_length(3)        # field-level (dotted path)
    response.expect("$.data[0].name").equal_to("abc")  # field-level (jsonpath)
```

The facade handles the plumbing: paths are rooted at the response body root, the
auto-check fires on first access to `response.expect`, and the polling baseline
(`assert_timeout` / `assert_delay`) comes from the configuration. The full method
catalog: [Assertions](asserts.md).

## How they work together

Every facade method resolves the value, wraps it into a context, and delegates the
judgement to a matcher — under the hood `has_length(3)` ends in
`assert_that(context, ValueLengthEqualMatcher(3))`:

```
response.expect("data.items").has_length(3)
        │                    │
        │                    └─ matcher: HOW to check (comparison, messages, retry)
        └─ assert layer: WHAT to check (path resolution, polling)
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
available on the field entry — `response.expect(search, hook=...)` — and on every
drill-down `field(...)`; the order is fixed: dotted path → `index` → `hook`.

```python
# normalize before comparing
response.expect("name")(hook=str.upper).equal_to("ABC")

# hook as a computed value: derive, then assert
response.expect("price")(hook=lambda cents: cents / 100).equal_to(19.99)
```

The powerful pattern is **lookup by predicate over an array**: select the array
(`expect("data")` for the array under the envelope key, or `expect()` without search for
a root-level array) and let the hook find the element; `None` (no match)
fails the check:

```python
def _find_call(items, test_id):
    for item in items:
        if item["request"]["test_id"] == test_id:
            return item["response"]["body"]
    return None


response.expect("data")(hook=lambda items: _find_call(items, tid)).equal_to({"owner": "A1"})
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
response.expect("data.items", in_array=True).equal_to(2, any=True)   # at least one == 2
```

## Calling endpoints

The generated endpoint fixtures are called like functions and used as context managers.
Two paths exist:

```python
def test_initiate(post_clients_calls_initiate: Endpoint):
    with post_clients_calls_initiate(json=Request(order_id=1), params={":id": "42", "q": "x"}) as response:
        response.expect("data.items").has_length(3)


def test_initiate_error(post_clients_calls_initiate: Endpoint):
    with post_clients_calls_initiate.error(json={"name": "x"}) as response:
        response.expect.has_status_code(400)
        response.expect("error.message").not_empty()
```

- `endpoint(...)` — the **positive** path; `endpoint.error(...)` — the **negative** path
  (status and JSON schema are not auto-checked; the body is parsed as JSON only).
- `params=` takes query parameters (a pydantic model or a dict). Keys prefixed with `:`
  (e.g. `:id`) are **substituted into the route** (`/clients/:id` → `/clients/42`) and not
  sent as query parameters — the variable names and schemas come from the `vars` key of
  the endpoint's generated `meta.json` (see [CLI — generate](../cli/generate.md)).
- `json=` takes a pydantic model (serialized) or a raw dict. For schema-invalid requests
  pass a **raw dict** — a model raises `ValidationError` before the request is sent and
  the SUT is never tested. `data="{"` + an explicit `Content-Type` header tests malformed
  JSON; calling with no body arguments sends an empty body.
- `use_autocheck=False` (on the `Endpoint` or on a single call) disables the auto-check
  entirely — see [Assertions — auto-check](asserts.md#auto-check).

### Request-level keyword arguments

`endpoint(...)` / `endpoint.error(...)` forward the remaining keyword arguments to the
underlying `resq` verb:

- `auth=` — call-level authentication: a `requests` `AuthBase`, an object with an
  `.auth(request)` method, or a plain callable; combined with the `Api`-level authenticator
  (the call-level one wins on conflict).
- `headers=` / `cookies=` — call-level values; merged over the `Api`-level defaults
  (call-level keys win).
- `use_aliases=True` — serialize a pydantic `params`/`json` model with `by_alias`.

```python
from requests.auth import HTTPBasicAuth

endpoint(json=Request(id=1), params={":id": "42", "q": "x"}, auth=HTTPBasicAuth("u", "p"))
```

The `Api` client itself is configured by the plugin from the tool config — base URL,
default auth/headers/cookies, the assert baseline, and the sync-only resq `adapter`
(`"requests"`; `"httpx"` is async and rejected until an async stack exists). A per-endpoint
`adapter=` may be added by hand to a generated fixture; only `"requests"` is currently
accepted.

### Where `schemas_dir` comes from — frame inspection

The generated fixture resolves `schemas/` via `inspect.stack()[1]`: `Endpoint` reads
`__file__` from its caller's frame and computes `Path(file).parent / "schemas"`. Therefore:

- Create the `Endpoint` **directly in the fixture function body** (`api.py`) — `schemas/`
  lands next to that file, as generated.
- Moving the construction into a helper or a module-level statement yields a foreign
  `__file__` and the JSON-schema part of the auto-check **silently skips** — keep the
  `return Endpoint(...)` line inside the fixture.

See [Assertions — auto-check](asserts.md#auto-check) for what is verified against those
schema files.

## Also worth knowing

- **`.value`** — an `AssertField` property returning the resolved value **without** any
  check; useful for pytest's plain `assert` or logging.
- **Drill-down** — call the field again (`field(search=..., index=..., hook=...)`) to
  step deeper instead of writing one long path.
- **`reason`** — every check accepts a message prefix; it heads the failure output, use
  it to name the intent of the check.
- **Exception checks** — `raise_exc(expected_exc)` / `not_raise_exc()` context managers
  over a field: assert that accessing the value raises (or does not raise).
- **jsonpath rooting** — `$` in a jsonpath counts from the root of the response body;
  spell out the full path including the envelope key (`$.data.items[*]`).
- **Pluggable assert classes** — `assert_field_class` / `assert_response_class` swap in
  your own `AssertField`/`Expect` subclasses (see
  [Configuration — pluggable assert classes](../configuration.md#pluggable-assert-classes)).
- **Custom matchers** — extend `BaseMatcher`, implement the single `_assert` hook, and
  use it anywhere via `assert_that` (see
  [Writing a custom matcher](matchers.md#writing-a-custom-matcher)).