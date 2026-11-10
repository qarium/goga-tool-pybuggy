# pybuggy-web — browser UI tests with step sentences

## Domain

The `web` fixture for browser UI/E2E tests: each step sentence ("Open https://ya.ru") is turned into
Playwright code by an LLM once, cached next to the test, and replayed from the cache without any LLM
involvement. Target audience: test authors writing web tests in a pybuggy-initialized project.

## Enable

The fixture requires the web config document `.goga/tools/pybuggy/web.yml` in the repository. With
the document present, the standard `goga_tool_pybuggy.plugins.install()` call (the root conftest of a
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
- One action per step sentence; name the target and the action in plain language: the target is
  addressed by its visible name (label, text) — never by CSS/XPath selectors or testids.

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

## Group steps into one mini-scenario

```python
def test_checkout(web):
    web.step("Open https://shop.example.com/checkout")

    with web.group("Submit the order form") as g:
        g.step('Fill the "Email" field with user@example.com')
        g.step("Submit the form")
        g.expect("The order confirmation appears")
```

- `web.group(prompt)` — the authoring block for one coherent mini-scenario with a shared goal;
  the prompt names that goal and reaches generation requests verbatim. Inside the block the
  surface is the ordinary one: `g.step` / `g.expect` with the `tries`/`delay`/`vars` step
  parameters.
- Use a group when a set of actions moves the page or a widget from one state to another —
  fill and submit a form, walk a multi-field dialog to its outcome, log in. Such steps are
  meaningful together and the group prompt names the reached state; independent actions stay
  as ordinary steps.
- A group heals as a unit: on a non-strict run a failed group step is diagnosed once against
  the whole group, and a `recoverable` verdict regenerates the affected steps forward — the
  case where a later step fails because an earlier action never actually moved the page to
  the expected state. A diagnosed product defect still fails the test loudly.
- Group membership changes no step's cache address: cached group steps replay as ordinary
  steps, `--strict-mode` included; the steps after the block are ordinary steps again.
- `speed` (0–100, between-step pace) and `delay` (entry pause, seconds) optionally pace the
  block.
- The group prompt follows the same no-secrets rule as step sentences.

## Per-test extra instructions

Some tests need test-specific instructions (a page quirk) that must not
leak into the global prompt. Declare them with the `generation_prompt` decorator — imported
from the package root:

```python
from goga_tool_pybuggy import generation_prompt


@generation_prompt("A cookie banner covers the page on every navigation — dismiss it before any interaction.")
def test_checkout(web):
    web.step("Open https://shop.example.com/checkout")
```

- The text **appends** to `web.yml:generation_prompt` (newline-joined) for this test only — the
  file stays the single project-wide source, the decorator carries only the extras; other
  tests are unaffected.
- The marked test gets the web runtime even without an explicit `web` parameter (an automatic
  `usefixtures("web")` stamp). Without `web.yml` it fails at setup with pytest's standard
  "fixture 'web' not found" — the same as any web test.
- Stack decorators; texts apply top-to-bottom in the order written:

```python
@generation_prompt("The country dropdown is a native <select> — use select_option.")
@generation_prompt("Dates render as DD.MM.YYYY.")
def test_order_form(web):
    ...
```

- Validation is early: a non-string, empty, or whitespace-only text raises `ValueError` at
  collection — before any browser or LLM. The text is trimmed at decoration.
- **Never put secrets in the text** — it lands in LLM prompts and logs, exactly like step
  sentences.
- The prompt participates only in generation (a cache miss): changing the text never
  regenerates already-cached steps — delete the step's cache file to force regeneration on
  the next non-strict run. In `--strict-mode` runs the decorator is inert (zero LLM calls).

## Run modes

- `pytest tests/` — normal runs: a cache miss triggers one LLM generation round, then the step is cached.
- `pytest tests/ --strict-mode` — replay-only: zero LLM calls; a cache miss fails the test. CI should
  always run web suites with `--strict-mode`.
- `pytest tests/ --interactive` — interactive step healing on failures.
- `pytest tests/ --browser-endpoint ws://grid.example:3000` — run against a remote Playwright
  endpoint for this run only: the flag overrides `browser.endpoint` of the web config, and a typed
  empty string forces the local launch. `ws://`/`wss://` address a Playwright server,
  `http://`/`https://` a CDP browser of the chromium family; an invalid value fails the run at
  pytest configuration.

Both mode flags force the mode on; they never switch off a mode enabled in the web config.

## Step cache

The step cache lands next to the test file and is committed to the repository — replay (and strict
runs) needs no LLM:

```
tests/test_search.py
tests/test_search/test_duckduckgo_search/   # the per-test cache
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
