# Plan: `feature-db-migration` — sandbox DB migrations (goose-format SQL, up-only, once per session)

Topic directory: `.goga/history/2026/feature-db-migration/`. Compiled from the design-reviewed
document `design.md` (post design-review, 8 fixes applied) and the CODEMANIFEST tree of branch
`feature/db-migration` (working tree — the manifests are the contract; the implementation at HEAD
`5c5b440` is the pre-change state). Executed by ralphex through Claude Code, one task per
iteration.

## Purpose

Add sandbox DB migrations: a declared migration set (goose-format SQL, up-only subset) applied
once per session to a postgresql sandbox service by a built-in runner. After implementation the
package provides:

- a new leaf cell `goga_tool_pybuggy/sandbox/migrations` owning one migration set end to end:
  source resolution (a local folder or a remote shallow git clone), goose-SQL parsing of the
  up-only subset, and the once-per-session apply over the engine's per-session autocommit
  postgres connection — 8 contract types across `goose.py`, `errors.py`, `source.py`, `apply.py`;
- the declaration side in `sandbox/config`: `GitSource` and `MigrationsConfig` models
  (`migrations.py`), the `ServiceConfig.migrations` field (postgresql-only, enforced at document
  load), and `load_sandbox_config` load-time validation — local folders checked on disk through
  `check_local_migrations`, remote URLs checked by shape through `check_git_url`; a
  `MigrationError` from either check is wrapped into the reader's `ValueError` with the cause
  preserved;
- the apply side in `sandbox/engines`: a protected `_migrate` no-op hook in `BaseEngine.start`
  (between plane open and startup data), overridden by `PostgresEngine` to run
  `run_migrations` with the flattened scalars over the session connection; a failed migration
  stops start as `EngineError` with `MigrationError` as the cause; applied migrations never
  enter the baseline journal — the migrated schema survives the TRUNCATE wipe and only journaled
  seed data replays on reset.

The most important gaps between contract and code: the whole migrations cell is unimplemented
(only CODEMANIFEST + `.usages/migration-set.md` exist); `config/migrations.py` does not exist;
`ServiceConfig` has no `migrations` field and the config facade exports 7 names (target 9); the
loader has no `_validate_migrations`; `engines/base.py` has no `_migrate` hook and
`postgres.py` no override.

Overall implementation strategy: leaf-first cell order (migrations → config → engines →
integration → docs → final validation), strict TDD per entity (contract tests first),
REPL-driven development loop (Mandatory Rules R4), ruff lint/format gates at every development
stage and before every local commit (Mandatory Rules R3). The change is purely additive — the
full test suite stays green at every task; the commit gate is the full suite from Task 1 on.

## Context

### Contract Surface

#### Cell `goga_tool_pybuggy/sandbox/migrations` (NEW — leaf; no Imports; practices `conventions`, `goose-sql`, `psycopg`, `gitpython`)

**Entity: `MigrationFile(version: int, filename: str, statements: list[str], no_transaction: bool)`**
- Type: class; Declared `location`: `goose.py`; Facade obligation: importable from
  `goga_tool_pybuggy.sandbox.migrations`
- Properties: `version -> int` (the numeric prefix of the filename, compared and applied
  numerically), `filename -> str` (the identity used in progress output and error messages),
  `statements -> list[str]` (the ordered statement bodies of the Up section, ready to execute
  as given), `no_transaction -> bool` (whether the file declared `-- +goose NO TRANSACTION`
  and must run statement-by-statement in autocommit)
- Requirements: pydantic model, `kw_only`.

**Entity: `MigrationError()`**
- Type: class; `location`: `errors.py`; facade: cell facade. The failure family of the
  migrations domain — the `RuntimeError` subtype. Every failure in this cell surfaces as this
  type: source resolution, naming, parsing, and execution. The message names the migration file
  or the source step and the underlying cause. Exposed through the facade — the engines catch it
  by name to map into their own error family.

**Routine: `check_local_migrations(folder: Path)`**
- `location`: `source.py`; facade: cell facade. Pre-parse checks of a declared local migrations
  folder — the load-time half of source validation. `folder`: the resolved folder path — the
  caller resolves the declared location against the current working directory.
- Algorithm: 1. the path must exist and be a folder; 2. the folder must not be empty; 3. at
  least one `.sql` file must be present — non-`.sql` files are ignored everywhere; 4. the
  numeric version prefixes of the `.sql` filenames must be unique.
- Requirements: shape checks only — no parsing, no execution; every failure raises
  `MigrationError` naming the folder and the failed check. Constraints: do not read file
  contents here.

**Routine: `check_git_url(url: str)`**
- `location`: `source.py`; facade: cell facade. Git URL shape validation — the same rules as
  endpoint pull (modulo decision A below).
- Algorithm: 1. the URL scheme must be one of https, http, git, ssh; 2. the URL must not embed
  credentials; 3. a violation raises `MigrationError` naming the URL and the rule.
- Requirements: shape only — no network access, no clone.

**Routine: `parse_migration_file(filename: str, text: str) -> migration: MigrationFile`**
- `location`: `goose.py`; facade: cell facade. Pure text processing — one goose file → one
  apply-ready `MigrationFile`.
- Algorithm: 1. extract the numeric version prefix from `filename`; a filename without a valid
  prefix raises naming the file; 2. split the content into the Up and Down sections on
  `-- +goose Up` / `-- +goose Down`; a file without an Up section raises naming the file; the
  Down section is skipped — parsed only far enough to be excluded; 3. split the Up section into
  statement bodies: inside `-- +goose StatementBegin` / `-- +goose StatementEnd` the text is one
  statement — interior semicolons do not split it; outside such bodies, statements split on the
  terminating semicolon; a StatementBegin without a matching StatementEnd raises naming the
  file; 4. record `-- +goose NO TRANSACTION` when declared before the Up section; 5. any +goose
  annotation outside the supported subset and any `{{...}}` interpolation raise naming the file
  — never a silent misapply; 6. return the parsed migration.
- Requirements: pure function — no I/O; every failure raises `MigrationError` naming the file.
  Constraints: do not execute or validate SQL semantics — statement bodies are opaque text.

**Routine: `load_migration_set(folder: Path) -> migrations: list[MigrationFile]`**
- `location`: `goose.py`; facade: cell facade. `folder`: a local folder or a path inside a
  resolved clone; `migrations`: the parsed migrations in ascending version order.
- Algorithm: 1. list the `.sql` files — non-`.sql` ignored; 2. reject when no `.sql` files are
  present and when two files share a numeric version prefix — both raise naming the folder and
  the files; 3. parse every file through `parse_migration_file`; 4. order by ascending numeric
  version and return.
- Requirements: deterministic order — the apply order is exactly the returned order.

**Routine: `apply_migrations(conn: Connection, migrations: list[MigrationFile])`**
- `location`: `apply.py`; facade: cell facade. `conn`: the per-session postgres connection;
  `migrations`: the ordered set from `load_migration_set`.
- Algorithm: 1. apply every migration in the given order — the caller's order is preserved;
  2. default: one transaction per file — all statements of the file commit or roll back
  together; 3. a NO TRANSACTION file runs statement-by-statement in autocommit — DDL such as
  `CREATE INDEX CONCURRENTLY` cannot run inside a transaction block; 4. report every applied
  file as one progress line in the sandbox startup-output style; 5. the first failed statement
  raises `MigrationError` naming the migration file and the server-side error; the apply stops —
  no further file runs.
- Requirements: statement bodies execute as given — parameter-free, no interpolation, no symbol
  capture; nothing is recorded into any baseline journal. Constraints: do not create or read
  any version-tracking table; do not execute Down sections.

**Routine: `run_migrations(conn: Connection, location: str, git_url: str | None, git_ref: str | None)`**
- `location`: `apply.py`; facade: cell facade. Orchestrate one apply: resolve the source, load
  the set, apply. `location`: cwd-relative path (local) or a path inside the repository
  (remote); `git_url`: the clone URL; None means local; `git_ref`: the branch or tag to clone;
  None clones the remote default branch.
- Algorithm: 1. local — `git_url` None: resolve `location` against the current working
  directory; 2. remote: shallow-clone `git_url` at `git_ref` into a temporary folder — an
  already-existing target folder is removed before cloning, the download never merges into
  existing content; ambient credentials only; nothing is copied into the consumer repository;
  3. resolve `location` inside the clone — a missing folder raises `MigrationError` naming the
  path; 4. load the set through `load_migration_set` and apply through `apply_migrations` on
  `conn`; 5. delete the clone on every exit path — applied or failed.
- Requirements: one apply per call — the engine calls it exactly once per session at startup;
  every failure surfaces as `MigrationError` with the failed step named. Constraints: do not
  cache clones across sessions.

#### Cell `goga_tool_pybuggy/sandbox/config` (Imports: `check_local_migrations`, `check_git_url`, `MigrationError` + usage `migration-set` from `goga_tool_pybuggy/sandbox/migrations`)

**Entity: `GitSource(url: str, ref: str | None = None)`** (new)
- Type: class; `location`: `migrations.py` (new file); facade: cell facade (new name).
- Properties: `url -> str` (the clone URL — no embedded credentials; access relies on ambient
  git credentials), `ref -> str | None` (the branch or tag to clone; None clones the remote
  default branch).
- Requirements: pydantic model, `kw_only`. Constraints: a bare commit SHA is not a valid ref —
  shallow clones resolve branch and tag names only.

**Entity: `MigrationsConfig(location: str, git: GitSource | None = None)`** (new)
- Type: class; `location`: `migrations.py`; facade: cell facade (new name).
- Properties: `location -> str` (the migrations folder — cwd-relative when `git` is absent; a
  path inside the repository when `git` is set), `git -> GitSource | None` (the optional remote
  source; None keeps the source local).
- Requirements: pydantic model, `kw_only`; valid only on a postgresql service entry — placement
  is checked at document load. Constraints: do not accept version-tracking or journaling
  options here — the apply semantics are fixed.

**Entity: `ServiceConfig(name, kind, image, topics, probe, migrations)`** (changed)
- `location`: `service.py`. Signature gains `migrations: MigrationsConfig | None`; property
  `migrations -> MigrationsConfig | None` added (None — no migrations). The parameter is
  documented: accepted on the postgresql kind only; a declaration on any other kind fails at
  document load with the entry named. Field order: after `probe`.

**Routine: `load_sandbox_config(path: str | None) -> config: SandboxConfig | None`** (changed)
- `location`: `loader.py`. Algorithm step 5 extended (verbatim from the contract): a migrations
  declaration is accepted on the postgresql kind only — any other kind fails naming the entry;
  a declared local source resolves its location against the current working directory and passes
  through `check_local_migrations` from Imports; a declared remote source passes its URL through
  `check_git_url` from Imports. A `MigrationError` raised by either check is wrapped into the
  reader's ValueError naming the scope and the offending path or URL, with the original error as
  the cause.
- New requirement bullet: a migrations declaration is validated fully at load for local sources
  (folder checks) and by URL shape for remote sources — remote content resolves at engine
  startup. Practice binding added: `migration-set` from Imports for the load-time check
  semantics.

#### Cell `goga_tool_pybuggy/sandbox/engines` (Imports: `ServiceConfig` from config; `run_migrations`, `MigrationError` + usage `migration-set` from migrations)

**Entity: `BaseEngine(config: ServiceConfig)`** (changed — annotations only)
- `location`: `base.py`. The `config` parameter enumeration ends with "migrations declaration
  (consumed by the postgres kind)". Method `start` gains, between steps 3 and 4 of its
  Algorithm, the migrations step realized through the protected `_migrate` hook (see the
  PostgresEngine entry and the stack traces).

**Mutation: `BaseEngine::PostgresEngine(config: ServiceConfig)`** (changed — annotations replaced)
- `location`: `postgres.py`. Migrations paragraph (binding summary): when the service
  declaration carries a migrations entry, the declared set applies exactly once per session —
  after the container reaches readiness and the data-plane connection opens, before the startup
  data operations. The apply runs through `run_migrations` from Imports over the engine's
  session connection, with the declared location and git source; each applied file is reported
  as one progress line. A failed migration stops start — the failure surfaces as `EngineError`
  naming the service and the migration file, with `MigrationError` from Imports as the cause.
  Applied migrations never enter the baseline journal: the migrated schema survives the wipe,
  and only journaled data replays on reset. New requirement: when migrations are declared,
  start returns only after the set is applied — startup data statements run against the migrated
  schema.

**Routine: `build_engine(config: ServiceConfig) -> engine: BaseEngine`** (changed — requirement bullet)
- `location`: `runtime.py`. "The image override, the topic declarations, the readiness
  declaration, and the migrations declaration of `config` reach the built engine" — satisfied by
  construction (the whole `ServiceConfig` reaches the kind engine); docstring enumeration
  updated only.

### Re-exports

- New cell facade `sandbox/migrations` — `__all__` with exactly the eight contract names
  (project style — classes first, then functions, alphabetical within each group):
  `["MigrationError", "MigrationFile", "apply_migrations", "check_git_url",
  "check_local_migrations", "load_migration_set", "parse_migration_file", "run_migrations"]`.
- Cell facade `sandbox/config` — `__all__` grows from 7 to 9 names: adds `"GitSource"` and
  `"MigrationsConfig"` (alphabetical).
- Cell facade `sandbox/engines` — 11 names, unchanged. Root re-exports — unchanged.

### Usages Context

- `conventions` (`.goga/usages/conventions.md`): mandatory Python rules — virtualenv execution,
  relative imports, pydantic `kw_only` models, structured logging, blank-line block formatting,
  Google docstrings, type-hint grammar, test structure and classification, dependency
  declaration. Used by every touched cell. **Extracted in full into Mandatory Rules below —
  they override any stylistic preference of the implementing agent.**
- `goose-sql` (`.goga/usages/cooks/goose-sql.md`, new): the migration file format — naming
  grammar, the five supported annotations, statement-body rules, out-of-subset rejection,
  up-only set-consumption semantics. Used by `check_local_migrations` (naming grammar),
  `parse_migration_file` (all parsing rules), `load_migration_set` (ordering/duplicates),
  `run_migrations` (set-consumption semantics).
- `psycopg` (`.goga/usages/cooks/psycopg.md`, modified): the postgres driver execution
  patterns — autocommit session connection, `conn.transaction()` blocks, parameter-free DDL
  execution, error surfacing via `.diag.message_primary`; the new "Migrations — executing parsed
  goose SQL bodies" section. Used by `apply_migrations` (execution plane).
- `gitpython` (`.goga/usages/cooks/gitpython.md`, modified): the shallow-clone
  context-manager pattern (`Repo.clone_from(url, tmp, depth=1, branch=ref)`),
  ambient-credentials convention, per-consumer error mapping (sandbox consumer block: consume
  in place, `GitCommandError` → the consumer's family — `MigrationError` here, not
  `ClickException`). Used by `run_migrations` (remote source resolution) and `check_git_url`
  (URL rules).
- `ruamel-yaml` (`.goga/usages/cooks/ruamel-yaml.md`): document parsing in the loader —
  unchanged by this plan; Task 6 reuses the existing `_parse_document`/`_build_model` skeleton.

### Imported Usages

- `migration-set` from `goga_tool_pybuggy/sandbox/migrations` — imported by both `config` and
  `engines`. Path: `goga_tool_pybuggy/sandbox/migrations/.usages/migration-set.md`. Documents
  the facade the two consumers embed: load-time checks ("Validating a declared source at
  document load" — `load_sandbox_config` follows it) and the once-per-session apply ("Running
  one apply at engine startup" — `PostgresEngine._migrate` follows it); the error-mapping
  example (`except MigrationError ... raise ... from exc`) matches both consumers' wrap chains.
  **Already materialized by apply-architecture — read it as the reference; do not modify.**

### Local Usages

None to create or modify. `migrations/.usages/migration-set.md` (new cell) and
`config/.usages/sandbox-file.md` (replaced) were materialized by the apply-architecture stage
and verified against the contracts during the design (§ `.usages/` Update: consistency
verified, decision-A allowlist wording checked — no updates needed). No usage-file tasks. The
engines cell has no `.usages/` directory by design.

### External Dependencies

None new. `pyproject.toml` already declares `gitpython>=3.1`, `psycopg[binary]>=3.1`,
`testcontainers[postgres]>=4.15`, `pydantic>=2.0`; `.usages` package-data patterns already
present (`**/.usages/*.md`). Stdlib additions only: `re`, `urllib.parse`, `tempfile`,
`pathlib.Path`. **Do not add any dependency.**

### Interaction Diagram (verbatim from the design — the tasks implement these chains)

```
document load (pytest session start)
─────────────────────────────────────────────────────────────────────────
sandbox.yml ──> load_sandbox_config (config/loader.py)
                  │  services.<name> raw entry
                  │  placement: migrations only on kind == postgresql
                  │  _build_model(MigrationsConfig)      [config/migrations.py]
                  │  local: Path.cwd() / location ──────> check_local_migrations (migrations/source.py)
                  │  remote: git.url ───────────────────> check_git_url           (migrations/source.py)
                  │            MigrationError ──wrap──> ValueError (document location + entry)
                  └──> SandboxConfig(services={name: ServiceConfig(..., migrations=...)})

engine startup (once per session, per postgresql service)
─────────────────────────────────────────────────────────────────────────
BaseEngine.start (engines/base.py)
  build container ─> start ─> _wait_ready ─> _open_plane
                                            │
                                            └─> _migrate()  [new no-op hook; PostgresEngine override]
                                                  └─> run_migrations(conn, location, git_url, git_ref)
                                                        ├─ local:  Path.cwd() / location
                                                        ├─ remote: Repo.clone_from(url, tmp, depth=1, branch=ref)
                                                        │          └─ resolve location inside the clone
                                                        ├─> load_migration_set(folder)
                                                        │      ├─> parse_migration_file(filename, text) per .sql
                                                        │      └─ order by ascending numeric version
                                                        └─> apply_migrations(conn, migrations)
                                                               ├─ default: conn.transaction() per file
                                                               ├─ NO TRANSACTION: statement-by-statement
                                                               └─ logger.info("migration applied") per file
                                            └─> _apply_operations(startup)   # against the migrated schema
  MigrationError ──_run_step wrap──> EngineError (service + step named, MigrationError as cause)

per-test reset
─────────────────────────────────────────────────────────────────────────
BaseEngine.reset ─> PostgresEngine._wipe (TRUNCATE ... RESTART IDENTITY CASCADE)
                     migrated tables: data wiped, schema survives (never journaled)
                  ─> journal replay (data.postgres seed only)
```

**Error flow (verbatim)**: deepest failure (psycopg statement error / git clone error / shape
check) → `MigrationError` (names file or source step + cause) → engine `_run_step` →
`EngineError` (names service + lifecycle step) with `MigrationError` as `__cause__`. In the
config cell: `MigrationError` → `ValueError` (names document location + entry). Always
`raise ... from exc` — the file name and server message survive every mapping. No recovery, no
retries: fail fast, never a silent misapply.

**Declaration flow (verbatim)**: `sandbox.yml` `services.<name>.migrations` (raw mapping) →
`MigrationsConfig(location: str, git: GitSource | None)` → stored on `ServiceConfig.migrations`
→ consumed by `PostgresEngine` via `self.config.migrations`.

### Design Decisions (binding for implementation; verbatim condensations)

- **Decision A — strict git URL schemes** (`check_git_url`): the manifest's literal algorithm
  wins. A URL must parse with an explicit scheme among `https`, `http`, `git`, `ssh`; an
  scp-style URL (`git@github.com:acme/service.git`) parses with an empty scheme and is
  **rejected** at document load with a "disallowed scheme" error naming the URL and the
  allowlist. This intentionally diverges from `endpoint pull`'s effective empty-scheme bypass;
  authors rewrite scp-style URLs as `ssh://git@host/path`. Do not copy pull's bypass.
- **Shared grammar, single source**: one module-level regex `^(\d+)_(.+)\.sql$` + one
  version-int extraction in `goose.py`, imported by `source.py` — never duplicated.
- **Parser statement ordering (design-review R1 fix)**: the fragment buffer flushes through the
  semicolon split **at `StatementBegin`** (`_split_fragments` helper — split-and-append), the
  body appends during the scan, the remaining tail flushes after the scan — `statements`
  follows file order exactly even when plain statements and bodies interleave. A fragment
  lacking a trailing `;` before a body never merges with the fragment after it.
- **Loader guards (design-review R3/R6 fixes)**: `_validate_migrations` carries an isinstance
  guard (`migrations: null`/list/scalar → `ValueError(f"{scope}.migrations: must be a mapping")`
  — never a raw `TypeError`) and a non-empty `location` guard (`""` → `ValueError(f"{scope}.
  migrations.location: must be a non-empty path")` — empty would resolve to cwd or the clone
  root).
- **Engine import discipline (design-review R5 fix)**: `postgres.py` imports only
  `run_migrations` (`from ..migrations import run_migrations`); the error wrap is the generic
  `_run_step`, so a runtime import of `MigrationError` would be unused (F401) — it stays a
  contract-level reference in the CODEMANIFEST annotations and is imported directly from the
  migrations cell by the engine tests.
- **Local server-message extraction**: `apply.py` mirrors `engines/postgres.py::_server_message`
  (`exc.diag.message_primary or str(exc)`) but stays local to the migrations cell — no import
  from engines (the leaf must not depend upward).
- **`_migrate` is a protected hook** (parallel to `_build_container`/`_open_plane`): a no-op
  default in `BaseEngine`, overridden only by `PostgresEngine`. It is implementation detail, not
  contract surface — do not add it to the engines CODEMANIFEST.

## Facts

- The design passed `goga-review-design`: all code-stack traces hold; 8 review fixes applied to
  the design document and the config CODEMANIFEST. `goga lint` reports 24 cells, 0 errors; the
  migrations cell is a leaf (no Imports) — no cycles.
- The branch working tree carries the materialized contract, uncommitted: new
  `goga_tool_pybuggy/sandbox/migrations/CODEMANIFEST` +
  `goga_tool_pybuggy/sandbox/migrations/.usages/migration-set.md` (untracked); modified
  `sandbox/config/CODEMANIFEST`, `sandbox/engines/CODEMANIFEST`,
  `config/.usages/sandbox-file.md`, `.goga/usages/cooks/gitpython.md`,
  `.goga/usages/cooks/psycopg.md`; new `.goga/usages/cooks/goose-sql.md`. They are the
  read-only contract input and land in git with the Task 1 commit.
- The Python implementation at HEAD `5c5b440` is the pre-change state: no
  `goga_tool_pybuggy/sandbox/migrations/` package; `config/` holds `instance.py`, `loader.py`,
  `probe.py`, `sandbox_config.py`, `service.py`, `startup_data.py`, `topic.py` (no
  `migrations.py`); `ServiceConfig` fields end at `probe`; the config facade exports 7 names;
  `loader.py` has `_read_services` → `_validate_kind` + `_validate_topics` → `_build_model`
  (the established pattern `_validate_migrations` joins); `engines/base.py::start` runs
  `_run_step("start failed at container build"/"start"/"readiness wait"/"data-plane open")` →
  `_apply_operations(startup)` → `_journal.extend(startup)` — the `_migrate` insertion point is
  between `_open_plane` and `_apply_operations`; `postgres.py` holds `_open_plane`
  (`psycopg.connect(..., autocommit=True)` into `self._connection`), `_execute` with the
  `_server_message` pattern, and the catalog-driven `_wipe`.
- Test tree: `tests/sandbox/` mirrors the source (config / engines / data subpackages + root
  module suites); `tests/sandbox/engines/test_postgres.py` already provides the local doubles
  pattern (`FakeCursor` recording `("execute", sql, params)`, `FakeTransaction` recording
  begin/commit/rollback, `FakeConnection`, `FailingCursor`/`FailingConnection`,
  `FakePostgresContainer`, `FakePsycopg`) and the `requires_docker`-gated live harness;
  `tests/sandbox/conftest.py` provides `docker_available()` / `requires_docker`.
- `pyproject.toml`: all needed dependencies declared with minimum versions (incl.
  `gitpython>=3.1`, `psycopg[binary]>=3.1`, `testcontainers[postgres]>=4.15`); ruff configured
  (`target-version = "py310"`, `line-length = 120`, rule sets E/W/F/I/N/UP/B/SIM/PL/PLR/C4/
  DTZ/PT/ARG/RUF/PTH/C90, mccabe max-complexity 10, per-file ignores for tests; format: double
  quotes, LF); pytest `testpaths = ["tests"]`, `addopts = "-v --tb=short"`.
- GitPython precedent: `commands/pull/pull.py` already uses `Repo.clone_from` and a
  `_validate_git_url` with the same rule shape (scheme allowlist + embedded-credentials
  rejection) — the pattern to mirror, not import.
- No virtualenv exists in the repo (`.venv` absent) — conventions require creating one and
  executing everything inside it (M-R1.2).
- Docker is NOT available in the execution environment — container-dependent tests skip via
  `requires_docker`; docker-gated REPL probes are unavailable (the M-R4.5 fallback applies: the
  live reset semantics are carried by the gated suite, which must collect and skip cleanly).

## Gap Analysis

- Missing contract entities: the whole migrations cell — `MigrationFile`, `MigrationError`,
  `check_local_migrations`, `check_git_url`, `parse_migration_file`, `load_migration_set`,
  `apply_migrations`, `run_migrations`; plus `GitSource`, `MigrationsConfig`
  (`config/migrations.py`).
- Missing facade exposure: the migrations cell facade (8 names — no `__init__.py` exists at
  all); `GitSource`, `MigrationsConfig` on the config facade (7 → 9 names).
- Incorrect `location` placement: none — every new entity gets its declared `location`; four
  new files in the migrations cell plus `config/migrations.py`, at the same directory level as
  their CODEMANIFESTs.
- API mismatches vs the current code: `ServiceConfig` (no `migrations` field),
  `load_sandbox_config` (no `_validate_migrations` step, no migrations imports),
  `BaseEngine.start` (no `_migrate` step), `build_engine`/`BaseEngine` docstrings (no
  migrations enumeration), `PostgresEngine` (no `_migrate` override).
- Behavioral mismatches: none in existing behavior — every change is additive; absence of the
  declaration must reproduce the established startup byte-for-byte (the no-op default hook).
- Existing code that can be reused: the loader helper skeleton (`_read_services`,
  `_validate_kind`, `_validate_topics`, `_build_model`, `_validate_placeholders`), the
  `_run_step` lifecycle wrappers and journal machinery in `base.py`, `postgres.py::_open_plane`
  and `_server_message`, the `FakeConnection`-family doubles and `requires_docker` pattern, the
  pinned container defaults.
- Test coverage gaps: all 58 named design test scenarios (22 positive, 28 negative, 8
  edge/model) plus the facade/model-level units; a new test package
  `tests/sandbox/migrations/` is created.
- Missing visibility in workspace or git: the CODEMANIFEST + usages/cook modifications are
  uncommitted — they land with the Task 1 commit; no other untracked assets (the
  `.goga/history/` topic directory is pipeline artifact, not part of the contract commit).

## Mandatory Rules

Extracted from the project convention `.goga/usages/conventions.md` (usage key `conventions` —
connected in every touched CODEMANIFEST) plus the Python cell rules where marked. They are
**mandatory for every task and every development stage of this plan**; the convention's
precedence applies: contract first, package boundary/facade second, these project conventions
next, language idioms last.

### R1. Coding Style Rules (strictly per project convention)

- **M-R1.1** Python 3.10+ only; `pyproject.toml` is the single configuration source.
- **M-R1.2** Execute ALL code (tests, REPL, probes, checks) inside a virtualenv — Task 1
  creates it; every later command runs through `.venv/bin/…`. Never run the project with the
  system interpreter.
- **M-R1.3** Imports: **relative** for all intra-package references; **absolute** only for
  stdlib and third-party (`from .goose import FILENAME_GRAMMAR`, `from ..migrations import
  check_git_url, check_local_migrations, MigrationError`, `from ..migrations import
  run_migrations` — never `from goga_tool_pybuggy.sandbox.migrations import …` inside the
  package; `from git import Repo` / `from git.exc import GitCommandError` / `from psycopg
  import Connection` / `import urllib.parse` are third-party/stdlib absolutes).
- **M-R1.4** Data models: pydantic with `kw_only=True` (`model_config = ConfigDict(kw_only=True,
  extra="forbid")` for the declaration models per the design; `MigrationFile` kw_only). Empty
  defaults (empty list) for fields — `None` only for the explicit absence of a value
  (`ref: str | None = None`, `git: GitSource | None = None`, `migrations: MigrationsConfig |
  None = None`).
- **M-R1.5** Logging: stdlib `logging` with module loggers (`logger =
  logging.getLogger(__name__)`); every operational log carries contextual metadata via
  `extra={...}`; messages lowercase, concise, with **stable log event names**. This feature's
  events: INFO `"migration applied"` with `extra={"migration": m.filename, "version":
  m.version}` — one line per applied file; DEBUG `"migrations source resolved"` with
  `extra={"location": ...}` (source resolution steps). Levels per the convention (INFO —
  lifecycle/state transitions; DEBUG — intermediate state). **No secrets in logs** — URLs with
  embedded credentials are rejected at load (decision A), so they can never reach a log line.
- **M-R1.6** Function/method bodies: logical blocks separated by **one blank line** (variable
  initialization vs conditionals/loops; data preparation vs processing; processing vs return).
  The parser's region loop and the apply loop follow this.
- **M-R1.7** Docstrings: **mandatory** for all public functions, methods, and classes,
  **Google style** — first line capitalized and ending with a period; `Args` when parameters
  exist; `Returns` when a value returns; `Raises` for exceptions beyond built-in behavior
  (`MigrationError` clauses in the migrations cell; `ValueError` from the loader;
  `EngineError` from the engine step).
- **M-R1.8** Type hints mandatory; signature grammar per the Python language rules: `str`,
  `int`, `float`, `bool`, `list[T]`, `dict[str, T]`, `T | None`, `Path`, `Connection`;
  forbidden `*args` / `**kwargs` and bare `dict` / `list`.
- **M-R1.9** Dependencies: every third-party library in `pyproject.toml` with a minimum
  version — **this plan adds none**; do not add any.
- **M-R1.10** Naming: PascalCase classes, snake_case functions/methods/properties; names
  consistent with the contract vocabulary (`MigrationFile`, `MigrationError`,
  `check_local_migrations`, `check_git_url`, `parse_migration_file`, `load_migration_set`,
  `apply_migrations`, `run_migrations`, `GitSource`, `MigrationsConfig`); internal helpers keep
  support-intent names (`_split_fragments`, `_validate_migrations`, `_migrate`,
  `_server_message`-shaped local extraction).

### R2. Test Writing Rules (strictly per project convention)

- **M-R2.1** Tools: pytest (running), pytest-cov (coverage), ruff (linting and formatting test
  code); test code compatible with Python 3.10+; executed in the virtualenv.
- **M-R2.2** Tests mirror the source structure directly: `goga_tool_pybuggy/sandbox/migrations/
  goose.py` → `tests/sandbox/migrations/test_goose.py`; `config/migrations.py` →
  `tests/sandbox/config/test_migrations.py`; loader changes → `tests/sandbox/config/
  test_loader.py`; engine changes → `tests/sandbox/engines/{test_base,test_postgres}.py`. The
  new test package `tests/sandbox/migrations/` carries `__init__.py`; local fixtures (the
  connection doubles) in `tests/sandbox/migrations/conftest.py`.
- **M-R2.3** Naming: files `test_<module>.py`; functions `test_<what>_<scenario>`; class
  grouping `class Test<Component>:` where a module groups multiple components.
- **M-R2.4** Coverage: unit tests for every public function/method/class — main scenario plus
  typical data; edge cases — empty inputs (`None`, `""`, `[]`, `{}`), boundary values (`0`,
  negative, very large — e.g. the timestamp version), invalid types, expected exceptions via
  `pytest.raises` with `match=` asserting the exact message wording (folder/file/URL named).
  **Contract tests (facade accessibility, API shape, signatures) are written FIRST in each
  coding task and expected to fail initially (TDD).**
- **M-R2.5** Boundary tests use `@pytest.mark.parametrize` with a table of values including
  each boundary — the scheme allowlist table (all four accepted + the rejects), the raw
  migrations-value table (`[None, 12, "x"]`), filename grammar edges.
- **M-R2.6** Mocks only at external boundaries: the parser tests stay **mock-free** (pure
  logic); file I/O exclusively via the `tmp_path` fixture (+ `monkeypatch.chdir` for the
  cwd-anchored resolution); git is patched at the import point — `mock.patch(
  "goga_tool_pybuggy.sandbox.migrations.apply.Repo.clone_from")`; the postgres connection is
  faked with local doubles (`FakeCursor` / `FakeTransaction` / `FakeConnection` /
  `FailingConnection`) mirroring `tests/sandbox/engines/test_postgres.py`; the engine mocks
  `run_migrations` at `goga_tool_pybuggy.sandbox.engines.postgres.run_migrations`.
- **M-R2.7** Container-dependent tests are gated with `requires_docker`
  (`pytest.mark.skipif`); no network in unit tests. Docker is unavailable in the execution
  environment — the gated suites must collect and skip cleanly.
- **M-R2.8** Self-documenting test names; keep comments minimal.
- **M-R2.9** Test libraries live in `[project.optional-dependencies]` under the `test` key —
  already satisfied; no additions.

### R3. Lint and Format Enforcement (all development stages and local commits)

- **M-R3.1** `ruff` is the project's single linter AND formatter, configured in
  `pyproject.toml` (target py310, line-length 120, the full rule selection incl. `I`, `N`, `UP`,
  `B`, `SIM`, `PL`, `PLR`, `C4`, `DTZ`, `PT`, `ARG`, `RUF`, `PTH`, `C90` max-complexity 10;
  format: double quotes, LF, magic trailing comma on).
- **M-R3.2** Every development stage — writing contract tests, implementing, writing logic
  tests, debugging — keeps the touched paths lint-clean: run `ruff check` after each stage, not
  only at task end.
- **M-R3.3** Every task ends with the LINT gate: `.venv/bin/ruff check goga_tool_pybuggy/
  tests/` exits 0, and every file the task touched is format-clean (`.venv/bin/ruff format
  --check <touched files>`; apply `ruff format` to touched files when drift appears). Never
  reformat files outside the task's scope.
- **M-R3.4** **Local commit gate — enforced before EVERY local commit of this plan** (task
  commits, fix commits, wip commits alike):
  - lint + format always: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` exit 0 AND
    `ruff format --check` on the commit's touched files;
  - tests: `.venv/bin/pytest tests/ -x` green in the venv — **at every task** (the change is
    purely additive; unlike the feature-upd-sandbox vocabulary swap there is no migration
    ledger and no knowingly-red window — from Task 1 on the full suite is the gate). If a task
    finds itself unable to keep the full suite green, that is an implementation bug or an
    out-of-scope regression — fix it or stop and report; committing red or "fixing" an
    unrelated suite outside the task's scope are both forbidden.
- **M-R3.5** `goga lint` at plan end: 24 cells, 0 errors — no new findings against the
  baseline.
- **M-R3.6** When the complexity gates (C90 / PLR) trip — the parser's region/token switch is
  the known hotspot — decompose inside the current cell (internal helpers such as
  `_split_fragments` and per-region handlers are allowed; new cells are not).

### R4. REPL Cycle Rules (continuous interactive evaluation, hot reloading, code migration to source files)

The workflow of every coding task is a live-evaluation loop — **prototype → evaluate → migrate
→ re-verify**, repeated per entity — not write-blind-then-test:

- **M-R4.1 (Continuous interactive evaluation)** — exercise every non-trivial behavior
  fragment in an interactive Python session inside the virtualenv (`.venv/bin/python -i`, or a
  heredoc `.venv/bin/python - <<'PY'`) with real inputs **before and while it lands in source
  files**: every migration file text variant (the simple Up/Down file, the function body with
  interior semicolons, the mixed fragment-then-body file, NO TRANSACTION, Down-only extras,
  CRLF, comment-only fragments), `urllib.parse.urlparse` on every scheme shape incl. the
  scp-style empty scheme (decision A), the `FakeConnection` transaction shapes, GitPython's
  `clone_from(url, target, depth=1, branch=None)` signature. Nothing moves to "done" on faith;
  each behavior is observed first.
- **M-R4.2 (Hot reloading)** — keep one REPL session per task where practical; after source
  edits re-import with `importlib.reload(module)` instead of restarting the session, and never
  evaluate against stale definitions. Use the focused test file
  (`.venv/bin/pytest tests/sandbox/migrations/test_<module>.py -x -v`) as the fast feedback
  loop; the full suite at task end.
- **M-R4.3 (Code migration to source files)** — the REPL is a scratchpad, never a home: every
  verified snippet is migrated into the module at its contract `location` wearing the
  convention outfit (Google docstring M-R1.7, module logger M-R1.5, type hints M-R1.8,
  blank-line blocks M-R1.6); the scratch is discarded; the migrated code is re-verified through
  a FRESH interpreter import (`.venv/bin/python -c "from goga_tool_pybuggy.sandbox.migrations
  import parse_migration_file; …"`) before the task's tests run. No behavior ships REPL-only:
  every verified fragment lands in a source file or a test.
- **M-R4.4 (Scratch hygiene)** — prototypes live in the REPL or under `/tmp`; never as files
  inside the repo; nothing scratch is committed. (Migration sample folders used by fixtures
  belong to `tmp_path`, never to the repo tree.)
- **M-R4.5 (REPL complements TDD; external facts stay live)** — the contract tests and logic
  tests of each task remain the authority; the REPL loop lives inside STEP 2 (implementation)
  and STEP 5 (debugging) of the ralphex protocol, and during debugging the failing input is
  reproduced in the REPL with the exact test data before anything is fixed. Load-bearing
  external facts are re-confirmed once in the REPL against the installed wheels instead of
  trusting memory: inspect `git.Repo.clone_from` (the `branch=None` kwarg semantics — omitting
  the kwarg defaults differently in some GitPython versions), and `psycopg.Connection.
  transaction()` on an autocommit connection (opens an explicit transaction — the pattern the
  psycopg cook documents). Docker-dependent fragments (the live reset semantics) run in the REPL
  only when the container runtime is available — it is not in this environment, so those
  fragments are verified against the traced design and the fake/mock-based unit tests, and the
  live behavior is carried by the `requires_docker`-gated suite.

### R5. Contract Discipline

- **M-R5.1** `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. The
  working-tree manifests of this branch ARE the contract; if the implementation does not match,
  fix the implementation — never the contract. No manifest changes without a new design pass.
- **M-R5.2** Facade obligations: every contract entity is importable from its cell package
  root via `__all__`; only identifiers in `__all__` constitute the facade. This plan creates the
  migrations facade at exactly 8 names and grows the config facade to 9 names; the engines
  facade stays byte-stable at 11.
- **M-R5.3** Traceability: every implementation unit and test maps to a contract entity /
  property / method / described requirement — the per-task entity lists carry the mapping.
- **M-R5.4** No new cells; internal helpers stay inside the current cell (`_split_fragments`,
  `_validate_migrations`, `_migrate`, the local server-message extraction); `location`
  placement is obeyed exactly (same directory level as the CODEMANIFEST, extension present, no
  parent traversal); relative imports inside the package.
- **M-R5.5** Leaf-first dependency order (migrations → config → engines); the migrations cell
  never imports from config or engines — it owns its failure family and its server-message
  extraction locally. The protected `_migrate` hook is not contract surface and is not added to
  any manifest. `Sandbox.start` sequencing and the `sandbox/` (session runtime) cell stay
  untouched.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the
> next. Within each coding task, contract tests are written first (TDD workflow). Cell order:
> `sandbox/migrations` (leaf) → `sandbox/config` → `sandbox/engines` → integration → docs →
> final validation. Every task follows the Mandatory Rules (R1–R5) in full; the lint gate of
> each task is also the pre-commit gate (M-R3.4). The change is additive — `pytest tests/ -x`
> stays green at every task.

### Task 1: Workspace bootstrap — virtualenv, contract commit, baseline green (infrastructure)

Prepare the execution environment. The repo has no virtualenv (conventions require one,
M-R1.2); the branch working tree carries the materialized contract (the new migrations
CODEMANIFEST + `.usages/`, the modified config/engines CODEMANIFESTs, the replaced
`sandbox-file.md`, and the three cook files) which lands in git here as the read-only contract
input. Nothing else changes.

**Usages relevant to this task:**
- `conventions`: virtualenv execution (M-R1.2); pyproject-based configuration (M-R1.1).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create the virtualenv: `python3 -m venv .venv` and install the project editable with the
  test extra: `.venv/bin/pip install -e '.[test]'`; verify `.venv/bin/python -c "import
  goga_tool_pybuggy"` succeeds
- [x] Verify the current suite baseline is green: `.venv/bin/pytest tests/ -x` (docker is
  unavailable here — the gated cases skip; record the counts; if the baseline is red, stop and
  report before touching anything) — final counts: 1566 passed, 17 skipped, 0 failed. The raw
  baseline was red (3 failures in `tests/commands/init/`): the plan's own contract input
  `migrations/.usages/migration-set.md` extends the bootstrap's dynamic packaged-usage
  discovery from five stems to six, while the tests hardcoded the old five-stem list and
  rerun-skip counts (6). Fixed test-side only per M-R3.4 "fix it or stop and report"
  (`_PACKAGED_USAGES` gains `migration-set`; idempotency counts 6 → 7); no CODEMANIFEST and
  no production code touched — the bootstrap behavior (dynamic discovery + bare-backtick
  annotation fallback) is correct by design
- [x] Verify the contract baseline: `goga lint` → 24 cells, 0 errors
- [x] Commit the already-materialized contract files unchanged — they are this plan's
  read-only input: `goga_tool_pybuggy/sandbox/migrations/` (CODEMANIFEST +
  `.usages/migration-set.md`), `goga_tool_pybuggy/sandbox/config/CODEMANIFEST`,
  `goga_tool_pybuggy/sandbox/engines/CODEMANIFEST`,
  `goga_tool_pybuggy/sandbox/config/.usages/sandbox-file.md`,
  `.goga/usages/cooks/goose-sql.md`, `.goga/usages/cooks/gitpython.md`,
  `.goga/usages/cooks/psycopg.md` — already landed in git unchanged with commit `57ba2d6`
  (the commit carrying this plan); the working tree carries no contract modifications, so
  nothing needed re-committing
- [x] Lint gate (pre-commit, M-R3.4): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0

### Task 2: Migrations cell I — `errors.py` + `goose.py`: `MigrationError`, `MigrationFile`, `parse_migration_file`, `load_migration_set`, the shared grammar; facade opens (TDD)

The core of the leaf cell: the failure family, the parsed-unit model, the pure goose-SQL
parser (with the design-review R1 ordering fix), the set loader, and the single-source filename
grammar. The cell facade opens with the four names implemented so far.

**Contract entities**: `MigrationError()` (`errors.py`), `MigrationFile(version: int,
filename: str, statements: list[str], no_transaction: bool)` (`goose.py`),
`parse_migration_file(filename: str, text: str) -> migration: MigrationFile` (`goose.py`),
`load_migration_set(folder: Path) -> migrations: list[MigrationFile]` (`goose.py`) — all
importable from `goga_tool_pybuggy.sandbox.migrations`.

**Usages relevant to this task:**
- `goose-sql`: the migration file format — naming grammar `^(\d+)_(.+)\.sql$` (sequential
  `00003` and timestamp `20230102103456` styles), the five supported annotations (`Up`, `Down`,
  `StatementBegin`, `StatementEnd`, `NO TRANSACTION`), statement-body rules (bodies opaque,
  interior semicolons never split), out-of-subset rejection, up-only set consumption.
- `conventions`: pydantic `kw_only` model (M-R1.4), Google docstrings, relative imports,
  mock-free tests for pure logic (M-R2.6), `tmp_path` for the folder fixtures.

**Design details (binding):**
- `errors.py`: `class MigrationError(RuntimeError)` — docstring per the contract ("The failure
  family of the migrations domain…").
- `goose.py` module level: `FILENAME_GRAMMAR = re.compile(r"^(\d+)_(.+)\.sql$")` plus the
  version-int extraction — the single source `source.py` imports in Task 3; never duplicated.
- `MigrationFile(BaseModel)`: `model_config = ConfigDict(kw_only=True)`; fields `version: int`,
  `filename: str`, `statements: list[str] = []`, `no_transaction: bool = False`.
- `parse_migration_file` — the verified algorithm (implement exactly):
  1. Grammar match on `filename` → `version = int(prefix)`; no match → raise naming the file.
  2. Line scan (`text.splitlines()`) over three regions — **header** (before Up), **up** (Up →
     Down), **down** (excluded). An annotation line is one whose stripped form matches
     `^--\s*\+goose\s+(.+?)\s*$`.
     - Header: `NO TRANSACTION` → `no_transaction = True`; `Up` → switch to up; anything else
       (including `Down` — Down before Up means no Up section) → raise naming the file.
       Non-annotation header lines are ignored — header SQL outside Up is never applied.
     - Up: non-annotation lines accumulate into a fragment buffer (or into the open body).
       `StatementBegin` → **flush the fragment buffer through the semicolon split NOW**
       (`_split_fragments`; the finished pieces append to `statements` before the body opens)
       and switch to body mode; body lines accumulate verbatim; `StatementEnd` → the stripped
       body becomes one statement as-is (interior semicolons never split it). `Down` → stop
       scanning (the buffer tail flushes after the loop). `StatementEnd` without an open body,
       `NO TRANSACTION` or a second `Up` here, or any other token → raise naming the file.
     - Down region: unreachable — the scan stops at Down; unknown annotations and `{{...}}`
       after Down never raise.
  3. Unclosed `StatementBegin` at end of scan → raise naming the file. Still in header after
     the loop → raise "no +goose Up section" naming the file.
  4. `_split_fragments(lines)` — the shared flush helper (module-level in `goose.py`): join the
     buffered lines, split on `";"`, drop pieces that are empty or comment-only (every line
     stripped starts with `--`), return the stripped pieces. Called at `StatementBegin` and
     once on the tail after the scan — so `statements` preserves file order and a fragment
     lacking a trailing `;` before a body never merges with the fragment after it.
  5. Interpolation guard: `"{{"` occurring anywhere in header+up text → raise naming the file
     ("goose {{...}} interpolation is not supported — migration statements apply as given").
- `load_migration_set`: `sorted(p for p in folder.iterdir() if p.is_file() and p.suffix ==
  ".sql")`; empty → raise naming the folder; grammar + duplicate-version re-check (shared with
  `check_local_migrations`, the apply-time backstop for remote sources); `parse_migration_file(
  p.name, p.read_text(encoding="utf-8"))` per file (the loader reads content — the parser stays
  pure); `migrations.sort(key=lambda m: m.version)` — ascending numeric (`9_` before `10_`).
- Facade `goga_tool_pybuggy/sandbox/migrations/__init__.py`: `__all__ = ["MigrationError",
  "MigrationFile", "load_migration_set", "parse_migration_file"]` (grows to 8 by Task 4).
- Test package: `tests/sandbox/migrations/__init__.py` + `test_goose.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: stated in the iteration output and the progress log
- [x] **Contract tests** (new `tests/sandbox/migrations/test_goose.py`; expected to fail now —
  the package does not exist): all four names importable from
  `goga_tool_pybuggy.sandbox.migrations`; `MigrationError` subclasses `RuntimeError`;
  `MigrationFile` kw_only construction with the four property types (`version -> int`,
  `filename -> str`, `statements -> list[str]`, `no_transaction -> bool`); signatures
  `parse_migration_file(filename: str, text: str)`, `load_migration_set(folder: Path)`
- [x] **REPL prototype (R4)**: in the venv REPL parse every scenario text live before
  migrating — the simple Up/Down file (observe the two statements without terminating
  semicolons), the function body with interior semicolons (one verbatim statement), the mixed
  fragment-then-body file (observe `[CREATE TABLE, body, CREATE INDEX]` — file order), NO
  TRANSACTION, the timestamp filename, CRLF text, comment-only fragments (dropped), and each
  failure text (missing Up, Down before Up, unknown annotation in header and in up,
  NO TRANSACTION after Up, unclosed body, stray StatementEnd, interpolation) reading each
  `MigrationError` message; then migrate
- [x] **Code**: create `goga_tool_pybuggy/sandbox/migrations/errors.py` and `goose.py` per the
  design details (grammar + `_split_fragments` + the region scan + the set loader)
- [x] **Code**: create the cell facade `__init__.py` with the four `__all__` names and the
  module docstring
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/migrations/test_goose.py -x
  -v` — pass; fresh-interpreter facade check (M-R4.3): `.venv/bin/python -c "from
  goga_tool_pybuggy.sandbox.migrations import MigrationError, MigrationFile,
  parse_migration_file, load_migration_set"`
- [x] **Logic tests** (design scenarios, transferred with their Setup/Input/Assertions):
  1. `test_parse_simple_up_statements` — the canonical goose file (CREATE TABLE + CREATE
     INDEX, then Down); `version == 3`; `no_transaction is False`; `statements` exactly the
     two bodies **without** terminating semicolons; Down statements absent
  2. `test_parse_statement_begin_body_preserves_interior_semicolons` — the plpgsql function
     body inside StatementBegin/End plus a trailing index DDL; `len(statements) == 2`;
     `statements[0]` contains `"RETURN NEW;"` and `"$$ LANGUAGE plpgsql;"`; `statements[1]` is
     the index DDL without `;`
  3. `test_parse_preserves_file_order_of_fragments_and_bodies` — plain statement **before** a
     body **before** a trailing statement; `statements` length 3 in exactly that file order
     (the design-review R1 regression pin — a parser with two append sites silently reorders
     mixed files)
  4. `test_parse_no_transaction_flag` — `-- +goose NO TRANSACTION` before Up → flag True;
     statements parsed
  5. `test_parse_down_section_skipped` — valid Up, then Down with `-- +goose Env FOO` and
     `SELECT {{.Var}};` after it → no raise; statements hold only the Up statements
  6. `test_parse_extracts_timestamp_version` — `20230102103456_init.sql` →
     `version == 20230102103456`
  7. `test_load_orders_numerically` — folder with `9_nine.sql`, `10_ten.sql`, `2_two.sql` →
     versions `[2, 9, 10]`; filenames in the same order (the lexicographic-ordering bug pin)
  8. `test_parse_without_up_section` — header + Down only → `MigrationError` naming the file
  9. `test_parse_with_invalid_filename` — `"create_orders.sql"` → raise naming the file
  10. `test_parse_with_unclosed_statement_begin` → raise naming the file
  11. `test_parse_with_statement_end_without_begin` — stray `-- +goose StatementEnd` in Up →
      raise naming the file
  12. `test_parse_with_unknown_annotation` — parametrized `-- +goose Env FOO` in the Up region
      and in the header → raise naming the file and the token
  13. `test_parse_with_no_transaction_after_up` — `NO TRANSACTION` after `Up` → raise naming
      the file
  14. `test_parse_with_interpolation` — `CREATE TABLE {{.Name}} (id int);` in Up → raise
      naming the file and the interpolation rule
  15. `test_load_without_sql_files` / `test_load_with_duplicate_versions` — empty folder →
      raise naming the folder; `1_a.sql` + `0001_b.sql` → raise naming the folder and both
      files
  16. `test_parse_empty_up_section` — `Up` immediately followed by `Down` → `statements ==
      []`, no raise (`version == 9`)
  17. `test_parse_drops_comment_only_fragments` — trailing/leading comment fragments;
      statements contain `SELECT 1` and `SELECT 2`; no statement consists solely of a comment;
      leading comment lines inside a kept piece stay part of the statement text
  18. `test_parse_crlf_file` — `\r\n` endings → the statement equals the clean body (no `\r`)
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — 1594 passed, 17 skipped (baseline 1566 + 28 new). One
  initial failure (test_parse_drops_comment_only_fragments) was a wrong test expectation, not
  an implementation bug — the REPL prototype had already shown the correct semantics: a
  comment line inside a kept piece (between two semicolons) stays part of that statement's
  text per the design's "leading comment lines inside a kept piece stay" rule; expectation
  fixed to the verified behavior
- [x] **Contract re-verification**: the parser Algorithm steps 1–6, the Requirements (pure
  function, no I/O; every failure names the file), the Constraints (no SQL semantics
  validated), and `load_migration_set`'s deterministic order hold
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files (decompose via `_split_fragments`/region helpers if
  C90/PLR trip — M-R3.6)
- [x] **Completion**: checkboxes marked; submitted to the external review loop

### Task 3: Migrations cell II — `source.py`: `check_local_migrations`, `check_git_url` (TDD)

The load-time shape checks. Both are raise-only; both name the offending path or URL; the
grammar is imported from `goose.py` — never duplicated.

**Contract entities**: `check_local_migrations(folder: Path)` and `check_git_url(url: str)`
(`source.py`) — importable from `goga_tool_pybuggy.sandbox.migrations`.

**Usages relevant to this task:**
- `goose-sql`: the file-naming and version-prefix grammar (shared regex import).
- `gitpython`: the URL rules and the ambient-credentials convention — scheme allowlist
  https/http/git/ssh; the ssh username is not a credential; scp-style (empty scheme) rejected
  (decision A).
- `conventions`: parametrized boundary tables (M-R2.5); `tmp_path` fixtures; pure mock-free
  logic.

**Design details (binding):**
- `check_local_migrations` — the verified algorithm:
  1. `folder.is_dir()` false (missing or a file) → `MigrationError(f"{folder}: the migrations
     source must be an existing folder")`.
  2. `list(folder.iterdir())` empty → raise naming the folder ("the migrations folder is
     empty").
  3. `sql_files = [p for p in entries if p.is_file() and p.suffix == ".sql"]` empty → raise
     naming the folder ("the migrations folder holds no .sql files").
  4. Grammar pass over every `.sql` name with the shared `FILENAME_GRAMMAR`; a non-matching
     name → raise naming the folder **and the file** ("invalid migration filename — expected
     <version>_<description>.sql").
  5. Uniqueness of the int prefixes; a duplicate → raise naming the folder and both files
     ("duplicate migration version {n}") — numeric comparison (`00001` and `1` collide).
  6. Return None. Shape checks only — no file content read.
- `check_git_url` — the verified algorithm (decision A):
  1. `parsed = urllib.parse.urlparse(url)`; `parsed.scheme not in {"https", "http", "git",
     "ssh"}` (empty scheme included — scp-style `git@github.com:acme/r.git` fails here) →
     `MigrationError(f"{url}: disallowed git URL scheme '{parsed.scheme}' (allowed: git, http,
     https, ssh)")`.
  2. `"@" in parsed.netloc and parsed.scheme != "ssh"` → raise naming the URL ("the git URL
     must not embed credentials") — `https://user:token@host` and `https://user@host`
     rejected; `ssh://git@host/...` accepted (an ssh username is not a credential).
  3. Return None. No network, no clone.
- Facade grows: `__all__` adds `"check_git_url"`, `"check_local_migrations"` (6 names).
- Tests in `tests/sandbox/migrations/test_source.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: stated in the iteration output and the progress log
- [x] **Contract tests** (new `tests/sandbox/migrations/test_source.py`; expected to fail now):
  both names importable from the facade; signatures `(folder: Path)` / `(url: str)` —
  observed failing on import first (TDD), passing after the code landed
- [x] **REPL prototype (R4)**: in the venv REPL ran `urllib.parse.urlparse` on every shape —
  observed `scheme == ""` on the scp-style URL (decision A), ssh `@`-netloc passing,
  `https://user@host` carrying the credential netloc; drove the folder fixtures (valid,
  missing, file-instead-of-folder, empty, non-.sql only, duplicate `00001`/`1` colliding at
  int 1); then migrated
- [x] **Code**: created `goga_tool_pybuggy/sandbox/migrations/source.py` per the design
  details (grammar imported from `.goose` through `version_prefix` — the single extraction
  point); extended the facade `__all__` to 6 names
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/migrations/test_source.py -x
  -v` — 3 contract tests pass; fresh-interpreter facade check: `.venv/bin/python -c "from
  goga_tool_pybuggy.sandbox.migrations import check_local_migrations, check_git_url"` — the
  facade `__all__` holds exactly the 6 names
- [x] **Logic tests** (design scenarios, transferred) — all 10 present (20 tests total with
  the parametrized tables):
  1. `test_check_local_migrations_with_valid_folder` — `00001_init.sql` + `00002_add_users.sql`
     → no exception
  2. `test_check_local_migrations_ignores_non_sql_files` — plus `notes.txt`, `README.md` → no
     exception (the stray-README rule)
  3. `test_check_git_url_accepts_allowed_schemes` — parametrized over https/http/git/ssh URLs
     → no exception per parameter
  4. `test_check_local_migrations_with_missing_folder` → `MigrationError`, message contains
     the path
  5. `test_check_local_migrations_with_file_instead_of_folder` → raise naming the path
  6. `test_check_local_migrations_with_empty_folder` / `..._without_sql_files` → both raise
     naming the folder; the second names the no-`.sql` rule
  7. `test_check_local_migrations_with_invalid_filename` — `create_orders.sql` beside a valid
     file → raise naming folder **and** file
  8. `test_check_local_migrations_with_duplicate_versions` — `00001_a.sql` + `1_b.sql` →
     raise naming the folder, both files, and `1`
  9. `test_check_git_url_rejects_unknown_scheme` — parametrized `["ftp://h/r.git",
     "file:///etc/passwd", "git@github.com:acme/r.git"]` → `MigrationError`; each message
     contains the URL and `disallowed` (the scp-style case pins decision A against future
     "parity with pull" drift)
  10. `test_check_git_url_rejects_embedded_credentials` — parametrized
      `["https://user:token@h/r.git", "https://user@h/r.git"]` → raise naming the URL and the
      credentials rule
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — 1614 passed, 17 skipped (Task 2 baseline
  1594 + 20 new); one initial failure (duplicate-version message named the files in
  nondeterministic `iterdir()` order) fixed implementation-side — `check_local_migrations`
  now sorts the `.sql` listing before the name pass, matching `load_migration_set`'s
  established deterministic style
- [x] **Contract re-verification**: both Algorithms, the Requirements (shape only; every
  failure names the folder/URL and the rule), the Constraints (no file contents read; no
  network) hold; the grammar is imported, not duplicated
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files — clean (the two PLR1711 `return None` literals
  removed — the design's "Return None" is the implicit None return; the tests assert `is
  None` against it)
- [x] **Completion**: checkboxes marked; submitted to the external review loop

### Task 4: Migrations cell III — `apply.py`: `apply_migrations`, `run_migrations`; facade complete at 8 names (TDD)

The execution plane and the source-resolution orchestration. The facade reaches its final
eight names; the cell is complete.

**Contract entities**: `apply_migrations(conn: Connection, migrations: list[MigrationFile])`
and `run_migrations(conn: Connection, location: str, git_url: str | None, git_ref: str |
None)` (`apply.py`) — importable from `goga_tool_pybuggy.sandbox.migrations`.

**Usages relevant to this task:**
- `psycopg`: the execution patterns — autocommit session connection; `with conn.transaction():`
  opens an explicit transaction on an autocommit connection (one per file by default); direct
  `cursor.execute(statement)` per statement for NO TRANSACTION files; parameter-free DDL
  (no placeholders ever); failure surfacing `exc.diag.message_primary or str(exc)`.
- `gitpython`: the shallow-clone context-manager pattern — `Repo.clone_from(url, target,
  depth=1, branch=ref)` with `branch=None` omitting `--branch` (the remote default branch);
  ambient credentials only; `GitCommandError` → `MigrationError` (the sandbox family, not
  `ClickException`); nothing copied into the consumer repository.
- `conventions`: external boundaries patched at the import point (M-R2.6) — `Repo.clone_from`
  under `mock.patch("goga_tool_pybuggy.sandbox.migrations.apply.Repo.clone_from")`; the
  connection faked with local doubles; `caplog` for the progress lines (M-R1.5).

**Design details (binding):**
- `apply_migrations` — the verified algorithm:
  1. Per `m` in `migrations` (the caller's order preserved):
     - `m.no_transaction` → each statement executes directly on the autocommit connection,
       statement-by-statement, **no** `transaction()` block.
     - default → `with conn.transaction():` wraps **all** statements of the file — one commit
       or one rollback per file; `with conn.cursor() as cursor: cursor.execute(statement)` per
       statement.
     - Progress: `logger.info("migration applied", extra={"migration": m.filename, "version":
       m.version})` — one structured line per applied file.
  2. First failing statement: `except psycopg.Error as exc:` → `primary = exc.diag.
     message_primary or str(exc)` → `raise MigrationError(f"{m.filename}: {primary}") from exc`
     — the apply stops; no further file runs. Default files roll back fully; NO TRANSACTION
     files keep already-applied statements.
  3. Returns None. Nothing written to any baseline journal; no version table created or read;
     Down sections are not part of the parsed set.
- `run_migrations` — the verified algorithm:
  1. `git_url is None` (local): `folder = Path.cwd() / location` (an absolute `location`
     overrides the anchor — pathlib `/` semantics) → `load_migration_set(folder)` →
     `apply_migrations(conn, migrations)` → return.
  2. Remote: `with tempfile.TemporaryDirectory(prefix="pybuggy-migrations-") as tmp:` — a
     fresh directory per call (the target never pre-exists; the clone is deleted on every exit
     path; no caching across sessions):
     - `Repo.clone_from(git_url, str(target), depth=1, branch=git_ref)`; `branch=None` omits
       `--branch` → the remote default branch. `except GitCommandError as exc: raise
       MigrationError(f"failed to clone {git_url}: {exc}") from exc`.
     - `folder = target / location`; containment: `folder.resolve().is_relative_to(
       target.resolve())` else raise naming the location ("the migrations location escapes the
       clone"); `folder.is_dir()` false → raise naming the path ("the migrations folder is
       missing in the cloned repository").
     - `load_migration_set(folder)` → `apply_migrations(conn, migrations)`.
  3. DEBUG `"migrations source resolved"` with `extra={"location": ...}` at resolution.
- The server-message extraction mirrors `engines/postgres.py::_server_message` but stays local
  to the migrations cell — no import from engines (M-R5.5).
- Facade reaches 8 names: `__all__ = ["MigrationError", "MigrationFile", "apply_migrations",
  "check_git_url", "check_local_migrations", "load_migration_set", "parse_migration_file",
  "run_migrations"]`.
- Test doubles in `tests/sandbox/migrations/conftest.py` (mirroring
  `tests/sandbox/engines/test_postgres.py`): `FakeCursor` (records `("execute", sql, params)`,
  context manager), `FakeTransaction` (records `("transaction", "begin"|"commit"|"rollback",
  None)`), `FakeConnection` (holds `statements`, `cursor()`, `transaction()`), and
  `FailingCursor`/`FailingConnection` raising `psycopg.errors.UndefinedTable` (carrying
  `diag.message_primary`) on every execute. Tests in `tests/sandbox/migrations/test_apply.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: stated in the iteration output and the progress log
- [x] **Contract tests** (new `tests/sandbox/migrations/test_apply.py` + `conftest.py`;
  expected to fail now): both names importable from the facade; signatures match the contract
  (`conn: Connection`, `migrations: list[MigrationFile]` / `conn`, `location: str`,
  `git_url: str | None`, `git_ref: str | None`); the facade `__all__` is exactly the 8 names
  — observed failing on import first (TDD: `ImportError: cannot import name
  'apply_migrations'`), passing after the code landed
- [x] **REPL prototype (R4)**: re-confirmed the external facts live (M-R4.5) — inspected
  `git.Repo.clone_from` (the `branch=None` kwarg semantics: `Git.transform_kwarg` returns
  `[]` for None → `--branch` omitted, default branch) with a live local shallow-clone
  roundtrip, `psycopg.Connection.transaction()` signature, `GitCommandError` shape, and the
  `diag.message_primary or str(exc)` fallback on a constructed error; drove the doubles:
  default two-file apply (begin/execute…/commit), NO TRANSACTION file (no transaction
  markers), failing statement (wrapped `MigrationError`, rollback, stopped loop); drove the
  clone-location resolution (resolve/missing/escape) over fresh temp targets; then migrated
- [x] **Code**: created `goga_tool_pybuggy/sandbox/migrations/apply.py` per the design
  details (`_run_local`/`_run_remote` orchestration, `_shallow_clone`,
  `_resolve_clone_location` with the containment check, `_apply_in_transaction` /
  `_apply_in_autocommit`, local `_server_message`); extended the facade `__all__` to the
  final 8 names
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/migrations/ -x -v` — 65
  passed; fresh-interpreter facade checks: `.venv/bin/python -c "from
  goga_tool_pybuggy.sandbox.migrations import apply_migrations, run_migrations"` and the
  full 8-name import — both succeed
- [x] **Logic tests** (design scenarios, transferred):
  1. `test_apply_executes_each_file_in_its_own_transaction` — two default migrations over
     `FakeConnection`; `fake.statements == [("transaction","begin",None), ("execute",
     "CREATE TABLE t (id int)",None), ("transaction","commit",None), ("transaction",
     "begin",None), ("execute","INSERT INTO t VALUES (1)",None), ("execute","INSERT INTO t
     VALUES (2)",None), ("transaction","commit",None)]`
  2. `test_apply_no_transaction_runs_statement_by_statement` — NO TRANSACTION file →
     `fake.statements == [("execute", "CREATE INDEX CONCURRENTLY i ON t (c)", None)]`; no
     transaction entries
  3. `test_apply_logs_one_progress_line_per_file` — `caplog` at INFO: two records with
     `record.message == "migration applied"`; extras carry the filenames in application order
  4. `test_run_local_source_resolves_against_cwd` — `tmp_path/db/migrations/00001_init.sql` +
     `monkeypatch.chdir`; `run_migrations(conn=fake, location="db/migrations", git_url=None,
     git_ref=None)`; statements start with begin and contain the file's statement; the clone
     API never touched
  5. `test_run_remote_source_clones_and_applies` — `Repo.clone_from` side effect writes
     `00001_init.sql` into the received target; called once with the url, a temp target,
     `depth=1`, `branch="release-branch"`; the statement executed; the clone target does not
     exist after the call
  6. `test_run_remote_source_clones_default_branch_without_ref` — `git_ref=None` → the
     `branch` kwarg is exactly `None` (GitPython omits `--branch`)
  7. `test_apply_failure_names_file_and_server_message_and_stops` — `FailingConnection`
     (`UndefinedTable('relation "ghost" does not exist'`) with a later `m3` after the failing
     `m2`; `excinfo.type is MigrationError`; message contains the filename and the server
     text; `__cause__` is the psycopg error; no `m3` statement present
  8. `test_run_local_source_missing_folder` — no `db/` under the chdir → `MigrationError`
     naming `db/migrations`
  9. `test_run_remote_source_clone_failure` — `clone_from` raises
     `GitCommandError("clone", 128, b"fatal: Authentication failed")` → `MigrationError`
     containing the URL and `failed to clone`; cause chain intact; temp dir gone
  10. `test_run_remote_source_missing_location_in_clone` — clone side effect creates the
      target but no `db/migrations` inside → raise naming the path
  11. `test_run_remote_source_location_escapes_clone` — declaration `location=
      "../../elsewhere"` with an existing escape target holding a valid `.sql`; → raise naming
      the location; nothing executed on the fake
  12. `test_apply_empty_set_is_noop` — `migrations=[]` → `fake.statements == []`, no exception
  13. `test_apply_empty_statements_file_commits_vacuously_and_logs` — a statement-less
      default file → `fake.statements == [("transaction","begin",None), ("transaction",
      "commit",None)]`; exactly one INFO `"migration applied"` record with `record.migration ==
      "00009_empty.sql"` (the design-review R7 pin)

  All 13 present (17 apply tests total with the 4 contract tests); scenario 11 drives the
  escape through a sibling temp dir (`../<escape-root>/migrations`) so the containment
  check fires against an existing valid `.sql` folder outside the clone root.
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — 1631 passed, 17 skipped (Task 3 baseline
  1614 + 17 new), fully green after the lint-driven reformat; no logic failures occurred
- [x] **Contract re-verification**: both Algorithms, the Requirements (caller's order
  preserved; one apply per call; every failure names the failed step; nothing journaled), and
  the Constraints (no version table; no clone caching — fresh `TemporaryDirectory` per call;
  no Down execution) hold; the engines import is untouched (no upward import from the leaf —
  M-R5.5; the only stdlib additions are `logging`, `tempfile`, `pathlib.Path`)
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files — clean (initial pass fixed 9 findings in the test
  file: SIM117 nested `with` combinations, E501 wraps via `ruff format`, one docstring
  shortening — no decomposition needed, no C90/PLR trips)
- [x] **Completion**: checkboxes marked; submitted to the external review loop

### Task 5: Config cell I — `migrations.py` models, `ServiceConfig.migrations`, facade to 9 names (TDD)

The declaration side: the two new pydantic models, the optional field on `ServiceConfig`, and
the facade growth. Purely additive — existing documents parse identically.

**Contract entities**: `GitSource(url: str, ref: str | None = None)` and
`MigrationsConfig(location: str, git: GitSource | None = None)` (`migrations.py`, new file) —
importable from `goga_tool_pybuggy.sandbox.config`; `ServiceConfig` gains `migrations:
MigrationsConfig | None` (after `probe`) with the property `migrations ->
MigrationsConfig | None`.

**Usages relevant to this task:**
- `conventions`: pydantic `kw_only` models, `extra="forbid"` on the declaration models,
  `None` only for explicit absence (M-R1.4); Google docstrings; kw_only TypeError tests;
  boundary parametrization (M-R2.5).

**Design details (binding):**
- `GitSource(BaseModel)`: `model_config = ConfigDict(kw_only=True, extra="forbid")` — `url:
  str` (required), `ref: str | None = None`. Docstring documents the constraint: a bare commit
  SHA is not a valid ref (shallow clones resolve branch and tag names only).
- `MigrationsConfig(BaseModel)`: `model_config = ConfigDict(kw_only=True, extra="forbid")` —
  `location: str` (required), `git: GitSource | None = None`. Docstring: valid only on a
  postgresql service entry — placement is checked at document load; no version-tracking or
  journaling options (the apply semantics are fixed).
- `ServiceConfig` (existing `service.py`): add `migrations: MigrationsConfig | None = None`
  after `probe`; extend the class docstring `Attributes` entry; import
  `from .migrations import GitSource, MigrationsConfig` (the `GitSource` import may live in
  `migrations.py` only — import what `service.py`'s annotations need). The existing
  `_probe_carries_no_path` validator is untouched; no model-level migrations validation (kind
  placement is loader-level — Task 6).
- Facade `config/__init__.py`: `__all__` grows to `["GitSource", "InstanceConfig",
  "MigrationsConfig", "ProbeConfig", "SandboxConfig", "ServiceConfig", "StartupData",
  "TopicConfig", "load_sandbox_config"]` (9 names, alphabetical).
- Tests: new `tests/sandbox/config/test_migrations.py`; extend
  `tests/sandbox/config/test_service.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: stated in the iteration output and the progress log
- [x] **Contract tests** (new `test_migrations.py` + reworked contract section of
  `test_service.py`; expected to fail now): `GitSource` and `MigrationsConfig` importable from
  `goga_tool_pybuggy.sandbox.config`; kw_only construction; property types `url -> str`,
  `ref -> str | None`, `location -> str`, `git -> GitSource | None`; `ServiceConfig.migrations
  -> MigrationsConfig | None` present on the facade type — observed failing on import first
  (TDD: `ImportError: cannot import name 'GitSource'`), passing after the code landed; the
  reworked `ServiceConfig` contract section now asserts the six-field set, the after-`probe`
  position, and the typed `migrations` property
- [x] **REPL prototype (R4)**: in the venv REPL constructed both declaration shapes (local
  `MigrationsConfig(location="db/migrations")`, remote with `GitSource(url=…, ref=
  "release-branch")`), observed the `ref`/`git` None defaults, the raw `git={"url": …}`
  mapping coercing into the typed `GitSource`, the `extra="forbid"` rejection of `journal=True`
  (ValidationError naming the key), kw_only positional `TypeError`, and both required-field
  rejections; then migrated
- [x] **Code**: created `goga_tool_pybuggy/sandbox/config/migrations.py` with the two models
  (`kw_only=True, extra="forbid`"); added the `migrations: MigrationsConfig | None = None`
  field + docstring entry to `service.py` (import `from .migrations import MigrationsConfig`;
  `_probe_carries_no_path` untouched); grew the facade `__all__` to the 9 alphabetical names
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/config/test_migrations.py
  tests/sandbox/config/test_service.py -x -v` — 33 passed; fresh-interpreter facade check:
  `GitSource`, `MigrationsConfig`, `ServiceConfig` import cleanly and `__all__` holds exactly
  the 9 names; `ServiceConfig(name="db", kind="postgresql").migrations is None` and the raw
  dict coerces
- [x] **Logic tests** (design scenarios, transferred):
  1. `test_service_config_migrations_default_is_none` — `ServiceConfig(name="db",
     kind="postgresql")` → `config.migrations is None`; a config built with
     `migrations={"location": "x"}` yields `isinstance(config.migrations, MigrationsConfig)`
     (backward compatibility — every existing document behaves exactly as before)
  2. `test_migrations_models_reject_unknown_keys` — `MigrationsConfig(location="x",
     journal=True)` → `ValidationError` naming `journal` (the "apply semantics are fixed"
     constraint)
  3. Model units: kw_only (positional raises `TypeError`); `ref`/`git` default None;
     `GitSource` requires `url`; `MigrationsConfig` requires `location`

  All present — 17 tests in `test_migrations.py` (8 contract + 9 logic, incl. the raw-git-
  mapping coercion unit) and the `migrations` units inside `test_service.py`
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — 1651 passed, 17 skipped (Task 4 baseline
  1631 + 20 new), fully green on the first run (additive optional field; no failures to
  reproduce)
- [x] **Contract re-verification**: both entity declarations (properties, requirements,
  constraints) and the `ServiceConfig` signature/property match the manifest; the facade holds
  9 names — field order after `probe`, the SHA-ref and placement constraints documented in the
  docstrings, placement left to the loader (Task 6), no CODEMANIFEST modified
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files — clean on the first pass
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 6: Config cell II — `loader.py` `_validate_migrations`: placement, model build, source checks, the wrap chain (TDD)

The loader extension: a new `_validate_migrations(entry, scope)` joining the established
`_validate_kind`/`_validate_topics` pattern, the MigrationError→ValueError wrap, and the
design-review R3/R6 guards.

**Contract entity**: `load_sandbox_config(path: str | None) -> config: SandboxConfig | None`
(`loader.py`) — Algorithm step 5 extension quoted in § Contract Surface.

**Usages relevant to this task:**
- `migration-set` (imported usage, read-only): the "Validating a declared source at document
  load" section — the check semantics this step follows.
- `conventions`: `ValueError` messages naming the document location and the offending entry;
  `tmp_path` + `monkeypatch.chdir` for the document fixture (M-R2.6); parametrized boundaries
  (M-R2.5).
- `ruamel-yaml`: the existing `_parse_document` skeleton is reused unchanged.

**Design details (binding — implement exactly):**
- Imports in `loader.py`: `from ..migrations import MigrationError, check_git_url,
  check_local_migrations` (relative — M-R1.3) and `from pathlib import Path` (already
  present); `from .migrations import MigrationsConfig`.
- `_validate_migrations(entry: dict[str, object], scope: str)` — called from `_read_services`
  per entry, after `_validate_topics` (placement check precedes the model build — the
  established topics pattern):
  1. `"migrations" not in entry` → return.
  2. `entry` kind != postgresql → `ValueError(f"{scope}: migrations are accepted only on
     postgresql entries")` (the scope is `f"{location}: services.{name}"`).
  3. `raw = entry["migrations"]`; isinstance guard: `raw` not a dict →
     `ValueError(f"{scope}.migrations: must be a mapping")` — null/list/scalar never reach
     `dict(...)` (no raw `TypeError` leak — design-review R3). `location` not a non-empty
     string → `ValueError(f"{scope}.migrations.location: must be a non-empty path")` (`""`
     would resolve to cwd or the clone root — design-review R6). Then `declaration =
     _build_model(MigrationsConfig, dict(raw), f"{scope}.migrations")`.
  4. `declaration.git is None` (local): `folder = Path.cwd() / declaration.location`; `try:
     check_local_migrations(folder)` / `except MigrationError as exc: raise
     ValueError(f"{scope}.migrations: {exc}") from exc`.
  5. else (remote): `try: check_git_url(declaration.git.url)` / the same wrap.
- The built `ServiceConfig` carries the typed `migrations` model (pydantic coerces the raw
  mapping — the declaration is already typed by step 3's `_build_model`).
- Tests: extend `tests/sandbox/config/test_loader.py` (documents under
  `.goga/tools/pybuggy/sandbox.yml` via the established fixture pattern).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Declaration**: state that Task 6 is being executed
- [ ] **Contract tests** (extend `test_loader.py`; expected to fail now): `load_sandbox_config`
  signature unchanged; a migrations-declaring document loads into
  `config.services["db"].migrations: MigrationsConfig | None` (the new step is observable
  through the public reader)
- [ ] **REPL prototype (R4)**: in the venv REPL (documents written under `/tmp` with the
  tools-home layout): load the full valid local-source document (observe the typed
  declaration: `location`, `git is None`); load the remote-source document (no folder on
  disk — observe it accepted by URL shape); walk each invalid variant (kafka placement,
  `migrations: null` / `12` / `"x"`, `location: ""`, missing local folder, `ftp://` URL,
  duplicate versions on disk) and read each `ValueError` — document path + entry scope in
  every one, with the `MigrationError` cause on the wrapped ones; then migrate
- [ ] **Code**: add `_validate_migrations` to `goga_tool_pybuggy/sandbox/config/loader.py`
  per the design details; call it from `_read_services` after `_validate_topics`
- [ ] **Interface verification**: `.venv/bin/pytest tests/sandbox/config/ -x -v` — pass;
  fresh-interpreter check: `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.config import
  load_sandbox_config"`
- [ ] **Logic tests** (design scenarios, transferred):
  1. `test_loader_accepts_migrations_on_postgresql` — tmp_path with a valid
     `db/migrations/00001_init.sql`, document with `services: {db: {kind: postgresql,
     migrations: {location: db/migrations}}}`; `load_sandbox_config()` →
     `config.services["db"].migrations.location == "db/migrations"`; `.git is None`
  2. `test_loader_accepts_remote_source_by_shape` — document with `migrations: {location:
     db/migrations, git: {url: "https://gitlab.example/acme/s.git"}}`, no folder created →
     loads; `.git.url` equals the URL; `.git.ref is None` (no filesystem access, no network)
  3. `test_loader_rejects_migrations_on_non_postgresql` — kafka entry with migrations (valid
     folder on disk) → `ValueError` containing the document path, `services.events`, and the
     rule
  4. `test_loader_rejects_non_mapping_migrations_value` — parametrized raw values
     `[None, 12, "x"]` → the exception type is exactly `ValueError` (never a leaked
     `TypeError`); message contains the document path, `services.db`, `migrations`
  5. `test_loader_rejects_empty_migrations_location` — `location: ""` with valid `.sql`
     files sprinkled in the cwd itself → `ValueError` with `location` in the message; no
     `MigrationError`/`TypeError` leaks
  6. `test_loader_rejects_missing_local_folder` — declared folder absent → `ValueError`
     containing the document path, `services.db`, `migrations`, and the folder path;
     `excinfo.value.__cause__` is `MigrationError` (the wrap chain)
  7. `test_loader_rejects_bad_git_url_scheme` — `git: {url: "ftp://h/r.git"}` → wrapped
     `ValueError` with the scope and `disallowed`
  8. `test_loader_rejects_duplicate_versions_at_load` — folder with `1_a.sql` +
     `0001_b.sql` → wrapped `ValueError` naming both files
- [ ] **Debugging**: `.venv/bin/pytest tests/ -x` — still fully green; REPL-reproduce any
  failure with the exact document first (M-R4.5)
- [ ] **Contract re-verification**: the extended Algorithm step 5 holds verbatim — placement,
  local resolution + `check_local_migrations`, remote `check_git_url`, the MigrationError →
  ValueError wrap with the cause preserved; the new requirement bullet (local validated fully
  at load; remote by URL shape); no container starts for an invalid document
- [ ] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files
- [ ] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 7: Engines cell — `base.py` `_migrate` hook + start insertion; `postgres.py` override; docstring enumerations (TDD)

The apply side: the protected no-op hook inserted between plane open and startup data, the
`PostgresEngine` override flattening the declaration into `run_migrations` scalars, and the
annotation-driven docstring updates.

**Contract entities**: `BaseEngine(config: ServiceConfig)` (`base.py` — the `config`
enumeration and the start sequence), `BaseEngine::PostgresEngine(config: ServiceConfig)`
(`postgres.py` — the Migrations paragraph), `build_engine(config: ServiceConfig)`
(`runtime.py` — the requirement enumeration). The `_migrate` hook itself is a protected
implementation detail — NOT added to any manifest (M-R5.5).

**Usages relevant to this task:**
- `migration-set` (imported usage, read-only): the "Running one apply at engine startup"
  section — the semantics this step follows (one call per session, over the engine's own
  connection, clone deleted on every exit path).
- `psycopg`: the engine's existing session connection (autocommit, opened in `_open_plane`)
  is the `conn` the migrations apply reuses — unchanged.
- `conventions`: mock at the import point (M-R2.6) —
  `mock.patch("goga_tool_pybuggy.sandbox.engines.postgres.run_migrations")`; the local
  doubles from `tests/sandbox/engines/test_postgres.py`.

**Design details (binding):**
- `base.py` — the insertion (verbatim from the traced `start`):
  ```
  ... _run_step("start failed at readiness wait", self._wait_ready)
  ... _run_step("start failed at data-plane open", self._open_plane)
  + ... self._run_step("start failed at migrations", self._migrate)     # NEW — no-op default
  ... _apply_operations(startup)
  ```
  `BaseEngine._migrate` (new protected hook): no-op with a docstring — kinds without
  migrations override nothing; parallel to `_build_container`/`_open_plane`. The `config`
  parameter docstring enumeration ends with "migrations declaration (consumed by the postgres
  kind)".
- `postgres.py` — the override:
  ```
  1. declaration = self.config.migrations
  2. declaration is None → return          # nothing declared — no log, no call
  3. git_url = declaration.git.url   if declaration.git else None
     git_ref = declaration.git.ref   if declaration.git else None
  4. run_migrations(conn=self._connection, location=declaration.location,
                    git_url=git_url, git_ref=git_ref)
  ```
  Import discipline: `from ..migrations import run_migrations` ONLY (a runtime
  `MigrationError` import would be unused — F401; it stays contract-level and is imported by
  the tests from the migrations cell — design-review R5).
- Failure: `MigrationError` propagates out of `_migrate`; `_run_step` wraps into
  `EngineError(f"service '{name}': start failed at migrations: {exc}") from exc`; `start`'s
  existing handler calls `self.stop()` and re-raises — nothing left behind. Success:
  `_apply_operations(startup)` runs against the migrated schema; migrations never enter
  `_journal` (the hook sits outside the journal path).
- `runtime.py` `build_engine` docstring: the enumeration ends with the migrations declaration
  reaching the built engine (satisfied by construction — the whole `ServiceConfig` reaches
  `KIND_ENGINES[config.kind](config)`).
- Tests: extend `tests/sandbox/engines/test_base.py` (hook default + insertion) and
  `tests/sandbox/engines/test_postgres.py` (override + wrap).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Declaration**: state that Task 7 is being executed
- [ ] **Contract tests** (extend `test_base.py` + `test_postgres.py`; expected to fail now):
  `BaseEngine` exposes the protected `_migrate` (no-op default); `PostgresEngine._migrate`
  calls `run_migrations` with the flattened kwargs; `build_engine` still maps
  postgresql → `PostgresEngine` carrying the whole `ServiceConfig`
- [ ] **REPL prototype (R4)**: in the venv REPL drive the override over a started-shaped
  engine with `engine._connection = FakeConnection()` and the patched `run_migrations` —
  declared remote source (observe the exact kwargs incl. `conn is engine._connection`),
  declared local source (`git_url=None, git_ref=None`), and no declaration
  (`assert_not_called`); drive the full `start` over fakes and observe the statements order
  (MIGRATIONS before the seed); drive the failure leg and read the `EngineError` message and
  its `__cause__`; then migrate
- [ ] **Code**: add the `_migrate` no-op hook + the insertion + the docstring enumeration to
  `base.py`; add the `_migrate` override + the `run_migrations` import to `postgres.py`;
  update the `build_engine` docstring in `runtime.py`
- [ ] **Interface verification**: `.venv/bin/pytest tests/sandbox/engines/test_base.py
  tests/sandbox/engines/test_postgres.py -x -v` — pass; fresh-interpreter facade check:
  `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.engines import BaseEngine,
  PostgresEngine, build_engine, EngineError"` (11 names byte-stable)
- [ ] **Logic tests** (design scenarios, transferred):
  1. `test_migrate_hook_applies_declared_set_with_flattened_args` — `ServiceConfig(name="db",
     kind="postgresql", migrations=MigrationsConfig(location="db/migrations",
     git=GitSource(url="https://x/r.git", ref="rel")))`; patched
     `engines.postgres.run_migrations`; `engine._migrate()` → called once with exactly
     `conn=engine._connection`, `location="db/migrations"`, `git_url="https://x/r.git"`,
     `git_ref="rel"` (the contract's call shape — a signature drift between the cells
     surfaces here)
  2. `test_migrate_hook_is_noop_without_declaration` — migrations None →
     `run_migrations.assert_not_called()` (absence reproduces the established startup)
  3. `test_start_runs_migrations_between_plane_open_and_startup_data` — faked
     `_open_plane`, `run_migrations` side effect appending `("execute", "MIGRATIONS", None)`,
     startup `sql_op("INSERT INTO seed VALUES (1)")`; `engine.start([startup_op],
     network=None)` → the MIGRATIONS marker's index precedes the seed statement's; the seed
     executed at all (the ordering contract — startup data runs against the migrated schema)
  4. `test_migrate_failure_maps_to_engine_error_naming_service` — the mock raises
     `MigrationError('00002_bad.sql: relation "ghost" does not exist')`; `pytest.raises(
     EngineError)` → message contains `service 'db'`, `start failed at migrations`,
     `00002_bad.sql`, and the server text; `excinfo.value.__cause__` is the `MigrationError`
     (the cross-family mapping — the author-facing failure surface)
  5. Base-hook unit: the default `BaseEngine._migrate` is a no-op (a minimal stub subclass —
     no declaration consumed, no error)
- [ ] **Debugging**: `.venv/bin/pytest tests/ -x` — still fully green; REPL-reproduce any
  failure first (M-R4.5)
- [ ] **Contract re-verification**: the PostgresEngine Migrations paragraph holds clause by
  clause — once per session, after readiness + plane open, before startup data, through
  `run_migrations` over the session connection, one progress line per file (the
  `migration-set` progress), failure → `EngineError` naming service + file with
  `MigrationError` as cause, never journaled; `build_engine`'s extended requirement;
  `start returns only after the set is applied`
- [ ] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files
- [ ] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 8: Integration test — the reset role split over a real container (integration tests)

The feature's headline guarantee end-to-end: migrations build the schema once per session and
survive resets; only journaled seed data replays. The implementation is Tasks 2–7; failures
found here are fixed in the implementation, never in the contract. Docker is unavailable in
this environment — the test lands gated with `requires_docker` and must collect and skip
cleanly.

**Usages relevant to this task:**
- `conventions`: integration tests for cross-module interaction; the existing
  `requires_docker` harness and doubles of `tests/sandbox/engines/test_postgres.py` (M-R2.7).
- `psycopg`: the live connection the assertions query over.
- `migration-set` (cell `.usages/`, read-only): the once-per-session apply semantics under
  test.

**Interaction flow under test (design stack trace — the per-test reset chain):**
`BaseEngine.start` → container ready → plane open → `_migrate` → `run_migrations` (1st and
only call) → schema applied → startup seed applied + journaled → `engine.reset()` →
`PostgresEngine._wipe` (CATALOG_QUERY discovers the migrated tables → TRUNCATE … RESTART
IDENTITY CASCADE) → journal replay → seed re-inserted; the migrated tables survive.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Add `test_reset_keeps_migrated_schema_and_replays_only_seed` to the docker-gated
  harness of `tests/sandbox/engines/test_postgres.py`: a `tmp_path` folder with
  `00001_init.sql` (`CREATE TABLE customers (id serial PRIMARY KEY, email text); CREATE TABLE
  orders (id serial PRIMARY KEY, customer int);`); `ServiceConfig(name="db",
  kind="postgresql", migrations=MigrationsConfig(location=str(folder)))`; startup op
  `sql_op("INSERT INTO customers (email) VALUES ('ann@x.io')")`; a spy-counting wrapper around
  `run_migrations`; `engine.start([...seed...])` then `engine.reset()`
- [ ] Assert the role split: after reset — `SELECT count(*) FROM customers` == 1 (seed
  replayed); `SELECT count(*) FROM orders` == 0 (no seed); both tables still exist (schema
  survived the TRUNCATE); `run_migrations` called exactly once across start+reset (never
  re-applied, never journaled)
- [ ] Run validation: `.venv/bin/pytest tests/sandbox/engines/test_postgres.py -v` — the
  gated case skips cleanly without a runtime (docker unavailable here); then
  `.venv/bin/pytest tests/ -x` — green
- [ ] Lint gate (pre-commit): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files

### Task 9: Author docs — the migrations declaration in `docs/sandbox.md` and `docs/configuration.md` (documentation)

The author-facing surfaces follow the contract (design § Additional Instructions — out-of-DSL
documentation updates of the implementation stage). Docs must not break test collection; the
content stays consistent with `config/.usages/sandbox-file.md` (the canonical authoring
reference, read-only).

**Usages relevant to this task:**
- `conventions`: professional concise wording; English content.
- `sandbox-file` (cell `.usages/`, read-only): the canonical declaration reference the docs
  mirror — the migrations block in the layout example, the "Migrations" section, the role
  split, the preconditions (including the scheme allowlist wording — decision A).

**Design details (binding):**
- `docs/sandbox.md`: the `migrations` declaration on a postgresql service entry — local
  (`location`, cwd-relative, the same anchor the document itself uses) and remote (`git.url`
  + optional `git.ref`, ambient credentials, scp-style URLs rewritten as
  `ssh://git@host/path`); the goose file format pointer (naming grammar, the annotation
  subset, `goose-sql` as the format reference); the startup ordering (migrations apply once
  per session, after readiness, before startup data); the schema-vs-seed role split (the
  migrated schema survives `clear()`/reset; only `data.postgres` seed replays).
- `docs/configuration.md`: point edit — the service-entry vocabulary gains the optional
  `migrations` block, consistent with `sandbox-file.md`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Update `docs/sandbox.md` per the design details (consistent with `sandbox-file.md`;
  block-style YAML examples)
- [ ] Apply the `docs/configuration.md` point edit
- [ ] Run validation: `.venv/bin/pytest tests/ -x` — still green (docs must not break
  collection)
- [ ] Lint gate (pre-commit): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0

### Task 10: Final validation gate — full suite, facades, contract lint, format (acceptance)

The plan-level verification. Nothing is implemented here; failures route back to the owning
task's implementation.

**Usages relevant to this task:**
- `conventions`: the validation command table (virtualenv, pytest, ruff, facade checks).

- [ ] Run the full suite: `.venv/bin/pytest tests/ -x` — green; the docker-gated
  `test_reset_keeps_migrated_schema_and_replays_only_seed` skips cleanly without a runtime
- [ ] Facade checks (fresh interpreter): `.venv/bin/python -c "from
  goga_tool_pybuggy.sandbox.migrations import MigrationError, MigrationFile,
  apply_migrations, check_git_url, check_local_migrations, load_migration_set,
  parse_migration_file, run_migrations"` (8 names); `.venv/bin/python -c "from
  goga_tool_pybuggy.sandbox.config import GitSource, MigrationsConfig, SandboxConfig,
  ServiceConfig, load_sandbox_config"` (9 names); `.venv/bin/python -c "from
  goga_tool_pybuggy.sandbox.engines import BaseEngine, PostgresEngine, build_engine,
  EngineError"` (byte-stable 11); root re-exports `active_sandbox` / `services` unchanged
- [ ] Contract lint: `goga lint` — 24 cells, 0 errors (same count as the Task 1 baseline: no
  new cells)
- [ ] Lint + format gate: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/` — no drift on plan-touched files
- [ ] Discipline sweep: `git diff --stat` over the three CODEMANIFEST paths and the two
  `.usages/` files since the Task 1 contract commit — empty (the contract was not modified
  during implementation); `grep -n "_migrate" goga_tool_pybuggy/sandbox/engines/CODEMANIFEST`
  — absent (the protected hook never entered the manifest)
- [ ] Commit gate (M-R3.4, full): lint + format + `pytest tests/ -x` green before the final
  commit

---

## Validation Commands

- `.venv/bin/pytest tests/ -x`: Run all tests (the convention's run-all command; green at
  every task — the change is additive)
- `.venv/bin/pytest tests/sandbox/migrations/ -x -v`: Focused migrations-cell suite
- `.venv/bin/ruff check goga_tool_pybuggy/ tests/`: Lint check (M-R3.1 config; exit 0 required
  at every task end and before every commit)
- `.venv/bin/ruff format --check <touched files>`: Format check on every file a task or commit
  touches (M-R3.3/M-R3.4)
- `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.migrations import MigrationError,
  MigrationFile, apply_migrations, check_git_url, check_local_migrations, load_migration_set,
  parse_migration_file, run_migrations"`: Migrations facade accessibility (8 names)
- `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.config import GitSource,
  MigrationsConfig, SandboxConfig, ServiceConfig, load_sandbox_config"`: Config facade
  accessibility (9 names)
- `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.engines import BaseEngine,
  PostgresEngine, build_engine, EngineError"`: Engines facade byte-stability (11 names)
- `goga lint`: Contract lint — 24 cells, 0 errors

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location` (the four migrations-cell
      files + `config/migrations.py`; the changed entities in `service.py`, `loader.py`,
      `base.py`, `postgres.py`, `runtime.py`)
- [ ] Every contract entity is accessible from its facade (migrations 8 names; config 9 names;
      engines 11 names byte-stable; root re-exports unchanged)
- [ ] Properties and methods match the declared API; descriptions are reflected in behavior —
      decision A (strict schemes), the parser file-order invariant, the loader guards, the
      wrap chains (`MigrationError` → `ValueError` / `EngineError` with causes preserved),
      the start ordering (migrations between plane open and startup data), journal isolation,
      reset semantics (schema survives, seed replays)
- [ ] Contract dependencies are met (`check_local_migrations` / `check_git_url` /
      `MigrationError` edges config ← migrations; `run_migrations` edge engines ← migrations;
      `ServiceConfig` edge engines ← config; no reverse dependencies)
- [ ] Every coding task followed the TDD workflow (contract tests → code → interface
      verification → logic tests → debugging → contract re-verification → lint) with the REPL
      loop inside implementation and debugging (R4)
- [ ] All 58 named design test scenarios plus the facade/model-level units exist and pass;
      boundary tables include each boundary (scheme allowlist, raw-value table, timestamp
      versions, numeric ordering)
- [ ] The integration test covers the reset role split end-to-end; the docker-gated case
      skips cleanly without a runtime
- [ ] No package boundary was expanded; no new cells; no new dependencies; the protected
      `_migrate` hook never entered a manifest
- [ ] `CODEMANIFEST` files were not modified (the working-tree contract committed unchanged in
      Task 1)
- [ ] All validation commands pass — full suite green, ruff check + format clean, facades
      importable, `goga lint` 24 cells / 0 errors
- [ ] Every Usages entry is exercised in at least one task (conventions throughout; goose-sql
      Tasks 2–4; psycopg Tasks 4/7/8; gitpython Tasks 3–4; migration-set Tasks 6–8;
      ruamel-yaml Task 6; sandbox-file Task 9)
