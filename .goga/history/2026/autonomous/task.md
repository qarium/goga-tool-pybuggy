# Autonomous runs of the `api.automate` pipeline

Implements the accepted ADR at `.goga/history/2026/autonomous/adr.md` — the stretch of the
`api.automate` pipeline from `review-testcases` through `commit-changes` runs unattended, driven by
one declarative workflow amendment contributed by pybuggy itself before compilation.

## Current State

- The package facade `goga_tool_pybuggy` (module `statuses.py`) subscribes exactly four hooks via
  `register_hooks`: two on the topic-statuses registration action (`register_automate_statuses`,
  `register_fix_statuses`) and two on the onboarding participation moments
  (`declare_pybuggy_session`, `amend_pybuggy_config`). No subscription to the pipeline domain
  exists.
- The pipeline file `goga_tool_pybuggy/pipelines/api.automate.yml` holds 13 stages; every stage is
  `communication: true` except `create-testcases`; `accept-result` carries `trigger: manual`. The
  whole lifecycle is interactive end to end.
- The tool config `.goga/tools/pybuggy/config.yml` is read by the `config` cell's `load_config`
  (own fixed-path resolution, `yaml.safe_load`, validation into the `Config(specs)` model). No
  `pipelines` section exists in the schema or the code; reading does not go through the platform
  `load_tool_config` facade.
- The onboarding session (cell `commands/init`) surveys the `pybuggy_questions` block
  (base_url, the scalar plugin keys, the first spec) and builds the tool config payload via
  `build_config_data`; `document_config_examples` documents absent plugin members as commented
  examples. No autonomy question exists.
- Documentation (`docs/pipelines/api-automate.md`, `docs/cli/init.md`) describes the interactive
  lifecycle only; no "Autonomous runs" coverage exists.

## Description

Add an autonomy mode to pybuggy: when the run's pipeline is `api.automate` and autonomy is enabled
in the tool config, pybuggy — through a single hook subscribed to the goga
`pipeline / amend_workflow` action — contributes a declarative `WorkflowDocument`-shaped amendment
before compilation:

- every stage of the fixed window `review-testcases`, `create-testcases`, `code-design`,
  `design-review`, `coding-plan`, `plan-review`, `commit-changes` receives the auto-approval
  directive (`approve: auto` — the runner-level interaction is suppressed);
- a `build` extend stage ("Build tests") is added after `commit-changes`: it runs the goga build of
  the topic's `plan.md`, with an 8-hour timeout and a `.ralphex` cleanup step after the build
  script; the generated test code stays uncommitted — the commit belongs to the acceptance step;
- `accept-result` is never touched — acceptance stays interactive and manual; autonomy ends at
  `commit-changes`;
- no per-stage prompt/description directive is contributed and the stage skills are not modified.

The configuration contract lives in the tool config under a per-pipeline-name key axis: a
`pipelines` mapping whose entries carry an `autonomous` boolean. Absent file, absent section,
absent key, or `autonomous: false` all mean off — the run composes identically to a project
without the feature. Unknown pipeline names under `pipelines` are ignored (forward
compatibility). Structural violations (a non-mapping `pipelines` or entry, a non-boolean
`autonomous`) fail the run with a clean error naming the tool — a typo must fail loudly, not
silently disable autonomy.

The tool config reading path migrates to the platform facade `load_tool_config` (user amendment
from the formulation dialog): the `config` cell keeps its validating surface for consumers, but
the raw read of `.goga/tools/pybuggy/config.yml` goes through `load_tool_config` instead of the
cell's own path resolution; the five command cells consuming `load_config` keep their contract.

The onboarding session (`pybuggy init`) asks one confirm question (default: disabled) and writes
the `pipelines` key into the tool config only when enabled.

## Scope

**In scope:**

- The autonomy hook in the package facade: a fifth subscription in `register_hooks` to the
  `pipeline / amend_workflow` action; a silent no-op unless the run's pipeline is `api.automate`
  and autonomy is enabled.
- The tool config contract: the `pipelines.<name>.autonomous` key axis, read through
  `load_tool_config`; loud, clean failures on structural violations; permissive ignoring of
  unknown pipeline names.
- The workflow amendment contribution: the fixed seven-stage `approve: auto` window and the
  `build` extend stage after `commit-changes` (goga build of the topic `plan.md`, 8h timeout,
  `.ralphex` cleanup after the script); the stage window and the build entry are compile-time
  constants of the package.
- Migration of the tool config reading to `load_tool_config` within the `config` cell, preserving
  the consumers' `load_config` contract.
- The onboarding confirm question (default off) and the conditional write of the `pipelines` key
  into the tool config payload.
- Documentation: an "Autonomous runs" section in `docs/pipelines/api-automate.md` and the
  corresponding update of `docs/cli/init.md`.
- Tests per the project conventions (unit, edge cases, boundary tests) and cell-level `.usages`
  updates where the affected cells' practices change.

**Out of scope:**

- Any modification of the pipeline stage skills or per-stage prompt/description directives.
- Making `accept-result` autonomous (autonomous failure triage, `manual: false`) — rejected in the
  ADR as premature.
- A separate tool package owning the autonomy contribution — rejected in the ADR.
- Changes to goga itself (the compiler, the hooks platform, `load_tool_config`).
- Extending autonomy to other pipelines (the axis is per-name, but only `api.automate` is
  implemented).

## Acceptance Criteria

- With autonomy off (absent file, absent section, absent key, or `false`), a run of any pipeline
  composes exactly as before the feature: no contribution, no error, no behavioral difference.
- With autonomy on and the running pipeline `api.automate`, the committed amendment carries
  `approve: auto` for exactly the seven named stages and adds the `build` extend stage positioned
  after `commit-changes`; `accept-result` keeps `communication: true` and `trigger: manual` in the
  compiled flow.
- With autonomy on and the running pipeline not `api.automate`, the hook is a silent no-op.
- A structural violation in the `pipelines` section fails the run with a clean error naming
  pybuggy; unknown pipeline names under `pipelines` never fail.
- The tool config is read through `load_tool_config`; the command cells (pull, diff, info, list,
  generate) load the config through the unchanged `load_config` contract.
- The onboarding session asks the autonomy confirm question (default: disabled) and writes the
  `pipelines` key into the tool config only on an enabling answer.
- `docs/pipelines/api-automate.md` documents the autonomous mode (the window, the build stage, the
  config key, the authored-workflow precedence) and `docs/cli/init.md` mentions the question.
- `pytest tests/ -x` passes and `ruff check goga_tool_pybuggy/` is clean.

## Stack

- **Language:** Python 3.10+ — relative intra-package imports, pydantic data models with
  `kw_only=True`, structured `logging`.
- **Libraries (existing, no additions):** click (CLI wrappers), ruamel-yaml (round-trip config
  edits in the bootstrap), pyyaml (leaves the tool-config read path — parsing moves behind
  `load_tool_config`).
- **Platform (goga, provided by the ecosystem — test extra only):** the hooks subscription
  surface, the `pipeline / amend_workflow` amendment view (`WorkflowAmendment` reads and
  `contribute`), the `WorkflowDocument` instruction vocabulary, `load_tool_config`, the onboarding
  `Question` records, the compiler's stage-merge and script-directive semantics.
- **Infrastructure:** none — no databases, brokers, or services involved.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| goga hooks platform | `.goga/usages/github/goga/hooks/registering-hooks.md` | existing (synced) |
| goga pipeline amendment | `.goga/usages/github/goga/pipeline/registering-hooks.md` | existing (synced) |
| goga WorkflowDocument vocabulary | `.goga/usages/github/goga/pipeline/workflow/parse-workflow.md` | existing (synced) |
| goga tool configuration | `.goga/usages/github/goga/config/tool-configuration.md` | existing (synced) |
| goga onboarding questions | `.goga/usages/github/goga/onboarding/questions/question-records.md` | existing (synced) |
| goga compiler flow | `.goga/usages/github/goga/pipeline/compiler/compile-flow.md` | existing (synced) |
| goga onboarding session | `.goga/usages/github/goga/onboarding/onboarding-usage.md` | existing (synced) |

No new files in `.goga/usages/cooks/` — the feature introduces no new third-party library; the
existing cooks (click, ruamel-yaml) cover the involved patterns. Synced usage files are read-only
references managed by `goga usages sync`.

## Risks and Constraints

- **Merge precedence:** an authored project workflow wins per slot — a project can re-enable
  interaction for any window stage or displace the build stage. The contribution must respect the
  platform merge semantics: stage fields fill only what the author left unset; extend entries add
  under fresh names.
- **Fail-loud amendment:** a failing amendment hook stops the command with a clean error naming
  the tool, and the whole contribution is discarded — the hook code must treat any internal error
  as fatal-but-clean, never as a silent disable.
- **Constant window drift:** the stage window and the build entry are compile-time constants; a
  renamed pipeline stage surfaces as the compiler's structural error — visible by design, not
  silent.
- **Unattended review skills:** in autonomous stages the review skills' ask-the-user mandates find
  no dialog; the stage agent resolves findings on its own. Residual mistakes are caught by the
  interactive acceptance gate — this is the designed safety net, not a defect.
- **Raw config parse:** `load_tool_config` returns the raw parse (or `None` for an absent file —
  the normal state); interpreting and validating the `pipelines` section, including the loud
  structural failures, is pybuggy's own responsibility.
- **No runtime dependency growth:** goga stays declared only in the test extra
  (`goga>=2.0.1,<2.1`); the runtime dependency list of the package must not change.
- **Python 3.10+ compatibility** for all code and tests.

## Scope Estimate

Single task — no decomposition. One cohesive feature threading the config contract, one hook, the
onboarding question, and the documentation through three existing cells of one package; no
independent subsystems, no new packages, no additional topics created.

## Existing Architecture

Affected cells and their link connections (facts of the current tree, not a design):

- **`goga_tool_pybuggy` (root facade)** — `register_hooks` in `statuses.py` currently holds the
  four subscriptions; the platform imports `register_hooks` from the package root. The fifth
  subscription (the autonomy hook) joins this registration surface. The facade imports
  `init_cmd`, `declare_pybuggy_session`, `amend_pybuggy_config` from `commands/init` and
  `install` from `plugin`.
- **`goga_tool_pybuggy/config`** — owns `Config`, `SpecEntry`, `GitEntry`, `load_config`
  (`storage.py`) and the practice `configuration`. Imported by five command cells — `commands/pull`
  (`load_config`, `Config`, `SpecEntry`, `GitEntry`), `commands/diff`, `commands/info`,
  `commands/list` (`load_config`, `Config`, `SpecEntry`), `commands/generate` — all calling
  `load_config` at their fixed config path. The migration to `load_tool_config` and the
  `pipelines` section contract land here without breaking those imports.
- **`goga_tool_pybuggy/commands/init`** — owns the onboarding participation
  (`declare_pybuggy_session`, `amend_pybuggy_config`), the question block
  (`pybuggy_questions`), and the payload builders (`build_config_data`, `build_config_amendments`,
  `parse_specs`); the bootstrap documents absent plugin members via `document_config_examples`.
  The autonomy confirm question and the conditional payload key extend this cell.
- **Docs (outside the cells)** — `docs/pipelines/api-automate.md`, `docs/cli/init.md`.
- **Tests** — mirror the source tree per the conventions (`tests/<package>/test_<module>.py`).

## Notes

- The authoritative decision record is the ADR at `.goga/history/2026/autonomous/adr.md`
  (accepted); this task is its implementation formulation.
- User amendment from the formulation dialog: the tool config reading migrates to the platform
  `load_tool_config` — the existing own-path `yaml.safe_load` read in the `config` cell is
  replaced, the validating surface for command consumers is preserved.
- The onboarding autonomy question defaults to disabled; the config key is written only on an
  enabling answer, so existing projects stay untouched until the user opts in.
