# goga_tool_pybuggy.api — consuming the runtime from test fixtures

## Domain

The `goga_tool_pybuggy/api` cell runtime executes HTTP requests from generated fixtures and
verifies the response. The audience is the test project author who consumes the generated
`pybuggy` fixtures. The document provides ready-made templates for consuming the facade and
a detailed API reference: `Api`, `Endpoint`, `ResponseWrapper`, `Expected`, `AssertField`,
`Auth`.

pybuggy ships **classes only**. The `Api` instance for fixtures and the generated endpoint
fixtures are provided by a separate pybuggy pytest plugin (see "Plugin wiring").

---

## Facade

```python
from goga_tool_pybuggy.api import Api, Endpoint, ResponseWrapper, Expected, AssertField, Auth
```

| Entity | Purpose |
|----------|------------|
| `Api` | HTTP client (a composition over `resq.Session`); stores auth/headers/cookies/`data_key`/`error_key` and assert settings, and injects them into every request |
| `Endpoint` | A callable route: `endpoint(json=...)` performs the request and returns a `ResponseWrapper` |
| `ResponseWrapper` | A context manager over the response; `.response` is the raw `resq.http.Response`, `.expected` is the `Expected` |
| `Expected` | A two-level assertion dispatcher built on matchcrest (response-level methods + `__call__` for field-level) |
| `AssertField` | A field-level assertion over a field value; created via `Expected.__call__`, re-exported for type hints |
| `Auth` | A structural protocol for type-hinting a call-level authenticator (any object with an `auth(request)` method) |

`CombineAuth`/`AuthWrapper` are internal (they combine auth in `Endpoint._call`) and are not
part of the facade.

---

## Api — reference

### Constructor

```python
Api(
    base_url: str,
    auth: AuthBase | None = None,
    headers: dict[str, str] | None = None,
    cookies: SimpleCookie | None = None,
    timeout: float | None = None,
    data_key: str | None = None,
    error_key: str | None = None,
    assert_timeout: int | float | None = None,
    assert_delay: int | float | None = None,
    assert_field_class: str | None = None,
    assert_response_class: str | None = None,
    adapter: str = "requests",
)
```

| Parameter | Purpose |
|----------|------------|
| `base_url` | Base URL for the `resq.Session`; concatenated with each request's path |
| `auth` | A `requests.AuthBase` applied to all requests (unless overridden at call level); read/write |
| `headers` | Default headers merged into every request (call-level wins) |
| `cookies` | Default cookies |
| `timeout` | Network timeout (passed to `resq.Session`, not re-supplied per request) |
| `data_key` | The "success" body key (e.g. `"data"`): a fallback for an `Endpoint` without its own `data_key`; **defines the root of field assertions and of the auto-check on the positive path** — always set it, otherwise the checks look past the envelope |
| `error_key` | The "error" body key (e.g. `"error"`): a fallback for an `Endpoint` without its own `error_key`; **defines the root of field assertions and of the auto-check on the negative path** — always set it |
| `assert_timeout` | Baseline assertion polling timeout (distinct from the network `timeout`); goes into every `AssertConfig` |
| `assert_delay` | Baseline pause between polling attempts; goes into every `AssertConfig` |
| `assert_field_class` | Dotted `module:Class` of a custom `AssertField` subclass |
| `assert_response_class` | Dotted `module:Class` of a custom `Expected` subclass |
| `adapter` | Default resq adapter the composed session is built with. Only `"requests"` (sync): `"httpx"` is async in resq and is rejected until an async stack appears. Per-endpoint override — via `Endpoint(adapter=...)` (see below) |

### Properties

| Property | Type | Access | Purpose |
|----------|------|--------|------------|
| `base_url` | `str` | RO | Base URL from the `resq.Session` |
| `adapter` | `str` | RO | Default resq adapter fixed in the constructor (`"requests"` in the sync runtime); routes each request to the cached session with the matching adapter |
| `auth` | `AuthBase \| None` | **RW** | Stored auth (getter/setter) |
| `headers` | `dict[str, str]` | RO | Default headers (an empty dict if not set) |
| `cookies` | `SimpleCookie \| None` | RO | Default cookies |
| `data_key` | `str \| None` | RO | Success-key fallback for endpoints |
| `error_key` | `str \| None` | RO | Error-key fallback for endpoints |
| `assert_timeout` | `int \| float \| None` | RO | Baseline assertion polling timeout |
| `assert_delay` | `int \| float \| None` | RO | Baseline polling pause |
| `assert_field_class` | `str \| None` | RO | Dotted path of the custom `AssertField` |
| `assert_response_class` | `str \| None` | RO | Dotted path of the custom `Expected` |

### Methods

- `request(method, url_path, **kwargs) -> resq.http.Response` — a single HTTP request:
  serializes the pydantic `params`/`json` (with optional `by_alias` via `use_aliases`),
  substitutes `:name` path parameters, injects auth/headers/cookies with call-level priority,
  resolves the effective adapter (call-level `adapter`, otherwise the `Api` default), selects
  the matching cached session, and dispatches to the resq verb
  (`get/post/put/delete/patch/head/options`). It never passes `timeout`/`delay`/polling
  options or the `adapter` itself into the verb.
- `close()` — delegates to the public `resq.Session.close()` for the composed session and
  every cached override session; called in the `api` fixture teardown. In sync mode it is
  a no-op by resq design: the `requests.Session` pool is released by the garbage collector.
  No httpx client is created (pybuggy is synchronous).

---

## Endpoint — reference

### Constructor

```python
Endpoint(
    api: Api,
    url_path: str,
    method: str,
    status: int | None = 200,
    use_autocheck: bool = True,
    data_key: str | None = None,
    error_key: str | None = None,
    adapter: str | None = None,
)
```

| Parameter | Purpose |
|----------|------------|
| `api` | The `Api` client the request is made with |
| `url_path` | Route path (`:name` placeholders are possible, substituted by `Api.request`) |
| `method` | HTTP verb |
| `status` | Expected success code; an Enum is normalized to `.value`; `None` disables the status auto-check |
| `use_autocheck` | Runs the lazy auto-check on first access to `response.expected` |
| `data_key` | Per-endpoint success key; `None` → falls back to `api.data_key` |
| `error_key` | Per-endpoint error key; `None` → falls back to `api.error_key` |
| `adapter` | Per-endpoint resq adapter; passed to `api.request`. `None` → falls back to the `Api` default. Only `"requests"` (sync) — `"httpx"` is async and is rejected until an async stack exists |

`schemas_dir` is resolved automatically via frame inspection (see below).

### Methods and properties

- `endpoint(**kwargs) -> ResponseWrapper` — the **positive** path (`is_negative=False`).
- `endpoint.error(**kwargs) -> ResponseWrapper` — the **negative** path (`is_negative=True`):
  status and JSON schema are not checked in the auto-check.
- `url_path -> str`, `method -> str` — the path and the verb (RO).
- `adapter -> str | None` — the per-endpoint resq adapter (RO); `None` = fallback to the
  `Api` default.

Both paths delegate to the internal `_call`, which copies kwargs (without mutating the
caller's dict), pops `auth`/`use_autocheck`, injects its own `adapter`, resolves the
data/error key, assembles the `AssertConfig` (with the `assert_*` options from `Api`),
performs the request, and wraps the response.

---

## ResponseWrapper — reference

A context manager over `resq.http.Response`.

| Element | Purpose |
|---------|------------|
| `.response -> resq.http.Response` | Raw response (available only through this property; the wrapper does not proxy resq attributes) |
| `.expected -> Expected` | The assertion dispatcher. Built **lazily** on first access; with `use_autocheck=True`, `autocheck()` then runs once (with the flag memoized). With `config.assert_response_class`, a custom `Expected` subclass is loaded |
| `with endpoint(...) as response:` | Context entry; the exit is **without** exception suppression (no report is generated) |

---

## Plugin wiring

The `api` fixture (assembles an `Api` from configuration options) and the generated endpoint
fixtures are provided by a separate pybuggy pytest plugin — enable it in the root `conftest.py`
of the test project.

**You do not need to write your own `api` fixture** — the plugin already provides it.

---

## Template: generated endpoint fixture

```python
# api/<spec>/<id>/api.py
import pytest
from goga_tool_pybuggy.api import Endpoint, Api
from pydantic import BaseModel


class Request(BaseModel):
    order_id: int


@pytest.fixture(scope="function")
def post_clients_calls_initiate(api: Api) -> Endpoint:
    return Endpoint(api, "/clients/calls/initiate", method="POST")
```

The `Endpoint` is created **directly in the fixture function body** — a mandatory requirement
of frame inspection (see below).

---

## Template: positive check

```python
def test_initiate(post_clients_calls_initiate: Endpoint):
    with post_clients_calls_initiate(json=Request(order_id=1)) as response:
        response.expected.has_status_code(200)
```

On first access to `response.expected` (if `use_autocheck=True`) the auto-check fires
**once**. **Positive path:** status == expected → `error_key` absent → `data_key` present →
body validation against `schemas/<status>*.json`. An explicit `has_status_code(200)`
duplicates only the status part — that is normal.

---

## Template: negative check

```python
def test_initiate_error(post_clients_calls_initiate: Endpoint):
    with post_clients_calls_initiate.error(json=Request(order_id=-1)) as response:
        response.expected.has_status_code(400)
        response.expected("message").not_empty()
```

`.error(...)` is the negative path: status and JSON schema are **not
checked** in the auto-check, so the status must be verified explicitly. **Negative auto-check
path:** `data_key` absent → `error_key` present. Field paths resolve under
`error_key` (e.g. `response.expected("message")` → `body["error"]["message"]`).

If the body is schema-invalid (a missing required field, a wrong type, an empty body,
malformed JSON), the `Request` model cannot be built — bypass pydantic by passing a raw
`dict` (`json={...}`), `data="{"`, or by calling `.error()` with no arguments
(see "Request parameters"):

```python
# a required field is missing — a dict, bypassing pydantic
with post_clients_calls_initiate.error(json={"name": "x"}) as response:
    response.expected.has_status_code(400)
    response.expected("status_code").equal_to(400)

# empty body
with post_clients_calls_initiate.error() as response:
    response.expected.has_status_code(400)

# malformed JSON — raw data + an explicit Content-Type
with post_clients_calls_initiate.error(data="{", headers={"Content-Type": "application/json"}) as response:
    response.expected.has_status_code(400)
```

---

## Template: field-level value check

Calling `response.expected(path)` (the dispatcher used as a function) returns an `AssertField`
for checks on a specific field. The path is **relative to the root**: on the positive path
the root is `data_key`, on the negative path — `error_key`; without `data_key`/`error_key`
the path is absolute to the response body.

```python
def test_initiate(post_clients_calls_initiate: Endpoint):
    with post_clients_calls_initiate(json=Request(order_id=1)) as response:
        # the path is relative to data_key ("data"): items → body["data"]["items"]
        response.expected("items").has_length(3)
        response.expected("items", in_array=True).equal_to(2, any=True)
        response.expected("name").equal_to("abc")

        # drill-down: index/hook
        response.expected("items")(index=0).equal_to(1)
        response.expected("name")(hook=str.upper).equal_to("ABC")

        # jsonpath — for nested arrays/filters
        response.expected("$.items[*]", in_array=True).equal_to(2, any=True)
```

---

## Request parameters

`endpoint(json=...)` / `endpoint.error(...=...)` accept the resq-verb arguments:

- `params=` — a pydantic `BaseModel` (serialized via `model_dump`) or a `dict`
  (query parameters).
- `json=` — a pydantic `BaseModel` (serialized) or a `dict`. For schema-invalid requests
  (a missing required field, a wrong value type), **pass a raw `dict`**,
  not a model — otherwise pydantic raises a `ValidationError` before the request is sent,
  and the SUT is never tested.
- `data=` — a raw body (string/bytes), sent as is, bypassing pydantic serialization.
  Used to test the handling of malformed JSON (e.g. `data="{"`). For a correct
  Content-Type, pass it in `headers=`.
- without `json=`/`data=` — the request is sent without a body (an empty body); tests
  the handling of an empty request.
- path parameters — keys in `params` prefixed with `:` (for example `:id`) are substituted
  into `url_path` and are **not** sent to the query.
- `auth=` — call-level authentication; accepts an `AuthBase`, an `Auth` protocol object
  (with an `.auth(request)` method), or a callable. When passed, it is **combined**
  with `Api.auth` via `CombineAuth` (order: `AuthBase` directly → protocol → callable →
  otherwise `TypeError`); without call-level `auth`, `Api.auth` applies.
- `headers=` / `cookies=` — call-level; they win over the `Api` defaults.
- `use_aliases=` (bool) — controls pydantic `by_alias` during serialization.
- `use_autocheck=` (bool) — a call-level override of the lazy auto-check; by default it is
  taken from `Endpoint.use_autocheck`. `use_autocheck=False` on a specific call disables
  the auto-check for that call only; `use_autocheck=True` turns it back on.

```python
endpoint(json=Request(id=1), params={":id": "42", "q": "x"}, auth=MyAuth())
```

---

## Auto-check — what exactly is verified

Runs once on lazy access to `response.expected`, if `use_autocheck=True`. The path is
determined by the `is_negative` flag:

- **Positive** (`endpoint(...)`): status (if set) → `error_key` absent → `data_key`
  present → validation against the first `schemas/<status>*.json`
  (skipped if the directory/file does not exist).
- **Negative** (`endpoint.error(...)`): `data_key` absent → `error_key` present.
  Status and JSON schema are **not** checked.

`use_autocheck=False` (on the `Endpoint` or on a call) disables the auto-check entirely —
then verify everything explicitly via `response.expected.*`.

---

## Frame inspection — a mandatory requirement

The `Endpoint` resolves the `schemas/` directory via `inspect.stack()[1]`: it takes the
caller's frame, reads `__file__` from its `f_globals`, then computes
`Path(file).parent / "schemas"`. Therefore:

- Create the `Endpoint` **directly in the fixture function** (`api.py`) — then the
  caller frame is the fixture with the correct `__file__`, and `schemas/` lands next to
  that `api.py`.
- Creating the `Endpoint` elsewhere (a top-level module, a helper function) yields a foreign
  `__file__` or `None` → `schemas_dir` resolves incorrectly / to `None`, and the JSON-schema
  auto-validation **silently skips**.

If `schemas/` or a file for the status is missing — the auto-validation is skipped as well,
without an error.

---

## resq adapter (sync-only)

The `Api` owns the resq adapter: it builds one cached `resq.Session` per adapter name
(the default being the composed session `_client`) and routes each request to the session
with the matching adapter. The effective adapter of a request = the call-level `adapter`
(from `Endpoint`), otherwise the `Api` default.

Only `"requests"` is supported in the sync runtime. `"httpx"` is async in resq (the verbs
return coroutines wrapped in `AsyncResponse`) and is **rejected** with `ValueError` at `Api`
construction and at request time — until an async stack appears in pybuggy.

```python
# The default for the whole api fixture — via Api:
@pytest.fixture(scope="function")
def api() -> Api:
    return Api(base_url="https://api.example.com", adapter="requests")


# Per-endpoint override — via Endpoint (None = fallback to the Api default):
@pytest.fixture(scope="function")
def post___admin___api_v1_mocks_add(api: Api) -> Endpoint:
    return Endpoint(api, "/__admin__/api_v1/mocks/add", method="POST", adapter="requests")
```

The fixture generator does not emit `adapter` (it is opt-in through the default) — add it
by hand whenever an explicit or overridden adapter is needed. Different endpoints may use
different values; `Api` caches one session per unique adapter name.

---

## Pluggable classes

Custom assert subclasses are plugged in via the `Api`-level options
(`assert_field_class` / `assert_response_class`, dotted `module:Class`):

- the class must inherit from the built-in one (`AssertField` / `Expected` respectively);
- it is loaded via `load_assert_class` at the point where the field/response class is built;
- `None` (the default) — the built-in classes.

```python
class StrictAssertField(AssertField): ...


Api(base_url=..., assert_field_class="myproj:StrictAssertField")
```
