# Trace Report

## Call Flow

The goga update reaches pybuggy through three traced flows:

```
flow A — autonomy contribution (autonomous cell)
  platform run_pipeline
    → hooks platform: pipeline/amend_workflow (hard checkpoint)
      → goga_tool_pybuggy.reg_hooks.register_hooks  [subscribed: ("pipeline","amend_workflow","autonomy")]
        → goga_tool_pybuggy.autonomous.amendment.amend_workflow(context)
          → context.pipeline.name  → match against CONTRIBUTIONS (3 records)
          → goga_tool_pybuggy.config.storage.resolve_autonomy(axis, config_file)
              → goga.config.load_tool_config("pybuggy", api.yml|web.yml)   [platform facade]
          → goga_tool_pybuggy.autonomous.workflow.build_autonomous_workflow(contribution)
              → goga.pipeline.workflow.{WorkflowDocument, WorkflowStage, WorkflowExtendStage}  [call-time import]
          → context.contribute(document)
      → platform: render_contribution(document, profile context)   [NEW in 2.1]
      → platform: merge (authored wins per slot) → compile → run

flow B — config reads (config cell)
  goga_tool_pybuggy.config.storage.load_config / resolve_autonomy
    → goga.config.load_tool_config  [platform facade; !ENV resolution inside the platform loader]
      → raw mapping → pydantic Config / PipelineAutonomy validation

flow C — hook registration (root cell)
  platform → goga_tool_pybuggy.reg_hooks.register_hooks(hooks)
    → hooks.subscribe ×7:
       ("statuses","register_statuses","api.automate"|"web.automate"|"api.fix"|"api.patch")
       ("onboarding","declare_session","declare"), ("onboarding","amend_config","amend")
       ("pipeline","amend_workflow","autonomy")
```

## Data Flow

- Flow A: `PipelineIdentity.name` (string) → record match → axis + config_file (strings) →
  facade read → `bool` enabled → `WorkflowDocument(stages={name: WorkflowStage(approve="auto")},
  extend={"build": WorkflowExtendStage(after=[window[-1]], body={title, script, after_script,
  timeout})})` → platform render → merge → compile. The contributed strings are
  `"Build tests"`, `python3 -P -m goga.build "$(python3 -m goga history path -f <artifact>)"`,
  `rm -rf .ralphex`, `"8h"` — none carries `{{ }}` template syntax.
- Flow B: YAML file bytes → platform `!ENV`-aware loader (2.1: `!ENV NAME` → process-env string,
  unset → `""`) → mapping → pydantic models (pybuggy applies its own semantics to resolved strings).
- Flow C: subscription tuples — all seven addresses exist in the 2.1 platform (statuses and
  onboarding domains unchanged; pipeline domain extended from 3 to 18 actions, `amend_workflow`
  among them, its view gaining the additive `profile` member).

## Manifest Algorithm Mapping

| Manifest step | Code path | Status |
|---|---|---|
| root `register_hooks` 7 subscriptions | `reg_hooks.py:24-36` | matches; all addresses valid in 2.1 |
| `amend_workflow` steps 1-5 | `autonomous/amendment.py:24-36` | matches; `context.pipeline` + `.name` still the documented members |
| `build_autonomous_workflow` steps 1-3 | `autonomous/workflow.py:40-52` | matches; `approve`, extend `title`/`script`/`after_script`/`timeout` all still-valid vocabulary |
| `load_config` steps 1-3 | `config/storage.py:14-37` | matches; facade call unchanged, `!ENV` resolves inside the platform |
| `resolve_autonomy` steps 1-4 | `config/storage.py:40-89` | matches; strict pydantic validation of resolved values is pybuggy's own semantics |
| init cell flows (session/bootstrap) | `commands/init/*` | bound usages (scaffold/onboarding) unchanged by the sync |

## Cross-Cell Traversals

| Source Cell | Target Cell | Type | Path |
|---|---|---|---|
| root | autonomous | call | `reg_hooks.py` → `amend_workflow` |
| root | statuses / commands.init | call | `reg_hooks.py` → the other six subscriptions |
| autonomous | config | call | `amendment.py` → `resolve_autonomy` |
| autonomous | goga (platform) | data | `WorkflowDocument` construction + `context.contribute` |
| config | goga (platform) | data | `load_tool_config` facade reads |
| commands.init | goga (platform) | data | onboarding engine session, scaffold engine, `host_goga_version()` (dynamic — no stale pin) |

## Inconsistencies

| Type | Location | Expected | Actual |
|---|---|---|---|
| Stale environment pin | `pyproject.toml` `[project.optional-dependencies].test` | `goga` on the target-env line (2.1) per the entry's own comment ("runtime dep of the target env … needed here only to import the package in tests") | `goga>=2.0.1,<2.1` — resolves to 2.0.5 while the target env is 2.1 (Dockerfile `qarium/goga-python-3.13:2.1`, usages ref `2.1.x`, local platform 2.1.2) |
| Manifest ↔ code wording | `autonomous/CODEMANIFEST` `amend_workflow` step 1 ("Read the identity … from `context`") | — | Code reads `context.pipeline` — the documented member name; wording drift only, no behavioral mismatch |

No code/manifest behavioral inconsistencies detected. No circular dependencies. All traced paths resolve.

## Trace Graph

```
goga 2.1 platform ──usages sync──▶ .goga/usages/github/goga/  (25 files changed, 18 new, 0 removed)
        │
        ├─!ENV loader (additive) ─────▶ config cell: transparent (facade reads)
        ├─18 pipeline actions (additive) ▶ root reg_hooks: subscribes 1 of them (unchanged address)
        ├─profile member (additive) ──▶ amendment.py: unread, no impact
        ├─{{ }} rendering (behavior change) ▶ workflow.py contribution: no template syntax → composes as before
        └─vocabulary growth (additive) ─▶ workflow.py uses approve/extend(title,script,after_script,timeout): all valid

pyproject.toml test pin (2.0 line) ──stale──▶ target env is 2.1 line  ⟹ THE required change
```
