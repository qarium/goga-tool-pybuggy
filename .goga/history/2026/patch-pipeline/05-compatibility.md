# Compatibility Report — Patch cycle 2 (init autonomy for api.patch)

## Checklist Results

### API Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Function signature unchanged for existing callers? | **NO** | `survey_autonomy() -> bool` becomes `-> dict[str, bool]`; `build_config_data`'s `autonomous: bool = False` becomes `autonomous: dict[str, bool] \| None = None`. Both are cell-internal (init cell facade only); the sole caller `amend_pybuggy_config` is updated in the same change; neither is on the root facade |
| Return type unchanged? | **NO** | `survey_autonomy` returns per-axis answers; `build_config_data`'s enabling payload gains the `api.patch` record |
| Default parameter values preserved? | **NO** (literal) / YES (semantics) | `autonomous=False` → `autonomous=None`; both defaults write no `pipelines` key |

### Semantic Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Same arguments produce same behavior? | **NO** | The enabling path writes both axes (per-pipeline answers); `survey_autonomy()` asks two confirms instead of one |
| Output format unchanged? | **NO** (content) / YES (schema) | The `pipelines` mapping gains entries; the YAML shape stays the resolver-validated one (one boolean `autonomous` member per name) |
| File paths unchanged? | YES | Same `config.yml` through `context.write_config`; no path touched |
| Error messages and codes unchanged? | YES | No new failure paths; the numeric-coercion `ValueError` path is untouched |

### Algorithmic Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Manifest-defined algorithm steps preserved? | YES | `amend_pybuggy_config`'s 6-step order is untouched (specs → autonomy → amendments → write); the two reworded annotations evolve in-lockstep with the code per the cell convention (current state, not changelogs) |
| Execution order unchanged? | YES | Spec survey still completes before any autonomy question; the automate question keeps its position, the patch question follows it; payload key order `pipelines` before `specs` preserved |
| Side effects unchanged? | YES (in kind) | One extra confirm asked; one extra YAML entry per enabling answer; no other I/O |

### Consumer Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Existing tests pass without modification? | **NO** | Three suites pin the old prompt/payload/types (test_session.py signature tables + TestSurveyAutonomy + TestBuildConfigData; test_init_integration.py confirm tables; test_autonomy_integration.py bridge) — updated by this change |
| Usage recipes remain valid? | YES | `config/.usages/autonomy.md` (per-name axis) and `configuration.md` remain accurate unchanged |
| Downstream consumers unaffected? | YES | `resolve_autonomy`, `amend_workflow`, `CONTRIBUTIONS`, automate's window/build — untouched and stay green; existing project configs are never rewritten (the session refuses an existing `.goga/config.yml` before any tool moment) |

## Verdict

**BREAKING** — failed boxes: API signature, API return type, API default literal, same-args
behavior, output content, existing tests.

## Breaking Change Details

Per the STOP rule the pipeline halts here absent an override. The override exists and is
explicit:

1. **q1 (task)** — the user requested this exact behavior change, specifying the target
   config verbatim (`pipelines: {api.automate: autonomous: true, api.patch:
   autonomous: true}`).
2. **q2 (design approval)** — the plan presented the breaking assessment in full ("По
   букве политики goga-change это breaking: build_config_data(...) начинает писать
   дополнительную запись, текст вопроса меняется, 3 теста-пина обновляются… ваш мандат
   и есть override STOP-а политики") and the user approved with a design refinement:
   separate per-pipeline confirms ("надо по отдельности спрашивать про оба пайплайна").
   The per-pipeline answers require a per-axis carrier, which mechanically entails the
   `survey_autonomy` return-type and `build_config_data` parameter-type changes — the
   direct consequence of the user's instruction, same files, same functions.

Blast radius: fresh onboarding trees only; existing projects, existing configs, automate
behavior, and every downstream consumer are provably untouched (checkbox evidence above).
The pipeline proceeds to implementation under the user's override.
