# Web tests: embed prettyplay into pybuggy as a second test kind

pybuggy currently supports only OpenAPI-driven API tests. We decided to add browser
UI/E2E tests ("web tests") by embedding **prettyplay** (AI-powered step-sentence testing:
each step sentence is turned into Playwright code by an LLM once, cached in the repo,
and replayed without any LLM involvement) as a first-class second test kind, delivered
through the same turnkey pattern as API tests: fixed-path tool config, init onboarding,
and a pytest plugin that leaves the consumer's conftest at `plugin.install()` only.

## Decisions

1. **Both test kinds coexist in one consumer project.** API and web are parallel kinds,
   not modes: a project may have `api.yml` and `web.yml` side by side with both plugins
   active. Mixed suites (UI step + API check) stay possible.
2. **Config rename with a clean break.** `.goga/tools/pybuggy/config.yml` is renamed to
   `api.yml`; web settings live in `.goga/tools/pybuggy/web.yml` (joining `sandbox.yml`).
   Old `config.yml` files are not read and no migration shim is provided — existing
   consumer projects rename by hand.
3. **prettyplay is a hard dependency** of the `goga-tool-pybuggy` package (declared in
   `pyproject.toml` with the repo's own-package convention: lower bound + upper cap).
   There is no `[web]` extra: pybuggy is installed globally via `goga install pybuggy`,
   not into consumer venvs, so dependency weight in the consumer project is not a concern.
4. **No `web.automate` pipeline now.** Web tests are written manually in v1; no autonomy
   axis, statuses, or pipeline registration for web. Revisit when skills/SDD development
   arrives.
5. **Web steps carry full URLs** (`web.step("Open https://ya.ru")`). No application
   `base_url` templating (the api-style Jinja2 render does not apply) and no sandbox
   binding in v1 — matching the reference `prettyplay_example` tests.
6. **The pytest fixture is named `web`**, symmetric with `api`: function-scoped, yields a
   per-test `PrettyPlay` with `cache_key` = test name and the step cache stored next to
   the test file and committed to the repository.
7. **The web plugin absorbs the whole reference conftest** (`prettyplay_example`):
   the `web` fixture, building `PrettyConfig` from `web.yml`, Allure step hooks with
   failure screenshots (active only when allure-pytest is installed), the prettyplay log
   formatter, and the `--strict-mode` / `--interactive` pytest options.
8. **`web.yml` is the single configuration source for web tests.** pybuggy reads it and
   constructs an explicit `PrettyConfig` (LLM provider + optional base_url proxy, models,
   generation/classification prompt instructions, attempt limits, browser settings,
   strict/interactive defaults, cache policy). `pyproject.toml [tool.prettyplay]` is not
   used, and `PRETTYPLAY_*` env vars do not override `web.yml` (an explicit config is the
   highest priority layer in prettyplay).
9. **`pybuggy init` asks the test kind first** (api / web / both) and gates every
   downstream block on it. The web branch surveys the minimum (LLM provider,
   generation/classification model, browser, headless); the remaining `web.yml` keys are
   delivered as commented examples in the file (same approach as `document_config_examples`
   for api). The web bootstrap writes `web.yml`, copies and registers the `pybuggy-web`
   usage doc (step-sentence authoring, var capture, strict mode, "no secrets in step
   sentences"), and appends `RUN playwright install --with-deps <browser>` to the
   Dockerfile. API-specific questions (application base_url, specs, autonomy axes) are
   asked only when api is chosen.

## Considered options

- **Fixture name `play` (as in `prettyplay_example`) vs `web`.** Chose `web`: symmetry
  with the existing `api` fixture outweighs copy-paste compatibility with the example.
- **`web.yml` vs `pyproject.toml [tool.prettyplay]` vs split ownership.** Chose
  `web.yml`-only: pybuggy's config standard is fixed paths under `.goga/tools/pybuggy/`;
  an explicit config also bypasses prettyplay's pyproject auto-search, which raises
  `FileNotFoundError` when no `pyproject.toml` exists above the cwd.
- **Backward compatibility for old `config.yml` (read-as-api + deprecation warning, or
  auto-migration) vs clean break.** Chose the clean break.
- **Optional extra `pybuggy[web]` / separate package vs hard dependency.** Chose the hard
  dependency (see decision 3).
- **Minimal plugin (fixture + config only) vs absorbing the full reference conftest.**
  Chose the full absorption, with allure as an optional activation.

## Consequences

- WebPlugin is a separate pluginator plugin (pattern of `pybuggy-sandbox`), activated by
  the presence of `web.yml` in `plugin.install()`.
- LLM API keys live only in env/`.env` (`load_env` already loads it); `web.yml` never
  contains keys. Step sentences, captured vars, and cache files land in LLM prompts and
  logs — secrets must not be put in step sentences (documented in the usage doc).
- Browser binaries are an environment requirement: locally `playwright install`, in
  Docker via the bootstrap-appended Dockerfile line.
- CI should run with strict mode (`--strict-mode`): zero generation LLM calls; a cache
  miss fails as `IncurableStepError`.
- The endpoint command group (`pull/list/info/generate/diff`) and the api autonomy flow
  are untouched.
- The internal structure of pybuggy (config cell is api-centric: `load_config` reads api
  specs; plugin cell gains a second plugin; init becomes kind-aware) will likely need
  rework for multi-kind support. The need is recorded here; its depth is decided at the
  architecture/design stage.

## Unresolved questions (for the design stage, not blocking)

- Exact `web.yml` YAML schema (mapping onto `PrettyConfig` fields).
- Cell layout for the new plugin/config/init surface and the depth of the internal
  restructuring of existing cells.
