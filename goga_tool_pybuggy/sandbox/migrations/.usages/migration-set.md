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
