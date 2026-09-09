# pybuggy — CLI assembly and execution (composition root)

## Domain

Consumption patterns of the root cell `goga_tool_pybuggy/`: a package facade that defines the root Click group
`main`, loads `.env` into `os.environ` before any command executes, assembles the full CLI, and exposes the
`register_hooks` callback of the goga hooks platform. The audience: integrators who launch `pybuggy`
(console command or `python -m goga_tool_pybuggy`), external importers of the facade
(`from goga_tool_pybuggy import main`), and the goga hooks platform (which imports and calls `register_hooks`).

## Entry point

The package facade `pybuggy` exposes the root group `main`:

- Console command (entry point in `pyproject.toml`):

      pybuggy endpoint list

- Module execution (`goga_tool_pybuggy/__main__.py`):

      python -m goga_tool_pybuggy endpoint list

- Global option `--env-file` (BEFORE the subcommand) — loads `.env` into `os.environ` before the command runs:

      pybuggy --env-file ./my.env endpoint list      # explicit file (must exist)
      pybuggy endpoint list                          # implicit .env from CWD (absence handled silently)

- Spec-driven artifact scaffolding (`endpoint generate`, options `-s/--spec`, `-f/--force`):

      pybuggy endpoint generate -s shop
      pybuggy endpoint generate --spec shop --force

- Drift report (`endpoint diff`, options `-s/--spec`, variadic endpoint-ids):

      pybuggy endpoint diff
      pybuggy endpoint diff -s shop clients_startup_get

- Consumer-usages bootstrap (top-level `init`, no options):

      pybuggy init
      python -m goga_tool_pybuggy init

- Programmatic facade import:

      from goga_tool_pybuggy import main

## .env loading (global option --env-file and ctx.obj)

The root group `main` is the single load point for environment variables. The global option `--env-file` is
parsed at the group level, so the flag must come BEFORE the subcommand:

      pybuggy --env-file ./my.env <cmd>     # ✓ exit 0
      pybuggy <cmd> --env-file ./my.env     # ✗ exit 2 (No such option)

`load_env` in `env.py` implements two loading modes:

- **Explicit file** (`--env-file FILE`): the file must exist; otherwise a `click.ClickException` is raised.
  The file is loaded into `os.environ`.
- **Implicit `.env` from CWD** (flag absent): if `.env` exists in the CWD, it is loaded; if not, it is skipped
  silently (no error, no values).

`override=False` — variables already set in the environment are NOT overwritten. Loading completes BEFORE any
subcommand runs (eager callback of the root group).

The context object `ctx.obj` (type `EnvContext`, `env.py`) carries the resolved env-file path
(`env_path: str | None`) and the loaded values (`values: dict[str, str]`). Introducing a pass-object into the
root cell contract is deliberate: `ctx.obj` carries env context only; each command still loads its config
itself via `load_config()`.

> Note: the `pull` command receives `PYBUGGY_REF` through the `envvar=` binding of the `--ref` option in the
> click decorator (click reads `os.environ`), not from `ctx.obj` — loose coupling between cells is preserved.

## CLI assembly

Assembly lives in the `goga_tool_pybuggy/cli.py` module (owned by the root cell) and runs at import time:

1. Define the root group `main` (with the global option `--env-file` + an eager callback that loads the env).
2. Create the `endpoint` subgroup.
3. Register the commands `pull_cmd`, `list_cmd`, `info_cmd`, `generate_cmd`, `diff_cmd` on `endpoint`
   (from `goga_tool_pybuggy/commands/{pull,list,info,generate,diff}`).
4. Add the `endpoint` subgroup to `main`.
5. Register the top-level command `init_cmd` on `main` directly (from `goga_tool_pybuggy/commands/init`).
6. Export `main` via `__all__`. `load_env` and `EnvContext` are also available on the facade.

Top-level on `main`: `init`.
Registered under `endpoint`: `pull`, `list`, `info`, `generate`, `diff`.

## Static config

The config path is fixed (`.goga/tools/pybuggy/config.yml`, see `goga_tool_pybuggy.config.CONFIG_PATH`).
There is no `--config` option — commands load the config themselves via `load_config()` (no argument). The
pass-object `ctx.obj` exists but carries only the env context (`EnvContext`), not the config.

## goga hooks platform integration

The facade exposes one more entry point beside the CLI: `register_hooks` — the callback the goga hooks
platform imports and calls when a command first reaches a hook checkpoint of the run (inspect the registry
with `goga hooks`). A plain `import goga_tool_pybuggy` never triggers it; the platform owns the call.

`register_hooks` subscribes two status hooks to the single address statuses / register_statuses:

| Hook name | Callable | Registers |
|-----------|----------|-----------|
| `automate` | `register_automate_statuses` | the five PybuggyApiAutomate pipeline stages |
| `fix` | `register_fix_statuses` | the five PybuggyApiFix pipeline stages |

The tool identity (`pybuggy`) is assigned by the platform from the package name — the package never names
itself. Every registered status is stored and shown qualified: `pybuggy.<name>`.

The registered topic statuses (artifact paths relative to the topic directory):

| Qualified status | Artifact | Anchors |
|------------------|----------|---------|
| `pybuggy.automate.requirements-created` | `requirements.md` | after `defined`, before `discovered` |
| `pybuggy.automate.testcases-designed` | `testcases.md` | after `backlog`, before `designed` |
| `pybuggy.automate.cells-prepared` | `arch.md` | after `designed`, before `specified` |
| `pybuggy.automate.code-designed` | `design.md` | after `specified`, before `planned` |
| `pybuggy.automate.coding-planned` | `plan.md` | after `planned`, before `done` |
| `pybuggy.fix.collected` | `fix-collect.md` | after `done` |
| `pybuggy.fix.analyzed` | `fix-analysis.md` | after `pybuggy.fix.collected` |
| `pybuggy.fix.planned` | `fix-plan.md` | after `pybuggy.fix.analyzed` |
| `pybuggy.fix.executed` | `fix-execute.md` | after `pybuggy.fix.planned` |
| `pybuggy.fix.reviewed` | `fix-review.md` | after `pybuggy.fix.executed` |

The automate stages land between their built-in neighbors on the status scale; the arch/design/plan artifacts
are the same files as their built-in twins. The fix chain rides above the built-in top (`done`) in pipeline
order. Registration is add-only and never cached — package edits apply from the next run, without reinstall.

## Preconditions and side effects

- `import goga_tool_pybuggy` triggers the full CLI assembly (imports `click` and all command cells).
- Running a command requires a valid config at the fixed path; loading and validation happen via `load_config`
  in the subcommand.
- `--env-file` (explicit) or `.env` from the CWD (implicit) is loaded into `os.environ` (`override=False`)
  before the command runs; the values are available to all subcommands via `os.environ`
  (e.g. `PYBUGGY_REF` for `pull`).
- `init` is a top-level command and does NOT require the pybuggy config: it operates on the consumer's
  goga-project config (`<cwd>/.goga/config.yml`) and reads usages from the installed package.
