# Trace Report

## Call Flow

```
init_cmd (init.py)
└── run_init (init.py)
    ├── resolve_init_mode
    ├── run_session (session.py) ── engine-owned onboarding session
    │   ├── [declare moment] declare_pybuggy_session ── pybuggy_questions (kind, base_image, image)
    │   │     + context.skip("convention"), context.skip("docker_image")
    │   └── [amend moment] amend_pybuggy_config
    │       ├── kind ∈ {api, both}: survey_api_options → survey_specs → survey_autonomy
    │       │                    → build_config_data → context.write_config("api.yml")
    │       └── kind ∈ {web, both}: survey_web_config → build_web_config_data
    │                             → context.write_config("web.yml")
    └── run_bootstrap (init.py)
        ├── _discover_packaged_usages ── walks _USAGE_ROOTS (api, sandbox, web)
        │   └── copies EVERY discovered .usages/*.md → .goga/usages/cooks/pybuggy/…   [UNCONDITIONAL]
        ├── document_config_examples(api.yml)            ── no-op when api.yml absent
        ├── [web_written] document_web_config_examples(web.yml)
        ├── ensure_review_skip(config)
        ├── install_pybuggy(dockerfile)
        ├── [web_written] _register_web_kind ── register_usages/register_annotations(pybuggy-web)
        │                    └── install_playwright(dockerfile)   ── browser from web.yml
        ├── register_usages/register_annotations(pybuggy-api, pybuggy-asserts, conventions)  [UNCONDITIONAL]
        └── _gate_conftest
```

## Data Flow

- The kind answer lives only inside the session; it never crosses the session boundary. The bootstrap's only kind signals are the files the engine wrote: `.goga/tools/pybuggy/api.yml` (api/both) and `.goga/tools/pybuggy/web.yml` (web/both) — `web_written = web_config.exists()` in `run_bootstrap` (`init.py:319`).
- Usage delivery: `_USAGE_ROOTS` (`init.py:62`) lists api (flat), sandbox (`sandbox/` subdir), web (flat). Step 2 copies all of them regardless of kind; `_REGISTERED_USAGE_ROOTS = ("goga_tool_pybuggy.api",)` (`init.py:68`) feeds the unconditional step-7 registration of `pybuggy-api`/`pybuggy-asserts` (+ `conventions`); the web stem registers only inside the `web_written` branch.
- Web answers: `survey_web_config` (`session.py:219`) returns `{provider, generation_model, classification_model, browser_name, headless}` → `build_web_config_data` → engine writes `web.yml` → `install_playwright` reads `browser.name` back from the written file.
- Browser name: free `str` in `BrowserSettings` (web/config.py:30) and a free-text prompt (`session.py:237`); the only constraint lives in the runtime — prettyplay `_BROWSER_MATRIX = ("chromium", "firefox", "webkit", "chrome", "msedge")` (`prettyplay/config/models.py:11`), raising `ValueError("must be one of: chromium, firefox, webkit, chrome, msedge")` at load.

## Manifest Algorithm Mapping

| CODEMANIFEST (commands/init) step | Code path | Match |
|---|---|---|
| `run_bootstrap` step 2 "copy each under .goga/usages/cooks/pybuggy/ … (the api cell, the cells of the sandbox subtree, and the web cell)" | `_discover_packaged_usages` loop | matches — mandates the unconditional copy incl. the web root |
| `run_bootstrap` Requirement "every packaged usage — including the sandbox capability usages — is copied" | same loop | matches — this requirement IS defect D1 for the api-only kind |
| `run_bootstrap` step 6b/6c "When the web config was written …" | `if web_written:` blocks | matches (web side correctly gated) |
| `run_bootstrap` step 7 "Register the api-root usage keys (pybuggy-api, pybuggy-asserts) plus `conventions`" — no kind gate in text | unconditional registration | matches — this step IS defect D2 for the web-only kind |
| Global annotation "The api and web question sets never cross" | `amend_pybuggy_config` branch | matches for questions; delivery/registration are NOT covered by this sentence |
| `survey_web_config` algorithm steps 1–5 | `session.py:233-239` | matches — provider choice, two required model inputs, free-text browser name, headless confirm |

## Cross-Cell Traversals

| Source Cell | Target Cell | Type | Path |
|---|---|---|---|
| `commands/init` | `web` | data | `from ...web import WebConfigKeys` — survey keys, payload keys, example-documentation walk |
| `commands/init` | `web` | usage | Imports `pybuggy-web` usage — consumer meaning of the surveyed fields |
| `commands/init` | `plugin` | type | `PluginConfigKeys` — the api scalar prompt walk |
| `commands/init` | `config` | type | `SpecEntry`/`GitEntry` — `parse_specs` |
| `commands/init` (bootstrap) | runtime `prettyplay` (external) | data | `browser.name` written to `web.yml` → prettyplay `_BROWSER_MATRIX` validation at test runtime |

## Inconsistencies

| Type | Location | Expected (user requirement) | Actual |
|---|---|---|---|
| code+manifest vs user requirement | `init.py:62` `_USAGE_ROOTS` walk | api-only ships no web usage file; web-only ships no api usage files | all roots' files always copied (reproduced: `pybuggy-web.md` present at kind=api; `api.md`/`asserts.md` present at kind=web) |
| code+manifest vs user requirement | `init.py:368-375` step 7 | web-only registers no api usage keys/annotations | api pair + annotations always registered (reproduced at kind=web) |
| UX defect | `session.py:233-239` | web-branch questions answerable by a web-only user | provider/model prompts carry no explanation, models are required free-text — the reporting user could not answer them |
| validation gap | `session.py:237` vs prettyplay `_BROWSER_MATRIX` | invalid browser names rejected at the prompt | free text accepted; failure deferred to test runtime ("must be one of: chromium, firefox, webkit, chrome, msedge") |

## Trace Graph

```
kind answer (session-only)
   ├─ api/both ──► api.yml ─────────────► [bootstrap] api examples (natural no-op gate)
   │                                            └─► step 7 registration ── ALWAYS (defect D2)
   └─ web/both ──► web.yml ──► web_written gate ──► web examples, pybuggy-web registration, playwright line
                                                └─► (correctly gated)

_USAGE_ROOTS (api + sandbox + web) ──► step 2 copy ──► ALWAYS ALL (defect D1 for the cross-kind roots)

survey_web_config ──► provider/generation_model/classification_model (required, unexplained — defect D3)
                  ──► browser_name (free text; runtime-only validation — defect D4)
```
