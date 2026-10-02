# Design Document: Autonomous runs of the `api.automate` pipeline

Topic directory: `.goga/history/2026/autonomous/`. Sources: task.md, adr.md (accepted), the
architecture plan `arch.md` (materialized into the cells by the apply-architecture stage), and the
CODEMANIFEST tree at commit state of branch `autonomous` (working tree). Every contract statement
below traces to a CODEMANIFEST annotation or a synced usage file; every design decision that the
contracts leave open is marked **[decision]** and justified.

## Contract Changes

### Changed CODEMANIFEST Files

- `goga_tool_pybuggy/statuses/CODEMANIFEST` (created): the two topic-status routines moved out of
  the root manifest — `register_automate_statuses` (`automate.py`), `register_fix_statuses`
  (`fix.py`); practices `conventions`, `goga-statuses`.
- `goga_tool_pybuggy/config/CODEMANIFEST` (modified): header drops the inline `pyyaml` practice,
  gains `goga-tool-config`; `load_config` narrowed to `load_config() -> config: Config` with the
  platform raw read and the absent-file clean error; new entities `PipelineAutonomy`
  (`pipeline_autonomy.py`) and `resolve_autonomy` (`storage.py`); footer Description updated.
- `goga_tool_pybuggy/autonomous/CODEMANIFEST` (created): `amend_workflow` (`amendment.py`),
  `build_autonomous_workflow` (`workflow.py`); Imports `resolve_autonomy` + usage `autonomy` from
  `config`; practices `conventions`, `goga-pipeline-hooks`, `goga-workflow-document`,
  `goga-compile-flow`.
- `goga_tool_pybuggy/commands/init/CODEMANIFEST` (modified): Imports gains usage `autonomy` from
  `config`; `pybuggy_questions` gains Algorithm step 4 (the autonomy confirm) and its Requirements
  line; `build_config_data` gains Algorithm step 3 (the conditional pipelines axis entry) and its
  axis Requirements line.
- `goga_tool_pybuggy/CODEMANIFEST` (root, modified): Imports gains the `statuses` edge
  (`register_automate_statuses`, `register_fix_statuses`, usage `registration`) and the
  `autonomous` edge (`amend_workflow`, usage `contribution`); `register_hooks` moves to
  `reg_hooks.py` with five subscriptions; the two status-routine body contracts and the header
  `goga-statuses` practice are removed (moved to the statuses cell).

### New Entities

- `register_automate_statuses(context: object)` — statuses/automate.py: six literal registration
  calls placing the automate status line on the topic status scale.
- `register_fix_statuses(context: object)` — statuses/fix.py: five literal registration calls
  placing the independent fix status line.
- `PipelineAutonomy(autonomous: bool)` — config/pipeline_autonomy.py: pydantic record of one
  `pipelines`-axis entry; admits exactly the `autonomous` member.
- `resolve_autonomy(pipeline: str) -> enabled: bool` — config/storage.py: whole-axis-validating
  lookup of the autonomy flag for a pipeline name.
- `amend_workflow(context: object)` — autonomous/amendment.py: the `pipeline / amend_workflow`
  hook — gates on the pipeline identity, resolves autonomy, contributes the document.
- `build_autonomous_workflow() -> document: dict[str, object]` — autonomous/workflow.py: pure
  builder of the WorkflowDocument-shaped contribution from compile-time constants.

### Changed Entities

- `load_config()` — config/storage.py: no parameters anymore; raw read through
  `goga.config.load_tool_config`; absent file fails with a clean error naming the location;
  `CONFIG_PATH` and its facade export are deleted.
- `register_hooks(hooks: object)` — root reg_hooks.py (moved from statuses.py): five
  subscriptions (was four) — the statuses pair, the onboarding pair, and the autonomy hook.
- `pybuggy_questions()` — commands/init/session.py: appends the `autonomous` confirm (default
  disabled) as the last item of the block.
- `build_config_data(answers, extra_specs)` — commands/init/session.py: emits the `pipelines`
  axis entry only on an enabling `autonomous` answer.

### Deleted Entities

- Root body contracts `register_automate_statuses`, `register_fix_statuses` — moved verbatim
  (semantics unchanged) into the `statuses` cell; the root now imports them.
- `goga_tool_pybuggy/statuses.py` — module deleted on disk by the apply-architecture stage; the
  `statuses/` package becomes the sole carrier of the name (already the case in the working tree).

### Usages and Annotations Changes

- Root header: `goga-statuses` practice removed (consumed by the statuses cell now); connected-
  practices list and the hook-registration paragraph name `registration` and `contribution`.
- Config header: inline `pyyaml` practice replaced by `goga-tool-config`
  (`.goga/usages/github/goga/config/tool-configuration.md`).
- Autonomous header: four practices (`conventions`, `goga-pipeline-hooks`,
  `goga-workflow-document`, `goga-compile-flow`) plus the imported `autonomy` usage.
- `.usages` files: `statuses/.usages/registration.md` and `autonomous/.usages/contribution.md`
  created; `config/.usages/autonomy.md` created; `config/.usages/configuration.md`,
  `commands/init/.usages/config-build.md`, root `.usages/assembly.md` updated — all by the
  apply-architecture stage, verified consistent in this design (see `.usages/` Update).

## Applied Fixes

### Fixed CODEMANIFEST Defects

Both defects were found by the Phase-4 behavioral trace, proposed to the user in the stage dialog
(q1), and approved for application ("apply both").

- `goga_tool_pybuggy/autonomous/CODEMANIFEST` — `amend_workflow` Algorithm: the pipeline-identity
  gate was absent from the method algorithm (it lived only in the cell-level annotation). Before:
  steps read-pipeline → resolve → no-op/contribute. After: an explicit step 2 "When the identity
  is not api.automate, return without contributing — a silent no-op." (steps renumbered to five).
  Reason: without the gate, an enabling axis entry written for a *different* pipeline name would
  contribute the seven api.automate stage names into that pipeline and fail as the compiler's
  structural error — violating the task's acceptance criterion "running pipeline not
  `api.automate` → silent no-op".
- `goga_tool_pybuggy/config/CODEMANIFEST` — `resolve_autonomy` Requirements: the enumerated
  structural violations did not cover a present file whose root parses to a non-mapping (a bare
  string/list). After: the list opens with "a non-mapping config root". The same clarification was
  mirrored in `config/.usages/autonomy.md` ("a non-mapping file root"). Reason: the naive
  implementation (`raw.get(...)`) would crash with an unclean `AttributeError`; the contract now
  fixes the fail-loud behavior explicitly.

Validation after the fixes: `goga lint` → 19 cells, 0 errors; `goga schema` still shows both new
cells and the two new root dependency edges; the affected entry points were re-traced (below).

## Entity Interaction and Data Flow

### Interaction Diagram

```
                         goga platform (hooks)
                                │ imports register_hooks from package root
                                ▼
┌───────────────────── goga_tool_pybuggy (root) ─────────────────────────────┐
│ __init__.py ── from .reg_hooks import register_hooks                       │
│ reg_hooks.py ── 5 × hooks.subscribe(...)                                   │
│   ├── ("statuses",  "register_statuses", "automate", register_automate_statuses) ── statuses/
│   ├── ("statuses",  "register_statuses", "fix",      register_fix_statuses)      ── statuses/
│   ├── ("onboarding","declare_session",    "declare", declare_pybuggy_session)   ── commands/init
│   ├── ("onboarding","amend_config",       "amend",   amend_pybuggy_config)      ── commands/init
│   └── ("pipeline",  "amend_workflow",     "autonomy", amend_workflow)           ── autonomous/
└─────────────────────────────────────────────────────────────────────────────┘
        │ onboarding amend moment                          │ pipeline amendment moment
        ▼                                                  ▼
  commands/init/session.py                          autonomous/amendment.py
  pybuggy_questions()  ── "autonomous" confirm       amend_workflow(context)
  build_config_data() ── pipelines axis ─┐             ├─ context.pipeline gate ("api.automate")
                                         │             ├─ resolve_autonomy(pipeline)  ◄── config/
         .goga/tools/pybuggy/config.yml ◄─┴─ engine      └─ context.contribute(
                                                              build_autonomous_workflow())
                                                                    │
                                                     WorkflowDocument-shaped dict:
                                                     stages ×7 {approve: auto}
                                                     extend.build (after commit-changes,
                                                       title/script/after_script/timeout)
```

### Data Flows

- **Onboarding → axis**: `pybuggy_questions` declares the `autonomous` confirm → engine surveys
  it (bool, default False) → `amend_pybuggy_config` reads the answer view → `build_config_data`
  emits `pipelines: {"api.automate": {"autonomous": true}}` only on True → engine serializes to
  `.goga/tools/pybuggy/config.yml`. Execution order inside `build_config_data`: specs are parsed
  first, scalar keys collected second, the axis entry added third, `specs` placed last in the
  payload mapping.
- **Run → contribution**: platform fires `pipeline / amend_workflow` before compilation →
  `amend_workflow` reads `context.pipeline` → (gate) → `resolve_autonomy` reads the file through
  `load_tool_config` and validates the whole axis → on True, `build_autonomous_workflow()` builds
  the constants document → `context.contribute(document)` buffers it → platform merges (authored
  intent wins per slot) → compiler validates and compiles the merged workflow.
- **Commands → config**: pull/list/info/generate/diff call `load_config()` (unchanged call sites)
  → `load_tool_config("pybuggy", "config.yml")` raw read → `Config.model_validate` (extra keys —
  including `pipelines` — are ignored; `specs` required).
- **Statuses → topic scale**: platform fires `statuses / register_statuses` per subscribed hook →
  each routine makes its literal `context.register(...)` calls in normative order.

### Entity Dependencies

Import graph (all intra-package references relative; no cycles; lint-verified):

- `statuses/` — imports nothing (leaf).
- `config/` — stdlib + pydantic only; `goga.config.load_tool_config` imported *at call time*
  inside the routines (goga stays out of runtime dependencies).
- `autonomous/` — `from ..config import resolve_autonomy` (amendment.py); workflow.py imports
  nothing.
- `commands/init/session.py` — unchanged imports (`..config`, `..plugin`, `goga.onboarding`).
- root `reg_hooks.py` — `from .statuses import ...`, `from .autonomous import amend_workflow`,
  `from .commands.init import amend_pybuggy_config, declare_pybuggy_session`.

Design (implementation) order: statuses → config → autonomous → commands/init edits → root —
each level's imports exist before the consumer.

## Code Stack Trace

### Trace: `register_hooks(hooks)`

#### Chain
1. **Input**: the goga platform imports `register_hooks` from the package root
   (`goga_tool_pybuggy/__init__.py` re-exports it from `reg_hooks.py`) when a command first
   reaches a hook checkpoint, or on `goga hooks`. `hooks` — the subscription surface.
2. **Step**: five literal `hooks.subscribe(domain, action, name, callable)` calls in platform
   order: statuses/automate, statuses/fix, onboarding/declare, onboarding/amend,
   pipeline/autonomy → checkpoint: addresses match the action catalogs of `goga-hooks`,
   `goga-onboarding-hooks`, `goga-pipeline-hooks` ✓; hook names unique per address ✓.
3. **Step**: wrong address / empty name / repeated name → the platform warns and skips that one
   registration (the routine never defends against it) → checkpoint: failure behavior owned by
   the platform per `goga-hooks` ✓.
4. **Output**: None. The five handlers are reachable by the platform through its registry.

#### Checkpoint Summary
- Address/name table vs the three usage files: passed.
- Handlers receive `context` by name (all five declare exactly `(context: object)`;
  `goga-pipeline-hooks` confirms values land by declared name): passed.

### Trace: `register_automate_statuses(context)`

#### Chain
1. **Input**: platform fires `statuses / register_statuses` and delivers `context` — the
   registration surface scoped to the tool (`register(name, filepath, after=, before=)`).
2. **Step**: six literal `context.register` calls in the normative table order (done →
   coding-planned → code-designed → arch-prepared → testcases-designed → requirements-created),
   each anchored `after` its built-in twin, the middle five additionally `before` the previously
   registered qualified automate status → checkpoint: every anchor names an entry registered
   earlier in this run or a built-in status ✓ (chain property verified by the order).
3. **Step**: an unresolvable anchor is skipped with a platform warning — the routine never
   guards, wraps, or logs → checkpoint: matches `goga-statuses` skip-with-warning ✓.
4. **Output**: None. The platform stores the statuses qualified `pybuggy.<name>`.

#### Checkpoint Summary
- Registration table vs `goga-statuses` member contract: passed (identical to the deleted
  statuses.py behavior — pure relocation, zero semantic drift).
- Registered names carry no tool prefix; anchors follow the table exactly (own-status anchors
  qualified `pybuggy.automate.*` / `pybuggy.fix.*`): passed.

### Trace: `register_fix_statuses(context)`

#### Chain
1. **Input**: same address, hook name `fix`.
2. **Step**: five literal `context.register` calls in pipeline order (collected → analyzed →
   planned → executed → reviewed), each `after` the previous qualified fix status, the first
   anchored at the built-in `empty` → checkpoint: independent chain, no shared statuses with the
   automate line ✓.
3. **Output**: None.

#### Checkpoint Summary
- Anchor chain closure: passed. Normative table vs CODEMANIFEST: passed.

### Trace: `load_config()`

#### Chain
1. **Input**: a command handler (pull/list/info/generate/diff) calls `load_config()` with no
   arguments. No filesystem state is touched before the facade read.
2. **Step**: call-time import `from goga.config import load_tool_config` inside the function
   body → checkpoint: goga is a test-extra only dependency; the import resolves at call time in
   the goga-bearing consumer environment ✓; the late import is also the test seam (monkeypatch
   `goga.config.load_tool_config`) ✓.
3. **Step**: `raw = load_tool_config("pybuggy", "config.yml")` → checkpoint: the platform
   composes `<root>/.goga/tools/pybuggy/config.yml` and returns the raw parse or `None` for an
   absent (or empty) file ✓ (`goga-tool-config`).
4. **Step**: `raw is None` → raise `FileNotFoundError` whose message names
   `.goga/tools/pybuggy/config.yml` → checkpoint: "clean error naming the tool config location"
   ✓ **[decision]** — `FileNotFoundError` preserves the previously declared Raises behavior of
   the routine and keeps the cell free of a click dependency; message text:
   `"tool config not found: .goga/tools/pybuggy/config.yml"`.
5. **Step**: `return Config.model_validate(raw)` → checkpoint: a non-mapping raw raises pydantic
   `ValidationError` (clean, typed); a mapping without `specs` fails (required); extra keys —
   the scalar plugin keys and the `pipelines` axis — are ignored (pydantic default
   `extra="ignore"`, verified in config.py) ✓.
6. **Output**: the validated `Config`.

#### Checkpoint Summary
- Facade contract (absence → None → clean typed error): passed.
- `pipelines` section co-existence with the `Config(specs)` schema: passed (extra=ignore,
  verified against the live model).

### Trace: `PipelineAutonomy` (constructor/validator)

#### Chain
1. **Input**: `PipelineAutonomy.model_validate({"autonomous": true})` — called by
   `resolve_autonomy` for every axis entry.
2. **Step**: pydantic validates the single required bool field `autonomous`; `model_config =
   ConfigDict(kw_only=True, extra="forbid")` → checkpoint: `{}` fails (member required);
   `{"autonomous": true, "typo": 1}` fails (extra forbidden — "a mistyped key must surface") ✓;
   `{"autonomous": "maybe"}` fails (a non-coercible value) ✓. Note: pydantic v2 lax bool
   coercion accepts the truthy spellings (`"yes"`, `"on"`, `"1"`, `1`) as True — acceptable,
   because the record's strictness requirement is the member set (extra=forbid), not the value
   spelling.
3. **Output**: the typed record; property `autonomous -> bool`.

#### Checkpoint Summary
- Record strictness vs the CODEMANIFEST Requirements: passed.

### Trace: `resolve_autonomy(pipeline)`

#### Chain
1. **Input**: `amend_workflow` passes `context.pipeline` (str, e.g. `"api.automate"`).
2. **Step**: call-time `load_tool_config("pybuggy", "config.yml")` → checkpoint: fresh raw parse
   every call — the platform does no caching and the routine must not add any ✓.
3. **Step**: `raw is None` (absent or empty file) → return False → checkpoint: "absent file …
   mean[s] disabled" ✓.
4. **Step**: `not isinstance(raw, dict)` (a present file parsing to a string/list) → raise the
   clean structural error → checkpoint: the D2 fix names this case; message names pybuggy ✓
   **[decision]** — the error is `ValueError` starting with `"pybuggy tool config:"` so both the
   hook context (platform clean stop) and direct library use surface it cleanly.
5. **Step**: `axis = raw.get("pipelines")`; `axis is None` → return False → checkpoint: absent
   section = disabled ✓.
6. **Step**: `not isinstance(axis, dict)` → same clean structural error → checkpoint:
   "non-mapping pipelines value" ✓.
7. **Step**: validate **every** entry: `PipelineAutonomy.model_validate(entry)` per name; a
   failure (non-mapping entry, extra key, non-bool) is re-raised as the clean `ValueError`
   naming pybuggy and the offending entry name, chaining the pydantic detail → checkpoint:
   "validating the whole … axis on the way" ✓; the pydantic message alone would not name pybuggy,
   the wrap supplies it ✓.
8. **Step**: look up `pipeline` in the validated mapping: absent → False; present →
   `bool(record.autonomous)` → checkpoint: unknown names never fail (they were validated
   structurally but do not affect the result) ✓; `autonomous: false` → False ✓.
9. **Output**: `enabled: bool`.

#### Checkpoint Summary
- All four disabled-states and all four violation classes traced against the Requirements:
  passed (after the D2 fix).
- No interpretation of sections other than `pipelines`: passed (single `.get`).

### Trace: `amend_workflow(context)`

#### Chain
1. **Input**: the platform fires `pipeline / amend_workflow` (hard error class) after workflow
   resolution and the runner-skip merge, before compilation — in the run form and the card form
   alike; delivers the `WorkflowAmendment` view (`pipeline`, `decision`, `workflow`, `work`;
   method `contribute(document)`).
2. **Step**: `pipeline = context.pipeline` → checkpoint: read-only view read ✓.
3. **Step**: `pipeline != "api.automate"` → return — silent no-op → checkpoint (the D1 fix):
   prevents contributing the api.automate-shaped window into any other pipeline even when its
   axis entry is enabled ✓; acceptance criterion restored ✓.
4. **Step**: `enabled = resolve_autonomy(pipeline)` → checkpoint: str in, bool out ✓; any error
   propagates — the routine never catches (Constraints: "autonomy never disables silently") ✓.
5. **Step**: `not enabled` → return — silent no-op → checkpoint: "contributes nothing and raises
   nothing" ✓.
6. **Step**: `context.contribute(build_autonomous_workflow())` → checkpoint: one declarative
   WorkflowDocument-shaped dict buffered; a repeat call replaces the tool's buffer whole
   (platform semantics) ✓; the tool's contribution commits only after the hook returns without
   raising ✓.
7. **Output**: None. A raised error stops the command with a clean error naming pybuggy and the
   whole contribution is discarded (platform behavior, hard action).

#### Checkpoint Summary
- View contract vs `goga-pipeline-hooks`: passed.
- Gate/resolver/contribute ordering: passed (after the D1 fix).

### Trace: `build_autonomous_workflow()`

#### Chain
1. **Input**: none — reads only module-level compile-time constants.
2. **Step**: build `stages` — the seven fixed window names in pipeline order
   (`review-testcases`, `create-testcases`, `code-design`, `design-review`, `coding-plan`,
   `plan-review`, `commit-changes`), each mapping exactly `{"approve": "auto"}` → checkpoint:
   every name exists in `pipelines/api.automate.yml` (verified against the pipeline file) ✓;
   `approve` is a legal per-stage override key with a legal value ✓ (`goga-workflow-document`).
3. **Step**: build `extend` — the single entry `build`: `after: ["commit-changes"]` plus the body
   keys `title: "Build tests"`,
   `script: 'python3 -P -m goga.build "$(python3 -m goga history path -f plan.md)"'` (verbatim
   from the ADR), `after_script: "rm -rf .ralphex"`, `timeout: "8h"` → checkpoint:
   positioning key present (`after`, list[str]) ✓; body keys are verbatim stage content ✓;
   `timeout` requires `script` — present ✓; `script` is mutually exclusive with `prompt`/`skills`
   — the body carries neither ✓; `manual`/`notes`/`reflect`/`memory` are forbidden in an
   extend-entry — none present ✓.
4. **Step**: return `{"stages": {...}, "extend": {...}}` → checkpoint: top-level keys are a
   subset of the accepted `prompt`/`stages`/`extend`/`memory` ✓; deterministic and pure — no
   platform calls, no I/O, identical output on every call ✓.
5. **Output**: `document: dict[str, object]` — the contribution.

#### Checkpoint Summary
- Document vocabulary vs `goga-workflow-document`: passed.
- Compiled effects (traced via `goga-compile-flow`, documented for the implementation agent):
  for the six window stages carrying `communication: true`, `approve: "auto"` suppresses the
  `interactive: true` emission (the runner-level interaction suppression the ADR wants);
  `auto_approve: true` is *not* emitted anywhere — the pipeline stages carry no `roles`, and the
  default `["auto"]` contains no `planner`. `create-testcases` has no `communication` — the
  directive is a harmless no-op there, kept for uniformity. `accept-result` is untouched — it
  keeps `communication: true` and `trigger: manual` in the compiled flow. The `build` extend body
  compiles to `script`/`script_after`/`script_timeout` with **no `agents` key** (a body carrying
  `script` emits none — afm rejects the combination).

### Trace: `pybuggy_questions()`

#### Chain
1. **Input**: none. Called by `declare_pybuggy_session` during the declaration moment (invited
   sessions only).
2. **Step**: the current block is built unchanged — `base_url` input, one input per scalar
   `PluginConfigKeys` member (except BASE_URL/HEADERS/LOADER), the `first_spec` group.
3. **Step**: append the autonomy confirm as the last item:
   `Question(id="autonomous", kind="confirm", prompt="Run the api.automate pipeline unattended (autonomous mode)?", default=False)`
   → checkpoint: kind `confirm` yields a bool answer recorded on every survey ✓
   (`goga-onboarding-questions`); asked last ✓; a simple child at top level — the block still
   holds exactly one nesting level ✓; no id collision with the plugin scalar keys ✓.
4. **Output**: `items: list[Question]` — records fresh per call.

#### Checkpoint Summary
- Record shape and nesting vs `goga-onboarding-questions`: passed.
- **[decision]** — the exact prompt text above (the contract fixes semantics — boolean, default
  disabled, "whether the api.automate pipeline runs unattended" — not the wording).

### Trace: `build_config_data(answers, extra_specs)`

#### Chain
1. **Input**: the tool answer view (`amend_pybuggy_config` reads `context.answers`) and the
   surveyed extra specs (or None).
2. **Step**: `parse_specs(answers.get("first_spec") or {}, extra_specs)` — unchanged → the typed
   specs mapping.
3. **Step**: collect the answered scalar keys in `PluginConfigKeys` order, dropping
   `None`/`""`, coercing the numeric members — unchanged.
4. **Step**: `if answers.get("autonomous"):` → `data["pipelines"] = {"api.automate": {"autonomous": True}}`
   → checkpoint: a falsy answer (False — the confirm default — or None when the question somehow
   did not run) emits nothing ✓ ("existing projects stay untouched until the user opts in");
   the entry shape equals the `resolve_autonomy` consumption shape exactly ✓ (bridge verified
   end to end: emit → engine YAML → raw parse → axis validation).
5. **Step**: `data["specs"] = {name: entry.model_dump(exclude_none=True) ...}` placed last;
   return `data` → checkpoint: plain serializable data only ✓; `Config.model_validate` on the
   written file ignores `pipelines` ✓ (traced in `load_config`).
6. **Output**: `data: dict[str, object]` — the tool-config payload.

#### Checkpoint Summary
- Axis emit/ consume shape symmetry: passed.
- Payload ordering **[decision]**: scalar keys, then `pipelines` (when enabled), then `specs`
  last — preserves the established "specs last" convention that `document_config_examples` anchors
  on; the plugin-member comment walk is unaffected by the extra non-plugin key.

### Trace: `register_hooks` consumers (facade import)

#### Chain
1. **Input**: `python -c "from goga_tool_pybuggy import register_hooks"` (the platform import
   point; the acceptance checklist item).
2. **Step**: `goga_tool_pybuggy/__init__.py` executes `from .reg_hooks import register_hooks`;
   reg_hooks imports `.statuses`, `.autonomous`, `.commands.init` → checkpoint: all target
   modules exist after implementation; relative imports only ✓; `register_hooks` listed in
   `__all__` ✓.
3. **Output**: the callable resolves; the current working-tree state (import of the deleted
   `statuses` module) is repaired by this implementation.

## Algorithm Design

### `register_hooks` (reg_hooks.py)

**Responsibility**: the single subscription point of the package — five hooks on four addresses,
declared from one module at the package root.

**Algorithm:**
```
1. subscribe("statuses", "register_statuses", "automate", register_automate_statuses)
   → platform registers the automate-line hook
2. subscribe("statuses", "register_statuses", "fix", register_fix_statuses)
3. subscribe("onboarding", "declare_session", "declare", declare_pybuggy_session)
4. subscribe("onboarding", "amend_config", "amend", amend_pybuggy_config)
5. subscribe("pipeline", "amend_workflow", "autonomy", amend_workflow)
```

**Errors**: none raised here; malformed subscriptions are platform-side warnings (skip-and-
continue). **Edge Cases**: none — a pure declaration table.

### `register_automate_statuses` (statuses/automate.py)

**Responsibility**: place the six automate-line statuses on the topic status scale.

**Algorithm:**
```
1. context.register("automate.done", "completed/plan.md", after="done")
2. context.register("automate.coding-planned", "plan.md", after="planned",
                    before="pybuggy.automate.done")
3. context.register("automate.code-designed", "design.md", after="specified",
                    before="pybuggy.automate.coding-planned")
4. context.register("automate.arch-prepared", "arch.md", after="designed",
                    before="pybuggy.automate.code-designed")
5. context.register("automate.testcases-designed", "testcases.md", after="backlog",
                    before="pybuggy.automate.arch-prepared")
6. context.register("automate.requirements-created", "requirements.md", after="defined",
                    before="pybuggy.automate.testcases-designed")
```

**Errors**: none raised; unresolvable anchors are platform-side skip-with-warning.
**Edge Cases**: partial registration is legitimate (independent skip per call).

### `register_fix_statuses` (statuses/fix.py)

**Responsibility**: place the five fix-line statuses — an independent chain anchored at `empty`.

**Algorithm:**
```
1. context.register("fix.collected", "fix-collect.md", after="empty")
2. context.register("fix.analyzed", "fix-analysis.md", after="pybuggy.fix.collected")
3. context.register("fix.planned", "fix-plan.md", after="pybuggy.fix.analyzed")
4. context.register("fix.executed", "fix-execute.md", after="pybuggy.fix.planned")
5. context.register("fix.reviewed", "fix-review.md", after="pybuggy.fix.executed")
```

**Errors / Edge Cases**: same platform-side semantics as the automate line.

### `load_config` (config/storage.py)

**Responsibility**: read the tool config through the platform facade and validate it into
`Config`.

**Algorithm:**
```
1. from goga.config import load_tool_config          # call-time import
2. raw = load_tool_config("pybuggy", "config.yml")   # module constants _TOOL / _FILENAME
3. IF raw is None:
   - raise FileNotFoundError("tool config not found: .goga/tools/pybuggy/config.yml")
4. return Config.model_validate(raw)
```

**Errors**: `FileNotFoundError` (absent/empty file, message names the location) → the calling
command surfaces it; pydantic `ValidationError` (non-mapping root, missing `specs`, malformed
entries) → propagated as-is; `yaml.YAMLError` / `OSError` from the facade → propagated raw.
**Edge Cases**: an empty file parses to `None` → the absent-file branch (same clean error); a
config carrying `pipelines` validates unchanged (extra=ignore).

### `PipelineAutonomy` (config/pipeline_autonomy.py)

**Responsibility**: the typed record of one `pipelines`-axis entry.

**Algorithm:**
```
1. class PipelineAutonomy(BaseModel):
     model_config = ConfigDict(kw_only=True, extra="forbid")
     autonomous: bool
```

**Errors**: `ValidationError` on a missing member, an extra key, or a non-bool value.
**Edge Cases**: none — the strictness *is* the contract (a mistyped key must surface).

### `resolve_autonomy` (config/storage.py)

**Responsibility**: resolve the autonomy flag for a pipeline name, validating the whole axis.

**Algorithm:**
```
1. from goga.config import load_tool_config          # call-time import
2. raw = load_tool_config("pybuggy", "config.yml")
3. IF raw is None: return False                      # absent/empty file
4. IF not isinstance(raw, dict):
   - raise ValueError("pybuggy tool config: the file must parse to a mapping")
5. axis = raw.get("pipelines")
6. IF axis is None: return False                     # absent section
7. IF not isinstance(axis, dict):
   - raise ValueError("pybuggy tool config: pipelines must be a mapping")
8. records = {}
   FOR name, entry IN axis.items():
     - records[name] = PipelineAutonomy.model_validate(entry)
       ON ValidationError: raise ValueError(
           f"pybuggy tool config: invalid pipelines entry {name!r}") from err
9. IF pipeline not in records: return False
10. return records[pipeline].autonomous
```

**Errors**: the three `ValueError`s above — each message starts with "pybuggy tool config:" so
the failure names the tool in every context (platform clean stop or direct library use).
**Edge Cases**: unknown pipeline names are validated but never fail the call; no caching — every
call re-reads (a changed file is visible immediately).

### `amend_workflow` (autonomous/amendment.py)

**Responsibility**: the autonomy contribution moment — gate, resolve, contribute.

**Algorithm:**
```
1. pipeline = context.pipeline
2. IF pipeline != _PIPELINE ("api.automate"): return      # silent no-op
3. enabled = resolve_autonomy(pipeline)
4. IF not enabled: return                                  # silent no-op
5. context.contribute(build_autonomous_workflow())
```

**Errors**: anything raised by steps 3 or 5 propagates — no try/except anywhere in the module
(the Constraints forbid error-catching: autonomy never disables silently).
**Edge Cases**: a repeat `contribute` replaces the tool's buffer whole (platform semantics — a
single document per tool is correct).

### `build_autonomous_workflow` (autonomous/workflow.py)

**Responsibility**: the pure builder of the contribution from compile-time constants.

**Constants:**
```python
_PIPELINE = "api.automate"                      # lives in amendment.py
_WINDOW_STAGES = (
    "review-testcases", "create-testcases", "code-design", "design-review",
    "coding-plan", "plan-review", "commit-changes",
)
_BUILD_NAME = "build"
_BUILD_TITLE = "Build tests"
_BUILD_SCRIPT = 'python3 -P -m goga.build "$(python3 -m goga history path -f plan.md)"'
_BUILD_AFTER_SCRIPT = "rm -rf .ralphex"
_BUILD_TIMEOUT = "8h"                           # Go duration grammar, verbatim
_BUILD_AFTER = ("commit-changes",)
```

**Algorithm:**
```
1. stages = {name: {"approve": "auto"} for name in _WINDOW_STAGES}
2. extend = {_BUILD_NAME: {
       "after": list(_BUILD_AFTER),
       "title": _BUILD_TITLE,
       "script": _BUILD_SCRIPT,
       "after_script": _BUILD_AFTER_SCRIPT,
       "timeout": _BUILD_TIMEOUT,
   }}
3. return {"stages": stages, "extend": extend}
```

**Errors**: none possible — pure construction.
**Edge Cases**: deterministic — byte-identical output on every call (a test asserts it).

### `pybuggy_questions` (commands/init/session.py — changed tail)

**Algorithm (added step):**
```
4. items.append(Question(
       id="autonomous", kind="confirm", default=False,
       prompt="Run the api.automate pipeline unattended (autonomous mode)?"))
```

### `build_config_data` (commands/init/session.py — changed middle)

**Algorithm (added step, between scalar collection and the specs assignment):**
```
3. IF answers.get("autonomous"):
   - data["pipelines"] = {"api.automate": {"autonomous": True}}
```

## Cross-cutting Concerns

- **Error handling**: three zones. (1) statuses cell: no error handling at all — registration
  failures are platform-side skip-with-warning. (2) config cell: clean typed errors at the
  boundary — `FileNotFoundError` naming the location for `load_config`; `ValueError` messages
  prefixed `"pybuggy tool config:"` for every `resolve_autonomy` structural violation; pydantic
  and facade errors propagate raw. (3) autonomous cell: zero catching — any error is fatal-but-
  clean (the platform's hard action stops the command naming pybuggy and discards the
  contribution). The init contribution keeps its soft-drop-at-the-mediator semantics (engine-
  owned, unchanged).
- **Logging**: no new log statements. The contracts demand silent no-op branches ("contributes
  nothing and raises nothing") and pure builders; the skip/warn behaviors that do log belong to
  the platform, not the tool. Where the implementation touches existing logging (none of the
  changed routines), `logging` with structured `extra=` per `conventions` applies.
- **Validation**: `PipelineAutonomy` is the single strictness point (kw_only, extra=forbid, bool
  member); `Config` stays permissive (extra=ignore) so the axis and the scalar plugin keys
  co-exist with the specs schema; the axis is validated *whole* on every `resolve_autonomy` call.
- **Caching**: none, anywhere in the new paths — `load_tool_config` is uncached by contract and
  the routines add no layer; each `resolve_autonomy` call performs a fresh read.
- **Concurrency**: not applicable — single-threaded CLI/hook flows; no shared mutable state
  beyond the platform's own buffers.

## Usages Analysis

### `conventions` (all five cells)
- **What it provides**: the mandatory Python rules — relative intra-package imports, pydantic
  kw_only models, Google docstrings, structured logging, the test-tree mirroring standard.
- **Where used**: every entity and every test of this design.
- **Why chosen**: the project-wide code standard.
- **How exactly**: kw_only on `PipelineAutonomy`; relative imports in all new modules
  (`from ..config import resolve_autonomy`); test files at `tests/<package>/test_<module>.py`.

### `goga-statuses` (statuses cell)
- **What it provides**: the `statuses / register_statuses` member contract — `register(name,
  filepath, after=, before=)`, qualified storage, add-only, skip-with-warning.
- **Where used**: `register_automate_statuses`, `register_fix_statuses`.
- **Why chosen**: the registration surface the two routines call.
- **How exactly**: literal `context.register(...)` calls with bare names and table-exact anchors.

### `goga-tool-config` (config cell)
- **What it provides**: `load_tool_config(tool, filename, root=None)` — the raw parse or `None`,
  the fixed `.goga/tools/<tool>/<filename>` standard, no caching, no interpretation.
- **Where used**: `load_config`, `resolve_autonomy`.
- **Why chosen**: the platform facade is the task's user-amendment — one read path, platform-
  owned location.
- **How exactly**: call-time `from goga.config import load_tool_config`;
  `load_tool_config("pybuggy", "config.yml")`; `None` handled per routine.

### `goga-pipeline-hooks` (autonomous cell)
- **What it provides**: the `pipeline / amend_workflow` event — firing time, hard error class,
  the `WorkflowAmendment` view reads and `contribute`, merge precedence, failure behavior.
- **Where used**: `amend_workflow`.
- **Why chosen**: the subscription and view contract of the contribution moment.
- **How exactly**: read `context.pipeline`; single `context.contribute(document)`; no catching.

### `goga-workflow-document` (autonomous cell)
- **What it provides**: the WorkflowDocument vocabulary — per-stage override keys (`approve`),
  extend-entry keys (`before`/`after`, extracted inline overrides, verbatim body), forbidden
  extend-entry keys.
- **Where used**: `build_autonomous_workflow`.
- **Why chosen**: the contribution must speak the authored-workflow instruction vocabulary.
- **How exactly**: `{"approve": "auto"}` per window stage; the extend entry carries `after` +
  title/script/after_script/timeout body keys only.

### `goga-compile-flow` (autonomous cell)
- **What it provides**: the compiled effects — approve→(interactive suppression, auto_approve
  emission rules), script directive translation, timeout→script_timeout, the no-agents-with-script
  rule.
- **Where used**: `build_autonomous_workflow` (effects verification), this document's trace.
- **Why chosen**: the design must prove the contribution compiles to the intended flow shape.
- **How exactly**: the effects table in the `build_autonomous_workflow` trace.

### Imported Usages
- `autonomy` from `goga_tool_pybuggy/config` — the axis contract and the resolver consumption
  pattern; the bridge document between the config cell and its autonomy consumers.
  Path: `goga_tool_pybuggy/config/.usages/autonomy.md`. Consumed by: `amend_workflow`
  (annotation), `build_config_data` + `pybuggy_questions` (annotations, init cell).
- `registration` from `goga_tool_pybuggy/statuses` — the status subscription pattern for the
  root's two statuses subscriptions. Path: `goga_tool_pybuggy/statuses/.usages/registration.md`.
  Consumed by: root `register_hooks` annotation.
- `contribution` from `goga_tool_pybuggy/autonomous` — the autonomy subscription pattern for the
  root's fifth subscription. Path: `goga_tool_pybuggy/autonomous/.usages/contribution.md`.
  Consumed by: root `register_hooks` annotation.
- `configuration` from `goga_tool_pybuggy/config` (init cell, unchanged edge) — schema
  compatibility of the payload.

## `.usages/` Update

All `.usages` files were created/updated by the apply-architecture stage; this design verified
them against the (post-fix) CODEMANIFESTs. One file was amended by this stage (D2 mirror).

### Cell: `goga_tool_pybuggy/statuses`
- **`registration.md`** → current. Describes both routines, the subscribe pattern (matching the
  root table), the normative-order and skip-with-warning preconditions. No additions needed.

### Cell: `goga_tool_pybuggy/config`
- **`configuration.md`** → current. The no-argument `load_config()` example, the facade read,
  the absent-file semantics — matches the post-change contract.
- **`autonomy.md`** → current (updated by this stage: "a non-mapping file root" added to the
  structural-violation list, mirroring the D2 CODEMANIFEST fix). Describes the axis shape, the
  resolver call, the failure semantics.

### Cell: `goga_tool_pybuggy/autonomous`
- **`contribution.md`** → current. Describes both entities, the subscribe pattern, the no-op and
  precedence preconditions. Matches the five-step algorithm (the gate is stated as "a silent
  no-op for every other pipeline").

### Cell: `goga_tool_pybuggy/commands/init`
- **`config-build.md`** → current. Documents the `autonomous` question (asked last, default no)
  and the conditional axis entry. No additions needed.

### Cell: `goga_tool_pybuggy` (root)
- **`assembly.md`** → current. The five-hook table (including `autonomy` → `pipeline /
  amend_workflow`), the callable locations, the no-op semantics. No additions needed.

## Test Stack Trace

Test tree per `conventions` (mirror the source; `__init__.py` in every new test directory):

```
tests/
├── test_reg_hooks.py                     (replaces tests/test_statuses.py)
├── statuses/__init__.py, test_automate.py, test_fix.py
├── autonomous/__init__.py, test_amendment.py, test_workflow.py
├── config/test_PipelineAutonomy.py       (new)
├── config/test_storage.py                (rewritten: no-arg load_config + resolve_autonomy)
├── commands/init/test_session.py         (extended: autonomy question + axis emission)
└── seam migration (8 files — every test file that patches CONFIG_PATH):
    test_cli_integration.py, test_cli_env.py, commands/pull/test_pull.py,
    commands/diff/test_diff.py, commands/diff/test_diff_integration.py,
    commands/info/test_info.py, commands/list/test_list.py,
    commands/generate/test_generate.py
```

### General Setup

Recorder doubles (no mocks of business logic; platform boundaries only):

```python
class _RecorderHooks:                    # subscription surface
    calls: list[tuple[str, str, str, object]]
    def subscribe(self, domain, action, name, hook): self.calls.append((domain, action, name, hook))

class _RecorderContext:                  # status registration surface
    calls: list[tuple[str, str, str | None, str | None]]
    def register(self, name, artifact, after=None, before=None): self.calls.append(...)

class _AmendmentView:                    # WorkflowAmendment double
    def __init__(self, pipeline): self.pipeline, self.contributed = pipeline, []
    def contribute(self, document): self.contributed.append(document)
```

The config seam fixture (replaces every `CONFIG_PATH` monkeypatch):

```python
@pytest.fixture
def tool_config(tmp_path, monkeypatch):          # writes the standard tree under a chdir'd root
    monkeypatch.chdir(tmp_path)
    def _write(text: str) -> None:
        path = tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return _write
```

`load_tool_config` composes `<cwd>/.goga/tools/pybuggy/config.yml` when `root` is None, so a
chdir'd prepared tree exercises the real path composition with zero patching; the CLI tests use
`runner.isolated_filesystem()` and write the same standard relative path. (The platform `root`
override remains available for direct `load_tool_config` unit use; pybuggy's own tests do not
need it.)

### Source File Registry

`goga_tool_pybuggy/reg_hooks.py`; `goga_tool_pybuggy/statuses/{__init__,automate,fix}.py`;
`goga_tool_pybuggy/config/{storage,pipeline_autonomy,__init__}.py`;
`goga_tool_pybuggy/autonomous/{amendment,workflow,__init__}.py`;
`goga_tool_pybuggy/commands/init/session.py`; `goga_tool_pybuggy/__init__.py`.

---

### Positive Tests

#### `test_register_hooks_subscribes_five_hooks`

**Setup**: import `register_hooks` from `goga_tool_pybuggy`; a `_RecorderHooks`; the cell
objects `register_automate_statuses`, `register_fix_statuses` (statuses),
`declare_pybuggy_session`, `amend_pybuggy_config` (commands.init), `amend_workflow`
(autonomous).

**Input**: `register_hooks(recorder)`.

**Trace**:
```
register_hooks(recorder)
  → recorder.subscribe("statuses", "register_statuses", "automate", register_automate_statuses)
  → recorder.subscribe("statuses", "register_statuses", "fix", register_fix_statuses)
  → recorder.subscribe("onboarding", "declare_session", "declare", declare_pybuggy_session)
  → recorder.subscribe("onboarding", "amend_config", "amend", amend_pybuggy_config)
  → recorder.subscribe("pipeline", "amend_workflow", "autonomy", amend_workflow)
  → assert recorder.calls
```

**Assertions**:
```
recorder.calls == [
    ("statuses", "register_statuses", "automate", register_automate_statuses),
    ("statuses", "register_statuses", "fix", register_fix_statuses),
    ("onboarding", "declare_session", "declare", declare_pybuggy_session),
    ("onboarding", "amend_config", "amend", amend_pybuggy_config),
    ("pipeline", "amend_workflow", "autonomy", amend_workflow),
]
# and each callable is the cell object by identity (calls[i][3] is <cell object>)
```

**Sufficiency**: the fifth subscription is the feature's entry into the platform; this test
prevents any future reordering, renaming, or dropping of the subscription table (the regression
the old four-hook test guarded, extended).

#### `test_register_automate_statuses_registers_six_statuses_in_order`

**Setup**: `_RecorderContext`.

**Input**: `register_automate_statuses(context)`.

**Trace**:
```
register_automate_statuses(context)
  → context.register("automate.done", "completed/plan.md", after="done")
  → context.register("automate.coding-planned", "plan.md", after="planned",
                     before="pybuggy.automate.done")
  → … (four more, table order)
  → assert context.calls
```

**Assertions**:
```
context.calls == [
    ("automate.done", "completed/plan.md", "done", None),
    ("automate.coding-planned", "plan.md", "planned", "pybuggy.automate.done"),
    ("automate.code-designed", "design.md", "specified", "pybuggy.automate.coding-planned"),
    ("automate.arch-prepared", "arch.md", "designed", "pybuggy.automate.code-designed"),
    ("automate.testcases-designed", "testcases.md", "backlog", "pybuggy.automate.arch-prepared"),
    ("automate.requirements-created", "requirements.md", "defined",
     "pybuggy.automate.testcases-designed"),
]
```

**Sufficiency**: the normative table is behavior, not documentation — order and anchors decide
the topic status scale; guards the relocation from statuses.py (the module was deleted).

#### `test_register_fix_statuses_registers_five_statuses_in_order`

**Setup/Input/Trace**: same shape with `register_fix_statuses`.

**Assertions**:
```
context.calls == [
    ("fix.collected", "fix-collect.md", "empty", None),
    ("fix.analyzed", "fix-analysis.md", "pybuggy.fix.collected", None),
    ("fix.planned", "fix-plan.md", "pybuggy.fix.analyzed", None),
    ("fix.executed", "fix-execute.md", "pybuggy.fix.planned", None),
    ("fix.reviewed", "fix-review.md", "pybuggy.fix.executed", None),
]
```

**Sufficiency**: the fix chain's anchor closure; prevents chain reordering.

#### `test_load_config_reads_standard_path`

**Setup**: `tool_config` fixture; text =
`"specs:\n  client:\n    type: openapi\n    location: specs/client.yaml\n"`.

**Input**: `load_config()`.

**Trace**:
```
load_config()
  → from goga.config import load_tool_config            # call-time
  → load_tool_config("pybuggy", "config.yml")           # <cwd>/.goga/tools/pybuggy/config.yml
    returns: {"specs": {"client": {"type": "openapi", "location": "specs/client.yaml"}}}
  → Config.model_validate(raw)
    returns: Config(specs={"client": SpecEntry(...)})
  → assert config.specs["client"].location
```

**Assertions**:
```
config.specs["client"].location == "specs/client.yaml"
config.specs["client"].type == "openapi"
config.specs["client"].git is None
inspect.signature(load_config).parameters == {}          # no-arg contract
```

**Sufficiency**: proves the facade migration reads the platform-standard location with no
parameters — the load path every command depends on.

#### `test_load_config_ignores_pipelines_section`

**Setup**: `tool_config`; text with a `specs` block **and**
`"pipelines:\n  api.automate:\n    autonomous: true\n"`.

**Input**: `load_config()`.

**Trace**: facade returns the mapping with both sections → `Config.model_validate` (extra=ignore)
→ returns Config.

**Assertions**: `config.specs` intact; no error raised.

**Sufficiency**: the axis and the specs schema must co-exist in one file — the onboarding writes
both; prevents an implementer from adding `extra="forbid"` to `Config`.

#### `test_resolve_autonomy_enabled_returns_true`

**Setup**: `tool_config`; text =
`"pipelines:\n  api.automate:\n    autonomous: true\n"`.

**Input**: `resolve_autonomy("api.automate")`.

**Trace**:
```
resolve_autonomy("api.automate")
  → load_tool_config("pybuggy", "config.yml")  returns: {"pipelines": {"api.automate": {"autonomous": True}}}
  → raw is a dict; axis = {"api.automate": {"autonomous": True}}
  → PipelineAutonomy.model_validate({"autonomous": True})  returns: record
  → "api.automate" in records
  → returns: record.autonomous
```

**Assertions**: `resolve_autonomy("api.automate") is True`.

**Sufficiency**: the single enabling path of the whole feature.

#### `test_amend_workflow_contributes_when_enabled`

**Setup**: `_AmendmentView("api.automate")`; `monkeypatch.setattr(
"goga_tool_pybuggy.autonomous.amendment.resolve_autonomy", lambda pipeline: True)`.

**Input**: `amend_workflow(view)`.

**Trace**:
```
amend_workflow(view)
  → pipeline = view.pipeline                     # "api.automate"
  → gate: pipeline == "api.automate" → continue
  → resolve_autonomy(pipeline)  returns: True    # stubbed
  → build_autonomous_workflow()  returns: document
  → view.contribute(document)
  → assert view.contributed
```

**Assertions**:
```
view.contributed == [build_autonomous_workflow()]      # exactly one document, equal by value
```

**Sufficiency**: the contribution path end to end (gate passed, resolver True, one buffered
document).

#### `test_amend_workflow_end_to_end_with_real_config`

**Setup**: `tool_config` (axis enabled, resolver **not** stubbed); `_AmendmentView("api.automate")`.

**Input**: `amend_workflow(view)`.

**Trace**: real `resolve_autonomy` reads the prepared tree → True → contribute.

**Assertions**: one document equal to the builder output.

**Sufficiency**: proves the two cells compose through the real file standard (integration).

#### `test_build_autonomous_workflow_document_shape`

**Setup**: none (pure).

**Input**: `build_autonomous_workflow()`.

**Trace**: constant construction → returns dict.

**Assertions**:
```
set(document) == {"stages", "extend"}
list(document["stages"]) == [
    "review-testcases", "create-testcases", "code-design", "design-review",
    "coding-plan", "plan-review", "commit-changes",
]
all(value == {"approve": "auto"} for value in document["stages"].values())
build = document["extend"]["build"]
build["after"] == ["commit-changes"]
build["title"] == "Build tests"
build["script"] == 'python3 -P -m goga.build "$(python3 -m goga history path -f plan.md)"'
build["after_script"] == "rm -rf .ralphex"
build["timeout"] == "8h"
"accept-result" not in document["stages"] and "accept-result" not in document["extend"]
set(build) == {"after", "title", "script", "after_script", "timeout"}   # no prompt/skills/
                                                                        # manual/notes/reflect/memory
```

**Sufficiency**: the compile-time constants are the feature's contract with the compiler — any
drift (a renamed stage, a lost timeout, a forbidden key) breaks the compiled run; this test pins
the exact ADR values.

#### `test_build_autonomous_workflow_deterministic`

**Input**: two calls. **Assertions**: `build_autonomous_workflow() ==
build_autonomous_workflow()` (deep equality). **Sufficiency**: purity — repeated amendment calls
must buffer identical documents.

#### `test_pipeline_autonomy_accepts_valid_record`

**Setup**: none. **Input**: `PipelineAutonomy.model_validate({"autonomous": True})`.
**Trace**: pydantic validates the single bool member. **Assertions**: `record.autonomous is
True`; `PipelineAutonomy(autonomous=False).autonomous is False`.
**Sufficiency**: the axis entry's happy path.

#### `test_pybuggy_questions_appends_autonomy_confirm_last`

**Setup**: none (pure); import `Question`, `QuestionGroup` from `goga.onboarding` for the shape
assertions.

**Input**: `pybuggy_questions()`.

**Trace**: block built → the confirm appended after the `first_spec` group.

**Assertions**:
```
last = items[-1]
isinstance(last, Question) and last.id == "autonomous" and last.kind == "confirm"
last.default is False
items[-2].id == "first_spec"                       # asked last, after the group
```

**Sufficiency**: the question is the feature's only user-facing opt-in; position and default are
contract ("asked last", "defaulting to disabled").

#### `test_build_config_data_emits_pipelines_axis_on_enabling_answer`

**Setup**: answers view =
`{"base_url": "https://api.example.com", "first_spec": {"name": "s", "type": "swagger",
"location": "specs/s.yaml"}, "autonomous": True}`; `extra_specs=None`.

**Input**: `build_config_data(answers, None)`.

**Trace**:
```
build_config_data(answers, None)
  → parse_specs(answers["first_spec"], None)  returns: {"s": SpecEntry(...)}
  → scalar walk: base_url answered → data["base_url"] = "https://api.example.com"
  → answers.get("autonomous") is True → data["pipelines"] = {"api.automate": {"autonomous": True}}
  → data["specs"] = {"s": {...}}
  → assert data
```

**Assertions**:
```
data["pipelines"] == {"api.automate": {"autonomous": True}}
list(data)[-1] == "specs"                          # specs stay last
yaml.safe_load(yaml.safe_dump(data)) == data       # plain serializable
```

**Sufficiency**: the emit side of the axis bridge — prevents shape drift against
`resolve_autonomy`.

---

### Negative Tests

#### `test_load_config_absent_file_raises_naming_location` (parametrized: no file / empty file)

**Setup**: `tool_config` fixture; row "no file" writes nothing (empty chdir'd tree), row
"empty file" writes `""` to the standard path.

**Input**: `load_config()`.

**Trace**: facade returns `None` — absent by the existence check, empty by the raw parse
(`yaml.safe_load("")` → None) → the absent-file branch raises.

**Assertions** (both rows):
```
with pytest.raises(FileNotFoundError, match=r"\.goga/tools/pybuggy/config\.yml"):
    load_config()
```

**Sufficiency**: the clean-error contract for the normal absent state (an uninitialized
project) and for the empty-file boundary declared in the algorithm's Edge Cases; the match
pins the "naming the tool config location" requirement.

#### `test_resolve_autonomy_structural_violations_parametrized`

**Setup**: `tool_config` with the file content per row.

**Input** (parametrized):
```
content                                            | call
---------------------------------------------------|------------------------------
"just a string\n"                                  | resolve_autonomy("api.automate")
"specs: {}\npipelines:\n  - a\n  - b\n"            | resolve_autonomy("api.automate")
"pipelines:\n  api.automate: plain-string\n"        | resolve_autonomy("api.automate")
"pipelines:\n  api.automate:\n    autonomous: maybe\n"| resolve_autonomy("api.automate")
"pipelines:\n  api.automate:\n    autonomous: true\n    typo: 1\n" | resolve_autonomy(...)
```

The non-bool row must use a **non-coercible** string: PyYAML (YAML 1.1) parses `yes`/`no`/`on`/
`off` to real booleans, so `autonomous: yes` is a *valid* enabling entry and never raises —
YAML-truthy spellings are deliberately absent from the violation matrix.

**Trace**: facade → raw parse → the violating isinstance/model_validate branch → `ValueError`.

**Assertions**:
```
with pytest.raises(ValueError, match="pybuggy tool config"):
    resolve_autonomy("api.automate")
```

**Sufficiency**: the fail-loud matrix — a typo must surface, never silently disable autonomy
(the ADR's loudest requirement); the message prefix proves the error names the tool.

#### `test_resolve_autonomy_propagates_facade_parse_error`

**Setup**: `tool_config` writes invalid YAML (`"pipelines: [unclosed"`).

**Input**: `resolve_autonomy("api.automate")`.

**Assertions**: `pytest.raises((yaml.YAMLError, ValueError))`.

**Sufficiency**: facade errors propagate raw — the routine adds no suppression.

#### `test_amend_workflow_no_op_for_other_pipeline_even_when_axis_enabled`

**Setup**: `monkeypatch.setattr("...amendment.resolve_autonomy", lambda pipeline: True)` — the
resolver returns True for *anything*, isolating the gate; `_AmendmentView("code.review")`.

**Input**: `amend_workflow(view)`.

**Trace**: `pipeline = "code.review"` → gate: `!= "api.automate"` → return.

**Assertions**: `view.contributed == []` and no exception.

**Sufficiency**: the D1 regression test — without the explicit gate, an axis entry for another
pipeline would contribute the api.automate window and fail at the compiler; this test fails on
exactly that implementation error.

#### `test_amend_workflow_errors_propagate_undamped`

**Setup**: resolver stub `lambda pipeline: (_ for _ in ()).throw(ValueError("pybuggy tool
config: boom"))`; `_AmendmentView("api.automate")`.

**Input**: `amend_workflow(view)`.

**Assertions**:
```
with pytest.raises(ValueError, match="pybuggy tool config: boom"):
    amend_workflow(view)
view.contributed == []
```

**Sufficiency**: the "never catch to force the no-op" constraint — autonomy never disables
silently.

#### `test_pipeline_autonomy_rejects_parametrized`

**Input** (parametrized): `{}`, `{"autonomous": True, "typo": 1}`,
`{"autonomous": "maybe"}`, `{"autonomous": None}` → `pytest.raises(pydantic.ValidationError)` on
`PipelineAutonomy.model_validate(...)`. The non-bool row uses a non-coercible string — pydantic
v2 lax mode coerces `"yes"`/`"on"`/`"1"` to True, so those spellings are not rejection cases.
Also `pytest.raises(TypeError)` on positional construction `PipelineAutonomy(True)` (kw_only).

**Sufficiency**: the record's strictness boundary (extra=forbid, bool typing, keyword-only).

#### `test_config_facade_no_longer_exports_config_path`

**Setup/Input**: `import goga_tool_pybuggy.config as cfg`.

**Assertions**:
```
"CONFIG_PATH" not in vars(cfg) and "CONFIG_PATH" not in cfg.__all__
sorted(cfg.__all__) == ["Config", "GitEntry", "PipelineAutonomy", "SpecEntry",
                        "load_config", "resolve_autonomy"]
```

**Sufficiency**: the delete commitment — the platform facade owns the location; a stale export
would resurrect the dead seam.

---

### Edge Case Tests

#### `test_resolve_autonomy_disabled_states_parametrized`

**Setup**: `tool_config` per row.

**Input** (parametrized — the four disabled states; five rows, the empty file sharing the
absent-file branch):
```
no file at all                                     | resolve_autonomy("api.automate") → False
"" (an empty file — the facade raw-parses it to None) | resolve_autonomy("api.automate") → False
"specs: {}\n"                                      | resolve_autonomy("api.automate") → False
"pipelines:\n  other.pipeline:\n    autonomous: true\n" | resolve_autonomy("api.automate") → False
"pipelines:\n  api.automate:\n    autonomous: false\n"  | resolve_autonomy("api.automate") → False
```

**Trace**: absent → None branch; an empty file → the same None branch; absent section →
`.get` None; absent name → lookup miss; explicit false → `record.autonomous` False.

**Assertions**: `result is False` for every row (and no exception).

**Sufficiency**: the acceptance criterion "autonomy off composes identically to a project
without the feature" — each of the four off-states is a distinct code branch.

#### `test_resolve_autonomy_no_caching`

**Setup**: `tool_config`; write `"pipelines:\n  api.automate:\n    autonomous: false\n"`;
call once; rewrite the file with `autonomous: true`; call again.

**Assertions**: first call `is False`, second call `is True`.

**Sufficiency**: the "do not cache the read" constraint — a stale read would ignore the user
flipping the flag between runs.

#### `test_resolve_autonomy_unknown_names_never_fail`

**Setup**: `tool_config` with a *valid* entry for `"code.review"` only.

**Input**: `resolve_autonomy("api.automate")`.

**Assertions**: returns False, no exception (a foreign-but-valid entry is not a violation).

**Sufficiency**: forward compatibility of the per-name axis.

#### `test_build_config_data_disabling_and_absent_answers_emit_no_axis`

**Setup**: two answer views — `"autonomous": False` and no `autonomous` key.

**Input**: `build_config_data(answers, None)` each.

**Assertions**: `"pipelines" not in data` in both; `data["specs"]` present.

**Sufficiency**: "the entry is absent on a disabling or absent answer — existing projects stay
untouched until the user opts in"; the default confirm answer (False) must not write the key.

#### `test_register_hooks_facade_and_signature`

**Setup/Input**: `from goga_tool_pybuggy import register_hooks`.

**Assertions**: `callable(register_hooks)`; `register_hooks.__annotations__ == {"hooks":
object, "return": None}`.

**Sufficiency**: the platform import point and the facade-callback signature (the checklist's
`python -c "from goga_tool_pybuggy import register_hooks"` probe, as a test).

#### Seam migration (existing files)

- Eight files carry the `CONFIG_PATH` seam (grep-verified — the complete set, not a sample):
  `tests/test_cli_integration.py`, `tests/test_cli_env.py`, `tests/commands/pull/test_pull.py`,
  `tests/commands/diff/test_diff.py`, `tests/commands/diff/test_diff_integration.py`,
  `tests/commands/info/test_info.py`, `tests/commands/list/test_list.py`,
  `tests/commands/generate/test_generate.py`.
- In every one of them: delete the `CONFIG_PATH_ATTR` constant and each
  `monkeypatch.setattr(CONFIG_PATH_ATTR, ...)` line, and write the config at the standard
  relative path `pathlib.Path(".goga/tools/pybuggy/config.yml")` (parent directories created)
  instead — each of these tests already runs `monkeypatch.chdir(tmp_path)` or
  `runner.isolated_filesystem()`, so the relative write lands under the test's own root and the
  real path composition is exercised. No other assertion changes — the commands' observable
  behavior is identical. A missed file fails loudly: `monkeypatch.setattr` on the deleted
  attribute raises `AttributeError`, so the `pytest tests/ -x` gate guards the completeness of
  this list.

**Sufficiency**: the tests keep exercising the real path composition (`.goga/tools/pybuggy/
config.yml` under cwd) instead of a patched module attribute; the migration is the checklist
item "the command test tree migrates the config seam" — which names the whole command test
tree (pull, diff, info, list, generate), not only the three files the first draft listed.

## Additional Instructions for the Implementation Agent

- Implement in this order: (1) `statuses/` package (`automate.py`, `fix.py`, `__init__.py`); (2)
  `config/` (`pipeline_autonomy.py` new, `storage.py` rewritten, `__init__.py` facade without
  `CONFIG_PATH`); (3) `autonomous/` (`workflow.py`, `amendment.py`, `__init__.py`); (4)
  `commands/init/session.py` tail edits; (5) root `reg_hooks.py` + `__init__.py` import switch;
  (6) tests (new tree + seam migration, delete `tests/test_statuses.py`); (7) docs sections
  (`docs/pipelines/api-automate.md` "Autonomous runs", `docs/cli/init.md`) — the task's non-cell
  follow-ups.
- `statuses/automate.py` and `statuses/fix.py` are literal relocations of the deleted
  `statuses.py` bodies (the register tables above are verbatim); only the module docstrings and
  imports change. Do not "improve" the tables.
- Every new module: Google docstrings, relative imports, `logging` only where a log is
  warranted (nowhere new, per Cross-cutting). `pyproject.toml` runtime dependencies do NOT
  change: `goga` stays test-extra only; `pyyaml` stays runtime (still used by
  `commands/init/init.py`).
- The call-time import pattern (`from goga.config import load_tool_config` inside the function
  body) is contract, not style — it keeps goga out of the runtime dependency graph and creates
  the test seam. Do not hoist it to module level.
- Facades: `statuses/__all__ = ["register_automate_statuses", "register_fix_statuses"]`;
  `autonomous/__all__ = ["amend_workflow", "build_autonomous_workflow"]`; config `__all__` per
  the negative facade test above; root `__init__.py` switches to
  `from .reg_hooks import register_hooks` (keep `__all__` unchanged).
- Acceptance gates: `goga lint` (19 cells, 0 errors), `pytest tests/ -x` green,
  `ruff check goga_tool_pybuggy/` clean, and `python -c "from goga_tool_pybuggy import
  register_hooks"` resolves. Re-verify the arch.md checklist items that concern source behavior
  (resolve_autonomy matrix, workflow vocabulary, five subscriptions, statuses.py absence,
  CONFIG_PATH removal + seam migration, question default/payload conditionality).
- Out of scope (do not touch): the pipeline file `pipelines/api.automate.yml`, the stage skills,
  `accept-result`, the goga platform itself, and the five command cells' CODEMANIFESTs (their
  `load_config()` call sites already match the narrowed signature).
