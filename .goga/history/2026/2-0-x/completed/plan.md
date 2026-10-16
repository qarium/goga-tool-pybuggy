# Hotfix: init version pin — concrete major.minor → minor x-range

Flow: Bugfix (2026-10-16), stage: hotfix. Classification: bugfix (defect fix; breaking with recorded user override).

# Change Plan

## Task Classification
bugfix — the `pybuggy init` command records the pybuggy version pin in the concrete `major.minor` form
(`"2.0"`), which the host installer resolves to an exact pip pin (`==2.0`), freezing consumer projects at the
line's zeroth patch (2.0.0) while later patches ship. Fix: emit the minor x-range form (`"2.0.x"` → `~=2.0.0`).

## Affected Cells

| Cell | Files to Modify | What Changes |
|---|---|---|
| `goga_tool_pybuggy/commands/init` | `session.py`, `bootstrap.py`, `CODEMANIFEST`, `.usages/init.md`, `.usages/config-build.md` | Emit minor x-range pin in both writers; sync manifest + usages |
| docs (data) | `docs/cli/init.md`, `docs/getting-started.md` | Sync pin-form descriptions |
| tests | `tests/commands/init/{test_session,test_bootstrap,test_init,test_init_integration}.py` | Flip assertions to the new form; invert the repin test |

## Root Cause Analysis
Both pin derivations truncate the installed version to `major.minor` and emit it verbatim — the concrete host
grammar form — instead of the minor x-range form. Evidence: `session.py::_pybuggy_version_axis`,
`bootstrap.py::install_pybuggy`; host `goga/version/version.py::resolve_version` (concrete → `==form`;
`N.M.x` → `~={N}.{M}.0`); host `goga/commands/install/install.py::_resolve_pkg`. The x-range form was the
original `up-goga` design; the `feature-db-migration` patch "…-and-major-minor-pin" regressed it to the
concrete form.

## Trace Summary
`_pybuggy_version_axis` → `tools.pybuggy` in the generated consumer `.goga/config.yml`;
`install_pybuggy` → the Dockerfile `RUN goga install pybuggy -v <pin>` line; consumed externally by the host
`goga install` (bulk path reads `tools:`, single path reads `-v`).

## Change Strategy
1. Append `.x` to the derived line in both writers; docstrings state the x-range semantics.
2. `_INSTALL_LINE` comment: the concrete `-v 2.0` is now the previous shape that gets repinned in place
   (regex unchanged — it matches the command prefix).
3. Manifest/usages/docs — replace concrete-pin wording with the x-range form at each pinned-behavior statement.
4. Tests — expected values flipped; the repin test inverts (existing concrete line → repinned to x-range).
5. Repo-wide text search for stale mentions afterwards.

## Specification Impact
CODEMANIFEST annotations only (no signatures, imports, or structure): `build_config_amendments` Algorithm
step 3 + Requirements; `install_pybuggy` header + Algorithm step 3 + Requirements.

## Usage Impact
`.usages/init.md` (tools record + bootstrap table row), `.usages/config-build.md` (tools amendment),
`docs/cli/init.md` (two passages), `docs/getting-started.md` (table row).

## Compatibility Verification
Not backward compatible (generated content changes under identical inputs; 6 test assertions encoded the old
form). User override recorded (question q2, answer A, 2026-10-16). Rollout: existing consumer projects keep
their checked-in pins until a re-run of the bootstrap repins the line in place; fresh inits float immediately.

## Test Strategy
Updated existing derivation/idempotency/repin/merge/integration tests cover the new form end-to-end; the
integration regex tightened to `\d+\.\d+\.x`. No new tests needed — coverage is complete without duplication.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Stale doc/usage fragment missed | Medium | Low | repo-wide grep (done — clean) |
| Over-scope into the Docker image tag | Low | High | out of scope — registry tags float; `:2.0` already delivers goga 2.0.5 |
| Manifest/implementation drift | Low | Medium | reconciliation + `goga lint` (0 errors) |

---

# Change Execution Report

## Summary
The `pybuggy init` command pinned the pybuggy tool version in the concrete `major.minor` form in two generated
artifacts — the consumer `.goga/config.yml` (`tools.pybuggy: "2.0"`) and the Dockerfile install line
(`RUN goga install pybuggy -v 2.0`). The host installer resolves that form to an exact pip pin (`==2.0`),
freezing consumers at 2.0.0 forever. Both writers now emit the minor x-range form (`"2.0.x"` / `-v 2.0.x` →
pip `~=2.0.0`), floating within the installed major.minor line; manifest, usages, docs, and tests are
reconciled to the same semantics.

## Root Cause
Version-truncation to `major.minor` emitted verbatim — selecting the host grammar's concrete (exact-pin) form
instead of the minor x-range (floating) form. The regression was introduced by the
`feature-db-migration` patch "init-download-only-sandbox-usages-and-major-minor-pin"; the original `up-goga`
design had the x-range.

## Modified Cells

| Cell | Files Modified |
|---|---|
| `goga_tool_pybuggy/commands/init` | `session.py`, `bootstrap.py`, `CODEMANIFEST`, `.usages/init.md`, `.usages/config-build.md` |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| x-range tools record | `goga_tool_pybuggy/commands/init/session.py` | `_pybuggy_version_axis` returns `<N.M>.x`; docstrings updated |
| x-range install line | `goga_tool_pybuggy/commands/init/bootstrap.py` | `install_pybuggy` writes `-v <N.M>.x`; `_INSTALL_LINE` comment updated (concrete form is now the stale shape) |
| manifest sync | `goga_tool_pybuggy/commands/init/CODEMANIFEST` | 5 annotation passages state the x-range pin |
| usages sync | `.usages/init.md`, `.usages/config-build.md` | pin-form statements and examples |
| docs sync | `docs/cli/init.md`, `docs/getting-started.md` | pin-form statements and examples |
| test flip | 4 test files | expectations to the new form; repin test inverted |

## Tests Added
None — the updated existing suite fully covers the changed behavior (derivation, idempotency, repin of the
old shape, user-tools merge, `latest` fallback, orchestration, end-to-end artifacts).

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| `commands/init` | `build_config_amendments` step 3 + requirement; `install_pybuggy` header + step 3 + requirement → x-range | 2 cell usage files + 2 public doc pages |

## Validation Results
VERIFIED — full suite 1756 passed / 18 skipped (baseline parity); `ruff check` clean; `goga lint` 24 cells,
0 errors; triple consistency (manifest ↔ implementation ↔ usages) holds; repo-wide stale-mention search clean.
Pre-existing, out-of-scope: `ruff format --check` flags `docs/sandbox/api.md` (comment alignment in a code
block, present since the sandbox docs restructure) — recommended follow-up.

## Compatibility Status
BREAKING (generated config value + Dockerfile line text change; old-form tests replaced) — implemented under
the explicit user override recorded at plan approval. API signatures, return types, file paths, and error
semantics unchanged.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Consumer projects keep stale concrete pins until re-bootstrap | Low | repin-in-place on the next bootstrap run; documented in usages/docs |
| Pre-existing docs format-gate failure (sandbox/api.md) | Low | flagged as follow-up; not absorbed into this change |

## Updated Files
- docs/cli/init.md
- docs/getting-started.md
- goga_tool_pybuggy/commands/init/.usages/config-build.md
- goga_tool_pybuggy/commands/init/.usages/init.md
- goga_tool_pybuggy/commands/init/CODEMANIFEST
- goga_tool_pybuggy/commands/init/bootstrap.py
- goga_tool_pybuggy/commands/init/session.py
- tests/commands/init/test_bootstrap.py
- tests/commands/init/test_init.py
- tests/commands/init/test_init_integration.py
- tests/commands/init/test_session.py
