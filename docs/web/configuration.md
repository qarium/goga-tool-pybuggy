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
| `request_max_tokens` | `int` | `16384` | the anthropic completion cap (`max_tokens`) — a reasoning model spends the budget on thinking before the text block, and a cap-truncated response carries no text block at all (an empty completion); raise it for models that think longer; the openai side sends no cap |
| `send_screenshots` | `bool` | `false` | attach screenshots to LLM requests |
| `send_structure` | `bool` | `true` | attach the structural element registry (interactive elements with verified unique selectors) to LLM requests — lets the generated code anchor on the markup instead of element text |
| `generation_approve` | `bool` | `true` | confirm generated code before caching |
| `probe_timeout` | `float` | `0` | the locator probe timeout, seconds; `0` keeps the page default |
| `cache_root` | `str` | `""` | the root directory of the step cache; empty selects the run's rootdir — per-test files land in a `cache` subdirectory beside the test module, the pages' shared step cache under a `cache` segment at the page module's path |
| `site` | mapping | see below | the nested tested-site settings |
| `browser` | mapping | see below | the nested browser settings |

The `site` section:

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `site.base_url` | `str` | `""` | the base URL of the tested site — a Jinja2 template (see below) rendered once at pytest configuration; the rendered value must be a valid `http://`/`https://` URL; empty means unset — page objects fail loudly on use; consumed through the web runtime by `BasePage` |

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
| `browser.ignore_https_errors` | `bool` | `false` | treat HTTPS certificate errors as non-fatal (self-signed and invalid certificates open) — a context parameter, applied in every launch mode |

An omitted key behaves as the library default; unknown keys are a hard error (the
document is validated strictly).

### `site.base_url` as a Jinja2 template

`site.base_url` renders **once**, eagerly, at pytest configuration against the
rendering context — the full environment plus the CLI options you actually typed
(the same engine and context as the api kind's `base_url`): `StrictUndefined` (an
unknown variable fails the run at configuration, never a silently truncated URL),
a `match_re` test for conditional assembly, and every whitespace run of the
rendered value removed (a multi-line YAML scalar renders to one clean URL). A
plain URL without placeholders renders to itself. The **rendered** value is what
the `http://`/`https://` validation judges.

```yaml
site:
  base_url: "https://{{ STAGE }}.example.com"
```

```bash
STAGE=staging pytest tests/            # → https://staging.example.com
pytest tests/ --env prod               # a typed --env joins the context → https://prod.example.com
```

The `--env`-style options are your own conftest `pytest_addoption` registrations
(unregistered options pytest rejects); only the options actually typed on the CLI
enter the context.

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

`goga tool pybuggy init` (test kind `web` or `both`) asks six questions — `provider`,
`generation_model` (required), `classification_model` (required), the tested-site
`base_url` (optional, a Jinja2 template; empty leaves it to the commented example
record), `browser.name` (default `chromium`), `browser.headless` (default yes) — and
writes exactly those keys plus explicit `strict: false` / `interactive: false`:

```yaml
provider: openai
generation_model: glm-5.3
classification_model: glm-5.3
site:
  base_url: https://{{ STAGE }}.example.com
browser:
  name: chromium
  headless: true
strict: false
interactive: false
```

The bootstrap then documents every absent key inside the file as a commented example
record, pinned before the next active key — idempotent, never touching active entries.

## Per-test extra instructions

The `generation_prompt` key above is the project-wide baseline. A single test can add its own
instructions with the `generation_prompt` decorator — imported from the package root:

```python
from goga_tool_pybuggy import generation_prompt


@generation_prompt(
    "A cookie banner (#onetrust) covers the page on every navigation — dismiss it before any interaction."
)
def test_checkout(web):
    web.step("Open https://shop.example.com/checkout")
```

- The text appends to the `generation_prompt` key (newline-joined) for this test only — the
  file stays the single project-wide source; other tests are unaffected.
- Stack decorators — texts apply top-to-bottom in the order written.
- Validation is early: a non-string, empty, or whitespace-only text raises `ValueError` at
  collection, before any browser or LLM.
- The marked test gets the web runtime automatically (an automatic `usefixtures("web")` stamp);
  without `web.yml` it fails at setup with pytest's standard "fixture 'web' not found".
- **Never put secrets in the text** — it lands in LLM prompts and logs, exactly like step
  sentences.
- The prompt participates only in generation (a cache miss): changing the text never
  regenerates already-cached steps — delete the step's cache file to force regeneration. In
  `--strict-mode` runs the decorator is inert.

## Related

- [Web — Overview](index.md) — activation, writing tests, run modes, the step cache.
- [CLI — init](../cli/init.md) — the kind-aware onboarding session and the web bootstrap.
- [Pytest Plugins](../plugins/index.md) — the `web` fixture and the `--strict-mode` / `--interactive` / `--browser-endpoint` flags.
