# Patch — the init session never asks the language question (python fixed)

Change Execution Report of the goga-change pipeline run (2026-11-19), branch `web-tests`.
Verdict: **VERIFIED (sandbox differential + live smoke)**. User approvals on the run: task
clarification (the TODO file was absent — the task arrived as the user's answer), Change Plan +
breaking-change override (the surveyed language choice disappears from the wizard).

# Change Plan (approved)

## Task Classification
Type: behavior fix (wizard simplification) — the engine's core "Language (python, golang,
kotlin, swift, javascript)" question never appears in a pybuggy-invited session; the project
language is fixed `python` and recorded into `.goga/config.yml` through the session amendments.
pybuggy is python-only (pytest runtime, goga-python image family, python conftest), so the
question carried no decision.

## Affected Cells

| Cell | Files to Modify | What Changes |
|---|---|---|
| `goga_tool_pybuggy/commands/init` | `session.py`, `CODEMANIFEST`, `.usages/init.md`, `.usages/config-build.md` | `declare_pybuggy_session` skips the core `language` section (first skip); `build_config_amendments` buffers `language: python` as the first amendment; docstrings; manifest global + 2 type annotations; both usage files |

Non-cell surfaces in the same change: `docs/cli/init.md`, `tests/commands/init/test_session.py`,
`tests/commands/init/test_init_integration.py`.

## Change Strategy
1. Engine contract reuse — the same skip+amend mechanism already used for `convention` and
   `docker_image`: `context.skip("language")` prunes the section from the session plan (the
   question is never asked); the `language → python` amendment lands top-level in the answer
   space, and the engine generator writes it into `config.yml` (`snapshot["language"]`).
2. Manifest: global annotation "two core sections" → "three" (+ the language rationale);
   `declare_pybuggy_session` gains the skip step; `build_config_amendments` gains the amendment
   step and the single-source requirement (the skipped question leaves the amendment the only
   source of the recorded language).
3. Usages and docs describe the fixed language (asked-set, skips list, contribution list).
4. Tests: the skips pin and the amendments pin gain the language entries; the three scripted
   `"Language"` answers are removed; absence pins assert the prompt is never asked (and the
   unscripted defaultless choice prompt would fail the scripted TTY outright on regression).

## Compatibility Verification
NOT backward compatible — user-approved override:
- the interactive wizard changes: a question that was asked is no longer asked;
- a non-python language can no longer be recorded in a pybuggy session (such a project was
  already unservable — pytest runtime, python-family images, python conftest);
- `.goga/config.yml` output is unchanged for every session that answered python (the default
  first choice): `language: python` still lands, now via the amendment.
- Dropped-contribution path (e.g. a non-numeric timeout answer): the old flow failed at the
  bootstrap's mandatory-Dockerfile check (exit 1, "Dockerfile missing"); the new flow fails at
  session generation on the missing language (exit 1, one clean message) — same terminal
  outcome, earlier and cleaner.

## Test Strategy
No new test files: the behavior is fully pinned by the existing suite (declare-hook skips pin,
amendments pins, session smoke with the real engine and registry). Pins updated in place; two
absence pins added to the smoke tests.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A future engine change renames the core `language` section | Low | The skip no-ops with an engine warning; the amendment still records the language | The smoke tests pin the absence of the prompt and the config value |
| A dropped tool contribution leaves no language → session error | Low | Exit 1 with a clean message instead of a silently pybuggy-less project | Documented in the manifest requirement and the usage |

# Artifacts

| Layer | File | Change |
|---|---|---|
| Code | `goga_tool_pybuggy/commands/init/session.py` | `context.skip("language")`; `"language": "python"` first amendment; 2 docstrings; the `_BASE_IMAGE_NAMES` comment |
| Manifest | `goga_tool_pybuggy/commands/init/CODEMANIFEST` | Global annotation (three skips), `declare_pybuggy_session` (step + summary), `build_config_amendments` (step + requirement) |
| Usages | `.usages/init.md`, `.usages/config-build.md` | Three-skips list + language bullet; fixed-language wording; the `language: python` amendment bullet |
| Docs | `docs/cli/init.md` | Asked-set drops "the language"; three-skips list + bullet; the amendment in the enumeration |
| Tests | `test_session.py`, `test_init_integration.py` | Skips pin ×3; six-entry amendments pin; `snapshot["language"]` merge pin; scripted Language answers removed; two absence pins |

# Tests Added
None as files — updated pins in place plus two absence assertions
(`"Language" not in {…tty.prompts}`) in the api and web smoke tests.

# Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| `goga_tool_pybuggy/commands/init` | Global annotation; `declare_pybuggy_session`; `build_config_amendments` | `init.md` skips + amendments; `config-build.md` asked-set + contribution |

# Validation Results
- `goga lint` — 27 cells, 0 errors.
- `goga contract` — no manifest-implementation inconsistencies.
- Differential suite run (sandbox without the private prettyplay 0.0.4 index; import-name/field
  stubs only: `SiteConfig`, `request_max_tokens`, `send_structure`, `site`): changed tree
  **2142 passed / 8 failed / 21 skipped**; the pre-change baseline fails the identical 8
  (set-equal, zero flips in either direction) — the failures are tests of real prettyplay 0.0.4
  behavior the stub cannot carry; the change introduces no regression and fixes nothing outside
  its scope. The init-cell modules (`test_session.py`, `test_init_integration.py`,
  `test_init.py`, `test_bootstrap.py` web-documentation aside) pass. Authoritative full gate:
  CI with the org index.
- `ruff check` on all changed files — clean; `ruff format --check` — clean. (Two pre-existing
  `PLR0917` findings in untouched `api/` files reproduce on the baseline under the sandbox's
  newer ruff 0.17.5 — not introduced by this change.)
- Live smoke (scripted TTY, real engine + registry): the wizard starts at the codemanifest
  gates — no `Language` prompt; exit 0; `.goga/config.yml` carries `language: python`.

# Compatibility Status
Breaking (user-overridden): the language question disappears from the pybuggy onboarding
wizard; the recorded language is always `python`.

# Updated Files
- goga_tool_pybuggy/commands/init/session.py
- goga_tool_pybuggy/commands/init/CODEMANIFEST
- goga_tool_pybuggy/commands/init/.usages/init.md
- goga_tool_pybuggy/commands/init/.usages/config-build.md
- docs/cli/init.md
- tests/commands/init/test_session.py
- tests/commands/init/test_init_integration.py
