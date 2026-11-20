# Compatibility Report

| # | Question | Answer | Notes |
|---|---|---|---|
| 1 | Existing function call with same arguments produces different behavior? | ☐ NO ☐ YES → **NO** | No runtime code modified |
| 2 | Existing file paths change? | **NO** | Files edited in place |
| 3 | Output format change? | **NO** | CLI formats unchanged; diagnostic content reflects corrected declarations (task goal) |
| 4 | Return value semantics change? | **NO** | No signatures touched |
| 5 | Manifest-defined guarantees altered? | **YES** | Declared contract surface of three manifests shrinks (7 declarations removed, 1 embedding added) |
| 6 | Existing tests break? | **NO** | No test reads manifests; code and facades untouched; suite re-run green |

## Verdict

**BREAKING CHANGE** (question 5). Pipeline STOP executed at Step 2; escalation report written
(`breaking-escalation.md`).

## User Override

Authorized by the user in this run (question q2, option A): proceed with the manifest-side
reconciliation — remove the seven internal-type declarations, add the `->allow_failure: {}`
embedding, de-link the orphaned references. Rationale accepted: the manifests themselves record the
internal-by-design intent; facades and runtime stay byte-identical; behavioral documentation remains
in code docstrings and prose annotations.
