# Usage Reconciliation Report

## Classification

| Usage File | Classification |
|---|---|
| `autonomous/.usages/contribution.md` | INDIRECTLY AFFECTED — references the changed platform amendment moment |
| root `.usages/assembly.md` | INDIRECTLY AFFECTED — carries the hook subscription table incl. `pipeline/amend_workflow` |
| `config/.usages/configuration.md`, `config/.usages/autonomy.md` | INDIRECTLY AFFECTED — document the tool-config files the platform now `!ENV`-resolves |
| `web/.usages/pybuggy-web.md` | UNAFFECTED — references approve/workflow vocabulary only as consumer context |
| `statuses/.usages/registration.md`, `commands/init/.usages/*`, all other cell usages | UNAFFECTED — no reference into the sync's blast radius |
| `.goga/usages/github/goga/**` (the synced tree) | sync-managed — deployed verbatim by `goga usages sync -f`; kept as synced per the approved plan (no hand edits) |

## Updated Usages

| Usage File | Changes Made | Reason |
|---|---|---|
| none | — | No example, parameter description, or recipe in any pybuggy cell usage contradicts the 2.1 platform state; the approved plan explicitly excludes cell-usage edits |

## Verified Usages

| Usage File | Verified? | Notes |
|---|---|---|
| `autonomous/.usages/contribution.md` | YES | `amend_workflow` still a hard pipeline-domain checkpoint delivering the amendment view; the `PipelineIdentity.name` gate unchanged; the contributed `WorkflowDocument` (approve window + extend build stage, no template syntax) composes exactly as before; "authored wins per slot" still the platform's merge law |
| root `.usages/assembly.md` | YES | subscription table addresses (`statuses/register_statuses` ×4, `onboarding/declare_session`, `onboarding/amend_config`, `pipeline/amend_workflow`) all valid under the 2.1 platform |
| `config/.usages/configuration.md` | YES | schema doc unaffected; `!ENV` is platform-loader behavior documented by the platform's own bound practice (`goga-tool-config`), not pybuggy's consumer surface |
| `config/.usages/autonomy.md` | YES | the `pipelines` axis contract unchanged; strict pydantic validation of resolved values remains the documented pybuggy semantics |
| all twelve manifest-bound platform practices | YES | paths resolve; the four changed files carry additive/platform-side content only (see `03-investigation.md`) |

## Canonical Patterns Status

**Preserved.** Every canonical pattern — the subscription recipe
(`hooks.subscribe("pipeline", "amend_workflow", "autonomy", amend_workflow)`), the
contribution recipe (record → builder → `contribute`), and the config read recipe
(facade → pydantic validation) — is byte-identical and still valid under the 2.1 platform.

## Consistency Summary

**Consistent.** No usage-implementation inconsistency detected; no pybuggy usage file
required an update; `goga lint` (27 cells, 0 errors) confirms every CODEMANIFEST references
valid usages after the re-sync.
