# Design Document: `2026/patch-pipeline`

The third pybuggy line — `api.patch` — materialized into the three cell contracts by the
apply-architecture stage (topic `2026/patch-pipeline`, plan `arch.md`). This document
designs the **implementation code** against those contracts: the new modules, the
generalized modules, the facade exports, and the tests. It does not write code and does
not produce an execution plan.

Scope (per the stage assignment): `statuses/patch.py`, `autonomous/contributions.py`,
the facade exports of the two cells, the generalized `autonomous/amendment.py` /
`autonomous/workflow.py`, `reg_hooks.py`, and the mirroring tests. The non-cell package
data (`pipelines/api.patch.yml`, `skills/pybuggy-api-patch-*`, `docs/pipelines/*`) stays
outside this design's change set — traced for consistency in
[Traced Adjacent Artifacts](#traced-adjacent-artifacts-non-cell).

## Contract Changes

### Changed CODEMANIFEST Files

- `goga_tool_pybuggy/statuses/CODEMANIFEST`: body gains the Routine
  `register_patch_statuses(context: object)` (location `patch.py`) with the six-status
  normative table; global Annotations move from two to three status lines; footer
  Description gains the patch line.
- `goga_tool_pybuggy/autonomous/CODEMANIFEST`: body gains the Entity
  `PipelineContribution(identity: str, axis: str, window: list[str], build_artifact: str)`
  (location `contributions.py`) with four properties and the two-record normative
  contribution table; `amend_workflow` annotation re-targets record resolution;
  `build_autonomous_workflow` signature becomes
  `(contribution: PipelineContribution) -> document: WorkflowDocument`; global Annotations
  generalize to both qualifying identities.
- `goga_tool_pybuggy/CODEMANIFEST` (root): `Imports` — statuses entry gains
  `register_patch_statuses`; `register_hooks` algorithm gains the patch subscription
  (step 3) and renumbers to six; the constraint moves from five to six named hooks.

### New Entities

- `register_patch_statuses` — Routine, `goga_tool_pybuggy/statuses/patch.py`: registers
  the six-status patch line on the topic status scale — an independent chain anchored at
  the built-in `empty`.
- `PipelineContribution` — Entity, `goga_tool_pybuggy/autonomous/contributions.py`:
  pydantic record of one pipeline's autonomy contribution (identity, axis, window,
  build_artifact); the package defines exactly two compile-time records (automate, patch).

### Changed Entities

- `amend_workflow` — `goga_tool_pybuggy/autonomous/amendment.py`: the identity gate
  resolves a `PipelineContribution` record by the discovered pipeline name (no record →
  silent no-op); autonomy resolves for the record's `axis`; the contribution is built via
  `build_autonomous_workflow` over the record.
- `build_autonomous_workflow` — `goga_tool_pybuggy/autonomous/workflow.py`: takes the
  record; the window mapping, the build script target, and the extend positioning derive
  from the record — no per-pipeline branching.
- `register_hooks` — `goga_tool_pybuggy/reg_hooks.py`: gains the third statuses
  subscription (`patch`), between `fix` and the onboarding pair; six subscriptions total.

### Deleted Entities

None.

### Usages and Annotations Changes

Contract-level (already materialized by apply-architecture; no further edits in this
design):

- statuses: global Annotations "two → three lines"; patch annotation references
  `goga-statuses` (unchanged key set — no new Usages entries).
- autonomous: global Annotations generalized to "one `PipelineContribution` record per
  qualifying pipeline"; `build_autonomous_workflow` annotation now references
  `contribution`; key set unchanged (`conventions`, `goga-pipeline-hooks`,
  `goga-workflow-document`, `goga-compile-flow`, imported `autonomy`).
- root: `register_hooks` annotation steps 1–6; constraint six hooks; Imports statuses
  types list.

## Applied Fixes

### Fixed CODEMANIFEST Defects

None. The Phase-3 audit (interface↔type, type↔mutation, interface↔interface,
annotations↔entity) found no defects: every `Imports → From` target exists; every
backtick reference resolves inside its document; the `amend_workflow` →
`build_autonomous_workflow(contribution: PipelineContribution)` → `resolve_autonomy(str)`
type flow is consistent; `goga lint` reports 24 cells, 0 errors. The contracts were
reviewed (architecture-review PASSED) and applied byte-exact — this stage designs
strictly against them.

## Entity Interaction and Data Flow

### Interaction Diagram

```
goga platform (imports register_hooks from the package root at the first hook checkpoint)
  │
  ▼
register_hooks (reg_hooks.py) ── subscribes six hooks to four addresses:
  │    statuses/register_statuses: automate, fix, patch
  │    onboarding/declare_session: declare   onboarding/amend_config: amend
  │    pipeline/amend_workflow:   autonomy
  │
  ├─ statuses checkpoint ──► register_patch_statuses(context)          [statuses/patch.py, NEW]
  │      └─ context.register(...) ×6 — add-only chain above `empty`
  │
  └─ pipeline/amend_workflow checkpoint ──► amend_workflow(context)    [autonomous/amendment.py]
         │
         ├─ context.pipeline.name ──► CONTRIBUTIONS lookup             [autonomous/contributions.py, NEW]
         │      └─ PipelineContribution | None
         ├─ None ─────────────────────► silent return (no-op)
         ├─ resolve_autonomy(record.axis) ──► bool | raises            [config cell, unchanged]
         ├─ False ──────────────────────► silent return (no-op)
         └─ True ──► build_autonomous_workflow(record) ──► WorkflowDocument
                            └─ context.contribute(document) — buffered; the platform
                               merges (authored workflow wins per slot) and compiles
```

### Data Flows

- **Status registration** (patch line): platform → `register_patch_statuses(context)` →
  six `context.register(name, artifact, after=...)` calls in table order → platform
  stores each as `pybuggy.<name>` on the topic scale. Execution order: intended →
  analyzed → applied → designed → planned → done; every anchor names the predecessor
  (or the built-in `empty`), so the chain is resolvable in one forward pass.
- **Autonomy qualification**: platform → `amend_workflow(context)` →
  `PipelineIdentity.name` (str, e.g. `pybuggy:api.patch`) → record lookup by
  `identity` → `axis` (str, e.g. `api.patch`) → `resolve_autonomy(axis)` → bool →
  `build_autonomous_workflow(record)` → `WorkflowDocument(stages, extend)` →
  `context.contribute(document)`.
- **Document construction**: `record.window` (list[str]) →
  `{name: WorkflowStage(approve="auto")}`; `record.build_artifact` (str) → build script;
  `record.window[-1]` → extend `after`; fixed constants supply the extend name, title,
  after-script, timeout.

### Entity Dependencies

- `autonomous/contributions.py` — pydantic only; no cell imports; imported by
  `amendment.py` (records), `workflow.py` (type), `autonomous/__init__.py` (export),
  tests.
- `autonomous/workflow.py` — imports `.contributions` (annotation type); platform models
  imported at call time (module imports without goga).
- `autonomous/amendment.py` — imports `..config.resolve_autonomy` (module-level name —
  the test monkeypatch surface), `.contributions.CONTRIBUTIONS`, and
  `.workflow.build_autonomous_workflow`.
- `reg_hooks.py` — imports the three statuses routines, the two onboarding handlers, and
  `amend_workflow`; the package root re-exports only `register_hooks`.
- Initialization order at import: `contributions` constructs its two records (pydantic
  validation runs at import — a mistyped record fails fast, before any hook can fire).
- No cycles: `config` and `statuses` are leaves; `autonomous` depends only on `config`;
  the root depends downward only.

## Code Stack Trace

### Trace: `register_patch_statuses`

#### Chain

1. **Input**: the platform fires the `statuses / register_statuses` checkpoint and
   invokes the hook subscribed under the name `patch` with `context` — the registration
   surface scoped to the tool (`register(name, filepath, after=, before=)`).
2. `context.register("patch.intended", "intent.md", after="empty")` — the platform
   records `pybuggy.patch.intended` tracking the topic artifact `intent.md`, anchored
   above the built-in `empty` → checkpoint: anchor is a built-in status — resolvable;
   name unprefixed (platform assigns identity) — passed.
3. `context.register("patch.analyzed", "impact.md", after="pybuggy.patch.intended")` →
   checkpoint: the anchor is the qualified form of the call in step 2, registered
   earlier in this run — resolvable — passed.
4. `context.register("patch.applied", "apply.md", after="pybuggy.patch.analyzed")` →
   checkpoint as in step 3 — passed.
5. `context.register("patch.designed", "rework.md", after="pybuggy.patch.applied")` →
   checkpoint as in step 3 — passed.
6. `context.register("patch.planned", "workplan.md", after="pybuggy.patch.designed")` →
   checkpoint as in step 3 — passed.
7. `context.register("patch.done", "completed/workplan.md", after="pybuggy.patch.planned")`
   → checkpoint: nested artifact path keeps its directory part (`completed/workplan.md`,
   matching `automate.done`'s `completed/plan.md` precedent) — passed.
8. **Output**: `None`; side effect — six add-only registrations forming an independent
   chain that never references an automate or fix status.

#### Checkpoint Summary

- Anchor resolvability in one forward pass: passed (empty + five predecessors).
- Table order == call order: passed (intended → done, pipeline order).
- Artifact-path relativity / nested directory part: passed.
- No tool prefix in registered names: passed.

### Trace: `PipelineContribution` (constructor / records)

#### Chain

1. **Input**: the module `autonomous/contributions.py` is imported (via the cell facade
   or `amendment.py`); the two records are constructed at import time from keyword
   arguments.
2. `PipelineContribution(identity=..., axis=..., window=..., build_artifact=...)` —
   pydantic `kw_only=True` validates the four `str` / `list[str]` fields;
   `extra="forbid"` rejects any mistyped extra key → checkpoint: a typo in a record
   fails at import with a `ValidationError`, before any hook can fire — passed.
3. `AUTOMATE_CONTRIBUTION`: identity `pybuggy:api.automate`, axis `api.automate`,
   window `("review-testcases", "create-testcases", "code-design", "design-review",
   "coding-plan", "plan-review", "commit-changes")`, build_artifact `plan.md` →
   checkpoint: byte-identical in effect to the constants currently hardcoded in
   `workflow.py` / `amendment.py` — passed.
4. `PATCH_CONTRIBUTION`: identity `pybuggy:api.patch`, axis `api.patch`, window
   `("review-impact", "apply-manifests", "code-design", "design-review", "coding-plan",
   "plan-review", "commit-changes")`, build_artifact `workplan.md` → checkpoint: window
   stages all exist in the `api.patch` stage chain (task skeleton); both windows end at
   `commit-changes` — passed.
5. `CONTRIBUTIONS = (AUTOMATE_CONTRIBUTION, PATCH_CONTRIBUTION)` — the normative table
   as importable data → checkpoint: exactly two records, the tuple is what
   `amend_workflow` searches — passed.
6. **Output**: module-level constants; no runtime behavior.

#### Checkpoint Summary

- Normative table fidelity (two records, exact values): passed.
- kw_only / extra=forbid hardening: passed (mirrors `config/pipeline_autonomy.py`).
- Import-time failure mode for record typos: passed.

### Trace: `amend_workflow`

#### Chain

1. **Input**: the platform fires `pipeline / amend_workflow` (after workflow resolution
   and the runner-skip merge, before compilation) and delivers `context` — a
   `WorkflowAmendment` view: `pipeline` (a `PipelineIdentity`), `contribute(document)`.
2. `pipeline = context.pipeline` — read the identity of the running pipeline →
   checkpoint: the view contract (`goga-pipeline-hooks`) — passed.
3. `contribution = next((c for c in CONTRIBUTIONS if c.identity == pipeline.name), None)`
   — linear resolution of the record whose identity equals the discovered,
   installer-namespaced name → checkpoint: `pipeline.name` is a `str`, `identity` is a
   `str` — type flow passed; unknown pipelines (e.g. `pybuggy:code.review`,
   `pybuggy:api.fix`) resolve to `None`.
4. `if contribution is None: return` — silent no-op → checkpoint: contributes nothing,
   raises nothing — passed.
5. `enabled = resolve_autonomy(contribution.axis)` — the config cell validates the whole
   `pipelines` axis and returns a bool; `ValueError` / `yaml.YAMLError` propagate
   undamped → checkpoint: `contribution.axis` is `str`, matching
   `resolve_autonomy(pipeline: str)` — interface↔interface consistency passed; the
   module-level import keeps `amendment_module.resolve_autonomy` as the test monkeypatch
   surface — passed.
6. `if not enabled: return` — silent no-op → checkpoint: passed.
7. `context.contribute(build_autonomous_workflow(contribution))` — the builder returns a
   real `WorkflowDocument`; the view buffers it; the platform commits the buffer after
   the hook returns and merges with authored-intent-wins precedence → checkpoint:
   argument type `PipelineContribution` matches the builder contract — passed.
8. **Output**: `None`; side effect — one buffered document, or nothing.

#### Checkpoint Summary

- Record resolution by discovered name: passed.
- Axis routing per record (automate → `api.automate`, patch → `api.patch`): passed.
- No-op branches contribute nothing and raise nothing: passed.
- Error propagation (autonomy never disables silently): passed.
- Authored workflow untouched (merge precedence belongs to the platform): passed.

### Trace: `build_autonomous_workflow`

#### Chain

1. **Input**: called by `amend_workflow` step 5 with `contribution` — one of the two
   compile-time records (and directly by tests).
2. Call-time import of `WorkflowDocument`, `WorkflowStage`, `WorkflowExtendStage` from
   `goga.pipeline.workflow` (`noqa: PLC0415`) → checkpoint: the package still imports
   without goga; the models are reached only at call time — passed.
3. `stages = {name: WorkflowStage(approve="auto") for name in contribution.window}` →
   checkpoint: `approve: "auto"` is accepted workflow vocabulary; the mapping keys are
   the record's window stages in order — passed.
4. `build_entry = WorkflowExtendStage(after=[contribution.window[-1]], body={...})` with
   `body = {"title": "Build tests", "script": f'python3 -P -m goga.build "$(python3 -m
   goga history path -f {contribution.build_artifact})"', "after_script": "rm -rf
   .ralphex", "timeout": "8h"}` → checkpoints: `after` is `list[str]` naming the final
   window stage (`commit-changes` for both records); the body is verbatim stage content
   (title / script / after_script / timeout — compiled to `script`, `script_after`,
   `script_timeout`); no `manual` / `notes` / `reflect` / `memory` / inline `approve` in
   the extend entry — all passed.
5. `return WorkflowDocument(stages=stages, extend={"build": build_entry})` →
   checkpoint: a real platform document (typed fields, read by attribute); only one
   record qualifies per run, so the single fresh name `build` never collides — passed.
6. **Output**: the `WorkflowDocument` — the auto-approval window plus the build extend
   entry; deterministic and pure (identical output on every call for the same record).

#### Checkpoint Summary

- Record-driven derivation, no per-pipeline branching: passed.
- Extend-entry vocabulary conformance (`goga-workflow-document`): passed.
- Determinism / purity / no I/O / no platform facade calls: passed.
- Acceptance stage never present (`accept-result` in neither `stages` nor `extend`):
  passed.

### Trace: `register_hooks`

#### Chain

1. **Input**: the platform imports `register_hooks` from the package root and calls it
   with `hooks` — the subscription surface (`subscribe(domain, action, name, hook)`).
2. `hooks.subscribe("statuses", "register_statuses", "automate", register_automate_statuses)`
   → checkpoint: address exists — passed.
3. `hooks.subscribe("statuses", "register_statuses", "fix", register_fix_statuses)` →
   checkpoint: passed.
4. `hooks.subscribe("statuses", "register_statuses", "patch", register_patch_statuses)`
   — the new subscription, imported from `.statuses` → checkpoint: hook name `patch` is
   unique within the tool; sits in the statuses group after `fix` (algorithm step 3) —
   passed.
5. `hooks.subscribe("onboarding", "declare_session", "declare", declare_pybuggy_session)`
   → checkpoint: passed.
6. `hooks.subscribe("onboarding", "amend_config", "amend", amend_pybuggy_config)` →
   checkpoint: passed.
7. `hooks.subscribe("pipeline", "amend_workflow", "autonomy", amend_workflow)` →
   checkpoint: passed.
8. **Output**: `None`; side effect — six subscriptions; exactly the six named hooks and
   nothing else (constraint).

#### Checkpoint Summary

- Six subscriptions in platform order, patch after fix: passed.
- No subscription beyond the six named hooks: passed.

### Trace: facade exports

1. `statuses/__init__.py` — imports the three routines from `.automate` / `.fix` /
   `.patch`; `__all__ = ["register_automate_statuses", "register_fix_statuses",
   "register_patch_statuses"]`; module docstring "two → three routines" → checkpoint:
   matches `registration.md`'s subscribe example — passed.
2. `autonomous/__init__.py` — imports `PipelineContribution` from `.contributions` and
   the two routines; `__all__ = ["PipelineContribution", "amend_workflow",
   "build_autonomous_workflow"]`; docstring generalized → checkpoint: matches
   `contribution.md`'s "What the cell provides" — passed.
3. Root `__init__.py` — **unchanged**: `register_hooks` is already exported; statuses
   and autonomous members are deliberately not re-exported at root (`assembly.md`: only
   `register_hooks` reaches the platform through the facade).

## Algorithm Design

### `register_patch_statuses` (new, `statuses/patch.py`)

**Responsibility**: register the six patch-line topic statuses as an independent chain
anchored at the built-in `empty`.

**Algorithm**:
```
1. register patch.intended for intent.md, anchored after `empty`
2. register patch.analyzed for impact.md, anchored after pybuggy.patch.intended
3. register patch.applied for apply.md, anchored after pybuggy.patch.analyzed
4. register patch.designed for rework.md, anchored after pybuggy.patch.applied
5. register patch.planned for workplan.md, anchored after pybuggy.patch.designed
6. register patch.done for completed/workplan.md, anchored after pybuggy.patch.planned
```

**Errors**: none raised — a structurally invalid registration (never the case for this
literal table) is skipped with a platform-side log warning; the hook never aborts the
command.

**Edge cases**: none — the routine is six literal calls with no branching.

### `PipelineContribution` (new, `autonomous/contributions.py`)

**Responsibility**: compile-time record of one pipeline's autonomy contribution — pure
data carrier with no behavior.

**Algorithm** (construction):
```
1. pydantic model, model_config = ConfigDict(kw_only=True, extra="forbid")
2. fields: identity: str, axis: str, window: list[str], build_artifact: str — all required, no defaults
3. define AUTOMATE_CONTRIBUTION and PATCH_CONTRIBUTION with the normative values
4. define CONTRIBUTIONS = (AUTOMATE_CONTRIBUTION, PATCH_CONTRIBUTION)
```

Normative records:

| Record | identity | axis | window | build_artifact |
|---|---|---|---|---|
| automate | `pybuggy:api.automate` | `api.automate` | review-testcases, create-testcases, code-design, design-review, coding-plan, plan-review, commit-changes | `plan.md` |
| patch | `pybuggy:api.patch` | `api.patch` | review-impact, apply-manifests, code-design, design-review, coding-plan, plan-review, commit-changes | `workplan.md` |

Design decisions (implementation freedom exercised):

- **Record constants are public module-level names** (`AUTOMATE_CONTRIBUTION`,
  `PATCH_CONTRIBUTION`, `CONTRIBUTIONS`) — they are the normative contribution table,
  imported by `amendment.py` and asserted by tests; not re-exported beyond the cell
  facade except the type itself (`PipelineContribution`).
- **`extra="forbid"`** mirrors `config/pipeline_autonomy.py` — a mistyped record key
  fails at import time instead of silently dropping a field.
- **No field defaults** — all four values are always meaningful for a record; absence is
  not a state (the conventions' empty-default rule targets optional data, matching
  `PipelineAutonomy`'s required `autonomous` precedent).
- **`window` typed `list[str]`** per the contract signature; the records pass tuples of
  strings, which pydantic coerces to lists — the model is the authority.

**Errors**: `pydantic.ValidationError` at import time for a malformed record definition
(fail-fast; cannot occur in shipped code).

**Edge cases**: empty `window` would make `window[-1]` fail in the builder — impossible
for the two compile-time records; the model adds no validators (pure data carrier).

### `amend_workflow` (modified, `autonomous/amendment.py`)

**Responsibility**: the autonomy contribution moment — qualify the run by record, gate
on the axis, contribute the document.

**Algorithm**:
```
1. read pipeline = context.pipeline (a PipelineIdentity)
2. contribution ← first record in CONTRIBUTIONS whose identity == pipeline.name, else None
3. IF contribution is None: return                      (silent no-op)
4. enabled ← resolve_autonomy(contribution.axis)
5. IF not enabled: return                               (silent no-op)
6. context.contribute(build_autonomous_workflow(contribution))
```

Module shape: drop the `_PIPELINE` / `_AXIS` constants; imports become
`from ..config import resolve_autonomy` (unchanged — keeps the monkeypatch surface),
`from .contributions import CONTRIBUTIONS, PipelineContribution` (the type only for the
local annotation, if annotated), `from .workflow import build_autonomous_workflow`.
Docstring and module docstring generalize from "pybuggy:api.automate" to the record
table.

**Errors**: `ValueError` (structural tool-config violation) and `yaml.YAMLError`
(invalid config file) propagate undamped — the platform stops the command with a clean
error naming pybuggy and discards the contribution.

**Edge cases**: unknown pipeline identity → no-op even when some axis entry is enabled
(the window never leaks across pipelines — guarded by the existing D1 regression test,
now parametrized).

### `build_autonomous_workflow` (modified, `autonomous/workflow.py`)

**Responsibility**: the pure builder of the contributed document from a record.

**Algorithm**:
```
1. import the platform models at call time (WorkflowDocument, WorkflowStage, WorkflowExtendStage)
2. stages ← {name: WorkflowStage(approve="auto") for name in contribution.window}
3. build_entry ← WorkflowExtendStage(
     after=[contribution.window[-1]],
     body={"title": "Build tests",
           "script": f'python3 -P -m goga.build "$(python3 -m goga history path -f {contribution.build_artifact})"',
           "after_script": "rm -rf .ralphex",
           "timeout": "8h"})
4. return WorkflowDocument(stages=stages, extend={"build": build_entry})
```

Module shape: keep `from __future__ import annotations` and the `TYPE_CHECKING`
`WorkflowDocument` import; add `from .contributions import PipelineContribution`
(module-level, intra-package — no goga dependency); delete `_WINDOW_STAGES`,
`_BUILD_SCRIPT`, `_BUILD_AFTER`; keep `_BUILD_NAME = "build"`, `_BUILD_TITLE =
"Build tests"`, `_BUILD_AFTER_SCRIPT = "rm -rf .ralphex"`, `_BUILD_TIMEOUT = "8h"`;
generalize the module and function docstrings ("seven-stage window" → "the record's
window").

**Errors**: none — deterministic and pure; no I/O, no platform facade calls.

**Edge cases**: none beyond the record's own shape (see `PipelineContribution`).

### `register_hooks` (modified, `reg_hooks.py`)

**Responsibility**: the platform subscription table — six hooks, four addresses.

**Algorithm**:
```
1. subscribe register_automate_statuses → statuses/register_statuses as automate
2. subscribe register_fix_statuses      → statuses/register_statuses as fix
3. subscribe register_patch_statuses    → statuses/register_statuses as patch   (NEW)
4. subscribe declare_pybuggy_session    → onboarding/declare_session as declare
5. subscribe amend_pybuggy_config       → onboarding/amend_config as amend
6. subscribe amend_workflow             → pipeline/amend_workflow as autonomy
```

Module shape: add `register_patch_statuses` to the `.statuses` import; docstring
"five subscriptions" → "six subscriptions in platform order"; module docstring unchanged
in scope (statuses, onboarding, autonomy).

**Errors**: none.

**Edge cases**: none — six literal subscriptions.

## Cross-cutting Concerns

- **Error handling**: the two silent no-op branches in `amend_workflow` return without
  contributing and without raising; every resolver error propagates undamped (autonomy
  never disables silently); the statuses routine raises nothing (skip-with-warning
  belongs to the platform). Errors are never wrapped or translated — the boundary rule:
  the config cell's failure modes are facts about the config cell; this cell's contract
  commits to propagation.
- **Logging**: none in the changed cells — the no-op branches are silent by contract,
  registration warnings are platform-side, and the builder is pure. No new log events.
- **Validation**: pydantic at import time for the contribution records (kw_only,
  extra=forbid); the config axis is validated by the unchanged `resolve_autonomy` on
  every call (no caching); no runtime validation is added to the statuses literals.
- **Caching**: none — `resolve_autonomy` re-reads per call by its own contract; the
  records are immutable module constants.
- **Concurrency**: not applicable — hooks run single-threaded inside a platform command;
  the touched modules hold no mutable state.

## Usages Analysis

### `conventions`
- **What it provides**: mandatory Python rules — relative intra-package imports, pydantic
  `kw_only=True` models, Google-style docstrings, blank-line block separation, test
  structure mirroring the source tree, naming, validation commands.
- **Where used**: every new/changed file and every test file in this design.
- **Why chosen**: the global annotation of all three cells mandates it.
- **How exactly**: `from .contributions import ...` (relative); `model_config =
  ConfigDict(kw_only=True, extra="forbid")`; docstrings with `Args` / `Returns` /
  `Raises`; `tests/autonomous/test_contributions.py` mirrors
  `autonomous/contributions.py`; ruff (line-length 120, target py310) must stay clean.

### `goga-statuses` (`.goga/usages/github/goga/history/registering-hooks.md`)
- **What it provides**: the registration surface — `register(name, filepath, after=,
  before=)`, qualified storage as `<tool>.<name>`, add-only built-ins,
  skip-with-warning failure behavior, nested artifact paths.
- **Where used**: `register_patch_statuses` (and the tests' recorder double, which
  mirrors the surface).
- **Why chosen**: the routine's annotation references it for parameters and anchor
  semantics.
- **How exactly**: six `context.register` calls with `after` anchors only (no `before` —
  the fix-line pattern); names unprefixed; `completed/workplan.md` keeps its directory
  part.

### `goga-pipeline-hooks` (`.goga/usages/github/goga/pipeline/registering-hooks.md`)
- **What it provides**: the `pipeline / amend_workflow` amendment moment — the
  `WorkflowAmendment` view reads (`pipeline`, `decision`, `workflow`, `work`),
  `contribute(document)` buffering, commit-after-return, authored-intent-wins merge,
  clean-stop failure behavior.
- **Where used**: `amend_workflow`.
- **Why chosen**: its annotation references it for the view contract and contribute
  semantics.
- **How exactly**: read `context.pipeline.name`; contribute exactly one document; never
  read the authored workflow; raise nothing on the no-op paths.

### `goga-workflow-document` (`.goga/usages/github/goga/pipeline/workflow/parse-workflow.md`)
- **What it provides**: the `WorkflowDocument` instruction vocabulary — per-stage
  override keys (`approve` among them) and extend-entry keys (`before`/`after`
  positioning, verbatim body, forbidden extend keys).
- **Where used**: `build_autonomous_workflow`.
- **Why chosen**: its annotation references it for the accepted document structure.
- **How exactly**: `WorkflowStage(approve="auto")` per window stage;
  `WorkflowExtendStage(after=[...], body={title, script, after_script, timeout})`; no
  `manual`/`notes`/`reflect`/`memory` anywhere in the contribution.

### `goga-compile-flow` (`.goga/usages/github/goga/pipeline/compiler/compile-flow.md`)
- **What it provides**: the compiled effects of the contributed directives —
  `approve: "auto"` suppresses `communication: true` and emits `auto_approve: true` for
  planner roles; body `script`/`after_script`/`timeout` compile to
  `script`/`script_after`/`script_timeout`.
- **Where used**: `build_autonomous_workflow` (effects reasoning); the design's
  acceptance reasoning that `accept-result` must never carry `approve`.
- **Why chosen**: the builder's annotation references it for directive effects.
- **How exactly**: the window stages compile unattended; the build extend-stage carries
  its script block verbatim.

### Imported Usages
- `autonomy` from `goga_tool_pybuggy/config` — the resolver consumption pattern (whole
  axis validated per call, clean error naming pybuggy, no caching).
  - Path: `goga_tool_pybuggy/config/.usages/autonomy.md`
- `registration` from `goga_tool_pybuggy/statuses` (root Imports) — the status
  subscription pattern; already materialized in `statuses/.usages/registration.md`.
- `contribution` from `goga_tool_pybuggy/autonomous` (root Imports) — the autonomy
  subscription pattern; already materialized in `autonomous/.usages/contribution.md`.

## `.usages/` Update

### Cell: `goga_tool_pybuggy/statuses`

- **`registration.md`** → `goga_tool_pybuggy/statuses/.usages/registration.md`
  - Status: current — three hooks, the `register_patch_statuses` bullet, the `patch`
    subscribe line, generalized stable-names/add-only sentences.
  - Additions needed: none.
  - Updates needed: none.

### Cell: `goga_tool_pybuggy/autonomous`

- **`contribution.md`** → `goga_tool_pybuggy/autonomous/.usages/contribution.md`
  - Status: current — both qualifying identities, the `PipelineContribution` bullet with
    both records, the record-taking builder, both axis keys.
  - Additions needed: none.
  - Updates needed: none.

### Cell: `goga_tool_pybuggy` (root)

- **`assembly.md`** → `goga_tool_pybuggy/.usages/assembly.md`
  - Status: current — six-hooks/four-addresses wording, the `patch` hook-table row, both
    qualifying pipelines in the autonomy sentence, the six patch status rows, the
    patch-chain stacking sentence.
  - Additions needed: none.
  - Updates needed: none.

No new `.usages/` files: the changes stay inside the existing functional domains
(status subscription; autonomy contribution; root assembly), and the files were applied
by the apply-architecture stage in their target form. This design's facades match them
exactly — no CODEMANIFEST `Usages` references point at own `.usages/` files.

## Test Stack Trace

### General Setup

- `tests/statuses/conftest.py` — `recorder_context` fixture (`_RecorderContext` with
  `register(name, artifact, after=None, before=None)` recording tuples): **reused
  unchanged**.
- `tests/autonomous/conftest.py` — `amendment_view` fixture (automate identity),
  `amendment_identity(name)` helper, `_AmendmentView` double: **reused unchanged**; patch
  views are built as `_AmendmentView(amendment_identity("pybuggy:api.patch"))`.
- No mocks beyond `monkeypatch.setattr(amendment_module, "resolve_autonomy", ...)`
  (external boundary: the config cell's file read) — everything else is pure logic.

### Source File Registry

- `goga_tool_pybuggy/statuses/patch.py` (new) — tested by `tests/statuses/test_patch.py`
- `goga_tool_pybuggy/autonomous/contributions.py` (new) — tested by
  `tests/autonomous/test_contributions.py`
- `goga_tool_pybuggy/autonomous/amendment.py` (modified) — tested by
  `tests/autonomous/test_amendment.py`
- `goga_tool_pybuggy/autonomous/workflow.py` (modified) — tested by
  `tests/autonomous/test_workflow.py`
- `goga_tool_pybuggy/reg_hooks.py` (modified) — tested by `tests/test_reg_hooks.py`
- `tests/test_autonomy_integration.py` (modified) — the integration consumer of the
  changed builder signature; its two no-arg builder call sites (lines 61 and 85) move to
  the record form

---

### Positive Tests

#### `test_register_patch_statuses_importable_from_facade`
(`tests/statuses/test_patch.py` — new)

**Setup**: none (pure import).

**Input**: the facade symbol.

**Trace**:
```
from goga_tool_pybuggy.statuses import register_patch_statuses
  → assert callable(...)
```

**Assertions**:
```
callable(register_patch_statuses)
"register_patch_statuses" in goga_tool_pybuggy.statuses.__all__
```

**Sufficiency**: the facade contract — `registration.md` documents this import path; a
dropped export breaks the platform subscription at import time.

#### `test_register_patch_statuses_signature_matches_contract`
(`tests/statuses/test_patch.py` — new)

**Setup**: none.

**Input**: `inspect.signature(register_patch_statuses)`.

**Trace**:
```
inspect.signature(register_patch_statuses)
  → parameters ["context"]; context annotation is object; return annotation None
```

**Assertions**:
```
list(signature.parameters) == ["context"]
signature.parameters["context"].annotation is object
signature.return_annotation is None
```

**Sufficiency**: the CODEMANIFEST Routine signature `(context: object)`; guards against
parameter drift that would break the platform's by-name delivery.

#### `test_register_patch_statuses_registers_six_statuses_in_order`
(`tests/statuses/test_patch.py` — new)

**Setup**: `recorder_context` fixture (fresh `_RecorderContext`).

**Input**: `recorder_context`.

**Trace**:
```
register_patch_statuses(recorder_context)
  → context.register("patch.intended", "intent.md", after="empty")        # call 1
  → context.register("patch.analyzed", "impact.md", after="pybuggy.patch.intended")   # 2
  → context.register("patch.applied", "apply.md", after="pybuggy.patch.analyzed")     # 3
  → context.register("patch.designed", "rework.md", after="pybuggy.patch.applied")    # 4
  → context.register("patch.planned", "workplan.md", after="pybuggy.patch.designed")  # 5
  → context.register("patch.done", "completed/workplan.md", after="pybuggy.patch.planned")  # 6
```

**Assertions**:
```
recorder_context.calls == [
    ("patch.intended", "intent.md", "empty", None),
    ("patch.analyzed", "impact.md", "pybuggy.patch.intended", None),
    ("patch.applied", "apply.md", "pybuggy.patch.analyzed", None),
    ("patch.designed", "rework.md", "pybuggy.patch.applied", None),
    ("patch.planned", "workplan.md", "pybuggy.patch.designed", None),
    ("patch.done", "completed/workplan.md", "pybuggy.patch.planned", None),
]
```

**Sufficiency**: the normative status table end to end — order (anchor resolvability),
artifact spelling, anchor spelling, the unprefixed names, and the nested
`completed/workplan.md` directory part; prevents any silent reorder or rename of the
line.

#### `test_pipeline_contribution_importable_from_facade`
(`tests/autonomous/test_contributions.py` — new)

**Setup**: none.

**Input**: the facade symbols.

**Trace**:
```
from goga_tool_pybuggy.autonomous import PipelineContribution
  → issubclass(PipelineContribution, BaseModel)
```

**Assertions**:
```
issubclass(PipelineContribution, pydantic.BaseModel)
"PipelineContribution" in goga_tool_pybuggy.autonomous.__all__
```

**Sufficiency**: the facade export contract from the arch checklist ("facade exports
`PipelineContribution` plus the two routines").

#### `test_pipeline_contribution_is_kw_only_data_carrier`
(`tests/autonomous/test_contributions.py` — new)

**Setup**: none.

**Input**: keyword construction with all four fields; one positional attempt; one extra
kwarg.

**Trace**:
```
PipelineContribution(identity="i", axis="a", window=["s"], build_artifact="f.md")
  → model instance with the four fields
PipelineContribution("i", "a", ["s"], "f.md")
  → TypeError (kw_only)
PipelineContribution(identity="i", axis="a", window=["s"], build_artifact="f.md", typo=1)
  → pydantic.ValidationError (extra="forbid")
```

**Assertions**:
```
record.identity == "i"; record.axis == "a"; record.window == ["s"]; record.build_artifact == "f.md"
with pytest.raises(TypeError): PipelineContribution("i", "a", ["s"], "f.md")
with pytest.raises(ValidationError): PipelineContribution(..., typo=1)
```

**Sufficiency**: the "pydantic model with kw_only=True; pure data carrier" requirement —
positional construction and stray fields must both fail, so the compile-time table
cannot drift into ambiguity.

#### `test_contribution_table_is_normative`
(`tests/autonomous/test_contributions.py` — new)

**Setup**: none.

**Input**: `CONTRIBUTIONS`, `AUTOMATE_CONTRIBUTION`, `PATCH_CONTRIBUTION` from
`goga_tool_pybuggy.autonomous.contributions`.

**Trace**:
```
CONTRIBUTIONS
  → exactly (AUTOMATE_CONTRIBUTION, PATCH_CONTRIBUTION)
AUTOMATE_CONTRIBUTION fields → identity/axis/window/build_artifact
PATCH_CONTRIBUTION fields    → identity/axis/window/build_artifact
```

**Assertions**:
```
CONTRIBUTIONS == (AUTOMATE_CONTRIBUTION, PATCH_CONTRIBUTION)
AUTOMATE_CONTRIBUTION.identity == "pybuggy:api.automate"
AUTOMATE_CONTRIBUTION.axis == "api.automate"
AUTOMATE_CONTRIBUTION.window == ["review-testcases", "create-testcases", "code-design",
                                 "design-review", "coding-plan", "plan-review", "commit-changes"]
AUTOMATE_CONTRIBUTION.build_artifact == "plan.md"
PATCH_CONTRIBUTION.identity == "pybuggy:api.patch"
PATCH_CONTRIBUTION.axis == "api.patch"
PATCH_CONTRIBUTION.window == ["review-impact", "apply-manifests", "code-design",
                              "design-review", "coding-plan", "plan-review", "commit-changes"]
PATCH_CONTRIBUTION.build_artifact == "workplan.md"
```

**Sufficiency**: the normative contribution table — a mistyped identity/axis/window
stage or build artifact here would misroute autonomy or break compilation; this test
pins every literal.

#### `test_contribution_windows_end_at_commit_changes`
(`tests/autonomous/test_contributions.py` — new)

**Setup**: none.

**Input**: each record of `CONTRIBUTIONS`.

**Trace**:
```
for record in CONTRIBUTIONS:
  record.window[-1]
```

**Assertions**:
```
all(record.window for record in CONTRIBUTIONS)
all(record.window[-1] == "commit-changes" for record in CONTRIBUTIONS)
```

**Sufficiency**: the invariant "both windows end at commit-changes — autonomy ends there,
the acceptance stage stays interactive"; a window that stopped early would leave stages
interactive, one that ran past would auto-approve acceptance.

#### `test_amend_workflow_contributes_when_enabled`
(`tests/autonomous/test_amendment.py` — modified: builder call site gains the record;
assertions kept)

**Setup**: `amendment_view` (identity `pybuggy:api.automate`);
`monkeypatch.setattr(amendment_module, "resolve_autonomy", lambda _pipeline: True)`.

**Input**: `amendment_view`.

**Trace**:
```
amend_workflow(amendment_view)
  → pipeline.name == "pybuggy:api.automate"
  → record resolved: AUTOMATE_CONTRIBUTION
  → resolve_autonomy("api.automate") → True
  → build_autonomous_workflow(AUTOMATE_CONTRIBUTION) → WorkflowDocument
  → context.contribute(document)
```

**Assertions**:
```
amendment_view.contributed == [build_autonomous_workflow(AUTOMATE_CONTRIBUTION)]
```

**Sufficiency**: the automate happy path after generalization — proves the refactor kept
automate's contribution byte-identical in effect (same window, same build target).

#### `test_amend_workflow_contributes_patch_window_for_patch_pipeline`
(`tests/autonomous/test_amendment.py` — new)

**Setup**: `view = _AmendmentView(amendment_identity("pybuggy:api.patch"))`;
`monkeypatch.setattr(amendment_module, "resolve_autonomy", lambda _pipeline: True)`.

**Input**: `view`.

**Trace**:
```
amend_workflow(view)
  → pipeline.name == "pybuggy:api.patch"
  → record resolved: PATCH_CONTRIBUTION
  → resolve_autonomy("api.patch") → True
  → build_autonomous_workflow(PATCH_CONTRIBUTION) → WorkflowDocument (patch window, workplan build)
  → context.contribute(document)
```

**Assertions**:
```
view.contributed == [build_autonomous_workflow(PATCH_CONTRIBUTION)]
```

**Sufficiency**: the new feature core — the patch pipeline qualifies and receives the
patch-shaped document (not automate's); prevents the record table or the lookup from
dropping patch.

#### `test_amend_workflow_resolves_the_records_axis`
(`tests/autonomous/test_amendment.py` — new; parametrized)

**Setup**: parametrize `(pipeline_name, expected_axis)` over
`("pybuggy:api.automate", "api.automate")` and `("pybuggy:api.patch", "api.patch")`;
monkeypatch the resolver with a recording lambda returning `False` (no contribution
needed).

**Input**: a view reporting `pipeline_name`.

**Trace**:
```
amend_workflow(view)
  → record resolved for pipeline_name
  → resolve_autonomy(expected_axis) — captured argument
  → False → silent return
```

**Assertions**:
```
captured == [expected_axis]
```

**Sufficiency**: axis routing — a record with a wrong `axis` would silently disable
autonomy for its pipeline (the resolver would just miss); only an argument-capture test
catches that.

#### `test_amend_workflow_end_to_end_patch_with_real_config`
(`tests/test_autonomy_integration.py` — modified: new patch scenario in `TestRunChain`;
the file's two no-arg builder call sites move to the record form per the Source File
Registry)

**Setup**: `tool_config("pipelines:\n  api.patch:\n    autonomous: true\n")` (writes the
real standard tree `.goga/tools/pybuggy/config.yml` under `tmp_path`, chdirs into it);
`view = _AmendmentView(amendment_identity("pybuggy:api.patch"))` — the existing double
from `tests/autonomous/conftest.py`, unchanged.

**Input**: `view`.

**Trace**:
```
amend_workflow(view)
  → pipeline.name == "pybuggy:api.patch"
  → PATCH_CONTRIBUTION resolved from CONTRIBUTIONS
  → resolve_autonomy("api.patch") reads the real config tree
  → axis {api.patch: {autonomous: true}} validates into PipelineAutonomy → True
  → build_autonomous_workflow(PATCH_CONTRIBUTION) → WorkflowDocument
  → context.contribute(document)
```

**Assertions**:
```
view.contributed == [build_autonomous_workflow(PATCH_CONTRIBUTION)]
```

**Sufficiency**: the end-to-end routing of the real `api.patch` axis key through the
real resolver — catches a record-axis ↔ config-key mismatch that the monkeypatched unit
tests cannot see (a wrong axis string passes every unit test while silently disabling
autonomy in real runs); exactly the task's acceptance scenario.

#### `test_build_autonomous_workflow_document_shape`
(`tests/autonomous/test_workflow.py` — modified: gains the automate record argument;
assertions kept)

**Setup**: none.

**Input**: `AUTOMATE_CONTRIBUTION`.

**Trace**:
```
build_autonomous_workflow(AUTOMATE_CONTRIBUTION)
  → stages: seven WorkflowStage(approve="auto") keyed by the automate window
  → extend["build"]: after ["commit-changes"], body {title, script(plan.md), after_script, timeout}
```

**Assertions**:
```
isinstance(document, WorkflowDocument)
document.prompt is None; document.memory is None
list(document.stages) == ["review-testcases", "create-testcases", "code-design",
                          "design-review", "coding-plan", "plan-review", "commit-changes"]
all(stage.approve == "auto" for stage in document.stages.values())
document.extend["build"].after == ["commit-changes"]
document.extend["build"].before is None
document.extend["build"].body == {
    "title": "Build tests",
    "script": 'python3 -P -m goga.build "$(python3 -m goga history path -f plan.md)"',
    "after_script": "rm -rf .ralphex",
    "timeout": "8h",
}
"accept-result" not in document.stages
"accept-result" not in document.extend
```

**Sufficiency**: automate's document shape after the refactor — the acceptance criteria
demand automate behavior unchanged; this is the byte-level guard.

#### `test_build_autonomous_workflow_patch_document_shape`
(`tests/autonomous/test_workflow.py` — new)

**Setup**: none.

**Input**: `PATCH_CONTRIBUTION`.

**Trace**:
```
build_autonomous_workflow(PATCH_CONTRIBUTION)
  → stages: seven WorkflowStage(approve="auto") keyed by the patch window
  → extend["build"]: after ["commit-changes"], body {title, script(workplan.md), after_script, timeout}
```

**Assertions**:
```
list(document.stages) == ["review-impact", "apply-manifests", "code-design",
                          "design-review", "coding-plan", "plan-review", "commit-changes"]
all(stage.approve == "auto" for stage in document.stages.values())
document.extend["build"].after == ["commit-changes"]
document.extend["build"].body == {
    "title": "Build tests",
    "script": 'python3 -P -m goga.build "$(python3 -m goga history path -f workplan.md)"',
    "after_script": "rm -rf .ralphex",
    "timeout": "8h",
}
"accept-result" not in document.stages
"accept-result" not in document.extend
```

**Sufficiency**: the patch contribution — window membership, the manual acceptance stage
excluded, and the build stage running on `workplan.md` (not `plan.md`); catches a
record-derivation bug that would build the wrong artifact.

#### `test_build_autonomous_workflow_deterministic`
(`tests/autonomous/test_workflow.py` — modified: parametrized over both records)

**Setup**: parametrize over `CONTRIBUTIONS`.

**Input**: each record, twice.

**Trace**:
```
first = build_autonomous_workflow(record); second = build_autonomous_workflow(record)
```

**Assertions**:
```
first == second
```

**Sufficiency**: the "deterministic and pure" requirement — repeated amendment moments
must produce identical documents (pydantic models compare by value).

#### `test_register_hooks_subscribes_six_hooks`
(`tests/test_reg_hooks.py` — modified)

**Setup**: `_RecorderHooks()` double.

**Input**: the recorder.

**Trace**:
```
register_hooks(recorder)
  → six subscribe calls in platform order
```

**Assertions**:
```
recorder.calls == [
    ("statuses", "register_statuses", "automate", register_automate_statuses),
    ("statuses", "register_statuses", "fix", register_fix_statuses),
    ("statuses", "register_statuses", "patch", register_patch_statuses),
    ("onboarding", "declare_session", "declare", declare_pybuggy_session),
    ("onboarding", "amend_config", "amend", amend_pybuggy_config),
    ("pipeline", "amend_workflow", "autonomy", amend_workflow),
]
```

**Sufficiency**: the six-entry subscription table — the patch row's presence, position
(in the statuses group, after `fix`), address, and the identity of the subscribed
callable; also guards the "nothing beyond the six" constraint by exact-length equality.

---

### Negative Tests

#### `test_amend_workflow_no_op_for_other_pipeline_even_when_axis_enabled`
(`tests/autonomous/test_amendment.py` — modified: parametrized)

**Setup**: parametrize the reported name over `"pybuggy:code.review"` and
`"pybuggy:api.fix"`; resolver monkeypatched to `True`.

**Input**: `view = _AmendmentView(amendment_identity(name))`.

**Trace**:
```
amend_workflow(view)
  → no record matches the name → None
  → silent return (resolve_autonomy never called)
```

**Assertions**:
```
view.contributed == []
```

**Sufficiency**: the window must never leak into a non-qualifying pipeline even with an
enabled axis entry (the D1 regression, now also covering the fix pipeline, which must
never receive any autonomy window).

#### `test_amend_workflow_no_op_when_autonomy_disabled`
(`tests/autonomous/test_amendment.py` — kept)

**Setup**: `amendment_view`; resolver monkeypatched to `False`.

**Input**: `amendment_view`.

**Trace**:
```
amend_workflow(amendment_view)
  → record resolved; resolve_autonomy("api.automate") → False
  → silent return
```

**Assertions**:
```
amendment_view.contributed == []
```

**Sufficiency**: the disabled opt-in (`autonomous: false`, absent entry, absent file) is
a silent no-op — the explicit acceptance criterion.

#### `test_amend_workflow_errors_propagate_undamped`
(`tests/autonomous/test_amendment.py` — kept)

**Setup**: `amendment_view`; resolver monkeypatched with
`def _raise(pipeline): raise ValueError("pybuggy tool config: boom")`.

**Input**: `amendment_view`.

**Trace**:
```
amend_workflow(amendment_view)
  → record resolved; resolve_autonomy raises ValueError
  → error propagates out of the hook
```

**Assertions**:
```
with pytest.raises(ValueError, match="pybuggy tool config: boom"): amend_workflow(amendment_view)
amendment_view.contributed == []
```

**Sufficiency**: autonomy never disables silently — a structural tool-config violation
must stop the command (the platform turns it into a clean error naming pybuggy), never
swallow into a no-op.

---

### Edge Case Tests

#### `test_build_autonomous_workflow_signature_matches_contract`
(`tests/autonomous/test_workflow.py` — modified)

**Setup**: none.

**Input**: `inspect.signature(build_autonomous_workflow)`.

**Trace**:
```
inspect.signature(build_autonomous_workflow)
  → one parameter "contribution"; annotations stringified by from __future__ import annotations
```

**Assertions**:
```
list(signature.parameters) == ["contribution"]
signature.parameters["contribution"].annotation == "PipelineContribution"
signature.return_annotation == "WorkflowDocument"
```

**Sufficiency**: the changed signature `(contribution: PipelineContribution) ->
document: WorkflowDocument` — the call-site contract every consumer (amendment, tests)
relies on; string comparison because `workflow.py` keeps `from __future__ import
annotations`.

#### `test_amend_workflow_signature_matches_contract` /
`test_register_patch_statuses_signature_matches_contract`

Covered above (positive contract tests) — the parameter surface stays exactly
`context: object` for both hooks despite the internal rewrite.

The kw_only / extra-forbid edge behaviors of `PipelineContribution` are covered by
`test_pipeline_contribution_is_kw_only_data_carrier` above.

## Traced Adjacent Artifacts (Non-Cell)

Outside this design's change set (package data, not cells — carried by the task/arch
plan for the coding stages), but traced for consistency with the contracts designed
above:

- `goga_tool_pybuggy/pipelines/api.patch.yml` (to be created) — its stage chain must
  contain every window stage of `PATCH_CONTRIBUTION` (`review-impact`,
  `apply-manifests`, `code-design`, `design-review`, `coding-plan`, `plan-review`,
  `commit-changes`) and an `accept-result` stage outside the window: the task skeleton's
  10 stages satisfy this exactly. A contributed `approve` on an unknown stage would
  surface as the compiler's structural error — the consistency holds as designed.
- Status artifacts vs pipeline artifacts — the patch status table's artifacts
  (`intent.md`, `impact.md`, `apply.md`, `rework.md`, `workplan.md`,
  `completed/workplan.md`) match the task's artifact list; no collision with automate
  (`plan.md`, `completed/plan.md`) or fix (`fix-*.md`) lines.
- `goga_tool_pybuggy/skills/pybuggy-api-patch-*` and `docs/pipelines/api-patch.md` —
  content work, no interaction with the cells designed here beyond the stage names
  above.
- Packaging: `pipelines/*.yml` and `skills/**/*` are covered by the existing
  package-data globs in `pyproject.toml` — no packaging registration needed.

## Additional Instructions for the Implementation Agent

- Do not edit any `CODEMANIFEST` or `.usages/` file — the contracts and consumer docs
  are already materialized and verified; this design implements against them as-is.
- Follow `conventions` strictly: relative intra-package imports; pydantic `kw_only=True`;
  Google-style docstrings on every public routine/class (module docstrings updated where
  counts changed: "two → three" status routines, "five → six" subscriptions, generalized
  autonomy wording); one blank line between logical blocks; ruff (line-length 120,
  py310) must stay clean.
- Keep `from ..config import resolve_autonomy` as a module-level name inside
  `amendment.py` — tests monkeypatch `amendment_module.resolve_autonomy`; do not switch
  to `from .. import config` + attribute calls.
- Keep the call-time platform import in `workflow.py` (with `noqa: PLC0415`) and
  `from __future__ import annotations` — the package must import without goga, and the
  signature test compares stringified annotations.
- Remove the dead constants when generalizing (`_PIPELINE`, `_AXIS` in `amendment.py`;
  `_WINDOW_STAGES`, `_BUILD_SCRIPT`, `_BUILD_AFTER` in `workflow.py`) — do not leave
  both the constants and the record paths alive.
- The extend entry name stays `"build"` and its title stays `"Build tests"` for both
  records — only the window, the `after` positioning, and the script artifact derive
  from the record.
- Update the existing tests in place (`test_amendment.py`, `test_workflow.py`,
  `test_reg_hooks.py`, `test_autonomy_integration.py`) rather than duplicating them; add
  the two new files (`tests/statuses/test_patch.py`,
  `tests/autonomous/test_contributions.py`); reuse the existing conftest doubles
  unchanged.
- In `tests/test_autonomy_integration.py`, update the two no-arg builder call sites to
  `build_autonomous_workflow(AUTOMATE_CONTRIBUTION)` and add the patch end-to-end
  scenario (`test_amend_workflow_end_to_end_patch_with_real_config`), importing
  `AUTOMATE_CONTRIBUTION` / `PATCH_CONTRIBUTION` from
  `goga_tool_pybuggy.autonomous.contributions` — the records stay module-level names,
  not facade exports (everything else in the file is unchanged: real resolver, real
  platform delivery).
- Validation: `pytest tests/ -x` and `ruff check` must run in the project virtualenv —
  this design container has neither binary (pytest/ruff absent; the root package import
  requires `swax`). Cell-level import smoke
  (`python -c "from goga_tool_pybuggy.statuses import register_patch_statuses"` and
  `...autonomous import PipelineContribution"`) is possible with the goga interpreter
  and should be re-run after implementation.
