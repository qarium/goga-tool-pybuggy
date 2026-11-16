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

- Page-object scaffolding for the web kind (`page generate`, positional PATH + optional NAME,
  `-f/--force`):

      pybuggy page generate /admin/api/v1/mocks
      pybuggy page generate /login login --force

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
6. Create the `page` subgroup and register the command `page_generate_cmd` on it (from
   `goga_tool_pybuggy/commands/page`), then add the subgroup to `main`.
7. Export `main` via `__all__`. `load_env` and `EnvContext` are also available on the facade.

Top-level on `main`: `init`.
Registered under `endpoint`: `pull`, `list`, `info`, `generate`, `diff`.
Registered under `page`: `generate`.

## Static config

The api tool config location is fixed by the platform path standard for tool configs
(`.goga/tools/pybuggy/api.yml`); the config cell reads the file through the platform facade. The web kind owns its
own tool config document — `web.yml`, read by the web cell — so each test kind carries its own configuration.
There is no `--config` option — commands load the
config themselves via `load_config()` (no argument). The pass-object `ctx.obj` exists but carries only the env
context (`EnvContext`), not the config.

## goga hooks platform integration

The facade exposes two more entry points beside the CLI: `register_hooks` — the callback the goga hooks
platform imports and calls when a command first reaches a hook checkpoint of the run (inspect the registry
with `goga hooks`); and `install` — the post-install hook `goga install` calls after a successful pip
(owned by the `goga_tool_pybuggy/lifecycle` cell: installs the `@playwright/cli` agent CLI via npm —
npm absent is a warning skip, a failing command fails the install). A plain `import goga_tool_pybuggy`
never triggers either; the platform owns the calls.

`register_hooks` lives in `goga_tool_pybuggy/reg_hooks.py` and subscribes seven hooks to four addresses —
the statuses registration action (four status lines), the two onboarding actions, and the pipeline
amendment action:

| Hook name | Callable | Address | Registers / contributes |
|-----------|----------|---------|------------------------|
| `api.automate` | `register_automate_statuses` | statuses / register_statuses | the six api-automate-line statuses (including the completed-accept `api.automate.done`) |
| `web.automate` | `register_web_statuses` | statuses / register_statuses | the four web-automate-line statuses (no testcases/arch — the web pipeline writes no such artifacts) |
| `api.fix` | `register_fix_statuses` | statuses / register_statuses | the five api-fix-line statuses |
| `api.patch` | `register_patch_statuses` | statuses / register_statuses | the six api-patch-line statuses |
| `declare` | `declare_pybuggy_session` | onboarding / declare_session | the pybuggy question block of the session survey |
| `amend` | `amend_pybuggy_config` | onboarding / amend_config | the `build.review.skip` amendment and the tool config file |
| `autonomy` | `amend_workflow` | pipeline / amend_workflow | the autonomous workflow amendment (auto-approval window + build stage) for a qualifying run |

The status hook callables live in `goga_tool_pybuggy/statuses`, the autonomy hook callable in
`goga_tool_pybuggy/autonomous`, the onboarding hook callables in `goga_tool_pybuggy/commands/init` — none is
re-exported on the package facade, only `register_hooks` is; the platform reaches them through its
subscription. The onboarding handlers return immediately when the session did not invite pybuggy
(`goga init` without `-t pybuggy`); the autonomy hook is a silent no-op unless the running pipeline is one of
the qualifying pipelines (`pybuggy:api.automate`, `pybuggy:api.patch`, `pybuggy:web.automate`) with autonomy
enabled for its axis in the tool config `pipelines` axis — the api axes of `api.yml`, the web axis of `web.yml`.

The tool identity (`pybuggy`) is assigned by the platform from the package name — the package never names
itself. Every registered status is stored and shown qualified: `pybuggy.<name>`.

The registered topic statuses (artifact paths relative to the topic directory):

| Qualified status | Artifact | Anchors |
|------------------|----------|---------|
| `pybuggy.api.automate.done` | `completed/plan.md` | after `done` |
| `pybuggy.api.automate.coding-planned` | `plan.md` | after `planned`, before `pybuggy.api.automate.done` |
| `pybuggy.api.automate.code-designed` | `design.md` | after `designed`, before `pybuggy.api.automate.coding-planned` |
| `pybuggy.api.automate.arch-prepared` | `arch.md` | after `designed`, before `pybuggy.api.automate.code-designed` |
| `pybuggy.api.automate.testcases-designed` | `testcases.md` | after `backlog`, before `pybuggy.api.automate.arch-prepared` |
| `pybuggy.api.automate.requirements-created` | `requirements.md` | after `defined`, before `pybuggy.api.automate.testcases-designed` |
| `pybuggy.web.automate.done` | `completed/plan.md` | after `done` |
| `pybuggy.web.automate.planned` | `plan.md` | after `planned`, before `pybuggy.web.automate.done` |
| `pybuggy.web.automate.designed` | `design.md` | after `designed`, before `pybuggy.web.automate.planned` |
| `pybuggy.web.automate.requirements-created` | `requirements.md` | after `defined`, before `pybuggy.web.automate.designed` |
| `pybuggy.api.fix.collected` | `fix-collect.md` | after `empty` |
| `pybuggy.api.fix.analyzed` | `fix-analysis.md` | after `pybuggy.api.fix.collected` |
| `pybuggy.api.fix.planned` | `fix-plan.md` | after `pybuggy.api.fix.analyzed` |
| `pybuggy.api.fix.executed` | `fix-execute.md` | after `pybuggy.api.fix.planned` |
| `pybuggy.api.fix.reviewed` | `fix-review.md` | after `pybuggy.api.fix.executed` |
| `pybuggy.api.patch.intended` | `intent.md` | after `empty` |
| `pybuggy.api.patch.analyzed` | `impact.md` | after `pybuggy.api.patch.intended` |
| `pybuggy.api.patch.applied` | `apply.md` | after `pybuggy.api.patch.analyzed` |
| `pybuggy.api.patch.designed` | `rework.md` | after `pybuggy.api.patch.applied` |
| `pybuggy.api.patch.planned` | `workplan.md` | after `pybuggy.api.patch.designed` |
| `pybuggy.api.patch.done` | `completed/workplan.md` | after `pybuggy.api.patch.planned` |

The automate statuses register in reverse pipeline order: `api.automate.done` lands above the built-in `done`,
and each middle status anchors above its built-in twin and below the previously registered automate status
(the arch/design/plan artifacts are the same files as their built-in twins); the web automate line stacks the
same way over its own four artifacts — it shares the requirements/design/plan file names with the api line,
and both lines apply independently. The fix chain starts above the
built-in `empty` and stacks in pipeline order, every status anchored to its predecessor; the patch chain
stacks the same way above `empty` — an independent chain that never reorders the automate line.
Registration is add-only and never cached — package edits apply from the next run, without reinstall.

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

The facade also re-exports the capability surfaces of the test kinds — `services` (the
per-test data-preset decorator of the sandbox kind) and `generation_prompt` (the per-test
extra generation-instructions decorator of the web kind) — so consumer tests import them from
the package root: `from goga_tool_pybuggy import services`, `from goga_tool_pybuggy import
generation_prompt`. The session sandbox fixture and the web runtime fixture are product-owned
through the plugin installation and need no facade import.
