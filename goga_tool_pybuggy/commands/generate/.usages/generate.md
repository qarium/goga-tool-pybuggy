# goga_tool_pybuggy.commands.generate — команда endpoint generate

## Предметная область

Шаблоны потребления cell `goga_tool_pybuggy/commands/generate`: скаффолдинг каталогов `api/` (JSON-схемы
ответов + pytest-фикстура `api.py` на эндпоинт + пустые `__init__.py`-маркеры пакета на каждом
каталоге пути к `api.py`) и пустых каталогов `tests/` из спецификаций.
Аудитория — регистрация в CLI (`generate_cmd`) и тесты (`run_generate` напрямую; чистый рендерер
`render_api_module` — напрямую для текстовых проверок).

## Вызов handler-функции

`run_generate` — тестируемая точка входа (Click-обёртка `generate_cmd` связывает опции и вызывает
`run_generate`):

    from goga_tool_pybuggy.commands.generate import run_generate

    run_generate(spec_name=None, force=False)    # все спеки, пропуск существующего
    run_generate(spec_name="shop", force=True)  # одна спека, перезапись
    run_generate(None, False, endpoint_ids=["clients_startup_get"])  # только указанные эндпоинты
    run_generate(None, False, endpoint_ids=[])  # пустой/None фильтр — все эндпоинты (no-op)

`render_api_module` — чистая функция `Endpoint -> str`, возвращает полный текст `api.py`. Используется
в тестах для проверки содержимого фикстуры без записи на диск:

    from goga_tool_pybuggy.commands.generate import render_api_module

    module_text = render_api_module(endpoint)   # str; детерминирован для данного endpoint

## Наблюдаемое поведение

Для каждой (отфильтрованной) спеки `name`: разобрать файл в `location` → извлечь эндпоинты → для
каждого эндпоинта записать схему каждого кода ответа, сгенерировать `api.py`, проставить пустые
`__init__.py`-маркеры пакета на каждом каталоге пути к `api.py` и создать каталог тестов.

Дерево артефактов (в текущем рабочем каталоге):

    api/__init__.py                       # пустой маркер пакета
    api/<spec>/__init__.py                # пустой маркер пакета
    api/<spec>/<endpoint.id>/__init__.py  # пустой маркер пакета
    api/<spec>/<endpoint.id>/schemas/<status_code>.json
    api/<spec>/<endpoint.id>/api.py
    tests/<spec>/<endpoint.id>/          # пустой каталог

Пример: спека `shop`, эндпоинт `clients_startup_get` с кодами `200`, `404`:

    api/__init__.py
    api/shop/__init__.py
    api/shop/clients_startup_get/__init__.py
    api/shop/clients_startup_get/schemas/200.json
    api/shop/clients_startup_get/schemas/404.json
    api/shop/clients_startup_get/api.py
    tests/shop/clients_startup_get/

Содержимое `<status_code>.json` — prettified JSON развёрнутой схемы ответа (indent=2,
ensure_ascii=False). Для кодов без `application/json` пишется `{}`. Пишутся все коды из ответа
эндпоинта.

## Содержимое api.py

`api.py` — pytest-модуль-фикстура на эндпоинт, выровненный `ruff` (двойные кавычки,
сортировка импортов, line-length 120):

- `@pytest.fixture(scope="function")` с именем `{method}_{path_part}` (`path_part` = `endpoint.id`
  без суффикса `_{method}`), принимающая `api: Api` и возвращающая
  `Endpoint(api, "<route>", method="<METHOD>")`. `<METHOD>` — метод в верхнем регистре.
- `<route>` = `endpoint.path`, где `{param}` заменено на `:param` с сохранением имени и регистра
  параметра (например `/clients/{orderID}/status` → `/clients/:orderID/status`).
- `class Request(BaseModel)` — тело запроса, сгенерированное `datamodel-code-generator`
  (см. `datamodel-code-generator`) из `endpoint.request`: вложенные объекты становятся
  отдельными pydantic-классами, массивы — типизированными `list[...]`, enum'ы — `Literal[...]`,
  необязательные поля — `T | None = None` (union operator), nullable required — `T | None`
  без дефолта. При отсутствии свойств тела класс `Request` и импорт `pydantic` опускаются.
- Импорты собираются `ruff` (`check --fix --select I`): `pytest`,
  `from goga_tool_pybuggy.api import Api, Endpoint`, опционально `from pydantic import BaseModel`
  (и `RootModel`/`typing` — только когда сгенерированные модели их требуют).

Пример с телом и path-параметром (POST `/clients/calls/{orderID}/status`, тело `{note: string}`):

```python
import pytest
from goga_tool_pybuggy.api import Api, Endpoint
from pydantic import BaseModel


class Request(BaseModel):
    note: str


@pytest.fixture(scope="function")
def post_clients_calls_orderid_status(api: Api) -> Endpoint:
    return Endpoint(api, "/clients/calls/:orderID/status", method="POST")
```

## Семантика --force

- Без `-f` (`force=False`): существующие `<status_code>.json`, `api.py` и `__init__.py`-маркеры
  пропускаются молча (без вывода в консоль), недостающие файлы и каталоги создаются. Поведение идемпотентно.
- С `-f` (`force=True`): файлы перезаписываются, `__init__.py`-маркеры перезаписываются пустым
  содержимым, каталоги (пере)создаются — всё дерево артефактов регенерируется единообразно.
- `__init__.py`-маркеры проставляются только на пути к `api.py` (`api/`, `api/<spec>/`,
  `api/<spec>/<endpoint.id>/`), но не под `tests/`.

## Флаг --spec

`-s/--spec <name>` ограничивает генерацию одной спекой. Несуществующее имя →
`click.ClickException("spec not found: <name>")`, ненулевой exit.

## Фильтр по endpoint-id

Позиционный variadic-аргумент `endpoint-ids` ограничивает генерацию подмножеством эндпоинтов по их
id (`Endpoint.id`, те же id, что в командах `endpoint list`/`endpoint info` — строка вида
`clients_startup_get`):

    pybuggy endpoint generate clients_startup_get health_get
    pybuggy endpoint generate -s shop -f clients_startup_get   # опции — до позиционных id

Эндпоинты отбираются только среди выбранных спек (`--spec` или все):

- Аргумент не передан — генерируются все эндпоинты выбранных спек (поведение не изменилось).
- Пустой список / `None` у handler-а — то же самое (no-op).
- id найден хотя бы в одной выбранной спеке — генерируются только совпадающие эндпоинты.
- id не найден ни в одной выбранной спеке → `click.ClickException("endpoint not found: <id>")`,
  ненулевой exit; при нескольких отсутствующих id они перечисляются все (отсортированы).

У handler-а `run_generate` фильтр — третий параметр `endpoint_ids: list[str] | None`. Валидация
выполняется до записи артефактов, поэтому неизвестный id не оставляет частично сгенерированного
дерева `api/` и `tests/`.

## Особые случаи

- Спека без `paths` → `click.ClickException`.
- Спека без эндпоинтов → WARNING, артефактов не создаётся.
- Эндпоинт без тела / тело без полей → `api.py` без `class Request` (импорт `pydantic` опускается);
  фикстура генерируется в любом случае.
- Неизвестный `endpoint-id` (нет ни в одной выбранной спеке) →
  `click.ClickException("endpoint not found: <id>")`; валидация до записи, артефактов не создаётся.

## Предусловия

- Файлы spec должны быть в `location` (после `pull` или вручную).
- Конфиг валиден и лежит по фиксированному пути (см. `goga_tool_pybuggy.config`); загрузка — через `load_config`.
- Артефакты пишутся в текущий рабочий каталог (`Path.cwd()`); тесты изолируют через `tmp_path` и
  подмену `cwd`.
- `api.py` импортирует из `goga_tool_pybuggy.api` (`Endpoint`, `Api`); модуль может отсутствовать в проекте на
  момент генерации — файл предназначен для последующего использования, а не для импорта в самом goga_tool_pybuggy.
