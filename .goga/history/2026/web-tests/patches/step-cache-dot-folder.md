# Patch — step cache subfolder renamed to `.cache`

Change Execution Report of the goga-change pipeline run (2026-11-19), branch `web-tests`.
Verdict: **VERIFIED (sandbox differential)**. User approvals on the run: task clarification (the
TODO file was absent — the task arrived as the user's answer), Change Plan + breaking-change
override (existing cache paths change).

# Change Plan (approved)

## Task Classification
Type: refactor (behavioral rename) — the generated web step-cache subfolder `cache` becomes
`.cache`; the specification layer, docs, skills, and test pins follow the rename.

## Affected Cells

| Cell | Files to Modify | What Changes |
|---|---|---|
| `goga_tool_pybuggy/plugins` | `web_plugin.py`, `CODEMANIFEST`, `.usages/enable.md` | Literal segment `"cache"` → `".cache"` in `web_cache_path`; docstring; 2 manifest annotation sites; usage wording |
| `goga_tool_pybuggy/web` | `pages.py`, `CODEMANIFEST`, `.usages/pybuggy-web.md` | Literal segment in `_page_scope`; docstring; manifest annotation site; usage layout paths |

Non-cell surfaces in the same rename: `docs/web/index.md`, `docs/web/configuration.md`, 12
`goga_tool_pybuggy/skills/*/SKILL.md` files, `tests/plugins/test_web_plugin.py`,
`tests/web/test_pages.py`.

## Change Strategy
1. `web_plugin.py:web_cache_path` — `segments.insert(-1, ".cache")`; the docstring layout
   `<root>/<module_path…>/.cache/<test_name>`.
2. `pages.py:_page_scope` — `segments.insert(-1, ".cache")`; the docstring example
   `pages/admin/.cache/auth_page` and the `.cache` segment/parent wording.
3. Manifests describe the directory by its new name (`.cache subdirectory`, `.cache segment`) at
   every annotation site that names it.
4. Usages, docs, and skills: every `cache/` path and `cache` segment mention becomes `.cache`;
   the stale pre-rename path in `skills/pybuggy/SKILL.md` is aligned to the current shape.
5. Tests: the expected literals of the path pins change to `.cache`.

## Compatibility Verification
NOT backward compatible — user-approved override:
- same call arguments produce different addresses (`web_cache_path` / `_page_scope` return
  `.cache` paths);
- existing file paths change (the generated cache directories move);
- existing test pins break (updated in the same change);
- consumer effect: committed `cache/` directories stop being found — the next non-strict run
  regenerates under `.cache/`; strict runs fail on cache miss until the cache is regenerated or
  the consumer renames the directory (`git mv cache .cache`).

## Test Strategy
No new tests: the behavior is fully pinned by the existing suite (`web_cache_path` unit tests,
fixture-flow `made[].cache_path` pins, `_page_scope` pins). Only the expected literals change.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `.cache` ignored by consumer `.gitignore` (the standard Python template ignores `.cache`) — the committed-cache workflow stops committing | Medium | High | Release notes: consumer repos need the step-cache `.cache` directories un-ignored (`!**/.cache/` or dropping the rule) |
| Existing consumer caches missed → strict CI fails | High | Medium | One-time regeneration or `git mv cache .cache`; release notes |
| Missed a doc/skill/test mention | Low | Low | Repo-wide sweeps for `/cache/` and segment wording — clean |

# Change Execution Report

## Summary
Renamed the generated web step-cache subfolder from `cache` to `.cache` across the two runtime
sites that compute step-cache addresses (`web_cache_path` of the plugins cell, `_page_scope` of
the web cell) and synchronized every specification, usage, documentation, skill, and test
surface that names the directory. The rename is breaking for existing committed caches —
approved by the user with an explicit override.

## Root Cause
Not a defect: a naming decision. The folder is generated tooling output; the dot-prefix hides it
from default directory listings and marks it as tool-owned, matching the `.prettyplay` /
`.pytest_cache` family. The directory name lived as a string literal in exactly two functions.

## Modified Cells

| Cell | Files Modified |
|---|---|
| `goga_tool_pybuggy/plugins` | `web_plugin.py`, `CODEMANIFEST`, `.usages/enable.md` |
| `goga_tool_pybuggy/web` | `pages.py`, `CODEMANIFEST`, `.usages/pybuggy-web.md` |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| Per-test segment rename | `goga_tool_pybuggy/plugins/web_plugin.py` | `segments.insert(-1, ".cache")` + docstring layout |
| Page-scope segment rename | `goga_tool_pybuggy/web/pages.py` | `segments.insert(-1, ".cache")` + docstring example and wording |
| Manifest wording | `goga_tool_pybuggy/plugins/CODEMANIFEST` | `.cache subdirectory` / `.cache segment` at the 2 annotation sites |
| Manifest wording | `goga_tool_pybuggy/web/CODEMANIFEST` | `.cache segment` at the BasePage annotation site |
| Usage wording | `goga_tool_pybuggy/plugins/.usages/enable.md` | `.cache` segment beside the test module's path |
| Usage layout | `goga_tool_pybuggy/web/.usages/pybuggy-web.md` | Layout tree and addressing examples under `.cache/` |
| Docs | `docs/web/index.md`, `docs/web/configuration.md` | Layout tree, addressing prose, `cache_root` row |
| Skills | 12 `goga_tool_pybuggy/skills/*/SKILL.md` | `…/.cache/…` paths; stale pre-rename path in `pybuggy/SKILL.md` aligned |
| Test pins | `tests/plugins/test_web_plugin.py`, `tests/web/test_pages.py` | Expected `.cache` literals |

## Tests Added
None — the existing pins cover the changed behavior exhaustively; their expected values were
updated in place.

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| `goga_tool_pybuggy/plugins` | 2 annotation sites name `.cache` | `enable.md` segment wording |
| `goga_tool_pybuggy/web` | 1 annotation site names `.cache` | `pybuggy-web.md` layout and addressing |

## Validation Results
- `goga lint` — 27 cells, 0 errors.
- `goga contract` — no manifest-implementation inconsistencies.
- Differential suite run (sandbox without the private prettyplay 0.0.4 index; import-name stubs
  only): changed tree **2086 passed / 64 failed / 21 skipped**; the pre-change baseline fails the
  identical 64 (set-equal, zero flips in either direction) — the failures are tests of real
  prettyplay behavior the stub cannot carry; the change introduces no regression and fixes
  nothing outside its scope. The cache-path pins pass: `web_cache_path` units (7) and the whole
  `test_pages.py` module (41). Authoritative full gate: CI with the org index.
- `ruff check` on all changed files — clean; `ruff format --check` — clean. (Two pre-existing
  `PLR0917` findings in untouched `api/` files reproduce on the baseline under the sandbox's
  newer ruff 0.17.5 — not introduced by this change.)

## Compatibility Status
Breaking (user-overridden): generated cache paths move from `<path>/cache/…` to
`<path>/.cache/…`. Existing committed caches are missed until regenerated or renamed.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Consumer `.gitignore` ignoring `.cache` | High | Release note: un-ignore the step-cache `.cache` directories |
| Strict-run cache misses after upgrade | Medium | One-time regeneration or `git mv cache .cache` |

## Updated Files
- goga_tool_pybuggy/plugins/web_plugin.py
- goga_tool_pybuggy/plugins/CODEMANIFEST
- goga_tool_pybuggy/plugins/.usages/enable.md
- goga_tool_pybuggy/web/pages.py
- goga_tool_pybuggy/web/CODEMANIFEST
- goga_tool_pybuggy/web/.usages/pybuggy-web.md
- docs/web/index.md
- docs/web/configuration.md
- goga_tool_pybuggy/skills/pybuggy/SKILL.md
- goga_tool_pybuggy/skills/pybuggy-web-automate-accept-consistency/SKILL.md
- goga_tool_pybuggy/skills/pybuggy-web-automate-accept-run/SKILL.md
- goga_tool_pybuggy/skills/pybuggy-web-automate-accept-scope/SKILL.md
- goga_tool_pybuggy/skills/pybuggy-web-automate-design-review/SKILL.md
- goga_tool_pybuggy/skills/pybuggy-web-automate-design/SKILL.md
- goga_tool_pybuggy/skills/pybuggy-web-automate-plan-review/SKILL.md
- goga_tool_pybuggy/skills/pybuggy-web-automate-plan/SKILL.md
- goga_tool_pybuggy/skills/pybuggy-web-automate-requirements-report/SKILL.md
- goga_tool_pybuggy/skills/pybuggy-web-cookbook/SKILL.md
- goga_tool_pybuggy/skills/pybuggy-web-usage/SKILL.md
- tests/plugins/test_web_plugin.py
- tests/web/test_pages.py
