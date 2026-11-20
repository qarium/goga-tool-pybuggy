# Compatibility Report

## Checklist Results

### API Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Function signature unchanged for existing callers? | YES | `install_pybuggy(dockerfile_path: Path)` and `install_playwright(dockerfile_path: Path)` keep their parameters and call sites (`run_bootstrap` steps 6/6c, init.py:399-403); only the contract's return *label* changes (`line` → `block`), the Python surface `str | None` is unchanged |
| Return type unchanged? | YES | `str | None` in both writers — the string now carries the 4-line block text instead of one line |
| Default parameter values preserved? | YES | no parameters carry defaults; nothing added or removed |

### Semantic Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Same arguments produce same behavior? | **NO** | same `dockerfile_path` input → the written artifact changes from the single `RUN goga install pybuggy -v <N.M>.x` line to the `USER root`/`COPY . /tmp/project`/`RUN cd /tmp/project && goga install && rm -rf /tmp/project`/`USER goga` block; `install_playwright` inserts at the root-section anchor instead of end-of-file (03-investigation.md #1) |
| Output format unchanged? | **NO** | generated Dockerfile content changes (03-investigation.md #1, #3) |
| File paths unchanged? | YES | the written artifact path (consumer Dockerfile via `_resolve_dockerfile_path`) and every usage/config path are unchanged |
| Error messages and codes unchanged? | **NO** | the `ValueError` on missing distribution metadata disappears with the removed version derivation (the `goga-tool-pybuggy distribution metadata not found` text); bootstrap INFO log texts change ("install block added/replaced"); the wrapped tier `(OSError, YAMLError, ValueError)` in `run_bootstrap` is unaffected — `install_playwright`/other writers still raise `ValueError` paths |

### Algorithmic Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Manifest-defined algorithm steps preserved? | **NO** | the `install_pybuggy` CODEMANIFEST algorithm (pin derivation, single-line write) is intentionally replaced by the block algorithm; `install_playwright` gains the anchor/relocate steps — the manifest moves in lockstep in the same change (04-change-plan.md §Specification Impact) |
| Execution order unchanged? | YES | `run_bootstrap` step order (6 → 6b/6c → 7 → 8 → 9) and the internal writer order (presence check → presence of prior install step → replace/append) are preserved |
| Side effects unchanged? | **NO** | the Dockerfile byte content a bootstrap produces changes (the defect being fixed) |

### Consumer Compatibility

| Question | Answer | Evidence |
|----------|--------|----------|
| Existing tests pass without modification? | **NO** | `TestInstallPybuggy` (5 tests), `test_init.py` install/playwright pins (7 assert sites), `test_init_integration.py` (2 sites) pin the single-line form and are rewritten by the plan |
| Usage recipes remain valid? | **NO** | `.usages/init.md` (row 107/108, mandatory-Dockerfile wording), `.usages/config-build.md` (x-range cross-reference), `docs/cli/init.md`, `docs/getting-started.md` describe the retired line form — all updated in lockstep |
| Downstream consumers unaffected? | YES | no other cell imports `install_pybuggy`/`install_playwright` (02-trace.md: no cross-cell traversals); the consumer-facing `tools:` record and every other delivered artifact are unchanged |

## Verdict

**BREAKING** — failed checkboxes: Semantic #1 (same arguments → different behavior), Semantic #2 (output
format), Semantic #4 (removed ValueError branch), Algorithmic #1 (manifest algorithm replaced),
Algorithmic #3 (artifact content), Consumer #1 (pinning tests), Consumer #2 (usage/docs mirrors).

## Breaking Change Details

Exactly the breaks enumerated in `breaking-escalation.md` (rows 1-6), detected at Step 2 and escalated
there. **User override**: q2 (2026-10-30), option A — approved proceeding ("Override да + playwright внутри
root-секции + убрать -v полностью"). The override is recorded in `breaking-escalation.md` and is cited here
as the authorization to pass this guard: the pipeline proceeds to implementation under the approved plan
(q3, 2026-10-30). Rollout remains staged per the project rule — existing consumer projects keep their prior
Dockerfile output until the next bootstrap re-run replaces the retired line shape with the block in place;
fresh initializations emit the block immediately.
