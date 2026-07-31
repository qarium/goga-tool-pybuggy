# jsonschema — валидация тела ответа (Draft7Validator)

## Предметная область

`jsonschema` валидирует JSON-тело ответа (`resq.http.Response.json()`) против json-схемы.
Используется ячейкой `goga_tool_pybuggy/api/asserts`: методы `Expected.jsonschema_is_valid`
(одна схема dict/путь) и `Expected.jsonschemas_is_valid` (каталог схем по статусу), а также
авто-валидация positive-пути (по файлу `schemas/<status>*.json`).

```python
import jsonschema
from pathlib import Path

schema = json.loads(Path("schemas/200.json").read_text(encoding="utf-8"))
jsonschema.Draft7Validator(schema).validate(response.json())  # raises ValidationError при ошибке
```

---

## Draft7Validator — базовый контракт

- `jsonschema.Draft7Validator(schema)` строит валидатор; `.validate(instance)` выбрасывает
  `jsonschema.exceptions.ValidationError`, когда `instance` не соответствует схеме.
- В pybuggy `instance` — это всегда `response.json()` (распарсенное тело ответа).
- Схема — обычный dict (json-schema: `type`, `properties`, `required`, `items`, и т.п.).

Схема может быть загружена из dict напрямую или прочитана из `.json`-файла (UTF-8):
```python
if isinstance(schema, str):
    schema = json.loads(Path(schema).read_text(encoding="utf-8"))
jsonschema.Draft7Validator(schema).validate(body)
```

---

## Авто-валидация по статусу

`Expected` на positive-пути грузит **первый** файл из `schemas_dir`, чьё имя начинается со
строки фактического статус-кода (`str(response.status_code)`), и валидирует тело. Файлы
сортируются — берётся первый совпадающий:

```python
code = str(response.status_code)
for entry in sorted(schemas_dir.iterdir()):
    if entry.is_file() and entry.name.startswith(code):
        schema = json.loads(entry.read_text(encoding="utf-8"))
        jsonschema.Draft7Validator(schema).validate(response.json())
        return
```

Когда `schemas_dir` нет / не каталог / нет файла под статус — авто-валидация **тихо
пропускается** (без ошибки).

---

## OpenAPI-flavored схемы — ограничение Draft7

Response-схемы пишутся из OpenAPI-спеки и могут не содержать принудительного `$schema`, а также
нести ключевые слова, которые `Draft7Validator` не понимает (`nullable`, и т.п.). По умолчанию
используется именно `Draft7Validator`. Если такие расхождения проявятся как ложные
ошибки/пропуски — переключиться на `openapi-schema-validator`; текущий контракт этого не делает.
