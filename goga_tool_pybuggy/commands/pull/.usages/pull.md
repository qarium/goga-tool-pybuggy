# goga_tool_pybuggy.commands.pull — the endpoint pull command

## Domain

Consumption patterns of the cell `goga_tool_pybuggy/commands/pull`: download specs from git sources into local `location`
directories. The audience: CLI registration (`pull_cmd`) and tests (call `run_pull` directly).

## Entry point

`run_pull` is the testable entry point. The Click wrapper `pull_cmd` only binds the options and calls `run_pull`:

    from goga_tool_pybuggy.commands.pull import run_pull

    run_pull(spec_name=None)                                    # pull all specs
    run_pull(spec_name="client")                               # only a single spec
    run_pull(spec_name="client", ref="v2")                     # the same spec, a global ref
    run_pull(spec_name=None, ref=(("client", "v1"), ("server", "v2")))  # per-spec ref

CLI form (`pull_cmd`):

    pybuggy endpoint pull                       # pull all specs
    pybuggy endpoint pull --spec client         # only a single spec
    pybuggy endpoint pull --ref v2              # a global ref for all pulled specs
    pybuggy endpoint pull --spec client --ref v2
    pybuggy endpoint pull --ref client:v1 --ref server:v2   # different refs for different specs
    pybuggy endpoint pull --ref v2 --ref server:v3          # global v2, but server pinned to v3

`--ref` is repeatable (`multiple=True`) and parsed by `SmartParam`:
- without `:` — a **global** ref applied to all selected specs;
- `NAME:REF` — a **per-spec** override only for spec `NAME`.

## The PYBUGGY_REF environment variable

A git ref can be set via the `PYBUGGY_REF` environment variable (without the command option) — it is **the default value
for `--ref`** taken from the environment. Convenient for CI and for pinning several repositories to a single ref:

    export PYBUGGY_REF=v2
    pybuggy endpoint pull                      # all specs at ref v2 (if there is no --ref/git.ref)
    PYBUGGY_REF=v2 pybuggy endpoint pull --spec client

`PYBUGGY_REF` is bound to `--ref` via `envvar=` in the click decorator (`show_envvar=True`): when `--ref` is not passed
explicitly, click reads `PYBUGGY_REF` from `os.environ` and supplies it as the value of `--ref` (an empty `PYBUGGY_REF`
is treated as unset). The value appears in `os.environ` when the root CLI group loads `.env` (the eager callback
`--env-file`) — therefore `PYBUGGY_REF` can be set either in the shell environment or via `.env`.
An explicit `--ref` (global or per-spec) **fully overrides** `PYBUGGY_REF`; `run_pull`/`_effective_ref` do not read
the environment variable — its resolution lives in the Click wrapper `pull_cmd`.

## Behavior

- A spec with `git` → shallow-clone of `git.url` (depth=1) into a temporary directory at the **effective ref**, then copy
  `git.location` → `<project_root>/<location>` (overwrite, idempotent).
- Effective ref priority (per spec): per-spec override (`NAME:REF`) → global ref from `--ref`/`ref` (if passed
  explicitly; otherwise `PYBUGGY_REF`, bound to `--ref` via the click envvar) → `git.ref` from the configuration →
  the default branch. Absence/`None` at any level ⇒ fall through to the next; `None` in `git.ref` ⇒ the default branch.
  An explicit `--ref` fully overrides `PYBUGGY_REF`.
- The global `--ref`/`ref` (including `PYBUGGY_REF` as its default value) applies to all selected specs
  in one call, but a per-spec `NAME:REF` overrides it for the specified spec. A per-spec ref with a name absent from the
  configuration → `click.ClickException`. For configs with specs from different repositories: a global ref without `--spec`
  applies to each repository and requires the branch/tag to exist in all of them; a per-spec `NAME:REF` lifts
  this requirement (a different ref for each repository).
- A spec without `git` → skip (local-only), without an error.
- `--spec <name>` narrows the selection to a single spec.
- The config is loaded from the fixed path (`.goga/tools/pybuggy/config.yml`) via `load_config()`.
- Clone/missing-path errors → `click.ClickException` (a single non-zero exit).

## Preconditions

- The config is valid and located at the fixed path `.goga/tools/pybuggy/config.yml`.
- Tokens are not embedded in clone URLs — rely on git credential helpers.
- The repository is read-only (no commit/push).
- `PYBUGGY_REF` is optional; the root CLI group loads `.env` (an explicit `--env-file` or `.env` from the CWD) before
  the command starts, so `PYBUGGY_REF` can be set either in the shell environment or via `.env`.
