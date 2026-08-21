# Pytest Plugin — Enable & Fixtures

Enabling the pybuggy plugin gives a test suite the `api` fixture, the plugin CLI options,
and automatic loading of the generated endpoint fixtures under `api/`.

## Enable the plugin

Call `goga_tool_pybuggy.plugin.install()` from the root `conftest.py`:

```python
# conftest.py
from dotenv import load_dotenv

load_dotenv()

from goga_tool_pybuggy import plugin

plugin.install()
```

`load_dotenv()` runs before `install()` so plugin options (resolved from `os.environ`)
see the `.env` values; the argumentless call keeps `override=False` (CI/operator-exported
variables win).

> There is **no import-time auto-wiring**: `pytest_plugins = ["goga_tool_pybuggy.plugin"]`
> alone does NOT enable the plugin — the explicit `install()` call is required.

`goga tool pybuggy init` generates this `conftest.py` for you (see
[CLI — init](../cli/init.md)).

## What enabling wires

- **CLI options** — `--base-url` (resolves `base_url`, required; a typed flag overrides
  the config-file and `QA_BASE_URL` value), `--api-timeout` (resolves `timeout`),
  `--retries` (the flaky rerun count), `--api-assert-timeout` / `--api-assert-delay`
  (the assert-polling baseline). The remaining options (`headers`, `data_key`,
  `error_key`, `assert_field_class`, `assert_response_class`) have no CLI flag —
  config-file only. See [Configuration](../configuration.md).
- **`base_url` template** — a Jinja2 template rendered once at `pytest_configure`
  against `os.environ` + the CLI options you actually passed. Placeholders fed from the
  CLI require registering those options via `pytest_addoption` in `conftest.py`.
- **Flaky reruns** — when `retries` resolves to a positive int, every collected test
  without an existing flaky marker is stamped with `pytest.mark.flaky(max_runs=retries)`.
  The reruns take effect when the `flaky` package is installed in the consumer suite; a
  programmatic default can be passed as `install(default_retries=N)`.
- **The `api` fixture** — function-scoped, yields an [`Api`](../api/index.md) built from
  the resolved options and closes it after the test. Generated endpoint fixtures depend
  on it; pytest resolves `api` automatically — no extra wiring:

  ```python
  @pytest.fixture(scope="function")
  def get_orders(api: Api) -> Endpoint:
      return Endpoint(api, "/orders", method="GET")
  ```

- **Recursive generated-fixture loading** — `install()` defaults
  `loaders` to `[PackageLoader("api", required=False)]`, so every generated
  `api/<spec>/<id>/api.py` module is discovered and loaded through the recursive
  `pytest_plugins` list, out of the box.

## Overriding discovery

Pass an explicit `loaders` to `install()`, or add a `loader` section to the config to do
it declaratively (details: [Loaders](loaders.md)):

```python
goga_tool_pybuggy.plugin.install(loaders=[PackageLoader("api"), PackageLoader("service")])
goga_tool_pybuggy.plugin.install(loaders=[])   # disable discovery entirely
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

- The `api/` tree is discovered by default; a missing tree is tolerated
  (`required=False`).
- The plugin reads `.goga/tools/pybuggy/config.yml` at import; a missing file is
  tolerated (defaults apply).
- Loader paths walk the filesystem relative to the **current working directory** (while
  candidate imports go through `sys.path`). Run `pytest` from the project root — the
  directory that both contains `api/` and is on `sys.path`. Running from another
  directory makes discovery silently return `[]`, so generated fixtures are not loaded
  and tests fail with `fixture '<name>' not found`.

## Test reruns

Two mechanisms exist:

- **Suite-wide** — the `retries` option (or `install(default_retries=N)`) stamps every
  collected test without an existing flaky marker; requires the `flaky` package in the
  suite.
- **Per-test decorator** — the facade `retries` decorator (see
  [Home — test reruns](../index.md#test-reruns)): `@retries(max_runs=3, min_passes=2, delay=1)`.
