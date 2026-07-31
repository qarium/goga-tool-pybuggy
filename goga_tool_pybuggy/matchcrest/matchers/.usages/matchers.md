# matchcrest/matchers — механика матчеров

## Предметная область

Клетка матчеров matchcrest: базис (`BaseContext`, `BaseMatcher`, `MatchResult`) и конкретные матчёры
для значений, HTTP-ответов и исключений. Аудитория — прямые потребители матчёров и авторы кастомных
матчёров. Описывает, как подать данные в матча, применить его через `assert_that` и расширить
`BaseMatcher`. Каталог «какой матча для какой проверки» — в корневой клетке `pybuggy.matchcrest`.

Все матчёры построены на PyHamcrest: `BaseMatcher` наследует `hamcrest.core.base_matcher.BaseMatcher`,
а `assert_that(actual, matcher)` запускает проверку.

---

## Фасад

```python
from pybuggy.matchcrest.matchers import (
    BaseContext, BaseMatcher, MatchResult,
    ValueIsEqualMatcher, ResponseCodeMatcher, RaisedExceptionMatcher,  # ...и т.д.
)
```

---

## Контракт источника данных — BaseContext

Матчёр ничего не знает про HTTP или requests: он читает значение из контекста `item`. Потребитель
реализует `BaseContext`, открывая `value`, `key` и `update()`:

```python
from pybuggy.matchcrest.matchers import BaseContext

class ResponseContext(BaseContext):
    def __init__(self, response):
        self._response = response

    @property
    def value(self):
        return self._response.status_code

    @property
    def key(self):
        return self._response.url

    def update(self):
        self._response = refetch(self._response.url)  # для retry между попытками
```

- `value` — проверяемое значение; `key` — метка источника (попадает в сообщения).
- `update()` вызывается между попытками retry (когда `proofs > 1` или `timeout` задан).

---

## Применение матчера через assert_that

```python
from hamcrest import assert_that
from pybuggy.matchcrest.matchers import ResponseCodeMatcher

assert_that(ResponseContext(response), ResponseCodeMatcher(200, timeout=10))
```

- Конструкция матчера: `(expected_value, *, proofs, timeout, delay)` + опции конкретного матчера.
- `timeout`/`proofs`/`delay` управляют retry: матч повторяется, пока не станет зелёным или не выйдет timeout.

---

## Value-матчёры — модификаторы any / in_array

Value-матчёры принимают `any` и `in_array` (оба по умолчанию False):

- `in_array=True` — `item.value` трактуется как коллекция; матча проверяет каждый элемент.
- `any=True` (только вместе с `in_array`) — достаточно первого успешного элемента.

```python
from pybuggy.matchcrest.matchers import ValueIsEqualMatcher

ValueIsEqualMatcher("admin", any=True, in_array=True)  # хотя бы один элемент == "admin"
```

---

## Свой матча — расширение BaseMatcher

Реализуйте единственный хук `_assert(item) -> MatchResult`:

```python
from pybuggy.matchcrest.matchers import BaseMatcher, MatchResult

class StatusCodeInRange(BaseMatcher):
    def _assert(self, item) -> MatchResult:
        code = item.value
        ok = 200 <= code < 300
        return MatchResult(
            ok,
            expectations=[f'"{item.key}" code should be 2xx'],
            errors=None if ok else [f'{code} is not 2xx'],
        )
```

- `_assert` вызывается движком `BaseMatcher._matches` (retry/timeout/report берётся на себя).
- Возвращайте `MatchResult(False, errors=..., expectations=...)` при провале — оба списка обязательны.
