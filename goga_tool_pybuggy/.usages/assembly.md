# pybuggy — CLI assembly and execution (composition root)

## Domain

Consumption patterns of the root cell `goga_tool_pybuggy/`: a package facade that defines the root Click group
`main`, loads `.env` into `os.environ` before any command executes, and assembles the full CLI. The audience:
integrators who launch `pybuggy` (console command or `python -m goga_tool_pybuggy`) and external importers of
the facade (`from goga_tool_pybuggy import main`).

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
3. Register the commands `pull_cmd`, `list_cmd`, `info_cmd`, `generate_cmd` on `endpoint`
   (from `goga_tool_pybuggy/commands/{pull,list,info,generate}`).
4. Add the `endpoint` subgroup to `main`.
5. Register the top-level command `init_cmd` on `main` directly (from `goga_tool_pybuggy/commands/init`).
6. Export `main` via `__all__`. `load_env` and `EnvContext` are also available on the facade.

Top-level on `main`: `init`.
Registered under `endpoint`: `pull`, `list`, `info`, `generate`.

## Static config

The config path is fixed (`.goga/tools/pybuggy/config.yml`, see `goga_tool_pybuggy.config.CONFIG_PATH`).
There is no `--config` option — commands load the config themselves via `load_config()` (no argument). The
pass-object `ctx.obj` exists but carries only the env context (`EnvContext`), not the config.

## Preconditions and side effects

- `import goga_tool_pybuggy` triggers the full CLI assembly (imports `click` and all command cells).
- Running a command requires a valid config at the fixed path; loading and validation happen via `load_config`
  in the subcommand.
- `--env-file` (explicit) or `.env` from the CWD (implicit) is loaded into `os.environ` (`override=False`)
  before the command runs; the values are available to all subcommands via `os.environ`
  (e.g. `PYBUGGY_REF` for `pull`).
- `init` is a top-level command and does NOT require the pybuggy config: it operates on the consumer's
  goga-project config (`<cwd>/.goga/config.yml`) and reads usages from the installed package.
