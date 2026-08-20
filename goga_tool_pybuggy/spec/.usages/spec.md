# goga_tool_pybuggy.spec — разбор спек и извлечение эндпоинтов

## Предметная область

Шаблоны потребления cell `goga_tool_pybuggy/spec`: разбор spec-файла в dict и извлечение эндпоинтов (метод+путь + развёрнутые схемы) для спецификаций **Swagger 2.0 и OpenAPI 3.x**. Формат определяется автоматически по содержимому спеки. Аудитория — команды `list`/`info`/`generate` и cell `output`.

## Разбор spec-файла

```python
from goga_tool_pybuggy.spec import load_spec

spec = load_spec(spec_path)  # pathlib.Path; $ref уже инлайнированы Prance
```

При ошибке разбора `load_spec` бросает `click.ClickException` (маппинг `SpecParseError` из swax).

## Определение версии

```python
from goga_tool_pybuggy.spec import detect_spec_version

version = detect_spec_version(spec)  # "swagger" (Swagger 2.0) | "openapi" (OpenAPI 3.x)
```

Версия определяется по наличию top-level ключа `swagger` против `openapi`, а не по декларативному `SpecEntry.type`. Спека без обоих ключей некорректна — `detect_spec_version` выбрасывает `ValueError`. Выбор пути извлечения управляется этой версией внутри `extract_endpoints` — потребителю обычно не нужно вызывать `detect_spec_version` вручную.

## Извлечение эндпоинтов

```python
from goga_tool_pybuggy.spec import extract_endpoints

endpoints = extract_endpoints(spec)  # list[Endpoint], один на метод+путь
for ep in endpoints:
    ep.id  # 'clients_startup_get' — computed через build_endpoint_id
    ep.method  # 'get' (нижний регистр)
    ep.path  # '/clients/{id}'
    ep.request  # развёрнутая схема request body (или {})
    ep.response  # {status: schema}
    ep.query_params  # {name: schema}
```

Семантика по форматам одинакова на выходе: для OpenAPI 3.x request/response/query извлекаются из структуры `requestBody`/`responses[code].content`/`parameters[].schema`; для Swagger 2.0 — из параметра `in: body`/`responses[code].schema`/инлайн-полей параметра `in: query`. Оба формата дают одну и ту же нормализованную модель `Endpoint` при одинаковой семантике операций.

## Nullable-нормализация

Схемы в `request`, `response`, `query_params` уже **nullable-нормализованы** для JSON-Schema: OpenAPI `nullable: true` и Swagger `x-nullable: true` переписаны в union-форму (`type` со списком, включающим `"null"`, с anyOf-фолбэком при невозможности разместить union в одном `type`), ключи `nullable`/`x-nullable` удалены. Валидатор `jsonschema` игнорирует оба ключевых слова, поэтому нормализация выполнена на границе разбора — потребителю не нужно нормализовать схемы повторно.

## Идентификатор эндпоинта

`build_endpoint_id(method, path)` — чистая функция; `Endpoint.id` вычисляется из неё. Детерминирован: одинаковые метод+путь → одинаковый id; коллизии обрабатываются на уровне команды `info`.

`Endpoint.id` гарантированно является **валидным Python-идентификатором**: дефисы в пути нормализуются в `_` (например `/clients/payment-details` → `clients_payment_details_post`). Это важно, так как id используется как имя pytest-фикстуры и как имя директории-пакета при генерации (`generate`) — без нормализации сгенерированный модуль был бы синтаксически некорректен.

## Предусловия

- `spec` должен быть полностью разыменован (используйте `load_spec`; не разыменяйте `$ref` вручную).
- Извлечение — чистая логика над dict, тестируется без моков.
