# Architecture Plan — Sandbox DB migrations

## Topic

Sandbox DB migrations — goose-format SQL applied once per session by a built-in up-only runner.

Plan file: `.goga/history/2026/feature-db-migration/arch.md`
Decision record: `.goga/history/2026/feature-db-migration/adr.md` (accepted 2026-10-08)
Task: `.goga/history/2026/feature-db-migration/task.md`

## Implementation Order

1. **`goga_tool_pybuggy/sandbox/migrations`** — CREATE. A leaf cell: no project imports (primitives
   in/out), so it is designed and implemented first; both later cells import from it.
2. **`goga_tool_pybuggy/sandbox/config`** — MODIFY. Depends on cell 1 (`check_local_migrations`,
   `check_git_url` via Imports); its declaration models are referenced by cell 3's imported
   `ServiceConfig`.
3. **`goga_tool_pybuggy/sandbox/engines`** — MODIFY. Depends on cells 1 and 2 (`run_migrations`,
   `MigrationError`, `ServiceConfig`); applies the migration step inside `PostgresEngine.start`.

Out-of-plan artifacts (documentation, not DSL): `docs/sandbox.md`, `docs/configuration.md` — update
alongside cell 2 to document the declaration and the schema-vs-seed role split.

## Artifacts

### Cell 1 — `goga_tool_pybuggy/sandbox/migrations` (CREATE)

#### CODEMANIFEST — `goga_tool_pybuggy/sandbox/migrations/CODEMANIFEST`

```yaml
Usages:
  conventions: .goga/usages/conventions.md
  goose-sql: .goga/usages/cooks/goose-sql.md
  psycopg: .goga/usages/cooks/psycopg.md
  gitpython: .goga/usages/cooks/gitpython.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `conventions` for the pydantic kw_only data models and the docstring rules.
  Use `goose-sql` for the migration file format: naming, version ordering, and the supported
  annotation subset.
  Use `psycopg` for executing migration statement bodies over the postgres connection.
  Use `gitpython` for the shallow-clone source resolution of remote migration folders.

  Migrations cell. Owns one migration set end to end: source resolution (a local folder or a
  remote git repository), goose-SQL parsing of the up-only subset, and the once-per-session
  apply over the sandbox's postgres connection. Every failure surfaces as `MigrationError`
  naming the migration file or source step and the underlying cause — never a silent misapply.
  Applied migrations are session-static: nothing here reads or writes the baseline journal.
  Use relative imports inside the cell.

---

"MigrationFile(version: int, filename: str, statements: list[str], no_transaction: bool)":
  location: goose.py
  annotations: |
    One parsed goose-format migration file — the apply-ready unit of the set.

    `version`: the numeric prefix of the filename, compared and applied numerically.
    `filename`: the source file name — the identity used in progress output and error messages.
    `statements`: the ordered statement bodies of the Up section, ready to execute as given.
    `no_transaction`: whether the file declared `-- +goose NO TRANSACTION` and must run
    statement-by-statement in autocommit.

    Requirements:
    - pydantic model, kw_only.

    Use `conventions` for the data-model rules.
  properties:
    "version -> int": |
      The numeric prefix of the filename.
    "filename -> str": |
      The source file name — the identity in progress output and error messages.
    "statements -> list[str]": |
      The ordered statement bodies of the Up section.
    "no_transaction -> bool": |
      Whether the file runs statement-by-statement in autocommit.

"MigrationError()":
  location: errors.py
  annotations: |
    The failure family of the migrations domain — the RuntimeError subtype.

    Every failure in this cell surfaces as this type: source resolution, naming, parsing, and
    execution. The message names the migration file or the source step and the underlying
    cause. Exposed through the cell facade — the engines catch it by name to map into their own
    error family.

    Use `conventions` for type hints and testing.

"check_local_migrations(folder: Path)":
  location: source.py
  annotations: |
    Pre-parse checks of a declared local migrations folder — the load-time half of source
    validation.

    `folder`: the resolved folder path — the caller resolves the declared location against the
    current working directory.

    Algorithm:
    1. The path must exist and be a folder.
    2. The folder must not be empty.
    3. At least one file with the .sql extension must be present — non-.sql files are ignored
    everywhere.
    4. The numeric version prefixes of the .sql filenames must be unique.

    Requirements:
    - Shape checks only — no parsing, no execution; content parsing belongs to
    `parse_migration_file` at apply time.
    - Every failure raises `MigrationError` naming the folder and the failed check.

    Constraints:
    - Do not read file contents here.

    Use `goose-sql` for the file-naming and version-prefix grammar.
    Use `conventions` for type hints and testing.

"check_git_url(url: str)":
  location: source.py
  annotations: |
    Git URL shape validation of a declared remote migrations source — the same rules as
    endpoint pull.

    `url`: the clone URL as declared.

    Algorithm:
    1. The URL scheme must be one of https, http, git, ssh.
    2. The URL must not embed credentials.
    3. A violation raises `MigrationError` naming the URL and the rule.

    Requirements:
    - Shape only — no network access, no clone; resolution belongs to `run_migrations` at
    apply time.

    Use `gitpython` for the URL rules and the ambient-credentials convention.
    Use `conventions` for type hints and testing.

"parse_migration_file(filename: str, text: str) -> migration: MigrationFile":
  location: goose.py
  annotations: |
    Parse one goose-format migration file into its apply-ready form — pure text processing.

    `filename`: the source file name — carried into the result and every error message.
    `text`: the file content.
    `migration`: the parsed migration.

    Algorithm:
    1. Extract the numeric version prefix from `filename`; a filename without a valid prefix
    raises naming the file.
    2. Split the content into the Up and Down sections on the `-- +goose Up` / `-- +goose Down`
    annotations; a file without an Up section raises naming the file; the Down section is
    skipped — parsed only far enough to be excluded.
    3. Split the Up section into statement bodies: inside `-- +goose StatementBegin` /
    `-- +goose StatementEnd` the text is one statement — interior semicolons do not split it;
    outside such bodies, statements split on the terminating semicolon. A `StatementBegin`
    without a matching `StatementEnd` raises naming the file.
    4. Record `-- +goose NO TRANSACTION` when declared before the Up section.
    5. Any `+goose` annotation outside the supported subset and any `{{...}}` interpolation
    raise naming the file — never a silent misapply.
    6. Return the parsed migration.

    Requirements:
    - Pure function — no I/O; the caller reads the file.
    - Every failure raises `MigrationError` naming the file.

    Constraints:
    - Do not execute or validate SQL semantics here — statement bodies are opaque text.

    Use `goose-sql` for the supported annotation subset and the statement-body grammar.
    Use `conventions` for type hints and testing.

"load_migration_set(folder: Path) -> migrations: list[MigrationFile]":
  location: goose.py
  annotations: |
    Load a migrations folder into the ordered apply-ready set.

    `folder`: the source folder — a local folder or a path inside a resolved clone.
    `migrations`: the parsed migrations in ascending version order.

    Algorithm:
    1. List the .sql files of the folder — non-.sql files are ignored.
    2. Reject the set when no .sql files are present, and when two files share a numeric
    version prefix — both failures raise naming the folder and the files.
    3. Parse every file through `parse_migration_file`.
    4. Order the set by ascending numeric version and return it.

    Requirements:
    - Deterministic order — the apply order is exactly the returned order.

    Use `goose-sql` for the naming grammar.
    Use `conventions` for type hints and testing.

"apply_migrations(conn: Connection, migrations: list[MigrationFile])":
  location: apply.py
  annotations: |
    Execute a parsed migration set once over the postgres connection.

    `conn`: the per-session postgres connection.
    `migrations`: the ordered set from `load_migration_set`.

    Algorithm:
    1. Apply every migration in the given order — the caller's order is preserved.
    2. Default: one transaction per file — all statements of the file commit or roll back
    together.
    3. A file declared NO TRANSACTION runs statement-by-statement in autocommit — DDL such as
    CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
    4. Report every applied file as one progress line in the sandbox startup-output style.
    5. The first failed statement raises `MigrationError` naming the migration file and the
    server-side error; the apply stops — no further file runs.

    Requirements:
    - Statement bodies execute as given — parameter-free, no interpolation, no symbol capture.
    - Nothing is recorded into any baseline journal — the schema is session-static.

    Constraints:
    - Do not create or read any version-tracking table.
    - Do not execute Down sections — they are not part of the parsed set.

    Use `psycopg` for the execution patterns — transaction per file and the autocommit opt-out.
    Use `conventions` for structured logging and testing.

"run_migrations(conn: Connection, location: str, git_url: str | None, git_ref: str | None)":
  location: apply.py
  annotations: |
    Orchestrate one migration apply for a service: resolve the source, load the set, apply.

    `conn`: the per-session postgres connection.
    `location`: the declared location — a path relative to the current working directory for a
    local source, or a path inside the repository for a remote source.
    `git_url`: the clone URL of the remote source; None means the source is local.
    `git_ref`: the branch or tag to clone; None clones the remote default branch.

    Algorithm:
    1. Local source — `git_url` None: resolve `location` against the current working directory.
    2. Remote source: shallow-clone `git_url` at `git_ref` into a temporary folder — an
    already-existing target folder is removed before cloning, the download never merges into
    existing content; ambient credentials only — nothing is embedded in the URL; nothing is
    copied into the consumer repository.
    3. Resolve `location` inside the clone — a missing folder raises `MigrationError` naming
    the path.
    4. Load the set through `load_migration_set` and apply it through `apply_migrations` on
    `conn`.
    5. Delete the clone on every exit path — applied or failed.

    Requirements:
    - One apply per call — the engine calls it exactly once per session at startup.
    - Every failure surfaces as `MigrationError` with the failed step named.

    Constraints:
    - Do not cache clones across sessions — each apply downloads fresh.

    Use `gitpython` for the shallow-clone context-manager pattern and the error mapping
    conventions.
    Use `goose-sql` for the set-consumption semantics.
    Use `psycopg` for the execution plane.

---

Author: Goga
CreatedAt: 08/10/26
Description: |
  Migrations of the sandbox — source resolution (a local folder or a remote git repository),
  goose-SQL parsing of the up-only subset, and the once-per-session apply over the postgres
  connection.
```

Package facade `__init__.py` exports through `__all__`: `MigrationFile`, `MigrationError`,
`check_local_migrations`, `check_git_url`, `parse_migration_file`, `load_migration_set`,
`apply_migrations`, `run_migrations`.

#### .usages file — `goga_tool_pybuggy/sandbox/migrations/.usages/migration-set.md` (CREATE)

```md
# Migration set — validating sources and applying once per session

## Domain

The migrations facade of the sandbox: how the sandbox runtime consumes a declared migration
source — fail-fast source checks at document load, and the once-per-session apply at engine
startup. Target audience: the sandbox cells that embed migrations (the configuration reader
and the postgres engine) and maintainers extending the migration flow. Test authors do not
call this facade — they declare `migrations` on a postgresql service entry of the sandbox
document.

## Validating a declared source at document load

The document reader validates every declared migrations entry before any container starts —
local folders are checked on disk, remote URLs are checked by shape only (the clone happens
later, at apply):

```python
from pathlib import Path

from goga_tool_pybuggy.sandbox.migrations import check_git_url, check_local_migrations

# local source: the declared location resolved against the current working directory
check_local_migrations(folder=Path("db/migrations"))
# raises when the folder is missing, empty, holds no .sql files,
# or two files share a numeric version prefix

# remote source: URL shape only — scheme allowlist https/http/git/ssh, no embedded credentials
check_git_url(url="https://gitlab.example/acme/service.git")
```

- Both routines are raise-only: they return nothing and raise `MigrationError` with the
  offending path or URL named — catch it to wrap into the reader's own failure family.
- The version grammar is the leading numeric prefix before the first underscore
  (`00003_create_orders.sql`, `20230102103456_init.sql`) — duplicates are rejected here,
  before any container starts.

## Running one apply at engine startup

The postgres engine applies the declared set exactly once per session, after the container is
ready and before startup data — over the engine's own per-session connection:

```python
from goga_tool_pybuggy.sandbox.migrations import run_migrations

# local source
run_migrations(conn=conn, location="db/migrations", git_url=None, git_ref=None)

# remote source: shallow clone of the repository folder, deleted after the apply
run_migrations(
    conn=conn,
    location="db/migrations",
    git_url="https://gitlab.example/acme/service.git",
    git_ref="release-branch",  # None clones the remote default branch
)
```

- One call per session: resolves the source (a local folder as-is; a remote repository
  through a shallow clone — an already-existing clone target is removed first, the download
  never merges), loads and orders the set, applies it, and deletes the clone on every exit
  path.
- `location` resolves against the current working directory for local sources; for remote
  sources it is the path inside the repository.
- `git_ref` is a branch or tag name; a bare commit SHA is not guaranteed to resolve under a
  shallow clone.
- Credentials come from the environment (ssh-agent, credential helper, gitconfig) — never
  embed tokens in the URL.

## Reading failures

Every failure surfaces as `MigrationError` with the migration file or source step named and
the underlying cause attached — wrap it into the caller's own failure family:

```python
from goga_tool_pybuggy.sandbox.migrations import MigrationError, run_migrations

try:
    run_migrations(conn=conn, location="db/migrations", git_url=None, git_ref=None)
except MigrationError as exc:
    # the message names the file and the server-side error, e.g.
    # "00003_create_orders.sql: relation 'orders' already exists"
    raise RuntimeError(f"service db: migrations failed: {exc}") from exc
```

- Map the failure into the caller's error family naming the service and the step; the
  migration file name and the server message survive the mapping.
- A failed apply stops at the first failing file — default files roll back fully (one
  transaction per file); files declared `-- +goose NO TRANSACTION` run statement-by-statement,
  and already-applied statements stay applied.

## Preconditions and side effects

- The connection is the caller's per-session postgres connection in autocommit mode; the
  applier opens one transaction per file unless the file opts out.
- The apply reports one progress line per applied migration, in the sandbox startup-output
  style.
- Nothing enters the baseline journal: the migrated schema is session-static, per-test resets
  keep it, and only seed data replays.
- No version-tracking table is created or read; Down sections never execute.
```

### Cell 2 — `goga_tool_pybuggy/sandbox/config` (MODIFY)

#### CODEMANIFEST — `goga_tool_pybuggy/sandbox/config/CODEMANIFEST` (diff)

**Add** to the header, before `Usages:`:

```yaml
Imports:
  - Types:
      - check_local_migrations
      - check_git_url
    Usages:
      - migration-set
    From: goga_tool_pybuggy/sandbox/migrations
```

`Usages` and global `Annotations` — unchanged.

**Add** two new type declarations (new module `migrations.py`):

```yaml
"GitSource(url: str, ref: str | None = None)":
  location: migrations.py
  annotations: |
    The optional remote source of a service's migrations.

    `url`: the clone URL of the repository holding the migration folder — no embedded
    credentials; access relies on ambient git credentials.
    `ref`: the branch or tag to clone; None clones the remote default branch.

    Requirements:
    - pydantic model, kw_only.

    Constraints:
    - A bare commit SHA is not a valid ref — shallow clones resolve branch and tag names only.

    Use `conventions` for the data-model rules.
  properties:
    "url -> str": |
      The clone URL — no embedded credentials.
    "ref -> str | None": |
      The branch or tag to clone; None — the remote default branch.

"MigrationsConfig(location: str, git: GitSource | None = None)":
  location: migrations.py
  annotations: |
    The migrations declaration of one postgresql service — the schema source applied once per
    session by the sandbox.

    `location`: the migrations folder — a path relative to the current working directory (the
    same anchor the document itself uses) when `git` is absent; a path inside the repository
    when `git` is set.
    `git`: the optional remote source; None keeps the source local.

    Requirements:
    - pydantic model, kw_only.
    - Valid only on a postgresql service entry — placement is checked at document load.

    Constraints:
    - Do not accept version-tracking or journaling options here — the apply semantics are
    fixed.

    Use `conventions` for the data-model rules.
  properties:
    "location -> str": |
      The migrations folder — cwd-relative, or a path inside the repository when `git` is set.
    "git -> GitSource | None": |
      The optional remote source; None — the source is local.
```

**Change** `ServiceConfig` — signature gains the parameter, annotations gain the parameter
description, properties gain one entry:

```yaml
"ServiceConfig(name: str, kind: str, image: str | None, topics: list[TopicConfig], probe: ProbeConfig | None, migrations: MigrationsConfig | None)":
```

- annotations: append after the `probe` parameter description:

  ```
  `migrations`: the optional migrations declaration — accepted on the postgresql kind only;
  a declaration on any other kind fails at document load with the entry named.
  ```

- properties: append:

  ```yaml
    "migrations -> MigrationsConfig | None": |
      The migrations declaration; None — no migrations.
  ```

**Change** `load_sandbox_config` — annotations only (signature unchanged):

- Algorithm step 5: append after "the probe carries no path.":

  ```
  A migrations declaration is accepted on the postgresql kind only — any other kind fails
  naming the entry; a declared local source resolves its location against the current working
  directory and passes through `check_local_migrations` from Imports; a declared remote source
  passes its URL through `check_git_url` from Imports.
  ```

- Requirements: append:

  ```
  - A migrations declaration is validated fully at load for local sources (folder checks)
  and by URL shape for remote sources — remote content resolves at engine startup.
  ```

- Practice bindings: append `Use `migration-set` from Imports for the load-time check semantics.`
  next to the existing `ruamel-yaml` / `conventions` lines.

SandboxConfig, InstanceConfig, StartupData, ProbeConfig, TopicConfig, and the footer — unchanged.

#### .usages file — `goga_tool_pybuggy/sandbox/config/.usages/sandbox-file.md` (MODIFY, full replacement content)

```md
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
service, missing local path, empty folder, no `.sql` files, duplicate version prefixes, a git
URL outside the scheme allowlist (https/http/git/ssh) or with embedded credentials.

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
  root token `sandbox-root` (send it as `VAULT_TOKEN` / `X-Vault-Token`; secrets live on the
  default KV v2 `secret/` mount).

## Startup data layer

Applied in a fixed order after all services are up and before the instance starts:

| section | target | declarations |
|---|---|---|
| `vault` | vault services | `{path, data}` secret writes |
| `http` | http services | WireMock mapping objects (`request` + `response`) |
| `postgres` | postgresql services | SQL statements (seed data) |

- A `kafka` section does not exist — declaring one fails; the kafka topology lives on the
  service entry.
- Within a section, declarations apply in the order written — for dependent rows (foreign keys),
  declare parents before children. Postgres init statements are raw sql: they resolve no
  `$ref` / `$lookup` references and their rows are addressable later only through `$lookup`.
- Postgres statements run after the service's migrations (when declared), against the migrated
  schema, and replay on every per-test reset — write them idempotent; the TRUNCATE-based reset
  keeps tables (and the migrated schema), only data is wiped.

## Locating the document

- The file name and location are fixed: `.goga/tools/pybuggy/sandbox.yml`, resolved from the
  current working directory only — resolution never searches elsewhere.
- If the sandbox does not activate, verify the document sits at exactly this path and that the
  run starts from the repository root.

## Preconditions and constraints

- An invalid document (unknown kind, unknown service reference, missing or unknown entry key,
  malformed placeholder or declaration, kafka entry without topics, topics on a non-kafka
  entry, migrations on a non-postgresql entry, invalid migrations declaration — missing or
  empty folder, no `.sql` files, duplicate version prefixes, git URL outside the allowlist or
  with embedded credentials — probe `path` on a service or without its leading slash,
  unparsable YAML) fails the run before any container starts, with an error naming the entry.
- Without the document the product is fully inert — nothing starts, nothing changes.
- A container runtime must be available in the environment running the tests.
```

### Cell 3 — `goga_tool_pybuggy/sandbox/engines` (MODIFY)

#### CODEMANIFEST — `goga_tool_pybuggy/sandbox/engines/CODEMANIFEST` (diff)

**Add** to the header `Imports`, after the existing `ServiceConfig` entry:

```yaml
  - Types:
      - run_migrations
      - MigrationError
    Usages:
      - migration-set
    From: goga_tool_pybuggy/sandbox/migrations
```

`Usages`, global `Annotations`, and all other types — unchanged.

**Change** `BaseEngine::PostgresEngine` annotations (full replacement of the annotations block;
signature, location, mutation unchanged):

```yaml
  annotations: |
    postgresql kind — a real postgres service.

    Container: the postgres module container with the product-pinned default image; module
    readiness wrapped in the declared deadline — start returns after the server accepts
    connections within the declared timeout at the declared interval.
    Migrations: when the service declaration carries a migrations entry, the declared migration
    set applies exactly once per session — after the container reaches readiness and the
    data-plane connection opens, before the startup data operations. The apply runs through
    `run_migrations` from Imports over the engine's session connection, with the declared
    location and git source; each applied file is reported as one progress line in the existing
    startup-output style. A failed migration stops start — the failure surfaces as this
    engine's error type naming the service and the migration file, with `MigrationError`
    from Imports as the cause. Applied migrations never enter the baseline journal: the migrated schema
    survives the wipe, and only journaled data replays on reset.
    Data plane: SQL over the postgres driver — a table + rows insert resolves $ref / $lookup
    values, then applies the rows one by one inside one transaction with RETURNING; every
    applied row joins the engine's per-table symbol stream — the address space $ref resolves
    against (the stream covers the data plane's own applied rows since the last wipe: journal,
    presets, in-test declarations, in application order; a later row may reference an earlier
    row of the same insert). A $lookup resolves through one parameterized match query against
    the current database state — exactly one match required, the column defaults to the table's
    primary key discovered from the catalog. Startup raw sql statements execute as given,
    opaque — no resolution, no symbol capture.
    Wipe: clear the symbol stream, discover the user tables from the catalog at reset time,
    then truncate them all with identity restart and cascade — the cascade carries the
    foreign-key ordering; the container is never restarted. The journal replay rebuilds the
    symbol stream and re-resolves the journaled references.

    Requirements:
    - One connection for the session in autocommit mode, closed on stop.
    - Catalog discovery runs at every reset — the table set may change mid-session.
    - One transaction per insert — a failing row leaves nothing applied, and the symbol stream
    rolls back with it.
    - Resolution never rewrites the declared payload.
    - When migrations are declared, start returns only after the set is applied — startup data
    statements run against the migrated schema.

    Constraints:
    - Do not format SQL with interpolated values — parameters are bound server-side.

    Use `migration-set` from Imports for the apply semantics of the migration step.
    Use `psycopg` for the data plane and the catalog-driven reset.
    Use `testcontainers` for the postgres module container.
```

**Change** `BaseEngine` — annotations only (signature, location unchanged): the `config` parameter
description enumerates the service declaration fields; append the new one, so the enumeration ends
with `readiness declaration, migrations declaration (consumed by the postgres kind)`.

**Change** `build_engine` — annotations only (signature unchanged): extend the requirement bullet to
"The image override, the topic declarations, the readiness declaration, and the migrations
declaration of `config` reach the built engine."

No `.usages/` files for this cell.

## Dependency Map

```
goga_tool_pybuggy/sandbox/migrations  [CREATE, leaf]
  ├──(Imports: check_local_migrations, check_git_url + usage migration-set)──▶ goga_tool_pybuggy/sandbox/config  [MODIFY]
  └──(Imports: run_migrations, MigrationError + usage migration-set)─────────▶ goga_tool_pybuggy/sandbox/engines  [MODIFY]
goga_tool_pybuggy/sandbox/config  ──(Imports: ServiceConfig — existing)────▶ goga_tool_pybuggy/sandbox/engines

Unchanged: sandbox/, sandbox/data/, plugin/, commands/, root composition.
```

## Verification Checklist

After implementing each artifact, verify:

- **Cell `sandbox/migrations`**
  - `goga lint` passes on the new CODEMANIFEST; the facade `__init__.py` exposes exactly the
    eight contract names through `__all__`.
  - Parser: Up/Down split, StatementBegin/End bodies with interior semicolons, NO TRANSACTION
    flag, version-prefix extraction, unclosed StatementBegin rejection, unknown-annotation and
    `{{...}}` rejection — each failure names the file.
  - Checks: missing/empty folder, no `.sql`, duplicate versions — raise-only, folder named.
  - Apply: once per session, ascending order, transaction-per-file default, autocommit
    statement-by-statement for NO TRANSACTION, per-file progress line, first failure stops the
    apply with the file and the server error; no journal writes, no version table.
  - Remote: shallow clone (branch/tag or default), existing target folder removed before the
    download, clone deleted on every exit path, nothing copied into the consumer repository,
    ambient credentials only.
  - Tests per `conventions` (unit tests for every public routine; `Repo.clone_from` mocked at
    the import site; `tmp_path` for file checks; no real network in tests).
- **Cell `sandbox/config`**
  - `goga lint` passes; the new Imports resolve to the migrations cell.
  - Declaration: `migrations` accepted on postgresql entries only; load failures name the
    document location and the entry, before any container starts.
  - Local sources: location resolved against cwd, then folder checks; remote sources: URL
    shape only at load.
  - `sandbox-file.md` renders the new section consistently with the document behavior.
- **Cell `sandbox/engines`**
  - `goga lint` passes; PostgresEngine applies migrations between readiness/connection and
    startup data; startup data runs against the migrated schema; failures map into the engine
    error family naming the service and the file; reset keeps the schema and replays only
    journaled data.
  - `Sandbox.start` sequencing and the sandbox cell stay untouched.
- **Documentation (out of DSL plan)**
  - `docs/sandbox.md` and `docs/configuration.md` document the declaration, the ordering, and
    the schema-vs-seed role split.
- **Project validation**
  - `pytest tests/ -x` and `ruff check goga_tool_pybuggy/` pass in a virtualenv.
