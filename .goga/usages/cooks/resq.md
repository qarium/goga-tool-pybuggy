# resq — the pybuggy HTTP client (sync)

## Domain

`resq` is the project's HTTP client; cell `goga_tool_pybuggy/api` uses it as the transport behind `Api`. The sync side of resq is built on top of `requests` (resq holds a `requests.Session`), so `requests.auth.AuthBase` authentication applies directly — without adapters.

Import in code:
```python
import resq
from resq import Session          # the facade re-exports Session
from resq.http import Response    # the response type for annotations
```

---

## Session — a client with base_url

`Session` is the "persistent" flavor: a single `requests.Session` reused across sync calls (connection pool, cookies). The consumer selects the sync/async mode **per instance** through the mandatory `adapter` argument (not per verb):

```python
session = resq.Session("https://api.example.com", "requests", timeout=10.0)
```

- `Session(base_url: str, adapter: str, timeout: float | None = None)`.
- `adapter` — the mandatory mode selector, 2nd positional argument: `"requests"` = sync, `"httpx"` = async; an unknown value → `ValueError`. pybuggy makes `adapter` configurable on `Api` (default `"requests"`) with an optional per-endpoint override on `Endpoint`, but the pybuggy sync runtime supports only `"requests"` — `Api._validate_adapter` rejects `"httpx"` (async) until an async stack exists. `Api` builds and caches one `resq.Session` per adapter name in use.
- `timeout` — the network timeout (3rd positional argument); `None` disables it.
- `base_url` is exposed as the `session.base_url` property (a string; resq stores it as is).
- resq itself joins `base_url` + `path` (normalizing the base to a trailing `/` via `urljoin`).

Verbs — one per HTTP method:
```python
session.get(path, **kwargs)
session.post(path, **kwargs)
session.put(path, **kwargs)
session.delete(path, **kwargs)
session.patch(path, **kwargs)
session.head(path, **kwargs)
session.options(path, **kwargs)
```

Each verb takes `(path, timeout=None, delay=1.0, **kwargs)`. `timeout`/`delay` belong to resq's polling window — pybuggy does **not** forward them for a single request; `**kwargs` passes through to `requests.Session.request` (params, json, headers, cookies, auth, …).

The verb is dispatched dynamically: `getattr(session, method.lower())`.

### Lifecycle and close()

`Session` exposes a **public** `close()` and a sync context manager (`__enter__`/`__exit__`). In sync mode (`adapter="requests"`), `close()` is a **no-op by resq design**: the garbage collector releases the held `requests.Session` — it is not closed explicitly (resq contract: "Do NOT close the requests.Session held by the `Session` flavor"). `Api.close()` delegates to this public `session.close()`.

```python
session = resq.Session("https://api.example.com", "requests")
session.close()  # sync: no-op (the requests.Session pool is left to GC)

# or a sync context manager:
with resq.Session("https://api.example.com", "requests") as s:
    s.get("/path")
```

---

## AuthBase applies directly

Sync resq runs `requests` under the hood, so `requests.auth.AuthBase` — any callable object `(PreparedRequest) -> PreparedRequest` — plugs in through the standard `auth=` argument and applies to the `PreparedRequest`. This mechanism is the foundation for `CombineAuth`/`AuthWrapper` in `goga_tool_pybuggy/api`.

```python
from requests.auth import AuthBase

class TokenAuth(AuthBase):
    def __call__(self, r):
        r.headers["Authorization"] = "Bearer x"
        return r
```

---

## Response — the response surface

`resq.http.Response` (sync) proxies **explicit** properties/methods only — no `__getattr__` passthrough:

- properties: `status_code`, `text`, `content`, `headers`, `url`, `encoding`, `ok`.
- methods: `json()`, `raise_for_status()`, `reload()` (re-issues the request).

`resq.http.Response` has **no** `.request` property (`PreparedRequest`) — do not use it. The pybuggy `ResponseWrapper` does **not** proxy `resq.http.Response` attributes: reach the raw response only through the `.response` property (e.g., `wrapper.response.status_code`).
