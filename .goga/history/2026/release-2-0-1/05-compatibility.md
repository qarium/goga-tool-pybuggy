# Compatibility Report

## Checklist Results

### API Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Function signature unchanged for existing callers? | YES | `run_generate`, `run_diff`, `run_list`, `sanitize_id`, `endpoint_statuses` signatures untouched; no new parameters |
| Return type unchanged? | YES | All handlers keep `None`; helpers keep their types |
| Default parameter values preserved? | YES | No defaults change anywhere |

### Semantic Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Same arguments produce same behavior? | **NO** | `run_generate("some-spec", …)` writes `api/some_spec/…` instead of `api/some-spec/…` (plan §Change Strategy 1); diff/list locate the sanitized tree |
| Output format unchanged? | YES | Formats identical; only path/values for non-identifier names differ |
| File paths unchanged? | **NO** | `api/<name>/…`, `tests/<name>/…` become sanitized for non-identifier spec names; identifier names unchanged |
| Error messages and codes unchanged? | YES | No existing message or exit code changes; one NEW error case is added (spec-segment collision) for input that previously silently mixed artifacts |

### Algorithmic Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Manifest-defined algorithm steps preserved? | **NO** | generate steps 7.1–7.6 and 6.5, diff step 7, list status-mode step are amended from raw `<name>` to the sanitized segment (plan §Specification Impact) |
| Execution order unchanged? | YES | Phase 1 validation → phase 2 writes preserved; the new collision check joins the existing pre-write validation block |
| Side effects unchanged? | **NO** | Write/read locations change for non-identifier spec names (the defect fix itself) |

### Consumer Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Existing tests pass without modification? | YES | No test uses a non-identifier spec name (`shop`, `client`, `t` verified); full-suite run scheduled at Step 6 |
| Usage recipes remain valid? | YES | All documented examples use identifier names; `run_generate(spec_name="shop", force=True)` etc. behave identically; generate.md/diff.md/list.md updated to also document the sanitization rule |
| Downstream consumers unaffected? | YES | Config key space, `--spec` filters, pull destinations, init flow, plugin loader contract unchanged; the plugin's `pytest_plugins` discovery keeps consuming `api/<spec>/<id>/api.py` — now importable for all names |

## Verdict

**BREAKING** — failed checkboxes: Semantic (same-args behavior, file paths), Algorithmic (manifest steps, side effects). Scope of every break: spec names that are not valid Python identifier segments only.

## Breaking Change Details

1. **Relocated artifact trees** — hyphenated (non-identifier) spec names now generate under `api/<sanitized>/…`, `tests/<sanitized>/…`; pre-fix trees become orphans surfaced by diff/list as REMOVED; consumers regenerate and delete stale dirs manually.
2. **Amended manifest algorithm text** — three CODEMANIFESTs document the sanitized segment; the importability guarantee is fulfilled, not weakened.
3. **New error path** — spec-segment collision raises `ClickException` where artifacts previously silently mixed.

**Standing user override:** the STOP for exactly this break scope was escalated (investigation, q2) and overridden by the user on 2026-10-13 — answer **A** (proceed: derivation-site sanitization, raw config keys, collision guard). The pipeline proceeds under that override; no new incompatibility beyond the overridden scope is introduced by the plan.
