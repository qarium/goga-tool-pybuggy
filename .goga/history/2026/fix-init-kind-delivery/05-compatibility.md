# Compatibility Report

## Checklist Results

### API Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Function signature unchanged for existing callers? | YES | No facade routine changes; the only signature change is the private helper `_discover_packaged_usages` (underscore-private, no callers outside `init.py`, not in the 25-name facade, not manifest-declared) |
| Return type unchanged? | YES | All public routines keep their return types; `_discover_packaged_usages` keeps `(list, list)` with the roots now passed in |
| Default parameter values preserved? | YES | No parameter defaults change (`build_config_data`'s `autonomous=None` and every other default untouched) |

### Semantic Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Same arguments produce same behavior? | NO | `run_bootstrap(...)` over a web-only tree no longer registers `pybuggy-api`/`pybuggy-asserts` and no longer copies `api.md`/`asserts.md`; over an api-only tree it no longer copies `pybuggy-web.md`; `survey_web_config` rejects out-of-matrix browser names at the prompt and asks with new prompt texts (user-approved option A) |
| Output format unchanged? | NO | The consumer `.goga/config.yml` `codemanifest.usages`/`annotations` content differs per kind; the delivered file set under `.goga/usages/cooks/pybuggy/` differs per kind |
| File paths unchanged? | NO (delivered set) | The destination paths of what IS delivered are unchanged; the per-kind delivered set changes (escalation rows 1–2) |
| Error messages and codes unchanged? | YES | No routine's error text or exit code changes; the browser rejection is a new prompt-level choice validation (the user-facing improvement), not a changed message of an existing path |

### Algorithmic Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Manifest-defined algorithm steps preserved? | NO (deliberately revised) | The `run_bootstrap` steps 2 and 7 are revised to the kind-gated form and the Requirements rewritten — the manifest change is the requested fix, approved with the plan (q3); all other algorithm steps and their order are preserved |
| Execution order unchanged? | YES | The 10-step order stands; the gates only skip per-root work inside steps 2 and 7 |
| Side effects unchanged? | NO (delivered set) | Same class as the semantic row: fewer files/keys per non-selected kind; no new side effects |

### Consumer Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Existing tests pass without modification? | NO | The pinning tests named in the plan (`TestRunBootstrapUsages`, three `TestRunBootstrap` kind tests, the two `survey_web_config` tests, the two smoke assertions) are updated to the corrected contract — a planned, approved consequence |
| Usage recipes remain valid? | YES (recipes) with wording updates | The recipes' procedural content stays valid; the delivery-table and question-list wording changes document the new gates |
| Downstream consumers unaffected? | YES | In-repo grep: `register_usages`/`register_annotations`/`pybuggy-api` are referenced only by the bootstrap and its tests; `statuses.py` imports only `init_cmd`, `declare_pybuggy_session`, `amend_pybuggy_config` (signatures unchanged); externally initialized projects keep their existing files/registrations — nothing is removed on upgrade |

## Verdict

**BREAKING** — failed boxes: Semantic (same-arguments behavior, output format, file paths), Algorithmic (manifest algorithm revised), Consumer (existing tests modified).

## Breaking Change Details

Exactly the breaks enumerated in `breaking-escalation.md` (rows 1–5), already escalated at Step 2 and **explicitly overridden by the user** (q2, 2026-10-29: "Override подтверждаю"), with the plan approved (q3, 2026-10-29: "Утверждаю — выполнять как описано"). Per the pipeline's user-override rule, the STOP is discharged and implementation proceeds; no additional break beyond the escalated and approved set is introduced by the plan.
