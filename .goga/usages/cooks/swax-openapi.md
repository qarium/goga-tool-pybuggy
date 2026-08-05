# swax.openapi — разбор спецификаций и экстракция эндпоинтов

## Предметная область

Шаблоны потребления парсящей cell `swax.openapi` в CLI `pybuggy`. Из swax используется **только** этот модуль — для разбора спецификаций. `pybuggy` НЕ использует `swax.git`, `swax.fs`, `swax.config`, `swax.cli`.

Публичный API (фасад `swax.openapi`):
- `parse_spec(spec_path: Path) -> dict` — полностью разыменованная спека (Prance инлайнит `$ref`).
- `discover_specs(root: Path) -> list[Path]` — дешёвое перечисление файлов спек в каталоге.
- `extract_paths` / `extract_schemas` — **не используем** (см. ниже).
- `SpecParseError` — доменная ошибка разбора.

---

## Главное правило: extract_paths отбрасывает методы

`swax.openapi.extract_paths` сознательно возвращает **только** шаблоны путей, без HTTP-методов — граф отслеживаемости swax оперирует путями. `pybuggy` же работает с эндпоинтами метод+путь и строит `endpoint_id` из обоих. Поэтому **извлечение операций pybuggy делает сам** поверх dict из `parse_spec`, а `extract_paths`/`extract_schemas` не вызывает.

---

## Разбор спецификации

`parse_spec` возвращает dict с уже инлайнеными `$ref` — разрешать ссылки вручную не нужно. Swagger 2.0 и OpenAPI 3.x обрабатываются прозрачно; поле `type` в конфиге `pybuggy` носит декларативный характер и не влияет на разбор.

```python
from pathlib import Path
from swax.openapi import parse_spec

def load_spec(spec_location: str, project_root: Path) -> dict:
    return parse_spec(project_root / spec_location)
```

Соглашения потребителя:
- `spec_location` — путь от корня проекта до файла спеки (значение `specs.<name>.location` из конфига).
- Принимает `.yaml`, `.yml`, `.json`.
- При ошибке разбора выбрасывает `SpecParseError(path=..., reason=...)` — CLI-handler маппит в `click.ClickException`.

---

## Определение версии спецификации

Формат определяется **по содержимому спеки**, а не по декларативному полю конфига `SpecEntry.type`. Этим управляет `detect_spec_version` из cell `spec`.

```python
def detect_spec_version(spec: dict) -> str:
    # Swagger 2.0: top-level "swagger": "2.0"; OpenAPI 3.x: top-level "openapi": "3.x"
    if "swagger" in spec:
        return "swagger"
    if "openapi" in spec:
        return "openapi"
    raise ValueError("spec declares neither a swagger nor an openapi version")
```

Соглашения потребителя:
- Проверка по наличию top-level ключа `swagger` (Swagger 2.0) против `openapi` (OpenAPI 3.x).
- Спека без top-level ключа `swagger` или `openapi` некорректна — выбрасывается ValueError (валидная спека обязана объявить версию).
- Не использовать `SpecEntry.type` для выбора пути извлечения.

---

## Экстракция эндпоинтов (своя, поверх parsed spec)

Операции живут в `spec["paths"][path][method]`, где `method` — `get`/`post`/`put`/`delete`/`patch`/`options`/`head`. Схемы уже инлайнированы Prance, поэтому `$ref` нигде не разрешаем. Поля операции извлекаются по структуре, выбранной `detect_spec_version`; оба формата приводятся к идентичной нормализованной форме.

```python
HTTP_METHODS = ("get", "post", "put", "delete", "patch", "options", "head")

def iter_operations(spec: dict):
    for path, item in spec.get("paths", {}).items():
        for method in HTTP_METHODS:
            operation = item.get(method)
            if operation is not None:
                yield method, path, operation
```

Соглашения потребителя:
- Ключи-не-методы (`parameters`, `summary` на уровне path-item) пропускаем.
- Параметры path-item (`item["parameters"]`) наследуются всеми операциями; мерджим с `operation["parameters"]`.

### Поля операции — OpenAPI 3.x

```python
def extract_request_schema_openapi(operation: dict) -> dict:
    content = operation.get("requestBody", {}).get("content", {})
    return content.get("application/json", {}).get("schema", {})

def extract_response_schemas_openapi(operation: dict) -> dict:
    return {
        code: resp.get("content", {}).get("application/json", {}).get("schema", {})
        for code, resp in operation.get("responses", {}).items()
    }

def extract_query_params_openapi(operation: dict) -> dict:
    return {p["name"]: p.get("schema", {}) for p in operation.get("parameters", []) if p.get("in") == "query"}
```

### Поля операции — Swagger 2.0

В Swagger 2.0 структура иная: request body задаётся параметром `in: body` с корневым `schema`; response — `responses[code].schema` напрямую без обёртки `content`; поля типа инлайнятся в сам параметр (нет вложенного `schema`); nullable обозначается `x-nullable`.

```python
def extract_request_schema_swagger(operation: dict) -> dict:
    for p in operation.get("parameters", []):
        if p.get("in") == "body":
            return p.get("schema", {})
    return {}

def extract_response_schemas_swagger(operation: dict) -> dict:
    return {code: resp.get("schema", {}) for code, resp in operation.get("responses", {}).items()}

_TYPE_FIELDS = ("type", "format", "items", "enum", "default", "description", "x-nullable")
# `x-nullable` включён намеренно: иначе ключевое слово удаляется фильтрацией полей до
# nullable-нормализации и nullability query-параметра теряется (см. cell spec / design review).
def extract_query_params_swagger(operation: dict) -> dict:
    result = {}
    for p in operation.get("parameters", []):
        if p.get("in") == "query":
            result[p["name"]] = {k: v for k, v in p.items() if k in _TYPE_FIELDS}
    return result
```

Соглашения потребителя (оба формата):
- `Request` / `Response` / `QueryParams` в выводе `info` — уже **развёрнутые** схемы (Prance всё инлайнил).
- Primary content-type — `application/json`; при его отсутствии поля пусты (`{}`).
- `Description` = `operation.get("description", "")`.
- Оба формата приводятся к идентичной нормализованной форме перед попаданием в `Endpoint` (nullable-нормализация выполняется внутри cell `spec`).

---

## Маппинг ошибок в CLI

```python
import click
from swax.openapi import SpecParseError, parse_spec

def safe_parse(spec_path: Path) -> dict:
    try:
        return parse_spec(spec_path)
    except SpecParseError as exc:
        raise click.ClickException(f"failed to parse spec {exc.path}: {exc.reason}") from exc
```

---

## Тестирование

- Разбор/экстракцию тестировать на фикстурах-спеках в `tmp_path` (без моков — чистая логика поверх dict).
- Swagger 2.0 и OpenAPI 3.x кейсы — inline-спеки как dict, с утверждением эквивалентности нормализованных схем при одинаковой семантике операций.
