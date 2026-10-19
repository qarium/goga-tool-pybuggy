# Design Document: `sandbox-redis`

Redis as the fifth sandbox dependency kind — a real `redis:8-alpine` container driven by
redis-py, integrated into the same configuration / engine / data-view / preset surface as the
existing kinds. The CODEMANIFEST contracts of the four affected cells were materialized by the
apply-architecture stage (working tree, branch `sandbox-redis`); this document is the complete
architectural specification of the code that implements them.

Sources of truth: `.goga/history/2026/sandbox-redis/adr.md` (settled decisions),
`.goga/history/2026/sandbox-redis/task.md` (scope), the four CODEMANIFESTs (contract),
`.goga/usages/cooks/redis.md` (the redis cook), `.goga/usages/conventions.md` (project rules).

Library facts verified against the actual pinned sources (not assumed):

- `testcontainers==4.15.0` — `testcontainers/community/redis/__init__.py`:
  `RedisContainer(image="redis:latest", port=6379, password=None, **kwargs)` calls
  `super().__init__(image, _wait_strategy=PingWaitStrategy(), **kwargs)`, then
  `with_exposed_ports(port)` and, when `password` is truthy,
  `with_command(f"redis-server --requirepass {password}")`. `get_client(**kwargs)` builds
  `redis.Redis(host, port, password, **kwargs)`. Passing `_wait_strategy` ourselves would be a
  duplicate keyword — the only override seam is `waiting_for(...)` after construction.
- `testcontainers.core.container.DockerContainer.waiting_for(strategy)` sets
  `self._wait_strategy = strategy`, and `start()` runs
  `self._wait_strategy.wait_until_ready(self)` when the strategy is not `None` — so a
  post-construction `waiting_for(...)` call replaces the module's built-in strategy.
- `redis==7.0` — `redis/exceptions.py`: `AuthenticationError(ConnectionError)` and
  `TimeoutError(RedisError)`; `redis.Redis` connects lazily; `Redis.close()` releases the
  connection pool.

## Contract Changes

### Changed CODEMANIFEST Files

- `goga_tool_pybuggy/sandbox/config/CODEMANIFEST` — `ServiceConfig` gains `password`
  (redis-only, optional) and `db` (redis-only, 0–15, default 0); `StartupData` gains the
  `redis` section; `validate_sandbox_config` extends the kind list to five, the kind-specific
  key rules, the db range check, and the `data.redis` declaration grammar (step 4).
- `goga_tool_pybuggy/sandbox/engines/CODEMANIFEST` — header `Usages` gains
  `redis: .goga/usages/cooks/redis.md` + one global annotation line; `DataOperation` action
  set gains `set`/`hset`/`rpush`/`sadd` (redis payload = key + value/values/members);
  `build_engine` maps redis and passes the password/db declarations through;
  `BaseEngine.config` description mentions password/db; **new type**
  `BaseEngine::RedisEngine` (`location: redis.py`).
- `goga_tool_pybuggy/sandbox/data/CODEMANIFEST` — **new type** `RedisInstance`
  (`location: redis.py`, declare-only view with `set`/`hset`/`rpush`/`sadd`); `services`
  validates the five kinds and the redis action-key declaration grammar.
- `goga_tool_pybuggy/sandbox/CODEMANIFEST` — data `Imports.Types` gains `RedisInstance`;
  `Sandbox` start step 3 fixes the section order vault → http → postgres → **redis**;
  requirements clause lists redis among the view-bound kinds; **new method**
  `redis(name) -> instance: RedisInstance`.

### New Entities

- `RedisEngine` — `BaseEngine` mutation, `goga_tool_pybuggy/sandbox/engines/redis.py`: the
  redis kind engine (module container, engine-owned bounded PING readiness, one-session
  redis-py connection to the declared db, four operations, FLUSHDB wipe).
- `RedisInstance` — `goga_tool_pybuggy/sandbox/data/redis.py`: test-facing declare-only view
  of a started redis service.

### Changed Entities

- `ServiceConfig` — two new optional fields `password: str | None = None`, `db: int = 0`
  (placement validated by the loader, redis-only).
- `StartupData` — new section `redis: dict[str, list[dict[str, object]]] = {}`, last in the
  fixed section order.
- `validate_sandbox_config` — `_SUPPORTED_KINDS` five; `_SECTION_KINDS` gains
  `"redis": "redis"`; new `_validate_redis_keys` (password/db placement + db range) and
  `_validate_redis_declarations` (action-key grammar) steps.
- `DataOperation` — no model change; docstring action set and kind list extend.
- `build_engine` / `KIND_ENGINES` — `"redis": RedisEngine`; docstring.
- `services` — `_SUPPORTED_KINDS` five; redis declaration validation at decoration.
- `Sandbox` — `redis(name)` facade; `_KIND_ACTIONS` re-typed for the per-declaration redis
  action; `_startup_operations` gains the redis loop last; `TypeVar` view bound gains
  `RedisInstance`.
- Facades — `engines/__init__.py` and `data/__init__.py` re-export the new types.

### Deleted Entities

- None.

### Usages and Annotations Changes

- engines header `Usages`: `redis: .goga/usages/cooks/redis.md` (file form — extensive,
  reused practice living at project level); global `Annotations` line
  "Use `redis` for the redis data plane and container."; `RedisEngine` annotations reference
  `redis` and `testcontainers`.
- Cell `.usages/` consumer docs updated by the apply stage and verified current (see
  `.usages/ Update`).

## Applied Fixes

### Fixed CODEMANIFEST Defects

- None. Static validation: `goga lint` — 24 cells, 0 errors; `goga schema` — `RedisEngine`
  in engines, `RedisInstance` in data, root ← data import edge carries `RedisInstance`, no
  import cycles. The four consistency dimensions (interface↔type, type↔mutation,
  interface↔interface, annotations↔entity) hold: every redis action name, payload field
  (`key` + `value`/`values`/`members`), and type reference agrees across config, engines,
  data, and root contracts. No user-approval edits were required.

## Entity Interaction and Data Flow

### Interaction Diagram

```
 author code / tests
   sandbox.yml: services.cache{kind: redis, password, db}; data.redis.cache[...]
        │                        @services(redis={"cache": [...]})
        │                                  │
        ▼                                  ▼
┌── config cell ──────────────┐   ┌── data cell ──────────────────┐
│ validate_sandbox_config     │   │ services() validates action   │
│  ├ kind list (five)         │   │  grammar at decoration        │
│  ├ password/db redis-only   │   │ RedisInstance.set/hset/rpush/ │
│  ├ db 0–15 at load          │   │  sadd → DataOperation → batch │
│  └ data.redis grammar       │   └───────────────┬───────────────┘
│ → ServiceConfig(+password,db)│                  │ DataOperation
│ → StartupData(+redis)        │                  │ (kind redis)
└──────────┬───────────────────┘                  │
           │ SandboxConfig                        │
           ▼                                      │
┌── engines cell ─────────────────────────────────┴──────────────┐
│ build_engine(config) → RedisEngine                             │
│  ├ RedisContainer(image|override, password, labels)            │
│  │   └ waiting_for(_NoWaitStrategy)  — replaces built-in PING  │
│  ├ _wait_ready: engine PING loop at declared bounds            │
│  ├ _open_plane: redis.Redis(host, port, db, password) ×1       │
│  ├ _execute: set/hset/rpush/sadd → wire form at execution      │
│  └ _wipe: FLUSHDB of declared db → base replays journal        │
└──────────┬─────────────────────────────────────────────────────┘
           │ BaseEngine / DataOperation / InstanceAddress
           ▼
┌── sandbox root ────────────────────────────────────────────────┐
│ Sandbox.redis(name) → _view(RedisInstance, "redis", name)      │
│ start(): _startup_operations — vault, http, postgres, redis    │
│ enqueue_presets: redis action read from the declaration        │
│ reset()/clear(): engine reset (FLUSHDB + journal replay)       │
└────────────────────────────────────────────────────────────────┘
```

### Data Flows

- **Document → engines**: `validate_sandbox_config` builds `ServiceConfig(password, db)` and
  `StartupData.redis`; `Sandbox.__init__` calls `build_engine` per service; `start()` assembles
  `DataOperation(action=declaration["action"], payload=declaration minus "action")` per redis
  declaration and hands them to `RedisEngine.start` as the startup batch.
- **Test → view → batch → engine**: `sandbox.redis("cache").set(k, v)` appends
  `DataOperation("cache", "redis", "set", {"key": k, "value": v})` to the current `DataBatch`;
  `apply_pending` groups by service and calls `RedisEngine.apply`; `_execute` serializes values
  to the wire form and issues the redis command over the session connection bound to the
  declared db.
- **Preset → batch**: the `services` decorator validates the action grammar, stamps the marker;
  the plugin's per-test fixture calls `enqueue_presets`, which resolves the service and reads
  the action from each declaration — preset operations land ahead of in-test declarations in
  the same service group.
- **Reset**: plugin per-test fixture → `Sandbox.clear` → `RedisEngine.reset` → base flow:
  `_wipe` (`FLUSHDB` on the declared db) → `_apply_operations(journal)` — the startup data and
  baseline-boundary operations replay through the identical execution path.

### Entity Dependencies

Design and implementation order (bottom-up, the established direction):
config → engines → data → sandbox root → pyproject/docs/tests. `RedisEngine` imports
`ServiceConfig` (config cell) and `BaseEngine`/`DataOperation` (engines cell);
`RedisInstance` imports `DataOperation`/`InstanceAddress` (engines) and `DataBatch` (data);
`Sandbox` imports `RedisInstance` (data). No new cross-cell edges beyond the declared ones.

## Code Stack Trace

### Trace: `validate_sandbox_config` (redis paths)

#### Chain

1. **Input**: parsed document mapping, e.g.
   `{"instance": {...env: {"REDIS_URL": "redis://{{cache.host}}:{{cache.port}}/0"}...},
   "services": {"cache": {"kind": "redis", "password": "sandbox-redis", "db": 2}},
   "data": {"redis": {"cache": [{"action": "set", "key": "feature-flag/a", "value": "enabled"}]}}}`.
2. `_read_services` → `_validate_kind`: `redis` ∈ five supported kinds → passes; grpc keeps its
   dedicated "not supported yet" error → checkpoint: passed (kind list extended).
3. NEW `_validate_redis_keys(entry, scope)` runs after `_validate_migrations`:
   kind ≠ redis and (`password` or `db` present) → `ValueError` naming
   `{location}: services.{name}`; kind = redis → password must be a non-empty string when
   present (see D7), db must be an int (bools rejected) within 0–15 → checkpoint: passed
   (placement + range match the contract steps 3 and Requirements).
4. `ServiceConfig` model build with `extra="forbid"`, kw_only — accepts exactly the known keys
   → checkpoint: passed (new fields default `None`/`0`, so non-redis entries build unchanged).
5. `_read_data` → `_SECTION_KINDS` now carries `"redis": "redis"` (iteration order vault, http,
   postgres, redis — the model field order); NEW `_validate_redis_declarations` enforces the
   action grammar (D4) → checkpoint: passed (declaration shape equals the engines payload
   contract minus the `action` key).
6. `_validate_placeholders`: `{{cache.host}}`/`{{cache.port}}` resolve against configured names
   — generic rendering, no redis-specific branch → checkpoint: passed (placeholders apply to a
   redis service unchanged, as the ADR requires).
7. **Output**: `SandboxConfig` with the redis `ServiceConfig` (password/db) and
   `StartupData.redis` declarations → consumer: `Sandbox`.

#### Checkpoint Summary

- kind/placement/range/grammar checks: passed — each failure message names the carried
  document location and the offending entry (contract requirement).
- `data.kafka` rejection and every existing four-kind behavior: unchanged.

### Trace: `build_engine(config: ServiceConfig)` — redis mapping

1. `KIND_ENGINES["redis"]` → `RedisEngine(config)`; the password/db/image/probe declarations
   reach the engine inside `config` → checkpoint: passed (contract requirement).
2. Unmapped kind → `EngineError` listing the five supported kinds (now includes redis)
   → checkpoint: passed (acceptance: every supported-kinds message lists redis).

### Trace: `RedisEngine.start(startup, network)` (inherited `BaseEngine.start` flow)

#### Chain

1. **Input**: `startup` — the service's redis `DataOperation` list in declaration order;
   `network` — the sandbox network (optional).
2. `_build_container`: `image = config.image or "redis:8-alpine"`;
   `RedisContainer(image, password=config.password or None, labels=SANDBOX_LABELS)` — the
   module publishes 6379 and wires `--requirepass` itself when the password is truthy;
   `container.waiting_for(_NoWaitStrategy())` replaces the built-in `PingWaitStrategy`
   (verified: `waiting_for` overwrites `_wait_strategy`, `start()` runs the installed
   strategy) → checkpoint: passed (D1; the module's global-config-bounded wait never runs).
   `_attach_network(container)` joins the sandbox network under the service-name alias.
3. `container.start()` → docker create/start; the no-op strategy returns immediately
   → checkpoint: passed (readiness is engine-owned, not module-owned).
4. `_wait_ready`: `_probe_until` loop at the declared `(timeout, interval)` — each attempt
   builds a probe client `redis.Redis(host, port, password, socket_timeout=2,
   connect_timeout=2)` and calls
   `ping()`: `ConnectionError`/`TimeoutError` → retry; `AuthenticationError` → immediate
   failure naming the PING check and the auth cause (D2); deadline expiry →
   `RuntimeError("the redis service did not answer PING at host:port within Ns")` →
   `_run_step("start failed at readiness wait")` wraps into `EngineError` naming the service,
   the waited check, and the deadline → checkpoint: passed (never a hang; same error shape as
   the other four engines).
5. `_open_plane`: session client `redis.Redis(host, port, db=config.db,
   password=config.password or None, socket_timeout=5, connect_timeout=5)` + one eager
   `ping()` binding the
   connection (D6) → checkpoint: passed (db and password reach the data plane — the
   declared-database contract).
6. `_migrate`: base no-op default — migrations are rejected on redis at document load
   → checkpoint: passed (contract).
7. `_apply_operations(startup)`: each operation → `_execute` (below); failures wrap into
   `EngineError` naming service, action, cause → checkpoint: passed.
8. `journal.extend(startup)`; `_started = True`.
9. **Output**: ready service; `address` property reads the mapped host and published port from
   the container engine → consumed by `render_service_env` and `_view`.
10. Failure path: base `start` catches, `stop()`s (client close + container remove), re-raises
    → checkpoint: passed (leaves nothing behind).

### Trace: `RedisEngine._execute(operation)`

1. **Input**: `DataOperation(kind="redis", action ∈ {set, hset, rpush, sadd}, payload)` —
   payload carries `key` plus `value` (set) / `values` mapping (hset) / `values` list (rpush) /
   `members` list (sadd); guaranteed by the three declaration paths (loader, presets, typed
   view methods).
2. Dispatch on `action`:
   - `set` → `client.set(key, _wire(value))`;
   - `hset` → empty mapping executes nothing; otherwise
     `client.hset(key, mapping={field: _wire(v) for field, v in values.items()})`;
   - `rpush` → empty list executes nothing; otherwise `client.rpush(key, *[_wire(v) for v in values])`;
   - `sadd` → empty list executes nothing; otherwise `client.sadd(key, *[_wire(m) for m in members])`;
   - anything else → `RuntimeError("unknown redis action ...")` (wrapped by `_run_operation`).
3. `_wire(value)`: `str` → as-is; every other value → `json.dumps(value)` (D3) — serialization
   happens at execution; the declared payload object is never mutated → journal replay
   deterministic → checkpoint: passed (type flow: `_wire` returns `str`, redis-py encodes
   UTF-8; `json.dumps` failure on non-serializable data wraps into `EngineError` naming the
   action).
4. Non-string keys/fields (possible only through a hand-built marker payload, bypassing the
   typed view and the validators) surface as the client's `DataError` → `EngineError` naming
   the service and action → checkpoint: passed (readable failure, no coercion).
5. **Output**: command applied on the session connection bound to the declared db; debug log
   "operation executed" from the base (service + action; never the password).

### Trace: `RedisEngine.reset()` (inherited) / `_wipe`

1. `_require_started` → guard.
2. `_wipe`: `client.flushdb()` — one command against the open connection; the client is bound
   to `config.db`, so only the declared logical database is wiped → checkpoint: passed
   (contract: FLUSHDB wipes no other logical database; container never restarts; connection
   survives).
3. `_apply_operations(journal)` — startup data + baseline operations replay through the exact
   `_execute` path → checkpoint: passed (replay re-serializes untouched payloads — identical
   wire form).

### Trace: `RedisEngine.stop()` (inherited) / `_close_plane`

1. `_close_plane`: `client.close()` when open, then `None`; safe when nothing is open
   → checkpoint: passed (one connection per session, closed on stop; second stop is a no-op).
2. Container removal + "service stopped" log from the base.

### Trace: `RedisInstance` view methods

1. **Input**: e.g. `set("feature-flag/a", "enabled")` on the view bound to
   `(name="cache", address, batch)`.
2. `DataOperation(instance="cache", kind="redis", action="set",
   payload={"key": "feature-flag/a", "value": "enabled"})` → `batch.add` → nothing executed
   → checkpoint: passed (lazy declaration contract; payload shape equals the engines payload
   contract field-for-field).
3. **Output**: the batch entry, later applied by `Sandbox.apply_pending` grouped per service.

### Trace: `services(redis={"cache": [...]})` and `Sandbox.enqueue_presets`

1. Decoration: `_SUPPORTED_KINDS` now five; every redis declaration validated against the
   action grammar (D4) — exact key set `{action} ∪ action fields`, non-empty string `key`,
   `values` mapping for hset, `values`/`members` lists for rpush/sadd → `ValueError` names
   `services preset 'redis.{name}'` → checkpoint: passed (contract: "anything else fails
   naming the declaration").
2. Marker + `usefixtures("sandbox")` stamp — unchanged mechanics.
3. `enqueue_presets`: `_require_service("redis", name)` lists configured services on mismatch;
   `_KIND_ACTIONS["redis"]` is `None` → the action is read from the declaration, with a
   graceful marker-payload guard (D5): a missing/unknown `action` key fails with the
   preset-style message instead of a bare pydantic error → checkpoint: passed.
4. **Output**: enqueued `DataOperation`s ahead of in-test view declarations; count returned.

### Trace: `Sandbox.start()` — redis sections

1. `_start_engines` iterates configured services in declaration order; `_startup_operations`
   assembles per service: vault loop, http loop, postgres loop, NEW redis loop last —
   `action=declaration["action"]`, `payload={k: v for k, v in declaration.items() if k != "action"}`
   (fresh dict; the declaration is never mutated) → checkpoint: passed (fixed section order;
   the action key is guaranteed by load validation).
2. `render_service_env` resolves `{{cache.host}}`/`{{cache.port}}` from the redis engine's
   mapped address — generic path → checkpoint: passed.
3. Instance start — unchanged.

## Algorithm Design

### Design decisions (contract-consistent choices the DSL deliberately leaves open)

- **D1 — readiness mechanism**: `_build_container` installs a `_NoWaitStrategy` via the core
  `waiting_for(...)` — the settled replacement seam — and the engine owns the bounded PING in
  the `_wait_ready` hook, exactly like postgres/http/vault/kafka (reuse of `_probe_until` and
  `_readiness_bounds`; readiness failures read `start failed at readiness wait: the redis
  service did not answer PING at host:port within Ns`, the family error shape). Alternative
  considered: a custom `WaitStrategy` running the bounded PING inside `container.start()` —
  rejected: it bypasses the engine hook every other kind uses and duplicates the probe loop.
- **D2 — wrong password fails fast**: `AuthenticationError` is deterministic — retrying cannot
  fix it. The probe lets it escape the retry loop immediately and the lifecycle wrapper wraps
  it into `EngineError` naming the service, the PING check, and the auth cause (the cook:
  "a wrong password surfaces as an auth error ... never a hang"). Catch order matters — the
  `AuthenticationError` clause precedes the `ConnectionError` clause (subclass first).
- **D3 — wire serialization**: `_wire(value) -> str`: `str` as-is; otherwise `json.dumps`.
  Empty `values`/`members`/mapping executes nothing (the postgres empty-rows precedent).
- **D4 — declaration grammar duplication**: the loader (config cell) and the presets decorator
  (data cell) each carry a small action-grammar validator — config cannot import from
  engines/data (it is the bottom cell; engines imports config), and the existing design already
  splits shape checks this way (vault shape in the loader, insert grammar shared via engines
  only because engines sits between config and data). Strict exact key set: `{action}` plus the
  action's fields — extras fail ("anything else fails naming the entry/declaration").
- **D5 — preset action source**: `_KIND_ACTIONS` keeps the four single-action kinds and maps
  `"redis"` to `None` (the action comes from each declaration); a graceful guard replaces a
  bare `KeyError`/pydantic error for hand-built markers. The enqueued redis payload drops the
  `action` key — a fresh dict of the view-operation fields only, field-for-field what
  `_startup_operations` builds; the four single-action kinds keep `payload=declaration`
  unchanged (their declaration fields already equal the view payload fields).
- **D6 — eager plane binding**: `_open_plane` issues one `ping()` on the session client so a
  data-plane connectivity failure surfaces at the `start failed at data-plane open` step
  (postgres parity), not on the first startup command.
- **D7 — empty password rejected**: the module treats a falsy password as "no
  `--requirepass`", so `password: ""` would silently contradict "present starts with
  --requirepass" — the loader rejects it naming the entry.
- **D8 — bounded sockets**: probe clients use `socket_timeout=2` and `connect_timeout=2`
  (the postgres `PROBE_CONNECT_TIMEOUT` value); the session client uses `socket_timeout=5`
  and `connect_timeout=5` (the http `PLANE_TIMEOUT` value) — both phases are bounded:
  `connect_timeout` covers the TCP connect, `socket_timeout` the command I/O, so clients
  fail readably instead of hanging. The probe client closes on every attempt outcome
  (success, retry, auth refusal) — `close()` is safe on a live and on a failed client.
- **D9 — db validation**: `db` must be an `int` that is not a `bool`, within 0–15 inclusive;
  YAML floats/strings/bools fail at load naming the entry.
- **D10 — unsupported-kind example in tests**: the re-pointed negative tests use `mysql` (a
  plain unsupported kind; `grpc` keeps its dedicated message).

### `RedisEngine` (new, `goga_tool_pybuggy/sandbox/engines/redis.py`)

**Responsibility**: own one started redis service — container, data plane, baseline journal,
reset — for the redis kind.

Module constants: `DEFAULT_IMAGE = "redis:8-alpine"`, `CONTAINER_PORT = 6379`,
`PLANE_TIMEOUT = 5`, `PROBE_CONNECT_TIMEOUT = 2`, `SANDBOX_LABELS = {"pybuggy-sandbox": "true"}`,
`_REDIS_ACTIONS = {"set": ("key", "value"), "hset": ("key", "values"),
"rpush": ("key", "values"), "sadd": ("key", "members")}` (dispatch table shared by `_execute`
error messages).

**Algorithm:**
```
_NoWaitStrategy(WaitStrategy): wait_until_ready → no-op (D1)

RedisEngine: _container_port = CONTAINER_PORT      # class attr — the family contract

__init__(config):
  super().__init__(config); _client = None

_build_container() -> RedisContainer:
  image ← config.image or DEFAULT_IMAGE
  container ← RedisContainer(image, password=config.password or None, labels=SANDBOX_LABELS)
    → module publishes 6379, wires --requirepass when password truthy
  container.waiting_for(_NoWaitStrategy())      → built-in PING wait replaced
  _attach_network(container)                    → sandbox network + service-name alias
  → container

_wait_ready():
  address ← self.address; (timeout, interval) ← _readiness_bounds
  failure ← "the redis service did not answer PING at {host}:{port}"
  attempt():
    probe ← redis.Redis(host, port, password=config.password or None,
                        socket_timeout=PROBE_CONNECT_TIMEOUT,
                        connect_timeout=PROBE_CONNECT_TIMEOUT)
    TRY:
      probe.ping() → True
        ON AuthenticationError → raise RuntimeError(f"{failure}: authentication failed: {exc}")  (D2)
        ON (ConnectionError, TimeoutError)     → False (retry)
        # clause order is load-bearing: AuthenticationError IS a ConnectionError subclass —
        # the specific clause must precede the retry clause, or auth failures retry to expiry
    FINALLY:
      probe.close()              # every attempt outcome — success, retry, auth refusal
  _probe_until(timeout, interval, attempt, failure)
  → debug log "redis service ready" (service, host, port — never the password)

_open_plane():
  address ← self.address
  _client ← redis.Redis(host, port, db=config.db, password=config.password or None,
                        socket_timeout=PLANE_TIMEOUT, connect_timeout=PLANE_TIMEOUT)
                                                                # decode_responses stays False
  _client.ping()                                               (D6 — binds the connection)
  → debug log "redis plane open"

_migrate(): base no-op default — not overridden

_execute(operation):
  payload ← operation.payload; key ← payload["key"]
  IF action = set     → _client.set(key, _wire(payload["value"]))
  ELIF action = hset  → values ← payload.get("values") or {}
                        IF values → _client.hset(key, mapping={f: _wire(v) for f, v in values.items()})
  ELIF action = rpush → values ← payload.get("values") or []
                        IF values → _client.rpush(key, *[_wire(v) for v in values])
  ELIF action = sadd  → members ← payload.get("members") or []
                        IF members → _client.sadd(key, *[_wire(m) for m in members])
  ELSE → raise RuntimeError(f"unknown redis action '{action}' (set, hset, rpush, sadd)")
  → base _run_operation wraps any failure into EngineError

_wire(value) -> str: IF isinstance(value, str) → value ELSE json.dumps(value)   (D3)

_wipe(): _client.flushdb()          — declared db only; connection survives

_close_plane(): IF _client is not None → _client.close(); _client = None
```

**Errors:**
- `EngineError` (via base wrappers) → start step failures name the service and the step
  (readiness expiry adds the waited check and deadline; auth adds the cause); operation
  failures name the service, the action, and the cause → the consumer sees one error type.
- `RuntimeError` from `_probe_until`/auth/unknown-action → converted by the base wrappers.

**Edge Cases:**
- No startup data → zero operations applied; journal empty; reset = FLUSHDB only.
- `db: 0` (default) and `db: 15` — boundaries accepted at load.
- Empty `values`/`members`/mapping → command skipped (declared, journaled, executes nothing).
- Password declared → container command and both probe and session clients carry it; password
  absent → `config.password or None` normalizes `""`-like inputs away (the loader already
  rejects empty strings).
- Stop before start / double stop → `_client` `None` guard + base container guard.

### `RedisInstance` (new, `goga_tool_pybuggy/sandbox/data/redis.py`)

**Responsibility**: declare redis data operations from tests; nothing executes at declaration.

**Algorithm:** mirror `HttpInstance` exactly — `__init__(name, address, batch)`, properties
`name`/`host`/`port`, then:

```
set(key: str, value: object)        → DataOperation(kind="redis", action="set",
                                        payload={"key": key, "value": value}) → batch.add
hset(key: str, values: dict)        → action="hset", payload={"key": key, "values": values}
rpush(key: str, values: list)       → action="rpush", payload={"key": key, "values": values}
sadd(key: str, members: list)       → action="sadd", payload={"key": key, "members": members}
```

**Errors:** none — declaration only. **Edge cases:** payloads of any plain object ride as
given; serialization is execution-time.

### `ServiceConfig` (changed, `config/service.py`)

Add `password: str | None = None` and `db: int = 0` (kw_only, `extra="forbid"` unchanged);
docstring kinds list and field docs extend. No validator changes in the model — placement is
the loader's job (existing division).

### `StartupData` (changed, `config/startup_data.py`)

Add `redis: dict[str, list[dict[str, object]]] = {}` last; docstring names the four-section
order and the declaration grammar summary.

### `validate_sandbox_config` (changed, `config/loader.py`)

**Algorithm:**
```
_SUPPORTED_KINDS += "redis"                        (five; grpc branch untouched)
_SECTION_KINDS += {"redis": "redis"}               (iteration order: vault, http, postgres, redis)

_read_services: after _validate_migrations call
  _validate_redis_keys(entry, scope):
    IF kind ≠ redis AND ("password" in entry OR "db" in entry)
      → ValueError(f"{scope}: password and db are accepted only on redis entries")
    IF kind = redis:
      IF "password" in entry AND (not a str OR empty)
        → ValueError(f"{scope}.password: must be a non-empty string")     (D7)
      IF "db" in entry AND (not isinstance(int) OR isinstance(bool) OR not 0 ≤ db ≤ 15)
        → ValueError(f"{scope}.db: must be an integer within 0-15")       (D9)

_read_section("redis"): after the kind-match check call
  _validate_redis_declarations(target, declarations, location):          (D4)
    IF not a list → return (model build fails with the scope-named error — vault precedent)
    FOR each dict declaration:
      action ← declaration.get("action")
      IF action ∉ _REDIS_ACTIONS
        → ValueError(f"{location}: data.redis.{target}: every declaration requires an "
                     "'action' key (set, hset, rpush, or sadd)")
      expected ← {"action"} ∪ _REDIS_ACTIONS[action] fields
      IF set(declaration) ≠ expected
        → ValueError(f"{location}: data.redis.{target}: a '{action}' declaration carries "
                     "exactly {expected-list}, got {unexpected/missing-list}")
      IF key is not a non-empty str → ValueError(... naming the entry)
      IF hset values not a mapping / rpush values not a list / sadd members not a list
        → ValueError(... naming the entry)
```

**Errors:** every message names `{location}` and the entry — the fail-fast contract.
**Edge cases:** `db: 16`, `db: -1`, `db: 2.5`, `db: true` all fail; `db: 0`/`db: 15` pass;
non-dict/non-list declaration values defer to the model build (vault precedent).

### `services` (changed, `data/presets.py`)

`_SUPPORTED_KINDS` five; per-declaration validation for redis with the same grammar as D4,
message context `services preset 'redis.{name}'` (a local `_validate_redis_declarations`
helper + `_REDIS_ACTIONS` table). Decoration executes nothing — unchanged.

### `Sandbox` (changed, `sandbox/sandbox.py`)

```
imports += RedisInstance (from .data)
ViewT bound += RedisInstance
_KIND_ACTIONS: dict[str, str | None] = {...four kinds..., "redis": None}

redis(name) → _view(RedisInstance, "redis", name)      # docstring mirrors the other factories

enqueue_presets: action ← _KIND_ACTIONS[kind]
  IF action is None:
    action ← declaration.get("action")
    IF action ∉ {"set","hset","rpush","sadd"}
      → ValueError(f"services preset 'redis.{name}': every declaration requires an "
                   "'action' key (set, hset, rpush, or sadd)")            (D5)
    payload ← {k: v for k, v in declaration.items() if k != "action"}   # fresh dict
  ELSE:
    payload ← declaration
  DataOperation(instance=name, kind=kind, action=action, payload=payload)

_startup_operations: after the postgres loop
  FOR declaration in data.redis.get(name, []):
    operations += DataOperation(instance=name, kind="redis",
                                action=declaration["action"],
                                payload={k: v for k, v in declaration.items() if k != "action"})
```

### Registries, facades, packaging

- `engines/runtime.py`: `from .redis import RedisContainer`-free — `from .redis import
  RedisEngine`; `KIND_ENGINES["redis"] = RedisEngine`; `build_engine` docstring mentions the
  password/db reach-through.
- `engines/operation.py` / `engines/__init__.py` / `data/__init__.py`: docstring action set
  extension; `RedisEngine` / `RedisInstance` re-exports.
- `pyproject.toml`: `"testcontainers[postgres]>=4.15"` → `"testcontainers[postgres,redis]>=4.15"`
  (the extended existing entry); `"redis>=7.0"` added (floor forced by the testcontainers
  redis extra — one consistent resolution).

## Cross-cutting Concerns

- **Error handling**: one strategy per layer — document problems fail at load as `ValueError`
  naming the location and entry; preset problems fail at decoration as `ValueError` naming
  `services preset 'kind.name'`; runtime problems surface as `EngineError` naming the service,
  the operation/step, and the cause; auth failures fail fast within the declared bounds; the
  facade fails fast listing configured services. No error swallowing; teardown steps log
  instead of raising (base behavior).
- **Logging**: structured `logging` with `extra` metadata (`service`, `kind`, `action`,
  `host`, `port`) following the base engine events (`service starting` / `service ready` /
  `service stopped` / `operation executed`). **The password never appears in any log or error
  message** (conventions — log content restrictions); readiness messages carry host:port only.
- **Validation**: load-time (kind list, password/db placement, db range, action grammar,
  placeholder resolution) before any container exists; decoration-time (preset grammar);
  declaration-time (typed view signatures); execution-time (`json.dumps` serializability,
  client-side key typing) — each failing readably.
- **Caching**: none (one session connection per redis service is a lifecycle resource, not a
  cache; no pooling — the cook's decision).
- **Concurrency**: unchanged — engines live on the single-threaded pytest session flow; the
  session client is used by start/apply/reset/stop exclusively.

## Usages Analysis

### `redis` (engines header Usages → `.goga/usages/cooks/redis.md`)

- **What it provides**: the redis-py client contract (lazy connect, one client per session,
  write-only v1 plane with `decode_responses` default), the community `RedisContainer` module
  contract (constructor `password` wiring, `waiting_for` replacement seam, `get_client`
  kwargs), the engine-owned PING readiness loop, the four operation commands, and the
  FLUSHDB-of-declared-db reset semantics.
- **Where used**: `RedisEngine` annotations (all hooks); the global engines `Annotations`
  line.
- **Why chosen**: the official client on the exact floor the pinned testcontainers extra
  forces (`redis>=7`); the module container standardizes port handling at zero cost.
- **How exactly**: `redis.Redis(host, port, db, password, socket_timeout)`; `client.ping()`;
  `client.set/hset(mapping=)/rpush(*)/sadd(*)`; `client.flushdb()`; `client.close()`;
  `RedisContainer(image, password=..., labels=...)` + `container.waiting_for(...)`.

### `testcontainers` (engines + root Usages → `.goga/usages/cooks/testcontainers.md`)

- **What it provides**: container lifecycle, module/generic containers, `waiting_for`,
  labels, ryuk-backed stop guarantee, `Network` attach.
- **Where used**: `RedisEngine` (container lifecycle and stop guarantee), base engine
  mechanics, `Sandbox` network.
- **Why chosen / how**: the pinned 4.15 platform every engine already drives; the community
  redis module with the engine-installed no-op strategy (D1).

### `conventions` (all four cells)

Relative imports, kw_only pydantic models, Google docstrings, structured logging, blank-line
blocking, test mirroring — applied throughout; `ruff check` clean; `pytest tests/ -x` green.

### Imported Usages

- `sandbox-file` from `goga_tool_pybuggy/sandbox/config` (root Imports) — path
  `goga_tool_pybuggy/sandbox/config/.usages/sandbox-file.md`; updated by the apply stage with
  the redis entry, keys, image row, readiness, placeholder and `data.redis` documentation.
  Traceable cross-cell link consumed by `Sandbox`/`render_service_env` context; verified
  consistent with the config contract.
- `data-operations` from `goga_tool_pybuggy/sandbox/data` (root Imports) — path
  `goga_tool_pybuggy/sandbox/data/.usages/data-operations.md`; updated with the redis view,
  preset, ordering, and reset documentation. Verified consistent.
- `migration-set` from `goga_tool_pybuggy/sandbox/migrations` (engines/config Imports) —
  unchanged by this task; referenced by `validate_sandbox_config` and `PostgresEngine` only.

## `.usages/` Update

### Cell: `goga_tool_pybuggy/sandbox/config`

- **`sandbox-file`** → `.usages/sandbox-file.md` — Status: **current** (apply stage). Covers
  the redis entry (`password`/`db` comments), the five-kind rule, the `redis:8-alpine` image
  row, the "Redis keys" subsection (env-literal password precedent, db alignment), PING
  readiness, `{{cache.host}}`/`{{cache.port}}`, the `data.redis` table row + example, and the
  extended failure list (`password`/`db` on non-redis, db out of range). No additions needed.

### Cell: `goga_tool_pybuggy/sandbox/data`

- **`data-operations`** → `.usages/data-operations.md` — Status: **current**. Covers
  `sandbox.redis(...)` reaching, the four operation examples, type-correct-writer visibility
  rule, JSON-serializable values, declared-db alignment, the `action`-key preset example,
  ordering semantics, plain-values-only references, FLUSHDB reset. No additions needed.

### Cell: `goga_tool_pybuggy/sandbox`

- **`sandbox-session`** → `.usages/sandbox-session.md` — Status: **current**. Covers the redis
  direct-use and baseline examples and the per-test FLUSHDB reset note. No additions needed.

No new `.usages/` files: all redis consumer guidance belongs to the three existing domains
(configuration, data operations, session usage) — supplement, not new-domain, per the cookbook
rules. No CODEMANIFEST `Usages` key points at the cell's own `.usages/` files.

## Test Stack Trace

### General Setup

- Unit tests patch module seams (the established style): `redis_module.RedisContainer` →
  `FakeRedisContainer` (records image/password/labels kwargs, `waiting_for` strategies,
  network attach, mapped address `127.0.0.2:16379`, start/stop counters);
  `redis_module.redis` → a fake namespace (records constructed client kwargs, serves scripted
  `ping` results/errors, carries the real `redis.exceptions` classes);
  `install_fake_clock(monkeypatch)` from the http tests for `_probe_until`.
- `FakeRedisClient`: records commands as `(name, args, kwargs)`, serves scripted errors,
  counts `close()`.
- Container-backed tests reuse `requires_docker` from `tests/sandbox/conftest.py`
  (`from ..conftest import requires_docker`).
- Existing fixtures: `sandbox_yaml` (loader tests), `SandboxHarness`/`started` (sandbox tests).

### Source File Registry

Under test: `goga_tool_pybuggy/sandbox/config/{service,startup_data,loader}.py`,
`goga_tool_pybuggy/sandbox/engines/{redis,runtime,operation}.py`,
`goga_tool_pybuggy/sandbox/data/{redis,presets}.py`, `goga_tool_pybuggy/sandbox/sandbox.py`.
New test files: `tests/sandbox/engines/test_redis.py`, `tests/sandbox/data/test_redis.py`.
Extended: `tests/sandbox/config/test_service.py`, `test_startup_data.py`, `test_loader.py`,
`tests/sandbox/engines/test_runtime.py`, `tests/sandbox/data/test_presets.py`,
`tests/sandbox/test_sandbox.py`, `tests/plugin/test_sandbox_plugin.py`,
`tests/plugin/test_install.py`.

---

### Positive Tests

#### `test_service_config_accepts_the_redis_fields_with_defaults`
(`tests/sandbox/config/test_service.py`)

**Setup**: none (pure model). **Input**: `ServiceConfig(name="cache", kind="redis")`.
**Trace**: model constructs kw_only → fields default.
→ `ServiceConfig(name="cache", kind="redis")` → pydantic defaults.
**Assertions**: `config.password is None`; `config.db == 0`; `model_config` kw_only/extra-forbid unchanged.
**Sufficiency**: pins the two new fields and their defaults — every non-redis document builds identically (regression guard for the model surface).

#### `test_service_config_carries_declared_password_and_db`

**Setup**: none. **Input**: `ServiceConfig(name="cache", kind="redis", password="sandbox-redis", db=7)`.
**Trace**: model stores the declared values.
**Assertions**: `password == "sandbox-redis"`; `db == 7`.
**Sufficiency**: the reach-through contract — the engine reads exactly these fields.

#### `test_startup_data_defaults_the_redis_section_empty`
(`tests/sandbox/config/test_startup_data.py`)

**Setup**: none. **Input**: `StartupData()`.
**Trace**: pydantic default (deep-copied `{}` per instance).
**Assertions**: `data.redis == {}`; the four section attribute order is vault, http, postgres, redis.
**Sufficiency**: documents without redis data start nothing redis-shaped; guards the shared-mutable-default class of bug.

#### `test_load_accepts_a_redis_service_with_password_and_db`
(`tests/sandbox/config/test_loader.py`)

**Setup**: `sandbox_yaml` with
`services: {cache: {kind: redis, password: sandbox-redis, db: 2}}` and a valid instance.
**Input**: the written document.
**Trace**: `validate_sandbox_config` → `_validate_kind` passes (five kinds) →
`_validate_redis_keys` passes (redis kind, str password, db 2 ∈ 0–15) → model build.
**Assertions**: `config.services["cache"].kind == "redis"`; `.password == "sandbox-redis"`; `.db == 2`; no exception.
**Sufficiency**: the acceptance headline — a redis document validates end to end.

#### `test_load_accepts_the_redis_data_section_for_all_four_actions`

**Setup**: `sandbox_yaml` with a redis service and `data.redis.cache` listing
`{action: set, key: feature-flag/a, value: enabled}`,
`{action: hset, key: user:1, values: {name: Ann}}`,
`{action: rpush, key: queue:orders, values: [{id: 1}, {id: 2}]}`,
`{action: sadd, key: members:vip, members: [ann, bob]}`.
**Input**: the written document.
**Trace**: `_read_data` → section kind match → `_validate_redis_declarations` — each action's
exact field set present.
**Assertions**: `config.data.redis["cache"]` holds the four declarations verbatim (dict equality).
**Sufficiency**: the whole declaration grammar passes load — the shapes the engine later executes.

#### `test_load_accepts_redis_placeholders_in_instance_env`

**Setup**: redis service `cache`; instance env `REDIS_URL: "redis://{{cache.host}}:{{cache.port}}/0"`.
**Input**: the written document.
**Trace**: `_validate_placeholders` → `cache` resolves against configured names.
**Assertions**: validation returns; no exception.
**Sufficiency**: the ADR requirement — placeholders apply to a redis service through the generic rendering, unchanged.

#### `test_build_engine_returns_the_redis_engine`
(`tests/sandbox/engines/test_runtime.py`)

**Setup**: none. **Input**: `build_engine(ServiceConfig(name="cache", kind="redis"))`.
**Trace**: `KIND_ENGINES["redis"]` → `RedisEngine(config)`.
**Assertions**: `isinstance(engine, RedisEngine)`; `engine.config.name == "cache"`.
**Sufficiency**: the kind → engine mapping — a redis document starts a redis engine.

#### `test_redis_engine_is_importable_and_subclasses_base`
(`tests/sandbox/engines/test_redis.py`, contract class)

**Setup**: none. **Input**: the engines facade.
**Trace**: `from goga_tool_pybuggy.sandbox.engines import RedisEngine`.
**Assertions**: `issubclass(RedisEngine, BaseEngine)`; `__init__` signature `["self", "config"]` over `ServiceConfig`; `RedisEngine._wait_ready is not BaseEngine._wait_ready` (engine-owned readiness).
**Sufficiency**: the facade re-export and the mutation contract (`BaseEngine::RedisEngine`).

#### `test_build_uses_the_pinned_image_labels_and_port`

**Setup**: monkeypatch `redis_module.RedisContainer` → `FakeRedisContainer`. **Input**:
`RedisEngine(ServiceConfig(name="cache", kind="redis"))._build_container()`.
**Trace**: `config.image` is `None` → `DEFAULT_IMAGE`; labels pass through kwargs; module
publishes 6379 (fake records `with_exposed_ports`).
**Assertions**: `container.image == "redis:8-alpine"`; `container.kwargs["labels"] == {"pybuggy-sandbox": "true"}`; exposed port 6379; `container.network is None` (no network set).
**Sufficiency**: the product pin (major-version precedent) and the sandbox labeling contract.

#### `test_build_honors_the_image_override`

**Setup/Input**: as above with `image="redis:9-alpine"`.
**Assertions**: `container.image == "redis:9-alpine"`.
**Sufficiency**: the common `image` override reaches the container build.

#### `test_build_passes_the_password_to_the_module_container`

**Setup**: fake module container. **Input**: config with `password="sandbox-redis"`.
**Trace**: constructor receives `password="sandbox-redis"`; the module (fake records what the
real module does with it) wires `--requirepass`.
**Assertions**: `container.kwargs["password"] == "sandbox-redis"`; with `password=None` →
`container.kwargs["password"] is None` and no command recorded.
**Sufficiency**: present password starts the container authenticated; absent — the primary no-auth mode (the module owns the command wiring).

#### `test_build_replaces_the_builtin_wait_strategy`

**Setup**: fake module container. **Input**: `_build_container()`.
**Trace**: the module constructor installs its `PingWaitStrategy` (fake default); the engine
calls `waiting_for(...)` after construction.
**Assertions**: the container's final strategy is the engine's no-op strategy (`container.wait_strategies[-1]` is an instance of the module's `_NoWaitStrategy`); the built-in strategy instance is no longer installed.
**Sufficiency**: the settled mechanism — the module's global-config-bounded wait never runs; readiness is engine-owned (D1).

#### `test_build_joins_the_sandbox_network_under_the_service_alias`

**Setup**: fake container; `engine._network = network_object()`.
**Assertions**: `container.network is network_object`; `container.network_aliases == ["cache"]`.
**Sufficiency**: redis containers join the per-session isolation boundary like every kind.

#### `test_wait_ready_probes_ping_until_success`

**Setup**: fake `redis` namespace with scripted results `[ConnectionError, ConnectionError, True]`;
fake clock; `engine._container = FakeRedisContainer(...)`.
**Input**: `engine._wait_ready()`.
**Trace**: probe clients built at `127.0.0.2:16379` with `socket_timeout=2` and
`connect_timeout=2` → attempts at the declared interval (default 0.5); every attempt closes
its probe client.
**Assertions**: three `ping` calls recorded; `clock.slept == [0.5, 0.5]`; each constructed probe client carries the declared password.
**Sufficiency**: the bounded retry loop at the declared bounds — connection refusals during startup never fail early, never hang.

#### `test_wait_ready_fails_fast_on_authentication_error`

**Setup**: fake namespace scripted to raise `AuthenticationError("invalid password")` on the
first `ping`.
**Input**: `engine._wait_ready()`.
**Trace**: attempt 1 → `AuthenticationError` escapes the retry loop as
`RuntimeError("... did not answer PING ... authentication failed: invalid password")`.
**Assertions**: `pytest.raises(RuntimeError, match=r"did not answer PING.*authentication failed")`; exactly one `ping` recorded (no retry, no sleep).
**Sufficiency**: a wrong password surfaces as the auth error within the deadline — never retried into expiry, never a hang (D2).

#### `test_wait_ready_fails_past_the_declared_deadline`

**Setup**: fake namespace always raising `ConnectionError`; fake clock; probe
`ProbeConfig(timeout=0.2, interval=0.05)`.
**Input**: `engine._wait_ready()`.
**Trace**: loop probes until the monotonic deadline.
**Assertions**: `pytest.raises(RuntimeError, match=r"did not answer PING.*within 0\.2s")`; `len(clock.slept) >= 4`; every sleep is 0.05.
**Sufficiency**: an unreachable service fails at the declared deadline with the waited check named — the bounded-readiness contract.

#### `test_open_plane_connects_to_the_declared_database`

**Setup**: fake namespace; `engine._container` set; config `password="p"`, `db=3`.
**Input**: `engine._open_plane()`.
**Trace**: `redis.Redis(host, port, db=3, password="p", socket_timeout=5, connect_timeout=5)` +
eager `ping()`.
**Assertions**: constructed kwargs recorded (`db=3`, `password="p"`, `connect_timeout=5`); one `ping` on the session client; `decode_responses` not set (default False).
**Sufficiency**: the data plane binds to the declared logical database with the declared password — FLUSHDB and seeds address exactly that db.

#### `test_execute_applies_the_four_operations_with_wire_serialization`

**Setup**: `FakeRedisClient` on `engine._client`; config kind redis.
**Input**: four operations — `set` with `value={"on": true}` (dict), `hset` with
`values={"name": "Ann", "plan": "pro"}`, `rpush` with `values=[{"id": 1}, "tail"]`, `sadd`
with `members=["ann", 2]`.
**Trace**: `_execute` per operation → `_wire` per value.
**Assertions**:
```
client.commands == [
    ("set",    ("feature-flag/a", '{"on": true}'), {}),
    ("hset",   ("user:1",), {"mapping": {"name": "Ann", "plan": "pro"}}),
    ("rpush",  ("queue:orders", '{"id": 1}', "tail"), {}),
    ("sadd",   ("members:vip", "ann", "2"), {}),
]
```
**Sufficiency**: action → command mapping; str values pass as-is, non-str values serialize to
JSON text at execution only — the deterministic-replay contract (D3).

#### `test_execute_skips_empty_values_members_and_mapping`

**Input**: `rpush` with `values=[]`, `sadd` with `members=[]`, `hset` with `values={}`.
**Assertions**: `client.commands == []`.
**Sufficiency**: the empty-rows precedent — a declared no-op executes no command (redis would reject argless RPUSH/SADD).

#### `test_execute_unknown_action_names_the_operation`

**Input**: `DataOperation(action="zadd", payload={"key": "k", "members": []})` through `engine.apply([...])` with `_started = True`.
**Assertions**: `pytest.raises(EngineError, match=r"service 'cache': zadd failed: unknown redis action 'zadd'")`.
**Sufficiency**: the deferred v1 surface fails readably if reached through a hand-built payload; the base wrapping names service + action + cause.

#### `test_execute_failure_wraps_into_engine_error_through_apply`

**Setup**: `FakeRedisClient` scripted to raise `redis.exceptions.ResponseError("OOM")`.
**Input**: a `set` operation through `engine.apply([...])`.
**Assertions**: `pytest.raises(EngineError, match=r"service 'cache': set failed.*OOM")`.
**Sufficiency**: the "failed command surfaces as the engine error naming the service, the operation, and the cause" requirement.

#### `test_wipe_flushes_the_declared_database`

**Setup**: `FakeRedisClient` on `engine._client`.
**Input**: `engine._wipe()`.
**Assertions**: `client.commands == [("flushdb", (), {})]`.
**Sufficiency**: reset is one cheap command against the open session connection — bound to the declared db by construction (the client's `db`).

#### `test_close_plane_closes_the_client_once`

**Input**: `_close_plane()` twice with a client set.
**Assertions**: `client.closed == 1`; `engine._client is None` after the first call.
**Sufficiency**: one connection per session closed on stop; stop stays safe when repeated.

#### `test_start_applies_startup_operations_and_journals_them`

**Setup**: fakes armed (module container, namespace, clock); startup =
`[set_op, hset_op]`.
**Input**: `engine.start(startup)` → base flow.
**Trace**: container start (no-op strategy) → `_wait_ready` (first ping True) → `_open_plane`
(eager ping) → no-op migrate → operations applied in order.
**Assertions**: `engine._journal == [set_op, hset_op]`; client commands ordered `set` then `hset`; `engine.stop()` afterwards leaves `engine._container is None` and `client.closed == 1`.
**Sufficiency**: startup data is the initial baseline — the exact replay input of every reset.

#### `test_reset_flushes_then_replays_the_journal`

**Setup**: fakes; `engine._client` set, `_started = True`, `_journal = [set_op]`.
**Input**: `engine.reset()`.
**Assertions**: command order `[("flushdb", ...), ("set", ...)]`; the container stop counter unchanged (no restart).
**Sufficiency**: FLUSHDB + journal replay with no container restart — the ADR reset decision; the connection survives.

#### `test_redis_view_declares_the_four_operations`
(`tests/sandbox/data/test_redis.py`)

**Setup**: `DataBatch()` recorder; `RedisInstance("cache", InstanceAddress("127.0.0.2", 16379), batch)`.
**Input**: `set("k", "v")`; `hset("h", {"f": 1})`; `rpush("l", [1, 2])`; `sadd("s", ["a"])`.
**Trace**: four `DataOperation`s appended; nothing executed (no engine involved).
**Assertions**:
```
[(op.action, op.payload) for op in batch.take()] == [
    ("set",   {"key": "k", "value": "v"}),
    ("hset",  {"key": "h", "values": {"f": 1}}),
    ("rpush", {"key": "l", "values": [1, 2]}),
    ("sadd",  {"key": "s", "members": ["a"]}),
]
```
and `(view.name, view.host, view.port) == ("cache", "127.0.0.2", 16379)`.
**Sufficiency**: the declare-only view contract — payload shapes match the engines contract field-for-field; the batch drains on take.

#### `test_services_accepts_redis_presets_for_all_actions`
(`tests/sandbox/data/test_presets.py`)

**Setup**: none. **Input**: `services(redis={"cache": [four valid declarations]})` applied to a dummy function.
**Trace**: kind check passes (five kinds) → grammar validation passes → marker attached.
**Assertions**: the marker carries the presets verbatim; `usefixtures("sandbox")` stamped; no exception.
**Sufficiency**: the preset surface accepts the redis kind — decoration-time validation passes valid shapes.

#### `test_enqueue_presets_reads_the_redis_action_from_the_declaration`
(`tests/sandbox/test_sandbox.py`)

**Setup**: `SandboxHarness` with a redis service `cache` (fake engine records applied).
**Input**: `sandbox.enqueue_presets({"redis": {"cache": [{"action": "hset", "key": "user:1", "values": {"name": "Ann"}}]}})`.
**Trace**: `_require_service("redis", "cache")` passes → action read from the declaration → `DataOperation(action="hset", payload={"key": ..., "values": ...})` into the current batch.
**Assertions**: return value `1`; the batch's operation equals the expected `DataOperation`; `apply_pending` routes it to the `cache` engine group.
**Sufficiency**: the four-action kind enqueues per-declaration actions — the D5 mechanism.

#### `test_sandbox_redis_factory_binds_the_redis_view`

**Setup**: `SandboxHarness` started with a redis service `cache` (address `127.0.0.2:6379`).
**Input**: `sandbox.redis("cache")`.
**Assertions**: `isinstance(view, RedisInstance)`; `(view.name, view.host, view.port) == ("cache", "127.0.0.2", 6379)`; a `view.set(...)` declaration lands in the live batch and `apply_pending` routes it to the `cache` engine.
**Sufficiency**: the facade accessor returns the view bound to the current batch — the test-facing surface.

#### `test_startup_operations_assemble_the_redis_section_last`

**Setup**: harness config with `data.vault`/`data.http`/`data.postgres` for their services and
`data.redis.cache = [set declaration]`.
**Input**: `sandbox._startup_operations("cache")`.
**Assertions**: the assembled list is exactly `[DataOperation(kind="redis", action="set", payload={"key": ..., "value": ...})]` — the `action` key stripped from the payload, values verbatim.
**Sufficiency**: the section→operation assembly for redis — action to `DataOperation.action`, remaining fields to the payload, declaration never mutated; the redis section assembles after the other three loops.

---

### Negative Tests

#### `test_load_fails_password_on_a_non_redis_entry`
(`tests/sandbox/config/test_loader.py`)

**Setup**: `sandbox_yaml` with `db: {kind: postgresql, password: x}` + valid instance.
**Input**: `validate_written()`.
**Trace**: `_validate_redis_keys` → kind ≠ redis with `password` present.
**Assertions**: `pytest.raises(ValueError, match=r"services\.db.*password and db are accepted only on redis entries")`.
**Sufficiency**: the kind-specific-key common rule — password placement fails at load naming the entry.

#### `test_load_fails_db_on_a_non_redis_entry`

**Input**: `payments: {kind: http, db: 3}`.
**Assertions**: same message shape naming `services.payments`.
**Sufficiency**: the db key follows the same placement rule.

#### `test_load_fails_db_outside_the_range`

**Setup/Input**: parametrized `db: 16`, `db: -1` on a redis entry.
**Assertions**: `pytest.raises(ValueError, match=r"services\.cache\.db: must be an integer within 0-15")`.
**Sufficiency**: the 0–15 range is enforced at document load — before any container starts.

#### `test_load_fails_db_of_wrong_type`

**Setup/Input**: parametrized `db: 2.5` (YAML float), `db: "2"` (string), `db: true` (bool).
**Assertions**: the same db error naming the entry.
**Sufficiency**: bools are ints in Python — the explicit bool guard prevents `db: true` passing as db 1 (D9).

#### `test_load_fails_empty_password`

**Input**: `cache: {kind: redis, password: ""}`.
**Assertions**: `pytest.raises(ValueError, match=r"services\.cache\.password: must be a non-empty string")`.
**Sufficiency**: an empty password would silently mean no-auth in the module — rejected to keep "present = authenticated" truthful (D7).

#### `test_load_fails_topics_on_redis`

**Input**: `cache: {kind: redis, topics: [...]}`.
**Assertions**: `pytest.raises(ValueError, match=r"topics are accepted only on kafka entries")`.
**Sufficiency**: the rejected-keys rule — redis joins every other non-kafka kind.

#### `test_load_fails_migrations_on_redis`

**Input**: `cache: {kind: redis, migrations: {location: x}}`.
**Assertions**: `pytest.raises(ValueError, match=r"migrations are accepted only on postgresql entries")`.
**Sufficiency**: the migrate hook stays no-op because load rejects the declaration — both halves of the contract.

#### `test_load_fails_redis_declaration_without_action`

**Input**: `data.redis.cache: [{key: k, value: v}]`.
**Assertions**: `pytest.raises(ValueError, match=r"data\.redis\.cache: every declaration requires an 'action' key \(set, hset, rpush, or sadd\)")`.
**Sufficiency**: the action key is the kind's operation selector — its absence fails at load naming the entry.

#### `test_load_fails_redis_declaration_with_unknown_action`

**Input**: `{action: zadd, key: k, members: [a]}`.
**Assertions**: the same action-key error (zadd is deferred to the next iteration).
**Sufficiency**: the v1 surface boundary is enforced at load, not at container start.

#### `test_load_fails_redis_declaration_with_missing_or_extra_fields`

**Setup/Input**: parametrized — `set` without `value`; `hset` without `values`; `rpush` carrying `members`; a `set` carrying both `value` and `values`.
**Assertions**: `pytest.raises(ValueError, match=r"data\.redis\.cache: a '(set|hset|rpush|sadd)' declaration carries exactly")`.
**Sufficiency**: the exact key set — extras are author errors (wrong field for the action) and fail naming the entry (D4).

#### `test_load_fails_redis_declaration_with_wrong_field_types`

**Setup/Input**: `hset` with `values: [1]` (list, not mapping); `rpush` with `values: {a: 1}`; `sadd` with `members: x`; `key: 5`.
**Assertions**: `ValueError` naming `data.redis.cache` and the field.
**Sufficiency**: shallow type checks fail at load instead of as client `DataError` at container-start time.

#### `test_load_fails_redis_section_targeting_a_non_redis_service`

**Input**: `data.redis.db: [...]` with `db` a postgresql service.
**Assertions**: `pytest.raises(ValueError, match=r"data\.redis\.db: targets service 'db' of kind 'postgresql', the section requires kind 'redis'")`.
**Sufficiency**: section targets must match the kind — the shared `_read_section` rule extended to redis.

#### `test_load_fails_unknown_service_kind_lists_redis` (re-pointed)

**Setup**: the existing unsupported-kind test currently using `kind: redis`.
**Input**: re-pointed to `kind: mysql` (D10).
**Assertions**: `pytest.raises(ValueError, match=r"mysql.*postgresql.*kafka.*vault.*http.*redis")`.
**Sufficiency**: redis joined the supported list — the negative example must move, and the message must now list redis (acceptance).

#### `test_services_fails_redis_preset_without_action`
(`tests/sandbox/data/test_presets.py`)

**Input**: `services(redis={"cache": [{"key": "k", "value": "v"}]})`.
**Assertions**: `pytest.raises(ValueError, match=r"services preset 'redis\.cache'.*'action' key")`.
**Sufficiency**: decoration-time grammar — the same rule as the loader, at the preset entry point.

#### `test_services_fails_redis_preset_with_wrong_fields`

**Setup/Input**: parametrized — missing `value` for `set`; `hset` with `members`; extra `value` on an `rpush`.
**Assertions**: `ValueError` naming `services preset 'redis.cache'`.
**Sufficiency**: presets carry "the same fields as the matching view operation" plus the action key — enforced where the test author sees it.

#### `test_services_fails_unsupported_kind_lists_redis` (re-pointed)

**Input**: `services(mysql={"x": []})` (was `redis`).
**Assertions**: `pytest.raises(ValueError, match=r"mysql.*postgresql.*kafka.*vault.*http.*redis")`.
**Sufficiency**: same re-pointing rationale at the preset surface.

#### `test_enqueue_presets_fails_redis_declaration_without_action`
(`tests/sandbox/test_sandbox.py`)

**Setup**: harness with a redis service. **Input**: `enqueue_presets({"redis": {"cache": [{"key": "k", "value": "v"}]}})`.
**Assertions**: `pytest.raises(ValueError, match=r"services preset 'redis\.cache': every declaration requires an 'action' key")`.
**Sufficiency**: a hand-built `pybuggy_services` marker (bypassing the decorator) fails with the readable message instead of a bare pydantic error (D5).

#### `test_sandbox_redis_view_kind_mismatch_and_unknown_name`

**Input**: `sandbox.redis("db")` on a harness whose `db` is postgresql; `sandbox.redis("ghost")`.
**Assertions**: `pytest.raises(ValueError, match=r"no redis service named 'db'")`; `match=r"no redis service named 'ghost'.*cache \(redis\)"`.
**Sufficiency**: the facade fail-fast contract listing the configured services.

#### `test_build_engine_unmapped_kind_lists_five_kinds`
(`tests/sandbox/engines/test_runtime.py`, updated)

**Input**: `build_engine(ServiceConfig(name="x", kind="grpc"))` (loader bypassed).
**Assertions**: match extended to `...postgresql.*kafka.*vault.*http.*redis`.
**Sufficiency**: the engine-factory error lists the five kinds.

#### `test_install_and_plugin_gate_unsupported_kind_re_pointed`
(`tests/plugin/test_install.py`, `tests/plugin/test_sandbox_plugin.py`)

**Input**: documents with `cache: { kind: mysql }` (was redis) through the plugin gate.
**Assertions**: the existing matches updated to `mysql.*not one of the supported kinds` with the five-kind list.
**Sufficiency**: the plugin installation gate keeps rejecting unknown kinds; redis no longer trips it.

---

### Edge Case Tests

#### `test_load_accepts_db_boundaries_zero_and_fifteen`

**Input**: parametrized `db: 0` and `db: 15` on a redis entry.
**Assertions**: validation passes; `config.services["cache"].db` equals the input.
**Sufficiency**: inclusive boundaries of the documented range (boundary-table convention).

#### `test_load_ignores_absent_password_and_db`

**Input**: `cache: {kind: redis}` only.
**Assertions**: `password is None`, `db == 0` — the primary no-auth mode, default database.
**Sufficiency**: the ADR primary mode — nothing declared, defaults reproduce the conventional client behavior.

#### `test_execute_serializes_plain_scalars_deterministically`

**Input**: `set` with `value=5`, `value=True`, `value=None`, `value=2.5`.
**Assertions**: client receives `"5"`, `"true"`, `"null"`, `"2.5"`.
**Sufficiency**: the JSON wire form is fixed for every scalar — replay and cross-language readers see one encoding (str `5` and int `5` intentionally share `"5"`, the kafka-precedent ambiguity).

#### `test_execute_fails_readably_on_non_serializable_values`

**Setup**: `FakeRedisClient` is bypassed — the value is a plain `object()` (non-JSON-serializable).
**Input**: a `set` operation through `engine.apply([...])`.
**Assertions**: `pytest.raises(EngineError, match=r"service 'cache': set failed")` with the `TypeError` as cause.
**Sufficiency**: "strings or JSON-serializable plain data" — violations surface as engine errors naming the operation, never as a bare traceback.

#### `test_reset_with_empty_journal_only_flushes`

**Setup**: fakes; `_journal = []`, `_started = True`.
**Input**: `engine.reset()`.
**Assertions**: commands == `[("flushdb", (), {})]`.
**Sufficiency**: a baseline-less redis service still resets to empty — FLUSHDB alone is the wipe.

#### `test_stop_is_safe_before_start`

**Input**: `RedisEngine(config).stop()` twice on a fresh engine.
**Assertions**: no exception; no container/client touched.
**Sufficiency**: the stop guarantee on every exit path — including failed starts (base flow calls stop on failure).

#### `test_redis_engine_container_roundtrip` (docker-gated, `TestRedisEngineContainer`)

**Setup**: `requires_docker`; `RedisEngine(ServiceConfig(name="cache", kind="redis", db=2))`.
**Input**: `engine.start([set_op("feature-flag/a", "enabled"), hset_op("user:1", {"name": "Ann"})])`.
**Trace**: real container start → engine PING readiness → plane opens on db 2 → operations apply.
**Assertions**: a verification client (`redis.Redis(host, port, db=2)`) reads back
`GET feature-flag/a == b"enabled"` (str value passes as-is) and
`HGETALL user:1 == {b"name": b"Ann"}`; a client on `db=0` sees none of the keys.
**Sufficiency**: the end-to-end vertical — declared db isolation proves both the connect and the visibility contract.

#### `test_redis_engine_container_reset_flushes_only_the_declared_db` (docker-gated)

**Setup**: as above on `db=1`; journal `[set_op]`; after start, write an extra key on `db=1`
and one key on `db=0` through verification clients.
**Input**: `engine.reset()`.
**Assertions**: `db=1` holds exactly the journaled key again; the `db=0` key survives; the
container was never restarted (same mapped port before/after).
**Sufficiency**: the FLUSHDB-of-declared-database contract and the no-restart reset, proven live.

#### `test_redis_engine_container_password_mode` (docker-gated)

**Setup**: `RedisEngine(ServiceConfig(name="cache", kind="redis", password="sandbox-redis"))`.
**Input**: `engine.start([])`.
**Assertions**: start completes (engine PING with the password succeeded — the container requires auth); a passwordless verification client's `ping` raises `AuthenticationError`.
**Sufficiency**: present password ⇒ authenticated container and working data plane; the no-password mode is covered by the two tests above.

---

## Additional Instructions for the Implementation Agent

- Implement bottom-up in the established slice order: **config → engines → data → sandbox
  root**, then `pyproject.toml`, then the re-pointed/extended tests, then the docs pages
  (`docs/sandbox/configuration.md`, `docs/sandbox/api.md`, `docs/sandbox/index.md` — five-kind
  lists, redis keys, `data.redis` row, `redis:8-alpine` image row, `sandbox.redis(name)` and
  `RedisInstance` methods, `@services(redis=...)`).
- `pyproject.toml`: extend the existing entry to `testcontainers[postgres,redis]>=4.15` and add
  `redis>=7.0` — do not fork a second testcontainers dependency line (one resolution).
- Never log or surface the password in any message; readiness/operation errors carry
  host:port and causes only.
- Do not mutate declared payloads anywhere on the apply path — build fresh dicts
  (`_startup_operations` strips `action` into a new payload dict; `_wire` builds fresh
  strings). Journal replay depends on this.
- Keep `decode_responses` at its default (write-only v1 plane); read-back belongs to the next
  iteration (`zadd`, TTL, deletion, assertions — deferred by the ADR; do not add them).
- The grpc "not supported yet" branch and every existing kind's behavior stay untouched
  beyond the shared-surface extensions (kind lists, action registry, section order).
- Validation commands: `pytest tests/ -x` green; `ruff check` clean; facade checks
  `python -c "from goga_tool_pybuggy.sandbox.engines import RedisEngine"` and
  `python -c "from goga_tool_pybuggy.sandbox.data import RedisInstance"`.
- Acceptance criteria map 1:1 to the task file; the test stack above covers every criterion
  (document validation, section order, engine mapping/image/readiness, password modes,
  session connection, four operations, reset semantics, facade, presets, packaging, docs).
