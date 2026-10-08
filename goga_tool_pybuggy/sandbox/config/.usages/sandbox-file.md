# Sandbox file — authoring the sandbox document

## Domain

The declarative description of one service sandbox: the instance under test, its mocked
dependency services, and the data they start with. Target audience: service test authors. The
document lives under the pybuggy tools home of the service test repository; its presence alone
activates the sandbox for every pytest run, and an invalid document fails the run before
anything starts.

## File layout

```yaml
# .goga/tools/pybuggy/sandbox.yml
instance:
  image: my-service:latest          # required — the image under test
  port: 8080                        # required — the container port the service serves on
  probe:                            # optional — readiness declaration
    path: /health                   # health path; omit to wait for the port only
    timeout: 60.0                   # readiness deadline seconds; default 30.0
    interval: 1.0                   # seconds between attempts; default 0.5
  env:                              # required — environment values of the service
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

## Services

- Every service has a name (the key) and a `kind`: `postgresql`, `kafka`, `vault`, or `http`.
- The name is a template identifier — letters, digits, underscores, not starting with a digit —
  because it names the `{{<name>.host}}` / `{{<name>.port}}` placeholders (a hyphenated name
  such as `my-db` is rejected at load time).
- `image` overrides the product-pinned default image of the kind — omit it for the default:

| kind | product-pinned default image |
|---|---|
| `postgresql` | `postgres:16-alpine` |
| `kafka` | `mokapi/mokapi:0.52.0` |
| `vault` | `hashicorp/vault:1.17` |
| `http` | `wiremock/wiremock:3.13.0` |

- Any subset of kinds may be configured; configure only the dependencies the service needs.
- A `grpc` kind is rejected at document load with an explicit "not supported yet" error.

## Kafka topics

The kafka topology is a property of the kafka service entry — declared inline, like `image` and
`kind`:

- `topics` is required on every kafka entry and holds at least one declaration; an entry
  without topics fails before any container starts.
- Each declaration carries `name` (required) and `partitions` (optional, default 1).
- Topics exist only on kafka entries — a `topics` list on any other kind is rejected.
- The AsyncAPI document the mock consumes is generated internally; no spec file is read or
  written, and nothing generated is exposed to authors.

## Readiness probes

Readiness is declared per target, Kubernetes-probe-like, as an optional `probe` block:

| field | applies to | default | meaning |
|---|---|---|---|
| `timeout` | every target | 30.0 | readiness deadline seconds; expiry fails with an actionable error |
| `interval` | every target | 0.5 | seconds between attempts |
| `path` | the instance entry only | — | health path; omit to wait for the port only |

- The probe endpoints of the kafka/vault/http services are fixed by the tool; `timeout` and
  `interval` are the only knobs they accept — a `path` there is rejected.
- The postgresql service readiness is an engine-owned driver connection probe bounded by
  the declared timeout and interval.
- The health `path` must start with `/` — it is appended to `http://<host>:<port>`; a path
  without the leading slash fails at document load.
- The `interval` must not exceed the `timeout` — declare a smaller interval alongside a
  sub-second timeout.
- Omitting the block (or any field) keeps the established behavior — defaults reproduce it
  exactly.
- No global defaults block exists; readiness is declared per target only.

## Wiring the instance to its dependencies

Instance env values are Jinja2 templates over the started service addresses:

- `{{<service>.host}}` and `{{<service>.port}}` resolve to the mapped address of the named
  service — e.g. `{{db.host}}` / `{{db.port}}` for the service named `db`.
- Placeholders resolve only for configured service names; an unknown name fails validation.
- Values without placeholders pass through unchanged.
- The dependency mocks carry fixed test credentials the instance env must match: postgres
  accepts user `test`, password `test`, database `test`
  (`postgres://test:test@{{db.host}}:{{db.port}}/test`); vault runs in dev mode with the
  root token `sandbox-root` (send it as `VAULT_TOKEN` / `X-Vault-Token`; secrets live on
  the default KV v2 `secret/` mount).

## Startup data layer

Applied in a fixed order after all services are up and before the instance starts:

| section | target | declarations |
|---|---|---|
| `vault` | vault services | `{path, data}` secret writes |
| `http` | http services | WireMock mapping objects (`request` + `response`) |
| `postgres` | postgresql services | SQL statements (schema/bootstrap SQL) |

- A `kafka` section does not exist — declaring one fails; the kafka topology lives on the
  service entry.
- Within a section, declarations apply in the order written — for dependent rows (foreign keys),
  declare parents before children. Postgres init statements are raw sql: they resolve no
  `$ref` / `$lookup` references and their rows are addressable later only through `$lookup`.
- Postgres init statements replay on every per-test reset — write them idempotent (e.g.
  `CREATE TABLE IF NOT EXISTS`); the TRUNCATE-based reset keeps tables, only data is wiped.

## Locating the document

- The file name and location are fixed: `.goga/tools/pybuggy/sandbox.yml`, resolved from the
  current working directory only — resolution never searches elsewhere.
- If the sandbox does not activate, verify the document sits at exactly this path and that the
  run starts from the repository root.

## Preconditions and constraints

- An invalid document (unknown kind, unknown service reference, missing or unknown entry
  key, malformed placeholder or declaration, kafka entry without topics, topics on a
  non-kafka entry, probe `path` on a service or without its leading slash, unparsable YAML)
  fails the run before any container starts, with an error naming the entry.
- Without the document the product is fully inert — nothing starts, nothing changes.
- A container runtime must be available in the environment running the tests.
