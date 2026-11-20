# Architecture Plan — Web tests: embed prettyplay as a second test kind

## Topic

**web-tests** — embed prettyplay into pybuggy as a first-class second test kind (web tests), delivered
through the same turnkey pattern as API tests: the fixed-path tool config `web.yml`, the WebPlugin
pytest plugin, and the kind-aware `pybuggy init` onboarding. The api tool config is renamed
`config.yml` → `api.yml` with a clean break.

Plan path: `.goga/history/2026/web-tests/arch.md`

Resolved design decisions (dialogue, 2026-10-28):

- **Cell layout** — a new capability cell `goga_tool_pybuggy/web` holds the whole web surface
  (config model + reader + PrettyConfig builder + WebPlugin + the `pybuggy-web` consumer usage doc);
  the plugin cell keeps only the presence gate in `install()` (the pattern of the sandbox capability:
  the capability owns its config and docs).
- **Kind gating in init** — the kind question is the first declarative record of the engine block;
  every kind-dependent survey (api and web alike) moves to the amendment moment (the declarative
  records carry no conditional visibility); both config files are buffered through the session and
  written by the engine.
- **Cache addressing** — the `prettyplay_example` rule: `cache_key` = the item name
  (parametrize-aware), the per-test path `<module_stem>/<ClassName>/<original_name>`
  (class-aware, parametrize-agnostic); the root is the test module's own directory (absolute, from
  the item — never the cwd) or the `cache_root` key of `web.yml`. The example's cwd-relative
  conversion is dropped: no crash when running outside the project root.

## Implementation Order

1. **`goga_tool_pybuggy/web`** (CREATE) — no Imports (leaf); everything downstream imports it.
2. **`goga_tool_pybuggy/config`** (MODIFY, rename-only) — no Imports (leaf); independent of web.
3. **`goga_tool_pybuggy/plugin`** (MODIFY) — imports the web cell (WebPlugin, WebConfigKeys,
   pybuggy-web usage); applies the api.yml rename in its own annotations.
4. **`goga_tool_pybuggy/commands/init`** (MODIFY) — imports the web cell (WebConfigKeys,
   pybuggy-web) and the existing config/plugin contracts; kind-aware questions and bootstrap.
5. **Root `goga_tool_pybuggy`** (doc-only) — `.usages/assembly.md` follows the rename; no CODEMANIFEST
   change, no new types. The repository doc sweep (docs/ tree, endpoint-command usage docs, the
   packaged skill, the pluginator/jinja2 cooks) rides the same doc-only step.
6. **`pyproject.toml`** — `prettyplay>=0.0.3,<0.1.0`; `allure-pytest` under the `test` extra.

## Artifacts

### Cell 1 — `goga_tool_pybuggy/web` (CREATE)

#### CODEMANIFEST — `goga_tool_pybuggy/web/CODEMANIFEST`

```yaml
Usages:
  conventions: .goga/usages/conventions.md
  prettyplay: .goga/usages/cooks/prettyplay.md
  allure-pytest: .goga/usages/cooks/allure-pytest.md
  pluginator: .goga/usages/cooks/pluginator.md

Annotations: |
  Use `conventions` for code writing rules, relative imports, docstrings, and testing.
  Use `pluginator` for the plugin framework contract — @define.plugin bound to the web config file,
  define.option with the option resolution chain and CLI authority, fixtures as plugin-class methods,
  the configure() lifecycle hook, and gate-driven construction.
  Use `prettyplay` for the prettyplay contract — the PrettyConfig field table, PrettyPlay construction
  (cache_key/cache_path/config), the StepHooks event set, and the security rules.
  Use `allure-pytest` for the guarded import and the StepHooks-to-Allure mapping with failure
  screenshots.

  Web-test cell — the prettyplay test kind. Provides the WebPlugin (the `web` fixture, the
  strict/interactive options, Allure step reporting, the prettyplay event log formatter) and the web
  config surface: the WebConfig model validated from web.yml and mapped onto an explicit PrettyConfig.
  web.yml is the single configuration source for web tests: an explicitly constructed config is the
  highest-priority layer of prettyplay, so the pyproject auto-search never runs and PRETTYPLAY_* env
  vars never override the file. LLM API keys live only in env/.env (the root load_env loads it);
  web.yml never carries keys; step sentences, captured vars, and cache files land in LLM prompts and
  logs — no secrets in step sentences (documented in this cell's consumer usage doc).
  The plugin is activated by the installation entry of the plugin cell when the web config document
  is present; this cell registers nothing on its own. Web steps carry full URLs
  (web.step("Open https://ya.ru")) — no base_url templating, no sandbox binding in v1.

  Constraints:
  - All pydantic models use kw_only=True; defaults mirror the prettyplay defaults so an omitted key
    behaves as the library default.
  - Use relative imports inside the cell.
  - The only direct playwright import is playwright.sync_api.Error (a transitive dependency, not
    declared separately — documented in `prettyplay`).
  - allure-pytest is never a runtime dependency: the import sits under a guard (`allure is None`
    constructs no hooks — web tests run without step decoration).

---

"BrowserSettings(name: str = 'chromium', headless: bool = True, screen: str = '', endpoint: str = '', accept_dialogs: bool = False, speed: int = 100, timeout: float = 30)":
  location: config.py
  annotations: |
    Nested browser section of the web config — the settings that map onto the prettyplay
    BrowserConfig.

    `name`: browser or channel name — chromium, chrome, firefox, and the names the runtime accepts.
    `headless`: run without a visible window.
    `screen`: the screen mode (e.g. fullscreen); empty keeps the runtime default.
    `endpoint`: the remote Playwright endpoint; empty runs locally.
    `accept_dialogs`: auto-accept dialogs.
    `speed`: the execution speed in percent.
    `timeout`: the default page timeout in seconds.

    Requirements:
    - Defaults mirror the prettyplay BrowserConfig defaults exactly — an omitted subkey behaves as
      the library default.

    Constraints:
    - Never carry credentials — a remote endpoint address only; access relies on ambient
      configuration.

    Use `conventions` for pydantic model rules.
  properties:
    "name -> str": |
      The browser or channel name; the default chromium.
    "headless -> bool": |
      Whether the browser runs without a visible window; the default True.
    "screen -> str": |
      The screen mode; empty keeps the runtime default.
    "endpoint -> str": |
      The remote Playwright endpoint; empty runs locally.
    "accept_dialogs -> bool": |
      Whether dialogs are auto-accepted; the default False.
    "speed -> int": |
      The execution speed in percent; the default 100.
    "timeout -> float": |
      The default page timeout in seconds; the default 30.

"WebConfig(provider: Literal['openai','anthropic'] = 'openai', base_url: str = '', model: str = '', generation_model: str = '', classification_model: str = '', generation_prompt: str = '', classification_prompt: str = '', strict: bool = False, interactive: bool = False, polling_timeout: float | None = None, polling_delay: float = 0.5, generation_attempts: int = 3, healing_attempts: int = 2, llm_request_attempts: int = 3, send_screenshots: bool = False, generation_approve: bool = True, probe_timeout: float = 0, cache_root: str = '', browser: BrowserSettings = BrowserSettings())":
  location: config.py
  annotations: |
    Validated model of the web config document web.yml — the web-test settings that map onto an
    explicit PrettyConfig.

    `provider`: the LLM provider — constrained to openai/anthropic via Literal; pydantic rejects
      other values at validation time.
    `base_url`: the optional LLM API proxy endpoint; empty uses the provider default.
    `model`: the shared model override; empty means no override.
    `generation_model`: the model for step-code generation.
    `classification_model`: the model for step classification.
    `generation_prompt`: extra instructions appended to the generation prompt.
    `classification_prompt`: extra instructions appended to the classification prompt.
    `strict`: the replay-only default — zero LLM calls, a cache miss fails.
    `interactive`: the interactive step healing default.
    `polling_timeout`: the assertion polling timeout; None keeps the runtime default.
    `polling_delay`: the delay between polling attempts in seconds.
    `generation_attempts`: blind generation attempts before diagnosis.
    `healing_attempts`: healing attempts for a failing step.
    `llm_request_attempts`: retries of a failed LLM request.
    `send_screenshots`: attach screenshots to LLM requests.
    `generation_approve`: confirm generated code before caching.
    `probe_timeout`: the locator probe timeout in seconds; 0 keeps the page default.
    `cache_root`: the root directory of the step cache; empty selects the per-test default — the
      directory of the requesting test's own module file.
    `browser`: the nested browser settings (`BrowserSettings`).

    Requirements:
    - Defaults mirror the prettyplay defaults exactly — an omitted key behaves as the library default.
    - All fields carry empty or zero defaults; polling_timeout is the only field whose absence is
      explicit (None).

    Constraints:
    - Never carry LLM API keys — keys live only in env/.env; a document carrying a key-shaped value
      is a configuration error of the author, not of the model.

    Use `conventions` for pydantic model rules.
  properties:
    "provider -> str": |
      The LLM provider — openai or anthropic; the default openai.
    "base_url -> str": |
      The optional LLM API proxy endpoint; empty uses the provider default.
    "model -> str": |
      The shared model override; empty means no override.
    "generation_model -> str": |
      The model for step-code generation.
    "classification_model -> str": |
      The model for step classification.
    "generation_prompt -> str": |
      Extra instructions appended to the generation prompt.
    "classification_prompt -> str": |
      Extra instructions appended to the classification prompt.
    "strict -> bool": |
      The replay-only default — zero LLM calls, a cache miss fails; the default False.
    "interactive -> bool": |
      The interactive step healing default; the default False.
    "polling_timeout -> float | None": |
      The assertion polling timeout; None keeps the runtime default.
    "polling_delay -> float": |
      The delay between polling attempts in seconds; the default 0.5.
    "generation_attempts -> int": |
      Blind generation attempts before diagnosis; the default 3.
    "healing_attempts -> int": |
      Healing attempts for a failing step; the default 2.
    "llm_request_attempts -> int": |
      Retries of a failed LLM request; the default 3.
    "send_screenshots -> bool": |
      Whether screenshots are attached to LLM requests; the default False.
    "generation_approve -> bool": |
      Whether generated code is confirmed before caching; the default True.
    "probe_timeout -> float": |
      The locator probe timeout in seconds; 0 keeps the page default.
    "cache_root -> str": |
      The root directory of the step cache; empty selects the per-test default next to the test file.
    "browser -> BrowserSettings": |
      The nested browser settings.

"WebConfigKeys()":
  location: keys.py
  annotations: |
    Fixed value set of the web config keys — the canonical key set of web.yml, mirroring the
    PrettyConfig field names 1:1, plus the config file name. Consumed data-driven by the init web
    survey and payload builder, the commented-example documentation of the bootstrap, the WebConfig
    validation alignment, and the presence gate of the plugin installation entry (the FILENAME member
    names the document).

    Requirements:
    - Members map to the lowercase key strings of web.yml; the FILENAME member maps to the file name
      web.yml.
    - Scalar members are single values; BROWSER is the complex member carrying the nested browser
      section (documented as commented examples, never surveyed as a scalar).

    Constraints:
    - Fixed value set (implement as enum.Enum). Do not add, remove, or rename members or change
      their values — the init survey, the example documentation, the validation alignment, and the
      installation gate depend on the exact key set.

    Use `conventions` for the Enum declaration style and relative imports.
  properties:
    "FILENAME -> str": |
      web.yml — the web config document file name (under the fixed platform tool-config path of
      pybuggy).
    "PROVIDER -> str": |
      provider — the LLM provider key.
    "BASE_URL -> str": |
      base_url — the optional LLM API proxy endpoint key.
    "MODEL -> str": |
      model — the shared model override key.
    "GENERATION_MODEL -> str": |
      generation_model — the step-code generation model key.
    "CLASSIFICATION_MODEL -> str": |
      classification_model — the step classification model key.
    "GENERATION_PROMPT -> str": |
      generation_prompt — the extra generation instructions key.
    "CLASSIFICATION_PROMPT -> str": |
      classification_prompt — the extra classification instructions key.
    "STRICT -> str": |
      strict — the replay-only default key.
    "INTERACTIVE -> str": |
      interactive — the interactive healing default key.
    "POLLING_TIMEOUT -> str": |
      polling_timeout — the assertion polling timeout key.
    "POLLING_DELAY -> str": |
      polling_delay — the delay between polling attempts key.
    "GENERATION_ATTEMPTS -> str": |
      generation_attempts — the blind generation attempts key.
    "HEALING_ATTEMPTS -> str": |
      healing_attempts — the healing attempts key.
    "LLM_REQUEST_ATTEMPTS -> str": |
      llm_request_attempts — the retries of a failed LLM request key.
    "SEND_SCREENSHOTS -> str": |
      send_screenshots — the attach-screenshots-to-LLM-requests key.
    "GENERATION_APPROVE -> str": |
      generation_approve — the confirm-generated-code-before-caching key.
    "PROBE_TIMEOUT -> str": |
      probe_timeout — the locator probe timeout key.
    "CACHE_ROOT -> str": |
      cache_root — the step cache root key.
    "BROWSER -> str": |
      browser — the nested browser section key; complex member (commented example, not surveyed).

"validate_web_config(data: dict[str, object]) -> config: WebConfig":
  location: config.py
  annotations: |
    Validate the raw parse of the web config document into a `WebConfig`.

    `data`: the raw mapping of web.yml (the plugin_config parse of the document).
    `config`: the validated model.

    Algorithm:
    1. Reject a non-mapping root with a clean error naming the web config document.
    2. Reject an empty mapping — the document must carry at least the surveyed minimum (the provider
       and the browser name) — with an explicit error naming the document.
    3. Validate the mapping into `WebConfig`; a validation error surfaces as a clean error naming
       the document.

    Requirements:
    - A structural violation fails with a clean error naming web.yml — never a raw traceback.
    - Pure — no filesystem access, no TTY; the caller owns the raw parse.

    Constraints:
    - Do not interpret keys outside the `WebConfig` field set — an unknown key surfaces as a
      validation error (a mistyped key must fail, not silently disable a setting).

    Use `conventions` for pydantic validation rules.

"build_pretty_config(config: WebConfig, strict_flag: bool, interactive_flag: bool) -> pretty: PrettyConfig":
  location: pretty.py
  annotations: |
    Map a `WebConfig` onto an explicit PrettyConfig — the single construction point of the
    prettyplay settings layer.

    `config`: the validated web config.
    `strict_flag`: the effective strict override — True forces strict even when the document says
      false.
    `interactive_flag`: the effective interactive override — the same form.
    `pretty`: the explicitly constructed prettyplay config.

    Algorithm:
    1. Map every field of `config` onto the same-named field of the prettyplay config, including
       `BrowserSettings` onto the prettyplay browser config.
    2. Compute the effective modes: strict = config.strict or strict_flag; interactive =
       config.interactive or interactive_flag — a CLI flag forces the mode on, never off.
    3. Construct the explicit object.

    Requirements:
    - The explicit construction is the highest-priority layer of prettyplay: the pyproject
      auto-search never runs and PRETTYPLAY_* env vars never override the file (see `prettyplay`).
    - Pure — no I/O, no environment reads.

    Constraints:
    - Do not read env or pyproject here — the single source is the passed model and flags.

    Use `prettyplay` for the PrettyConfig and browser config field contract.
    Use `conventions` for type hints.

"WebPlugin()":
  location: plugin.py
  annotations: |
    Pluginator plugin of the web test kind: the `web` fixture, the strict/interactive options, Allure
    step reporting, and the prettyplay event log formatter. The web config document web.yml is the
    plugin's config: pluginator reads it into plugin_config, and configure validates it into the
    activation — an invalid document fails the run at configphase, before any collection or browser.

    Constructed only by the installation gate of the plugin cell (the document presence check); zero
    constructor arguments; no work at construction — the activation and the formatter land in
    configure.

    Algorithm:
    1. Declare the strict and interactive options — plugin config keys strict and interactive, CLI
       flags --strict-mode and --interactive (store_true).
    2. Nothing else at construction.

    Use `pluginator` for the @define.plugin contract, define.option, fixtures as plugin-class
    methods, and the configure() lifecycle.
    Use `prettyplay` for the runtime contract consumed by the fixture.
    Use `allure-pytest` for the guarded activation of the reporting hooks.
    Use `conventions` for docstrings, type hints, and relative imports.
  properties:
    "strict -> bool": |
      Resolved strict mode: the web config strict key → the CLI --strict-mode flag (a typed flag
      forces true — the CLI authority applied in configure, the pattern of --base-url) → the default
      False. Strict runs are replay-only: zero LLM calls, a cache miss fails the test.
    "interactive -> bool": |
      Resolved interactive healing mode: the web config interactive key → the CLI --interactive flag
      (the same CLI-authority form) → the default False.
    "activation -> WebConfig | None": |
      The validated web config — the document the configure step validated; None before configure
      ran. The fixture builds the runtime from it.
  methods:
    "configure()": |
      Validate the document into the activation, apply the CLI authority to the options, and install
      the prettyplay event log formatter.

      Algorithm:
      1. Apply CLI authority: when the user typed --strict-mode or --interactive, store True onto
         the option — a typed flag overrides the config-file and env resolution (see `pluginator` for
         the config-time CLI sources).
      2. Validate plugin_config via `validate_web_config` into the activation; an invalid document
         fails with its clean error at configphase.
      3. Install the prettyplay event log formatter via `install_event_log_formatter`.

      Requirements:
      - Runs once at pytest configphase, before any collection and before any fixture invocation.
      - The formatter is installed unconditionally with the plugin active — it is not allure-gated.

      Use `pluginator` for the configure lifecycle and the config-time CLI sources.
    "web(request: pytest.FixtureRequest) -> web: Iterator[PrettyPlay]": |
      Function-scope generator fixture: build the per-test prettyplay runtime and close it after the
      test.

      `request`: the fixture request of the test being set up.
      web: the opened prettyplay runtime the test consumes — step, expect, group, run_on_page (see
      `prettyplay`).

      Algorithm:
      1. Compute the cache address: the root is the activation cache_root when set, otherwise the
         absolute directory of the requesting test's own module file (from the item — never the
         cwd); the per-test path is `web_cache_path(request.node)`; the cache key is the item's name
         (parametrize-aware).
      2. Build the explicit prettyplay config via `build_pretty_config` from the activation and the
         resolved strict and interactive options.
      3. Construct the prettyplay runtime with the cache key, the path, and the config, with
         cleanup disabled (the persistence mode of the committed-cache workflow: every cached
         file of the test's key is kept — a run that fails mid-test must not destroy the cached
         steps it never reached, so the next strict replay stays green; a stale step is removed
         by deleting its file).
      4. When allure is importable (see `allure-pytest`), attach `AllureStepHooks` to the runtime.
      5. Open the runtime (the context manager), yield it, close it on finalization.

      Requirements:
      - A --strict-mode run makes zero LLM calls — a cache miss fails the test.
      - The step cache lands next to the test file and is committable; the addressing never depends
        on the cwd — tests running outside the project root resolve their paths from the item
        itself.

      Constraints:
      - No base_url templating and no sandbox binding — web steps carry full URLs.
      - Do not construct `AllureStepHooks` when the guarded import reports allure absent.

      Use `pluginator` for the fixture-as-method convention.
      Use `prettyplay` for the runtime construction and the cache addressing contract.
      Use `conventions` for type hints.

"web_cache_path(item: pytest.Item) -> path: str":
  location: plugin.py
  annotations: |
    Compute the per-test step-cache path from the requesting test item.

    `item`: the pytest item of the requesting test.
    `path`: the posix-relative subdirectory inside the cache root — <module_stem>/<ClassName>/<test_name>
      with a class, <module_stem>/<test_name> without.

    Algorithm:
    1. Take the module stem from the item's own module file path.
    2. Take the original name — originalname when present, the node name otherwise: the path is
       parametrize-agnostic while the cache key stays parametrize-aware.
    3. Insert the class-name segment when the item carries a class.
    4. Join the segments with forward slashes.

    Requirements:
    - Derived from the item's own file — never from the cwd.
    - Pure — no filesystem access.

    Use `prettyplay` for the cache addressing contract (the cache key and the path form the address).
    Use `conventions` for type hints.

"AllureStepHooks(play: PrettyPlay)":
  location: allure_hooks.py
  annotations: |
    Allure reporting integration over the prettyplay hook contract — a StepHooks subclass active
    only when allure-pytest is installed (guarded import; see `allure-pytest`).

    `play`: the prettyplay runtime whose steps are reported — the failure screenshot source.

    Algorithm:
    1. Hold two exit stacks — steps and groups — so the enter/exit pairs stay balanced when a step
       fails mid-group (see `allure-pytest` for the stack discipline).

    Requirements:
    - Constructed only when the guarded allure import succeeded — never on import failure.

    Use `allure-pytest` for the mapping table and the stack discipline.
    Use `prettyplay` for the StepHooks event signatures and the screenshot source.
  methods:
    "on_group_started(group_prompt: str)": |
      Enter an allure step context titled "[group] " + group_prompt on the group stack.

      `group_prompt`: the group sentence.
    "on_group_finished(group_prompt: str)": |
      Close the group stack — every entered group context exits.

      `group_prompt`: the group sentence.
    "on_step_started(step_text: str, step_type: str)": |
      Enter an allure step wrapper titled "[<step_type>] <step_text>" on the step stack.

      `step_text`: the step sentence.
      `step_type`: the step type (action or assertion).
    "on_step_failed(step_text: str, step_type: str, error: str)": |
      Mark the current step failed and attach the failure screenshot: AssertionError for the
      assertion type, a generic Exception otherwise; the screenshot bytes attach as screenshot.png,
      and a PlaywrightError is swallowed — no page, no screenshot (the failure itself is already
      recorded; see `prettyplay` for the only playwright import).

      `step_text`: the step sentence.
      `step_type`: the step type.
      `error`: the failure description.
    "on_step_finished(step_text: str, step_type: str, outcome: str)": |
      Close the step stack — the step context exits with the accumulated failure.

      `step_text`: the step sentence.
      `step_type`: the step type.
      `outcome`: the step outcome.

"EventLogFormatter(fmt: str, datefmt: str)":
  location: logging_setup.py
  annotations: |
    Console formatter of the prettyplay log events — renders human-readable events without payload
    duplication. A logging.Formatter subclass.

    `fmt`: the logging format string.
    `datefmt`: the date format string.

    Requirements:
    - The human-readable event set — step_results_declared, step_inputs, step_candidate_code,
      step_cached_code, step_captured — renders as the plain message (the message already carries the
      execution context); every other event keeps its context visible through the appended extras.
    - Pure rendering — no I/O.

    Use `conventions` for the logging rules.
  methods:
    "format(record: logging.LogRecord) -> message: str": |
      Render the record; when the record's event is one of the human-readable events, return the
      rendered message as is; otherwise append the sorted non-reserved record extras as
      " | key=value" pairs.

      `record`: the log record, including its structured context.
      `message`: the formatted console text.

"install_event_log_formatter()":
  location: logging_setup.py
  annotations: |
    Install the prettyplay event log formatter on the console.

    Algorithm:
    1. Set the prettyplay logger to INFO.
    2. Attach a stdout stream handler carrying `EventLogFormatter`.
    3. Idempotent — a repeated installation adds no duplicate handler.

    Requirements:
    - Web-test runs render prettyplay log events in the console, human-readable, without payload
      duplication.
    - Installed by the configure step of `WebPlugin` — active whenever the plugin is, independent of
      allure.

    Use `conventions` for the logging rules.

---

Author: Goga
CreatedAt: 28/10/26
Description: |
  Web test kind cell — the prettyplay capability: the WebPlugin (the web fixture, the
  strict/interactive options, Allure step reporting, the prettyplay event log formatter) and the web
  config surface (the WebConfig model validated from web.yml and mapped onto an explicit
  PrettyConfig). Activated by the plugin cell installation gate on the presence of the web config
  document.
```

#### .usages file — `goga_tool_pybuggy/web/.usages/pybuggy-web.md` (CREATE)

```md
# pybuggy-web — browser UI tests with step sentences

## Domain

The `web` fixture for browser UI/E2E tests: each step sentence ("Open https://ya.ru") is turned into
Playwright code by an LLM once, cached next to the test, and replayed from the cache without any LLM
involvement. Target audience: test authors writing web tests in a pybuggy-initialized project.

## Enable

The fixture requires the web config document `.goga/tools/pybuggy/web.yml` in the repository. With
the document present, the standard `goga_tool_pybuggy.plugin.install()` call (the root conftest of a
pybuggy project) registers the web plugin and the `web` fixture; without it nothing web-related is
registered and a test requesting `web` fails with pytest's standard "fixture 'web' not found".
`pybuggy init` (test kind: web or both) writes the document — the surveyed minimum (LLM provider,
generation/classification model, browser, headless) as active keys, the remaining keys as commented
examples inside the file. LLM API keys live only in env/`.env`; the document never contains keys.

## Write a web test

```python
def test_duckduckgo_search(web):
    web.step("Open https://duckduckgo.com")
    web.step('Find results for "UI testing automation"')

    web.expect('The results page contains the text "test"')
```

- `web.step(sentence)` — an action step: generated once, then replayed from the cache.
- `web.expect(sentence)` — an assertion step: polled until it holds or the polling budget ends.
- Steps carry full URLs — no base_url templating, no sandbox binding.
- One action per step sentence; name the target and the action in plain language.

## Capture vars from a page

```python
def test_order_total(web):
    web.step("Open https://shop.example.com/orders/42")
    web.step("Capture the order total into `total`")

    web.expect("The total equals the captured `total`")
```

Captured vars are addressed by name in later sentences. Everything captured — and every step
sentence — reaches the LLM provider prompt and the repository: **never put secrets in step
sentences** (no passwords, tokens, keys, personal data).

## Run modes

- `pytest tests/` — normal runs: a cache miss triggers one LLM generation round, then the step is cached.
- `pytest tests/ --strict-mode` — replay-only: zero LLM calls; a cache miss fails the test. CI should
  always run web suites with `--strict-mode`.
- `pytest tests/ --interactive` — interactive step healing on failures.

Both flags force the mode on; they never switch off a mode enabled in the web config.

## Step cache

The step cache lands next to the test file and is committed to the repository — replay (and strict
runs) needs no LLM:

```
tests/test_search.py
tests/test_search/test_search/test_duckduckgo_search/   # the per-test cache
```

The address is class-aware: a test inside `class TestLogin` gets `test_login/TestLogin/<test_name>`.
Parametrized tests share the directory; each parameter case keeps its own cache key. Cache files
are never deleted automatically — the runtime runs in the persistence mode, so a run that fails
mid-test keeps the cached steps it never reached. Do not edit cache files by hand — delete a step's
file to force its regeneration on the next non-strict run.

## Reporting

When allure-pytest is installed, every step renders as an Allure step (groups as nested steps) and a
failed step attaches `screenshot.png` to the report; without the package the integration stays
inactive and the tests run exactly the same. Web-test runs render prettyplay log events in the
console (human-readable, no payload duplication). Browser binaries are an environment requirement:
`playwright install --with-deps <browser>` locally; the Dockerfile line appended by `pybuggy init`
covers images.
```

#### Implementation files (from the CODEMANIFEST `location` values)

`__init__.py` (facade, `__all__` = the ten contract names), `keys.py`, `config.py`, `pretty.py`,
`plugin.py`, `allure_hooks.py`, `logging_setup.py` — a Python package per the language rules.

### Cell 2 — `goga_tool_pybuggy/config` (MODIFY, rename-only)

#### CODEMANIFEST — `goga_tool_pybuggy/config/CODEMANIFEST` (diff)

**Change** the global `Annotations` — the first-paragraph phrase:

```
Was: The tool config file is the single source of both reading routines: …
Now: The api tool config file (.goga/tools/pybuggy/api.yml) is the single source of both reading
routines: each obtains the raw parse through the platform facade; the platform import resolves at
call time so goga never becomes a runtime dependency. Old config.yml files are not read — a clean
break, no migration shim; existing consumer projects rename by hand.
```

The remaining global-annotation paragraphs — unchanged.

**Change** `Config` — the annotation first line:

```
Was: Root configuration of pybuggy, stored at .goga/tools/pybuggy/config.yml.
Now: Root configuration of pybuggy api tests, stored at .goga/tools/pybuggy/api.yml.
```

**Change** `load_config` — the annotation first line and one added Requirement:

```
Was: Read the pybuggy tool config and validate it into a `Config` model.
Now: Read the pybuggy api tool config and validate it into a `Config` model.

Requirements (+):
- The file location is .goga/tools/pybuggy/api.yml (the platform path standard) — an old
  config.yml is ignored entirely: never read, never migrated.
```

The Algorithm and the remaining Requirements — unchanged (an absent file fails with a clean error
naming the location).

**Change** `resolve_autonomy` — the annotation first line and Algorithm step 1:

```
Was: …validating the whole pipelines axis of the tool config on the way.
Now: …validating the whole pipelines axis of the api tool config on the way.

Algorithm step 1: Read the raw content of the api tool config file through the platform facade.
```

**Unchanged**: `GitEntry`, `SpecEntry`, `PipelineAutonomy` (all annotations and members), the
document structure. **Change** the footer `Description`:

```
pybuggy api-test configuration models and reading routines for .goga/tools/pybuggy/api.yml —
the specs schema and the pipelines autonomy axis. The web kind reads its own web.yml (the web
cell); this cell is api-only.
```

#### .usages file — `goga_tool_pybuggy/config/.usages/configuration.md` (MODIFY, full replacement content)

```md
# goga_tool_pybuggy.config — Configuration Loading

## Domain

Cell `goga_tool_pybuggy/config` provides consumption patterns for loading `.goga/tools/pybuggy/api.yml` into typed models and accessing spec entries. Target audience: consumer commands and the CLI facade.

## Loading the configuration

```python
from goga_tool_pybuggy.config import load_config

config = load_config()  # the fixed location .goga/tools/pybuggy/api.yml
```

The `load_config` function obtains the raw parse of the api tool config file through the goga tool-config facade and validates the result into the `Config` model. An absent file fails with a clean error naming the tool config location; an invalid configuration raises a pydantic validation error.

An old `.goga/tools/pybuggy/config.yml` is not read — pybuggy 2.1 renamed the file to `api.yml` (clean break): rename an existing `config.yml` by hand.

## Accessing spec entries

```python
for name, entry in config.specs.items():
    location = entry.location  # project-root-relative path to the spec file
    git = entry.git  # Optional[GitEntry]; None → local spec
    clone_url = git.url  # clone URL (no embedded tokens)
    repo_path = git.location  # path inside the repository
    repo_ref = git.ref  # Optional[str]; branch/tag to clone; None → default branch
```

- `name` (the dict key) is used by consumers for output and for the `--spec` filter. The key is
  free-form; consumers that lay artifacts on the filesystem derive a Python-identifier segment
  from it (every non-word character becomes `_`, a leading digit is prefixed with `_` — the key
  `some-spec` yields the `some_spec` directory), so any name is safe to declare.
- `entry.git` can be `None` — the consumer treats such a spec as local and skips it silently.
- `git.ref` is the default ref for cloning; the consumer can override it with the `--ref` option (priority order: `--ref` > `git.ref` > default branch).

## Preconditions

- The file location follows the platform path standard for tool configs (`.goga/tools/<tool>/<filename>`); the platform resolves it.
- The `type` field is declarative — it does not affect parsing (Prance auto-detects the version).
```

#### .usages file — `goga_tool_pybuggy/config/.usages/autonomy.md` (MODIFY, targeted)

Every occurrence of `.goga/tools/pybuggy/config.yml` → `.goga/tools/pybuggy/api.yml` (the pipelines
axis is read from the api config). All other content preserved verbatim.

### Cell 3 — `goga_tool_pybuggy/plugin` (MODIFY)

#### CODEMANIFEST — `goga_tool_pybuggy/plugin/CODEMANIFEST` (diff)

**Add** to the header `Imports` (the last block):

```yaml
  - Types:
      - WebPlugin
      - WebConfigKeys
    Usages:
      - pybuggy-web
    From: goga_tool_pybuggy/web
```

`Usages` — unchanged (conventions, pluginator, jinja2, testcontainers).

**Add** to the global `Annotations` — a paragraph after the sandbox paragraph ("The cell carries the
fixture-driven sandbox activation…"):

```
The cell carries the fixture-driven web activation: the installation entry gates on the presence of
the web config document (named by `WebConfigKeys` from Imports) — with the document the `WebPlugin`
joins the same installation call and owns the web test kind: the `web` fixture (a per-test
prettyplay runtime with the step cache next to the test file), the --strict-mode and --interactive
options, Allure step reporting, and the prettyplay event log formatter. The web plugin reads and
validates its own document in its configure step — an invalid document fails the run at
configphase; without the document nothing web-related is registered, and a test requesting the web
fixture gets pytest's standard "fixture 'web' not found".
Use `pybuggy-web` from Imports for the consumer patterns of web tests.
```

**Change** in the global `Annotations` and the `ApiPlugin`/`PluginConfigKeys` annotations: every
occurrence of `.goga/tools/pybuggy/config.yml` → `.goga/tools/pybuggy/api.yml` (in `ApiPlugin`:
"Decorated with @define.plugin bound to the pybuggy api config file"; in `PluginConfigKeys`:
"written into .goga/tools/pybuggy/api.yml" — the 9 members and their values unchanged).

**Change** `install(...kwargs: object)` — insert an Algorithm step between the sandbox step (4) and
`install_pytest_plugins`, renumbering:

```yaml
    5. Gate the `WebPlugin` on the presence of the web config document (the file check of the fixed
       platform tool-config path named by `WebConfigKeys.FILENAME` from Imports): with the document,
       append a `WebPlugin` instance to the same positional plugin list — the plugin reads and
       validates its config itself in its configure step; without the document nothing web-related
       is registered, and a test requesting the `web` fixture gets pytest's standard "fixture 'web'
       not found".
    6. Call install_pytest_plugins with every gated plugin to inject pytest_addoption/
       pytest_configure/pytest_collection_finish into that namespace (see `pluginator`).
```

**Change** `install` — Requirements (the "same installation call" item updated, one item added):

```
- The same installation call enables the ApiPlugin and — when the documents are present — the
  `SandboxPlugin` and the `WebPlugin`; no new enablement surface exists.
- The web gate performs no validation — the document is only checked for presence; validation
  belongs to the web plugin's configure step (an invalid document fails at configphase).
```

**Change** `install` — Use-lines (+):

```
Use `pybuggy-web` from Imports for the consumer patterns of the web test kind.
```

**Unchanged**: `ApiPlugin` (members, signature, methods — only the path renames above),
`SandboxPlugin` (entirely), `render_base_url` (entirely), `PluginConfigKeys` (structure and 9
properties). **Change** the footer `Description` (+ one sentence):

```
… The installation entry gates the product sandbox plugin on the sandbox document and the web
plugin on the web document (goga_tool_pybuggy/web).
```

Implementation touch implied by the CODEMANIFEST: `defaults.py` gains the web document path constant
(named by `WebConfigKeys.FILENAME` under the platform tool-config root) used by the `install` gate.

#### .usages file — `goga_tool_pybuggy/plugin/.usages/enable.md` (MODIFY, add a section)

Add after "Sandbox activation":

```md
## Web activation

The same `plugin.install()` call also installs the pybuggy web plugin: when the test repository
holds the web config document at `.goga/tools/pybuggy/web.yml`, the plugin provides the `web`
fixture — a per-test browser runtime for step-sentence tests (each step sentence becomes Playwright
code once, cached next to the test file and replayed without any LLM involvement). The web plugin
validates the document at configphase; an invalid document fails the run before any collection.
Without the document nothing changes — no fixture exists, and a test requesting it fails with
pytest's standard "fixture 'web' not found". Run web suites with `--strict-mode` in CI (replay-only,
zero LLM calls); `--interactive` enables interactive step healing locally. Writing web tests means
authoring step sentences consumed by the `web` fixture (one action per sentence, full URLs); the
step cache lands next to the test file and is committed to the repository.
```

The remaining sections — unchanged.

#### .usages file — `goga_tool_pybuggy/plugin/.usages/configuration.md` (MODIFY, targeted)

Every occurrence of `.goga/tools/pybuggy/config.yml` → `.goga/tools/pybuggy/api.yml` (the options
table, the examples, the resolution priority), plus a note closing the "Resolution priority"
section:

```md
These options belong to the api plugin reading `api.yml`; the web plugin reads its own `web.yml`
with its own key set. An old `config.yml` is not read — pybuggy 2.1 renamed the file to `api.yml`
(clean break): rename an existing `config.yml` by hand.
```

### Cell 4 — `goga_tool_pybuggy/commands/init` (MODIFY)

#### CODEMANIFEST — `goga_tool_pybuggy/commands/init/CODEMANIFEST` (diff)

**Add** to the header `Imports` (the last block):

```yaml
  - Types:
      - WebConfigKeys
    Usages:
      - pybuggy-web
    From: goga_tool_pybuggy/web
```

`Usages` — unchanged.

**Add** to the global `Annotations` (a paragraph after the first, order-of-actions paragraph):

```
The pybuggy question block is kind-aware: the first record asks the test kind (api / web / both) and
gates every downstream block on it. The declarative block carries only the unconditional records —
the kind, the base image, and the built-image name; every kind-dependent survey happens at the
amendment moment, where the tool reads the kind from the answer view and branches: the api branch
surveys the api options, the specs (first and additional), and the autonomy confirms; the web branch
surveys the web minimum (LLM provider, generation/classification model, browser, headless). Both
tool config files — api.yml and web.yml — are buffered through the session contribution and written
by the engine. The bootstrap closes kind-dependently: the written file is the kind signal — the api
examples document into api.yml; the web examples, the pybuggy-web usage registration, and the
Dockerfile playwright line apply only when web.yml was written. The api and web question sets never
cross. The web config keys are `WebConfigKeys` from Imports — the single source for the survey, the
payload, and the commented examples.
```

**Add** six new type declarations:

```yaml
"survey_api_options() -> answers:dict[str, object]":
  location: session.py
  annotations: |
    Interactively survey the api plugin options — the kind-gated api branch of the amendment moment
    (moved from the former declarative block: the declarative records carry no conditional
    visibility).

    `answers`: the answered api scalar keys; unanswered keys dropped.

    Algorithm:
    1. Ask base_url as a required input — a Jinja2 template string; an empty entry re-asks with a
       required prompt.
    2. Ask every scalar member of `PluginConfigKeys` except BASE_URL, HEADERS, and LOADER as an
       optional input, each prompt stating what the field is for; Enter skips.

    Requirements:
    - Prompt texts preserved from the former declarative block so both flows read as one.
    - Required fields validated at the prompt — an empty base_url never reaches the payload.

    Constraints:
    - Do not catch click.Abort — a cancelled prompt propagates so the engine mediator drops the whole
      contribution with a warning (the session continues).
    - Do not survey HEADERS or LOADER — the bootstrap documents them as commented examples.

    Use `PluginConfigKeys` for the scalar key set. Use `conventions` for logging-free TTY practices
    and testing.

"survey_specs() -> specs:list[dict[str, object]]":
  location: session.py
  annotations: |
    Interactively survey the specs — the first spec and the confirm-gated additional specs as one
    flow (absorbs the former extra-specs follow-up; the first spec moved from the declarative
    block).

    `specs`: one mapping per accepted spec, keyed by the first-spec field names.

    Algorithm:
    1. Ask the first spec field by field: name (required — an empty entry re-asks with a required
       prompt), type (a swagger|openapi choice), location (required — re-asked when empty), then the
       optional git fields (input; an empty git url means no git source, an empty git ref the default
       branch).
    2. Ask "Add another spec?" as a confirm (default no); a decline ends the survey with no
       additional specs.
    3. For each accepted additional spec ask the fields in the first-spec order; repeat the confirm
       after every accepted spec until declined; return the collected mappings (the first spec
       first).

    Requirements:
    - The prompt texts mirror across the first and the additional specs so both read as one flow.
    - Required fields validated at the prompt.
    - At least the first spec always lands.

    Constraints:
    - Do not validate spec semantics here — `parse_specs` owns the entry assembly.
    - Do not catch click.Abort — a cancelled prompt propagates so the engine mediator drops the whole
      contribution with a warning (the session continues).

    Use `conventions` for logging-free TTY practices and testing.

"survey_web_config() -> answers:dict[str, object]":
  location: session.py
  annotations: |
    Interactively survey the web minimum — the kind-gated web branch of the amendment moment.

    `answers`: the surveyed web keys.

    Algorithm:
    1. Ask provider as a choice of openai|anthropic (default openai).
    2. Ask generation_model as a required input (re-asked when empty).
    3. Ask classification_model as a required input (re-asked when empty).
    4. Ask browser_name as an input (default chromium).
    5. Ask headless as a confirm (default yes).

    Requirements:
    - The minimum only — the remaining `WebConfigKeys` arrive as commented examples in web.yml.
    - The answers shape feeds `build_web_config_data`.

    Constraints:
    - Do not catch click.Abort — a cancelled prompt propagates so the engine mediator drops the whole
      contribution with a warning (the session continues).
    - Do not survey prompts, attempts, polling, or cache keys — the bootstrap documents them as
      commented examples.

    Use `WebConfigKeys` from Imports for the key set.
    Use `pybuggy-web` from Imports for the consumer meaning of the surveyed fields.
    Use `conventions` for logging-free TTY practices and testing.

"build_web_config_data(web_answers: dict[str, object]) -> data:dict[str, object]":
  location: session.py
  annotations: |
    Pure mapping of the surveyed web answers into the web config file payload.

    `web_answers`: the `survey_web_config` answers.
    `data`: the serializable payload of .goga/tools/pybuggy/web.yml.

    Algorithm:
    1. Map the surveyed minimum into active keys: provider, generation_model, classification_model,
       browser.name, browser.headless.
    2. Add the active defaults: strict false, interactive false.
    3. Return the payload.

    Requirements:
    - The payload satisfies the web config schema — every key is a `WebConfigKeys` member; the
      document carries the surveyed minimum plus the strict/interactive defaults.
    - The payload is plain serializable data — the engine writes the YAML.

    Constraints:
    - Do not prompt or touch the filesystem — pure.
    - Do not emit commented records — `document_web_config_examples` adds them in the bootstrap.

    Use `WebConfigKeys` from Imports for the key set. Use `conventions` for type hints and testing.

"document_web_config_examples(config_path: Path) -> documented:list[str]":
  location: bootstrap.py
  annotations: |
    Round-trip edit of .goga/tools/pybuggy/web.yml documenting the absent web keys as commented
    example records — the option surface the engine's plain serialization does not carry.

    `config_path`: path to the web config file.
    `documented`: the record texts added; empty when nothing was added.

    Algorithm:
    1. No-op (return an empty list) when the file is absent or holds no mapping.
    2. Walk the `WebConfigKeys` members in declaration order; a member absent as an active key whose
       record marker is not already in the file text accumulates its example record — the browser
       subkeys as nested records, the prompts as block-scalar examples, the scalars as one-line
       records, cache_root as a path example.
    3. Pin the accumulated records, in walk order, before the next active key via the
       before-comment — the browser section is the terminal anchor.
    4. Write the document back only when at least one record was added.

    Requirements:
    - Idempotent by marker detection: a repeat run over its own output adds nothing.
    - Active keys and their values are never modified — only comments are added.
    - The surveyed keys (provider, the models, browser.name, browser.headless) and the
      strict/interactive defaults stay active and are never documented.

    Constraints:
    - Do not create the file when absent — only document an existing web config.
    - Do not touch keys or comments beyond the added records.

    Use `WebConfigKeys` from Imports for the member walk. Use `ruamel-yaml` for the round-trip edit.
    Use `conventions` for testing.

"install_playwright(dockerfile_path: Path) -> line:str | None":
  location: bootstrap.py
  annotations: |
    Write the playwright browser-install RUN line to the consumer Dockerfile — the web-kind
    environment step (browser binaries are an environment requirement).

    `dockerfile_path`: path to the consumer Dockerfile.
    `line`: the written install line; None when nothing was written.

    Algorithm:
    1. No-op (return None) when the Dockerfile does not exist — never create the file here.
    2. Read the browser name leniently from the written web.yml (the browser.name key); an absent or
       unreadable document or key is a no-op with a WARNING.
    3. When a playwright install line is already present: return None when it equals the current
       form; otherwise repin it in place — the match keys on the command prefix, not the exact line
       text.
    4. Otherwise ensure the content ends with a newline, append RUN playwright install
       --with-deps <browser>, write the file back; log INFO; return the line.

    Requirements:
    - The line installs the browsers of the surveyed browser name with their dependencies.
    - The existing Dockerfile content is preserved — the install line is the only line this step
      ever writes; appended when absent, repinned in place when a previous form differs.
    - Idempotent at the current browser within a single Dockerfile.

    Constraints:
    - Do not create the Dockerfile when absent — only augment an existing one.
    - Do not hardcode the browser — it is read from the written web config.

    Use `ruamel-yaml` for the lenient read. Use `conventions` for logging and testing.
```

**Change** `pybuggy_questions` — the annotation purpose line and the Algorithm:

```
Was: Build the declarative pybuggy question block — the image survey and the survey of the tool
configuration, asked by the engine.
Now: Build the declarative pybuggy question block — the kind question and the image survey, asked
by the engine.
```

The Algorithm is replaced entirely:

```yaml
    Algorithm:
    1. Declare kind as a choice of api|web|both (default api) — the first record of the block; every
       downstream survey gates on it.
    2. Declare base_image as an input — the FROM of the always-created Dockerfile; the prompt embeds
       the goga-python family hints completed with the runtime minor tag, the newest member is the
       default.
    3. Declare image as an input — the built-image name; the default is "{project}:latest" from the
       git-derived project name, and the input is required when the name is not derivable.
```

Requirements: "The block holds exactly one nesting level — groups carry simple children only.
base_image always carries an answer (its default); image carries one through the default or a
required input; kind always carries an answer (its default)." Constraints (replaced):

```yaml
    - Do not declare kind-dependent records (base_url, the scalar plugin keys, the spec group) —
      they are surveyed at the amendment moment (`survey_api_options`, `survey_specs`); the
      declarative engine records carry no conditional visibility.
    - Do not survey HEADERS or LOADER — the bootstrap documents them as commented example records.
    - Do not declare autonomy questions — the autonomy confirms are surveyed by `survey_autonomy` at
      the amendment moment, after the spec survey.
    - Do not declare web records — the web minimum is surveyed by `survey_web_config` at the
      amendment moment.
    - Do not declare a Dockerfile-path question — the path is the fixed constant delivered by
      `build_config_amendments`.
```

Use-lines: unchanged (no web-key reference — the block declares kind/base_image/image only; the
web-key gating lives in the Constraint naming `survey_web_config`).

**Change** `amend_pybuggy_config` — the annotation purpose line, the Use-lines, and the Algorithm
(replaced entirely):

```
Purpose line — Was: …survey the additional specs and then the autonomy confirms, read the isolated
answer view, and buffer the pybuggy contribution — the config amendments and the tool config file.
Now: …survey the kind-gated branches (api options, specs, autonomy confirms / web minimum), read
the isolated answer view, and buffer the pybuggy contribution — the config amendments and the tool
config files.

Use-lines — Was: Use `survey_extra_specs`, `survey_autonomy`, `build_config_amendments`,
`build_config_data`.
Now: Use `survey_api_options`, `survey_specs`, `survey_autonomy`, `survey_web_config`,
`build_config_amendments`, `build_config_data`, `build_web_config_data`.
```

```yaml
    Algorithm:
    1. Return immediately when the session did not invite this tool.
    2. Read the answer view from the context.
    3. Read the kind answer.
    4. api or both: survey the api options via `survey_api_options`, the specs via `survey_specs`,
       then the autonomy confirms via `survey_autonomy` — specs first, autonomy after them.
    5. web or both: survey the web minimum via `survey_web_config`.
    6. Buffer every entry of `build_config_amendments` as a config amendment (unconditional — the
       image inputs are kind-neutral).
    7. api or both: buffer the api tool config file with `build_config_data`.
    8. web or both: buffer the web tool config file with `build_web_config_data`.
```

Requirements (+): "The api and web question sets never cross — an api-only session never asks a web
question and vice versa; a both-kind session asks both branches in order (api first, web after it)."
The existing requirements (answer view contents, exception → contribution dropped with a warning)
and the Constraints — unchanged.

**Remove** `survey_extra_specs` (absorbed by `survey_specs`).

**Change** `survey_autonomy` — Constraints (+ first item): "Called only for the api and both kinds,
after `survey_specs` completed." Plus the purpose-line reference: "…asked by the tool after
`survey_specs` completed…" (Was: `survey_extra_specs`). Everything else verbatim.

**Change** `build_config_data` — the signature and Algorithm step 1:

```yaml
"build_config_data(answers: dict[str, object], specs: list[dict[str, object]], autonomous: dict[str, bool]) -> data:dict[str, object]":
```

```
    1. Build the specs mapping via `parse_specs` from the surveyed specs list — the first mapping is
       the first spec (strictly validated), the rest are the additional specs.
```

`answers` is now the `survey_api_options` output (plus the block answers), `specs` the
`survey_specs` output, `autonomous` the `survey_autonomy` output. The purpose annotation names
api.yml (rename). Requirements (+): "Called only for the api and both kinds — the caller owns the
kind gate." Everything else unchanged.

**Change** `document_config_examples` — the annotation: "Round-trip edit of
.goga/tools/pybuggy/api.yml documenting the absent plugin members…" (the logic unchanged).

**Change** `run_bootstrap` — Algorithm step 2 gains the web root; steps 3b/6b/6c inserted:

```
Step 2 (+): "…the packaged usage roots — the api cell, the cells of the sandbox subtree, and the
web cell that carry usage files; …the web usage flat as <stem>.md…"

3b. When the web config was written (the kind signal — the file the session wrote), document its
    absent keys via `document_web_config_examples` — idempotent; a no-op when the session wrote no
    web config.
6b. When the web config was written, register the pybuggy-web usage key and its annotation line via
    `register_usages` and `register_annotations` — idempotent.
6c. When the web config was written, augment the Dockerfile via `install_playwright` (the browser
    comes from the written web config).
```

Requirements (+): "…when the web kind was chosen — the web config carries the commented examples of
its absent keys, the pybuggy-web usage key and its annotation line are registered, and the Dockerfile
carries the playwright install line. The api steps no-op naturally when api.yml is absent (web-only)
and the web steps no-op when web.yml is absent (api-only)." Constraints (+): "Do not prompt about
the web delivery — the gates are file presence; the kind answer never crosses the session boundary."

**Change** `parse_specs` — the `extra_specs` parameter description only (the signature, Algorithm,
Requirements, and Constraints stay unchanged):

```
Was: `extra_specs`: the `survey_extra_specs` mappings; None when the gate was declined.
Now: `extra_specs`: the additional surveyed mappings of `survey_specs`; None when only the first
spec was surveyed.
```

**Unchanged**: `init_cmd`, `run_init`, `resolve_init_mode`, `run_session`, `declare_pybuggy_session`,
`build_config_amendments`, `write_test_convention`, `ensure_review_skip`,
`install_pybuggy`, `register_usages`, `register_annotations`, `write_pybuggy_conftest`. The footer
`Description` gains the "kind-aware" sentence.

#### .usages file — `goga_tool_pybuggy/commands/init/.usages/init.md` (MODIFY)

The "What is asked"/artifacts sections: the kind question is asked first (api / web / both); the
artifacts — api.yml when api is chosen, web.yml (the surveyed minimum plus commented examples) when
web is chosen; the bootstrap steps gain the playwright line and the pybuggy-web registration; a
clean-break note (an old config.yml is not read). The remaining sections are preserved.

#### .usages file — `goga_tool_pybuggy/commands/init/.usages/config-build.md` (MODIFY)

"What is asked" is rebuilt: unconditional — kind, base_image, image; the api branch — base_url
(required), the optional scalars, the first + additional specs (one flow), the autonomy confirms
last; the web branch — provider, generation_model, classification_model, browser_name, headless.
"What is not asked": headers and loader (api — commented examples), the remaining web keys
(commented examples). The artifacts: api.yml and web.yml, both written by the engine. A clean-break
note is added.

### Root — `goga_tool_pybuggy` (doc-only)

#### .usages file — `goga_tool_pybuggy/.usages/assembly.md` (MODIFY, targeted)

Every occurrence of the api tool config path `.goga/tools/pybuggy/config.yml` →
`.goga/tools/pybuggy/api.yml` (lines 91 and the session/bootstrap mentions); the web kind joins the
assembly description where the tool configs are enumerated. No CODEMANIFEST change, no new types.

### Project manifest — `pyproject.toml` (MODIFY)

- `prettyplay>=0.0.3,<0.1.0` (the lower bound exists; the upper cap is added — the repo's
  own-package convention).
- `allure-pytest` added under `[project.optional-dependencies].test`.
- playwright stays transitive (no separate declaration — the single direct import
  `playwright.sync_api.Error` is documented in the prettyplay usage).

### Repository doc sweep (targeted rename)

Every remaining occurrence of the old api tool config path `.goga/tools/pybuggy/config.yml` →
`.goga/tools/pybuggy/api.yml` across the surfaces the cell artifacts do not cover (verified by
grep; the endpoint-command CODEMANIFESTs are clean — only their usage docs carry the path):

- `docs/` — the published package documentation, 9 files: `index.md`, `configuration.md`,
  `getting-started.md`, `plugin/index.md`, `cli/init.md`, `cli/list.md`, `cli/pull.md`,
  `pipelines/api-automate.md`, `pipelines/api-patch.md`. Mechanical path rename only; a
  content-level kind-aware rewrite of `docs/cli/init.md` (the new kind question, the web branch)
  is noted for the apply stage and not part of this sweep.
- Cell usage docs of the dependent endpoint-command cells: `commands/pull/.usages/pull.md`,
  `commands/diff/.usages/diff.md`, `commands/info/.usages/info.md`,
  `commands/list/.usages/list.md`, `commands/generate/.usages/generate.md`.
- The packaged skill `goga_tool_pybuggy/skills/pybuggy-api-automate-requirements-intake/SKILL.md`.
- Project-level usages: `.goga/usages/cooks/pluginator.md` (the `@define.plugin` example binding
  and the plugin_config paragraph) and `.goga/usages/cooks/jinja2.md` (the base_url example
  document header).

## Dependency Map

```
goga_tool_pybuggy/web  [CREATE, leaf — no internal Imports]
  ├──(Imports: WebPlugin, WebConfigKeys + usage pybuggy-web)──▶ goga_tool_pybuggy/plugin        [MODIFY]
  └──(Imports: WebConfigKeys + usage pybuggy-web)──────────────▶ goga_tool_pybuggy/commands/init [MODIFY]

goga_tool_pybuggy/config  [MODIFY, leaf]
  └──(Imports: SpecEntry, GitEntry + usages configuration, autonomy — existing)──▶ goga_tool_pybuggy/commands/init

goga_tool_pybuggy/plugin ──(Imports: PluginConfigKeys — existing)──▶ goga_tool_pybuggy/commands/init
goga_tool_pybuggy/plugin ──(Imports: install — existing)──────────▶ goga_tool_pybuggy (root, doc-only)

Existing edges unchanged: plugin → {api, plugin/loaders, sandbox, sandbox/engines, sandbox/config};
commands/init and the endpoint commands → config; root → the command/plugin/autonomous/statuses
cells.

New edges: plugin → web, commands/init → web. No cycles (web is a leaf; neither web's providers
import it back).
Implementation order: web → config → plugin → commands/init → root docs → pyproject.toml.
```

## Verification Checklist

After implementing each artifact, verify:

- **Cell `web`**
  - `goga lint` passes on the new CODEMANIFEST; the facade `__init__.py` exposes exactly the ten
    contract names through `__all__`; `python -c "from goga_tool_pybuggy.web import WebPlugin"`
    works in the virtualenv.
  - `WebConfig`/`BrowserSettings`: pydantic kw_only; defaults equal the prettyplay defaults;
    unknown keys rejected; `validate_web_config` — non-mapping root and empty mapping fail with
    clean errors naming the document (never a raw traceback).
  - `build_pretty_config`: 1:1 field mapping; `strict`/`interactive` OR-semantics (a flag forces
    on, never off); no env or pyproject reads (assert via monkeypatched env — the explicit object
    wins).
  - `WebPlugin`: an invalid web.yml fails at configphase (before collection); the formatter is
    installed once (idempotent — no duplicate handlers); the `web` fixture computes the cache
    address from the item (a test running outside the project root resolves paths — no
    `relative_to(cwd)` crash); the runtime is constructed with cleanup disabled — a run failing
    mid-test keeps every cached file of the test's key (no cache-miss cascade on the next strict
    run); strict mode makes zero provider calls (a mocked provider counter
    stays 0 and a cache miss fails).
  - `web_cache_path`: class-aware and parametrize-agnostic path, parametrize-aware key (per
    `parametrize` fixtures); pure.
  - `AllureStepHooks`: constructed only with allure importable (guard mocked both ways); a failed
    step attaches `screenshot.png` (mock `get_screenshot` bytes; `PlaywrightError` swallowed); the
    step/group stacks stay balanced on a mid-group failure.
  - `EventLogFormatter`: the human-readable event set renders without extras; other events carry
    sorted extras; no reserved field leaks.
  - Unit tests make no LLM calls and open no browser: the provider is mocked, cache/replay paths
    exercised with canned artifacts; browser-bound checks carry `pytest.mark.skipif` guards.
- **Cell `config`**
  - `goga lint` passes; `load_config` reads `api.yml`; a repo holding only an old `config.yml`
    gets the clean absent-file error (the old file is never read); `resolve_autonomy` unchanged
    behavior on the renamed path.
  - The two usage docs name api.yml consistently.
- **Cell `plugin`**
  - `goga lint` passes; the new Imports resolve to the web cell (no reverse import — web never
    imports plugin).
  - `install()` with `web.yml` present registers WebPlugin and the `web` fixture; without it,
    nothing web-related registers and a test requesting `web` fails with the standard
    "fixture 'web' not found"; the same call keeps the api and sandbox gating intact.
  - `ApiPlugin` resolves its options from `api.yml` (an old `config.yml` ignored).
  - `enable.md` renders the web activation section consistently with the gate behavior.
- **Cell `commands/init`**
  - `goga lint` passes; `pybuggy_questions` declares exactly kind/base_image/image; the kind
    question is first (default api).
  - `amend_pybuggy_config`: kind=api — only the api surveys run, only api.yml is buffered; kind=web
    — only `survey_web_config` runs, only web.yml is buffered; kind=both — both branches in order;
    a cancelled prompt drops the whole contribution (the session continues, exit 0).
  - `build_web_config_data`: the payload carries provider, the models, browser{name, headless},
    strict false, interactive false — every key a `WebConfigKeys` member.
  - `document_web_config_examples`: idempotent by marker; active keys untouched; the surveyed keys
    and the strict/interactive defaults never documented.
  - `install_playwright`: absent Dockerfile — None; repin on browser change (prefix match); the
    browser read leniently from the written web.yml; idempotent.
  - `run_bootstrap`: web-only session — the web steps apply, the api steps no-op; api-only — the
    reverse; a repeat run changes nothing.
  - Interactive flows tested with click runner / mocked prompts (no TTY in tests).
- **Docs and manifest**
  - `assembly.md`, `enable.md`, `configuration.md` (plugin), `init.md`, `config-build.md`,
    `configuration.md`/`autonomy.md` (config) — no stale `config.yml` mentions of the api kind.
  - The repository doc sweep is complete: `grep -rn "tools/pybuggy/config.yml" docs/
    goga_tool_pybuggy/ .goga/usages/` returns nothing (the endpoint-command usage docs, the
    packaged skill, and the pluginator/jinja2 cooks included).
  - `pyproject.toml`: `prettyplay>=0.0.3,<0.1.0`; `allure-pytest` under the `test` extra;
    `pytest -x` and `ruff check goga_tool_pybuggy/` pass in the virtualenv.
- **Project validation**
  - `pytest tests/ -x` passes; `ruff check goga_tool_pybuggy/` is clean; `goga lint` passes across
    the four touched cells.
