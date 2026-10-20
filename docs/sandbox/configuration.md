# The sandbox document

The sandbox document — `.goga/tools/pybuggy/sandbox.yml`, under the pybuggy tools home
of the test repository — declaratively describes one service sandbox: the service under
test, its mocked dependency services, and the data they start with. Its presence alone
activates the sandbox for every pytest run; an invalid document fails the run before
anything starts (the activation rules are covered in the
[overview](index.md#activation)). This page is the field-by-field reference; the
[Python API](api.md) covers what tests do with the running sandbox.

## Layout

```yaml
# .goga/tools/pybuggy/sandbox.yml
instance:                           # the entry under test
  image: my-service:latest          # required — the image under test
  port: 8080                        # required — the container port the service serves on
  base_path: /api/v1                # optional — the API path prefix the sandbox base_url carries
  probe:                            # optional — readiness probe
    path: /health                   # health path; omit to wait for the port only
    timeout: 60.0                   # readiness deadline seconds; default 30.0
    interval: 1.0                   # seconds between attempts; default 0.5
  env:                              # required — environment values of the instance
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

data:                               # startup data, applied before the instance starts
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

A mistyped top-level key fails the load with a hint toward the intended one — `service`
suggests `instance`, `instances` suggests `services`.

## instance

| field | type | default | meaning |
|---|---|---|---|
| `image` | `str` | required | the image under test |
| `port` | `int` | required | the container port the service serves on |
| `base_path` | `str` | `""` | URL path prefix of the service API — carried by the sandbox `base_url` the bound api client resolves; must start with `/` |
| `env` | `map[str, str]` | required | environment values of the instance — Jinja2 templates over the started service addresses |
| `probe` | `map` | — | readiness probe; the `path` field is accepted here only (see [probe](#probe)) |

`base_path` prefixes every bound request URL of the sandbox session — declare it when the
service mounts its API under a path prefix (`http://localhost:8080/api/v1` →
`base_path: /api/v1`). It must start with `/` (it is appended to
`http://<host>:<port>`); a prefix without the leading slash fails at document load. The
readiness `probe.path` stays relative to the host:port root regardless of `base_path` —
health endpoints commonly live outside the API prefix.

Instance env values are Jinja2 templates over the started service addresses:

- `{{<service>.host}}` and `{{<service>.port}}` resolve to the mapped address of the
  named service — e.g. `{{db.host}}` / `{{db.port}}` for the service named `db`, or
  `{{cache.host}}` / `{{cache.port}}` for a redis service named `cache`.
- Placeholders resolve only for configured service names; an unknown name fails
  validation.
- Values without placeholders pass through unchanged.
- The dependency mocks use fixed test credentials that the instance env must match:
  postgres accepts user `test`, password `test`, database `test` (connect with
  `postgres://test:test@{{db.host}}:{{db.port}}/test`); vault runs in dev mode with the
  root token `sandbox-root` (send it as `VAULT_TOKEN` / `X-Vault-Token`; secrets live on
  the default KV v2 `secret/` mount). A redis service with a declared `password` carries
  it as an env literal (`REDIS_PASSWORD: "sandbox-redis"`) — the same literal the sandbox
  passes to the container; an undeclared password means no authentication at all.

## services

Every service has a name (the mapping key) and a `kind`; any subset of kinds may be
configured, several services of one kind are allowed — configure only the dependencies
the service needs.

| field | type | default | meaning |
|---|---|---|---|
| `kind` | `str` | required | `postgresql`, `kafka`, `vault`, `http`, or `redis` |
| `image` | `str` | kind default | image override — omit for the product-pinned default of the kind |
| `probe` | `map` | — | readiness bounds; a `path` here is rejected (see [probe](#probe)) |
| `topics` | `list` | `[]` | kafka only — required and non-empty; rejected on any other kind |
| `migrations` | `map` | — | postgresql only — the schema source; rejected on any other kind (see [migrations](#migrations)) |
| `password` | `str` | — | redis only — start redis with authentication (`--requirepass`); omit for no authentication (the primary mode) |
| `db` | `int` | `0` | redis only — the logical database index, an integer within 0–15; the engine connects, seeds, and wipes this database |

- Service names are template identifiers (letters, digits, underscores; not starting
  with a digit — a hyphenated name such as `my-db` is rejected at load time): they name
  the `{{<service>.host}}` / `{{<service>.port}}` placeholders the instance env values
  resolve to.
- Every kind has a product-pinned default image; `image` overrides it:

| kind | default image | reset strategy |
|------|---------------|-----------------|
| `postgresql` | `postgres:16-alpine` | catalog-driven `TRUNCATE ... RESTART IDENTITY CASCADE` + journal replay |
| `kafka` | `mokapi/mokapi:0.52.0` | container restart (in-memory state wiped) + journal replay |
| `vault` | `hashicorp/vault:1.17` | container restart (dev-mode in-memory storage) + journal replay |
| `http` | `wiremock/wiremock:3.13.0` | `POST /__admin/mappings/reset` + journal replay |
| `redis` | `redis:8-alpine` | `FLUSHDB` of the declared database + journal replay |

- A `grpc` kind is rejected with an explicit "not supported yet" error.
- `password` and `db` exist only on redis entries — the common kind-specific-key rule. A
  `topics` or `migrations` declaration on a redis entry is rejected at load, exactly as on
  every other non-matching kind; conversely, `password` or `db` on any other kind fails
  the load naming the entry.
- Redis `password` (optional) starts redis with authentication (`--requirepass
  <password>`); omit it and redis starts without authentication (the primary mode). The
  value reaches the service under test as an env literal in the instance env — e.g.
  `REDIS_PASSWORD: "sandbox-redis"` — the postgres-URL precedent; no placeholder exists
  for it. The password rides the redis container command line, so it must be a non-empty
  string carrying no whitespace, quotes, or backslashes — an empty value or one with such
  characters fails the load naming the entry.
- Redis `db` (optional) is the logical database index, `0` by default (the conventional
  client default); it must be an integer within 0–15, checked at document load — an
  out-of-range value or a non-integer fails the load naming the entry. The engine
  connects, seeds, and wipes the declared database — align the service's own db
  configuration with it (a service configured to db 2 will not see db-0-seeded data).

## probe

Readiness is probed per target, similar to a Kubernetes probe, through an optional
`probe` block:

| field | applies to | default | meaning |
|---|---|---|---|
| `timeout` | every target | 30.0 | readiness deadline seconds; expiry fails with an actionable error |
| `interval` | every target | 0.5 | seconds between attempts |
| `path` | the instance entry only | — | health path; omit to wait for the port only |

- The probe endpoints of the kafka/vault/http services are fixed by the tool; `timeout`
  and `interval` are the only knobs they accept — a `path` there is rejected.
- The postgresql service readiness is a driver connection probe — no HTTP endpoint
  involved, bounded by the declared `timeout` and `interval`.
- The redis service readiness is an engine-owned PING probe bounded by the declared
  `timeout` and `interval` — a wrong password surfaces as an authentication error within
  the deadline, never a hang.
- The health `path` must start with `/` (it is appended to `http://<host>:<port>`); a
  path without the leading slash fails at document load.
- Both bounds must be positive, and the `interval` must not exceed the `timeout` —
  declare a smaller interval alongside a sub-second timeout.
- Omitting the block (or any field) keeps the defaults (30.0s / 0.5s). There is no
  global defaults block; readiness is configured per target only.

## migrations

The schema of a postgresql service — a folder of goose-format SQL migration files
applied once per test session at startup. Migrations are a property of the postgresql
service entry, the same way topics are a property of the kafka service:

| field | type | default | meaning |
|---|---|---|---|
| `location` | `str` | required | the migrations folder — resolves against the current working directory for a local source (the same anchor the document itself uses, no upward search); the path inside the repository for a remote one |
| `git.url` | `str` | required with `git` | the clone URL of the remote source — omit `git` entirely for a local source |
| `git.ref` | `str` | default branch | branch or tag — a bare commit SHA is not a valid ref |

- Access to a remote source relies on ambient git credentials (ssh-agent, credential
  helper, gitconfig) — never embed tokens in the URL; the scheme must be one of
  `https`, `http`, `git`, `ssh`, so rewrite scp-style URLs as `ssh://git@host/path`.
- One migration per file, named `<version>_<description>.sql` (e.g.
  `00003_create_orders.sql`); files apply once per session in ascending numeric version
  order; non-`.sql` files are ignored; duplicate version prefixes are invalid. The
  format is the goose SQL annotation subset — `-- +goose Up` / `-- +goose Down` (Down
  never executes), `-- +goose StatementBegin` / `-- +goose StatementEnd`, and
  `-- +goose NO TRANSACTION` (the file runs statement-by-statement, required by DDL
  such as `CREATE INDEX CONCURRENTLY`); anything else from goose — unknown annotations,
  `{{...}}` template variables, Go-based migrations — fails with the file named, and so
  does a file without an `-- +goose Up` section or a `StatementBegin` without its
  matching `StatementEnd`.
- The declaration is validated at document load, before any container starts. A local
  source fails the run naming the entry on: a missing folder, an empty folder, no
  `.sql` files, an invalid migration filename, or duplicate version prefixes. A remote
  source checks its URL shape at load (scheme allowlist, no embedded credentials) and
  its folder at apply.
- A remote source is shallow-cloned into a fresh temporary directory for the apply and
  deleted afterwards — nothing is copied into your repository, and each session
  downloads fresh. No version-tracking table is created; a failed migration stops
  startup naming the file and the postgres error. The apply runs one transaction per
  file — a failed file rolls back fully, while a file declared
  `-- +goose NO TRANSACTION` applies statement-by-statement and keeps its
  already-applied statements.

Role split — migrations build the schema once per session; `data.postgres` stays the
per-test seed data. Startup order inside the service: container ready → migrations →
`data.postgres` statements journaled as baseline. The per-test reset keeps the migrated
schema and replays only `data.postgres` — write seed statements as INSERTs, not as
`CREATE TABLE`. If the service applies its own migrations at startup, simply do not
declare sandbox migrations.

## topics

The kafka topology is a property of the kafka service entry — declared inline, like
`image` and `kind`:

- `topics` is required on every kafka entry and holds at least one declaration; an
  entry without topics fails before any container starts.
- Each declaration carries `name` (required, non-empty) and `partitions` (optional,
  default 1, a positive integer); topic names are unique within the service entry.
- Topics exist only on kafka entries — a `topics` list on any other kind is rejected.
- The AsyncAPI document the mock consumes is generated internally from the declared
  topics; no spec file is read or written, and nothing generated is exposed to authors.

## data

The `data` sections are applied in a fixed order after all services are up and before
the instance starts — vault secrets, then http mappings, then postgres init, then redis
data:

| section | target | declarations |
|---|---|---|
| `vault` | vault services | `{path, data}` secret writes |
| `http` | http services | WireMock mapping objects (`request` + `response`) |
| `postgres` | postgresql services | SQL statements (seed data) |
| `redis` | redis services | `{action: set/hset/rpush/sadd, key, value/values/members}` — the action key plus the fields of the matching view operation |

- A `kafka` section does not exist — declaring one fails; the kafka topology lives on
  the service entry.
- Http declarations pass through as WireMock mapping objects — matching, priority,
  delays, and faults stay available to authors; a request that matches no mapping gets
  a visible near-miss response, so wiring mistakes surface in test failures.
- Within a section, declarations apply in the order written — for dependent rows
  (foreign keys), declare parents before children.
- Postgres init statements are raw sql: they resolve no `$ref` / `$lookup` references,
  and they run after the service's migrations (when declared), against the migrated
  schema. They replay on every per-test reset — write them idempotent; the
  TRUNCATE-based reset keeps tables and the migrated schema, only data is wiped.
- Rows created by raw sql startup statements are addressable from test declarations
  only through `$lookup`.
- Redis declarations carry the `action` key (`set`, `hset`, `rpush`, or `sadd`) plus the
  fields of the matching view operation — `key` with `value`, `values`, or `members`.
  Anything else fails at load naming the entry: a declaration without a valid `action`
  key, or one whose field set is not exactly the action's own (a `set` with `members`,
  an `hset` without `values`):

  ```yaml
  redis:
    cache:
      - action: set
        key: feature-flag/a
        value: enabled
      - action: hset
        key: user:1
        values: {name: Ann, plan: pro}
      - action: rpush
        key: queue:orders
        values: [{id: 1}, {id: 2}]
      - action: sadd
        key: members:vip
        members: [ann, bob]
  ```

- Redis declarations seed the declared logical database and replay on every per-test
  reset — `FLUSHDB` of the declared database, then the journal replay; the container
  never restarts through the reset. Values are strings or JSON-serializable plain data;
  serialization to the wire form happens at execution and the declaration is never
  rewritten.
