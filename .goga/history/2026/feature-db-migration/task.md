# Sandbox DB migrations — goose-format SQL applied once per session by a built-in runner

## Current State

The sandbox supports four dependency kinds (postgresql, kafka, vault, http). A postgres schema
today is created through `data.postgres` — raw idempotent SQL statements replayed from the
baseline journal after every per-test reset (`CREATE TABLE IF NOT EXISTS` style). There is no
migrations support at all: no parser for goose-format SQL, no way to point the sandbox at a
folder of migration files, and no way to reference a remote git source for sandbox assets.

The shallow-clone pattern for remote git sources already exists for `pybuggy endpoint pull`
(`GitEntry` in `goga_tool_pybuggy/config`, the `gitpython` cook) and is the declared precedent
for the migrations link shape.

Decision record: `.goga/history/2026/feature-db-migration/adr.md` (accepted 2026-10-08). It
supersedes the "DB migrations via goose — rejected" point of the feature-upd-sandbox ADR —
the need returned deliberately: real migration sets already live as goose-generated files, and
duplicating them as raw SQL under `data.postgres` is not viable.

## Description

The sandbox document gains SQL migrations for `postgresql`-kind services. The service entry
points to a folder of goose-format migration files — local, or remote via git (GitLab) — and
the files are applied to the database once per test session at startup by a small built-in
up-only applier over the sandbox's existing psycopg plane (not the goose binary).

Illustrative declaration shape (exact YAML field names are a design-stage decision, per the
ADR):

```yaml
# .goga/tools/pybuggy/sandbox.yml
services:
  db:
    kind: postgresql
    migrations:                    # schema — applied once per session, never journaled
      location: db/migrations      # local folder (cwd-relative), or a path inside the repo
      git:                         # optional — omit for a local source
        url: https://gitlab.example/acme/service.git
        ref: release-branch        # optional — branch or tag; omit for the default branch

data:
  postgres:                       # seed — replayed from the baseline after every reset
    db:
      - "INSERT INTO customers (email) VALUES ('ann@x.io')"   # illustrative; $ref/$lookup not shown
```

Role separation: migrations build the schema once per session; `data.postgres` keeps its role
as per-test baseline seed data. Order within engine startup: container ready → migrations →
`data.postgres` startup ops journaled as baseline.

## Scope

**In scope:**
- `sandbox/config` — the migrations declaration on postgresql service entries (link shape:
  `location` + optional `git: {url, ref}` per the `GitEntry` precedent); fail-fast validation
  at document load, before any container starts.
- Migration source resolution — a local folder (relative `location` resolved against cwd, the
  same anchor the document itself uses) or a shallow clone from a remote git repository with
  ambient credentials (ssh-agent / credential helper / gitconfig; no tokens in URLs).
- A goose-SQL parser for the up-only annotation subset: numeric version prefixes, Up/Down
  section split, StatementBegin/End statement bodies, NO TRANSACTION; non-`.sql` files ignored.
- A built-in applier over the existing per-session psycopg connection: once per session,
  version order, per-file visible progress in the existing startup-output style, fail-fast
  with the file and the postgres error named; Down sections never execute; no
  version-tracking table; nothing enters the baseline journal.
- Documentation: `docs/sandbox.md`, `docs/configuration.md`, and the `sandbox-file` usage of
  the sandbox config cell.
- Tests per `.goga/usages/conventions.md`.

**Out of scope:**
- The goose binary (no pip package, no official image — rejected in the ADR).
- Go-based migrations; SQL only.
- Down/rollback, status, repair; any beyond-up functionality.
- A goose-compatible version table (`goose_db_version`).
- Explicit token authentication for private repos (deferred unless CI demands it).
- Database kinds other than postgresql (the only DB kind the sandbox has).

## Acceptance Criteria

- A postgresql service entry accepts the migrations declaration; declaring migrations on a
  non-postgresql service fails at document load, before any container starts, with an
  actionable error naming the entry.
- Load-time validation fails fast with actionable errors for: local path missing, folder
  empty, no `.sql` files, duplicate numeric version prefixes; git URL validation as in pull
  (scheme allowlist https/http/git/ssh, no credentials embedded in the URL).
- Remote sources resolve through a shallow clone (branch/tag ref or default branch) that is
  deleted after the apply; nothing is copied into the consumer repository.
- Migrations apply once per session in ascending version order, after the postgres container
  reaches readiness, before the `data.postgres` startup ops, and before the service under
  test starts; `data.postgres` statements run against the migrated schema; each applied file
  is reported line-by-line in the startup output.
- The first failed migration stops startup with an actionable error naming the file and the
  postgres error; per default, one transaction per file rolls back fully, and
  `-- +goose NO TRANSACTION` files run statement-by-statement.
- `-- +goose Down` sections never execute; no version-tracking table is created.
- Applied migrations do not enter the baseline journal: the per-test reset (TRUNCATE +
  replay) keeps the migrated schema and replays only `data.postgres`.
- Migration files leaning on goose behavior outside the supported subset (unknown
  annotations, `{{...}}` interpolation) fail with the file named.
- `docs/sandbox.md`, `docs/configuration.md`, and the `sandbox-file` usage document the new
  declaration and the schema-vs-seed role split.
- New and existing tests pass under the project validation commands.

## Stack

- **Frameworks:** pytest (plugin surface unchanged), pydantic (kw_only models)
- **Libraries:** ruamel.yaml (document parsing), psycopg 3 (SQL execution plane), GitPython
  (shallow clone), testcontainers (unchanged container lifecycle)
- **Infrastructure:** docker-compatible container runtime; postgres `16-alpine` default image

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| goose SQL format | `.goga/usages/cooks/goose-sql.md` | created |
| psycopg | `.goga/usages/cooks/psycopg.md` | updated (migrations execution section) |
| GitPython | `.goga/usages/cooks/gitpython.md` | updated (second consumer — sandbox migrations) |
| conventions / ruamel-yaml / testcontainers | existing cooks | existing |

Synced usage files are managed by `goga usages sync` — reference them read-only, never create or update them in the task.

## Risks and Constraints

- The parser owns a well-specified annotation subset; malformed input (StatementBegin without
  End, a file without an Up section, unknown `+goose` annotations) must fail with the file
  named — never silently misapply.
- Shallow-clone refs are branch/tag names; a bare commit SHA is not guaranteed to resolve
  (documented in the `gitpython` cook).
- `NO TRANSACTION` must be honored: DDL such as `CREATE INDEX CONCURRENTLY` cannot run inside
  a transaction block.
- Remote clones add startup latency; the progress output keeps the apply visible.
- A service that applies its own migrations at startup is handled by the tester simply not
  declaring sandbox migrations — either/or, the author's choice and responsibility.
- Python 3.10+ compatibility; kw_only pydantic models; relative imports inside cells.

## Scope Estimate

Single task, no decomposition. All parts serve one value scenario (sandbox migrations) and are
not independently valuable; the scale is comparable to the previous `feature-upd-sandbox`
topic.

## Existing Architecture

- `goga_tool_pybuggy/sandbox/config` — `ServiceConfig` gains the migrations declaration;
  `load_sandbox_config` validation extends with the fail-fast checks.
- `goga_tool_pybuggy/sandbox/engines` — `PostgresEngine` applies the migration set between
  container readiness and startup data; parsing and source-resolution modules land here or in
  a new cell (`goga_tool_pybuggy/sandbox/migrations`) — the cell layout is a design-stage
  decision, deliberately left open by the ADR.
- `goga_tool_pybuggy/sandbox` — `Sandbox.start` sequencing is unchanged (the migrations step
  is engine-internal); the startup progress output gains per-file lines.
- `docs/sandbox.md`, `docs/configuration.md`, `sandbox/config/.usages/sandbox-file.md` —
  author-facing documentation.

## Notes

- Decisions were settled in the discover stage and recorded in the ADR; this task converts
  them into scope. Exact YAML field names, Python signatures, and cell changes remain
  design-stage concerns.
- The three usage-file actions of this stage are already done: `goose-sql.md` created,
  `gitpython.md` and `psycopg.md` extended — the task consumes them as-is.
