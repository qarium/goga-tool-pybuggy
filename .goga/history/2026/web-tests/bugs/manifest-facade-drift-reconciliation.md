# Change Execution Report — manifest↔facade drift reconciliation

**Run**: 2026-11-12 (branch `web-tests`) · **Pipeline**: goga-change (11 steps, all complete)
**Artifacts**: `.goga/history/2026/drift-reconciliation/` (01-scope … 10-validation, breaking-escalation)

## Summary

`goga drift` reported four type-level entries (7 types) of disagreement between the declared view
(CODEMANIFEST bodies) and the code-derived view (Python cell facades — `__init__.py` `__all__`).
The reconciliation moved the three affected manifests to the code's recorded design: seven
internal-type declarations were removed (types the facades deliberately never exposed), the matchers
facade's deliberate `allow_failure` re-export gained its missing declaration, and every orphaned
backtick link was reworded to plain text. No runtime code, facade, test, docs, or usage file was
touched — `goga drift` now returns `[]`.

## Root Cause

Manifest authoring defects, not code defects: (1) internal types were declared as contract body
types in three CODEMANIFESTs whose facades — by recorded design ("stay internal to the cell",
"Not exported through the facade") — exclude them; every such declaration is a permanent
schema_only drift entry. (2) The matchers facade re-exports `allow_failure` from the sibling utils
cell, but the manifest body never declared it (codegraph_only). Verified against the goga 2.1.0
source: the code view takes cell types from `__all__`, the declared view from body
entities+routines, drift is the two-directional difference. Confidence: HIGH (02-investigation.md).

## Modified Cells

| Cell | Files Modified |
|---|---|
| `goga_tool_pybuggy/api` | `CODEMANIFEST` |
| `goga_tool_pybuggy/matchcrest/matchers` | `CODEMANIFEST` |
| `goga_tool_pybuggy/plugins` | `CODEMANIFEST` |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| auth pair declarations removed | `api/CODEMANIFEST` | `CombineAuth()` and `AuthWrapper(...)` body declarations deleted; header facade sentence and `Endpoint._call` step 2 keep the combine/wrap/raise behavior with plain-text names; footer Description updated |
| matcher bases de-declared | `matchcrest/matchers/CODEMANIFEST` | `BaseMatcher::BaseValueMatcher(...)` and `BaseValueMatcher::BaseSetValueMatcher(...)` deleted (header already documents the bases' role); `allow_failure` dropped from the utils Imports.Types |
| allow_failure re-export declared | `matchcrest/matchers/CODEMANIFEST` | Full routine declaration `allow_failure(f: Callable) -> wrapped: Callable` (location base.py) mirroring the utils contract — sibling embedding is prohibited by the `embedded_type_has_low_level` lint rule, so the planned `->allow_failure: {}` was corrected to this sanctioned form during stabilization |
| internal plugin routines de-declared | `plugins/CODEMANIFEST` | `loader_section_of`, `load_fixture_plugins`, `render_base_url`, `web_cache_path` declarations deleted; surviving ApiPlugin/SandboxPlugin/WebPlugin/web-fixture annotations de-linked (prose kept, backticks dropped); `PackageLoader`/`ModuleLoader` dropped from the loaders Imports.Types (`BaseLoader` stays — used by plugin signatures) |

## Tests Added

None — the change alters no executable behavior and no existing test reads the manifests (plan,
approved). Acceptance is asserted by the deterministic specification gates.

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| api | 2 declarations removed; header/`_call` rewording; Description | none needed — `api.md` already stated the pair internal |
| matchcrest/matchers | 2 declarations removed; 1 re-export routine added; Imports narrowed | none needed — no usage mentions the bases or the re-export |
| plugins | 4 declarations removed; annotations de-linked; Imports narrowed | none needed — no usage mentions the routines |

## Validation Results

**VERIFIED** (10-validation.md): `goga drift` → `[]`; `goga lint` → 26 cells / 0 errors;
programmatic schema-vs-facade parity over every cell → no mismatch; `ruff check`/`format --check`
byte-identical to the pre-change tree (2 pre-existing PLR0917, 1 markdown-format nit). Full pytest
suite blocked by the pre-existing prettyplay 0.0.3-vs-0.0.4 environment gap (import failure at
`web_plugin.py:285`), proven identical on the unmodified tree — documented in the prior patch
report, not caused by this change (zero executable-code changes in the diff).

## Compatibility Status

**Breaking — authorized.** Manifest-defined guarantees altered (declared contract surface of three
manifests shrinks; questions 1–4 and 6 of the assessment: NO — code, facades, paths, formats, tests
untouched). Detected at Step 2, escalated (breaking-escalation.md), overridden by the user
(q2, 2026-11-12, option A: manifest-side reconciliation). Consumers are unaffected: the consumable
surface (facades) never contained the removed names.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Documentation loss for the seven internal types | low | contracts preserved in code docstrings (verified) and prose annotations of surviving contract types |
| future internal-type declarations reintroduce drift | medium | empty `goga drift` is now the checked state; optionally pin it as a repository test (owner decision, noted in 06-testing.md) |
| facade expansion temptation (reverse direction) | low | manifests now record the internal-by-design intent in the header sentences |

## Updated Files

- `.goga/history/2026/drift-reconciliation/01-scope.md` … `10-validation.md`, `breaking-escalation.md` (run artifacts)
- `goga_tool_pybuggy/api/CODEMANIFEST`
- `goga_tool_pybuggy/matchcrest/matchers/CODEMANIFEST`
- `goga_tool_pybuggy/plugins/CODEMANIFEST`
- `.goga/history/2026/web-tests/bugs/manifest-facade-drift-reconciliation.md` (this report)
