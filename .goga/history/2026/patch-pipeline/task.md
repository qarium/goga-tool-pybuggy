# Add the `api.patch` pipeline for modifying existing tests

## Current State

pybuggy ships two goga pipelines: `api.automate` (`PybuggyApiAutomate`, 13 stages —
creates new API tests end to end) and `api.fix` (`PybuggyApiFix`, 6 stages — repairs
failing suites). Conventions live in `goga_tool_pybuggy/pipelines/*.yml` and stage
skills in `goga_tool_pybuggy/skills/pybuggy-api-<pipeline>-*/SKILL.md` (package data,
installed under the `goga-tool-` prefix), docs in `docs/pipelines/`. Topic status lines
are registered by the `goga_tool_pybuggy/statuses` cell (`register_automate_statuses`,
`register_fix_statuses`; subscribed in `reg_hooks.py`). The autonomy contribution in
`goga_tool_pybuggy/autonomous` is hardcoded to automate: `amend_workflow` qualifies only
`pybuggy:api.automate`, resolves the axis `api.automate`, and
`build_autonomous_workflow` fixes the seven-stage window
`review-testcases`…`commit-changes` plus a `build` stage over `plan.md`. There is no
path for user-requested modification of already existing tests.

## Description

Add a third pipeline, `api.patch` (`PybuggyApiPatch`, launched as
`goga pipeline pybuggy:api.patch`): user-requested modification of existing tests,
shaped like `api.automate` minus testcase construction. Its defining rule: every change
lands in the CODEMANIFEST and in the test code together. The boundary with the
neighbors is by intent, not by test color — automate writes new tests, fix repairs what
broke, patch changes what the user asks to change; it may start on red tests, and any
failure it meets is surfaced to the user.

Patch categories (all in scope): replace a data fixture/tool and update its usage
across tests; update/add/change asserts; add markers; re-bind tests between sandbox and
target env; update Routine annotations; remove obsolete cases; update
practices/usages references; structural moves of cells between specs. Selection is
intent-driven: the user states the intent plus scope constraints
(spec/directory/marker); several intents per run are allowed — each becomes its own
section in `intent.md` and its own group in the impact dossier and the plan.

Stage chain (10 stages): `collect-intent` (communication; also fixes the topic version —
spec ref + base URL, as `api.fix` does) → `analyze-impact` (communication) →
`review-impact` (communication) → `apply-manifests` (silent — writes the manifest
deltas) → `code-design` (communication) → `design-review` (communication) →
`coding-plan` (communication) → `plan-review` (communication) → `commit-changes`
(communication) → `accept-result` (manual trigger: consistency check, final full run,
triage with the user, `bugs.md`).

Build — same as automate: the design stages produce documents only; test-code changes
are rebuilt through ralphex (`goga build`). Interactive mode: the user runs
`goga build` on `workplan.md` after `plan-review`. Autonomous contribution: a `build`
stage appended after `commit-changes`, running on `workplan.md`. Verification is
mandatory: pytest in the plan's Validation Commands per task, plus the final full-suite
run at `accept-result`.

Deletions — a removed Routine or cell produces deletion tasks inside the ralphex plan
("delete this test / these tests in that file"); `apply-manifests` only edits
manifests. The fix-line edit invariants are inverted for patch: executors may edit
CODEMANIFESTs and delete Routines — every task records its changed files.

Artifacts (no `patch-` prefix, non-colliding with automate/fix): `intent.md`,
`impact.md`, `apply.md` (report of changed CODEMANIFESTs), `rework.md`, `workplan.md`,
`accept.md`, `accept-log.txt`; `bugs.md` is shared. Repeated patch cycles in the same
topic overwrite the chain (latest cycle wins; history stays in git).

## Scope

**In scope:**
- `goga_tool_pybuggy/pipelines/api.patch.yml` — the 10-stage pipeline definition
  (skeleton in Notes).
- Stage skills `goga_tool_pybuggy/skills/pybuggy-api-patch-*` — one orchestrator skill
  per skill-bearing stage (9 orchestrators); sub-skill decomposition is design-stage
  freedom.
- `goga_tool_pybuggy/statuses/patch.py` — `register_patch_statuses` registering the
  independent chain anchored at the built-in `empty` (like the fix line); export from
  `statuses/__init__.py`; the sixth subscription in `reg_hooks.py`; statuses CODEMANIFEST
  updated with the normative table.
- `goga_tool_pybuggy/autonomous` generalization — qualification for
  `pybuggy:api.patch` with the axis `api.patch` (opt-in via
  `pipelines: api.patch: autonomous: true` in `.goga/tools/pybuggy/config.yml`); the
  patch window `review-impact`…`commit-changes` (7 stages with `approve: "auto"`); a
  `build` stage after `commit-changes` running on `workplan.md` (same script shape as
  automate: `python3 -P -m goga.build "$(python3 -m goga history path -f workplan.md)"`,
  8h timeout, `.ralphex` cleanup after); `accept-result` is never auto-approved;
  automate behavior unchanged; silent no-op for every other pipeline and every disabled
  state (per the existing amendment contract).
- `docs/pipelines/api-patch.md` — the pipeline page (stages, artifacts, sandbox
  interplay, topic status, autonomous runs) and a `docs/pipelines/index.md` update
  listing it.
- Tests mirroring the source structure per conventions: statuses
  (`register_patch_statuses` normative table), autonomous patch
  qualification/window/build, `reg_hooks` subscription order.

**Out of scope:**
- Regeneration of the generated `api/` client modules — patch intents are test-level;
  a spec-level change goes through `pull`/`generate` outside the pipeline.
- Behavior changes to `api.automate` / `api.fix` beyond sharing the generalized
  autonomous cell.

## Acceptance Criteria

- `goga pipeline pybuggy:api.patch` launches the 10-stage chain with the defined
  communication/silent mode per stage and the manual trigger on `accept-result`.
- Every patch status registers on the topic scale exactly per the normative table
  below; the chain is independent (anchored at `empty`) and never reorders the automate
  line; `goga history status` reports patch statuses as `pybuggy.patch.*`.
- With `pipelines: api.patch: autonomous: true` set, a `pybuggy:api.patch` run receives
  the workflow contribution: auto-approval on `review-impact`…`commit-changes` and the
  `build` stage after `commit-changes` over `workplan.md`; `accept-result` keeps its
  manual trigger. With the entry absent, `autonomous: false`, or the file absent, the
  contribution is a silent no-op; a structural violation of the section stops the
  command with a clean error naming pybuggy (the existing resolver contract, unchanged).
- Autonomy for automate is unchanged: window `review-testcases`…`commit-changes`, build
  over `plan.md`, existing automate tests stay green.
- `docs/pipelines/api-patch.md` documents the patch lifecycle — the stage chain, the
  artifacts, and the autonomous run mode — and `docs/pipelines/index.md` lists
  `api.patch` beside automate and fix.
- `pytest tests/ -x` and `ruff check` pass in the project virtualenv.

Normative status table (registration order):

| # | Status | Artifact | Anchor |
|---|--------|----------|--------|
| 1 | `patch.intended` | `intent.md` | after `empty` |
| 2 | `patch.analyzed` | `impact.md` | after `pybuggy.patch.intended` |
| 3 | `patch.applied` | `apply.md` | after `pybuggy.patch.analyzed` |
| 4 | `patch.designed` | `rework.md` | after `pybuggy.patch.applied` |
| 5 | `patch.planned` | `workplan.md` | after `pybuggy.patch.designed` |
| 6 | `patch.done` | `completed/workplan.md` | after `pybuggy.patch.planned` |

## Stack

- **Frameworks:** pytest (tests), pluginator (plugin surface, unchanged)
- **Libraries:** existing only — pydantic, click, ruamel.yaml/pyyaml, the goga
  platform API (`WorkflowDocument`, `WorkflowStage`, `WorkflowExtendStage`)
- **Infrastructure:** none — YAML/Markdown package data; mkdocs for docs

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| goga statuses registration | `.goga/usages/github/goga/history/registering-hooks.md` | existing (synced) |
| goga pipeline / workflow amendment | `.goga/usages/github/goga/pipeline/**` | existing (synced) |
| goga build / ralphex | `.goga/usages/github/goga/build/build-usage.md`, `.goga/usages/github/goga/ralphex/run-ralphex.md` | existing (synced) |
| project code conventions | `.goga/usages/conventions.md` | existing |

Synced usage files are managed by `goga usages sync` — referenced read-only. This task
creates or updates no usage files.

## Risks and Constraints

- The autonomous cell generalization must not shift automate's contribution (same
  window, same build target); the existing automate tests guard against regression.
- The skill inventory is sizeable (~9 orchestrators); content mirrors automate/fix
  skills, and wording must consistently name the patch artifacts (no `patch-` prefix on
  artifacts, `pybuggy-api-patch-` on skills).
- Status registration order must equal the normative table order — every anchor names
  an entry registered earlier in the run or a built-in status.
- Python 3.10+ compatibility; relative imports inside cells; `Author: Goga` in
  CODEMANIFEST footers.

## Scope Estimate

Single task, no decomposition. All work stays on the current branch topic
(`2026/patch-pipeline`); the goga cycle (prototype → apply → plan → build) decomposes it
into ralphex tasks internally.

## Existing Architecture

- `goga_tool_pybuggy/statuses` — new `patch.py` + CODEMANIFEST entry; facade export.
- Root cell `goga_tool_pybuggy` — `reg_hooks.py` gains the sixth subscription:
  `hooks.subscribe("statuses", "register_statuses", "patch", register_patch_statuses)`.
  The root CODEMANIFEST is updated accordingly: Imports gains `register_patch_statuses`
  from the statuses cell, and the `register_hooks` algorithm/constraint move from five to
  six subscriptions (module docstring count included).
- `goga_tool_pybuggy/autonomous` — dispatch by pipeline identity
  (`pybuggy:api.automate` / `pybuggy:api.patch`) with a per-pipeline axis and workflow
  document; CODEMANIFEST updated.
- Conventions (pipeline YAML, skills) and docs are package data, not cells:
  `pipelines/*.yml` and `skills/**/*` are covered by the existing package-data globs —
  no packaging registration needed.

## Notes

Target shapes agreed with the user (final wording is design-stage work).

Skeleton `goga_tool_pybuggy/pipelines/api.patch.yml`:

```yaml
name: PybuggyApiPatch
description: "Pybuggy API-test patch lifecycle"
---

- name: collect-intent
  title: "Collect patch intent"
  communication: true
  prompt: |
    Constraints:
      - Don't research a project until you receive the task
  skills:
    - goga-tool-pybuggy-api-patch-collect

- name: analyze-impact
  title: "Analyze impact"
  communication: true
  skills:
    - goga-tool-pybuggy-api-patch-analyze

- name: review-impact
  title: "Review impact dossier"
  communication: true
  skills:
    - goga-tool-pybuggy-api-patch-review

- name: apply-manifests
  title: "Apply manifest changes"
  skills:
    - goga-tool-pybuggy-api-patch-apply

- name: code-design
  title: "Design code changes"
  communication: true
  skills:
    - goga-tool-pybuggy-api-patch-design

- name: design-review
  title: "Review code design"
  communication: true
  skills:
    - goga-tool-pybuggy-api-patch-design-review

- name: coding-plan
  title: "Create coding plan"
  communication: true
  prompt: |
    Extract rules from the convention and add them to the plan as mandatory rules.
  skills:
    - goga-tool-pybuggy-api-patch-plan

- name: plan-review
  title: "Review coding plan"
  communication: true
  skills:
    - goga-tool-pybuggy-api-patch-plan-review

- name: commit-changes
  title: "Commit changes"
  communication: true
  prompt: |
    Commit all added and modified files.

- name: accept-result
  title: "Accept patch results"
  communication: true
  trigger: manual
  prompt: |
    Commit changes after fixes
  skills:
    - goga-tool-pybuggy-api-patch-accept
```

`register_patch_statuses` fragment (`statuses/patch.py`):

```python
def register_patch_statuses(context: object) -> None:
    """Register the patch status line — an independent chain anchored at ``empty``."""
    context.register("patch.intended", "intent.md", after="empty")
    context.register("patch.analyzed", "impact.md", after="pybuggy.patch.intended")
    context.register("patch.applied", "apply.md", after="pybuggy.patch.analyzed")
    context.register("patch.designed", "rework.md", after="pybuggy.patch.applied")
    context.register("patch.planned", "workplan.md", after="pybuggy.patch.designed")
    context.register("patch.done", "completed/workplan.md", after="pybuggy.patch.planned")
```

Autonomy opt-in (explicit): the patch axis in the tool config —

```yaml
# .goga/tools/pybuggy/config.yml
pipelines:
  api.patch:
    autonomous: true
```

The amendment qualifies the pipeline identity `pybuggy:api.patch` and resolves the axis
`api.patch` — the same resolver and the same silent-no-op contract as automate; the
axis key is the config path of the pipeline name, exactly as `api.automate` works today.

ADR: `.goga/history/2026/patch-pipeline/adr.md`.
