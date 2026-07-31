# pluginator — фреймворк pytest-плагинов

## Предметная область

`pluginator` — фреймворк для декларативного описания pytest-плагинов: опции (env / конфиг /
CLI / дефолт), фикстуры как методы класса-плагина, действия (`actions`) и единая установка в
pytest через инъекцию хуков. Используется ячейкой `goga_tool_pybuggy/plugin`, чтобы предоставить фикстуру
`api` и зарегистрировать сгенерированные фикстуры.

Импорт в коде:
```python
from pluginator import define, CommandLine, Action, ActionContext
from pluginator import install_pytest_plugins, call_context
```

---

## @define.plugin — класс-плагин

`define.plugin` — декоратор класса. Задаёт имя, путь к yaml-конфигу, дефолтный конфиг, список
зависимостей и действий. Декоратор подмешивает `BasePlugin` в базы и кладёт `__meta__: PluginMeta`
в класс. Конфиг читается лениво через `plugin_config` (см. ниже).

```python
@define.plugin("pybuggy", config=".goga/tools/pybuggy/config.yml")
class PyBuggyPlugin:
    plugin_config: dict  # сюда плагин кладёт распарсенный yaml (см. BasePlugin.plugin_config)

    base_url = define.option(str, env_var="QA_BASE_URL", command_line=CommandLine("--api-url"))
```

- `define.plugin(name, /, *, config=None, default_config=None, deps=None, actions=None)`.
- `config` — относительный путь к yaml-файлу; читается через `plugin_config` (см. ниже).
- Класс должен иметь атрибут `plugin_config: dict` (декларация-«якорь»; реальный dict даёт
  `BasePlugin.plugin_config`).

---

## define.option — опция плагина

`define.option` — дескриптор (`PluginOption`), объявляющий настраиваемое поле класса-плагина.
Значение вычисляется лениво при доступе через `self.<option>`.

```python
base_url = define.option(
    str,
    env_var="QA_BASE_URL",
    plugin_config_key="base_url",
    command_line=CommandLine("--api-url", action="store", help="Base URL"),
    default_from="_default_base_url",
    nullable=True,
)
```

- `define.option(opt_type, /, *, strict=True, nullable=False, required=False, env_var=None,
  default_from=None, plugin_config_key=None, command_line=None, hook=None)`.
- `default_from` — имя свойства/атрибута класса-плагина, дающего дефолт.

**Цепочка резолва значения** (порядок строгий, первый непустой выигрывает —
`PluginOption.__get__`):

1. `plugin_config_key` → значение из yaml-конфига плагина (`plugin_config.get(key, ...)`).
2. `env_var` → `os.getenv(env_var)`.
3. `command_line` → `pytest_config.getoption(opt)`.
4. `default_from` → `getattr(plugin, default_from)`.
5. иначе: `required` → `ValueError`; `nullable` → `None`; иначе `opt_type()` (пустое значение).

Значение проходит через `hook` (если задан) и приводится к `opt_type` (`strict=True`).

---

## plugin_config — чтение yaml

`BasePlugin.plugin_config` (`cached_property`) читает `meta.config_file`, объединяет с
`meta.default_config` (`default_config | loaded`). Когда файл отсутствует — возвращает только
`default_config` (или `{}`). Таким образом опции с `plugin_config_key` берут значения из
`.goga/tools/pybuggy/config.yml`, а `default_config` задаёт встроенные дефолты.

---

## Фикстуры — методы класса-плагина

Фикстуры — обычные методы класса-плагина, декорированные `@pytest.fixture`. Они попадают в pytest
вместе с установкой плагина. Зависимости от других фикстур разрешаются через
`request.getfixturevalue("<name>")` (имя внешней фикстуры), что позволяет не хардкодить сигнатуру:

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

## install_pytest_plugins + call_context — установка

`install_pytest_plugins(*plugins, check_deps=True, context=None)` инжектит в `context` три хука:
`pytest_addoption` (регистрирует CLI-опции всех плагинов), `pytest_configure` (инициализирует
конфиг и регистрирует плагины в `pluginmanager`, вызывает `configure()` если есть),
`pytest_collection_finish` (опциональная проверка `deps`). `context` — это `dict`-неймспейс
модуля (обычно globals модуля-плагина или conftest), куда и ложатся хуки.

`call_context()` достаёт globals вызывающего модуля через `inspect.stack()[2][0].f_globals`.
Поэтому **вызывать его нужно через одноуровневую обёртку** `install()` — тогда `stack[2]` указывает
на модуль, в котором вызвана обёртка:

```python
def install(**kwargs):
    kwargs.setdefault("context", call_context())
    install_pytest_plugins(PyBuggyPlugin(**kwargs), context=kwargs["context"])
```

---

## configure() — lifecycle-хук конфигурации

pluginator в инжектированном `pytest_configure` (после `init_pytest_config(config)` и
`install()`) вызывает `plugin.configure()` без аргументов, если метод определён. Это
идиоматичное место для одноразовой подготовки, которой нужен уже установленный
pytest-config:

```python
def pytest_configure(config: Config):      # инжектируется в context обёрткой install_pytest_plugins
    ctx_pytest_configure(config)
    for plugin in plugins:
        plugin.init_pytest_config(config)   # ① plugin.pytest_config становится доступен
        plugin.install()                     # ② регистрация в pluginmanager
        configure_callback = getattr(plugin, "configure", None)
        if configure_callback is not None:
            configure_callback()             # ③ вызывается без аргументов, если метод есть
```

`configure()` — это **обычный метод**, НЕ `@pytest.hookimpl`. pluginator находит его через
`getattr(plugin, "configure", None)` и зовёт без аргументов. Выполняется в фазе configphase
— раньше collection и любых фикстур.

`BasePlugin.pytest_config` — property; поднимает `AssertionError`, пока `init_pytest_config`
не отработал. Поэтому внутри `configure()` (и только после `init_pytest_config`) безопасно
читать `self.pytest_config`.

Источники CLI для рендеринга/логики на config-time:
- `config.invocation_params.args` — сырые токены CLI (что пользователь реально набрал).
- `config.option` — namespace со значениями всех зарегистрированных опций.

```python
@define.plugin("myplugin", config="config.yml")
class MyPlugin:
    plugin_config: dict

    def configure(self):
        # self.pytest_config уже установлен — init_pytest_config отработал выше
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

Важно: `pytest_addoption` (регистрация опций) выполняется инжектируемой обёрткой ДО
`pytest_configure`. Произвольная «голая» опция без `pytest_addoption` (или `command_line`
у `define.option`) отвергается pytest ещё до хуков (`unrecognized arguments`). Поэтому
свои опции-плейсхолдеры потребитель регистрирует сам через `pytest_addoption` в conftest.

---

## Паттерн установки через pytest_plugins

Чтобы потребитель подключал плагин одной строкой в `conftest.py`:

```python
# conftest.py
pytest_plugins = ["goga_tool_pybuggy.plugin"]
```

— обёртка `install()` вызывается **на верхнем уровне** модуля-плагина (`<пакет>/__init__.py`). При
импорте `goga_tool_pybuggy.plugin` `call_context()` резолвится в globals этого же модуля, хуки
(`pytest_addoption`/`pytest_configure`/`pytest_collection_finish`) инжектятся в неймспейс
`goga_tool_pybuggy.plugin`, и pytest их находит.

Тот же приём регистрирует **сгенерированные фикстуры**: loader, отрабатывая внутри `install()`,
кладёт список найденных модулей в `context["pytest_plugins"]` (т.е. в `goga_tool_pybuggy.plugin.pytest_plugins`),
и pytest рекурсивно их догружает. Поэтому loader обязан работать синхронно при импорте.

Важно: импорт модуля-плагина вне pytest-проекта не должен падать — обход отсутствующего пакета
`api/` идёт с `required=False`.

---

## CommandLine — CLI-опция pytest

`CommandLine(opt, *args, **kwargs)` — обёртка над `parser.addoption`. Регистрируется
автоматически через `command_line=...` у `define.option`. Опция добавляется в группу с именем
плагина; повторная регистрация того же `opt` пропускается (`register_once`).

```python
CommandLine("--api-url", action="store", help="Base URL of the service under test")
```

---

## Actions — точка расширения (опционально)

`Action(name, module, *, enable=True, default_config=None)` — отложенно-импортируемое действие.
`module` — dotted-путь к модулю с функцией `main(context, config)` (и опционально
`setup(config)`). Действие вызывается через `plugin.action(name, context, lazy=True/False)`; при
`lazy=True` возвращает замыкание, дорабатывающее контекст в момент вызова. Ячейка `goga_tool_pybuggy/plugin`
actions не использует — описано для полноты картины фреймворка.

---

## Что pybuggy НЕ использует

- `deps`/`check_deps` — проверка зависимостей между плагинами (один плагин, зависимостей нет).
- `actions` — отложенные действия (не нужно: `Api` делает одиночный запрос, без polling/collector).
- `hook` у `define.option` — пост-обработка значения опции (опции простые, приводятся типом).
