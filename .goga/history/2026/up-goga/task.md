# Migrate pybuggy to goga 2.0 (canonical onboarding model)

## Current State

`goga-tool-pybuggy` targets goga 1.x and breaks hard on a goga 2.0 host (2.0.1 is installed in this
environment):

- The only goga imports in the package are `goga.onboarding` and `goga.scaffold`, both in the
  `commands/init` cell. goga 2.0 rewrote the onboarding facade: the 1.x entities
  (`GogaConfigAnswers`, `InitAnswers`, the single-argument `FileGenerator` call, per-field
  `Questionnaire` orchestration) are gone, replaced by `SessionAnswers` / `SessionPlan` /
  `ToolParticipation` / `ToolContribution` and a two-argument generator call
  (answers + contributions). `pybuggy init` therefore fails at import time.
- `register_hooks` in the package facade subscribes only to the `statuses` actions. The two goga 2.0
  onboarding actions (`onboarding/declare_session`, `onboarding/amend_config`) are not subscribed,
  so pybuggy cannot participate in a native `goga init -t pybuggy` session.
- The Dockerfile install line `_INSTALL_LINE` is hardcoded to a fixed `1.0.x` version line.
- The CI test extra in `pyproject.toml` pins `goga>=1.3.0,<1.4.0`.
- Tests under `tests/commands/init/` parity-stub the goga 1.x API surface.
- Docs (`docs/getting-started.md`, `docs/cli/init.md`, `README.md`, plugin/pipelines pages) describe
  the 1.x initialization model.
- Everything else was verified compatible with goga 2.0 unchanged: the install hook, the
  `statuses` hook subscriptions, `goga tool` dispatch, skills/pipelines layout
  (`pybuggy:api.automate`), the pipeline DSL, usages/cooks layout, tool config self-loading through
  the `config` cell storage.

Observed environment fact (pre-existing, not caused by this migration): `goga schema` currently
fails with "AST parsing failed with 1 error(s)" on this repository under goga 2.0.1.

## Description

Fully migrate pybuggy to goga 2.0 and drop 1.x support. The `init` command is rebuilt on the
canonical goga 2.0 onboarding model: the tool participates in the onboarding session through the two
participation actions, tool config writes go through the tool contribution mechanism
(`ToolContribution` / buffered config files), and the consumer config enforcement uses the renamed
`build.review.skip` key. The `goga tool pybuggy init` UX is preserved (bare / template / upgrade
modes, interactive tool config survey with its current invariants), and pybuggy gains native
participation in `goga init -t pybuggy`. The pybuggy-specific bootstrap (root conftest delivery,
Dockerfile install line, packaged usages → consumer cooks copy, `conventions` slot delivery) remains
owned by pybuggy. goga stays an environment precondition — it is not a pyproject runtime dependency;
only the CI test extra pins the goga 2.0.x line. The Dockerfile install line becomes dynamic,
derived from the package's own version line. A consumer migration guide is added at the repository
root (`MIGRATION.md`). No runtime host-version guard is introduced.

## Scope

**In scope:**

- Rebuild of the `commands/init` cell on the goga 2.0 onboarding model: contract (`CODEMANIFEST`),
  implementation (`init.py`), and the cell-level usage file (`.usages/init.md`).
- Subscriptions for the two onboarding actions (`declare_session`, `amend_config`) in the package
  facade `register_hooks`, alongside the existing `statuses` subscriptions — and the matching update of
  the root cell `goga_tool_pybuggy/CODEMANIFEST` contract for `register_hooks` (revise the "only the two
  topic-status hooks" requirement; connect the onboarding `registering-hooks` usage at
  `.goga/usages/cooks/goga/onboarding/registering-hooks.md`).
- Enforcement of the renamed `build.review.skip` consumer config key (replacing
  `build.review_executor.skip`).
- Dynamic `_INSTALL_LINE` derived from the package's own version line (no hardcoded `1.0.x`).
- `pyproject.toml` test extra: `goga>=2.0.1,<2.1` (the only pyproject dependency change).
- Tests: parity stubs updated to the goga 2.0 signatures; an automated smoke test running `init`
  plus endpoint generate in a temporary directory; the full consumer quickstart e2e accepted after
  one manual run.
- Documentation: update the pages referencing the old model (`docs/getting-started.md`,
  `docs/cli/init.md`, `README.md`, and the plugin/pipelines pages where the old model appears);
  add the root `MIGRATION.md` consumer migration guide covering the key rename and the new
  `goga init -t pybuggy` path.

**Out of scope:**

- Any goga 1.x support (no dual-stack) and any runtime host-version guard.
- Hook subscriptions beyond the agreed scope (`statuses` + the two onboarding actions).
- Changes to the plugin, api, config loader, skills, and pipelines surfaces beyond documentation
  references (verified compatible with 2.0 as is).
- pybuggy release management and versioning decisions (stays with the maintainer).
- Changes to goga itself; goga code and its own artifacts are never modified from pybuggy.

## Acceptance Criteria

- The full test suite is green under goga 2.0.1 (`pytest tests/ -x`), with parity stubs on the 2.0
  API signatures.
- The consumer quickstart works end-to-end: `goga install pybuggy` → `goga tool pybuggy init` →
  `goga pipeline pybuggy:api.automate` (one manual run is the accepted evidence).
- `goga init -t pybuggy` runs a native session in which pybuggy delivers its questions, its tool
  config file, and the `build.review.skip` amendment through the participation mechanism.
- The `goga tool pybuggy init` UX invariants hold on 2.0: bare/template/upgrade modes, the
  already-initialized guard, overwrite/skip gates, required BASE_URL, at-least-one-spec rule,
  mandatory Dockerfile.
- An automated smoke test covers `init` and endpoint generate in a temporary directory.
- `pyproject.toml` pins `goga>=2.0.1,<2.1` in the `test` extra only; no goga runtime dependency.
- `MIGRATION.md` exists at the repository root; the affected docs pages no longer describe the 1.x
  model.
- The `commands/init` CODEMANIFEST reflects the 2.0 contract; `ruff check goga_tool_pybuggy/` is
  clean.

## Stack

- **Frameworks:** pytest (testing), click (CLI), pluginator (pytest plugin framework — unchanged)
- **Libraries:** ruamel.yaml (round-trip YAML edits and emission — unchanged), jinja2; the runtime
  dependency set is unchanged
- **Infrastructure:** goga 2.0.x host as an environment precondition (goga 2.0.1 installed; Docker
  image `qarium/goga-python-3.13:2.0` per `.goga/config.yml`); goga usage sync ref stays
  `release/2.0.0` (no drift per `goga usages status`)

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| goga onboarding (session, participation, generator, hooks) | `.goga/usages/cooks/goga/onboarding/onboarding-usage.md`, `.../participation/session-participation.md`, `.../generator/artifact-generation.md`, `.../registering-hooks.md` | existing (synced) |
| goga scaffold | `.goga/usages/cooks/goga/scaffold/scaffold-usage.md` | existing (synced) |
| goga config (project configuration, `build.review.skip` key semantics) | `.goga/usages/cooks/goga/config/project-configuration.md` | existing (synced) |
| click | `.goga/usages/cooks/click.md` | existing |
| ruamel-yaml | `.goga/usages/cooks/ruamel-yaml.md` | existing |
| conventions | `.goga/usages/conventions.md` | existing |

Synced usage files are managed by `goga usages sync` — reference them read-only, never create or update them in the task.

## Risks and Constraints

- The declarative question model of goga 2.0 (`Question` / one-level `QuestionGroup` records asked
  by the engine) differs from the current imperative click survey (repeat-until-done specs loop with
  optional git blocks). The mapping must preserve the survey invariants (required BASE_URL as a
  Jinja2 template, at least one spec, typed scalar keys); the mapping itself is a design-stage
  decision.
- Session semantics change: an existing `.goga/config.yml` ends a session immediately and is never
  rewritten ("whoever created it first wins"). The interaction with the three init modes and their
  gates (bare guard parity, template silent-skip) must be re-derived, not assumed.
- Tool failures inside a session are soft (a failing tool contribution is discarded with a warning;
  the session continues) — failure propagation differs from the current strict exit-code handling of
  the bootstrap steps.
- The key rename `build.review_executor.skip` → `build.review.skip` affects existing consumer
  configs; `MIGRATION.md` must cover it explicitly.
- CI must provision a goga 2.0.x environment for the test extra pin to resolve.
- Known pre-existing fact: `goga schema` fails with "AST parsing failed with 1 error(s)" on this
  repository under goga 2.0.1 — unrelated to this migration, but later stages relying on schema
  output will hit it.

## Scope Estimate

Single task — no decomposition. The migration delivers value only as a whole (green suite on 2.0.1 +
working consumer quickstart); the parts (init rebuild, hooks, tests, docs) are tightly coupled and
have no independent value. No additional topics were created.

## Existing Architecture

- **`goga_tool_pybuggy/commands/init`** — the rebuilt cell: `CODEMANIFEST`, `init.py`, the cell
  usage file `.usages/init.md`, and the cell `__init__.py` exports.
- **Package facade** (`goga_tool_pybuggy/__init__.py`, `statuses.py`, `CODEMANIFEST`) — `register_hooks`
  gains the two onboarding action subscriptions next to the existing `statuses` ones; the root cell
  contract drops its "only the two topic-status hooks" requirement and connects the onboarding
  `registering-hooks` usage.
- **`goga_tool_pybuggy/config`** — unaffected (tool config stays self-loaded from
  `.goga/tools/pybuggy/config.yml` via its storage; scalar plugin keys remain extra=ignore).
- **Integration points on the goga 2.0 side** (read-only, referenced via synced usages): the
  `goga.onboarding` facade (session logic, questionnaire, generator, participation mediator,
  contribution commit), the `onboarding/declare_session` and `onboarding/amend_config` hook actions,
  buffered tool config files written under `.goga/tools/<tool>/`, and `goga.scaffold`
  (generate/upgrade — unchanged, pinned by the existing parity test).
- **Tests** — `tests/commands/init/` (parity stubs + smoke); consumer quickstart e2e run manually.
- **Docs** — `docs/getting-started.md`, `docs/cli/init.md`, `README.md`, plugin/pipelines pages,
  new root `MIGRATION.md`.

## Notes

Decisions carried from the ADR (`.goga/history/2026/up-goga/adr.md`) and confirmed in this
specification session:

- goga 2.0-only; 1.x support dropped.
- goga is an environment precondition, not a pyproject runtime dependency; only the CI `test` extra
  pins `goga>=2.0.1,<2.1`.
- `init` is rebuilt on the canonical 2.0 participation model; the pybuggy-specific bootstrap stays
  in pybuggy.
- Tool config stays self-loaded (no config injection).
- Hooks scope: existing `statuses` subscriptions plus the two onboarding actions — nothing else.
- `_INSTALL_LINE` becomes dynamic, derived from the package's own version line.
- Tests: updated parity stubs + automated init/generate smoke; the full pipeline e2e is accepted
  after one manual run.
- Consumer migration guide lives at the repository root as `MIGRATION.md`.
- No runtime host-version guard.
- The goga usage sync ref stays `release/2.0.0` (no drift detected).
- Per stage constraints this task document contains no code examples and makes no architecture
  decisions; both belong to the later design/prototype stages.
