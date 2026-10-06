# Sandbox file — authoring `.sandbox.yml`

## Domain

The declarative description of one service sandbox: the service under test, its mocked dependency
instances, and the data they start with. Target audience: service test authors. The file lives at
the root of the service test repository; its presence alone activates the sandbox for every pytest
run, and an invalid file fails the run before anything starts.

## File layout

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
  db:       { kind: postgresql, image: postgres:16-alpine }
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

## Instances

- Every instance has a name (the key) and a `kind`: `postgresql`, `kafka`, `vault`, or `http`.
- The name is a template identifier — letters, digits, underscores, not starting with a digit —
  because it names the `{{<name>.host}}` / `{{<name>.port}}` placeholders (a hyphenated name
  such as `my-db` is rejected at load time).
- `image` overrides the product-pinned default image of the kind — omit it for the default:

| kind | product-pinned default image |
|---|---|
| `postgresql` | `postgres:16-alpine` |
| `kafka` | `mokapi/mokapi:0.28.0` |
| `vault` | `hashicorp/vault:1.17` |
| `http` | `wiremock/wiremock:3.13.0` |

- Any subset of kinds may be configured; configure only the dependencies the service needs.
- A `grpc` kind is rejected at document load with an explicit "not supported yet" error.

## Wiring the service to its dependencies

Service env values are Jinja2 templates over the started instance addresses:

- `{{<instance>.host}}` and `{{<instance>.port}}` resolve to the mapped address of the named
  instance — e.g. `{{db.host}}` / `{{db.port}}` for the instance named `db`.
- Placeholders resolve only for configured instance names; an unknown name fails validation.
- Values without placeholders pass through unchanged.

## Startup data layer

Applied in a fixed order after all instances are up and before the service starts:

| section | target | declarations |
|---|---|---|
| `vault` | vault instances | `{path, data}` secret writes |
| `http` | http instances | WireMock mapping objects (`request` + `response`) |
| `kafka` | kafka instances | AsyncAPI spec file path (topics of the mock) |
| `postgres` | postgresql instances | SQL statements (schema/bootstrap SQL) |

Within a section, declarations apply in the order written — for dependent rows (foreign keys),
declare parents before children.

- Postgres init statements replay on every per-test reset — write them idempotent (e.g.
  `CREATE TABLE IF NOT EXISTS`); the TRUNCATE-based reset keeps tables, only data is wiped.

## Preconditions and constraints

- The file name and location are fixed: `.sandbox.yml` at the repository root.
- An invalid file (unknown kind, unknown instance reference, missing required field, malformed
  placeholder or declaration, unparsable YAML) fails the run before any container starts, with
  an error naming the entry.
- Without the file the product is fully inert — nothing starts, nothing changes.
- A container runtime must be available in the environment running the tests.
