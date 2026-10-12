# Change Execution Report — init downloads sandbox usages into a subdirectory

Executed 12/10/2026 via the goga-change pipeline (scope → investigation → plan → compatibility
guard → implementation → testing → manifest/usage reconciliation → drift analysis → validation).

## Summary

The `pybuggy init` bootstrap now distributes the four sandbox capability usage files into their
own subdirectory — `.goga/usages/cooks/pybuggy/sandbox/` (`sandbox-session.md`, `sandbox-file.md`,
`data-operations.md`, `migration-set.md`) — while the api usages (`api.md`, `asserts.md`) stay
flat under `.goga/usages/cooks/pybuggy/`. The config registration split is unchanged: only the
api-root keys (`pybuggy-api`, `pybuggy-asserts`) plus `conventions` are registered; the sandbox
usages remain download-only. The destination change is a deliberate, user-approved breaking
change; flat copies left by earlier distributions are never migrated or removed (user decision,
pinned by a manifest constraint and a test).

## Root Cause

Not a defect — a requested contract change. The copy loop of `run_bootstrap` computed one flat
destination for every discovered stem, and the discovery result carried no per-root information,
so a subdirectory layout was impossible without changing the discovery payload.

## Modified Cells

| Cell | Files Modified |
|---|---|
| goga_tool_pybuggy/commands/init | init.py, CODEMANIFEST, .usages/init.md |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| Per-root destination subdirectory | goga_tool_pybuggy/commands/init/init.py | `_USAGE_ROOTS` pairs each root with its destination subdir (api → flat, sandbox → `sandbox`); `_discover_packaged_usages` returns `(stem, text, subdir)` triples; the copy loop writes `pybuggy/[sandbox/]<stem>.md` |
| Algorithm step 2 / Requirement / Constraint | goga_tool_pybuggy/commands/init/CODEMANIFEST | per-root destinations in the `run_bootstrap` algorithm; the sandbox guarantee restated as its own distribution path; new no-migration constraint |
| Artifact table split | goga_tool_pybuggy/commands/init/.usages/init.md | two destination rows (flat api, `sandbox/`) with the stale-copy note |
| Docs | docs/cli/init.md, docs/getting-started.md | artifact tables split; roots listing and the download-only note carry the `sandbox/` path |

## Tests Added

| Test | File | What It Validates |
|---|---|---|
| test_bootstrap_keeps_a_stale_flat_sandbox_copy | tests/commands/init/test_bootstrap.py | a flat copy from an earlier distribution survives; the fresh copy lands in `sandbox/` |

Updated destination assertions: test_bootstrap.py (layout, byte-identity, template/bare gates at
the new path), test_init.py (full-pass existence), test_init_integration.py (smoke e2e split).

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| goga_tool_pybuggy/commands/init | `run_bootstrap`: Algorithm step 2 (per-root destinations), Requirements (sandbox subdirectory as its own distribution path), Constraints (no migration of flat copies) | `.usages/init.md` artifact table split into flat api and `sandbox/` rows |

## Validation Results

**VERIFIED** — 1717 passed / 18 skipped; `ruff check` and `ruff format --check` clean;
`goga lint` 24 cells 0 errors; init-cell facade imports; coverage of init.py 99% with all changed
lines covered; a scratch-project smoke run produced the exact requested tree.

## Compatibility Status

BREAKING (user-approved): the four sandbox usage files change their output path; five existing
tests were updated accordingly. API signatures, exit codes, log formats, config registration,
and the download-only semantics are unchanged. The override was recorded explicitly (escalation
question answered "A — proceed, no migration of old copies"; plan then approved).

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Stale flat copies persist next to `sandbox/` in older projects | low | accepted by the user; documented in the manifest constraint, usage note, and covered by a test |
| Packaged skills listing usages | low | already recursive ("recursively when subdirectories appear"); no skill references the four stems by name |

## Updated Files

- goga_tool_pybuggy/commands/init/init.py
- goga_tool_pybuggy/commands/init/CODEMANIFEST
- goga_tool_pybuggy/commands/init/.usages/init.md
- docs/cli/init.md
- docs/getting-started.md
- tests/commands/init/test_bootstrap.py
- tests/commands/init/test_init.py
- tests/commands/init/test_init_integration.py

---

# Change Plan (approved)

## Task Classification

feature — user-approved breaking adjustment of the init bootstrap distribution layout.

## Affected Cells

| Cell | Files to Modify | What Changes |
|---|---|---|
| goga_tool_pybuggy/commands/init | init.py | per-root subdir in discovery; copy loop destination |
| goga_tool_pybuggy/commands/init | CODEMANIFEST | Algorithm step 2, Requirement, new Constraint |
| goga_tool_pybuggy/commands/init | .usages/init.md | artifact table rows |
| — | docs/cli/init.md, docs/getting-started.md | artifact tables, preconditions |
| — | tests/commands/init/* | destination assertions + no-migration test |

## Change Strategy

1. init.py: `_USAGE_ROOTS` as (module, subdir) pairs; `_discover_packaged_usages` →
   `(stem, text, subdir)` triples; destination `pybuggy/[subdir/]<stem>.md`.
2. CODEMANIFEST: per-root destinations; sandbox = own distribution path; no-migration constraint.
3. `.usages/init.md`: two destination rows.
4. Docs: split tables, path notes.
5. Tests: update assertions; add stale-flat-copy survival test; run pytest, ruff, facade check.

## Test Strategy

Layout listing (flat = api.md + asserts.md + sandbox/), byte-identity at both destinations,
template skip / bare overwrite gates at the new path, no-migration, registration set unchanged,
idempotent rerun byte-identical, e2e smoke split.

## Risk Assessment

Stale copies remain (accepted); skills already recursive; triple consistency enforced by the
pipeline reconciliation steps.
