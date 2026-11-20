# Manifest Reconciliation Report

## Cells Reconciled

| Cell | Manifest Updated? | Sections Changed |
|---|---|---|
| `goga_tool_pybuggy/commands/init` | YES | Global `Annotations` (bootstrap-ownership paragraph + kind-aware paragraph); `run_bootstrap` algorithm steps 1/2/7, Requirements (2 bullets), Constraints (+1); `survey_web_config` algorithm steps 1–4 + Requirements (+1) |
| `goga_tool_pybuggy/web` | NO | No code or contract change; `BrowserSettings.name` annotation ("chromium, chrome, firefox, and the names the runtime accepts") already consistent with the new choice question |

Base usages/annotations (goga-codemanifest-base): `conventions` usage and its base annotation line remain declared and referenced in the init cell header — preserved.

## Algorithm Consistency

- `run_bootstrap`: step 1 now resolves the kind signals (api.yml/web.yml presence — `init.py:351-360`); step 2 copies only the active roots via `_kind_gated_roots`/`_discover_packaged_usages(active_roots)` with a DEBUG log per absent kind (`init.py:311-332, 363-373`) — matches the manifest text. Step 7 registers the api pair only when the api root was active (`registered` derives from the active roots, `init.py:405-409`); `conventions` registers unconditionally — matches. Steps 3–6c, 8–10 unchanged in code and manifest.
- `survey_web_config`: provider choice with the purpose line, two required models with per-model purpose prompts, browser name as a choice of the five runtime names, headless confirm — code (`session.py:233-249` post-change) matches the rewritten algorithm steps and the added requirement (the choice mirrors the runtime matrix — the `_BROWSER_NAMES` constant is the single touch point).
- All other declared routines (`pybuggy_questions`, `amend_pybuggy_config`, builders, writers): untouched in code, untouched in manifest.

## Operational Flow Consistency

Session → engine-written kind configs → bootstrap gates: the flow description in the global annotation ("The bootstrap closes kind-dependently on the written files — the kind signals…") now names both gates symmetrically; code computes both signals before step 2 and every kind-dependent step re-checks its own file. Consistent.

## Guarantees Verification

- Old guarantee "every packaged usage is copied" — deliberately REPLACED (the defect); new guarantee "a kind's usages never ship without its written config" is asserted by tests in all three kind variants plus the no-config edge.
- "The api and web question sets, usages, and registrations never cross" — questions were already separated (unchanged code, tests still pass); usages/registrations now also separated (verified end-to-end by the integration smokes).
- Idempotence, never-overwrite of user keys, exit-code semantics, mandatory-Dockerfile invariant — unchanged, full suite green.

## Practices Consistency

Relative imports, type hints, structured logging, docstring style (`Args`/`Returns`/`Raises`), and the cyclomatic-complexity practice (gate logic extracted into `_kind_gated_roots`, mirroring the `_log_registration` precedent) — all preserved; `ruff check` and `ruff format` clean.

## Semantic Consistency Summary

**Consistent.** Manifest, implementation, tests, usages, and docs describe the same kind-gated contract; `goga lint` reports 25 cells / 0 errors after the updates; the manifest YAML parses (3 documents, 25 body types, footer intact).
