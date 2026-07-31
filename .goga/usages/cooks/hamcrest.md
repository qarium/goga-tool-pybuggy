# PyHamcrest

Библиотека декларативных матчёров (Hamcrest для Python). matchcrest построен поверх неё.

## Точка проверки — assert_that

```python
from hamcrest import assert_that

assert_that(actual, matcher)        # базовая форма
assert_that(actual, matcher, reason)  # с префиксом сообщения
```

Применяет `matcher` к `actual`; при несовпадении поднимает `AssertionError` с описанием
ожидания и реального значения (из `describe_to` / `describe_mismatch` матчера).

## Базовый матчёр — BaseMatcher

`hamcrest.core.base_matcher.BaseMatcher` — базовый класс для кастомных матчёров.

- `_matches(self, item) -> bool` — ядро проверки; вызывается движком `assert_that`.
- `describe_to(self, description)` — записывает ожидание в `Description`.
- `describe_mismatch(self, item, mismatch_description)` — записывает фактическое расхождение.

`hamcrest.core.description.Description` — объект для накопления текста описания
(`append_text`, и т.п.).

## Использование в matchcrest

`matchcrest.matchers.base.BaseMatcher` наследует `hamcrest.core.base_matcher.BaseMatcher` и
переопределяет `_matches` (retry/timeout-цикл), делегируя саму проверку хуку `_assert`.
Корневой фасад реэкспортит `assert_that` из `hamcrest` как точку входа проверок.