# Init — per-pipeline autonomy confirms (Patch cycle 2)

> One document per the reporting contract: the approved Change Plan (cycle artifact
> `04-change-plan.md`, Option B as approved) followed by the Change Execution Report.

## Part I — Change Plan (approved)

Task classification: **feature** (extension of the onboarding autonomy opt-in to the
`api.patch` axis). User request: `autonomous_execution.q1` (Patch flow, 2026-10-15) —
the init command must ask about autonomous runs for `api.patch` the same way as for
`api.automate` and create the config entries. Design decision resolved at plan approval
(`autonomous_execution.q2`): **one confirm per pipeline** ("надо по отдельности
спрашивать про оба пайплайна") — automate first, patch after it, each default No, each
answer writing its own `pipelines` entry.

Affected cell: `goga_tool_pybuggy/commands/init` (`session.py`, `CODEMANIFEST`, two
`.usages` files). Unchanged neighbors: `config` (per-name axis contract already valid),
`autonomous` (both records already shipped), root, statuses. Full plan, trace,
investigation, and gate reports: cycle artifacts `01`–`10` in this topic directory.

## Part II — Change Execution Report

## Summary

The `pybuggy init` onboarding autonomy opt-in was extended to the `api.patch` pipeline:
the amendment moment now asks one autonomy confirm per pipeline — `Run the api.automate
pipeline unattended (autonomous mode)?` then `Run the api.patch pipeline unattended
(autonomous mode)?` — and each accepted confirm writes that pipeline's record
(`autonomous: true`) into the fresh `.goga/tools/pybuggy/config.yml`. Both accepted
reproduce the user-specified config exactly; every declined confirm leaves its axis
absent. Manifest, usage files, tests, and docs were updated in lockstep (triple
consistency), and the whole goga-change pipeline (scope → investigation → plan →
compatibility → implementation → tests → reconciliation → drift → validation) ran to
completion with all gates green.

## Root Cause

The onboarding autonomy path predated the `api.patch` pipeline: `survey_autonomy`'s
prompt and `build_config_data`'s enabling branch hardcoded the single `api.automate`
axis (former session.py:187, 225-226) while the consumer chain (`resolve_autonomy` ←
`PATCH_CONTRIBUTION.axis`) already supported the patch axis — init was the only gap.

## Modified Cells

| Cell | Files Modified |
|---|---|
| `goga_tool_pybuggy/commands/init` | `session.py`, `CODEMANIFEST`, `.usages/config-build.md`, `.usages/init.md` |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| Per-axis survey | `goga_tool_pybuggy/commands/init/session.py` | `_AUTONOMY_AXES` constant (automate, patch); `survey_autonomy() -> dict[str, bool]` — one confirm per axis, the automate prompt byte-identical to the historical one |
| Per-axis payload | `goga_tool_pybuggy/commands/init/session.py` | `build_config_data` takes `autonomous: dict[str, bool] \| None`; writes one `pipelines` record per enabled axis in axis order; no enabled axis → no `pipelines` key |
| Manifest sync | `goga_tool_pybuggy/commands/init/CODEMANIFEST` | `survey_autonomy`/`build_config_data` signatures + annotations, `amend_pybuggy_config` step 4, `pybuggy_questions` constraint, header sentence — current state |
| Usage sync | `.usages/config-build.md`, `.usages/init.md` | The confirm(s), the per-axis payload, the programmatic mapping shape, the per-axis precondition |
| Docs | `docs/getting-started.md`, `docs/cli/init.md`, `docs/pipelines/api-patch.md` | Both prompts, the both-entries payload YAML, both autonomous-runs cross-references; the "covers only the api.automate axis" parenthetical removed |

## Tests Added

| Test | File | What It Validates |
|---|---|---|
| `test_survey_autonomy_asks_both_axes_in_order_with_disabled_defaults` | tests/commands/init/test_session.py | Both prompts in order, disabled defaults, keyed return |
| `test_survey_autonomy_acceptance_enables_each_axis` | tests/commands/init/test_session.py | Both accepted → both True |
| `test_survey_autonomy_answers_are_independent_per_axis` | tests/commands/init/test_session.py | Mixed answers recorded per axis |
| `test_build_config_data_emits_only_the_enabled_axis` | tests/commands/init/test_session.py | Single enabling answer → exactly that entry |
| `absent-answers` / `declined-confirms` params | tests/commands/init/test_session.py | No enabling answer → no `pipelines` key |

Modified pins: the two signature tables, the both-entries payload test, the four
`TestAmendPybuggyConfig` stubs, the integration confirm tables +
`test_session_smoke_autonomy_confirms_accepted_write_axes`, and the emit↔consume bridge
asserting `resolve_autonomy("api.automate")` and `resolve_autonomy("api.patch")` both
True on the real init payload.

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| commands/init | 2 signature keys + 5 annotation passages (see above) | 2 files, 7 passages |

## Validation Results

**VERIFIED** — `pytest tests/ -x`: 1756 passed / 18 skipped (+3 tests); `ruff check`:
clean; `ruff format --check`: clean; `goga lint`: 24 cells, 0 errors; facade signatures
verified; drift sweep clean; triple consistency holds.

## Compatibility Status

Breaking by the letter of the policy (payload gains entries on the enabling path; two
cell-internal signature types change; three test suites re-pinned) — detected at the
compatibility-guard step, escalated in the plan, and **overridden by the user** (q1
mandate + informed q2 approval). Blast radius: fresh onboarding trees only; existing
projects are never rewritten; automate's behavior, the resolver contract, and every
downstream consumer are untouched and green.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| A consumer pinned the old single-axis payload | Low | Only fresh configs affected; docs describe the new shape; resolver accepts both axes |
| Axis-literal drift between init and the autonomous records | Low | Bridge test resolves both axes through the real resolver; contribution drift tests guard the consumer side |
| Docs desync on a future pipeline addition | Low | The fixed axis order is a single constant; docs name both pipelines explicitly |

## Updated Files

- goga_tool_pybuggy/commands/init/session.py
- goga_tool_pybuggy/commands/init/CODEMANIFEST
- goga_tool_pybuggy/commands/init/.usages/config-build.md
- goga_tool_pybuggy/commands/init/.usages/init.md
- tests/commands/init/test_session.py
- tests/commands/init/test_init_integration.py
- tests/test_autonomy_integration.py
- docs/getting-started.md
- docs/cli/init.md
- docs/pipelines/api-patch.md
- .goga/history/2026/patch-pipeline/todo.md (task record)
- .goga/history/2026/patch-pipeline/01-scope.md … 10-validation.md (cycle gate reports)
- .goga/history/2026/patch-pipeline/patches/init-per-pipeline-autonomy-confirms.md (this report)
