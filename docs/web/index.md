# Web

The **web test kind** is pybuggy's browser UI testing: each test writes its scenario as
plain step sentences, an LLM turns every sentence into Playwright code **once**, the
generated code is cached next to the test, and every later run replays it from the cache
with **zero LLM calls**. When a `web.yml` document is present, the built-in `web` pytest
fixture becomes available. Without the document nothing web-related is registered — a
test requesting the fixture fails with pytest's standard `fixture 'web' not found`.

The web kind's documentation has three pages: this one — activation, writing tests, run
modes, and the step cache; [Steps](steps.md) — the step parameters, captured variables,
groups, the raw-Playwright escape hatch, and the failure verdicts; and the
[web document](configuration.md) — `.goga/tools/pybuggy/web.yml`, the fixed-path settings
file written by `goga tool pybuggy init` (test kind `web` or `both`).

## Activation

The web plugin activates by file presence: `.goga/tools/pybuggy/web.yml`, resolved from
the current working directory. The same `plugins.install()` call that wires the pybuggy
plugins also enables the web plugin:

```python
# conftest.py
from goga_tool_pybuggy import plugins

plugins.install()
```

With the document present the `web` fixture exists; a structurally invalid document fails
the run during pytest configuration, before any collection or browser start (a value that
violates the runtime's semantics — an unknown browser name, a non-positive attempt count —
surfaces when the test builds its runtime). The document carries the LLM provider and
models for the one-time generation; **LLM API keys live only in the environment or
`.env`** — the document never contains keys.

One environment requirement applies to every web run:

- Browser binaries: run `playwright install --with-deps <browser>` locally (the
  `pybuggy init` bootstrap appends the matching `RUN` line to the project Dockerfile for
  image runs).

Nothing api-related is required: the api plugin activates only when `api.yml` exists,
and a **web-only** project writes no `api.yml` — its runs need no api `base_url` at all.
(A `both`-kind project activates the api plugin through its `api.yml`.)

`web.yml` is the web run's single configuration source (the single CLI exception: the typed
`--browser-endpoint` flag overrides `browser.endpoint` for the run): the runtime adopts the config
built from it verbatim, and every `PRETTYPLAY_*` environment variable is removed at pytest
configuration — so neither the library's env layer nor its pyproject section ever applies,
and no `pyproject.toml` is required. A key left empty or omitted keeps the prettyplay
default (see [Web — Configuration](configuration.md)).

## Writing a web test

```python
# test_search.py
def test_duckduckgo_search(web):
    web.step("Open https://duckduckgo.com")
    web.step('Find results for "UI testing automation"')

    web.expect('The results page contains the text "test"')
```

- `web.step(sentence)` — an **action step**: generated once, then replayed from the cache.
- `web.expect(sentence)` — an **assertion step**: polled until it holds or the polling
  budget ends.
- Both take the keyword-only `tries` / `delay` / `vars` parameters — repeats, a pre-step
  pause, and call-local inputs (see [Step parameters](steps.md#step-parameters)).
- `web.group(sentence)` — a coherent mini-scenario: the steps inside share one goal and
  render as one Allure group (see [Groups](steps.md#groups)).
- `web.run_on_page(action)` — the escape hatch: run a callable receiving the raw
  Playwright `Page` when a step sentence cannot express the interaction (see
  [Raw Playwright](steps.md#raw-playwright-escape-hatch-run_on_page)).
- Steps carry full URLs — no `base_url` templating of sentences, no sandbox binding; the
  tested site's own base URL is the [`site.base_url`](configuration.md#keys) directive,
  consumed by `BasePage` (below).
- One action per sentence; name the target and the action in plain language.
- **Transient elements verify inside their triggering sentence** — a toast that appears on
  an action and auto-disappears is checked in the very sentence that triggers it: each
  sentence's code is generated immediately before it runs, so a separate expectation
  starts generating only after the trigger already ran (see
  [Transient elements](steps.md#transient-elements)).
- Capture values from a page into variables addressed by name in later sentences —
  `{% var <name> %}` captures, `{{ <name> }}` interpolates (see
  [Capture vars](steps.md#capture-vars-from-a-page)).
- Everything captured — and every step sentence — reaches the LLM provider prompt and the
  repository: **never put secrets in step sentences** (no passwords, tokens, keys,
  personal data).

## Tested-site pages (`BasePage`)

When the suite addresses one site, set its base URL once — the `site.base_url` directive of
[the web document](configuration.md#keys) (a Jinja2 template rendered at pytest
configuration) — and model pages as classes: a page object **inherits `BasePage`**, carries
its address at construction (never in the class), and encapsulates the page's logic as
methods — the web counterpart of the api kind's `Endpoint`, but with behavior.

```python
# pages/login_page.py — inheritance + encapsulated logic
import pytest

from goga_tool_pybuggy.web import BasePage


class LoginPage(BasePage):
    def dismiss_cookie_banner(self) -> None:
        """Dismiss the cookie banner that covers the form on every visit."""
        self()
        with self.group("Dismiss the cookie banner"):
            self.step("Close the cookie banner")

        self.expect("The cookie banner is gone")


@pytest.fixture(scope="function")
def page_login(web) -> LoginPage:
    return LoginPage(web, "/login")  # the address lives here — never in the class
```

```python
# test_login.py — the page fixture replaces the web fixture
def test_login_form(page_login):
    with page_login() as page:
        page.dismiss_cookie_banner()
        page.expect("The login form is visible")
```

- A page object is a **`BasePage` subclass** carrying behavior only — the **address never
  lives in the class**: it arrives as the required constructor argument, the per-page fixture
  binding it (`LoginPage(web, "/login")`).
- **The page performs its characteristic action on call** — `page_login()` opens the page (one
  action step carrying the full URL, composed from `site.base_url`) and returns the page, the
  pattern of the api kind's `Endpoint`; `with page_login() as page:` scopes the work on the
  opened page under a short local name — the exit closes nothing (the `web` fixture owns the
  runtime lifecycle) and never suppresses.
- **The step surface is proxied onto the page** — `page.step` / `page.expect` / `page.group`
  without the `.web` hop; the runtime stays public for everything else
  (`page.web.run_on_page`). step/expect/group are reserved names, never redefined by a
  subclass.
- **Encapsulate the page's logic as methods**: closing a cookie banner, a form flow, adding to
  cart — a repeated scenario becomes a method running its steps through the same proxied
  surface. The test reads as domain actions; the sentences live next to the page they belong
  to, one fixture per page.
- **Method sentences are the page's shared vocabulary**: a step executed from a named method
  of the page class (the activation call included) addresses the page's **shared cache** —
  one cached entry per sentence per method for every test calling that method (the first test
  generates it, every other test replays it with no LLM call; the same sentence of two methods
  of one page is two entries). A step called inline from a test
  (`page.step(...)` in the test body) stays the test's own per-test entry. The boundary is
  automatic — no path is ever passed by hand — so make it a deliberate choice: a method is a
  reusable sentence, an inline step is private. Word method sentences against the live DOM
  (position, role, visible text), never against the data of the moment that generated them,
  unless that data is guaranteed in every state the method runs from (see
  [Step cache](#step-cache)).
- `page.url` — the joined URL (`<site.base_url>/<path>`, slashes normalized; an empty or `/`
  path keeps the declared base verbatim — its trailing slash is significant); the activation
  call is an ordinary step of the cycle (generated once, replayed from the cache like every
  step); a missing `site.base_url` fails loudly at the call, naming the directive.
- Scaffold the class and its fixture with the generator — `goga tool pybuggy page generate
  /login login` writes the subclass skeleton and the fixture under `pages/` (see
  [page generate](../cli/page-generate.md)); the scenario methods are added by hand inside the
  generated subclass.
- The fixtures load **automatically**: `pages/` is the web kind's default fixture package (the
  mirror of the api kind's `api/`) — the web plugin discovers every module under `pages/` at
  installation, no imports, no `loader:` section; `install(loaders=[])` disables the default.
- **The entry-page pattern (auth)**: the site's login flow lives in the entry page object,
  never in every test. The sanctioned overrides: `url` — return `self.web.site_base_url`
  verbatim when the page is the site root (the trailing slash is significant); `__call__` —
  chain pre-navigation work into the activation (`self.server_auth()` setting extra HTTP
  headers via `run_on_page` from env-cred variables — secrets never reach sentences) and
  call `super().__call__()`; the app-level login form / city selection — named methods
  (`app_auth()`, `select_town()`) the test calls after the activation. `step` / `expect` /
  `group` stay reserved — a subclass never redefines them; anything else (raw Playwright
  pre-auth, dialog arming) goes through
  [`run_on_page`](steps.md#raw-playwright-escape-hatch-run_on_page).
- **Environment switch**: change `site.base_url` — not the code — and run once without
  `--strict-mode`: the navigation sentences are composed from the directive at runtime, so
  their cache regenerates; literal URLs kept in sentences (external pages, URL expectations)
  are revised by hand.
- Secrets never belong in the base URL (query tokens included) or in anything a page method
  renders into a sentence — step sentences reach the LLM prompt and the repository.

## One session per test

The `web` fixture is function-scoped: each test composes its own runtime — a Playwright
driver, a browser, one isolated context with a single page — and closes it after the test.
Nothing is shared between tests: cookies, localStorage, and auth state never carry over from
one test into another.

- With `browser.endpoint` set, the runtime connects to that browser for the test (`ws://` —
  a Playwright server, `http://` — CDP) and opens a fresh isolated context inside it; the
  external browser process keeps running between tests. Without an endpoint the browser is
  launched per test and closed with it.
- Cross-test state must be produced inside the test itself: logging in is part of the test's
  own steps (a login group / a precondition), never a shared setup between tests.

## Run modes

| Invocation | Mode | Behavior |
|------------|------|----------|
| `pytest tests/` | normal | a cache miss triggers one LLM generation round, then the step is cached |
| `pytest tests/ --strict-mode` | strict | replay-only: zero LLM calls; a cache miss fails the test |
| `pytest tests/ --interactive` | interactive | interactive step healing on failures |
| `pytest tests/ --browser-endpoint ws://host:port` | endpoint | runs against a remote Playwright endpoint (`ws://`/`wss://`) or a CDP browser (`http://`/`https://`) for this run — it overrides `browser.endpoint` of the web document; a typed empty string forces the local launch |

Both mode flags **force** their mode on — they never switch off a mode enabled in the web
document. CI should always run web suites with `--strict-mode`.

## Step cache

The step cache is committed to the repository — replay (and strict runs) needs no LLM. Steps
address two ways, decided automatically by where the call comes from: an inline step of a test
lands in the test's own cache; a step sentence executed from a named method of a page class
(the activation call included) lands in the page's **shared** cache — one entry per sentence
per method for every test using that method: the same sentence of two methods of one page is
two entries (two same-named «OK» buttons of one page press in their own contexts, the code of
one never stands in for the other):

```
tests/test_search.py
tests/.cache/test_search/test_duckduckgo_search/    # the per-test cache — inline steps of the test
pages/.cache/login_page/fill_credentials/3f2a….py  # the page's shared cache — per method
```

The cache root is the run's rootdir (or the explicit `cache_root` directive); the per-test
address is the test module's path under it with a `.cache` segment above the module stem,
class-aware: a test inside `class TestLogin` gets
`tests/.cache/test_login/TestLogin/<test_name>`. A parametrized test gets a directory per
parameter case — the address carries the node name with its `[<param_id>]` suffix
(`tests/.cache/test_search/test_duckduckgo_search[phrase-ui]/`); pytest's ASCII escape of a
non-latin id decodes back to the letters (`имя и отчество` → `имя-и-отчество`), and unsafe
characters and spaces flatten to dashes. The page's shared cache lives under the same `.cache`
segment at the page module's path, one directory per method below the page's own (`__call__`
for the activation) — never
put an `__init__.py` inside a page's cache directory (the fixture discovery imports every
module of a marked directory at startup — the generated step files would join that sweep). Cache
files are never deleted
automatically — a run that fails mid-test keeps the cached steps it never reached. Do not
edit cache files by hand — delete a step's file to force its regeneration on the next
non-strict run (deleting a method's file affects every test calling that method).

## Reporting

When [allure-pytest](https://pypi.org/project/allure-pytest/) is installed, every step
renders as an Allure step (groups as `[group]` steps) and a failed step attaches
`screenshot.png` to the report; without the package the integration stays inactive and
the tests run exactly the same. Attachments reach the report only when the run passes
`--alluredir` (`pytest tests/web/ -q --alluredir=allure-results --clean-alluredir`, then
`allure serve allure-results`) — the project convention keeps the flag out of addopts
(a CI concern), and without it allure-pytest writes no result files: steps and failure
screenshots go nowhere silently. Web-test runs render the prettyplay log events in the
console, human-readable without payload duplication.

Author-initiated screenshots: `web.get_screenshot()` returns full-page PNG bytes and
`web.save_screenshot(filepath)` writes them to a file — the decision to capture belongs to
the author (nothing is captured automatically outside the failure hooks above); both require
an open page and fail loudly before the first step.

Every library failure is a structured `PrettyplayError` — the terminal ones a test author
meets (`ProductDefectError`, `IncurableStepError`, the `recoverable` healing verdict) are
covered in [Terminal failures and verdicts](steps.md#terminal-failures-and-verdicts).
