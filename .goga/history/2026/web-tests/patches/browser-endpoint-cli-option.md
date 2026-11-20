# Patch — browser-endpoint CLI option

Change Execution Report of the goga-change pipeline run (2026-11-02), branch `web-tests`.
Verdict: **VERIFIED**. User approvals on the run: breaking-change override (contract-pin test
evolution), Change Plan, scope extension (prettyplay 0.0.4 endpoint-scheme alignment).

# Change Plan (approved)

## Task Classification
Type: feature (extension) — an additive CLI value-option `--browser-endpoint` for the web run;
no existing behavior changes.

## Affected Cells

| Cell | Files to Modify | What Changes |
|---|---|---|
| `goga_tool_pybuggy/plugins` | `web_plugin.py`, `CODEMANIFEST`, `.usages/enable.md` | New option + document-copy injection before validation; WebPlugin contract; flag mention |
| `goga_tool_pybuggy/web` | `CODEMANIFEST` (2 lines) | `data` provenance of `validate_web_config` + single-CLI-override clause |
| docs | `docs/web/configuration.md`, `docs/web/index.md`, `docs/plugins/index.md` | `browser.endpoint` row, Run-modes table, Web CLI options, Related; pre-existing layering drift fixed |
| tests | `tests/plugins/test_web_plugin.py`, `tests/web/test_config.py` | Option-set pin extension + 7 new tests; endpoint-scheme pin alignment to 0.0.4 |

## Change Strategy
1. Option declaration after `interactive` — `define.option(str, nullable=True,
   command_line=CommandLine("--browser-endpoint", action="store", ...))`. No `plugin_config_key`
   (pluginator resolves config keys by a flat `.get()` — a nested `browser.endpoint` never
   resolves); no `env_var` (the env layer is scrubbed by design).
2. `configure()` reads `getoption("browser_endpoint", default=None)`, copies the document at read
   (`dict(self.plugin_config)` under the parse guard), and — when the flag is typed — injects the
   value into the browser section of the copy before `validate_web_config`. `is not None` =
   "typed": a typed empty string applies verbatim (forces the local launch over a document
   endpoint). `or {}` guards a `browser: null` document. The copy keeps the `cached_property`
   document unmutated.
3. The injected value passes the same single gate: an invalid endpoint fails at configphase with
   `web.yml: invalid web config document` (the library pydantic validator), never at a browser start.

## Compatibility Verification
Backward compatible: without the flag the document copy is identical, validation and activation
are bit-for-bit the same. All 5 behavioral criteria NO. The only touched test pins the exhaustive
option set — extended in the same change (user-approved override of the formal STOP).

## Test Strategy
Option-set pin (3 options, store spec, nullable, no config key); override + no-flag identity;
creates/null-guards the browser section; invalid flag fails configphase; typed empty forces local;
memo-safety (the read document never mutated); fixture flow-through into the runtime config;
endpoint-scheme pins per prettyplay 0.0.4 (http/https CDP accepted, garbage rejected).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Option name conflicts with consumer pytest options | Low | Medium | dest `browser_endpoint` unique; pluginator `register_once` idempotent |
| Flag-created browser section changes validation semantics | Low | Low | Same gate; fields fill from model defaults (name=chromium); pinned by test |
| "single source" wording drift across docs/manifests | Medium | Low | All sites updated in the same change; drift analysis swept the repo |

# Change Execution Report

## Summary
Added the `--browser-endpoint <url>` value-option to `WebPlugin` (the `pybuggy-web` pytest
plugin): a typed flag overrides `browser.endpoint` of `web.yml` for the run by injecting the value
into the document copy in `configure()` before validation, so the existing configphase gate stays
the single validation gate and the value flows into the runtime through `build_pretty_config`
untouched. The motivating consumer use case: running web suites against a remote Playwright
endpoint (ws/wss server or http/https CDP) without editing the committed `web.yml`
(giveit/api-tests). An approved scope extension aligned the endpoint-scheme test pin to the
prettyplay 0.0.4 semantics (http/https CDP accepted) that the repository already targets.

## Root Cause
Feature gap, not a defect: the only entry point of the `browser.endpoint` value was the document;
of the CLI sources the plugin declared just two `store_true` flags. Investigation (HIGH
confidence) verified the mechanics: pluginator registers value options automatically; the
descriptor chain resolves config keys by a flat `.get()` (pluginator/pytest.py:117), so a nested
key requires the configure-time injection; the library endpoint validator runs inside
`PrettyConfig.model_validate` at configphase (pinned by tests).

## Modified Cells

| Cell | Files Modified |
|---|---|
| `goga_tool_pybuggy/plugins` | `web_plugin.py`, `CODEMANIFEST`, `.usages/enable.md` |
| `goga_tool_pybuggy/web` | `CODEMANIFEST` (provenance + single-source clause + scheme wording), `config.py` (docstring wording) |
| docs | `docs/web/configuration.md`, `docs/web/index.md`, `docs/plugins/index.md` |
| tests | `tests/plugins/test_web_plugin.py`, `tests/web/test_config.py` |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| Option | `goga_tool_pybuggy/plugins/web_plugin.py` | `browser_endpoint = define.option(str, nullable=True, CommandLine("--browser-endpoint", action="store"))` — no config key, no env |
| Injection | `goga_tool_pybuggy/plugins/web_plugin.py` | `configure()`: flag read; document copied at read; `is not None` injection under `WebConfigKeys.BROWSER` with `or {}` null-guard; validation after |
| Docstrings | `goga_tool_pybuggy/plugins/web_plugin.py` | Class (options list, `browser_endpoint` attribute), `configure()` (injection step), `_scrub_prettyplay_env` (single-CLI-exception clause) |
| Wording | `goga_tool_pybuggy/web/config.py` | "a non-ws endpoint" → "an invalid remote endpoint" |

## Tests Added

| Test | File | What It Validates |
|---|---|---|
| `test_web_plugin_declares_the_web_options` (rework) | `tests/plugins/test_web_plugin.py` | 3 options; `--browser-endpoint` store; nullable; no config key |
| `test_configure_applies_cli_authority_browser_endpoint` | 〃 | Typed flag beats the document; untyped keeps it |
| `test_configure_browser_endpoint_creates_the_missing_browser_section` | 〃 | Section created; name fills the default |
| `test_configure_browser_endpoint_overrides_a_null_browser_section` | 〃 | `browser: null` + flag validates |
| `test_configure_typed_empty_endpoint_forces_local_launch` | 〃 | Typed empty applies verbatim |
| `test_configure_fails_configphase_on_invalid_typed_endpoint` | 〃 | Same gate; `activation is None` |
| `test_configure_does_not_mutate_the_read_document` | 〃 | Memo-safety of the cached document |
| `test_web_fixture_carries_the_typed_endpoint` | 〃 | Flow into the runtime config without touching `pretty.py` |
| `test_validate_web_config_accepts_http_cdp_endpoint` (new) | `tests/web/test_config.py` | 0.0.4: http/https CDP accepted |
| `test_validate_web_config_rejects_invalid_endpoint` (rework) | 〃 | Garbage rejected naming ws/wss or http/https |

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| plugins | Global annotations: three options; `WebPlugin` Algorithm step 1 — three options with the no-config-key rationale; property `browser_endpoint -> str \| None`; `configure()` — 6-step algorithm (injection step 3) + requirements (same-gate, no-mutation) | `.usages/enable.md`: flag in the web-flags sentence |
| web | Global annotation: single-source clause (the single CLI exception) + endpoint scheme ws/wss or http/https (CDP); `validate_web_config` `data` provenance + step-3 wording | `.usages/pybuggy-web.md`: §Run modes endpoint line |

## Validation Results
**VERIFIED**: full suite 2003 passed / 0 failed; `ruff check` + `format --check` clean (355 files);
`goga lint` 25 cells / 0 errors; end-to-end smoke via a real pytest run (flag registered by
pluginator, override reached the activation, invalid flag failed at configphase, no flag kept the
document value).

## Compatibility Status
COMPATIBLE (compatibility-guard verdict respected). Without the flag every run is identical.
One documented exception, user-approved before implementation: the contract-pin test of the
option set evolved with the contract.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| prettyplay 0.0.4 unreleased (index serves 0.0.3) — test env must install the 0.0.x checkout | Medium | Documented here; CI/envs install from the 0.0.x line; the released 0.0.3 fails the verbatim-adoption pin (pre-existing, unrelated to this change) |
| Flag-created browser section surprises a `browser:`-less document | Low | Same validation gate; defaults explicit; test-pinned |
| Consumer availability | Info | Available to giveit/api-tests after the dependency update |

## Updated Files
- `goga_tool_pybuggy/plugins/web_plugin.py`
- `goga_tool_pybuggy/plugins/CODEMANIFEST`
- `goga_tool_pybuggy/plugins/.usages/enable.md`
- `goga_tool_pybuggy/web/CODEMANIFEST`
- `goga_tool_pybuggy/web/config.py`
- `goga_tool_pybuggy/web/.usages/pybuggy-web.md`
- `docs/web/configuration.md`
- `docs/web/index.md`
- `docs/plugins/index.md`
- `tests/plugins/test_web_plugin.py`
- `tests/web/test_config.py`
