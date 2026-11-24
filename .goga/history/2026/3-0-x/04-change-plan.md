# Change Plan

## Task Classification

Type: **bugfix** (environment-consistency fix exposed by a dependency update) — plus the
already-executed `goga usages sync -f` (the task's requested operation, whose resulting
file changes stay in the working tree and are committed together with this fix).

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
import the package in tests"), so a fresh test environment resolves goga 2.0.5 while the
target platform is the 2.1 line — the test env no longer mirrors the environment pybuggy
actually runs on. No pybuggy code, contract, or usage change is required by the update
itself: every semantic delta in the re-synced practices is platform-side, additive, or
neutralized by pybuggy's template-free contribution (see `03-investigation.md`).

## Trace Summary

Three flows carry the goga update into pybuggy — the autonomy contribution
(`amend_workflow` → `resolve_autonomy` → `build_autonomous_workflow` → `contribute`),
the config facade reads (`load_tool_config`), and the root hook registration (seven
subscriptions). All remain valid under 2.1; the only defect found on these paths is the
stale pin (see `02-trace.md` inconsistencies table).

## Change Strategy

1. Edit `pyproject.toml` `[project.optional-dependencies].test`: replace `"goga>=2.0.1,<2.1"`
   with `"goga>=2.1,<2.2"` — one line, comment unchanged (it still describes the intent).
2. Keep the synced `.goga/usages/github/goga/**` exactly as `goga usages sync -f` deployed
   it — no hand edits (the manifest-referenced twelve paths all resolve; the sync is
   authoritative).
3. Nothing else: no CODEMANIFEST edits, no cell `.usages` edits, no code edits, no new
   subscriptions, no adoption of new platform vocabulary (scope minimization).

## Specification Impact

None. No CODEMANIFEST section changes: the manifests' algorithms, signatures, and bound
practices remain valid under the re-synced usages (verified path-by-path in
`03-investigation.md`).

## Usage Impact

None beyond the sync itself. The twelve manifest-bound usage files resolve; the four that
changed content describe platform behavior that pybuggy already consumes correctly. The
~21 new unbound practice files are optional platform capabilities — not referenced by any
manifest, not adopted.

## Compatibility Verification

Backward compatible. The change alters only the test-environment dependency range; no
function signature, file path, output format, return semantics, or manifest guarantee
changes. Same-arguments behavior is identical — the full suite passes unchanged with goga
2.0.5, 2.1.0, 2.1.2, and 2.1.4 (2152 passed, 21 environment-gated skips in each run), so
both sides of the pin boundary are green.

## Test Strategy

No new tests — the pin bump is not a code behavior change, and the existing suite already
covers every platform-facing behavior. Verification steps instead:

1. Re-resolve the test environment from the updated extras in a fresh venv and confirm pip
   selects a 2.1.x goga (proves the pin resolves as intended, not just that a manually
   installed 2.1.x works).
2. Run the full suite in that environment (`pytest tests/`) — expect 2152 passed, 21 skipped.
3. `ruff check goga_tool_pybuggy/` — lint clean.
4. Facade check `python -c "import goga_tool_pybuggy"` and `goga lint` — 24 cells, 0 errors.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A future 2.1.x patch breaks an API pybuggy tests rely on | low | test-env only (target env floats on the same line regardless) | the line pin is exactly the platform's own line contract (`:2.1` image, `2.1.x` usages ref); suite re-run validates the resolved version |
| The synced usages drift from what the local platform implements | low | documentation-level only | local 2.1.2 platform verified to implement each documented behavior (profile member, template rendering, `!ENV`, bridge actions) |
| Unbound new usage files invite scope creep (adoption of new features) | low | out-of-scope changes | explicitly excluded by this plan; practices create no contractual obligations |
