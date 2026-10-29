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
the tools, the usages records — and then the pybuggy block under a heading with the
tool name. The block is **kind-aware**: its first record asks the test kind — `api`,
`web`, or `both` (default `api`) — and gates every downstream survey on it. The
declarative block carries only the unconditional records (the kind and the two image
questions, below); every kind-dependent ask happens at the amendment moment, where
pybuggy prompts on its own, branching on the kind answer (the api branch: the api
options, the specs, the autonomy confirms; the web branch: the web minimum — see the
[Interactive tool-config survey](#interactive-tool-config-survey) below). The api and
web question sets never cross.

Two core sections are skipped by pybuggy:

- the **base convention** — the pybuggy session never offers the goga
  base-convention download; the `conventions` slot is the bootstrap's delivery;
- the **docker image decision** — the engine's "Create Dockerfile?" confirm never
  appears: a pybuggy project always carries a Dockerfile. The pybuggy block asks the
  two image questions itself (the base image FROM and the built-image name — see
  below), the path is fixed at `.goga/Dockerfile`, and the amendments deliver the
  file.

The `tools` core question stays: whatever the user answers (or declines), pybuggy
amends the recorded tools with its own entry — `pybuggy: <installed-major.minor>.x`, a
quoted string (e.g. `"2.0.x"`), the same x-range the Dockerfile install line
pins — so pybuggy is always recorded in `.goga/config.yml`; tools the user added
are kept.

Session semantics that shape the modes:

- An existing `.goga/config.yml` ends the session immediately — no questions, no tool
  events, no artifacts. Whoever created the config first wins; it is never rewritten.
- In bare mode this case is unreachable through the CLI: the already-initialized guard
  refuses first.
- In template mode it is the expected path when the template brings its own
  `.goga/config.yml`: the session returns at once and only the bootstrap runs.
- A failing tool contribution is soft: the engine discards it with a warning naming
  pybuggy and continues; the session still returns 0.

Through the session pybuggy delivers its tool config files —
`.goga/tools/pybuggy/api.yml` when the kind is api or both, and
`.goga/tools/pybuggy/web.yml` when the kind is web or both — and buffers the config
amendments — the tool's
declared intent in the session answer space: `build.review.skip: true` (the engine's
config mapper does not carry that flag into the generated `.goga/config.yml`; the
bootstrap enforces it afterwards), the Dockerfile pair (the fixed `.goga/Dockerfile`
path plus the answered FROM — the engine's generator writes the Dockerfile from
exactly this pair — and the answered built-image name), and the `tools` record above.
An old `.goga/tools/pybuggy/config.yml` is not read — pybuggy 2.1 renamed the file to
`api.yml` (clean break): rename an existing `config.yml` by hand.
Consequence: a native `goga init -t pybuggy` session (without the pybuggy CLI) runs
no bootstrap and sets no flag — add `build.review.skip: true` and the pybuggy-owned
files by hand, or run the pybuggy CLI.

## What the command does

Two stages in bare and template modes; upgrade mode skips both.

**Stage 1 — the onboarding session** (see above). Writes `.goga/config.yml`, the
Dockerfile (always — created from the answered base image), and the tool config of
the chosen kind — `.goga/tools/pybuggy/api.yml` (kind api or both) and
`.goga/tools/pybuggy/web.yml` (kind web or both). A non-zero session exit stops the
command — the
bootstrap is skipped, the code is propagated unchanged.

**Stage 2 — the pybuggy bootstrap.** Delivers the files the session does not carry.
Every kind-dependent step is gated on the written tool configs (the kind signals): the
api steps — the api usage copy and the api usage registration — apply only when `api.yml`
was written and no-op for a web-only project; the web steps — the web examples, the
`pybuggy-web` copy and registration, and the playwright line — apply only when `web.yml`
was written and no-op for an api-only project. A kind's usages and registrations never
cross into the other's project.

| Artifact | Gate |
|----------|------|
| `.goga/usages/cooks/pybuggy/<stem>.md` — the packaged api usages (`api.md`, `asserts.md`) and the web usage (`pybuggy-web.md`) | kind-gated: the api pair only when `api.yml` was written, `pybuggy-web.md` only when `web.yml` was written; template: skip existing (INFO); bare: overwrite |
| `.goga/usages/cooks/pybuggy/sandbox/<stem>.md` — the packaged sandbox usages (`sandbox-session.md`, `sandbox-file.md`, `data-operations.md`, `migration-set.md`) | template: skip existing (INFO); bare: overwrite; flat copies from earlier distributions stay untouched |
| commented example records for absent plugin members in `.goga/tools/pybuggy/api.yml` | emitted, idempotent, comment-only |
| commented example records for absent web keys in `.goga/tools/pybuggy/web.yml` | emitted when the web config was written, idempotent, comment-only |
| `.goga/usages/conventions.md` — the `conventions` slot | skip-if-exists in both modes |
| `build.review.skip: true` in `.goga/config.yml` | always enforced, idempotent |
| the pybuggy install `RUN` line in the project Dockerfile (the config `dockerfile` field, default `.goga/Dockerfile`) | appended when the file exists, idempotent |
| the playwright browser-install `RUN` line — `RUN playwright install --with-deps <browser>`, the browser read from the written `web.yml` | when the web config was written — appended when absent, repinned in place on a browser change, idempotent |
| the api usage keys (`pybuggy-api`, `pybuggy-asserts`) and `conventions` with their annotation lines in `.goga/config.yml` (`codemanifest`); the `pybuggy-web` usage key with its annotation line | idempotent — `conventions` always; the api pair only when `api.yml` was written; the `pybuggy-web` key only when `web.yml` was written; the sandbox capability usages are copied as files only — never registered (they may or may not apply to a given cell, and the config usages bind every cell) |
| `conftest.py` at the project root | template: skip existing (INFO); bare: ask, default no |

The install line is derived from the **installed pybuggy version** — e.g. an
installed `2.0.3` yields `RUN goga install pybuggy -v 2.0.x` (the minor x-range
form — a floating patch pin within the installed major.minor line; a concrete
`-v 2.0` would pin `==2.0` forever); there is no hardcoded version pin. The Dockerfile
path is resolved from the consumer config `dockerfile` field so the line lands in the
project's actual Dockerfile (a custom session answer wins).

**The mandatory Dockerfile.** A Dockerfile missing after the session fails the
command with a non-zero exit — pybuggy requires one to carry its install line. The
session always creates the Dockerfile (the amendments deliver the fixed path and the
answered FROM), so the missing-file branch is an unreachable safety net of the
invariant, not a declinable outcome of the survey. If you deleted the file after the
session, create it at the config `dockerfile` path (default `.goga/Dockerfile`) with a
`FROM <base image>` line and re-run the registrations by hand, or remove `.goga` and
re-run — a repeat bare `pybuggy init` is refused by the already-initialized guard.

## Interactive tool-config survey

The pybuggy block of the session asks the kind and the image questions; the
kind-dependent surveys build `.goga/tools/pybuggy/api.yml` (kind api or both) and
`.goga/tools/pybuggy/web.yml` (kind web or both). What is asked, in order:

1. The **test kind** (`kind`) — a choice of `api` | `web` | `both`, default `api`;
   the first record of the block, gating every downstream survey.
2. The **base image** (`base_image`) — the FROM of the always-created Dockerfile. The
   prompt lists the goga-python image family hints of the running goga minor line
   (`qarium/goga-python-3.10` … `qarium/goga-python-3.14`, each tagged with the minor
   line); the newest member is the default. The pybuggy test runtime is pytest, so the
   python family serves every pybuggy project.
3. The **built-image name** (`image`) — the name the project image is built and tagged
   with. Default `{project}:latest` derived from the git origin; a required input when
   no origin is configured.

The **api branch** (kind `api` or `both`) is asked by pybuggy itself at the amendment
moment, **after** the block:

- `base_url` — **required** (empty input is re-asked). A Jinja2 URL template — a plain
  URL is a valid template that renders to itself.
- The optional scalar plugin keys, one input each, skippable with Enter: `timeout`,
  `retries`, `assert_timeout`, `assert_delay`, `assert_field_class`,
  `assert_response_class`. Numeric answers are coerced (`timeout`/`assert_delay` →
  float, `retries`/`assert_timeout` → int).
- The **specs as one flow** — the first spec field by field: `name`, `type` (a choice
  of `swagger`|`openapi`), `location` — all required — and the optional git fields
  `git_url`, `git_location`, `git_ref`. A git block is attached only when both
  `git_url` and `git_location` are non-empty; an empty `git_ref` means the default
  branch. The first spec is validated strictly, so at least one spec always lands in
  the config. Then `Add another spec?` (default No) gates the **additional specs** —
  a confirm-gated per-field loop mirroring the first-spec prompts: `name` / `type` /
  `location` (required, re-asked when empty) and the optional git fields. Any number
  of extras; a decline ends the survey.
- The **autonomy confirms**, asked last — after the spec survey completed, so the
  questions never interleave the spec fields: one per pipeline, `Run the api.automate
  pipeline unattended (autonomous mode)?` and then `Run the api.patch pipeline
  unattended (autonomous mode)?` — each default No. Each Yes is the one way the session
  writes that pipeline's `pipelines` section entry into the tool config — both accepted:

  ```yaml
  pipelines:
    api.automate:
      autonomous: true
    api.patch:
      autonomous: true
  ```

  The default (or declined) answer writes nothing for that pipeline — the entry is
  dropped like any unanswered key, and that pipeline's runs stay fully interactive
  (see [Automate — Autonomous runs](../pipelines/api-automate.md#autonomous-runs) and
  [Patch — Autonomous runs](../pipelines/api-patch.md#autonomous-runs)).

The **web branch** (kind `web` or `both`) is asked by pybuggy at the amendment moment
as well — the web minimum:

- `provider` — the LLM provider: a choice of `openai` | `anthropic`, default `openai`.
  The prompt states the purpose: the provider's models write and classify the
  browser-test steps.
- `generation_model` — **required** (empty input is re-asked); the model that writes
  the browser-step code.
- `classification_model` — **required** (empty input is re-asked); the model that
  classifies captured steps.
- `browser_name` — the browser for web tests: a choice of the five names the runtime
  accepts (`chromium`, `firefox`, `webkit`, `chrome`, `msedge`), default `chromium` —
  an out-of-list name is rejected at the prompt instead of failing later at test
  startup.
- `headless` — whether the browser runs without a visible window; a confirm, default
  yes.

A `both` session asks both branches in order — the api branch first, the web branch
after it. LLM API keys are never surveyed: they live only in `env`/`.env`, and
`web.yml` never carries keys.

`headers` and `loader` are **never surveyed** (api), and the session writes the tool
configs
as plain YAML carrying only the answered values (unanswered keys are dropped, never
written empty). The bootstrap then documents every absent member with commented
example records — pinned before the next active key, idempotent, never touching
active entries — so the two complex sections stay visible as comments:

```yaml
# headers: example (skipped complex member)
#   X-Example: value
#   default request headers dict
# loader: example (skipped complex member)
#   packages:
#     - api
#   modules: []
```

The same documentation pass runs over `web.yml`: every key beyond the surveyed minimum
(the prompts, the attempts, the polling, the screenshots, the probe timeout,
`cache_root`, the browser subkeys beyond name/headless) lands as a commented example
record. The generated api file is valid for
[configuration](../configuration.md) loading.

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
- The session never offers the goga base-convention download (the base-convention core
  section is skipped; the `conventions` slot is the bootstrap's delivery, read from the
  installed package) — the session itself stays offline; template/upgrade modes reach
  the template source (a git URL) through the engine.
- Only the packaged usage roots are copied — the `api` cell root (its `asserts`
  sub-package rides along; both land flat under `.goga/usages/cooks/pybuggy/`), the
  `web` cell root (`pybuggy-web` — flat under `.goga/usages/cooks/pybuggy/`), and the
  `sandbox` subtree roots (`sandbox-session`, `sandbox-file`, `data-operations`,
  `migration-set` — under `.goga/usages/cooks/pybuggy/sandbox/`); the `plugin` and `commands`
  cells and internal development cells (`config`/`spec`/`output`/…) are not copied. The api
  and web roots ship only for their kind (the written `api.yml` / `web.yml`); the sandbox
  subtree is kind-neutral and always ships. Only the api-root usages are registered in
  `codemanifest` (when the api config was written; plus `pybuggy-web`, when the web
  config was written); the sandbox capability usages stay
  download-only.
