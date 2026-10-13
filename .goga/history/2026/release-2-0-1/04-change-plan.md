# Change Plan

## Task Classification

Type: bugfix — hyphenated spec names produce non-importable artifact segments; sanitize the spec segment at derivation sites.

## Affected Cells

| Cell | Files to Modify | What Changes |
|---|---|---|
| goga_tool_pybuggy/commands/generate | generate.py, CODEMANIFEST, .usages/generate.md | Sanitize the spec segment for `api/` and `tests/` writes; spec-segment collision guard; manifest/usage wording |
| goga_tool_pybuggy/commands/diff | diff.py, CODEMANIFEST, .usages/diff.md | `api_spec_dir` derived from the sanitized segment |
| goga_tool_pybuggy/commands/list | list.py, CODEMANIFEST, .usages/list.md | status-mode `api/<spec>` derived from the sanitized segment |
| goga_tool_pybuggy/config | .usages/configuration.md (doc-only) | Clarify that name keys are free-form and consumers derive filesystem-safe segments |
| tests | tests/commands/generate/test_generate.py, tests/commands/diff/*, tests/commands/list/test_list.py | New coverage per Test Strategy |

## Root Cause Analysis

`_write_artifacts` interpolates the raw config spec `name` into `api/<name>/…` and `tests/<name>/…` (generate.py:395,399); diff (diff.py:118) and list (list.py:128) mirror the raw name when reading. The identifier-sanitization rule (`_safe_identifier` / `sanitize_id`: non-word → `_`, leading digit → `_` prefix) is applied only to endpoint ids. A spec name that is not a valid Python identifier segment yields an unimportable package path, breaking the plugin's recursive `pytest_plugins` discovery of `api/<spec>/<id>/api.py` — a violation of the generate CODEMANIFEST's own importability guarantees.

## Trace Summary

init answers → config key (raw, verbatim) → `load_config()` → three consumers derive the segment independently: generate (write), diff (compare), list (classify). Endpoint segments sanitized; spec segments not. Pull is name-independent (uses `entry.location`); init and config key space stay untouched.

## Change Strategy

1. `generate.py` — in `run_generate` phase 1 (validation, before any write): compute `_safe_identifier(name)` per selected spec; when two distinct selected names share a segment, raise `click.ClickException` naming both names and the shared segment (mirror of the existing 6.5 endpoint-collision guard). In `_write_artifacts`: derive `spec_seg = _safe_identifier(name)` once per spec and use it for the `api/` and `tests/` trees. Extend the `_safe_identifier` docstring: the rule also names the spec segment.
2. `diff.py` — `api_spec_dir = cwd / "api" / sanitize_id(name)`.
3. `list.py` — `endpoint_statuses(cwd / "api" / sanitize_id(name), endpoints)` (`sanitize_id` already imported).
4. Manifests (current state, not changelogs): generate — extend step 7.1 to sanitize both segments, reword 7.2–7.6 to `<sanitized name>`, extend 6.5 with the spec-segment collision, update the affected Requirements bullets; diff — reword step 7 and the `api/<name>/` requirement to the sanitized segment; list — reword the `api/<name>` status-mode references.
5. Usages: generate.md — document `<spec.dir>` with the same sanitization rule as `<endpoint.dir>`, add a hyphen example (`some-spec` → `api/some_spec/…`), note the config key and `--spec` filter stay raw; diff.md and list.md — mirror statements; configuration.md — one self-contained clarifying sentence.
6. Tests per Test Strategy; run the full suite.

## Specification Impact

- generate CODEMANIFEST: Algorithm 7.1 (sanitize spec name and endpoint id), 7.2–7.6 (`cwd/api/<sanitized name>/…`), 6.5 (+spec-segment collision), Requirements (importable-package bullet covers the spec segment; new collision bullet; `--spec`/filter keys stay raw).
- diff CODEMANIFEST: Algorithm 7 (`api_spec_dir` from the sanitized segment), Requirement "A spec without an api/<sanitized name>/ tree …".
- list CODEMANIFEST: status-mode tree references `api/<sanitized name>`.
- Footer `Description` fields stay accurate (no change needed).

## Usage Impact

- generate.md: `<spec.dir>` definition + hyphen example + raw-key note; artifact-tree diagram updated.
- diff.md: reading path statement mirrors the sanitized segment.
- list.md: status-mode path statement mirrors the sanitized segment.
- configuration.md: self-contained note — name keys are free-form; artifact trees use derived filesystem-safe segments.
- plugin/.usages/enable.md, api/.usages/api.md: unchanged (their `api/<spec>/<id>/api.py` statements remain true).

## Compatibility Verification

Not backward compatible for spec names that are not valid identifier segments: same-arguments `run_generate`/`run_diff`/`run_list` change paths/output for those names only. Identifier names (all existing tests: `shop`, `client`, `t`) behave identically. Breaking change detected at Step 2 and **overridden by the user** (q2 answer A, 2026-10-13): proceed with sanitization at derivation sites + collision guard. Config keys, `--spec` filters, pull, init: unchanged.

## Test Strategy

- generate: (a) hyphenated `some-spec` → artifacts under `api/some_spec/<id>/` and `tests/some_spec/<id>/`, `__init__.py` markers present, module importable via dotted path under tmp cwd; (b) segment collision `some-spec` + `some_spec` → `ClickException` naming both, no artifacts written; (c) regression — identifier name paths unchanged.
- diff: hyphenated spec — generate then `run_diff` reports empty diffs and no orphans (locates the sanitized tree); a stale raw `api/some-spec/` tree reports as removed.
- list: status mode returns `OK` for endpoints of a generated hyphenated spec (locates the sanitized tree).
- Full suite green (`pytest tests/ -x`) — no existing test uses non-identifier names.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Pre-fix hyphenated trees orphaned in consumer projects | Certain (for hyphenated specs) | Medium — stale dirs, REMOVED noise | Documented in the change report; diff/list surface them explicitly; regenerate + manual cleanup |
| Spec-segment collisions now hard-fail generation | Low | Medium — explicit error, no silent mixing | Guard mirrors existing 6.5 semantics; message names both specs |
| Rule wording drift across three manifests/usages | Medium | Low — doc inconsistency | Identical rule sentence reused verbatim in all edits |
| Hidden consumers of `tests/<name>` beyond traced ones | Low | Medium | Trace re-verified by grep (`"tests" / name` only in generate); drift analysis at Step 9 re-checks |
