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

---

# Change Execution Report

## Summary

A hyphenated spec name in `.goga/tools/pybuggy/config.yml` (`specs.some-spec:`) produced hyphenated artifact directories (`api/some-spec/…`, `tests/some-spec/…`) that cannot be imported as Python modules, breaking the generated fixtures and the plugin's `pytest_plugins` discovery. The fix derives the spec's directory segment with the existing identifier-sanitization rule (non-word → `_`, leading digit → `_` prefix) at every site that writes or reads the artifact tree — generate (both trees), diff, and list — while config keys, `--spec` filters, pull, and init remain untouched. A pre-write guard now rejects two selected spec names whose segments collide (`some-spec` vs `some_spec`). The change was executed through the full goga-change pipeline; the detected breaking change (path relocation for non-identifier names only) was escalated and overridden by the user (option A).

## Root Cause

`_write_artifacts` interpolated the raw config spec name into the artifact path (generate.py:395,399), and the reading commands mirrored the raw name (diff.py:118, list.py:128). The sanitization rule existed but was applied only to endpoint ids, violating the generate CODEMANIFEST's own guarantees ("importable package", "importable under the dotted path it is written to") for any spec name that is not a valid Python identifier segment.

## Modified Cells

| Cell | Files Modified |
|---|---|
| goga_tool_pybuggy/commands/generate | generate.py, CODEMANIFEST, .usages/generate.md |
| goga_tool_pybuggy/commands/diff | diff.py, CODEMANIFEST, .usages/diff.md |
| goga_tool_pybuggy/commands/list | list.py, CODEMANIFEST, .usages/list.md |
| goga_tool_pybuggy/config | .usages/configuration.md |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| Spec-segment sanitization (write) | goga_tool_pybuggy/commands/generate/generate.py | `spec_seg = _safe_identifier(name)` drives `api/` and `tests/` trees; docstring of `_safe_identifier` extended |
| Spec-segment collision guard | goga_tool_pybuggy/commands/generate/generate.py | Step 5.6: two selected names sharing a segment → `ClickException` naming both, before any write |
| Spec-segment sanitization (read) | goga_tool_pybuggy/commands/diff/diff.py | `api_spec_dir = cwd / "api" / sanitize_id(name)` |
| Spec-segment sanitization (status read) | goga_tool_pybuggy/commands/list/list.py | `endpoint_statuses(cwd / "api" / sanitize_id(name), …)` |

## Tests Added

| Test | File | What It Validates |
|---|---|---|
| test_run_generate_hyphenated_spec_name_yields_importable_segment | tests/commands/generate/test_generate.py | `some-spec` → `api/some_spec/…`; dotted-path import via `_module_is_pytest_plugin` |
| test_run_generate_leading_digit_spec_name_gets_underscore_prefix | tests/commands/generate/test_generate.py | `2shop` → `_2shop` segment |
| test_run_generate_spec_segment_collision_raises_before_writes | tests/commands/generate/test_generate.py | collision → ClickException naming both; no writes |
| test_run_diff_reads_sanitized_spec_segment | tests/commands/diff/test_diff.py | clean diff over the sanitized root |
| test_run_diff_raw_hyphenated_tree_is_outside_the_sanitized_root | tests/commands/diff/test_diff.py | stale raw tree: endpoint added, no orphan line |
| test_run_list_status_reads_sanitized_spec_segment | tests/commands/list/test_list.py | status OK over the sanitized root |
| test_run_list_status_raw_hyphenated_tree_reports_add | tests/commands/list/test_list.py | stale raw tree: ADD, no REMOVED |

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| commands/generate | Algorithm 7.1 sanitizes both segments; 7.2–7.6 `<sanitized name>`; new 6.6 collision step; five Requirements bullets updated/added | generate.md: `<spec.dir>` rule, hyphen example, raw-key note, collision coverage, marker paths |
| commands/diff | Algorithm 7.1 locates the sanitized tree; requirement `api/<sanitized name>/`; `sanitize_id` annotations cover spec names; `orphan_artifact_dirs` wording aligned | diff.md: `api/<spec.dir>/` definition + stale-tree caveat |
| commands/list | Algorithm 3.5 derives the segment via `sanitize_id` | list.md: defining bullet for the status-mode tree path |
| config | none (contract unchanged) | configuration.md: free-form-key note with the derivation rule |

## Validation Results

VERIFIED (`10-validation.md`). Full suite 1724 passed / 18 skipped (1717 pre-existing + 7 new); `ruff check` and `ruff format --check` clean; `goga lint` 24 cells / 0 errors; facades importable. End-to-end reproduction of the reported scenario: config `specs.some-spec:` → `api/some_spec/clients_startup_get/…` generated, `from api.some_spec.clients_startup_get.api import get_clients_startup` succeeds, `endpoint diff` → `{"clients_startup_get": {}}`, `endpoint list --status` → `OK` printed under the raw config name.

## Compatibility Status

BREAKING within the overridden scope (compatibility report `05-compatibility.md`): for spec names that are not valid identifier segments, same-argument calls change written/read paths (`api/some-spec` → `api/some_spec`); manifest path-shape text amended. Identifier names byte-identical; all 1717 pre-existing tests unmodified and green. User override recorded 2026-10-13 (q2 answer A). Consumer migration: regenerate with `pybuggy endpoint generate -f` and delete stale raw-hyphen trees manually — diff/list do not discover them (they sit outside the sanitized root; endpoints report ADD).

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Stale pre-fix hyphenated trees remain on disk unnoticed | Medium | Endpoints report ADD in diff/list until regeneration; release note instructs manual cleanup of `api/<raw-hyphen>/`, `tests/<raw-hyphen>/` |
| Two config names colliding after sanitization now hard-fail generation | Low | Explicit ClickException naming both specs; mirror of the established 6.5 semantics |
| Documentation/manifest wording divergence across the three command cells | Low | One rule sentence reused verbatim; drift analysis re-verified |

## Updated Files

- goga_tool_pybuggy/commands/generate/generate.py
- goga_tool_pybuggy/commands/generate/CODEMANIFEST
- goga_tool_pybuggy/commands/generate/.usages/generate.md
- goga_tool_pybuggy/commands/diff/diff.py
- goga_tool_pybuggy/commands/diff/CODEMANIFEST
- goga_tool_pybuggy/commands/diff/.usages/diff.md
- goga_tool_pybuggy/commands/list/list.py
- goga_tool_pybuggy/commands/list/CODEMANIFEST
- goga_tool_pybuggy/commands/list/.usages/list.md
- goga_tool_pybuggy/config/.usages/configuration.md
- tests/commands/generate/test_generate.py
- tests/commands/diff/test_diff.py
- tests/commands/list/test_list.py
