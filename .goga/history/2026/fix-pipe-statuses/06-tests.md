# Test Report

## Changes Requiring Coverage

| Change | Type |
|---|---|
| `automate.code-designed` anchor corrected to `designed` — the four dropped statuses now register | behavior |
| Full scale assembly of the three lines against the real platform axis (zero skips) | regression |
| Any future anchor naming a nonexistent status must fail the suite | manifest |

## Tests Added

| Test Name | File | What It Validates |
|---|---|---|
| `TestScaleAssembly.test_three_lines_place_completely_in_normative_order` | `tests/statuses/test_scale_assembly.py` | All 17 pybuggy registrations resolve through the platform's own `_placement_index` over the real `_BUILTIN_AXIS`; the assembled scale equals the 26-entry normative order (9 built-ins + 17 tool statuses). A dead anchor raises instead of being skipped. |
| `TestScaleAssembly.test_public_assembly_registers_all_pybuggy_statuses_without_warnings` | `tests/statuses/test_scale_assembly.py` | End-to-end public `assemble_status_scale()`: every qualified pybuggy status present, and no `skipping status registration` record logged (skipif pybuggy is not an installed distribution). |

## Test Results

| Test | Status | Details |
|---|---|---|
| `tests/statuses/` (11 tests incl. 2 new) | PASS | 3.5–4.3 s, clean |
| Full suite `pytest tests/ -x` | PASS | 1758 passed, 18 skipped (pre-existing environment-gated skips), 10 pre-existing deprecation warnings |
| `ruff check` on touched code/tests | PASS | All checks passed |
| `ruff format --check` on the new test | PASS | formatted |
| Real-environment reproduction after fix | PASS | 17 pybuggy statuses in the assembled scale, 0 warnings (was 4 warnings, 13 statuses) |
| `goga lint` | PASS | cells: 24, errors: 0 |

Note: the plan text said "24-entry scale"; the observed and asserted total is **26** (9 built-ins + 17 pybuggy) — plan corrected to the observed value; scope unchanged.

## Coverage Gaps

| Changed Behavior | Covered? | Notes |
|---|---|---|
| Corrected anchor registers successfully | Yes | Both new tests + real reproduction |
| Cascade failure cannot recur silently | Yes | Placement test raises on any unresolvable anchor |
| End-to-end platform enumeration | Yes | Public-assembly test (skipif-guarded for non-installed environments) |
| Updated literal expectation in the call-order guard | Yes | `test_automate.py` updated with the fix |

## Missing Coverage Analysis

Nothing changed is left untested. The pre-existing suite's blind spot — anchors never resolved
against the real axis — is closed by `test_scale_assembly.py`. The literal call-order tests
(`test_automate/fix/patch.py`) remain as pure unit guards and stay green unmodified except the
one approved anchor tuple.
