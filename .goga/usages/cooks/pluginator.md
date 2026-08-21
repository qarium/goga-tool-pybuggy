# pluginator — a pytest-plugin framework

## Domain

`pluginator` is a framework for declaring pytest plugins: options (env / config / CLI / default), fixtures as plugin-class methods, actions (`actions`), and a single-step installation into pytest via hook injection. Cell `goga_tool_pybuggy/plugin` uses it to provide the `api` fixture and to register the generated fixtures.

Import in code:
```python
from pluginator import define, CommandLine, Action, ActionContext
from pluginator import install_pytest_plugins, call_context
```

---

## @define.plugin — the plugin class

`define.plugin` is a class decorator. It sets the plugin name, the yaml config path, the default config, and the lists of dependencies and actions. The decorator mixes `BasePlugin` into the class bases and places `__meta__: PluginMeta` on the class. The plugin reads its config lazily via `plugin_config` (see below).

```python
@define.plugin("pybuggy", config=".goga/tools/pybuggy/config.yml")
class PyBuggyPlugin:
    plugin_config: dict  # the parsed yaml lands in this attribute (see BasePlugin.plugin_config)

    base_url = define.option(str, env_var="QA_BASE_URL", command_line=CommandLine("--base-url"))
```

- `define.plugin(name, /, *, config=None, default_config=None, deps=None, actions=None)`.
- `config` — a relative path to the yaml file; the plugin reads it via `plugin_config` (see below).
- The plugin class must declare a `plugin_config: dict` attribute (an "anchor" declaration; `BasePlugin.plugin_config` supplies the real dict).

---

## define.option — a plugin option

`define.option` is a descriptor (`PluginOption`) declaring a configurable field of the plugin class. The descriptor resolves the value lazily, on access via `self.<option>`.

```python
base_url = define.option(
    str,
    env_var="QA_BASE_URL",
    plugin_config_key="base_url",
    command_line=CommandLine("--base-url", action="store", help="Base URL"),
    default_from="_default_base_url",
    nullable=True,
)
```

- `define.option(opt_type, /, *, strict=True, nullable=False, required=False, env_var=None, default_from=None, plugin_config_key=None, command_line=None, hook=None)`.
- `default_from` — the name of a plugin-class property/attribute supplying the default.

**The value resolve chain** (strict order; the first non-empty source wins — `PluginOption.__get__`):

1. `plugin_config_key` → the value from the plugin's yaml config (`plugin_config.get(key, ...)`).
2. `env_var` → `os.getenv(env_var)`.
3. `command_line` → `pytest_config.getoption(opt)`.
4. `default_from` → `getattr(plugin, default_from)`.
5. otherwise: `required` → `ValueError`; `nullable` → `None`; else `opt_type()` (an empty value).

The resolved value passes through the `hook` (when set), and the descriptor coerces it to `opt_type` (`strict=True`).

---

## plugin_config — reading yaml

`BasePlugin.plugin_config` (a `cached_property`) reads `meta.config_file` and merges the file with `meta.default_config` (`default_config | loaded`). When the file is absent, the property returns only `default_config` (or `{}`). Consequently, options with a `plugin_config_key` take values from `.goga/tools/pybuggy/config.yml`, and `default_config` supplies the built-in defaults.

---

## Fixtures — plugin-class methods

Fixtures are plain plugin-class methods decorated with `@pytest.fixture`. The plugin installation carries the fixtures into pytest. A fixture resolves dependencies on other fixtures via `request.getfixturevalue("<name>")` — the external fixture's name — which avoids hardcoding the signature:

```python
@pytest.fixture(scope="function")
def api(self, request: pytest.FixtureRequest):
    return Api(
        base_url=self.base_url,
        headers=self.headers,
        timeout=self.timeout,
        data_key=self.data_key,
        error_key=self.error_key,
    )
```

---

## install_pytest_plugins + call_context — installation

`install_pytest_plugins(*plugins, check_deps=True, context=None)` injects three hooks into `context`: `pytest_addoption` (registers the CLI options of all plugins), `pytest_configure` (initializes the config, registers the plugins with the `pluginmanager`, and calls `configure()` when the method exists), and `pytest_collection_finish` (an optional `deps` check). `context` is the module's dict namespace — usually the plugin module's or a conftest's globals — where the hooks land.

`call_context()` fetches the calling module's globals via `inspect.stack()[2][0].f_globals`. Therefore **call it through a one-level wrapper** `install()` — then `stack[2]` points at the module that invoked the wrapper:

```python
def install(**kwargs):
    kwargs.setdefault("context", call_context())
    install_pytest_plugins(PyBuggyPlugin(**kwargs), context=kwargs["context"])
```

---

## configure() — the configuration lifecycle hook

Inside the injected `pytest_configure` (after `init_pytest_config(config)` and `install()`), pluginator calls `plugin.configure()` with no arguments when the plugin defines the method. `configure()` is the idiomatic place for one-time preparation that needs an already-installed pytest config:

```python
def pytest_configure(config: Config):      # the install_pytest_plugins wrapper injects this into context
    ctx_pytest_configure(config)
    for plugin in plugins:
        plugin.init_pytest_config(config)   # ① plugin.pytest_config becomes available
        plugin.install()                     # ② registration with the pluginmanager
        configure_callback = getattr(plugin, "configure", None)
        if configure_callback is not None:
            configure_callback()             # ③ called with no arguments when the method exists
```

`configure()` is a **plain method**, NOT `@pytest.hookimpl`. pluginator finds it via `getattr(plugin, "configure", None)` and calls it with no arguments. The call runs in the configphase — before collection and before any fixture.

`BasePlugin.pytest_config` is a property; the property raises an `AssertionError` until `init_pytest_config` has run. Therefore, inside `configure()` — and only after `init_pytest_config` — reading `self.pytest_config` is safe.

CLI sources for config-time rendering/logic:
- `config.invocation_params.args` — the raw CLI tokens (what the user actually typed).
- `config.option` — a namespace holding the values of all registered options.

```python
@define.plugin("myplugin", config="config.yml")
class MyPlugin:
    plugin_config: dict

    def configure(self):
        # self.pytest_config is already set — init_pytest_config ran above
        names = {
            token.strip("-").split("=", 1)[0].replace("-", "_")
            for token in self.pytest_config.invocation_params.args
            if token.startswith("-")
        }
        context = {
            n: getattr(self.pytest_config.option, n)
            for n in names
            if hasattr(self.pytest_config.option, n)
        }
        self.rendered = self.template.format_map(context)
```

Important: the injected wrapper runs `pytest_addoption` (option registration) BEFORE `pytest_configure`. pytest rejects an arbitrary "bare" option — one without `pytest_addoption` (or without `command_line` on a `define.option`) — before any hook runs (`unrecognized arguments`). Therefore the consumer registers its own placeholder options itself via `pytest_addoption` in conftest.

---

## The installation pattern via pytest_plugins

The consumer attaches the plugin with one line in `conftest.py`:

```python
# conftest.py
pytest_plugins = ["goga_tool_pybuggy.plugin"]
```

— the plugin module (`<package>/__init__.py`) calls the `install()` wrapper **at the top level**. On import of `goga_tool_pybuggy.plugin`, `call_context()` resolves to that same module's globals; the hooks (`pytest_addoption`/`pytest_configure`/`pytest_collection_finish`) are injected into the `goga_tool_pybuggy.plugin` namespace, and pytest finds them.

The same trick registers the **generated fixtures**: the loader — running inside `install()` — places the list of discovered modules into `context["pytest_plugins"]` (i.e. `goga_tool_pybuggy.plugin.pytest_plugins`), and pytest loads them recursively. Therefore the loader must run synchronously at import time.

Important: importing the plugin module outside a pytest project must not crash — the loader works around the missing `api/` package with `required=False`.

---

## CommandLine — a pytest CLI option

`CommandLine(opt, *args, **kwargs)` wraps `parser.addoption`. `define.option` registers the option automatically via `command_line=...`. The option joins a group named after the plugin; a repeated registration of the same `opt` is skipped (`register_once`).

```python
CommandLine("--base-url", action="store", help="Base URL of the service under test")
```

---

## Actions — an extension point (optional)

`Action(name, module, *, enable=True, default_config=None)` is a lazily-imported action. `module` is a dotted path to a module that provides a `main(context, config)` function (and optionally `setup(config)`). The plugin invokes the action via `plugin.action(name, context, lazy=True/False)`; with `lazy=True` the call returns a closure that finalizes the context at call time. Cell `goga_tool_pybuggy/plugin` does not use actions — documented for completeness of the framework picture.

---

## What pybuggy does NOT use

- `deps`/`check_deps` — inter-plugin dependency checks (pybuggy ships one plugin; the plugin has no dependencies).
- `actions` — deferred actions (not needed: `Api` issues a single request, without polling/collector).
- `hook` on `define.option` — option-value post-processing (the options are simple; the type coerces them).
