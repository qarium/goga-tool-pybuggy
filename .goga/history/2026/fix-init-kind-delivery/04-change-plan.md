# Change Plan

## Task Classification

Type: **bugfix** (user-reported defects in the `pybuggy init` kind-gated delivery and web survey; breaking-change override approved by the user in q2, 2026-10-29).

## Affected Cells

| Cell | Files to Modify | What Changes |
|---|---|---|
| `goga_tool_pybuggy/commands/init` | `init.py` | kind-gate the usage copy (per root) and the api registration (step 7) on the written `api.yml`/`web.yml` |
| `goga_tool_pybuggy/commands/init` | `session.py` | `survey_web_config`: explanatory provider/model prompts (models stay required), browser name becomes a choice of the five runtime-valid names |
| `goga_tool_pybuggy/commands/init` | `CODEMANIFEST` | `run_bootstrap` algorithm steps 2/7 + Requirements + global annotation paragraph; `survey_web_config` algorithm |
| `goga_tool_pybuggy/commands/init` | `.usages/init.md`, `.usages/config-build.md` | delivery table + web-branch question list rewritten to the kind-gated contract |
| `goga_tool_pybuggy/web` | — (no code change) | semantics only; `pybuggy-web.md` wording checked, unchanged unless it names the free-text browser question |
| tests (mirror, outside cells) | `tests/commands/init/test_session.py`, `test_bootstrap.py`, `test_init.py`, `test_init_integration.py` | pin the corrected contract |
| docs (outside cells) | `docs/cli/init.md`, `docs/getting-started.md` | delivery tables + web question list re-synced |

## Root Cause Analysis

From `03-investigation.md`: D1 — the copy step walks all `_USAGE_ROOTS` unconditionally (web file ships into api-only projects); D2 — step 7 registers the api pair unconditionally (api keys/annotations land in web-only configs, api files land in web-only trees); D3 — the web-branch LLM prompts carry no explanation and the models are required free text; D4 — `browser_name` is free text while the runtime (prettyplay `_BROWSER_MATRIX`) accepts exactly chromium/firefox/webkit/chrome/msedge.

## Trace Summary

From `02-trace.md`: the kind answer never crosses the session boundary; the engine-written `api.yml`/`web.yml` are the kind signals. The web-side steps are already gated on `web.yml`; the fix extends the same signal to the copy roots and the step-7 registration. `survey_web_config` → `build_web_config_data` → `web.yml` → `install_playwright` reads `browser.name` back — the payload shape is untouched.

## Change Strategy

1. **`init.py` — kind signals**: compute `api_written` alongside `web_written` at the top of `run_bootstrap` (both from `.goga/tools/pybuggy/<kind>.yml` existence).
2. **`init.py` — gated copy**: `_USAGE_ROOTS` entries gain a kind-signal column (`"api"` / `None` / `"web"`); `run_bootstrap` filters the roots to those whose signal file was written (`None` = always: the sandbox subtree) and DEBUG-logs each skipped root (mirroring the existing web-absent DEBUG). `_discover_packaged_usages` receives the active roots (private-helper signature change; facade unchanged).
3. **`init.py` — gated registration**: with discovery running over active roots only, the `registered` stems list is empty without `api.yml`, so step 7 registers only `conventions` for web-only/no-config trees; `_REGISTERED_USAGE_ROOTS` and `_register_web_kind` stay as they are.
4. **`session.py` — web survey (option A)**: provider prompt gains the purpose line (the LLM writes and classifies browser-test steps); the two model prompts state what each model does (and stay required — empty re-asks); `browser_name` becomes `click.Choice` of `_BROWSER_NAMES = ("chromium", "firefox", "webkit", "chrome", "msedge")` (default `chromium`), a commented module constant mirroring the prettyplay matrix. Question order and the returned key set unchanged.
5. **Contract surfaces in lockstep**: CODEMANIFEST (below), `.usages/init.md` + `.usages/config-build.md`, `docs/cli/init.md` + `docs/getting-started.md`, and a repository-wide text sweep for the retired wording ("always registered", "download-only" for the web stem, "every packaged usage", "seven stems", free-text browser wording).

## Specification Impact

- Global `Annotations` paragraph "The bootstrap closes kind-dependently…" — rewritten: both written files are kind signals; the api root's usage files and the api registration apply only when `api.yml` was written; the web root's file, the web registration, and the playwright line only when `web.yml` was written; the sandbox subtree and `conventions` are kind-neutral and always deliver.
- `run_bootstrap`:
  - Algorithm step 2 — per-root kind gate added; step 7 — "Register the api-root usage keys … only when the api config was written; `conventions` always".
  - Requirements — "every packaged usage … is copied" becomes "every packaged usage of the kinds the session wrote — plus the kind-neutral sandbox subtree — is copied; a kind's usages never ship without its written config"; the registration requirement gains the api kind gate; the existing web requirement stays.
  - Constraints — add: do not deliver or register a kind's usages when its config file is absent (the written file is the only kind signal).
- `survey_web_config` — algorithm step 1: provider asked as an explained choice; steps 2–3: required models whose prompts name their purpose; step 4: browser name asked as a choice of the five runtime-accepted names (default chromium).
- No signature changes; footer untouched.

## Usage Impact

- `.usages/init.md`: the artifact-table rows for the flat usage files and the registration row gain the per-kind gates; the web-branch bullet list shows the explained prompts and the browser choice.
- `.usages/config-build.md`: the "web branch" question list rewritten the same way; the "What is asked" wording for `browser_name` states the five valid names.
- `docs/cli/init.md`, `docs/getting-started.md`: the two delivery tables and the web-question fragment re-synced (same statements, user-facing voice).
- `goga_tool_pybuggy/web/.usages/pybuggy-web.md`: checked for the surveyed-minimum wording; expected unchanged (it does not name the browser question form).

## Compatibility Verification

NOT backward compatible for identical inputs — generated file sets and `codemanifest.usages`/`annotations` content change per kind, and out-of-matrix browser names are rejected at the prompt instead of at test runtime. Verdict recorded in `breaking-escalation.md`; **user override received (q2)** — the pipeline STOP is discharged and the plan proceeds within the approved scope. Routine signatures, exit codes, `web.yml` payload shape, and the session seam are unchanged.

## Test Strategy

- `test_session.py`: update the two `survey_web_config` tests to the new prompt texts; add an assertion that the browser question is a choice of exactly the five names and that an out-of-matrix answer is rejected by the prompt (choice type), plus an explanation-text assertion (the prompts name the LLM purpose).
- `test_bootstrap.py::TestRunBootstrapUsages`: rework the two distribution tests — a no-tool-config tree ships only the sandbox quartet and registers only `conventions`; an api-kind tree (api.yml seeded) ships api+sandbox, registers the api pair, and does NOT ship `pybuggy-web.md`; add the web-kind variant (web.yml seeded → `pybuggy-web.md` only + its registration).
- `test_init.py`: update the kind tests — web-kind registration set becomes `{"pybuggy-web", "conventions"}` and the api files are absent; api-only additionally asserts `pybuggy-web.md` is not delivered; both-kind set unchanged; re-seed/adjust the no-config tests (`missing_dockerfile`, `corrupt_web_config`, `bare_mode_gates`, `existing_config_session_end`, `empty_and_broken`, `non_string`, `corrupt_config`, `idempotent_rerun`) to the gated contract.
- `test_init_integration.py`: api-only smoke asserts `pybuggy-web.md` not downloaded (registration set unchanged); web-kind smoke — new prompt texts, registration set `{"pybuggy-web", "conventions"}`, api files not downloaded.
- Full suite + `ruff check goga_tool_pybuggy/ tests/` + `goga lint` green; repo-wide grep for the retired wording returns only deliberate history entries.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A template-mode project without tool configs silently loses the api registration it used to get | medium | medium | documented in the escalation (row 4) and the usage tables; the template can carry `api.yml` to opt in — noted in `init.md` |
| The prettyplay matrix drifts (new browser name) and the choice list ages | low | low | the constant is commented as a mirror of the runtime matrix; failure mode is a missing option, never an invalid write |
| Prompt-text churn breaks scripted-TTY tests beyond the four files listed | medium | low | the scripted double keys on exact texts; a full-suite run catches every miss |
| Docs/usage mirrors drift from the new contract | low | low | repository-wide text sweep for the retired wording is a plan task |
| Hidden consumers of the unconditional api registration | low | medium | within-package grep for `register_usages`/`pybuggy-api` callers; only the bootstrap and its tests reference them |
