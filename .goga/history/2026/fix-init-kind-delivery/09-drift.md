# Specification Drift Analysis

## Manifest Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `commands/init` | The manifest mandated the defective contract (unconditional copy incl. the web root; unconditional api registration) — the deliberate drift introduced by the fix | YES — steps 1/2/7, Requirements, Constraints, `survey_web_config`, and both global paragraphs rewritten in lockstep; `goga lint` 0 errors; YAML parses (3 docs, 25 body types) |
| `web` | None — no code or contract change | n/a (no drift) |

## Usage Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `commands/init` | `init.md` and `config-build.md` described the old delivery/registration and the old question forms | YES — both updated; repository-wide sweep for the retired wording returns nothing outside `.goga/history/` |
| docs mirrors | `docs/cli/init.md`, `docs/getting-started.md` carried the old table rows and prompt descriptions | YES — re-synced per the lockstep rule |
| `web` (`pybuggy-web.md`) | None — never documented the question form or the registration gates | n/a (no drift) |

## Behavioral Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `commands/init` | Same-inputs output changed exactly as escalated and user-approved (q2): per-kind delivered file sets, per-kind `codemanifest.usages`/`annotations` content, at-prompt rejection of out-of-matrix browser names, new prompt texts | YES — the intended change; verified end-to-end on the real engine (repro: api-only ships no web file/key, web-only ships no api files/keys) and pinned by the updated tests |

## Algorithmic Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `commands/init` | `run_bootstrap` gained the kind-signal resolution and per-root gate (helper `_kind_gated_roots`); `_discover_packaged_usages` now takes the active roots; `survey_web_config` prompts/choice changed | YES — manifest algorithms rewritten to match; step order and all other steps unchanged |

## Resolution Status

**All drift resolved.** One pre-existing, out-of-scope inaccuracy discovered and deliberately left untouched (per the scope-governance rule): the `bootstrap.py` module docstring says "Six pure writers" while the cell exposes nine (the facade test already pins nine). Recommended follow-up only.
