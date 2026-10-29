# Validation Report

## Scope Resolution

All modifications within the approved scope: `goga_tool_pybuggy/commands/init` (code `init.py`/`session.py`, CODEMANIFEST, both `.usages/` files), the mirror tests under `tests/commands/init/`, and the two doc mirrors (`docs/cli/init.md`, `docs/getting-started.md`). Excluded cells untouched: `web`, `config`, `plugin`, `api`, sandbox subtree, all other commands — `git status` confirms the 11 modified files all belong to the plan's "Affected Cells" table. The web cell required no code change (its `BrowserSettings` semantics already cover the runtime matrix).

## Task Resolution

All four reported defects eliminated and verified end-to-end on the real engine session + bootstrap:
- api-only no longer delivers `pybuggy-web.md` (reproduced before: delivered; after: absent);
- web-only no longer delivers `api.md`/`asserts.md` and no longer registers `pybuggy-api`/`pybuggy-asserts` (registration set is exactly `{pybuggy-web, conventions}`);
- the web questions state their purpose (provider line + per-model prompts, models still required — approved option A);
- the browser name is a choice of the five runtime-accepted names, so out-of-matrix input is rejected at the prompt instead of at test startup.

## Trace Consistency

The kind signals (engine-written `api.yml`/`web.yml`) now gate every kind-dependent step symmetrically — copy (step 2), api registration (step 7), web examples/registration/playwright (3b/6b/6c). Call/data flows otherwise unchanged; the trace graph of `02-trace.md` holds with the gates closed.

## Change Plan Compliance

Implementation matches the approved plan item-for-item (kind signals, gated copy with DEBUG logging, gated registration, option-A prompts, browser choice, lockstep contract surfaces, test rework). One addition inside the same contract: the `_kind_gated_roots` helper — required by the project complexity practice (C901), the file's established pattern. No unplanned behavioral change.

## Backward Compatibility

NOT backward compatible for identical inputs — exactly the escalated set (`breaking-escalation.md` rows 1–5): per-kind delivered files, per-kind config content, at-prompt browser rejection. Verdict recorded at Step 4; user override received (q2) and plan approved (q3). Routine signatures, exit codes, `web.yml` payload shape, and the session seam unchanged; previously initialized projects keep their files (nothing is removed on upgrade).

## Implementation Quality

- Full suite: **1973 passed, 21 skipped** (the 21 are the pre-existing web-runtime environment skips; an initial run showing 53 failures was environmental — ruff binary missing during that background run — and disappeared once ruff was installed).
- `ruff check goga_tool_pybuggy/ tests/` — All checks passed; `ruff format` clean on the touched trees.
- `goga lint` — 25 cells, 0 errors.
- No orphaned code: `_REGISTERED_USAGE_ROOTS`, `PYBUGGY_ANNOTATIONS`, `_register_web_kind` all still used; the retired wording sweep is empty.

## Test Coverage

Changed behavior covered in unit (three kind variants + no-config + corrupt-web edges), integration (both kinds through the real engine with scripted TTY), and regression (both-kind path, idempotence, template/bare gates). The only unasserted artifact is the per-absent-kind DEBUG log — log-only, no contract weight (documented in `06-tests.md`).

## Manifest Reconciliation

| Cell | Algorithms | Operational Flow | Guarantees | Practices | Status |
|---|---|---|---|---|---|
| `commands/init` | updated in lockstep (steps 1/2/7, `survey_web_config`) | kind-signal gating described symmetrically | old copy/registration guarantees replaced by the kind-gated ones | complexity practice honored via the extracted helper | CONSISTENT |
| `web` | unchanged | unchanged | unchanged | unchanged | CONSISTENT |

## Usage Reconciliation

| Usage | Classification | Validated | Status |
|---|---|---|---|
| `init.md` | DIRECTLY | YES | updated |
| `config-build.md` | DIRECTLY | YES | updated |
| `pybuggy-web.md` | INDIRECTLY | YES | no edit needed |
| docs/cli/init.md, docs/getting-started.md | mirrors | YES | re-synced |

## Drift Resolution

All introduced drift resolved (`09-drift.md`). One pre-existing out-of-scope inaccuracy flagged as a follow-up (`bootstrap.py` module docstring says "Six pure writers"; the facade pins nine) — deliberately untouched per the scope-governance rule.

## Template Completeness

| Skill | All Sections Filled? | Missing Sections |
|---|---|---|
| scope-resolver (`01-scope.md`) | YES | none |
| tracer (`02-trace.md`) | YES | none |
| investigator (`03-investigation.md`) | YES | none |
| breaking escalation (`breaking-escalation.md`) | YES (+ user override recorded) | none |
| planner (`04-change-plan.md`) | YES | none |
| compatibility-guard (`05-compatibility.md`) | YES | none |
| test-engineer (`06-tests.md`) | YES | none |
| manifest-reconciler (`07-manifests.md`) | YES | none |
| usage-reconciler (`08-usages.md`) | YES | none |
| drift-analyzer (`09-drift.md`) | YES | none |

## Blocking Issues

None.

## Overall Status

**VERIFIED** — every gate green, triple consistency holds for the affected cell, the change matches the approved plan and the user's breaking-change override, and the original defects are demonstrably eliminated.
