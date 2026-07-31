# Enable — wiring the pybuggy plugin into a pytest suite

## Domain

Enabling the pybuggy plugin so a test suite gets the `api` fixture, the plugin CLI options, and automatic loading of
the generated endpoint fixtures under `api/`. Target audience: test-suite and infrastructure authors.

## Enable the plugin

Call `pybuggy.plugin.install()` from the root `conftest.py`:

```python
# conftest.py
import pybuggy.plugin

pybuggy.plugin.install()
```

`install()` resolves the caller's (conftest) namespace through `call_context()` and injects the pytest hooks
(`pytest_addoption` / `pytest_configure` / `pytest_collection_finish`) into it, then synchronously fills its
`pytest_plugins` with the discovered generated fixtures. Pass an explicit `install(loaders=[...])` to override
discovery, or `install(loaders=[])` to disable it.

> There is **no import-time auto-wiring**: `pytest_plugins = ["pybuggy.plugin"]` alone does NOT enable the plugin —
> the explicit `install()` call is required.

## What enabling wires

- **CLI options** — `--api-url` (resolves `base_url`, required), `--api-timeout` (resolves `timeout`),
  `--retries` (resolves `retries`, the flaky rerun count for the test run), `--api-assert-timeout`
  (resolves `assert_timeout`, the baseline assert-polling timeout), and `--api-assert-delay` (resolves
  `assert_delay`, the delay between polling attempts). The remaining options (`headers`, `data_key`,
  `error_key`, `assert_field_class`, `assert_response_class`) have no CLI flag and are set only via the
  config file.
- **`base_url` template** — `base_url` is a Jinja2 template rendered once in the pluginator `configure()`
  hook against `os.environ` + the CLI options the user actually passed. Placeholders that should be fed
  from the CLI (e.g. `{{ env }}`, `{{ version }}`) require the consumer to register those options via
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
  (calling `Api.close()` to release the underlying resq session's connection pool). Generated endpoint
  fixtures depend on it:
  ```python
  @pytest.fixture(scope="function")
  def get_orders(api: Api) -> Endpoint:
      return Endpoint(api, "/orders", method="GET")
  ```
  pytest resolves `api` automatically; no extra wiring is needed in tests.
- **Recursive generated-fixture loading** — `install()` defaults `loaders` to `[PackageLoader("api", required=False)]`,
  so every generated `api/<spec>/<id>/api.py` module is discovered and loaded through the recursive `pytest_plugins`
  list, out of the box.

## Overriding discovery

Pass an explicit `loaders` to `install()` to change the discovered trees, or add a `loader` section to the config to
do it declaratively:

```python
pybuggy.plugin.install(loaders=[PackageLoader("api"), PackageLoader("service")])
# or disable discovery entirely:
pybuggy.plugin.install(loaders=[])
```

```yaml
# .goga/tools/pybuggy/config.yml
loader:
  packages:
    - name: api        # walk the api/ package tree (dots map to path separators)
      required: false  # tolerate a missing tree
  modules:
    - my_plugin.conftest
```

## Preconditions and side effects

- The `api/` tree is discovered by default; a missing tree is tolerated (`required=False`).
- The plugin reads `.goga/tools/pybuggy/config.yml` at import; a missing file is tolerated (defaults apply).
- Loader paths walk the filesystem relative to the **current working directory** (while the plugin probe imports
  candidates through `sys.path`). Run `pytest` from the project root — the directory that both contains `api/` and
  is on `sys.path`. Running from another directory makes discovery silently return `[]`, so generated fixtures are
  not loaded and tests fail with `fixture '<name>' not found`.