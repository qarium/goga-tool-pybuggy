# Change Plan (approved 2026-11-24) + Change Execution Report

## Task Classification

Type: **bugfix** (environment-consistency fix exposed by a dependency update) — plus the
task's requested operation `goga usages sync -f` (whose resulting file changes stayed in the
working tree and are committed together with this fix).

## Affected Cells

| Cell | Files to Modify | What Changes |
|------|----------------|--------------|
| none (no code cell is affected) | `pyproject.toml` | `[project.optional-dependencies].test`: bump `goga>=2.0.1,<2.1` → `goga>=2.1,<2.2` |
| — (sync result, no further edits) | `.goga/usages/github/goga/**` (25 modified + 18 new files from the sync) | kept as synced; no pybuggy-side usage edits required |

## Root Cause Analysis

The goga 2.1 platform update (2026-11-09, commit 2702d4d1: Dockerfile base
`qarium/goga-python-3.13:2.0` → `:2.1`, usages ref `2.0.x` → `2.1.x`) did not touch the
test-extra goga pin. The pin's own comment defines it as a mirror of the target-env runtime
dependency ("runtime dep of the target env (installed next to goga), needed here only to
import the package in tests"), so a fresh test environment resolved goga 2.0.5 while the
target platform is the 2.1 line — the test env no longer mirrored the environment pybuggy
actually runs on. No pybuggy code, contract, or usage change is required by the update
itself: every semantic delta in the re-synced practices is platform-side, additive, or
neutralized by pybuggy's template-free contribution.

## Trace Summary

Three flows carry the goga update into pybuggy — the autonomy contribution
(`amend_workflow` → `resolve_autonomy` → `build_autonomous_workflow` → `contribute`), the
config facade reads (`load_tool_config`), and the root hook registration (seven
subscriptions). All remain valid under 2.1; the only defect found on these paths was the
stale pin.

## Change Strategy

1. Edit `pyproject.toml` `[project.optional-dependencies].test`: replace `"goga>=2.0.1,<2.1"`
   with `"goga>=2.1,<2.2"` — one line, comment unchanged.
2. Keep the synced `.goga/usages/github/goga/**` exactly as `goga usages sync -f` deployed
   it — no hand edits.
3. Nothing else: no CODEMANIFEST edits, no cell `.usages` edits, no code edits, no new
   subscriptions, no adoption of new platform vocabulary.

## Specification Impact

None. No CODEMANIFEST section changes.

## Usage Impact

None beyond the sync itself; the ~21 new unbound practice files are optional platform
capabilities — not referenced by any manifest, not adopted.

## Compatibility Verification

Backward compatible (all twelve compatibility-guard checklist items YES).

## Test Strategy

No new tests — verification steps instead: fresh-venv resolution from the updated extras
(must auto-select 2.1.x), full suite, ruff, facade import, `goga lint`.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A future 2.1.x patch breaks an API pybuggy tests rely on | low | test-env only | the line pin mirrors the platform's own line contract; suite re-run validates the resolved version |
| Synced usages drift from the local platform | low | documentation-level only | local 2.1.2 platform verified to implement each documented behavior |
| Unbound new usage files invite scope creep | low | out-of-scope changes | explicitly excluded by this plan |

---

# Change Execution Report

## Summary

Executed the user's request: ran `goga usages sync -f` (the goga git dependency
`github/goga` at ref `2.1.x` carried many updates), which re-deployed the platform
practices into `.goga/usages/github/goga/` — 25 files changed content, 18 new files
appeared, nothing was removed, `cooks/` and the root `conventions.md` preserved, and all
twelve CODEMANIFEST-bound practice paths resolve. Then analyzed the pybuggy impact of the
goga update to a HIGH-confidence conclusion: **no pybuggy code, manifest, or usage change
is required** — every semantic delta in the re-synced practices is platform-side
(`!ENV` inside the facade loader), additive (18 pipeline actions, `profile` member, new
workflow vocabulary), or neutralized by pybuggy's template-free contribution (the
platform's intended `{{ }}` rendering behavior change composes it "exactly as before").
The single defect the update exposed — the `test` extra pinning goga to the 2.0 line
while the project runs on the 2.1 platform — was fixed with the approved one-line pin
bump.

## Root Cause

The 2026-11-09 platform move to goga 2.1 (Dockerfile base `:2.1`, usages ref `2.1.x`)
left `pyproject.toml`'s test-extra goga pin on the 2.0 line, so fresh test environments
resolved goga 2.0.5 instead of mirroring the target env — contradicting the pin entry's
own stated purpose. Evidence chain: pyproject comment → Dockerfile base `:2.1` → usages
ref `2.1.x` → local platform 2.1.2 → PyPI line head 2.1.4 → suite green across
2.1.0/2.1.2/2.1.4.

## Modified Cells

| Cell | Files Modified |
|---|---|
| none (no code cell modified) | `pyproject.toml` (packaging metadata, not a cell) |
| — sync-managed tree | `.goga/usages/github/goga/**` (deployed by `goga usages sync -f`) |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| Test-env pin bump | `pyproject.toml` | `[project.optional-dependencies].test`: `goga>=2.0.1,<2.1` → `goga>=2.1,<2.2` — the test env mirrors the 2.1 target platform again |
| Usages re-sync | `.goga/usages/github/goga/**` | `goga usages sync -f` (exit 0) deployed the 2.1.x head (`32d25c6`) practices: 25 files modified, 18 new, 0 removed; `goga usages status` now clean |

## Tests Added

None (per the approved plan) — the pin is environment provisioning, verified at the
environment level: a fresh venv resolved from the updated extras auto-selects goga 2.1.4,
and the unmodified full suite passes inside it.

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| all 27 cells | none | none |

## Validation Results

**VERIFIED** — full suite 2152 passed, 21 environment-gated skips, 20 pre-existing
warnings (identical on goga 2.0.5, 2.1.0, 2.1.2, 2.1.4, and the fresh pin-resolved env);
`ruff check` clean; facade import OK; `goga lint` 27 cells, 0 errors; `goga usages status`
clean. Zero fix iterations during stabilization; scope exactly matches the approved plan.

## Compatibility Status

**COMPATIBLE** — all twelve compatibility-guard checklist items YES; no breaking change;
no escalation required.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Future 2.1.x patch breaks a tested platform API | low | line pin mirrors the platform's own line contract; suite re-run validates the resolved version |
| Synced practices vs local platform drift | low | local 2.1.2 platform verified to implement every documented behavior used |
| Scope creep via new platform capabilities | low | adoption explicitly out of scope; practices impose no obligations |

## Updated Files

- `.goga/usages/github/goga/**` — 25 modified + 18 new files (sync-deployed, verbatim)
- `pyproject.toml` — one line (test-extra goga pin)
- `.goga/history/2026/3-0-x/` — todo.md, 01-scope.md … 10-validation.md, completed/plan.md
  (this run's artifacts)
