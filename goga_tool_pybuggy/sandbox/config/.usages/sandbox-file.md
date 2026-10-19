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
    REDIS_URL: "redis://{{cache.host}}:{{cache.port}}/0"

services:                           # named dependency services; several of one kind are allowed
  db:
    kind: postgresql
    image: postgres:16-alpine       # optional image override
    migrations:                     # optional — the schema, applied once per session, never journaled
      location: db/migrations       # local folder (cwd-relative), or a path inside the repo when git is set
      # git:                       # optional — omit for a local source
      #   url: https://gitlab.example/acme/service.git
      #   ref: release-branch      # optional — branch or tag; omit for the default branch
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
  cache:                            # redis — a real redis container
    kind: redis
    # password: sandbox-redis      # optional — omit to start redis WITHOUT authentication
    # db: 2                        # optional — logical database index 0–15; default 0

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
      - "INSERT INTO customers (email) VALUES ('ann@x.io')"
  redis:
    cache:
      - action: set            # set / hset / rpush / sadd — the view operation
        key: feature-flag/a
        value: enabled
```

## Services

- Every service has a name (the key) and a `kind`: `postgresql`, `kafka`, `vault`, `http`,
  or `redis`.
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
| `redis` | `redis:8-alpine` |

- Any subset of kinds may be configured; configure only the dependencies the service needs.
- A `grpc` kind is rejected at document load with an explicit "not supported yet" error.

### Redis keys

`password` and `db` exist only on redis entries — the common kind-specific-key rule:

- `password` (optional) — when present, redis starts with authentication
  (`--requirepass <password>`); omit it and redis starts without authentication (the primary
  mode). The value travels to the service under test as an env literal in the sandbox
  document (the postgres-URL precedent) — e.g. `REDIS_PASSWORD: "sandbox-redis"` — no
  placeholder kind exists for it. The password rides the redis container command line, so it
  must carry no whitespace, quotes, or backslashes — a value with such characters fails the
  load naming the entry.
- `db` (optional) — the logical database index, `0` by default (the conventional client
  default); must be an integer within 0–15, checked at document load. The engine connects,
  seeds, and wipes the declared database — align the service's own db configuration with it
  (a service configured to db 2 will not see db-0-seeded data).
- A `topics` or `migrations` declaration on a redis entry is rejected at load, exactly as on
  every other non-matching kind.

## Migrations

The schema of a postgresql service — a folder of goose-format SQL migration files applied once
per test session at startup. Migrations are a property of the postgresql service entry, the
same way topics are a property of the kafka service:

- `migrations` exists only on postgresql entries — a declaration on any other kind is rejected
  at document load with the entry named.
- `location` — the migrations folder. For a local source it resolves against the current
  working directory (the same anchor the document itself uses, no upward search); for a remote
  source it is the path inside the repository.
- `git` — the optional remote source. `url` is the clone URL; `ref` is an optional branch or
  tag (omit it for the default branch). Access relies on ambient git credentials
  (ssh-agent, credential helper, gitconfig) — never embed tokens in the URL.

Role split — migrations build the schema once per session; `data.postgres` stays the per-test
seed data. Startup order inside the service: container ready → migrations → `data.postgres`
statements journaled as baseline. The per-test reset keeps the migrated schema and replays only
`data.postgres` — write seed statements as INSERTs, not as `CREATE TABLE`.

File rules of the folder:

- One migration per file: `<version>_<description>.sql` (e.g. `00003_create_orders.sql`);
  files apply once per session in ascending numeric version order; non-`.sql` files are
  ignored; duplicate version prefixes are invalid.
- Supported goose annotations: `-- +goose Up` / `-- +goose Down` (Down never executes),
  `-- +goose StatementBegin` / `-- +goose StatementEnd`, `-- +goose NO TRANSACTION` (the file
  runs statement-by-statement — required by DDL such as `CREATE INDEX CONCURRENTLY`). Anything
  else from goose (unknown annotations, `{{...}}` variables, Go-based migrations) is
  unsupported and fails with the file named.
- No version-tracking table is created; migration failures stop startup with the file and the
  postgres error named.

Validation at document load, before any container starts: migrations on a non-postgresql
service, a missing or empty local path, and — for a local source — the on-disk folder checks:
empty folder, no `.sql` files, an invalid migration filename, duplicate version prefixes.
A remote source checks its URL shape only (scheme allowlist https/http/git/ssh, no embedded
credentials) — its folder is checked at apply time, inside the clone.

Remote sources: the repository is shallow-cloned for the apply and deleted afterwards —
nothing is copied into your repository; each session downloads fresh.

A service that applies its own migrations at startup: simply do not declare sandbox
migrations — either/or, the author's choice and responsibility.

## Kafka topics

The kafka topology is a property of the kafka service entry — declared inline, like `image`
and `kind`:

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
- The redis service readiness is an engine-owned PING probe bounded by the declared timeout
  and interval — a wrong password surfaces as an auth error within the deadline, never a hang.
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
  service — e.g. `{{db.host}}` / `{{db.port}}` for the service named `db`; they apply to a
  redis service unchanged (e.g. `{{cache.host}}` / `{{cache.port}}`).
- Placeholders resolve only for configured service names; an unknown name fails validation.
- Values without placeholders pass through unchanged.
- The dependency mocks carry fixed test credentials the instance env must match: postgres
  accepts user `test`, password `test`, database `test`
  (`postgres://test:test@{{db.host}}:{{db.port}}/test`); vault runs in dev mode with the
  root token `sandbox-root` (send it as `VAULT_TOKEN` / `X-Vault-Token`; secrets live on the
  default KV v2 `secret/` mount). A redis service with a declared `password` carries it as an
  env literal (`REDIS_PASSWORD: "sandbox-redis"`) — the same literal the sandbox passes to the
  container; an undeclared password means no authentication at all.

## Startup data layer

Applied in a fixed order after all services are up and before the instance starts:

| section | target | declarations |
|---|---|---|
| `vault` | vault services | `{path, data}` secret writes |
| `http` | http services | WireMock mapping objects (`request` + `response`) |
| `postgres` | postgresql services | SQL statements (seed data) |
| `redis` | redis services | `{action: set/hset/rpush/sadd, key, value/values/members}` — the action key plus the matching view operation fields |

- A `kafka` section does not exist — declaring one fails; the kafka topology lives on the
  service entry.
- Within a section, declarations apply in the order written — for dependent rows (foreign keys),
  declare parents before children. Postgres init statements are raw sql: they resolve no
  `$ref` / `$lookup` references and their rows are addressable later only through `$lookup`.
- Postgres statements run after the service's migrations (when declared), against the migrated
  schema, and replay on every per-test reset — write them idempotent; the TRUNCATE-based reset
  keeps tables (and the migrated schema), only data is wiped.
- Redis declarations seed the declared logical database and replay on every per-test reset
  (FLUSHDB of the declared db, then replay); values are strings or JSON-serializable plain
  data — the declaration is never rewritten.

## Locating the document

- The file name and location are fixed: `.goga/tools/pybuggy/sandbox.yml`, resolved from the
  current working directory only — resolution never searches elsewhere.
- If the sandbox does not activate, verify the document sits at exactly this path and that the
  run starts from the repository root.

## Preconditions and constraints

- An invalid document (unknown kind, unknown service reference, missing or unknown entry key,
  malformed placeholder or declaration, kafka entry without topics, topics on a non-kafka
  entry, migrations on a non-postgresql entry, `password` or `db` on a non-redis entry, redis
  `db` outside 0–15, invalid migrations declaration — missing or empty local folder, no `.sql`
  files, invalid migration filename, duplicate version prefixes (local sources; a remote
  source fails on its URL shape here and on its folder at apply), git URL outside the
  allowlist or with embedded credentials — probe `path` on a service or without its leading
  slash, unparsable YAML) fails the run before any container starts, with an error naming the
  entry.
- Without the document the product is fully inert — nothing starts, nothing changes.
- A container runtime must be available in the environment running the tests.
