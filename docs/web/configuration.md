# Web — Configuration

The web test kind reads a single YAML file — `.goga/tools/pybuggy/web.yml` — from a
**fixed path** relative to the current working directory. There is no `--web-config`
option. The file is read by the web plugin at pytest configuration; an invalid document
fails the run before any collection or browser start. `goga tool pybuggy init`
(test kind `web` or `both`) writes the surveyed minimum as active keys and documents
every remaining key inside the file as a commented example record.

LLM API keys are **never** written to this file — they live only in the environment or
`.env`.

## Keys

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `provider` | `openai` \| `anthropic` | `openai` | the LLM provider of the one-time step generation |
| `base_url` | `str` | `""` | the optional LLM API proxy endpoint; empty uses the provider default |
| `model` | `str` | `""` | the shared model override; empty means no override |
| `generation_model` | `str` | `""` | the model for step-code generation |
| `classification_model` | `str` | `""` | the model for step classification |
| `generation_prompt` | `str` | `""` | extra instructions appended to the generation prompt |
| `classification_prompt` | `str` | `""` | extra instructions appended to the classification prompt |
| `strict` | `bool` | `false` | the replay-only default — zero LLM calls, a cache miss fails; `--strict-mode` forces it on |
| `interactive` | `bool` | `false` | the interactive step-healing default; `--interactive` forces it on |
| `polling_timeout` | `float` | `None` | the assertion polling timeout; `None` keeps the runtime default |
| `polling_delay` | `float` | `0.5` | the delay between polling attempts, seconds |
| `generation_attempts` | `int` | `3` | blind generation attempts before diagnosis |
| `healing_attempts` | `int` | `2` | healing attempts for a failing step |
| `llm_request_attempts` | `int` | `3` | retries of a failed LLM request |
| `send_screenshots` | `bool` | `false` | attach screenshots to LLM requests |
| `generation_approve` | `bool` | `true` | confirm generated code before caching |
| `probe_timeout` | `float` | `0` | the locator probe timeout, seconds; `0` keeps the page default |
| `cache_root` | `str` | `""` | the root directory of the step cache; empty selects the per-test default (the test's own module directory) |
| `browser` | mapping | see below | the nested browser settings |

The `browser` section:

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `browser.name` | `str` | `chromium` | the browser or channel name (`chromium`, `firefox`, `webkit`, `chrome`, `msedge`) |
| `browser.headless` | `bool` | `true` | run the browser without a visible window |
| `browser.screen` | `str` | `""` | the screen mode; empty keeps the runtime default |
| `browser.endpoint` | `str` | `""` | a remote Playwright endpoint — `ws://`/`wss://` a Playwright server, `http://`/`https://` a CDP browser of the chromium family; empty runs locally; the `--browser-endpoint` flag overrides it for the run (a typed empty string forces the local launch) |
| `browser.accept_dialogs` | `bool` | `false` | auto-accept dialogs |
| `browser.speed` | `int` | `100` | the execution speed in percent |
| `browser.timeout` | `float` | `30` | the default page timeout, seconds |

An omitted key behaves as the library default; unknown keys are a hard error (the
document is validated strictly).

## The `pipelines` section

The one sanctioned foreign section is `pipelines` — the autonomy axis of the web line:

```yaml
pipelines:
  web.automate:
    autonomous: true
```

The web plugin never interprets it: `configure()` drops the section from the document
copy before the validation, so it cannot fail the run. It is read by the tool's own
autonomy resolver — an enabling entry makes a running `web.automate` pipeline run
unattended ([web.automate — Автономные прогоны](../pipelines/web-automate.md#автономные-прогоны)).
The `pybuggy init` web confirm (`Run the web.automate pipeline unattended (autonomous
mode)?`) writes it; a declined confirm writes nothing.

## Resolution and validation layering

The document is validated at pytest configuration — an unknown key, a wrong type, an
unparsable file, or a semantic violation (an off-matrix browser name, an invalid endpoint
scheme, an out-of-range speed) fails the run there, before any collection or browser start.

The `--browser-endpoint` flag joins the same gate: the typed value overrides
`browser.endpoint` on the document copy before the validation, so an invalid endpoint fails
at pytest configuration (and a typed empty string forces the local launch).

An empty or omitted key keeps the prettyplay model default: the `web` fixture passes the
config built from `web.yml` explicitly, and prettyplay adopts an explicit config verbatim —
the library's pyproject and env layers never load for it and never back-fill an empty key.
Every `PRETTYPLAY_*` environment variable is removed at pytest configuration on top of
that, so the library's env layer never applies to a web run, and no `pyproject.toml` is
required in or above the run directory.

## The surveyed minimum

`goga tool pybuggy init` (test kind `web` or `both`) asks five questions — `provider`,
`generation_model` (required), `classification_model` (required), `browser.name`
(default `chromium`), `browser.headless` (default yes) — and writes exactly those keys
plus explicit `strict: false` / `interactive: false`:

```yaml
provider: openai
generation_model: glm-5.3
classification_model: glm-5.3
browser:
  name: chromium
  headless: true
strict: false
interactive: false
```

The bootstrap then documents every absent key inside the file as a commented example
record, pinned before the next active key — idempotent, never touching active entries.

## Related

- [Web — Overview](index.md) — activation, writing tests, run modes, the step cache.
- [CLI — init](../cli/init.md) — the kind-aware onboarding session and the web bootstrap.
- [Pytest Plugins](../plugins/index.md) — the `web` fixture and the `--strict-mode` / `--interactive` / `--browser-endpoint` flags.
