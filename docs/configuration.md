# Configuration

pybuggy reads a single YAML file — `.goga/tools/pybuggy/config.yml` — from a **fixed
path** relative to the project root. There is no `--config` option; every command loads
the config itself via `load_config()`.

The file carries three concerns: the **plugin options** (feed the `api` fixture), the
**`specs`** section (what the CLI commands operate on), and the optional **`loader`**
section (generated-fixture discovery).

## Plugin options

| Option                | Type           | Env (default)    | CLI flag               | Default  |
|-----------------------|----------------|------------------|------------------------|----------|
| `base_url`            | `str`          | `QA_BASE_URL`    | `--base-url`           | required |
| `headers`             | `dict[str, str]` | —              | —                      | `{}`     |
| `timeout`             | `float`        | `QA_API_TIMEOUT` | `--api-timeout`        | `None`   |
| `data_key`            | `str`          | —                | —                      | `None`   |
| `error_key`           | `str`          | —                | —                      | `None`   |
| `retries`             | `int`          | —                | `--retries`            | `0`      |
| `assert_timeout`      | `int`          | —                | `--api-assert-timeout` | `None`   |
| `assert_delay`        | `float`        | —                | `--api-assert-delay`   | `None`   |
| `assert_field_class`  | `str`          | —                | —                      | `None`   |
| `assert_response_class` | `str`        | —                | —                      | `None`   |

### Resolution priority

Each option resolves by the first non-empty source:

1. the plugin config key (this file)
2. the environment variable
3. the CLI flag
4. the default (or required/None)

So the config file overrides env, env overrides the CLI flag, the flag overrides the
default. **`base_url` is the exception** — when you actually type `--base-url`, its value
wins over the config file and `QA_BASE_URL`.

### `base_url` as a Jinja2 template

`base_url` is rendered **once**, eagerly, at `pytest_configure` against
`os.environ` + the CLI options you actually passed:

```yaml
base_url: "https://{{ env }}.svc.example/api/{{ version }}"
```

```bash
pytest --env=dev --version=1.2   # -> https://dev.svc.example/api/1.2
```

Placeholders fed from the CLI (e.g. `{{ env }}`) require registering the options in
`conftest.py` (pytest rejects unregistered flags):

```python
def pytest_addoption(parser):
    parser.addoption("--env", action="store", default=None)
```

Behavior:

- An unknown variable **raises** (`StrictUndefined`) — URLs are never silently truncated.
- Every whitespace run in the rendered URL is removed — multi-line YAML scalars (`>`/`|`)
  render to one clean URL.
- Internal pytest/plugin options do not enter the template — only the flags you typed.
- Conditional assembly works via the registered `match_re` test (regex anchored at the
  start):

  ```yaml
  base_url: "http://x/api/v1{% if service_version is match_re('^feature-.*$') %}-{{ service_version }}{% endif %}"
  ```

### Assert polling

`assert_timeout`/`assert_delay` are the **baseline** for matchcrest assertion polling:
when `assert_timeout` is set, each assertion retries — re-fetching the response by
replaying the request — until it passes or the timeout elapses. `None` (default) runs
each assertion once. Per-check `timeout`/`delay` kwargs override the baseline for a
single call (see [Assertions — polling](api/asserts.md#polling)).

### Pluggable assert classes

`assert_field_class` / `assert_response_class` are dotted `module:Class` paths selecting
custom `AssertField`/`Expected` subclasses (they must subclass the built-ins):

```yaml
assert_field_class: my_pkg.asserts:CustomAssertField
assert_response_class: my_pkg.asserts:CustomExpected
```

## The `specs` section

Each entry describes one specification:

```yaml
specs:
  shop:
    type: openapi                                     # swagger | openapi (declarative)
    location: .specs/openapi/shop/shop-openapi.yaml   # project-root-relative (required)
    git:                                              # optional; absent → local spec
      url: https://git.example.com/specs/shop.git     # clone URL, no embedded tokens
      location: openapi/shop-openapi.yaml             # path inside the repository
      ref: main                                      # optional; None → default branch
```

- The dict key (`shop`) is the spec name used by output and the `--spec` filters.
- `type` is declarative — parsing auto-detects the actual version
  (see [Spec Parsing](internals/spec.md)).
- A spec without `git` is local-only: `pull` skips it, the other commands read
  `location` directly.
- `git.ref` is the default ref for cloning; `--ref` overrides it (priority:
  `--ref` > `git.ref` > default branch — see [pull](cli/pull.md)).

## The `loader` section

Overrides the generated-fixture discovery of the plugin (default: the `api/` package,
missing tree tolerated):

```yaml
loader:
  packages:
    - name: api        # walk the api/ package tree (dots map to path separators)
      required: false  # tolerate a missing tree
  modules:
    - my_plugin.conftest
```

Details: [Plugin — loaders](plugin/loaders.md).

## Loading

```python
from goga_tool_pybuggy.config import load_config

config = load_config(path)   # path is project-root-relative; None → the fixed path
```

The file is read with `yaml.safe_load` and validated into the typed `Config` model; an
invalid configuration raises a pydantic validation error. Scalar plugin keys are ignored
by `Config` (`extra=ignore`) — the same file safely serves both the CLI and the plugin.

```python
for name, entry in config.specs.items():
    entry.location   # project-root-relative path to the spec file
    entry.git        # Optional[GitEntry]; None → local spec
    entry.git.url    # clone URL
    entry.git.location   # path inside the repository
    entry.git.ref    # Optional[str]; None → default branch
```
