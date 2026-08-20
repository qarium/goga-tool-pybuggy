# matchcrest/utils — вспомогательные routines

## Предметная область

Внутренняя utility-клетка matchcrest: retry-цикл, URL-хелперы, конвертация дат и декоратор
`allow_failure`. Аудитория — клетка `matchers` (импортирует `waiting_for`, `allow_failure`,
`date_to_timestamp`, `url_is_valid`) и редкие прямые потребители `allow_failure` (реэкспорт
через корень matchcrest). Содержит готовые шаблоны потребления фасада.

---

## Фасад

```python
from goga_tool_pybuggy.matchcrest.utils import (
    waiting_for,
    join,
    url_is_valid,
    url_is_live,
    date_to_timestamp,
    allow_failure,
)
```

---

## Retry-цикл

`waiting_for` вызывает функцию, пока она не вернёт truthy-значение или не выйдет timeout.

```python
from goga_tool_pybuggy.matchcrest.utils import waiting_for


def ready() -> bool:
    return poll_resource()  # True когда ресурс готов


try:
    result = waiting_for(ready, timeout=10, delay=0.5)
except TimeoutError:
    ...
```

- `args`/`kwargs` — позиционные/именованные аргументы вызова `f`.
- `hook` — опц. трансформер возвращаемого значения перед проверкой truthiness.

---

## URL-хелперы

```python
from goga_tool_pybuggy.matchcrest.utils import join, url_is_valid

join("https://api.example.com/", "/v1/", "/users/")  # 'https://api.example.com/v1/users/'
url_is_valid("https://example.com")  # True (структурно)
url_is_valid("https://example.com", is_live=True)  # True только при ответе 2xx
```

- `url_is_valid` принимает относительные ссылки (подставляет первый allowed-протокол).
- `is_live=True` делает реальный GET через `url_is_live` — это сетевой побочный эффект.

---

## Конвертация дат

```python
from datetime import date
from goga_tool_pybuggy.matchcrest.utils import date_to_timestamp

ts = date_to_timestamp(date(2026, 7, 14))  # float
```

- Принимает только `date`/`datetime`; иначе ValueError.

---

## Декоратор allow_failure

Гасит любое исключение, логирует его, возвращает None. Применяется внутри matchcrest для
безопасной записи отчёта (`BaseMatcher.__save_report__`).

```python
from goga_tool_pybuggy.matchcrest.utils import allow_failure


@allow_failure
def risky(): ...
```
