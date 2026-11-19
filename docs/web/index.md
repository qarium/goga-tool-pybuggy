# Web

The **web test kind** is pybuggy's browser UI testing: each test writes its scenario as
plain step sentences, an LLM turns every sentence into Playwright code **once**, the
generated code is cached next to the test, and every later run replays it from the cache
with **zero LLM calls**. When a `web.yml` document is present, the built-in `web` pytest
fixture becomes available. Without the document nothing web-related is registered — a
test requesting the fixture fails with pytest's standard `fixture 'web' not found`.

The web kind has two surfaces: the [web document](configuration.md) — `.goga/tools/pybuggy/web.yml`,
the fixed-path settings file written by `goga tool pybuggy init` (test kind `web` or
`both`) — and this page: activation, writing tests, run modes, and the step cache.

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
- `web.group(sentence)` — a coherent mini-scenario: the steps inside share one goal and
  render as one Allure group.
- `web.run_on_page(action)` — the escape hatch: run a callable receiving the raw
  Playwright `Page` when a step sentence cannot express the interaction.
- Steps carry full URLs — no `base_url` templating of sentences, no sandbox binding; the
  tested site's own base URL is the [`site.base_url`](configuration.md#keys) directive,
  consumed by `BasePage` (below).
- One action per sentence; name the target and the action in plain language.

Capture values from a page into variables addressed by name in later sentences:

```python
def test_open_third_video(web):
    web.step("Open https://video.example.com/feed")
    web.step("Save the title of the third video in {% var video_title %}")
    web.step("Open the video '{{ video_title }}'")

    web.expect("The opened video page shows the text '{{ video_title }}'")
```

- `{% var <name> %}` inside a step sentence captures a value from the page into a variable;
  `{{ <name> }}` in any later sentence — a step or an expectation — interpolates it.
- Capture only dynamic page data the test cannot know at write time; a value known in advance
  (a URL, a typed text, an expected literal) stays inline in the sentence.
- Everything captured — and every step sentence — reaches the LLM provider prompt and the
  repository: **never put secrets in step sentences** (no passwords, tokens, keys,
  personal data).

Coherent mini-scenarios group under a shared goal:

```python
def test_checkout(web):
    with web.group("Fill and submit the checkout form"):
        web.step("Open https://shop.example.com/checkout")
        web.step("Fill the email field with test@example.com")
        web.step("Click the submit button")

    web.expect("The confirmation page shows the order number")
```

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
- Secrets never belong in the base URL (query tokens included) or in anything a page method
  renders into a sentence — step sentences reach the LLM prompt and the repository.

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
for every test using that page:

```
tests/test_search.py
tests/cache/test_search/test_duckduckgo_search/   # the per-test cache — inline steps of the test
pages/cache/login_page/3f2a….py                   # the page's shared cache — method sentences
```

The cache root is the run's rootdir (or the explicit `cache_root` directive); the per-test
address is the test module's path under it with a `cache` segment above the module stem,
class-aware: a test inside `class TestLogin` gets
`tests/cache/test_login/TestLogin/<test_name>`. A parametrized test gets a directory per
parameter case — the address carries the node name with its `[<param_id>]` suffix
(`tests/cache/test_search/test_duckduckgo_search[phrase-ui]/`); pytest's ASCII escape of a
non-latin id decodes back to the letters (`имя и отчество` → `имя-и-отчество`), and unsafe
characters and spaces flatten to dashes. The page's shared cache lives under the same `cache`
segment at the page module's path — never
put an `__init__.py` inside a page's cache directory (the fixture discovery imports every
module of a marked directory at startup — the generated step files would join that sweep). Cache
files are never deleted
automatically — a run that fails mid-test keeps the cached steps it never reached. Do not
edit cache files by hand — delete a step's file to force its regeneration on the next
non-strict run (deleting a page-scope file affects every test of that page).

## Reporting

When [allure-pytest](https://pypi.org/project/allure-pytest/) is installed, every step
renders as an Allure step (groups as `[group]` steps) and a failed step attaches
`screenshot.png` to the report; without the package the integration stays inactive and
the tests run exactly the same. Web-test runs render the prettyplay log events in the
console, human-readable without payload duplication.
