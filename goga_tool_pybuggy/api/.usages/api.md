# goga_tool_pybuggy.api — потребление runtime из тестовых фикстур

## Предметная область

Runtime ячейки `goga_tool_pybuggy/api` выполняет HTTP-запросы из сгенерированных фикстур и
проверяет ответ. Аудитория — автор тестового проекта, который использует
сгенерированные `pybuggy` фикстуры. Содержит готовые шаблоны потребления фасада и
подробный референс API: `Api`, `Endpoint`, `ResponseWrapper`, `Expected`,
`AssertField`, `Auth`.

pybuggy поставляет **только классы**. Экземпляр `Api` собирает сам потребитель в
своём `conftest.py` и отдаёт его в фикстуре `api`.

---

## Фасад

```python
from goga_tool_pybuggy.api import Api, Endpoint, ResponseWrapper, Expected, AssertField, Auth
```

| Сущность | Назначение |
|----------|------------|
| `Api` | HTTP-клиент (композиция над `resq.Session`); хранит auth/headers/cookies/`data_key`/`error_key` и assert-настройки, инжектит их в каждый запрос |
| `Endpoint` | callable-маршрут: `endpoint(json=...)` делает запрос, возвращает `ResponseWrapper` |
| `ResponseWrapper` | контекстный менеджер над ответом; `.response` — raw `resq.http.Response`, `.expected` — `Expected` |
| `Expected` | двухуровневый диспетчер проверок на базе matchcrest (response-level методы + `__call__` для field-level) |
| `AssertField` | field-level ассерт над значением поля; создаётся через `Expected.__call__`, реэкспортируется для type-hint'а |
| `Auth` | структурный протокол для type-hint'а call-level аутентификатора (любой объект с методом `auth(request)`) |

`CombineAuth`/`AuthWrapper` — внутренние (комбинируют auth в `Endpoint._call`), в
фасад не входят.

---

## Api — референс

### Конструктор

```python
Api(
    base_url: str,
    auth: AuthBase | None = None,
    headers: dict[str, str] | None = None,
    cookies: SimpleCookie | None = None,
    timeout: float | None = None,
    data_key: str | None = None,
    error_key: str | None = None,
    assert_timeout: int | float | None = None,
    assert_delay: int | float | None = None,
    assert_field_class: str | None = None,
    assert_response_class: str | None = None,
)
```

| Параметр | Назначение |
|----------|------------|
| `base_url` | Базовый URL для `resq.Session`; конкатенируется с путём каждого запроса |
| `auth` | `requests.AuthBase`, применяемый ко всем запросам (если не переопределён на вызове); read/write |
| `headers` | Заголовки по умолчанию, сливаются в каждый запрос (call-level побеждает) |
| `cookies` | Cookies по умолчанию |
| `timeout` | Сетевой таймаут (передаётся в `resq.Session`, не переотправляется на запрос) |
| `data_key` | Ключ тела «успех»: фолбэк для `Endpoint` без своего `data_key` |
| `error_key` | Ключ тела «ошибка»: фолбэк для `Endpoint` без своего `error_key` |
| `assert_timeout` | Бейзлайн polling-таймаута ассертов (отличен от сетевого `timeout`); уходит в каждый `AssertConfig` |
| `assert_delay` | Бейзлайн паузы между polling-попытками; уходит в каждый `AssertConfig` |
| `assert_field_class` | Dotted `module:Class` кастомного подкласса `AssertField` |
| `assert_response_class` | Dotted `module:Class` кастомного подкласса `Expected` |

### Свойства

| Свойство | Тип | Доступ | Назначение |
|----------|------|--------|------------|
| `base_url` | `str` | RO | Базовый URL из `resq.Session` |
| `auth` | `AuthBase \| None` | **RW** | Хранимый auth (getter/setter) |
| `headers` | `dict[str, str]` | RO | Заголовки по умолчанию (пустой dict, если не заданы) |
| `cookies` | `SimpleCookie \| None` | RO | Cookies по умолчанию |
| `data_key` | `str \| None` | RO | Фолбэк success-ключа для endpoint-ов |
| `error_key` | `str \| None` | RO | Фолбэк error-ключа для endpoint-ов |
| `assert_timeout` | `int \| float \| None` | RO | Бейзлайн polling-таймаута ассертов |
| `assert_delay` | `int \| float \| None` | RO | Бейзлайн паузы polling |
| `assert_field_class` | `str \| None` | RO | Dotted-путь кастомного `AssertField` |
| `assert_response_class` | `str \| None` | RO | Dotted-путь кастомного `Expected` |

### Методы

- `request(method, url_path, **kwargs) -> resq.http.Response` — один HTTP-запрос:
  сериализует pydantic `params`/`json` (с опц. `by_alias` через `use_aliases`),
  подставляет `:name` path-параметры, инжектит auth/headers/cookies с call-приоритетом,
  диспатчит на resq-глагол (`get/post/put/delete/patch/head/options`). Никогда не
  пробрасывает `timeout`/`delay`/polling-опции.
- `close()` — закрывает пул соединений (`requests.Session`) под капотом `Api`;
  вызывается в teardown фикстуры `api`. httpx-клиент не создаётся (pybuggy синхронный).

---

## Endpoint — референс

### Конструктор

```python
Endpoint(
    api: Api,
    url_path: str,
    method: str,
    status: int | None = 200,
    use_autocheck: bool = True,
    data_key: str | None = None,
    error_key: str | None = None,
)
```

| Параметр | Назначение |
|----------|------------|
| `api` | Клиент `Api`, которым делается запрос |
| `url_path` | Путь маршрута (возможны `:name` плейсхолдеры, подставляемые `Api.request`) |
| `method` | HTTP-глагол |
| `status` | Ожидаемый код успеха; Enum нормализуется к `.value`; `None` отключает статус-автопроверку |
| `use_autocheck` | Запускает ленивый авто-чек при первом доступе к `response.expected` |
| `data_key` | Per-endpoint success-ключ; `None` → фолбэк на `api.data_key` |
| `error_key` | Per-endpoint error-ключ; `None` → фолбэк на `api.error_key` |

`schemas_dir` резолвится автоматически через frame-inspection (см. ниже).

### Методы и свойства

- `endpoint(**kwargs) -> ResponseWrapper` — **позитивный** путь (`is_negative=False`).
- `endpoint.error(**kwargs) -> ResponseWrapper` — **негативный** путь (`is_negative=True`):
  статус и json-схема в авто-чеке не проверяются.
- `url_path -> str`, `method -> str` — путь и глагол (RO).

Оба пути делегируют внутренний `_call`, который: копирует kwargs (не мутируя
caller-словарь), вынимает `auth`/`use_autocheck`, резолвит data/error-key, собирает
`AssertConfig` (с `assert_*` опциями из `Api`), делает запрос и оборачивает ответ.

---

## ResponseWrapper — референс

Контекстный менеджер над `resq.http.Response`.

| Элемент | Назначение |
|---------|------------|
| `.response -> resq.http.Response` | Raw ответ (доступен только через это свойство; обёртка не проксирует атрибуты resq) |
| `.expected -> Expected` | Диспетчер проверок. Строится **лениво** при первом доступе; при `use_autocheck=True` тогда же один раз запускается `autocheck()` (с мемоизацией флага). При `config.assert_response_class` грузится кастомный подкласс `Expected` |
| `with endpoint(...) as response:` | Вход в контекст; выход **без** подавления исключений (отчёт не формируется) |

---

## Шаблон: фикстура `api` (собирает потребитель)

```python
# conftest.py тестового проекта
from collections.abc import Iterator

import pytest
from goga_tool_pybuggy.api import Api


@pytest.fixture(scope="session")
def api() -> Iterator[Api]:
    api = Api(
        base_url="https://api.example.com",
        data_key="data",
        error_key="error",
    )
    yield api
    api.close()
```

Скоуп — на усмотрение потребителя (`session`/`function`). `data_key`/`error_key`
здесь — defaults для всех endpoint-ов; конкретный `Endpoint` может переопределить
их своими. Фикстура-генератор вызывает `api.close()` после теста (на `session`-скоупе
— один раз в конце), закрывая пул соединений.

Для polling/кастомных классов добавьте assert-опции уровня `Api`:

```python
api = Api(
    base_url="https://api.example.com",
    data_key="data",
    error_key="error",
    assert_timeout=5,        # бейзлайн polling-таймаута (сек.)
    assert_delay=0.2,        # пауза между попытками (сек.)
    assert_field_class="myproj.asserts:StrictAssertField",
)
```

---

## Шаблон: сгенерированная фикстура endpoint-а

```python
# api/<spec>/<id>/api.py
import pytest
from goga_tool_pybuggy.api import Endpoint, Api
from pydantic import BaseModel


class Request(BaseModel):
    order_id: int


@pytest.fixture(scope="function")
def post_clients_calls_initiate(api: Api) -> Endpoint:
    return Endpoint(api, "/clients/calls/initiate", method="POST")
```

`Endpoint` создаётся **прямо в теле функции-фикстуры** — обязательное условие
frame-inspection (см. ниже).

---

## Шаблон: позитивная проверка

```python
def test_initiate(post_clients_calls_initiate: Endpoint):
    with post_clients_calls_initiate(json=Request(order_id=1)) as response:
        response.expected.has_status_code(200)
```

При первом доступе к `response.expected` (если `use_autocheck=True`) срабатывает
авто-проверка **один раз**. **Positive-путь:** статус == ожидаемому → отсутствие
`error_key` → наличие `data_key` → валидация тела по `schemas/<status>*.json`.
Явный `has_status_code(200)` дублирует только статус-часть — это нормально.

---

## Шаблон: негативная проверка

```python
def test_initiate_error(post_clients_calls_initiate: Endpoint):
    with post_clients_calls_initiate.error(json=Request(order_id=-1)) as response:
        response.expected.has_status_code(400)
```

`.error(...)` — негативный путь: статус и json-schema в авто-чеке **не
проверяются**, поэтому статус нужно проверить явно. **Negative-путь авто-чека:**
`data_key` отсутствует → `error_key` присутствует.

---

## Шаблон: field-level проверка значения поля

Вызов `response.expected(path)` (диспетчер как функция) возвращает `AssertField`
для проверок конкретного поля. Путь **относителен корню**: на позитивном пути
корень — `data_key`, на негативном — `error_key`; без `data_key`/`error_key` путь
абсолютен к телу ответа.

```python
def test_initiate(post_clients_calls_initiate: Endpoint):
    with post_clients_calls_initiate(json=Request(order_id=1)) as response:
        # path относителен data_key ("data"): items → body["data"]["items"]
        response.expected("items").has_length(3)
        response.expected("items", in_array=True).equal_to(2, any=True)
        response.expected("name").equal_to("abc")

        # drill-down: index/hook
        response.expected("items")(index=0).equal_to(1)
        response.expected("name")(hook=str.upper).equal_to("ABC")

        # jsonpath — для вложенных массивов/фильтров
        response.expected("$.items[*]", in_array=True).equal_to(2, any=True)
```

Полный референс всех field-level и response-level матчёров — в практике
суб-клетки `goga_tool_pybuggy/api/asserts`.

---

## Параметры запроса

В `endpoint(json=...)` / `endpoint.error(...=...)` передаются аргументы resq-глагола:

- `params=` — pydantic `BaseModel` (сериализуется через `model_dump`) или `dict`.
- `json=` — pydantic `BaseModel` (сериализуется) или `dict`.
- path-параметры — ключи в `params` с префиксом `:` (например `:id`) подставляются
  в `url_path` и **не** уходят в query.
- `auth=` — call-level аутентификация; принимает `AuthBase`, объект-протокол `Auth`
  (с методом `.auth(request)`), или callable. При передаче **комбинируется** с
  `Api.auth` через `CombineAuth` (порядок: `AuthBase` напрямую → протокол → callable
  → иначе `TypeError`); без call-level `auth` применяется `Api.auth`.
- `headers=` / `cookies=` — call-level; побеждают defaults `Api`.
- `use_aliases=` (bool) — управляет pydantic `by_alias` при сериализации.
- `use_autocheck=` (bool) — call-level override ленивого авто-чека; по умолчанию
  берётся `Endpoint.use_autocheck`. `use_autocheck=False` на конкретном вызове
  отключает авто-чек только для него; `use_autocheck=True` включает обратно.

```python
endpoint(json=Request(id=1), params={":id": "42", "q": "x"}, auth=MyAuth())
```

---

## Auto-check — что именно проверяется

Запускается один раз при ленивом доступе к `response.expected`, если
`use_autocheck=True`. Путь определяется флагом `is_negative`:

- **Positive** (`endpoint(...)`): статус (если задан) → `error_key` отсутствует →
  `data_key` присутствует → валидация по первому `schemas/<status>*.json`
  (пропуск, если каталога/файла нет).
- **Negative** (`endpoint.error(...)`): `data_key` отсутствует → `error_key`
  присутствует. Статус и json-схема **не** проверяются.

`use_autocheck=False` (на `Endpoint` или на вызове) отключает авто-чек целиком —
тогда проверяйте всё явно через `response.expected.*`.

---

## Frame-inspection — обязательное условие

`Endpoint` резолвит каталог `schemas/` через `inspect.stack()[1]`: берёт кадр
вызывающего и читает `__file__` из его `f_globals`, затем `Path(file).parent / "schemas"`. Поэтому:

- Создавайте `Endpoint` **прямо в функции-фикстуре** (`api.py`) — тогда кадр
  caller = фикстура с верным `__file__`, и `schemas/` ляжет рядом с этим `api.py`.
- Создание `Endpoint` в другом месте (модуль верхнего уровня, вспомогательная
  функция) даст чужой `__file__` или `None` → `schemas_dir` определится неверно /
  `None`, и авто-валидация json-схемы **тихо пропустится**.

При отсутствии `schemas/` или файла под статус — авто-валидация тоже пропускается
без ошибки.

---

## Pluggable классы

Кастомные подклассы ассертов подключаются опциями уровня `Api`
(`assert_field_class` / `assert_response_class`, dotted `module:Class`):

- класс должен наследовать встроенный (`AssertField` / `Expected` соответственно);
- грузится через `load_assert_class` в точке построения field/response-класса;
- `None` (по умолчанию) — встроенные классы.

```python
class StrictAssertField(AssertField):
    ...

Api(base_url=..., assert_field_class="myproj:StrictAssertField")
```

---

## Два разных `Endpoint`

Имя `Endpoint` встречается в двух местах pybuggy — это **разные классы**, не взаимозаменяемые:

| Класс | Откуда импортировать | Назначение |
|-------|----------------------|------------|
| runtime-`Endpoint` | `goga_tool_pybuggy.api` | callable-маршрут: делает HTTP-запрос, проверяет ответ (этот фасад) |
| spec-`Endpoint` (pydantic) | слой спецификаций | pydantic-модель операции (method/path/schemas); запросов не делает |

В тестах нужен runtime-`Endpoint` — импортируйте его из `goga_tool_pybuggy.api`. spec-`Endpoint`
к выполнению запросов отношения не имеет.
