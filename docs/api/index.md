# HTTP API — `Api`, `Endpoint`, `ResponseWrapper`

The `goga_tool_pybuggy.api` runtime executes HTTP requests from generated fixtures and
verifies the response. pybuggy ships **classes only** — the `Api` instance and the
generated endpoint fixtures are provided by the [pytest plugin](../plugin/index.md).

```python
from goga_tool_pybuggy.api import Api, Endpoint, ResponseWrapper, Expected, AssertField, Auth
```

| Entity | Purpose |
|--------|---------|
| `Api` | HTTP client (a composition over `resq.Session`); stores auth/headers/cookies/`data_key`/`error_key` and assert settings, injects them into every request |
| `Endpoint` | A callable route: `endpoint(json=...)` performs the request and returns a `ResponseWrapper` |
| `ResponseWrapper` | A context manager over the response; `.response` is the raw `resq.http.Response`, `.expected` is the `Expected` |
| `Expected` | A two-level assertion dispatcher (response-level methods + `__call__` for field-level) |
| `AssertField` | A field-level assertion over a field value; created via `Expected.__call__` |
| `Auth` | A structural protocol for type-hinting a call-level authenticator (`auth(request)`) |

## `Api` — reference

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
|-----------|---------|
| `base_url` | Base URL for the `resq.Session`; concatenated with each request path |
| `auth` | A `requests.AuthBase` applied to all requests (unless overridden at call level); read/write |
| `headers` | Default headers merged into every request (call-level wins) |
| `cookies` | Default cookies |
| `timeout` | Network timeout (lives on the session; not re-supplied per request) |
| `data_key` | The "success" body key (e.g. `"data"`); fallback for endpoints without their own; **defines the root of field assertions and of the positive auto-check** — always set it |
| `error_key` | The "error" body key (e.g. `"error"`); fallback for endpoints without their own; **root of the negative auto-check** — always set it |
| `assert_timeout` / `assert_delay` | Baseline assertion-polling settings; go into every `AssertConfig` |
| `assert_field_class` / `assert_response_class` | Dotted `module:Class` of custom assert subclasses |
| `adapter` | Default resq adapter. Only `"requests"` (sync) is supported — `"httpx"` is async in resq and is rejected |

### Methods

- `request(method, url_path, **kwargs) -> resq.http.Response` — a single HTTP request:
  serializes the pydantic `params`/`json` (optional `by_alias` via `use_aliases`),
  substitutes `:name` path parameters, injects auth/headers/cookies with call-level
  priority, resolves the effective adapter and dispatches to the resq verb. Polling
  options and the adapter itself never reach the verb.
- `close()` — closes the composed session and every cached override session (called in
  the `api` fixture teardown; a no-op in sync mode by resq design).

## `Endpoint` — reference

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
|-----------|---------|
| `api` | The `Api` client the request is made with |
| `url_path` | Route path (`:name` placeholders are substituted by `Api.request`) |
| `method` | HTTP verb |
| `status` | Expected success code (an Enum is normalized to `.value`); `None` disables the status auto-check |
| `use_autocheck` | Run the lazy auto-check on first access to `response.expected` |
| `data_key` / `error_key` | Per-endpoint keys; `None` → fall back to the `Api` values |
| `adapter` | Per-endpoint resq adapter; `None` → the `Api` default |

`schemas_dir` is resolved automatically via frame inspection — see
[the mandatory requirement](#frame-inspection-a-mandatory-requirement).

Call forms:

- `endpoint(**kwargs) -> ResponseWrapper` — the **positive** path.
- `endpoint.error(**kwargs) -> ResponseWrapper` — the **negative** path: status and JSON
  schema are not checked in the auto-check.

## `ResponseWrapper` — reference

| Element | Purpose |
|---------|---------|
| `.response` | The raw `resq.http.Response` (the wrapper does not proxy resq attributes) |
| `.expected` | The `Expected` dispatcher — built **lazily** on first access; with `use_autocheck=True` the auto-check then runs once |
| `with endpoint(...) as response:` | Context entry; the exit does **not** suppress exceptions |

## Templates

### Generated endpoint fixture

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

The `Endpoint` is created **directly in the fixture function body** — a mandatory
requirement of frame inspection.

### Positive check

```python
def test_initiate(post_clients_calls_initiate: Endpoint):
    with post_clients_calls_initiate(json=Request(order_id=1)) as response:
        response.expected.has_status_code(200)
```

Positive auto-check (fires once on first access to `.expected`): status → `error_key`
absent → `data_key` present → validation against `schemas/<status>*.json`.

### Negative check

```python
def test_initiate_error(post_clients_calls_initiate: Endpoint):
    with post_clients_calls_initiate.error(json=Request(order_id=-1)) as response:
        response.expected.has_status_code(400)
        response.expected("message").not_empty()
```

`.error(...)` — the negative path: status and JSON schema are **not** auto-checked;
verify the status explicitly. Negative auto-check: `data_key` absent → `error_key`
present. Field paths resolve under `error_key`.

Schema-invalid request bodies (a missing required field, a wrong type, an empty or
malformed body) cannot be built as a pydantic model — bypass pydantic:

```python
# a required field is missing — a raw dict
with post_clients_calls_initiate.error(json={"name": "x"}) as response: ...
# empty body
with post_clients_calls_initiate.error() as response: ...
# malformed JSON — raw data + an explicit Content-Type
with post_clients_calls_initiate.error(data="{", headers={"Content-Type": "application/json"}) as response: ...
```

### Field-level value check

Calling `response.expected(path)` returns an `AssertField`. The path is **relative to the
root**: `data_key` on the positive path, `error_key` on the negative path; without the
keys — absolute to the response body.

```python
with post_clients_calls_initiate(json=Request(order_id=1)) as response:
    response.expected("items").has_length(3)                    # dotted path under data_key
    response.expected("items", in_array=True).equal_to(2, any=True)
    response.expected("name").equal_to("abc")

    response.expected("items")(index=0).equal_to(1)             # drill-down: index
    response.expected("name")(hook=str.upper).equal_to("ABC")   # drill-down: hook

    response.expected("$.items[*]", in_array=True).equal_to(2, any=True)   # jsonpath
```

The full check catalog: [Assertions](asserts.md).

## Request parameters

`endpoint(...)` / `endpoint.error(...)` accept the resq-verb arguments:

- `params=` — a pydantic `BaseModel` (serialized) or a `dict` (query parameters).
- `json=` — a pydantic `BaseModel` (serialized) or a `dict`. For schema-invalid requests
  **pass a raw `dict`** — otherwise pydantic raises before the request is sent and the
  SUT is never tested.
- `data=` — a raw body (string/bytes), sent as-is — e.g. `data="{"` for malformed JSON;
  set the Content-Type via `headers=`.
- Without `json=`/`data=` the request is sent with an empty body.
- Path parameters — keys in `params` prefixed with `:` (e.g. `:id`) are substituted into
  `url_path` and are **not** sent to the query.
- `auth=` — call-level authentication: an `AuthBase`, an `Auth` protocol object, or a
  plain callable; combined with `Api.auth` via `CombineAuth`.
- `headers=` / `cookies=` — call-level; win over the `Api` defaults.
- `use_aliases=` (bool) — pydantic `by_alias` during serialization.
- `use_autocheck=` (bool) — a call-level override of the lazy auto-check.

```python
endpoint(json=Request(id=1), params={":id": "42", "q": "x"}, auth=MyAuth())
```

## Auto-check — what exactly is verified

Runs once on lazy access to `response.expected`, if `use_autocheck=True`:

- **Positive** (`endpoint(...)`): status (if set) → `error_key` absent → `data_key`
  present → validation against the first `schemas/<status>*.json` (silently skipped when
  the directory/file is missing).
- **Negative** (`endpoint.error(...)`): `data_key` absent → `error_key` present. Status
  and JSON schema are not checked.

`use_autocheck=False` (on the `Endpoint` or on a call) disables the auto-check entirely —
verify everything explicitly via `response.expected.*`.

## Frame inspection — a mandatory requirement

The `Endpoint` resolves `schemas/` via `inspect.stack()[1]`: it reads `__file__` from the
caller's frame globals and computes `Path(file).parent / "schemas"`. Therefore:

- Create the `Endpoint` **directly in the fixture function** (`api.py`) — `schemas/`
  lands next to that file.
- Creating it elsewhere (a top-level module, a helper) yields a foreign `__file__` or
  `None` → `schemas_dir` resolves incorrectly and the JSON-schema auto-validation
  **silently skips**.

## resq adapter (sync-only)

`Api` builds one cached `resq.Session` per adapter name and routes each request to the
session matching the effective adapter (call-level `adapter`, otherwise the `Api`
default). Only `"requests"` is supported — `"httpx"` is async in resq and is **rejected**
with `ValueError` until an async stack exists. The fixture generator does not emit
`adapter` — add it by hand when needed:

```python
@pytest.fixture(scope="function")
def post___admin___api_v1_mocks_add(api: Api) -> Endpoint:
    return Endpoint(api, "/__admin__/api_v1/mocks/add", method="POST", adapter="requests")
```

## Pluggable classes

Custom assert subclasses are plugged in via the `Api`-level options
(`assert_field_class` / `assert_response_class`, dotted `module:Class`); the class must
inherit the built-in one:

```python
class StrictAssertField(AssertField): ...

Api(base_url=..., assert_field_class="myproj:StrictAssertField")
```
