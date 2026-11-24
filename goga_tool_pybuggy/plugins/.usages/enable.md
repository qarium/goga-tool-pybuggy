# Enable — wiring the pybuggy plugins into a pytest suite

## Domain

Enabling the pybuggy plugins so a test suite gets the fixtures of every activated test kind — the `api` fixture of the
api plugin, the `sandbox` fixture, the `web` fixture — each gated on its own activation sources by one `install()` call.
Target audience: test-suite and infrastructure authors.

## Enable the plugins

Call `goga_tool_pybuggy.plugins.install()` from the root `conftest.py`:

```python
# conftest.py
from dotenv import load_dotenv

load_dotenv()

from goga_tool_pybuggy import plugins

plugins.install()
```

`load_dotenv()` runs before `install()` so plugin options (resolved from `os.environ`) see the `.env` values; the
argumentless call keeps `override=False` (CI/operator-exported variables win).

`install()` resolves the caller's (conftest) namespace through `call_context()` and injects the pytest hooks
(`pytest_addoption` / `pytest_configure` / `pytest_collection_finish`) into it, then synchronously fills its
`pytest_plugins` with the discovered generated fixtures. Pass an explicit `install(loaders=[...])` to override
discovery, or `install(loaders=[])` to disable it.

> There is **no import-time auto-wiring**: `pytest_plugins = ["goga_tool_pybuggy.plugins"]` alone does NOT enable the plugin —
> the explicit `install()` call is required.

## Api activation

The api plugin activates when the api document `.goga/tools/pybuggy/api.yml` exists. With the document, the
`install()` call registers the `api` fixture, the plugin CLI options, and the generated-fixture discovery; without
the document, nothing api-related is registered — a web-only or sandbox-only project runs with no `base_url` at all,
and a test requesting the `api` fixture gets pytest's standard `fixture 'api' not found` (`BASE_URL` stays a value
source for the option, never an activation source for the plugin).

## What enabling wires

- **CLI options** — `--base-url` (resolves `base_url`, required; a typed flag overrides the config-file and
  `BASE_URL` value), `--api-timeout` (resolves `timeout`),
  `--retries` (resolves `retries`, the flaky rerun count for the test run), `--api-assert-timeout`
  (resolves `assert_timeout`, the baseline assert-polling timeout), and `--api-assert-delay` (resolves
  `assert_delay`, the delay between polling attempts). The remaining options (`headers`,
  `assert_field_class`, `assert_response_class`) have no CLI flag and are set only via the
  config file.
- **`base_url` template** — `base_url` is a Jinja2 template rendered once in the pluginator `configure()`
  hook against `os.environ` + the CLI options the user actually passed. Placeholders that should be fed
  from the CLI (e.g. `{{ env }}`, `{{ api_version }}`) require the consumer to register those options via
  `pytest_addoption` in `conftest.py`, since pytest rejects unregistered flags:
  ```python
  # conftest.py
  def pytest_addoption(parser):
      parser.addoption("--env", action="store", default=None)
  ```
  A plain `base_url` without Jinja placeholders renders to itself; an unknown variable raises
  (`StrictUndefined`); every whitespace run in the rendered URL is removed, so a multi-line
  template (YAML folded `>` / literal `|`) renders to one clean URL.
- **Flaky reruns** — when `retries` resolves to a positive int, a `pytest_collection_modifyitems` hook stamps every
  collected test without an existing flaky marker with `pytest.mark.flaky(max_runs=retries)`. The reruns take effect
  when the `flaky` package is installed in the consumer suite; a programmatic default can be passed as
  `install(default_retries=N)`.
- **The `api` fixture** — function-scope, yields an `Api` built from the resolved options and closes it after the test
  (calling `Api.close()`, which delegates to the underlying resq.Session's public close()). Generated endpoint
  fixtures depend on it:
  ```python
  @pytest.fixture(scope="function")
  def get_orders(api: Api) -> Endpoint:
      return Endpoint(api, "/orders", method="GET")
  ```
  pytest resolves `api` automatically; no extra wiring is needed in tests.
- **Recursive generated-fixture loading** — the api and web plugins own their discovery defaults: when `install()`
  receives no explicit `loaders`, the api plugin adds `[PackageLoader("api", required=False)]` itself (every
  generated `api/<spec>/<id>/api.py` module) and the web plugin adds `[PackageLoader("pages", required=False)]`
  (every generated `pages/**` page-object module of `page generate`), so both fixture trees are discovered and
  loaded through the recursive `pytest_plugins` list, out of the box.

## Overriding discovery

Pass an explicit `loaders` to `install()` to change the discovered trees, or add a `loader` section to a tool
document to do it declaratively. The explicit `loaders` reach every active plugin's discovery (api, sandbox, web
alike); the api and web plugins apply their own `api/` and `pages/` defaults only when no explicit loaders arrive.
The same `loader`
section is accepted by every tool document — `api.yml`, `sandbox.yml`, and `web.yml` — so external fixture
packages can be wired into any test kind through the config, without touching the conftest:

```python
goga_tool_pybuggy.plugins.install(loaders=[PackageLoader("api"), PackageLoader("service")])
# or disable discovery entirely:
goga_tool_pybuggy.plugins.install(loaders=[])
```

```yaml
# .goga/tools/pybuggy/api.yml
loader:
  packages:
    - name: api        # walk the api/ package tree (dots map to path separators)
      required: false  # tolerate a missing tree
  modules:
    - my_plugin.conftest
```

## Preconditions and side effects

- The api plugin activates when `.goga/tools/pybuggy/api.yml` exists; the `api/` tree is then discovered by
  default, and a missing tree is tolerated (`required=False`).
- When the api plugin is active and its required `base_url` resolves from no source (no document key, no `BASE_URL`,
  no typed `--base-url`), the run fails at pytest configuration on the required-option error.
- Loader paths walk the filesystem relative to the **current working directory** (while the plugin probe imports
  candidates through `sys.path`). Run `pytest` from the project root — the directory that both contains `api/` and
  is on `sys.path`. Running from another directory makes discovery silently return `[]`, so generated fixtures are
  not loaded and tests fail with `fixture '<name>' not found`.

## Sandbox activation

The same `plugins.install()` call also installs the pybuggy sandbox plugin: when the test
repository holds the sandbox document at `.goga/tools/pybuggy/sandbox.yml` (under the pybuggy
tools home), the plugin provides the product `sandbox` fixture — the sandbox starts lazily, on
the first test that requests the fixture (mock dependency services and the instance under test,
with visible progress), and stops at session finalization. With the document the call also
normalizes the container-host address automatically (`host.docker.internal` inside a container,
the host's own routable IP on a host run; an explicit `TESTCONTAINERS_HOST_OVERRIDE` always
wins) — the sandbox works identically on a host and in a container, nothing to configure.
Binding an api address to the sandbox is explicit — the test body calls
`endpoint.bind(sandbox)` (or `api.bind(sandbox)`);
the declared data then applies and the service liveness is ensured before every request.
Without the document nothing changes — no fixture exists, and a test requesting it fails with
pytest's standard `fixture 'sandbox' not found`. An invalid document fails the run at
configphase, before any container. `--base-url` governs every test unless the test binds its
api to the sandbox — a bound test uses the sandbox address.

## Web activation

The same `plugins.install()` call also installs the pybuggy web plugin: when the test repository
holds the web config document at `.goga/tools/pybuggy/web.yml`, the plugin provides the `web`
fixture — a per-test browser runtime for step-sentence tests (each step sentence becomes Playwright
code once, cached and replayed without any LLM involvement). The web plugin
validates the document at configphase; an invalid document fails the run before any collection.
Without the document nothing changes — no fixture exists, and a test requesting it fails with
pytest's standard "fixture 'web' not found". Run web suites with `--strict-mode` in CI (replay-only,
zero LLM calls); `--interactive` enables interactive step healing locally; `--browser-endpoint <url>`
runs the suite against a remote Playwright endpoint for that run, overriding `browser.endpoint` of
the web config (an invalid value fails the run at pytest configuration). Writing web tests means
authoring step sentences consumed by the `web` fixture (one action per sentence, full URLs); the
step cache is rooted at the run's rootdir (or the explicit `cache_root` directive) — the per-test
files under a `.cache` segment beside the test module's path, the page-method shared cache of the
pages' own methods beside the page modules — and is committed to the repository. The tested site's base
URL is the `site.base_url` directive of the web config — a Jinja2 template rendered once at pytest
configuration against the environment plus the typed CLI options (the api `base_url` pattern; the
rendered value is what the http/https validation judges), carried by the runtime and consumed by
the page objects of the web cell (`BasePage` — see the pybuggy-web usage).