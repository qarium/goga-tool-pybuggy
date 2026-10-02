# Plan: `autonomous` — Autonomous runs of the `api.automate` pipeline

<!-- Topic: `.goga/history/2026/autonomous/` — compiled from `design.md` (post design-review,
     all four fixes applied) into a ralphex-executable task sequence. -->

## Purpose

Implement the `api.automate` autonomous-runs feature across the five changed cells: the new
`statuses` cell (relocated topic-status routines), the reworked `config` cell (platform-facade
read, `PipelineAutonomy`, `resolve_autonomy`), the new `autonomous` cell (the workflow
amendment contribution), the `commands/init` autonomy opt-in, and the root five-hook
`reg_hooks.py` subscription table — plus the test-tree rebuild (new per-cell suites, the
`CONFIG_PATH` seam migration across eight command test files) and the two documentation
sections.

After implementation the package must provide: an `autonomous: true` axis entry in
`.goga/tools/pybuggy/config.yml` that makes a running `api.automate` pipeline contribute the
fixed seven-stage auto-approval window plus the `build` stage; a silent no-op for every other
pipeline and every disabled state; a clean, pybuggy-naming error for every structural
violation; and a fully green `pytest tests/ -x` / `ruff check` / facade-import acceptance
gate.

Overall strategy: implement in the design's dependency order (statuses → config → autonomous
→ init edits → root) so each level's imports exist before the consumer; repair the currently
broken package import (root `__init__.py` still points at the deleted `statuses` module) in
the first task so every later task is testable; keep every task scoped to one cell; migrate
the eight-file test seam in one dedicated task that restores the full-suite gate.

## Context

### Contract Surface

**Entity: `register_automate_statuses(context: object)`**
- Type: function (Routine)
- Declared `location`: `goga_tool_pybuggy/statuses/automate.py`
- Facade obligation: importable from `goga_tool_pybuggy.statuses` (cell facade
  `__all__ = ["register_automate_statuses", "register_fix_statuses"]`)
- Semantic requirements: six literal `context.register(...)` calls in the normative table
  order (done → coding-planned → code-designed → arch-prepared → testcases-designed →
  requirements-created), each anchored `after` its built-in twin, the middle five also
  `before` the previously registered qualified automate status; registered names carry no
  tool prefix; no error handling (unresolvable anchors are platform-side skip-with-warning);
  partial registration is legitimate
- Imported dependencies: none (leaf cell)
- Annotation cascade: cell `conventions` + `goga-statuses` → routine annotation with the
  normative table

**Entity: `register_fix_statuses(context: object)`**
- Type: function (Routine)
- Declared `location`: `goga_tool_pybuggy/statuses/fix.py`
- Facade obligation: importable from `goga_tool_pybuggy.statuses`
- Semantic requirements: five literal `context.register(...)` calls in pipeline order
  (collected → analyzed → planned → executed → reviewed), each `after` the previous
  qualified fix status, the first anchored at the built-in `empty`; independent chain, no
  shared statuses with the automate line
- Imported dependencies: none
- Annotation cascade: same as above

**Entity: `PipelineAutonomy(autonomous: bool)`**
- Type: class (pydantic record)
- Declared `location`: `goga_tool_pybuggy/config/pipeline_autonomy.py`
- Facade obligation: importable from `goga_tool_pybuggy.config`; final cell facade
  `__all__ = ["Config", "GitEntry", "PipelineAutonomy", "SpecEntry", "load_config",
  "resolve_autonomy"]`
- Properties: `autonomous -> bool` — whether the pipeline named by the entry's dict key runs
  unattended
- Semantic requirements: pydantic model with `kw_only=True` and `extra="forbid"`
  (`model_config = ConfigDict(kw_only=True, extra="forbid")`); admits exactly the
  `autonomous` member — a key outside the member set fails validation (a mistyped key must
  surface, not silently disable autonomy); pydantic v2 lax bool coercion of truthy spellings
  (`"yes"`, `"on"`, `"1"`, `1`) is acceptable — the strictness requirement is the member set
- Imported dependencies: none (stdlib `typing` + pydantic)
- Annotation cascade: config cell header (kw_only, `typing.Optional` style, relative
  imports) → entity annotation → property annotation

**Entity: `load_config() -> config: Config`**
- Type: function (Routine) — **changed**: no parameters anymore
- Declared `location`: `goga_tool_pybuggy/config/storage.py`
- Facade obligation: importable from `goga_tool_pybuggy.config`; `CONFIG_PATH` and its
  facade export are **deleted**
- Semantic requirements: raw read through `goga.config.load_tool_config` (call-time import
  inside the function body — contract, not style); absent **or empty** file (the facade
  returns `None` for both) raises `FileNotFoundError` with message
  `"tool config not found: .goga/tools/pybuggy/config.yml"`; returns
  `Config.model_validate(raw)`; pydantic `ValidationError` and facade `yaml.YAMLError` /
  `OSError` propagate raw; `Config` stays permissive (pydantic default `extra="ignore"`) so
  the `pipelines` axis co-exists with the specs schema
- Imported dependencies: `Config` from `.config` (intra-cell)
- Annotation cascade: config cell header → routine annotation (3-step algorithm)

**Entity: `resolve_autonomy(pipeline: str) -> enabled: bool`**
- Type: function (Routine)
- Declared `location`: `goga_tool_pybuggy/config/storage.py` (same `location` as
  `load_config` — grouped)
- Facade obligation: importable from `goga_tool_pybuggy.config`
- Semantic requirements: whole-axis-validating lookup — call-time
  `load_tool_config("pybuggy", "config.yml")`; `raw is None` → False; non-mapping root →
  clean `ValueError` starting `"pybuggy tool config:"`; absent `pipelines` section → False;
  non-mapping axis → same clean error; every entry validated into `PipelineAutonomy`, a
  failure re-raised as `ValueError` naming pybuggy and the offending entry name, chaining
  the pydantic detail; absent name → False; present → `bool(record.autonomous)`;
  unknown names never fail; **no caching** — each call re-reads; interprets no section other
  than `pipelines`
- Imported dependencies: `PipelineAutonomy` from `.pipeline_autonomy`, `Config` context
- Annotation cascade: config cell header → routine annotation (algorithm + Requirements +
  Constraints)

**Entity: `amend_workflow(context: object)`**
- Type: function (Routine)
- Declared `location`: `goga_tool_pybuggy/autonomous/amendment.py`
- Facade obligation: importable from `goga_tool_pybuggy.autonomous` (cell facade
  `__all__ = ["amend_workflow", "build_autonomous_workflow"]`)
- Semantic requirements: read `context.pipeline`; **identity gate** — when the identity is
  not `"api.automate"`, return without contributing (silent no-op — the D1 fix: prevents
  contributing the api.automate-shaped window into any other pipeline even when its axis
  entry is enabled); `enabled = resolve_autonomy(pipeline)`; `not enabled` → silent no-op;
  `context.contribute(build_autonomous_workflow())`; **zero error catching** — anything
  raised propagates (autonomy never disables silently); do not read or alter the authored
  workflow
- Imported dependencies: `resolve_autonomy` (Types import from `goga_tool_pybuggy/config`,
  used as `from ..config import resolve_autonomy`)
- Annotation cascade: autonomous cell header → routine annotation (5-step algorithm,
  Requirements, Constraints) → imported usage `autonomy`

**Entity: `build_autonomous_workflow() -> document: dict[str, object]`**
- Type: function (Routine, pure builder)
- Declared `location`: `goga_tool_pybuggy/autonomous/workflow.py`
- Facade obligation: importable from `goga_tool_pybuggy.autonomous`
- Semantic requirements: reads only module-level compile-time constants; `stages` — the
  seven fixed window names in pipeline order (`review-testcases`, `create-testcases`,
  `code-design`, `design-review`, `coding-plan`, `plan-review`, `commit-changes`), each
  mapping exactly `{"approve": "auto"}`; `extend` — the single entry `build`:
  `after: ["commit-changes"]` plus body keys `title: "Build tests"`,
  `script: 'python3 -P -m goga.build "$(python3 -m goga history path -f plan.md)"'`
  (verbatim from the ADR), `after_script: "rm -rf .ralphex"`, `timeout: "8h"`; returns
  `{"stages": {...}, "extend": {...}}`; deterministic and pure — no platform calls, no I/O,
  byte-identical output on every call; no per-stage prompt/description directives, no
  acceptance-stage (`accept-result`) directives, no forbidden extend keys
  (`manual`/`notes`/`reflect`/`memory`/`prompt`/`skills`)
- Imported dependencies: none (workflow.py imports nothing)
- Annotation cascade: autonomous cell header → routine annotation (algorithm, Requirements,
  Constraints) → `goga-workflow-document` + `goga-compile-flow`

**Entity: `register_hooks(hooks: object)`**
- Type: function (Routine) — **changed**: five subscriptions (was four), moved to
  `reg_hooks.py`
- Declared `location`: `goga_tool_pybuggy/reg_hooks.py` (package root)
- Facade obligation: exposed on the ROOT facade via `__all__` — the platform imports it
  from the package root (`python -c "from goga_tool_pybuggy import register_hooks"`)
- Semantic requirements: five literal `hooks.subscribe(domain, action, name, callable)`
  calls in platform order — `("statuses", "register_statuses", "automate",
  register_automate_statuses)`, `("statuses", "register_statuses", "fix",
  register_fix_statuses)`, `("onboarding", "declare_session", "declare",
  declare_pybuggy_session)`, `("onboarding", "amend_config", "amend",
  amend_pybuggy_config)`, `("pipeline", "amend_workflow", "autonomy", amend_workflow)`;
  hook names stable and unique; handlers receive `context` by name; no error handling
  (malformed subscriptions are platform-side warnings); do not subscribe beyond the five
- Imported dependencies: `register_automate_statuses`/`register_fix_statuses` +
  usage `registration` from `goga_tool_pybuggy/statuses`; `amend_workflow` + usage
  `contribution` from `goga_tool_pybuggy/autonomous`; `declare_pybuggy_session`/
  `amend_pybuggy_config` from `goga_tool_pybuggy/commands/init`
- Annotation cascade: root header (hook-registration paragraph) → routine annotation
  (5-step algorithm, Requirements, Constraints)

**Entity: `pybuggy_questions() -> items: list[Question]`**
- Type: function — **changed**: appends the autonomy confirm
- Declared `location`: `goga_tool_pybuggy/commands/init/session.py`
- Facade obligation: declared in the init cell; consumed by `declare_pybuggy_session`
- Semantic requirements: current block built unchanged; append as the last item
  `Question(id="autonomous", kind="confirm", prompt="Run the api.automate pipeline unattended
  (autonomous mode)?", default=False)`; kind `confirm` yields a bool answer recorded on
  every survey; asked last (after the `first_spec` group); a simple child at top level — the
  block keeps exactly one nesting level; no id collision with the plugin scalar keys
- Imported dependencies: `Question`/`QuestionGroup` from `goga.onboarding`;
  `PluginConfigKeys` from `..plugin`; usage `autonomy` (Imports) for the gated axis
- Annotation cascade: init cell header → routine annotation (algorithm step 4 + Requirements
  line)

**Entity: `build_config_data(answers: dict[str, object], extra_specs: list[dict[str, object]] | None) -> data: dict[str, object]`**
- Type: function — **changed**: emits the conditional `pipelines` axis entry
- Declared `location`: `goga_tool_pybuggy/commands/init/session.py`
- Facade obligation: declared in the init cell; consumed by `amend_pybuggy_config`
- Semantic requirements: specs parsed first (unchanged), scalar keys collected second
  (unchanged); **new step 3**: `if answers.get("autonomous"):` →
  `data["pipelines"] = {"api.automate": {"autonomous": True}}` — a falsy answer (False, the
  confirm default, or None) emits nothing; `specs` placed last in the payload mapping
  (payload order: scalar keys, then `pipelines` when enabled, then `specs`); plain
  serializable data only; the entry shape equals the `resolve_autonomy` consumption shape
  exactly
- Imported dependencies: `SpecEntry`/`GitEntry` + usages `configuration`, `autonomy` from
  `goga_tool_pybuggy/config`; `PluginConfigKeys`
- Annotation cascade: init cell header → routine annotation (algorithm steps 3–4 +
  Requirements lines)

### Re-exports

- `->install: {}` (root CODEMANIFEST)
  - Name: `install`
  - Source: `Imports` → `Types: [install]` from `goga_tool_pybuggy/plugin`
  - Facade obligation: importable from `goga_tool_pybuggy` — already satisfied by the
    current `from .plugin import install` (unchanged; verification only)
- The statuses and autonomous Types imports at the root are consumed by `reg_hooks.py`
  imports, not re-exported on the root `__all__` (keep root `__all__` unchanged).

### Usages Context

- `conventions` (`.goga/usages/conventions.md`) — connected in **all five** changed cells.
  The mandatory Python rules: relative intra-package imports, pydantic kw_only models,
  Google docstrings, structured logging, blank-line block formatting, and the test-tree
  mirroring standard. Relevant to every entity and every test. Extracted in full into
  **Mandatory Rules** below.
- `goga-statuses` (`.goga/usages/github/goga/history/registering-hooks.md`) — statuses cell.
  The `statuses / register_statuses` member contract: `register(name, filepath, after=,
  before=)`, qualified storage, add-only, skip-with-warning. Used by both status routines.
- `goga-tool-config` (`.goga/usages/github/goga/config/tool-configuration.md`) — config cell.
  `load_tool_config(tool, filename, root=None)`: returns the raw parse or `None` for an
  absent (or empty) file; fixed `.goga/tools/<tool>/<filename>` standard; no caching, no
  interpretation; `root=None` → cwd-relative composition. Used by `load_config` and
  `resolve_autonomy`.
- `goga-pipeline-hooks` (`.goga/usages/github/goga/pipeline/registering-hooks.md`) —
  autonomous cell. The `pipeline / amend_workflow` event: firing time, hard error class,
  the `WorkflowAmendment` view reads (`pipeline`, `decision`, `workflow`, `work`) and
  `contribute(document)`, merge precedence, failure behavior. Used by `amend_workflow`.
- `goga-workflow-document` (`.goga/usages/github/goga/pipeline/workflow/parse-workflow.md`) —
  autonomous cell. The WorkflowDocument vocabulary: per-stage override keys (`approve`),
  extend-entry keys (`before`/`after`, extracted inline overrides, verbatim body), forbidden
  extend-entry keys. Used by `build_autonomous_workflow`.
- `goga-compile-flow` (`.goga/usages/github/goga/pipeline/compiler/compile-flow.md`) —
  autonomous cell. Compiled effects: `approve: auto` suppresses `interactive` emission for
  communication stages; `auto_approve` is not emitted (no roles); script directive →
  `script`/`script_after`/`script_timeout` with **no `agents` key**; timeout-requires-script;
  script exclusive with prompt/skills. Used to verify the contribution's compiled shape.
- `goga-hooks`, `goga-onboarding-hooks` (root) — the facade callback contract and the two
  onboarding action subscriptions. Used by `register_hooks`.
- `click`, `python-dotenv`, `ruamel-yaml`, `goga-scaffold`, `goga-onboarding`,
  `goga-onboarding-questions`, `goga-onboarding-generator` — unchanged contexts of the root
  and init cells; only the parts touched by this plan matter (the `Question` record kinds of
  `goga-onboarding-questions` for the confirm).

### Imported Usages

- `autonomy` — from cell `goga_tool_pybuggy/config`, source
  `goga_tool_pybuggy/config/.usages/autonomy.md`. The axis contract and the resolver
  consumption pattern; the bridge document between the config cell and its autonomy
  consumers. Consumed by: `amend_workflow` (autonomous cell) and `pybuggy_questions` +
  `build_config_data` (init cell).
- `registration` — from cell `goga_tool_pybuggy/statuses`, source
  `goga_tool_pybuggy/statuses/.usages/registration.md`. The status subscription pattern for
  the root's two statuses subscriptions. Consumed by: root `register_hooks`.
- `contribution` — from cell `goga_tool_pybuggy/autonomous`, source
  `goga_tool_pybuggy/autonomous/.usages/contribution.md`. The autonomy subscription pattern
  for the root's fifth subscription. Consumed by: root `register_hooks`.
- `configuration` — from cell `goga_tool_pybuggy/config` (init cell, unchanged edge).
  Schema compatibility of the `build_config_data` payload.

### Local Usages

All `.usages/` files were created/updated by the apply-architecture stage and verified
current by the design (and its review). **No usage-file tasks in this plan** — they are
read-only context; verify consistency only if an implementation detail contradicts them
(then fix the implementation, never the usage file, within this plan's scope).

- `goga_tool_pybuggy/statuses/.usages/registration.md` — status: current; entities: both
  status routines; describes both routines, the subscribe pattern, normative order,
  skip-with-warning.
- `goga_tool_pybuggy/config/.usages/configuration.md` — status: current; the no-argument
  `load_config()` example, the facade read, absent-file semantics.
- `goga_tool_pybuggy/config/.usages/autonomy.md` — status: current (amended by the design
  stage with "a non-mapping file root"); the axis shape, the resolver call, failure
  semantics.
- `goga_tool_pybuggy/autonomous/.usages/contribution.md` — status: current; both entities,
  the subscribe pattern, the no-op and precedence preconditions.
- `goga_tool_pybuggy/commands/init/.usages/config-build.md` — status: current; the
  `autonomous` question (asked last, default no) and the conditional axis entry.
- `goga_tool_pybuggy/.usages/assembly.md` — status: current; the five-hook table (including
  `autonomy` → `pipeline / amend_workflow`), the callable locations, the no-op semantics.

### Entity Interaction and Data Flow (verbatim from the design)

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

**Data flows:**

- **Onboarding → axis**: `pybuggy_questions` declares the `autonomous` confirm → engine
  surveys it (bool, default False) → `amend_pybuggy_config` reads the answer view →
  `build_config_data` emits `pipelines: {"api.automate": {"autonomous": true}}` only on True
  → engine serializes to `.goga/tools/pybuggy/config.yml`. Execution order inside
  `build_config_data`: specs are parsed first, scalar keys collected second, the axis entry
  added third, `specs` placed last in the payload mapping.
- **Run → contribution**: platform fires `pipeline / amend_workflow` before compilation →
  `amend_workflow` reads `context.pipeline` → (gate) → `resolve_autonomy` reads the file
  through `load_tool_config` and validates the whole axis → on True,
  `build_autonomous_workflow()` builds the constants document → `context.contribute(document)`
  buffers it → platform merges (authored intent wins per slot) → compiler validates and
  compiles the merged workflow.
- **Commands → config**: pull/list/info/generate/diff call `load_config()` (unchanged call
  sites) → `load_tool_config("pybuggy", "config.yml")` raw read → `Config.model_validate`
  (extra keys — including `pipelines` — are ignored; `specs` required).
- **Statuses → topic scale**: platform fires `statuses / register_statuses` per subscribed
  hook → each routine makes its literal `context.register(...)` calls in normative order.

**Entity dependencies (import graph; no cycles):**

- `statuses/` — imports nothing (leaf).
- `config/` — stdlib + pydantic only; `goga.config.load_tool_config` imported *at call time*
  inside the routines (goga stays out of runtime dependencies).
- `autonomous/` — `from ..config import resolve_autonomy` (amendment.py); workflow.py
  imports nothing.
- `commands/init/session.py` — unchanged imports (`..config`, `..plugin`, `goga.onboarding`).
- root `reg_hooks.py` — `from .statuses import ...`, `from .autonomous import
  amend_workflow`, `from .commands.init import amend_pybuggy_config,
  declare_pybuggy_session`.

### External Dependencies

- `goga` platform (test-extra only, `goga>=2.0.1,<2.1`): `goga.config.load_tool_config`
  (call-time import — never a runtime dependency), `goga.onboarding` records
  (`Question`, `QuestionGroup`) already used by session.py.
- `pydantic>=2.0` — `BaseModel`, `ConfigDict`, `ValidationError` (v2 semantics: lax bool
  coercion, `extra="ignore"` default on `Config`).
- `pyyaml>=6.0` — still a runtime dependency via `commands/init/init.py`; YAML 1.1 bool
  parsing (`yes`/`no`/`on`/`off` → real booleans) shapes the violation matrices.
- `click`, `pytest>=8.0`, `pytest-cov>=5.0`, `ruff>=0.15.0` — per `pyproject.toml`.
- **`pyproject.toml` dependency lists do NOT change** in this plan.

## Facts

- The working tree is **import-broken right now**: `goga_tool_pybuggy/statuses.py` is
  deleted (apply-architecture stage) and `goga_tool_pybuggy/statuses/` exists with only
  `CODEMANIFEST` + `.usages/` — while root `__init__.py` still does
  `from .statuses import register_hooks`. Every package-importing test currently fails at
  collection. Task 1 repairs this.
- `goga_tool_pybuggy/autonomous/` likewise exists with only `CODEMANIFEST` +
  `.usages/contribution.md` — no Python files yet.
- The two status routines are **literal relocations**: `git show
  HEAD:goga_tool_pybuggy/statuses.py` holds the verbatim register tables (six + five
  calls); only module docstrings and imports change. Do not "improve" the tables.
- `goga.config.load_tool_config("pybuggy", "config.yml")` composes
  `<root>/.goga/tools/pybuggy/config.yml` (`root=None` → cwd-relative) and returns the raw
  parse, or `None` for an absent **and for an empty** file; it propagates raw
  `yaml.YAMLError`; no caching.
- pydantic v2 lax bool coercion accepts `"yes"`/`"on"`/`"1"`/`1` as `True`; PyYAML (YAML
  1.1) parses `yes`/`no`/`on`/`off` to real booleans — so the non-bool rejection rows must
  use the non-coercible `"maybe"` (design-review findings 2 and 3, verified live).
- `pipelines/api.automate.yml` contains all seven window stage names; `approve: auto` is a
  legal per-stage override; the `build` extend body (script + after_script + timeout) emits
  no `agents` key.
- Eight test files carry the `CONFIG_PATH` seam — the complete set, grep-verified:
  `tests/test_cli_integration.py`, `tests/test_cli_env.py`,
  `tests/commands/pull/test_pull.py`, `tests/commands/diff/test_diff.py`,
  `tests/commands/diff/test_diff_integration.py`, `tests/commands/info/test_info.py`,
  `tests/commands/list/test_list.py`, `tests/commands/generate/test_generate.py` (~107
  occurrences). A missed file fails loudly: `monkeypatch.setattr` on the deleted attribute
  raises `AttributeError`.
- `tests/test_statuses.py` tests the deleted module (four-hook table) — superseded by
  `tests/statuses/*` and `tests/test_reg_hooks.py`.
- `tests/config/test_storage.py` tests the old `load_config(path)` signature — to be
  rewritten, not extended.
- The five command cells' `load_config()` call sites already match the narrowed no-arg
  signature; their CODEMANIFESTs are out of scope.
- Out of scope (do not touch): `pipelines/api.automate.yml`, the stage skills,
  `accept-result`, the goga platform itself, the five command cells' CODEMANIFESTs, and
  `pyproject.toml` dependencies.
- `goga lint` currently reports 19 cells, 0 errors; `goga schema` shows both new cells and
  the two new root dependency edges.

## Gap Analysis

- **Missing contract entities (no Python files at all)**:
  `statuses/{__init__,automate,fix}.py`, `config/pipeline_autonomy.py`,
  `autonomous/{__init__,amendment,workflow}.py`, root `reg_hooks.py`.
- **Missing facade exposure**: `statuses` and `autonomous` cell facades; config facade
  missing `PipelineAutonomy` + `resolve_autonomy`.
- **Broken/stale imports**: root `__init__.py` imports `register_hooks` from the deleted
  `statuses` module (package unimportable).
- **API mismatches**: `load_config(path=None)` + module `CONFIG_PATH` constant vs the
  contract's no-arg platform-facade read; config facade still exports `CONFIG_PATH`;
  `register_hooks` has four subscriptions vs the contract's five.
- **Behavioral mismatches**: `session.py` lacks the autonomy confirm and the conditional
  axis emission.
- **Existing code that can be reused**: the deleted `statuses.py` bodies (verbatim
  relocation source, git HEAD); the existing `_SCALAR_PROMPTS` / `_NUMERIC_MEMBERS` /
  `parse_specs` machinery of `session.py` (unchanged); the `tests/test_statuses.py`
  `_RecorderHooks` double pattern (basis for `tests/test_reg_hooks.py`); the command tests'
  `_write_config` helpers (adapted to the standard relative path).
- **Test coverage gaps**: no tests for the statuses cell, the autonomous cell,
  `PipelineAutonomy`, `resolve_autonomy`, the no-arg `load_config`, the autonomy question,
  the axis emission; the eight-file seam on a to-be-deleted attribute.
- **Docs gaps**: `docs/pipelines/api-automate.md` has no "Autonomous runs" section;
  `docs/cli/init.md` does not document the `autonomous` question.

---

## Mandatory Rules

Extracted from the project convention (`.goga/usages/conventions.md` — the `conventions`
practice connected by every changed cell) and the project tool configuration
(`pyproject.toml`). These rules are **mandatory for every task**; they override convenience
and apply in addition to each task's contract annotations. Where a contract annotation and
these rules overlap, the contract wins; where both are silent, the rules decide.

### M1. Coding Style (strictly per `conventions`)

- **M1.1** Python 3.10+ only. No syntax or stdlib usage beyond 3.10 compatibility.
- **M1.2** `pyproject.toml` is the single configuration source; all commands run inside the
  project virtualenv — create it if missing (`python3 -m venv .venv && .venv/bin/pip
  install -e ".[test]"`). Never execute against the system interpreter.
- **M1.3** Imports: **relative** for all intra-package references (`from ..config import
  resolve_autonomy`); **absolute** only for stdlib and third-party. An absolute import of
  the project's own package is forbidden.
- **M1.4** The call-time import pattern (`from goga.config import load_tool_config` inside
  the function body) is **contract, not style** — never hoist it to module level; it keeps
  goga out of the runtime dependency graph and is the test seam.
- **M1.5** All data models are pydantic with `kw_only=True`. Use `typing.Optional` (not
  `X | None`) for fields meaning explicit absence (ruff `UP045` is ignored project-wide for
  this reason). Empty defaults for regular fields; `None` only for explicit absence.
- **M1.6** Type hints are mandatory on every function and method (including tests).
- **M1.7** Docstrings: Google style, on **all** public functions, methods, and classes.
  First line capitalized and ending with a period; `Args` when parameters exist; `Returns`
  when a value returns; `Raises` for exceptions beyond built-ins.
- **M1.8** Function-body formatting: one blank line between logical blocks (initialization
  vs conditionals/loops, data preparation vs processing, processing vs return). Match the
  existing modules' visual rhythm — the deleted `statuses.py` body is the reference for the
  relocated routines.
- **M1.9** Logging: the `logging` library with a module-level
  `logger = logging.getLogger(__name__)`; structured `extra={...}` contextual metadata;
  lowercase concise messages; levels per the convention semantics (DEBUG diagnostics, INFO
  lifecycle, WARNING recoverable abnormality, ERROR failed operation). **This feature adds no
  new log statements** — the contracts demand silent no-op branches and pure builders;
  skip/warn behaviors belong to the platform. No secrets in any output.
- **M1.10** Dependencies: nothing new is added to `pyproject.toml` in this plan; `goga`
  stays test-extra; `pyyaml` stays runtime.
- **M1.11** Naming: PascalCase classes, snake_case functions/methods (language rules);
  helper names reflect support intent, not facade intent.

### M2. Test Writing Rules (strictly per `conventions`)

- **M2.1** The test tree mirrors the source directly: `goga_tool_pybuggy/<cell>/<module>.py`
  → `tests/<cell>/test_<module>.py`; root-package modules → `tests/test_<module>.py`;
  integration tests spanning multiple packages → directly in `tests/`.
- **M2.2** Every new test directory carries `__init__.py`. Local fixtures live in
  `tests/<package>/conftest.py`, shared fixtures in `tests/conftest.py`.
- **M2.3** File names `test_<module>.py`; test functions `test_<what>_<scenario>`; grouping
  `class Test<Component>:` where it aids navigation. Self-documenting names, minimal
  comments.
- **M2.4** Test categories (mirrored by the ralphex steps): **contract tests** — facade
  accessibility, API shape, signatures — written FIRST, expected to fail; **logic tests** —
  positive, negative, edge — written after implementation; **integration tests** — only for
  cross-module/package interaction, as separate tasks. Integration tests never replace
  contract or logic tests per entity.
- **M2.5** Edge coverage must include the convention's set: empty inputs (`None`, `""`,
  `[]`, `{}`), boundary values (`0`, negative, very large), invalid types, and expected
  exceptions via `pytest.raises`. Thresholds/state transitions use `@pytest.mark.parametrize`
  with a table including each boundary — the disabled-states and structural-violations
  matrices of this feature are parametrized tables by design.
- **M2.6** Doubles, not business-logic mocks: recorder doubles for platform surfaces only
  (`_RecorderHooks`, `_RecorderContext`, `_AmendmentView`); pure logic is tested
  mock-free; file I/O through the `tmp_path` fixture exclusively; external boundaries mocked
  at the import point (`monkeypatch.setattr` on the module attribute).
- **M2.7** CLI/handler tests call the command handler function directly (existing suites
  already do; the seam migration changes only the config-tree preparation, never the call
  style or assertions).
- **M2.8** Test dependencies stay in `[project.optional-dependencies].test`; no new test
  libraries.
- **M2.9** When debugging, fix **implementation code**, never test code, unless the test
  contradicts the design (then stop and re-check the design, not the contract).

### M3. Linters and Formatters — Enforced at Every Development Stage and Every Local Commit

- **M3.1** `ruff` is the project's linter **and** formatter, configured in `pyproject.toml`
  (`target-version = "py310"`, `line-length = 120`, rule sets `E,W,F,I,N,UP,B,SIM,PL,PLR,
  C4,DTZ,PT,ARG,RUF,PTH,C90`; format: double quotes, space indent, LF, magic trailing
  comma; `max-complexity = 10`). The per-file ignores for `tests/**` apply automatically.
- **M3.2** **Stage gate** — every task ends with BOTH commands clean (run in the venv):
  - `.venv/bin/ruff check goga_tool_pybuggy/ tests/`
  - `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/` (apply
    `.venv/bin/ruff format goga_tool_pybuggy/ tests/` first, then verify)
  Formatting fixes are applied before the task's completion checkbox is ticked. Decompose
  when `C90`/complexity or pylint rules demand it.
- **M3.3** **Local commit gate** — before **every** `git commit` (one commit per completed
  task; ralphex tasks commit locally as they finish):
  1. `.venv/bin/ruff check goga_tool_pybuggy/ tests/` → clean
  2. `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/` → clean
  3. `.venv/bin/pytest tests/ -x` → green **or** green in the plan-declared scope of the
     current task window (Tasks 2–6: the eight unmigrated seam files are the declared,
     design-sanctioned red set — everything else must pass)
  A commit that fails either ruff command is not made. Fix, re-run, commit.
- **M3.4** Facade checks follow the convention's command shape:
  `python -c "from goga_tool_pybuggy import register_hooks"` and the per-cell equivalents —
  run at the task gate where the facade changes.

### M4. REPL Cycle Rules — Continuous Interactive Evaluation, Hot Reloading, Code Migration

The workflow of every coding task is structured around a live REPL cycle: evaluate as you
write, reload instead of restart, and migrate verified code into source files.

- **M4.1 Continuous evaluation** — develop each entity against a live interpreter session
  (`.venv/bin/python3 -i` or `python3 -c` probes) started against prepared fixtures: for the
  config cell, a scratch tree with `mkdir -p <tmp>/.goga/tools/pybuggy` and handwritten
  `config.yml` variants (absent, empty, axis-enabled, each violation), `os.chdir` into it,
  then call the routines and observe real returns/raises before writing the logic tests.
  For pydantic/PyYAML boundary questions (coercion, bool parsing), settle them in the REPL
  against the installed versions — never from memory.
- **M4.2 Hot reloading** — after each source edit, re-evaluate in the same session via
  `importlib.reload(<module>)` (or re-import the facade) rather than restarting; keep the
  fixture tree valid across reloads. The point is a tight edit→reload→observe loop per
  entity.
- **M4.3 Code migration REPL → source** — the migration direction is one-way: snippets
  verified in the REPL are moved into the module file (with docstrings, type hints, and
  blank-line blocks per M1), never re-typed divergently. No working behavior may live only
  in the REPL session; the session is scaffolding, the source file is the deliverable.
- **M4.4 Pin REPL findings as tests** — every behavior confirmed interactively that the
  contract depends on (e.g. `"maybe"` rejected while `"yes"` coerces; empty file → `None`;
  no-arg signature importability) becomes an assertion in the task's logic/contract tests.
  The REPL observation is not done until it is pinned in `tests/`.
- **M4.5 REPL checkpoints in the task flow** — each coding task includes an explicit REPL
  verification checkbox between implementation and logic tests (see tasks: "REPL cycle"),
  covering: import resolution, one positive call, one negative call per error branch.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the
> next. Within each coding task, contract tests are written first (TDD workflow). The
> ralphex execution protocol steps (STEP 0–8) are embedded in each coding task. Every task
> is executed inside the project virtualenv (M1.2) and ends with the lint/format stage gate
> (M3.2) and the local commit gate (M3.3).

### Task 1: statuses cell + package import repair (TDD coding)

<Context: this task creates the `statuses` cell — the two topic-status routines relocated
verbatim from the deleted `goga_tool_pybuggy/statuses.py` (recover with `git show
HEAD:goga_tool_pybuggy/statuses.py`) — and repairs the currently broken package import.
The cell contract: `register_automate_statuses` in `automate.py` (six literal registrations
in the normative table order) and `register_fix_statuses` in `fix.py` (five literal
registrations), both facade-exposed via `statuses/__init__.py` with
`__all__ = ["register_automate_statuses", "register_fix_statuses"]`. Because the root
`__init__.py` still imports `register_hooks` from the deleted module (the whole package is
currently unimportable), this task also creates root `reg_hooks.py` with the four
subscriptions whose handlers already exist (statuses pair + onboarding pair) and switches
`__init__.py` to `from .reg_hooks import register_hooks` (keep root `__all__` unchanged).
The fifth subscription is added in Task 5, completing the root contract. The stale
`tests/test_statuses.py` (tests the deleted module) is deleted here; its coverage is
superseded by `tests/statuses/*` (this task) and `tests/test_reg_hooks.py` (Task 5).
Handlers receive `context` by name; no error handling anywhere in the cell —
unresolvable anchors are platform-side skip-with-warning.>

**Usages relevant to this task:**
- `conventions`: relative imports; Google docstrings; blank-line blocks; test tree
  `tests/statuses/test_{automate,fix}.py` with `__init__.py` + `conftest.py`; recorder
  doubles, no mocks of business logic.
- `goga-statuses`: the registration surface — `register(name, filepath, after=, before=)`,
  qualified storage (`pybuggy.<name>` assigned by the platform), add-only,
  skip-with-warning on unresolvable anchors.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this task (`Task 1: statuses cell + package import repair`) before writing anything.
- [x] **STEP 1 (CONTRACT TESTS)**: create `tests/statuses/__init__.py`,
      `tests/statuses/conftest.py` (the `_RecorderContext` double capturing
      `(name, artifact, after, before)` tuples), `tests/statuses/test_automate.py`, and
      `tests/statuses/test_fix.py`. Contract tests: both routines importable from
      `goga_tool_pybuggy.statuses`; `inspect.signature` shows exactly one parameter
      `context: object`, return annotation `None`. Expected to fail now (the cell has no
      Python files).
- [x] **STEP 2 (IMPLEMENTATION)**: create `goga_tool_pybuggy/statuses/automate.py` —
      relocate `register_automate_statuses` verbatim from `git show
      HEAD:goga_tool_pybuggy/statuses.py` (six literal `context.register` calls:
      `("automate.done", "completed/plan.md", after="done")`,
      `("automate.coding-planned", "plan.md", after="planned",
      before="pybuggy.automate.done")`,
      `("automate.code-designed", "design.md", after="specified",
      before="pybuggy.automate.coding-planned")`,
      `("automate.arch-prepared", "arch.md", after="designed",
      before="pybuggy.automate.code-designed")`,
      `("automate.testcases-designed", "testcases.md", after="backlog",
      before="pybuggy.automate.arch-prepared")`,
      `("automate.requirements-created", "requirements.md", after="defined",
      before="pybuggy.automate.testcases-designed")`); only the module docstring changes.
- [x] **STEP 2 (IMPLEMENTATION)**: create `goga_tool_pybuggy/statuses/fix.py` — relocate
      `register_fix_statuses` verbatim (five literal calls:
      `("fix.collected", "fix-collect.md", after="empty")`,
      `("fix.analyzed", "fix-analysis.md", after="pybuggy.fix.collected")`,
      `("fix.planned", "fix-plan.md", after="pybuggy.fix.analyzed")`,
      `("fix.executed", "fix-execute.md", after="pybuggy.fix.planned")`,
      `("fix.reviewed", "fix-review.md", after="pybuggy.fix.executed")`).
- [x] **STEP 2 (IMPLEMENTATION)**: create `goga_tool_pybuggy/statuses/__init__.py` — the
      cell facade docstring, the two relative imports, and
      `__all__ = ["register_automate_statuses", "register_fix_statuses"]`.
- [x] **STEP 2 (IMPLEMENTATION)**: create root `goga_tool_pybuggy/reg_hooks.py` —
      `register_hooks(hooks: object) -> None` with the **four** subscriptions available at
      this stage, in platform order:
      `hooks.subscribe("statuses", "register_statuses", "automate", register_automate_statuses)`,
      `hooks.subscribe("statuses", "register_statuses", "fix", register_fix_statuses)`,
      `hooks.subscribe("onboarding", "declare_session", "declare", declare_pybuggy_session)`,
      `hooks.subscribe("onboarding", "amend_config", "amend", amend_pybuggy_config)`;
      imports `from .statuses import register_automate_statuses, register_fix_statuses` and
      `from .commands.init import amend_pybuggy_config, declare_pybuggy_session`; docstring
      documents the four subscriptions (updated to five in Task 5).
- [x] **STEP 2 (IMPLEMENTATION)**: switch `goga_tool_pybuggy/__init__.py` — replace
      `from .statuses import register_hooks` with `from .reg_hooks import register_hooks`;
      keep `__all__` unchanged (this repairs the package import).
- [x] **STEP 2 (IMPLEMENTATION)**: delete `tests/test_statuses.py` (tests the deleted
      module; superseded by `tests/statuses/*` and, in Task 5, `tests/test_reg_hooks.py`).
- [x] **REPL cycle (M4)**: in the venv REPL — `from goga_tool_pybuggy import
      register_hooks` resolves; `from goga_tool_pybuggy.statuses import
      register_automate_statuses, register_fix_statuses` resolve; exercise both routines
      against an inline recorder object; verify six + five tuples and the anchor chain;
      reload (`importlib.reload`) after any edit.
- [x] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest tests/statuses/ -v` — all
      contract tests pass.
- [x] **STEP 4 (LOGIC TESTS)**: in `tests/statuses/test_automate.py` —
      `test_register_automate_statuses_registers_six_statuses_in_order` asserting
      `context.calls == [("automate.done", "completed/plan.md", "done", None),
      ("automate.coding-planned", "plan.md", "planned", "pybuggy.automate.done"),
      ("automate.code-designed", "design.md", "specified", "pybuggy.automate.coding-planned"),
      ("automate.arch-prepared", "arch.md", "designed", "pybuggy.automate.code-designed"),
      ("automate.testcases-designed", "testcases.md", "backlog", "pybuggy.automate.arch-prepared"),
      ("automate.requirements-created", "requirements.md", "defined",
      "pybuggy.automate.testcases-designed")]`; in `tests/statuses/test_fix.py` —
      `test_register_fix_statuses_registers_five_statuses_in_order` asserting
      `context.calls == [("fix.collected", "fix-collect.md", "empty", None),
      ("fix.analyzed", "fix-analysis.md", "pybuggy.fix.collected", None),
      ("fix.planned", "fix-plan.md", "pybuggy.fix.analyzed", None),
      ("fix.executed", "fix-execute.md", "pybuggy.fix.planned", None),
      ("fix.reviewed", "fix-review.md", "pybuggy.fix.executed", None)]`.
- [x] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/ -x` — fix implementation code until
      all tests pass (the full suite is expected green at this point: `CONFIG_PATH` still
      exists, the old `tests/config/test_storage.py` still matches the old signature).
- [x] **STEP 6 (CONTRACT RE-VERIFICATION)**: facade probes —
      `.venv/bin/python -c "from goga_tool_pybuggy import register_hooks"` and
      `.venv/bin/python -c "from goga_tool_pybuggy.statuses import register_automate_statuses, register_fix_statuses"`;
      confirm the register tables are byte-identical to the git-HEAD originals (diff the
      call blocks).
- [x] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — fix formatting, decompose if
      necessary.
- [x] **STEP 8 (COMPLETION + COMMIT GATE)**: mark this task's checkboxes complete; run the
      local commit gate (M3.3: ruff check, ruff format --check, `pytest tests/ -x` green)
      and `git commit` the task.
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 2: config cell — `PipelineAutonomy`, `load_config`, `resolve_autonomy`, facade without `CONFIG_PATH` (TDD coding)

<Context: this task implements the reworked config cell. Three contract entities:
`PipelineAutonomy` (new file `pipeline_autonomy.py` — pydantic record, `kw_only=True`,
`extra="forbid"`, single `autonomous: bool` member), the narrowed no-arg `load_config`, and
the new `resolve_autonomy` — both in `storage.py`, which drops the `CONFIG_PATH` constant
entirely. Both routines read through the platform facade with a **call-time** import
(`from goga.config import load_tool_config` inside the function body — contract, never
hoisted); module constants `_TOOL = "pybuggy"` / `_FILENAME = "config.yml"` carry the read
arguments. `load_config`: `raw is None` (absent or empty file) → `FileNotFoundError(
"tool config not found: .goga/tools/pybuggy/config.yml")`; else
`Config.model_validate(raw)` (extra keys — including `pipelines` — ignored).
`resolve_autonomy`: `None` → False; non-mapping root / non-mapping axis / invalid entry →
`ValueError` with messages starting `"pybuggy tool config:"` (the entry violation names the
offending entry and chains the pydantic error: `raise ValueError(f"pybuggy tool config:
invalid pipelines entry {name!r}") from err`); absent section/name → False; present →
`bool(record.autonomous)`; no caching. The facade `config/__init__.py` becomes
`__all__ = ["Config", "GitEntry", "PipelineAutonomy", "SpecEntry", "load_config",
"resolve_autonomy"]` — `CONFIG_PATH` deleted from the module and the facade. The old
`tests/config/test_storage.py` (old signature) is rewritten in this task; the shared
`tool_config` fixture lands in `tests/conftest.py`. **Known-red window opens**: deleting
`CONFIG_PATH` breaks the eight command test files until Task 7 — full-suite gates are
scoped until then; `tests/config/` must be green.>

**Usages relevant to this task:**
- `conventions`: pydantic kw_only + `typing.Optional`; relative imports; Google docstrings
  with `Raises`; `tmp_path`-based file I/O; parametrized boundary tables; test tree
  `tests/config/test_PipelineAutonomy.py`, `tests/config/test_storage.py`.
- `goga-tool-config`: `load_tool_config(tool, filename)` → the raw parse or `None` (absent
  **or empty** file); fixed `.goga/tools/<tool>/<filename>` standard; `root=None` →
  cwd-relative composition; no caching — the fixture writes the standard tree under a
  chdir'd `tmp_path` so the real composition is exercised with zero patching.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this task (`Task 2: config cell — PipelineAutonomy, load_config, resolve_autonomy`).
- [x] **STEP 1 (CONTRACT TESTS)**: create `tests/config/test_PipelineAutonomy.py`
      (importable from `goga_tool_pybuggy.config`; `PipelineAutonomy.model_fields` holds
      exactly `autonomous`; `model_config` is kw_only + extra=forbid) and rewrite
      `tests/config/test_storage.py` contract rows: `load_config` importable and
      `inspect.signature(load_config).parameters == {}`; `resolve_autonomy` importable with
      signature `(pipeline: str) -> bool`; the final facade shape test
      `test_config_facade_no_longer_exports_config_path` —
      `"CONFIG_PATH" not in vars(cfg)`, `"CONFIG_PATH" not in cfg.__all__`,
      `sorted(cfg.__all__) == ["Config", "GitEntry", "PipelineAutonomy", "SpecEntry",
      "load_config", "resolve_autonomy"]`. Add the shared `tool_config` fixture to
      `tests/conftest.py`:
      `@pytest.fixture def tool_config(tmp_path, monkeypatch): monkeypatch.chdir(tmp_path); def _write(text): path = tmp_path / ".goga" / "tools" / "pybuggy" / "config.yml"; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8"); return _write`.
      Expected to fail now.
- [x] **STEP 2 (IMPLEMENTATION)**: create `goga_tool_pybuggy/config/pipeline_autonomy.py` —
      `class PipelineAutonomy(BaseModel)` with
      `model_config = ConfigDict(kw_only=True, extra="forbid")` and
      `autonomous: bool`; Google docstring; property semantics per the annotation.
- [x] **STEP 2 (IMPLEMENTATION)**: rewrite `goga_tool_pybuggy/config/storage.py` — drop
      `CONFIG_PATH` and the `path` parameter; module constants `_TOOL = "pybuggy"`,
      `_FILENAME = "config.yml"`; `load_config()` implementing:
      call-time `from goga.config import load_tool_config`; `raw =
      load_tool_config(_TOOL, _FILENAME)`; `if raw is None: raise
      FileNotFoundError("tool config not found: .goga/tools/pybuggy/config.yml")`;
      `return Config.model_validate(raw)`. Then `resolve_autonomy(pipeline: str) -> bool`:
      call-time facade read; `None` → `False`; `not isinstance(raw, dict)` →
      `raise ValueError("pybuggy tool config: the file must parse to a mapping")`;
      `axis = raw.get("pipelines")`; `None` → `False`; `not isinstance(axis, dict)` →
      `raise ValueError("pybuggy tool config: pipelines must be a mapping")`; per-name
      `PipelineAutonomy.model_validate(entry)` with `ValidationError` re-raised as
      `ValueError(f"pybuggy tool config: invalid pipelines entry {name!r}") from err`;
      `pipeline not in records` → `False`; `return bool(records[pipeline].autonomous)`.
      No try/except beyond the entry wrap; no caching; pydantic/facade errors propagate.
- [x] **STEP 2 (IMPLEMENTATION)**: update `goga_tool_pybuggy/config/__init__.py` — imports
      `Config`, `GitEntry`, `PipelineAutonomy`, `SpecEntry`, `load_config`,
      `resolve_autonomy`; `__all__ = ["Config", "GitEntry", "PipelineAutonomy",
      "SpecEntry", "load_config", "resolve_autonomy"]`; facade docstring updated (no
      `CONFIG_PATH`).
- [x] **REPL cycle (M4)**: in the venv REPL against a scratch tree — verify live: absent
      file and empty file both raise the exact `FileNotFoundError` (message contains
      `.goga/tools/pybuggy/config.yml`); axis-enabled tree returns `True`; each violation
      string raises `ValueError` starting `pybuggy tool config:`; `"autonomous": "maybe"`
      raises while `"autonomous": "yes"` coerces to True (pin both as tests); a rewrite of
      the file between two `resolve_autonomy` calls is visible immediately (no caching).
      Reload after each edit.
- [x] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest tests/config/ -v` — contract
      tests pass.
- [x] **STEP 4 (LOGIC TESTS)**: in `tests/config/test_PipelineAutonomy.py` —
      `test_pipeline_autonomy_accepts_valid_record`
      (`model_validate({"autonomous": True}).autonomous is True`;
      `PipelineAutonomy(autonomous=False).autonomous is False`) and
      `test_pipeline_autonomy_rejects_parametrized` — rows `{}`,
      `{"autonomous": True, "typo": 1}`, `{"autonomous": "maybe"}`,
      `{"autonomous": None}` → `pytest.raises(pydantic.ValidationError)`; plus
      `pytest.raises(TypeError)` on positional `PipelineAutonomy(True)` (kw_only). In
      `tests/config/test_storage.py` — `test_load_config_reads_standard_path` (specs-only
      tree; asserts `config.specs["client"].location/type/git`; plus the no-arg signature
      assert), `test_load_config_ignores_pipelines_section`,
      `test_load_config_absent_file_raises_naming_location` (parametrized: no file / empty
      file; `pytest.raises(FileNotFoundError, match=r"\.goga/tools/pybuggy/config\.yml")`),
      `test_resolve_autonomy_enabled_returns_true`,
      `test_resolve_autonomy_structural_violations_parametrized` (rows: `"just a string\n"`,
      `"specs: {}\npipelines:\n  - a\n  - b\n"`,
      `"pipelines:\n  api.automate: plain-string\n"`,
      `"pipelines:\n  api.automate:\n    autonomous: maybe\n"`,
      `"pipelines:\n  api.automate:\n    autonomous: true\n    typo: 1\n"` — all
      `pytest.raises(ValueError, match="pybuggy tool config")`; YAML-truthy spellings
      deliberately absent: PyYAML parses `yes`/`on` to real booleans),
      `test_resolve_autonomy_propagates_facade_parse_error` (invalid YAML
      `"pipelines: [unclosed"` → `pytest.raises((yaml.YAMLError, ValueError))`),
      `test_resolve_autonomy_disabled_states_parametrized` (five rows: no file, `""`,
      `"specs: {}\n"`, other-pipeline entry, `autonomous: false` → `result is False`),
      `test_resolve_autonomy_no_caching` (false → rewrite true → `is True`),
      `test_resolve_autonomy_unknown_names_never_fail`.
- [x] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/config/ tests/statuses/ -x` — fix
      implementation code until green. Then `.venv/bin/pytest tests/ --ignore
      tests/test_cli_integration.py --ignore tests/test_cli_env.py --ignore
      tests/commands/pull/test_pull.py --ignore tests/commands/diff/test_diff.py --ignore
      tests/commands/diff/test_diff_integration.py --ignore tests/commands/info/test_info.py
      --ignore tests/commands/list/test_list.py --ignore
      tests/commands/generate/test_generate.py` — green (everything outside the declared
      eight-file red set passes; the seam files themselves stay red with `CONFIG_PATH`
      `AttributeError` until Task 7 migrates them).
- [x] **STEP 6 (CONTRACT RE-VERIFICATION)**: facade probes —
      `.venv/bin/python -c "from goga_tool_pybuggy.config import Config, GitEntry, PipelineAutonomy, SpecEntry, load_config, resolve_autonomy"`
      and `.venv/bin/python -c "import goga_tool_pybuggy.config as c; assert not hasattr(c, 'CONFIG_PATH')"`.
- [x] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/`.
- [x] **STEP 8 (COMPLETION + COMMIT GATE)**: mark checkboxes complete; commit gate per
      M3.3 (pytest scoped green: `tests/config/ tests/statuses/ tests/commands/init/` +
      the declared eight-file red set) and `git commit`.
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 3: autonomous cell — `build_autonomous_workflow`, `amend_workflow` (TDD coding)

<Context: this task creates the `autonomous` cell. `workflow.py` holds the compile-time
constants — `_WINDOW_STAGES = ("review-testcases", "create-testcases", "code-design",
"design-review", "coding-plan", "plan-review", "commit-changes")`, `_BUILD_NAME = "build"`,
`_BUILD_TITLE = "Build tests"`,
`_BUILD_SCRIPT = 'python3 -P -m goga.build "$(python3 -m goga history path -f plan.md)"'`
(verbatim from the ADR), `_BUILD_AFTER_SCRIPT = "rm -rf .ralphex"`,
`_BUILD_TIMEOUT = "8h"`, `_BUILD_AFTER = ("commit-changes",)` — and the pure builder
returning `{"stages": {name: {"approve": "auto"} for name in _WINDOW_STAGES}, "extend":
{_BUILD_NAME: {"after": list(_BUILD_AFTER), "title": _BUILD_TITLE, "script":
_BUILD_SCRIPT, "after_script": _BUILD_AFTER_SCRIPT, "timeout": _BUILD_TIMEOUT}}}`.
`amendment.py` holds `_PIPELINE = "api.automate"` and the five-step hook: read
`context.pipeline`; gate (identity ≠ `_PIPELINE` → silent return); `enabled =
resolve_autonomy(pipeline)`; `not enabled` → silent return;
`context.contribute(build_autonomous_workflow())`. Import
`from ..config import resolve_autonomy` and
`from .workflow import build_autonomous_workflow` (relative). **Zero try/except in the
module** — errors propagate (autonomy never disables silently). Facade
`autonomous/__init__.py` with `__all__ = ["amend_workflow", "build_autonomous_workflow"]`.
The root subscription is NOT touched here (Task 5).>

**Usages relevant to this task:**
- `conventions`: relative imports; Google docstrings; recorder doubles; pure-builder tests
  mock-free; test tree `tests/autonomous/test_{amendment,workflow}.py` with `__init__.py`
  + `conftest.py`.
- `goga-pipeline-hooks`: the `pipeline / amend_workflow` moment — hard error class; the
  `WorkflowAmendment` view reads (`pipeline` et al.) and `contribute(document)`; a repeat
  `contribute` replaces the tool's buffer whole; the tool's contribution commits only after
  the hook returns without raising.
- `goga-workflow-document`: per-stage override key `approve`; extend-entry `after`
  positioning (list[str]) + verbatim body keys; forbidden extend-entry keys
  (`manual`/`notes`/`reflect`/`memory`); script exclusive with `prompt`/`skills`;
  `timeout` requires `script`.
- `goga-compile-flow` (verification context): `approve: "auto"` suppresses `interactive`
  emission for communication stages; `auto_approve` never emitted (no roles); the script
  body compiles to `script`/`script_after`/`script_timeout` with **no `agents` key**.
- `autonomy` (imported from `config`): the resolver consumption pattern — str in, bool
  out, errors surface.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare this task (`Task 3: autonomous cell — build_autonomous_workflow, amend_workflow`).
- [ ] **STEP 1 (CONTRACT TESTS)**: create `tests/autonomous/__init__.py`,
      `tests/autonomous/conftest.py` (the `_AmendmentView` double:
      `__init__(self, pipeline)` setting `self.pipeline` and `self.contributed = []`;
      `contribute(self, document)` appending), `tests/autonomous/test_workflow.py`,
      `tests/autonomous/test_amendment.py`. Contract tests: both names importable from
      `goga_tool_pybuggy.autonomous`; `build_autonomous_workflow` signature `() ->
      dict[str, object]`; `amend_workflow` signature `(context: object) -> None`. Expected
      to fail now.
- [ ] **STEP 2 (IMPLEMENTATION)**: create `goga_tool_pybuggy/autonomous/workflow.py` — the
      constants block + `build_autonomous_workflow()` per the context above; pure, no
      platform calls, no I/O.
- [ ] **STEP 2 (IMPLEMENTATION)**: create `goga_tool_pybuggy/autonomous/amendment.py` —
      `_PIPELINE` + `amend_workflow(context)` implementing the five steps; no catching.
- [ ] **STEP 2 (IMPLEMENTATION)**: create `goga_tool_pybuggy/autonomous/__init__.py` —
      facade docstring, relative imports,
      `__all__ = ["amend_workflow", "build_autonomous_workflow"]`.
- [ ] **REPL cycle (M4)**: in the venv REPL — call `build_autonomous_workflow()` twice,
      confirm deep equality and the exact stage list order; verify the script string
      byte-for-byte (shell quotes included); drive `amend_workflow` with an inline view
      double for `"api.automate"` (resolver monkeypatched True via
      `monkeypatch`-equivalent `setattr`) and for `"code.review"`; verify a raising
      resolver propagates. Reload after each edit.
- [ ] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest tests/autonomous/ -v`.
- [ ] **STEP 4 (LOGIC TESTS)**: in `tests/autonomous/test_workflow.py` —
      `test_build_autonomous_workflow_document_shape`:
      `set(document) == {"stages", "extend"}`;
      `list(document["stages"]) == ["review-testcases", "create-testcases", "code-design",
      "design-review", "coding-plan", "plan-review", "commit-changes"]`;
      `all(v == {"approve": "auto"} for v in document["stages"].values())`;
      `build = document["extend"]["build"]`; `build["after"] == ["commit-changes"]`;
      `build["title"] == "Build tests"`;
      `build["script"] == 'python3 -P -m goga.build "$(python3 -m goga history path -f plan.md)"'`;
      `build["after_script"] == "rm -rf .ralphex"`; `build["timeout"] == "8h"`;
      `set(build) == {"after", "title", "script", "after_script", "timeout"}`;
      `"accept-result" not in document["stages"] and "accept-result" not in
      document["extend"]`. Plus `test_build_autonomous_workflow_deterministic`
      (two calls deeply equal). In `tests/autonomous/test_amendment.py` —
      `test_amend_workflow_contributes_when_enabled`
      (`monkeypatch.setattr("goga_tool_pybuggy.autonomous.amendment.resolve_autonomy",
      lambda pipeline: True)`; view `"api.automate"`;
      `view.contributed == [build_autonomous_workflow()]`),
      `test_amend_workflow_no_op_for_other_pipeline_even_when_axis_enabled` (resolver
      stubbed True for anything; view `"code.review"`; `view.contributed == []`, no
      exception — the D1 regression test),
      `test_amend_workflow_errors_propagate_undamped` (resolver stub raising
      `ValueError("pybuggy tool config: boom")`; `pytest.raises(ValueError, match=...)`;
      `view.contributed == []`).
- [ ] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/autonomous/ tests/config/ -x` — fix
      implementation until green (full-suite failures remain only the declared eight seam
      files).
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)**: facade probe —
      `.venv/bin/python -c "from goga_tool_pybuggy.autonomous import amend_workflow, build_autonomous_workflow"`;
      confirm no `try`/`except` and no logging in `amendment.py`; confirm `workflow.py`
      imports nothing.
- [ ] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/`.
- [ ] **STEP 8 (COMPLETION + COMMIT GATE)**: mark checkboxes complete; commit gate per
      M3.3 (scoped pytest green) and `git commit`.
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 4: init cell — autonomy confirm + conditional axis entry (TDD coding)

<Context: this task makes the two tail edits in `goga_tool_pybuggy/commands/init/session.py`
(the module otherwise stays untouched). (1) `pybuggy_questions`: append as the last item —
after the `first_spec` group — `Question(id="autonomous", kind="confirm", default=False,
prompt="Run the api.automate pipeline unattended (autonomous mode)?")`; the block keeps
exactly one nesting level (the confirm is a simple top-level child). (2)
`build_config_data`: after the scalar-key collection loop and before the
`data["specs"] = ...` assignment, insert `if answers.get("autonomous"): data["pipelines"] =
{"api.automate": {"autonomous": True}}` — payload order becomes scalar keys, `pipelines`
(when enabled), `specs` last. A falsy answer (False — the confirm default — or None) emits
nothing: existing projects stay untouched until the user opts in. The emitted entry shape
must equal the `resolve_autonomy` consumption shape exactly (the emit↔consume bridge).
Extend `tests/commands/init/test_session.py` (existing file, existing fixtures).>

**Usages relevant to this task:**
- `conventions`: pure functions tested mock-free; Google docstrings; parametrized
  disabling/absent rows.
- `goga-onboarding-questions`: the `Question` record kinds — `confirm` yields a bool answer
  recorded on every survey; simple children at top level.
- `autonomy` (imported from `config`): the axis the answer gates — the entry shape
  `{"api.automate": {"autonomous": True}}`.
- `configuration` (imported from `config`): schema compatibility — `Config.model_validate`
  ignores the `pipelines` key on loading.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare this task (`Task 4: init cell — autonomy confirm + conditional axis entry`).
- [ ] **STEP 1 (CONTRACT TESTS)**: in `tests/commands/init/test_session.py` add contract
      rows: `pybuggy_questions()` last item is a `Question` with `id == "autonomous"`,
      `kind == "confirm"`, `default is False`; `build_config_data` keeps its declared
      signature. Expected to fail now.
- [ ] **STEP 2 (IMPLEMENTATION)**: in `pybuggy_questions()` append the confirm as the final
      `items.append(...)` — literal texts from the context above (prompt wording is the
      design-fixed [decision]).
- [ ] **STEP 2 (IMPLEMENTATION)**: in `build_config_data()` insert the conditional axis
      step between the scalar loop and the `specs` assignment; update the docstring's
      payload-order description (scalar keys, then `pipelines` when enabled, then `specs`
      last) and the module docstring if it enumerates the block.
- [ ] **REPL cycle (M4)**: in the venv REPL — call `pybuggy_questions()`; assert
      `items[-1].id == "autonomous"`, `items[-2].id == "first_spec"`; drive
      `build_config_data` with an enabling and a disabling answer view; `yaml.safe_load(
      yaml.safe_dump(data)) == data` (plain serializable); feed the enabling payload
      through `yaml.safe_dump` into a scratch `config.yml` and confirm `resolve_autonomy(
      "api.automate") is True` on it (the bridge, live). Reload after each edit.
- [ ] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest tests/commands/init/ -v`.
- [ ] **STEP 4 (LOGIC TESTS)**:
      `test_pybuggy_questions_appends_autonomy_confirm_last` (`last = items[-1]`;
      `isinstance(last, Question)`; `last.id == "autonomous"`; `last.kind == "confirm"`;
      `last.default is False`; `items[-2].id == "first_spec"`),
      `test_build_config_data_emits_pipelines_axis_on_enabling_answer` (answers view with
      `base_url`, `first_spec`, `"autonomous": True`; `extra_specs=None`;
      `data["pipelines"] == {"api.automate": {"autonomous": True}}`;
      `list(data)[-1] == "specs"`; `yaml.safe_load(yaml.safe_dump(data)) == data`),
      `test_build_config_data_disabling_and_absent_answers_emit_no_axis` (two rows:
      `"autonomous": False` and no key; `"pipelines" not in data`; `data["specs"]`
      present). Adapt the one stale row `test_pybuggy_questions_returns_block_in_survey_order`
      to the new block shape — `len(items) == 9`, the `first_spec` group at `items[-2]`
      (the autonomy confirm is `items[-1]`); preserve every other existing row unchanged
      (they stay green).
- [ ] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/commands/init/ -x` — fix
      implementation until green (full-suite failures remain only the declared eight seam
      files).
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)**: probes —
      `.venv/bin/python -c "from goga_tool_pybuggy.commands.init import declare_pybuggy_session, amend_pybuggy_config"`;
      confirm no existing question id collides with `autonomous`; confirm the block still
      holds exactly one nesting level.
- [ ] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/`.
- [ ] **STEP 8 (COMPLETION + COMMIT GATE)**: mark checkboxes complete; commit gate per
      M3.3 (scoped pytest green) and `git commit`.
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 5: root — fifth subscription + `tests/test_reg_hooks.py` (TDD coding)

<Context: this task completes the root `register_hooks` contract: add the fifth
subscription — `hooks.subscribe("pipeline", "amend_workflow", "autonomy", amend_workflow)` —
to `goga_tool_pybuggy/reg_hooks.py` (import
`from .autonomous import amend_workflow`), making the table five hooks on four addresses in
platform order (statuses/automate, statuses/fix, onboarding/declare, onboarding/amend,
pipeline/autonomy), and update the docstring from four to five subscriptions. Write
`tests/test_reg_hooks.py` (root-package module → directly in `tests/`, replacing the
deleted `tests/test_statuses.py` coverage): the five-subscription table test and the
facade/signature test. Nothing else in the root changes; root `__all__` stays unchanged.>

**Usages relevant to this task:**
- `conventions`: root-package module tests live directly in `tests/`; recorder doubles;
  identity assertions on callables.
- `goga-hooks`: the facade callback contract and the failure behavior of registrations
  (platform-side warnings — the routine never defends).
- `goga-onboarding-hooks`: the two onboarding action subscriptions (declare_session,
  amend_config).
- `registration` (imported from `statuses`): the status subscription pattern — stable hook
  names `automate`/`fix`, context by name, independent moments.
- `contribution` (imported from `autonomous`): the autonomy subscription pattern — hook
  name `autonomy` on the `pipeline / amend_workflow` action, context by name.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare this task (`Task 5: root — fifth subscription + test_reg_hooks`).
- [ ] **STEP 1 (CONTRACT TESTS)**: create `tests/test_reg_hooks.py` with the
      `_RecorderHooks` double (capturing `(domain, action, name, hook)` tuples) and
      contract rows: `register_hooks` importable from `goga_tool_pybuggy` and callable —
      expected to fail against the current four-subscription table (the table assertion
      expects five entries).
- [ ] **STEP 2 (IMPLEMENTATION)**: in `goga_tool_pybuggy/reg_hooks.py` — add
      `from .autonomous import amend_workflow`; append the fifth `hooks.subscribe(...)`
      call; update the docstring to the five-subscription description (topic-status hooks,
      onboarding pair, autonomy amendment hook).
- [ ] **REPL cycle (M4)**: in the venv REPL — `from goga_tool_pybuggy import
      register_hooks`; drive it with an inline recorder; verify the five tuples in order
      and that each fourth element IS the cell object by identity
      (`goga_tool_pybuggy.statuses.register_automate_statuses`, etc.). Reload after the
      edit.
- [ ] **STEP 3 (INTERFACE VERIFICATION)**: `.venv/bin/pytest tests/test_reg_hooks.py -v`.
- [ ] **STEP 4 (LOGIC TESTS)**: `test_register_hooks_subscribes_five_hooks` —
      `recorder.calls == [("statuses", "register_statuses", "automate",
      register_automate_statuses), ("statuses", "register_statuses", "fix",
      register_fix_statuses), ("onboarding", "declare_session", "declare",
      declare_pybuggy_session), ("onboarding", "amend_config", "amend",
      amend_pybuggy_config), ("pipeline", "amend_workflow", "autonomy", amend_workflow)]`
      with each callable the cell object by identity; plus
      `test_register_hooks_facade_and_signature` — `callable(register_hooks)`;
      `register_hooks.__annotations__ == {"hooks": object, "return": None}`.
- [ ] **STEP 5 (DEBUGGING)**: `.venv/bin/pytest tests/test_reg_hooks.py tests/statuses/
      tests/autonomous/ -x` — fix implementation until green (full-suite failures remain
      only the declared eight seam files).
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)**: the acceptance probe —
      `.venv/bin/python -c "from goga_tool_pybuggy import register_hooks"`; confirm
      exactly five `subscribe` calls and no other root file changed.
- [ ] **STEP 7 (LINT)**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/`.
- [ ] **STEP 8 (COMPLETION + COMMIT GATE)**: mark checkboxes complete; commit gate per
      M3.3 (scoped pytest green) and `git commit`.
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 6: Integration tests — the autonomy bridge (integration tests)

<Context: cross-cell verification of the feature's two end-to-end chains, placed directly
in `tests/` per the convention (multi-package integration). (1) The run chain:
`amend_workflow` with a REAL `resolve_autonomy` reading a prepared standard tree — the
autonomous and config cells compose through the real file standard, no stubs. (2) The
emit↔consume bridge: the `build_config_data` payload (init cell), serialized as YAML to the
standard path, is consumed by `resolve_autonomy` (config cell) — the exact bridge the
design verified (emit → engine YAML → raw parse → axis validation). Both scenarios use the
shared `tool_config` fixture from `tests/conftest.py` (Task 2).>

**Usages relevant to this task:**
- `conventions`: integration tests covering multiple packages go directly in `tests/`;
  file I/O via `tmp_path` exclusively; no mocks in these scenarios (the real platform facade
  read is the point).
- `autonomy` (imported usage): the resolver call pattern and failure semantics.
- `goga-tool-config`: the standard-tree fixture exercises the real cwd-relative path
  composition.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create `tests/test_autonomy_integration.py` (module docstring stating the two
      chains).
- [ ] Test cross-cell interaction (run chain): `test_amend_workflow_end_to_end_with_real_config`
      — `tool_config` writes `"pipelines:\n  api.automate:\n    autonomous: true\n"`;
      `_AmendmentView("api.automate")` (import the double from `tests/autonomous/conftest.py`
      or re-declare locally); `amend_workflow(view)` with the real resolver;
      `view.contributed == [build_autonomous_workflow()]`.
- [ ] Test cross-cell interaction (emit↔consume bridge):
      `test_build_config_data_payload_enables_resolve_autonomy` — build the enabling
      payload via `build_config_data`; `tool_config(yaml.safe_dump(payload))`;
      `resolve_autonomy("api.automate") is True`; and the disabling payload
      (`"autonomous": False`) leaves `resolve_autonomy(...) is False` (no `pipelines` key
      written).
- [ ] Test edge case: `test_amend_workflow_end_to_end_disabled_is_silent_no_op` — the
      same chain with `autonomous: false` in the tree; `view.contributed == []`, no
      exception.
- [ ] Run validation: `.venv/bin/pytest tests/test_autonomy_integration.py -v`.
- [ ] **Lint**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/`.
- [ ] **COMMIT GATE (M3.3)**: scoped pytest green; `git commit`.

### Task 7: Test seam migration — the eight `CONFIG_PATH` files (integration tests)

<Context: the final test-tree task. Eight files still patch the deleted
`goga_tool_pybuggy.config.storage.CONFIG_PATH` attribute (~107 occurrences —
`monkeypatch.setattr` on it now raises `AttributeError`). In every one: delete the
`CONFIG_PATH_ATTR` constant and each `monkeypatch.setattr(CONFIG_PATH_ATTR, ...)` line, and
write the config at the standard relative path `pathlib.Path(".goga/tools/pybuggy/config.yml")`
(parent directories created) instead — each of these tests already runs
`monkeypatch.chdir(tmp_path)` or `runner.isolated_filesystem()`, so the relative write lands
under the test's own root and the real path composition (`<cwd>/.goga/tools/pybuggy/
config.yml`) is exercised. Adapt each file's `_write_config` helper (or equivalent) to write
the standard relative path and return it; no assertion changes — the commands' observable
behavior is identical. The complete set (grep-verified; a missed file fails loudly at
collection/run with `AttributeError`): `tests/test_cli_integration.py`,
`tests/test_cli_env.py`, `tests/commands/pull/test_pull.py`,
`tests/commands/diff/test_diff.py`, `tests/commands/diff/test_diff_integration.py`,
`tests/commands/info/test_info.py`, `tests/commands/list/test_list.py`,
`tests/commands/generate/test_generate.py`. This task closes the known-red window and
restores the full acceptance gate.>

**Usages relevant to this task:**
- `conventions`: CLI tests invoke handlers/runners directly (unchanged); file I/O via the
  isolated/chdir'd tree; `pytest tests/ -x` is the full gate.
- `goga-tool-config`: the standard `.goga/tools/pybuggy/config.yml` location the migrated
  writes must produce.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Migrate `tests/test_cli_integration.py` and `tests/test_cli_env.py` (delete
      `CONFIG_PATH_ATTR` + every `monkeypatch.setattr(CONFIG_PATH_ATTR, ...)`; write the
      standard relative path inside the existing isolated filesystems).
- [ ] Migrate `tests/commands/pull/test_pull.py`, `tests/commands/diff/test_diff.py`,
      `tests/commands/diff/test_diff_integration.py`, `tests/commands/info/test_info.py`,
      `tests/commands/list/test_list.py`, `tests/commands/generate/test_generate.py`
      (same pattern; per-file `_write_config` helper adapted to the standard path).
- [ ] Verify no stragglers: `grep -rn "CONFIG_PATH" tests/ goga_tool_pybuggy/` → zero hits.
- [ ] REPL cycle (M4): spot-drive one migrated command handler in the REPL against a
      chdir'd scratch tree with the standard config path before trusting the suite.
- [ ] Run validation (full gate): `.venv/bin/pytest tests/ -x` — **entire suite green**;
      `.venv/bin/goga lint` → 19 cells, 0 errors.
- [ ] **Lint**: `.venv/bin/ruff format goga_tool_pybuggy/ tests/` then
      `.venv/bin/ruff check goga_tool_pybuggy/ tests/`.
- [ ] **COMMIT GATE (M3.3)**: full pytest green; `git commit`.

### Task 8: Documentation — the autonomy sections (infrastructure)

<Context: the task's non-cell follow-ups. (1) `docs/pipelines/api-automate.md`: add an
"Autonomous runs" section — the `autonomous` axis entry of `.goga/tools/pybuggy/config.yml`
(the exact YAML shape), what it changes in the run (the seven-stage auto-approval window
ending at commit-changes, the `build` stage after it, the acceptance stage staying
interactive and manual), the silent no-op for every other pipeline and every disabled
state, and the fail-loud behavior of structural violations. (2) `docs/cli/init.md`: document
the `autonomous` confirm asked last (default no) and the conditional `pipelines` axis entry
it writes. Documentation is English, matches the existing sections' tone and structure, and
states only behaviors implemented by Tasks 1–7.>

**Usages relevant to this task:**
- `conventions`: project documentation style — match the existing sections of
  `docs/pipelines/api-automate.md` and `docs/cli/init.md`.
- `autonomy` (cell usage, content source): the axis shape and the disabled-state
  semantics.
- `contribution` (cell usage, content source): the window, the build entry, the no-op and
  precedence semantics.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Add the "Autonomous runs" section to `docs/pipelines/api-automate.md` (axis YAML
      example, enabled/disabled behavior, error behavior, `accept-result` interactivity
      note).
- [ ] Extend `docs/cli/init.md` with the `autonomous` confirm (asked last, default no) and
      the conditional axis entry in the written tool config.
- [ ] Verify consistency: every documented statement traces to an implemented behavior
      (Tasks 1–7); no forward references to unimplemented features.
- [ ] Run validation: `grep -c "Autonomous runs" docs/pipelines/api-automate.md` ≥ 1 and
      `grep -c "autonomous" docs/cli/init.md` ≥ 1; `.venv/bin/goga lint` still 19 cells,
      0 errors.
- [ ] **Lint** (where applicable — markdown is outside ruff scope; keep line lengths and
      formatting consistent with the neighboring sections).
- [ ] **COMMIT GATE (M3.3)**: `pytest tests/ -x` green (docs cannot break it — confirm);
      `git commit`.

---

## Validation Commands

All commands run inside the project virtualenv (create if missing per M1.2:
`python3 -m venv .venv && .venv/bin/pip install -e ".[test]"`).

- `.venv/bin/pytest tests/ -x`: Run all tests (the full acceptance gate — green from Task 7
  onward; before that, the per-task scoped gates in Tasks 2–6 declare the eight seam files
  as the known-red set)
- `.venv/bin/pytest tests/statuses/ tests/autonomous/ tests/config/ tests/commands/init/
  tests/test_reg_hooks.py tests/test_autonomy_integration.py -v`: Run every test tree
  created/rewritten by this plan
- `.venv/bin/ruff check goga_tool_pybuggy/ tests/`: Lint check (convention lint command,
  pyproject rule sets)
- `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/`: Formatter check (convention
  formatter config: py310, line-length 120, double quotes, LF)
- `.venv/bin/python -c "from goga_tool_pybuggy import register_hooks"`: Facade check — the
  platform import point (root facade)
- `.venv/bin/python -c "from goga_tool_pybuggy.statuses import register_automate_statuses,
  register_fix_statuses"`: Facade check — statuses cell
- `.venv/bin/python -c "from goga_tool_pybuggy.config import Config, GitEntry,
  PipelineAutonomy, SpecEntry, load_config, resolve_autonomy"`: Facade check — config cell
- `.venv/bin/python -c "from goga_tool_pybuggy.autonomous import amend_workflow,
  build_autonomous_workflow"`: Facade check — autonomous cell
- `.venv/bin/python -c "import goga_tool_pybuggy.config as c; assert 'CONFIG_PATH' not in
  vars(c) and 'CONFIG_PATH' not in c.__all__"`: The deleted seam stays dead
- `grep -rn "CONFIG_PATH" tests/ goga_tool_pybuggy/ || true`: Zero hits after Task 7
- `.venv/bin/goga lint`: 19 cells, 0 errors (contract-tree health)
- `.venv/bin/goga schema`: the two new cells and the two new root dependency edges resolve

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`:
      `statuses/{automate,fix,__init__}.py`, `config/{pipeline_autonomy,storage,__init__}.py`,
      `autonomous/{amendment,workflow,__init__}.py`, root `reg_hooks.py`, and the two
      `commands/init/session.py` edits
- [ ] Every contract entity is accessible from its facade (statuses, config, autonomous,
      root — including `register_hooks` on the package root)
- [ ] Properties and methods match the declared API (`PipelineAutonomy.autonomous -> bool`;
      the no-arg `load_config`; `resolve_autonomy(pipeline: str) -> bool`)
- [ ] Descriptions are reflected in behavior: the five-step amendment algorithm (identity
      gate first), the whole-axis validation with pybuggy-naming errors, the exact
      workflow constants (script string verbatim), the conditional axis emission, the
      confirm asked last defaulting to disabled
- [ ] Contract dependencies are met: `amend_workflow` uses `resolve_autonomy` via
      `from ..config import resolve_autonomy`; the root imports the statuses and autonomous
      types and consumes the `registration`/`contribution` practices
- [ ] Re-exports are accessible from the facade (`install` unchanged)
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification →
      logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding
      task; the designed matrices (disabled states, structural violations, record
      rejections) are parametrized tables including every boundary
- [ ] Integration tests exist for the cross-cell chains (`tests/test_autonomy_integration.py`)
- [ ] No package boundary was expanded (no new cells, no new facades beyond the declared
      ones, no changes to out-of-scope files: `pipelines/api.automate.yml`, stage skills,
      `accept-result`, the goga platform, the five command cells' CODEMANIFESTs,
      `pyproject.toml` dependencies)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass — in particular `pytest tests/ -x` fully green, both
      ruff commands clean, every facade probe resolves, `goga lint` 19 cells 0 errors
- [ ] Every Usages entry is mentioned in at least one task (`conventions`, `goga-statuses`,
      `goga-tool-config`, `goga-pipeline-hooks`, `goga-workflow-document`, `goga-compile-flow`,
      `goga-hooks`, `goga-onboarding-hooks`, imported `autonomy`/`registration`/
      `contribution`/`configuration`)
- [ ] The Mandatory Rules were enforced throughout: coding style per M1, test rules per M2,
      ruff lint+format at every task gate and every local commit per M3, and the REPL cycle
      (continuous evaluation, hot reloading, REPL→source migration, findings pinned as
      tests) per M4
- [ ] The arch.md checklist items concerning source behavior are re-verified: the
      `resolve_autonomy` matrix, the workflow vocabulary, the five subscriptions, the
      `statuses.py` absence, the `CONFIG_PATH` removal + full seam migration, and the
      question default / payload conditionality
