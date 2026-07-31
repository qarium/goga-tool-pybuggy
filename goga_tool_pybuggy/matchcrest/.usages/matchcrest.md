# goga_tool_pybuggy.matchcrest — проверка ответов и значений матчёрами

## Предметная область

matchcrest — библиотека Hamcrest-матчёров для assert-проверок HTTP-ответов, значений и исключений.
Аудитория — авторы тестов, которые хотят декларативных проверок через `assert_that(actual, matcher)`.
Содержит готовые шаблоны: подать данные в матча, выбрать нужный по каталогу, применить через assert_that.

matchcrest построен на PyHamcrest: матчёры наследуют `BaseMatcher`, а `assert_that` запускает проверку.

---

## Фасад

```python
from goga_tool_pybuggy.matchcrest import assert_that, ResponseCodeMatcher, ValueIsEqualMatcher
```

- `assert_that` — точка проверки (реэкспорт из hamcrest).
- Матчёры — конструируются с `expected_value` (+ опции), применяются к источнику данных.

---

## Модель проверки

Матчёр не знает про HTTP/requests — он читает значение из контекста `BaseContext`. Минимальный сценарий:

```python
from goga_tool_pybuggy.matchcrest import assert_that, BaseContext, ResponseCodeMatcher

class Ctx(BaseContext):
    def __init__(self, response):
        self._r = response
    @property
    def value(self): return self._r.status_code
    @property
    def key(self): return self._r.url
    def update(self): self._r = refetch(self._r.url)

assert_that(Ctx(response), ResponseCodeMatcher(200))
```

- `value` — проверяемое значение; `key` — метка источника (в сообщениях); `update()` — рефетч для retry.

---

## Каталог матчёров — ответы (response)

| Матчёр | Проверка |
|---|---|
| `ResponseCodeMatcher(code)` | код статуса (int/Enum/`"ok"` из requests.codes) |
| `ResponseHeadersByKeyMatcher(key, *, contains/startswith/endswith, count)` | наличие заголовка по ключу |
| `ResponseHeadersByValueMatcher(value, *, key, contains/startswith/endswith)` | значение заголовка по ключу |
| `ResponseBodyMatcher(body)` | равенство тела |
| `JsonschemaMatcher(schema)` | тело-JSON соответствует jsonschema |
| `JsonHasDataByKeyMatcher(key)` / `JsonHasNotDataByKeyMatcher(key)` | (нет) данных по ключу |
| `JsonContainsKeyMatcher(path)` | вложенный путь ключей существует |

```python
assert_that(Ctx(response), ResponseCodeMatcher("ok"))
assert_that(JsonCtx(response), JsonHasDataByKeyMatcher("data"))
```

## Каталог матчёров — значения (value)

Опции `any`/`in_array`: `in_array=True` — значение трактуется как коллекция; `any=True` (с `in_array`) — достаточно первого успеха.

| Матчёр | Проверка | Доп. опции |
|---|---|---|
| `ValueIsEqualMatcher(v)` / `ValueIsNotEqualMatcher(v)` | (не) равно | `strict` (через `is`) |
| `ValueIsGreaterMatcher(v)` / `ValueIsLesserMatcher(v)` | больше/меньше | `or_equal` |
| `ValueContainsMatcher(v)` / `ValueNotContainsMatcher(v)` | (не) содержит | — |
| `ValueIsInMatcher(c)` / `ValueIsNotInMatcher(c)` | (не) входит в коллекцию | — |
| `ValueLengthEqualMatcher(n)` / `Greater` / `Lesser` | длина равна/больше/меньше | — |
| `ValueContainsDictMatcher(d)` | dict содержит пары key/value | — |
| `ValueStartsWithMatcher(s)` / `ValueEndsWithMatcher(s)` | префикс/суффикс | — |
| `ValueRegexMatcher(pattern)` | соответствие regex | — |
| `ValueIsEmpty()` / `ValueIsNotEmpty()` | пусто/не пусто | — |
| `ValueIsUrlMatcher(*, is_live, allowed_protocols)` | валидный URL (+опц. liveness) | `is_live`, протоколы |
| `ValueDateEqualMatcher(d)` / `Greater` / `Lesser` | дата равна/больше/меньше (через timestamp) | — |
| `ValueIsSubsetMatcher(s)` / `ValueIsDisjointMatcher(s)` | подмножество/не пересекается | — |

```python
assert_that(ValCtx(row), ValueIsEqualMatcher("admin"))
assert_that(ValCtx(tags), ValueIsInMatcher(["a", "b"], any=True, in_array=True))
```

## Каталог матчёров — исключения (error)

| Матчёр | Проверка |
|---|---|
| `RaisedExceptionMatcher((expected_types, raised_exc))` | поднятое исключение входит в expected_types |
| `NotRaisedExceptionMatcher(raised_exc_or_None)` | исключение не поднято |

```python
assert_that(ExcCtx(call_result), RaisedExceptionMatcher(((ValueError,), raised_exc)))
```

---

## Retry

Любой матча принимает `proofs`/`timeout`/`delay` — движок `BaseMatcher` повторяет `_assert`, вызывая
`item.update()` между попытками, пока результат не станет зелёным или не выйдет timeout.

```python
assert_that(Ctx(response), ResponseCodeMatcher(200, timeout=10, delay=0.5))
```
