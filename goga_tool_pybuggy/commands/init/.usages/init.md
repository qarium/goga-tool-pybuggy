# goga_tool_pybuggy.commands.init — goga project initialization and pybuggy bootstrap

## Domain

The `pybuggy init` command **initializes the goga project** and **bootstraps the pybuggy test environment** in the
directory where it is invoked. It operates in three modes selected by the CLI arguments:

- **bare** (`pybuggy init`) — interactive onboarding of a fresh project; refused (exit 1) when `.goga/` already
  exists — the same already-initialized guard `goga init` applies;
- **template** (`pybuggy init <tpl> [--ref <git-ref>]`) — scaffold a copier-compatible template project first, then
  run the onboarding session and the pybuggy bootstrap with skip-if-exists gates;
- **upgrade** (`pybuggy init --upgrade [--ref <git-ref>]`) — migrate a previously scaffolded project to a newer
  template version; no onboarding.

The audience is the integrator wiring pybuggy into their project (`goga install pybuggy`), and the consumer's goga
agent.

## CLI surface

- `pybuggy init` — bare onboarding.
- `pybuggy init <tpl>` — template onboarding. `<tpl>` is a local path or a git URL of a copier-compatible template
  project, optionally carrying a `#ref` fragment (`https://host/repo.git#v2`).
- `--ref <git-ref>` — overrides the template ref: beats the URL fragment in template mode; sets the migration target
  in upgrade mode.
- `--upgrade` — template migration only (the template source is read from `.goga/scaffold.yml`).

Flag rules (mirroring `goga init`): `<tpl>` and `--upgrade` are mutually exclusive; `--ref` requires `<tpl>` or
`--upgrade`. Violations print an error message and exit with code 1.

The command stays interactive: the onboarding session (the core goga questions plus the pybuggy block) and the
copier TUI (template questions) require a TTY.

## The onboarding session

`pybuggy init` and a native `goga init -t pybuggy` run the **same** engine session with pybuggy invited. The engine
asks the core goga questions and then the pybuggy block under a heading with the tool name; pybuggy never prompts on
its own.

Session semantics that shape the modes:

- An existing `.goga/config.yml` ends the session immediately — no questions, no tool events, no artifacts.
  Whoever created the config first wins; it is never rewritten.
- In bare mode this case is unreachable through the CLI: the already-initialized guard refuses first.
- In template mode it is the expected path when the template brings its own `.goga/config.yml`: the session returns
  at once and only the bootstrap below runs.
- A failing tool contribution is soft: the engine discards it with a warning naming pybuggy and continues; the
  session still returns 0.

Through the session pybuggy delivers two things: its questions (the tool configuration survey) and its tool config
file `.goga/tools/pybuggy/config.yml`. It also buffers the `build.review.skip: true` amendment — the tool's declared
intent in the session answer space. The engine's config mapper does not carry that flag into the generated
`.goga/config.yml`; the `pybuggy init` bootstrap enforces it afterwards (`ensure_review_skip`). Consequence: a
native `goga init -t pybuggy` session (without the pybuggy CLI) runs no bootstrap and sets no flag — add
`build.review.skip: true` by hand or run the bootstrap programmatically.

## The pybuggy bootstrap

After the session (bare and template modes only), the command delivers the files the session does not carry:

| Artifact | Gate |
|---|---|
| `.goga/usages/cooks/pybuggy/<stem>.md` — the packaged api usages | template: skip existing (INFO); bare: overwrite |
| `.goga/usages/conventions.md` — the `conventions` slot | skip-if-exists in both modes |
| `build.review.skip: true` in `.goga/config.yml` | always enforced, idempotent |
| the pybuggy install RUN line in the project Dockerfile (the config `dockerfile` field, default `.goga/Dockerfile`) | appended when the file exists, idempotent |
| the pybuggy usage keys and annotation lines in `.goga/config.yml` | always registered, idempotent |
| `conftest.py` at the project root | template: skip existing (INFO); bare: ask, default no |

A Dockerfile missing after the session fails the command with a non-zero exit — pybuggy requires one to carry its
install line. This includes the decline branch: the session's core confirm "Create Dockerfile?" defaults to No, and
answering No leaves no Dockerfile at all — the command then fails after the session artifacts are written (a repeat
bare `pybuggy init` is refused by the already-initialized guard; create the Dockerfile at the config `dockerfile`
path yourself, or remove `.goga` and re-run).

## Upgrade mode

Only the template migration runs (copier run_update via the `.goga/scaffold.yml` state file); no onboarding prompts
appear, nothing else is written. A template without a persisted answers-file entry leaves `--upgrade` unusable: the
engine reports the missing state file with a non-zero exit, which the command propagates without wrapping. Engine
preconditions (a clean git repository, a git-trackable template, a non-decreasing version) surface as non-zero
exits.

## Programmatic usage (tests/scripts)

`run_init` is the testable entry point: it takes the three CLI values and returns an exit code, never raising.
`run_session` and `run_bootstrap` are the seams behind it — stub them with monkeypatch to avoid the TTY and the
filesystem. `resolve_init_mode` is pure and safe to call directly.
