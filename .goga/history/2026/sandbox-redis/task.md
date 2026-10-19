# Sandbox: Redis as a fifth dependency kind

## Current State

The pybuggy sandbox supports four dependency kinds — postgresql (a real container), kafka
(mokapi), vault (dev mode), http (wiremock). The kind surface spans four cells:

- `goga_tool_pybuggy/sandbox/config` — the document models (`ServiceConfig`, `StartupData`)
  and `validate_sandbox_config` (fail-fast kind and kind-specific-key validation);
- `goga_tool_pybuggy/sandbox/engines` — the per-kind engines (`PostgresEngine`,
  `KafkaEngine`, `VaultEngine`, `HttpEngine`), `build_engine`, and `DataOperation` (the
  action set is fixed per kind);
- `goga_tool_pybuggy/sandbox/data` — the instance views (`PostgresInstance`,
  `KafkaInstance`, `VaultInstance`, `HttpInstance`) and the `@services(...)` presets;
- `goga_tool_pybuggy/sandbox` (root) — the `Sandbox.postgresql/kafka/vault/http(name)`
  facade and the startup-data section order (vault → http → postgres).

Redis does not exist anywhere in this surface today: a `kind: redis` service entry fails
validation, there is no redis engine, view, facade accessor, or `data.redis` section;
pyproject carries no `redis` dependency and no `testcontainers[redis]` extra; the usage
cooks and the sandbox documentation pages do not mention redis. The unsupported-kind negative
tests currently use `redis` as their example — `tests/plugin/test_sandbox_plugin.py`,
`tests/plugin/test_install.py`, `tests/sandbox/config/test_loader.py`, and
`tests/sandbox/data/test_presets.py` expect a `kind: redis` entry (and a `services(redis=...)`
preset) to fail validation — and break structurally once redis joins the supported kinds.

## Description

Add `redis` as the fifth dependency kind — a real `redis:8-alpine` container driven by
redis-py, integrated into the same configuration, engine, data-view, and preset surface as
the existing kinds, following the same vertical slice. Decisions are settled in
`.goga/history/2026/sandbox-redis/adr.md`; this task implements them:

- **config**: accept kind `redis`; accept the kind-specific keys `password` (optional;
  absent starts the container without authentication, present starts it with
  `--requirepass`) and `db` (optional, default 0, validated at document load to 0–15) on
  the redis kind only; reject `topics` and `migrations` on redis; add the `redis` section
  to `StartupData` (service name → declarations).
- **engines**: `RedisEngine` (a `BaseEngine` mutation) — the
  `testcontainers.community.redis.RedisContainer` module with the product-pinned
  `redis:8-alpine` default image and the common `image` override; engine-owned PING
  readiness bounded by the declared probe (the module's built-in `PingWaitStrategy`
  replaced through `waiting_for`, the postgres principle); a redis-py data plane — one
  connection to the declared db for the session, closed on stop; the v1 actions
  `set`/`hset`/`rpush`/`sadd`; wipe = `FLUSHDB` of the declared database plus
  baseline-journal replay, no container restart; `build_engine` maps redis; the
  `DataOperation` action set gains the four redis actions.
- **data**: the `RedisInstance` view with `set`/`hset`/`rpush`/`sadd` methods; the
  `services` preset accepts the `redis` key.
- **sandbox root**: the `Sandbox.redis(name)` facade accessor; the `data.redis` section
  applies last in the fixed order vault → http → postgres → redis; the
  `{{name.host}}`/`{{name.port}}` placeholders work through the generic rendering with no
  changes.

The password reaches the service under test as an env literal in the sandbox document (the
postgres-URL precedent) — no new placeholder kind.

## Scope

**In scope:**
- Kind `redis` in document validation: supported-kinds lists, kind-specific keys
  (`password`, `db`), rejected keys (`topics`, `migrations`), db range validation at load.
- `RedisEngine`: container (module + pinned image + override + password wiring), engine
  PING readiness within the declared probe, redis-py data plane to the declared db, the
  four v1 operations, `FLUSHDB` + journal-replay reset, stop guarantees.
- `DataOperation` action extension; `build_engine` mapping; `EngineError` surfacing.
- `RedisInstance` view (`set`/`hset`/`rpush`/`sadd`); `@services(redis=...)` preset.
- `Sandbox.redis(name)` accessor; `data.redis` startup section applied last.
- pyproject: `testcontainers[postgres,redis]>=4.15` (extend the existing entry) and
  `redis>=7.0`.
- The usage cook `.goga/usages/cooks/redis.md` (created with this task).
- CODEMANIFEST updates of the four affected cells; cell `.usages` updates
  (`sandbox-file.md`, `data-operations.md`, `sandbox-session.md`).
- Documentation pages: `docs/sandbox/configuration.md`, `docs/sandbox/api.md`,
  `docs/sandbox/index.md`.
- Re-pointing the existing unsupported-kind negative tests — they currently use `redis` as
  the unsupported example (`tests/plugin/test_sandbox_plugin.py`, `tests/plugin/test_install.py`,
  `tests/sandbox/config/test_loader.py`, `tests/sandbox/data/test_presets.py`) — to another
  unsupported kind.
- Tests per the project conventions (unit + edge cases; container-backed engine tests
  following the existing engine test style).

**Out of scope:**
- `zadd` (sorted sets), TTL/expire, key deletion, read-back/assertions — deferred to the
  next iteration by the ADR.
- Persistence/volumes for redis; valkey; any mock product — rejected by the ADR.
- New placeholder kinds (the password travels as an env literal).
- The grpc "not supported yet" behavior — unchanged.
- Changes to the existing kinds' behavior beyond the shared surface extension (supported
  kinds lists, action registry, section order).

## Acceptance Criteria

- A sandbox document with a `kind: redis` service passes validation; `password` and `db`
  are accepted on the redis kind only and rejected on every other kind; `topics` and
  `migrations` on redis fail at document load naming the entry; `db` outside 0–15 fails
  at load; every supported-kinds error message lists redis.
- The `data.redis` section is validated (targets must name configured redis services) and
  applies last — order vault → http → postgres → redis.
- `build_engine` returns the redis engine for a redis service; the container runs
  `redis:8-alpine` by default and the declared `image` override replaces it; readiness is
  the engine PING within the declared deadline at the declared interval — an expired
  deadline surfaces as `EngineError` naming the service and the waited check.
- A declared `password` starts the container with authentication and the data plane
  connects with it; an absent `password` starts the container without authentication.
- The data plane holds one connection to the declared db for the session, closed on stop;
  stopping a stopped service is safe.
- `set`/`hset`/`rpush`/`sadd` apply through redis-py against the declared db; payloads
  are strings or JSON-serializable plain data; the declared payload is never rewritten.
- Reset: `FLUSHDB` of the declared db plus journal replay restores the baseline exactly;
  the container does not restart during reset; the data-plane connection survives it.
- `sandbox.redis(name)` returns the `RedisInstance` view; an unknown name or a kind
  mismatch fails fast listing the configured services; `{{name.host}}`/`{{name.port}}`
  render for a redis service.
- `@services(redis={...})` validates at decoration and enqueues ahead of the test's own
  view declarations.
- `pytest tests/ -x` passes; `ruff check` is clean; pyproject declares
  `testcontainers[postgres,redis]>=4.15` (the extended existing entry) and `redis>=7.0`; the
  four CODEMANIFESTs, the cell `.usages` files, and the three documentation pages mention and
  cover the redis kind.

## Stack

- **Frameworks:** pytest (the plugin runtime), pydantic (config models) — unchanged.
- **Libraries:** redis-py (`redis>=7.0`) — the data plane;
  `testcontainers.community.redis.RedisContainer` (the `redis` extra of the pinned
  testcontainers 4.15) — the container module.
- **Infrastructure:** a real `redis:8-alpine` container (major product pin, the
  `postgres:16-alpine` precedent), port 6379, no volume, optional `--requirepass`.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| redis (redis-py) | `.goga/usages/cooks/redis.md` | created |
| testcontainers (redis extra, RedisContainer) | `.goga/usages/cooks/redis.md` + `.goga/usages/cooks/testcontainers.md` | created / existing |

Synced usage files are managed by `goga usages sync` — reference them read-only, never
create or update them in the task. (`github/goga` is the only synced group; no synced
usage covers this task's dependencies.)

## Risks and Constraints

- **Version floor correction**: the approved floor `redis>=6.0` conflicts with the pinned
  testcontainers 4.15 metadata — its `redis` extra requires `redis>=7`. The task pins
  `redis>=7.0` (one consistent resolution; available line up to 8.x).
- The module constructor hardcodes `PingWaitStrategy`; the replacement must go through the
  core container's `waiting_for(...)` (verified in the 4.15 sources) — an extra
  `_wait_strategy` constructor kwarg would collide with the module's own call.
- `FLUSHDB` wipes only the declared logical database — the author aligns the service's db
  configuration with the declared `db`, and picks the type-correct writer for the
  service's read path (both are the visibility contract, documented in the cook).
- A wrong password surfaces as an auth error on the first PING — the readiness probe must
  bound it within the declared deadline, never as a hang.
- Serialization happens at execution and the declared payload is never rewritten — journal
  replay depends on this; do not mutate payloads anywhere on the apply path.
- Python 3.10+ compatibility; relative imports inside the cells; kw_only pydantic models;
  all project conventions (`.goga/usages/conventions.md`) apply.

## Scope Estimate

Single task — no decomposition. One vertical kind-slice following the established pattern
(each of the four existing kinds is one slice); two new types (`RedisEngine`,
`RedisInstance`) plus point extensions to the config models, the facade, the preset
surface, and the shared registries; no independent subsystems. No additional topics are
created; the work stays on the `sandbox-redis` branch.

## Existing Architecture

Affected cells (modifications only — no new cells):

- `goga_tool_pybuggy/sandbox/config` — `ServiceConfig` gains `password`/`db`
  (redis-only); `StartupData` gains the `redis` section; `validate_sandbox_config`
  extends the kind list, the kind-specific-key rules, and the db range check.
- `goga_tool_pybuggy/sandbox/engines` — new `BaseEngine::RedisEngine`; `build_engine`
  maps redis; `DataOperation`'s per-kind action set gains `set`/`hset`/`rpush`/`sadd`;
  the `redis` usage cook joins the header `Usages`.
- `goga_tool_pybuggy/sandbox/data` — new `RedisInstance`; the `services` preset accepts
  the redis kind.
- `goga_tool_pybuggy/sandbox` (root) — new `Sandbox.redis(name)`; the startup-data order
  extends to vault → http → postgres → redis; `RedisInstance` joins the data Imports.

Integration requirements: design and implement bottom-up (config → engines → data →
root), the established dependency direction; the engine follows `BaseEngine`'s journal and
readiness contracts; the view follows the lazy-declaration contract (declare only, apply
at the facade).

## Notes

- Input artifacts: `.goga/history/2026/sandbox-redis/adr.md` (settled decisions — the
  authoritative source for every behavioral choice in this task).
- Container-module facts verified against the testcontainers 4.15 sources:
  `testcontainers/community/redis.py` — `RedisContainer(image, port=6379, password=None)`
  wires `--requirepass` through `with_command` itself; `waiting_for` (core container)
  replaces the built-in `PingWaitStrategy`; the `redis` extra requires `redis>=7`.
- The usage cook `.goga/usages/cooks/redis.md` is created together with this task
  (approved content outline: domain/version floor, container contract, connect, readiness,
  operations, logical database and reset).
- Deferred by the ADR to a next iteration: `zadd`, TTL/expire, key deletion,
  read-back/assertions.
