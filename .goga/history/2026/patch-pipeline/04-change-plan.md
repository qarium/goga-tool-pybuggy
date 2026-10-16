# Change Plan — Patch cycle 2 (init autonomy for api.patch)

## Task Classification

**Feature** (extension of the onboarding autonomy opt-in to the `api.patch` axis).

## Affected Cells

| Cell | Files to Modify | What Changes |
|------|-----------------|--------------|
| `goga_tool_pybuggy/commands/init` | `session.py`, `CODEMANIFEST` | `survey_autonomy` prompt covers both pipelines; `build_config_data` enabling branch writes both axis records; the two manifest annotations track the current state |
| — (package data, not cells) | `docs/getting-started.md`, `docs/cli/init.md`, `docs/pipelines/api-patch.md` | Survey descriptions, prompt text, payload YAML, and the "covers only the `api.automate` axis" parenthetical |
| — (tests) | `tests/commands/init/test_session.py`, `tests/commands/init/test_init_integration.py`, `tests/test_autonomy_integration.py` | Pin the new prompt/payload; add the `resolve_autonomy("api.patch")` acceptance assertion |

No other cell changes: `config` (resolver contract already per-name), `autonomous`
(records already carry both axes), root (subscription untouched).

## Root Cause Analysis

The onboarding autonomy path predates `api.patch`: the confirm prompt and the payload
branch hardcode the single `api.automate` axis (session.py:187, 225-226). The consumer
chain (`resolve_autonomy` ← `PATCH_CONTRIBUTION.axis == "api.patch"`) and
`docs/configuration.md` already support the patch axis — init is the only gap
(03-investigation.md).

## Trace Summary

Amendment moment: `amend_pybuggy_config` → `survey_autonomy` (one confirm, automate-only
wording) → `build_config_data` → `context.write_config` → fresh
`.goga/tools/pybuggy/config.yml` → (run time) `amend_workflow` → `resolve_autonomy(axis)`
→ per-pipeline contribution. The change touches the two producer literals and everything
that pins their old text (02-trace.md).

## Change Strategy

Design decision (resolved with the user at plan approval, `autonomous_execution.q2` —
**Option B chosen**: "надо по отдельности спрашивать про оба пайплайна"):

- **B — one confirm per pipeline** (implemented): `survey_autonomy` asks one question per
  autonomous pipeline in a fixed axis order — automate first, patch after it — each
  "Run the {axis} pipeline unattended (autonomous mode)?" (default No). Each enabling
  answer writes its own axis entry; both accepted reproduce the user's both-true YAML.
- A — one combined confirm (rejected by the user).

Steps:

1. `session.py` — module constant `_AUTONOMY_AXES: tuple[str, ...] = ("api.automate",
   "api.patch")` (the question order and the payload order derive from it).
2. `session.py :: survey_autonomy` — returns `dict[str, bool]` keyed by axis: one
   `click.confirm` per axis of `_AUTONOMY_AXES`, the interpolated prompt keeping the
   automate question byte-identical to the historical one; docstring updated (Returns:
   answers keyed by axis — true enables that pipeline's unattended window).
3. `session.py :: build_config_data` — third parameter becomes
   `autonomous: dict[str, bool] | None = None`; writes `data["pipelines"]` with a record
   per enabled axis of `_AUTONOMY_AXES` (survey shape respected, unknown keys ignored);
   no enabled axis (None, absent, or all-false) writes no `pipelines` key — the
   declined-writes-nothing guarantee preserved.
4. `commands/init/CODEMANIFEST` — current-state updates: the `survey_autonomy` signature
   and annotation (per-axis algorithm), the `build_config_data` signature and annotation
   (step 3 + param line), the `amend_pybuggy_config` step 4 and `pybuggy_questions`
   constraint pluralized ("autonomy confirms/questions"), and the cell-header sentence
   ("the autonomy confirms … specs first, autonomy after them").
5. Tests (mirror structure per `conventions`):
   - `tests/commands/init/test_session.py` — the two signature tables (`autonomous`
     param type, `survey_autonomy` return type); `TestSurveyAutonomy`: both-defaults,
     both-accepted, and the mixed answer (automate yes / patch no — the per-pipeline
     semantics); `TestBuildConfigData`: both-enabled payload (order + serializability),
     single-axis payload, and the no-axis parametrization (None / all-false /
     stale-answer-key).
   - `tests/commands/init/test_init_integration.py` — `_CONFIRM_ANSWERS` and
     `_EXPECTED_CONFIRMS` gain the patch question (after automate); the
     autonomy-accepted test enables both and asserts both entries.
   - `tests/test_autonomy_integration.py ::
     TestEmitConsumeBridge.test_build_config_data_payload_enables_resolve_autonomy` — the
     enabling payload carries both axes: `resolve_autonomy("api.automate")` and
     `resolve_autonomy("api.patch")` both True (the acceptance gate of `todo.md`).
6. Docs:
   - `docs/getting-started.md` — the confirm description: two questions, one per
     pipeline; Yes writes that pipeline's entry; link both autonomous-runs sections.
   - `docs/cli/init.md` — the two prompts and the payload YAML (both entries when both
     accepted); the closing cross-reference names both pipelines.
   - `docs/pipelines/api-patch.md` — drop "(the autonomy confirm of `pybuggy init`
     covers only the `api.automate` axis)" → its own confirm now covers it.
7. Validation: `pytest tests/ -x` and `ruff check` in the project venv (`.venv`).

## Specification Impact

- `commands/init/CODEMANIFEST`:
  - `"survey_autonomy() -> autonomous:bool"` annotation — Algorithm step 1 and the
    `autonomous` description (both windows).
  - `"build_config_data(...)"` annotation — Algorithm step 3 ("add the pipelines axis
    entries — the api.automate and api.patch records with autonomous true") and the
    `autonomous` param line ("false writes no axis entries").
  - Cell header, `amend_pybuggy_config`, `pybuggy_questions` — verified: no automate-only
    wording; unchanged.
- No other CODEMANIFEST changes.

## Usage Impact

- `goga_tool_pybuggy/config/.usages/autonomy.md` — **no change**: the contract is
  per-pipeline-name (unchanged); its single-entry example remains a valid minimal shape
  (same decision as `docs/configuration.md`, whose example also stays minimal).
- `.goga/usages/conventions.md` — no change (rules applied, not modified).

## Compatibility Verification

Not backward compatible by the letter of the policy — `build_config_data(…, True)` gains
an entry and the confirm is reworded (investigation §Breaking Change Assessment: 1/3/6 =
YES). Bounded by three facts: the change is the user's explicit request (their `q1`
answer specifies the target payload verbatim — the user override of the STOP); only
**freshly created** config trees are affected (the session refuses an existing
`.goga/config.yml` before any tool moment — no rewrite path exists); the consumer side is
additive (`api.patch` is already a resolver-valid axis). Existing projects, existing
configs, and automate's contribution behavior are untouched. **Proceeding under the
user's mandate, confirmed at plan approval.**

## Test Strategy

- Behavior pins updated: the new prompt text (unit, scripted click), the two-record
  payload with key order and plain-serializability intact (unit), the end-to-end session
  confirm wiring and written tool config (integration, real config tree).
- Acceptance added: the enabling payload round-trips through the real resolver with
  `resolve_autonomy("api.patch") is True` (emit↔consume bridge).
- Disabling path stays pinned: no `pipelines` key on False (existing parametrized test
  unchanged — verifies the "never writes when declined" guarantee).
- Gates: `pytest tests/ -x` green; `ruff check` clean.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Missed test pinning the old strings | Low | Red gate | Three suites enumerated; full `-x` run |
| Manifest drift (annotation lagging code) | Low | goga lint failure | Manifest + code edited in the same step; reconciliation step re-verifies |
| Docs inconsistency (a page still describing automate-only confirm) | Medium | User confusion | Four pages enumerated (getting-started, cli/init, api-patch, api-automate checked); drift step re-greps |
| Unintended automate regression | Low | Regression | Automate autonomy tests untouched and green; window/build records untouched |
| UX regression from reworded confirm | Low | Behavior choice | Design decision confirmed with the user at plan approval |
