# Registration — assembling `pytest_plugins` from a plugin config

## Domain

Assembling the recursive `pytest_plugins` list a pytest plugin exposes, from the `loader` section of its yaml config
and any explicit loaders passed at install time. Target audience: plugin authors and plugin cells that need pytest to
auto-load discovered fixture modules (e.g. a generated `api/.../api.py` fixture tree).

## The `loader` config section

The consumer reads a `loader` section from the plugin's raw yaml config:

```yaml
loader:
  packages:
    - api                       # bare dotted name → required=True by default
    - name: generated.fixtures  # mapping form → required taken from the item
      required: false
  modules:
    - my_plugin.conftest
```

- `packages` — dotted package names to walk recursively (every subdir with `__init__.py`).
- `modules` — single dotted module files.
- Each item is a `str` (required defaults to True) or a mapping `{name, required}`.
- Both `packages` and `modules` default to empty when the section is absent; `install()` then falls back to its
  built-in default `loaders = [PackageLoader("api", required=False)]`, so the `api/` tree is discovered out of the box.

## Explicit loaders

The plugin's `install()` entry point defaults `loaders` to `[PackageLoader("api", required=False)]` when omitted. Pass
an explicit `loaders` to override, or `loaders=[]` to disable discovery:

```python
from pybuggy.plugin.loaders import PackageLoader

install(loaders=[PackageLoader("api")])   # override the default
install(loaders=[])                       # disable discovery
```

## The context contract

`context` is the namespace dict the plugin installs its hooks into (typically the plugin module globals). The routine
reads `context['pytest_plugins']` as the starting list and writes the deduplicated result back to the same key.

## How it is wired

The registration routine runs synchronously from the plugin constructor, so `context['pytest_plugins']` is populated
before the module finishes loading:

1. Read the `loader` section of the plugin config.
2. Build `PackageLoader`/`ModuleLoader` from its `packages`/`modules` via `from_config`.
3. Prepend the explicit `loaders`, then drive each `loader.load(modules)` to append discovered dotted names into the
   accumulator.
4. Deduplicate and write back to `context['pytest_plugins']`.

So the plugin's `install(...)` entry point only needs to forward `context` and `loaders` (both defaulted) to the plugin
class:

```python
def install(**kwargs):
    kwargs.setdefault("context", call_context())
    kwargs.setdefault("loaders", [PackageLoader("api", required=False)])  # discover api/ out of the box
    plugin = Plugin(**kwargs)                          # constructor runs registration
    install_pytest_plugins(plugin, context=kwargs["context"])
```

## Preconditions and side effects

- Must run synchronously at import time — callers rely on `context['pytest_plugins']` being populated before the
  module finishes loading.
- Tolerates a missing `loader` section (no error); the `api/` package is then discovered via the `install()` default
  `loaders`, unless the caller passed `loaders=[]` to disable it.
- Mutates `context['pytest_plugins']` in place.
