# Change Plan — pybuggy init goga 2.0 regression fixes

## Task Classification
bugfix (restores pre-2.0 UX/behavior of `pybuggy init` inside the 2.0 participation architecture)

## Affected Cells
| Cell | Files to Modify | What Changes |
|---|---|---|
| goga_tool_pybuggy/commands/init | session.py | extra_specs record removed; new `survey_extra_specs()` interactive loop; amend hook self-surveys; `parse_specs`/`build_config_data` take the surveyed extras; `declare_pybuggy_session` skips the core `convention` section |
| goga_tool_pybuggy/commands/init | bootstrap.py | new `document_config_examples()` (commented examples for absent members); `install_pybuggy` maps missing dist metadata to a clean error |
| goga_tool_pybuggy/commands/init | init.py | run_bootstrap gains the documentation step (10 steps) |
| goga_tool_pybuggy/commands/init | CODEMANIFEST, .usages/init.md, .usages/config-build.md | contract + usage reconciliation |

## Root Cause Analysis
1. `pybuggy_questions` declared additional specs as one compact line-input — a 2.0 rework design decision; the engine
   surveys tool-block records flatly, so a confirm-gated per-field repetition is inexpressible declaratively.
2. The engine session downloads goga language conventions into `.goga/usages/conventions.md` (on "Download base
   convention" accept) before the bootstrap runs, and the bootstrap's conventions gate is skip-if-exists — the
   pybuggy packaged test convention never lands.
3. Version derivation verified CORRECT (dist version → "N.M" → `-v N.M.x` → engine `resolve_version` → `~=N.M.0` →
   `goga-tool-pybuggy`). Only gap: `PackageNotFoundError` escaped the bootstrap's `(OSError, YAMLError, ValueError)`
   tier as a raw traceback on metadata-less runs.
4. The 2.0 rework deleted the 1.x comment-rich config emitter, and the engine buffer serializes plain data only —
   the commented examples for unanswered members disappeared.

## Change Strategy
1. Remove the compact extra_specs input from the declared block (8 items ending at first_spec).
2. New `survey_extra_specs()` — `Add another spec?` confirm (default no); per accepted spec ask name (required,
   re-asked) → type (choice swagger|openapi) → location (required, re-asked) → git_url/git_location/git_ref
   (optional); repeat while confirmed. Run from `amend_pybuggy_config` (post-survey, engine still the writer).
3. `parse_specs(spec_answers, extra_specs: list[dict] | None)` — surveyed mappings; duplicates warned and skipped.
4. `build_config_data(answers, extra_specs=None)`.
5. `declare_pybuggy_session` additionally `context.skip("convention")`.
6. New `document_config_examples(path)` — ruamel round-trip adding the 1.x commented records for absent members in
   PluginConfigKeys order (specs as terminal anchor); idempotent by marker detection.
7. `run_bootstrap` inserts the documentation step (now 10 steps) inside the wrapped error tier.
8. `install_pybuggy` maps `PackageNotFoundError` to a clean ValueError (ERROR log + exit 1).

## Compatibility Verification
NOT backward compatible — user-requested behavior restoration. Breaking surface disclosed and explicitly approved
by the user (plan approval dialog; answer: "Полное одобрение — все 4 пункта плана").

## Test Strategy
Reworked session/bootstrap/init unit tests for the new shapes; new TestSurveyExtraSpecs and
TestDocumentConfigExamples classes; metadata-guard test; smoke integration extended (convention skip proof,
extra-specs interactive path, commented examples, packaged-convention equality).

---

# Change Execution Report

## Summary
The goga 2.0 migration broke four `pybuggy init` behaviors: additional specs surveyed as one compact line-input, the
conventions slot receiving goga's language convention instead of pybuggy's test convention, an unverified (and
edge-fragile) Dockerfile version derivation, and the loss of commented example records in the generated tool config.
All four were fixed inside the commands/init cell following the goga-change pipeline (scope → investigation → plan →
user approval → compatibility guard (user-overridden BREAKING) → implementation → tests → manifest/usage
reconciliation → drift analysis → validation), restoring the 1.x UX within the 2.0 participation architecture.

## Root Cause
See Root Cause Analysis above — four independent causes, all confirmed by direct code evidence (engine generator
conventions download + skip-if-exists gate; declarative flat survey; plain-data serialization; rework deletion),
confidence HIGH.

## Modified Cells
| Cell | Files Modified |
|---|---|
| goga_tool_pybuggy/commands/init | CODEMANIFEST, __init__.py, init.py, session.py, bootstrap.py, .usages/init.md, .usages/config-build.md |
| tests (mirror) | tests/commands/init/{conftest.py, test_session.py, test_bootstrap.py, test_init.py, test_init_integration.py} |

## Implemented Changes
| Change | File | Description |
|---|---|---|
| compact input removed | goga_tool_pybuggy/commands/init/session.py | pybuggy_questions no longer declares extra_specs |
| interactive extra-specs survey | goga_tool_pybuggy/commands/init/session.py | survey_extra_specs() — confirm gate + per-field loop with required re-asks |
| extras plumbing | goga_tool_pybuggy/commands/init/session.py | parse_specs/build_config_data take the surveyed mappings |
| convention skip | goga_tool_pybuggy/commands/init/session.py | declare_pybuggy_session skips the core convention section |
| commented examples | goga_tool_pybuggy/commands/init/bootstrap.py | document_config_examples() restores the 1.x records, idempotent |
| clean metadata error | goga_tool_pybuggy/commands/init/bootstrap.py | install_pybuggy maps PackageNotFoundError to ValueError |
| bootstrap step | goga_tool_pybuggy/commands/init/init.py | 10-step run_bootstrap with the documentation step |
| facade | goga_tool_pybuggy/commands/init/__init__.py | 19 routines (survey_extra_specs, document_config_examples added) |

## Tests Added
| Test | File | What It Validates |
|---|---|---|
| TestSurveyExtraSpecs (4 tests) | tests/commands/init/test_session.py | declined gate, field order, required re-asks, add-another loop |
| parse/build/amend extras tests | tests/commands/init/test_session.py | surveyed extras reach the payload; malformed/duplicate guards; uninvited never surveys |
| declare skip test | tests/commands/init/test_session.py | the convention section is skipped when invited |
| TestDocumentConfigExamples (6 tests) | tests/commands/init/test_bootstrap.py | exact record layout/order, idempotency, active-key preservation, no-op cases, full member coverage |
| metadata guard test | tests/commands/init/test_bootstrap.py | PackageNotFoundError → clean ValueError, Dockerfile untouched |
| smoke extension | tests/commands/init/test_init_integration.py | native session: no convention gate asked, extra spec surveyed into engine-written config, bootstrap adds comments and the packaged convention |
| ScriptedTTY FIFO queues | tests/commands/init/conftest.py | repeated prompts/gates scriptable |

## Specification Updates
| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| goga_tool_pybuggy/commands/init | cell Annotations (self-survey + convention skip + documentation step); pybuggy_questions; NEW survey_extra_specs; build_config_data; parse_specs; declare_pybuggy_session; amend_pybuggy_config; run_bootstrap (10 steps); NEW document_config_examples; install_pybuggy guarantee | .usages/config-build.md (interactive follow-up, emitted examples, programmatic notes); .usages/init.md (session semantics, bootstrap table row, conventions slot) |

## Validation Results
VERIFIED — 970 tests pass (baseline 954); ruff check/format clean; goga lint 17 cells 0 errors; facade importable;
scope check clean (only approved files modified).

## Compatibility Status
BREAKING (by design) — every break disclosed in the approval dialog and explicitly overridden by the user
("Полное одобрение — все 4 пункта плана"). Facade call-compatibility preserved via the `extra_specs=None` default.

## Risks
| Risk | Severity | Mitigation |
|---|---|---|
| Ctrl-C at the extra-spec prompts drops the whole pybuggy contribution (engine soft-fail; session continues) | low | documented engine semantics in manifest + usages |
| skip("convention") no-ops with a cosmetic engine warning when the section is absent (template with conventions.md) | cosmetic | documented in the manifest |
| Published docs (docs/cli/init.md, docs/getting-started.md) still describe the old compact form | low | flagged as follow-up documentation update |

## Updated Files
- goga_tool_pybuggy/commands/init/CODEMANIFEST
- goga_tool_pybuggy/commands/init/__init__.py
- goga_tool_pybuggy/commands/init/init.py
- goga_tool_pybuggy/commands/init/session.py
- goga_tool_pybuggy/commands/init/bootstrap.py
- goga_tool_pybuggy/commands/init/.usages/init.md
- goga_tool_pybuggy/commands/init/.usages/config-build.md
- tests/commands/init/conftest.py
- tests/commands/init/test_session.py
- tests/commands/init/test_bootstrap.py
- tests/commands/init/test_init.py
- tests/commands/init/test_init_integration.py
