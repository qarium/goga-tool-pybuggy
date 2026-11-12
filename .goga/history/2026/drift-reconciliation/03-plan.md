# Change Plan

**Status**: APPROVED (user, q2 of this run — combined breaking-change override + plan approval).

## Task Classification

Type: specification reconciliation (manifest-only). No runtime code changes; no facade changes;
no test-code changes. Direction: manifest-side (bring CODEMANIFEST bodies in line with the facades).

## Affected Cells

| Cell | Files to Modify | What Changes |
|---|---|---|
| `goga_tool_pybuggy/api` | `CODEMANIFEST` | Remove `CombineAuth()` and `AuthWrapper(...)` body declarations; de-link (un-backtick) their names in the surviving header annotations and `Endpoint._call` step 2 |
| `goga_tool_pybuggy/matchcrest/matchers` | `CODEMANIFEST` | Remove `BaseMatcher::BaseValueMatcher(...)` and `BaseValueMatcher::BaseSetValueMatcher(...)`; add `->allow_failure: {}` embedding after the base block |
| `goga_tool_pybuggy/plugins` | `CODEMANIFEST` | Remove the four internal routine declarations (`loader_section_of`, `load_fixture_plugins`, `render_base_url`, `web_cache_path`); de-link their names in the surviving plugin-class and fixture annotations |

## Change Strategy

1. **api**: delete the two declaration blocks; in header annotation sentences keep the prose but
   drop the backticks around `CombineAuth`/`AuthWrapper` (links must resolve — `AnnotationLinksExists`);
   `Endpoint._call` Algorithm step 2 keeps its description with plain-text names. The footer
   Description keeps naming the auth pair (cell content summary, metadata — not a contract link).
2. **matchers**: delete the two base declarations (the only `BaseValueMatcher::` mutation chain goes
   with them — `MutationExists` stays satisfied; concrete matchers mutate from `BaseMatcher`, which
   stays); insert `->allow_failure: {}` after `BaseMatcher` (mirrors the parent cell ordering).
3. **plugins**: delete the four routine declarations; de-link the names in ApiPlugin.configure
   (render steps), SandboxPlugin/WebPlugin constructor steps, and the web-fixture cache-addressing
   annotation — prose unchanged, backticks dropped.
4. **Verification gates** (in order): `goga drift` (empty), `goga lint` (0 errors),
   `goga schema` (per-cell types == facade), `pytest tests/ -x` (green), `ruff check` + `ruff format --check`
   (clean — control run, code untouched).

## Compatibility Verification

Breaking per policy (manifest contract surface shrinks) — detected at Step 2, escalated
(`breaking-escalation.md`), **user override received (option A)**. Runtime behavior, facades, paths,
output formats, and tests are untouched (assessment questions 1–4, 6: NO).

## Test Strategy

No new test files: the change alters no executable behavior, and no existing test reads the
manifests. Acceptance is carried by the deterministic gates above — `goga drift` empty is the
assertion under test, `goga lint` guards DSL/link validity of the edited manifests, the pytest suite
guards against accidental code impact, ruff guards formatting.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Dangling backtick links after removals | Medium | Low (lint error) | Every reference enumerated in investigation; `goga lint` gate |
| Orphaned mutation/import references | Low | Low (lint error) | Only `BaseValueMatcher::BaseSetValueMatcher` chain exists and is removed with its base; `ImportIsUsed` re-verified for matchers (embedding) and plugins (signatures) |
| Documentation loss for internal types | Low | Low | Contracts preserved in code docstrings (verified present) + prose annotations of surviving types |
| Hidden consumers of the removed declarations | Low | Medium | Facades unchanged — the consumable surface never included these names; docs/usages swept, no references |
