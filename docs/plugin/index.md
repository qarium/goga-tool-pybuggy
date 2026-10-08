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

`goga tool pybuggy init` generates this `conftest.py` for you when it is absent — an
existing file is kept (bare mode: unless you confirm the overwrite) — see
[CLI — init](../cli/init.md).

The same `install()` call arms the **sandbox**: when
`.goga/tools/pybuggy/sandbox.yml` exists under the pybuggy tools home, it starts before
the first test, the `api` fixture's address resolves to the sandbox service, and every
request first applies the test's pending sandbox data (see
[Sandbox](../sandbox.md)).

## What enabling wires

- **CLI options** — `--base-url` (resolves `base_url`, required; a typed flag overrides
  the config-file and `BASE_URL` value; it fails fast with a usage error when the sandbox
  is active — `.goga/tools/pybuggy/sandbox.yml` present — because the sandbox owns the
  service address),
  `--api-timeout` (resolves `timeout`),
  `--retries` (the flaky rerun count), `--api-assert-timeout` / `--api-assert-delay`
  (the assert-polling baseline). The remaining options (`headers`,
  `assert_field_class`, `assert_response_class`) have no CLI flag —
  config-file only. See [Configuration](../configuration.md).
- **`base_url` template** — a Jinja2 template rendered once at `pytest_configure`
  against `os.environ` + the CLI options you actually passed. Placeholders fed from the
  CLI require registering those options via `pytest_addoption` in `conftest.py`.
- **Flaky reruns** — when `retries` resolves to a positive int, every collected test
  without an existing flaky marker is stamped with `pytest.mark.flaky(max_runs=retries)`.
  The reruns take effect when the `flaky` package is installed in the consumer suite; a
  programmatic default can be passed as `install(default_retries=N)`.
- **The `api` fixture** — function-scoped, yields the HTTP client built from
  the resolved options and closes it after the test. With an active sandbox the
  sandbox's service address wins `base_url` at read time (the option value stays
  untouched) and every request passes the sandbox guard first — pending data is
  applied, the service liveness is ensured, then the original request runs; a died
  service fails the request with the service output attached. Generated endpoint
  fixtures depend on it; pytest resolves `api` automatically — no extra wiring:

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

- A sandbox document at `.goga/tools/pybuggy/sandbox.yml` activates the sandbox on the
  same `install()` call; the environment then needs a docker-compatible container
  runtime (see [Sandbox](../sandbox.md)).
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
- **Per-test decorator** — the facade `retries` decorator (`from goga_tool_pybuggy
  import retries`; built on the `flaky` package): `@retries(max_runs=3, min_passes=2,
  delay=1)` reruns a flaky test up to `max_runs` times requiring `min_passes`
  successes, pausing `delay` seconds between reruns.
