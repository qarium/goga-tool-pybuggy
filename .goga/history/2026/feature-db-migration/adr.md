# Sandbox DB migrations: goose-format SQL applied once per session by a built-in runner

Status: accepted (2026-10-08)

The sandbox document gains SQL migrations for `postgresql`-kind services: the service entry
points to a folder of migration files — local, or remote via git (GitLab) — and the files are
applied to the database once per test session at startup. The runner is a small built-in
up-only applier over the sandbox's existing psycopg plane, not the goose binary. This record
supersedes the "DB migrations via goose — rejected" point of
`.goga/history/2026/feature-upd-sandbox/adr.md` (same day): the need returned deliberately —
real migration sets already live as goose-generated files, and duplicating them as raw SQL
under `data.postgres` is not viable.

## Settled decisions

- **Source format — goose SQL.** Files as goose produces them: numeric version prefixes
  (`00003_create_orders.sql`), `-- +goose Up` / `-- +goose Down` section annotations,
  `-- +goose StatementBegin/StatementEnd` around statement bodies (functions), and
  `-- +goose NO TRANSACTION`. SQL only — Go-based migrations are out of scope.
- **Mechanism — built-in minimal applier.** A custom runner parses the up-only subset of the
  goose annotations and executes over the existing per-session psycopg connection. Only
  "apply a set of migrations" is needed; no status, rollback, or repair.
- **Apply semantics.** Once per session, after the postgres container is ready and before the
  service under test starts (the service may need the schema to boot). First failed migration
  stops startup with an actionable error naming the file and the postgres error. `Down`
  sections never execute. Applied migrations are not journaled into the baseline.
- **Placement.** On the postgresql service entry inside `services:` — schema is a property of
  the DB service, the same way topics are a property of the kafka service. A `migrations`
  declaration on a non-postgresql service fails fast at config validation, before any
  container starts.
- **Link shape — the `GitEntry` precedent from `pybuggy pull`.** A `location` for a local
  folder; for a remote source, a `location` path inside the repository plus
  `git: {url, ref}` with `ref` optional. One declaration shape covers both cases. Relative
  `location` paths resolve against cwd — the same anchor the document itself uses (cwd-only,
  no upward search).
- **Role separation from `data.postgres`.** Migrations build the schema once per session;
  `data.postgres` keeps its role as per-test baseline seed data (idempotent SQL, replayed
  after every reset). Order within engine startup: container ready → migrations →
  `data.postgres` startup ops journaled as baseline.
- **Remote auth — ambient git credentials.** The same shallow-clone path and URL validation
  as `pybuggy pull` (scheme allowlist https/http/git/ssh, no credentials embedded in the
  URL); ssh-agent / credential helper / gitconfig provide access. No new token mechanism in
  v1.
- **No version-tracking table.** Migrations apply to a fresh empty database once per session;
  nothing reads a version table afterwards. A service that applies its own migrations at
  startup is handled by the tester simply not declaring sandbox migrations (either/or, the
  author's choice and responsibility).
- **Per-service, postgres-only.** Several postgresql services each declare their own
  migrations folder. v1 scope is the postgresql kind — the only DB kind the sandbox has.
- **Validation before containers.** At config load, fail-fast with actionable errors: local
  path missing, folder empty, no `.sql` files, duplicate version prefixes, `migrations` on a
  non-postgresql service; git URL validation as in pull. Non-`.sql` files are ignored.
- **Visible progress.** Each applied migration is reported line-by-line in the existing
  startup-output style.

## Considered options

- **The goose binary** (installed into an image or on the host): rejected. goose is a Go
  tool — no pip package and no official docker image (community images only); shipping it
  means a self-built derived postgres image, trusting a third-party image, or a host binary
  dependency for every consumer of the pytest plugin. The applier needs none of goose's
  beyond-up functionality.
- **Placement under `data.postgres`** (e.g. a `data.postgres.db` key): rejected.
  `data.postgres` is a service-name → SQL-statements map replayed from the baseline journal
  after every per-test reset; re-executing `CREATE TABLE` after `TRUNCATE` is not a no-op,
  and a path/git object does not fit the strings-only shape.
- **A goose-compatible version table** (`goose_db_version`): rejected as unnecessary — see
  the no-version-table decision above.
- **Explicit token auth for private GitLab repos**: deferred — ambient credentials cover the
  current setups; add an explicit token option only if CI demands it.

## Consequences

- The built-in runner owns a well-specified annotation subset (Up/Down split,
  StatementBegin/End, NO TRANSACTION). Migration files that lean on goose behavior outside
  that subset are unsupported and fail with the file named.
- `docs/sandbox.md`, `docs/configuration.md`, and the capability usage files document the new
  declaration and the schema-vs-seed role split.
- Exact YAML field names, Python signatures, and cell changes are design-stage concerns
  outside this record.
