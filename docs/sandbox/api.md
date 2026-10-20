# Python API

The Python surface of the sandbox: the built-in `sandbox` fixture, the session baseline,
binding the api to the running instance, and the data operations tests declare on the
dependency services. Data operations are write-only — reading dependency state back is
not part of the surface; assert on the responses of the service under test. The services
themselves — names, kinds, images, topics, migrations — come from the
[sandbox document](configuration.md); the lifecycle (activation, reset ownership,
environments) is covered in the [overview](index.md).

## The sandbox fixture

pybuggy owns the session-scoped `sandbox` fixture — do not define your own; a consumer
definition would shadow it and feed the reset and the api pre-flight a foreign object.
Take the fixture as a test argument, or let the `@services` preset decorator request it
for you:

```python
def test_direct(sandbox):  # requests the sandbox explicitly
    sandbox.postgresql("db").insert("orders", rows=[{"id": 100}])


@services(postgresql={"db": [{"table": "customers", "rows": [{"id": 1}]}]})
def test_marked(api):  # the decorator's usefixtures mark pulls the sandbox in
    ...
```

Starting and stopping are automatic — the sandbox starts on first use and stops at
session finalization.

## Session baseline

A session-scoped consumer fixture depending on the built-in one establishes the
code-declared baseline:

```python
# conftest.py
import pytest


@pytest.fixture(scope="session")
def seeded(sandbox):
    with sandbox.baseline():  # the baseline block — author code
        sandbox.postgresql("db").insert("customers", rows=[{"id": 1, "name": "Ann"}])
        sandbox.vault("secrets").put("payment/api-key", {"api_key": "test-key"})
    yield sandbox  # stopping is automatic — do not stop manually
```

Operations inside the `with sandbox.baseline()` block apply immediately and become the
session baseline: after every reset the services return to exactly this state. Baseline
rows may use `$ref` / `$lookup` references like any declaration — after every reset the
journal replay re-applies and re-resolves them, so generated keys stay consistent
between the baseline and the tests built on top of it.

## Binding the api

Binding is explicit — call `endpoint.bind(sandbox)` (or `api.bind(sandbox)`) once in
the test body. The bind replaces the client's address with the sandbox's service
address and installs the request pre-flight: the test's declared data applies as one
batch and the instance liveness is checked before every request. Every other test uses
the configured `base_url` (`--base-url` / `BASE_URL` / config) with no pre-flight.

```python
from goga_tool_pybuggy.api import Api, Endpoint


@pytest.fixture(scope="function")
def checkout(api: Api) -> Endpoint:
    return Endpoint(api, "/checkout", method="POST")


def test_checkout(checkout, sandbox):
    checkout.bind(sandbox)
    sandbox.postgresql("db").insert("orders", rows=[{"id": 100, "customer_id": 1}])
    response = checkout(json={"customer": 1, "total": 500})
    response.expect.has_status_code(200)
```

- All endpoints of one test share one `Api` — one `bind(sandbox)` rebinds them together.
- `--base-url` applies to the tests that do not bind; a bound test uses the sandbox
  address. The option itself stays required (see
  [Preconditions](index.md#preconditions-and-side-effects)).
- Declared operations apply automatically as one batch before the first service call —
  also the moment `$ref` / `$lookup` row values resolve, so a declaration made after
  earlier service calls may reference rows those calls created (`$lookup`).
- A crashed instance fails the affected tests, with the instance output attached to the
  failure.

## Service views

Every configured service is reachable by name through the session fixture, kind-named:

```python
sandbox.postgresql("db")   # a postgresql service named db
sandbox.http("payments")   # an http service named payments
sandbox.vault("secrets")   # a vault service named secrets
sandbox.kafka("events")    # a kafka service named events
sandbox.redis("cache")     # a redis service named cache
```

Each view also exposes `name`, `host`, and `port` — `host` and `port` are the mapped
address the `{{<service>.host}}` / `{{<service>.port}}` placeholders of the instance env
resolve to. The sandbox object itself exposes `base_url` — the address of the running
service under test, the value a bound api client resolves to; it carries the instance
entry's declared `base_path` prefix when one is declared (see
[configuration](configuration.md#instance)). Nothing executes at
declaration time — the sandbox applies the accumulated batch automatically before the
first call to the service under test; an unknown service name fails fast.

## Postgres operations

```python
sandbox.postgresql("db").insert("orders", rows=[{"id": 1, "total": 100}])
```

One `insert` call targets one table; the rows apply in list order inside one
transaction. A plain mapping column value binds as JSON text — the json/jsonb column
form.

### Referencing rows

Explicit literal ids are optional — a row value may reference another row instead of a
hardcoded key. Two reference forms:

- **`$ref`** — addresses the rows the data plane itself applied since the last reset
  (baseline journal, presets, in-test declarations — in application order):

  ```python
  sandbox.postgresql("db").insert("customers", rows=[{"name": "Ann"}])  # id generated
  sandbox.postgresql("db").insert("orders", rows=[{"customer_id": {"$ref": "customers.0.id"}, "total": 500}])
  ```

  The value is the real applied column value — an autoincrement id resolves to whatever
  the sequence generated (deterministic after a reset: 1, 2, 3 in application order). A
  later row of one insert may reference an earlier row; inserting an extra earlier
  parent row shifts the indexes.

- **`$lookup`** — matches the current database state by predicate, regardless of who
  created the row (the service under test included):

  ```python
  # the service itself created the customer through its API
  response = checkout.post(json={"name": "Ann", "email": "ann@x.io"})

  sandbox.postgresql("db").insert(
      "orders",
      rows=[{"customer_id": {"$lookup": {"table": "customers", "where": {"email": "ann@x.io"}}}}],
  )
  ```

  The predicate must match exactly one row — zero matches fail naming the missing
  precondition, several matches fail naming the ambiguity. The resolved column defaults
  to the table's primary key; pass `"column"` to choose another.

Common rules:

- References are recognized only as top-level row values; a nested dict carrying `$ref`
  stays plain column data — and a plain mapping column value binds as JSON text (the
  json/jsonb column form).
- The reference grammar is validated at declaration — a malformed form fails before
  anything executes.
- Resolution happens at apply time, right before the first service call; declarations
  are never rewritten, so baseline replay re-resolves references after every reset.
- References resolve within one postgres service; rows created by raw sql startup
  statements are addressable only through `$lookup`.

## Http operations

```python
sandbox.http("payments").stub(
    {
        "request": {"method": "POST", "urlPath": "/v1/charge"},
        "response": {"status": 200, "jsonBody": {"status": "captured"}},
    }
)
```

The stub body is a WireMock mapping object (`request` + `response`) — the same shape the
`data.http` section of the [sandbox document](configuration.md#data) accepts, passed
through as given: matching, priority, delays, and faults stay available.

## Vault operations

```python
sandbox.vault("secrets").put("payment/api-key", {"api_key": "test-key"})
```

The secret lands on the dev-mode vault's default KV v2 `secret/` mount, under the given
path (the [mock credentials](index.md#preconditions-and-side-effects) apply).

## Kafka operations

```python
sandbox.kafka("events").produce("orders.events", {"id": 1}, key="1")
```

A produced topic must be declared on the kafka service entry of the sandbox document —
an undeclared topic fails the operation. The wire encoding is fixed: a mapping value
arrives as JSON bytes, a plain string value as UTF-8 bytes, and the key (when given) as
UTF-8 — the service under test consumes exactly that.

## Redis operations

```python
sandbox.redis("cache").set("feature-flag/a", "enabled")
sandbox.redis("cache").hset("user:1", {"name": "Ann", "plan": "pro"})
sandbox.redis("cache").rpush("queue:orders", [{"id": 1}, {"id": 2}])
sandbox.redis("cache").sadd("members:vip", ["ann", "bob"])
```

The operation names mirror the redis commands, and the choice is part of your visibility
contract — the writer must be type-correct for the service's read path: a `set`-seeded
key is invisible to a service reading `HGET`. Pick by the reader — `GET` (`set`),
`HGET`/`HGETALL` (`hset`), `LRANGE` (`rpush`), `SMEMBERS` (`sadd`).

- Values are strings or JSON-serializable plain data; serialization to the wire form
  happens at execution and the declared payload is never rewritten — a string passes
  through as given, everything else arrives as its JSON text.
- Operations apply to the logical database declared on the service entry (`db`, default
  `0` — see the [sandbox document](configuration.md#services)); align the service's own
  db configuration with it, or the service will not see the seeded data.
- Later writes to the same key follow the redis command semantics — a second `set`
  overwrites, `rpush`/`sadd` append.

## Presets

Data can also be declared directly on the test as a **preset** — each declaration
carries the same fields as the matching view operation — redis declarations additionally
name the operation through the `action` key (`set` / `hset` / `rpush` / `sadd`), because
the kind has four operations — and presets apply on top of the reset state, ahead of the
test's own operations. All five kinds are accepted (`postgresql`, `kafka`, `vault`,
`http`, `redis`); an unsupported kind or a malformed row fails at decoration time,
before anything starts. The decorator also stamps a `usefixtures` mark that pulls the
sandbox into the test's fixture closure, so the reset and the presets run. The mark does
not imply binding: a preset-declaring test that calls the service still takes the
`sandbox` argument and calls `endpoint.bind(sandbox)` explicitly:

```python
from goga_tool_pybuggy import services


@services(
    postgresql={"db": [{"table": "customers", "rows": [{"id": 1, "name": "Ann"}]}]},
    http={
        "payments": [
            {
                "request": {"method": "GET", "urlPath": "/v1/rate"},
                "response": {"status": 200, "jsonBody": {"rate": 0.5}},
            }
        ]
    },
    redis={
        "cache": [
            {"action": "set", "key": "feature-flag/a", "value": "enabled"},
            {"action": "hset", "key": "user:1", "values": {"name": "Ann", "plan": "pro"}},
        ]
    },
)
def test_checkout(api, sandbox):
    api.bind(sandbox)
    ...
```

## Ordering and apply timing

Operations apply in declaration order, per service: presets first, then in-test
operations in call order. Foreign-key chains are expressed by declaring parents before
children — one `insert` call targets one table (the database constraint still requires
the parent row first). Redis operations apply in declaration order against the declared
database — later writes to the same key follow the redis command semantics (a second
`set` overwrites, `rpush`/`sadd` append). The per-test reset of a redis service is
`FLUSHDB` of the declared logical database plus the baseline journal replay — the
container keeps running through the reset, and keys written by one test never leak into
the next. Reset-side cleanup needs no ordering from the author.
