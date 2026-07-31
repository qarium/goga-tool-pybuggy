# Discovery — finding pytest-plugin modules with loaders

## Domain

Directly discovering pytest-plugin modules inside a package tree or a single module file, by appending their dotted
names into an accumulator list. Target audience: plugin authors building custom registration logic on top of the
loaders.

## Loaders

`PackageLoader` walks a package directory; `ModuleLoader` inspects one module file. Both inherit `PythonImportLoader`
(`name` + `required`) and the abstract `BaseLoader` contract (`from_config` factory + `load`). `load` mutates the
accumulator list passed to it and returns nothing.

```python
from pybuggy.plugin.loaders import PackageLoader, ModuleLoader
```

## Build a loader from a config item

`from_config` accepts a bare dotted name or a mapping:

```python
PackageLoader.from_config("api")                           # required=True
PackageLoader.from_config({"name": "api", "required": False})
ModuleLoader.from_config("my_plugin.conftest")
```

A loader may also be constructed directly with the positional `name`:

```python
PackageLoader("api")                                       # required=True (default)
ModuleLoader("my_plugin.conftest")
```

## Discover modules

```python
modules: list[str] = []

PackageLoader.from_config({"name": "api", "required": False}).load(modules)
# modules -> ['api.orders.get_orders.api', 'api.users.create_user.api', ...]

ModuleLoader.from_config("my_plugin.conftest").load(modules)
# appends 'my_plugin.conftest' when it is a pytest plugin
```

## Preconditions and side effects

- A module counts as a pytest plugin when it exposes a public `pytest_`-prefixed attribute (a hook) or an attribute
  carrying a pytest-fixture marker. Detection uses a trial import.
- `required=True` (default) raises `OSError` (package) / `FileNotFoundError` (module) when the target is missing;
  `required=False` is a no-op (appends nothing) instead.
- A directory is walked only when it contains `__init__.py`.
- Trial imports do not pollute `sys.modules`: a module (and any ancestor package) absent before the probe is removed
  afterwards.
