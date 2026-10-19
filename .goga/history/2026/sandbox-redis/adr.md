# Sandbox: Redis as a fifth dependency kind

Status: accepted (2026-10-19)

The sandbox gains a `redis` dependency kind alongside `postgresql`, `kafka`, `vault`, and
`http` — a real redis container driven by redis-py, integrated into the same configuration,
engine, data-view, and preset surface as the existing kinds. A real service was chosen over a
mock because no maintained redis mock speaking RESP with runtime data control exists, and redis
itself is already what a mock would try to be: lightweight, in-memory, second-start, trivially
resettable — the postgres precedent applies.

## Settled decisions

- **Service nature**: a real redis container; no mock (research 2026-10: no maintained RESP
  mock product with a runtime data plane exists; kafka/vault/http have mock products, redis has
  none and needs none).
- **Image**: product-pinned `redis:8-alpine` (major pin, matching `postgres:16-alpine`), with
  the common `image` override on the service entry. No persistence configuration — no volume is
  mounted and the reset never restarts the container.
- **Auth**: optional `password` on the redis service entry — absent (the primary mode) starts
  redis without authentication; present starts it with `--requirepass`. The password reaches the
  service under test as an env literal in the sandbox document — the postgres precedent
  (`postgres://test:test@{{db.host}}:{{db.port}}/test` carries credentials as literals); no new
  placeholder kind is introduced.
- **Logical database**: optional `db` on the redis service entry, default 0 (the conventional
  client default), validated at document load to the 0–15 range. The engine connects, seeds,
  and wipes the declared database.
- **Container**: the `testcontainers.community.redis.RedisContainer` module (present in the
  pinned testcontainers 4.15; a generic `DockerContainer` underneath, publishing port 6379).
  Readiness stays engine-owned — the module's built-in `PingWaitStrategy` is replaced with the
  engine's PING probe bounded by the declared probe deadline and interval, the same principle
  by which the postgres engine disables its module's internal wait.
- **Data plane**: the official redis-py client (the client the testcontainers module itself is
  built on); one connection to the declared db for the session, closed on stop. Dependencies:
  `testcontainers[redis]` extra plus an explicit `redis` entry in pyproject; a new usage cook
  `.goga/usages/cooks/redis.md` records the contract, following `psycopg.md` / `kafka-python.md`.
- **Data operations (v1)**: `set(key, value)`, `hset(key, values)`, `rpush(key, values)`,
  `sadd(key, members)` — action names mirror the redis commands, as `put`/`produce`/`stub`
  mirror their planes. Values are strings or JSON-serializable plain data. Rationale: the
  seeding writer must be type-correct for the service's read path — a `SET`-seeded key is
  invisible to a service reading `HGET` (wrong value encoding), so v1 covers the structures
  services read through: GET (strings), HGET/HGETALL (hashes), LRANGE (lists), SMEMBERS (sets).
- **Deferred** (candidates for the next iteration): `zadd` (sorted sets), TTL/expire, key
  deletion, read-back/assertions.
- **Startup data**: a `data.redis` section of the sandbox document — service name →
  declarations, the same shapes the view operations declare — applied last in the fixed
  section order: vault → http → postgres → redis.
- **Reset between tests**: `FLUSHDB` of the declared database plus baseline-journal replay, no
  container restart — the postgres style: the wipe is a cheap command, the data-plane
  connection survives the reset. Restart-based reset stays reserved for kinds whose state
  cannot be wiped by command (kafka, vault).
- **Naming**: kind `redis`; facade `sandbox.redis(name)`; view `RedisInstance`; preset key
  `@services(redis={...})`; the `{{name.host}}` / `{{name.port}}` placeholders apply
  automatically through the generic rendering.
- **Validation**: kind-specific keys follow the common rule — `password` and `db` are accepted
  on the redis kind only; `topics` and `migrations` are rejected on it. Redis joins the
  supported-kinds list; the grpc "not supported yet" behavior is unchanged.

## Per-kind mechanics (redis row)

| kind | tool | data operations | reset between tests |
|---|---|---|---|
| redis | real `redis:8-alpine` container (testcontainers community redis module) | SET / HSET / RPUSH / SADD via redis-py | `FLUSHDB` of the declared db + baseline replay, no restart |

## Considered options

- **Mock vs real**: a mock would carry permanent wire-protocol or admin-API ownership with no
  benefit — redis already starts in about a second and holds its state in memory. Rejected.
- **Valkey instead of official redis** (BSD licensing): the image is a test-scope dependency,
  never distributed; official redis keeps author familiarity with command names and docs.
  Rejected for v1.
- **Generic container without the testcontainers module**: the module adds no env setup (unlike
  the postgres module's user/password/dbname), but it costs nothing, standardizes the port
  handling, and its wait strategy is injectable — the module is used with the engine's own
  bounded readiness.
- **`db` deferred like `zadd`**: rejected during discovery — a service configured to a
  non-zero database index would not see db-0-seeded data (the same visibility failure class as
  a type-incorrect writer), and the fix is cheap: connect, seed, and FLUSHDB the declared db.

## Consequences

- pyproject gains `testcontainers[redis]` and `redis`; a usage cook is added; the sandbox
  documentation pages (`docs/sandbox/configuration.md`, `api.md`, `index.md`) and the sandbox
  `.usages` files gain the redis kind.
- `FLUSHDB` wipes only the declared logical database — an author aligning the service's db
  configuration with the declared `db` is part of the visibility contract, as is choosing the
  type-correct writer for the service's read path.
- Seeded payloads stay plain serializable data end to end — the declaration is never rewritten;
  serialization to the wire form happens at execution, so journal replay is deterministic.
