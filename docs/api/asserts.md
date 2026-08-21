# Assertions — `Expected` and `AssertField`

The complete pybuggy assert layer, built on [matchcrest](../matchcrest/index.md). You
never create these objects manually: pybuggy assembles the `AssertConfig` when you call
the endpoint, builds `Expected` lazily on first access to `response.expected`, and hands
you the field-level assert from `response.expected('path')`.

```python
from goga_tool_pybuggy.api.asserts import AssertField   # for a type hint
```

## Common parameters

Every check method follows one template — it calls `assert_that` internally and returns
its own object for chaining. Universal kwargs:

- `reason: str = ""` — the error message prefix.
- `any: bool = False` — element-iteration mode; effective **only** with `in_array=True`:
  `any=False` (default) requires **all** list elements to match, `any=True` — at least
  one. Passing `any=True` without `in_array=True` raises `ValueError`.
- `timeout` / `delay` — per-call override of the polling baseline for a **single** check
  (see [Polling](#polling)).

`.value` (an `AssertField` property) returns the resolved value **without** a check;
calling the field (`field(index=0)`, `field(search=...)`) drills one level deeper.

## `Expected` — response-level checks

Obtained from `response.expected`; each method returns `Expected` for chaining.

| Method | What it checks |
|--------|----------------|
| `has_status_code(code)` | Response code equals `code` (`int`, a `requests.codes` name like `"ok"`, or an `Enum`) |
| `has_header(key, value=None, ...)` | Header `key` exists; with `value` — the value matches |
| `json_has_data_by_key(key)` | Body contains key `key` with a non-`None` value |
| `json_has_not_data_by_key(key)` | Body lacks key `key` (or its value is `None`) |
| `json_contains_key(key)` | Body contains key `key` (nested when passed a list) |
| `jsonschema_is_valid(schema)` | Body validates against a json schema (dict or `.json` path) |
| `jsonschemas_is_valid(schemas_dir, status_code)` | Body validates against the first `<status_code>*` file in the directory; silently skips when absent |

`has_header(key, value=None, *, contains=None, startswith=None, endswith=None, count=None)`:
without `value` — header presence (optional substring/prefix/suffix filter, optional
`count`); with `value` — the header value (exact, or `contains`/`startswith`/`endswith`).
Keys and values compare **case-insensitively**; `count` combined with `value` →
`ValueError`.

## Field-level entry

```python
field = response.expected("items")      # dotted path under the root key
field = response.expected("$.items[*]") # jsonpath under the root key
field = response.expected()             # the whole value under the root key
```

`Expected.__call__(search=None, *, index=None, hook=None, in_array=False)`:

- `search` — a dotted path (`a.b.c`) **or** a jsonpath; resolved under the root key:
  `data_key` on the positive path, `error_key` on the negative path. `None` selects the
  whole value under that key; when the keys are absent, the response body is the root.
- `index` — an optional list index applied after the search.
- `hook` — a callable applied to the resolved value (a non-callable → `TypeError`).
- `in_array` — treat the value as a list for per-element `any`.

**jsonpath rule**: `$` counts **from the root key value**, not from the response body.
With `data_key="data"`: `$.items[*]` → `body["data"]["items"]`; `$[0].name` →
`body["data"][0]["name"]`.

## `AssertField` — field-level check catalog

The context resolves the path under `data_key` (positive) or `error_key` (negative);
without both keys — relative to the whole body. All methods except `raise_exc` /
`not_raise_exc` accept `reason`/`any`/`timeout`/`delay`.

### Membership and containment

| Method | What it checks |
|--------|----------------|
| `contains(value)` | Value **contains** `value` (substring for str, membership for list, key presence for dict) |
| `not_contains(value)` | Value does not contain `value` |
| `contains_dict(dct)` | Dict contains all key/value pairs from `dct` |
| `is_in(value)` | Value is an element of `value` (`value` is the container) |
| `is_not_in(value)` | Value is not an element of `value` |
| `is_subset(value)` | Iterable value is a subset of `value` |
| `is_disjoint(value)` | Iterable value shares no elements with `value` |

> Argument direction: in `is_in`/`is_subset`/`is_disjoint`, `value` is the **second**
> operand (the container/superset). `is_subset`/`is_disjoint` build sets via `set()` —
> both operands must be iterable and hashable.

```python
response.expected("name").contains("abc")
response.expected("tags").is_in(["x", "y"])
response.expected("filters").is_subset({"a": 1, "b": 2})
```

### Equality and emptiness

| Method | What it checks |
|--------|----------------|
| `equal_to(value)` | Equals `value`; `strict=True` → identity (`is`) |
| `not_equal_to(value)` | Not equal |
| `empty()` / `not_empty()` | Empty/falsy — non-empty/truthy |

### Number comparison

| Method | What it checks |
|--------|----------------|
| `greater_than(value)` | `>` value; `or_equal=True` → `>=` |
| `lesser_than(value)` | `<` value; `or_equal=True` → `<=` |

### Length

| Method | What it checks |
|--------|----------------|
| `has_length(value)` | `len(value) == value` |
| `has_length_greater(value)` / `has_length_lesser(value)` | Strictly greater/less |

### Strings and URLs

| Method | What it checks |
|--------|----------------|
| `startswith(value)` / `endswith(value)` | Prefix / suffix |
| `match_regex(pattern)` | `re.match` semantics — anchored to the **start** |
| `is_url()` | Valid URL; `is_live=True` — reachable (GET → 2xx); `allowed_protocols` — allowed schemes (default `['https','http']`) |

### Dates

| Method | What it checks |
|--------|----------------|
| `has_date(value)` | Date/datetime equals `value` |
| `has_date_greater(value)` / `has_date_lesser(value)` | Strictly greater/less |

> Dates compare **by timestamp**: a `date` converts to midnight, a `datetime` to its own
> timestamp — compare values of the same type.

### Exceptions (context managers)

| Method | What it checks |
|--------|----------------|
| `raise_exc(expected_exc)` | Accessing the value raises one of `expected_exc` |
| `not_raise_exc()` | Accessing the value raises nothing |

```python
with response.expected("missing").raise_exc(KeyError):
    ...

with response.expected("ok").not_raise_exc() as value:
    assert value == "abc"
```

## Drill-down and arrays

- **Drill**: `field(search=..., index=..., hook=...)` returns a new `AssertField` over the
  extended context (dotted steps → `index` → `hook`, in that order).
- **`in_array`**: `any=False` (default) requires **all** elements to match; `any=True` —
  at least one.
- **All elements satisfy a set**: select the value list with jsonpath `$[*].field` and
  apply `is_subset` / `is_in` over the list.
- **Element absent among array elements**: `$[*].field` + `not_contains` (scalars) or
  `is_disjoint` (set semantics).
- **Custom element lookup by predicate**: pass a regular lookup function as a `hook` over
  the array root (`expected()` without search); the hook returns the found element
  (`None` on no match — `None` fails the check).
- **Empty jsonpath result** (including `$[*]` over an empty array) raises
  `AssertionError` ("No results") — check emptiness via `has_length(0)` over the root.

```python
response.expected("items", in_array=True).equal_to(2, any=True)   # at least one == 2
response.expected("items")(index=0).equal_to(1)                   # drill by index
response.expected("name")(hook=str.upper).equal_to("ABC")         # hook before comparison

response.expected().has_length_greater(0)          # the data_key value is non-empty
response.expected("$[0].name").equal_to("abc")     # data[0].name

response.expected("$[*].status").is_subset(["active", "idle"])          # every ∈ set
response.expected("$[*].request.test_id").not_contains(test_id_b)       # none equals


def _mock_body(items, test_id, path, method):
    for item in items:
        req = item["request"]
        if (req["test_id"], req["path"], req["method"]) == (test_id, path, method):
            return _normalize_body(item["response"]["body"])
    return None


response.expected()(hook=lambda items: _mock_body(items, tid, "/api/shared", "POST")).equal_to({"owner": "A1"})
```

## Polling

`timeout`/`delay` from the configuration form the baseline. The check repeats until it
passes or `timeout` expires; between attempts the response is re-fetched **in place** by
replaying the same request (`resq.http.Response.reload()`), pausing `delay`. Per-call
`timeout`/`delay` kwargs override the baseline for a single check; `None` means one
attempt without polling.

## Pluggable classes

`assert_field_class` / `assert_response_class` (dotted `module:Class`) plug in custom
subclasses; they must inherit the built-ins and are loaded at the point where the class
is built:

```python
Api(base_url=..., assert_field_class="myproj.asserts:StrictAssertField")
```
