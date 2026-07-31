# Configuration — plugin options

## Domain

Configuring the pybuggy plugin options that feed the `api` fixture. Target audience: test-suite authors and CI
configuration.

## Options

| Option                | Type           | Env (default)    | CLI flag               | Config key            | Default  |
|-----------------------|----------------|------------------|------------------------|-----------------------|----------|
| base_url              | str            | `QA_BASE_URL`    | `--api-url`            | base_url              | required |
| headers               | dict[str, str] | —                | —                      | headers               | `{}`     |
| timeout               | float          | `QA_API_TIMEOUT` | `--api-timeout`        | timeout               | None     |
| data_key              | str            | —                | —                      | data_key              | None     |
| error_key             | str            | —                | —                      | error_key             | None     |
| retries               | int            | —                | `--retries`            | retries               | 0        |
| assert_timeout        | int            | —                | `--api-assert-timeout` | assert_timeout        | None     |
| assert_delay          | float          | —                | `--api-assert-delay`   | assert_delay          | None     |
| assert_field_class    | str            | —                | —                      | assert_field_class    | None     |
| assert_response_class | str            | —                | —                      | assert_response_class | None     |

## Resolution priority

Each option resolves by the first non-empty source, in this order:

1. plugin config key (from `.goga/tools/pybuggy/config.yml`)
2. env variable
3. CLI flag
4. `default` (or required/None)

So a CLI flag overrides env, env overrides the config file, and the config file overrides the default.

## base_url template rendering

`base_url` is a Jinja2 template string rendered once at `pytest_configure` (the pluginator
`configure()` lifecycle hook, configphase) against the rendering context = the full
environment (`os.environ`) + the CLI options the user actually passed. Jinja2 is a required
dependency of pybuggy (declared in `pyproject.toml`), so no extra install is needed. The
rendered value is stored back onto the `base_url` option for the `api` fixture to consume.

```yaml
# .goga/tools/pybuggy/config.yml
base_url: "https://{{ env }}.svc.example/api/{{ version }}"
```

```bash
pytest --env=dev --version=1.2   # -> https://dev.svc.example/api/1.2
```

Context sources:
- **Environment** — the full `os.environ`; any variable is available as a placeholder.
- **CLI options** — only the ones the user actually typed (detected via
  `config.invocation_params.args`); values are taken from `config.option`.

Placeholders fed from the CLI (e.g. `{{ env }}`, `{{ version }}`) require the consumer to
register the matching options via `pytest_addoption` in `conftest.py` — pytest rejects
unregistered options:

```python
# conftest.py
def pytest_addoption(parser):
    parser.addoption("--env", action="store", default=None)
    parser.addoption("--version", action="store", default=None)
```

Behavior:
- An **unknown variable raises** (`jinja2.UndefinedError` via `StrictUndefined`) — URLs must
  not be silently truncated. Use only placeholders present in `os.environ` or passed on the
  CLI.
- A plain URL without Jinja placeholders renders to itself.
- **Whitespace is normalized**: every whitespace run in the rendered URL is removed (a URL
  never legitimately contains literal whitespace — it would be percent-encoded to `%20` and
  break the request path). So a multi-line template — a YAML folded scalar (`>`) or a literal
  block scalar (`|`) — renders to a single clean URL in both conditional branches, with no
  stray trailing/internal spaces from the newlines or an empty conditional block.
- Internal pytest/plugin options (150+ in `config.option`) do NOT enter the template — the
  filter keeps only the `--key` tokens the user actually typed.
- Rendering is eager: a missing required `base_url` surfaces at `configure()`
  (`pytest_configure`), not on fixture invocation.
- Conditional URL assembly works via the registered `match_re` test (regex match anchored at
  the start) — see [Conditional URL assembly](#conditional-url-assembly--match_re) below.

### Conditional URL assembly — `match_re`

Because every `base_url` is rendered with Jinja2, conditional URL assembly works out of the
box via the registered `match_re` test (regex match anchored at the start) — e.g. append a
suffix only for feature branches:

```yaml
base_url: "http://x/api/v1{% if service_version is match_re('^feature-.*$') %}-{{ service_version }}{% endif %}"
```

```bash
pytest --service-version=feature-123   # -> http://x/api/v1-feature-123
pytest --service-version=1.2.3         # -> http://x/api/v1
```

## Config file

Options live in the same yaml the pybuggy CLI reads:

```yaml
# .goga/tools/pybuggy/config.yml
base_url: https://api.example.com
headers:
  X-Custom: value
timeout: 10.0
data_key: data
error_key: error
retries: 2
assert_timeout: 10        # baseline assert-polling timeout (seconds)
assert_delay: 0.5         # delay between polling attempts (seconds)
assert_field_class: my_pkg.asserts:CustomAssertField      # optional, module:Class
assert_response_class: my_pkg.asserts:CustomExpected      # optional, module:Class
```

The file may also carry a `loader` section that overrides generated-fixture discovery (`packages`/`modules`). The
default discovery is the `api/` package (set by `install()` as `[PackageLoader("api", required=False)]`); a `loader`
section or an explicit `install(loaders=[...])` overrides it, and `install(loaders=[])` disables it. The plugin reads
its option keys and the `loader` section from the same file without conflicting with the CLI's own keys.

## Preconditions and side effects

- `base_url` is required — the suite fails to provide a working `Api` when it is unset across all sources. It is a Jinja2 template rendered once, eagerly, in `configure()` (configphase); a missing value surfaces there, not on fixture invocation.
- Most options are read lazily on fixture invocation, so env/CLI changes take effect per test run without code changes. `base_url` is the exception: it is rendered once in `configure()` against `os.environ` + the CLI options the user passed.
- `retries` is orthogonal to the `api` fixture: when set to a positive int, the plugin stamps every collected test without an existing flaky marker with `pytest.mark.flaky(max_runs=retries)` during collection. The actual reruns require the `flaky` package to be installed in the consumer suite; without it the marker is inert. A programmatic default can be supplied via `install(default_retries=N)`.
- `assert_timeout`/`assert_delay` enable assert polling: when `assert_timeout` is set, each matchcrest assertion retries (re-fetching the response via `resq.http.Response.reload()`) until it passes or the timeout elapses, sleeping `assert_delay` between attempts. They are the baseline; each `Expected`/`AssertField` check method also accepts per-call `timeout`/`delay` kwargs that override them for one assertion. `None` (default) runs each assertion once. Programmatic defaults: `install(default_assert_timeout=N, default_assert_delay=D)`.
- `assert_field_class`/`assert_response_class` are dotted `module:Class` paths selecting a custom `AssertField`/`Expected` subclass (it must subclass the built-in). The field class is loaded in `Expected.__call__`; the response class in `ResponseWrapper.expected`. `None` (default) uses the built-ins.
