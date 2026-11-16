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
generation/classification model, the tested-site base URL, browser, headless) as active keys, the
remaining keys as commented examples inside the file. LLM API keys live only in env/`.env`; the
document never contains keys.

## Write a web test

```python
def test_duckduckgo_search(web):
    web.step("Open https://duckduckgo.com")
    web.step('Find results for "UI testing automation"')

    web.expect('The results page contains the text "test"')
```

- `web.step(sentence)` — an action step: generated once, then replayed from the cache.
- `web.expect(sentence)` — an assertion step: polled until it holds or the polling budget ends.
- Steps carry full URLs — no sentence templating, no sandbox binding; the tested site's own base
  URL is the `site.base_url` directive of the web config, consumed by `BasePage` (below).
- One action per step sentence; name the target and the action in plain language: the target is
  addressed by its visible name (label, text) — never by CSS/XPath selectors or testids.

## Tested-site pages (`BasePage`)

When the suite addresses one site, set its base URL once — the `site.base_url` directive of the
web config (a Jinja2 template rendered at pytest configuration) — and model pages as classes:
a page object **inherits `BasePage`**, declares its `path`, and encapsulates the page's own
logic as methods — the web counterpart of the api kind's `Endpoint`, but with behavior.

```python
# pages/login_page.py — the page object: inheritance + encapsulated logic
import pytest

from goga_tool_pybuggy.web import BasePage


class LoginPage(BasePage):
    path = "/login"

    def dismiss_cookie_banner(self) -> None:
        """Dismiss the cookie banner that covers the form on every visit."""
        self.goto()
        with self.web.group("Dismiss the cookie banner"):
            self.web.step("Close the cookie banner")

        self.web.expect("The cookie banner is gone")


@pytest.fixture(scope="function")
def page_login(web) -> LoginPage:
    return LoginPage(web)
```

```python
def test_login_form(page_login):
    page_login.dismiss_cookie_banner()  # the page drives its own steps

    page_login.web.expect("The login form is visible")
```

- A page object is a **`BasePage` subclass** with a class-level `path` — `class LoginPage(BasePage):
  path = "/login"`; the constructor also accepts a path (`BasePage(web, "/login")` for a quick
  anonymous page), but the subclass form is the working pattern for real pages.
- **Encapsulate the page's logic as methods**: closing a cookie banner, a form flow, adding to
  cart — any repeated scenario becomes a method that runs its steps through the held runtime
  (`self.web.step` / `self.web.expect` / `self.web.group`, `self.goto()` included). The test
  reads as domain actions; the sentences live next to the page they belong to, one fixture per
  page.
- `page.url` joins the site base URL with the page path (slashes normalized); `page.goto()`
  executes the "Open <url>" action step — an ordinary step of the cycle (generated once, cached,
  replayed, healed).
- Scaffold the class and its fixture with `goga tool pybuggy page generate /login login` — it
  writes the `LoginPage` skeleton and the fixture under `pages/`; the scenario methods are added
  by hand inside the generated subclass.
- A missing `site.base_url` fails loudly at first use (`url`/`goto`), never at construction.
- The no-secrets rule covers everything a page method renders into a sentence — the base URL,
  the vars, the literals: real secrets (passwords, tokens, keys) never go into a step sentence —
  it reaches the LLM prompt and the committed cache.

## One session per test

The `web` fixture is function-scoped: each test composes its own runtime — a Playwright driver,
a browser, one isolated context with a single page — and closes it after the test. Nothing is
shared between tests: cookies, localStorage, and auth state never carry over from one test into
another.

- With `browser.endpoint` set, the runtime connects to that browser for the test (`ws://` —
  a Playwright server, `http://` — CDP) and opens a fresh isolated context inside it; the
  external browser process keeps running between tests. Without an endpoint the browser is
  launched per test and closed with it.
- Cross-test state must be produced inside the test itself: logging in is part of the test's own
  steps (a login group / a precondition), never a shared setup between tests.

## Capture vars from a page

```python
def test_open_third_video(web):
    web.step("Open https://video.example.com/feed")
    web.step("Save the title of the third video in {% var video_title %}")
    web.step("Open the video '{{ video_title }}'")

    web.expect("The opened video page shows the text '{{ video_title }}'")
```

- `{% var <name> %}` inside a step sentence captures a value from the page into a variable —
  place the marker inline at the point of the sentence where the value belongs.
- `{{ <name> }}` in any later sentence — a step or an expectation — interpolates the captured
  value.
- Capture only a value the test cannot know at write time — dynamic page data (the title of the
  third video, a generated order number). A value known in advance — a URL, a typed text, an
  expected literal — stays inline in the sentence; capturing it is noise. A captured var lives
  inside its own test only (one session per test, nothing carries between tests).
- Everything captured — and every step sentence — reaches the LLM provider prompt and the
  repository: **never put secrets in step sentences** (no passwords, tokens, keys, personal data).

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
A parametrized test gets a directory per parameter case — the address carries the node name with
its `[<param_id>]` suffix (`test_search/test_duckduckgo_search[phrase-ui]/`); pytest's ASCII
escape of a non-latin id decodes back to the letters (`имя и отчество` → `имя-и-отчество`), and
unsafe characters and spaces flatten to dashes. Cache files
are never deleted automatically — the runtime runs in the persistence mode, so a run that fails
mid-test keeps the cached steps it never reached. Do not edit cache files by hand — delete a step's
file to force its regeneration on the next non-strict run.

## Reporting

When allure-pytest is installed, every step renders as an Allure step (groups as nested steps) and a
failed step attaches `screenshot.png` to the report; without the package the integration stays
inactive and the tests run exactly the same. Attachments reach the report only when the run passes
`--alluredir` (`pytest tests/web/ -q --alluredir=allure-results --clean-alluredir`, then `allure
serve allure-results`) — the project convention keeps the flag out of addopts (a CI concern), and
without it allure-pytest writes no result files: steps and failure screenshots go nowhere silently.
Web-test runs render prettyplay log events in the
console (human-readable, no payload duplication). Browser binaries are an environment requirement:
`playwright install --with-deps <browser>` locally; the Dockerfile line appended by `pybuggy init`
covers images.
