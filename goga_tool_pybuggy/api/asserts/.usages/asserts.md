# goga_tool_pybuggy.api.asserts — complete assert reference

## Domain

The sub-cell `goga_tool_pybuggy/api/asserts` provides the complete pybuggy assert layer
built on matchcrest. The target reader is a test project author who verifies responses
through generated fixtures. The practice describes **how to consume** asserts
(response-level and field-level), not how pybuggy implements them.

The layer consists of three entities:

- `AssertConfig` — a static check configuration (all fields optional);
- `Expected` — a two-level dispatcher: response-level checks plus the field-level entry
  via `Expected.__call__(search)`; it is also the default response-level class;
- `AssertField` — a field-level assert over a response body field value; it is also the
  default field-level class.

The consumer never creates these objects manually: pybuggy assembles `AssertConfig` when
the consumer calls the endpoint, builds `Expected` lazily on first access to
`response.expected`, and the consumer obtains the field-level assert from
`response.expected('path')`.

---

## Entry point

```python
from goga_tool_pybuggy.api.asserts import AssertField  # for a type hint
```

`AssertField` wraps the internal search context and provides matchcrest matchers over the
resolved value. The module also re-exports `Expected`, `AssertConfig`, and
`load_assert_class`, but a typical test receives them from `response.expected`.

---

## Common parameters of all check methods

Every check method on `Expected` and every check method on `AssertField` follows one
template: the method calls `assert_that(context, matcher, reason=...)` and returns its own
object (`Expected` or `AssertField`) for chaining.

Universal kwargs:

- `reason: str = ""` — the error message prefix (applied on every check).
- `any: bool = False` — controls element iteration; it takes effect **only** together
  with `in_array=True` (a field-level flag set on field entry or on drill-down). Under
  `in_array=True` there are two modes: `any=False` (default) requires a match for **all**
  list elements; `any=True` accepts **at least one** matching element. Passing `any=True`
  without `in_array=True` raises `ValueError` (`"any" can be used with "in_array" only`).
  `raise_exc`/`not_raise_exc` do not accept this parameter.
- `timeout: int | float | None = None` / `delay: int | float | None = None` — per-call
  override of the `AssertConfig` baseline for a **single** check (see Polling).

`.value` (an `AssertField` property) returns the resolved value **without running a
check**. Calling the field (`field(index=0)`, `field(search=...)`) drills one level deeper
and returns a new `AssertField`.

---

## AssertConfig — static configuration

| Field                  | Type                    | Purpose                                                                                                     |
|------------------------|-------------------------|-------------------------------------------------------------------------------------------------------------|
| `status`               | `int \| None`          | Expected success code; `None` disables the status autocheck                                                  |
| `data_key`             | `str \| None`          | "success" body key: present on positive, absent on negative; field-search root on the positive path          |
| `error_key`            | `str \| None`          | "error" body key: absent on positive, present on negative; field-search root on the negative path           |
| `schemas_dir`          | `Path \| None`         | Directory of `<status>*.json` schemas for auto-validation; `None`/missing — skip                            |
| `timeout`              | `int \| float \| None` | Polling timeout baseline (sec.); `None` — single attempt                                                    |
| `delay`                | `int \| float \| None` | Pause between polling attempts (sec.); `None` — matcher default                                             |
| `assert_field_class`   | `str \| None`          | Dotted `module:Class` of a custom `AssertField` subclass; `None` — built-in                                 |
| `assert_response_class`| `str \| None`          | Dotted `module:Class` of a custom `Expected` subclass; `None` — built-in                                    |

---

## Expected — response-level dispatcher

The consumer obtains `Expected` from `response.expected`. Response-level methods operate
on the whole response (status/headers/body); each method returns `Expected` for chaining.

### Response-level checks (complete list)

| Method                                           | Matcher                                                          | What it checks                                                                      |
|--------------------------------------------------|------------------------------------------------------------------|-------------------------------------------------------------------------------------|
| `has_status_code(code)`                          | `ResponseCodeMatcher`                                           | Response code equals `code` (`int`, a `requests.codes.<name>` string, or an `Enum`) |
| `has_header(key, value=None, ...)`               | `ResponseHeadersByKeyMatcher` / `ResponseHeadersByValueMatcher` | Header `key` exists; with `value` — the header value matches                         |
| `json_has_data_by_key(key)`                      | `JsonHasDataByKeyMatcher`                                       | Body contains key `key` with a non-`None` value                                     |
| `json_has_not_data_by_key(key)`                  | `JsonHasNotDataByKeyMatcher`                                    | Body lacks key `key` (or the key value is `None`)                                   |
| `json_contains_key(key)`                         | `JsonContainsKeyMatcher`                                        | Body contains key `key` (nested when passed a list)                                 |
| `jsonschema_is_valid(schema)`                    | `JsonschemaMatcher`                                             | Body validates against a json schema (dict or path to `.json`)                      |
| `jsonschemas_is_valid(schemas_dir, status_code)` | `JsonschemaMatcher`                                             | Body validates against the first `<status_code>*` file in the directory; skips when absent |

Parameter details:

- `has_status_code(code, *, reason="", timeout=None, delay=None)`: `code` is an `int`
  (e.g. `200`), a name string from `requests.codes` (e.g. `"ok"`→200), or an `Enum` (the
  method takes `.value`).
- `has_header(key, value=None, *, contains=None, startswith=None, endswith=None, count=None, reason="", timeout=None, delay=None)`:
  - without `value` — checks header presence (optional substring/prefix/suffix filter; optional `count` — exactly that many matches);
  - with `value` — checks the header value (exact equality by default, or `contains`/`startswith`/`endswith`);
  - the method compares **case-insensitively** for **both keys and values** (it lowercases the key and the expected value);
  - `count` combined with `value` → `ValueError`.
- `json_contains_key(key)`: `key` is a single string or an ordered list that the method
  uses to descend into nested objects.
- `jsonschema_is_valid(schema)`: `schema` is a `dict` or a path to a `.json` file (read
  as UTF-8).
- `jsonschemas_is_valid(schemas_dir, status_code)`: the method takes the **first** file
  in sort order whose name starts with the status string; a missing directory/file means
  a silent skip.

### Field-level entry

```python
field = response.expected("items")  # dotted path under data_key
field = response.expected("$.items[*]")  # jsonpath under data_key
field = response.expected()  # the whole value under data_key (array/object)
```

`Expected.__call__(search=None, *, index=None, hook=None, in_array=False)`:

- `search` — a dotted path (`a.b.c`) **or** a jsonpath (`$.a.b[*]`); pybuggy resolves it
  under the root key: `data_key` on the positive path, `error_key` on the negative path.
  `None` selects the whole value under that key (not "the whole response body"); when
  `data_key`/`error_key` are absent, the response body itself is the root;
- `index` — an optional list index that pybuggy applies after the search;
- `hook` — an optional callable applied to the resolved value (a non-callable →
  `TypeError`);
- `in_array` — makes pybuggy treat the value as a list for per-element `any`.

**Important jsonpath rule**: `$` counts **from the root key value**, not from the
response body. When `data_key="data"`, the expression `$.items[*]` resolves to
`body["data"]["items"]`, and `$[0].name` resolves to `body["data"][0]["name"]`. This one
rule governs both dotted paths and jsonpath.

The call returns `AssertField` for chaining.

### autocheck (internal)

The response wrapper calls `Expected.autocheck()` exactly once — at the lazy access
point — when `use_autocheck=True`. The `is_negative` flag selects the path:

- **positive:** status (when configured) → `error_key` absent → `data_key` present →
  validation against the `<status>*` schema (skip when the schema is absent);
- **negative:** `data_key` absent → `error_key` present (the path checks neither status
  nor json schema).

---

## AssertField — field-level matchers (complete list)

`AssertField` is a field-level assert over the resolved field value. Each method wraps a
matchcrest `assert_that` call and returns `AssertField` for chaining. All methods except
`raise_exc`/`not_raise_exc` accept `reason`/`any`/`timeout`/`delay`; methods with
additional parameters list them in the tables below.

The context resolves the path: under `data_key` on the positive path, under `error_key`
on the negative path; when both keys are absent, the path is relative to the whole body.
This rule covers **both dotted paths and jsonpath**: pybuggy evaluates jsonpath after it
prefixes the root key.

### Membership and containment

| Method                | Additional params | What it checks                                                                                                  |
|-----------------------|-------------------|-----------------------------------------------------------------------------------------------------------------|
| `contains(value)`     | —                 | Value **contains** `value` (Python `in`: substring for str, membership for list, **key** presence for dict)     |
| `not_contains(value)` | —                 | Value does **not** contain `value` (inverse of `in`)                                                            |
| `contains_dict(dct)`  | `dct: dict`       | Dict contains **all** key/value pairs from `dct`                                                                |
| `is_in(value)`        | —                 | Value is an **element of** `value` (`value` is a container)                                                     |
| `is_not_in(value)`    | —                 | Value is **not** an element of `value`                                                                          |
| `is_subset(value)`    | —                 | Iterable value is a subset of `value`                                                                           |
| `is_disjoint(value)`  | —                 | Iterable value shares no elements with `value`                                                                  |

```python
response.expected("name").contains("abc")
response.expected("tags").is_in(["x", "y"])
response.expected("filters").is_subset({"a": 1, "b": 2})
```

> Mind the argument direction: in `is_in(value)` / `is_subset(value)` /
> `is_disjoint(value)`, `value` is the **second** operand (the container/superset),
> while the resolved field is the first operand. `is_subset`/`is_disjoint` build sets
> via `set()`; therefore both the resolved value and `value` must be **iterable and
> hashable**; a non-iterable value → `ValueError`.

### Equality and emptiness

| Method                | Additional params    | What it checks                                     |
|-----------------------|----------------------|----------------------------------------------------|
| `equal_to(value)`     | `strict: bool=False` | Equals `value`; `strict=True` → identity (`is`)    |
| `not_equal_to(value)` | `strict: bool=False` | Not equal to `value`                               |
| `empty()`             | —                    | Empty/falsy                                        |
| `not_empty()`         | —                    | Non-empty/truthy                                   |

```python
response.expected("name").equal_to("abc")
response.expected("count").equal_to(1, strict=True)
response.expected("items").not_empty()
```

### Number comparison

| Method                | Additional params      | What it checks                        |
|-----------------------|------------------------|---------------------------------------|
| `greater_than(value)` | `or_equal: bool=False` | `>` `value`; `or_equal=True` → `>=`   |
| `lesser_than(value)`  | `or_equal: bool=False` | `<` `value`; `or_equal=True` → `<=`   |

```python
response.expected("count").greater_than(0)
response.expected("count").greater_than(0, or_equal=True)
```

### Length

| Method                      | What it checks                 |
|-----------------------------|--------------------------------|
| `has_length(value)`         | `len(resolved value) == value` |
| `has_length_greater(value)` | `len(resolved value) > value`  |
| `has_length_lesser(value)`  | `len(resolved value) < value`  |

```python
response.expected("items").has_length(3)
response.expected("items").has_length_greater(0)
```

### Strings and URLs

| Method                 | Additional params                                                  | What it checks                                                                                                              |
|------------------------|--------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| `startswith(value)`    | —                                                                  | String starts with `value`                                                                                                  |
| `endswith(value)`      | —                                                                  | String ends with `value`                                                                                                    |
| `match_regex(pattern)` | `pattern: str`                                                     | Matches the regex; `re.match` semantics — anchored to the **start** of the string (not `search`/`fullmatch`)                 |
| `is_url()`             | `is_live: bool=False`, `allowed_protocols: list[str] \| None=None` | Valid URL; `is_live=True` — reachable (GET → 2xx); `allowed_protocols` — allowed schemes (defaults to `['https','http']`)   |

```python
response.expected("email").match_regex(r"^[\w.]+@[\w.]+$")
response.expected("avatar").is_url()
response.expected("avatar").is_url(is_live=True, allowed_protocols=["https"])
```

### Dates

| Method                    | What it checks                                    |
|---------------------------|---------------------------------------------------|
| `has_date(value)`         | Date/datetime equals `value` (`date`/`datetime`)  |
| `has_date_greater(value)` | Date is greater than `value`                      |
| `has_date_lesser(value)`  | Date is less than `value`                         |

> The method compares **by timestamp** (`date_to_timestamp`): a `date` converts to
> midnight; a `datetime` converts to its own timestamp. Therefore a `date` and a
> `datetime` with different times may not match — compare values of the same type.

```python
from datetime import date

response.expected("created_at").has_date(date(2026, 1, 1))
response.expected("created_at").has_date_greater(date(2025, 1, 1))
```

### Exceptions (context managers)

| Method                    | Additional params             | What it checks                                     |
|---------------------------|-------------------------------|----------------------------------------------------|
| `raise_exc(expected_exc)` | `expected_exc: type \| tuple` | Accessing the value raises one of `expected_exc`  |
| `not_raise_exc()`         | —                             | Accessing the value raises nothing                 |

These methods are **context managers**: they yield the resolved value and verify that the
block raises (or does not raise) an exception. They do not accept `any`.

```python
with response.expected("missing").raise_exc(KeyError):
    ...  # field access inside the block must raise KeyError

with response.expected("ok").not_raise_exc() as value:
    assert value == "abc"
```

---

## Drill-down and arrays

- **Drill:** when the consumer calls `field(search=..., index=..., hook=...)` (or
  `field(index=0)`), the call returns a new `AssertField` over the extended context; the
  new context inherits the `timeout`/`delay` baseline. pybuggy applies dotted steps in
  order, then `index`, then `hook`.
- **in_array:** a field-level flag (set via `Expected.__call__(in_array=True)` or on
  drill-down). Under `in_array=True` pybuggy treats the value as a list: `any=False`
  (default) requires **all** elements to match; `any=True` — **at least one**.
- **All elements of an array** (jsonpath with `[*]` returns a list of values): when the
  consumer needs to verify that **every** element belongs to the allowed set, the
  consumer applies `is_in`/`is_subset` over the list. This is the "all satisfy" pattern,
  unlike `any=True` ("at least one").
- **Element absent among array elements**: the consumer selects the value list with
  jsonpath `$[*].field` and checks `not_contains` (for scalar values) or `is_disjoint`
  (set semantics). `not_contains` over a list without `in_array` checks membership of a
  value in the list — i.e. "the value occurs in no element". For string values this is
  an exact absence-equality check — unlike `in_array=True`, where `in` over strings
  works as a substring test.
- **Custom array element lookup**: when the test locates an element by predicate (several
  fields must match) rather than by index, the consumer writes a regular lookup function
  and passes it as a hook over the array root (`expected()` without search — the whole
  value under `data_key`). The hook returns the found element (`None` when nothing
  matches) — the assert stays inside the framework, and `None` fails the check; one chain
  therefore delivers both "found" and "equals the expected value".
- **Empty jsonpath result** (including `$[*]` over an empty array) raises
  `AssertionError` ("No results"). To check emptiness, the consumer uses
  `has_length(0)` over the root, not jsonpath.

```python
response.expected("items", in_array=True).equal_to(2, any=True)  # at least one == 2
response.expected("items")(index=0).equal_to(1)  # drill by index
response.expected("name")(hook=str.upper).equal_to("ABC")  # hook runs before comparison

# data_key is an array: non-emptiness / a specific element
response.expected().has_length_greater(0)  # the value under data_key (array) is non-empty
response.expected("$[0].name").equal_to("abc")  # data[0].name

# all elements: data[*].status is a list; is_subset guarantees every element belongs to the set
response.expected("$[*].status").is_subset(["active", "idle"])  # every status ∈ the set

# element absent: data[*].request.test_id is a value list; not_contains — none equals
response.expected("$[*].request.test_id").not_contains(test_id_b)


# custom predicate-based element lookup: a hook over the array root, then regular asserts
def _mock_body(items: list, test_id: str, path: str, method: str):
    for item in items:
        req = item["request"]
        if (req["test_id"], req["path"], req["method"]) == (test_id, path, method):
            return _normalize_body(item["response"]["body"])
    return None


response.expected()(hook=lambda items: _mock_body(items, test_id_a, "/api/shared", "POST")).equal_to({"owner": "A1"})
```

---

## Polling

`timeout`/`delay` from `AssertConfig` form the baseline. matchcrest repeats the check
until success or `timeout` expiry; between attempts matchcrest re-fetches the response
via `resq.http.Response.reload()` (an in-place replay of the same request) and pauses for
`delay`. Per-call `timeout`/`delay` kwargs override the baseline for a single check;
`None` (the default) means one attempt without polling. `AssertConfig`
(`timeout`/`delay`) is the source of the baseline.

## Pluggable classes

`assert_field_class`/`assert_response_class` (dotted `module:Class`) plug in custom
`AssertField`/`Expected` subclasses; the subclasses must inherit the built-in classes.
pybuggy loads both via `load_assert_class` at the point where it builds the
field/response class. `None` selects the built-in classes.

```python
Api(base_url=..., assert_field_class="myproj.asserts:StrictAssertField")
```

## pybuggy specifics

- contexts wrap `resq.http.Response`;
- polling (`timeout`/`delay`): between attempts pybuggy re-fetches the response by
  replaying the same request in place;
- pybuggy uses plain classes without a reporting layer (asserts depend on neither pytest
  nor step reporting);
- check configuration lives in `AssertConfig`; the dispatchers deliver it to the
  matchers.
