# Test Report — Patch cycle 2 (init autonomy for api.patch)

## Changes Requiring Coverage

| Change | Type |
|---|---|
| `survey_autonomy` asks one confirm per axis, fixed order, returns per-axis answers | behavior |
| The automate question stays byte-identical to the historical single confirm | regression |
| `build_config_data` writes one entry per enabled axis, in axis order, before `specs` | behavior |
| A single enabled axis writes exactly that entry (per-pipeline independence) | edge |
| None / all-declined / stale-key answers write no `pipelines` key | regression + edge |
| `amend_pybuggy_config` passes the per-axis answers through to the payload | behavior |
| The end-to-end session asks both confirms in order and lands both entries | behavior (integration) |
| The enabling payload resolves True through the real resolver for BOTH axes | manifest (acceptance of `todo.md`) |
| Signature surfaces (`dict[str, bool]` return; `dict[str, bool] \| None` param) | manifest |

## Tests Added

| Test Name | File | What It Validates |
|---|---|---|
| `test_survey_autonomy_asks_both_axes_in_order_with_disabled_defaults` | tests/commands/init/test_session.py | Both prompts in order (automate first), disabled defaults, keyed dict return |
| `test_survey_autonomy_acceptance_enables_each_axis` | tests/commands/init/test_session.py | Both accepted → both True |
| `test_survey_autonomy_answers_are_independent_per_axis` | tests/commands/init/test_session.py | Mixed answers recorded per axis — the Option-B semantics |
| `test_build_config_data_emits_only_the_enabled_axis` | tests/commands/init/test_session.py | Single enabling answer writes exactly that pipeline's entry |
| `absent-answers` / `declined-confirms` params | tests/commands/init/test_session.py | No enabling answer → no `pipelines` key (extended parametrization) |

Tests modified: the two signature tables (`autonomous` param type, `survey_autonomy` return
type), `test_build_config_data_emits_pipelines_axes_on_enabling_answers` (both entries,
key order, serializability), the four `TestAmendPybuggyConfig` stubs (per-axis dict),
`_CONFIRM_ANSWERS`/`_EXPECTED_CONFIRMS` + `test_session_smoke_autonomy_confirms_accepted_write_axes`
(integration), and `TestEmitConsumeBridge.test_build_config_data_payload_enables_resolve_autonomy`
(both axes resolve True — the `todo.md` acceptance).

## Test Results

| Suite | Status | Details |
|---|---|---|
| `pytest tests/ -x` (full) | **PASS** | 1756 passed, 18 skipped (was 1753 before the change; +3 new tests) |
| `ruff check` | **PASS** | All checks passed |
| `ruff format --check` | **PASS** | 333 files formatted, none pending |

Stabilization iterations: 2 (one missed test pin — `TestAmendPybuggyConfig` stubs; one
line-length formatting pass) — within the MAX 5.

## Coverage Gaps

| Changed Behavior | Covered? | Notes |
|---|---|---|
| Per-axis survey questions and order | Yes | scripted-click unit + integration confirm table |
| Per-axis payload entries and independence | Yes | unit (both / single / none) + integration both-true |
| Declined / absent answers write nothing | Yes | parametrized unit + declined integration path (unchanged test) |
| Resolver round-trip for both axes | Yes | emit↔consume bridge with the real config tree |
| `amend_pybuggy_config` wiring | Yes | recorder-context unit tests |
| Cancelled prompt (`click.Abort`) propagation | Yes (existing) | the constraint is unchanged; covered by the existing contract tests of the amend moment |

## Missing Coverage Analysis

Nothing identified. The full changed surface is pinned: the survey (unit + end-to-end),
the payload builder (unit, three answer shapes), the hook wiring (recorder doubles), and
the resolver bridge (real config tree, both axes). The unchanged neighbors (automate
window/build, resolver validation errors) keep their existing green suites as regression
guards.
