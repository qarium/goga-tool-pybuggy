# Plugin — Loaders

The discovery primitives behind the plugin's generated-fixture loading: finding
pytest-plugin modules inside a package tree or a single module file, and assembling the
recursive `pytest_plugins` list from the [configuration](../configuration.md).

```python
from goga_tool_pybuggy.plugins.loaders import BaseLoader, PackageLoader, ModuleLoader
```

## The loaders

`PackageLoader` walks a package directory; `ModuleLoader` inspects one module file. Both
share the `name`/`required` constructor fields and the abstract `BaseLoader` contract
(`from_config` factory + `load`). `load` mutates the accumulator list passed to it and
returns nothing.

## Building a loader from config

`from_config` accepts a bare dotted name or a mapping:

```python
PackageLoader.from_config("api")  # required=True
PackageLoader.from_config({"name": "api", "required": False})  # mapping form
ModuleLoader.from_config("my_plugin.conftest")

PackageLoader("api")  # positional construction; required=True (default)
ModuleLoader("my_plugin.conftest")
```

## Discovering modules

```python
modules: list[str] = []

PackageLoader.from_config({"name": "api", "required": False}).load(modules)
# modules -> ['api.orders.get_orders.api', 'api.users.create_user.api', ...]

ModuleLoader.from_config("my_plugin.conftest").load(modules)
# appends 'my_plugin.conftest' when it is a pytest plugin
```

## The `loader` config section

The section is accepted by **every tool document** — `api.yml`, `sandbox.yml`, and
`web.yml` — so external fixture packages can be wired into any test kind through the
config, without touching the conftest:

```yaml
loader:
  packages:
    - api                       # bare dotted name → required=True by default
    - name: generated.fixtures  # mapping form → required taken from the item
      required: false
  modules:
    - my_plugin.conftest
```

- `packages` — dotted package names to walk recursively (every subdir with
  `__init__.py`).
- `modules` — single dotted module files.
- Each item is a `str` (required defaults to True) or a mapping `{name, required}`.
- Both lists default to empty when the section is absent; explicit loaders (from the
  section or a `loaders=` argument) reach **every active plugin's** discovery — api,
  sandbox, and web alike.
- Without explicit loaders the api and web plugins apply their own defaults: the api
  plugin adds `[PackageLoader("api", required=False)]` (every generated
  `api/<spec>/<id>/api.py` module), the web plugin adds
  `[PackageLoader("pages", required=False)]` (every `page generate` page-object module
  under `pages/`) — both fixture trees are discovered out of the box;
  `install(loaders=[])` disables discovery entirely.

## Preconditions and side effects

- A module counts as a pytest plugin when it exposes a public `pytest_`-prefixed
  attribute (a hook) or an attribute carrying a pytest-fixture marker. Detection uses a
  trial import.
- `required=True` (default) raises `OSError` (package) / `FileNotFoundError` (module)
  when the target is missing; `required=False` is a no-op.
- A directory is walked only when it contains `__init__.py`.
- Trial imports do not pollute `sys.modules`: a module (and any ancestor package) absent
  before the probe is removed afterwards.
- Loaders run synchronously at `install()` time; each `load` mutates the shared
  accumulator in place.
