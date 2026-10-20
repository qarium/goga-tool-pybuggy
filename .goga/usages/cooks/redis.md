# redis — the client and container of the sandbox redis instance

## Domain

`redis` (redis-py, the official client) is the redis data plane of the pybuggy sandbox
capability. Its v1 job: seed precondition data (SET / HSET / RPUSH / SADD) from the test
process into the real redis container, answer the readiness probe (PING), and reset the
declared logical database (FLUSHDB). Read-back is out of the v1 scope — the client's read
side stays unused apart from PING.

Version floor: redis >= 7 (`redis>=7.0` in the pybuggy dependencies). The pinned
testcontainers 4.15 declares `redis>=7` for its `redis` extra — the floor keeps one
resolution, no conflicts.

Import in code:
```python
import redis
from testcontainers.community.redis import RedisContainer
```

---

## Container — the community redis module

`RedisContainer` (community module, present in the pinned testcontainers 4.15) is a generic
`DockerContainer` underneath — no env setup, port 6379 published:

```python
container = RedisContainer(image="redis:8-alpine", password=password or None)
container.waiting_for(engine_probe)  # replaces the module's built-in PingWaitStrategy
```

- The product-pinned default image is `redis:8-alpine` (major pin); the service entry's
  `image` override replaces it.
- The module constructor hardcodes its `PingWaitStrategy`. The engine replaces it through
  `waiting_for(...)` — the core container sets `_wait_strategy` from that call — so readiness
  stays engine-owned, bounded by the declared probe deadline and interval.
- Auth: pass `password` to the constructor and the module wires the container command
  (`redis-server --requirepass <password>`) itself; omit it and the container starts without
  authentication — the primary mode. The password reaches the service under test as an env
  literal in the sandbox document — no placeholder kind exists for it.
- No volume is mounted — the state is in-memory by design; the reset never restarts the
  container.
- `get_client(**kwargs)` builds a `redis.Redis` against the mapped host/port with the module
  password; `db` and other client kwargs pass through. The engine may build the client itself —
  mapped address, declared db, declared password.

---

## Connect — one client per session instance

```python
client = redis.Redis(
    host=host,        # mapped host from the container engine
    port=port,        # published host-side port — never assume a fixed one
    db=db,            # the declared logical database, default 0
    password=password or None,
)
```

- `redis.Redis` connects lazily — the first command opens the connection. `client.ping()` is
  the readiness primitive; call it deliberately, do not rely on a first data command.
- Keep one client per redis instance for the session; close it (`client.close()`) on stop.
  No pooling — the data set is tiny and the lifecycle is session-scoped.
- The client is write-only in v1 — `decode_responses` stays at the default (False); responses
  of SET/HSET/RPUSH/SADD/FLUSHDB are not consumed.

---

## Readiness — engine-owned PING probe

Readiness is a PING loop run by the engine, bounded by the target's readiness declaration:
attempt PING at the declared interval, fail with an actionable error when the deadline
expires. redis-py failures live in `redis.exceptions` (`ConnectionError`,
`AuthenticationError`) — a wrong password surfaces as an auth error on the first PING, so
the probe catches it within the declared bounds, never as a hang.

---

## Operations — type-correct writers

Action names mirror the redis commands — `set`, `hset`, `rpush`, `sadd`:

```python
client.set(key, value)              # GET readers
client.hset(key, mapping=values)    # HGET / HGETALL readers
client.rpush(key, *values)          # LRANGE readers
client.sadd(key, *members)          # SMEMBERS readers
```

- The writer must be type-correct for the service's read path: a SET-seeded key is invisible
  to a service reading HGET (wrong value encoding) — the operation choice is part of the
  author's visibility contract.
- Values are strings or JSON-serializable plain data. Serialization to the wire form happens
  at execution — the declared payload is never rewritten, so baseline-journal replay is
  deterministic.
- A failed command raises a redis exception; the sandbox layer wraps it into an error naming
  the service and the operation.

---

## Logical database and reset

- `db` is declared on the service entry, validated at document load to the 0–15 range,
  default 0 (the conventional client default). The engine connects, seeds, and wipes the
  declared database. An author aligning the service's db configuration with the declared
  `db` is part of the visibility contract — a service configured to db 2 will not see
  db-0-seeded data.
- Reset between tests: `client.flushdb()` of the declared database, then baseline-journal
  replay through the same execution path as apply. The wipe is one cheap command; the
  data-plane connection survives the reset and the container never restarts.
- `FLUSHDB` wipes only the declared logical database — other databases keep their keys.
