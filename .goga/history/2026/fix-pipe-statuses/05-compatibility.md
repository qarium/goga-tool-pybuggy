# Compatibility Report

## Checklist Results

### API Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Function signature unchanged for existing callers? | YES | `register_automate_statuses(context: object) -> None` untouched; only one anchor string value inside the routine body changes |
| Return type unchanged? | YES | Returns `None` as before |
| Default parameter values preserved? | YES | No parameters besides `context`; `register` call keeps both anchors as literal arguments |

### Semantic Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Same arguments produce same behavior? | NO | Identical call delivers six accepted registrations instead of two accepted + four skipped |
| Output format unchanged? | NO | `goga history status` for automate topics with `requirements.md`/`testcases.md`/`arch.md`/`design.md` reports `pybuggy.automate.*` names instead of built-in fallbacks; four warnings vanish from run logs |
| File paths unchanged? | YES | No registered artifact path, module path, or output file location changes |
| Error messages and codes unchanged? | YES | No error text produced by this package changes; the platform's skip warnings disappear because the skips disappear |

### Algorithmic Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Manifest-defined algorithm steps preserved? | YES | All six registrations, their order, artifacts, and the reverse-pipeline pattern are exactly as the contract mandates; the edit replaces an unsatisfiable anchor value that violated the contract's own Requirement line |
| Execution order unchanged? | YES | Registration order and platform processing order untouched |
| Side effects unchanged? | NO | Scale assembly gains four entries per run; downstream topic status resolution changes for automate topics |

### Consumer Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Existing tests pass without modification? | NO | `tests/statuses/test_automate.py` asserts the literal defective anchor and is updated as part of the approved plan |
| Usage recipes remain valid? | YES | Every usage example stays valid; `assembly.md` needs one table cell corrected (in plan); no recipe's steps or outcomes change beyond the fix |
| Downstream consumers unaffected? | NO | Automation filtering `goga history status` by built-in names stops matching automate topics at their next resolution |

## Verdict

BREAKING — failed checkboxes: Semantic (same-arguments behavior, output format),
Algorithmic (side effects), Consumer (existing tests, downstream consumers).

## Breaking Change Details

All failures share one cause: four statuses that were silently dropped now register, which is
the defect fix itself. The break was detected at Investigation (Step 2), escalated in
`breaking-escalation.md`, and **the user explicitly overrode the STOP and approved this exact
minimal scope** (answer q2, then plan approval q3). Per pipeline policy the user is the only
party entitled to override a breaking-change STOP; the override is recorded and the pipeline
proceeds to implementation. No stored or generated artifact carries the old form — the scale
is reassembled on every run, so the new form applies from the next pipeline run with no
migration surface.
