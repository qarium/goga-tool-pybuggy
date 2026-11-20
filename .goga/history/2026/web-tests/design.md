# Design Document: `web-tests`

Compiled by `goga-design-by-changes` from the CODEMANIFEST diff of branch `web-tests` against the
base `release/3.0.0` (working-tree state — the contracts are materialized, the implementation is
not). Source architecture plan: `.goga/history/2026/web-tests/arch.md`. Every library fact below was
verified against the real sources: `prettyplay` 0.0.3 (wheel from PyPI), `pluginator` (via
`.goga/usages/cooks/pluginator.md`), `pytest` 8, and this repository's existing cells.

The document specifies the **build stage**: the implementation files of the four touched cells, the
facade, and the tests. It does not contain implementation code to copy verbatim — it fixes every
decision an implementer would otherwise have to make.

---

## Contract Changes

### Changed CODEMANIFEST Files

- `goga_tool_pybuggy/web/CODEMANIFEST` — **new** cell: 10 contract types (leaf, no Imports).
- `goga_tool_pybuggy/config/CODEMANIFEST` — rename-only: the tool config path `config.yml` →
  `api.yml` in annotations/footer (global Annotations, `Config`, `load_config`, `resolve_autonomy`).
- `goga_tool_pybuggy/plugin/CODEMANIFEST` — new Imports block (`WebPlugin`, `WebConfigKeys`, usage
  `pybuggy-web` from `goga_tool_pybuggy/web`); global-annotations web-activation paragraph;
  `install` Algorithm step 5 (web gate) + renumbered step 6; api.yml renames; footer sentence.
- `goga_tool_pybuggy/commands/init/CODEMANIFEST` — new Imports block (`WebConfigKeys`, usage
  `pybuggy-web`); kind-aware global paragraph; 6 new types; `survey_extra_specs` removed;
  `pybuggy_questions` / `amend_pybuggy_config` / `build_config_data` / `survey_autonomy` /
  `document_config_examples` / `parse_specs` / `run_bootstrap` amended.

### New Entities

| Entity | Kind | Location | Cell |
|---|---|---|---|
| `BrowserSettings` | Entity (7 properties) | `config.py` | web |
| `WebConfig` | Entity (19 properties) | `config.py` | web |
| `WebConfigKeys` | Entity (20 properties, str-Enum) | `keys.py` | web |
| `validate_web_config` | Routine | `config.py` | web |
| `build_pretty_config` | Routine | `pretty.py` | web |
| `WebPlugin` | Entity (3 properties, 2 methods) | `plugin.py` | web |
| `web_cache_path` | Routine | `plugin.py` | web |
| `AllureStepHooks` | Entity (5 methods) | `allure_hooks.py` | web |
| `EventLogFormatter` | Entity (1 method) | `logging_setup.py` | web |
| `install_event_log_formatter` | Routine | `logging_setup.py` | web |
| `survey_api_options` | Routine | `session.py` | commands/init |
| `survey_specs` | Routine | `session.py` | commands/init |
| `survey_web_config` | Routine | `session.py` | commands/init |
| `build_web_config_data` | Routine | `session.py` | commands/init |
| `document_web_config_examples` | Routine | `bootstrap.py` | commands/init |
| `install_playwright` | Routine | `bootstrap.py` | commands/init |

### Changed Entities

- `install` (plugin cell) — gates `WebPlugin` on the web document presence (step 5).
- `pybuggy_questions` — declares exactly `kind` / `base_image` / `image`.
- `amend_pybuggy_config` — kind-gated branches; buffers `api.yml` and/or `web.yml`.
- `build_config_data` — signature `(answers, specs, autonomous)`; `specs` is the surveyed list.
- `survey_autonomy` — called only for api/both kinds.
- `document_config_examples` — annotation names `api.yml` (logic unchanged).
- `parse_specs` — `extra_specs` description only.
- `run_bootstrap` — web usage root in step 2; steps 3b / 6b / 6c; api.yml path.
- `load_config` / `resolve_autonomy` / `Config` — api.yml naming only.

### Deleted Entities

- `survey_extra_specs` (commands/init) — absorbed by `survey_specs`.

### Usages and Annotations Changes

- New project-level practices: `.goga/usages/cooks/prettyplay.md`,
  `.goga/usages/cooks/allure-pytest.md` (both connected by the web cell).
- `pyproject.toml`: `prettyplay>=0.0.3,<0.1.0` (runtime), `allure-pytest>=2.13` (test extra) —
  already applied by the materialization stage.
- This design amends the web CODEMANIFEST annotations and the prettyplay cook (see Applied Fixes).

---

## Applied Fixes

### Fixed CODEMANIFEST Defects

**Defect (trace checkpoint failure, user-approved fix — variant A).** The web CODEMANIFEST (global
Annotations and `build_pretty_config` Requirements) claimed: *an explicitly constructed config is
the highest-priority layer, so the pyproject auto-search never runs and `PRETTYPLAY_*` env vars
never override the file.* Verified against the prettyplay 0.0.3 source, both clauses are wrong:

1. `PrettyPlay.__init__` **always** calls `load_config(None, config)` → `_find_pyproject()` walks
   upward from the cwd and raises `FileNotFoundError` when no `pyproject.toml` exists — even with
   an explicit config. A consumer repository without one fails every web test at fixture setup.
2. `_apply_overrides` merges **per field**: only values in `model_fields_set` that are non-`None`
   and non-empty-string participate. Empty-string fields (`model`, `base_url`, `cache_root`,
   `generation_prompt`, `classification_prompt`, `browser.screen`, `browser.endpoint`) and
   `polling_timeout=None` fall through to the file layer — `PRETTYPLAY_*` env and a
   `[tool.prettyplay]` pyproject section fill them.

**Applied fix (annotations only — no signature changed):**

- `goga_tool_pybuggy/web/CODEMANIFEST` global Annotations — replaced with the verified semantics:
  per-field merge; `configure` scrubs `PRETTYPLAY_*` once at configphase; the pyproject auto-search
  runs at every runtime construction (a repo without `pyproject.toml` upward fails at fixture
  setup with the library's `FileNotFoundError` — a 0.0.x limitation, upstream-fix candidate, bound
  by the `<0.1.0` pin); a `[tool.prettyplay]` section may fill keys `web.yml` leaves empty.
- `build_pretty_config` Requirements — first bullet replaced with the per-field-merge wording.
- `WebPlugin.configure` — purpose line, Algorithm step 3 (env scrub with one INFO log), and two
  Requirements (permanent + race-free scrub) added.
- `.goga/usages/cooks/prettyplay.md` — the layering paragraph rewritten to the verified behavior.

`goga lint` after the edits: **25 cells, 0 errors**.

**Approved sub-decisions (default acceptance):**

- `document_web_config_examples`: pending records with no active `browser` key in a hand-written
  document are **dropped silently** — mirroring `document_config_examples`, which drops pending
  records when `specs` is absent.
- The `pybuggy-web` annotation line registered into consumer configs:
  ``Use `pybuggy-web` for browser UI tests written as step sentences (the web fixture: step/expect, capture vars, strict replay).``

---

## Entity Interaction and Data Flow

### Interaction Diagram

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

### Data Flows

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

### Entity Dependencies

- web cell internal: `keys.py` (leaf) ← `config.py` ← `pretty.py` ← `plugin.py`;
  `allure_hooks.py` and `logging_setup.py` ← `plugin.py`. Facade imports all six modules.
- Cross-cell: `plugin` → `web` (`WebPlugin`, `WebConfigKeys`); `commands/init` → `web`
  (`WebConfigKeys`); `commands/init` → `config`, `plugin` (existing). No reverse edges — web is a
  leaf (verified by `goga schema`).
- Implementation-only constants: `plugin/defaults.py` gains `WEB_CONFIG_FILE`; `web/keys.py` gains
  `CONFIG_FILE` (the `@define.plugin` config path and the error-naming source).

---

## Code Stack Trace

Every entry point was traced against the real sources. Checkpoints marked **verified** were
confirmed against the prettyplay 0.0.3 wheel, the pluginator cook, or this repository's code.

### Trace: `goga_tool_pybuggy.plugin.install()` (changed)

1. **Input**: called at import of the plugin module (consumer conftest `pytest_plugins`), kwargs
   default `context=call_context()`, `loaders=[PackageLoader("api", required=False)]`.
2. `plugins = [ApiPlugin(**kwargs)]` — unchanged.
3. Sandbox gate (step 4) — unchanged (`defaults.SANDBOX_CONFIG_FILE` presence;
   `normalize_container_host()` before `SandboxPlugin()`).
4. **New step 5**: `Path(defaults.WEB_CONFIG_FILE).is_file()` → append `WebPlugin()` (zero args),
   INFO `web plugin enabled`; else DEBUG `web plugin absent`. No validation here — the document is
   only checked for presence → checkpoint: **verified** against the plugin CODEMANIFEST step 5 and
   the sandbox precedent.
5. Step 6: `install_pytest_plugins(*plugins, context=…)` — injects `pytest_addoption` /
   `pytest_configure` / `pytest_collection_finish`; `pytest_configure` loops plugins calling
   `init_pytest_config` → `install()` → `configure()` → checkpoint: **verified** (pluginator cook:
   the wrapper iterates every plugin; two plugins with `--strict-mode` / `--base-url` dests do not
   collide).
6. **Output**: the consumer namespace carries the hooks of all gated plugins.

### Trace: `WebPlugin.configure()` (new)

1. **Input**: pluginator lifecycle call, no arguments, after `init_pytest_config` —
   `self.pytest_config` is readable.
2. CLI authority: `self.pytest_config.getoption("strict_mode", default=False)` / `…("interactive",
   default=False)` (dest derived from `--strict-mode` / `--interactive`; `store_true` ⇒ True only
   when typed) → assign True onto the option → checkpoint: **verified** against the ApiPlugin
   `--base-url` pattern (`self.base_url = cli_base_url` assignment through the descriptor).
3. Read the document under a parse guard — `try: document = self.plugin_config` /
   `except YAMLError as exc: raise ValueError(f"{CONFIG_FILE}: unparsable document: {exc}")` (the
   sandbox-plugin pattern) — then `self.activation = validate_web_config(dict(document))`; an
   unparsable or structurally invalid document raises `ValueError` naming
   `.goga/tools/pybuggy/web.yml` → pytest configphase fails → checkpoint: **verified**
   (SandboxPlugin precedent: same shape, `meta.config_file` naming, including the YAMLError wrap).
4. Env scrub: remove every `os.environ` key starting with `PRETTYPLAY_`; one INFO log with the
   sorted names (DEBUG when none) → checkpoint: **verified** necessity — `load_config` reads env
   per field; configphase is single-threaded (race-free); the variables exist only for the
   library's env layer.
5. `install_event_log_formatter()` — unconditional (not allure-gated).
6. **Output**: activation set, options resolved, env neutralized, console formatter active.

### Trace: `WebPlugin.web(request)` (new)

1. **Input**: `pytest.FixtureRequest` of the requesting test; `self.activation` from configure.
2. `activation = self._require_activation()` — `RuntimeError` when configure never ran (defensive;
   pluginator always configures installed plugins).
3. Address: `item = request.node`; root = `activation.cache_root` when non-empty, otherwise
   `str(item.path.parent.resolve())` → checkpoint: **verified** — `StepCache` roots at
   `Path(config.cache_root)`; an empty root would mean the cwd, which the contract forbids.
4. `config = build_pretty_config(activation, self.strict, self.interactive)`; when
   `activation.cache_root` is empty, `config = config.model_copy(update={"cache_root": root})` →
   checkpoint: **verified** — the root participates in prettyplay's per-field merge because
   `build_pretty_config` passes **every** field as a constructor kwarg, so `cache_root` is in
   `model_fields_set` from construction (pydantic v2 `model_copy(update=…)` itself does **not**
   add keys to `model_fields_set` — verified empirically on 2.14); the copied non-empty value then
   participates and wins over the library's `cwd/.prettyplay/cache` default.
5. `runtime = PrettyPlay(item.name, web_cache_path(item), cleanup=False, config=config)` →
   checkpoint: **verified** signature `PrettyPlay(cache_key, cache_path=None, *, cleanup=True,
   hooks=None, config=None)`; `cleanup=False` keeps every cached file of the key (persistence
   mode) — a run failing mid-test never destroys cached steps it never reached.
6. Allure: `if allure_hooks.allure is not None: runtime.add_hooks(AllureStepHooks(runtime))` →
   checkpoint: **verified** guarded-import cook (feature detection by module object).
7. `with runtime as play: yield play` — close on finalization.
8. **Output**: the per-test runtime (`step` / `expect` / `group` / `run_on_page`).

### Trace: `web_cache_path(item)` (new)

1. `item.path.stem` — the module stem (pytest≥7 `Item.path`; never the cwd).
2. `original = getattr(item, "originalname", None) or item.name` — parametrize-agnostic.
3. `cls = getattr(item, "cls", None)` — insert `cls.__name__` when present (class-aware).
4. `"/".join(segments)` → **Output**: posix-relative `<module_stem>/[<Class>/]<original_name>`;
   pure, no filesystem access. → checkpoint: **verified** against the pybuggy-web.md consumer doc
   examples (`test_search/test_search/test_duckduckgo_search`, `test_login/TestLogin/<name>`).

### Trace: `build_pretty_config(config, strict_flag, interactive_flag)` (new)

1. `fields = config.model_dump()` — exactly the 19 `WebConfig` field names (1:1 with
   `PrettyConfig`; `model_dump()` returns every field, set and unset alike) → checkpoint:
   **verified** field-by-field against `prettyplay/config/models.py`: same 18 scalars + `browser`,
   same defaults.
2. `browser = BrowserConfig(**fields.pop("browser"))` — the nested group maps 1:1
   (`BrowserSettings` ↔ `BrowserConfig`: name/headless/screen/endpoint/accept_dialogs/speed/timeout,
   defaults identical); semantic validation (browser matrix, ws/wss endpoint, speed range) happens
   here in the library → checkpoint: **verified**.
3. Overwrite the modes in `fields` — `fields["strict"] = config.strict or strict_flag`,
   `fields["interactive"] = config.interactive or interactive_flag` (overwrite in the dict, never
   duplicate kwargs: `model_dump()` already carries both keys, and
   `PrettyConfig(strict=…, **fields)` raises `TypeError: got multiple values for keyword argument
   'strict'` — verified empirically on pydantic 2.14) — then `PrettyConfig(browser=browser,
   **fields)`; OR-semantics (a flag forces on, never off); `polling_timeout=None` passes through
   (library default).
4. **Output**: the explicit settings layer; no I/O, no env reads (purity — env handling belongs to
   configure's scrub and prettyplay's merge).

### Trace: `validate_web_config(data)` (new)

1. Non-mapping root → `ValueError(f"{CONFIG_FILE}: the document must parse to a mapping")`.
2. Empty mapping → `ValueError(f"{CONFIG_FILE}: the document is empty — it must carry at least the
   provider and the browser name")`.
3. `WebConfig.model_validate(data)` — `extra="forbid"` rejects unknown keys (a mistyped key fails,
   never silently disables); `ValidationError` wrapped: `ValueError(f"{CONFIG_FILE}: invalid web
   config document")` with the pydantic error chained.
4. **Output**: the validated `WebConfig`; pure.

### Trace: `EventLogFormatter.format(record)` + `install_event_log_formatter()` (new)

1. `message = super().format(record)`; `event = getattr(record, "event", None)`.
2. `event ∈ {step_results_declared, step_inputs, step_candidate_code, step_cached_code,
   step_captured}` → return the message as is (it already renders the execution context).
3. Otherwise extras = `record.__dict__` minus the reserved `LogRecord` fields
   (`frozenset(LogRecord(...).__dict__) | {"message", "asctime"}`) and `_`-prefixed keys; empty →
   the message; else `" ".join(f"{k}={v!r}" …)` sorted, appended as `f"{message} | {payload}"` →
   checkpoint: **verified** against the shape of `prettyplay_example/conftest.py`.
4. Installer: `logging.getLogger("prettyplay")` at INFO; a `StreamHandler(sys.stdout)` with
   `EventLogFormatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")`; idempotent — skip
   when any existing handler of that logger already carries an `EventLogFormatter`.

### Trace: `AllureStepHooks` (new)

1. Module-level guarded import: `try: import allure / except ImportError: allure = None`;
   `from playwright.sync_api import Error as PlaywrightError` — the only direct playwright import.
2. Two `ExitStack`s (`_step_stack`, `_group_stack`) + the current step wrapper — enter/exit pairs
   stay balanced when a step fails mid-group.
3. `on_step_failed`: `wrapper.fail(error, cls=AssertionError if step_type == "assertion" else
   Exception)`; screenshot attach inside `try: allure.attach(play.get_screenshot(),
   name="screenshot.png", attachment_type=allure.attachment_type.PNG) except (PlaywrightError,
   PrettyplayError): pass` — the no-page case raises the library's `PrettyplayError`, a capture
   failure a `PlaywrightError` (verified against the prettyplay 0.0.3 source) → checkpoint:
   **verified** against the allure-pytest cook mapping table.
4. Constructed only from the fixture guard (`allure is not None`).

### Trace: `load_config()` / `resolve_autonomy()` (changed, rename-only)

1. `_TOOL="pybuggy"`, `_FILENAME` `"config.yml"` → **`"api.yml"`**; call-time
   `from goga.config import load_tool_config` unchanged (goga stays out of runtime deps).
2. Absent/empty → `FileNotFoundError` message names `.goga/tools/pybuggy/api.yml` — an old
   `config.yml` is never read, never migrated (clean break).
3. `Config` docstring names `api.yml`. → checkpoint: **verified** against the config CODEMANIFEST
   diff (annotation-only change).

### Trace: `pybuggy_questions()` (changed)

1. `kind` record first: `Question(id="kind", kind="choice", prompt="Test kind (api — API tests over
   specs, web — browser UI tests, both)", choices=["api", "web", "both"], default="api")` →
   checkpoint: **verified** `Question(id, kind, prompt, choices, default)` signature supports it.
2. `base_image` / `image` records — byte-identical to today (hints from `_BASE_IMAGE_NAMES` + the
   runtime minor tag; `{project}:latest` default; `None` default ⇒ engine-required when not
   derivable).
3. **Output**: exactly three records; no base_url, no scalar keys, no spec group, no web records.

### Trace: `amend_pybuggy_config(context)` (changed)

1. Gate on `context.invited`; `answers = context.answers`.
2. `kind = str(answers.get("kind") or "api")` — the block always carries the answer; the `or`
   default is defensive.
3. `kind in ("api", "both")`: `api_answers = survey_api_options()`; `specs = survey_specs()`;
   `autonomous = survey_autonomy()` — in that order (specs before autonomy).
4. `kind in ("web", "both")`: `web_answers = survey_web_config()`.
5. Amendments (unconditional): `context.answer(id, value)` for every `build_config_amendments(
   answers)` entry.
6. `kind in ("api", "both")`: `context.write_config("api.yml", build_config_data({**answers,
   **api_answers}, specs, autonomous))` — the renamed file.
7. `kind in ("web", "both")`: `context.write_config("web.yml", build_web_config_data(
   web_answers))`.
8. **Output**: the buffered contribution; any exception (incl. `click.Abort`) propagates → the
   mediator drops the whole contribution with a warning; the session continues.

### Trace: `build_web_config_data(web_answers)` (new)

1. Payload in insertion order (the engine's `yaml.dump` preserves it; the documenter walks it):
   `provider`, `generation_model`, `classification_model` (from the survey),
   `browser: {"name": browser_name, "headless": headless}`, `strict: False`, `interactive: False`.
2. Keys spelled via `WebConfigKeys` members (`.value`) — data-driven, no duplicated literals.
3. **Output**: plain serializable dict; every key a `WebConfigKeys` member.

### Trace: `document_web_config_examples(config_path)` (new)

1. Absent file / non-`CommentedMap` root → `[]`.
2. Walk `WebConfigKeys` in declaration order, skipping `FILENAME`; a member absent as an active
   key whose record marker (`record.split("\n", 1)[0]`) is not already in the file text
   accumulates its example record.
3. Flush pending records (joined by newline) via
   `data.yaml_set_comment_before_after_key(member.value, before=…)` before the next active key;
   `browser` (last in declaration order) is the terminal anchor; pending records remaining when
   `browser` is absent are dropped (approved sub-decision).
4. Write back only when at least one record was added; active keys never modified.

### Trace: `install_playwright(dockerfile_path)` (new)

1. Absent Dockerfile → `None` (never create the file).
2. Lenient read of `.goga/tools/pybuggy/web.yml` (ruamel, cwd-relative; `YAMLError` caught) →
   `data["browser"]["name"]` when the path holds a mapping; absent/unreadable document or key →
   WARNING + `None`.
3. `_PLAYWRIGHT_LINE = re.compile(r"^[ \t]*RUN playwright install\b[^\n]*$", re.MULTILINE)`:
   existing line equal to `f"RUN playwright install --with-deps {browser}"` → `None`; a different
   form → repin in place (prefix match, not exact text) — the `install_pybuggy` pattern.
4. Otherwise ensure the trailing newline, append the line, INFO log, return the line text.

### Trace: `run_bootstrap(template_mode)` (changed)

Steps 1–2: usage copy — `_USAGE_ROOTS` gains `("goga_tool_pybuggy.web", "")` (web usages flat,
template-mode skip / bare overwrite unchanged). Step 3: `document_config_examples(cwd/".goga"/
"tools"/"pybuggy"/"api.yml")`. Step 3b: `document_web_config_examples(web_config_path)` when the
file exists. Steps 4–6 unchanged (conventions slot, `ensure_review_skip`, Dockerfile resolve +
`install_pybuggy`). Step 6b (web file present): `register_usages` /
`register_annotations` with the single `pybuggy-web` entry + `_log_registration`. Step 6c (web
file present): `install_playwright(dockerfile)`. Step 7: api registration unchanged
(`_REGISTERED_USAGE_ROOTS` stays api-only — the web usage is kind-gated, not always-on). Step 8:
`_gate_conftest`. The mandatory-Dockerfile invariant unchanged. → checkpoint: **verified** — every
added step is file-presence-gated; the kind answer never crosses the session boundary.

---

## Algorithm Design

### `web/keys.py` — `WebConfigKeys` + the document path

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

Member order is contract order (the documenter walks it); values are the lowercase `web.yml` keys;
no validators, no behavior. `CONFIG_FILE` is the implementation-hint source for
`@define.plugin(config=…)` and for the `validate_web_config` error naming.

**Errors**: none. **Edge cases**: none — a fixed value set.

### `web/config.py` — `BrowserSettings`, `WebConfig`, `validate_web_config`

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
unknown-key rejection. `default_factory` avoids any shared-mutable-default concern under the
repo's ruff set. No value-level validators: semantic validation (browser matrix, ws/wss endpoint,
speed range, positive ints) belongs to prettyplay at `build_pretty_config` time — pybuggy
validates structure at configphase, semantics surface at the fixture with the library's clean
messages (validation layering; see Edge Cases).

`validate_web_config`: the three-rejection algorithm from the trace; docstring per the Google
convention (`Raises: ValueError`).

**Errors**: `ValueError` naming `CONFIG_FILE` for non-mapping / empty / invalid documents (the
pydantic `ValidationError` chained as `__cause__`).

**Edge cases**: a `web.yml` carrying only the surveyed minimum validates (browser defaults fill
in); a hand-edited document with `browser: {}` — `name` defaults to `"chromium"`; semantic
violations (`browser.name: safari`, `generation_attempts: 0`, `endpoint: http://…`) pass
`validate_web_config` and fail at `build_pretty_config`/first fixture with prettyplay's message —
accepted layering, documented in `pybuggy-web.md` terms ("the names the runtime accepts").

### `web/pretty.py` — `build_pretty_config`

Algorithm as traced: `model_dump` → pop browser → `BrowserConfig(**…)` → overwrite
`strict`/`interactive` in `fields` with the OR values → `PrettyConfig(browser=browser, **fields)`.
The mode values must be overwritten in the dict, never passed as separate kwargs alongside
`**fields` — `model_dump()` already carries both keys, and duplicate keyword arguments raise
`TypeError`. Pure. Type hints `-> PrettyConfig`; imports
`from prettyplay import BrowserConfig, PrettyConfig`.

**Errors**: pydantic `ValidationError` from `PrettyConfig`/`BrowserConfig` construction (semantic
violations) — propagates to the fixture; the consumer sees prettyplay's actionable per-setting
text.

**Edge cases**: `polling_timeout=None` passes through (the library default); empty strings pass
through and fall to the library's file layer per-field (env scrubbed; `[tool.prettyplay]` may fill
them — documented). The all-fields construction is load-bearing: passing every field as a
constructor kwarg puts each into `model_fields_set`, which is what makes an explicit
`strict: false`/`generation_attempts` win over the scrubbed env layer and lets the root override
of `WebPlugin.web` participate in the per-field merge — do not reduce the call to
set-fields-only.

### `web/plugin.py` — `WebPlugin`, `web_cache_path`

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
    web(self, request): the fixture trace above
    _require_activation(): RuntimeError guard (sandbox pattern)
```

Option resolution without a typed flag: `plugin_config_key` (web.yml) → `command_line`
(`getoption`, False when untyped) → `bool()` False. The explicit-false-in-file + typed-flag case
is exactly what `configure`'s authority step corrects. Module helpers: `_scrub_prettyplay_env()`
(pop `PRETTYPLAY_*`, INFO with sorted names / DEBUG when none) and `web_cache_path(item)` (pure).

**Errors**: `ValueError` from `validate_web_config` at configphase (clean, names the document);
`RuntimeError` from `_require_activation` (defensive, never in practice).

**Edge cases**: running from outside the project root — paths derive from `item.path`
(`resolve()`), never the cwd; parametrized tests share the cache directory (`originalname`) but
keep per-case keys (`item.name`); `--strict-mode` makes zero LLM calls (library contract: strict
= replay-only, a cache miss fails).

### `web/allure_hooks.py` — `AllureStepHooks`

Guarded `allure` import at module top; `PlaywrightError` from `playwright.sync_api` and
`PrettyplayError` from `prettyplay.failures` (a public library module path — the cell's
playwright-import constraint limits only playwright imports); private
`_AllureStepWrapper` (enter/fail/exit — exits as broken with the accumulated failure) exactly in
the shape of `prettyplay_example/conftest.py` (with the widened capture guard of the trace); the
five hook methods per the trace. Hook params
the body does not use carry `# noqa: ARG002` (the hook contract fixes the signatures).

**Errors**: none raised — failures are recorded on the Allure step context.

**Edge cases**: `get_screenshot()` raising `PrettyplayError` (no page — the library's own error
shape) or `PlaywrightError` (a capture failure) — both swallowed, the failure itself is already
recorded; step failing mid-group — the two stacks keep the enter/exit pairs
balanced.

### `web/logging_setup.py` — `EventLogFormatter`, `install_event_log_formatter`

As traced. Module constants: `_RESERVED_RECORD_FIELDS`, `_HUMAN_READABLE_EVENTS` (the five
events), `_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"`, `_DATEFMT = "%H:%M:%S"`. The
constructor takes `(fmt: str, datefmt: str)`; the installer passes the constants. Pure rendering;
the installer touches only the `prettyplay` logger.

**Edge cases**: a record with no extras renders the plain message; unknown events still render
with their extras (nothing is hidden).

### `web/__init__.py` — facade

```
__all__ = ["AllureStepHooks", "BrowserSettings", "EventLogFormatter", "WebConfig",
           "WebConfigKeys", "WebPlugin", "build_pretty_config", "install_event_log_formatter",
           "validate_web_config", "web_cache_path"]
```

Classes first, then routines, alphabetical within each group (the config-cell facade pattern).
Docstring: one line naming the cell and the ten names.

### `plugin/` cell changes

- `defaults.py`: `CONFIG_FILE` value → `".goga/tools/pybuggy/api.yml"`; add
  `WEB_CONFIG_FILE: Final[str] = ".goga/tools/pybuggy/web.yml"` (literal, mirroring
  `SANDBOX_CONFIG_FILE`; an alignment test pins it to `WebConfigKeys.FILENAME`).
- `__init__.py`: import `WebPlugin` from `..web`; step-5 gate in `install()`; docstring of
  `install()` gains the web sentence. `__all__` stays at its four names — `WebPlugin` is a
  web-cell contract type, and re-exporting it in the plugin `__all__` would create a second
  declaration point of the contract surface (`SandboxPlugin` is in `__all__` because it *is* a
  plugin-cell type). The import alone makes `goga_tool_pybuggy.plugin.WebPlugin` addressable,
  which is all the gate and the tests need.

### `config/` cell changes

`storage.py`: `_FILENAME = "api.yml"`, the path comment, and the `FileNotFoundError` message
text. `config.py`: the `Config` docstring path. Nothing else — signatures, algorithms, the
call-time platform import, and the `pipelines` validation are untouched.

### `commands/init/session.py` changes

- `_SCALAR_PROMPTS`, `_NUMERIC_MEMBERS`, `_SPEC_TYPES`, `_AUTONOMY_AXES`, `_BASE_IMAGE_NAMES`,
  `_DOCKERFILE_PATH` — all stay (reused by the new surveys/builders).
- `pybuggy_questions()` — the three records (trace above); drop the base_url/scalar/spec-group
  declarations.
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
- `build_web_config_data(web_answers)` — the trace payload, keys via `WebConfigKeys`.
- `amend_pybuggy_config(context)` — the trace branching; `context.write_config("api.yml", …)` /
  `("web.yml", …)`.
- New import: `from ...web import WebConfigKeys`.

### `commands/init/bootstrap.py` changes

- `document_web_config_examples(config_path)` — the trace algorithm. Example-record texts
  (module constants):
  - scalars: `f"{member.value}: (skipped optional scalar)"`
  - `GENERATION_PROMPT`: `"generation_prompt: |\n  extra instructions appended to the generation prompt (skipped optional scalar)"`
  - `CLASSIFICATION_PROMPT`: `"classification_prompt: |\n  extra instructions appended to the classification prompt (skipped optional scalar)"`
  - `CACHE_ROOT`: `"cache_root: (path example — the step cache root, e.g. tests/.web_cache)"`
  - `BROWSER`: `"browser:\n  name: chromium\n  screen: ''\n  headless: true\n  endpoint: ''\n  accept_dialogs: false\n  speed: 100\n  timeout: 30"`
  - `FILENAME` is skipped in the walk (it names the document, not a key).
- `install_playwright(dockerfile_path)` — the trace algorithm; `_PLAYWRIGHT_LINE` regex; the
  web.yml lenient read uses ruamel (`YAML()`), `YAMLError` caught → WARNING; the browser name is
  never hardcoded.
- New import: `from ...web import WebConfigKeys`.

### `commands/init/init.py` changes

- `_USAGE_ROOTS` gains `("goga_tool_pybuggy.web", "")`; `_REGISTERED_USAGE_ROOTS` unchanged.
- `PYBUGGY_ANNOTATIONS` gains the approved `pybuggy-web` line.
- `run_bootstrap`: the api.yml path in step 3; `web_config = cwd / ".goga" / "tools" / "pybuggy" /
  "web.yml"`; `web_written = web_config.exists()`; steps 3b / 6b (a **separate**
  `register_usages`+`register_annotations` call with the single web entry, then
  `_log_registration`) / 6c in contract order.

### `commands/init/__init__.py` — facade (25 names)

Add `document_web_config_examples`, `install_playwright`, `survey_api_options`, `survey_specs`,
`survey_web_config`, `build_web_config_data`; remove `survey_extra_specs`. Alphabetical `__all__`.

---

## Cross-cutting Concerns

- **Error handling**: structural config failures surface as `ValueError` naming the document at
  configphase (web — including an unparsable document: the reader's parse error is wrapped, never
  a raw traceback) / clean `FileNotFoundError` naming the path (config cell) / WARNING + no-op
  (bootstrap lenient reads). Onboarding survey exceptions propagate — the engine mediator drops
  the contribution softly. Bootstrap write failures are ERROR-logged and fail the command (exit
  1) — the existing wrapper.
- **Logging**: `logging` everywhere, lowercase messages with structured `extra` (conventions):
  INFO `web plugin enabled` / `prettyplay env layer scrubbed` / `web config examples documented` /
  `playwright install line added|repinned to Dockerfile` / `usage registered`; DEBUG for the
  absent-gate branches; WARNING for lenient no-ops (`web config unreadable — playwright install
  line skipped`) and already-registered skips. No secrets in any log (step sentences reach LLM
  prompts — `pybuggy-web.md` documents the rule).
- **Validation**: layering — pybuggy validates **structure** at configphase (`extra="forbid"`,
  Literal provider, empty/non-mapping rejection); prettyplay validates **semantics** at
  `build_pretty_config` (browser matrix, endpoint scheme, positive ints, ranges). The init survey
  validates required prompts at the prompt (`_required`).
- **Caching**: the step cache is prettyplay's, addressed by the fixture (`cache_key` =
  parametrize-aware item name; subdirectory = class-aware, parametrize-agnostic path; root =
  `web.yml` `cache_root` or the test module's absolute directory); `cleanup=False` — the
  persistence mode of the committed-cache workflow. Nothing else is cached;
  `plugin_config`/`pytest_config` are pluginator-managed.
- **Concurrency**: no shared mutable state in the web cell; the env scrub runs once at
  configphase (single-threaded by definition) and is permanent for the run — race-free by design.
  The per-test runtime is fully isolated (prettyplay: one runtime per test, lazy page).

---

## Usages Analysis

### `conventions` — `.goga/usages/conventions.md`
- **What it provides**: Python rules — relative imports, pydantic `kw_only`, Google docstrings,
  logging, blank-line discipline, test structure/mirroring, mock policy, venv requirement.
- **Where used**: every new/changed module and test file.
- **Why chosen**: mandatory project-wide practice.
- **How exactly**: `model_config = ConfigDict(kw_only=True, extra="forbid")`; relative imports
  inside the cells (`from .config import …`, `from ...web import WebConfigKeys`); `logger =
  logging.getLogger(__name__)`; tests mirror `tests/web/test_<module>.py` with `__init__.py` and
  a local `conftest.py`.

### `pluginator` — `.goga/usages/cooks/pluginator.md`
- **What it provides**: `@define.plugin(name, config=…)`, `define.option` chain, fixtures as
  plugin-class methods, `configure()` lifecycle, `install_pytest_plugins`/`call_context`.
- **Where used**: `web/plugin.py` (WebPlugin), the plugin-cell `install()` change.
- **Why chosen**: the framework the plugin cell is built on; the sandbox capability set the
  pattern to mirror.
- **How exactly**: `@define.plugin("pybuggy-web", config=CONFIG_FILE)`; options with
  `plugin_config_key` + `CommandLine(…, action="store_true")`; `configure()` as a plain method
  reading `self.pytest_config.getoption(...)`; the fixture as a `@pytest.fixture` method.

### `prettyplay` — `.goga/usages/cooks/prettyplay.md` (amended by this design)
- **What it provides**: the `PrettyConfig`/`BrowserConfig` field contract, `PrettyPlay`
  construction (`cache_key`/`cache_path`/`cleanup`/`config`), `StepHooks` events, security rules,
  and the verified layering semantics.
- **Where used**: `web/config.py`, `web/pretty.py`, `web/plugin.py`, `web/allure_hooks.py`.
- **Why chosen**: the web test kind is the prettyplay capability.
- **How exactly**: field-1:1 models; explicit `PrettyConfig` construction; `StepHooks` subclass;
  the only direct playwright import is `playwright.sync_api.Error`.

### `allure-pytest` — `.goga/usages/cooks/allure-pytest.md`
- **What it provides**: the guarded-import pattern and the StepHooks→Allure mapping with failure
  screenshots.
- **Where used**: `web/allure_hooks.py`, the fixture guard in `web/plugin.py`.
- **Why chosen**: optional reporting integration, never a runtime dependency.
- **How exactly**: `try: import allure / except ImportError: allure = None`; feature detection by
  `allure is None`; `allure.step` contexts on two `ExitStack`s; `allure.attach(…,
  name="screenshot.png", attachment_type=allure.attachment_type.PNG)`.

### Imported Usages
- `pybuggy-web` from `goga_tool_pybuggy/web` (imported by the plugin and commands/init cells) —
  consumer patterns of the web test kind; the init survey's Use-line references it for the
  consumer meaning of the surveyed fields. Path: `goga_tool_pybuggy/web/.usages/pybuggy-web.md`.
  Traceable documentation link only — no contractual obligation crosses the boundary.

---

## `.usages/` Update

### Cell: `goga_tool_pybuggy/web`
- **`pybuggy-web`** → `goga_tool_pybuggy/web/.usages/pybuggy-web.md`
  - Status: **current** (delivered by the materialization stage; verified against the CODEMANIFEST
    surface — enable gate, run modes, cache addressing, reporting guard; no secrets rule).
  - Additions needed: none. (The layering nuance is a pybuggy-internal concern; the consumer doc
    correctly says nothing about it.)

### Cell: `goga_tool_pybuggy/plugin`
- **`enable`** → `.usages/enable.md` — Status: **current** (the "Web activation" section matches
  the gate behavior: presence-gated, configphase validation, strict/interactive flags).
- **`configuration`** → `.usages/configuration.md` — Status: **current** (api.yml renames applied;
  the web note closing "Resolution priority" present).

### Cell: `goga_tool_pybuggy/config`
- **`configuration`** / **`autonomy`** → Status: **current** (api.yml naming; clean-break note).

### Cell: `goga_tool_pybuggy/commands/init`
- **`init`** / **`config-build`** → Status: **current** (kind-aware question flow, both artifacts,
  clean-break note).

No `.usages/` file changes are required by this design — the materialization stage delivered them
and the verification above found no drift. (The CODEMANIFEST annotation and cook fixes are already
recorded under Applied Fixes.)

---

## Test Stack Trace

### General Setup

- **Environment prerequisite (build stage)**: create the repo venv (conventions: create if
  missing) and install `pip install -e '.[test]'` — brings `prettyplay>=0.0.3,<0.1.0` (+
  transitive `playwright` package, no browsers), `allure-pytest>=2.13`, `pluginator`, pytest 8.
  Network reachability verified in this environment (PyPI download succeeded).
- **No LLM calls, no browsers anywhere in the suite**: the provider is never invoked (no
  `PrettyPlay` real construction except the layering-pin test, which is lazy and browser-free);
  `PrettyPlay` is doubled in fixture tests; the real `allure` package **is** exercised (test
  extra). Zero `pytest.mark.skipif` browser guards are needed because no test opens a browser.
- **Existing shared fixtures**: `tests/conftest.py::tool_config` — the writer path changes to
  `.goga/tools/pybuggy/api.yml`; add a sibling `web_config` writer fixture (same shape, `web.yml`)
  in `tests/web/conftest.py` or extend the shared one with a filename parameter.
- **Doubles** (the sandbox-plugin test pattern): `_FakePytestConfig` (needs `getoption(name,
  default=…)` + `addinivalue_line` for the web tests), `_FakeNode`/`SimpleNamespace` items for
  `web_cache_path`, a recording `PrettyPlay` double for the fixture tests,
  `monkeypatch.setattr(type(plugin), "plugin_config", document, raising=False)` +
  `plugin.init_pytest_config(fake)` + `plugin.configure()` for configure tests,
  `_ScriptedClick` (existing in `tests/commands/init/test_session.py`) for survey tests.
- **Env isolation**: the suite-wide `_isolate_os_environ` autouse fixture (snapshot/restore)
  already covers the scrub tests' restoration needs.

### Source File Registry

Created: `goga_tool_pybuggy/web/{__init__,keys,config,pretty,plugin,allure_hooks,logging_setup}.py`.
Changed: `goga_tool_pybuggy/plugin/{__init__,defaults}.py`,
`goga_tool_pybuggy/config/{config,storage}.py`,
`goga_tool_pybuggy/commands/init/{__init__,init,session,bootstrap}.py`.
Test files: `tests/web/{__init__,conftest,test_keys,test_config,test_pretty,test_plugin,
test_allure_hooks,test_logging_setup,test_integration}.py`; updated
`tests/conftest.py`, `tests/config/test_storage.py`, `tests/plugin/test_install.py`,
`tests/commands/init/{test_session,test_bootstrap,test_init}.py`.

---

### Positive Tests

#### `test_web_config_keys_members_mirror_web_config_fields` (tests/web/test_keys.py)
**Setup**: none. **Input**: `WebConfigKeys` iteration, `WebConfig.model_fields`.
**Trace**: `[m.value for m in WebConfigKeys if m is not WebConfigKeys.FILENAME]` → compared to
`list(WebConfig.model_fields)`.
**Assertions**: the 19 values equal the field names **in order**; `len(WebConfigKeys) == 20`;
every member is a `str` (`isinstance(WebConfigKeys.PROVIDER.value, str)`).
**Sufficiency**: pins the "single source" claim — the init survey, the documenter, and the model
can never drift apart (a renamed key breaks this test first).

#### `test_web_config_keys_filename_names_the_document`
**Input**: `WebConfigKeys.FILENAME.value`. **Assertions**: `== "web.yml"`; and
`CONFIG_FILE == ".goga/tools/pybuggy/web.yml"`; and `plugin_defaults.WEB_CONFIG_FILE ==
CONFIG_FILE` (cross-cell alignment).
**Sufficiency**: the installation gate and the `@define.plugin` binding read different constants —
this test is the only guard that they name the same document.

#### `test_browser_settings_defaults_mirror_prettyplay` (tests/web/test_config.py)
**Trace**: `BrowserSettings().model_dump()` vs `BrowserConfig().model_dump()`.
**Assertions**: equal dicts (`{"name": "chromium", "headless": True, "screen": "", "endpoint": "",
"accept_dialogs": False, "speed": 100, "timeout": 30.0}`).
**Sufficiency**: the contract's "omitted subkey = library default"; catches a prettyplay bump
changing defaults silently (the `<0.1.0` pin bounds, this catches).

#### `test_web_config_defaults_mirror_prettyplay`
**Trace**: per-field `WebConfig.model_fields[name].default` vs `PrettyConfig.model_fields[name].
default` for the 19 shared names (browser via dump; `polling_timeout` both `None`).
**Assertions**: equal for every field.
**Sufficiency**: same guard at the top level.

#### `test_validate_web_config_accepts_surveyed_minimum`
**Setup**: `data = {"provider": "anthropic", "generation_model": "glm-5.3",
"classification_model": "glm-5.3", "browser": {"name": "chrome", "headless": False}}`.
**Trace**: `validate_web_config(data)` → `WebConfig.model_validate` fills defaults.
**Assertions**: `config.provider == "anthropic"`; `config.browser.name == "chrome"`;
`config.browser.headless is False`; `config.browser.screen == ""` (group default filled);
`config.strict is False`; `config.polling_timeout is None`.
**Sufficiency**: the exact document `pybuggy init` writes must validate — the happy path of the
whole kind.

#### `test_build_pretty_config_maps_every_field` (tests/web/test_pretty.py)
**Setup**: `WebConfig(provider="anthropic", base_url="https://api.example", generation_model="g",
classification_model="c", generation_attempts=7, probe_timeout=3.0, cache_root="/tmp/x",
browser=BrowserSettings(name="firefox", speed=50))`.
**Trace**: `build_pretty_config(config, False, False)` → `PrettyConfig(**dump, BrowserConfig(**…))`.
**Assertions**: every listed field equal on the result; `result.browser.speed == 50`;
`result.polling_timeout is None`; `result.generation_approve is True` (untouched default).
**Sufficiency**: the 1:1 mapping is the whole contract of the routine; a field added to
`PrettyConfig` without `WebConfig` (or a typo'd name) fails here.

#### `test_build_pretty_config_or_semantics_forces_on_never_off`
**Setup**: parametrize `(config.strict, strict_flag, expected)` over
`[(False, False, False), (False, True, True), (True, False, True), (True, True, True)]`; same for
interactive.
**Assertions**: `build_pretty_config(cfg, strict_flag, False).strict == expected`.
**Sufficiency**: a CLI flag must never disable a mode enabled in the file (the consumer doc
promises "force the mode on; never switch off").

#### `test_build_pretty_config_propagates_semantic_validation_error`
**Setup**: `WebConfig(browser=BrowserSettings(name="safari"))` — structurally valid for
`validate_web_config`.
**Input**: `build_pretty_config(config, False, False)`.
**Trace**: `model_dump` → `BrowserConfig(**{"name": "safari", …})` → pydantic `ValidationError`
of the library's browser matrix (chromium/firefox/webkit/chrome/msedge — the `_validate_name`
source of prettyplay 0.0.3).
**Assertions**: `pytest.raises(ValidationError)` with `browser.name` in the error text; in the
same test, `validate_web_config({"provider": "openai", "browser": {"name": "safari"}})` succeeds —
the layering: structure passes at configphase, semantics surface at the builder.
**Sufficiency**: pins the validation-layering decision and guards against a value validator
quietly appearing in `WebConfig` against its Constraints.

#### `test_web_cache_path_shapes` (tests/web/test_plugin.py)
**Setup**: item doubles — plain `SimpleNamespace(path=Path("/proj/tests/test_search.py"),
name="test_duckduckgo_search", originalname="test_duckduckgo_search")`; class item adds
`cls=TestLogin` (a real class); parametrized item `name="test_foo[x-1]", originalname="test_foo"`.
**Trace**: `web_cache_path(item)` → stem / [class] / original joins.
**Assertions**: `"test_search/test_duckduckgo_search"`; `"test_login/TestLogin/test_foo"`;
`"test_mod/test_foo"` (parametrize-agnostic).
**Sufficiency**: the cache address is the committed-cache contract; a regression here silently
orphanes every existing cache directory.

#### `test_web_cache_path_originalname_missing_falls_back_to_name`
**Input**: item without `originalname`. **Assertions**: path ends with `item.name`. **Sufficiency**:
non-Function items must not crash the fixture.

#### `test_configure_validates_document_and_scrubs_env` (tests/web/test_plugin.py)
**Setup**: `plugin = WebPlugin()`; `monkeypatch.setattr(type(plugin), "plugin_config",
{"provider": "openai", "generation_model": "g", "classification_model": "c", "browser": {"name":
"chromium", "headless": True}}, raising=False)`; `monkeypatch.setenv("PRETTYPLAY_STRICT",
"true")`, `("PRETTYPLAY_BROWSER_SPEED", "10")`; `plugin.init_pytest_config(_FakePytestConfig())`.
**Trace**: `plugin.configure()` → CLI authority (no flags) → validate → scrub → formatter.
**Assertions**: `plugin.activation.provider == "openai"`; `"PRETTYPLAY_STRICT" not in os.environ`
and `"PRETTYPLAY_BROWSER_SPEED" not in os.environ`; an unrelated var survives.
**Sufficiency**: the env layer is the only channel that could override `web.yml` after the
per-field-merge discovery — this test pins the neutralization.

#### `test_configure_applies_cli_authority`
**Setup**: same, plus `_FakePytestConfig` returning `True` for `getoption("strict_mode")`; the
document carries `strict: False`.
**Assertions**: after `configure()`, `plugin.strict is True` (the typed flag beat the explicit
file false); with no flag, `plugin.strict is False`.
**Sufficiency**: the resolution-chain edge (config-first would swallow the flag) — the exact
behavior the contract's "CLI authority applied in configure" clause fixes.

#### `test_web_fixture_builds_address_and_cleanup` (tests/web/test_plugin.py)
**Setup**: configured plugin (activation with `cache_root: ""`, strict False); a recording
`PrettyPlay` double monkeypatched into `goga_tool_pybuggy.web.plugin.PrettyPlay`; a request double
whose `node` is `SimpleNamespace(path=Path("/proj/tests/test_a.py"), name="test_a",
originalname="test_a")`; `allure_hooks.allure` monkeypatched to `None`.
**Trace**: consume the fixture generator (`next(...)`) → address → `build_pretty_config` →
`model_copy` root override → double constructed → `next(...)` closes.
**Assertions**: the double recorded `cache_key == "test_a"`; `cache_path == "test_a/test_a"`;
`cleanup is False`; `config.cache_root == str(Path("/proj/tests").resolve())`;
`config.browser.name` per the activation; no `add_hooks` call (allure absent); the context manager
closed on exhaustion.
**Sufficiency**: pins every fixture decision at once — addressing never touches the cwd, the
persistence mode, the allure guard.

#### `test_web_fixture_honors_cache_root_key`
**Setup**: activation with `cache_root: "/tmp/webcache"`. **Assertions**: the double's
`config.cache_root == "/tmp/webcache"` (no override). **Sufficiency**: the explicit key must win
over the module-dir default.

#### `test_web_fixture_without_configure_raises_runtime_error`
**Setup**: `plugin = WebPlugin()`; `init_pytest_config` never called; the request double of the
address test.
**Input**: consume the fixture generator (`next(plugin.web(request))`).
**Trace**: `web` → `_require_activation()` → `self.activation is None` → raise RuntimeError.
**Assertions**: `pytest.raises(RuntimeError, match="not configured")`; the PrettyPlay double was
never constructed.
**Sufficiency**: the defensive branch of the contract — pins the guard so a later "simplification"
(removing it) cannot pass silently.

#### `test_web_fixture_attaches_allure_hooks_when_importable`
**Setup**: `monkeypatch.setattr(goga_tool_pybuggy.web.allure_hooks, "allure", object())`; same
double. **Assertions**: `add_hooks` called once with an `AllureStepHooks` instance.
**Sufficiency**: the guard must construct hooks only on a successful import (both directions
covered with the absent test above).

#### `test_install_event_log_formatter_idempotent` (tests/web/test_logging_setup.py)
**Setup**: the `prettyplay` logger handlers cleared first (test isolation).
**Trace**: `install_event_log_formatter()` twice.
**Assertions**: exactly one handler afterwards; it is a `StreamHandler` on `sys.stdout` carrying
an `EventLogFormatter`; the logger level is INFO.
**Sufficiency**: configure runs once per session but the guard must hold anyway (repeat installs,
multiple plugin instances in tests).

#### `test_event_log_formatter_human_readable_events_render_plain`
**Setup**: `formatter = EventLogFormatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")`.
**Input**: `logging.LogRecord("prettyplay", 20, "p", 1, "step cached", (), None)` with
`record.event = "step_cached_code"` and an extra `{"step": "open"}`.
**Assertions**: the output contains `"step cached"` and **not** `"step="`.
**Sufficiency**: the five events already render their context — appending extras would duplicate
every payload line in the console.

#### `test_event_log_formatter_appends_sorted_extras`
**Input**: a record with `event="llm_request"` and extras `{"b": 2, "a": 1}`.
**Assertions**: output matches `… | a=1 b=2` (sorted, `!r` rendering); reserved fields
(`levelname`, `message`, `asctime`) never appear; `_private` keys excluded.
**Sufficiency**: the visibility contract for every other event.

#### `test_allure_step_hooks_failed_step_attaches_screenshot` (tests/web/test_allure_hooks.py)
**Setup**: real `allure` (test extra); `play` double with `get_screenshot() -> b"PNG"`;
`monkeypatch.setattr(allure, "attach")` recording calls; `hooks = AllureStepHooks(play)`.
**Trace**: `on_step_started("Find results", "assertion")` → `on_step_failed("Find results",
"assertion", "not found")` → `on_step_finished(...)`.
**Assertions**: `allure.attach` called with `b"PNG"`, `name="screenshot.png"`,
`attachment_type=allure.attachment_type.PNG`; the step context exits broken (the wrapper's
recorded exception class is `AssertionError` for `"assertion"`, `Exception` for `"action"`).
**Sufficiency**: the reporting contract — a failed step must carry its screenshot and the right
exception class.

#### `test_allure_step_hooks_swallows_playwright_error`
**Setup**: `play.get_screenshot` raises `PlaywrightError("no page")` (real import — the playwright
package is installed, browsers are not needed); a second case raises the library's own
`PrettyplayError("no test page yet: run a step first")` (the actual no-page shape — verified
against the prettyplay 0.0.3 source).
**Assertions**: no exception escapes `on_step_failed` in either case; the step still exits broken.
**Sufficiency**: the failure itself is already recorded; a missing page (either error shape) must
not mask it.

#### `test_allure_step_hooks_stacks_balance_mid_group`
**Trace**: `on_group_started("g")` → `on_step_started` → `on_step_failed` → `on_step_finished` →
`on_group_finished("g")`.
**Assertions**: both stacks empty afterwards; a second group/step cycle after the failure works.
**Sufficiency**: the ExitStack discipline — an unbalanced stack corrupts every later Allure step
in the run.

#### `test_install_gates_web_plugin_on_document_presence` (tests/plugin/test_install.py)
**Setup**: `monkeypatch.chdir(tmp_path)`; namespace double; `mock.patch("goga_tool_pybuggy.plugin.
WebPlugin")` — case A: write a minimal `web.yml` under `.goga/tools/pybuggy/`; case B: none.
**Trace**: `install(context=ns)` → gate → `install_pytest_plugins`.
**Assertions**: A — `WebPlugin.assert_called_once_with()`; B — `WebPlugin.assert_not_called()`;
both cases leave the api/sandbox gating intact (SandboxPlugin mock called only with its own
document).
**Sufficiency**: the presence gate is the entire enablement surface of the web kind.

#### `test_install_web_gate_performs_no_validation`
**Setup**: an **invalid** `web.yml` (e.g. `provider: nope`). **Assertions**: the gate still
constructs `WebPlugin` (the mock is called) — validation belongs to configure. **Sufficiency**:
pins "the web gate performs no validation" (a validation-at-gate regression would fail web-less
projects with unrelated parse errors).

#### `test_pybuggy_questions_declares_kind_base_image_image` (tests/commands/init/test_session.py)
**Setup**: monkeypatched version helpers (existing `pinned_version_axis`-style fixtures).
**Trace**: `pybuggy_questions()`.
**Assertions**: exactly 3 records; ids `["kind", "base_image", "image"]`; `kind` is
`kind="choice"`, `choices == ["api", "web", "both"]`, `default == "api"`; no record carries a
plugin scalar id, `base_url`, or a spec group.
**Sufficiency**: the declarative block is the engine-visible surface — an extra record would leak
a question into every project regardless of kind.

#### `test_survey_api_options_asks_base_url_then_scalars` — scripted clicks (`_ScriptedClick`):
base_url `"https://api.example"`, timeout `"5"`, Enter for the rest.
**Assertions**: returns `{"base_url": "https://api.example", "timeout": "5"}`; prompt order
base_url first; unanswered keys dropped.
**Sufficiency**: the moved block must read as one flow with preserved prompt texts.

#### `test_survey_specs_first_spec_then_confirm_gate` — scripted: name/location/type/git fields,
then decline. **Assertions**: one mapping, `{"name": "client", "type": "swagger", "location":
".specs/client.yaml", "git_url": "", "git_location": "", "git_ref": ""}`; decline adds nothing.
**Sufficiency**: the first spec always lands (the api payload requires it).

#### `test_survey_web_config_asks_minimum_in_order` — scripted: provider default, models,
browser default, headless yes. **Assertions**: `{"provider": "openai", "generation_model": "g",
"classification_model": "c", "browser_name": "chromium", "headless": True}`; exactly five prompts
in contract order. **Sufficiency**: the answers shape feeds `build_web_config_data` verbatim.

#### `test_build_web_config_data_payload_shape`
**Input**: the survey dict above. **Assertions**: `data == {"provider": "openai",
"generation_model": "g", "classification_model": "c", "browser": {"name": "chromium", "headless":
True}, "strict": False, "interactive": False}` — exact key order too (`list(data) == [...]`);
every key a `WebConfigKeys` member value.
**Sufficiency**: this payload becomes `web.yml` verbatim; key order drives the documenter's pin
anchors.

#### `test_amend_pybuggy_config_kind_branches` (parametrized api / web / both)
**Setup**: `ContributionRecorder` (existing double) with `answers={"kind": kind, "base_image":
"img", "image": "p:latest"}`; surveys monkeypatched to sentinel returns.
**Trace**: `amend_pybuggy_config(context)`.
**Assertions**: api — `survey_api_options`, `survey_specs`, `survey_autonomy` called (in order),
`survey_web_config` not; files == `[("api.yml", …)]`. web — only `survey_web_config`; files ==
`[("web.yml", …)]`. both — all four surveys, api before web; files == `[("api.yml", …),
("web.yml", …)]`; amendments always buffered.
**Sufficiency**: "the api and web question sets never cross" is the contract's central promise —
this is its direct test.

#### `test_amend_pybuggy_config_kind_missing_defaults_to_api`
**Input**: answers without `kind`. **Assertions**: the api branch ran. **Sufficiency**: defensive
default for hand-built contexts.

#### `test_document_web_config_examples_documents_absent_keys` (tests/commands/init/test_bootstrap.py)
**Setup**: `tmp_path` web.yml written as the engine would: `provider: openai\n
generation_model: g\nclassification_model: c\nbrowser:\n  name: chromium\n  headless: true\n
strict: false\ninteractive: false\n`.
**Trace**: `document_web_config_examples(path)` → walk → pin → dump; second call over the output.
**Assertions**: first call returns ≥ 12 records (every absent member except FILENAME/PROVIDER/
GENERATION_MODEL/CLASSIFICATION_MODEL/BROWSER/STRICT/INTERACTIVE); the text now contains
`# base_url: (skipped optional scalar)` and the `cache_root` path example; the second call returns
`[]` and the file bytes are unchanged; active keys and their values untouched (re-parse equals
the original data minus comments).
**Sufficiency**: idempotency-by-marker and never-touch-active-keys are the two invariants a
round-trip editor can silently break.

#### `test_document_web_config_examples_pins_before_next_active_key`
**Setup**: the same file. **Assertions**: in the written text, the `base_url`/`model` records
appear before `generation_model:`; the prompts/polling block before `strict:`; the tail
(`generation_attempts` … `cache_root`) before `browser:` (the terminal anchor).
**Sufficiency**: pin position is what makes the examples readable in place.

#### `test_install_playwright_appends_and_repins` 
**Setup**: tmp Dockerfile `FROM base\n`; web.yml with `browser: {name: chromium}`.
**Trace**: `install_playwright(df)` → append; repeat; change the browser to `firefox`; repeat.
**Assertions**: first returns `"RUN playwright install --with-deps chromium"` and the file ends
with it; second returns `None`, file unchanged; after the browser change the line is repinned
**in place** (one playwright line total, now `… firefox`).
**Sufficiency**: idempotency plus the prefix-match repin (a second line would install two browser
sets into every image).

#### `test_run_bootstrap_web_kind_delivers_web_artifacts` (tests/commands/init/test_init.py)
**Setup**: tmp cwd with `.goga/config.yml` (dockerfile field), `.goga/tools/pybuggy/web.yml`
(surveyed minimum), a Dockerfile at the configured path; no `api.yml`.
**Trace**: `run_bootstrap(template_mode=False)`.
**Assertions**: exit 0; `.goga/usages/cooks/pybuggy/pybuggy-web.md` exists (copied flat from the
web root); `.goga/config.yml` `codemanifest.usages` carries `pybuggy-web` → that path and the
annotation line carries the approved text; the Dockerfile gained the playwright line; the web.yml
carries commented examples; nothing api-specific was registered beyond `conventions` (the api
steps no-op'd naturally).
**Sufficiency**: the end-to-end kind signal — file presence alone drives every web artifact.

#### `test_run_bootstrap_api_only_skips_web_steps`
**Setup**: the mirror — `api.yml` present, no `web.yml`. **Assertions**: exit 0; no
`pybuggy-web` registration; no playwright line; api examples documented.
**Sufficiency**: the reverse gate — web-less projects must be untouched by web delivery.

#### `test_prettyplay_construction_honors_web_config` (tests/web/test_integration.py)
**Setup**: repo venv (pyproject.toml exists — the auto-search succeeds); `WebConfig` with
distinctive values (`generation_attempts=7`, `provider="anthropic"`, `cache_root=str(tmp_path)`);
`monkeypatch.setenv("PRETTYPLAY_STRICT", "true")` and `("PRETTYPLAY_GENERATION_ATTEMPTS", "9")`.
**Trace**: `cfg = build_pretty_config(wc, False, False)` → `PrettyPlay("k", "sub", cleanup=False,
config=cfg)` (lazy — no browser, no LLM) → read back `play._runtime.config` (private access,
pinned deliberately).
**Assertions**: `generation_attempts == 7` (explicit wins over env); `strict is False` (explicit
bool wins); `cache_root == str(tmp_path)`; then a second construction with an **empty** field
(`base_url=""`) and env `PRETTYPLAY_BASE_URL=https://env.example` set → the effective
`base_url == "https://env.example"` — the documented per-field fall-through, proving the scrub is
what closes it (this test documents why `configure` scrubs).
**Sufficiency**: pins the verified library layering this design's Applied Fix rests on; if
prettyplay 0.0.4 changes the merge, this test names the exact behavior change.

### Negative Tests

#### `test_validate_web_config_rejects_non_mapping_root`
**Input**: `["not", "a", "mapping"]`. **Assertions**: `pytest.raises(ValueError, match=r"web\.yml:
the document must parse to a mapping")`. **Sufficiency**: a malformed YAML root must fail with the
clean named error, never a pydantic internals traceback.

#### `test_validate_web_config_rejects_empty_mapping`
**Input**: `{}`. **Assertions**: `ValueError` matching `"web.yml: the document is empty"`.
**Sufficiency**: an empty document (present file, no keys) passes the presence gate — this is the
only guard left, and it must fire at configphase.

#### `test_validate_web_config_wraps_validation_error_naming_document`
**Input**: `{"provider": "nope"}`. **Assertions**: `ValueError` matching `"web.yml: invalid web
config document"`; `exc.__cause__` is a pydantic `ValidationError`. **Sufficiency**: the wrap
contract (clean error, cause chained for diagnostics).

#### `test_web_config_rejects_unknown_key`
**Input**: `{"provider": "openai", "browesr": {"name": "chromium"}}` (typo). **Assertions**:
`ValidationError` (`extra_forbidden`). **Sufficiency**: "a mistyped key must fail, not silently
disable a setting" — without `extra="forbid"` pydantic would ignore it.

#### `test_configure_fails_configphase_on_invalid_document`
**Setup**: plugin with `plugin_config = {"provider": "nope"}`. **Trace**: `init_pytest_config` →
`configure()`. **Assertions**: `ValueError` naming the document; `plugin.activation is None`.
**Sufficiency**: the run must die before any collection or browser.

#### `test_configure_fails_configphase_on_unparsable_document`
**Setup**: a `_RefusingPlugin` subclass of `WebPlugin` whose `plugin_config` property raises
`YAMLError("bad indentation")` (the sandbox-test pattern); `plugin.init_pytest_config(
_FakePytestConfig())`.
**Trace**: `configure()` → CLI authority → the guarded read raises `YAMLError` → wrapped
`ValueError`.
**Assertions**: `pytest.raises(ValueError, match=r"web\.yml: unparsable document.*bad
indentation")`; `exc.__cause__` is the original `YAMLError`; `plugin.activation is None`.
**Sufficiency**: a hand-broken document must fail configphase with the clean named error —
without the wrap pytest dies with a raw reader traceback (INTERNALERROR-shaped) instead of the
contract's clean failure.

#### `test_load_config_names_api_yml_and_never_reads_old_config` (tests/config/test_storage.py)
**Setup**: `tool_config` writer (now api.yml) absent; an **old** `config.yml` written with valid
specs content under `.goga/tools/pybuggy/`.
**Assertions**: `pytest.raises(FileNotFoundError, match=r"\.goga/tools/pybuggy/api\.yml")` — the
old file is ignored entirely (clean break, no migration).
**Sufficiency**: the rename's sharpest edge — a renamed-back consumer must get the actionable
absent-file error, not a silent read of the stale file.

#### `test_install_playwright_noop_paths`
**Setup/Assertions**: absent Dockerfile → `None`, file still absent; web.yml absent → `None` +
WARNING (caplog); web.yml invalid YAML → `None` + WARNING; Dockerfile without trailing newline →
the appended line still lands on its own line.
**Sufficiency**: every lenient path is a no-op with a log — never a crash, never a created file.

#### `test_document_web_config_examples_noop_when_absent_or_non_mapping`
**Assertions**: absent file → `[]`; a list-root file → `[]`. **Sufficiency**: mirrors the api
documenter's guards.

#### `test_amend_cancelled_prompt_drops_contribution`
**Setup**: a survey monkeypatched to raise `click.Abort`. **Assertions**: the exception propagates
out of `amend_pybuggy_config` (the mediator drops the contribution; the session continues —
existing engine contract). **Sufficiency**: the never-catch constraint.

### Edge Case Tests

#### `test_document_web_config_examples_drops_pending_without_browser` (approved sub-decision)
**Setup**: hand-written web.yml with the engine-minimum keys active **except** `browser` —
provider, generation_model, classification_model, strict, interactive.
**Assertions**: the first call documents exactly the pre-strict blocks (base_url and model before
`generation_model:`; generation_prompt and classification_prompt before `strict:`); the tail
records (polling_timeout … CACHE_ROOT, BROWSER) are dropped, not appended at the end; exit
without error; the second call returns `[]` and the file bytes are unchanged (idempotent).
**Sufficiency**: pins the approved resolution of the unspecified case (mirror of the api
documenter's `specs` behavior) so the build stage cannot "improve" it silently.

#### `test_web_fixture_resolves_outside_project_root`
**Setup**: item `path=Path("/elsewhere/tests/test_a.py")` while `monkeypatch.chdir(tmp_path)`.
**Assertions**: the runtime double's `config.cache_root == str(Path("/elsewhere/tests").resolve())`
— no `relative_to(cwd)` anywhere (the dropped prettyplay_example conversion).
**Sufficiency**: the arch plan's explicit crash-fix scenario.

#### `test_build_config_data_takes_surveyed_specs_list`
**Input**: `answers={"timeout": "5"}`, `specs=[{"name": "a", "type": "swagger", "location": "x"},
{"name": "b", "type": "openapi", "location": "y"}]`, `autonomous={"api.automate": True}`.
**Assertions**: `data["specs"]` holds both entries (first first); `data["timeout"] == 5.0`;
`data["pipelines"] == {"api.automate": {"autonomous": True}}`.
**Sufficiency**: the changed signature — the first mapping strictly validated, the rest lenient
(`parse_specs` unchanged).

#### `test_event_log_formatter_record_without_event`
**Input**: a record with no `event` attribute and extras. **Assertions**: extras appended
(`getattr(record, "event", None)` — no `AttributeError`). **Sufficiency**: non-prettyplay records
can reach the handler only via the `prettyplay` logger, but the formatter must not assume.

#### `test_facade_exports_exactly_ten_names` (tests/web/test_integration.py)
**Trace**: `from goga_tool_pybuggy.web import WebPlugin` in a subprocess/venv check +
`sorted(goga_tool_pybuggy.web.__all__)`.
**Assertions**: the ten contract names, exactly; importable.
**Sufficiency**: the plan's verification line (`python -c "from goga_tool_pybuggy.web import
WebPlugin"`), made permanent.

#### `test_init_facade_exports_twenty_five_names` (tests/commands/init/)
**Assertions**: `sorted(init_facade.__all__)` — 25 names; `survey_extra_specs` gone; the six new
names present. **Sufficiency**: the facade is the consumer surface of the cell.

---

## Additional Instructions for the Implementation Agent

- **Order**: web cell (keys → config → pretty → logging_setup → allure_hooks → plugin → facade) →
  config cell rename → plugin cell (defaults + install gate + facade export) → commands/init
  (session → bootstrap → init + facade) → tests → docs verification. Bottom-up, the plan's order.
- **Venv**: create if missing (conventions); `pip install -e '.[test]'`; run
  `pytest tests/ -x` and `ruff check goga_tool_pybuggy/` inside it. `goga lint` must stay at
  0 errors across the 25 cells.
- **Relative imports** everywhere inside the cells; `from ...web import WebConfigKeys` /
  `WebPlugin` from the plugin/init cells. The web cell imports nothing internal.
- **Google docstrings** on every public name (`Args`/`Returns`/`Raises`); module docstrings in the
  house style (one line, then the contract nuance); blank-line discipline inside bodies; `# noqa:
  ARG002` on the unused hook parameters; line length 120; target py310.
- **Do not** add value validators to `BrowserSettings`/`WebConfig` (validation layering is a
  design decision); **do not** read env or pyproject in `build_pretty_config`; **do not** catch
  `click.Abort` in any survey; **do not** create the Dockerfile or the web.yml from the bootstrap
  writers; **do not** register the web usage unconditionally (file presence is the only gate).
- The exact user-visible strings fixed by this design: the three `validate_web_config` error
  texts (§ Algorithm Design), the playwright line `RUN playwright install --with-deps <browser>`,
  the approved `pybuggy-web` annotation line, the example-record texts of
  `document_web_config_examples`, the survey prompts of `survey_web_config` / `survey_api_options`
  / `survey_specs`, and the `kind` question record. Do not reword them — tests pin them.
- `tests/conftest.py::tool_config` switches its writer to `api.yml`; keep the old-name coverage
  via the dedicated never-read test rather than the shared fixture.
- After implementation, re-run the doc-sweep grep (`grep -rn "tools/pybuggy/config.yml" docs/
  goga_tool_pybuggy/ .goga/usages/`). The rename is complete when the only remaining hits are the
  three deliberate clean-break notes naming the old file (docs/cli/init.md,
  goga_tool_pybuggy/config/.usages/configuration.md, goga_tool_pybuggy/commands/init/.usages/init.md)
  and **no** `.py` carrier survives — equivalently,
  `grep -rn "tools/pybuggy/config.yml" goga_tool_pybuggy/ --include="*.py"` is empty. Do not
  reword the clean-break notes — they intentionally reference the old name.
