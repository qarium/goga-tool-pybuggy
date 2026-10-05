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
asks the core goga questions and then the pybuggy block under a heading with the tool name. The engine asks
everything the declarative records can express; the pybuggy-owned asks are the amendment-moment follow-ups —
`Add another spec?` with its per-field loop, then the autonomy confirm `Run the api.automate pipeline unattended?` —
run by the amendment hook right after the engine survey, specs first and autonomy last (a confirm-gated repeated
group is beyond the declarative records, and the autonomy question must not interleave the spec fields).

The session skips two core sections:

- the **base convention** — a pybuggy session never offers the goga language-convention download, because the engine
  would land it in `.goga/usages/conventions.md` first and the bootstrap's skip-if-exists gate would keep the wrong
  convention. The `conventions` slot is the bootstrap's delivery and always carries the packaged pybuggy test
  convention in a fresh project.
- the **docker image decision** — the engine's `Create Dockerfile?` gate never appears: a pybuggy project always
  carries a Dockerfile. The pybuggy block asks the base image (FROM — the goga-python family hints of the running
  minor tag, newest as the default) and the built-image name (`{project}:latest` from the git origin when
  derivable, a required input otherwise); the fixed path is always `.goga/Dockerfile`.

Session semantics that shape the modes:

- An existing `.goga/config.yml` ends the session immediately — no questions, no tool events, no artifacts.
  Whoever created the config first wins; it is never rewritten.
- In bare mode this case is unreachable through the CLI: the already-initialized guard refuses first.
- In template mode it is the expected path when the template brings its own `.goga/config.yml`: the session returns
  at once and only the bootstrap below runs.
- A failing tool contribution is soft: the engine discards it with a warning naming pybuggy and continues; the
  session still returns 0. This includes a Ctrl-C at the additional-spec or autonomy prompts.

Through the session pybuggy delivers two things: its questions (the image inputs, the tool configuration survey, the
surveyed additional specs, the autonomy confirm) and its tool config file `.goga/tools/pybuggy/config.yml`. It also
buffers the config amendments — the tool's declared intent in the session answer space:

- `build.review.skip: true` — the engine's config mapper does not carry that flag into the generated
  `.goga/config.yml`; the `pybuggy init` bootstrap enforces it afterwards (`ensure_review_skip`);
- the Dockerfile pair — the fixed `.goga/Dockerfile` path plus the answered FROM (the engine's generator writes the
  Dockerfile from exactly this pair) and the answered built-image name;
- the `tools` record `pybuggy: <installed-minor>.x` — merged over whatever the core tools question collected, so
  pybuggy is always recorded in `.goga/config.yml` whatever the answer to `Add tools?` was.

Consequence: a native `goga init -t pybuggy` session (without the pybuggy CLI) runs no bootstrap and sets no flag —
add `build.review.skip: true` by hand or run the bootstrap programmatically.

## The pybuggy bootstrap

After the session (bare and template modes only), the command delivers the files the session does not carry:

| Artifact | Gate |
|---|---|
| `.goga/usages/cooks/pybuggy/<stem>.md` — the packaged api usages | template: skip existing (INFO); bare: overwrite |
| commented example records for the absent members of `.goga/tools/pybuggy/config.yml` | added when the file exists, idempotent |
| `.goga/usages/conventions.md` — the `conventions` slot | skip-if-exists in both modes |
| `build.review.skip: true` in `.goga/config.yml` | always enforced, idempotent |
| the pybuggy install RUN line in the project Dockerfile (the config `dockerfile` field, default `.goga/Dockerfile`) | appended when the file exists, idempotent |
| the pybuggy usage keys and annotation lines in `.goga/config.yml` | always registered, idempotent |
| `conftest.py` at the project root | template: skip existing (INFO); bare: ask, default no |

A Dockerfile missing after the session fails the command with a non-zero exit — pybuggy requires one to carry its
install line. The session always creates the Dockerfile (the amendments deliver the fixed path and the answered
FROM), so the missing-file branch is the unreachable safety net of the mandatory-Dockerfile invariant, not a
declinable outcome of the survey.

## Upgrade mode

Only the template migration runs (copier run_update via the `.goga/scaffold.yml` state file); no onboarding prompts
appear, nothing else is written. A template without a persisted answers-file entry leaves `--upgrade` unusable: the
engine reports the missing state file with a non-zero exit, which the command propagates without wrapping. Engine
preconditions (a clean git repository, a git-trackable template, a non-decreasing version) surface as non-zero
exits.

## Programmatic usage (tests/scripts)

`run_init` is the testable entry point: it takes the three CLI values and returns an exit
code. It raises `click.ClickException` on an invalid flag combination (`<tpl>` with
`--upgrade`, or `--ref` without either) — at the CLI boundary click prints the message
and exits 1.
`run_session` and `run_bootstrap` are the seams behind it — stub them with monkeypatch to avoid the TTY and the
filesystem. `resolve_init_mode` is pure and safe to call directly.
