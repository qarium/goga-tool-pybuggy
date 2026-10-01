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

- Project initialization and bootstrap (top-level `init`, three modes):

      pybuggy init                                  # bare onboarding (refused over an existing .goga/)
      pybuggy init <tpl> [--ref <git-ref>]          # scaffold a template, then onboard
      pybuggy init --upgrade [--ref <git-ref>]      # migrate a scaffolded template only

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

The config location is fixed by the platform path standard for tool configs (`.goga/tools/pybuggy/config.yml`);
the config cell reads the file through the platform facade. There is no `--config` option — commands load the
config themselves via `load_config()` (no argument). The pass-object `ctx.obj` exists but carries only the env
context (`EnvContext`), not the config.

## goga hooks platform integration

The facade exposes one more entry point beside the CLI: `register_hooks` — the callback the goga hooks
platform imports and calls when a command first reaches a hook checkpoint of the run (inspect the registry
with `goga hooks`). A plain `import goga_tool_pybuggy` never triggers it; the platform owns the call.

`register_hooks` lives in `goga_tool_pybuggy/reg_hooks.py` and subscribes five hooks to four addresses —
the statuses registration action, the two onboarding actions, and the pipeline amendment action:

| Hook name | Callable | Address | Registers / contributes |
|-----------|----------|---------|------------------------|
| `automate` | `register_automate_statuses` | statuses / register_statuses | the six automate-line statuses (including the completed-accept `automate.done`) |
| `fix` | `register_fix_statuses` | statuses / register_statuses | the five fix-line statuses |
| `declare` | `declare_pybuggy_session` | onboarding / declare_session | the pybuggy question block of the session survey |
| `amend` | `amend_pybuggy_config` | onboarding / amend_config | the `build.review.skip` amendment and the tool config file |
| `autonomy` | `amend_workflow` | pipeline / amend_workflow | the autonomous workflow amendment (auto-approval window + build stage) for a qualifying run |

The status hook callables live in `goga_tool_pybuggy/statuses`, the autonomy hook callable in
`goga_tool_pybuggy/autonomous`, the onboarding hook callables in `goga_tool_pybuggy/commands/init` — none is
re-exported on the package facade, only `register_hooks` is; the platform reaches them through its
subscription. The onboarding handlers return immediately when the session did not invite pybuggy
(`goga init` without `-t pybuggy`); the autonomy hook is a silent no-op unless the running pipeline is
`api.automate` with autonomy enabled in the tool config `pipelines` axis.

The tool identity (`pybuggy`) is assigned by the platform from the package name — the package never names
itself. Every registered status is stored and shown qualified: `pybuggy.<name>`.

The registered topic statuses (artifact paths relative to the topic directory):

| Qualified status | Artifact | Anchors |
|------------------|----------|---------|
| `pybuggy.automate.done` | `completed/plan.md` | after `done` |
| `pybuggy.automate.coding-planned` | `plan.md` | after `planned`, before `pybuggy.automate.done` |
| `pybuggy.automate.code-designed` | `design.md` | after `specified`, before `pybuggy.automate.coding-planned` |
| `pybuggy.automate.arch-prepared` | `arch.md` | after `designed`, before `pybuggy.automate.code-designed` |
| `pybuggy.automate.testcases-designed` | `testcases.md` | after `backlog`, before `pybuggy.automate.arch-prepared` |
| `pybuggy.automate.requirements-created` | `requirements.md` | after `defined`, before `pybuggy.automate.testcases-designed` |
| `pybuggy.fix.collected` | `fix-collect.md` | after `empty` |
| `pybuggy.fix.analyzed` | `fix-analysis.md` | after `pybuggy.fix.collected` |
| `pybuggy.fix.planned` | `fix-plan.md` | after `pybuggy.fix.analyzed` |
| `pybuggy.fix.executed` | `fix-execute.md` | after `pybuggy.fix.planned` |
| `pybuggy.fix.reviewed` | `fix-review.md` | after `pybuggy.fix.executed` |

The automate statuses register in reverse pipeline order: `automate.done` lands above the built-in `done`,
and each middle status anchors above its built-in twin and below the previously registered automate status
(the arch/design/plan artifacts are the same files as their built-in twins). The fix chain starts above the
built-in `empty` and stacks in pipeline order, every status anchored to its predecessor. Registration is
add-only and never cached — package edits apply from the next run, without reinstall.

## Preconditions and side effects

- `import goga_tool_pybuggy` triggers the full CLI assembly (imports `click` and all command cells).
- Running a command requires a valid config at the fixed path; loading and validation happen via `load_config`
  in the subcommand.
- `--env-file` (explicit) or `.env` from the CWD (implicit) is loaded into `os.environ` (`override=False`)
  before the command runs; the values are available to all subcommands via `os.environ`
  (e.g. `PYBUGGY_REF` for `pull`).
- `init` is a top-level command and does NOT require the pybuggy config: it runs a goga onboarding session with
  pybuggy invited (an existing `.goga/config.yml` ends the session immediately) and then bootstraps the consumer's
  pybuggy environment (packaged usages, `conventions` slot, `build.review.skip`, Dockerfile install line, root
  conftest).
