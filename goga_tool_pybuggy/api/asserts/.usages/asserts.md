# goga_tool_pybuggy.api.asserts — полный референс ассертов

## Предметная область

Sub-cell `goga_tool_pybuggy/api/asserts` — полный assert-слой pybuggy на базе matchcrest.
Аудитория — автор тестового проекта, проверяющий ответы через сгенерированные
фикстуры. Практика описывает **как потреблять** ассерты (response-level и
field-level), а не как они реализованы.

Слой собран из трёх сущностей:

- `AssertConfig` — статический конфиг проверок (все поля опциональны);
- `Expected` — двухуровневый диспетчер: response-level проверки + field-level
  вход через `Expected.__call__(search)`; он же — response-level класс по
  умолчанию;
- `AssertField` — field-level ассерт над значением поля тела ответа; он же —
  field-level класс по умолчанию.

Эти объекты потребитель **не создаёт вручную**: `AssertConfig` собирается при
вызове endpoint-а, `Expected` строится лениво при первом доступе к
`response.expected`, field-level ассерт получается из `response.expected('path')`.

---

## Точка входа

```python
from goga_tool_pybuggy.api.asserts import AssertField  # для type-hint'а
```

`AssertField` оборачивает внутренний search-context и предоставляет matchcrest-матчёры над разрешённым значением. `Expected`, `AssertConfig` и `load_assert_class`
также реэкспортируются, но в типовом тесте они приходят из `response.expected`.

---

## Общие параметры всех check-методов

Каждый check-метод `Expected` и `AssertField` построен по одному шаблону:
`assert_that(context, matcher, reason=...)`, возвращает свой объект (`Expected`
или `AssertField`) для цепочек.

Универсальные kwargs:

- `reason: str = ""` — префикс сообщения об ошибке (на каждой проверке).
- `any: bool = False` — управление перебором элементов; действует **только**
  вместе с `in_array=True` (флаг уровня поля, задаётся на входе в поле или при
  drill-down). Два режима при `in_array=True`: `any=False` (умолчание) —
  совпадение требуется для **всех** элементов списка; `any=True` — достаточно
  **хотя бы одного** совпадающего. Передавать `any=True` без `in_array=True`
  нельзя — это бросает `ValueError` (`"any" can be used with "in_array" only`).
  Параметра нет у `raise_exc`/`not_raise_exc`.
- `timeout: int | float | None = None` / `delay: int | float | None = None` —
  per-call override бейзлайна из `AssertConfig` для **одной** проверки (см. Polling).

`.value` (свойство `AssertField`) отдаёт разрешённое значение **без проверки**.
Вызов поля (`field(index=0)`, `field(search=...)`) drills на уровень глубже и
возвращает новый `AssertField`.

---

## AssertConfig — статический конфиг

| Поле                    | Тип                    | Назначение                                                                                                  |
|-------------------------|------------------------|-------------------------------------------------------------------------------------------------------------|
| `status`                | `int \| None`          | Ожидаемый код успеха; `None` отключает статус-автопроверку                                                  |
| `data_key`              | `str \| None`          | Ключ тела «успех»: positive — присутствует, negative — отсутствует; корень field-поиска на позитивном пути  |
| `error_key`             | `str \| None`          | Ключ тела «ошибка»: positive — отсутствует, negative — присутствует; корень field-поиска на негативном пути |
| `schemas_dir`           | `Path \| None`         | Каталог json-схем `<status>*.json` для авто-валидации; `None`/отсутствие — пропуск                          |
| `timeout`               | `int \| float \| None` | Бейзлайн polling-таймаута (сек.); `None` — одна попытка                                                     |
| `delay`                 | `int \| float \| None` | Пауза между polling-попытками (сек.); `None` — дефолт матчёра                                               |
| `assert_field_class`    | `str \| None`          | Dotted `module:Class` кастомного подкласса `AssertField`; `None` — встроенный                               |
| `assert_response_class` | `str \| None`          | Dotted `module:Class` кастомного подкласса `Expected`; `None` — встроенный                                  |

---

## Expected — response-level диспетчер

Получается из `response.expected`. Response-level методы работают по целому
ответу (статус/заголовки/тело) и возвращают `Expected` для цепочек.

### Response-level проверки (полный список)

| Метод                                            | Матчёр                                                          | Что проверяет                                                                         |
|--------------------------------------------------|-----------------------------------------------------------------|---------------------------------------------------------------------------------------|
| `has_status_code(code)`                          | `ResponseCodeMatcher`                                           | Код ответа равен `code` (`int`, строка `requests.codes.<name>` или `Enum`)            |
| `has_header(key, value=None, ...)`               | `ResponseHeadersByKeyMatcher` / `ResponseHeadersByValueMatcher` | Заголовок `key` есть; при `value` — значение совпадает                                |
| `json_has_data_by_key(key)`                      | `JsonHasDataByKeyMatcher`                                       | В теле есть ключ `key` со значением не `None`                                         |
| `json_has_not_data_by_key(key)`                  | `JsonHasNotDataByKeyMatcher`                                    | В теле нет ключа `key` (или он `None`)                                                |
| `json_contains_key(key)`                         | `JsonContainsKeyMatcher`                                        | В теле есть ключ `key` (вложенный, если передан список)                               |
| `jsonschema_is_valid(schema)`                    | `JsonschemaMatcher`                                             | Тело валидно против json-схемы (dict или путь к `.json`)                              |
| `jsonschemas_is_valid(schemas_dir, status_code)` | `JsonschemaMatcher`                                             | Тело валидно против первого файла `<status_code>*` в каталоге; пропуск при отсутствии |

Детали параметров:

- `has_status_code(code, *, reason="", timeout=None, delay=None)`: `code` —
  `int` (напр. `200`), строка-имя из `requests.codes` (напр. `"ok"`→200), либо
  `Enum` (берётся `.value`).
- `has_header(key, value=None, *, contains=None, startswith=None, endswith=None, count=None, reason="", timeout=None, delay=None)`:
  - без `value` — факт наличия заголовка (опц. фильтр по подстроке/префиксу/суффиксу, опц. `count` — ровно столько совпадений);
  - с `value` — значение заголовка совпадает (по умолчанию точное равенство, либо `contains`/`startswith`/`endswith`);
  - сравнение **case-insensitive** и для **ключей**, и для **значений** (и ключ, и ожидаемое значение приводятся к нижнему регистру);
  - `count` вместе с `value` → `ValueError`.
- `json_contains_key(key)`: `key` — одна строка или упорядоченный список для
  спуска во вложенные объекты.
- `jsonschema_is_valid(schema)`: `schema` — `dict`, либо путь к `.json` (читается UTF-8).
- `jsonschemas_is_valid(schemas_dir, status_code)`: берётся **первый** по сортировке
  файл, чьё имя начинается со строки статуса; нет каталога/файла — тихий пропуск.

### Field-level вход

```python
field = response.expected("items")  # dotted-путь под data_key
field = response.expected("$.items[*]")  # jsonpath под data_key
field = response.expected()  # целиком значение под data_key (массив/объект)
```

`Expected.__call__(search=None, *, index=None, hook=None, in_array=False)`:

- `search` — dotted-путь (`a.b.c`) **или** jsonpath (`$.a.b[*]`), разрешаемые под
  корневым ключом: на позитивном пути — `data_key`, на негативном — `error_key`.
  `None` — значение под этим ключом целиком (не «всё тело ответа»); без
  `data_key`/`error_key` корнем служит само тело ответа;
- `index` — опц. индекс списка после поиска;
- `hook` — опц. callable, применяется к разрешённому значению (не-callable → `TypeError`);
- `in_array` — трактовать значение как список для поэлементных `any`.

**Важно про jsonpath**: `$` отсчитывается **от значения корневого ключа**, а не от
тела ответа. При `data_key="data"` выражение `$.items[*]` → `body["data"]["items"]`,
а `$[0].name` → `body["data"][0]["name"]`. Это единое правило для dotted и jsonpath.

Возвращает `AssertField` для цепочек.

### autocheck (внутренний)

`Expected.autocheck()` вызывается обёрткой ответа один раз при ленивом доступе,
если `use_autocheck=True`. Путь выбирается флагом `is_negative`:

- **positive:** статус (если задан) → `error_key` отсутствует → `data_key`
  присутствует → валидация по `<status>*` схеме (пропуск при отсутствии);
- **negative:** `data_key` отсутствует → `error_key` присутствует (статус и
  json-схема **не** проверяются).

---

## AssertField — field-level матчёры (полный список)

Field-level ассерт над разрешённым значением поля. Каждый метод — matchcrest
`assert_that`, возвращает `AssertField` для цепочек. Все (кроме `raise_exc`/
`not_raise_exc`) принимают `reason`/`any`/`timeout`/`delay`; у методов со звёздочкой
есть дополнительные параметры.

Путь разрешается контекстом: на позитивном пути — под `data_key`, на негативном —
под `error_key`; без ключей — относительно тела целиком. Это относится **и к dotted,
и к jsonpath**: jsonpath вычисляется после префиксирования корневым ключом.

### Вхождение и содержание

| Метод                 | Доп. параметры | Что проверяет                                                                                                       |
|-----------------------|----------------|---------------------------------------------------------------------------------------------------------------------|
| `contains(value)`     | —              | Значение **содержит** `value` (Python `in`: для str — подстрока, для list — членство, для dict — наличие **ключа**) |
| `not_contains(value)` | —              | Значение **не содержит** `value` (обратная семантика `in`)                                                          |
| `contains_dict(dct)`  | `dct: dict`    | Dict содержит **все** пары key/value из `dct`                                                                       |
| `is_in(value)`        | —              | Значение является **элементом** `value` (`value` — контейнер)                                                       |
| `is_not_in(value)`    | —              | Значение **не** является элементом `value`                                                                          |
| `is_subset(value)`    | —              | Итерируемое значение — подмножество `value`                                                                         |
| `is_disjoint(value)`  | —              | Итерируемое значение не имеет общих элементов с `value`                                                             |

```python
response.expected("name").contains("abc")
response.expected("tags").is_in(["x", "y"])
response.expected("filters").is_subset({"a": 1, "b": 2})
```

> Внимание на направление аргумента: `is_in(value)` / `is_subset(value)` /
> `is_disjoint(value)` — `value` это **второй** операнд (контейнер/надмножество),
> а разрешённое поле — первый. `is_subset`/`is_disjoint` строят множества через
> `set()`, поэтому и разрешённое значение, и `value` должны быть **итерируемыми
> и хешируемыми**; не-итерируемое значение → `ValueError`.

### Равенство и пустота

| Метод                 | Доп. параметры       | Что проверяет                                   |
|-----------------------|----------------------|-------------------------------------------------|
| `equal_to(value)`     | `strict: bool=False` | Равно `value`; `strict=True` → тождество (`is`) |
| `not_equal_to(value)` | `strict: bool=False` | Не равно `value`                                |
| `empty()`             | —                    | Пусто/falsy                                     |
| `not_empty()`         | —                    | Не пусто/truthy                                 |

```python
response.expected("name").equal_to("abc")
response.expected("count").equal_to(1, strict=True)
response.expected("items").not_empty()
```

### Сравнение чисел

| Метод                 | Доп. параметры         | Что проверяет                       |
|-----------------------|------------------------|-------------------------------------|
| `greater_than(value)` | `or_equal: bool=False` | `>` `value`; `or_equal=True` → `>=` |
| `lesser_than(value)`  | `or_equal: bool=False` | `<` `value`; `or_equal=True` → `<=` |

```python
response.expected("count").greater_than(0)
response.expected("count").greater_than(0, or_equal=True)
```

### Длина

| Метод                       | Что проверяет            |
|-----------------------------|--------------------------|
| `has_length(value)`         | `len(значение) == value` |
| `has_length_greater(value)` | `len(значение) > value`  |
| `has_length_lesser(value)`  | `len(значение) < value`  |

```python
response.expected("items").has_length(3)
response.expected("items").has_length_greater(0)
```

### Строки и URL

| Метод                  | Доп. параметры                                                     | Что проверяет                                                                                                                  |
|------------------------|--------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|
| `startswith(value)`    | —                                                                  | Строка начинается с `value`                                                                                                    |
| `endswith(value)`      | —                                                                  | Строка заканчивается на `value`                                                                                                |
| `match_regex(pattern)` | `pattern: str`                                                     | Соответствует регулярке; семантика `re.match` — совпадение с **начала** строки (не `search`/`fullmatch`)                       |
| `is_url()`             | `is_live: bool=False`, `allowed_protocols: list[str] \| None=None` | Валидный URL; `is_live=True` — достижим (GET → 2xx); `allowed_protocols` — разрешённые схемы (по умолчанию `['https','http']`) |

```python
response.expected("email").match_regex(r"^[\w.]+@[\w.]+$")
response.expected("avatar").is_url()
response.expected("avatar").is_url(is_live=True, allowed_protocols=["https"])
```

### Даты

| Метод                     | Что проверяет                                   |
|---------------------------|-------------------------------------------------|
| `has_date(value)`         | Дата/datetime равна `value` (`date`/`datetime`) |
| `has_date_greater(value)` | Дата больше `value`                             |
| `has_date_lesser(value)`  | Дата меньше `value`                             |

> Сравнение выполняется **по timestamp** (`date_to_timestamp`): `date` приводится
> к полуночи, `datetime` — к своему timestamp. Поэтому `date` и `datetime` с
> разным временем могут не совпасть — сравнивайте значения в одном типе.

```python
from datetime import date

response.expected("created_at").has_date(date(2026, 1, 1))
response.expected("created_at").has_date_greater(date(2025, 1, 1))
```

### Исключения (context managers)

| Метод                     | Доп. параметры                | Что проверяет                                   |
|---------------------------|-------------------------------|-------------------------------------------------|
| `raise_exc(expected_exc)` | `expected_exc: type \| tuple` | Доступ к значению raises один из `expected_exc` |
| `not_raise_exc()`         | —                             | Доступ к значению не raises ничего              |

Это **контекстные менеджеры**: yield'ят разрешённое значение и проверяют, что
выброшено (или не выброшено) внутри блока. Не принимают `any`.

```python
with response.expected("missing").raise_exc(KeyError):
    ...  # обращение к полю внутри блока должно выбросить KeyError

with response.expected("ok").not_raise_exc() as value:
    assert value == "abc"
```

---

## Drill-down и массивы

- **Drill:** вызов `field(search=..., index=..., hook=...)` (или `field(index=0)`)
  возвращает новый `AssertField` на расширенном контексте; бейзлайн
  `timeout`/`delay` наследуется. Dotted-шаги применяются по очереди, затем
  `index`, затем `hook`.
- **in_array:** флаг уровня поля (через `Expected.__call__(in_array=True)` или при
  drill-down). С `in_array=True` значение трактуется как список: `any=False`
  (умолчание) требует совпадения **всех** элементов, `any=True` — **хотя бы одного**.
- **Все элементы массива** (jsonpath с `[*]` возвращает список значений): чтобы
  проверить, что **каждый** элемент входит в допустимое множество, примените
  `is_in`/`is_subset` над списком. Это «все удовлетворяют», в отличие от `any=True`
  («хотя бы один»).
- **Элемент отсутствует среди элементов массива**: выберите список значений
  jsonpath-ом `$[*].field` и проверьте `not_contains` (для скалярных значений)
  или `is_disjoint` (множественная семантика). `not_contains` над списком без
  `in_array` — это членство значения в списке, то есть «значение не встречается
  ни у одного элемента». Для строковых значений это точная проверка равенства
  отсутствия — в отличие от `in_array=True`, где `in` для строк работает как
  подстрока.
- **Кастомный поиск элемента массива**: когда элемент находится по предикату
  (несколько полей совпадают), а не по индексу, напишите обычную функцию
  поиска и подайте её hook-ом над корнем массива (`expected()` без search —
  значение под `data_key` целиком). Hook возвращает найденный элемент (`None`,
  если не нашли) — ассерт остаётся во фреймворке, `None` валит проверку, что
  даёт и «найдено», и «равно ожидаемому» одной цепочкой.
- **Пустой результат jsonpath** (в т.ч. `$[*]` по пустому массиву) бросает
  `AssertionError` («No results»). Для проверки пустоты используйте `has_length(0)`
  по корню, а не jsonpath.

```python
response.expected("items", in_array=True).equal_to(2, any=True)  # хотя бы один == 2
response.expected("items")(index=0).equal_to(1)  # drill по индексу
response.expected("name")(hook=str.upper).equal_to("ABC")  # hook перед сравнением

# data_key — массив: непустота / конкретный элемент
response.expected().has_length_greater(0)  # значение под data_key (массив) непусто
response.expected("$[0].name").equal_to("abc")  # data[0].name

# все элементы: data[*].status — список; is_subset гарантирует, что каждый входит в множество
response.expected("$[*].status").is_subset(["active", "idle"])  # каждый status ∈ множество

# элемент отсутствует: data[*].request.test_id — список значений, not_contains — ни один не равен
response.expected("$[*].request.test_id").not_contains(test_id_b)


# кастомный поиск элемента по предикату: hook над корнем массива, дальше — штатные ассерты
def _mock_body(items: list, test_id: str, path: str, method: str):
    for item in items:
        req = item["request"]
        if (req["test_id"], req["path"], req["method"]) == (test_id, path, method):
            return _normalize_body(item["response"]["body"])
    return None


response.expected()(hook=lambda items: _mock_body(items, test_id_a, "/api/shared", "POST")).equal_to({"owner": "A1"})
```

---

## Polling

`timeout`/`delay` из `AssertConfig` — бейзлайн. matchcrest повторяет проверку
(рефетчая ответ между попытками через `resq.http.Response.reload()` — повтор того
же запроса in-place) до успеха или истечения `timeout`, делая паузу `delay`.
Per-call `timeout`/`delay` kwargs переопределяют бейзлайн для одной проверки;
`None` (по умолчанию) — одна попытка без polling. Источник бейзлайна — `AssertConfig`
(`timeout`/`delay`).

## Pluggable классы

`assert_field_class`/`assert_response_class` (dotted `module:Class`) подключают
кастомные подклассы `AssertField`/`Expected` (должны наследовать встроенные);
оба грузятся через `load_assert_class` в точке построения field/response-класса.
`None` — встроенные классы.

```python
Api(base_url=..., assert_field_class="myproj.asserts:StrictAssertField")
```

## Особенности pybuggy

- контексты оборачивают `resq.http.Response`;
- polling (`timeout`/`delay`): между попытками ответ рефетчится повтором того же
  запроса in-place;
- pybuggy — plain-классы, без слоя отчётности (ассерты не зависят от pytest и не
  ведут отчёт по шагам);
- конфигурация проверок собрана в `AssertConfig` и доходит до матчёров через
  диспетчеры.