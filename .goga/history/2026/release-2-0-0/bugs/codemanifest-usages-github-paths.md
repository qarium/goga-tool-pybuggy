# Change Execution Report — CODEMANIFEST usages paths follow the github group rename

## Summary

The linter (`goga lint` / `goga schema`) failed with 8 `usage_filepath_exists` errors after
commit `221f2fb` renamed the usages dependency group `cooks` → `github` in `.goga/config.yml`.
The rename relocated 113 synchronized usage files from `.goga/usages/cooks/goga/` to
`.goga/usages/github/goga/` (pure rename, 0% content change), but 8 path references in two
CODEMANIFEST headers kept pointing at the old prefix. The fix updates the 8 path values to the
new prefix. No implementation code changed; the full test suite (970 tests) and all goga gates
(lint, schema, contract) pass after the fix.

## Root Cause

Commit `221f2fb` ("upd usages") renamed the config group `usages.cooks` → `usages.github`.
The sync mechanism deploys git dependencies into `.goga/usages/<group>/<dep>/`
(`sync-usages.md`), so all goga usages moved to `.goga/usages/github/goga/`. The two CODEMANIFEST
files below were not updated with the rename, leaving 8 dangling paths. Evidence chain:
lint output naming the exact missing paths; git history of the config rename; rename detection
showing 0 content change for all 113 files; presence of all 8 targets under the new prefix;
`goga usages status` exit 0 (tree up to date with remote `2.0.x`); no other live references
to the old prefix in the project.

## Modified Cells

| Cell | Files Modified |
|---|---|
| `goga_tool_pybuggy` | `goga_tool_pybuggy/CODEMANIFEST` |
| `goga_tool_pybuggy/commands/init` | `goga_tool_pybuggy/commands/init/CODEMANIFEST` |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| 3 path values | `goga_tool_pybuggy/CODEMANIFEST` | `goga-hooks`, `goga-statuses`, `goga-onboarding-hooks`: prefix `.goga/usages/cooks/goga/` → `.goga/usages/github/goga/` |
| 5 path values | `goga_tool_pybuggy/commands/init/CODEMANIFEST` | `goga-scaffold`, `goga-onboarding`, `goga-onboarding-hooks`, `goga-onboarding-questions`, `goga-onboarding-generator`: same prefix change |

## Tests Added

| Test | File | What It Validates |
|---|---|---|
| — | — | None required: spec-level path values only; behavior unchanged. The failing check itself (`usage_filepath_exists`) is the gate and now passes. |

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| `goga_tool_pybuggy` | `Usages:` header — 3 path values | none |
| `goga_tool_pybuggy/commands/init` | `Usages:` header — 5 path values | none |

## Validation Results

**VERIFIED.** `goga lint`: 17 cells / 0 errors (was 8). `goga schema`: parses cleanly.
`goga contract`: `{}` (no drift). `pytest`: 970 passed (10 pre-existing deprecation warnings,
unrelated — click `isolated_filesystem`). Residual `cooks/goga` references in code/tests: 0.

## Compatibility Status

**Compatible** — all compatibility-guard checklist items YES. No code changed; usage keys,
annotations, signatures, algorithms, and file guarantees preserved; the moved usage files are
byte-identical to the old ones (pure rename).

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Typo in a new path | low | all 8 targets verified to exist; `goga lint` is the final gate — green |
| Hidden consumers of old paths | low | full-project grep: only the 2 manifests (fixed) and the history archive (records, untouched) |
| Usages sync drift | none | `goga usages status` exit 0 — tree up to date with remote `2.0.x` |

## Updated Files

- goga_tool_pybuggy/CODEMANIFEST
- goga_tool_pybuggy/commands/init/CODEMANIFEST
- .goga/history/2026/release-2-0-0/bugs/codemanifest-usages-github-paths.md (this report)

## Attached Change Plan

Task Classification: **bugfix** (defect fix).

Affected Cells: `goga_tool_pybuggy` (3 lines), `goga_tool_pybuggy/commands/init` (5 lines).

Change Strategy:
1. Replace the `.goga/usages/cooks/goga/` prefix with `.goga/usages/github/goga/` in the 8
   `Usages:` entries of the two manifests.
2. Change nothing else: keys, annotations, signatures, footer untouched.
3. Verify with `goga lint` (0 errors), `goga schema` (clean AST), `pytest` (no regressions).

Compatibility Verification: backward compatible; breaking-change analysis — all six questions NO.

Test Strategy: no new tests (spec-only change); validation via lint/schema gates plus the
existing suite.

Risk Assessment: typo risk mitigated by existence checks and the lint gate; no hidden
consumers (grep-verified); no sync drift (status exit 0).

---

Author: Goga
CreatedAt: 02/10/26
Description: |
  Hotfix record — 8 CODEMANIFEST usage paths follow the usages group rename
  cooks → github after commit 221f2fb; linter restored to green.
