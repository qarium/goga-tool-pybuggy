# Plan: `sandbox-redis` — Redis as the fifth sandbox dependency kind

## Purpose

Implement the redis dependency kind end to end across the four sandbox cells: a real
`redis:8-alpine` container driven by redis-py, integrated into the same configuration /
engine / data-view / preset surface as the existing four kinds. After implementation a
sandbox document may declare `services.cache: {kind: redis, password: ..., db: N}`, a
`data.redis` startup section, `@services(redis=...)` presets, and tests may call
`sandbox.redis("cache").set/hset/rpush/sadd(...)`; the engine owns bounded PING readiness,
one session connection to the declared logical database, wire serialization at execution,
and FLUSHDB-of-declared-db reset with journal replay.

The contract surface (four CODEMANIFESTs) is already materialized in the working tree by the
apply-architecture stage; the gap is the implementation: `engines/redis.py` and
`data/redis.py` do not exist, the config models/loader know four kinds, the registries and
facades carry no redis entries, `pyproject.toml` carries no redis dependencies, tests and
docs do not cover the kind. Strategy: bottom-up in the established slice order — packaging →
config → engines → data → sandbox root → docker-gated integration tests → docs — one ralphex
task per slice, TDD inside every coding task.

## Context

### Contract Surface

Only the changed/new entities are listed; every other entity of the four cells is unchanged
background.

**Entity: `ServiceConfig` (changed)** — config cell
- Type: class (pydantic model), `location: goga_tool_pybuggy/sandbox/config/service.py`
- Facade obligation: importable from `goga_tool_pybuggy.sandbox.config`
- Signature gains: `password: str | None = None`, `db: int = 0` (redis-only, placement
  validated by the loader — no model validator changes)
- Existing surface: `name`, `kind`, `image`, `topics`, `probe`, `migrations`;
  `model_config = ConfigDict(kw_only=True, extra="forbid")` unchanged
- Semantic requirements: `kind` list extends to postgresql, kafka, vault, http, redis;
  docstring kinds list and field docs extend; `password` — absent starts the service without
  authentication, present starts it with `--requirepass`; `db` — 0 by default, valid range
  0–15

**Entity: `StartupData` (changed)** — config cell
- Type: class (pydantic model), `location: goga_tool_pybuggy/sandbox/config/startup_data.py`
- Facade obligation: importable from `goga_tool_pybuggy.sandbox.config`
- Gains the section `redis: dict[str, list[dict[str, object]]] = {}` — last in the fixed
  section order vault, http, postgres, redis
- Semantic requirements: declarations target services by name; each declaration carries the
  `action` key (set, hset, rpush, sadd) plus the fields of the matching view operation (key
  with value/values/members); within a section the declaration order is the application
  order; no kafka section ever

**Routine: `validate_sandbox_config` (changed)** — config cell
- Type: function, `location: goga_tool_pybuggy/sandbox/config/loader.py`
- Signature unchanged: `(document: dict[str, object], location: Path | str) -> SandboxConfig`
- Behavioral changes (contract Algorithm steps 3–4):
  - kind list five: postgresql, kafka, vault, http, redis; the grpc "not supported yet"
    branch untouched
  - `password`/`db` accepted on the redis kind only — either on any other kind fails naming
    the entry; `db` must be an integer within 0–15 (bools rejected), anything else fails at
    document load naming the entry
  - `data.redis` declarations: action key plus the matching view operation fields — anything
    else fails naming the entry
  - every failure message names the carried document location and the offending entry

**Entity: `BaseEngine::RedisEngine` (new, mutation of `BaseEngine`)** — engines cell
- Type: class, `location: goga_tool_pybuggy/sandbox/engines/redis.py`
- Facade obligation: importable from `goga_tool_pybuggy.sandbox.engines`
- Constructor: `RedisEngine(config: ServiceConfig)`; inherits `start/apply/record/reset/stop`
  and the `address` property from `BaseEngine`
- Contract behavior (annotation summary): community redis module container with the
  product-pinned default image `redis:8-alpine` unless overridden; the module's built-in wait
  strategy replaced through the core container's `waiting_for` — readiness is the engine's
  PING probe bounded by the declared deadline at the declared interval; expired deadline or
  wrong password surfaces as the engine error naming the service and the waited check —
  never a hang; declared password reaches the container command through the module
  constructor (`--requirepass`); absent password starts redis without authentication — the
  primary mode. Data plane: the official redis client over one connection to the declared
  logical database, opened after readiness, held for the session, closed on stop. Four v1
  operations — set, hset, rpush, sadd — values serialized to the wire form at execution; the
  declared payload is never rewritten, so journal replay is deterministic. Migrate hook stays
  the no-op default. Wipe: FLUSHDB of the declared database, then journal replay; the
  container never restarts and the connection survives the reset
- Requirements: one connection to the declared db for the session, closed on stop; the wipe
  and the seed address the declared db only — FLUSHDB wipes no other logical database; a
  failed command surfaces as the engine error naming the service, the operation, and the
  cause
- Annotation context: header `Usages` gained `redis: .goga/usages/cooks/redis.md` with the
  global line "Use `redis` for the redis data plane and container"; `RedisEngine`
  annotations reference `redis` and `testcontainers`

**Routine: `build_engine` (changed)** — engines cell
- Type: function, `location: goga_tool_pybuggy/sandbox/engines/runtime.py`
- `KIND_ENGINES` gains `"redis": RedisEngine`; the unmapped-kind error lists the five kinds;
  docstring mentions that the redis password and db declarations reach the built engine

**Entity: `DataOperation` (changed — docstring only)** — engines cell
- `location: goga_tool_pybuggy/sandbox/engines/operation.py`; no model change; the docstring
  action set extends to "insert, produce, put, stub, set, hset, rpush, or sadd" and the kind
  list gains redis; a redis operation's payload carries the key plus value, values, or
  members — the fields of the matching view operation

**Entity: `BaseEngine` (changed — docstring only)** — engines cell
- `location: goga_tool_pybuggy/sandbox/engines/base.py`; no behavior change; the `config`
  attribute descriptions (class docstring + `__init__` Args) mention "password and db
  declarations (consumed by the redis kind)"

**Entity: `RedisInstance` (new)** — data cell
- Type: class, `location: goga_tool_pybuggy/sandbox/data/redis.py`
- Facade obligation: importable from `goga_tool_pybuggy.sandbox.data`
- Constructor: `RedisInstance(name: str, address: InstanceAddress, batch: DataBatch)`;
  mirrors `HttpInstance` exactly
- Properties: `name -> str`, `host -> str`, `port -> int`
- Methods (declare-only — nothing executes at declaration):
  - `set(key: str, value: object)` — one string value write; `value` is a string or
    JSON-serializable plain data, serialized at execution; the declared payload is never
    rewritten
  - `hset(key: str, values: dict[str, object])` — one hash write (field-to-value mapping)
  - `rpush(key: str, values: list[object])` — one list tail append, in list order
  - `sadd(key: str, members: list[object])` — one set members add

**Routine: `services` (changed)** — data cell
- `location: goga_tool_pybuggy/sandbox/data/presets.py`; `_SUPPORTED_KINDS` five; redis
  declarations validated at decoration: the action key (set, hset, rpush, sadd) plus the
  matching fields (key with value, values, or members) — anything else fails naming the
  declaration (`services preset 'redis.{name}'`); nothing executes at decoration

**Entity: `Sandbox` (changed)** — sandbox root
- `location: goga_tool_pybuggy/sandbox/sandbox.py`
- New method `redis(name: str) -> instance: RedisInstance` — the test-facing view of the
  named redis service; unknown name or kind mismatch fails fast listing the configured
  services
- `enqueue_presets`: the marker payload validation reads the redis action from each
  declaration (the kind has no single fixed action)
- `_startup_operations`: the fixed section order is vault secrets, http mappings, postgres
  init, then redis data (step 3 of the `start` algorithm)
- `ViewT` bound gains `RedisInstance`; root `Imports.Types` gains `RedisInstance` from the
  data cell

### Interaction and Data Flow (verbatim from the design)

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

Data flows:

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

Design and implementation order (bottom-up, the established direction): config → engines →
data → sandbox root → pyproject/docs/tests. `RedisEngine` imports `ServiceConfig` (config
cell) and `BaseEngine`/`DataOperation` (engines cell); `RedisInstance` imports
`DataOperation`/`InstanceAddress` (engines) and `DataBatch` (data); `Sandbox` imports
`RedisInstance` (data). No new cross-cell edges beyond the declared ones.

### Re-exports

- `RedisEngine` — source: new module `goga_tool_pybuggy/sandbox/engines/redis.py`; facade
  obligation: importable from `goga_tool_pybuggy.sandbox.engines` (`__init__.py` import +
  `__all__` entry, ruff-sorted between `PostgresEngine` and `VaultEngine`).
- `RedisInstance` — source: new module `goga_tool_pybuggy/sandbox/data/redis.py`; facade
  obligation: importable from `goga_tool_pybuggy.sandbox.data` (`__init__.py` import +
  `__all__` entry, ruff-sorted between `PostgresInstance` and `VaultInstance`).

### Usages Context

- `redis` (engines header Usages → `.goga/usages/cooks/redis.md`): the redis-py client
  contract (lazy connect, one client per session, write-only v1 plane with `decode_responses`
  default False), the community `RedisContainer` module contract (constructor `password`
  wiring, `waiting_for` replacement seam, `get_client` kwargs), the engine-owned PING
  readiness loop, the four operation commands, FLUSHDB-of-declared-db reset semantics. How:
  `redis.Redis(host, port, db, password, socket_timeout)`; `client.ping()`;
  `client.set/hset(mapping=)/rpush(*)/sadd(*)`; `client.flushdb()`; `client.close()`;
  `RedisContainer(image, password=..., labels=...)` + `container.waiting_for(...)`.
  Version floor `redis>=7.0` — the pinned testcontainers 4.15 redis extra forces `redis>=7`;
  one consistent resolution.
- `testcontainers` (engines + root Usages → `.goga/usages/cooks/testcontainers.md`): container
  lifecycle, module/generic containers, `waiting_for`, labels, ryuk-backed stop guarantee,
  `Network` attach. The pinned 4.15 platform every engine already drives; the community redis
  module with the engine-installed no-op strategy.
- `conventions` (all four cells → `.goga/usages/conventions.md`): the mandatory-rules source
  of this plan — see "Mandatory Rules"; relative imports, kw_only pydantic models, Google
  docstrings, structured logging with `extra` metadata (no secrets in log output — the redis
  password never appears in any log or error), blank-line blocking, test mirroring; `ruff`
  clean; `pytest tests/ -x` green.

### Imported Usages

- `sandbox-file` from `goga_tool_pybuggy/sandbox/config` (root Imports) —
  `goga_tool_pybuggy/sandbox/config/.usages/sandbox-file.md`; updated by the apply stage with
  the redis entry (password/db keys), the five-kind rule, the `redis:8-alpine` image row, the
  "Redis keys" subsection, PING readiness, `{{cache.host}}`/`{{cache.port}}`, the `data.redis`
  table row + example, and the extended failure list. Consumer context for
  `Sandbox`/`render_service_env`.
- `data-operations` from `goga_tool_pybuggy/sandbox/data` (root Imports) —
  `goga_tool_pybuggy/sandbox/data/.usages/data-operations.md`; updated with the redis view,
  preset, ordering, and reset documentation. Consumer context for the view/preset surface.
- `migration-set` from `goga_tool_pybuggy/sandbox/migrations` (engines/config Imports) —
  unchanged by this task; referenced by `validate_sandbox_config` and `PostgresEngine` only.

### Local Usages

No new `.usages/` files and no `.usages/` tasks. The apply-architecture stage already updated
all three consumer docs; the design review verified them current — implementation must not
touch them:

- `goga_tool_pybuggy/sandbox/config/.usages/sandbox-file.md` — status: current (redis entry,
  keys, image row, readiness, placeholder and `data.redis` documentation).
- `goga_tool_pybuggy/sandbox/data/.usages/data-operations.md` — status: current (redis view,
  preset, ordering, reset).
- `goga_tool_pybuggy/sandbox/.usages/sandbox-session.md` — status: current (redis direct-use
  and baseline examples, per-test FLUSHDB reset note).

All redis consumer guidance belongs to the three existing domains — supplement, not
new-domain, per the cookbook rules. No CODEMANIFEST `Usages` key points at a cell's own
`.usages/` files.

### External Dependencies

- `redis>=7.0` (redis-py, new direct dependency) — the data plane client; exceptions:
  `AuthenticationError(ConnectionError)`, `TimeoutError(RedisError)`, `DataError(RedisError)`;
  lazy connect; `close()` releases the pool.
- `testcontainers[postgres,redis]>=4.15` (extended existing entry) — the community redis
  module `testcontainers.community.redis.RedisContainer`:
  `RedisContainer(image="redis:latest", port=6379, password=None, **kwargs)` installs
  `PingWaitStrategy()` in `super().__init__`, publishes 6379, wires `--requirepass` when the
  password is truthy. Passing `_wait_strategy` ourselves would be a duplicate keyword — the
  only override seam is `waiting_for(...)` after construction (verified against the pinned
  sources).
- `pytest` / `pytest-cov` / `ruff` — existing test tooling (no new test libraries).
- Docker (for the gated integration tests only) — via the existing `requires_docker` skip.

## Facts

- Verified against the pinned `testcontainers==4.15.0` community redis module: the constructor
  calls `super().__init__(image, _wait_strategy=PingWaitStrategy(), **kwargs)`, then
  `with_exposed_ports(port)` and, for a truthy password,
  `with_command(f"redis-server --requirepass {password}")`; `DockerContainer.waiting_for(strategy)`
  overwrites `self._wait_strategy` and `start()` runs it when not `None` — a post-construction
  `waiting_for(...)` call replaces the module's built-in strategy.
- Verified against the pinned `redis==7.0`: `AuthenticationError` inherits `ConnectionError`;
  `TimeoutError` inherits `RedisError`; `Redis` connects lazily; `Redis.close()` releases the
  connection pool. Catch order in the probe is load-bearing — the `AuthenticationError` clause
  must precede the `ConnectionError` clause or auth failures retry to expiry.
- The base engine (`engines/base.py`) already provides everything the family contract needs:
  `_container_port` class attribute read by the `address` property; `_readiness_bounds`
  (`ProbeConfig` defaults 30.0/0.5); `_probe_until(timeout, interval, attempt, failure)`
  raising `RuntimeError(f"{failure} within {timeout:g}s")` on expiry; `_run_step` wrapping
  step failures into `EngineError(f"service '{name}': {failure}: {exc}")`; `_run_operation`
  wrapping operation failures into `EngineError(f"service '{name}': {action} failed: {exc}")`;
  `_attach_network` joining under the service-name alias; `stop()` safe on every exit path.
- Family constants precedent: `postgres.py` — `DEFAULT_IMAGE = "postgres:16-alpine"`,
  `CONTAINER_PORT = 5432`, `PROBE_CONNECT_TIMEOUT = 2`, `SANDBOX_LABELS =
  {"pybuggy-sandbox": "true"}`; `http.py` — `PLANE_TIMEOUT = 5`.
- The loader today: `_SUPPORTED_KINDS = ("postgresql", "kafka", "vault", "http")`,
  `_SECTION_KINDS = {"vault": "vault", "http": "http", "postgres": "postgresql"}`; per-entry
  validators run in `_read_services` (`_validate_kind`, `_validate_topics`,
  `_validate_migrations`) before the `ServiceConfig` model build; the vault shape validator
  (`_validate_vault_declarations`) is the precedent for section declaration checks inside
  `_read_section`; unknown data-section errors list `_SECTION_KINDS` (dict order).
- The presets decorator today validates kinds, mapping/list shapes, and postgres rows only;
  the marker is `pytest.mark.pybuggy_services(presets=presets)` + `usefixtures("sandbox")`.
- `Sandbox._KIND_ACTIONS: dict[str, str]` maps the four single-action kinds;
  `enqueue_presets` builds `DataOperation(..., action=_KIND_ACTIONS[kind], payload=declaration)`;
  `_startup_operations` assembles vault/http/postgres loops in that order; the view contract
  loops in `tests/sandbox/test_sandbox.py` enumerate the four kind factory names.
- The sandbox test harness (`tests/sandbox/conftest.py`) provides `requires_docker`,
  `sandbox_yaml` (writes `.goga/tools/pybuggy/sandbox.yml` under `tmp_path` + chdir),
  `FakeEngine`, `FakeService`, `FakeNetwork`; `tests/sandbox/test_sandbox.py` provides
  `sandbox_config()` (one service of every kind — vault `secrets`, http `payments`, kafka
  `events`, postgresql `db`) and `SandboxHarness`/`started`;
  `tests/sandbox/engines/test_http.py` provides `install_fake_clock` for `_probe_until` tests.
- The plugin gate flows through `validate_sandbox_config` — the two plugin tests using
  `kind: redis` as their unsupported-kind example fail once the loader accepts redis; the
  design re-points them (and the loader/presets equivalents) to `kind: mysql` (D10).
- `pyproject.toml` carries `testcontainers[postgres]>=4.15`; no `redis` entry exists; no
  `.venv` exists in the workspace yet.

## Gap Analysis

- **Missing contract entities**: `goga_tool_pybuggy/sandbox/engines/redis.py` (`RedisEngine`,
  the whole file); `goga_tool_pybuggy/sandbox/data/redis.py` (`RedisInstance`, the whole
  file).
- **Missing facade exposure**: `RedisEngine` absent from
  `goga_tool_pybuggy/sandbox/engines/__init__.py` (`__all__` + import); `RedisInstance`
  absent from `goga_tool_pybuggy/sandbox/data/__init__.py`.
- **API mismatches (models/registries)**: `ServiceConfig` lacks `password`/`db`;
  `StartupData` lacks the `redis` section; `KIND_ENGINES` lacks `"redis"`; loader
  `_SUPPORTED_KINDS`/`_SECTION_KINDS` lack redis; presets `_SUPPORTED_KINDS` lack redis;
  `Sandbox` lacks `redis(name)`, the `ViewT` bound entry, the `_KIND_ACTIONS` redis entry,
  and the redis loop in `_startup_operations`.
- **Docstring drift (contract-mirroring surfaces)**: `operation.py` action set / kind list;
  `base.py` config attribute descriptions; `runtime.py build_engine` docstring; both facade
  module docstrings; `service.py` / `startup_data.py` docstrings.
- **Test coverage gaps**: no `tests/sandbox/engines/test_redis.py`, no
  `tests/sandbox/data/test_redis.py`; the loader, presets, runtime, sandbox, and plugin
  suites carry no redis scenarios and three tests use `redis` as an unsupported-kind example
  that must be re-pointed (`tests/sandbox/config/test_loader.py` — unknown kind and
  unknown-section matches; `tests/plugin/test_install.py`; `tests/plugin/test_sandbox_plugin.py`);
  the sandbox contract loops enumerate four factories.
- **Packaging gap**: `pyproject.toml` lacks `testcontainers[redis]` and `redis>=7.0`; the
  workspace lacks the virtualenv.
- **Docs gap**: `docs/sandbox/configuration.md`, `docs/sandbox/api.md`, `docs/sandbox/index.md`
  carry four-kind lists, no redis keys, no `data.redis` row, no `redis:8-alpine` image row, no
  `sandbox.redis(name)` / `RedisInstance` / `@services(redis=...)` documentation.
- **Existing code that can be reused**: everything — `BaseEngine` lifecycle/journal/probe
  machinery, `_PostgresContainer` disable-wait precedent, `HttpInstance` as the
  `RedisInstance` mirror, `_validate_vault_declarations` as the declaration-validator
  precedent, the full fake/test-fixture infrastructure. No code is deleted; the grpc branch
  and every existing kind's behavior stay untouched beyond the shared-surface extensions.

---

## Mandatory Rules

Extracted from the project convention (`.goga/usages/conventions.md` — the `conventions`
practice connected by every changed cell) and the project tool configuration
(`pyproject.toml`: ruff `target-version = "py310"`, `line-length = 120`, rule sets
`E,W,F,I,N,UP,B,SIM,PL,PLR,C4,DTZ,PT,ARG,RUF,PTH,C90` + `max-complexity = 10`, format
double-quote/space-indent/LF/magic-trailing-comma, per-file ignores for `tests/**`). These
rules are **mandatory for every task**; they override convenience and apply in addition to
each task's contract annotations. Where a contract annotation and these rules overlap, the
contract wins; where both are silent, the rules decide.

### M1. Coding Style (strictly per `conventions`)

- **M1.1** Python 3.10+ only. No syntax or stdlib usage beyond 3.10 compatibility.
- **M1.2** `pyproject.toml` is the single configuration source; all commands run inside the
  project virtualenv — create it if missing (`python3 -m venv .venv && .venv/bin/pip
  install -e ".[test]"`). Never execute against the system interpreter.
- **M1.3** Imports: **relative** for all intra-package references (`from ..config.service
  import ServiceConfig`, `from .base import BaseEngine`, `from .data import RedisInstance`);
  **absolute** only for stdlib and third-party (`import json`, `import redis`,
  `from testcontainers.community.redis import RedisContainer`). An absolute import of the
  project's own package is forbidden.
- **M1.4** All data models are pydantic with `kw_only=True`. `ServiceConfig` keeps
  `extra="forbid"`; the new `password: str | None = None` and `db: int = 0` carry defaults
  (absence is the explicit default state); `StartupData.redis` defaults `{}`. No model
  validators are added — placement and range are the loader's job (the existing division).
- **M1.5** Type hints are mandatory on every function and method (including tests).
- **M1.6** Docstrings: Google style, on **all** public functions, methods, and classes. First
  line capitalized, ends with a period; `Args` when parameters exist; `Returns` when a value
  returns; `Raises` for exceptions beyond built-ins. Module docstrings update where lists
  changed: `operation.py` (action set eight, kinds five), `base.py` (config description
  gains password/db), `runtime.py` (`build_engine` reach-through), both facades, `service.py`
  and `startup_data.py` kinds/section lists.
- **M1.7** Function-body formatting: one blank line between logical blocks (initialization
  vs conditionals/loops, data preparation vs processing, processing vs return). Match the
  existing modules' visual rhythm — `postgres.py` / `http.py` are the references for
  `engines/redis.py`; `http.py` (data cell) is the reference for `data/redis.py`.
- **M1.8** Logging: structured `logging` with `extra` metadata (`service`, `kind`, `action`,
  `host`, `port`) following the base engine events (`service starting` / `service ready` /
  `service stopped` / `operation executed`); lowercase concise messages; DEBUG for readiness
  and plane events ("redis service ready", "redis plane open"), INFO stays with the base
  lifecycle. **The password never appears in any log or error message** (conventions — log
  content restrictions); readiness messages carry host:port only.
- **M1.9** Dependencies: exactly the Task 1 edits — `testcontainers[postgres]>=4.15` extends
  to `testcontainers[postgres,redis]>=4.15` (one entry, one resolution) and `redis>=7.0` is
  added with a minimum version. Nothing else enters `pyproject.toml`.
- **M1.10** Naming: PascalCase classes, snake_case functions/methods/constants;
  `__all__` stays ruff-sorted (`RUF022`) — engines facade inserts `"RedisEngine"` between
  `"PostgresEngine"` and `"VaultEngine"`; data facade inserts `"RedisInstance"` between
  `"PostgresInstance"` and `"VaultInstance"`.
- **M1.11** Never mutate a declared payload anywhere on the apply path — build fresh dicts
  (`_startup_operations` and `enqueue_presets` strip `action` into a new payload dict;
  `_wire` builds fresh strings). Journal replay determinism depends on this.

### M2. Test Writing Rules (strictly per `conventions`)

- **M2.1** The test tree mirrors the source directly:
  `goga_tool_pybuggy/sandbox/engines/redis.py` → `tests/sandbox/engines/test_redis.py`;
  `goga_tool_pybuggy/sandbox/data/redis.py` → `tests/sandbox/data/test_redis.py`. Existing
  files are extended in place.
- **M2.2** Every test directory carries `__init__.py` (all needed ones exist). Local fixtures
  stay in `tests/<package>/conftest.py`; reuse unchanged: `sandbox_yaml`,
  `SandboxHarness`/`started`, `FakeEngine`, `requires_docker`
  (`from ..conftest import requires_docker`), `install_fake_clock`
  (`from .test_http import install_fake_clock`).
- **M2.3** File names `test_<module>.py`; test functions `test_<what>_<scenario>`
  (self-documenting — who/what, under what condition, what should happen); grouping
  `class Test<Component>:`; docstring-per-test style of the existing suites; minimal
  comments.
- **M2.4** Test categories (mirrored by the ralphex steps): **contract tests** — facade
  accessibility, API shape, signatures — written FIRST, expected to fail; **logic tests** —
  positive, negative, edge — written after implementation; **integration tests** — real
  container, gated on availability — the separate Task 9. Integration tests never replace
  contract or logic tests per entity.
- **M2.5** Edge coverage per the convention: expected exceptions via `pytest.raises`;
  thresholds and ranges via `@pytest.mark.parametrize` with a table including each boundary —
  db `0`/`15` pass, `16`/`-1` fail; wrong types `2.5`/`"2"`/`true` fail; wire scalars
  `5`/`True`/`None`/`2.5` parametrized; declaration field-set matrices parametrized.
- **M2.6** Doubles at external boundaries only: monkeypatch the module seams
  (`redis_module.RedisContainer` → `FakeRedisContainer`; `redis_module.redis` → a fake
  namespace carrying the real `redis.exceptions` classes), recording doubles
  (`FakeRedisClient` records `(name, args, kwargs)`, serves scripted errors, counts
  `close()`), the fake clock for `_probe_until`. Pure logic (models, view declarations,
  grammar validators, payload assembly) is tested mock-free.
- **M2.7** Update the existing tests **in place** (`test_service.py`, `test_startup_data.py`,
  `test_loader.py`, `test_runtime.py`, `test_presets.py`, `test_sandbox.py`,
  `tests/plugin/test_sandbox_plugin.py`, `tests/plugin/test_install.py`) rather than
  duplicating them; add the two new files.
- **M2.8** Test dependencies stay in `[project.optional-dependencies].test`; no new test
  libraries.
- **M2.9** When debugging, fix **implementation code**, never test code, unless the test
  contradicts the design (then stop and re-check the design, never the CODEMANIFEST).
- **M2.10** Skip integration tests with unavailable external dependencies via
  `pytest.mark.skipif` — the docker-gated class reuses `requires_docker`.

### M3. Linters and Formatters — Enforced at Every Development Stage and Every Local Commit

- **M3.1** `ruff` is the project's linter **and** formatter, configured in `pyproject.toml`
  (`target-version = "py310"`, `line-length = 120`, the full select set,
  `max-complexity = 10`, format double quotes / space indent / LF / magic trailing comma).
  The per-file ignores for `tests/**` (`S101`, `ARG001`, `ARG002`, `PLR2004`, `RUF001`,
  `PLC0415`) apply automatically. This plan adds no ruff configuration changes.
- **M3.2** **Stage gate** — every task ends with BOTH commands clean (run in the venv):
  - `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/` (apply
    `.venv/bin/ruff format goga_tool_pybuggy/ tests/` first, then verify)
  - `.venv/bin/ruff check goga_tool_pybuggy/ tests/`
  Formatting fixes are applied before the task's completion checkbox is ticked. Decompose
  when `C90`/complexity or pylint rules demand it. For the non-`.py` tasks (1, 10) the
  command set must still exit 0 over the unchanged tree.
- **M3.3** **Local commit gate** — before **every** `git commit` (one commit per completed
  task, on the current `sandbox-redis` branch):
  1. `.venv/bin/ruff check goga_tool_pybuggy/ tests/` → clean
  2. `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/` → clean
  3. `.venv/bin/pytest tests/ -x` → green (docker-gated tests skip where docker is
     unavailable — a skip is green)
  A commit that fails either ruff command is not made. Fix, re-run, commit. Commits add
  **only the task's own files by name** (`git add <explicit paths> && git commit`) — never
  `git add -A`: the CODEMANIFEST / `.usages/` modifications of the apply-architecture stage
  sitting in the working tree stay uncommitted for the pipeline's commit-changes stage.
- **M3.4** Facade checks follow the convention's command shape
  (`python -c "from package import Entity"`), run in the venv at every task gate where a
  facade changes (Tasks 4 and 6).

### M4. REPL Cycle Rules — Continuous Interactive Evaluation, Hot Reloading, Code Migration

The workflow of every coding task is structured around a live REPL cycle: evaluate as you
write, reload instead of restart, and migrate verified code into source files.

- **M4.1 Continuous evaluation** — develop each entity against a live interpreter session
  (`.venv/bin/python3 -i` or `.venv/bin/python3 -c` probes) with prepared scratch state. For
  every library fact this feature depends on, settle it in the REPL against the installed
  pinned version — never from memory: the community `RedisContainer` constructor kwargs and
  the `waiting_for` replacement seam; the `redis.exceptions` hierarchy
  (`AuthenticationError` IS a `ConnectionError` subclass — pin the catch order); the
  `json.dumps` wire forms of plain scalars (`5`→`"5"`, `True`→`"true"`, `None`→`"null"`,
  `2.5`→`"2.5"`); pydantic `kw_only`/`extra="forbid"` rejections of the new fields; the
  `_probe_until` sleep cadence under the fake clock.
- **M4.2 Hot reloading** — after each source edit, re-evaluate in the same session via
  `importlib.reload(<module>)` (or re-import the facade) rather than restarting; keep the
  scratch state valid across reloads. The point is a tight edit→reload→observe loop per
  entity.
- **M4.3 Code migration REPL → source** — the migration direction is one-way: snippets
  verified in the REPL are moved into the module file (with docstrings, type hints, and
  blank-line blocks per M1), never re-typed divergently. No working behavior may live only
  in the REPL session; the session is scaffolding, the source file is the deliverable.
- **M4.4 Pin REPL findings as tests** — every behavior confirmed interactively that the
  contract depends on (the constructor password kwarg; the strategy replacement; the
  exception clause order; the wire forms; the payload key sets) becomes an assertion in the
  task's logic/contract tests. The REPL observation is not done until it is pinned in
  `tests/`.
- **M4.5 REPL checkpoints in the task flow** — each coding task includes an explicit REPL
  verification checkbox between implementation and logic tests (see tasks: "REPL cycle"),
  covering: import resolution, one positive call, one negative call per error or no-op
  branch.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the
> next. Within each coding task, contract tests are written first (TDD workflow).

### Task 1: Packaging — the redis dependencies and the project virtualenv (infrastructure)

This task makes the pinned libraries importable before any engine code exists.
`pyproject.toml` extends the existing single testcontainers entry to
`testcontainers[postgres,redis]>=4.15` (the `redis` extra pulls the community module's client
floor `redis>=7`) and adds the direct data-plane dependency `redis>=7.0` next to the other
data-plane clients (after `kafka-python>=3.0`). Do NOT fork a second testcontainers
dependency line — one resolution. The workspace has no `.venv` yet; create it and install
the editable package with the `test` extras. No `.py` file changes in this task.

**Usages relevant to this task:**
- `redis`: the version-floor rationale — the pinned testcontainers 4.15 declares `redis>=7`
  for its `redis` extra; the direct dependency takes the same floor so one resolution holds.
- `conventions`: all commands run inside the virtualenv; every dependency carries a minimum
  version in `pyproject.toml`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION + ENVIRONMENT)**: declare this task (`Task 1: Packaging — the
      redis dependencies and the project virtualenv`); create the venv if missing:
      `python3 -m venv .venv && .venv/bin/pip install -e ".[test]"` (after the pyproject
      edit below, so the redis deps land in one install).
- [x] **Edit `pyproject.toml`**: `"testcontainers[postgres]>=4.15"` →
      `"testcontainers[postgres,redis]>=4.15"`; add `"redis>=7.0"` to `dependencies`
      (after `"kafka-python>=3.0"`, the data-plane client group).
- [x] **Install**: `.venv/bin/pip install -e ".[test]"`; then
      `.venv/bin/pip check` → clean.
- [x] **Verify the pinned surface (REPL probe, M4.1)**:
      `.venv/bin/python -c "import redis; from testcontainers.community.redis import
      RedisContainer; import inspect; print(redis.__version__);
      print(inspect.signature(RedisContainer.__init__))"` → redis resolves against the
      `>=7.0` floor (8.1.0 — the single resolution pip picks) and the constructor shows
      the `password` parameter; `AuthenticationError` MRO confirms the `ConnectionError`
      ancestry.
- [x] Verify the suite baseline is green before any code change:
      `.venv/bin/pytest tests/ -x` (docker-gated tests skip where docker is unavailable).
- [x] **Lint gate (M3.2)**: `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/` and
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/` → clean (no `.py` touched).
- [x] **STEP 8 (COMPLETION + COMMIT GATE)**: run the local commit gate (M3.3) and commit
      exactly `pyproject.toml`.

### Task 2: config cell — `ServiceConfig` password/db and the `StartupData` redis section (TDD coding)

This task extends the two configuration models of the config cell: `ServiceConfig` gains
`password: str | None = None` and `db: int = 0` (kw_only, `extra="forbid"` unchanged — no
validator changes, placement is the loader's job in Task 3); `StartupData` gains
`redis: dict[str, list[dict[str, object]]] = {}` as the last field. Docstrings extend (the
kinds list five; the section order vault, http, postgres, redis; field docs per the
contract). Locations: `goga_tool_pybuggy/sandbox/config/service.py`,
`goga_tool_pybuggy/sandbox/config/startup_data.py`. Tests extend
`tests/sandbox/config/test_service.py` and `tests/sandbox/config/test_startup_data.py` in
place.

**Usages relevant to this task:**
- `conventions`: pydantic `kw_only` models; empty defaults with `None` only for explicit
  absence; Google docstrings; test mirroring (M2.1).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION + ENVIRONMENT)**: declare this task; ensure the venv (M1.2).
- [x] **STEP 1 (CONTRACT TESTS)**: in `tests/sandbox/config/test_service.py` —
      `test_service_config_accepts_the_redis_fields_with_defaults`:
      `ServiceConfig(name="cache", kind="redis")` builds; `config.password is None`;
      `config.db == 0`; `model_config` still kw_only + extra-forbid (an extra key still
      raises `ValidationError`). In `tests/sandbox/config/test_startup_data.py` —
      `test_startup_data_defaults_the_redis_section_empty`: `StartupData()` →
      `data.redis == {}`; the section attribute order is exactly vault, http, postgres,
      redis (`list(StartupData.model_fields)`). Expected to fail now (fields absent).
- [x] **STEP 2 (IMPLEMENTATION)**: `config/service.py` — add `password: str | None = None`
      and `db: int = 0` after `migrations`; extend the class docstring (kinds list five,
      the two field docs per the contract annotation). `config/startup_data.py` — add
      `redis: dict[str, list[dict[str, object]]] = {}` after `postgres`; extend the
      docstring (four-section order, the declaration grammar summary).
- [x] **REPL cycle (M4)**: in the venv REPL — construct `ServiceConfig(name="c",
      kind="redis")` and `ServiceConfig(name="c", kind="redis", password="p", db=7)`;
      confirm defaults and reach-through; confirm a non-redis entry still builds identically
      with the new fields defaulted (regression guard); reload after each edit.
- [x] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest
      tests/sandbox/config/test_service.py tests/sandbox/config/test_startup_data.py -v` —
      all pass.
- [x] **STEP 4 (LOGIC TESTS)**: in `test_service.py` —
      `test_service_config_carries_declared_password_and_db`:
      `ServiceConfig(name="cache", kind="redis", password="sandbox-redis", db=7)` →
      `password == "sandbox-redis"`, `db == 7` (the reach-through contract the engine reads).
      In `test_startup_data.py` — a plain-redis-declaration storage check:
      `StartupData(redis={"cache": [{"action": "set", "key": "k", "value": "v"}]})` holds
      the declarations verbatim (dict equality).
- [x] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/ -x` — fix implementation code until
      all tests pass.
- [x] **STEP 6 (CONTRACT RE-VERIFICATION)**: facade probe — `.venv/bin/python -c "from
      goga_tool_pybuggy.sandbox.config import ServiceConfig, StartupData"`; the new fields
      match the CODEMANIFEST signatures (`password: str | None = None`, `db: int = 0`;
      `redis: dict[str, list[dict[str, object]]] = {}`).
- [x] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/`.
- [x] **STEP 8 (COMPLETION + COMMIT GATE)**: mark checkboxes complete; run the commit gate
      (M3.3); commit exactly `goga_tool_pybuggy/sandbox/config/service.py`,
      `goga_tool_pybuggy/sandbox/config/startup_data.py`,
      `tests/sandbox/config/test_service.py`, `tests/sandbox/config/test_startup_data.py`.
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 3: config cell — `validate_sandbox_config` redis validation and the re-pointed negative examples (TDD coding)

This task extends the loader (`goga_tool_pybuggy/sandbox/config/loader.py`) — the fail-fast
document validation. `_SUPPORTED_KINDS` gains `"redis"` (five; the grpc "not supported yet"
branch untouched); `_SECTION_KINDS` gains `"redis": "redis"` (dict iteration order vault,
http, postgres, redis — the model field order); a new `_validate_redis_keys(entry, scope)`
runs in `_read_services` after `_validate_migrations`; a new
`_validate_redis_declarations(target, declarations, location)` runs inside `_read_section`
for the redis section after the kind-match check. Design algorithm (verbatim):

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

`_REDIS_ACTIONS = {"set": ("key", "value"), "hset": ("key", "values"), "rpush": ("key",
"values"), "sadd": ("key", "members")}` lives in the loader (D4 — config cannot import from
engines/data; the existing design splits shape checks this way). Every message names
`{location}` and the entry — the fail-fast contract. Because redis becomes a supported kind,
three existing negative tests that use redis as the unsupported example break — re-point
them to `mysql` in this task (D10): `tests/sandbox/config/test_loader.py`
(`test_load_fails_unknown_service_kind*` — input `kind: redis` → `kind: mysql`, match
extended to `mysql.*postgresql.*kafka.*vault.*http.*redis`; the unknown-data-section match
`vault, http, postgres` gains `, redis`), `tests/plugin/test_install.py` and
`tests/plugin/test_sandbox_plugin.py` (the `kind: redis` unsupported-kind documents →
`kind: mysql`; the existing matches re-point to `mysql.*not one of the supported kinds` with
the five-kind list). Tests extend `tests/sandbox/config/test_loader.py` in place; the
`sandbox_yaml` fixture writes the documents.

**Usages relevant to this task:**
- `conventions`: fail-fast validation before any side effect; diagnostics naming key, value,
  and location; boundary tables via parametrize; mock-free pure-logic tests.
- `sandbox-file` (imported usage, context): the documented `data.redis` grammar and failure
  list the loader enforces — password/db on non-redis, db out of range, action-key and
  field-set errors.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION + ENVIRONMENT)**: declare this task; ensure the venv.
- [x] **STEP 1 (CONTRACT TESTS)**: in `tests/sandbox/config/test_loader.py` —
      `test_load_accepts_a_redis_service_with_password_and_db` (contract-level): a
      `sandbox_yaml` document with `services: {cache: {kind: redis, password:
      sandbox-redis, db: 2}}` and a valid instance validates;
      `config.services["cache"].kind == "redis"`, `.password == "sandbox-redis"`,
      `.db == 2`. Expected to fail now.
- [x] **STEP 2 (IMPLEMENTATION)**: `config/loader.py` — the `_SUPPORTED_KINDS`,
      `_SECTION_KINDS`, `_REDIS_ACTIONS` constants; `_validate_redis_keys` called in
      `_read_services` after `_validate_migrations`; `_validate_redis_declarations` called
      from `_read_section` for `section == "redis"` (the vault-check call-site precedent),
      with Google docstrings per module style.
- [x] **REPL cycle (M4)**: in the venv REPL — drive `validate_sandbox_config` over scratch
      documents: one valid redis service + `data.redis` four-action section; each invalid
      variant below; observe the exact messages; confirm non-redis entries with password/db
      fail naming the entry; reload after each edit.
- [x] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest
      tests/sandbox/config/test_loader.py -v` — the contract test passes.
- [x] **STEP 4 (LOGIC TESTS)**: in `tests/sandbox/config/test_loader.py` (all via
      `sandbox_yaml`, asserting `pytest.raises(ValueError, match=...)`):
      - `test_load_accepts_the_redis_data_section_for_all_four_actions` — the four
        declarations (`{action: set, key: feature-flag/a, value: enabled}`,
        `{action: hset, key: user:1, values: {name: Ann}}`,
        `{action: rpush, key: queue:orders, values: [{id: 1}, {id: 2}]}`,
        `{action: sadd, key: members:vip, members: [ann, bob]}`) pass load and
        `config.data.redis["cache"]` holds them verbatim.
      - `test_load_accepts_redis_placeholders_in_instance_env` — instance env
        `REDIS_URL: "redis://{{cache.host}}:{{cache.port}}/0"` validates (generic
        placeholder path).
      - Negative: `test_load_fails_password_on_a_non_redis_entry`
        (`db: {kind: postgresql, password: x}` →
        `match=r"services\.db.*password and db are accepted only on redis entries"`);
        `test_load_fails_db_on_a_non_redis_entry` (`payments: {kind: http, db: 3}` → same
        shape naming `services.payments`); `test_load_fails_db_outside_the_range`
        (parametrized `db: 16`, `db: -1` →
        `match=r"services\.cache\.db: must be an integer within 0-15"`);
        `test_load_fails_db_of_wrong_type` (parametrized `db: 2.5`, `db: "2"`, `db: true` →
        the same db error — the explicit bool guard); `test_load_fails_empty_password`
        (`password: ""` →
        `match=r"services\.cache\.password: must be a non-empty string"`);
        `test_load_fails_topics_on_redis` (`topics: [...]` on redis →
        `match=r"topics are accepted only on kafka entries"`);
        `test_load_fails_migrations_on_redis` (`migrations: {location: x}` →
        `match=r"migrations are accepted only on postgresql entries"`);
        `test_load_fails_redis_declaration_without_action` (`[{key: k, value: v}]` →
        `match=r"data\.redis\.cache: every declaration requires an 'action' key \(set,
        hset, rpush, or sadd\)"`); `test_load_fails_redis_declaration_with_unknown_action`
        (`{action: zadd, ...}` → the same action-key error);
        `test_load_fails_redis_declaration_with_missing_or_extra_fields` (parametrized:
        `set` without `value`; `hset` without `values`; `rpush` carrying `members`; a `set`
        carrying both `value` and `values` →
        `match=r"data\.redis\.cache: a '(set|hset|rpush|sadd)' declaration carries
        exactly"`); `test_load_fails_redis_declaration_with_wrong_field_types`
        (parametrized: `hset` `values: [1]`; `rpush` `values: {a: 1}`; `sadd`
        `members: x`; `key: 5` → `ValueError` naming `data.redis.cache` and the field);
        `test_load_fails_redis_section_targeting_a_non_redis_service` (`data.redis.db` with
        `db` a postgresql service →
        `match=r"data\.redis\.db: targets service 'db' of kind 'postgresql', the section
        requires kind 'redis'"`).
      - Edge: `test_load_accepts_db_boundaries_zero_and_fifteen` (parametrized `db: 0`,
        `db: 15` — validation passes, the value reaches the model — the inclusive
        boundaries); `test_load_ignores_absent_password_and_db` (`cache: {kind: redis}`
        only → `password is None`, `db == 0` — the primary no-auth mode).
      - Re-pointed: the unknown-kind test input `kind: redis` → `kind: mysql`, match
        `mysql.*postgresql.*kafka.*vault.*http.*redis`; the unknown-data-section match
        extends to `vault, http, postgres, redis`.
- [x] **Re-point the plugin gates**: `tests/plugin/test_install.py` and
      `tests/plugin/test_sandbox_plugin.py` — the unsupported-kind documents
      `cache: { kind: redis }` → `cache: { kind: mysql }`; the matches re-point to
      `mysql.*not one of the supported kinds` carrying the five-kind list.
- [x] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/ -x` — fix implementation code until
      all tests pass (the re-pointed plugin tests must be green again in the same run).
- [x] **STEP 6 (CONTRACT RE-VERIFICATION)**: the loader algorithm steps 3–4 of the
      CODEMANIFEST hold: kind list five; password/db placement + db range; `data.redis`
      grammar; every failure message names the location and the entry; `data.kafka`
      rejection and the existing four-kind behaviors unchanged.
- [x] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/`.
- [x] **STEP 8 (COMPLETION + COMMIT GATE)**: mark checkboxes complete; run the commit gate
      (M3.3); commit exactly `goga_tool_pybuggy/sandbox/config/loader.py`,
      `tests/sandbox/config/test_loader.py`, `tests/plugin/test_install.py`,
      `tests/plugin/test_sandbox_plugin.py`.
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 4: engines cell — `RedisEngine` lifecycle, readiness, plane, and the four operations (TDD coding)

This task creates the engine entity: `goga_tool_pybuggy/sandbox/engines/redis.py` with
`RedisEngine(BaseEngine)` and the module-private `_NoWaitStrategy`, plus the facade
re-export in `engines/__init__.py`. Style references: `postgres.py` (module constants,
`_PostgresContainer` disable-wait precedent, probe loop) and `http.py`. Design algorithm
(verbatim):

```
Module constants: DEFAULT_IMAGE = "redis:8-alpine", CONTAINER_PORT = 6379,
PLANE_TIMEOUT = 5, PROBE_CONNECT_TIMEOUT = 2, SANDBOX_LABELS = {"pybuggy-sandbox": "true"},
_REDIS_ACTIONS = {"set": ("key", "value"), "hset": ("key", "values"),
"rpush": ("key", "values"), "sadd": ("key", "members")} (dispatch table shared by `_execute`
error messages)

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

Design decisions in force: D1 (the `waiting_for` replacement seam — readiness is
engine-owned, never module-owned), D2 (wrong password fails fast within the bounds —
`AuthenticationError` escapes the retry loop immediately), D3 (str as-is, everything else
`json.dumps`; empty values/members/mapping executes nothing — the postgres empty-rows
precedent), D6 (one eager `ping()` on the session client so a data-plane failure surfaces at
the `start failed at data-plane open` step), D8 (probe clients `socket_timeout=2` /
`connect_timeout=2`; session client `socket_timeout=5` / `connect_timeout=5`; the probe
client closes on every attempt outcome). Errors: `EngineError` via the base wrappers — start
step failures name the service and the step (readiness expiry adds the waited check and
deadline; auth adds the cause); operation failures name the service, the action, and the
cause. The password never appears in any log or error. Edge cases: no startup data → zero
operations, journal empty, reset = FLUSHDB only; `db: 0`/`db: 15` boundaries accepted at
load (Task 3); stop before start / double stop safe. The facade
`goga_tool_pybuggy/sandbox/engines/__init__.py` gains `from .redis import RedisEngine`, the
`__all__` entry (ruff-sorted), and the docstring list extension. Tests: the new
`tests/sandbox/engines/test_redis.py` — unit tests patch the module seams
(`monkeypatch.setattr(redis_module, "RedisContainer", FakeRedisContainer)` and the
`redis_module.redis` namespace carrying the real `redis.exceptions` classes);
`FakeRedisContainer` records image/password/labels kwargs, `waiting_for` strategies,
network attach, mapped address `127.0.0.2:16379`, start/stop counters; `FakeRedisClient`
records commands as `(name, args, kwargs)`, serves scripted errors, counts `close()`;
`install_fake_clock` (`from .test_http import install_fake_clock`) drives `_probe_until`.

**Usages relevant to this task:**
- `redis`: the client contract (lazy connect, one client per session, `decode_responses`
  default False), the module container contract (constructor `password` wiring, the
  `waiting_for` seam), PING readiness, the four commands, FLUSHDB-of-declared-db reset.
- `testcontainers`: the container lifecycle, `waiting_for`, labels, the stop guarantee.
- `conventions`: structured logging with `extra` (no secrets), Google docstrings,
  blank-line blocks, boundary parametrize, doubles at external boundaries only.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION + ENVIRONMENT)**: declare this task; ensure the venv.
- [x] **STEP 1 (CONTRACT TESTS)**: create `tests/sandbox/engines/test_redis.py` —
      `test_redis_engine_is_importable_and_subclasses_base` (class `TestRedisEngineContract`):
      `from goga_tool_pybuggy.sandbox.engines import RedisEngine`;
      `issubclass(RedisEngine, BaseEngine)`; `"RedisEngine" in
      goga_tool_pybuggy.sandbox.engines.__all__`; `__init__` signature `["self", "config"]`;
      `RedisEngine._wait_ready is not BaseEngine._wait_ready` (engine-owned readiness);
      `RedisEngine._container_port == 6379`. Expected to fail now (module absent).
- [x] **STEP 2 (IMPLEMENTATION)**: create `goga_tool_pybuggy/sandbox/engines/redis.py` per
      the algorithm above — imports (`json`, `logging`, `redis`,
      `from testcontainers.community.redis import RedisContainer`,
      `from testcontainers.core.wait_strategy import WaitStrategy`, relative `..config.service`,
      `.base`, `.operation`); module constants; `_NoWaitStrategy`; `RedisEngine` with all
      hooks and Google docstrings; debug logs "redis service ready" / "redis plane open"
      with `extra` metadata (never the password). Update
      `goga_tool_pybuggy/sandbox/engines/__init__.py`: import, `__all__` entry, docstring
      list.
- [x] **REPL cycle (M4)**: in the venv REPL — pin the library facts against the installed
      versions: `inspect.signature(RedisContainer.__init__)` shows `password`; construct a
      `RedisContainer` and call `waiting_for(...)` — observe `_wait_strategy` replaced;
      `redis.exceptions.AuthenticationError.__mro__` shows the `ConnectionError` ancestry
      (the clause order is load-bearing); `json.dumps` forms of `5`/`True`/`None`/`2.5`;
      import the facade and reload (`importlib.reload`) after each edit.
- [x] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest
      tests/sandbox/engines/test_redis.py -v` — the contract test passes; facade probe
      (M3.4): `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.engines import
      RedisEngine"`.
- [x] **STEP 4 (LOGIC TESTS)**: in `tests/sandbox/engines/test_redis.py` (fakes per the
      general setup; every scenario from the design):
      - Container build: `test_build_uses_the_pinned_image_labels_and_port`
        (`container.image == "redis:8-alpine"`;
        `container.kwargs["labels"] == {"pybuggy-sandbox": "true"}`; exposed port 6379;
        `container.network is None` without a network);
        `test_build_honors_the_image_override` (`image="redis:9-alpine"` →
        `container.image == "redis:9-alpine"`); `test_build_passes_the_password_to_the_module_container`
        (`password="sandbox-redis"` → `container.kwargs["password"] == "sandbox-redis"`;
        with `password=None` → `container.kwargs["password"] is None` and no command
        recorded); `test_build_replaces_the_builtin_wait_strategy` (the container's final
        strategy is the engine's `_NoWaitStrategy` instance
        (`container.wait_strategies[-1]`); the module's built-in `PingWaitStrategy`
        instance is no longer installed); `test_build_joins_the_sandbox_network_under_the_service_alias`
        (`engine._network = network_object()` → `container.network is network_object`,
        `container.network_aliases == ["cache"]`).
      - Readiness: `test_wait_ready_probes_ping_until_success` (scripted
        `[ConnectionError, ConnectionError, True]`; fake clock; three `ping` calls;
        `clock.slept == [0.5, 0.5]`; probe clients carry the declared password,
        `socket_timeout=2`, `connect_timeout=2`; every probe client closed);
        `test_wait_ready_fails_fast_on_authentication_error` (scripted
        `AuthenticationError("invalid password")` on the first `ping` →
        `pytest.raises(RuntimeError, match=r"did not answer PING.*authentication failed")`;
        exactly one `ping`, no sleep); `test_wait_ready_fails_past_the_declared_deadline`
        (always `ConnectionError`; `ProbeConfig(timeout=0.2, interval=0.05)` →
        `pytest.raises(RuntimeError, match=r"did not answer PING.*within 0\.2s")`;
        `len(clock.slept) >= 4`, every sleep 0.05).
      - Plane: `test_open_plane_connects_to_the_declared_database` (config `password="p"`,
        `db=3` → constructed kwargs `db=3`, `password="p"`, `socket_timeout=5`,
        `connect_timeout=5`; one eager `ping`; `decode_responses` not set — default False).
      - Execution: `test_execute_applies_the_four_operations_with_wire_serialization`
        (input: `set` `value={"on": true}`; `hset` `values={"name": "Ann", "plan": "pro"}`;
        `rpush` `values=[{"id": 1}, "tail"]`; `sadd` `members=["ann", 2]` →
        `client.commands == [("set", ("feature-flag/a", '{"on": true}'), {}), ("hset",
        ("user:1",), {"mapping": {"name": "Ann", "plan": "pro"}}), ("rpush",
        ("queue:orders", '{"id": 1}', "tail"), {}), ("sadd", ("members:vip", "ann", "2"),
        {})]`); `test_execute_skips_empty_values_members_and_mapping` (`values=[]`,
        `members=[]`, `values={}` → `client.commands == []`);
        `test_execute_unknown_action_names_the_operation` (`action="zadd"` through
        `engine.apply([...])` with `_started = True` →
        `pytest.raises(EngineError, match=r"service 'cache': zadd failed: unknown redis
        action 'zadd'")`); `test_execute_failure_wraps_into_engine_error_through_apply`
        (scripted `redis.exceptions.ResponseError("OOM")` on `set` →
        `pytest.raises(EngineError, match=r"service 'cache': set failed.*OOM")`).
      - Wipe/close: `test_wipe_flushes_the_declared_database`
        (`engine._wipe()` → `client.commands == [("flushdb", (), {})]`);
        `test_close_plane_closes_the_client_once` (twice → `client.closed == 1`,
        `engine._client is None` after the first).
      - Lifecycle flows: `test_start_applies_startup_operations_and_journals_them` (fakes
        armed; `engine.start([set_op, hset_op])` → `engine._journal == [set_op, hset_op]`;
        client commands ordered `set` then `hset`; afterwards `engine.stop()` leaves
        `engine._container is None` and `client.closed == 1`);
        `test_reset_flushes_then_replays_the_journal` (`_started = True`,
        `_journal = [set_op]` → command order `[("flushdb", ...), ("set", ...)]`; container
        stop counter unchanged — no restart).
      - Edge: `test_execute_serializes_plain_scalars_deterministically` (parametrized
        `value=5`/`True`/`None`/`2.5` → the client receives `"5"`/`"true"`/`"null"`/`"2.5"`);
        `test_execute_fails_readably_on_non_serializable_values` (a plain `object()` value
        through `apply` → `pytest.raises(EngineError, match=r"service 'cache': set failed")`
        with the `TypeError` as cause); `test_reset_with_empty_journal_only_flushes`
        (`_journal = []` → commands == `[("flushdb", (), {})]`);
        `test_stop_is_safe_before_start` (`RedisEngine(config).stop()` twice on a fresh
        engine — no exception, nothing touched).
- [x] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/ -x` — fix implementation code until
      all tests pass.
- [x] **STEP 6 (CONTRACT RE-VERIFICATION)**: every `RedisEngine` contract requirement
      holds: one connection to the declared db closed on stop; wipe and seed address the
      declared db only; failed commands surface as `EngineError` naming service, operation,
      cause; readiness bounded by the declaration; the declared payload never rewritten.
- [x] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — decompose if complexity rules
      demand it.
- [x] **STEP 8 (COMPLETION + COMMIT GATE)**: mark checkboxes complete; run the commit gate
      (M3.3); commit exactly `goga_tool_pybuggy/sandbox/engines/redis.py`,
      `goga_tool_pybuggy/sandbox/engines/__init__.py`,
      `tests/sandbox/engines/test_redis.py`.
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 5: engines cell — the `build_engine` redis mapping and the contract-mirroring docstrings (TDD coding)

This task wires the engine into the factory and syncs the docstring surfaces that mirror
the contract. `goga_tool_pybuggy/sandbox/engines/runtime.py`: import `RedisEngine`
(`from .redis import RedisEngine`), `KIND_ENGINES["redis"] = RedisEngine` (last entry),
`build_engine` docstring mentions the redis password and db declarations reaching the built
engine. `goga_tool_pybuggy/sandbox/engines/operation.py`: docstring action set → "insert,
produce, put, stub, set, hset, rpush, or sadd", kind list gains redis, the payload sentence
gains "A redis operation's payload carries the key plus value, values, or members — the
fields of the matching view operation". `goga_tool_pybuggy/sandbox/engines/base.py`: the
`Attributes`/`Args` config descriptions gain "password and db declarations (consumed by the
redis kind)". No behavior changes beyond the registry entry. Tests extend
`tests/sandbox/engines/test_runtime.py` in place.

**Usages relevant to this task:**
- `conventions`: docstrings mirror behavior; every mirrored surface moves in lockstep when
  behavior changes; test mirroring and in-place updates.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION + ENVIRONMENT)**: declare this task; ensure the venv.
- [x] **STEP 1 (CONTRACT TESTS)**: in `tests/sandbox/engines/test_runtime.py` — extend the
      parametrized `test_build_engine_returns_the_kind_engine` with the redis case
      (`build_engine(ServiceConfig(name="cache", kind="redis"))` →
      `isinstance(engine, RedisEngine)`, `engine.config.name == "cache"`). Expected to fail
      now.
- [x] **STEP 2 (IMPLEMENTATION)**: the `runtime.py` import + registry entry + docstring;
      the `operation.py` docstring; the `base.py` docstring lines.
- [x] **REPL cycle (M4)**: in the venv REPL — `from
      goga_tool_pybuggy.sandbox.engines import build_engine`;
      `build_engine(ServiceConfig(name="c", kind="redis"))` returns a `RedisEngine`;
      `KIND_ENGINES` keys are the five kinds; a fabricated `kind="grpc"` raises the
      `EngineError` listing all five; reload after the edit.
- [x] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest
      tests/sandbox/engines/test_runtime.py -v` — all pass.
- [x] **STEP 4 (LOGIC TESTS)**: in `test_runtime.py` — update
      `test_build_engine_fails_unmapped_kind` / the unmapped-kind match to
      `match=r"service 'x': kind 'grpc' has no engine.*postgresql.*kafka.*vault.*http.*redis"`
      (the five-kind listing); `test_build_engine_carries_the_service_declaration` extends
      with a redis config carrying `password`/`db` — the built engine's `config` holds them
      (the reach-through contract).
- [x] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/ -x` — fix implementation code until
      all tests pass.
- [x] **STEP 6 (CONTRACT RE-VERIFICATION)**: `build_engine` maps redis and passes the
      declarations through; the unmapped error lists the five kinds; the docstrings of
      `operation.py` / `base.py` / `runtime.py` match the CODEMANIFEST wording they mirror.
- [x] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/`.
- [x] **STEP 8 (COMPLETION + COMMIT GATE)**: mark checkboxes complete; run the commit gate
      (M3.3); commit exactly `goga_tool_pybuggy/sandbox/engines/runtime.py`,
      `goga_tool_pybuggy/sandbox/engines/operation.py`,
      `goga_tool_pybuggy/sandbox/engines/base.py`,
      `tests/sandbox/engines/test_runtime.py`.
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 6: data cell — the `RedisInstance` declare-only view (TDD coding)

This task creates `goga_tool_pybuggy/sandbox/data/redis.py` — `RedisInstance`, mirroring
`HttpInstance` exactly (`__init__(name, address, batch)`; properties `name`/`host`/`port`;
declare-only methods) — and re-exports it on the data facade. Design algorithm (verbatim):

```
set(key: str, value: object)        → DataOperation(kind="redis", action="set",
                                        payload={"key": key, "value": value}) → batch.add
hset(key: str, values: dict)        → action="hset", payload={"key": key, "values": values}
rpush(key: str, values: list)       → action="rpush", payload={"key": key, "values": values}
sadd(key: str, members: list)       → action="sadd", payload={"key": key, "members": members}
```

Every method builds a fresh payload dict (M1.11), appends the `DataOperation` through
`batch.add`, and executes nothing — the laziness contract. Errors: none — declaration only.
Edge cases: payloads of any plain object ride as given; serialization is execution-time.
The facade `goga_tool_pybuggy/sandbox/data/__init__.py` gains the import, the `__all__`
entry (ruff-sorted), and the docstring list extension. Tests: the new
`tests/sandbox/data/test_redis.py` (a `DataBatch()` recorder; the `test_http.py` suite is
the structural reference).

**Usages relevant to this task:**
- `conventions`: Google docstrings, type hints mandatory, mock-free pure-logic tests,
  `test_<module>.py` mirroring.
- `data-operations` (imported usage, context): the documented redis view examples and the
  laziness contract this view implements.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION + ENVIRONMENT)**: declare this task; ensure the venv.
- [x] **STEP 1 (CONTRACT TESTS)**: create `tests/sandbox/data/test_redis.py` —
      `test_redis_instance_is_importable_from_the_data_facade`:
      `from goga_tool_pybuggy.sandbox.data import RedisInstance`;
      `"RedisInstance" in goga_tool_pybuggy.sandbox.data.__all__`; the `__init__`
      signature is `["self", "name", "address", "batch"]`; the four method signatures match
      the contract (`set(key, value)`, `hset(key, values)`, `rpush(key, values)`,
      `sadd(key, members)`); the three properties exist. Expected to fail now.
- [x] **STEP 2 (IMPLEMENTATION)**: create `goga_tool_pybuggy/sandbox/data/redis.py` per the
      algorithm (imports: relative `..engines` for `DataOperation`/`InstanceAddress`,
      `.batch` for `DataBatch`); update `data/__init__.py` (import, `__all__`, docstring).
- [x] **REPL cycle (M4)**: in the venv REPL — build a `RedisInstance("cache",
      InstanceAddress("127.0.0.2", 16379), DataBatch())`, call all four methods, take the
      batch, observe the four `DataOperation` payloads field-for-field; confirm nothing
      executes (no engine involved); reload after each edit.
- [x] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest tests/sandbox/data/test_redis.py
      -v` — the contract test passes; facade probe (M3.4): `.venv/bin/python -c "from
      goga_tool_pybuggy.sandbox.data import RedisInstance"`.
- [x] **STEP 4 (LOGIC TESTS)**: `test_redis_view_declares_the_four_operations` —
      `set("k", "v")`; `hset("h", {"f": 1})`; `rpush("l", [1, 2])`; `sadd("s", ["a"])` →
      `[(op.action, op.payload) for op in batch.take()] == [("set", {"key": "k", "value":
      "v"}), ("hset", {"key": "h", "values": {"f": 1}}), ("rpush", {"key": "l", "values":
      [1, 2]}), ("sadd", {"key": "s", "members": ["a"]})]`; `(view.name, view.host,
      view.port) == ("cache", "127.0.0.2", 16379)`; the batch drains on take; a non-str
      value (`{"on": True}`) rides as given — no serialization at declaration.
- [x] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/ -x` — fix implementation code until
      all tests pass.
- [x] **STEP 6 (CONTRACT RE-VERIFICATION)**: the payload shapes equal the engines payload
      contract field-for-field; declaration-only semantics hold; the facade exposes
      `RedisInstance`.
- [x] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/`.
- [x] **STEP 8 (COMPLETION + COMMIT GATE)**: mark checkboxes complete; run the commit gate
      (M3.3); commit exactly `goga_tool_pybuggy/sandbox/data/redis.py`,
      `goga_tool_pybuggy/sandbox/data/__init__.py`, `tests/sandbox/data/test_redis.py`.
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 7: data cell — `services` redis presets and the decoration-time grammar (TDD coding)

This task extends the preset decorator `goga_tool_pybuggy/sandbox/data/presets.py`:
`_SUPPORTED_KINDS` gains `"redis"` (five); redis declarations validate at decoration with
the same grammar as the loader (D4) — a local `_validate_redis_declarations` helper plus
the `_REDIS_ACTIONS` table (duplicated by design: the data cell cannot import the loader);
message context `services preset 'redis.{name}'`; nothing executes at decoration. Design
(D4/D5 context): exact key set `{action}` plus the action's fields — extras fail naming the
declaration; `values` a mapping for hset, `values`/`members` lists for rpush/sadd, `key` a
non-empty string. Because redis becomes supported, the existing
`test_services_rejects_unknown_kind_at_decoration` (uses `services(redis={"x": []})` as its
unsupported example) breaks — re-point it to `mysql` in this task (D10). Tests extend
`tests/sandbox/data/test_presets.py` in place.

**Usages relevant to this task:**
- `conventions`: fail-fast decoration-time validation naming the declaration; parametrized
  field-set matrices; pure-logic mock-free tests.
- `data-operations` (imported usage, context): the documented `action`-key preset example
  and the "same fields as the matching view operation" rule the decorator enforces.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION + ENVIRONMENT)**: declare this task; ensure the venv.
- [x] **STEP 1 (CONTRACT TESTS)**: in `tests/sandbox/data/test_presets.py` —
      `test_services_accepts_redis_presets_for_all_actions`:
      `services(redis={"cache": [four valid declarations]})` applied to a dummy function →
      the marker carries the presets verbatim; `usefixtures("sandbox")` stamped; no
      exception. Expected to fail now.
- [x] **STEP 2 (IMPLEMENTATION)**: `data/presets.py` — the constant, the helper, the
      per-declaration call for `kind == "redis"` (the postgresql rows-validation call-site
      precedent); docstring kinds list five and the redis grammar sentence.
- [x] **REPL cycle (M4)**: in the venv REPL — decorate scratch functions with valid and
      invalid redis presets; observe the exact `services preset 'redis.cache'` messages;
      confirm nothing executes at decoration; reload after each edit.
- [x] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest
      tests/sandbox/data/test_presets.py -v` — the contract test passes.
- [x] **STEP 4 (LOGIC TESTS)**: in `test_presets.py` — negative:
      `test_services_fails_redis_preset_without_action`
      (`services(redis={"cache": [{"key": "k", "value": "v"}]})` →
      `pytest.raises(ValueError, match=r"services preset 'redis\.cache'.*'action' key")`);
      `test_services_fails_redis_preset_with_wrong_fields` (parametrized: missing `value`
      for `set`; `hset` with `members`; extra `value` on an `rpush` → `ValueError` naming
      `services preset 'redis.cache'`). Re-pointed:
      `test_services_rejects_unknown_kind_at_decoration` input → `services(mysql={"x":
      []})` with `match="mysql"`; `test_services_unknown_kind_error_lists_supported_kinds`
      match extends to `postgresql.*kafka.*vault.*http.*redis`.
- [x] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/ -x` — fix implementation code until
      all tests pass.
- [x] **STEP 6 (CONTRACT RE-VERIFICATION)**: the decoration algorithm holds: five kinds;
      redis grammar enforced with the preset-naming messages; decoration executes nothing;
      the marker + usefixtures mechanics unchanged.
- [x] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/`.
- [x] **STEP 8 (COMPLETION + COMMIT GATE)**: mark checkboxes complete; run the commit gate
      (M3.3); commit exactly `goga_tool_pybuggy/sandbox/data/presets.py`,
      `tests/sandbox/data/test_presets.py`.
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 8: sandbox root — the `redis` view factory, preset enqueue, and the redis startup loop (TDD coding)

This task integrates the kind into the session runtime
`goga_tool_pybuggy/sandbox/sandbox.py`. Design algorithm (verbatim):

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

D5: the four single-action kinds keep `payload=declaration` unchanged (their declaration
fields already equal the view payload fields); redis builds the fresh view-fields-only
dict — field-for-field what `_startup_operations` builds. The declaration is never mutated
(M1.11). The harness: `sandbox_config()` in `tests/sandbox/test_sandbox.py` carries "one
service of every kind" by its own docstring — extend it and `SandboxHarness` with the fifth
service `cache` (redis kind, `FakeEngine(name="cache", kind="redis", address=
InstanceAddress(host="127.0.0.6", port=6379))`), a `REDIS_URL: "redis://{{cache.host}}:
{{cache.port}}/0"` instance env placeholder, and `data.redis` startup declarations — then
fix every existing harness-based assertion the fifth service affects (event sequences,
orderings, counts; the full-suite gate catches any missed one). Tests extend
`tests/sandbox/test_sandbox.py` in place.

**Usages relevant to this task:**
- `conventions`: fresh dicts over mutation; fail-fast facade errors listing the configured
  services; in-place test updates; parametrize where matrices exist.
- `data-operations` (imported usage, context): the ordering semantics (presets ahead of
  in-test declarations within one service group) and the preset `action`-key flow.
- `sandbox-file` (imported usage, context): the fixed startup section order vault → http →
  postgres → redis the `_startup_operations` loop implements.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION + ENVIRONMENT)**: declare this task; ensure the venv.
- [x] **STEP 1 (CONTRACT TESTS)**: in `tests/sandbox/test_sandbox.py` — extend
      `test_sandbox_exposes_the_view_factories` (the callable-factories loop) and
      `test_sandbox_methods_carry_the_declared_signatures` (the factory-signature loop)
      with `"redis"`; add `test_sandbox_redis_factory_binds_the_redis_view` skeleton:
      `sandbox.redis("cache")` returns a `RedisInstance` with
      `(view.name, view.host, view.port)` bound to the engine address. Expected to fail
      now.
- [x] **STEP 2 (IMPLEMENTATION)**: `sandbox.py` per the algorithm — the import, the `ViewT`
      bound, the re-typed `_KIND_ACTIONS` with `"redis": None`, the `redis()` factory
      (docstring mirroring the other factories), the `enqueue_presets` branch, the
      `_startup_operations` redis loop last with the fresh-dict payload.
- [x] **REPL cycle (M4)**: in the venv REPL over a wired harness — `sandbox.redis("cache")`
      binds the view; `enqueue_presets({"redis": {"cache": [{"action": "hset", ...}]}})`
      returns 1 and lands the stripped payload; a declaration without `action` raises the
      preset-style message; `_startup_operations("cache")` strips `action` into a fresh
      dict and leaves the declaration untouched (compare before/after); reload after each
      edit.
- [x] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest tests/sandbox/test_sandbox.py
      -v` — the contract tests pass.
- [x] **STEP 4 (LOGIC TESTS)**: in `test_sandbox.py` —
      `test_enqueue_presets_reads_the_redis_action_from_the_declaration` (harness with the
      redis service; `enqueue_presets({"redis": {"cache": [{"action": "hset", "key":
      "user:1", "values": {"name": "Ann"}}]}})` → returns 1; the batch operation equals
      `DataOperation(instance="cache", kind="redis", action="hset", payload={"key":
      "user:1", "values": {"name": "Ann"}})`; `apply_pending` routes it to the `cache`
      engine group); `test_sandbox_redis_factory_binds_the_redis_view` (full: a
      `view.set(...)` declaration lands in the live batch and `apply_pending` routes it to
      the `cache` engine); `test_startup_operations_assemble_the_redis_section_last`
      (harness config with all four data sections populated and
      `data.redis.cache = [set declaration]` → the assembled list is exactly the
      `DataOperation(kind="redis", action="set", payload={... minus action})`; the
      declaration dict is unmutated); negative:
      `test_sandbox_redis_view_kind_mismatch_and_unknown_name`
      (`sandbox.redis("db")` on the postgresql service →
      `pytest.raises(ValueError, match=r"no redis service named 'db'")`;
      `sandbox.redis("ghost")` →
      `match=r"no redis service named 'ghost'.*cache \(redis\)"`);
      `test_enqueue_presets_fails_redis_declaration_without_action` (a hand-built marker
      payload → `pytest.raises(ValueError, match=r"services preset 'redis\.cache': every
      declaration requires an 'action' key")`). Harness: extend `sandbox_config()` /
      `SandboxHarness` with the `cache` redis service and fix the affected existing
      assertions.
- [x] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/ -x` — fix implementation code until
      all tests pass (including every harness-extended assertion).
- [x] **STEP 6 (CONTRACT RE-VERIFICATION)**: the `Sandbox` contract holds — start step 3
      fixes the section order vault → http → postgres → redis; the requirements clause
      lists redis among the view-bound kinds; `redis(name)` fail-fast lists configured
      services; presets land ahead of in-test declarations.
- [x] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/`.
- [x] **STEP 8 (COMPLETION + COMMIT GATE)**: mark checkboxes complete; run the commit gate
      (M3.3); commit exactly `goga_tool_pybuggy/sandbox/sandbox.py`,
      `tests/sandbox/test_sandbox.py`.
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 9: Integration tests — the docker-gated redis engine roundtrips (integration tests)

Cross-plane verification of `RedisEngine` against a real docker daemon: the full lifecycle
(start → engine PING readiness → plane on the declared db → operations), the reset
semantics (FLUSHDB of the declared db only, no container restart), and the password mode.
These are real-environment integration tests of an adapter managing an external service —
gated on availability, never replacing the unit contract/logic tests of Task 4. Add the
`TestRedisEngineContainer` class to `tests/sandbox/engines/test_redis.py` (created in Task
4); every test method carries `@requires_docker`
  (`from ..conftest import requires_docker`).

**Usages relevant to this task:**
- `redis`: the verification-client patterns — a separate `redis.Redis(host, port, db=...)`
  per checked database; `decode_responses` default False means read-back values are bytes
  (`b"enabled"`, `{b"name": b"Ann"}`).
- `testcontainers`: the real container lifecycle and the ryuk-backed removal guarantee.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create the `TestRedisEngineContainer` class in
      `tests/sandbox/engines/test_redis.py` with the `requires_docker` gate.
- [x] `test_redis_engine_container_roundtrip`:
      `RedisEngine(ServiceConfig(name="cache", kind="redis", db=2))`;
      `engine.start([set_op("feature-flag/a", "enabled"), hset_op("user:1", {"name":
      "Ann"})])`; a verification client on `db=2` reads back `GET feature-flag/a ==
      b"enabled"` and `HGETALL user:1 == {b"name": b"Ann"}`; a client on `db=0` sees none
      of the keys (declared-db isolation proves connect and visibility); `engine.stop()`.
- [x] `test_redis_engine_container_reset_flushes_only_the_declared_db`: as above on `db=1`
      with a journaled `set_op`; after start, write an extra key on `db=1` and one key on
      `db=0` through verification clients; `engine.reset()` → `db=1` holds exactly the
      journaled key again, the `db=0` key survives, the container was never restarted (the
      same mapped port before/after); stop.
- [x] `test_redis_engine_container_password_mode`:
      `RedisEngine(ServiceConfig(name="cache", kind="redis", password="sandbox-redis"))`;
      `engine.start([])` completes (the engine PING with the password succeeded — the
      container requires auth); a passwordless verification client's `ping` raises
      `AuthenticationError`; stop.
- [x] Run validation: `.venv/bin/pytest tests/sandbox/engines/test_redis.py -v` (the
      container class runs where docker is available, skips otherwise — a skip is green);
      then `.venv/bin/pytest tests/ -x`.
- [x] **Lint gate (M3.2)** + **commit gate (M3.3)**: commit exactly
      `tests/sandbox/engines/test_redis.py`.

### Task 10: Docs — the redis pages of the sandbox documentation (package data)

This task syncs the public docs with the implemented kind — the docs pages are mirrors of
behavior and move in lockstep. `docs/sandbox/configuration.md`: the services section gains
the redis kind (five-kind lists everywhere a kind list appears), the `password` and `db`
keys (redis-only, db 0–15, password reaches the service under test as an env literal — the
postgres-URL precedent), the `redis:8-alpine` image row in the pinned-image table, the
`data.redis` table row + example (the four-action grammar), the `{{cache.host}}` /
`{{cache.port}}` placeholders, and the extended failure list (password/db on non-redis, db
out of range, action-key and field-set errors). `docs/sandbox/api.md`: the "Service views"
section gains `sandbox.redis(name)` and the `RedisInstance` operations (`set`/`hset`/
`rpush`/`sadd` — declare-only, JSON-serializable values, declared-db alignment); the
"Presets" section gains the `@services(redis=...)` example with the `action` key; the
ordering/reset notes mention FLUSHDB of the declared db. `docs/sandbox/index.md`: the
five-kind lists. Match the established page voice, tables, and example format; English;
no new pages.

**Usages relevant to this task:**
- `conventions` (documentation grounding): every mirrored surface moves in lockstep with
  behavior; factual statements match the code they describe.
- `sandbox-file` / `data-operations` (imported usages, content source): the consumer
  documentation the pages align with.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Update `docs/sandbox/configuration.md` — five-kind lists, redis keys, image row,
      `data.redis` row + example, placeholder note, extended failure list.
- [x] Update `docs/sandbox/api.md` — `sandbox.redis(name)`, `RedisInstance` operations,
      `@services(redis=...)` example, ordering and FLUSHDB reset notes.
- [x] Update `docs/sandbox/index.md` — the five-kind lists.
- [x] Verify grounding: `grep -rn "redis" docs/sandbox/` shows the three pages covering
      configuration, api, and index; a repository-wide search for stale four-kind lists
      (`postgresql, kafka, vault, http` without redis) in `docs/` returns nothing
      (two stale lists outside `docs/sandbox/` — `docs/index.md` and
      `docs/pipelines/api-automate.md` — were re-pointed to five kinds to satisfy this).
- [x] **Stage gate (M3.2)** over the unchanged `.py` tree (both ruff commands exit 0) +
      **commit gate (M3.3)**: commit exactly `docs/sandbox/configuration.md`,
      `docs/sandbox/api.md`, `docs/sandbox/index.md` (plus the two re-pointed pages and
      the plan).

---

## Validation Commands

- `.venv/bin/pytest tests/ -x`: Run all tests (docker-gated tests skip where docker is unavailable — a skip is green)
- `.venv/bin/pytest tests/sandbox/ -v`: Run the sandbox suite verbosely (the feature's home)
- `.venv/bin/pytest tests/sandbox/engines/test_redis.py tests/sandbox/data/test_redis.py -v`: Run the two new redis test files
- `.venv/bin/ruff check goga_tool_pybuggy/ tests/`: Lint check (M3.1 config, no changes)
- `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/`: Format check (apply `ruff format` first when fixing)
- `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.engines import RedisEngine"`: Facade check — the engine
- `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.data import RedisInstance"`: Facade check — the view
- `.venv/bin/pip check`: Dependency resolution consistency (one testcontainers entry, redis 7.x)

---

## Completion Criteria

- [x] Every contract entity is implemented in the correct `location` (`engines/redis.py`,
      `data/redis.py`; the changed entities in `service.py`, `startup_data.py`,
      `loader.py`, `runtime.py`, `presets.py`, `sandbox.py`)
- [x] Every contract entity is accessible from the facade (`RedisEngine` from
      `goga_tool_pybuggy.sandbox.engines`, `RedisInstance` from
      `goga_tool_pybuggy.sandbox.data`)
- [x] Properties and methods match the declared API (`RedisEngine` hooks and family
      contract; `RedisInstance` four methods + three properties; `Sandbox.redis(name)`;
      model fields with the declared defaults)
- [x] Descriptions are reflected in behavior (bounded PING readiness, auth fast-fail,
      wire serialization at execution, FLUSHDB-of-declared-db reset, journal determinism,
      fail-fast messages naming the location and entry)
- [x] Contract dependencies are met (config ← engines ← data ← root order; no new
      cross-cell edges)
- [x] Re-exports are accessible from the facades
- [x] Every coding task followed the TDD workflow (contract tests → code → REPL cycle →
      verification → logic tests → debugging → re-verification → lint)
- [x] Contract tests and logic tests cover facade, API, and behavior within each coding
      task; the docker-gated integration tests exist as the separate Task 9
- [x] No package boundary was expanded (no new cells; internal decomposition only within
      the engines/data modules)
- [x] `CODEMANIFEST` files were not modified (contract is read-only); the cell `.usages/`
      files were not modified (current by the apply stage)
- [x] All validation commands pass
- [x] Every Usages entry is mentioned in at least one task (`redis`, `testcontainers`,
      `conventions`, `sandbox-file`, `data-operations`, `migration-set` — context only)
- [x] The Mandatory Rules held at every stage: M1 style, M2 tests, M3 lint/format stage +
      commit gates on every local commit, M4 REPL cycle in every coding task
