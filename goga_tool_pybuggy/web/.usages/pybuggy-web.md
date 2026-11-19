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
- **Transient elements verify inside their triggering sentence.** A toast / notification banner
  that appears on an action and auto-disappears seconds later is checked (or read) in the very
  sentence that triggers it — `web.step('Click the "Save" button — the "Changes saved" toast
  appears in the top-left corner')`, a toast-borne value through a `{% var %}` capture placed in
  that same sentence. On the generating run each sentence's code is produced by an LLM round
  (tens of seconds) immediately before the sentence executes, so a separate expectation sentence
  only starts generating after the trigger already ran — by the time its check executes the
  transient element is long gone and the polling can never observe it. The sentence is the unit of generation: wrapping
  the two in a group or a page-object method does not help — fold the check into the triggering sentence.
- Steps carry full URLs — no sentence templating, no sandbox binding; the tested site's own base
  URL is the `site.base_url` directive of the web config, consumed by `BasePage` (below).
- One action per step sentence; name the target and the action in plain language: the target is
  addressed by its visible name (label, text) — never by CSS/XPath selectors or testids.

### Step parameters (keyword-only)

`step` and `expect` (and the page-object proxies `page.step` / `page.expect`) take three
keyword-only parameters:

- `tries=N` — the total number of executions of the step's code, the first execution included.
  `None` (default) — the settle mode: on a pollable failure the same code re-executes after
  `polling_delay` while time remains inside `polling_timeout` (web.yml). The settle window
  starts at the **first execution**, never at the first failure; the step's internal auto-waits
  count inside it, and the first execution may consume the whole window (no repetitions follow).
  Non-pollable failures (locator ambiguity, Python-level errors of the step code) never
  re-execute — they propagate.
- `delay=S` — a quiet pause before the step, seconds (non-negative, fractional allowed).
- `vars={...}` — call-local string inputs of this one step; every value must be a string.
  A separate namespace from captures: `{{ name }}` reads a captured memory value,
  `{{ vars.name }}` reads a call input — call inputs never establish memory.

A sentence is always a plain string literal: `{{ … }}` and `{{ vars.… }}` are prettyplay
markers reaching the engine verbatim, and a Python value enters a sentence only through
`vars=`:

```python
page.expect("Ячейка строки {{ driver_id }} показывает {{ vars.expected_telephone }}",
            vars={"expected_telephone": expected_telephone})
```

## Tested-site pages (`BasePage`)

When the suite addresses one site, set its base URL once — the `site.base_url` directive of the
web config (a Jinja2 template rendered at pytest configuration) — and model pages as classes:
a page object **inherits `BasePage`**, carries its address at construction (never in the
class), and encapsulates the page's own logic as methods — the web counterpart of the api
kind's `Endpoint`, but with behavior.

```python
# pages/login_page.py — the page object: inheritance + encapsulated logic
import pytest

from goga_tool_pybuggy.web import BasePage


class LoginPage(BasePage):
    def dismiss_cookie_banner(self) -> None:
        """Dismiss the cookie banner that covers the form on every visit."""
        with self.group("Dismiss the cookie banner"):
            self.step("Close the cookie banner")

        self.expect("The cookie banner is gone")


@pytest.fixture(scope="function")
def page_login(web) -> LoginPage:
    return LoginPage(web, "/login")  # the address lives here — never in the class
```

```python
def test_login_form(page_login):
    with page_login() as page:
        page.dismiss_cookie_banner()
        page.expect("The login form is visible")
```

- A page object is a **`BasePage` subclass** carrying behavior only — the **address never
  lives in the class**: it arrives as the required constructor argument, the per-page fixture
  binding it (`LoginPage(web, "/login")`); the class-level `path` declaration form is gone.
- **The page performs its characteristic action on call** — `page_login()` opens the page (one
  action step carrying the full URL, composed from `site.base_url`) and returns the page, the
  pattern of the api kind's `Endpoint`; `with page_login() as page:` scopes the work on the
  opened page under a short local name — the exit closes nothing (the `web` fixture owns the
  runtime lifecycle) and never suppresses.
- **The step surface is proxied onto the page**: `page.step` / `page.expect` / `page.group` —
  the same sentences and keyword-only parameters (`tries`/`delay`/`vars`) as the runtime's,
  without the `.web` hop; the runtime stays public for everything else
  (`page.web.run_on_page`, `page.web.site_base_url` — the rendered site base of this run).
- **Encapsulate the page's logic as methods**: closing a cookie banner, a form flow, adding to
  cart — any repeated scenario becomes a method running its steps through the same proxied
  surface (`self.step`, `self()` to re-open). The test reads as domain actions; the sentences
  live next to the page they belong to, one fixture per page.
- **Method sentences are the page's shared vocabulary**: a step executed from a named method of
  the page class (the activation call included) addresses the page's **shared cache** — one
  cached entry per sentence for every test using the page (the first test generates it, every
  other test replays it with no LLM call). A step called inline from a test (`page.step(...)` in
  the test body) stays the test's own per-test entry. The boundary is automatic — no path is
  ever passed by hand — so make it a deliberate choice: a method is a reusable sentence, an
  inline step is private. Word method sentences against the live DOM (position, role, visible
  text), never against the data of the moment that generated them, unless that data is
  guaranteed in every state the method runs from.
- `page.url` joins the site base URL with the page path (slashes normalized); a path without a
  non-empty segment (`""` or `"/"`) yields the declared base URL **verbatim** — a trailing
  slash in `site.base_url` is significant (servers may answer 404 to the slashed-off form);
  the activation
  call is an ordinary step of the cycle (generated once, cached, replayed, healed) — step,
  expect and group are reserved names, never redefined by a subclass.
- Scaffold the class and its fixture with `goga tool pybuggy page generate /login login` — it
  writes the `LoginPage` skeleton and the fixture under `pages/`; the scenario methods are added
  by hand inside the generated subclass.
- The fixtures load **automatically**: `pages/` is the web kind's default fixture package (the
  mirror of the api kind's `api/`) — the web plugin discovers every module under `pages/` at
  installation, no imports and no `loader:` section needed; `install(loaders=[])` disables the
  default.
- `page generate` is idempotent: an existing module is silently skipped without `-f` (the
  scenario methods added inside it survive); `__init__.py` markers are created only when missing
  and never overwritten — even with `-f`.
- Only the tested site's own pages become page objects: an external page (an origin other than
  the rendered `site.base_url`) and a query-parameter address open through an ordinary step
  sentence carrying the full URL — the steps run through any page fixture the test already
  holds.
- **The entry-page pattern (auth)**: the site's login flow lives in the entry page object, never
  in every test. The sanctioned overrides: `url` — return `self.web.site_base_url` verbatim when
  the page is the site root (the trailing slash is significant); `__call__` — chain pre-navigation
  work into the activation (`self.server_auth()` setting extra HTTP headers via `run_on_page`
  from env-cred variables — secrets never reach sentences) and call `super().__call__()`; the
  app-level login form / city selection — named methods (`app_auth()`, `select_town()`) the test
  calls after the activation. `step` / `expect` / `group` stay reserved — a subclass never
  redefines them; anything else (raw Playwright pre-auth, dialog arming) goes through
  `run_on_page`.
- Environment switch: change `site.base_url` — not the code — and run once without
  `--strict-mode`: the navigation sentences are composed from the directive at runtime, so their
  cache regenerates; literal URLs kept in sentences (external pages, URL expectations) are
  revised by hand.
- A missing `site.base_url` fails loudly at first use (`url` or the activation call), never at
  construction.
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
  value; `{{ vars.<name> }}` interpolates a call-local input of this step (the `vars=` parameter)
  — a separate namespace: `{{ <name> }}` reads memory, `{{ vars.<name> }}` reads the call inputs,
  and call inputs never establish memory.
- Capture only a value the test cannot know at write time — dynamic page data (the title of the
  third video, a generated order number). A value known in advance — a URL, a typed text, an
  expected literal — stays inline in the sentence; capturing it is noise. A captured var lives
  inside its own test only (one session per test, nothing carries between tests).
- The `{{ … }}` marker is part of the sentence text — sentences are plain string literals, and
  a Python value rides the `vars=` parameter as `{{ vars.… }}` (see Step parameters).
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

## Raw Playwright escape hatch (`run_on_page`)

`web.run_on_page(action)` (or `page.web.run_on_page(action)` from a page object) executes the
callable wholly inside the driver worker thread with the **genuine sync Playwright `Page`** —
the stateful actions excluded from generated code (auth headers, dialog handlers, downloads,
uploads, exact waits) are the author's explicit tools here:

```python
def test_delete_confirm(page_drivers):
    with page_drivers() as page:
        page.web.run_on_page(lambda pw: pw.on("dialog", lambda dialog: dialog.accept()))
        page.step("Click the Delete button of the first row")
```

- The callable runs sequentially with every step; whatever it raises propagates to the caller
  as-is; a call back into the test object from inside is rejected loudly.
- Returns plain data only — Playwright objects never cross back to the calling thread.
- Requires an open page: the page opens lazily on the first step — run a step (or activate a
  page object) first; before that the call fails with the loud "no test page yet" error.
- The same no-secrets rule: credentials come from env inside the callable, never from sentences.

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
def test_order_form(web): ...
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
- `pytest tests/ --interactive` — interactive step healing on failures: when a step fails on a
  non-strict run, the steering dialog opens — review the failed code and the page state, steer
  the regeneration (adjust the instruction, approve or edit the code); the healed code lands in
  the step cache, and the next runs replay it with no dialog.
- `pytest tests/ --browser-endpoint ws://grid.example:3000` — run against a remote Playwright
  endpoint for this run only: the flag overrides `browser.endpoint` of the web config, and a typed
  empty string forces the local launch. `ws://`/`wss://` address a Playwright server,
  `http://`/`https://` a CDP browser of the chromium family; an invalid value fails the run at
  pytest configuration.

Both mode flags force the mode on; they never switch off a mode enabled in the web config.

## Terminal failures and verdicts

Every library failure is a structured `PrettyplayError`. The terminal ones a test author meets:

- `ProductDefectError` — the step's expectation is genuinely broken in the product: neither
  replay nor regeneration helps, the test fails loudly (the triage signal of a service bug).
- `IncurableStepError` — the step never generated successfully, or the diagnosis verdict says
  regeneration cannot help.
- A **recoverable** verdict — a later step failed because an earlier action never actually moved
  the page to the expected state — regenerates the affected steps forward (group healing on
  non-strict runs); a diagnosed product defect still fails the test loudly.

In `--strict-mode` nothing regenerates: a cache miss or a failing step fails the test as-is —
that is exactly what CI replay checks.

## Step cache

The step cache is committed to the repository — replay (and strict runs) needs no LLM. Steps
address two ways, decided automatically by where the call comes from:

```
tests/test_search.py
tests/.cache/test_search/test_duckduckgo_search/  # the per-test cache — inline steps of the test
pages/.cache/login_page/3f2a….py                  # the page's shared cache — method sentences + activation
```

The cache root is the run's rootdir (or the explicit `cache_root` directive); the per-test
address is the test module's path under it with a `.cache` segment above the module stem,
class-aware: a test inside `class TestLogin` gets
`tests/.cache/test_login/TestLogin/<test_name>`. A parametrized test gets a directory per
parameter case — the address carries the node name with its `[<param_id>]` suffix
(`.cache/test_search/test_duckduckgo_search[phrase-ui]/`); pytest's ASCII escape of a non-latin
id decodes back to the letters (`имя и отчество` → `имя-и-отчество`), and unsafe characters and
spaces flatten to dashes. The page's shared cache lives under the same `.cache` segment at the
page module's path (`pages/` + the module's dotted path as directories, `.cache` above the
module's own name) — one entry per sentence shared by every test of the
page. **Never put an `__init__.py` inside a page's cache directory** — the fixture discovery
walks `pages/` by `__init__.py` markers and imports every module of a marked directory at
startup: a marked cache directory feeds the generated step files to that import sweep (they
are not fixture modules; an import-time failure of any of them fails the whole run). Cache
files are never deleted automatically — the
runtime runs in the persistence mode, so a run that fails mid-test keeps the cached steps it
never reached. Do not edit cache files by hand — delete a step's file to force its regeneration
on the next non-strict run (deleting a page-scope file affects every test of that page).

## Reporting

When allure-pytest is installed, every step renders as an Allure step (groups as nested steps) and a
failed step attaches `screenshot.png` to the report; without the package the integration stays
inactive and the tests run exactly the same.

Author-initiated screenshots: `web.get_screenshot()` returns full-page PNG bytes,
`web.save_screenshot(filepath)` writes them to a file — the decision to capture belongs to the
author (nothing is captured automatically outside the failure hooks above); both require an open
page and fail loudly before the first step.

Attachments reach the report only when the run passes
`--alluredir` (`pytest tests/web/ -q --alluredir=allure-results --clean-alluredir`, then `allure
serve allure-results`) — the project convention keeps the flag out of addopts (a CI concern), and
without it allure-pytest writes no result files: steps and failure screenshots go nowhere silently.
Web-test runs render prettyplay log events in the
console (human-readable, no payload duplication). Browser binaries are an environment requirement:
`playwright install --with-deps <browser>` locally; the Dockerfile line appended by `pybuggy init`
covers images.
