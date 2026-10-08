# Sandbox

The **sandbox** is pybuggy's session-scoped isolated service testing capability: when the
pybuggy tools home holds a `sandbox.yml` document, every pytest run starts the **instance
under test** plus its mocked dependency **services** (**postgresql**, **kafka**,
**vault**, **http**) in containers, wires them into the instance environment, and points
the `api` fixture at the sandbox instance. Without the document the product is fully
inert — nothing starts, nothing changes.

## Activation

The sandbox activates by presence: `.goga/tools/pybuggy/sandbox.yml`, resolved from the
current working directory only — resolution never searches elsewhere. The same plugin
installation call that enables pybuggy arms the sandbox — nothing else is enabled:

```python
# conftest.py
from goga_tool_pybuggy import plugin

plugin.install()
```

With the document present, every pytest run starts the sandbox before the first test (the
progress is visible in the output); an invalid document fails the run before any container
starts; without the document the suite behaves exactly as it would without the sandbox. If
the sandbox does not activate, verify the document sits at exactly this path and that the
run starts from the repository root.

## Authoring the sandbox document

```yaml
# .goga/tools/pybuggy/sandbox.yml
instance:                           # the entry under test
  image: my-service:latest          # required — the image under test
  port: 8080                        # required — the container port the service serves on
  probe:                            # optional — readiness declaration
    path: /health                   # health path; omit to wait for the port only
    timeout: 60.0                   # readiness deadline seconds; default 30.0
    interval: 1.0                   # seconds between attempts; default 0.5
  env:                              # required — environment values of the instance
    DATABASE_URL: "postgres://test:test@{{db.host}}:{{db.port}}/test"
    KAFKA_BOOTSTRAP: "{{events.host}}:{{events.port}}"
    VAULT_ADDR: "http://{{secrets.host}}:{{secrets.port}}"
    VAULT_TOKEN: "sandbox-root"

services:                           # named dependency services; several of one kind are allowed
  db:
    kind: postgresql
    image: postgres:16-alpine       # optional image override
  events:
    kind: kafka
    probe:
      timeout: 45.0                 # wait bounds apply to the fixed probe endpoint
    topics:                         # the mocked kafka topology — inline, on the service entry
      - name: orders.events
      - name: payments.events
        partitions: 6               # optional; default 1
  secrets:
    kind: vault
  payments:
    kind: http

data:                               # startup data layer, applied before the instance starts
  vault:
    secrets:
      - path: payment/api-key
        data:
          api_key: test-key
          ttl: 1h
  http:
    payments:
      - request:
          method: POST
          urlPath: /v1/charge
        response:
          status: 200
          jsonBody:
            status: captured
  postgres:
    db:
      - "CREATE TABLE IF NOT EXISTS orders (id bigint PRIMARY KEY, customer text, total numeric)"
```

- Every service has a name (the key) and a `kind`: `postgresql`, `kafka`, `vault`, or
  `http`. Service names are template identifiers (letters, digits, underscores; not
  starting with a digit) — they name the `{{<service>.host}}` / `{{<service>.port}}`
  placeholders the instance env values resolve to. Placeholders resolve only for
  configured service names; an unknown name fails validation.
- Every kind has a product-pinned default image; `image` overrides it:

| kind | default image | reset strategy |
|------|---------------|----------------|
| `postgresql` | `postgres:16-alpine` | catalog-driven `TRUNCATE ... RESTART IDENTITY CASCADE` + journal replay |
| `kafka` | `mokapi/mokapi:0.52.0` | container restart (in-memory state wiped) + journal replay |
| `vault` | `hashicorp/vault:1.17` | container restart (dev-mode in-memory storage) + journal replay |
| `http` | `wiremock/wiremock:3.13.0` | `POST /__admin/mappings/reset` + journal replay |

- A `grpc` kind is rejected with an explicit "not supported yet" error.

### Kafka topics

The kafka topology is a property of the kafka service entry — declared inline, like
`image` and `kind`:

- `topics` is required on every kafka entry and holds at least one declaration; an entry
  without topics fails before any container starts.
- Each declaration carries `name` (required) and `partitions` (optional, default 1);
  topic names are unique within the service entry.
- Topics exist only on kafka entries — a `topics` list on any other kind is rejected.
- The AsyncAPI document the mock consumes is generated internally from the declared
  topics; no spec file is read or written, and nothing generated is exposed to authors.

### Readiness probes

Readiness is declared per target, Kubernetes-probe-like, as an optional `probe` block:

| field | applies to | default | meaning |
|---|---|---|---|
| `timeout` | every target | 30.0 | readiness deadline seconds; expiry fails with an actionable error |
| `interval` | every target | 0.5 | seconds between attempts |
| `path` | the instance entry only | — | health path; omit to wait for the port only |

- The probe endpoints of the kafka/vault/http services are fixed by the tool; `timeout`
  and `interval` are the only knobs they accept — a `path` there is rejected.
- The health `path` must start with `/` (it is appended to `http://<host>:<port>`); a
  path without the leading slash fails at document load.
- The `interval` must not exceed the `timeout` — declare a smaller interval alongside a
  sub-second timeout.
- Omitting the block (or any field) keeps the established behavior — the defaults
  reproduce it exactly. No global defaults block exists; readiness is declared per target
  only.

### Startup data

The `data` sections are applied in a fixed order after all services are up and before the
instance starts — vault secrets, then http mappings, then postgres init:

| section | target | declarations |
|---|---|---|
| `vault` | vault services | `{path, data}` secret writes |
| `http` | http services | WireMock mapping objects (`request` + `response`) |
| `postgres` | postgresql services | SQL statements (schema/bootstrap SQL) |

- A `kafka` section does not exist — declaring one fails; the kafka topology lives on the
  service entry.
- Within a section, declarations apply in the order written — for dependent rows (foreign
  keys), declare parents before children.
- Postgres init statements are raw sql: they resolve no `$ref` / `$lookup` references, and
  they replay on every per-test reset — write them idempotent (e.g. `CREATE TABLE IF NOT
  EXISTS`); the TRUNCATE-based reset keeps tables, only data is wiped.

## Session fixture and baseline

```python
# conftest.py
import pytest
from goga_tool_pybuggy import active_sandbox

@pytest.fixture(scope="session")
def sandbox():
    sbx = active_sandbox()
    with sbx.baseline():                      # the baseline boundary — author code
        sbx.postgresql("db").insert("customers", rows=[{"id": 1, "name": "Ann"}])
        sbx.vault("secrets").put("payment/api-key", {"api_key": "test-key"})
    yield sbx                                 # stop is product-owned — do not stop manually
```

Operations inside the baseline boundary apply immediately and become the session baseline:
after every reset the services return to exactly this state.

## Per-test reset

```python
# conftest.py
@pytest.fixture(autouse=True)
def _sandbox_reset(sandbox):
    sandbox.clear()
    yield
```

Reset returns every dependency service to the baseline — test order cannot change
outcomes. Only dependency data resets; the instance container keeps running (instance
in-memory state not resetting is an accepted v1 limitation).

## Calling the service

Tests use the standard `api` fixture unchanged — its address resolves from the sandbox:

```python
from goga_tool_pybuggy.api import Api, Endpoint

@pytest.fixture(scope="function")
def checkout(api: Api) -> Endpoint:
    return Endpoint(api, "/checkout", method="POST")

def test_checkout(checkout, sandbox):
    sandbox.postgresql("db").insert("orders", rows=[{"id": 100, "customer_id": 1}])
    response = checkout(json={"customer": 1, "total": 500})
    response.expect.has_status_code(200)
```

- The sandbox address overrides the configured `base_url` value at read time; the option
  itself stays required (see below); the startup output names the source.
- A typed `--base-url` flag together with an active sandbox fails fast with an explicit
  usage error — the sandbox owns the service address.
- Declared operations apply automatically as one batch before the first service call.
- A crashed instance fails the affected tests with an indication that the instance died
  and its output attached.

## Declaring dependency data

Every configured service is reachable by name through the session fixture, kind-named.
Nothing is executed at declaration time — the sandbox applies the accumulated batch
automatically before the first call to the service under test:

```python
sandbox.postgresql("db").insert("orders", rows=[{"id": 1, "total": 100}])
sandbox.http("payments").stub({
    "request": {"method": "POST", "urlPath": "/v1/charge"},
    "response": {"status": 200, "jsonBody": {"status": "captured"}},
})
sandbox.vault("secrets").put("payment/api-key", {"api_key": "test-key"})
sandbox.kafka("events").produce("orders.events", {"id": 1}, key="1")
```

A produced topic must be declared on the kafka service entry of the sandbox document — an
undeclared topic fails the operation. The wire encoding is fixed: a mapping value arrives as
JSON bytes, a plain string value as UTF-8 bytes, and the key (when given) as UTF-8 — the
service under test consumes exactly that.

Data can also be declared directly on the test as a **preset** (each declaration carries
the same fields as the matching view operation; presets apply on top of the reset state,
ahead of the test's own operations):

```python
from goga_tool_pybuggy import services

@services(
    postgresql={"db": [{"table": "customers", "rows": [{"id": 1, "name": "Ann"}]}]},
    http={"payments": [{"request": {"method": "GET", "urlPath": "/v1/rate"},
                        "response": {"status": 200, "jsonBody": {"rate": 0.5}}}]},
)
def test_checkout(api):
    ...
```

Operations apply in the order declared, per service: presets first, then in-test
operations in call order; foreign-key chains are expressed by declaring parents before
children — one `insert` call targets one table (the database constraint still requires the
parent row first).

### Referencing rows

Explicit literal ids are optional — a row value may reference another row instead of a
hardcoded key. Two reference forms:

- **`$ref`** — addresses the rows the data plane itself applied since the last reset
  (baseline journal, presets, in-test declarations — in application order):

  ```python
  sandbox.postgresql("db").insert("customers", rows=[{"name": "Ann"}])  # id generated
  sandbox.postgresql("db").insert(
      "orders", rows=[{"customer_id": {"$ref": "customers.0.id"}, "total": 500}]
  )
  ```

  The value is the real applied column value — an autoincrement id resolves to whatever the
  sequence generated (deterministic after a reset: 1, 2, 3 in application order). A later row
  of one insert may reference an earlier row; inserting an extra earlier parent row shifts
  the indexes.

- **`$lookup`** — matches the current database state by predicate, regardless of who created
  the row (the service under test included):

  ```python
  # the service itself created the customer through its API
  response = checkout.post(json={"name": "Ann", "email": "ann@x.io"})

  sandbox.postgresql("db").insert(
      "orders",
      rows=[{"customer_id": {"$lookup": {"table": "customers", "where": {"email": "ann@x.io"}}}}],
  )
  ```

  The predicate must match exactly one row — zero matches fail naming the missing
  precondition, several matches fail naming the ambiguity. The resolved column defaults to
  the table's primary key; pass `"column"` to choose another.

Common rules:

- References are recognized only as top-level row values; a nested dict carrying `$ref`
  stays plain column data.
- The reference grammar is validated at declaration — a malformed form fails before anything
  executes.
- Resolution happens at apply time, right before the first service call; declarations are
  never rewritten, so baseline replay re-resolves references after every reset.
- References resolve within one postgres service; rows created by raw sql startup
  statements are addressable only through `$lookup`.

## Preconditions and side effects

- The environment running the tests needs a **docker-compatible container runtime**; the
  startup error names the requirement when it is missing.
- The sandbox pulls the container/DB/Kafka stack into the environment
  (`testcontainers`, `psycopg`, `kafka-python`, `requests` — main dependencies of the
  package).
- The dependency mocks carry fixed test credentials the instance env must match: the
  postgres mock accepts user `test`, password `test`, database `test` (all created by the
  container — connect with `postgres://test:test@{{db.host}}:{{db.port}}/test`); the vault
  mock runs in dev mode with the root token `sandbox-root` (send it as `VAULT_TOKEN` /
  `X-Vault-Token`; secrets live on the default KV v2 `secret/` mount).
- After the session — including failed or interrupted runs — nothing remains; a rerun
  starts fresh.
- `base_url` stays a required plugin option even with an armed sandbox (the render
  contract is unchanged); any configured value is simply overridden at fixture time by
  the sandbox address.

### Running the tests inside a container

When pytest itself runs inside a container (a pipeline runner, a CI step image), the sandbox
containers are **siblings** on the host daemon — the engine drives them through the docker API,
nothing runs inside the runner. That topology needs two things from the runner's launcher:

```bash
docker run \
  -v /var/run/docker.sock:/var/run/docker.sock \        # the daemon must be reachable
  -e TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal \ # published ports resolve here
  ... your-runner-image python -m pytest
```

- The **socket mount** gives the engine a daemon to drive; without it the startup probe fails
  with the runtime-requirement error.
- The **host override** tells testcontainers which host actually answers the published ports —
  without it the client aims at the container-network gateway and every connection is refused.
  `host.docker.internal` is the Docker Desktop name; on a plain Linux host use the host's
  address or `host-gateway`.
- One shared address space results: the mapped service addresses the tests bootstrap on, the
  kafka broker advertises in metadata, and the `{{<service>.host}}`/`{{<service>.port}}`
  placeholders inject into the instance env are the same `host:port` — every consumer (runner,
  instance container) reaches every dependency through it.
- Every session gets its **own docker network**: all containers the sandbox starts (the
  dependency services and the instance under test) join it, and it is removed at teardown.
  Parallel sandboxes on one daemon are network-isolated from each other; the runner keeps
  consuming the published host ports as before.
- Alternative — a docker-in-docker daemon inside a privileged runner — needs neither the socket
  nor the override, at the cost of `--privileged` and a private image cache; the sandbox works
  unchanged in both topologies.
