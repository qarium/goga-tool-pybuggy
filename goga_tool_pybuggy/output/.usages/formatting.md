# goga_tool_pybuggy.output — форматирование вывода команд

## Предметная область

Шаблоны потребления cell `goga_tool_pybuggy/output`: форматирование эндпоинтов в текст (`list`) и JSON (`info`). Аудитория — команды `list`/`info`. Форматтеры — чистые функции; печать в stdout делает команда-вызыватель.

## Вывод list (текст)

```python
from goga_tool_pybuggy.output import render_list

block = render_list(name, location, endpoints)
print(block)
```

Формат блока:
```
client (.specs/openapi/client/client-openapi.yaml)
* clients_startup_get -> [GET] /clients/startup
```
- Заголовок: `<name> (<location>)`; METHOD в верхнем регистре; path — исходный (со скобками).

## Вывод info (JSON)

```python
from goga_tool_pybuggy.output import render_info

print(render_info(endpoints))  # один объект или массив при коллизии
```

Ключи фиксированы (PascalCase): `Method` (нижний регистр), `Path` (`{param}`→`:param`), `Request`, `Response`, `QueryParams`, `Description`. При нескольких совпадениях — JSON-массив объектов.

Date-значения из спецификации (примеры `format: date`/`date-time`, которые Prance превращает в `datetime.date`/`datetime.datetime`) попадают в JSON как ISO 8601-строки — сериализация для них не падает.

## Предусловия

- Передавайте уже извлечённые `Endpoint`.
- Форматтеры не пишут в stdout — вызыватель решает, куда печатать.
