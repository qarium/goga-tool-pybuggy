# Specification Drift Analysis — Patch cycle 2 (init autonomy for api.patch)

## Manifest Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `commands/init` | The manifest pinned the single-axis confirm/payload (survey_autonomy signature + algorithm, build_config_data step 3, amend step 4, pybuggy_questions constraint, header sentence) | Yes — updated in-lockstep during implementation; re-verified line-by-line in step 7; `goga lint` 24 cells / 0 errors |
| `config`, `autonomous`, root | None — no behavioral change on their side | Yes (nothing to resolve) |

## Usage Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `commands/init` | `config-build.md` and `init.md` described the single automate confirm and the single-axis payload; the initial scope report wrongly assumed the cell had no usage files | Yes — both updated in step 8 (domain sentence, the `autonomous` bullet, the contribution bullet, the programmatic note, the precondition) |
| `config` | `autonomy.md`'s example shows one entry — cosmetic only; the contract is per-name | Yes — verified accurate without change (same convention as `docs/configuration.md`) |
| `autonomous` | `contribution.md` names both axes already | Yes — verified, no change |

## Behavioral Drift

| Location | Drift Description | Resolved? |
|---|---|---|
| `docs/getting-started.md` | Described the automate-only confirm | Yes — one confirm per pipeline, both cross-referenced |
| `docs/cli/init.md` | Prompt text, payload YAML, "the one way… entry" singular; a stale singular "the autonomy confirm, below" found by the final sweep | Yes — all updated, including the sweep find |
| `docs/pipelines/api-patch.md` | "the autonomy confirm of pybuggy init covers only the api.automate axis" | Yes — replaced with the patch-confirm reference |
| `docs/pipelines/api-automate.md` | "set it by hand or through the autonomy confirm" — still accurate for the automate axis | Yes — no change needed |
| Tests | Three suites pinned the old prompt/payload/types | Yes — updated and extended (+3 tests), full suite green |

## Algorithmic Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `commands/init` | None beyond the intended evolution — the amend-moment 6-step order, the invited gate, the abort propagation, the payload key order (`specs` last), and the declined-writes-nothing guarantee are all preserved and pinned by tests | Yes |

## Resolution Status

**All drift resolved.** The final sweep (singular-phrase grep, automate-prompt pairing,
"covers only", stale `bool` contracts) is clean; the last find (`cli/init.md:59`) was
fixed in this step. `pytest tests/ -x` 1756 passed / 18 skipped; `ruff check` and
`ruff format --check` clean; `goga lint` 0 errors.
