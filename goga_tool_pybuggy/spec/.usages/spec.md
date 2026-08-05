# goga_tool_pybuggy.spec — разбор спек и извлечение эндпоинтов

## Предметная область

Шаблоны потребления cell `goga_tool_pybuggy/spec`: разбор spec-файла в dict и извлечение эндпоинтов (метод+путь + развёрнутые схемы). Аудитория — команды `list`/`info`.

## Разбор spec-файла

```python
from goga_tool_pybuggy.spec import load_spec

spec = load_spec(spec_path)  # pathlib.Path; $ref уже инлайнированы Prance
```

При ошибке разбора `load_spec` бросает `click.ClickException` (маппинг `SpecParseError` из swax).

## Извлечение эндпоинтов

```python
from goga_tool_pybuggy.spec import extract_endpoints

endpoints = extract_endpoints(spec)  # list[Endpoint], один на метод+путь
for ep in endpoints:
    ep.id            # 'clients_startup_get' — computed через build_endpoint_id
    ep.method        # 'get' (нижний регистр)
    ep.path          # '/clients/{id}'
    ep.request       # развёрнутая схема request body (или {})
    ep.response      # {status: schema}
    ep.query_params  # {name: schema}
```

Схемы в `request`, `response`, `query_params` уже **nullable-нормализованы** для JSON-Schema: OpenAPI `nullable: true` переписан в union-форму (`type` со списком, включающим `"null"`), ключ `nullable` удалён. Валидатор `jsonschema` игнорирует OpenAPI `nullable`, поэтому нормализация выполнена на границе разбора — потребителю не нужно нормализовать схемы повторно.

## Идентификатор эндпоинта

`build_endpoint_id(method, path)` — чистая функция; `Endpoint.id` вычисляется из неё. Детерминирован: одинаковые метод+путь → одинаковый id; коллизии обрабатываются на уровне команды `info`.

## Предусловия

- `spec` должен быть полностью разыменован (используйте `load_spec`; не разыменяйте `$ref` вручную).
- Извлечение — чистая логика над dict, тестируется без моков.
