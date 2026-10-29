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
- One action per step sentence; name the target and the action in plain language.

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

## Run modes

- `pytest tests/` — normal runs: a cache miss triggers one LLM generation round, then the step is cached.
- `pytest tests/ --strict-mode` — replay-only: zero LLM calls; a cache miss fails the test. CI should
  always run web suites with `--strict-mode`.
- `pytest tests/ --interactive` — interactive step healing on failures.

Both flags force the mode on; they never switch off a mode enabled in the web config.

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
