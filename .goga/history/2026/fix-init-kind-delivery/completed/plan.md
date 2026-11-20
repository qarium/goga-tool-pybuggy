# Change Plan + Change Execution Report — pybuggy init kind-gated delivery and web survey

Task classification: **bugfix** (user-reported defects in `pybuggy init`, kind cross-delivery and web-branch questions).
Date: 29/10/26. Pipeline: Bugfix/hotfix (goga-change). User approvals: defect intake q1; breaking-change override q2
(option A for the LLM questions); plan approval q3.

## Summary

The `pybuggy init` kind selection (api / web / both) leaked across kinds: an api-only project received the web usage
file, a web-only project received the api usage files AND the `pybuggy-api`/`pybuggy-asserts` registrations in its
`.goga/config.yml`, the web survey asked LLM questions without saying why a browser-test setup needs an LLM (the
models required free text), and the browser name was free text while the runtime accepts exactly five names. The fix
extends the bootstrap's existing kind signal (the engine-written `api.yml`/`web.yml`) to the usage copy and the api
registration, rewrites the web prompts with their purpose (models stay required), and turns the browser question into
a choice of the runtime matrix. Contracts moved in lockstep (CODEMANIFEST, cell usages, docs) and the pinning tests
were reworked to the corrected contract.

## Root Cause

- D1: `run_bootstrap` step 2 walked `_USAGE_ROOTS` (api + sandbox + web) unconditionally — the web root shipped
  `pybuggy-web.md` into api-only projects.
- D2: step 7 registered the api-root stems unconditionally (`_REGISTERED_USAGE_ROOTS` fixed, regardless of
  `api.yml`) — api files landed in web-only trees and api keys/annotations in web-only configs.
- D3: `survey_web_config` asked `Provider` / `Generation model` / `Classification model` with no purpose context,
  the two models as required free text — a web-only user could not answer.
- D4: `browser_name` was free text; the accepted set lives in the runtime (prettyplay
  `_BROWSER_MATRIX = ("chromium", "firefox", "webkit", "chrome", "msedge")`), so invalid names surfaced only at test
  startup ("must be one of: …").

All four reproduced deterministically on the real engine session + bootstrap before the fix and verified gone after.

## Modified Cells

| Cell | Files Modified |
|---|---|
| `goga_tool_pybuggy/commands/init` | `session.py`, `init.py`, `CODEMANIFEST`, `.usages/init.md`, `.usages/config-build.md` |
| tests (mirror) | `tests/commands/init/test_session.py`, `test_bootstrap.py`, `test_init.py`, `test_init_integration.py` |
| docs (outside cells) | `docs/cli/init.md`, `docs/getting-started.md` |

`goga_tool_pybuggy/web`: no change — its `BrowserSettings` semantics already cover the runtime matrix.

## Implemented Changes

| Change | File | Description |
|---|---|---|
| kind signals | `init.py` | `run_bootstrap` resolves `api_written`/`web_written` (the written tool configs) before step 2 |
| gated copy | `init.py` | `_USAGE_ROOTS` entries carry a kind-signal column; `_kind_gated_roots` returns the active roots (sandbox always) and DEBUG-logs each absent kind; `_discover_packaged_usages` takes the active roots |
| gated api registration | `init.py` | step 7 registers the api pair only when the api root was active; `conventions` stays kind-neutral and always registers |
| web survey prompts | `session.py` | provider prompt states the models' role; each model prompt states its job (still required, re-asked when empty) — approved option A |
| browser choice | `session.py` | `_BROWSER_NAMES` mirrors the prettyplay matrix; `browser_name` is a `click.Choice` of the five names (default chromium) |
| manifest | `CODEMANIFEST` | global annotations (both paragraphs), `run_bootstrap` steps 1/2/7 + Requirements + Constraints, `survey_web_config` algorithm + Requirements |
| usages | `.usages/init.md`, `.usages/config-build.md` | delivery table rows kind-gated; web-branch question list rewritten |
| docs | `docs/cli/init.md`, `docs/getting-started.md` | stage-2 intro, table rows, web-question fragments, packaged-roots note re-synced |

## Tests Added

| Test | File | What It Validates |
|---|---|---|
| `test_bootstrap_without_tool_configs_ships_sandbox_only_and_registers_conventions` | `test_bootstrap.py` | no tool configs → sandbox quartet only, `conventions` only |
| `test_bootstrap_api_kind_copies_api_and_sandbox_and_registers_api_pair` | `test_bootstrap.py` | api tree ships api+sandbox, registers the api pair, never the web file |
| `test_bootstrap_web_kind_copies_web_and_sandbox_and_registers_web_usage` | `test_bootstrap.py` | web tree ships web+sandbox, registers exactly `{pybuggy-web, conventions}` |
| `test_survey_web_config_browser_name_is_a_choice_of_the_runtime_matrix` | `test_session.py` | the browser ask is a choice of exactly the five runtime names, default chromium |

Plus the reworked pinning tests (see `06-tests.md` for the full list) and the two integration smokes asserting the
split end-to-end through the real engine.

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| `commands/init` | kind-gated copy/registration in the algorithm, Requirements, and Constraints; `survey_web_config` prompts and browser choice; both global annotation paragraphs | `init.md` delivery table + web branch; `config-build.md` question list |

## Validation Results

- Full suite: **1973 passed, 21 skipped** (21 = pre-existing web-runtime environment skips).
- `ruff check goga_tool_pybuggy/ tests/` — clean; `ruff format` clean on the touched trees.
- `goga lint` — 25 cells, 0 errors; manifest YAML parses (3 docs, 25 body types, footer intact).
- End-to-end repro: api-only → no `pybuggy-web.md`, registration `{conventions, pybuggy-api, pybuggy-asserts}`;
  web-only → no api files, registration `{conventions, pybuggy-web}`, playwright line present.

## Compatibility Status

Breaking change (same-inputs output differs: delivered file sets, `codemanifest.usages`/`annotations` content,
at-prompt browser rejection, new prompt texts) — escalated at Step 2, **user override received (q2)**, plan approved
(q3). Signatures, exit codes, `web.yml` payload shape, and the session seam unchanged; previously initialized
projects keep their files (nothing removed on upgrade).

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| A template-mode project without tool configs no longer gets the api registration it used to receive | medium | documented in the escalation and the usage tables; a template carrying `api.yml` opts in |
| The browser matrix constant ages if prettyplay adds a name | low | single commented constant mirroring the runtime; failure mode is a missing option, never an invalid write |
| Pre-existing docstring drift in `bootstrap.py` ("Six pure writers" vs nine) | info | out of scope — flagged as a recommended follow-up, untouched |

## Updated Files

- goga_tool_pybuggy/commands/init/session.py
- goga_tool_pybuggy/commands/init/init.py
- goga_tool_pybuggy/commands/init/CODEMANIFEST
- goga_tool_pybuggy/commands/init/.usages/init.md
- goga_tool_pybuggy/commands/init/.usages/config-build.md
- tests/commands/init/test_session.py
- tests/commands/init/test_bootstrap.py
- tests/commands/init/test_init.py
- tests/commands/init/test_init_integration.py
- docs/cli/init.md
- docs/getting-started.md

Pipeline artifacts: `01-scope.md`, `02-trace.md`, `03-investigation.md`, `breaking-escalation.md`,
`04-change-plan.md`, `05-compatibility.md`, `06-tests.md`, `07-manifests.md`, `08-usages.md`, `09-drift.md`,
`10-validation.md` — all in this topic directory.
