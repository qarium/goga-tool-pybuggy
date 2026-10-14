# Plan: `2026/patch-pipeline` — the `api.patch` pipeline: generalized autonomy, patch statuses, and the pipeline package data

<!-- Topic: `.goga/history/2026/patch-pipeline/` — compiled from `design.md` (post
     design-review, both fixes applied and re-traced) into a ralphex-executable task
     sequence. Non-cell package data (`pipelines/api.patch.yml`, the nine patch stage
     skills, the docs pages) is carried per `arch.md` "Non-cell scope" and the task's
     In-Scope list — the design traced them for consistency; this plan schedules them. -->

## Purpose

Implement the third pybuggy pipeline line — `api.patch` — against the already-materialized
cell contracts (applied byte-exact by the apply-architecture stage; `goga lint` 24 cells,
0 errors). After implementation the package must provide: the six-status patch line
registered on the topic scale as an independent chain anchored at the built-in `empty`; a
generalized autonomous cell where one `PipelineContribution` record per qualifying pipeline
(`pybuggy:api.automate`, `pybuggy:api.patch`) drives qualification, axis routing, and
document construction — automate's contribution byte-identical in effect to today's; the
sixth `register_hooks` subscription; the 10-stage `api.patch.yml` pipeline convention with
its nine orchestrator skills; the docs pages; and a fully green `pytest tests/ -x` /
`ruff check` / facade-import acceptance gate.

Overall strategy: implement in the design's dependency order (statuses → autonomous →
root → integration), one cell per task window so every task gate leaves the full suite
green; the coupled generalization (`workflow.py` + `amendment.py` + their call sites)
lands as one task because the builder's signature change cannot be split without a red
suite between tasks; the non-cell package data follows the cell code (its consistency
check reads the implemented records); every coding task runs the STEP 0–8 ralphex
protocol with the Mandatory Rules (M1–M4) enforced throughout.

## Context

### Contract Surface

**Entity: `register_patch_statuses(context: object)`**
- Type: function (Routine) — NEW
- Declared `location`: `goga_tool_pybuggy/statuses/patch.py`
- Facade obligation: importable from `goga_tool_pybuggy.statuses` (final cell facade
  `__all__ = ["register_automate_statuses", "register_fix_statuses",
  "register_patch_statuses"]`)
- Semantic requirements: six literal `context.register` calls in the normative table
  order, every anchor naming the predecessor (or the built-in `empty` for the first) —
  the chain resolves in one forward pass; registered names carry no tool prefix; artifact
  paths relative to the topic directory with nested paths keeping their directory part
  (`completed/workplan.md`); raises nothing (skip-with-warning belongs to the platform);
  an independent chain sharing no statuses with the automate or fix lines
- Normative table (registration order):
  1. `patch.intended` → `intent.md` — after `empty`
  2. `patch.analyzed` → `impact.md` — after `pybuggy.patch.intended`
  3. `patch.applied` → `apply.md` — after `pybuggy.patch.analyzed`
  4. `patch.designed` → `rework.md` — after `pybuggy.patch.applied`
  5. `patch.planned` → `workplan.md` — after `pybuggy.patch.designed`
  6. `patch.done` → `completed/workplan.md` — after `pybuggy.patch.planned`
- Imported dependencies: none (leaf cell)
- Annotation cascade: cell header (`conventions`, `goga-statuses`, relative imports) →
  routine annotation (2-step algorithm, Requirements, normative table)

**Entity: `PipelineContribution(identity: str, axis: str, window: list[str], build_artifact: str)`**
- Type: class (pydantic record) — NEW
- Declared `location`: `goga_tool_pybuggy/autonomous/contributions.py`
- Facade obligation: importable from `goga_tool_pybuggy.autonomous` (final cell facade
  `__all__ = ["PipelineContribution", "amend_workflow", "build_autonomous_workflow"]`)
- Properties: `identity -> str` (the installer-namespaced pipeline name the platform
  delivers, e.g. `pybuggy:api.patch`); `axis -> str` (the tool-config `pipelines`-axis
  key, e.g. `api.patch`); `window -> list[str]` (ordered stage names carrying the
  auto-approval directive); `build_artifact -> str` (the topic artifact the build stage
  builds, e.g. `workplan.md`)
- Semantic requirements: pydantic model with `kw_only=True` — pure data carrier with no
  behavior; `model_config = ConfigDict(kw_only=True, extra="forbid")` mirroring
  `config/pipeline_autonomy.py` (a mistyped record key fails at import time instead of
  silently dropping a field); all four fields required, no defaults (absence is not a
  state); `window` typed `list[str]` per the contract — the records pass tuples of
  strings, pydantic coerces to lists (the model is the authority); the module defines
  exactly two records as public module-level constants — the normative contribution
  table — plus `CONTRIBUTIONS = (AUTOMATE_CONTRIBUTION, PATCH_CONTRIBUTION)`; the record
  constants are NOT facade exports (only the type is)
- Normative records:

  | Record | identity | axis | window | build_artifact |
  |---|---|---|---|---|
  | automate | `pybuggy:api.automate` | `api.automate` | review-testcases, create-testcases, code-design, design-review, coding-plan, plan-review, commit-changes | `plan.md` |
  | patch | `pybuggy:api.patch` | `api.patch` | review-impact, apply-manifests, code-design, design-review, coding-plan, plan-review, commit-changes | `workplan.md` |

- Both windows end at `commit-changes`; the build stage positions after the final window
  stage. Initialization order: importing the module constructs both records (pydantic
  validation runs at import — a mistyped record fails fast, before any hook can fire)
- Imported dependencies: pydantic only; no cell imports
- Annotation cascade: cell header → entity annotation (Requirements with the normative
  table) → four property annotations

**Entity: `amend_workflow(context: object)`**
- Type: function (Routine) — CHANGED (identity gate re-targets record resolution)
- Declared `location`: `goga_tool_pybuggy/autonomous/amendment.py`
- Facade obligation: importable from `goga_tool_pybuggy.autonomous` (unchanged)
- Semantic requirements: read `pipeline = context.pipeline` (a platform
  `PipelineIdentity`); `contribution = next((c for c in CONTRIBUTIONS if c.identity ==
  pipeline.name), None)` — linear resolution of the record whose identity equals the
  discovered, installer-namespaced name; `contribution is None` → return (silent no-op);
  `enabled = resolve_autonomy(contribution.axis)` — the module-level
  `from ..config import resolve_autonomy` import stays (the test monkeypatch surface);
  `not enabled` → return (silent no-op); else
  `context.contribute(build_autonomous_workflow(contribution))`; **zero error catching**
  — `ValueError` / `yaml.YAMLError` propagate undamped (autonomy never disables
  silently); do not read or alter the authored workflow (merge precedence belongs to the
  platform); drop the `_PIPELINE` / `_AXIS` constants — do not leave both the constants
  and the record paths alive; docstrings generalize from "pybuggy:api.automate" to the
  record table
- Imported dependencies: `resolve_autonomy` (Types import from `goga_tool_pybuggy/config`,
  used as the module-level `from ..config import resolve_autonomy`), `CONTRIBUTIONS` from
  `.contributions`, `build_autonomous_workflow` from `.workflow` (intra-cell, relative)
- Annotation cascade: cell header → routine annotation (5-step algorithm, Requirements,
  Constraints) → imported usage `autonomy`

**Entity: `build_autonomous_workflow(contribution: PipelineContribution) -> document: WorkflowDocument`**
- Type: function (Routine, pure builder) — CHANGED (signature gains the record)
- Declared `location`: `goga_tool_pybuggy/autonomous/workflow.py`
- Facade obligation: importable from `goga_tool_pybuggy.autonomous` (unchanged)
- Semantic requirements: the window mapping, the build script target, and the extend
  positioning derive from the record — **no per-pipeline branching**; call-time import of
  `WorkflowDocument`, `WorkflowStage`, `WorkflowExtendStage` from
  `goga.pipeline.workflow` (`# noqa: PLC0415`) — the package still imports without goga;
  `stages = {name: WorkflowStage(approve="auto") for name in contribution.window}`;
  `build_entry = WorkflowExtendStage(after=[contribution.window[-1]], body={"title":
  "Build tests", "script": f'python3 -P -m goga.build "$(python3 -m goga history path -f
  {contribution.build_artifact})"', "after_script": "rm -rf .ralphex", "timeout": "8h"})`;
  `return WorkflowDocument(stages=stages, extend={"build": build_entry})` — a real
  platform document (typed fields, read by attribute); deterministic and pure — identical
  output on every call for the same record, no I/O, no platform facade calls; the extend
  entry name stays `"build"` and its title stays `"Build tests"` for both records; no
  per-stage prompt/description directives, no stage-skill changes, no acceptance-stage
  directives (`accept-result` in neither `stages` nor `extend`), no forbidden extend keys
  (`manual`/`notes`/`reflect`/`memory`/inline `approve` in the extend body)
- Module shape: keep `from __future__ import annotations` and the `TYPE_CHECKING`
  `WorkflowDocument` import; add module-level `from .contributions import
  PipelineContribution` (intra-package — no goga dependency); delete `_WINDOW_STAGES`,
  `_BUILD_SCRIPT`, `_BUILD_AFTER`; keep `_BUILD_NAME = "build"`, `_BUILD_TITLE =
  "Build tests"`, `_BUILD_AFTER_SCRIPT = "rm -rf .ralphex"`, `_BUILD_TIMEOUT = "8h"`;
  generalize module and function docstrings ("seven-stage window" → "the record's
  window")
- Imported dependencies: `PipelineContribution` from `.contributions` (annotation type)
- Annotation cascade: cell header → routine annotation (3-step algorithm, Requirements,
  Constraints) → usages `goga-workflow-document`, `goga-compile-flow`

**Entity: `register_hooks(hooks: object)`**
- Type: function (Routine) — CHANGED (gains the patch subscription)
- Declared `location`: `goga_tool_pybuggy/reg_hooks.py`
- Facade obligation: importable from `goga_tool_pybuggy` (root facade `__init__.py`
  **unchanged** — `register_hooks` is already exported; statuses and autonomous members
  are deliberately not re-exported at root per `assembly.md`)
- Semantic requirements: six literal subscriptions in platform order — automate, fix,
  **patch** (new, in the statuses group after `fix`), declare, amend, autonomy; the
  `.statuses` import grows `register_patch_statuses`; hook names stable and unique
  within the tool; handlers receive their context argument by name; nothing beyond the
  six named hooks; docstring "five subscriptions" → "six subscriptions in platform order"
- Imported dependencies: the three statuses routines (`registration` usage), the two
  onboarding handlers, `amend_workflow` (`contribution` usage)
- Annotation cascade: root header → routine annotation (6-step algorithm, Constraints)

### Re-exports

- Root `->install: {}` and `->services: {}` — unchanged, not touched by this plan (the
  plugin and sandbox data cells are out of scope).
- Cell facades: statuses `__all__` gains `register_patch_statuses`; autonomous `__all__`
  gains `PipelineContribution`. No `->Name: {}` embedding blocks are added by the
  contracts — no embedding tasks.

### Usages Context

- `conventions` (`.goga/usages/conventions.md`) — mandatory Python rules: relative
  intra-package imports, pydantic `kw_only=True` models, Google-style docstrings,
  blank-line block separation, the test-tree mirroring rule, naming, mock policy, the
  validation command table. Referenced by the global annotation of all three cells;
  compiled into **Mandatory Rules M1–M4** below. Every new/changed file and every test
  file in this plan applies it.
- `goga-statuses` (`.goga/usages/github/goga/history/registering-hooks.md`) — the
  registration surface: `register(name, filepath, after=, before=)`, qualified storage as
  `<tool>.<name>`, add-only built-ins, skip-with-warning failure behavior, nested
  artifact paths. Applied by `register_patch_statuses` (and the tests' recorder double,
  which mirrors the surface): six `context.register` calls with `after` anchors only (no
  `before` — the fix-line pattern); names unprefixed; `completed/workplan.md` keeps its
  directory part.
- `goga-pipeline-hooks` (`.goga/usages/github/goga/pipeline/registering-hooks.md`) — the
  `pipeline / amend_workflow` amendment moment: the `WorkflowAmendment` view reads
  (`pipeline`, `decision`, `workflow`, `work`), `contribute(document)` buffering,
  commit-after-return, authored-intent-wins merge, clean-stop failure behavior. Applied
  by `amend_workflow`: read `context.pipeline.name`; contribute exactly one document;
  never read the authored workflow; raise nothing on the no-op paths.
- `goga-workflow-document` (`.goga/usages/github/goga/pipeline/workflow/parse-workflow.md`)
  — the `WorkflowDocument` instruction vocabulary: per-stage override keys (`approve`
  among them) and extend-entry keys (`before`/`after` positioning, verbatim body,
  forbidden extend keys). Applied by `build_autonomous_workflow`:
  `WorkflowStage(approve="auto")` per window stage; `WorkflowExtendStage(after=[...],
  body={title, script, after_script, timeout})`; no `manual`/`notes`/`reflect`/`memory`
  anywhere in the contribution.
- `goga-compile-flow` (`.goga/usages/github/goga/pipeline/compiler/compile-flow.md`) — the
  compiled effects: `approve: "auto"` suppresses `communication: true` and emits
  `auto_approve: true` for planner roles; body `script`/`after_script`/`timeout` compile
  to `script`/`script_after`/`script_timeout`. Applied by `build_autonomous_workflow`
  (effects reasoning) and the acceptance reasoning that `accept-result` must never carry
  `approve`: the window stages compile unattended; the build extend-stage carries its
  script block verbatim.

### Imported Usages

- `autonomy` from `goga_tool_pybuggy/config` (path
  `goga_tool_pybuggy/config/.usages/autonomy.md`) — the resolver consumption pattern:
  whole axis validated per call, clean error naming pybuggy, no caching. Applied by
  `amend_workflow` (step 4 of its algorithm).
- `registration` from `goga_tool_pybuggy/statuses` (path
  `goga_tool_pybuggy/statuses/.usages/registration.md`) — the status subscription
  pattern: the three subscribe lines with stable hook names, `context` delivered by name,
  independent moments. Applied by `register_hooks` steps 1–3; the file's subscribe
  example is the facade's target shape.
- `contribution` from `goga_tool_pybuggy/autonomous` (path
  `goga_tool_pybuggy/autonomous/.usages/contribution.md`) — the autonomy subscription
  pattern and the cell's consumer surface ("What the cell provides": the record-resolving
  `amend_workflow`, the `PipelineContribution` record type with both records, the
  record-taking builder). Applied by `register_hooks` step 6 and mirrored by the
  autonomous facade docstring.

### Local Usages

None created or updated. The design's `.usages/` Update audit found all three consumer
files already materialized in their target form by the apply-architecture stage (three
hooks in `registration.md`, both records in `contribution.md`, six-hooks/four-addresses
wording in `assembly.md`) — additions needed: none; updates needed: none. They are
**read-only** for the implementation agent together with the CODEMANIFESTs.

### External Dependencies

- pydantic v2 (runtime) — `PipelineContribution`'s `kw_only=True` / `extra="forbid"` /
  tuple→`list[str]` coercion / value equality semantics were verified live by the design
  review; nothing new to add to `pyproject.toml`.
- The goga platform API (test-extra `goga>=2.0.1,<2.1` in the venv; `/opt/goga/bin/python3`
  for the design's import smoke) — `WorkflowDocument`, `WorkflowStage`,
  `WorkflowExtendStage` (call-time import in `workflow.py`), `PipelineIdentity` (test
  doubles), `PipelineHooks` (integration delivery).
- pytest + pytest-cov + ruff (test extra) — the validation toolchain.
- PyYAML — `tests/test_autonomy_integration.py` and the `api.patch.yml` structural check.
- No new third-party libraries anywhere in this plan (M1.10).

## Facts

- The three CODEMANIFESTs and the three `.usages/` files are already materialized
  byte-exact in the working tree (uncommitted modifications of the apply-architecture
  stage); architecture-review PASSED; design-review PASSED with two fixes applied (the
  `tests/test_autonomy_integration.py` change-set entry and the patch end-to-end
  integration scenario); `goga lint` reports 24 cells, 0 errors; no CODEMANIFEST defects
  were found — no contract edits are needed or allowed.
- The contract type chains are consistent: root Imports ↔ statuses/autonomous
  declarations; `amend_workflow` → `build_autonomous_workflow(contribution:
  PipelineContribution)` → `resolve_autonomy(str)`.
- pydantic v2 semantics verified live: `kw_only=True` rejects positional construction
  with `TypeError`; `extra="forbid"` rejects extra kwargs with `ValidationError`;
  tuple-constructed and list-constructed models compare equal; `window` reads back as a
  list.
- The root facade `__init__.py` is unchanged by this feature — `register_hooks` is
  already exported and the platform imports it from the package root; statuses and
  autonomous members deliberately do not reach the root (`assembly.md`).
- `workflow.py` keeps `from __future__ import annotations` — the signature test compares
  **stringified** annotations (`"PipelineContribution"`, `"WorkflowDocument"`).
- `amendment.py` keeps the module-level `from ..config import resolve_autonomy` — tests
  monkeypatch `amendment_module.resolve_autonomy`; switching to `from .. import config` +
  attribute calls is forbidden (it would break the seam).
- No import cycles: `config` and `statuses` are leaves; `autonomous` depends only on
  `config` (unchanged); the root depends downward only. `contributions` constructs its
  records at import (fail-fast).
- The existing conftest doubles are reused **unchanged**: `_RecorderContext`
  (`tests/statuses/conftest.py`), `_AmendmentView` / `amendment_identity` /
  `amendment_view` (`tests/autonomous/conftest.py`), `tool_config`
  (`tests/conftest.py` — writes the real standard tree `.goga/tools/pybuggy/config.yml`
  under `tmp_path` and chdirs into it), `_RecorderHooks` (inline in
  `tests/test_reg_hooks.py`). Patch views are built as
  `_AmendmentView(amendment_identity("pybuggy:api.patch"))`.
- The only sanctioned mock is `monkeypatch.setattr(amendment_module, "resolve_autonomy",
  ...)` — the external boundary is the config cell's file read; everything else is pure
  logic.
- Non-cell artifacts delegated to the coding stages by `arch.md` "Non-cell scope":
  `pipelines/api.patch.yml` (the task-file Notes skeleton is **normative**), nine
  orchestrator skills `skills/pybuggy-api-patch-*` (flat — no sub-skills; sub-skill
  decomposition was design-stage freedom, left unexercised), `docs/pipelines/api-patch.md`
  (new), `docs/pipelines/index.md` (modified), `mkdocs.yml` (nav entry). The
  `pipelines/*.yml` and `skills/**/*` globs in `pyproject.toml` package-data already
  cover the new files — no packaging registration.
- No project virtualenv exists in the tree yet — it is created at Task 1 per M1.2.
- `docs/pipelines/index.md` currently lists automate and fix; `mkdocs.yml` nav lists
  `api.automate` and `api.fix` under Pipelines.

## Gap Analysis

- **Missing contract entities**: `goga_tool_pybuggy/statuses/patch.py` (the whole file);
  `goga_tool_pybuggy/autonomous/contributions.py` (the whole file).
- **Missing facade exposure**: `register_patch_statuses` absent from
  `statuses/__init__.py` (`__all__` lists two; module docstring says "the two …
  routines"); `PipelineContribution` absent from `autonomous/__init__.py` (`__all__`
  lists two routines).
- **API mismatches vs contract**: `build_autonomous_workflow()` takes no parameters
  (contract: `(contribution: PipelineContribution) -> document: WorkflowDocument`);
  `amend_workflow` gates on the hardcoded `_PIPELINE` / `_AXIS` constants (contract:
  record resolution by `pipeline.name`, axis per record); `register_hooks` subscribes
  five hooks (contract: six — `patch` missing between `fix` and the onboarding pair).
- **Behavioral mismatches**: a `pybuggy:api.patch` run resolves no record (identity gate
  misses it) → autonomy never applies to patch; the window/build constants fix automate's
  seven stages and `plan.md`.
- **Dead code to remove when generalizing** (do not leave both paths alive):
  `_PIPELINE`, `_AXIS` in `amendment.py`; `_WINDOW_STAGES`, `_BUILD_SCRIPT`,
  `_BUILD_AFTER` in `workflow.py`.
- **Existing code reused as-is**: `register_automate_statuses`, `register_fix_statuses`
  (style references for `patch.py`), `config` cell (`resolve_autonomy` untouched), the
  conftest doubles, `PipelineAutonomy` as the pydantic `kw_only`/`extra="forbid"`
  precedent, root `__init__.py`.
- **Test coverage gaps**: no `tests/statuses/test_patch.py`; no
  `tests/autonomous/test_contributions.py`; `tests/autonomous/test_workflow.py` tests a
  no-arg builder and hardcodes the automate window; `tests/autonomous/test_amendment.py`
  covers only the automate identity (the no-op regression covers `pybuggy:code.review`
  only); `tests/test_reg_hooks.py` asserts a five-entry table; no patch end-to-end
  scenario with the real config tree; `tests/test_autonomy_integration.py` calls the
  builder no-arg at lines 61 and 85 (breaks under the new required-argument signature —
  the design-review's High finding, fixed into the design).
- **Missing non-cell artifacts**: `pipelines/api.patch.yml`, the nine
  `skills/pybuggy-api-patch-*` orchestrators, `docs/pipelines/api-patch.md`, the
  `index.md` entry, the `mkdocs.yml` nav line.
- **Workspace state**: the CODEMANIFEST/.usages modifications sit uncommitted in the
  working tree (owned by the apply-architecture stage; the pipeline's commit-changes
  stage commits them) — per-task commits must add only their own files by name (M3.3).

---

## Mandatory Rules

Extracted from the project convention (`.goga/usages/conventions.md` — the `conventions`
practice connected by every changed cell) and the project tool configuration
(`pyproject.toml`: ruff `target-version = "py310"`, `line-length = 120`, rule sets
`E,W,F,I,N,UP,B,SIM,PL,PLR,C4,DTZ,PT,ARG,RUF,PTH,C90` + `max-complexity = 10`, format
double-quote/space-indent/LF/magic-trailing-comma, per-file ignores for `tests/**`).
These rules are **mandatory for every task**; they override convenience and apply in
addition to each task's contract annotations. Where a contract annotation and these rules
overlap, the contract wins; where both are silent, the rules decide.

### M1. Coding Style (strictly per `conventions`)

- **M1.1** Python 3.10+ only. No syntax or stdlib usage beyond 3.10 compatibility.
- **M1.2** `pyproject.toml` is the single configuration source; all commands run inside
  the project virtualenv — create it if missing (`python3 -m venv .venv && .venv/bin/pip
  install -e ".[test]"`). Never execute against the system interpreter.
- **M1.3** Imports: **relative** for all intra-package references (`from ..config import
  resolve_autonomy`, `from .contributions import CONTRIBUTIONS`, `from .statuses import
  register_patch_statuses`); **absolute** only for stdlib and third-party. An absolute
  import of the project's own package is forbidden.
- **M1.4** The call-time platform import in `workflow.py` (`from goga.pipeline.workflow
  import ...` inside the function body, `# noqa: PLC0415`) and the module-level
  `from ..config import resolve_autonomy` in `amendment.py` are **contract, not style**
  — never hoist the former, never re-route the latter; together they keep the package
  importable without goga and keep the test monkeypatch surface.
- **M1.5** All data models are pydantic with `kw_only=True`. `PipelineContribution` adds
  `extra="forbid"` (the contract's Requirement, mirroring `PipelineAutonomy`). No field
  defaults on the record — all four values are always meaningful (the conventions'
  empty-default rule targets optional data; absence is not a state here).
- **M1.6** Type hints are mandatory on every function and method (including tests).
- **M1.7** Docstrings: Google style, on **all** public functions, methods, and classes.
  First line capitalized and ending with a period; `Args` when parameters exist;
  `Returns` when a value returns; `Raises` for exceptions beyond built-ins. Module
  docstrings are updated where counts changed: statuses facade "two → three" status
  routines; `reg_hooks.py` "five → six subscriptions in platform order";
  `workflow.py` / `amendment.py` generalized from the automate wording to the record
  table.
- **M1.8** Function-body formatting: one blank line between logical blocks
  (initialization vs conditionals/loops, data preparation vs processing, processing vs
  return). Match the existing modules' visual rhythm — `fix.py` is the reference for
  `patch.py` (one blank line between the literal `register` calls).
- **M1.9** Logging: none added. The contracts demand silent no-op branches, platform-side
  registration warnings, and a pure builder — **this feature adds no new log statements**
  (no `logging` import, no logger). No secrets in any output anywhere.
- **M1.10** Dependencies: nothing new is added to `pyproject.toml` in this plan.
- **M1.11** Naming: PascalCase classes, snake_case functions/methods/constants;
  `__all__` stays ruff-sorted (`RUF022`) — the autonomous facade becomes
  `["PipelineContribution", "amend_workflow", "build_autonomous_workflow"]`. Record
  constants (`AUTOMATE_CONTRIBUTION`, `PATCH_CONTRIBUTION`, `CONTRIBUTIONS`) are
  module-level public names of `contributions.py` — support names, not facade exports.

### M2. Test Writing Rules (strictly per `conventions`)

- **M2.1** The test tree mirrors the source directly: `goga_tool_pybuggy/<cell>/<module>.py`
  → `tests/<cell>/test_<module>.py`; root-package modules → `tests/test_<module>.py`;
  integration tests spanning multiple packages → directly in `tests/`
  (`tests/test_autonomy_integration.py`).
- **M2.2** Every new test directory carries `__init__.py` (all needed ones exist). Local
  fixtures stay in `tests/<package>/conftest.py` (reuse `_RecorderContext`,
  `_AmendmentView`, `amendment_identity`, `amendment_view` unchanged), shared fixtures in
  `tests/conftest.py` (`tool_config`).
- **M2.3** File names `test_<module>.py`; test functions `test_<what>_<scenario>`
  (self-documenting — who/what, under what condition, what should happen); grouping
  `class Test<Component>:`; minimal comments (the existing suites' docstring-per-test
  style is the reference).
- **M2.4** Test categories (mirrored by the ralphex steps): **contract tests** — facade
  accessibility, API shape, signatures — written FIRST, expected to fail; **logic tests**
  — positive, negative, edge — written after implementation; **integration tests** — only
  for cross-module/package interaction, as a separate task (Task 5). Integration tests
  never replace contract or logic tests per entity.
- **M2.5** Edge coverage per the convention: expected exceptions via `pytest.raises`
  (positional `TypeError`, extra-key `ValidationError`, propagating `ValueError`);
  thresholds/state transitions via `@pytest.mark.parametrize` with a table including
  each boundary — the axis-routing matrix (both identities), the no-op matrix
  (`pybuggy:code.review`, `pybuggy:api.fix`), and the determinism matrix (both records)
  are parametrized tables by design. The empty-window boundary is impossible for the
  compile-time records and is pinned instead by
  `test_contribution_windows_end_at_commit_changes` (non-empty + last stage).
- **M2.6** Doubles, not business-logic mocks: recorder doubles for platform surfaces
  only; pure logic tested mock-free; the config file tree through the `tool_config`
  fixture (`tmp_path`-rooted) exclusively; the one external boundary mocked at the import
  point (`monkeypatch.setattr(amendment_module, "resolve_autonomy", ...)`). No mocks
  beyond that seam.
- **M2.7** Update the existing tests **in place** (`test_amendment.py`,
  `test_workflow.py`, `test_reg_hooks.py`, `test_autonomy_integration.py`) rather than
  duplicating them; add the two new files (`tests/statuses/test_patch.py`,
  `tests/autonomous/test_contributions.py`).
- **M2.8** Test dependencies stay in `[project.optional-dependencies].test`; no new test
  libraries.
- **M2.9** When debugging, fix **implementation code**, never test code, unless the test
  contradicts the design (then stop and re-check the design, never the contract).

### M3. Linters and Formatters — Enforced at Every Development Stage and Every Local Commit

- **M3.1** `ruff` is the project's linter **and** formatter, configured in
  `pyproject.toml` (`target-version = "py310"`, `line-length = 120`, the full select set,
  `max-complexity = 10`, format double quotes / space indent / LF / magic trailing
  comma). The per-file ignores for `tests/**` (`S101`, `ARG001`, `ARG002`, `PLR2004`,
  `RUF001`, `PLC0415`) apply automatically. This plan adds no ruff configuration
  changes.
- **M3.2** **Stage gate** — every task ends with BOTH commands clean (run in the venv):
  - `.venv/bin/ruff check goga_tool_pybuggy/ tests/`
  - `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/` (apply
    `.venv/bin/ruff format goga_tool_pybuggy/ tests/` first, then verify)
  Formatting fixes are applied before the task's completion checkbox is ticked.
  Decompose when `C90`/complexity or pylint rules demand it. For the package-data tasks
  (6–8) the `.py` set is untouched — the two commands must still exit 0.
- **M3.3** **Local commit gate** — before **every** `git commit` (one commit per
  completed task):
  1. `.venv/bin/ruff check goga_tool_pybuggy/ tests/` → clean
  2. `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/` → clean
  3. `.venv/bin/pytest tests/ -x` → green (every task in this plan leaves the full suite
     green — no declared red set)
  A commit that fails either ruff command is not made. Fix, re-run, commit. Commits add
  **only the task's own files by name** (`git add <explicit paths> && git commit`) —
  never `git add -A`: the CODEMANIFEST/.usages modifications of the apply-architecture
  stage stay uncommitted for the pipeline's commit-changes stage.
- **M3.4** Facade checks follow the convention's command shape
  (`python -c "from package import Entity"`), run in the venv at every task gate where a
  facade changes; the design's goga-interpreter smoke
  (`/opt/goga/bin/python3 -c "from goga_tool_pybuggy.statuses import
  register_patch_statuses"` and the autonomous equivalent) is re-run once after
  implementation as a cross-environment confirmation.

### M4. REPL Cycle Rules — Continuous Interactive Evaluation, Hot Reloading, Code Migration

The workflow of every coding task is structured around a live REPL cycle: evaluate as you
write, reload instead of restart, and migrate verified code into source files.

- **M4.1 Continuous evaluation** — develop each entity against a live interpreter session
  (`.venv/bin/python3 -i` or `.venv/bin/python3 -c` probes) with prepared scratch state:
  an inline recorder object for the statuses routine; direct construction attempts for
  the record model; a scratch `.goga/tools/pybuggy/config.yml` tree under a `tmp`
  directory (`os.chdir` into it) for resolver-driven runs. For pydantic boundary
  questions (positional rejection, extra-key rejection, tuple coercion, value equality)
  settle them in the REPL against the installed version — never from memory.
- **M4.2 Hot reloading** — after each source edit, re-evaluate in the same session via
  `importlib.reload(<module>)` (or re-import the facade) rather than restarting; keep the
  scratch tree valid across reloads. The point is a tight edit→reload→observe loop per
  entity.
- **M4.3 Code migration REPL → source** — the migration direction is one-way: snippets
  verified in the REPL are moved into the module file (with docstrings, type hints, and
  blank-line blocks per M1), never re-typed divergently. No working behavior may live
  only in the REPL session; the session is scaffolding, the source file is the
  deliverable.
- **M4.4 Pin REPL findings as tests** — every behavior confirmed interactively that the
  contract depends on (the six registration tuples; kw_only/extra-forbid rejections; the
  record table literals; the document shape per record; the six subscriptions) becomes an
  assertion in the task's logic/contract tests. The REPL observation is not done until it
  is pinned in `tests/`.
- **M4.5 REPL checkpoints in the task flow** — each coding task includes an explicit REPL
  verification checkbox between implementation and logic tests (see tasks: "REPL
  cycle"), covering: import resolution, one positive call, one negative call per error or
  no-op branch.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting
> the next (statuses → autonomous → root → integration; then the non-cell package data).
> Within each coding task, contract tests are written first (TDD workflow). The ralphex
> execution protocol steps (STEP 0–8) are embedded in each coding task. Every task is
> executed inside the project virtualenv (M1.2) and ends with the lint/format stage gate
> (M3.2) and the local commit gate (M3.3).

### Task 1: statuses cell — `register_patch_statuses` and the three-routine facade (TDD coding)

<Context: this task creates the patch status line — the new Routine of the `statuses`
cell contract — and widens the cell facade to three routines. `goga_tool_pybuggy/statuses/patch.py`
holds one function, `register_patch_statuses(context: object) -> None`, making six
literal `context.register` calls in the normative table order (intended → analyzed →
applied → designed → planned → done), every anchor naming the predecessor, the first
anchored at the built-in `empty` — an independent chain sharing no statuses with the
automate or fix lines. Names carry no tool prefix (the platform assigns
`pybuggy.<name>`); artifact paths stay relative with `completed/workplan.md` keeping its
directory part. No error handling — unresolvable anchors are platform-side
skip-with-warning. Style reference: `fix.py` (module docstring, Google docstring with
`Args`, one blank line between the literal calls). The facade
`goga_tool_pybuggy/statuses/__init__.py` gains the `.patch` import, the third `__all__`
entry, and the docstring "two → three" update — matching `registration.md`'s subscribe
example, which already documents all three. Tests: the new
`tests/statuses/test_patch.py` mirrors the module per M2.1 and reuses the
`recorder_context` fixture unchanged.>

**Usages relevant to this task:**
- `conventions`: relative imports; Google docstrings; blank-line blocks; test file
  `tests/statuses/test_patch.py` mirroring `statuses/patch.py`; recorder double, no
  mocks.
- `goga-statuses`: the registration surface — `register(name, filepath, after=,
  before=)`, qualified storage `pybuggy.<name>`, add-only built-ins,
  skip-with-warning on unresolvable anchors, nested artifact paths.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 (DECLARATION + ENVIRONMENT)**: declare this task (`Task 1: statuses cell —
      register_patch_statuses and the three-routine facade`); ensure the project
      virtualenv exists (M1.2) — if `.venv/bin/pytest` is absent, run `python3 -m venv
      .venv && .venv/bin/pip install -e ".[test]"`.
- [ ] **STEP 1 (CONTRACT TESTS)**: create `tests/statuses/test_patch.py` — contract
      tests first: `test_register_patch_statuses_importable_from_facade`
      (`from goga_tool_pybuggy.statuses import register_patch_statuses`;
      `callable(register_patch_statuses)`; `"register_patch_statuses" in
      goga_tool_pybuggy.statuses.__all__`) and
      `test_register_patch_statuses_signature_matches_contract`
      (`inspect.signature` → `list(signature.parameters) == ["context"]`,
      `signature.parameters["context"].annotation is object`,
      `signature.return_annotation is None`). Expected to fail now (`patch.py` does not
      exist).
- [ ] **STEP 2 (IMPLEMENTATION)**: create `goga_tool_pybuggy/statuses/patch.py` — module
      docstring mirroring `fix.py`'s ("The pybuggy patch status line — the topic status
      registrations for patch runs. An independent chain anchored at the built-in
      ``empty``, sharing no statuses with the automate and fix lines."); the function
      with its Google docstring (`Args`: `context` — the registration surface scoped to
      the tool); six literal calls in table order:
      `("patch.intended", "intent.md", after="empty")`,
      `("patch.analyzed", "impact.md", after="pybuggy.patch.intended")`,
      `("patch.applied", "apply.md", after="pybuggy.patch.analyzed")`,
      `("patch.designed", "rework.md", after="pybuggy.patch.applied")`,
      `("patch.planned", "workplan.md", after="pybuggy.patch.designed")`,
      `("patch.done", "completed/workplan.md", after="pybuggy.patch.planned")` —
      `after` anchors only, no `before`.
- [ ] **STEP 2 (IMPLEMENTATION)**: update `goga_tool_pybuggy/statuses/__init__.py` — add
      `from .patch import register_patch_statuses`; `__all__ =
      ["register_automate_statuses", "register_fix_statuses",
      "register_patch_statuses"]`; docstring "the two pybuggy topic-status registration
      routines" → "the three pybuggy topic-status registration routines".
- [ ] **REPL cycle (M4)**: in the venv REPL — `from goga_tool_pybuggy.statuses import
      register_patch_statuses` resolves; exercise it against an inline recorder object
      (`class R: calls = []` with a `register(name, artifact, after=None, before=None)`
      method); observe the six tuples and the one-forward-pass anchor chain (each
      `after` names the previous call's qualified form or `empty`); reload
      (`importlib.reload`) after any edit.
- [ ] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest tests/statuses/test_patch.py -v`
      — all contract tests pass.
- [ ] **STEP 4 (LOGIC TESTS)**: in `tests/statuses/test_patch.py` —
      `test_register_patch_statuses_registers_six_statuses_in_order` using the
      `recorder_context` fixture, asserting `recorder_context.calls == [
      ("patch.intended", "intent.md", "empty", None),
      ("patch.analyzed", "impact.md", "pybuggy.patch.intended", None),
      ("patch.applied", "apply.md", "pybuggy.patch.analyzed", None),
      ("patch.designed", "rework.md", "pybuggy.patch.applied", None),
      ("patch.planned", "workplan.md", "pybuggy.patch.designed", None),
      ("patch.done", "completed/workplan.md", "pybuggy.patch.planned", None)]`.
- [ ] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/ -x` — fix implementation code
      until all tests pass.
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)**: facade probes — `.venv/bin/python -c
      "from goga_tool_pybuggy.statuses import register_patch_statuses"` and
      `.venv/bin/python -c "import goga_tool_pybuggy.statuses as s;
      assert s.__all__ == ['register_automate_statuses', 'register_fix_statuses',
      'register_patch_statuses']"`; confirm the table literals are byte-identical to the
      CODEMANIFEST normative table.
- [ ] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — fix formatting, decompose if
      necessary.
- [ ] **STEP 8 (COMPLETION + COMMIT GATE)**: mark this task's checkboxes complete; run
      the local commit gate (M3.3) and commit exactly `goga_tool_pybuggy/statuses/patch.py`,
      `goga_tool_pybuggy/statuses/__init__.py`, `tests/statuses/test_patch.py`.
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 2: autonomous cell — `PipelineContribution` records and the widened facade (TDD coding)

<Context: this task creates the record layer of the autonomy generalization — the new
Entity of the `autonomous` cell contract. `goga_tool_pybuggy/autonomous/contributions.py`
defines the pydantic model `PipelineContribution` with `model_config =
ConfigDict(kw_only=True, extra="forbid")` and four required `str` / `list[str]` fields
(`identity`, `axis`, `window`, `build_artifact`) — a pure data carrier with no behavior
and no validators, mirroring `config/pipeline_autonomy.py`'s hardening so a mistyped
record key fails at import time (fail-fast, before any hook can fire). The module then
defines the normative contribution table as public module-level constants:
`AUTOMATE_CONTRIBUTION` (identity `pybuggy:api.automate`, axis `api.automate`, window
review-testcases, create-testcases, code-design, design-review, coding-plan,
plan-review, commit-changes — build_artifact `plan.md`), `PATCH_CONTRIBUTION`
(identity `pybuggy:api.patch`, axis `api.patch`, window review-impact, apply-manifests,
code-design, design-review, coding-plan, plan-review, commit-changes — build_artifact
`workplan.md`), and `CONTRIBUTIONS = (AUTOMATE_CONTRIBUTION, PATCH_CONTRIBUTION)`. The
records pass tuples of strings; pydantic coerces `window` to `list[str]` — the model is
the authority. The facade `autonomous/__init__.py` gains the `.contributions` import and
`PipelineContribution` in `__all__` (ruff-sorted first), with the docstring generalized
to match `contribution.md`'s "What the cell provides". Nothing else in the cell changes
yet — `workflow.py` still builds from its constants (Task 3 rewires it); the suite stays
green because the module is purely additive.>

**Usages relevant to this task:**
- `conventions`: pydantic for all data models, `kw_only=True`, relative imports, Google
  docstrings (class + `Attributes`), test file `tests/autonomous/test_contributions.py`
  mirroring `autonomous/contributions.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare this task (`Task 2: autonomous cell —
      PipelineContribution records and the widened facade`).
- [ ] **STEP 1 (CONTRACT TESTS)**: create `tests/autonomous/test_contributions.py` —
      contract tests first: `test_pipeline_contribution_importable_from_facade`
      (`from goga_tool_pybuggy.autonomous import PipelineContribution`;
      `issubclass(PipelineContribution, pydantic.BaseModel)`;
      `"PipelineContribution" in goga_tool_pybuggy.autonomous.__all__`). Expected to
      fail now.
- [ ] **STEP 2 (IMPLEMENTATION)**: create `goga_tool_pybuggy/autonomous/contributions.py`
      — module docstring (the compile-time contribution table of the qualifying
      pipelines); `from pydantic import BaseModel, ConfigDict`; the model per the
      contract (class docstring with `Attributes` for the four fields; no methods, no
      validators); the two record constants with the normative values above;
      `CONTRIBUTIONS = (AUTOMATE_CONTRIBUTION, PATCH_CONTRIBUTION)`.
- [ ] **STEP 2 (IMPLEMENTATION)**: update `goga_tool_pybuggy/autonomous/__init__.py` —
      add `from .contributions import PipelineContribution`; `__all__ =
      ["PipelineContribution", "amend_workflow", "build_autonomous_workflow"]`;
      docstring generalized to cover the record type beside the two routines (matching
      `contribution.md`'s "What the cell provides").
- [ ] **REPL cycle (M4)**: in the venv REPL — construct
      `PipelineContribution(identity="i", axis="a", window=["s"], build_artifact="f.md")`
      and read the four fields back; attempt positional construction
      `PipelineContribution("i", "a", ["s"], "f.md")` → observe `TypeError` (kw_only);
      attempt an extra key `typo=1` → observe `pydantic.ValidationError`
      (extra="forbid"); construct with a tuple window → observe list coercion and value
      equality with the list form; inspect `AUTOMATE_CONTRIBUTION.window[-1]` /
      `PATCH_CONTRIBUTION.window[-1]` == `"commit-changes"`; reload after any edit.
- [ ] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest
      tests/autonomous/test_contributions.py -v` — the contract test passes.
- [ ] **STEP 4 (LOGIC TESTS)**: in `tests/autonomous/test_contributions.py` —
      `test_pipeline_contribution_is_kw_only_data_carrier` (kw construction reads back
      the four fields; `with pytest.raises(TypeError)` for positional; `with
      pytest.raises(ValidationError)` for the extra key);
      `test_contribution_table_is_normative` (`CONTRIBUTIONS ==
      (AUTOMATE_CONTRIBUTION, PATCH_CONTRIBUTION)`; every field literal of both records:
      `AUTOMATE_CONTRIBUTION.identity == "pybuggy:api.automate"`, `.axis ==
      "api.automate"`, `.window == ["review-testcases", "create-testcases",
      "code-design", "design-review", "coding-plan", "plan-review", "commit-changes"]`,
      `.build_artifact == "plan.md"`; `PATCH_CONTRIBUTION.identity ==
      "pybuggy:api.patch"`, `.axis == "api.patch"`, `.window == ["review-impact",
      "apply-manifests", "code-design", "design-review", "coding-plan", "plan-review",
      "commit-changes"]`, `.build_artifact == "workplan.md"`);
      `test_contribution_windows_end_at_commit_changes` (`all(record.window for record
      in CONTRIBUTIONS)`; `all(record.window[-1] == "commit-changes" for record in
      CONTRIBUTIONS)`).
- [ ] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/ -x` — fix implementation code
      until all tests pass.
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)**: facade probe — `.venv/bin/python -c "from
      goga_tool_pybuggy.autonomous import PipelineContribution"`; confirm the record
      literals are byte-identical to the CODEMANIFEST normative table; confirm the record
      constants are NOT in the facade `__all__` (module-level names only).
- [ ] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — fix formatting, decompose if
      necessary.
- [ ] **STEP 8 (COMPLETION + COMMIT GATE)**: mark this task's checkboxes complete; run
      the local commit gate (M3.3) and commit exactly
      `goga_tool_pybuggy/autonomous/contributions.py`,
      `goga_tool_pybuggy/autonomous/__init__.py`,
      `tests/autonomous/test_contributions.py`.
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 3: autonomous cell — the record-driven document path: `build_autonomous_workflow(contribution)` + `amend_workflow` record resolution (TDD coding)

<Context: this task generalizes the two existing routines of the `autonomous` cell to
the record-driven form — one semantic change spanning two `location`s, landed together
because the builder's new required argument cannot be split from its only caller
without leaving the suite red. `workflow.py`: `build_autonomous_workflow(contribution:
PipelineContribution) -> WorkflowDocument` — add module-level `from .contributions
import PipelineContribution`; keep `from __future__ import annotations`, the
`TYPE_CHECKING` `WorkflowDocument` import, and the call-time platform import
(`# noqa: PLC0415`); delete `_WINDOW_STAGES`, `_BUILD_SCRIPT`, `_BUILD_AFTER`; keep
`_BUILD_NAME = "build"`, `_BUILD_TITLE = "Build tests"`, `_BUILD_AFTER_SCRIPT = "rm -rf
.ralphex"`, `_BUILD_TIMEOUT = "8h"`; the stages mapping, the build script target, and
the extend positioning derive from the record — no per-pipeline branching. Exact body:
`stages = {name: WorkflowStage(approve="auto") for name in contribution.window}`;
`build_entry = WorkflowExtendStage(after=[contribution.window[-1]], body={"title":
_BUILD_TITLE, "script": f'python3 -P -m goga.build "$(python3 -m goga history path -f
{contribution.build_artifact})"', "after_script": _BUILD_AFTER_SCRIPT, "timeout":
_BUILD_TIMEOUT})`; `return WorkflowDocument(stages=stages, extend={_BUILD_NAME:
build_entry})`. `amendment.py`: drop `_PIPELINE` / `_AXIS`; imports become `from
..config import resolve_autonomy` (unchanged — the monkeypatch surface), `from
.contributions import CONTRIBUTIONS`, `from .workflow import build_autonomous_workflow`;
the gate becomes `contribution = next((c for c in CONTRIBUTIONS if c.identity ==
pipeline.name), None)` → `if contribution is None: return` → `enabled =
resolve_autonomy(contribution.axis)` → `if not enabled: return` →
`context.contribute(build_autonomous_workflow(contribution))`; docstrings generalize
from "pybuggy:api.automate" to the record table. Tests updated in place:
`tests/autonomous/test_workflow.py`, `tests/autonomous/test_amendment.py`, and the two
no-arg builder call sites in `tests/test_autonomy_integration.py` (lines 61 and 85) move
to `build_autonomous_workflow(AUTOMATE_CONTRIBUTION)` — the records are imported from
`goga_tool_pybuggy.autonomous.contributions` (module-level names, not facade exports).
The new patch integration scenario is Task 5; here only the mechanical call-site
migration.>

**Usages relevant to this task:**
- `conventions`: relative intra-package imports; Google docstrings; the monkeypatch
  seam unchanged; tests updated in place per M2.7.
- `goga-workflow-document`: `WorkflowStage(approve="auto")` per window stage;
  `WorkflowExtendStage(after=[...], body={title, script, after_script, timeout})`; no
  `manual`/`notes`/`reflect`/`memory` anywhere in the contribution.
- `goga-compile-flow`: `approve: "auto"` compiles unattended for planner roles; body
  `script`/`after_script`/`timeout` compile to `script`/`script_after`/`script_timeout`.
- `goga-pipeline-hooks`: read `context.pipeline.name`; contribute exactly one document;
  raise nothing on the no-op paths.
- `autonomy` (imported, from `config`): the resolver consumption pattern — whole axis
  validated per call, errors propagate, no caching.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare this task (`Task 3: autonomous cell — the
      record-driven document path`).
- [ ] **STEP 1 (CONTRACT TESTS)**: update the contract tests to the new shapes first —
      in `tests/autonomous/test_workflow.py`:
      `test_build_autonomous_workflow_signature_matches_contract` now asserts
      `list(signature.parameters) == ["contribution"]`,
      `signature.parameters["contribution"].annotation == "PipelineContribution"` and
      `signature.return_annotation == "WorkflowDocument"` (stringified — `workflow.py`
      keeps `from __future__ import annotations`); in `tests/autonomous/test_amendment.py`
      the two existing contract tests stay as-is (`context: object`, return `None`).
      Expected to fail now.
- [ ] **STEP 2 (IMPLEMENTATION)**: rewrite `goga_tool_pybuggy/autonomous/workflow.py`
      per the context above (record parameter; dead constants deleted; kept constants
      reused; module and function docstrings generalized to "the record's window").
- [ ] **STEP 2 (IMPLEMENTATION)**: rewrite `goga_tool_pybuggy/autonomous/amendment.py`
      per the context above (record resolution; dead constants deleted; module and
      function docstrings generalized; `Raises` section kept).
- [ ] **STEP 2 (IMPLEMENTATION)**: migrate the call sites — in
      `tests/autonomous/test_amendment.py` line 40:
      `amendment_view.contributed == [build_autonomous_workflow(AUTOMATE_CONTRIBUTION)]`;
      in `tests/test_autonomy_integration.py` lines 61 and 85:
      `build_autonomous_workflow(AUTOMATE_CONTRIBUTION)`. Both files gain the
      module-level import `from goga_tool_pybuggy.autonomous.contributions import
      AUTOMATE_CONTRIBUTION` (in `test_amendment.py` also `PATCH_CONTRIBUTION` — the new
      STEP 4 test asserts it; the integration file imports `PATCH_CONTRIBUTION` only in
      Task 5, keeping ruff `F401` clean at this gate).
- [ ] **REPL cycle (M4)**: in the venv REPL — `build_autonomous_workflow(AUTOMATE_CONTRIBUTION)`
      and `build_autonomous_workflow(PATCH_CONTRIBUTION)`: observe `list(document.stages)`
      equals each record's window, every stage's `approve == "auto"`,
      `document.extend["build"].after == ["commit-changes"]`, the body script names
      `plan.md` / `workplan.md` respectively, `"accept-result"` in neither `stages` nor
      `extend`; then drive `amend_workflow` against an inline `_AmendmentView`-shaped
      double with `amendment_module.resolve_autonomy` swapped to `lambda _a: True` for
      both identities (observe the record-shaped document) and to `lambda _a: False`
      (observe `contributed == []`); reload after any edit.
- [ ] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest
      tests/autonomous/test_workflow.py tests/autonomous/test_amendment.py -v` — the
      contract tests pass.
- [ ] **STEP 4 (LOGIC TESTS)**: in `tests/autonomous/test_workflow.py` — update
      `test_build_autonomous_workflow_document_shape` to call with `AUTOMATE_CONTRIBUTION`
      (assertions kept: `isinstance(document, WorkflowDocument)`, `document.prompt is
      None`, `document.memory is None`, the seven automate stage names, all
      `approve == "auto"`, `extend["build"].after == ["commit-changes"]`, `.before is
      None`, the verbatim body dict with the `plan.md` script,
      `"accept-result" not in document.stages`, `"accept-result" not in
      document.extend`); add `test_build_autonomous_workflow_patch_document_shape`
      (same shape over `PATCH_CONTRIBUTION`: stage names `["review-impact",
      "apply-manifests", "code-design", "design-review", "coding-plan", "plan-review",
      "commit-changes"]`, body script `'python3 -P -m goga.build "$(python3 -m goga
      history path -f workplan.md)"'`, accept-result exclusions); parametrize
      `test_build_autonomous_workflow_deterministic` over `CONTRIBUTIONS`
      (`first == second` per record). In `tests/autonomous/test_amendment.py` — update
      `test_amend_workflow_contributes_when_enabled` (assertion via
      `build_autonomous_workflow(AUTOMATE_CONTRIBUTION)`); add
      `test_amend_workflow_contributes_patch_window_for_patch_pipeline` (`view =
      _AmendmentView(amendment_identity("pybuggy:api.patch"))`, resolver → `True`;
      `view.contributed == [build_autonomous_workflow(PATCH_CONTRIBUTION)]`); add the
      parametrized `test_amend_workflow_resolves_the_records_axis` over
      `("pybuggy:api.automate", "api.automate")` and `("pybuggy:api.patch",
      "api.patch")` with a recording resolver returning `False`; assert `captured ==
      [expected_axis]` and `view.contributed == []`; parametrize
      `test_amend_workflow_no_op_for_other_pipeline_even_when_axis_enabled` over
      `"pybuggy:code.review"` and `"pybuggy:api.fix"` (resolver → `True`;
      `view.contributed == []`); keep `test_amend_workflow_no_op_when_autonomy_disabled`
      and `test_amend_workflow_errors_propagate_undamped` unchanged.
- [ ] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/ -x` — fix implementation code
      until all tests pass (the integration file's migrated call sites keep it green).
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)**: facade probes — `.venv/bin/python -c "from
      goga_tool_pybuggy.autonomous import PipelineContribution, amend_workflow,
      build_autonomous_workflow"`; confirm the package still imports without goga at
      module level in `workflow.py` (the only goga imports are call-time / `TYPE_CHECKING`);
      confirm neither `_WINDOW_STAGES`/`_BUILD_SCRIPT`/`_BUILD_AFTER` nor
      `_PIPELINE`/`_AXIS` survive.
- [ ] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — fix formatting, decompose if
      necessary.
- [ ] **STEP 8 (COMPLETION + COMMIT GATE)**: mark this task's checkboxes complete; run
      the local commit gate (M3.3) and commit exactly
      `goga_tool_pybuggy/autonomous/workflow.py`,
      `goga_tool_pybuggy/autonomous/amendment.py`,
      `tests/autonomous/test_workflow.py`, `tests/autonomous/test_amendment.py`,
      `tests/test_autonomy_integration.py`.
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 4: root cell — the sixth subscription in `register_hooks` (TDD coding)

<Context: this task completes the root contract — the patch subscription. `goga_tool_pybuggy/reg_hooks.py`
gains `register_patch_statuses` in the `.statuses` import and the third statuses
subscription between `fix` and the onboarding pair:
`hooks.subscribe("statuses", "register_statuses", "patch", register_patch_statuses)` —
six subscriptions total, in platform order, nothing beyond the six named hooks. The
function docstring moves from "five subscriptions in platform order" to "six
subscriptions in platform order"; the module docstring keeps its scope wording
(statuses, onboarding, autonomy). The root facade `__init__.py` is untouched —
`register_hooks` is already exported and nothing else reaches the platform through it.
Tests: `tests/test_reg_hooks.py` updated in place — the module docstring, the class
docstring ("five" → "six"), and the subscription table test gains the patch row at
position three.>

**Usages relevant to this task:**
- `conventions`: relative imports; Google docstrings; counts updated in docstrings;
  tests updated in place.
- `goga-hooks`: the facade callback contract — the subscription surface
  `subscribe(domain, action, name, hook)`, hook signatures, failure behavior of
  registrations.
- `registration` (imported, from `statuses`): the status subscription pattern — its
  subscribe example already contains the `patch` line this task implements.
- `contribution` (imported, from `autonomous`): the autonomy subscription pattern — the
  `autonomy` line, unchanged.
- `goga-onboarding-hooks`: the two onboarding action subscriptions
  (`declare_session` / `amend_config`) — unchanged steps 4–5 of the algorithm.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare this task (`Task 4: root cell — the sixth
      subscription in register_hooks`).
- [ ] **STEP 1 (CONTRACT TESTS)**: the existing contract test
      (`test_register_hooks_facade_and_signature`) already pins
      `{"hooks": object, "return": None}` — verify it still passes unchanged (the
      signature does not move). Update the logic test to the six-entry table first
      (below) so it fails before the implementation lands.
- [ ] **STEP 2 (IMPLEMENTATION)**: update `goga_tool_pybuggy/reg_hooks.py` — import
      line `from .statuses import register_automate_statuses, register_fix_statuses,
      register_patch_statuses`; insert
      `hooks.subscribe("statuses", "register_statuses", "patch",
      register_patch_statuses)` directly after the `fix` subscription; docstring "five
      subscriptions" → "six subscriptions in platform order".
- [ ] **REPL cycle (M4)**: in the venv REPL — `from goga_tool_pybuggy import
      register_hooks` resolves; drive it against an inline `_RecorderHooks`-shaped
      double; observe exactly six tuples in platform order with the patch row third and
      the subscribed callable identical to
      `goga_tool_pybuggy.statuses.register_patch_statuses`; reload after any edit.
- [ ] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest tests/test_reg_hooks.py -v`
      — all tests pass.
- [ ] **STEP 4 (LOGIC TESTS)**: update `tests/test_reg_hooks.py` — module docstring
      ("the five hook subscriptions" → "the six hook subscriptions"; "exact five-entry"
      → "exact six-entry" in the header line), class docstring ("five entries" → "six
      entries"), and the test renamed
      `test_register_hooks_subscribes_six_hooks` asserting `recorder.calls == [
      ("statuses", "register_statuses", "automate", register_automate_statuses),
      ("statuses", "register_statuses", "fix", register_fix_statuses),
      ("statuses", "register_statuses", "patch", register_patch_statuses),
      ("onboarding", "declare_session", "declare", declare_pybuggy_session),
      ("onboarding", "amend_config", "amend", amend_pybuggy_config),
      ("pipeline", "amend_workflow", "autonomy", amend_workflow)]` — the import block
      gains `register_patch_statuses`.
- [ ] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/ -x` — fix implementation code
      until all tests pass.
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)**: facade probe — `.venv/bin/python -c "from
      goga_tool_pybuggy import register_hooks"`; confirm the root `__init__.py` was not
      modified; confirm the six subscriptions match the CODEMANIFEST algorithm steps
      1–6 exactly.
- [ ] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — fix formatting, decompose if
      necessary.
- [ ] **STEP 8 (COMPLETION + COMMIT GATE)**: mark this task's checkboxes complete; run
      the local commit gate (M3.3) and commit exactly `goga_tool_pybuggy/reg_hooks.py`,
      `tests/test_reg_hooks.py`.
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 5: integration tests — the patch end-to-end chain with the real config tree

<Context: this task adds the design-review's Test-Gap fix — the end-to-end integration
scenario for the patch axis that the monkeypatched unit tests cannot cover: a wrong
`axis` string in the record passes every unit test while silently disabling autonomy in
real runs; only the real resolver reading the real standard tree catches a
record-axis ↔ config-key mismatch. The file is `tests/test_autonomy_integration.py`
(already migrated to the record call sites by Task 3); the new test
`test_amend_workflow_end_to_end_patch_with_real_config` joins `TestRunChain` and uses
the existing `tool_config` fixture (writes `.goga/tools/pybuggy/config.yml` under
`tmp_path`, chdirs into it — real file I/O per the mock policy, no monkeypatch) and the
unchanged `_AmendmentView` / `amendment_identity` doubles. The existing automate
scenarios, the platform-delivery scenarios, and the emit↔consume bridge stay green —
automate's behavior is unchanged by the generalization, which these tests prove
end-to-end.>

**Usages relevant to this task:**
- `conventions`: integration tests spanning packages live directly in `tests/`; file
  I/O through the `tmp_path`-rooted `tool_config` fixture; no mocks at all in this
  scenario (the real resolver is the subject).
- `autonomy` (imported, from `config`): the resolver consumption pattern — the real
  standard tree, the whole-axis validation, the bool result.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create the test: in `tests/test_autonomy_integration.py`, class `TestRunChain` —
      `test_amend_workflow_end_to_end_patch_with_real_config(self, tool_config)`:
      `tool_config("pipelines:\n  api.patch:\n    autonomous: true\n")`; `view =
      _AmendmentView(amendment_identity("pybuggy:api.patch"))`; `amend_workflow(view)`;
      assert `view.contributed == [build_autonomous_workflow(PATCH_CONTRIBUTION)]`
      (docstring: the real `api.patch` axis key routes through the real resolver to the
      patch-shaped document); extend the module-level contributions import with
      `PATCH_CONTRIBUTION` (Task 3 imported `AUTOMATE_CONTRIBUTION` only).
- [ ] Test edge case: the disabled counterpart already exists for automate
      (`test_amend_workflow_end_to_end_disabled_is_silent_no_op`) — verify it still
      passes unchanged; no patch duplicate is added (the disabled state is
      resolver-level, already covered).
- [ ] Run validation: `.venv/bin/pytest tests/test_autonomy_integration.py -v` then
      `.venv/bin/pytest tests/ -x` — all green.
- [ ] REPL cycle (M4): in the venv REPL against a scratch tree — `mkdir -p
      /tmp/patch-e2e/.goga/tools/pybuggy`, write `config.yml` with
      `pipelines:\n  api.patch:\n    autonomous: true\n`, `os.chdir` into it, call the
      real `resolve_autonomy("api.patch")` → observe `True`; drive `amend_workflow`
      with a patch-identity view → observe one contributed document whose window starts
      at `review-impact`; pin the observation as the test above.
- [ ] Lint: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then `.venv/bin/ruff
      check goga_tool_pybuggy/ tests/` — fix formatting if necessary.
- [ ] Commit gate (M3.3): ruff check + ruff format --check + `pytest tests/ -x` green;
      commit exactly `tests/test_autonomy_integration.py`.

### Task 6: pipeline convention — `pipelines/api.patch.yml` from the normative skeleton (package data)

<Context: this task creates the 10-stage pipeline definition that the generalized
autonomy targets — without it, `goga pipeline pybuggy:api.patch` cannot launch and the
acceptance scenario has no pipeline to qualify. The task file's Notes skeleton is
**normative** (agreed target shape): header `name: PybuggyApiPatch`, `description:
"Pybuggy API-test patch lifecycle"`, document separator `---`, then the ten stages in
execution order — `collect-intent` (communication; prompt "Constraints:\n  - Don't
research a project until you receive the task"; skill
`goga-tool-pybuggy-api-patch-collect`), `analyze-impact` (communication; skill
`...-analyze`), `review-impact` (communication; skill `...-review`),
`apply-manifests` (silent — no `communication`; skill `...-apply`), `code-design`
(communication; skill `...-design`), `design-review` (communication; skill
`...-design-review`), `coding-plan` (communication; prompt "Extract rules from the
convention and add them to the plan as mandatory rules."; skill `...-plan`),
`plan-review` (communication; skill `...-plan-review`), `commit-changes`
(communication; prompt "Commit all added and modified files."; **no skill**),
`accept-result` (communication; `trigger: manual`; prompt "Commit changes after
fixes"; skill `...-accept`). Transfer the skeleton verbatim from the task file — no
improvisation. The consistency contract (design, Traced Adjacent Artifacts): the stage
chain must contain every window stage of `PATCH_CONTRIBUTION` and an `accept-result`
stage outside the window — verified against the implemented records.>

**Read-only reminder: the CODEMANIFEST and `.usages/` files stay untouched by this task —
the task-file skeleton and the traced records are inputs only.**

**Usages relevant to this task:**
- `conventions`: virtualenv execution for the validation command; no `.py` files
  touched.
- Design "Traced Adjacent Artifacts": stage chain ⊇ `PATCH_CONTRIBUTION.window`;
  `accept-result` outside the window; artifacts `intent.md`, `impact.md`, `apply.md`,
  `rework.md`, `workplan.md`, `completed/workplan.md` — no collision with the automate
  (`plan.md`, `completed/plan.md`) or fix (`fix-*.md`) lines.

- [ ] Create `goga_tool_pybuggy/pipelines/api.patch.yml` — the normative skeleton
      verbatim from the task file Notes (ten stages, exact names, titles, communication
      flags, prompts, skills, the manual trigger).
- [ ] Verify structure (REPL/verification cycle): in the venv — parse with
      `yaml.safe_load_all` (two documents: the header mapping and the stage list);
      assert the stage-name sequence equals `["collect-intent", "analyze-impact",
      "review-impact", "apply-manifests", "code-design", "design-review",
      "coding-plan", "plan-review", "commit-changes", "accept-result"]`; assert every
      `PATCH_CONTRIBUTION.window` stage is present and `"accept-result" not in
      PATCH_CONTRIBUTION.window`; assert `apply-manifests` is the only stage without
      `communication: true`; assert every `skills:` entry follows the
      `goga-tool-pybuggy-api-patch-<stage>` naming (directory existence is verified in
      Task 7 after the skills are created).
- [ ] Verify no packaging registration is needed: the `pipelines/*.yml` glob in
      `pyproject.toml` `[tool.setuptools.package-data]` already covers the file (grep,
      no edit).
- [ ] Lint gate (M3.2): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` and
      `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/` — clean (no `.py`
      touched).
- [ ] Commit gate (M3.3): `pytest tests/ -x` green; commit exactly
      `goga_tool_pybuggy/pipelines/api.patch.yml`.

### Task 7: stage skills — the nine `pybuggy-api-patch-*` orchestrators (package data)

<Context: this task creates the skill layer of the patch chain — one orchestrator skill
directory per skill-bearing stage (nine; `commit-changes` carries no skill), flat
decomposition (no sub-skills — the design left that freedom unexercised). Each
directory is `goga_tool_pybuggy/skills/pybuggy-api-patch-<stage>/SKILL.md` with the
frontmatter `name: goga-tool-pybuggy-api-patch-<stage>` and a one-line `description`,
then the body mirroring the closest automate/fix counterpart's structure (Identity →
Pipeline → steps), with sub-skill references replaced by direct step content (there are
no sub-skills to call). Mirror mapping and per-stage semantics (from the task's
Description — the patch boundary is by intent, not test color: automate writes new
tests, fix repairs what broke, patch changes what the user asks to change; it may start
on red tests and surfaces any failure it meets to the user):
- `collect` ← `fix-collect` + `automate-requirements-intake` — intake of the user's
  intent plus scope constraints (spec/directory/marker); several intents per run, each
  its own `intent.md` section; also fixes the topic version (spec ref + base URL) as
  `api.fix` does.
- `analyze` ← `fix-analyze` — the impact dossier over the intents (each intent its own
  group): affected tests, fixtures, manifests, usages references.
- `review` ← `automate-review` / `fix-review` — dossier review with the user, scope
  confirmation.
- `apply` ← `automate-apply` — applies the manifest deltas (`apply.md` reports changed
  CODEMANIFESTs); **manifests only** — no test code here.
- `design` ← `automate-design` — the code-change design over `rework.md`; deletions
  become explicit deletion tasks in the plan.
- `design-review` ← `automate-design-review` — the design verification pass.
- `plan` ← `automate-plan` — the ralphex coding plan over `workplan.md`; extracts the
  convention rules as mandatory plan rules (style, tests, lint gates, REPL cycle).
- `plan-review` ← `automate-plan-review` — the plan verification pass.
- `accept` ← the `automate-accept*` family collapsed to one orchestrator — consistency
  check, final full suite run, triage with the user, `bugs.md`.
Wording rules: artifacts carry **no** `patch-` prefix (`intent.md`, `impact.md`,
`apply.md`, `rework.md`, `workplan.md`, `accept.md`, `accept-log.txt`; `bugs.md`
shared); skills carry the `pybuggy-api-patch-` prefix; the patch invariants are stated
where relevant — every change lands in the CODEMANIFEST and in the test code together;
executors may edit CODEMANIFESTs and delete Routines (the fix-line edit invariants are
inverted for patch); every task records its changed files; verification is mandatory
(pytest per plan task + the final full-suite run at accept).>

**Read-only reminder: the CODEMANIFEST and `.usages/` files stay untouched by this task.
The sentence "executors may edit CODEMANIFESTs and delete Routines" above describes the
patch pipeline's own executor rules (SKILL.md content authored by this task), NOT this
plan's agent — no CODEMANIFEST is edited at any point of Tasks 1–8.**

**Usages relevant to this task:**
- `conventions`: nothing code-level — markdown authoring; the venv is needed only for
  the lint gate commands.
- Existing skills: the automate/fix SKILL.md files are the structural and tonal
  reference (frontmatter shape, Identity/Pipeline sections, step granularity,
  ~40–70 lines per orchestrator).

- [ ] Create the nine orchestrator directories with their `SKILL.md` files per the
      mapping above: `pybuggy-api-patch-collect`, `-analyze`, `-review`, `-apply`,
      `-design`, `-design-review`, `-plan`, `-plan-review`, `-accept` (under
      `goga_tool_pybuggy/skills/`).
- [ ] Verify naming consistency: every `skills:` entry in
      `goga_tool_pybuggy/pipelines/api.patch.yml` resolves to exactly one created
      directory (re-run the Task 6 check: stage skill reference ↔ directory ↔
      frontmatter `name:` triple-match).
- [ ] Verify wording rules: `grep -r "patch-" goga_tool_pybuggy/skills/pybuggy-api-patch-*/SKILL.md`
      shows no artifact name with a `patch-` prefix (only skill self-references
      `pybuggy-api-patch-*` / `goga-tool-pybuggy-api-patch-*`); artifacts named
      `intent.md`, `impact.md`, `apply.md`, `rework.md`, `workplan.md`.
- [ ] Verify packaging: the `skills/**/*` glob in `pyproject.toml` package-data covers
      the new directories (grep, no edit).
- [ ] Lint gate (M3.2): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` and
      `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/` — clean.
- [ ] Commit gate (M3.3): `pytest tests/ -x` green; commit exactly the nine new
      `goga_tool_pybuggy/skills/pybuggy-api-patch-*/SKILL.md` paths.

### Task 8: docs — the `api.patch` page, the index entry, the nav line (package data)

<Context: this task documents the patch lifecycle for users, mirroring the established
page shapes. `docs/pipelines/api-patch.md` (new) mirrors `api-fix.md` /
`api-automate.md`: the lifecycle intro (user-requested modification of existing tests —
the third line beside automate and fix, boundary by intent not test color; may start on
red tests, surfaces failures to the user); Launch (`goga pipeline pybuggy:api.patch`);
Topic version (fixed at `collect-intent` exactly as `api.fix` does — spec ref + base
URL); the stage chain table (ten stages with communication/silent mode and the manual
trigger on `accept-result`); Artifacts (`intent.md`, `impact.md`, `apply.md`,
`rework.md`, `workplan.md`, `accept.md`, `accept-log.txt`, shared `bugs.md`; repeated
patch cycles overwrite the chain — latest cycle wins, history stays in git); the
sandbox/target-env interplay sentence; Topic status (the six `pybuggy.patch.*` statuses
of the independent chain anchored at `empty`); and the **Autonomous runs** section
mirroring `api-automate.md`'s — the opt-in (`pipelines: api.patch: autonomous: true` in
`.goga/tools/pybuggy/config.yml`), the unattended window
`review-impact`…`commit-changes` with `approve: "auto"`, the `build` stage after
`commit-changes` over `workplan.md` (the same script shape as automate, 8h timeout,
`.ralphex` cleanup), `accept-result` keeping its manual trigger, and the silent no-op /
clean-error contract. `docs/pipelines/index.md` gains the third sentence in the intro,
the third launch line, and the third bullet in "In this section". `mkdocs.yml` gains
`- api.patch: pipelines/api-patch.md` after the `api.fix` nav entry.>

**Read-only reminder: the CODEMANIFEST and `.usages/` files stay untouched by this task —
the docs pages describe the contracts but never modify them.**

**Usages relevant to this task:**
- `conventions`: nothing code-level; the venv is needed only for the lint gate.
- `docs/pipelines/api-fix.md`, `api-automate.md`: the structural reference (section
  order, tone, link targets `../getting-started.md`, `workflows.md`).
- `contribution` (imported usage content): the autonomous-runs section's factual basis
  (opt-in axis, window, build entry, acceptance interactivity).

- [ ] Create `docs/pipelines/api-patch.md` per the context above (all sections;
      cross-links to `api-automate.md` / `api-fix.md` / `../getting-started.md` /
      `workflows.md`).
- [ ] Update `docs/pipelines/index.md` — intro paragraph names the third pipeline;
      Launch block gains `goga pipeline pybuggy:api.patch   # change existing tests`;
      "In this section" gains the `[The \`api.patch\` pipeline](api-patch.md)` bullet.
- [ ] Update `mkdocs.yml` — add `- api.patch: pipelines/api-patch.md` directly after
      the `- api.fix:` nav entry.
- [ ] Verify: `grep -n "api-patch" mkdocs.yml docs/pipelines/index.md` shows both
      entries; the page's stage list matches `pipelines/api.patch.yml` exactly (ten
      names, modes, trigger); the autonomous-runs section names `api.patch`,
      `workplan.md`, `review-impact`…`commit-changes`, and the manual `accept-result`.
- [ ] Lint gate (M3.2): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` and
      `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/` — clean.
- [ ] Commit gate (M3.3): `pytest tests/ -x` green; commit exactly
      `docs/pipelines/api-patch.md`, `docs/pipelines/index.md`, `mkdocs.yml`.

---

## Validation Commands

- `.venv/bin/pytest tests/ -x`: Run all tests (the convention's run-all command; green
  at every task gate — every task in this plan leaves the full suite green)
- `.venv/bin/pytest tests/statuses/ tests/autonomous/ tests/test_reg_hooks.py tests/test_autonomy_integration.py -v`:
  Focused suite for every file this plan touches
- `.venv/bin/ruff check goga_tool_pybuggy/ tests/`: Lint check (M3.1 config; exit 0
  required at every task end and before every commit)
- `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/`: Format check on every file
  the tasks touch (apply `ruff format` first; M3.2/M3.3)
- `.venv/bin/python -c "from goga_tool_pybuggy.statuses import register_patch_statuses"`:
  Statuses facade check
- `.venv/bin/python -c "from goga_tool_pybuggy.autonomous import PipelineContribution, amend_workflow, build_autonomous_workflow"`:
  Autonomous facade check
- `.venv/bin/python -c "from goga_tool_pybuggy import register_hooks"`: Root facade
  check (unchanged facade, re-verified)
- `/opt/goga/bin/python3 -c "from goga_tool_pybuggy.statuses import register_patch_statuses"`
  and `/opt/goga/bin/python3 -c "from goga_tool_pybuggy.autonomous import PipelineContribution"`:
  The design's goga-interpreter import smoke — re-run after implementation
- `goga lint`: Contract consistency of the read-only manifests — 24 cells, 0 errors

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`:
      `register_patch_statuses` in `statuses/patch.py`; `PipelineContribution` (with the
      two records and `CONTRIBUTIONS`) in `autonomous/contributions.py`;
      `amend_workflow` in `autonomous/amendment.py`; `build_autonomous_workflow` in
      `autonomous/workflow.py`; `register_hooks` in `reg_hooks.py`
- [ ] Every contract entity is accessible from its facade: statuses `__all__` carries
      the three routines; autonomous `__all__` carries `PipelineContribution` beside the
      two routines; the root facade still carries `register_hooks` (unchanged file)
- [ ] Properties and methods match the declared API — in particular
      `build_autonomous_workflow(contribution: PipelineContribution) -> document:
      WorkflowDocument` with stringified annotations, and `amend_workflow(context:
      object)` unchanged
- [ ] Descriptions are reflected in behavior: the six-status table verbatim; the
      normative contribution table verbatim; record resolution by discovered name; axis
      routing per record; silent no-ops; undamped error propagation; record-driven
      document with no per-pipeline branching; six subscriptions in platform order
- [ ] Contract dependencies are met: `resolve_autonomy` consumed through the
      module-level import (monkeypatch surface intact); `PipelineContribution` imported
      intra-package in `workflow.py` and `amendment.py`; `.statuses` import grown in
      `reg_hooks.py`
- [ ] Re-exports accessible from the facade (`install`, `services` untouched)
- [ ] Every coding task followed the TDD workflow (contract tests → code →
      verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding
      task; the designed matrices (axis routing, no-op identities, determinism over
      both records) are parametrized tables including every boundary
- [ ] Integration tests exist for the cross-cell chains
      (`tests/test_autonomy_integration.py`, including the patch end-to-end scenario
      with the real config tree)
- [ ] The non-cell artifacts exist and are consistent: `pipelines/api.patch.yml` matches
      the normative skeleton and contains every `PATCH_CONTRIBUTION.window` stage plus
      `accept-result` outside the window; the nine orchestrator skills exist with
      matching names; `docs/pipelines/api-patch.md`, the `index.md` entry, and the
      `mkdocs.yml` nav line are in place
- [ ] No package boundary was expanded (no new cells, no new facades beyond the two
      declared `__all__` additions, no changes to out-of-scope files: the goga
      platform, the `config` cell, `accept-result` handling, `pyproject.toml`)
- [ ] `CODEMANIFEST` and `.usages/` files were not modified (contract and consumer
      docs are read-only; the apply-architecture stage's uncommitted changes remain
      untouched for the pipeline's commit-changes stage)
- [ ] All validation commands pass — `pytest tests/ -x` fully green, both ruff commands
      clean, every facade probe resolves, `goga lint` 24 cells 0 errors
- [ ] Every Usages entry is mentioned in at least one task (`conventions`,
      `goga-statuses`, `goga-pipeline-hooks`, `goga-workflow-document`,
      `goga-compile-flow`; root `goga-hooks`, `goga-onboarding-hooks`; imported
      `autonomy`, `registration`, `contribution`)
- [ ] The Mandatory Rules were enforced throughout: coding style per M1, test rules per
      M2, ruff lint+format at every task gate and every local commit per M3, and the
      REPL cycle (continuous evaluation, hot reloading, REPL→source migration, findings
      pinned as tests) per M4
