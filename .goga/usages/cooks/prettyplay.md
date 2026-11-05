# prettyplay — step-sentence browser testing (LLM generates, cache replays)

## Domain

`prettyplay` (v0.0.4) is an AI-powered UI testing tool: each step sentence ("Open https://ya.ru")
is turned into Playwright code by an LLM **once**, cached next to the test, and replayed from the
cache without any LLM involvement. Cells `goga_tool_pybuggy/web` (the configuration model) and
`goga_tool_pybuggy/plugins` (the WebPlugin) use it to provide the `web` fixture for browser
UI/E2E tests.

Import in code:
```python
from prettyplay import BrowserConfig, PrettyConfig, PrettyPlay, StepHooks
from playwright.sync_api import Error as PlaywrightError  # the only direct playwright import
```

`playwright` itself is a transitive dependency (`playwright>=1.49` via prettyplay); browser binaries
are an environment requirement — `playwright install --with-deps <browser>` locally, a Dockerfile
`RUN` line in images.

---

## PrettyConfig — the explicit settings layer

All fields are keyword-only model fields. `PrettyPlay.__init__` picks the settings layer by its
`config` argument (the 0.0.4 split):

- `config=None` — the file layer, merged pyproject `[tool.prettyplay]` → `PRETTYPLAY_*` env,
  per field. This path **always** runs the pyproject auto-search upward from the cwd and raises
  `FileNotFoundError` when no `pyproject.toml` exists.
- `config=<PrettyConfig>` — the explicit layer, adopted **verbatim**: the passed model is the
  complete effective settings; pyproject and the `PRETTYPLAY_*` env never load for it and never
  back-fill anything. Only an empty `cache_root` resolves to the absolute
  `<cwd>/.prettyplay/cache` default.

Two consequences pybuggy accounts for:

- The WebPlugin's `web` fixture always passes the explicit config built from `web.yml`, so a
  repository without a `pyproject.toml` runs web tests fine — the auto-search `FileNotFoundError`
  applies only to the `config=None` construction the fixture never takes.
- The WebPlugin scrubs every `PRETTYPLAY_*` variable once at configphase anyway — a process-level
  guard that keeps the library's env layer away from any config-less construction in the same run.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `provider` | `Literal['openai','anthropic']` | `'openai'` | LLM provider |
| `browser` | `BrowserConfig` | chromium/headless | Browser settings (below) |
| `model` | `str` | `''` | Shared model override |
| `generation_model` | `str` | `''` | Model for step-code generation |
| `classification_model` | `str` | `''` | Model for step classification |
| `base_url` | `str` | `''` | Optional LLM API proxy endpoint |
| `cache_root` | `str` | `''` | Root directory of the step cache |
| `generation_prompt` | `str` | `''` | Extra instructions for generation |
| `classification_prompt` | `str` | `''` | Extra instructions for classification |
| `strict` | `bool` | `False` | Replay-only: zero LLM calls; a cache miss fails |
| `interactive` | `bool` | `False` | Interactive step healing mode |
| `polling_timeout` | `float | None` | `None` | Assertion polling timeout |
| `polling_delay` | `float` | `0.5` | Delay between polling attempts |
| `generation_attempts` | `int` | `3` | Blind generation attempts before diagnosis |
| `healing_attempts` | `int` | `2` | Healing attempts for a failing step |
| `llm_request_attempts` | `int` | `3` | Retries of a failed LLM request |
| `request_max_tokens` | `int` | `16384` | Completion cap of one anthropic request (`max_tokens`); sized so a reasoning model never truncates — thinking blocks spend the budget before the text block, and a cap-truncated response carries no text block (an empty completion); the openai side sends no cap |
| `send_screenshots` | `bool` | `False` | Attach screenshots to LLM requests |
| `generation_approve` | `bool` | `True` | Confirm generated code before caching |
| `probe_timeout` | `float` | `0` | Locator probe timeout in seconds (0 — page default) |

`BrowserConfig` fields: `name` (`'chromium'`), `screen` (`''`), `headless` (`True`), `endpoint`
(`''` — remote Playwright endpoint), `accept_dialogs` (`False`), `speed` (`100`), `timeout` (`30`).

```python
config = PrettyConfig(
    browser=BrowserConfig(name="chrome", headless=False, screen="fullscreen"),
    strict=strict, interactive=interactive,
    provider="anthropic",
    generation_model="glm-5.3",
    generation_attempts=2,
    probe_timeout=3,
    classification_model="glm-5.3",
    classification_prompt=CLASSIFICATION_INSTRUCTIONS,
    generation_prompt=GENERATION_INSTRUCTIONS,
)
```

---

## PrettyPlay — the per-test object

```python
PrettyPlay(cache_key: str, cache_path: str | None = None, *,
           cleanup: bool = True, hooks: list[StepHooks] | None = None,
           config: PrettyConfig | None = None)
```

- `cache_key` — the context key of the test; the addressing part of every cached step.
- `cache_path` — optional subdirectory inside the cache; part of the address, so steps of
  different subdirectories never collide. The committed-cache workflow stores it next to the
  test file and commits it to the repository.
- `cleanup` — cache lifecycle switch: `True` closes by deleting the untouched step files of this
  test's cache key; `False` keeps every file — the persistence mode of the committed-cache
  workflow.
- Context manager (`with prettyplay as pretty:`) opens and closes the runtime.

Public methods:

| Method | Meaning |
|---|---|
| `step(text, *, tries=None, delay=None, vars=None)` | Execute a step sentence; generate once, then replay from cache |
| `expect(text, *, tries=None, delay=None, vars=None)` | Assertion step sentence (polled) |
| `group(prompt, *, speed=None, delay=None) -> StepGroup` | A reusable named group of steps |
| `run_on_page(action: Callable[[Page], T]) -> T` | Escape hatch: raw Playwright `Page` access |
| `get_screenshot() -> bytes` | Screenshot bytes of the current page |
| `save_screenshot(filepath: str)` | Screenshot to a file |
| `add_hooks(hooks: StepHooks)` | Subscribe an integrator (reporting) callback |

---

## StepHooks — the integrator callbacks

Base class with no-op methods; override what the integration needs. Reporting (Allure) is built
on it. Full event set: `on_step_started(step_text, step_type)`,
`on_step_finished(step_text, step_type, outcome)`, `on_step_passed`, `on_step_failed(step_text,
step_type, error)`, `on_step_verdict`, `on_group_started(group_prompt)`,
`on_group_finished(group_prompt)`, `on_group_passed`, `on_group_failed`, `on_cache_saved`,
`on_cache_skipped`, `on_generation_started`, `on_healing_started`, `on_healed`.

Step types include at least `"action"` and `"assertion"` — failure mapping picks the exception
class by them.

---

## Security — secrets never in step sentences

Step sentences, captured `vars`, and cache files land in LLM prompts and logs:

- LLM API keys live only in env/`.env` (`load_env` loads it); never in `web.yml`.
- No secrets in step sentences — anything written in a step reaches the provider prompt.
- Cache files are committed to the repository; treat their content as public to the repo.

---

## Example integration

`prettyplay_example/conftest.py` in this repository is an example integration (prettyplay itself
ships no pytest plugin or fixture, so the example wires them by hand): the `play` fixture, the
event log formatter, the Allure hooks, and the `--strict-mode` / `--interactive` pytest options.
The pybuggy WebPlugin takes its wiring shape (fixture renamed to `web`, config from `web.yml`);
the example's hardcoded values are not canonical — they become `web.yml`-driven decisions.
