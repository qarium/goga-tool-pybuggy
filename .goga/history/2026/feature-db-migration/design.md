# Design Document: `feature-db-migration`

Sandbox DB migrations — goose-format SQL applied once per session by a built-in up-only runner.
Contract basis: the CODEMANIFEST changes applied by the `apply-architecture` stage (new cell
`goga_tool_pybuggy/sandbox/migrations`, modified `sandbox/config` and `sandbox/engines`),
derived from `.goga/history/2026/feature-db-migration/arch.md`.

## Contract Changes

### Changed CODEMANIFEST Files

- `goga_tool_pybuggy/sandbox/migrations/CODEMANIFEST` — **created**. Leaf cell, no Imports.
  Declares 8 contract types: `MigrationFile`, `MigrationError`, `check_local_migrations`,
  `check_git_url`, `parse_migration_file`, `load_migration_set`, `apply_migrations`,
  `run_migrations` across `goose.py`, `errors.py`, `source.py`, `apply.py`.
- `goga_tool_pybuggy/sandbox/config/CODEMANIFEST` — **modified**. Imports block added
  (`check_local_migrations`, `check_git_url`, `MigrationError`, usage `migration-set` from the
  migrations cell); new types `GitSource` and `MigrationsConfig` (module `migrations.py`);
  `ServiceConfig` gains the `migrations` parameter and property; `load_sandbox_config`
  algorithm/requirements/practice bindings extended (a `MigrationError` from the checks is
  wrapped into the reader's ValueError with the cause preserved — design-review fix).
- `goga_tool_pybuggy/sandbox/engines/CODEMANIFEST` — **modified**. Second Imports entry
  (`run_migrations`, `MigrationError`, usage `migration-set` from the migrations cell);
  `BaseEngine::PostgresEngine` annotations replaced with the migrations-aware version;
  `BaseEngine` `config` enumeration and `build_engine` requirement extended.

### New Entities

- `MigrationFile(version, filename, statements, no_transaction)` — one parsed goose-format
  migration file, the apply-ready unit (`migrations/goose.py`).
- `MigrationError` — the failure family of the migrations domain, `RuntimeError` subtype
  (`migrations/errors.py`).
- `check_local_migrations(folder: Path)` — load-time shape checks of a local migrations folder
  (`migrations/source.py`).
- `check_git_url(url: str)` — load-time git URL shape validation (`migrations/source.py`).
- `parse_migration_file(filename, text) -> MigrationFile` — pure goose-SQL parser
  (`migrations/goose.py`).
- `load_migration_set(folder) -> list[MigrationFile]` — folder → ordered apply-ready set
  (`migrations/goose.py`).
- `apply_migrations(conn, migrations)` — execute the parsed set over the postgres connection
  (`migrations/apply.py`).
- `run_migrations(conn, location, git_url, git_ref)` — source resolution + load + apply
  orchestration (`migrations/apply.py`).
- `GitSource(url, ref)` — the remote source declaration model (`config/migrations.py`).
- `MigrationsConfig(location, git)` — the migrations declaration model (`config/migrations.py`).

### Changed Entities

- `ServiceConfig` — signature gains `migrations: MigrationsConfig | None`; property
  `migrations -> MigrationsConfig | None` added; parameter documented (postgresql-only,
  enforced at document load).
- `load_sandbox_config` — algorithm step 5 extended: placement check (postgresql only), local
  source resolved against cwd and passed through `check_local_migrations`, remote URL passed
  through `check_git_url`; requirement bullet and `migration-set` practice binding added.
- `BaseEngine` — annotations only: the `config` parameter enumeration ends with
  "migrations declaration (consumed by the postgres kind)".
- `BaseEngine::PostgresEngine` — annotations replaced: Migrations paragraph (apply once per
  session after readiness + plane open, before startup data; through `run_migrations` from
  Imports; progress line per file; failure → engine error type with `MigrationError` as cause;
  never journaled) + requirement "start returns only after the set is applied".
- `build_engine` — requirement bullet extended: the migrations declaration of `config` reaches
  the built engine.

### Deleted Entities

- None.

### Usages and Annotations Changes

- `.goga/usages/cooks/goose-sql.md` — **created**: the migration file format (naming grammar,
  the five supported annotations, statement-body rules, out-of-subset behavior, set-consumption
  semantics).
- `.goga/usages/cooks/gitpython.md` — **modified**: generalized to two consumers (endpoint pull
  and the sandbox migrations source); sandbox consumer block (consume in place, ambient
  credentials, `ref` semantics); error mapping per consumer family.
- `.goga/usages/cooks/psycopg.md` — **modified**: "Migrations — executing parsed goose SQL
  bodies" section (parameter-free DDL, transaction-per-file, autocommit opt-out, failure
  surfacing with `.diag.message_primary`).
- Cell-level usages: `migrations/.usages/migration-set.md` — **created**;
  `config/.usages/sandbox-file.md` — **replaced** (migrations block in the layout example,
  "Migrations" section, role split, updated preconditions).
- Annotations: practice bindings added — `goose-sql`/`psycopg`/`gitpython` across the
  migrations cell; `migration-set` from Imports in `load_sandbox_config` and
  `BaseEngine::PostgresEngine`.

## Applied Fixes

### Fixed CODEMANIFEST Defects

- None. Static validation is clean: `goga lint` reports 24 cells, 0 errors; all four
  consistency dimensions pass (interface↔type, type↔mutation — no new mutations or embeddings,
  interface↔interface, annotations↔entity); `Imports` form no cycle (migrations is a leaf).

### Resolved Ambiguities (user decisions)

- **scp-style git URLs in `check_git_url`** — decision **A (strict)**: the manifest's literal
  algorithm wins. A URL must parse with an explicit scheme among `https`, `http`, `git`,
  `ssh`; an scp-style URL (`git@github.com:acme/service.git`) parses with an empty scheme and
  is **rejected** at document load with a "disallowed scheme" error naming the URL and the
  allowlist. This intentionally diverges from `endpoint pull`'s effective empty-scheme bypass;
  authors rewrite scp-style URLs as `ssh://git@host/path`. No CODEMANIFEST edit required — the
  recorded rule is a faithful reading of the existing algorithm text.

## Entity Interaction and Data Flow

### Interaction Diagram

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

### Data Flows

- **Declaration flow**: `sandbox.yml` `services.<name>.migrations` (raw mapping) →
  `MigrationsConfig(location: str, git: GitSource | None)` → stored on
  `ServiceConfig.migrations` → consumed by `PostgresEngine` via `self.config.migrations`.
- **Load-time check flow (local)**: `location` → `Path.cwd() / location` →
  `check_local_migrations(folder: Path)` → raise-only (`MigrationError`) → loader wraps into
  `ValueError` with the document location and entry scope.
- **Load-time check flow (remote)**: `git.url` → `check_git_url(url: str)` → raise-only →
  same wrap. No network at load.
- **Apply flow**: flattened scalars only — `run_migrations(conn, location, git_url, git_ref)`
  (the leaf cell takes primitives, not `GitSource`) → resolved `folder: Path` →
  `load_migration_set` → `list[MigrationFile]` ordered by version → `apply_migrations` over
  the engine's per-session autocommit `psycopg.Connection`.
- **Error flow**: deepest failure (psycopg statement error / git clone error / shape check) →
  `MigrationError` (names file or source step + cause) → engine `_run_step` → `EngineError`
  (names service + lifecycle step) with `MigrationError` as `__cause__`. In the config cell:
  `MigrationError` → `ValueError` (names document location + entry).

### Entity Dependencies

- `goga_tool_pybuggy/sandbox/migrations` — leaf; depends on stdlib + third-party only
  (pydantic, psycopg, gitpython). Designed and implemented first.
- `goga_tool_pybuggy/sandbox/config` — imports `check_local_migrations`, `check_git_url`,
  `MigrationError` + usage `migration-set` from migrations (Python:
  `from ..migrations import check_git_url, check_local_migrations, MigrationError`).
- `goga_tool_pybuggy/sandbox/engines` — imports `ServiceConfig` from config (existing) and
  `run_migrations`, `MigrationError` + usage `migration-set` from migrations. Python-level:
  `postgres.py` imports only `run_migrations` (`from ..migrations import run_migrations`) — the
  error wrap is the generic `_run_step`, so a runtime import of `MigrationError` would be unused
  (F401); it stays a contract-level reference in the CODEMANIFEST annotations and is imported
  directly from the migrations cell by the engine tests.
- Initialization order at runtime: `load_sandbox_config` (checks) → `build_engine` (carries the
  declaration) → `BaseEngine.start` → `_migrate` hook → `run_migrations`.
- No reverse dependencies; `sandbox/` (session runtime), `sandbox/data/`, `plugin/` untouched.

## Code Stack Trace

### Trace: `load_sandbox_config` (migrations path)

#### Chain

1. **Input**: pytest session start reads `.goga/tools/pybuggy/sandbox.yml`; a service entry
   carries `migrations: {location: db/migrations}` or `migrations: {location: ..., git: {url, ref}}`.
2. `_read_services` iterates entries; per entry calls `_validate_kind`, `_validate_topics`,
   then the new `_validate_migrations(entry, scope)` → checkpoint: placement check precedes the
   model build, mirroring the established topics pattern (loader-level, not a model validator —
   matches `MigrationsConfig`'s "placement is checked at document load").
3. `_validate_migrations`: absent key → return; `kind != "postgresql"` →
   `ValueError(f"{scope}: migrations are accepted only on postgresql entries")` → checkpoint:
   message names document location + entry ✓ (scope is `f"{location}: services.{name}"`).
4. `_build_model(MigrationsConfig, dict(declaration), f"{scope}.migrations")` → pydantic
   kw_only + `extra="forbid"` reject unknown keys with the scope-named error → checkpoint:
   `location: str` required; `git` parses into `GitSource(url: str, ref: str | None = None)`.
5. Local source (`git is None`): `folder = Path.cwd() / location`; call
   `check_local_migrations(folder)` inside `try/except MigrationError as exc: raise
   ValueError(f"{scope}.migrations: {exc}") from exc` → checkpoint: input type `Path` matches the contract
   signature; the wrap preserves the document location and entry, and keeps the cause chain ✓.
6. Remote source: `check_git_url(migrations.git.url)` with the same wrap → checkpoint: input
   `str` ✓; no network access at load ✓.
7. `ServiceConfig` build via `_build_model` — the raw `migrations` mapping is already the typed
   model (or passes the raw dict; pydantic coerces either way) →
   **Output**: `SandboxConfig.services[name].migrations: MigrationsConfig | None` — validated
   (local: on disk; remote: URL shape), `None` when undeclared.

#### Checkpoint Summary

- Placement before parse: passed (fail-fast, mirrors topics handling).
- `MigrationError` → `ValueError` wrap: passed (load failures stay in the reader's family;
  contract boundary isolation — the reader decides how to react to the provider's raises).
- Type flow `str → Path` (local) / `str` (remote): passed.

### Trace: `check_local_migrations`

#### Chain

1. **Input**: `folder: Path` — already resolved against cwd by the caller.
2. `folder.is_dir()` false (missing or a file) → `MigrationError` naming the folder and the
   failed check → checkpoint: "must exist and be a folder" ✓.
3. `list(folder.iterdir())` empty → raise naming folder → checkpoint: "must not be empty" ✓.
4. `sql_files = [p for p in folder.iterdir() if p.is_file() and p.suffix == ".sql"]` (files
   only; non-.sql ignored everywhere, subdirectories never join the version set) — empty →
   raise naming folder → checkpoint ✓.
5. Grammar pass: every `.sql` filename must match `^(\d+)_(.+)\.sql$`; a non-matching name →
   raise naming the folder **and the file** → checkpoint: the grammar is the same one
   `parse_migration_file` applies (single source — a shared module-level regex); failing it at
   load keeps fail-fast parity with apply-time parsing ✓ (design-level rule; the contract's
   "unique numeric version prefixes" presumes a defined grammar).
6. Uniqueness: `versions = [int(m.group(1)) ...]`; a duplicate int → raise naming the folder
   and both files → checkpoint: numeric comparison (`00001` and `1` collide) ✓.
7. **Output**: returns `None` (raise-only routine).

#### Checkpoint Summary

- Shape checks only — no file content read: passed (`Constraints: Do not read file contents`).
- Errors name folder + failed check: passed.

### Trace: `check_git_url`

#### Chain

1. **Input**: `url: str` as declared.
2. `parsed = urllib.parse.urlparse(url)`; `parsed.scheme not in {"https", "http", "git", "ssh"}`
   → raise `MigrationError` naming the URL and the allowlist → checkpoint: empty scheme
   (scp-style `git@host:path`) fails here — **user decision A** ✓; `file://`, `ftp://` fail ✓.
3. Embedded credentials: `"@" in parsed.netloc and parsed.scheme != "ssh"` → raise naming the
   URL → checkpoint: `https://user:token@host` and `https://user@host` rejected;
   `ssh://git@host/...` accepted (an ssh username is not a credential) ✓ — same rule shape as
   `endpoint pull`'s `_validate_git_url`.
4. **Output**: returns `None`. No network, no clone.

#### Checkpoint Summary

- Shape only, parity of rule structure with pull (modulo the decision-A scheme strictness):
  passed.

### Trace: `parse_migration_file`

#### Chain

1. **Input**: `filename: str` (e.g. `00003_create_orders.sql`), `text: str` (file content).
2. Grammar: `^(\d+)_(.+)\.sql$` on `filename` → `version = int(prefix)`; no match → raise
   naming the file → checkpoint: covers sequential (`00003`) and timestamp
   (`20230102103456`) styles ✓.
3. Line scan (`text.splitlines()`) with three regions — **header** (before Up), **up** (Up →
   Down), **down** (excluded):
   - An annotation line is one whose stripped form matches `^--\s*\+goose\s+(.+?)\s*$`.
   - Header: `NO TRANSACTION` → `no_transaction = True`; `Up` → switch region; `Down` or
     `StatementBegin`/`StatementEnd` or any other token → raise naming the file (Down before
     Up means no Up section) → checkpoint: "NO TRANSACTION when declared before the Up
     section" ✓; unsupported annotations fail, never silently misapply ✓.
   - Up: non-annotation lines accumulate into a fragment buffer. `StatementBegin` → flush the
     fragment buffer through the semicolon split **now** — the finished pieces append to
     `statements` before the body opens, so `statements` follows file order exactly even when
     plain statements and bodies interleave (a plain `CREATE TABLE` before a function body
     stays before it) — and switch to body mode; body lines accumulate verbatim;
     `StatementEnd` → the stripped body becomes one statement as-is (interior semicolons never
     split it) → checkpoint ✓. `StatementEnd` without an open body, `NO TRANSACTION` or a
     second `Up` here, or any other token → raise naming the file → checkpoint ✓. `Down` →
     stop scanning (the rest of the file is excluded; the buffer tail flushes after the loop).
   - Down region: excluded wholesale — unknown annotations and `{{...}}` inside Down do not
     raise → checkpoint: "the Down section is skipped — parsed only far enough to be excluded" ✓.
4. Unclosed `StatementBegin` at end of the Up region → raise naming the file ✓.
5. Semicolon split of the fragment buffer (outside bodies): `buffer.split(";")`; each piece is
   stripped; a piece that is empty or comment-only (every line stripped starts with `--`) is
   dropped; any other piece becomes one statement **without** the terminating semicolon
   (postgres accepts a statement without a trailing `;`). The split runs at every flush — at
   `StatementBegin` and on the remaining tail after the scan — so `statements` preserves file
   order and a fragment lacking a trailing `;` before a body never merges with the fragment
   after it → checkpoint: bodies containing semicolons inside strings outside
   `StatementBegin/End` are the author's responsibility — the same constraint goose itself
   has ✓.
6. Interpolation guard: `{{` occurring anywhere in header+up text → raise naming the file →
   checkpoint: unexpanded goose variables would apply literally-wrong SQL — never a silent
   misapply ✓.
7. **Output**: `MigrationFile(version=..., filename=..., statements=[...],
   no_transaction=...)` — statements ready to execute as given.

#### Checkpoint Summary

- Pure function, no I/O: passed (the caller reads the file).
- Statement bodies opaque (no SQL semantics validated): passed.
- Every failure names the file: passed.

### Trace: `load_migration_set`

#### Chain

1. **Input**: `folder: Path` — a local folder or a path inside a resolved clone.
2. `sql_files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix == ".sql")`
   → checkpoint: non-`.sql` ignored ✓.
3. Empty `sql_files` → raise naming the folder ✓.
4. Grammar + duplicate-version check (same shared regex/int extraction as
   `check_local_migrations`) → violations raise naming the folder and the file(s) ✓ — the
   apply-time re-check covers remote sources that never passed the load-time check.
5. `parse_migration_file(p.name, p.read_text(encoding="utf-8"))` per file → checkpoint: the
   routine reads the content here (the parser itself stays pure) ✓.
6. `migrations.sort(key=lambda m: m.version)` — ascending numeric → checkpoint: deterministic;
   `9_` sorts before `10_` (numeric, not lexicographic); ties impossible (duplicates rejected) ✓.
7. **Output**: `list[MigrationFile]` — the apply order is exactly the returned order.

#### Checkpoint Summary

- Deterministic order: passed.

### Trace: `apply_migrations`

#### Chain

1. **Input**: `conn` — the engine's per-session `psycopg.Connection` (autocommit mode);
   `migrations` — the ordered set.
2. Per migration, in order:
   - Default: `with conn.transaction():` wraps **all** statements of the file — one commit or
     one rollback per file → checkpoint: psycopg3 `Connection.transaction()` on an autocommit
     connection opens an explicit transaction — exactly the pattern the `psycopg` cook
     documents ✓.
   - `no_transaction=True`: each statement executes directly on the autocommit connection,
     statement-by-statement, no `transaction()` block → checkpoint:
     `CREATE INDEX CONCURRENTLY` and friends cannot run inside a transaction block ✓.
   - Statement bodies execute as given: `cursor.execute(body)` — no placeholders, no
     interpolation, no symbol capture → checkpoint: parameter-free DDL per the `psycopg` cook ✓.
   - Progress: `logger.info("migration applied", extra={"migration": m.filename,
     "version": m.version})` — one structured line per applied file, the established
     startup-output style (lowercase event, contextual `extra` metadata per `conventions`;
     the surrounding engine logs carry the service context) ✓.
3. First failing statement: `except psycopg.Error as exc: raise MigrationError(
   f"{m.filename}: {primary}") from exc` where `primary = exc.diag.message_primary or
   str(exc)` → the apply stops (exception propagates; no further file runs) → checkpoint:
   message names the migration file and the server-side error; the psycopg error stays as the
   cause ✓ — mirrors `_server_message` in `engines/postgres.py` and the `psycopg` cook.
4. **Output**: returns `None`. Nothing is written to any baseline journal; no version table is
   created or read.

#### Checkpoint Summary

- Transaction-per-file default + autocommit opt-out: passed.
- Contract interaction with the engine: the engine's `_connection` is exactly the
  `conn: Connection` the contract expects (autocommit, opened in `_open_plane`) — passed.
- NO TRANSACTION partial application on failure (already-applied statements stay applied):
  documented consumer-facing behavior in `migration-set.md` — consistent.

### Trace: `run_migrations`

#### Chain

1. **Input**: `conn` (as above), `location: str`, `git_url: str | None`, `git_ref: str | None`.
2. `git_url is None` (local): `folder = Path.cwd() / location` → checkpoint: same anchor as
   the document itself (load time resolved the identical way; an absolute `location`
   overrides the anchor — pathlib `/` semantics, the author's declared intent) ✓.
3. Remote: `with tempfile.TemporaryDirectory(prefix="pybuggy-migrations-") as tmp:`
   - `target = Path(tmp)` — a fresh directory per call → checkpoint: "already-existing target
     folder is removed before cloning" holds by construction (the target never pre-exists);
     "delete the clone on every exit path" holds by the context manager (applied or failed) ✓;
     "do not cache clones across sessions" — every call downloads fresh ✓.
   - `Repo.clone_from(git_url, str(target), depth=1, branch=git_ref)`; `branch=None` omits
     `--branch` → the remote default branch → checkpoint: the `gitpython` cook's shallow-clone
     pattern ✓.
   - `except GitCommandError as exc: raise MigrationError(f"failed to clone {git_url}: {exc}")
     from exc` → checkpoint: mapped into the migrations family (not `ClickException` — the
     sandbox runs inside pytest) per the cook's error-mapping section ✓.
   - `folder = target / location`; containment: `folder.resolve().is_relative_to(target.resolve())`
     else raise naming the path → checkpoint: design-level safeguard — a `location` escaping
     the clone (`../...`) fails clearly instead of applying files from outside the clone;
     precedented by pull's `_validate_no_path_traversal` ✓.
   - `folder.is_dir()` false → raise naming the path ✓ (matches the cook's
     missing-`git.location` rule).
4. `migrations = load_migration_set(folder)` → `apply_migrations(conn, migrations)` →
   checkpoint: the composed chain matches the contract's step 4 ✓.
5. **Output**: returns `None`; the clone (when remote) is deleted at `with` exit on every path.

#### Checkpoint Summary

- Ambient credentials only (nothing embedded in the URL — enforced earlier by `check_git_url`;
  the clone relies on ssh-agent / credential helpers): passed.
- Nothing copied into the consumer repository: passed (the clone is consumed in place).

### Trace: `BaseEngine.start` / `BaseEngine::PostgresEngine._migrate`

#### Chain

1. **Input**: `BaseEngine.start(startup, network)` — the session start of one service engine.
2. Existing sequence in `base.py`: `_run_step("start failed at container build",
   _build_container)` → container start → `_wait_ready` → `_open_plane` → then the new
   `self._run_step("start failed at migrations", self._migrate)` → `_apply_operations(startup)`
   → `self._journal.extend(startup)` → checkpoint: the insert point is exactly
   "after the container reaches readiness and the data-plane connection opens, before the
   startup data operations" ✓; `_migrate` is a new protected no-op hook in `BaseEngine`
   (parallel to `_build_container`/`_open_plane` — protected hooks are implementation detail,
   not contract surface; the base's own behavior for other kinds is unchanged: the default
   hook does nothing) ✓.
3. `PostgresEngine._migrate` override:
   - `declaration = self.config.migrations`; `None` → return (nothing declared — no log, no
     call) → checkpoint: optional declaration; absence reproduces established behavior ✓.
   - Flatten: `git_url = declaration.git.url if declaration.git else None`,
     `git_ref = declaration.git.ref if declaration.git else None` → checkpoint: scalars match
     `run_migrations`'s signature; `conn = self._connection` (opened by `_open_plane`) ✓.
   - `run_migrations(conn=..., location=declaration.location, git_url=..., git_ref=...)`.
4. Failure: `MigrationError` propagates out of `_migrate`; `_run_step` wraps into
   `EngineError(f"service '{name}': start failed at migrations: {exc}") from exc` → checkpoint:
   the engine's error type names the service and (via the MigrationError message) the
   migration file; `MigrationError` is the cause ✓; `BaseEngine.start`'s `except` handler
   calls `self.stop()` and re-raises — "a failed migration stops start", nothing left behind ✓.
5. Success path: `_apply_operations(startup)` executes the startup data statements **against
   the migrated schema** on the same connection → checkpoint: ordering guarantee
   ("start returns only after the set is applied") ✓; migrations never enter `_journal` — the
   hook sits outside the journal path ✓.
6. Reset interplay (contract checkpoint): `PostgresEngine._wipe` truncates user tables
   discovered from the catalog — migrated tables are truncated (data wiped, schema survives,
   identity restarted) and only journaled data replays → checkpoint: "the migrated schema
   survives the wipe, and only journaled data replays on reset" ✓ — `TRUNCATE` keeps tables;
   nothing migration-related is in the journal; the container is never restarted.

#### Checkpoint Summary

- Sequencing: passed. Error mapping: passed. Journal isolation: passed. Reset semantics:
  passed.

### Trace: `build_engine`

#### Chain

1. **Input**: `config: ServiceConfig` (now possibly carrying `migrations`).
2. `KIND_ENGINES[config.kind](config)` — the whole declaration, migrations included, reaches
   the constructed engine → checkpoint: the extended requirement ("the migrations declaration
   of `config` reach the built engine") is satisfied by construction — no code change beyond
   the docstring enumeration ✓.
3. **Output**: the kind engine (`PostgresEngine` for postgresql).

### Trace: declaration models (`GitSource`, `MigrationsConfig`, `ServiceConfig`)

#### Chain

1. `config/migrations.py`: `GitSource(BaseModel)` `kw_only=True`, `extra="forbid"` —
   `url: str` (required), `ref: str | None = None`; `MigrationsConfig(BaseModel)` `kw_only=True`,
   `extra="forbid"` — `location: str` (required), `git: GitSource | None = None` → checkpoint:
   pydantic kw_only models per `conventions`; defaults use `None` for explicit absence ✓;
   Google-style docstrings with Attributes sections ✓.
2. `ServiceConfig` gains `migrations: MigrationsConfig | None = None` (after `probe`) →
   checkpoint: optional, backward compatible — existing documents without `migrations` parse
   identically; `extra="forbid"` still rejects unknown keys ✓.
3. Facade `config/__init__.py`: export `GitSource`, `MigrationsConfig` through `__all__` (the
   cell's public models) alongside the existing names → checkpoint: facade parity with the
   CODEMANIFEST type set ✓.
4. **Output**: typed declaration graph stored on `SandboxConfig`.

## Algorithm Design

### `check_local_migrations` (source.py)

**Responsibility**: load-time shape validation of a declared local migrations folder.

**Algorithm:**
```
1. folder.is_dir() == False
   → raise MigrationError(f"{folder}: the migrations source must be an existing folder")
2. entries = list(folder.iterdir()); entries empty
   → raise MigrationError(f"{folder}: the migrations folder is empty")
3. sql_files = [p for p in entries if p.is_file() and p.suffix == ".sql"]; empty
   → raise MigrationError(f"{folder}: the migrations folder holds no .sql files")
4. FOR each name in sql_files:
   match = FILENAME_GRAMMAR.match(name)   # ^(\d+)_(.+)\.sql$
   match is None → raise MigrationError(f"{folder}: {name}: invalid migration filename —
   expected <version>_<description>.sql")
5. versions = [int(match.group(1)) per file]; any int appears twice
   → raise MigrationError(f"{folder}: {a} and {b}: duplicate migration version {n}")
6. return None
```

**Errors:** `MigrationError` → raise-only → the config loader wraps into `ValueError` with the
document scope; test authors see a load failure before any container starts.

**Edge cases:** a file (not a folder) at the path → step 1; folder with only non-`.sql` files →
step 3; `00001_a.sql` + `1_b.sql` → step 5 (both version `1`); `00003.sql` (no description) →
step 4.

### `check_git_url` (source.py)

**Responsibility**: git URL shape validation — no network.

**Algorithm:**
```
1. parsed = urllib.parse.urlparse(url)
2. parsed.scheme not in {"https", "http", "git", "ssh"}   # empty scheme included
   → raise MigrationError(f"{url}: disallowed git URL scheme '{parsed.scheme}'
   (allowed: git, http, https, ssh)")
3. "@" in parsed.netloc and parsed.scheme != "ssh"
   → raise MigrationError(f"{url}: the git URL must not embed credentials")
4. return None
```

**Errors:** `MigrationError` → loader wraps → `ValueError`.

**Edge cases:** scp-style `git@github.com:acme/r.git` → scheme `""` → step 2 (decision A);
`ssh://git@host/r.git` → passes both steps; `https://user@host/r.git` → step 3.

### `parse_migration_file` (goose.py)

**Responsibility**: pure text transformation — one goose file → one `MigrationFile`.

**Algorithm:**
```
1. match = FILENAME_GRAMMAR.match(filename); version = int(match.group(1))
   no match → raise MigrationError(f"{filename}: invalid migration filename")
2. region = "header"; no_transaction = False; fragments = []; body = None
   FOR line in text.splitlines():
     stripped = line.strip()
     IF stripped matches ^--\s*\+goose\s+(.+?)\s*$:
       token = the captured annotation
       SWITCH region:
         "header":
           token == "NO TRANSACTION" → no_transaction = True
           token == "Up"             → region = "up"
           else                      → raise MigrationError(f"{filename}: unsupported +goose
                                        annotation '{token}' before the Up section")   # Down incl.
         "up":
           token == "StatementBegin" → statements.extend(_split_fragments(fragments));
                                        fragments.clear(); body = []   # flush BEFORE the body —
                                        # fragments and bodies append in file order
           token == "StatementEnd"   → body is None → raise (no open body)
                                        else statements.append("\n".join(body).strip()); body = None
           token == "Down"           → region = "down"; BREAK the scan
           else                      → raise MigrationError(f"{filename}: unsupported +goose
                                        annotation '{token}' in the Up section")
       # "down": unreachable — the scan stops at Down
     ELSE:
       region == "header" → ignore the line (header SQL outside Up is not applied)
       region == "up"     → body is not None ? body.append(line) : fragments-accumulator.append(line)
3. body is not None after the loop → raise MigrationError(f"{filename}: StatementBegin without
   a matching StatementEnd")
4. region == "header" after the loop → raise MigrationError(f"{filename}: no +goose Up section")
5. FOR piece in "\n".join(fragments-accumulator).split(";"):   # the tail after the last flush
     piece stripped; empty or comment-only (every line starts with "--") → drop
     else statements.append(piece.strip())

   _split_fragments(lines) — the shared flush helper (module-level in goose.py): join the
   buffered lines, split on ";", drop empty/comment-only pieces, return the stripped pieces;
   called at StatementBegin and once on the tail after the scan.
6. "{{" in (header + up text) → raise MigrationError(f"{filename}: goose {{...}} interpolation
   is not supported — migration statements apply as given")
7. return MigrationFile(version, filename, statements, no_transaction)
```

**Errors:** `MigrationError` naming the file for: filename grammar, missing Up, Down before Up,
unsupported annotation (header or up), `NO TRANSACTION` after Up (it lands in the `else` branch
of the up region), unclosed body, `StatementEnd` without begin, interpolation.

**Edge cases:** empty Up section → `statements == []` (valid; the file applies nothing and still
logs one progress line); semicolons inside `StatementBegin/End` bodies never split; mixed files —
a plain statement before a body stays before it (the flush at `StatementBegin` finalizes pending
fragments into `statements` first; the body appends during the scan, the tail after it — file
order throughout); a fragment without a trailing `;` before a body never merges with the next
fragment (each flush splits its own buffer); a semicolon inside a line comment outside a body
splits a piece that is then comment-only → dropped; CRLF files — `splitlines()` + `strip()`
normalize; Down content (including unknown annotations and `{{...}}`) never raises — the scan
stopped.

### `load_migration_set` (goose.py)

**Responsibility**: folder → ordered, parsed, deduplicated set.

**Algorithm:**
```
1. sql_files = sorted(p.name-ascending) of folder where file and suffix == ".sql"
   empty → raise MigrationError(f"{folder}: the migrations folder holds no .sql files")
2. grammar + duplicate-version check (shared with check_local_migrations)
3. migrations = [parse_migration_file(name, path.read_text("utf-8")) per file]
4. migrations.sort(key=version)   # ascending numeric
   → return migrations
```

**Errors:** `MigrationError` (no `.sql`; grammar; duplicates; parse failures pass through
naming the file).

**Edge cases:** mixed `9_add.sql` / `10_add.sql` → numeric order (9 before 10); a non-`.sql`
file with a migration-looking name → ignored.

### `apply_migrations` (apply.py)

**Responsibility**: execute the parsed set once, in order, with per-file transaction policy.

**Algorithm:**
```
1. FOR m in migrations (caller's order):
2.   IF m.no_transaction:
       FOR statement in m.statements:
         with conn.cursor() as cursor: cursor.execute(statement)   # autocommit — each commits
     ELSE:
       with conn.transaction():
         FOR statement in m.statements:
           with conn.cursor() as cursor: cursor.execute(statement)
3.   logger.info("migration applied", extra={"migration": m.filename, "version": m.version})
4.   ON psycopg.Error as exc:
       primary = exc.diag.message_primary or str(exc)
       → raise MigrationError(f"{m.filename}: {primary}") from exc   # apply stops here
```

**Errors:** `MigrationError` (file + server message, psycopg error as cause); default files
roll back fully (one transaction per file); NO TRANSACTION files keep already-applied
statements.

**Edge cases:** empty `statements` → transaction opens and commits vacuously, one progress
line; empty `migrations` list → no-op.

### `run_migrations` (apply.py)

**Responsibility**: one apply — resolve the source, load the set, apply.

**Algorithm:**
```
1. IF git_url is None:
     folder = Path.cwd() / location
     migrations = load_migration_set(folder)
     apply_migrations(conn, migrations)
     return
2. with tempfile.TemporaryDirectory(prefix="pybuggy-migrations-") as tmp:
     target = Path(tmp)
     TRY Repo.clone_from(git_url, str(target), depth=1, branch=git_ref)
     EXCEPT GitCommandError as exc → raise MigrationError(f"failed to clone {git_url}: {exc}")
     folder = target / location
     folder.resolve() not under target.resolve()
       → raise MigrationError(f"{location}: the migrations location escapes the clone")
     not folder.is_dir() → raise MigrationError(f"{location}: the migrations folder is missing
     in the cloned repository")
     migrations = load_migration_set(folder)
     apply_migrations(conn, migrations)
   # clone deleted on every exit path — applied or failed
```

**Errors:** `MigrationError` at every step (clone, containment, missing folder, set loading,
apply) with the failed step named.

**Edge cases:** `git_ref` None → default branch (`branch=None` omits `--branch`); a bare SHA
`ref` → the clone fails with git's own error, surfaced as `MigrationError` (documented
constraint: refs are branch/tag names); two sessions → two independent clones (no caching).

### `PostgresEngine._migrate` override + `BaseEngine` hook (engines)

**Responsibility**: apply the declared set exactly once per session, between plane open and
startup data.

**Algorithm:**
```
BaseEngine.start (modified insertion):
  ... _run_step("start failed at readiness wait", self._wait_ready)
  ... _run_step("start failed at data-plane open", self._open_plane)
+ ... self._run_step("start failed at migrations", self._migrate)     # NEW — no-op default
  ... self._apply_operations(startup)

BaseEngine._migrate (new protected hook): no-op — kinds without migrations override nothing.

PostgresEngine._migrate:
1. declaration = self.config.migrations
2. declaration is None → return
3. git_url = declaration.git.url   if declaration.git else None
   git_ref = declaration.git.ref   if declaration.git else None
4. run_migrations(conn=self._connection, location=declaration.location,
                  git_url=git_url, git_ref=git_ref)
```

**Errors:** `MigrationError` → `_run_step` → `EngineError` ("service '<name>': start failed at
migrations: <file>: <server message>") with `MigrationError` as cause → `start`'s handler stops
the service (`stop()`) and re-raises.

**Edge cases:** no declaration → the hook returns immediately, zero overhead, established
behavior byte-for-byte; declaration with remote source → clone + apply inside the start step
(start returns only after the set is applied).

### Declaration models (config/migrations.py) and loader check (config/loader.py)

**Responsibility**: typed declaration + fail-fast document validation.

**Algorithm** (`_validate_migrations(entry, scope)` in loader.py, called from `_read_services`
after `_validate_topics`):
```
1. "migrations" not in entry → return
2. entry kind != "postgresql" → ValueError(f"{scope}: migrations are accepted only on
   postgresql entries")
3. raw = entry["migrations"]
   raw is not a dict → ValueError(f"{scope}.migrations: must be a mapping")   # null, list, scalar
   location not a non-empty string → ValueError(f"{scope}.migrations.location: must be a
   non-empty path")   # "" would resolve to cwd (local) or the clone root (remote)
   declaration = _build_model(MigrationsConfig, dict(raw), f"{scope}.migrations")
4. declaration.git is None:
     folder = Path.cwd() / declaration.location
     TRY check_local_migrations(folder)
     EXCEPT MigrationError as exc → raise ValueError(f"{scope}.migrations: {exc}") from exc
5. else:
     TRY check_git_url(declaration.git.url)
     EXCEPT MigrationError as exc → raise ValueError(f"{scope}.migrations: {exc}") from exc
```

**Errors:** `ValueError` naming the document location and the entry (the reader's family —
consistent with every other load failure).

**Edge cases:** `migrations: null` (or a list/scalar value) → step 3's isinstance guard:
`ValueError(f"{scope}.migrations: must be a mapping")` — never a raw `TypeError` out of
`dict(...)`; an empty `location` (`""`) → step 3's non-empty guard — empty resolves to the cwd
(local) or the clone root (remote), applying stray `.sql` files from an unintended folder;
a mapping without `location` fails the `MigrationsConfig` build with a scope-named
message (location required); an unknown key inside the block (`journal: true`) →
`extra="forbid"` rejection naming the key.

## Cross-cutting Concerns

- **Error handling**: three families, one direction of flow — `MigrationError` (migrations
  cell, `RuntimeError` subtype; message names the file or source step + underlying cause) →
  wrapped by the config reader into `ValueError` (document location + entry) or by the engine
  into `EngineError` (service + lifecycle step) — always `raise ... from exc`, so the file
  name and server message survive every mapping. No recovery, no retries: fail fast, never a
  silent misapply.
- **Logging**: `logging` stdlib, module-level `logger = logging.getLogger(__name__)`,
  structured `extra` metadata, lowercase stable event names. INFO: `"migration applied"` (one
  per file — the progress lines). DEBUG: source resolution steps (e.g. `"migrations source
  resolved"` with `{"location": ...}`). No URLs with credentials can appear (rejected at
  load); no secrets in logs per `conventions`.
- **Validation**: two-phase by design — **load time** (document semantics: placement,
  local-folder shape, URL shape; before any container starts) and **apply time** (content:
  grammar re-check, parse, execution). Both phases share one filename grammar regex and one
  version-int extraction (single source of truth in `goose.py`, imported by `source.py`).
- **Caching**: none. Every remote apply downloads a fresh shallow clone into a unique
  temporary directory; the clone is consumed in place and deleted on every exit path.
- **Concurrency**: no shared mutable state across calls; the engine calls `run_migrations`
  exactly once per session, sequentially inside `start`. Parallel sandboxes (per-session
  networks) get distinct temporary directories — no interference. All file operations are
  confined to the caller-provided folder or the private clone.

## Usages Analysis

### `conventions`
- **What it provides**: mandatory Python rules — pydantic `kw_only` models, relative imports,
  structured logging, Google docstrings, test structure/mocking rules, validation commands.
- **Where used**: every entity of all three cells (global annotations bind it).
- **Why chosen**: project-wide code standard.
- **How exactly**: `ConfigDict(kw_only=True, extra="forbid")` models; `from .goose import ...`
  / `from ..migrations import ...` intra-package imports; `logger = logging.getLogger(__name__)`;
  tests mirror source layout (`tests/sandbox/migrations/test_goose.py`); `Repo.clone_from`
  mocked at the import site; `tmp_path` for file fixtures.

### `goose-sql` (new cook)
- **What it provides**: the migration file format — naming grammar, the five supported
  annotations, statement-body rules, out-of-subset rejection, up-only set consumption.
- **Where used**: `check_local_migrations` (naming grammar), `parse_migration_file` (all
  parsing rules), `load_migration_set` (ordering/duplicates), `run_migrations`
  (set-consumption semantics).
- **Why chosen**: the runner consumes goose-generated files as produced; the format contract
  must live in one authoritative document.
- **How exactly**: the annotation table maps 1:1 to the parser's token switch; the
  naming/version rules map to the shared regex; "outside the subset fails with the file named"
  maps to the unsupported-annotation raises.

### `psycopg`
- **What it provides**: the postgres driver execution patterns — autocommit session
  connection, `conn.transaction()` blocks, parameter-free DDL execution, error surfacing via
  `.diag.message_primary`.
- **Where used**: `apply_migrations` (execution plane); `PostgresEngine` (existing data plane
  — unchanged); the new "Migrations" cook section.
- **Why chosen**: the engine's existing per-session connection is reused for migrations.
- **How exactly**: `with conn.transaction():` per default file; direct `cursor.execute(body)`
  per statement for NO TRANSACTION files and for bodies (no placeholders ever).

### `gitpython`
- **What it provides**: the shallow-clone context-manager pattern (`Repo.clone_from(url, tmp,
  depth=1, branch=ref)`), ambient-credentials convention, per-consumer error mapping.
- **Where used**: `run_migrations` (remote source resolution).
- **Why chosen**: the same idiom `endpoint pull` uses — the cook was extended to document the
  second consumer explicitly.
- **How exactly**: clone into `tempfile.TemporaryDirectory(prefix="pybuggy-migrations-")`;
  `branch=ref` (None → default branch); `GitCommandError` → `MigrationError` (the sandbox
  family, not `ClickException`); nothing copied into the consumer repository.

### Imported Usages

- `migration-set` from `goga_tool_pybuggy/sandbox/migrations` — imported by both `config` and
  `engines`; documents the facade the two consumers embed (load-time checks, once-per-session
  apply, failure reading, preconditions).
  - Path: `goga_tool_pybuggy/sandbox/migrations/.usages/migration-set.md`
  - Traced dependency: `load_sandbox_config` follows its "Validating a declared source at
    document load" section; `PostgresEngine._migrate` follows "Running one apply at engine
    startup"; the error-mapping example (`except MigrationError ... raise ... from exc`)
    matches both consumers' implemented wrap chains.
- `sandbox-file` (consumer doc of the config cell, not imported by the changed cells) — the
  author-facing declaration reference; verified consistent with the contracts (below).

## `.usages/` Update

### Cell: `goga_tool_pybuggy/sandbox/migrations`

#### New Files
- **`migration-set`** → `goga_tool_pybuggy/sandbox/migrations/.usages/migration-set.md`
  - Status: created by the apply-architecture stage.
  - Consistency verified against this design: the check/apply examples match the contract
    signatures (`check_local_migrations(folder=Path(...))`, `check_git_url(url=...)`,
    `run_migrations(conn=..., location=..., git_url=..., git_ref=...)`); the failure-reading
    section matches the wrap chains; the preconditions section matches the apply semantics
    (autocommit connection, per-file transactions, no journal, no version table).
  - One nuance checked against decision A: the file documents the allowlist as
    "https/http/git/ssh" — consistent with the strict scheme rule; no update needed.

### Cell: `goga_tool_pybuggy/sandbox/config`

#### Existing Files — Consistency
- **`sandbox-file`** → `goga_tool_pybuggy/sandbox/config/.usages/sandbox-file.md`
  - Status: replaced by the apply-architecture stage; **current**.
  - Verified: the layout example carries the `migrations` block; the "Migrations" section
    matches the contract (postgresql-only, cwd-relative local anchor, remote `git.url`/`ref`,
    ambient credentials); the role split (schema once per session vs `data.postgres` seed
    replay) matches the engine contract; the preconditions list enumerates the load-time
    failures including "git URL outside the scheme allowlist (https/http/git/ssh)" — consistent
    with decision A.
  - Additions needed: none. Updates needed: none.

### Cell: `goga_tool_pybuggy/sandbox/engines`

- No `.usages/` directory exists — skipped (no consumer docs to update; the engines cell
  exposes its facade through the sandbox cell's session API instead).

## Test Stack Trace

### General Setup

- New test package `tests/sandbox/migrations/` with `__init__.py` — mirrors
  `goga_tool_pybuggy/sandbox/migrations/` per `conventions`.
- Local connection doubles mirroring `tests/sandbox/engines/test_postgres.py`:
  `FakeCursor` (records `("execute", sql, params)`, context-manager), `FakeTransaction`
  (records `("transaction", "begin"|"commit"|"rollback", None)`), `FakeConnection`
  (holds `statements`, `cursor()`, `transaction()`); `FailingCursor`/`FailingConnection`
  raise `psycopg.errors.UndefinedTable` (carrying `diag.message_primary`) on every execute.
- Git mocking: `mock.patch("goga_tool_pybuggy.sandbox.migrations.apply.Repo.clone_from")` —
  the import site; the side effect writes migration files into the received target path
  (a pseudo-clone on disk).
- Filesystem fixtures: `tmp_path` + `monkeypatch.chdir(tmp_path)` for cwd-anchored resolution.
- No real network, no real containers in unit tests; container tests keep the existing
  `requires_docker` marker.

### Source File Registry

- `goga_tool_pybuggy/sandbox/migrations/goose.py` — parser + set loader (+ shared grammar).
- `goga_tool_pybuggy/sandbox/migrations/source.py` — load-time checks.
- `goga_tool_pybuggy/sandbox/migrations/apply.py` — apply + orchestration.
- `goga_tool_pybuggy/sandbox/migrations/errors.py` — `MigrationError`.
- `goga_tool_pybuggy/sandbox/config/migrations.py` — declaration models.
- `goga_tool_pybuggy/sandbox/config/loader.py` — `_validate_migrations`.
- `goga_tool_pybuggy/sandbox/engines/base.py` — `_migrate` hook + start insertion.
- `goga_tool_pybuggy/sandbox/engines/postgres.py` — `_migrate` override.

---

### Positive Tests

#### `test_check_local_migrations_with_valid_folder`

**Setup**: `tmp_path` holding `00001_init.sql` (`-- +goose Up\nCREATE TABLE a (id int);\n`) and
`00002_add_users.sql`.

**Input**: `check_local_migrations(folder=tmp_path)`.

**Trace**:
```
check_local_migrations(tmp_path)
  → tmp_path.is_dir()                     # step 1 — True
  → iterdir() → 2 entries                 # step 2 — non-empty
  → 2 .sql files                          # step 3
  → grammar: both match ^(\d+)_(.+)\.sql$ # step 4 — versions 1, 2
  → {1, 2} — unique                       # step 5
  → return None
```

**Assertions**: no exception raised.

**Sufficiency**: the happy path of the load-time gate — prevents regressions that would reject
every valid document.

---

#### `test_check_local_migrations_ignores_non_sql_files`

**Setup**: `tmp_path` holding `00001_init.sql`, `notes.txt`, `README.md`.

**Input**: `check_local_migrations(folder=tmp_path)`.

**Trace**:
```
check_local_migrations(tmp_path)
  → 3 entries; sql_files = [00001_init.sql]   # non-.sql filtered
  → grammar + uniqueness pass
  → return None
```

**Assertions**: no exception.

**Sufficiency**: pins the "non-.sql files are ignored everywhere" rule — a stray README must
not fail the document.

---

#### `test_check_git_url_accepts_allowed_schemes`

**Setup**: none (pure function).

**Input**: `pytest.mark.parametrize("url", ["https://gitlab.example/acme/s.git",
"http://gitlab.example/acme/s.git", "git://gitlab.example/acme/s.git",
"ssh://git@gitlab.example/acme/s.git"])` → `check_git_url(url=url)`.

**Trace**:
```
check_git_url(url)
  → urlparse(url).scheme in allowlist   # https/http/git/ssh
  → netloc "@" check: ssh username allowed; others carry no "@"
  → return None
```

**Assertions**: no exception per parameter.

**Sufficiency**: the four accepted schemes plus the ssh-username allowance — the boundary of
the allowlist.

---

#### `test_parse_simple_up_statements`

**Setup**: none.

**Input**: `parse_migration_file(filename="00003_create_orders.sql", text=...)` with
```
-- +goose Up
CREATE TABLE orders (id int PRIMARY KEY, customer text);
CREATE INDEX idx_orders_customer ON orders (customer);

-- +goose Down
DROP INDEX idx_orders_customer;
DROP TABLE orders;
```

**Trace**:
```
parse_migration_file("00003_create_orders.sql", text)
  → grammar: version=3                                  # step 1
  → header empty; "-- +goose Up" → region=up            # step 2
  → two DDL lines accumulate; "-- +goose Down" → scan stops
  → fragments split on ";": ["CREATE TABLE ... (id int PRIMARY KEY, customer text)",
    "\nCREATE INDEX ... (customer)", "\n\n"] → third dropped (empty/comment-only)
  → no "{{" in scanned text
  → MigrationFile(version=3, filename=..., no_transaction=False,
      statements=["CREATE TABLE orders (id int PRIMARY KEY, customer text)",
                  "CREATE INDEX idx_orders_customer ON orders (customer)"])
```

**Assertions**: `result.version == 3`; `result.no_transaction is False`; `result.statements ==
[...]` exactly the two bodies **without** terminating semicolons; Down statements absent.

**Sufficiency**: the canonical goose file parses into the exact apply-ready form — the core
parser contract, including the semicolon-consumption rule every apply test builds on.

---

#### `test_parse_statement_begin_body_preserves_interior_semicolons`

**Setup**: none.

**Input**: text with
```
-- +goose Up
-- +goose StatementBegin
CREATE OR REPLACE FUNCTION audit_orders() RETURNS trigger AS $$
BEGIN
  INSERT INTO audit_log (order_id) VALUES (NEW.id);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd
CREATE INDEX CONCURRENTLY idx ON orders (customer);
```

**Trace**:
```
parse_migration_file("00004_fn.sql", text)
  → StatementBegin → body mode; 6 interior lines collected verbatim
  → StatementEnd → one statement = the whole body, stripped — the 4 interior ";" never split
  → trailing CREATE INDEX ... ; → one fragment statement
  → MigrationFile(statements=[body, "CREATE INDEX CONCURRENTLY idx ON orders (customer)"])
```

**Assertions**: `len(result.statements) == 2`; `result.statements[0]` contains
`"RETURN NEW;"` and `"$$ LANGUAGE plpgsql;"`; `result.statements[1]` equals the index DDL
without `;`.

**Sufficiency**: the reason StatementBegin/End exists — interior semicolons must not shatter a
function body; regression here breaks every function-bearing migration set.

---

#### `test_parse_preserves_file_order_of_fragments_and_bodies`

**Setup**: none.

**Input**: `parse_migration_file(filename="00010_mixed.sql", text=...)` with
```
-- +goose Up
CREATE TABLE orders (id int PRIMARY KEY, customer text);
-- +goose StatementBegin
CREATE OR REPLACE FUNCTION audit_orders() RETURNS trigger AS $$
BEGIN
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
-- +goose StatementEnd
CREATE INDEX idx_orders_customer ON orders (customer);

-- +goose Down
DROP INDEX idx_orders_customer;
```

**Trace**:
```
parse_migration_file("00010_mixed.sql", text)
  → grammar: version=10                                 # step 1
  → Up region: "CREATE TABLE ..." buffers as a fragment
  → StatementBegin → flush: _split_fragments(["CREATE TABLE orders (...);"])
      → statements = ["CREATE TABLE orders (id int PRIMARY KEY, customer text)"]   # BEFORE the body
  → body collected verbatim; StatementEnd → statements.append(function body)
  → "CREATE INDEX ..." buffers; Down → scan stops; tail flush → index appended
  → statements = [CREATE TABLE, function body, CREATE INDEX] — exactly file order
```

**Assertions**: `result.statements` has length 3; `result.statements[0]` starts with
`CREATE TABLE orders`; `result.statements[1]` contains `RETURN NEW;` and
`$$ LANGUAGE plpgsql;`; `result.statements[2]` equals the index DDL without the trailing `;`.

**Sufficiency**: the ordering invariant — `statements` is the file's statement order. A parser
that appends body statements during the scan but fragment statements only after it (two append
sites, scan-time vs post-scan) silently reorders mixed files: the function body would run before
the `CREATE TABLE` it references. The body-first test above cannot catch this; this test is the
regression pin for it.

---

#### `test_parse_no_transaction_flag`

**Setup**: none.

**Input**: text starting `-- +goose NO TRANSACTION` then `-- +goose Up` with one statement.

**Trace**:
```
parse_migration_file("00005_nt.sql", text)
  → header token NO TRANSACTION → no_transaction=True
  → Up parsed → one statement
```

**Assertions**: `result.no_transaction is True`; statements parsed.

**Sufficiency**: the autocommit branch's trigger — a lost flag would wrap
`CREATE INDEX CONCURRENTLY` in a transaction and fail at apply.

---

#### `test_parse_down_section_skipped`

**Setup**: none.

**Input**: a valid Up section, then `-- +goose Down` followed by `-- +goose Env FOO` and
`SELECT {{.Var}};`.

**Trace**:
```
parse_migration_file("00006_down.sql", text)
  → Up parsed (statements from Up only)
  → "-- +goose Down" → scan stops
  → the unknown annotation and the interpolation after Down are never scanned → no raise
```

**Assertions**: no exception; `result.statements` holds only the Up statements.

**Sufficiency**: pins "the Down section is skipped — parsed only far enough to be excluded";
without it, valid goose files with Down-only extras would be rejected.

---

#### `test_parse_extracts_timestamp_version`

**Setup**: none.

**Input**: `filename="20230102103456_init.sql"`, minimal Up text.

**Trace**: grammar → `version == 20230102103456`.

**Assertions**: `result.version == 20230102103456`.

**Sufficiency**: both goose numbering styles (sequential and timestamp) must parse; a
digits-only-int grammar regression would drop timestamp sets.

---

#### `test_load_orders_numerically`

**Setup**: `tmp_path` with `9_nine.sql`, `10_ten.sql`, `2_two.sql` (each a valid Up file).

**Input**: `load_migration_set(folder=tmp_path)`.

**Trace**:
```
load_migration_set(tmp_path)
  → sql_files listed (name-sorted: "10_ten.sql", "2_two.sql", "9_nine.sql")
  → parsed → versions [10, 2, 9]
  → sort(key=version) → [2, 9, 10]
```

**Assertions**: `[m.version for m in result] == [2, 9, 10]`; filenames in the same order.

**Sufficiency**: lexicographic ordering ("10" < "9") would apply migrations in the wrong order
— the classic migration-runner bug this test prevents.

---

#### `test_apply_executes_each_file_in_its_own_transaction`

**Setup**: two parsed migrations — m1 (`00001_a.sql`, statements `["CREATE TABLE t (id int)"]`),
m2 (`00002_b.sql`, statements `["INSERT INTO t VALUES (1)", "INSERT INTO t VALUES (2)"]`), both
default; `FakeConnection()`.

**Input**: `apply_migrations(conn=fake, migrations=[m1, m2])`.

**Trace**:
```
apply_migrations(fake, [m1, m2])
  → m1: transaction() → begin; execute("CREATE TABLE t (id int)"); commit
       logger.info("migration applied", migration="00001_a.sql", version=1)
  → m2: transaction() → begin; execute("INSERT INTO t VALUES (1)");
       execute("INSERT INTO t VALUES (2)"); commit
       logger.info("migration applied", migration="00002_b.sql", version=2)
```

**Assertions**:
```
fake.statements == [
    ("transaction", "begin", None),
    ("execute", "CREATE TABLE t (id int)", None),
    ("transaction", "commit", None),
    ("transaction", "begin", None),
    ("execute", "INSERT INTO t VALUES (1)", None),
    ("execute", "INSERT INTO t VALUES (2)", None),
    ("transaction", "commit", None),
]
```

**Sufficiency**: one transaction per file, statements as given, in order — the atomicity unit
of the apply (a failing file must roll back only itself).

---

#### `test_apply_no_transaction_runs_statement_by_statement`

**Setup**: m = `00007_nt.sql`, statements `["CREATE INDEX CONCURRENTLY i ON t (c)"]`,
`no_transaction=True`; `FakeConnection()`.

**Input**: `apply_migrations(conn=fake, migrations=[m])`.

**Trace**:
```
apply_migrations(fake, [m])
  → no autocommit opt-out: no transaction() markers
  → execute("CREATE INDEX CONCURRENTLY i ON t (c)") directly
  → progress line logged
```

**Assertions**: `fake.statements == [("execute", "CREATE INDEX CONCURRENTLY i ON t (c)", None)]`
— no `("transaction", ...)` entries.

**Sufficiency**: `CREATE INDEX CONCURRENTLY` cannot run inside a transaction block — a
transaction wrapper here fails every NO TRANSACTION migration.

---

#### `test_apply_logs_one_progress_line_per_file`

**Setup**: two default migrations; `FakeConnection()`; `caplog` at `logging.INFO`.

**Input**: `apply_migrations(conn=fake, migrations=[m1, m2])`.

**Trace**: each applied file emits `logger.info("migration applied", extra={"migration": name,
"version": n})`.

**Assertions**: two INFO records with `record.message == "migration applied"`; extras carry the
filenames in application order.

**Sufficiency**: the per-file progress lines are contract-level output ("each applied file is
reported as one progress line") — authors count applied migrations by them.

---

#### `test_run_local_source_resolves_against_cwd`

**Setup**: `tmp_path/db/migrations/00001_init.sql` (valid); `monkeypatch.chdir(tmp_path)`;
`FakeConnection()`.

**Input**: `run_migrations(conn=fake, location="db/migrations", git_url=None, git_ref=None)`.

**Trace**:
```
run_migrations(fake, "db/migrations", None, None)
  → git_url None → folder = Path.cwd() / "db/migrations" → tmp_path/db/migrations
  → load_migration_set → [MigrationFile(version=1, statements=[...])]
  → apply_migrations → execute(...) inside one transaction
```

**Assertions**: no exception; `fake.statements` starts with `("transaction", "begin", None)`
and contains the file's statement; the clone API was never touched (no `Repo` import path
exercised).

**Sufficiency**: the local-source resolution anchor — the same anchor the document uses; a
regression resolves against the wrong base and finds no folder.

---

#### `test_run_remote_source_clones_and_applies`

**Setup**: `FakeConnection()`; `mock.patch("...migrations.apply.Repo.clone_from")` whose side
effect writes `00001_init.sql` into `Path(target_dir)`; captured call args.

**Input**: `run_migrations(conn=fake, location="db/migrations",
git_url="https://gitlab.example/acme/s.git", git_ref="release-branch")`.

**Trace**:
```
run_migrations(fake, "db/migrations", url, "release-branch")
  → TemporaryDirectory(prefix="pybuggy-migrations-") → target
  → Repo.clone_from(url, str(target), depth=1, branch="release-branch")   # side effect writes files
  → folder = target / "db/migrations" — inside the clone, is_dir → True
  → load_migration_set + apply_migrations over fake
  → with-block exits → target deleted
```

**Assertions**: `clone_from` called once with `url`, a path ending in no fixed name (the temp
target), `depth=1`, `branch="release-branch"`; the file's statement executed on `fake`;
`Path(clone_target).exists() is False` after the call (clone deleted).

**Sufficiency**: the whole remote orchestration — shallow clone at the declared ref, in-clone
resolution, apply, cleanup on the success path.

---

#### `test_run_remote_source_clones_default_branch_without_ref`

**Setup**: as above, `git_ref=None`.

**Input**: `run_migrations(conn=fake, location="db/migrations", git_url=url, git_ref=None)`.

**Trace**: `Repo.clone_from(url, target, depth=1, branch=None)` → default branch.

**Assertions**: the `branch` kwarg is exactly `None` (GitPython omits `--branch`).

**Sufficiency**: `branch=None` vs omitting the kwarg differ — omitting defaults to `master` in
some GitPython versions; the None-passing must be preserved.

---

#### `test_loader_accepts_migrations_on_postgresql`

**Setup**: `tmp_path` with a valid `db/migrations/00001_init.sql`; `monkeypatch.chdir(tmp_path)`;
a full sandbox document (instance + `services: {db: {kind: postgresql, migrations: {location:
db/migrations}}}`) written to `tmp_path/.goga/tools/pybuggy/sandbox.yml`.

**Input**: `load_sandbox_config()`.

**Trace**:
```
load_sandbox_config()
  → document found at cwd anchor → parsed
  → _read_services → db entry → _validate_migrations
    → kind postgresql ✓ → MigrationsConfig(location="db/migrations", git=None)
    → folder = cwd / "db/migrations" → check_local_migrations → passes
  → ServiceConfig(migrations=<MigrationsConfig ...>) → SandboxConfig
```

**Assertions**: `config.services["db"].migrations.location == "db/migrations"`;
`config.services["db"].migrations.git is None`.

**Sufficiency**: the end-to-end load path of the declaration — model, placement, and the
on-disk check composed.

---

#### `test_loader_accepts_remote_source_by_shape`

**Setup**: document with `migrations: {location: db/migrations, git: {url:
"https://gitlab.example/acme/s.git"}}`; no folder created; `monkeypatch.chdir(tmp_path)`.

**Input**: `load_sandbox_config()`.

**Trace**: `_validate_migrations` → remote branch → `check_git_url` passes (https, no
credentials) → no filesystem access, no network.

**Assertions**: `config.services["db"].migrations.git.url == "https://gitlab.example/acme/s.git"`;
`git.ref is None`.

**Sufficiency**: remote content resolves at engine startup, not at load — the load must accept
a URL whose folder does not exist locally.

---

#### `test_migrate_hook_applies_declared_set_with_flattened_args`

**Setup**: `ServiceConfig(name="db", kind="postgresql", migrations=MigrationsConfig(
location="db/migrations", git=GitSource(url="https://x/r.git", ref="rel")))`;
`mock.patch("goga_tool_pybuggy.sandbox.engines.postgres.run_migrations")`; a started-shaped
`PostgresEngine` with `engine._connection = FakeConnection()`.

**Input**: `engine._migrate()`.

**Trace**:
```
PostgresEngine._migrate()
  → declaration = config.migrations (not None)
  → git_url = "https://x/r.git"; git_ref = "rel"
  → run_migrations(conn=<the fake connection>, location="db/migrations",
                   git_url="https://x/r.git", git_ref="rel")
```

**Assertions**: `run_migrations` called once with exactly those kwargs; `conn is
engine._connection`.

**Sufficiency**: the contract's call shape — the engine passes the session connection and the
flattened scalars; a signature drift between the cells surfaces here.

---

#### `test_migrate_hook_is_noop_without_declaration`

**Setup**: `ServiceConfig(name="db", kind="postgresql")` (migrations None); the same mock.

**Input**: `engine._migrate()`.

**Trace**: `declaration is None → return` — `run_migrations` never called.

**Assertions**: `run_migrations.assert_not_called()`.

**Sufficiency**: absence of the declaration must reproduce the established startup exactly.

---

#### `test_start_runs_migrations_between_plane_open_and_startup_data`

**Setup**: a `PostgresEngine` wired with fakes: `_open_plane` replaced to set
`_connection = FakeConnection()`; `mock.patch("...engines.postgres.run_migrations")` with a
side effect appending `("execute", "MIGRATIONS", None)` to the connection; a startup
`sql_op("INSERT INTO seed VALUES (1)")` prepared; container doubles as the existing tests use.

**Input**: `engine.start([startup_op], network=None)`.

**Trace**:
```
BaseEngine.start
  → build/start/ready (fakes) → _open_plane (fake) → _connection set
  → _run_step("start failed at migrations", _migrate)
      → run_migrations(...)  # side effect: statements += ("execute", "MIGRATIONS", None)
  → _apply_operations([startup_op]) → statements += ("execute", "INSERT INTO seed VALUES (1)", None)
  → journal.extend([startup_op])
```

**Assertions**: index of `("execute", "MIGRATIONS", None)` in `connection.statements` is lower
than the index of the seed statement; the seed statement executed at all.

**Sufficiency**: the ordering contract — startup data statements run against the migrated
schema; a hook inserted after `_apply_operations` would silently invert it.

---

#### `test_migrate_failure_maps_to_engine_error_naming_service`

**Setup**: declared migrations; the mock raises `MigrationError("00002_bad.sql: relation
\"ghost\" does not exist")`.

**Input**: `engine._migrate()` wrapped in `pytest.raises(EngineError)` — or via `engine.start`
with remaining fakes.

**Trace**:
```
_migrate() → run_migrations raises MigrationError
  → _run_step catches (not EngineError) → raise EngineError(
      "service 'db': start failed at migrations: 00002_bad.sql: relation \"ghost\" does not exist")
      from MigrationError
```

**Assertions**: `excinfo.value` is `EngineError`; message contains `service 'db'`,
`start failed at migrations`, `00002_bad.sql`, and the server text;
`excinfo.value.__cause__` is the `MigrationError`.

**Sufficiency**: the cross-family mapping — the file name and server message must survive into
the engine's error with the cause chain intact; this is the author-facing failure surface.

---

### Negative Tests

#### `test_check_local_migrations_with_missing_folder`

**Setup**: `tmp_path / "nope"` does not exist.

**Input**: `pytest.raises(MigrationError)` around `check_local_migrations(tmp_path / "nope")`.

**Trace**: `is_dir()` False → raise naming the folder and the check.

**Assertions**: message contains `str(tmp_path / "nope")`.

**Sufficiency**: the most common authoring mistake — a wrong `location` — fails at load, before
any container starts.

---

#### `test_check_local_migrations_with_file_instead_of_folder`

**Setup**: `p = tmp_path / "file.txt"; p.write_text("x")`.

**Input**: `check_local_migrations(p)` inside `pytest.raises(MigrationError)`.

**Trace**: `is_dir()` False (a file) → raise naming the path.

**Assertions**: message names the path.

**Sufficiency**: "must exist **and be a folder**" — a file at the path is not a folder.

---

#### `test_check_local_migrations_with_empty_folder` / `..._without_sql_files`

**Setup**: empty `tmp_path` subfolder; another holding only `notes.txt`.

**Input**: both under `pytest.raises(MigrationError)`.

**Trace**: step 2 (empty) / step 3 (no `.sql`) → raise naming the folder.

**Assertions**: messages name the folder; the second names the no-`.sql` rule.

**Sufficiency**: an empty or non-migration folder declares nothing to apply — rejected at load,
not at engine start.

---

#### `test_check_local_migrations_with_invalid_filename`

**Setup**: folder with `00001_init.sql` and `create_orders.sql`.

**Input**: `check_local_migrations(folder)` inside `pytest.raises(MigrationError)`.

**Trace**: grammar fails on `create_orders.sql` → raise naming folder **and file**.

**Assertions**: message contains both the folder path and `create_orders.sql`.

**Sufficiency**: pins the shared grammar at load time — without it the failure surfaces only
at apply, after containers started (violating fail-fast).

---

#### `test_check_local_migrations_with_duplicate_versions`

**Setup**: folder with `00001_a.sql` and `1_b.sql`.

**Input**: `check_local_migrations(folder)` inside `pytest.raises(MigrationError)`.

**Trace**: versions `[1, 1]` → duplicate → raise naming the folder and both files.

**Assertions**: message contains `00001_a.sql`, `1_b.sql`, and `1`.

**Sufficiency**: numeric (not lexicographic) duplicate detection — `00001` and `1` are the same
version; a duplicate order is undefined behavior at apply.

---

#### `test_check_git_url_rejects_unknown_scheme`

**Setup**: none.

**Input**: parametrize `["ftp://h/r.git", "file:///etc/passwd", "git@github.com:acme/r.git"]`
under `pytest.raises(MigrationError)`.

**Trace**: scheme not in the allowlist (empty scheme included — scp-style, decision A) → raise
naming the URL and the allowed schemes.

**Assertions**: each message contains the URL and `disallowed`.

**Sufficiency**: the load-time URL gate; the scp-style case pins user decision A against
future "parity with pull" drift.

---

#### `test_check_git_url_rejects_embedded_credentials`

**Setup**: none.

**Input**: parametrize `["https://user:token@h/r.git", "https://user@h/r.git"]` under
`pytest.raises(MigrationError)`.

**Trace**: `"@" in netloc`, scheme not ssh → raise naming the URL.

**Assertions**: messages contain the URL and the credentials rule.

**Sufficiency**: credentials in a URL would leak into logs and the journal of error messages —
rejected up front.

---

#### `test_parse_without_up_section`

**Setup**: none.

**Input**: text with only a header and `-- +goose Down ...` → `pytest.raises(MigrationError)`.

**Trace**: `Down` reached while region == header → raise naming the file (no Up section).

**Assertions**: message contains the filename.

**Sufficiency**: "a file without an Up section raises" — there is nothing to apply.

---

#### `test_parse_with_invalid_filename`

**Setup**: none.

**Input**: `parse_migration_file("create_orders.sql", "-- +goose Up\nSELECT 1;")` under
`pytest.raises(MigrationError)`.

**Trace**: grammar fails (no `<version>_`) → raise naming the file.

**Assertions**: message contains `create_orders.sql`.

**Sufficiency**: parser-level grammar enforcement (the apply-time backstop of the load check).

---

#### `test_parse_with_unclosed_statement_begin`

**Setup**: none.

**Input**: text with `-- +goose StatementBegin` and body but no `StatementEnd`, under
`pytest.raises(MigrationError)`.

**Trace**: loop ends with an open body → raise naming the file.

**Assertions**: message names the file.

**Sufficiency**: an unclosed body would otherwise swallow the rest of the file as one
statement — a silent misapply.

---

#### `test_parse_with_statement_end_without_begin`

**Setup**: none.

**Input**: Up region containing a stray `-- +goose StatementEnd` → `pytest.raises(MigrationError)`.

**Trace**: token in up region, body is None → raise naming the file.

**Assertions**: message names the file.

**Sufficiency**: an unbalanced end is a corrupted file — fail, never guess.

---

#### `test_parse_with_unknown_annotation`

**Setup**: none.

**Input**: Up region containing `-- +goose Env FOO` (and, separately, header containing it) —
parametrized, under `pytest.raises(MigrationError)`.

**Trace**: token not in the supported subset for the region → raise naming the file and the
token.

**Assertions**: message contains the filename and `Env`.

**Sufficiency**: "any +goose annotation outside the supported subset ... raise — never a silent
misapply" — the fail-over-guess rule of the format.

---

#### `test_parse_with_no_transaction_after_up`

**Setup**: none.

**Input**: `-- +goose Up` followed later by `-- +goose NO TRANSACTION` → `pytest.raises(MigrationError)`.

**Trace**: `NO TRANSACTION` token arrives in the up region → unsupported position → raise
naming the file.

**Assertions**: message names the file.

**Sufficiency**: the flag is header-only by format; accepting it mid-file would silently
misread the file's transaction policy.

---

#### `test_parse_with_interpolation`

**Setup**: none.

**Input**: Up statement containing `CREATE TABLE {{.Name}} (id int);` → `pytest.raises(MigrationError)`.

**Trace**: `"{{"` found in scanned text → raise naming the file.

**Assertions**: message names the file and the interpolation rule.

**Sufficiency**: goose variables would apply as literal `{{.Name}}` SQL — the guard turns a
wrong-schema into an actionable error.

---

#### `test_load_without_sql_files` / `test_load_with_duplicate_versions`

**Setup**: empty folder; folder with `1_a.sql` + `0001_b.sql`.

**Input**: `load_migration_set(folder)` under `pytest.raises(MigrationError)`.

**Trace**: apply-time re-checks raise naming the folder (and both files for duplicates).

**Assertions**: messages name the folder (and files).

**Sufficiency**: the apply-time backstop — remote sources never passed the load-time check, so
the set loader enforces the same rules itself.

---

#### `test_apply_failure_names_file_and_server_message_and_stops`

**Setup**: m1 = `00001_ok.sql` (one statement), m2 = `00002_bad.sql` (statement
`("INSERT INTO ghost VALUES (1)")`); `FailingConnection()` — every execute raises
`psycopg.errors.UndefinedTable('relation "ghost" does not exist')` (diag.message_primary set).

**Input**: `apply_migrations(conn=failing, migrations=[m1, m2])` — wait: m1 would fail first on
a failing connection. Use `[m2]` plus a third `m3 = 00003_after.sql` after it.

**Trace**:
```
apply_migrations(failing, [m2, m3])
  → m2: transaction begin; execute raises UndefinedTable → transaction rolls back
  → except psycopg.Error → primary = 'relation "ghost" does not exist'
  → raise MigrationError('00002_bad.sql: relation "ghost" does not exist') from exc
  → m3 never runs
```

**Assertions**: `excinfo.type is MigrationError`; message contains `00002_bad.sql` and the
server text; `excinfo.value.__cause__` is the psycopg error; no statement of m3 in
`failing.statements` after the m2 entries.

**Sufficiency**: the failure contract — first failure stops the apply, names the file and the
server message, keeps the cause; a continue-on-error runner would leave half-built schemas.

---

#### `test_run_local_source_missing_folder`

**Setup**: `monkeypatch.chdir(tmp_path)` with no `db/` created; `FakeConnection()`.

**Input**: `run_migrations(conn=fake, location="db/migrations", git_url=None, git_ref=None)`
under `pytest.raises(MigrationError)`.

**Trace**: `load_migration_set(cwd / "db/migrations")` → no `.sql` (folder missing) → raise
naming the folder.

**Assertions**: message contains `db/migrations`.

**Sufficiency**: the folder may vanish between load and apply — the apply re-checks and fails
naming the path.

---

#### `test_run_remote_source_clone_failure`

**Setup**: `mock.patch("...apply.Repo.clone_from")` raising `GitCommandError("clone", 128,
b"fatal: Authentication failed")`; `FakeConnection()`.

**Input**: remote `run_migrations(...)` under `pytest.raises(MigrationError)`.

**Trace**: `GitCommandError` → `MigrationError("failed to clone <url>: ...") from exc`.

**Assertions**: message contains the URL and `failed to clone`; cause chain intact; the temp
dir is gone (context manager exited).

**Sufficiency**: bad credentials/repos are the common remote failure — surfaced in the
migrations family, not a bare GitPython traceback.

---

#### `test_run_remote_source_missing_location_in_clone`

**Setup**: clone side effect creates the target but no `db/migrations` inside.

**Input**: remote `run_migrations(...)` under `pytest.raises(MigrationError)`.

**Trace**: `folder.is_dir()` False → raise naming the location path.

**Assertions**: message contains `db/migrations`.

**Sufficiency**: a wrong in-repo path fails naming the path — matches the gitpython cook's
missing-location rule.

---

#### `test_run_remote_source_location_escapes_clone`

**Setup**: clone side effect creates a valid set at the clone root; declaration
`location="../../elsewhere"` with an existing `tmp_path/elsewhere` folder holding a valid
`.sql` (the escape target); `monkeypatch.chdir(tmp_path)`.

**Input**: remote `run_migrations(conn=fake, location="../../elsewhere", ...)` under
`pytest.raises(MigrationError)`.

**Trace**: `folder.resolve()` escapes `target.resolve()` → containment raise naming the
location.

**Assertions**: message names `../../elsewhere`; nothing executed on `fake`.

**Sufficiency**: the design-level containment safeguard — an escaping location must not read
files from outside the clone.

---

#### `test_loader_rejects_migrations_on_non_postgresql`

**Setup**: document with `services: {events: {kind: kafka, topics: [...], migrations:
{location: db/migrations}}}`; valid folder on disk; `monkeypatch.chdir(tmp_path)`.

**Input**: `load_sandbox_config()` under `pytest.raises(ValueError)`.

**Trace**:
```
_read_services → events entry → _validate_migrations
  → kind "kafka" != "postgresql" → ValueError(f"{location}: services.events: migrations are
    accepted only on postgresql entries")
```

**Assertions**: message contains the document path, `services.events`, and the rule.

**Sufficiency**: the placement rule — topics belong to kafka, migrations to postgresql; the
message names the entry as the contract demands.

---

#### `test_loader_rejects_non_mapping_migrations_value`

**Setup**: document with `services: {db: {kind: postgresql, migrations: null}}`, parametrized
over the raw values `[None, 12, "x"]`; `monkeypatch.chdir(tmp_path)`.

**Input**: `load_sandbox_config()` under `pytest.raises(ValueError)`.

**Trace**:
```
_read_services → db entry → _validate_migrations
  → "migrations" in entry (value None / 12 / "x") → kind postgresql ✓
  → isinstance guard: raw is not a dict
  → ValueError(f"{scope}.migrations: must be a mapping")
```

**Assertions**: the exception type is exactly `ValueError` (never a leaked `TypeError`); the
message contains the document path, `services.db`, and `migrations`.

**Sufficiency**: the reader's failure family stays `ValueError` for every malformed document —
without the guard, `dict(None)` raises a raw `TypeError` that escapes `load_sandbox_config`
unnamed. Mirrors the `_validate_topics` isinstance pattern.

---

#### `test_loader_rejects_empty_migrations_location`

**Setup**: document with `services: {db: {kind: postgresql, migrations: {location: ""}}}`;
`monkeypatch.chdir(tmp_path)` (with valid `.sql` files sprinkled in `tmp_path` itself — the
folder an unguarded `""` would resolve to).

**Input**: `load_sandbox_config()` under `pytest.raises(ValueError)`.

**Trace**:
```
_read_services → db entry → _validate_migrations
  → raw is a dict ✓ → location is "" → the non-empty guard
  → ValueError(f"{scope}.migrations.location: must be a non-empty path")
```

**Assertions**: the message contains the document path, `services.db`, `migrations`, and
`location`; no `MigrationError`/`TypeError` leaks.

**Sufficiency**: an empty `location` would silently turn the cwd (local) or the clone root
(remote) into the migrations folder — applying stray `.sql` files from an unintended place;
the guard keeps it a load-time failure.

---

#### `test_loader_rejects_missing_local_folder`

**Setup**: document declaring `migrations: {location: db/migrations}` on a postgresql service;
the folder does not exist; `monkeypatch.chdir(tmp_path)`.

**Input**: `load_sandbox_config()` under `pytest.raises(ValueError)`.

**Trace**: `check_local_migrations` raises `MigrationError` → loader wraps →
`ValueError(f"{scope}.migrations: {exc}") from exc`.

**Assertions**: message contains the document path, `services.db`, `migrations`, and the
folder path; `excinfo.value.__cause__` is `MigrationError`.

**Sufficiency**: the wrap chain — the load failure stays in the reader's family while the
cause and the path survive; and it fires before any container starts.

---

#### `test_loader_rejects_bad_git_url_scheme`

**Setup**: document with `migrations: {location: x, git: {url: "ftp://h/r.git"}}`;
`monkeypatch.chdir(tmp_path)`.

**Input**: `load_sandbox_config()` under `pytest.raises(ValueError)`.

**Trace**: `check_git_url` raises → wrapped `ValueError` with scope.

**Assertions**: message contains the scope and `disallowed`.

**Sufficiency**: URL shape is a load-time failure — no network, before containers.

---

#### `test_loader_rejects_duplicate_versions_at_load`

**Setup**: `tmp_path/db/migrations/` with `1_a.sql` and `0001_b.sql`; document declaring it.

**Input**: `load_sandbox_config()` under `pytest.raises(ValueError)`.

**Trace**: `check_local_migrations` duplicate raise → wrapped.

**Assertions**: message names both files.

**Sufficiency**: duplicates are rejected before any container starts (the load-time half of
the uniqueness rule).

---

### Edge Case Tests

#### `test_parse_empty_up_section`

**Setup**: none.

**Input**: text `-- +goose Up\n-- +goose Down\nDROP TABLE x;` → `parse_migration_file("00009_empty.sql", text)`.

**Trace**: Up region holds nothing → `statements == []`; no raise.

**Assertions**: `result.statements == []`; `result.version == 9`.

**Sufficiency**: an empty Up is legal goose — the runner applies nothing and logs one line;
rejecting it would break valid generated sets.

---

#### `test_parse_drops_comment_only_fragments`

**Setup**: none.

**Input**: Up text `SELECT 1;\n-- trailing comment\n` and a leading `-- leading comment\nSELECT 2;`.

**Trace**: fragments split → pieces `["SELECT 1", "\n-- trailing comment\n", ...]`; the
comment-only piece dropped; `-- leading comment\nSELECT 2` — leading comment lines inside a
kept piece stay part of the statement text (postgres accepts leading comments).

**Assertions**: statements contain `SELECT 1` and `SELECT 2`; no statement consists solely of
a comment.

**Sufficiency**: comment hygiene — a comment-only fragment executed as a statement is noise at
best; this pins the drop rule without stripping comments that belong to a statement.

---

#### `test_parse_crlf_file`

**Setup**: none.

**Input**: text with `\r\n` line endings and one statement.

**Trace**: `splitlines()` handles CRLF; `strip()` clears residual `\r`.

**Assertions**: statement equals the clean body (no `\r`).

**Sufficiency**: Windows-authored migration sets parse identically.

---

#### `test_apply_empty_set_is_noop`

**Setup**: `FakeConnection()`; `migrations=[]`.

**Input**: `apply_migrations(conn=fake, migrations=[])`.

**Trace**: loop body never runs.

**Assertions**: `fake.statements == []`; no exception.

**Sufficiency**: `load_migration_set` cannot return an empty set (no-`.sql` raises), but the
apply contract must not assume it.

---

#### `test_apply_empty_statements_file_commits_vacuously_and_logs`

**Setup**: `m = MigrationFile(version=1, filename="00009_empty.sql", statements=[],
no_transaction=False)`; `FakeConnection()`; `caplog` at `logging.INFO`.

**Input**: `apply_migrations(conn=fake, migrations=[m])`.

**Trace**:
```
apply_migrations(fake, [m])
  → m default → transaction() → begin
  → FOR statement in [] — loop body never runs
  → commit
  → logger.info("migration applied", migration="00009_empty.sql", version=1)
```

**Assertions**: `fake.statements == [("transaction", "begin", None),
("transaction", "commit", None)]`; exactly one INFO record with `record.message ==
"migration applied"` and `record.migration == "00009_empty.sql"`.

**Sufficiency**: pins the vacuous-transaction-plus-one-progress-line contract for valid goose
files whose Up section is empty — the only guard against a refactor that skips the transaction
or the progress line for statement-less files.

---

#### `test_reset_keeps_migrated_schema_and_replays_only_seed` (integration, `requires_docker`)

**Setup**: real postgres container via the existing integration harness: a `tmp_path` folder
with `00001_init.sql` (`CREATE TABLE customers (id serial PRIMARY KEY, email text);
CREATE TABLE orders (id serial PRIMARY KEY, customer int);`); `ServiceConfig(name="db",
kind="postgresql", migrations=MigrationsConfig(location=str(folder)))`; startup op
`sql_op("INSERT INTO customers (email) VALUES ('ann@x.io')")`; `run_migrations` spy-counting
wrapper.

**Input**: `engine.start([...seed...])`; then `engine.reset()`.

**Trace**:
```
start: container ready → plane open → _migrate → run_migrations (1st and only call)
  → schema applied (2 tables)
  → startup seed applied + journaled
reset: _wipe → CATALOG_QUERY discovers customers, orders → TRUNCATE ... RESTART IDENTITY CASCADE
  → journal replay → seed re-inserted
```

**Assertions**: after reset — `SELECT count(*) FROM customers` == 1 (seed replayed);
`SELECT count(*) FROM orders` == 0 (no seed); both tables still exist (schema survived);
`run_migrations` called exactly once across start+reset (never re-applied, never journaled).

**Sufficiency**: the role split end-to-end — migrations build the schema once per session and
survive resets; only journaled seed data replays. This is the feature's headline guarantee.

---

#### `test_service_config_migrations_default_is_none`

**Setup**: none.

**Input**: `ServiceConfig(name="db", kind="postgresql")`.

**Trace**: field default applies.

**Assertions**: `config.migrations is None`; a config built with
`migrations={"location": "x"}` yields `isinstance(config.migrations, MigrationsConfig)`.

**Sufficiency**: backward compatibility — every existing document (no migrations key) parses
to `None` and behaves exactly as before.

---

#### `test_migrations_models_reject_unknown_keys`

**Setup**: none.

**Input**: `MigrationsConfig(location="x", journal=True)` under `pytest.raises(ValidationError)`.

**Trace**: `extra="forbid"` rejects `journal`.

**Assertions**: validation error names `journal`.

**Sufficiency**: the declaration carries no version-tracking or journaling options — the
contract's "apply semantics are fixed" constraint.

---

## Additional Instructions for the Implementation Agent

- Implement in the arch order: **migrations cell first** (errors.py → goose.py → source.py →
  apply.py → `__init__.py` facade with exactly the eight `__all__` names: `MigrationFile`,
  `MigrationError`, `check_local_migrations`, `check_git_url`, `parse_migration_file`,
  `load_migration_set`, `apply_migrations`, `run_migrations`), then **config** (migrations.py
  models → loader `_validate_migrations` → facade exports `GitSource`, `MigrationsConfig`),
  then **engines** (base.py `_migrate` hook + start insertion → postgres.py override →
  build_engine docstring enumeration).
- Shared grammar: one module-level regex + one version-int helper in `goose.py`, imported by
  `source.py` — never duplicated.
- The server-message extraction in `apply.py` mirrors `engines/postgres.py::_server_message`
  (`exc.diag.message_primary or str(exc)`) but stays local to the migrations cell — no import
  from engines (the leaf must not depend upward).
- `git` URL rules (decision A): strict four schemes; empty-scheme (scp-style) rejected. Do not
  copy pull's empty-scheme bypass.
- Use relative imports inside each cell; `psycopg`, `git`, `pydantic` are absolute
  (third-party). No new `pyproject.toml` dependencies — `gitpython>=3.1`, `psycopg[binary]>=3.1`,
  `testcontainers[postgres]>=4.15` are already declared.
- `Sandbox.start` sequencing and the `sandbox/` (session runtime) cell stay untouched — the
  migration step lives entirely inside the engines cell.
- The `_migrate` hook in `BaseEngine` is a protected no-op default; only `PostgresEngine`
  overrides it. Do not add it to the engines CODEMANIFEST (protected hooks are not contract
  surface — same as `_build_container` et al.).
- Tests mirror the source layout: `tests/sandbox/migrations/{test_source,test_goose,test_apply}.py`
  plus `__init__.py`; extend `tests/sandbox/config/test_loader.py` (+ new
  `test_migrations.py`), `tests/sandbox/engines/test_base.py` and `test_postgres.py`.
- Validation: `pytest tests/ -x` and `ruff check goga_tool_pybuggy/` in a virtualenv.
- Out-of-DSL documentation updates (same feature, implementation stage): `docs/sandbox.md` and
  `docs/configuration.md` — the `migrations` declaration, the startup ordering, and the
  schema-vs-seed role split, consistent with `sandbox-file.md`.
