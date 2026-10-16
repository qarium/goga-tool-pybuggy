# Test Report

## Changes Requiring Coverage

| Change | Type |
|---|---|
| generate sanitizes the spec segment for `api/` and `tests/` trees | behavior |
| Generated dotted path importable for hyphenated spec names | behavior (the defect) |
| Leading-digit spec name → `_` prefix segment | edge |
| Spec-segment collision guard raises before writes | behavior + edge |
| diff locates the sanitized tree (no drift, no orphans) | behavior |
| Pre-fix raw hyphenated tree invisible to sanitized root (endpoints added, no orphan) | edge |
| list status mode locates the sanitized tree (OK) | behavior |
| Identifier spec names unchanged (all 1717 pre-existing tests) | regression |

## Tests Added

| Test Name | File | What It Validates |
|---|---|---|
| test_run_generate_hyphenated_spec_name_yields_importable_segment | tests/commands/generate/test_generate.py | `some-spec` → `api/some_spec/…`, `tests/some_spec/…`, markers, and `_module_is_pytest_plugin("api.some_spec.clients_startup_get.api")` — the import failure is gone |
| test_run_generate_leading_digit_spec_name_gets_underscore_prefix | tests/commands/generate/test_generate.py | `2shop` → `_2shop` segment |
| test_run_generate_spec_segment_collision_raises_before_writes | tests/commands/generate/test_generate.py | `some-spec` + `some_spec` → ClickException naming both; `api/`/`tests/` untouched |
| test_run_diff_reads_sanitized_spec_segment | tests/commands/diff/test_diff.py | hyphenated config + `api/some_spec/` artifacts → `{"clients_startup_get": {}}` only |
| test_run_diff_raw_hyphenated_tree_is_outside_the_sanitized_root | tests/commands/diff/test_diff.py | stale `api/some-spec/` tree: endpoint reported added (`values_changed` root), no orphan line |
| test_run_list_status_reads_sanitized_spec_segment | tests/commands/list/test_list.py | status `OK` for artifacts under the sanitized segment |
| test_run_list_status_raw_hyphenated_tree_reports_add | tests/commands/list/test_list.py | stale raw tree → `ADD`, no `REMOVED` |

## Test Results

| Test | Status | Details |
|---|---|---|
| Full suite | PASS | 1724 passed, 18 skipped (1717 pre-existing + 7 new) |
| ruff check (src + tests) | PASS | All checks passed |
| ruff format --check (changed files) | PASS | 6 files already formatted |

## Coverage Gaps

| Changed Behavior | Covered? | Notes |
|---|---|---|
| generate spec-segment sanitization (api + tests trees) | YES | hyphen + leading-digit tests |
| Importability of the generated dotted path | YES | `_module_is_pytest_plugin` assertion |
| Spec-segment collision guard | YES | message content + no-writes assertion |
| diff sanitized-root reads | YES | diff.py 100% line coverage in the run |
| list sanitized-root reads | YES | list.py 100% line coverage in the run |
| Identifier-name regression | YES | all pre-existing tests unmodified and green |

## Missing Coverage Analysis

generate.py lines 78 (JSON `TypeError` branch), 115 and 123 (ruff executable lookup fallbacks) remain uncovered — pre-existing gaps outside the changed behavior; not addressed to keep the diff within the approved scope. One behavioral note discovered and pinned by tests: pre-fix raw hyphenated trees are *invisible* to diff/list after the fix (they live outside the sanitized root) — endpoints report as ADD and stale directories are not listed as REMOVED; consumers must delete stale raw trees manually after regenerating.
