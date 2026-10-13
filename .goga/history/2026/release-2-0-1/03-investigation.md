# Investigation Report

## Task Summary

Spec names in `.goga/tools/pybuggy/config.yml` may contain hyphens (`specs.some-spec:`). `generate` uses the raw name as the artifact-tree segment, producing `api/some-spec/…` and `tests/some-spec/…`; a hyphen is not valid in a Python identifier, so the generated fixture modules cannot be imported (the plugin's recursive `pytest_plugins` discovery fails on them). Requested: normalize `-` to `_` so every generated segment is importable — at init time or at generation time.

## Candidate Cells

| Cell | Reason | Priority |
|---|---|---|
| goga_tool_pybuggy/commands/generate | Defect site: writes `api/<name>/…`, `tests/<name>/…` with the raw name (generate.py:395,399) | 1 |
| goga_tool_pybuggy/commands/diff | Reads `api/<name>` (diff.py:118); must mirror the naming rule or hyphenated specs report false drift/orphans | 2 |
| goga_tool_pybuggy/commands/list | Status mode reads `api/<name>` (list.py:128); same mirror requirement (added during tracing — wrongly excluded in scope) | 3 |
| goga_tool_pybuggy/config | Owns the spec-name key space; normalization site option | 4 |
| goga_tool_pybuggy/commands/init | Writes names verbatim into config (`_first_spec_entry` returns `str(name)` raw) | 5 |
| goga_tool_pybuggy/commands/pull | Verified: destination is `entry.location`, name-independent — no participation | excluded after tracing |

## Tracing Summary

See `02-trace.md`. Name flows: init answers → config key → `load_config()` → three consumers derive `api/<name>` independently (generate writes, diff compares, list classifies). Endpoint-level segments are sanitized (`_safe_identifier` / `sanitize_id`: non-word → `_`, leading digit → `_` prefix); the spec-level segment is sanitized nowhere.

## Data Flow Analysis

The spec name is a config dict key surfaced to users (`--spec` filter, list output, pull echo). It is never used for imports itself — only the derived artifact segments are. Therefore normalizing the derived segment (not the config key) fixes importability without touching the config key space, CLI filters, or pull destinations.

## Manifest Algorithm Analysis

- generate CODEMANIFEST already requires: "Every directory on the api.py path … carries an empty `__init__.py` so the generated fixture modules form an importable package" and "a module is always importable under the dotted path it is written to". The raw-`<name>` implementation violates these guarantees for non-identifier names — the fix fulfills existing guarantees.
- The literal algorithm text (steps 7.2–7.6) writes `cwd/api/<name>/…`; it must be amended to a sanitized spec segment, and the mirror texts in diff ("`api/<name>/` tree") and list ("`api/<name>` under the working directory") with it.
- generate step 6.5 rejects sanitized-endpoint-id collisions per spec; the same guard is needed for spec-name segments once names are sanitized (`some-spec` vs `some_spec` would otherwise silently share one artifact directory).

## Affected Usages

| Usage | Cell | Classification | Reason |
|---|---|---|---|
| .usages/generate.md | commands/generate | DIRECTLY AFFECTED | documents the artifact tree `api/<spec>/…`; must state the spec-segment sanitization rule |
| .usages/diff.md | commands/diff | DIRECTLY AFFECTED | documents reads over `api/<spec>/`; must mirror the rule |
| .usages/list.md | commands/list | DIRECTLY AFFECTED | status-mode tree `api/<name>/`; must mirror the rule |
| .usages/configuration.md | config | INDIRECTLY AFFECTED | documents the name key semantics; should note names are free-form keys and consumers derive sanitized segments |
| .usages/init.md, config-build.md | commands/init | INDIRECTLY AFFECTED | describe name collection; unchanged behavior (names stay verbatim) — verify no stale claims after the fix |
| .usages/enable.md | plugin | INDIRECTLY AFFECTED (doc-level) | mentions `api/<spec>/<id>/api.py` discovery; statement stays true with sanitized segments — no change required |
| .usages/api.md | api | INDIRECTLY AFFECTED (doc-level) | example path `api/<spec>/<id>/api.py`; stays true — no change required |

## Rejected Hypotheses

1. **The plugin loader mishandles hyphenated packages** — rejected: the loader imports standard packages; `api.some-spec` is not a legal dotted name, so no loader could import it. Root cause is upstream at path derivation.
2. **Init is the right single fix site** — rejected as *sufficient*: init writes names only at project creation; existing configs with hyphenated keys (and hand-edited configs) would stay broken. Init-time normalization also silently rewrites the user-visible key the user typed. Generation-time derivation fixes every config, old and new.
3. **`SpecEntry.location` or pull destinations are involved** — rejected: pull/generate read spec *files* via `entry.location`; the defect concerns the artifact *output* segment only.
4. **Endpoint-id sanitization is broken** — rejected: `_safe_identifier`/`sanitize_id` operate correctly; the spec-level segment simply never passes through them.

## Confirmed Root Cause

`_write_artifacts` (generate.py:395,399) interpolates the raw config spec `name` into `api/<name>/…` and `tests/<name>/…`, and the reading commands mirror the raw name (diff.py:118, list.py:128). The CODEMANIFEST sanitization rule exists only for the endpoint segment. Any spec name that is not a valid Python identifier segment (hyphen being the reported case) yields an unimportable package path, breaking the plugin's `pytest_plugins` discovery — exactly the manifest's own importability guarantee. Evidence chain: user report → generate.py:395/399 → diff.py:118 → list.py:128 → plugin/.usages/enable.md:69 (import of `api/<spec>/<id>/api.py`) → generate CODEMANIFEST requirements (importable package / dotted-path importability).

## Confidence Level

HIGH — deterministic causality verified end-to-end in code, manifests, and usages; reproduction is structural (hyphen → non-identifier segment → unimportable dotted path).

## Breaking Change Assessment

1. Existing function call with same arguments produces different behavior? **YES** — `run_generate("some-spec", …)` writes `api/some_spec/…` instead of `api/some-spec/…`; `run_diff`/`run_list` read the sanitized tree and classify a pre-fix hyphenated tree as removed/orphaned. Scope: only spec names that are not valid identifier segments; identifier names (all existing tests use `shop`, `client`, `t`) behave identically.
2. Existing file paths change? **YES** — for hyphenated spec names, as above; also `tests/<name>`.
3. Output format change? **NO** — formats unchanged; diff/list output *values* change for hyphenated specs (orphan keys reflect the relocated tree).
4. Return value semantics change? **NO**.
5. Manifest-defined guarantees altered? **YES (text)** — the documented path shape `cwd/api/<name>/…` in three manifests is amended to the sanitized segment; the importability guarantee itself is fulfilled, not weakened.
6. Existing tests break? **NO** — no test uses a non-identifier spec name (verified by grep over tests/commands/{generate,diff,list}); to be confirmed by a full test run.

**BREAKING CHANGE DETECTED** (questions 1, 2, 5 = YES). Per the goga-change policy the pipeline STOPs here; only the user can override. Escalation question q2 submitted with the exact blast radius and the proposed minimal fix.

### Proposed fix (pending override)

- Derive the spec's artifact segment with the existing identifier rule at all four sites: generate `api/`+`tests/` writes (local `_safe_identifier(name)`), diff `api_spec_dir` (`sanitize_id(name)`), list `api_spec_dir` (`sanitize_id(name)`). Config keys, `--spec` filters, pull, and init stay untouched.
- Add the 6.5-style guard in generate: two selected spec names whose segments collide raise `click.ClickException` naming both, before any write.
- Amend the three CODEMANIFESTs (path-shape wording + collision requirement) and the three directly-affected usages.
- Tests: hyphenated-name generation produces importable paths and is located by diff/list; segment-collision rejection; no regression for identifier names.
