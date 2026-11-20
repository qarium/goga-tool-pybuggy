# Web tests: embed prettyplay into pybuggy as a second test kind

## Current State

pybuggy supports only OpenAPI-driven API tests, delivered through a turnkey pattern: the fixed-path
tool config (`.goga/tools/pybuggy/config.yml`), `pybuggy init` onboarding, and a pluginator pytest
plugin that leaves the consumer's conftest at `plugin.install()` only.

- `goga_tool_pybuggy/plugin` already knows the second-plugin pattern: `SandboxPlugin` joins the
  same `install()` call, gated by the presence of `.goga/tools/pybuggy/sandbox.yml`.
- `prettyplay>=0.0.3` is already declared in `pyproject.toml` (no upper cap yet), and the package
  is installed.
- `prettyplay_example/conftest.py` (an in-repo example, not a canonical integration — prettyplay
  itself ships no pytest plugin or fixture, so the example wires one by hand) carries the full
  integration shape: the `play` fixture, the prettyplay event log formatter, Allure step hooks with
  failure screenshots, and the `--strict-mode` / `--interactive` pytest options — all hardcoded,
  outside pybuggy.

There is no browser/web test kind, no web config, and `pybuggy init` has no notion of a test kind.

## Description

Embed **prettyplay** (step-sentence browser testing: an LLM turns each step sentence into
Playwright code once, the cache lands in the repo, replay needs no LLM) as a first-class second
test kind — **web tests** — delivered through the same turnkey pattern as API tests:

1. **Config rename, clean break**: `config.yml` → `api.yml`. Old `config.yml` files are not read,
   no migration shim; existing consumer projects rename by hand. Web settings live in
   `.goga/tools/pybuggy/web.yml` (joining `sandbox.yml`).
2. **WebPlugin** — a separate pluginator plugin (pattern of `SandboxPlugin`), activated in
   `plugin.install()` by the presence of `web.yml`. It absorbs the whole example conftest (a wiring
   sketch, not a canonical form — its hardcoded values become `web.yml`-driven):
   - the `web` fixture (function-scoped, symmetric with `api`): yields a per-test `PrettyPlay`
     with `cache_key` = test name, the step cache stored next to the test file and committed to
     the repository;
   - building an explicit `PrettyConfig` from `web.yml` — the single configuration source for web
     tests (`pyproject.toml [tool.prettyplay]` is not used; `PRETTYPLAY_*` env does not override);
   - Allure step hooks with failure screenshots — active only when allure-pytest is installed;
   - the prettyplay event log formatter;
   - the `--strict-mode` / `--interactive` pytest options.
3. **Web steps carry full URLs** (`web.step("Open https://ya.ru")`): no `base_url` templating, no
   sandbox binding in v1.
4. **Kind-aware `pybuggy init`**: the first question asks the test kind (api / web / both) and
   gates every downstream block on it. The web branch surveys the minimum (LLM provider,
   generation/classification model, browser, headless); the remaining `web.yml` keys arrive as
   commented examples in the file (the `document_config_examples` approach). The web bootstrap
   writes `web.yml`, copies and registers the `pybuggy-web` usage doc (step-sentence authoring,
   var capture, strict mode, "no secrets in step sentences"), and appends
   `RUN playwright install --with-deps <browser>` to the Dockerfile. API-specific questions
   (application base_url, specs, autonomy axes) are asked only when api is chosen.
5. **Dependencies**: cap prettyplay to `>=0.0.3,<0.1.0` (the repo's own-package convention).

## Scope

**In scope:**
- Rename of the api tool config path to `api.yml` across config reading, plugin defaults, init
  bootstrap, and docs.
- The web config model: reading `web.yml` and constructing an explicit `PrettyConfig`.
- WebPlugin: `web` fixture, Allure hooks (guarded activation), event log formatter,
  `--strict-mode` / `--interactive` options, presence-gated registration in `install()`.
- Kind-aware init: the kind question, the web-branch survey, commented `web.yml` examples, the
  `pybuggy-web` usage doc packaging/registration, the Dockerfile playwright line.
- `pyproject.toml`: the prettyplay upper cap; `allure-pytest` in the `test` extra.
- Repository tests for all of the above (LLM- and browser-free at unit level).

**Out of scope:**
- `web.automate` — no autonomy axis, statuses, or pipeline registration for web (revisit when
  skills/SDD development arrives).
- The endpoint command group (`pull/list/info/generate/diff`) and the api autonomy flow.
- Any reading or migration of old `config.yml`.
- `base_url` templating and sandbox binding for web steps.
- The exact `web.yml` YAML schema and the cell layout / depth of the internal restructuring of
  existing cells — open questions recorded in the ADR, decided at the design stage.

## Acceptance Criteria

- With `web.yml` present, `plugin.install()` in a consumer conftest registers WebPlugin and the
  `web` fixture; without it, nothing web-related is registered and a test requesting `web` gets
  pytest's standard "fixture 'web' not found".
- The api plugin reads its options from `api.yml`; an old `config.yml` is ignored entirely.
- `web.yml` maps onto an explicit `PrettyConfig` (provider, models, prompts, attempts, browser,
  strict/interactive defaults, cache policy); prettyplay's pyproject auto-search is never
  triggered, `PRETTYPLAY_*` env does not override the file.
- `--strict-mode` runs make zero LLM calls (a cache miss fails); `--interactive` reaches the
  plugin option.
- Allure hooks are active only when allure-pytest is installed; a failed step attaches
  `screenshot.png` to the Allure report.
- The WebPlugin installs the prettyplay event log formatter: web-test runs render prettyplay log
  events in the console (human-readable events without payload duplication).
- `pybuggy init` asks the kind first; choosing web produces the minimal survey, `web.yml` with
  commented examples, the registered `pybuggy-web` usage, and the Dockerfile
  `RUN playwright install --with-deps <browser>` line; choosing api never asks web questions and
  vice versa.
- The step cache lands next to the test file (per-test address, class-aware) and is committable.
- `pyproject.toml` carries `prettyplay>=0.0.3,<0.1.0` and `allure-pytest` under the `test` extra.
- `pytest tests/ -x` passes; `ruff check goga_tool_pybuggy/` is clean.

## Stack

- **Frameworks:** pytest (plugin surface), pluginator (WebPlugin declaration and installation)
- **Libraries:** prettyplay 0.0.3 (hard dependency, capped `<0.1.0`); playwright (transitive via
  prettyplay — the only direct import is `playwright.sync_api.Error`; not declared separately by
  decision); allure-pytest (optional activation, `test` extra only); pydantic (web config model);
  ruamel-yaml (round-trip `web.yml` writing in init); python-dotenv (env for LLM keys)
- **Infrastructure:** none new — browser binaries are an environment requirement
  (`playwright install --with-deps` locally, the bootstrap-appended Dockerfile line in images)

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| prettyplay | `.goga/usages/cooks/prettyplay.md` | created |
| allure-pytest | `.goga/usages/cooks/allure-pytest.md` | created |
| pluginator | `.goga/usages/cooks/pluginator.md` | existing |
| ruamel-yaml | `.goga/usages/cooks/ruamel-yaml.md` | existing |
| python-dotenv | `.goga/usages/cooks/python-dotenv.md` | existing |
| goga (onboarding/scaffold) | `.goga/usages/github/goga/…` | existing (synced) |

Synced usage files are managed by `goga usages sync` — reference them read-only, never create or update them in the task.

pydantic, pytest, and playwright carry no separate usage files: pydantic model rules live in
`conventions.md`; pytest is the test framework itself; playwright (transitive) is documented
inside the prettyplay usage.

## Risks and Constraints

- **LLM and browser in repository tests**: unit tests must not call an LLM or open a real browser
  (mock the provider, exercise the cache/replay paths with canned artifacts; browser-bound
  integration checks get `pytest.mark.skipif` guards).
- **Clean break**: existing consumer projects stop finding their config until renamed by hand —
  accepted in the ADR, must be called out in the release notes.
- **prettyplay 0.0.x instability**: the surface may shift under a patch; the `<0.1.0` cap bounds
  the exposure.
- **Cache path addressing**: the example computes the cache path relative to the cwd; tests
  running outside the project root must not crash on path resolution (design stage decides the
  exact rule).
- **Concurrency**: web tests are slower and single-page; parallel browser sessions are a
  prettyplay runtime concern, not addressed here.

## Scope Estimate

Single task. The parts are tightly coupled — init writes the `web.yml` the plugin reads, the
rename touches the same config cell init consumes — and deliver no independent value apart.

## Existing Architecture

- `goga_tool_pybuggy/config` — `load_config`/`resolve_autonomy` switch to `api.yml`; a web config
  surface (model + reader) joins the multi-kind picture (layout decided at design).
- `goga_tool_pybuggy/plugin` — WebPlugin (new), `install()` gains the `web.yml` presence gate;
  `defaults.py` gains the `web.yml` path constant; `ApiPlugin` config path becomes `api.yml`.
- `goga_tool_pybuggy/commands/init` — kind-aware session questions and bootstrap steps; the
  packaged-usages roots (`_USAGE_ROOTS`) gain the web usage doc; `PYBUGGY_ANNOTATIONS` gains its
  annotation line.
- `goga_tool_pybuggy` (root) — doc-only touch: `assembly.md` names the tool config path and follows
  the rename.
- New web contract surface (cell layout — new cell vs plugin-cell member — decided at the design
  stage, per the ADR).

## Notes

- Dialogue decisions (2026-10-28): formulation approved as is; code examples included in this
  document; playwright stays **transitive** (no explicit `pyproject.toml` declaration — a
  conscious deviation from the "declare direct imports" convention, the single import is
  `playwright.sync_api.Error` documented in the prettyplay usage); allure-pytest lands in the
  `test` extra only.
- LLM API keys live only in env/`.env`; `web.yml` never contains keys. Step sentences, captured
  vars, and cache files land in LLM prompts and logs — no secrets in step sentences (documented
  in the `pybuggy-web` usage doc).
- `prettyplay_example` is an example integration, not a reference: prettyplay ships no plugin or
  fixture of its own; the WebPlugin takes its wiring shape, with the hardcoded values re-decided
  through `web.yml` (review dialogue, 2026-10-28).
- CI should run web suites with `--strict-mode` (zero generation LLM calls).
- Input artifacts: `.goga/history/2026/web-tests/adr.md` (decisions 1–9, consequences, open
  questions).

### Example — a web test (consumer side)

```python
from prettyplay import PrettyPlay


def test_duckduckgo_search(web: PrettyPlay):
    web.step("Open https://duckduckgo.com")
    web.step('Find results for "UI testing automation"')

    web.expect('The results page contains the text "test"')
```

### Example — `web.yml` (illustrative; the exact schema is decided at the design stage)

```yaml
# .goga/tools/pybuggy/web.yml — the single configuration source for web tests
provider: anthropic
base_url: https://api.z.ai/api/anthropic # optional LLM API proxy
generation_model: glm-5.3
classification_model: glm-5.3
browser:
  name: chrome
  headless: false
  screen: fullscreen
strict: false
interactive: false
# generation_attempts: 2
# probe_timeout: 3
# llm_request_attempts: 10
# healing_attempts: 3
# generation_prompt: |
#   Requirements:
#   - Prefer to use `id` or `class` attributes in HTML document to find elements.
#   - Make text matching checks case-insensitive.
#   Constraints:
#   - Don't do confirmation checks of the action's completion.
#   - Don't use `if` statement in step code.
# classification_prompt: Write explanations and recommendations in English
```
