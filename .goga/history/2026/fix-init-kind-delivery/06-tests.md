# Test Report

## Changes Requiring Coverage

| Change | Type |
|---|---|
| Kind-gated usage copy (api root ↔ `api.yml`, web root ↔ `web.yml`, sandbox always) | behavior + edge |
| Kind-gated api registration (step 7 registers the api pair only with `api.yml`; `conventions` always) | behavior + edge |
| No-tool-config tree (existing-config session end, empty/absent config) ships sandbox + conventions only | edge |
| `both` kind still ships and registers everything (regression of the pre-existing both-path) | regression |
| `survey_web_config` explanatory prompts, models still required (re-ask) | behavior |
| `browser_name` is a choice of exactly the five runtime names, default chromium | behavior |
| Corrupt `web.yml` still counts as the web signal for the copy, api stays out | edge |
| Real-engine end-to-end: api-only and web-only sessions deliver/ask exactly their kind | manifest (integration) |

## Tests Added

| Test Name | File | What It Validates |
|---|---|---|
| `test_bootstrap_without_tool_configs_ships_sandbox_only_and_registers_conventions` | `tests/commands/init/test_bootstrap.py` | no tool configs → only the sandbox quartet lands, only `conventions` registers |
| `test_bootstrap_api_kind_copies_api_and_sandbox_and_registers_api_pair` | `tests/commands/init/test_bootstrap.py` | api tree ships api+sandbox byte-identical, registers the api pair, never ships `pybuggy-web.md` |
| `test_bootstrap_web_kind_copies_web_and_sandbox_and_registers_web_usage` | `tests/commands/init/test_bootstrap.py` | web tree ships web+sandbox only, registers exactly `{pybuggy-web, conventions}` |
| `test_survey_web_config_browser_name_is_a_choice_of_the_runtime_matrix` | `tests/commands/init/test_session.py` | the browser ask is a `click.Choice` of exactly chromium/firefox/webkit/chrome/msedge, default chromium |

## Tests Modified

| Test Name | File | Change |
|---|---|---|
| `test_survey_web_config_asks_minimum_in_order` / `..._reasks_empty_models` | `test_session.py` | the new explanatory prompt texts (order and required re-ask pinned on them) |
| `test_run_bootstrap_missing_dockerfile_fails_with_error` (2 params) | `test_init.py` | kind-neutral delivery asserted (sandbox ships, api does not) |
| `test_run_bootstrap_corrupt_web_config_fails_at_documentation` | `test_init.py` | the corrupt web.yml counts as the web signal; api stays out |
| `test_run_bootstrap_bare_mode_gates` | `test_init.py` | api.yml seeded — the stale-copy overwrite keeps its meaning for an api-kind tree |
| `test_run_bootstrap_existing_config_session_end_still_enforces` | `test_init.py` | conventions-only registration for a no-tool-config tree |
| `test_run_bootstrap_idempotent_rerun` | `test_init.py` | skip-warning counts 1/1 (conventions only) |
| `test_run_bootstrap_empty_and_broken_config_variants` (2 params) | `test_init.py` | conventions-only registration |
| `test_run_bootstrap_web_kind_delivers_web_artifacts` | `test_init.py` | registration set `{pybuggy-web, conventions}`; api files absent |
| `test_run_bootstrap_api_only_skips_web_steps` | `test_init.py` | `pybuggy-web.md` no longer delivered |
| `_assert_bootstrap_registration_split` + the web-kind smoke | `test_init_integration.py` | end-to-end: api-only ships no web file; web-only registers no api keys and ships no api files; new model prompt texts scripted |

## Test Results

| Test | Status | Details |
|---|---|---|
| `tests/commands/init/` (164) | PASS | 164 passed |
| Full suite | PASS | 1973 passed, 21 skipped (21 web-runtime skips — prettyplay/browser environment, pre-existing pattern) |
| `ruff check goga_tool_pybuggy/ tests/` | PASS | All checks passed |
| `ruff format --check` (init cell + its tests) | PASS | clean after one reformat |
| `goga lint` | PASS | 25 cells, 0 errors |

## Coverage Gaps

| Changed Behavior | Covered? | Notes |
|---|---|---|
| Kind-gated copy per root | YES | unit (3 kind variants) + integration (both kinds) |
| Kind-gated api registration | YES | exact registration sets asserted in 5 tests |
| Explanatory prompts / required models | YES | prompt texts pinned in unit + integration |
| Browser choice | YES | the choice set and default asserted directly |
| Absent-kind DEBUG log line | NO (accepted) | log-only side effect; the delivery outcomes are asserted — consistent with the suite, which never asserted the former web-absent DEBUG either |

## Missing Coverage Analysis

Nothing behavioral is untested. The only unasserted artifact is the per-absent-kind DEBUG log — a diagnostic line with no contract weight; asserting it would couple tests to log formatting without protecting any behavior.
