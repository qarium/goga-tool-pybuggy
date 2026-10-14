# Add the `api.patch` pipeline for modifying existing tests

pybuggy ships `api.automate` (creates new tests end to end) and `api.fix` (repairs failing
suites), but there is no path for user-requested modification of already existing tests.
We decided to add a third pipeline, `api.patch` (`PybuggyApiPatch`,
`goga pipeline pybuggy:api.patch`): it is shaped like `api.automate` — document stages,
then test code rebuilt through ralphex (`goga build`) — minus testcase construction, and
its defining rule is that every change lands in the CODEMANIFEST and in the test code
together. The boundary with the neighbors is by intent, not by test color: automate writes
new tests, fix repairs what broke, patch changes what the user asks to change — it may
start on red tests, and any failure it meets is surfaced to the user.

## Decisions

- **Patch categories (all in scope)**: replace a data fixture/tool and update its usage
  across tests; update/add/change asserts; add markers; re-bind tests between sandbox and
  target env; update Routine annotations; remove obsolete cases; update practices/usages
  references; structural moves of cells between specs.
- **Selection is intent-driven**: the user states the intent plus scope constraints
  (spec/directory/marker); the analysis stage builds the affected-cells dossier for
  review. Several intents per run are allowed — each becomes its own section in
  `intent.md` and its own group in the dossier and the plan.
- **Stage chain (10 stages)**: `collect-intent` (communication; also fixes the topic
  version — spec ref + base URL, as `api.fix` does) → `analyze-impact` (communication)
  → `review-impact` (communication) → `apply-manifests` (silent — writes the manifest
  deltas) → `code-design` (communication) → `design-review` (communication) →
  `coding-plan` (communication) → `plan-review` (communication) → `commit-changes`
  (communication) → `accept-result` (manual trigger: consistency check, final full run,
  triage with the user, `bugs.md`).
- **Artifacts** — unique names without a `patch-` prefix, not colliding with the automate
  and fix chains: `intent.md`, `impact.md`, `apply.md` (report of changed CODEMANIFESTs),
  `rework.md`, `workplan.md`, `accept.md`, `accept-log.txt`; `bugs.md` is shared.
  Repeated patch cycles in the same topic overwrite the chain (latest cycle wins;
  history stays in git).
- **Status line** — registered without the tool prefix (the platform qualifies it as
  `pybuggy.*`): `patch.intended` → `patch.analyzed` → `patch.applied` → `patch.designed`
  → `patch.planned` → `patch.done` (filepath `completed/workplan.md`). An independent
  chain anchored at the built-in `empty`, like the fix line — it never reorders the
  automate line. Registered by a new `register_patch_statuses` routine in the statuses
  cell.
- **Build** — same as automate: in the interactive mode the user runs `goga build` on
  `workplan.md` after `plan-review`; the autonomous contribution appends a `build` stage
  after `commit-changes`. Verification is mandatory: pytest in the plan's Validation
  Commands per task, plus the final full-suite run at `accept-result`.
- **Accept contract** — `accept-result` never depends on the plan artifact: a successful
  `goga build` relocates `workplan.md` to `completed/workplan.md`, so the acceptance gates
  on the apply report (`apply.md`) and verifies the manifest ↔ test-code togetherness
  against it — the same shape as automate's accept, which gates on `testcases.md` and
  never on the relocated `plan.md`.
- **Deletions** — a removed Routine or cell produces deletion tasks inside the ralphex
  plan ("delete this test / these tests in that file"); `apply-manifests` only edits
  manifests.
- **Autonomy** — opt-in via `pipelines: api.patch: autonomous: true` in the tool config;
  the auto-approval window spans `review-impact` … `commit-changes` (everything after the
  user confirms the dossier), the build contribution follows commit, and `accept-result`
  is never auto-approved.
- **Out of scope** — regeneration of the generated `api/` client modules: patch intents
  are test-level; a spec-level change goes through `pull`/`generate` outside the pipeline.

## Consequences

- The fix-line edit invariants are inverted for patch: executors may edit CODEMANIFESTs
  and delete Routines — every task records its changed files.
- Conventions follow the existing pipelines: `goga_tool_pybuggy/pipelines/api.patch.yml`,
  skills `goga-tool-pybuggy-api-patch-*` under `goga_tool_pybuggy/skills/`, docs
  `docs/pipelines/api-patch.md` plus an `index.md` update.
