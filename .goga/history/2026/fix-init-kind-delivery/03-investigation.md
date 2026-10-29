# Investigation Report

## Task Summary

User-reported defects in `pybuggy init` around the surveyed test kind: with api-only, the web usage is delivered into the target project; with web-only, the api usages are delivered AND registered into `.goga/config.yml` (`codemanifest.usages`/`annotations`), and the web branch asks LLM questions (Provider, Generation model, Classification model) the user cannot answer; the browser-name question accepts any text while the runtime accepts only chromium/firefox/webkit/chrome/msedge ("must be one of: …" at test runtime). Requested outcome: delivery, registration, and questions match the selected kind and are answerable.

## Candidate Cells

| Cell | Reason | Priority |
|---|---|---|
| `goga_tool_pybuggy/commands/init` | Owns the kind-gated surveys, the usage distribution/registration, and the web bootstrap steps | 1 |
| `goga_tool_pybuggy/web` | Semantic source of the browser-name constraint and the provider/model fields the questions mirror | 2 |

## Tracing Summary

See `02-trace.md`. The kind answer never crosses the session boundary; the bootstrap's kind signal is the engine-written tool config (`api.yml` for api/both, `web.yml` for web/both). The web-side bootstrap steps are already gated on `web.yml` presence; the copy step (all `_USAGE_ROOTS`) and the api registration step (step 7) are unconditional.

## Data Flow Analysis

Reproduced deterministically on the real engine session + bootstrap (scripted TTY, fresh temp project per kind; environment prepared by installing the project deps incl. prettyplay):

- **kind=api**: downloaded usages = `api.md, asserts.md, data-operations.md, migration-set.md, pybuggy-web.md, sandbox-file.md, sandbox-session.md`; `codemanifest.usages` = `conventions, pybuggy-api, pybuggy-asserts`; tool configs = `api.yml`.
- **kind=web**: downloaded usages = the same seven files (api files included); `codemanifest.usages` = `conventions, pybuggy-api, pybuggy-asserts, pybuggy-web`; annotations carry the api lines; tool configs = `web.yml`; Dockerfile gains the playwright line.
- The web-only session asks (in order): Provider (choice openai/anthropic), Generation model (required), Classification model (required), Browser name (free text, default chromium), headless (confirm) — the first three are the questions the reporting user could not answer.

## Manifest Algorithm Analysis

`commands/init` CODEMANIFEST today MANDATES the defective behavior: `run_bootstrap` step 2 copies "the api cell, the cells of the sandbox subtree, and the web cell" unconditionally; its Requirement says "every packaged usage — including the sandbox capability usages — is copied"; step 7 registers the api-root keys with no kind gate. The global annotation's "The api and web question sets never cross" covers only the questions. So code and manifest are CONSISTENT with each other and BOTH diverge from the user-required behavior — the fix must change the manifest contract alongside the code (the written-file kind signal extended to the copy and the api registration).

## Affected Usages

| Usage | Cell | Classification | Reason |
|---|---|---|---|
| `.usages/init.md` | `commands/init` | DIRECTLY AFFECTED | artifact table documents the unconditional copy and the always-on api registration |
| `.usages/config-build.md` | `commands/init` | DIRECTLY AFFECTED | documents the web-branch question set (browser_name free text, required models) |
| `.usages/pybuggy-web.md` | `web` | INDIRECTLY AFFECTED | delivered practice; checked for browser-name wording consistency, content expected unchanged |
| `docs/cli/init.md`, `docs/getting-started.md` | outside cells | DIRECTLY AFFECTED | user-facing flow docs mirror the delivery table (per project memory: every mirrored surface moves in lockstep) |

## Rejected Hypotheses

| Hypothesis | Rejection evidence |
|---|---|
| "With api-only the web usage gets REGISTERED in codemanifest.usages/annotations (literal reading of the report)" | Reproduction shows `pybuggy-web` NOT registered at kind=api (`_register_web_kind` is gated on `web.yml`, which the api branch never writes). The visible defect at api-only is the downloaded `pybuggy-web.md` file plus the config gaining the codemanifest section (api entries); the registration half of the user's sentence matches the WEB-only run, where api entries do land. Both directions are real defects regardless of the conflation. |
| "The kind answer is lost / defaults to api, so web.yml is written for api-only or vice versa" | Reproduction: kind=api writes only `api.yml`; kind=web writes only `web.yml` — the session gating is correct. |
| "The engine (goga onboarding) itself registers the pybuggy usages into the config" | The engine's codemanifest gates were declined in the reproduction and the registrations still appeared — they come from `register_usages`/`register_annotations` in the pybuggy bootstrap (step 7 + `_register_web_kind`). |
| "The sandbox usage copy is part of the defect" | Sandbox usages are kind-neutral (apply to both kinds) and documented as download-only by design; the user report names the api/web crossing only. Out of scope. |
| "The browser message comes from pybuggy's own validation" | pybuggy `BrowserSettings.name` is a free `str`; the message text lives in prettyplay (`_BROWSER_MATRIX`, `config/models.py:11,84`). Pybuggy never validates the name today. |

## Confirmed Root Cause

Four deterministic causes, all reproduced:

- **D1 (api-only cross-delivery)**: `run_bootstrap` step 2 walks `_USAGE_ROOTS` unconditionally — the web root ships `pybuggy-web.md` into an api-only project (`init.py:62`, copy loop `init.py:324-332`).
- **D2 (web-only cross-registration)**: step 7 registers `_REGISTERED_USAGE_ROOTS` (the api pair) plus `conventions` unconditionally — a web-only project's `.goga/config.yml` gains `pybuggy-api`/`pybuggy-asserts` keys and annotation lines (`init.py:368-375`); the api usage FILES also land via D1's loop.
- **D3 (unanswerable web questions)**: `survey_web_config` asks `Provider` / `Generation model (step-code generation)` / `Classification model (step classification)` with no explanation of why a browser-test setup needs an LLM, the two models being required free-text (`session.py:233-239`) — the reporting user could not answer them.
- **D4 (browser-name validation gap)**: `browser_name` is free text (`session.py:237`); the accepted set is fixed by the runtime (prettyplay `_BROWSER_MATRIX = ("chromium", "firefox", "webkit", "chrome", "msedge")`); an invalid name passes init and fails only at test runtime with "must be one of: chromium, firefox, webkit, chrome, msedge".

## Confidence Level

**HIGH** — every defect reproduced deterministically on the real engine session + bootstrap; every cause pinned to exact lines; the runtime browser matrix located in prettyplay source; current tests explicitly pin the defective behavior (see below), confirming it is deliberate-but-wrong rather than environmental.

## Breaking Change Assessment

1. **Will existing function call with same arguments produce different behavior?** YES — `run_bootstrap(...)` over a web-only tree will no longer register `pybuggy-api`/`pybuggy-asserts`; over an api-only tree it will no longer copy `pybuggy-web.md` (and vice versa for the api files). Same inputs, different artifacts.
2. **Will existing file paths change?** YES (delivered set) — `.goga/usages/cooks/pybuggy/pybuggy-web.md` will not exist for api-only projects; `api.md`/`asserts.md` will not exist for web-only projects.
3. **Will output format change?** YES (config content) — a web-only `.goga/config.yml` will no longer carry the api usage keys/annotation lines.
4. **Will return value semantics change?** NO — exit codes and all routine signatures stay unchanged.
5. **Will manifest-defined guarantees be altered?** YES — the `run_bootstrap` Requirements ("every packaged usage … is copied", unconditional step 7) are rewritten to the kind-gated form; tests pinning them change (`test_bootstrap.py::TestRunBootstrapUsages` asserts the seven stems without api.yml; `test_init.py::test_run_bootstrap_web_kind_delivers_web_artifacts` asserts the api pair in a web-only config; `test_init.py::test_run_bootstrap_api_only_skips_web_steps` asserts the web file copy at api-only).
6. **Will existing tests break?** YES — the three named bootstrap/init tests (plus any docs assertions) must be updated to the corrected contract.

**BREAKING CHANGE DETECTED** — observable output for identical inputs changes (generated files and config content). Per the project rule, corrective intent does not downgrade it; explicit user override required before implementation (escalation below). D3/D4 change prompt behavior (D4 rejects previously-accepted free text at the prompt) — same class, folded into the same escalation.
