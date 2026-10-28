# Plan: `web-tests`

Compiled by `goga-plan-by-design` from `.goga/history/2026/web-tests/design.md` (design-review
applied: 7 findings fixed). Contract sources (read-only): `goga_tool_pybuggy/web/CODEMANIFEST`,
`goga_tool_pybuggy/plugin/CODEMANIFEST`, `goga_tool_pybuggy/config/CODEMANIFEST`,
`goga_tool_pybuggy/commands/init/CODEMANIFEST`.

---

## Purpose

Implement the **web test kind** — the new leaf cell `goga_tool_pybuggy.web` (the prettyplay
capability: `WebPlugin` with the `web` fixture, strict/interactive options, Allure step reporting,
the prettyplay event log formatter, and the `WebConfig` surface validated from `web.yml` and mapped
onto an explicit `PrettyConfig`), the `config.yml` → `api.yml` clean-break rename in the config and
plugin cells, the presence-gated `WebPlugin` installation in the plugin cell, and the kind-aware
`goga init` flow in the commands/init cell (new web surveys/builders, kind-branched contribution,
web-aware bootstrap delivery).

After implementation the package provides: a complete web cell with a 10-name facade; plugin
installation that gates the web plugin on `.goga/tools/pybuggy/web.yml` presence; config reading
that names `api.yml` and never reads the old `config.yml`; an init session that surveys api and/or
web settings by `kind` and writes `api.yml` and/or `web.yml`; a bootstrap that delivers web usages,
commented `web.yml` examples, the `pybuggy-web` usage registration, and the Dockerfile playwright
line — all file-presence-gated.

The main contract-vs-code gaps: all seven web module files and the facade are missing (only
`CODEMANIFEST` + `.usages/pybuggy-web.md` exist); `tests/web/` does not exist; the rename is not
applied to `config/storage.py`, `plugin/defaults.py`, or `tests/conftest.py::tool_config`; the
plugin `install()` has no step-5 web gate; `commands/init` carries the old question set (with
`survey_extra_specs`) and a 20-name facade (target: 25).

Strategy: bottom-up per the design — web cell internals (keys → config → pretty → logging_setup →
allure_hooks → plugin → facade), then the config rename, then the plugin cell, then commands/init
(session → bootstrap → init + facade), then web integration tests, then full verification. Every
coding task follows the TDD workflow (contract tests first) and the REPL cycle below.

---

## Mandatory Rules (extracted from the project convention)

These rules are extracted from `.goga/usages/conventions.md` (the `conventions` usage connected by
every touched CODEMANIFEST), the language rules (`goga-cell-python`), and the tool configuration in
`pyproject.toml`. They are **mandatory for every task in this plan** — no task may weaken them.

### M1. Coding style — strictly per `conventions`

1. **Python 3.10+ only**; all configuration lives in `pyproject.toml`.
2. **Virtualenv**: execute ALL code (pytest, ruff, python) inside the repo virtualenv — create it
   if missing. No tool runs against the system interpreter.
3. **Imports**: relative imports for ALL intra-package references
   (`from .config import …` inside the web cell; `from ...web import WebConfigKeys` from
   commands/init; `from ..web import WebPlugin` from the plugin cell). Absolute imports only for
   stdlib and third-party. An absolute import within the same package is forbidden.
4. **Data models**: pydantic for all data models; every model class uses
   `model_config = ConfigDict(kw_only=True, extra="forbid")` where the contract says so; fields
   carry empty/zero defaults — `None` only where absence is explicit (only `polling_timeout`).
5. **Logging**: the `logging` library; `logger = logging.getLogger(__name__)`; contextual metadata
   via `extra={...}` (machine-readable, filterable); lowercase concise messages; stable event
   names; levels per the convention (INFO lifecycle/enabled, DEBUG absent-gate branches, WARNING
   lenient no-ops, ERROR write failures); **no secrets, credentials, tokens, or PII in any log**
   (step sentences and captured vars land in LLM prompts — documented in `pybuggy-web.md`).
6. **Body formatting**: one blank line between logical blocks inside function/method bodies
   (initialization vs conditions/loops; data preparation vs processing; processing vs return).
7. **Docstrings**: Google style, mandatory on every public function, method, and class; the first
   line starts with a capital letter and ends with a period; `Args` when parameters exist,
   `Returns` when a value returns, `Raises` for exceptions beyond built-ins. Module docstrings in
   the house style: one line, then the contract nuance.
8. **Type hints**: mandatory everywhere; signature rules allow `str, int, float, bool,
   list[T], dict[str, T], T | None` — no `*args`/`**kwargs`, no unparametrized generics.
9. **Naming**: PascalCase classes; snake_case functions, methods, properties. Facade
   `__init__.py` exposes the contract API through `__all__` — only `__all__` names are the facade.
10. **Line length 120, target py310** (`[tool.ruff]` in `pyproject.toml`). `# noqa: ARG002` on
    hook parameters the body does not use (fixed hook signatures).
11. **Dependencies**: third-party libraries only via `pyproject.toml` with a minimum version; test
    libraries under `[project.optional-dependencies] test`. (Already applied: `prettyplay>=0.0.3,
    <0.1.0` runtime; `allure-pytest>=2.13` test — do not re-add.)

### M2. Test writing rules — strictly per `conventions`

1. **Tools**: pytest (+ pytest-cov); test code is Python 3.10+; runs inside the venv.
2. **Structure mirrors the source directly**: `goga_tool_pybuggy/web/<module>.py` →
   `tests/web/test_<module>.py`. Every test directory carries `__init__.py`. Local fixtures in
   `tests/web/conftest.py`; shared fixtures in `tests/conftest.py`; multi-package integration
   tests directly under `tests/`.
3. **Naming**: files `test_<module>.py`; functions `test_<what>_<scenario>`; grouping
   `class Test<Component>:`.
4. **Types**: unit tests for every public name (main scenario + typical data); edge cases (empty
   inputs `None`/`""`/`[]`/`{}`, boundary values, invalid types, expected exceptions via
   `pytest.raises`); integration tests only for cross-module interaction.
5. **Boundary tests** (option tables, mode resolution) via `@pytest.mark.parametrize` with a table
   covering each boundary.
6. **Mocks**: pure logic — no mocks; file I/O — the `tmp_path` fixture exclusively; subprocesses —
   `mock.patch` the subprocess call; external dependencies — `mock.patch` at the import point.
   Mock only at external boundaries; business-logic tests stay mock-free. The suite doubles only
   `PrettyPlay` (browser/LLM boundary) and click prompts (`_ScriptedClick`) — never the units
   under test.
7. **Self-documenting test names, minimal comments**; `pytest.mark.skipif` only for unavailable
   external dependencies (none needed here — no test opens a browser or calls an LLM).
8. **TDD (goga conventions on top)**: contract tests FIRST in each coding task (they fail —
   expected); logic tests AFTER implementation; integration tests as separate tasks. Every
   contract element has explicit coverage: facade accessibility, API shape, described behavior.
9. **CLI/survey testing**: call the handler function directly via Python (no subprocess); click
   prompts via the existing `_ScriptedClick` double; contributions via the existing
   `ContributionRecorder` double.

### M3. Linters and formatters — enforced across all development stages and local commits

1. **ruff is the single project linter AND formatter** (`conventions` Tools; `[tool.ruff]`,
   `[tool.ruff.lint]`, `[tool.ruff.format]` in `pyproject.toml`: py310, line-length 120, rule set
   `E W F I N UP B SIM PL PLR C4 DTZ PT ARG RUF PTH C90`, per-file ignores for `tests/**`).
   No other linter/formatter may be introduced.
2. **Per unit (REPL cycle, M4)**: focused test run + `ruff check <touched files>` after every
   implementation unit.
3. **Per task (STEP 7 LINT of every coding task)**: `ruff check goga_tool_pybuggy/ tests/` exits 0
   (0 errors); every file created or modified by the task is `ruff format`-clean
   (`ruff format --check <touched files>` — apply `ruff format <touched files>` if not). Do not
   reformat files the plan does not touch.
4. **Per local commit**: a commit is allowed only when, inside the venv, `ruff check
   goga_tool_pybuggy/ tests/` passes AND `pytest tests/ -x` passes. The commit gate applies to
   every stage of this plan (contract-test stage, implementation stage, logic-test stage,
   integration stage) — never commit red tests or lint errors. Commits happen after ralphex review
   approval of each task.
5. **Plan level**: `goga lint` must stay at **25 cells, 0 errors** (CODEMANIFEST integrity is
   checked separately from ruff).

### M4. REPL cycle — continuous interactive evaluation, hot reloading, code migration

1. **Continuous interactive evaluation**: after each implementation unit (a model, a routine, a
   hook method, a gate), evaluate it immediately inside the venv — a focused
   `pytest tests/web/test_<module>.py -x -q` and/or a `python -c "…"` construction — before moving
   to the next unit. Never batch unverified code: the STEP 1→5 loop (red contract tests →
   implement → focused green → extend with logic tests → full suite) is one REPL cycle per unit.
2. **Hot reloading**: the repo is an editable install (`pip install -e '.[test]'`) — every source
   edit is live on the next focused run with no rebuild or reinstall. After every edit, re-run the
   focused tests until green, then proceed to the next unit.
3. **Code migration to source files**: snippets prototyped interactively (`python -c` probes,
   throwaway constructions, exploratory pydantic/ruamel checks) are scaffolding only — anything
   verified interactively must be migrated into the cell source files or the mirrored test files
   before the task completes. Nothing may survive only in a REPL session; no exploratory snippet
   may shadow a contract entity; test doubles built for one focused run migrate into the mirrored
   test module (`_FakePytestConfig`, recording `PrettyPlay` double, item namespaces), never left
   as loose scripts.
4. **Migration target is fixed**: the interactive stage explores behavior; the deliverable is
   always the contract `location` file plus its mirrored `tests/web/test_<module>.py`.

---

## Context

### Contract Surface

**Cell `goga_tool_pybuggy/web` (new, leaf — no Imports)** — facade obligation: every name
importable from `goga_tool_pybuggy.web` (`__all__`, 10 names, classes first then routines,
alphabetical within groups).

**Entity: `WebConfigKeys`** (keys.py)
- Type: class (`str, Enum` — fixed value set; mirrors the `PluginConfigKeys` style)
- Properties: 20 — `FILENAME` (`web.yml`) + 19 scalar/browser keys whose values are the lowercase
  `web.yml` key strings: `PROVIDER, BASE_URL, MODEL, GENERATION_MODEL, CLASSIFICATION_MODEL,
  GENERATION_PROMPT, CLASSIFICATION_PROMPT, STRICT, INTERACTIVE, POLLING_TIMEOUT, POLLING_DELAY,
  GENERATION_ATTEMPTS, HEALING_ATTEMPTS, LLM_REQUEST_ATTEMPTS, SEND_SCREENSHOTS,
  GENERATION_APPROVE, PROBE_TIMEOUT, CACHE_ROOT, BROWSER`.
- Member order is contract order (the bootstrap documenter walks it); fixed — do not add, remove,
  rename, or revalue. Module constant `CONFIG_FILE: Final[str]` names
  `.goga/tools/pybuggy/web.yml` (the `@define.plugin` config path and the error-naming source).

**Entity: `BrowserSettings`** (config.py)
- Type: pydantic model, `kw_only=True, extra="forbid"`; 7 properties: `name: str = "chromium"`,
  `headless: bool = True`, `screen: str = ""`, `endpoint: str = ""`, `accept_dialogs: bool =
  False`, `speed: int = 100`, `timeout: float = 30`. Defaults mirror prettyplay `BrowserConfig`
  exactly. Never carries credentials.

**Entity: `WebConfig`** (config.py)
- Type: pydantic model, `kw_only=True, extra="forbid"`; 19 properties — `provider:
  t.Literal["openai", "anthropic"] = "openai"`, `base_url: str = ""`, `model: str = ""`,
  `generation_model: str = ""`, `classification_model: str = ""`, `generation_prompt: str = ""`,
  `classification_prompt: str = ""`, `strict: bool = False`, `interactive: bool = False`,
  `polling_timeout: float | None = None`, `polling_delay: float = 0.5`, `generation_attempts:
  int = 3`, `healing_attempts: int = 2`, `llm_request_attempts: int = 3`, `send_screenshots:
  bool = False`, `generation_approve: bool = True`, `probe_timeout: float = 0`, `cache_root:
  str = ""`, `browser: BrowserSettings = Field(default_factory=BrowserSettings)`.
- Field order = contract signature order; defaults mirror prettyplay `PrettyConfig` exactly;
  **no value-level validators** (semantic validation belongs to prettyplay at
  `build_pretty_config` time — validation layering). Never carries LLM API keys.

**Routine: `validate_web_config(data: dict[str, object]) -> config: WebConfig`** (config.py)
- Three-rejection algorithm (non-mapping root / empty mapping / `ValidationError` wrap), each
  `ValueError` naming `CONFIG_FILE`; pydantic error chained as `__cause__`; pure.

**Routine: `build_pretty_config(config: WebConfig, strict_flag: bool, interactive_flag: bool) -> pretty: PrettyConfig`** (pretty.py)
- Maps every field 1:1 onto `PrettyConfig` (`model_dump` → pop browser → `BrowserConfig(**…)` →
  overwrite `strict`/`interactive` in the dict with OR values → `PrettyConfig(browser=browser,
  **fields)`); pure — no I/O, no env/pyproject reads. The all-fields construction is load-bearing
  (puts every field into `model_fields_set`).

**Entity: `WebPlugin`** (plugin.py)
- Type: pluginator plugin class — `@define.plugin("pybuggy-web", config=CONFIG_FILE)`; zero
  constructor arguments.
- Properties: `strict -> bool`, `interactive -> bool` (options: `plugin_config_key` STRICT /
  INTERACTIVE, CLI `--strict-mode` / `--interactive`, `store_true`), `activation ->
  WebConfig | None` (None before configure).
- Methods: `configure()` — CLI authority → guarded document read → `validate_web_config` → scrub
  `PRETTYPLAY_*` env → `install_event_log_formatter()`; `web(request)` — function-scope generator
  fixture: cache address → `build_pretty_config` → `PrettyPlay(item.name, web_cache_path(item),
  cleanup=False, config=…)` → guarded `AllureStepHooks` attach → `with runtime: yield … close`.

**Routine: `web_cache_path(item: pytest.Item) -> path: str`** (plugin.py)
- Pure: `<module_stem>/[<Class>/]<original_name>` — parametrize-agnostic path, class-aware;
  derived from the item's own file, never the cwd.

**Entity: `AllureStepHooks`** (allure_hooks.py)
- Type: `StepHooks` subclass (prettyplay), constructed only from the fixture guard
  (`allure is not None`); 5 methods: `on_group_started`, `on_group_finished`, `on_step_started`,
  `on_step_failed` (best-effort screenshot; `AssertionError` for assertion type, `Exception`
  otherwise), `on_step_finished`. Two `ExitStack`s keep enter/exit pairs balanced.

**Entity: `EventLogFormatter`** (logging_setup.py)
- Type: `logging.Formatter` subclass; constructor `(fmt: str, datefmt: str)`; 1 method
  `format(record)` — the five human-readable prettyplay events render plain; other events append
  sorted non-reserved extras as ` | key=value`.

**Routine: `install_event_log_formatter()`** (logging_setup.py)
- `prettyplay` logger → INFO; stdout `StreamHandler` with `EventLogFormatter`; idempotent.

**Cell `goga_tool_pybuggy/config` (rename-only)** — `load_config` / `resolve_autonomy`
(`storage.py`) and `Config` (`config.py`): `config.yml` → `api.yml` naming only. Signatures,
algorithms, the call-time `from goga.config import load_tool_config` import, and `pipelines`
validation are untouched.

**Cell `goga_tool_pybuggy/plugin` (changed)** —
- `install` (`__init__.py`): new Algorithm step 5 — `Path(defaults.WEB_CONFIG_FILE).is_file()` →
  append `WebPlugin()` (zero args), INFO `web plugin enabled`; else DEBUG `web plugin absent`. No
  validation at the gate. Step 6 `install_pytest_plugins(*plugins, context=…)` unchanged.
- `defaults.py` (implementation hints, not contract types): `CONFIG_FILE` value →
  `.goga/tools/pybuggy/api.yml`; new `WEB_CONFIG_FILE: Final[str] = ".goga/tools/pybuggy/web.yml"`
  (literal, mirroring `SANDBOX_CONFIG_FILE`).
- Facade `__all__` stays at its four names (`ApiPlugin`, `PluginConfigKeys`, `SandboxPlugin`,
  `install`) — `WebPlugin` is a web-cell contract type; the plain import
  (`from ..web import WebPlugin`) makes it addressable without re-exporting.

**Cell `goga_tool_pybuggy/commands/init` (changed)** —
- New routines (`session.py`): `survey_api_options`, `survey_specs`, `survey_web_config`,
  `build_web_config_data`; new routines (`bootstrap.py`): `document_web_config_examples`,
  `install_playwright`.
- Changed: `pybuggy_questions` (exactly `kind` / `base_image` / `image`), `amend_pybuggy_config`
  (kind-gated branches; buffers `api.yml` and/or `web.yml`), `build_config_data` (signature
  `(answers, specs, autonomous)`; `specs` is the surveyed list), `survey_autonomy` (api/both
  only), `document_config_examples` (api.yml naming only), `parse_specs` (description only),
  `run_bootstrap` (web usage root in step 2; steps 3b / 6b / 6c; api.yml path in step 3).
- Deleted: `survey_extra_specs` (absorbed by `survey_specs`).
- Facade: 25 names (add `document_web_config_examples`, `install_playwright`,
  `survey_api_options`, `survey_specs`, `survey_web_config`, `build_web_config_data`; remove
  `survey_extra_specs`).

### Re-exports

None. No `->Name: {}` blocks exist in any touched CODEMANIFEST; no embedding obligations.

### Entity Interaction and Data Flow (verbatim from the design)

```
                         .goga/tools/pybuggy/web.yml  (presence-gates everything web)
                                     │ file
                                     ▼
 goga_tool_pybuggy.plugin.install() ─┼─ ApiPlugin (api.yml, unchanged)
   │ 4: sandbox.yml gate → SandboxPlugin
   │ 5: web.yml gate ──────────────► WebPlugin()                    [web cell]
   │ 6: install_pytest_plugins(*plugins)
   ▼
 pytest configphase: WebPlugin.configure()
   ├─ CLI authority  (--strict-mode / --interactive → force True)
   ├─ validate_web_config(plugin_config) ──► WebConfig   (config.py)
   ├─ scrub PRETTYPLAY_* env
   └─ install_event_log_formatter()        (logging_setup.py)
                                     │ activation
                                     ▼
 pytest run phase: WebPlugin.web(request)   (per test)
   ├─ web_cache_path(item) ──► "<module_stem>/<Class>/<original_name>"
   ├─ build_pretty_config(activation, strict, interactive) ──► PrettyConfig (pretty.py)
   │    cache_root override: activation.cache_root or abs(item.path.parent)
   ├─ PrettyPlay(item.name, path, cleanup=False, config=…)     [prettyplay 0.0.3]
   ├─ allure present? ──► AllureStepHooks(runtime).add_hooks()  (allure_hooks.py)
   └─ with runtime: yield … close

 goga init (kind-aware):
   pybuggy_questions() ──► [kind, base_image, image]
   amend_pybuggy_config(context)
     ├─ kind = api|both: survey_api_options → survey_specs → survey_autonomy
     ├─ kind = web|both: survey_web_config
     ├─ build_config_amendments → context.answer(...)
     ├─ api|both: build_config_data({**answers, **api_answers}, specs, autonomous)
     │            → context.write_config("api.yml", …)
     └─ web|both: build_web_config_data(web_answers) → context.write_config("web.yml", …)
   run_bootstrap()
     ├─ step 2: copy usages — api cell (flat), sandbox subtree (sandbox/), web cell (flat)
     ├─ step 3:  document_config_examples(api.yml)
     ├─ step 3b: document_web_config_examples(web.yml)      [file-present gate]
     ├─ step 6b: register pybuggy-web usage key + annotation [file-present gate]
     └─ step 6c: install_playwright(dockerfile)             [file-present gate]
```

**Data Flows (verbatim from the design):**

1. **Activation flow** — `web.yml` → pluginator `plugin_config` dict → `validate_web_config` →
   `WebConfig` (the activation) → per-test `build_pretty_config` → `PrettyConfig` → `PrettyPlay`.
2. **Mode flow** — `web.yml` `strict`/`interactive` keys + `--strict-mode`/`--interactive` CLI
   flags → resolved once in `configure` (a typed flag forces True) → OR-semantics inside
   `build_pretty_config` → `PrettyConfig.strict` / `.interactive`.
3. **Cache-address flow** — `pytest.Item` → `item.path.parent.resolve()` (root, when `cache_root`
   empty) + `web_cache_path(item)` (subdirectory) + `item.name` (cache key) → `PrettyPlay`
   construction; files land next to the test module, committed to the repository.
4. **Onboarding flow** — `kind` answer → branch selection in `amend_pybuggy_config` → surveyed
   answers → payload builders → engine writes `api.yml` and/or `web.yml` → `run_bootstrap` detects
   the written files (the kind signal) and delivers the kind-dependent artifacts.
5. **Reporting flow** — `PrettyPlay` events → `AllureStepHooks` (guarded) → Allure steps/groups +
   `screenshot.png`; `prettyplay` logger events → `EventLogFormatter` → stdout.

### Usages Context

- **`conventions`** — `.goga/usages/conventions.md`. Python rules: relative imports, pydantic
  `kw_only`, Google docstrings, logging with structured `extra`, blank-line discipline, test
  structure/mirroring, mock policy, venv requirement, validation commands. Used by: every new and
  changed module and test file (and distilled into Mandatory Rules above).
- **`pluginator`** — `.goga/usages/cooks/pluginator.md`. `@define.plugin(name, config=…)`,
  `define.option` with `plugin_config_key` + `CommandLine(…, action="store_true")`, fixtures as
  plugin-class methods, `configure()` lifecycle, `install_pytest_plugins`/`call_context`.
  Used by: `web/plugin.py`, the plugin-cell `install()` change.
- **`prettyplay`** — `.goga/usages/cooks/prettyplay.md` (amended by the design's Applied Fix).
  The `PrettyConfig`/`BrowserConfig` field contract, `PrettyPlay` construction
  (`cache_key`/`cache_path`/`cleanup`/`config`), `StepHooks` events, security rules, and the
  verified per-field layering semantics. Used by: `web/config.py`, `web/pretty.py`,
  `web/plugin.py`, `web/allure_hooks.py`.
- **`allure-pytest`** — `.goga/usages/cooks/allure-pytest.md`. The guarded-import pattern and the
  StepHooks→Allure mapping with failure screenshots. Used by: `web/allure_hooks.py`, the fixture
  guard in `web/plugin.py`.

### Imported Usages

- **`pybuggy-web`** from `goga_tool_pybuggy/web` (imported by the plugin and commands/init
  cells) — consumer patterns of the web test kind; the init survey's Use-line references it for
  the consumer meaning of the surveyed fields. Source path:
  `goga_tool_pybuggy/web/.usages/pybuggy-web.md`. Traceable documentation link only — no
  contractual obligation crosses the boundary.

### Local Usages

None required. The design verified `.usages/` state across all four cells: `pybuggy-web.md`,
plugin `enable`/`configuration`, config `configuration`/`autonomy`, init `init`/`config-build` —
all **current**; no drift, no additions. No `.usages/` file changes are planned.

### External Dependencies

- `prettyplay>=0.0.3,<0.1.0` (runtime; pin bounds the 0.0.x pyproject auto-search limitation) —
  `PrettyPlay`, `PrettyConfig`, `BrowserConfig`, `StepHooks`, `PrettyplayError` (from
  `prettyplay.failures`).
- `playwright` — transitive via prettyplay; the **only** direct playwright import permitted in the
  web cell is `playwright.sync_api.Error` (`PlaywrightError`). No browsers needed for tests.
- `pluginator>=1.0.0,<1.1.0` — plugin framework.
- `allure-pytest>=2.13` — test extra only; never a runtime dependency (guarded import).
- `pydantic>=2.0` (2.14 verified behavior: `model_dump` returns all fields; duplicate kwargs →
  `TypeError`; `model_copy(update=…)` does not add keys to `model_fields_set`).
- `ruamel.yaml` (round-trip commented examples, lenient web.yml reads), `click` (surveys),
  `pytest>=8.0`, `pytest-cov>=5.0`, `ruff>=0.15.0`.
- `goga>=2.0.1,<2.1` — test extra only (`load_tool_config` at call time; goga stays out of
  runtime deps).

## Facts

- The contracts are materialized; the implementation is not: `goga_tool_pybuggy/web/` contains
  only `CODEMANIFEST` (10 types) and `.usages/pybuggy-web.md`. `goga lint`: **25 cells, 0 errors**.
- `pyproject.toml` already carries `prettyplay>=0.0.3,<0.1.0` (runtime) and `allure-pytest>=2.13`
  (test extra) — applied by the materialization stage.
- Cell dependency graph (verified by `goga schema`): web is a leaf; edges plugin→web and
  commands/init→web; config-cell consumers are rename-only. Web cell internal:
  `keys.py` (leaf) ← `config.py` ← `pretty.py` ← `plugin.py`; `allure_hooks.py` and
  `logging_setup.py` ← `plugin.py`. Facade imports all six modules.
- Current `plugin/defaults.py`: `CONFIG_FILE = ".goga/tools/pybuggy/config.yml"`,
  `SANDBOX_CONFIG_FILE = ".goga/tools/pybuggy/sandbox.yml"`; `plugin/plugin.py:73` binds
  `@define.plugin("pybuggy", config=defaults.CONFIG_FILE)`.
- Current `config/storage.py`: `_TOOL = "pybuggy"`, `_FILENAME = "config.yml"`;
  `FileNotFoundError("tool config not found: .goga/tools/pybuggy/config.yml")`.
- Current plugin facade `__all__`: `["ApiPlugin", "PluginConfigKeys", "SandboxPlugin", "install"]`
  (stays). Current init facade `__all__`: 20 names including `survey_extra_specs` (target 25).
- `tests/conftest.py`: autouse `_isolate_os_environ` (snapshot/restore — covers scrub-test
  restoration) + `tool_config` writer fixture currently writing `config.yml` (switches to
  `api.yml`).
- Existing doubles to reuse: `tests/plugin/test_sandbox_plugin.py` (`_FakePytestConfig`,
  `_FakeNode`, `_FakeRequest`, `_RefusingPlugin` pattern), `tests/commands/init/conftest.py`
  (`ContributionRecorder`), `tests/commands/init/test_session.py` (`_ScriptedClick`,
  `pinned_version_axis`).
- No repo virtualenv exists yet; `.venv` is gitignored (the conventional location). No git hooks
  are configured — commit gating (M3.4) is procedural through this plan.
- No test opens a browser or calls an LLM: `PrettyPlay` is doubled in fixture tests; the single
  real construction (integration task) is lazy and browser-free; the real `allure` package is
  exercised from the test extra. Zero `skipif` browser guards needed.
- pydantic 2.14 verified facts the implementation relies on: `model_dump()` returns every field
  (set and unset); `PrettyConfig(strict=…, **fields)` raises
  `TypeError: got multiple values for keyword argument`; `model_copy(update=…)` does NOT add keys
  to `model_fields_set` — participation happens through the all-kwargs construction.

## Gap Analysis

- **Missing contract entities**: all 10 web-cell types (seven module files + facade); 6 new
  commands/init routines.
- **Missing facade exposure**: `goga_tool_pybuggy/web/__init__.py` does not exist (10 names);
  init facade lacks the 6 new names and still exports `survey_extra_specs`.
- **API mismatches**: `pybuggy_questions` still declares base_url/scalars/spec-group (contract:
  exactly kind/base_image/image); `build_config_data` signature lacks the `specs` list parameter;
  `amend_pybuggy_config` has no kind branching and writes `config.yml`; `install()` lacks the
  step-5 web gate; `run_bootstrap` lacks steps 3b/6b/6c and the web usage root.
- **Behavioral mismatches**: `plugin/defaults.py` + `config/storage.py` still name `config.yml`
  (contract: `api.yml`, clean break, no migration); `survey_extra_specs` still exists (deleted);
  no PRETTYPLAY env scrub; no event log formatter; no Allure hooks.
- **Existing code to reuse**: `normalize_container_host()` + the sandbox gate block (precedent for
  the web gate); `SandboxPlugin` configure shape (parse guard + `ValueError` wrap); the api
  documenter `document_config_examples` (guard/walk/pin/idempotency pattern for the web twin);
  `install_pybuggy` (prefix-match repin pattern for `install_playwright`); `_SCALAR_PROMPTS`,
  `_NUMERIC_MEMBERS`, `_SPEC_TYPES`, `_AUTONOMY_AXES`, `_BASE_IMAGE_NAMES`, `_DOCKERFILE_PATH`
  module constants in `session.py`/`bootstrap.py` (all stay).
- **Test coverage gaps**: no `tests/web/` tree; rename never-read test missing; plugin gate tests
  missing; kind-branch survey tests missing; documenter/playwright tests missing; init facade
  count test missing; prettyplay layering pin test missing.
- **Workspace visibility**: `goga_tool_pybuggy/web/` is untracked; the CODEMANIFEST/docs/cook
  changes of the materialization stage are uncommitted working-tree state — commit per task after
  review (M3.4 gate).

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next.
> Within each coding task, contract tests are written first (TDD workflow). Package order:
> `goga_tool_pybuggy.web` (Tasks 1–8) → `goga_tool_pybuggy.config` rename (Task 9) →
> `goga_tool_pybuggy.plugin` (Task 10) → `goga_tool_pybuggy.commands.init` (Tasks 11–13) →
> integration tests (Task 14) → final verification (Task 15).
>
> **Standing prohibitions (from the design — apply in every task):** do not add value validators
> to `BrowserSettings`/`WebConfig`; do not read env or pyproject in `build_pretty_config`; do not
> catch `click.Abort` in any survey; do not create the Dockerfile or `web.yml` from the bootstrap
> writers; do not register the web usage unconditionally (file presence is the only gate); do not
> reword any user-visible string pinned by tests (three `validate_web_config` error texts, the
> playwright line `RUN playwright install --with-deps <browser>`, the approved `pybuggy-web`
> annotation line, the example-record texts, the survey prompts, the `kind` question record).

### Task 1: web cell infrastructure — venv, package skeleton, `tests/web` scaffolding (infrastructure)

Establishes the runnable environment and the package/test scaffolding every later web task builds
on. The web cell is a Python package (`goga_tool_pybuggy/web/`) whose `CODEMANIFEST` already
exists; the package `__init__.py` is created here as a minimal marker (module docstring only — the
10-name facade `__all__` lands in Task 8, after all entities exist). Tests mirror the source
directly: `tests/web/` with `__init__.py` and a local `conftest.py` carrying the `web_config`
writer fixture (the sibling of the shared `tool_config`, same shape, `web.yml`).

**Usages relevant to this task:**
- `conventions`: venv requirement ("execute all code within a virtualenv — create it if
  missing"); test structure mirroring (`tests/web/` ↔ `goga_tool_pybuggy/web/`, `__init__.py` per
  directory, local fixtures in `tests/web/conftest.py`); Google docstrings.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create the repo virtualenv if missing: `python3 -m venv .venv` (`.venv` is gitignored); then
  `.venv/bin/pip install -e '.[test]'` (brings `prettyplay>=0.0.3,<0.1.0` + transitive
  `playwright` package, `allure-pytest>=2.13`, `pluginator`, `pytest>=8`, `ruff>=0.15`,
  `goga` test dep)
- [x] Verify the dependency stack in the venv (REPL check — M4):
  `.venv/bin/python -c "from prettyplay import BrowserConfig, PrettyConfig, PrettyPlay, StepHooks; from prettyplay.failures import PrettyplayError; from playwright.sync_api import Error; import allure, pluginator; print('ok')"`
- [x] Run the existing suite to establish the green baseline: `.venv/bin/python -m pytest tests/ -x`
  (all pass before any change)
- [x] Create `goga_tool_pybuggy/web/__init__.py` — module docstring only (one line naming the
  web-test cell); no `__all__` yet (Task 8 fills the 10-name facade)
- [x] Create `tests/web/__init__.py` (empty package marker)
- [x] Create `tests/web/conftest.py` with the `web_config` writer fixture — the same shape as
  `tests/conftest.py::tool_config` (chdir into `tmp_path`, write `text` under
  `.goga/tools/pybuggy/web.yml`, return the path), Google-docstringed
- [x] Verify: `.venv/bin/python -c "import goga_tool_pybuggy.web"` and
  `.venv/bin/python -m pytest tests/web/ -v` (collects, nothing to run yet)
- [x] Lint (M3.3): `.venv/bin/ruff check goga_tool_pybuggy/web/ tests/web/` — 0 errors;
  `ruff format --check` on the created files

### Task 2: `WebConfigKeys` + `CONFIG_FILE` in `web/keys.py` (TDD)

Implements the leaf entity of the web cell — the fixed key set consumed data-driven by the init
survey, the documenter, the validation alignment, and the installation gate. Contract
(`WebConfigKeys()`, location `keys.py`): 20 members, `str`-Enum mirroring the `PluginConfigKeys`
style, member order = contract order. Design algorithm (verbatim):

```
class WebConfigKeys(str, Enum):   # mirror PluginConfigKeys style
    FILENAME = "web.yml"; PROVIDER = "provider"; BASE_URL = "base_url"; MODEL = "model"
    GENERATION_MODEL = "generation_model"; CLASSIFICATION_MODEL = "classification_model"
    GENERATION_PROMPT = "generation_prompt"; CLASSIFICATION_PROMPT = "classification_prompt"
    STRICT = "strict"; INTERACTIVE = "interactive"; POLLING_TIMEOUT = "polling_timeout"
    POLLING_DELAY = "polling_delay"; GENERATION_ATTEMPTS = "generation_attempts"
    HEALING_ATTEMPTS = "healing_attempts"; LLM_REQUEST_ATTEMPTS = "llm_request_attempts"
    SEND_SCREENSHOTS = "send_screenshots"; GENERATION_APPROVE = "generation_approve"
    PROBE_TIMEOUT = "probe_timeout"; CACHE_ROOT = "cache_root"; BROWSER = "browser"

CONFIG_FILE: Final[str] = f".goga/tools/pybuggy/{WebConfigKeys.FILENAME.value}"
```

Member order is contract order (the documenter walks it); values are the lowercase `web.yml`
keys; no validators, no behavior. `CONFIG_FILE` is the implementation-hint source for
`@define.plugin(config=…)` and for the `validate_web_config` error naming. Errors: none. Edge
cases: none — a fixed value set. Constraint: do not add, remove, or rename members or change
their values.

**Usages relevant to this task:**
- `conventions`: Enum declaration style, relative imports, Google docstrings, type hints.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (create `tests/web/test_keys.py`; expected to fail — no module yet):
  import `from goga_tool_pybuggy.web.keys import CONFIG_FILE, WebConfigKeys`;
  `len(WebConfigKeys) == 20`; the 20 members in contract order with exact values; every member is
  a `str` (`isinstance(WebConfigKeys.PROVIDER.value, str)`); `CONFIG_FILE ==
  ".goga/tools/pybuggy/web.yml"`
- [x] **Code**: create `goga_tool_pybuggy/web/keys.py` — module docstring (one line), the
  `WebConfigKeys` enum exactly as the design block above, `CONFIG_FILE: Final[str]` built from
  `WebConfigKeys.FILENAME.value`; Google docstring on the class (purpose + fixed-set constraint)
- [x] **Interface verification**: `.venv/bin/python -m pytest tests/web/test_keys.py -v` — all
  contract tests pass
- [x] **Logic tests** (extend `tests/web/test_keys.py`): `test_web_config_keys_filename_names_the_document`
  — asserts `WebConfigKeys.FILENAME.value == "web.yml"` and `CONFIG_FILE ==
  ".goga/tools/pybuggy/web.yml"` (the cross-cell `plugin_defaults.WEB_CONFIG_FILE == CONFIG_FILE`
  assertion is added in Task 10, when that constant exists); REPL-verify the enum order with
  `.venv/bin/python -c "from goga_tool_pybuggy.web.keys import WebConfigKeys; print([m.value for m in WebConfigKeys])"`
- [x] **Debugging**: `.venv/bin/python -m pytest tests/web/ -x` — fix implementation code until
  all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: members/values/order match the CODEMANIFEST property list
  exactly (20 properties, same order); no extra members
- [x] **Lint** (M3.3): `.venv/bin/ruff check goga_tool_pybuggy/web/ tests/web/` — 0 errors;
  `ruff format --check` on touched files

### Task 3: `BrowserSettings`, `WebConfig`, `validate_web_config` in `web/config.py` (TDD)

Implements the web config surface — the pydantic models validated from `web.yml` and the
three-rejection validator. Contract locations: all three entities in `config.py`. Design
algorithm (verbatim):

```
BrowserSettings(BaseModel):  model_config = ConfigDict(kw_only=True, extra="forbid")
  name: str = "chromium"; headless: bool = True; screen: str = ""; endpoint: str = ""
  accept_dialogs: bool = False; speed: int = 100; timeout: float = 30

WebConfig(BaseModel):  model_config = ConfigDict(kw_only=True, extra="forbid")
  provider: t.Literal["openai", "anthropic"] = "openai"
  base_url: str = ""; model: str = ""; generation_model: str = ""; classification_model: str = ""
  generation_prompt: str = ""; classification_prompt: str = ""
  strict: bool = False; interactive: bool = False
  polling_timeout: float | None = None; polling_delay: float = 0.5
  generation_attempts: int = 3; healing_attempts: int = 2; llm_request_attempts: int = 3
  send_screenshots: bool = False; generation_approve: bool = True; probe_timeout: float = 0
  cache_root: str = ""
  browser: BrowserSettings = Field(default_factory=BrowserSettings)
```

Field order = the contract signature order. Defaults mirror the prettyplay defaults **exactly**
(verified against `PrettyConfig`/`BrowserConfig` 0.0.3). `extra="forbid"` delivers the
unknown-key rejection. `default_factory` avoids any shared-mutable-default concern. **No
value-level validators**: semantic validation (browser matrix, ws/wss endpoint, speed range,
positive ints) belongs to prettyplay at `build_pretty_config` time — pybuggy validates structure
at configphase, semantics surface at the fixture with the library's clean messages (validation
layering).

`validate_web_config` — the three-rejection algorithm from the design trace (verbatim):
1. Non-mapping root → `ValueError(f"{CONFIG_FILE}: the document must parse to a mapping")`.
2. Empty mapping → `ValueError(f"{CONFIG_FILE}: the document is empty — it must carry at least the
   provider and the browser name")`.
3. `WebConfig.model_validate(data)` — `extra="forbid"` rejects unknown keys; `ValidationError`
   wrapped: `ValueError(f"{CONFIG_FILE}: invalid web config document")` with the pydantic error
   chained. Output: the validated `WebConfig`; pure.

Errors: `ValueError` naming `CONFIG_FILE` for non-mapping / empty / invalid documents (pydantic
`ValidationError` chained as `__cause__`). Edge cases (design, verbatim): a `web.yml` carrying
only the surveyed minimum validates (browser defaults fill in); a hand-edited document with
`browser: {}` — `name` defaults to `"chromium"`; semantic violations (`browser.name: safari`,
`generation_attempts: 0`, `endpoint: http://…`) pass `validate_web_config` and fail at
`build_pretty_config`/first fixture with prettyplay's message — accepted layering, documented in
`pybuggy-web.md` terms ("the names the runtime accepts").

**Usages relevant to this task:**
- `conventions`: pydantic model rules (`kw_only=True`, empty defaults, `None` only for explicit
  absence), Google docstrings with `Raises:`, relative imports (`from .keys import CONFIG_FILE`).
- `prettyplay`: the `PrettyConfig`/`BrowserConfig` default tables the models mirror 1:1.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Contract tests** (create `tests/web/test_config.py`; expected to fail):
  `from goga_tool_pybuggy.web.config import BrowserSettings, WebConfig, validate_web_config`;
  model shape — `BrowserSettings` has exactly the 7 fields, `WebConfig` exactly the 19 fields in
  contract order (`list(WebConfig.model_fields)`); both models are `kw_only` and reject unknown
  keys; `validate_web_config` is a module-level callable
- [x] **Code**: create `goga_tool_pybuggy/web/config.py` — module docstring, relative import of
  `CONFIG_FILE` from `.keys`, the two models exactly as the design block, `validate_web_config`
  per the three-rejection algorithm, Google docstrings (`Raises: ValueError` on the validator;
  per-field `Args`-style description lines in the class docstrings kept to the contract nuance)
- [x] **Interface verification**: `.venv/bin/python -m pytest tests/web/test_config.py -v` — all
  contract tests pass
- [x] **Logic tests** (extend `tests/web/test_config.py`; design scenarios, verbatim):
  - `test_browser_settings_defaults_mirror_prettyplay` — `BrowserSettings().model_dump()` vs
    `BrowserConfig().model_dump()` equal dicts (`{"name": "chromium", "headless": True,
    "screen": "", "endpoint": "", "accept_dialogs": False, "speed": 100, "timeout": 30.0}`)
  - `test_web_config_defaults_mirror_prettyplay` — per-field
    `WebConfig.model_fields[name].default` vs `PrettyConfig.model_fields[name].default` for the
    19 shared names (browser via dump; `polling_timeout` both `None`)
  - `test_validate_web_config_accepts_surveyed_minimum` — input `{"provider": "anthropic",
    "generation_model": "glm-5.3", "classification_model": "glm-5.3", "browser": {"name":
    "chrome", "headless": False}}`; asserts `provider == "anthropic"`, `browser.name == "chrome"`,
    `browser.headless is False`, `browser.screen == ""`, `strict is False`,
    `polling_timeout is None`
  - `test_validate_web_config_rejects_non_mapping_root` — input `["not", "a", "mapping"]`;
    `pytest.raises(ValueError, match=r"web\.yml: the document must parse to a mapping")`
  - `test_validate_web_config_rejects_empty_mapping` — input `{}`; `ValueError` matching
    `"web.yml: the document is empty"`
  - `test_validate_web_config_wraps_validation_error_naming_document` — input `{"provider":
    "nope"}`; `ValueError` matching `"web.yml: invalid web config document"`; `exc.__cause__` is
    a pydantic `ValidationError`
  - `test_web_config_rejects_unknown_key` — input `{"provider": "openai", "browesr": {"name":
    "chromium"}}` (typo); `ValidationError` (`extra_forbidden`)
  - `test_web_config_keys_members_mirror_web_config_fields` (add to `tests/web/test_keys.py`) —
    `[m.value for m in WebConfigKeys if m is not WebConfigKeys.FILENAME]` equals
    `list(WebConfig.model_fields)` **in order** (19 values)
- [x] **Debugging**: `.venv/bin/python -m pytest tests/web/ -x` — fix implementation code until
  all tests pass (do NOT fix test code)
- [x] **Contract re-verification**: field names/order/defaults match the CODEMANIFEST signatures
  1:1; `extra="forbid"` present; no value validators added; the three error texts exact
- [x] **Lint** (M3.3): `.venv/bin/ruff check goga_tool_pybuggy/web/ tests/web/` — 0 errors;
  `ruff format --check` on touched files

### Task 4: `build_pretty_config` in `web/pretty.py` (TDD)

Implements the single construction point of the prettyplay settings layer. Contract
(`build_pretty_config(config: WebConfig, strict_flag: bool, interactive_flag: bool) -> pretty:
PrettyConfig`, location `pretty.py`). Design trace (verbatim):

1. `fields = config.model_dump()` — exactly the 19 `WebConfig` field names (1:1 with
   `PrettyConfig`; `model_dump()` returns every field, set and unset alike).
2. `browser = BrowserConfig(**fields.pop("browser"))` — the nested group maps 1:1
   (`BrowserSettings` ↔ `BrowserConfig`: name/headless/screen/endpoint/accept_dialogs/speed/
   timeout, defaults identical); semantic validation (browser matrix, ws/wss endpoint, speed
   range) happens here in the library.
3. Overwrite the modes in `fields` — `fields["strict"] = config.strict or strict_flag`,
   `fields["interactive"] = config.interactive or interactive_flag` (overwrite in the dict, never
   duplicate kwargs: `model_dump()` already carries both keys, and
   `PrettyConfig(strict=…, **fields)` raises `TypeError: got multiple values for keyword argument
   'strict'` — verified empirically on pydantic 2.14) — then `PrettyConfig(browser=browser,
   **fields)`; OR-semantics (a flag forces on, never off); `polling_timeout=None` passes through
   (library default).
4. Output: the explicit settings layer; no I/O, no env reads (purity — env handling belongs to
   configure's scrub and prettyplay's merge).

Design edge cases (verbatim): empty strings pass through and fall to the library's file layer
per-field (env scrubbed; `[tool.prettyplay]` may fill them — documented). **The all-fields
construction is load-bearing**: passing every field as a constructor kwarg puts each into
`model_fields_set`, which is what makes an explicit `strict: false`/`generation_attempts` win
over the scrubbed env layer and lets the root override of `WebPlugin.web` participate in the
per-field merge — do not reduce the call to set-fields-only. Errors: pydantic `ValidationError`
from `PrettyConfig`/`BrowserConfig` construction (semantic violations) — propagates to the
fixture; the consumer sees prettyplay's actionable per-setting text. Type hints `-> PrettyConfig`;
imports `from prettyplay import BrowserConfig, PrettyConfig`.

**Usages relevant to this task:**
- `prettyplay`: the `PrettyConfig`/`BrowserConfig` field contract; per-field merge semantics.
- `conventions`: type hints, Google docstrings, relative imports (`from .config import WebConfig`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (create `tests/web/test_pretty.py`; expected to fail):
  `from goga_tool_pybuggy.web.pretty import build_pretty_config`; callable with
  `(WebConfig, bool, bool)` returning a `PrettyConfig` instance
- [ ] **Code**: create `goga_tool_pybuggy/web/pretty.py` — module docstring, the traced algorithm
  (dump → pop browser → `BrowserConfig(**…)` → overwrite modes in the dict →
  `PrettyConfig(browser=browser, **fields)`), Google docstring (`Args`/`Returns`/`Raises`), pure
  (no env/pyproject reads anywhere in the module)
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/web/test_pretty.py -v` — pass
- [ ] **Logic tests** (design scenarios, verbatim):
  - `test_build_pretty_config_maps_every_field` — setup `WebConfig(provider="anthropic",
    base_url="https://api.example", generation_model="g", classification_model="c",
    generation_attempts=7, probe_timeout=3.0, cache_root="/tmp/x",
    browser=BrowserSettings(name="firefox", speed=50))`; `build_pretty_config(config, False,
    False)`; asserts every listed field equal on the result, `result.browser.speed == 50`,
    `result.polling_timeout is None`, `result.generation_approve is True` (untouched default)
  - `test_build_pretty_config_or_semantics_forces_on_never_off` — parametrize
    `(config.strict, strict_flag, expected)` over `[(False, False, False), (False, True, True),
    (True, False, True), (True, True, True)]`; same table for interactive; asserts
    `build_pretty_config(cfg, strict_flag, False).strict == expected`
  - `test_build_pretty_config_propagates_semantic_validation_error` — setup
    `WebConfig(browser=BrowserSettings(name="safari"))`; `build_pretty_config(config, False,
    False)` raises `pytest.raises(ValidationError)` with `browser.name` in the error text; in the
    same test, `validate_web_config({"provider": "openai", "browser": {"name": "safari"}})`
    succeeds — the layering: structure passes at configphase, semantics surface at the builder
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/web/ -x` — fix implementation code until
  all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: signature `(config, strict_flag, interactive_flag) -> PrettyConfig`;
  purity holds (no `os.environ`/`Path` reads); modes overwritten in the dict (no duplicate
  kwargs — the load-bearing all-kwargs construction preserved)
- [ ] **Lint** (M3.3): `.venv/bin/ruff check goga_tool_pybuggy/web/ tests/web/` — 0 errors;
  `ruff format --check` on touched files

### Task 5: `EventLogFormatter` + `install_event_log_formatter` in `web/logging_setup.py` (TDD)

Implements the console formatter of the prettyplay log events. Contract locations:
`EventLogFormatter(fmt: str, datefmt: str)` (a `logging.Formatter` subclass) and
`install_event_log_formatter()`, both in `logging_setup.py`. Design trace (verbatim):

1. `message = super().format(record)`; `event = getattr(record, "event", None)`.
2. `event ∈ {step_results_declared, step_inputs, step_candidate_code, step_cached_code,
   step_captured}` → return the message as is (it already renders the execution context).
3. Otherwise extras = `record.__dict__` minus the reserved `LogRecord` fields
   (`frozenset(LogRecord(...).__dict__) | {"message", "asctime"}`) and `_`-prefixed keys; empty →
   the message; else `" ".join(f"{k}={v!r}" …)` sorted, appended as `f"{message} | {payload}"`.
4. Installer: `logging.getLogger("prettyplay")` at INFO; a `StreamHandler(sys.stdout)` with
   `EventLogFormatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")`; idempotent — skip
   when any existing handler of that logger already carries an `EventLogFormatter`.

Module constants: `_RESERVED_RECORD_FIELDS`, `_HUMAN_READABLE_EVENTS` (the five events),
`_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"`, `_DATEFMT = "%H:%M:%S"`. The constructor
takes `(fmt: str, datefmt: str)`; the installer passes the constants. Pure rendering; the
installer touches only the `prettyplay` logger. Edge cases: a record with no extras renders the
plain message; unknown events still render with their extras (nothing is hidden).

**Usages relevant to this task:**
- `conventions`: the logging rules (logger acquisition, structured extras, no I/O assumptions);
  Google docstrings.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (create `tests/web/test_logging_setup.py`; expected to fail):
  `from goga_tool_pybuggy.web.logging_setup import EventLogFormatter, install_event_log_formatter`;
  `EventLogFormatter` is a `logging.Formatter` subclass constructible with `(fmt, datefmt)`;
  `install_event_log_formatter` is a module-level callable
- [ ] **Code**: create `goga_tool_pybuggy/web/logging_setup.py` — module docstring, the four
  module constants, the formatter per the trace, the idempotent installer per the trace, Google
  docstrings
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/web/test_logging_setup.py -v`
  — pass
- [ ] **Logic tests** (design scenarios, verbatim):
  - `test_install_event_log_formatter_idempotent` — clear the `prettyplay` logger handlers first
    (test isolation); call `install_event_log_formatter()` twice; asserts exactly one handler
    afterwards, a `StreamHandler` on `sys.stdout` carrying an `EventLogFormatter`, logger level
    INFO
  - `test_event_log_formatter_human_readable_events_render_plain` — formatter
    `EventLogFormatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")`; input
    `logging.LogRecord("prettyplay", 20, "p", 1, "step cached", (), None)` with
    `record.event = "step_cached_code"` and an extra `{"step": "open"}`; asserts the output
    contains `"step cached"` and **not** `"step="`
  - `test_event_log_formatter_appends_sorted_extras` — input a record with `event="llm_request"`
    and extras `{"b": 2, "a": 1}`; asserts output matches `… | a=1 b=2` (sorted, `!r` rendering);
    reserved fields (`levelname`, `message`, `asctime`) never appear; `_private` keys excluded
  - `test_event_log_formatter_record_without_event` (edge) — input a record with no `event`
    attribute and extras; asserts extras appended (`getattr(record, "event", None)` — no
    `AttributeError`)
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/web/ -x` — fix implementation code until
  all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: the five human-readable event names exact; the installer
  touches only the `prettyplay` logger; idempotency guard present
- [ ] **Lint** (M3.3): `.venv/bin/ruff check goga_tool_pybuggy/web/ tests/web/` — 0 errors;
  `ruff format --check` on touched files

### Task 6: `AllureStepHooks` in `web/allure_hooks.py` (TDD)

Implements the Allure reporting integration over the prettyplay hook contract. Contract
(`AllureStepHooks(play: PrettyPlay)`, location `allure_hooks.py`): 5 methods —
`on_group_started(group_prompt)`, `on_group_finished(group_prompt)`,
`on_step_started(step_text, step_type)`, `on_step_failed(step_text, step_type, error)`,
`on_step_finished(step_text, step_type, outcome)`. Design (verbatim):

- Module-level guarded import: `try: import allure / except ImportError: allure = None`;
  `from playwright.sync_api import Error as PlaywrightError` — the only direct playwright import —
  plus `PrettyplayError` from `prettyplay.failures` (a public library module path; the cell's
  playwright-import constraint limits only playwright imports).
- Two `ExitStack`s (`_step_stack`, `_group_stack`) + the current step wrapper — enter/exit pairs
  stay balanced when a step fails mid-group.
- `on_step_failed`: `wrapper.fail(error, cls=AssertionError if step_type == "assertion" else
  Exception)`; screenshot attach inside `try: allure.attach(play.get_screenshot(),
  name="screenshot.png", attachment_type=allure.attachment_type.PNG) except (PlaywrightError,
  PrettyplayError): pass` — the no-page case raises the library's `PrettyplayError`, a capture
  failure a `PlaywrightError`.
- Constructed only from the fixture guard (`allure is not None`).
- Private `_AllureStepWrapper` (enter/fail/exit — exits as broken with the accumulated failure)
  exactly in the shape of `prettyplay_example/conftest.py` (with the widened capture guard).
- Hook params the body does not use carry `# noqa: ARG002` (the hook contract fixes the
  signatures).
- Errors: none raised — failures are recorded on the Allure step context. Edge cases:
  `get_screenshot()` raising `PrettyplayError` (no page) or `PlaywrightError` (capture failure) —
  both swallowed, the failure itself already recorded; step failing mid-group — the two stacks
  keep the enter/exit pairs balanced.

**Usages relevant to this task:**
- `allure-pytest`: the guarded-import pattern; the StepHooks→Allure mapping table; the
  `allure.attach(..., name="screenshot.png", attachment_type=allure.attachment_type.PNG)` form;
  stack discipline.
- `prettyplay`: the `StepHooks` event signatures (`from prettyplay import StepHooks`) and the
  screenshot source.
- `conventions`: Google docstrings; `# noqa: ARG002` on fixed-signature unused params.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (create `tests/web/test_allure_hooks.py`; expected to fail):
  `from goga_tool_pybuggy.web.allure_hooks import AllureStepHooks`; the module exposes an `allure`
  attribute (guarded import; `None` when absent — real allure present in the test env);
  `AllureStepHooks` is a `StepHooks` subclass; the five hook methods exist with the contract
  signatures
- [ ] **Code**: create `goga_tool_pybuggy/web/allure_hooks.py` — module docstring, guarded
  imports, the private `_AllureStepWrapper`, the two stacks, the five hook methods per the design,
  `# noqa: ARG002` where needed, Google docstrings
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/web/test_allure_hooks.py -v`
  — pass
- [ ] **Logic tests** (design scenarios, verbatim):
  - `test_allure_step_hooks_failed_step_attaches_screenshot` — real `allure` (test extra); `play`
    double with `get_screenshot() -> b"PNG"`; `monkeypatch.setattr(allure, "attach")` recording
    calls; `hooks = AllureStepHooks(play)`; trace `on_step_started("Find results", "assertion")`
    → `on_step_failed("Find results", "assertion", "not found")` → `on_step_finished(…)`;
    asserts `allure.attach` called with `b"PNG"`, `name="screenshot.png"`,
    `attachment_type=allure.attachment_type.PNG`; the step context exits broken (the wrapper's
    recorded exception class is `AssertionError` for `"assertion"`, `Exception` for `"action"`)
  - `test_allure_step_hooks_swallows_playwright_error` — `play.get_screenshot` raises
    `PlaywrightError("no page")` (real import — the playwright package is installed, browsers are
    not needed); a second case raises the library's own
    `PrettyplayError("no test page yet: run a step first")`; asserts no exception escapes
    `on_step_failed` in either case; the step still exits broken
  - `test_allure_step_hooks_stacks_balance_mid_group` — trace `on_group_started("g")` →
    `on_step_started` → `on_step_failed` → `on_step_finished` → `on_group_finished("g")`;
    asserts both stacks empty afterwards; a second group/step cycle after the failure works
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/web/ -x` — fix implementation code until
  all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: five method signatures match the CODEMANIFEST; the catch is
  `(PlaywrightError, PrettyplayError)`; the only playwright import is
  `playwright.sync_api.Error`; no exception raised out of the hooks
- [ ] **Lint** (M3.3): `.venv/bin/ruff check goga_tool_pybuggy/web/ tests/web/` — 0 errors;
  `ruff format --check` on touched files

### Task 7: `WebPlugin` + `web_cache_path` in `web/plugin.py` (TDD)

Implements the pluginator plugin of the web test kind — the heaviest entity of the cell. Contract
locations: both entities in `plugin.py`. Design algorithm (verbatim):

```
@define.plugin("pybuggy-web", config=CONFIG_FILE)
class WebPlugin:
    plugin_config: dict                       # anchor declaration (BasePlugin supplies the dict)
    strict = define.option(bool, plugin_config_key=WebConfigKeys.STRICT,
                           command_line=CommandLine("--strict-mode", action="store_true",
                           help="Strict mode for using cache only"))
    interactive = define.option(bool, plugin_config_key=WebConfigKeys.INTERACTIVE,
                           command_line=CommandLine("--interactive", action="store_true",
                           help="Interactive step healing mode"))
    __init__(): super().__init__(); self.activation: WebConfig | None = None
    configure(): CLI authority → validate → scrub env → formatter   (contract order)
    web(self, request): the fixture trace below
    _require_activation(): RuntimeError guard (sandbox pattern)
```

Option resolution without a typed flag: `plugin_config_key` (web.yml) → `command_line`
(`getoption`, False when untyped) → `bool()` False. The explicit-false-in-file + typed-flag case
is exactly what `configure`'s authority step corrects. Module helpers: `_scrub_prettyplay_env()`
(pop `PRETTYPLAY_*`, INFO with sorted names / DEBUG when none) and `web_cache_path(item)` (pure).

**Trace: `WebPlugin.configure()` (verbatim)**
1. Input: pluginator lifecycle call, no arguments, after `init_pytest_config` —
   `self.pytest_config` is readable.
2. CLI authority: `self.pytest_config.getoption("strict_mode", default=False)` /
   `…("interactive", default=False)` (dest derived from `--strict-mode` / `--interactive`;
   `store_true` ⇒ True only when typed) → assign True onto the option.
3. Read the document under a parse guard — `try: document = self.plugin_config` /
   `except YAMLError as exc: raise ValueError(f"{CONFIG_FILE}: unparsable document: {exc}")` (the
   sandbox-plugin pattern) — then `self.activation = validate_web_config(dict(document))`; an
   unparsable or structurally invalid document raises `ValueError` naming
   `.goga/tools/pybuggy/web.yml` → pytest configphase fails.
4. Env scrub: remove every `os.environ` key starting with `PRETTYPLAY_`; one INFO log with the
   sorted names (DEBUG when none) — permanent for the run and race-free (configphase is
   single-threaded).
5. `install_event_log_formatter()` — unconditional (not allure-gated).
6. Output: activation set, options resolved, env neutralized, console formatter active.

**Trace: `WebPlugin.web(request)` (verbatim)**
1. Input: `pytest.FixtureRequest` of the requesting test; `self.activation` from configure.
2. `activation = self._require_activation()` — `RuntimeError` when configure never ran
   (defensive; pluginator always configures installed plugins).
3. Address: `item = request.node`; root = `activation.cache_root` when non-empty, otherwise
   `str(item.path.parent.resolve())` — `StepCache` roots at `Path(config.cache_root)`; an empty
   root would mean the cwd, which the contract forbids.
4. `config = build_pretty_config(activation, self.strict, self.interactive)`; when
   `activation.cache_root` is empty, `config = config.model_copy(update={"cache_root": root})` —
   the root participates in prettyplay's per-field merge because `build_pretty_config` passes
   **every** field as a constructor kwarg, so `cache_root` is in `model_fields_set` from
   construction (`model_copy(update=…)` itself does not add keys to `model_fields_set`); the
   copied non-empty value then participates and wins over the library's `cwd/.prettyplay/cache`
   default.
5. `runtime = PrettyPlay(item.name, web_cache_path(item), cleanup=False, config=config)` —
   signature `PrettyPlay(cache_key, cache_path=None, *, cleanup=True, hooks=None, config=None)`;
   `cleanup=False` keeps every cached file of the key (persistence mode).
6. Allure: `if allure_hooks.allure is not None: runtime.add_hooks(AllureStepHooks(runtime))`
   (guarded-import cook: feature detection by module object).
7. `with runtime as play: yield play` — close on finalization.
8. Output: the per-test runtime (`step` / `expect` / `group` / `run_on_page`).

**Trace: `web_cache_path(item)` (verbatim)**
1. `item.path.stem` — the module stem (pytest≥7 `Item.path`; never the cwd).
2. `original = getattr(item, "originalname", None) or item.name` — parametrize-agnostic.
3. `cls = getattr(item, "cls", None)` — insert `cls.__name__` when present (class-aware).
4. `"/".join(segments)` → output: posix-relative `<module_stem>/[<Class>/]<original_name>`;
   pure, no filesystem access.

Errors: `ValueError` from `validate_web_config` at configphase (clean, names the document);
`RuntimeError` from `_require_activation` (defensive, never in practice). Edge cases: running
from outside the project root — paths derive from `item.path` (`resolve()`), never the cwd;
parametrized tests share the cache directory (`originalname`) but keep per-case keys
(`item.name`); `--strict-mode` makes zero LLM calls (library contract: strict = replay-only, a
cache miss fails).

**Usages relevant to this task:**
- `pluginator`: `@define.plugin` bound to the config file; `define.option` chain with
  `plugin_config_key` + `CommandLine(…, action="store_true")`; fixtures as plugin-class methods
  (`@pytest.fixture` generator method); `configure()` lifecycle; the `--base-url` CLI-authority
  assignment pattern.
- `prettyplay`: runtime construction (`cache_key`/`cache_path`/`cleanup`/`config`) and the cache
  addressing contract.
- `allure-pytest`: the guarded activation of the reporting hooks.
- `conventions`: docstrings, type hints, relative imports (`from .allure_hooks import
  AllureStepHooks`, `from .config import WebConfig, validate_web_config`, `from .keys import
  CONFIG_FILE, WebConfigKeys`, `from .logging_setup import install_event_log_formatter`,
  `from .pretty import build_pretty_config`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (create `tests/web/test_plugin.py`; expected to fail):
  `from goga_tool_pybuggy.web.plugin import WebPlugin, web_cache_path`; `WebPlugin()` constructs
  with zero arguments; the plugin is registered as `pybuggy-web` bound to `CONFIG_FILE` (assert
  via the pluginator metadata the same way the sandbox tests do); options `strict`/`interactive`
  exist; a `web` fixture method exists; `web_cache_path` is a module-level callable
- [ ] **Code**: create `goga_tool_pybuggy/web/plugin.py` — the design block verbatim: the
  decorator, the `plugin_config` anchor, the two options, `__init__` (`super().__init__()`;
  `self.activation: WebConfig | None = None`), `configure()` in the contract order, the `web`
  fixture generator per the trace, `_require_activation()`, the module helpers
  (`_scrub_prettyplay_env`, `web_cache_path`); `PrettyPlay` imported at module top (monkeypatched
  in tests); Google docstrings; logging per M1.5 (INFO `web plugin enabled` lives in the plugin
  cell; here INFO `prettyplay env layer scrubbed` with the sorted names, DEBUG when none)
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/web/test_plugin.py -v` — pass
- [ ] **Logic tests** (design scenarios, verbatim; doubles per the sandbox-plugin test pattern —
  `_FakePytestConfig` needs `getoption(name, default=…)` + `addinivalue_line`, `SimpleNamespace`
  items, a recording `PrettyPlay` double, `monkeypatch.setattr(type(plugin), "plugin_config",
  document, raising=False)` + `plugin.init_pytest_config(fake)` + `plugin.configure()` for
  configure tests):
  - `test_web_cache_path_shapes` — items: plain `SimpleNamespace(path=Path("/proj/tests/
    test_search.py"), name="test_duckduckgo_search", originalname="test_duckduckgo_search")`;
    class item adds `cls=TestLogin` (a real class); parametrized item `name="test_foo[x-1]"`,
    `originalname="test_foo"`; asserts `"test_search/test_duckduckgo_search"`,
    `"test_login/TestLogin/test_foo"`, `"test_mod/test_foo"`
  - `test_web_cache_path_originalname_missing_falls_back_to_name` — item without `originalname`;
    asserts the path ends with `item.name`
  - `test_configure_validates_document_and_scrubs_env` — setup per the doubles note; document
    `{"provider": "openai", "generation_model": "g", "classification_model": "c", "browser":
    {"name": "chromium", "headless": True}}`; `monkeypatch.setenv("PRETTYPLAY_STRICT", "true")`,
    `("PRETTYPLAY_BROWSER_SPEED", "10")`; asserts `plugin.activation.provider == "openai"`,
    `"PRETTYPLAY_STRICT" not in os.environ`, `"PRETTYPLAY_BROWSER_SPEED" not in os.environ`, an
    unrelated var survives
  - `test_configure_applies_cli_authority` — `_FakePytestConfig` returning `True` for
    `getoption("strict_mode")`; the document carries `strict: False`; asserts after `configure()`
    `plugin.strict is True` (the typed flag beat the explicit file false); with no flag,
    `plugin.strict is False`
  - `test_configure_fails_configphase_on_invalid_document` (negative) — plugin with
    `plugin_config = {"provider": "nope"}`; `init_pytest_config` → `configure()`; asserts
    `ValueError` naming the document; `plugin.activation is None`
  - `test_configure_fails_configphase_on_unparsable_document` (negative) — a `_RefusingPlugin`
    subclass of `WebPlugin` whose `plugin_config` property raises `YAMLError("bad indentation")`
    (the sandbox-test pattern); asserts `pytest.raises(ValueError, match=r"web\.yml: unparsable
    document.*bad indentation")`; `exc.__cause__` is the original `YAMLError`;
    `plugin.activation is None`
  - `test_web_fixture_builds_address_and_cleanup` — configured plugin (activation with
    `cache_root: ""`, strict False); recording `PrettyPlay` double monkeypatched into
    `goga_tool_pybuggy.web.plugin.PrettyPlay`; request double whose `node` is
    `SimpleNamespace(path=Path("/proj/tests/test_a.py"), name="test_a", originalname="test_a")`;
    `allure_hooks.allure` monkeypatched to `None`; consume the fixture generator (`next(…)`) →
    exhaust; asserts the double recorded `cache_key == "test_a"`, `cache_path == "test_a/test_a"`,
    `cleanup is False`, `config.cache_root == str(Path("/proj/tests").resolve())`,
    `config.browser.name` per the activation, no `add_hooks` call (allure absent), the context
    manager closed on exhaustion
  - `test_web_fixture_honors_cache_root_key` — activation with `cache_root: "/tmp/webcache"`;
    asserts the double's `config.cache_root == "/tmp/webcache"` (no override)
  - `test_web_fixture_without_configure_raises_runtime_error` — `plugin = WebPlugin()`;
    `init_pytest_config` never called; consume `next(plugin.web(request))`; asserts
    `pytest.raises(RuntimeError, match="not configured")`; the PrettyPlay double was never
    constructed
  - `test_web_fixture_attaches_allure_hooks_when_importable` —
    `monkeypatch.setattr(goga_tool_pybuggy.web.allure_hooks, "allure", object())`; same double;
    asserts `add_hooks` called once with an `AllureStepHooks` instance
  - `test_web_fixture_resolves_outside_project_root` (edge) — item
    `path=Path("/elsewhere/tests/test_a.py")` while `monkeypatch.chdir(tmp_path)`; asserts the
    runtime double's `config.cache_root == str(Path("/elsewhere/tests").resolve())` — no
    `relative_to(cwd)` anywhere
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/web/ -x` — fix implementation code until
  all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: decorator name `pybuggy-web` + `config=CONFIG_FILE`; option
  keys map to `WebConfigKeys.STRICT`/`INTERACTIVE` with `--strict-mode`/`--interactive`
  `store_true`; configure order = CLI authority → parse-guarded read → validate → scrub →
  formatter; fixture `cleanup=False`; allure guard both directions; no cwd-derived paths
- [ ] **Lint** (M3.3): `.venv/bin/ruff check goga_tool_pybuggy/web/ tests/web/` — 0 errors;
  `ruff format --check` on touched files

### Task 8: web cell facade — `__init__.py` with the 10-name `__all__` (TDD)

Completes the web cell: the facade exposes the full contract API. Design (verbatim):

```
__all__ = ["AllureStepHooks", "BrowserSettings", "EventLogFormatter", "WebConfig",
           "WebConfigKeys", "WebPlugin", "build_pretty_config", "install_event_log_formatter",
           "validate_web_config", "web_cache_path"]
```

Classes first, then routines, alphabetical within each group (the config-cell facade pattern).
Docstring: one line naming the cell and the ten names. All six modules were implemented in Tasks
2–7; this task assembles the surface.

**Usages relevant to this task:**
- `conventions`: facade rule — only `__all__` names constitute the facade; relative imports.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (create `tests/web/test_integration.py`; expected to fail while the
  facade is the Task-1 marker): `test_facade_exports_exactly_ten_names` —
  `from goga_tool_pybuggy import web` then assert `sorted(web.__all__)` equals the sorted ten
  contract names exactly; every name importable from the facade
  (`from goga_tool_pybuggy.web import WebPlugin` as the anchor import)
- [ ] **Code**: fill `goga_tool_pybuggy/web/__init__.py` — the `__all__` block above (exact
  order), relative imports of the six modules, the one-line-plus-nuance module docstring
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/web/test_integration.py -v`
  and the facade command `.venv/bin/python -c "from goga_tool_pybuggy.web import WebPlugin"` —
  both pass
- [ ] **Logic tests**: none beyond the facade contract test (behavior lives in Tasks 2–7 tests);
  run the whole web tree: `.venv/bin/python -m pytest tests/web/ -x`
- [ ] **Debugging**: fix implementation (import wiring) until green — do NOT fix test code
- [ ] **Contract re-verification**: `__all__` == the ten names in the design order; nothing else
  exported
- [ ] **Lint** (M3.3): `.venv/bin/ruff check goga_tool_pybuggy/web/ tests/web/` — 0 errors;
  `ruff format --check` on touched files

### Task 9: `config.yml` → `api.yml` clean-break rename (TDD)

Applies the rename-only change set of the config and plugin cells. One semantic unit — every
carrier of the old file name switches together so the suite stays green: `config/storage.py`
(`_FILENAME`, the path comment, the `FileNotFoundError` message text), `config/config.py` (the
`Config` docstring path), `plugin/defaults.py` (`CONFIG_FILE` value — the `@define.plugin`
binding in `plugin/plugin.py:73` reads it), `commands/init/bootstrap.py` (the
`document_config_examples` docstring path — design: annotation names `api.yml`; logic unchanged),
and `tests/conftest.py::tool_config` (the writer switches to `api.yml`). Design trace (verbatim):

1. `_TOOL="pybuggy"`, `_FILENAME` `"config.yml"` → **`"api.yml"`**; call-time
   `from goga.config import load_tool_config` unchanged (goga stays out of runtime deps).
2. Absent/empty → `FileNotFoundError` message names `.goga/tools/pybuggy/api.yml` — an old
   `config.yml` is never read, never migrated (clean break).
3. `Config` docstring names `api.yml`.

Signatures, algorithms, the `pipelines` validation — untouched. Keep the old-name coverage via
the dedicated never-read test rather than the shared fixture.

**Usages relevant to this task:**
- `conventions`: mock policy (file I/O via `tmp_path`); expected exceptions via `pytest.raises`;
  test naming.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (in `tests/config/test_storage.py`, expected to fail before the rename):
  add `test_load_config_names_api_yml_and_never_reads_old_config` — setup: `tool_config` writer
  (after this task writes `api.yml`) absent; an **old** `config.yml` written with valid specs
  content under `.goga/tools/pybuggy/`; asserts
  `pytest.raises(FileNotFoundError, match=r"\.goga/tools/pybuggy/api\.yml")` — the old file is
  ignored entirely (clean break, no migration)
- [ ] **Code**: change `goga_tool_pybuggy/config/storage.py` — `_FILENAME = "api.yml"`, the path
  comment, the `FileNotFoundError` message text; change `goga_tool_pybuggy/config/config.py` —
  the `Config` docstring path; change `goga_tool_pybuggy/plugin/defaults.py` — `CONFIG_FILE`
  value `".goga/tools/pybuggy/api.yml"`; change `tests/conftest.py::tool_config` — the writer
  path to `api.yml` (fixture docstring updated to match); change
  `goga_tool_pybuggy/commands/init/bootstrap.py` — the `document_config_examples` docstring path
  names `api.yml` (design: annotation names `api.yml`; logic unchanged)
- [ ] **Test migration** (rename-only, not weakening): migrate the existing tests that pin the
  old tool-config name to `api.yml` — `tests/plugin/test_plugin.py` (6 writer sites),
  `tests/plugin/test_integration.py`, `tests/test_cli_integration.py` (`_write_config` helper +
  module docstring), `tests/test_cli_env.py`, `tests/commands/pull/test_pull.py`,
  `tests/commands/diff/test_diff.py` + `test_diff_integration.py`,
  `tests/commands/info/test_info.py`, `tests/commands/list/test_list.py`,
  `tests/commands/generate/test_generate.py` — every writer/reader of
  `.goga/tools/pybuggy/config.yml` switches to the `api.yml` name; no assertion semantics change
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/config/ tests/plugin/ -v` —
  the new test passes and the existing suites still pass
- [ ] **Logic tests**: none new beyond the never-read test (rename-only change; existing suites
  are the regression net after the old-name writer sites migrate to `api.yml` — rename-only test
  migration)
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/ -x` — fix implementation code until all
  tests pass (do NOT fix test code; the old-name writer sites are rename-migrated test code, not
  implementation fixes — the do-not-fix rule does not apply to them)
- [ ] **Contract re-verification**: no `.py` carrier of the old path remains in the touched
  files: `grep -rn "tools/pybuggy/config.yml" goga_tool_pybuggy/config/
  goga_tool_pybuggy/plugin/defaults.py goga_tool_pybuggy/commands/init/bootstrap.py
  tests/conftest.py` is empty (the repo-wide empty grep stays a Task 15 gate —
  `commands/init/init.py` switches its step-3 path in Task 13); signatures and algorithms
  untouched (diff review)
- [ ] **Lint** (M3.3): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — 0 errors;
  `ruff format --check` on touched files

### Task 10: plugin cell — `WEB_CONFIG_FILE` + the step-5 web gate in `install()` (TDD)

Wires the web kind into the plugin-cell installation entry. Changes: `plugin/defaults.py` gains
`WEB_CONFIG_FILE: Final[str] = ".goga/tools/pybuggy/web.yml"` (literal, mirroring
`SANDBOX_CONFIG_FILE`; an alignment test pins it to `WebConfigKeys.FILENAME`);
`plugin/__init__.py` imports `WebPlugin` from `..web`, adds the step-5 gate in `install()`, and
gains the web sentence in the `install()` docstring. `__all__` stays at its four names —
`WebPlugin` is a web-cell contract type, and re-exporting it in the plugin `__all__` would create
a second declaration point of the contract surface (`SandboxPlugin` is in `__all__` because it
*is* a plugin-cell type). The import alone makes `goga_tool_pybuggy.plugin.WebPlugin` addressable,
which is all the gate and the tests need.

**Trace: `goga_tool_pybuggy.plugin.install()` — new step 5 (verbatim)**
4. **New step 5**: `Path(defaults.WEB_CONFIG_FILE).is_file()` → append `WebPlugin()` (zero args),
   INFO `web plugin enabled`; else DEBUG `web plugin absent`. No validation here — the document
   is only checked for presence. (Step 4 sandbox gate unchanged; step 6
   `install_pytest_plugins(*plugins, context=…)` unchanged — the wrapper iterates every plugin;
   two plugins with `--strict-mode` / `--base-url` dests do not collide.)

**Usages relevant to this task:**
- `pluginator`: `install_pytest_plugins` iteration semantics; gate-driven construction.
- `conventions`: logging levels (INFO enabled / DEBUG absent); mock policy (`mock.patch` at the
  import point for `WebPlugin`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (in `tests/plugin/test_install.py`, expected to fail before the gate):
  import `goga_tool_pybuggy.plugin.WebPlugin` is addressable (the plain import);
  `test_install_gates_web_plugin_on_document_presence` — setup `monkeypatch.chdir(tmp_path)`;
  namespace double; `mock.patch("goga_tool_pybuggy.plugin.WebPlugin")` — case A: write a minimal
  `web.yml` under `.goga/tools/pybuggy/`; case B: none; asserts A —
  `WebPlugin.assert_called_once_with()`, B — `WebPlugin.assert_not_called()`; both cases leave
  the api/sandbox gating intact (SandboxPlugin mock called only with its own document)
- [ ] **Code**: `plugin/defaults.py` — add `WEB_CONFIG_FILE` (after `SANDBOX_CONFIG_FILE`,
  same literal style); `plugin/__init__.py` — `from ..web import WebPlugin` (absolute-in-package
  forbidden — relative only), the step-5 gate between the sandbox gate and
  `install_pytest_plugins` (INFO `web plugin enabled` / DEBUG `web plugin absent`, structured
  `extra={"document": …}` per the sandbox lines), the `install()` docstring gains the web
  sentence; `__all__` unchanged
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/plugin/ -v` — pass
- [ ] **Logic tests** (design scenarios, verbatim):
  - `test_install_web_gate_performs_no_validation` — setup an **invalid** `web.yml` (e.g.
    `provider: nope`); asserts the gate still constructs `WebPlugin` (the mock is called) —
    validation belongs to configure
  - `test_web_config_keys_filename_names_the_document` (extend `tests/web/test_keys.py`) — add
    the cross-cell assertion `plugin_defaults.WEB_CONFIG_FILE == CONFIG_FILE` (import
    `from goga_tool_pybuggy.plugin import defaults as plugin_defaults`) — the installation gate
    and the `@define.plugin` binding read different constants; this test is the only guard that
    they name the same document
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/ -x` — fix implementation code until all
  tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: gate is presence-only (no validation call), zero-argument
  construction, contract step order (4 sandbox → 5 web → 6 install), `__all__` still four names
- [ ] **Lint** (M3.3): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — 0 errors;
  `ruff format --check` on touched files

### Task 11: `commands/init/session.py` — kind-aware questions, surveys, payload builders (TDD)

Implements the kind-aware onboarding session surface in `session.py`: new routines
`survey_api_options`, `survey_specs` (absorbs the deleted `survey_extra_specs`),
`survey_web_config`, `build_web_config_data`; changed `pybuggy_questions` (exactly
`kind`/`base_image`/`image`), `build_config_data` (signature `(answers, specs, autonomous)`;
`specs` is the surveyed list), `amend_pybuggy_config` (kind-gated branches; buffers `api.yml`
and/or `web.yml`); `survey_autonomy` is called only for api/both kinds (inside the branch).
New import: `from ...web import WebConfigKeys`. The module constants
(`_SCALAR_PROMPTS`, `_NUMERIC_MEMBERS`, `_SPEC_TYPES`, `_AUTONOMY_AXES`, `_BASE_IMAGE_NAMES`,
`_DOCKERFILE_PATH`) all stay — reused by the new surveys/builders.

**Traces (verbatim):**

`pybuggy_questions()` — 1. `kind` record first: `Question(id="kind", kind="choice", prompt="Test
kind (api — API tests over specs, web — browser UI tests, both)", choices=["api", "web", "both"],
default="api")`. 2. `base_image` / `image` records — byte-identical to today (hints from
`_BASE_IMAGE_NAMES` + the runtime minor tag; `{project}:latest` default; `None` default ⇒
engine-required when not derivable). 3. Output: exactly three records; no base_url, no scalar
keys, no spec group, no web records.

`amend_pybuggy_config(context)` — 1. Gate on `context.invited`; `answers = context.answers`.
2. `kind = str(answers.get("kind") or "api")` — the block always carries the answer; the `or`
default is defensive. 3. `kind in ("api", "both")`: `api_answers = survey_api_options()`;
`specs = survey_specs()`; `autonomous = survey_autonomy()` — in that order (specs before
autonomy). 4. `kind in ("web", "both")`: `web_answers = survey_web_config()`. 5. Amendments
(unconditional): `context.answer(id, value)` for every `build_config_amendments(answers)` entry.
6. `kind in ("api", "both")`: `context.write_config("api.yml", build_config_data({**answers,
**api_answers}, specs, autonomous))` — the renamed file. 7. `kind in ("web", "both")`:
`context.write_config("web.yml", build_web_config_data(web_answers))`. 8. Output: the buffered
contribution; any exception (incl. `click.Abort`) propagates → the mediator drops the whole
contribution with a warning; the session continues.

`build_web_config_data(web_answers)` — 1. Payload in insertion order (the engine's `yaml.dump`
preserves it; the documenter walks it): `provider`, `generation_model`, `classification_model`
(from the survey), `browser: {"name": browser_name, "headless": headless}`, `strict: False`,
`interactive: False`. 2. Keys spelled via `WebConfigKeys` members (`.value`) — data-driven, no
duplicated literals. 3. Output: plain serializable dict; every key a `WebConfigKeys` member.

Survey specs (design, verbatim):
- `survey_api_options()` — `_required("Base URL (Jinja2 template, required)")`, then the scalar
  walk over `PluginConfigKeys` minus BASE_URL/HEADERS/LOADER with `_SCALAR_PROMPTS` and
  `click.prompt(…, default="", show_default=False)`; unanswered keys dropped from the returned
  dict; `click.Abort` propagates.
- `survey_specs()` — the first spec field-by-field (`"Spec name"`, `click.Choice(_SPEC_TYPES)`
  `"Spec type"`, `_required("Spec location (path from project root)")`, the three optional git
  prompts), then the `"Add another spec?"` confirm loop (default no); returns the mappings list,
  the first spec first. Absorbs `survey_extra_specs` (deleted).
- `survey_web_config()` — provider (`click.Choice(("openai", "anthropic"))`, default `"openai"`),
  `_required("Generation model (step-code generation)")`,
  `_required("Classification model (step classification)")`, browser name (default `"chromium"`),
  `click.confirm("Run the browser headless?", default=True)`; returns the five-key dict.
- `build_config_data(answers, specs, autonomous)` — `parse_specs(specs[0], specs[1:] or None)`;
  the scalar walk, numeric coercion, autonomy axes, and `specs` ordering unchanged.

**Usages relevant to this task:**
- `conventions`: CLI testing by direct handler call; mocks at external boundaries only
  (`_ScriptedClick` for click prompts, `ContributionRecorder` for the context, monkeypatched
  surveys for branch tests — the surveys themselves are real against scripted prompts); never
  catch `click.Abort`.
- `pybuggy-web` (imported usage): the init survey's Use-line references it for the consumer
  meaning of the surveyed fields.
- `conventions` pydantic/naming rules for the `WebConfigKeys`-driven keys.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (in `tests/commands/init/test_session.py`, expected to fail):
  `from goga_tool_pybuggy.commands.init import (amend_pybuggy_config, build_config_data,
  build_web_config_data, pybuggy_questions, survey_api_options, survey_specs,
  survey_web_config)` — all importable; `survey_extra_specs` no longer exported (checked fully in
  Task 13's facade test; here assert the module attribute is gone); `pybuggy_questions()` returns
  records; `build_config_data` accepts `(answers, specs, autonomous)`
- [ ] **Code**: rewrite the touched routines in `goga_tool_pybuggy/commands/init/session.py` per
  the traces; delete `survey_extra_specs`; add the `from ...web import WebConfigKeys` import;
  keep every reused module constant; Google docstrings; `Raises:` for the propagating Abort
  behavior documented on `amend_pybuggy_config`
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/commands/init/test_session.py
  -v` — the new contract tests pass
- [ ] **Logic tests** (design scenarios, verbatim):
  - `test_pybuggy_questions_declares_kind_base_image_image` — monkeypatched version helpers
    (existing `pinned_version_axis`-style fixtures); asserts exactly 3 records, ids
    `["kind", "base_image", "image"]`; `kind` is `kind="choice"`, `choices == ["api", "web",
    "both"]`, `default == "api"`; no record carries a plugin scalar id, `base_url`, or a spec
    group
  - `test_survey_api_options_asks_base_url_then_scalars` — scripted clicks (`_ScriptedClick`):
    base_url `"https://api.example"`, timeout `"5"`, Enter for the rest; asserts returns
    `{"base_url": "https://api.example", "timeout": "5"}`; prompt order base_url first;
    unanswered keys dropped
  - `test_survey_specs_first_spec_then_confirm_gate` — scripted: name/location/type/git fields,
    then decline; asserts one mapping, `{"name": "client", "type": "swagger", "location":
    ".specs/client.yaml", "git_url": "", "git_location": "", "git_ref": ""}`; decline adds nothing
  - `test_survey_web_config_asks_minimum_in_order` — scripted: provider default, models, browser
    default, headless yes; asserts `{"provider": "openai", "generation_model": "g",
    "classification_model": "c", "browser_name": "chromium", "headless": True}`; exactly five
    prompts in contract order
  - `test_build_web_config_data_payload_shape` — input the survey dict above; asserts
    `data == {"provider": "openai", "generation_model": "g", "classification_model": "c",
    "browser": {"name": "chromium", "headless": True}, "strict": False, "interactive": False}` —
    exact key order too (`list(data) == [...]`); every key a `WebConfigKeys` member value
  - `test_amend_pybuggy_config_kind_branches` (parametrized api / web / both) — `ContributionRecorder`
    with `answers={"kind": kind, "base_image": "img", "image": "p:latest"}`; surveys monkeypatched
    to sentinel returns; asserts api — `survey_api_options`, `survey_specs`, `survey_autonomy`
    called (in order), `survey_web_config` not; files == `[("api.yml", …)]`; web — only
    `survey_web_config`; files == `[("web.yml", …)]`; both — all four surveys, api before web;
    files == `[("api.yml", …), ("web.yml", …)]`; amendments always buffered
  - `test_amend_pybuggy_config_kind_missing_defaults_to_api` — answers without `kind`; asserts
    the api branch ran
  - `test_amend_cancelled_prompt_drops_contribution` (negative) — a survey monkeypatched to
    raise `click.Abort`; asserts the exception propagates out of `amend_pybuggy_config`
  - `test_build_config_data_takes_surveyed_specs_list` (edge) — input `answers={"timeout": "5"}`,
    `specs=[{"name": "a", "type": "swagger", "location": "x"}, {"name": "b", "type": "openapi",
    "location": "y"}]`, `autonomous={"api.automate": True}`; asserts `data["specs"]` holds both
    entries (first first), `data["timeout"] == 5.0`,
    `data["pipelines"] == {"api.automate": {"autonomous": True}}`
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/commands/init/ -x` — fix implementation
  code until all tests pass (do NOT fix test code); any existing test that still calls
  `survey_extra_specs` or expects the `("config.yml", …)` write_config tuple is updated to the
  new `survey_specs` flow and the `api.yml` name — `test_amend_pybuggy_config_buffers_surveyed_contribution`
  included (test migration, not weakening)
- [ ] **Contract re-verification**: the exact prompt texts and the `kind` question record match
  the design strings; `amend_pybuggy_config` never catches exceptions; `build_web_config_data`
  keys via `WebConfigKeys` only
- [ ] **Lint** (M3.3): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — 0 errors;
  `ruff format --check` on touched files

### Task 12: `commands/init/bootstrap.py` — `document_web_config_examples` + `install_playwright` (TDD)

Implements the two new bootstrap writers in `bootstrap.py` (new import
`from ...web import WebConfigKeys`).

**Trace: `document_web_config_examples(config_path)` (verbatim)**
1. Absent file / non-`CommentedMap` root → `[]`.
2. Walk `WebConfigKeys` in declaration order, skipping `FILENAME`; a member absent as an active
   key whose record marker (`record.split("\n", 1)[0]`) is not already in the file text
   accumulates its example record.
3. Flush pending records (joined by newline) via
   `data.yaml_set_comment_before_after_key(member.value, before=…)` before the next active key;
   `browser` (last in declaration order) is the terminal anchor; pending records remaining when
   `browser` is absent are dropped silently (approved sub-decision — mirrors
   `document_config_examples` dropping pending records when `specs` is absent).
4. Write back only when at least one record was added; active keys never modified.

Example-record texts (module constants, verbatim):
- scalars: `f"{member.value}: (skipped optional scalar)"`
- `GENERATION_PROMPT`: `"generation_prompt: |\n  extra instructions appended to the generation
  prompt (skipped optional scalar)"`
- `CLASSIFICATION_PROMPT`: `"classification_prompt: |\n  extra instructions appended to the
  classification prompt (skipped optional scalar)"`
- `CACHE_ROOT`: `"cache_root: (path example — the step cache root, e.g. tests/.web_cache)"`
- `BROWSER`: `"browser:\n  name: chromium\n  screen: ''\n  headless: true\n  endpoint: ''\n
  accept_dialogs: false\n  speed: 100\n  timeout: 30"`
- `FILENAME` is skipped in the walk (it names the document, not a key).

**Trace: `install_playwright(dockerfile_path)` (verbatim)**
1. Absent Dockerfile → `None` (never create the file).
2. Lenient read of `.goga/tools/pybuggy/web.yml` (ruamel, cwd-relative; `YAMLError` caught) →
   `data["browser"]["name"]` when the path holds a mapping; absent/unreadable document or key →
   WARNING + `None`.
3. `_PLAYWRIGHT_LINE = re.compile(r"^[ \t]*RUN playwright install\b[^\n]*$", re.MULTILINE)`:
   existing line equal to `f"RUN playwright install --with-deps {browser}"` → `None`; a different
   form → repin in place (prefix match, not exact text) — the `install_pybuggy` pattern.
4. Otherwise ensure the trailing newline, append the line, INFO log, return the line text.

**Usages relevant to this task:**
- `conventions`: file I/O via `tmp_path` exclusively; expected exceptions; ruamel round-trip
  discipline (active keys never touched); WARNING for lenient no-ops, INFO for deliveries.
- `pybuggy-web` (imported usage): the documented examples describe the keys the consumer's
  `web.yml` carries.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (in `tests/commands/init/test_bootstrap.py`, expected to fail):
  `from goga_tool_pybuggy.commands.init import document_web_config_examples, install_playwright`
  — importable; both accept the documented single argument
- [ ] **Code**: add the two routines + the module constants (example-record texts, the
  `_PLAYWRIGHT_LINE` regex) to `goga_tool_pybuggy/commands/init/bootstrap.py` per the traces;
  ruamel (`YAML()`) for the lenient read; the lenient no-op logs WARNING with the design
  wording `web config unreadable — playwright install line skipped`; Google docstrings
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/commands/init/test_bootstrap.py
  -v` — pass
- [ ] **Logic tests** (design scenarios, verbatim):
  - `test_document_web_config_examples_documents_absent_keys` — setup `tmp_path` web.yml written
    as the engine would: `provider: openai\ngeneration_model: g\nclassification_model: c\nbrowser:
    \n  name: chromium\n  headless: true\nstrict: false\ninteractive: false\n`; trace: first call
    → walk → pin → dump; second call over the output; asserts first call returns ≥ 12 records
    (every absent member except FILENAME/PROVIDER/GENERATION_MODEL/CLASSIFICATION_MODEL/BROWSER/
    STRICT/INTERACTIVE); the text now contains `# base_url: (skipped optional scalar)` and the
    `cache_root` path example; the second call returns `[]` and the file bytes are unchanged;
    active keys and their values untouched (re-parse equals the original data minus comments)
  - `test_document_web_config_examples_pins_before_next_active_key` — same file; asserts in the
    written text the `base_url`/`model` records appear before `generation_model:`; the
    prompts/polling block before `strict:`; the tail (`generation_attempts` … `cache_root`)
    before `browser:` (the terminal anchor)
  - `test_install_playwright_appends_and_repins` — tmp Dockerfile `FROM base\n`; web.yml with
    `browser: {name: chromium}`; trace: append; repeat; change the browser to `firefox`; repeat;
    asserts first returns `"RUN playwright install --with-deps chromium"` and the file ends with
    it; second returns `None`, file unchanged; after the browser change the line is repinned
    **in place** (one playwright line total, now `… firefox`)
  - `test_install_playwright_noop_paths` (negative) — absent Dockerfile → `None`, file still
    absent; web.yml absent → `None` + WARNING (caplog; `assert "web config unreadable" in
    caplog.text`); web.yml invalid YAML → `None` + WARNING; Dockerfile without trailing newline
    → the appended line still lands on its own line
  - `test_document_web_config_examples_noop_when_absent_or_non_mapping` (negative) — absent file
    → `[]`; a list-root file → `[]`
  - `test_document_web_config_examples_drops_pending_without_browser` (edge, approved
    sub-decision) — hand-written web.yml with the engine-minimum keys active **except**
    `browser` — provider, generation_model, classification_model, strict, interactive; asserts
    the first call documents exactly the pre-strict blocks (base_url and model before
    `generation_model:`; generation_prompt and classification_prompt before `strict:`); the tail
    records (polling_timeout … CACHE_ROOT, BROWSER) are dropped, not appended at the end; exit
    without error; the second call returns `[]` and the file bytes are unchanged (idempotent)
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/commands/init/ -x` — fix implementation
  code until all tests pass (do NOT fix test code)
- [ ] **Contract re-verification**: example-record texts exact; the repin is prefix-match;
  writers never create the Dockerfile or `web.yml`; WARNING + no-op on lenient paths
- [ ] **Lint** (M3.3): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — 0 errors;
  `ruff format --check` on touched files

### Task 13: `commands/init/init.py` + facade — web-aware bootstrap and the 25-name `__all__` (TDD)

Implements the bootstrap delivery wiring and the cell facade. Changes in `init.py`:
`_USAGE_ROOTS` gains `("goga_tool_pybuggy.web", "")` (web usages copied flat; template-mode skip
/ bare overwrite unchanged); `_REGISTERED_USAGE_ROOTS` unchanged (stays api-only — the web usage
is kind-gated, not always-on); `PYBUGGY_ANNOTATIONS` gains the approved `pybuggy-web` line:
``Use `pybuggy-web` for browser UI tests written as step sentences (the web fixture: step/expect, capture vars, strict replay).``
`run_bootstrap`: the `api.yml` path in step 3; `web_config = cwd / ".goga" / "tools" / "pybuggy"
/ "web.yml"`; `web_written = web_config.exists()`; steps 3b / 6b (a **separate**
`register_usages`+`register_annotations` call with the single web entry, then
`_log_registration`) / 6c in contract order. Facade `commands/init/__init__.py`: add
`document_web_config_examples`, `install_playwright`, `survey_api_options`, `survey_specs`,
`survey_web_config`, `build_web_config_data`; remove `survey_extra_specs`; alphabetical
`__all__` — 25 names.

**Trace: `run_bootstrap(template_mode)` — changed steps (verbatim)**
Steps 1–2: usage copy — `_USAGE_ROOTS` gains `("goga_tool_pybuggy.web", "")` (web usages flat,
template-mode skip / bare overwrite unchanged). Step 3: `document_config_examples(cwd/".goga"/
"tools"/"pybuggy"/"api.yml")`. Step 3b: `document_web_config_examples(web_config_path)` when the
file exists. Steps 4–6 unchanged (conventions slot, `ensure_review_skip`, Dockerfile resolve +
`install_pybuggy`). Step 6b (web file present): `register_usages` / `register_annotations` with
the single `pybuggy-web` entry + `_log_registration`. Step 6c (web file present):
`install_playwright(dockerfile)`. Step 7: api registration unchanged. Step 8: `_gate_conftest`.
The mandatory-Dockerfile invariant unchanged. Every added step is file-presence-gated; the kind
answer never crosses the session boundary.

**Usages relevant to this task:**
- `pybuggy-web` (imported usage): the registered usage entry and its annotation line.
- `conventions`: facade `__all__` discipline; INFO `web config examples documented` /
  `playwright install line added|repinned to Dockerfile` / `usage registered`; DEBUG for
  absent-gate branches.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (in `tests/commands/init/test_init.py`, expected to fail):
  `test_init_facade_exports_twenty_five_names` — `sorted(init_facade.__all__)` has exactly 25
  names; `survey_extra_specs` gone; the six new names present
- [ ] **Code**: apply the `init.py` changes per the trace (`_USAGE_ROOTS` entry,
  `PYBUGGY_ANNOTATIONS` line, the `web_written` gate, steps 3b/6b/6c in contract order); update
  `commands/init/__init__.py` `__all__` and imports to the 25 names
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/commands/init/test_init.py -v`
  — pass
- [ ] **Logic tests** (design scenarios, verbatim):
  - `test_run_bootstrap_web_kind_delivers_web_artifacts` — setup tmp cwd with
    `.goga/config.yml` (dockerfile field), `.goga/tools/pybuggy/web.yml` (surveyed minimum), a
    Dockerfile at the configured path; no `api.yml`; trace `run_bootstrap(template_mode=False)`;
    asserts exit 0; `.goga/usages/cooks/pybuggy/pybuggy-web.md` exists (copied flat from the web
    root); `.goga/config.yml` `codemanifest.usages` carries `pybuggy-web` → that path and the
    annotation line carries the approved text; the Dockerfile gained the playwright line; the
    web.yml carries commented examples; nothing api-specific was registered beyond `conventions`
    (the api steps no-op'd naturally)
  - `test_run_bootstrap_api_only_skips_web_steps` — the mirror — `api.yml` present, no
    `web.yml`; asserts exit 0; no `pybuggy-web` registration; no playwright line; api examples
    documented
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/ -x` — fix implementation code until all
  tests pass (do NOT fix test code); `tests/commands/init/test_init.py` (the bootstrap
  tool-config writer site) and `tests/commands/init/test_init_integration.py` (the
  created-message assertion + the tool-config path) switch to `api.yml` after the step-3 path
  change (rename-only test migration, not weakening)
- [ ] **Contract re-verification**: every added bootstrap step is file-presence-gated; the
  approved annotation line byte-exact; `_REGISTERED_USAGE_ROOTS` unchanged; facade exactly 25
  names
- [ ] **Lint** (M3.3): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — 0 errors;
  `ruff format --check` on touched files

### Task 14: Integration tests — the prettyplay layering pin (`tests/web/test_integration.py`)

The cross-entity pin of the whole design: the verified per-field layering between `WebConfig`,
the scrubbed env, and the real prettyplay construction. This test is why `configure` scrubs —
it documents the exact behavior an Applied Fix rests on; if prettyplay 0.0.4 changes the merge,
this test names the exact behavior change. Runs in the repo venv (`pyproject.toml` exists — the
library's auto-search succeeds); lazy construction only — no browser, no LLM calls.

**Usages relevant to this task:**
- `prettyplay`: `PrettyPlay` lazy construction; per-field merge semantics; `play._runtime.config`
  read-back (private access, pinned deliberately).
- `conventions`: integration tests for cross-module interaction; `@pytest.mark.parametrize` not
  needed here — the two construction scenarios are sequential in one test.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Extend `tests/web/test_integration.py` (created in Task 8) with
  `test_prettyplay_construction_honors_web_config` (design scenario, verbatim) — setup:
  `WebConfig` with distinctive values (`generation_attempts=7`, `provider="anthropic"`,
  `cache_root=str(tmp_path)`); `monkeypatch.setenv("PRETTYPLAY_STRICT", "true")` and
  `("PRETTYPLAY_GENERATION_ATTEMPTS", "9")`; trace: `cfg = build_pretty_config(wc, False, False)`
  → `PrettyPlay("k", "sub", cleanup=False, config=cfg)` (lazy — no browser, no LLM) → read back
  `play._runtime.config`; asserts `generation_attempts == 7` (explicit wins over env);
  `strict is False` (explicit bool wins); `cache_root == str(tmp_path)`; then a second
  construction with an **empty** field (`base_url=""`) and env
  `PRETTYPLAY_BASE_URL=https://env.example` set → the effective `base_url ==
  "https://env.example"` — the documented per-field fall-through, proving the scrub is what
  closes it
- [ ] Test edge case: assert the runtime closes cleanly (`with runtime: …` exits without
  touching a browser)
- [ ] Run validation: `.venv/bin/python -m pytest tests/web/ -v` then
  `.venv/bin/python -m pytest tests/ -x` — all green
- [ ] **Lint** (M3.3): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — 0 errors;
  `ruff format --check` on touched files

### Task 15: Final verification — full suite, lint gates, `goga lint`, doc sweep (verification)

The plan-level gate before the branch is declared done. Verifies every contract obligation, the
convention lint/format gates (M3), the CODEMANIFEST integrity, and the rename completeness
criterion.

**Usages relevant to this task:**
- `conventions`: the validation-commands table (all tests / specific test / lint / facade check).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Full suite in the venv: `.venv/bin/python -m pytest tests/ -x` — every test green
  (existing suites included — no regressions from the rename, the gate, or the question set)
- [ ] Lint gate (M3.5): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — 0 errors;
  `ruff format --check goga_tool_pybuggy/web/ tests/web/` plus every file touched by Tasks 9–13
- [ ] Facade checks:
  `.venv/bin/python -c "from goga_tool_pybuggy.web import AllureStepHooks, BrowserSettings, EventLogFormatter, WebConfig, WebConfigKeys, WebPlugin, build_pretty_config, install_event_log_formatter, validate_web_config, web_cache_path; print('web facade ok')"`
  and `.venv/bin/python -c "from goga_tool_pybuggy.plugin import WebPlugin; print('plugin addressable ok')"`
  (addressability via the plain import — `WebPlugin` is not in the plugin `__all__`) and
  `.venv/bin/python -c "from goga_tool_pybuggy.commands.init import survey_web_config; print('init facade ok')"`
- [ ] CODEMANIFEST integrity: `goga lint` — **25 cells, 0 errors**
- [ ] Doc sweep (design criterion, verbatim):
  `grep -rn "tools/pybuggy/config.yml" docs/ goga_tool_pybuggy/ .goga/usages/` — the only
  remaining hits are the three deliberate clean-break notes naming the old file
  (docs/cli/init.md, goga_tool_pybuggy/config/.usages/configuration.md,
  goga_tool_pybuggy/commands/init/.usages/init.md); and
  `grep -rn "tools/pybuggy/config.yml" goga_tool_pybuggy/ --include="*.py"` is empty; do not
  reword the clean-break notes — they intentionally reference the old name
- [ ] Coverage sanity (conventions tool): `.venv/bin/python -m pytest tests/ --cov=goga_tool_pybuggy/web
  --cov-report=term-missing` — review the web cell report; every contract entity shows coverage
- [ ] Commit gate (M3.4): with all gates green, stage and commit the working tree (contracts +
  implementation + tests + docs already staged by the materialization stage are included);
  never commit red tests or lint errors

---

## Validation Commands

All commands run inside the repo virtualenv (`.venv`, created in Task 1; activate with
`source .venv/bin/activate` or call `.venv/bin/<tool>` directly).

- `pytest tests/ -x`: Run all tests (the commit gate together with ruff — M3.4)
- `pytest tests/web/test_<module>.py -v`: Run a focused test file (the REPL-cycle heartbeat — M4)
- `pytest tests/ --cov=goga_tool_pybuggy/web --cov-report=term-missing`: Coverage of the web cell
- `ruff check goga_tool_pybuggy/ tests/`: Lint check — must exit 0 (0 errors)
- `ruff format --check <touched files>`: Formatter compliance for every file the plan touches
  (apply `ruff format <files>` when it reports a diff)
- `python -c "from goga_tool_pybuggy.web import WebPlugin"`: Facade accessibility (web cell)
- `python -c "from goga_tool_pybuggy.commands.init import survey_web_config"`: Facade
  accessibility (init cell)
- `goga lint`: CODEMANIFEST integrity — 25 cells, 0 errors
- `grep -rn "tools/pybuggy/config.yml" goga_tool_pybuggy/ --include="*.py"`: Rename completeness
  (must be empty)
- `grep -rn "tools/pybuggy/config.yml" docs/ goga_tool_pybuggy/ .goga/usages/`: Doc sweep (only
  the three deliberate clean-break notes remain)

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location` (seven web modules; config
      rename; plugin gate; six new + seven changed init routines)
- [ ] Every web contract entity is accessible from the facade (10-name `__all__`); the init
      facade exports exactly 25 names
- [ ] Properties and methods match the declared API (field order, defaults, signatures)
- [ ] Descriptions are reflected in behavior (error texts, OR-semantics, cache addressing,
      guards, idempotency, kind branching)
- [ ] Contract dependencies are met (plugin→web, commands/init→web imports; web imports nothing
      internal)
- [ ] No re-export obligations exist (none declared) and none were invented
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic
      tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task;
      integration tests cover the cross-entity layering pin
- [ ] Integration tests exist (Task 14) for the cross-entity scenario
- [ ] No package boundary was expanded (no new cells; `WEB_CONFIG_FILE`/`CONFIG_FILE` are
      implementation-hint constants, not contract types)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only)
- [ ] All validation commands pass (full suite, ruff check 0 errors, format-clean touched files,
      facade imports, `goga lint` 25/0, doc sweep empty over `*.py`)
- [ ] Every Usages entry is mentioned in at least one task (`conventions`, `pluginator`,
      `prettyplay`, `allure-pytest`, imported `pybuggy-web`)
- [ ] Mandatory Rules M1–M4 held in every task: convention-aligned style, convention-based
      tests, ruff lint/format gates at every stage and before every local commit, REPL cycle with
      code migration to source files
