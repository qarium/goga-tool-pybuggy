# Sandbox

The **sandbox** is pybuggy's session-scoped isolated service testing capability: when the
repository root holds a `.sandbox.yml` document, every pytest run starts the **service under
test** plus its mocked dependencies (**postgresql**, **kafka**, **vault**, **http**) in
containers, wires them into the service environment, and points the `api` fixture at the
sandbox service. Without the document the product is fully inert — nothing starts, nothing
changes.

## Activation

The sandbox activates by presence: `.sandbox.yml` at the repository root. The same plugin
installation call that enables pybuggy arms the sandbox — nothing else is enabled:

```python
# conftest.py
from goga_tool_pybuggy import plugin

plugin.install()
```

With the file present, every pytest run starts the sandbox before the first test (the
progress is visible in the output); an invalid file fails the run before any container
starts; without the file the suite behaves exactly as it would without the sandbox.

## Authoring `.sandbox.yml`

```yaml
service:
  image: my-service:latest        # required — the image under test
  port: 8080                      # required — the container port the service serves on
  health: /health                 # optional — readiness path; omit to wait for the port only
  env:                            # required — environment values of the service
    DATABASE_URL: "postgres://{{db.host}}:{{db.port}}/app"
    KAFKA_BOOTSTRAP: "{{events.host}}:{{events.port}}"
    VAULT_ADDR: "http://{{secrets.host}}:{{secrets.port}}"

instances:                        # named dependency instances; several of one kind are allowed
  db:       { kind: postgresql }
  events:   { kind: kafka }
  secrets:  { kind: vault }
  payments: { kind: http }

data:                             # startup data layer, applied before the service starts
  vault:
    secrets:
      - { path: "payment/api-key", data: { api_key: "test-key", ttl: "1h" } }
  http:
    payments:
      - request:  { method: POST, urlPath: /v1/charge }
        response: { status: 200, jsonBody: { status: "captured" } }
  kafka:
    events: "asyncapi.yaml"       # AsyncAPI document path — defines the mocked topics
  postgres:
    db:
      - "CREATE TABLE IF NOT EXISTS orders (id bigint PRIMARY KEY, customer text, total numeric)"
```

- Instance names are template identifiers (letters, digits, underscores; not starting with a
  digit) — they name the `{{<instance>.host}}` / `{{<instance>.port}}` placeholders the
  service env values resolve to. Placeholders resolve only for configured instance names.
- Every kind has a product-pinned default image; `image` overrides it:

| kind | default image | reset strategy |
|------|---------------|----------------|
| `postgresql` | `postgres:16-alpine` | catalog-driven `TRUNCATE ... RESTART IDENTITY CASCADE` + journal replay |
| `kafka` | `mokapi/mokapi:0.28.0` | container restart (in-memory state wiped) + journal replay |
| `vault` | `hashicorp/vault:1.17` | container restart (dev-mode in-memory storage) + journal replay |
| `http` | `wiremock/wiremock:3.13.0` | `POST /__admin/mappings/reset` + journal replay |

- Postgres init statements replay on every per-test reset — write them idempotent (e.g.
  `CREATE TABLE IF NOT EXISTS`).
- A `grpc` kind is rejected with an explicit "not supported yet" error.

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
after every reset the instances return to exactly this state.

## Per-test reset

```python
# conftest.py
@pytest.fixture(autouse=True)
def _sandbox_reset(sandbox):
    sandbox.clear()
    yield
```

Reset returns every dependency instance to the baseline — test order cannot change outcomes.
Only dependency data resets; the service container keeps running (service in-memory state
not resetting is an accepted v1 limitation).

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
- A crashed service fails the affected tests with an indication that the service died and
  its output attached.

## Declaring dependency data

Every configured instance is reachable by name through the session fixture, kind-named.
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

Operations apply in the order declared, per instance: presets first, then in-test
operations in call order; foreign-key chains are expressed by declaring parents before
children — one `insert` call targets one table.

## Preconditions and side effects

- The environment running the tests needs a **docker-compatible container runtime**; the
  startup error names the requirement when it is missing.
- The sandbox pulls the container/DB/Kafka stack into the environment
  (`testcontainers`, `psycopg`, `kafka-python`, `requests` — main dependencies of the
  package).
- After the session — including failed or interrupted runs — nothing remains; a rerun
  starts fresh.
- `base_url` stays a required plugin option even with an armed sandbox (the render
  contract is unchanged); any configured value is simply overridden at fixture time by
  the sandbox address.
