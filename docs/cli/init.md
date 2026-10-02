# CLI — `goga tool pybuggy init`

Initializes the goga project and bootstraps the consumer's pybuggy environment — bare,
from a template, or as a template upgrade. Top-level command (not under `endpoint`);
also available as `python -m goga_tool_pybuggy init`.

## Synopsis

```bash
goga tool pybuggy init [<tpl>] [--ref <git-ref>] [--upgrade]
```

- `pybuggy init` — bare initialization.
- `pybuggy init <tpl>` — template initialization. `<tpl>` is a local path or a git URL of a
  copier-compatible template project, optionally carrying a `#ref` fragment
  (`https://host/repo.git#v2`).
- `--ref <git-ref>` — overrides the template ref: beats the URL fragment in template
  mode; sets the migration target in upgrade mode.
- `--upgrade` — template migration only (the template source is read from
  `.goga/scaffold.yml`).

## Modes

| Mode | Invocation | Behavior |
|------|------------|----------|
| **bare** | `init` | Onboarding session of a fresh project + bootstrap with confirm gates; refused (exit 1) when `.goga/` already exists — the same guard `goga init` applies |
| **template** | `init <tpl> [--ref]` | Scaffold the template project first, then run the session and the bootstrap with silent-skip gates |
| **upgrade** | `init --upgrade [--ref]` | Migrate a previously scaffolded project to a newer template version; no session, no bootstrap |

Flag rules (mirroring `goga init`): `<tpl>` and `--upgrade` are mutually exclusive;
`--ref` requires `<tpl>` or `--upgrade`. Violations print an error message and exit
with code `1`.

**Template mode.** Scaffolding runs first (`goga.scaffold` engine, copier underneath):
the template is rendered into the current working directory; only `project_name` is
injected programmatically — the remaining template questions are asked interactively.
A failed scaffold stops the command with the engine's exit code — **no onboarding side
effects are applied**. After a successful scaffold the onboarding session runs (it
ends at once when the template brought its own `.goga/config.yml` — see below), and
the bootstrap applies **silent-skip gates**: an existing file is left untouched with
an INFO log and no interactive confirmation; a missing file is created through the
normal flow.

**Upgrade mode.** Only the template migration runs (copier `run_update` via the
`.goga/scaffold.yml` state file); no session prompts appear, nothing else is
written. The state file is persisted by the template itself (the answers-file entry) —
a template without one leaves `--upgrade` unusable: the engine reports the missing
state file with a non-zero exit. Engine preconditions (a clean git repository, a
git-trackable template, a non-decreasing version) surface as non-zero exits; the
command propagates them without wrapping.

## The onboarding session

`pybuggy init` and a native `goga init -t pybuggy` run the **same** engine session
(`goga.onboarding`, goga ≥ 2.0.1) with pybuggy invited: the engine asks the core goga
questions — the language, the optional codemanifest / build-agent / pipeline sections,
the Dockerfile — and then the pybuggy block under a heading with the tool name.
pybuggy never prompts on its own: it declares its questions through the
`declare_session` hook and the engine asks them; the `amend_config` hook contributes
the tool config file.

Session semantics that shape the modes:

- An existing `.goga/config.yml` ends the session immediately — no questions, no tool
  events, no artifacts. Whoever created the config first wins; it is never rewritten.
- In bare mode this case is unreachable through the CLI: the already-initialized guard
  refuses first.
- In template mode it is the expected path when the template brings its own
  `.goga/config.yml`: the session returns at once and only the bootstrap runs.
- A failing tool contribution is soft: the engine discards it with a warning naming
  pybuggy and continues; the session still returns 0.

Through the session pybuggy delivers the tool config file
`.goga/tools/pybuggy/config.yml` and buffers the `build.review.skip: true` amendment —
the tool's declared intent in the session answer space. The engine's config mapper
does not carry that flag into the generated `.goga/config.yml`; the bootstrap enforces
it afterwards. Consequence: a native `goga init -t pybuggy` session (without the
pybuggy CLI) runs no bootstrap and sets no flag — add `build.review.skip: true` and
the pybuggy-owned files by hand, or run the pybuggy CLI (see `MIGRATION.md` at the
repository root).

## What the command does

Two stages in bare and template modes; upgrade mode skips both.

**Stage 1 — the onboarding session** (see above). Writes `.goga/config.yml`, the
Dockerfile (when the "Create Dockerfile?" confirm is answered Yes), and
`.goga/tools/pybuggy/config.yml`. A non-zero session exit stops the command — the
bootstrap is skipped, the code is propagated unchanged.

**Stage 2 — the pybuggy bootstrap.** Delivers the files the session does not carry:

| Artifact | Gate |
|----------|------|
| `.goga/usages/cooks/pybuggy/<stem>.md` — the packaged api usages (`api.md`, `asserts.md`) | template: skip existing (INFO); bare: overwrite |
| `.goga/usages/conventions.md` — the `conventions` slot | skip-if-exists in both modes |
| `build.review.skip: true` in `.goga/config.yml` | always enforced, idempotent |
| the pybuggy install `RUN` line in the project Dockerfile (the config `dockerfile` field, default `.goga/Dockerfile`) | appended when the file exists, idempotent |
| the pybuggy usage keys and annotation lines in `.goga/config.yml` (`codemanifest`) | always registered, idempotent |
| `conftest.py` at the project root | template: skip existing (INFO); bare: ask, default no |

The install line is derived from the **installed pybuggy version** — e.g. an
installed `2.0.3` yields `RUN goga install pybuggy -v 2.0.x` (a minor x-range is a
valid `goga install` version form); there is no hardcoded version pin. The Dockerfile
path is resolved from the consumer config `dockerfile` field so the line lands in the
project's actual Dockerfile (a custom session answer wins).

**The mandatory Dockerfile.** A Dockerfile missing after the session fails the
command with a non-zero exit — pybuggy requires one to carry its install line. This
includes the decline branch: the session's core confirm "Create Dockerfile?" defaults
to No, and answering No leaves no Dockerfile at all — the command then completes the
bootstrap steps and fails (the session artifacts stay written). Recovery: create the
Dockerfile at the config `dockerfile` path (default `.goga/Dockerfile`) and re-run the
registrations by hand, or remove `.goga` and re-run — a repeat bare `pybuggy init` is
refused by the already-initialized guard.

## Interactive tool-config survey

The pybuggy block of the session builds `.goga/tools/pybuggy/config.yml`. What is
asked (by the engine):

- `base_url` — **required** (empty input is re-asked). A Jinja2 URL template — a plain
  URL is a valid template that renders to itself.
- The optional scalar plugin keys, one input each, skippable with Enter: `timeout`,
  `retries`, `assert_timeout`, `assert_delay`, `assert_field_class`,
  `assert_response_class`. Numeric answers are coerced (`timeout`/`assert_delay` →
  float, `retries`/`assert_timeout` → int).
- The first spec, field by field: `name`, `type` (a choice of `swagger`|`openapi`),
  `location` — all required — and the optional git fields `git_url`, `git_location`,
  `git_ref`. A git block is attached only when both `git_url` and `git_location` are
  non-empty; an empty `git_ref` means the default branch. The first spec is validated
  strictly, so at least one spec always lands in the config.
- The autonomy confirm, asked after the `first_spec` group as the last declared pybuggy
  question: `Run the api.automate pipeline unattended (autonomous mode)?` — default No.
  Answering Yes is the one way the session writes a `pipelines` axis entry into the tool
  config:

  ```yaml
  pipelines:
    api.automate:
      autonomous: true
  ```

  The default (or declined) answer writes nothing — the entry is dropped like any
  unanswered key, and the project's `api.automate` runs stay fully interactive (see
  [Autonomous runs](../pipelines/api-automate.md#autonomous-runs)).
- `extra_specs` — optional. Additional specs, one per line, in the compact form:

  ```
  name|type|location|git_url|git_location|git_ref
  ```

  A line carrying fewer than the three required fields (name, type, location) is
  malformed — it is skipped with a warning; the rest of the contribution is
  unaffected. A name colliding with an earlier spec keeps the earlier spec and warns.

`headers` and `loader` are **never surveyed**, and the tool config is written as plain
YAML carrying only the answered values (unanswered keys are dropped, never written
empty; no commented examples are emitted). The two complex sections stay documented
as hand-added examples:

```yaml
# headers:                        # optional section, hand-added: mapping of header name to value/template
#   X-Api-Key: "{{ API_KEY }}"
# loader:                         # optional section, hand-added: packages/modules structure
#   packages: [api]
```

The generated file is valid for [configuration](../configuration.md) loading.

## Idempotency

- **Bare mode.** A repeated invocation refuses up front, exactly like `goga init`: when
  `.goga/` already exists the command prints `Project already initialized` to stderr and
  exits with code `1` — no prompts, and not a single file is updated (the copied usages
  are not refreshed, the configs and `conftest.py` are not re-created). To re-run the
  initialization, delete `.goga/` first. There are no `--force`/`--dry-run` flags.
- **Template mode.** A repeated `init <tpl>` re-runs the scaffold (engine semantics);
  the session ends at once over an existing `.goga/config.yml`, and the bootstrap
  silently skips every existing gated file — no prompts.
- **Upgrade mode.** No session or bootstrap state is touched; the migration itself is
  managed by the engine.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Invalid flag combination (`<tpl>` with `--upgrade`; `--ref` without `<tpl>`/`--upgrade`); project already initialized (bare invocation over an existing `.goga/` — zero writes); a failed bootstrap step or a Dockerfile missing after the session (ERROR-logged, never a raised exception) |
| scaffold engine code | A failed scaffold or migration — propagated unchanged; a failed scaffold leaves **no** onboarding side effects |
| session code | A non-zero onboarding-session exit — propagated unchanged; the bootstrap is skipped |

## Preconditions and side effects

- Requires the installed `goga` package ≥ 2.0.1 (a pybuggy dependency) — for the
  onboarding session and the scaffold engine.
- Writes to `<cwd>/.goga/` (config, the Dockerfile install line, usages, the tool
  config) and `<cwd>/conftest.py`; the scaffold engine renders template files into
  `<cwd>` and may persist `.goga/scaffold.yml` (template-owned; it must not be
  git-ignored in a scaffolded project, or `--upgrade` stops working).
- Reads assets from the **installed** package (`importlib.resources`), not from the
  checkout directory; the install line is derived from the installed package version
  (`importlib.metadata`).
- The session stays offline when its "Download base convention" confirm is answered
  No; template/upgrade modes reach the template source (a git URL) through the engine.
- Only the `api` cell usages are copied — internal development cells
  (`config`/`spec`/`output`/…) are not copied.
