# Usage Reconciliation Report — Patch cycle 2 (init autonomy for api.patch)

## Classification

| Usage File | Classification |
|---|---|
| `goga_tool_pybuggy/commands/init/.usages/config-build.md` | **DIRECTLY AFFECTED** — documents the autonomy confirm and the payload's `pipelines` entry |
| `goga_tool_pybuggy/commands/init/.usages/init.md` | **DIRECTLY AFFECTED** — documents the amend-moment follow-ups |
| `goga_tool_pybuggy/config/.usages/autonomy.md` | INDIRECTLY AFFECTED — the axis contract the new entries must satisfy |
| `goga_tool_pybuggy/autonomous/.usages/contribution.md` | INDIRECTLY AFFECTED — names both axes of the contribution records |
| `.goga/usages/conventions.md` (base) | UNAFFECTED (read-only base practice) |
| synced `.goga/usages/github/goga/**` | UNAFFECTED (managed by `goga usages sync`, read-only) |
| `statuses/.usages/registration.md`, `api/.usages/*`, sandbox usages | UNAFFECTED — no reference to the onboarding autonomy path |

Note: the scope report's assumption that the init cell carries no usage files was wrong —
the reconciler pass found `config-build.md` and `init.md`; both are updated here (the
investigation's "affected usages" analysis is corrected by this step).

## Updated Usages

| Usage File | Changes Made | Reason |
|---|---|---|
| `commands/init/.usages/config-build.md` | Domain sentence pluralized; the `autonomous` bullet now describes one confirm per pipeline (fixed order automate → patch, per-pipeline effect); the contribution bullet describes one record per accepted confirm with the section absent on all-declined; the programmatic note carries the mapping shape (axis → boolean, or None); the precondition states per-axis absence | The described behavior changed with the implementation |
| `commands/init/.usages/init.md` | The amend-moment follow-up passage names both prompts verbatim; the delivered-questions list pluralized | Same |

## Verified Usages

| Usage File | Verified? | Notes |
|---|---|---|
| `config/.usages/autonomy.md` | Yes | The contract is per-pipeline-name with a single boolean member — unchanged; the single-entry example remains a valid minimal recipe (same convention as `docs/configuration.md`); `resolve_autonomy("api.patch")` demonstrated against the real init payload by the bridge test |
| `autonomous/.usages/contribution.md` | Yes | Names both axes (`api.automate`, `api.patch`) and the silent-no-op contract — accurate before and after; the init change only adds a second way to enable the patch axis |
| base + synced usages | Yes | Untouched, still referenced correctly by the manifests |

## Canonical Patterns Status

**Preserved.** No recipe's structure changed — the two updated files keep their sections
and patterns; only the described facts evolved with the behavior. The canonical
consumer recipes (resolver call, subscription snippet, pure-builder testing note) are
byte-stable.

## Consistency Summary

**Consistent.** `goga lint`: 24 cells, 0 errors after the updates. Every usage file that
describes the onboarding autonomy path now matches the implementation; the contract
usages of the neighboring cells were verified accurate without modification.
