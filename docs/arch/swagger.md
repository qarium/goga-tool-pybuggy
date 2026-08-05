# Architecture Plan — Поддержка спецификаций Swagger 2.0 в экстракции эндпоинтов

- **Topic:** `swagger`
- **Plan path:** `docs/arch/swagger.md`
- **Affected cell:** `goga_tool_pybuggy/spec` (**modify / extend** — новых ячеек нет)
- **Approvals:** PRIMARY_ANALYSIS (q3), TYPE_MAP (q4), TYPE_DETAIL (q5), CELL_DISTRIBUTION (q6), CONTRACTS (q7, q8), CELL_ASSEMBLY (q9) — получены.

---

## Implementation Order

Один ячейка-артефакт; цикл из одной итерации. Порядок leaves → root тривиален — `spec` это leaf в графе ячеек проекта.

1. **`goga_tool_pybuggy/spec`** — extend. **Причина порядка:** leaf (0 Imports из ячеек проекта; внешняя зависимость только `swax.openapi`). Потребители (`commands/*`, `output`, `api/asserts`) не модифицируются — их Imports из `spec` сохраняются, форма `Endpoint` стабильна.

Внутри ячейки порядок артефактов:
1. `.goga/usages/cooks/swax-openapi.md` (cook usage) — шаблоны экстракции Swagger 2.0 + определение версии.
2. `goga_tool_pybuggy/spec/.usages/spec.md` (cell-level usage) — Swagger-семантика на выходе.
3. `goga_tool_pybuggy/spec/CODEMANIFEST` — контракты (`detect_spec_version` новый, `extract_endpoints` расширен).

---

## Artifacts

> Все артефакты — **модификация существующих**. Ниже: полный целевой контент каждого файла + краткий diff.

### Cell: `goga_tool_pybuggy/spec` (MODIFIED — extend)

#### 1. `.goga/usages/cooks/swax-openapi.md` (MODIFIED)

**Diff:**
- ADD раздел «Определение версии спецификации» (`detect_spec_version`).
- ADD подраздел «Поля операции — Swagger 2.0» (`extract_request_schema_swagger` / `extract_response_schemas_swagger` / `extract_query_params_swagger`).
- CHANGE вводная «Экстракция эндпоинтов»: упомянуть маршрутизацию по версии и эквивалентность форматов.
- NOTE: nullable-нормализация сюда НЕ выносится — это внутренняя логика cell `spec` (см. CODEMANIFEST + `spec.md`).

**Полный целевой контент:**

````markdown
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

_TYPE_FIELDS = ("type", "format", "items", "enum", "default", "description")
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
````

#### 2. `goga_tool_pybuggy/spec/.usages/spec.md` (MODIFIED)

**Diff:**
- CHANGE «Предметная область»: упомянуть Swagger 2.0 и OpenAPI 3.x + автоопределение формата.
- ADD раздел «Определение версии» (`detect_spec_version` в фасаде).
- CHANGE «Извлечение эндпоинтов»: добавить семантику по форматам (эквивалентность на выходе).
- CHANGE «Nullable-нормализация»: расширить на `x-nullable`.

**Полный целевой контент:**

````markdown
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
    ep.id            # 'clients_startup_get' — computed через build_endpoint_id
    ep.method        # 'get' (нижний регистр)
    ep.path          # '/clients/{id}'
    ep.request       # развёрнутая схема request body (или {})
    ep.response      # {status: schema}
    ep.query_params  # {name: schema}
```

Семантика по форматам одинакова на выходе: для OpenAPI 3.x request/response/query извлекаются из структуры `requestBody`/`responses[code].content`/`parameters[].schema`; для Swagger 2.0 — из параметра `in: body`/`responses[code].schema`/инлайн-полей параметра `in: query`. Оба формата дают одну и ту же нормализованную модель `Endpoint` при одинаковой семантике операций.

## Nullable-нормализация

Схемы в `request`, `response`, `query_params` уже **nullable-нормализованы** для JSON-Schema: OpenAPI `nullable: true` и Swagger `x-nullable: true` переписаны в union-форму (`type` со списком, включающим `"null"`, с anyOf-фолбэком при невозможности разместить union в одном `type`), ключи `nullable`/`x-nullable` удалены. Валидатор `jsonschema` игнорирует оба ключевых слова, поэтому нормализация выполнена на границе разбора — потребителю не нужно нормализовать схемы повторно.

## Идентификатор эндпоинта

`build_endpoint_id(method, path)` — чистая функция; `Endpoint.id` вычисляется из неё. Детерминирован: одинаковые метод+путь → одинаковый id; коллизии обрабатываются на уровне команды `info`.

## Предусловия

- `spec` должен быть полностью разыменован (используйте `load_spec`; не разыменяйте `$ref` вручную).
- Извлечение — чистая логика над dict, тестируется без моков.
````

#### 3. `goga_tool_pybuggy/spec/CODEMANIFEST` (MODIFIED)

**Diff:**
- **ADD** тип `detect_spec_version` (новый Routine, `location: extract.py`): формат определяется по содержимому; для спеки без ключей `swagger`/`openapi` выбрасывается `ValueError`.
- **CHANGE** аннотацию `extract_endpoints`: шаг 2 (detect version) в Algorithm; расширение Requirements (per-format OpenAPI 3.x / Swagger 2.0 + расширенная nullable-нормализация для `nullable` и `x-nullable`); расширение Constraints (format-equivalence, propagation `ValueError` из `detect_spec_version` для некорректной версии, без `basePath`/`servers`, без `consumes`/`produces`, без `formData`/file-upload).
- **CHANGE** global Annotations: строка про dual-format routing + нормализацию.
- **CHANGE** Footer Description: добавить «for Swagger 2.0 and OpenAPI 3.x».
- **UNCHANGED:** `Usages` (header), `build_endpoint_id`, `Endpoint`, `load_spec`.

**Полный целевой контент CODEMANIFEST:**

```yaml
Usages:
  conventions: .goga/usages/conventions.md
  swax-openapi: .goga/usages/cooks/swax-openapi.md
  click: .goga/usages/cooks/click.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `swax-openapi` for parsing specs via swax.openapi and the endpoint-extraction patterns over the parsed dict (both Swagger 2.0 and OpenAPI 3.x).
  Use `click` for mapping SpecParseError to ClickException in `load_spec` (uniform non-zero exit).

  Use relative imports inside the cell.
  Extraction is pure logic over the parsed dict — $ref are already inlined by Prance (see `swax-openapi`).
  Extraction routes each spec by version detected from its content (swagger "2.0" vs openapi "3.x") and normalizes both formats to the same JSON-Schema shape on `Endpoint`.
  Keep only HTTP methods in path-items; merge path-item parameters into operations when present.

---

"build_endpoint_id(method: str, path: str) -> endpoint_id: str":
  location: endpoint_id.py
  annotations: |
    Deterministic id derived from an HTTP method and path template.

    `method`: HTTP method (e.g. POST, GET) — normalized to lower.
    `path`: path template (e.g. /v1/API/{name}) — leading slash and braces stripped.
    `endpoint_id`: stable lowercased identifier, e.g. v1_api_name_post.

    Algorithm:
    1. Drop a single leading "/" from `path`.
    2. Remove "{" and "}" from `path` (keep the parameter name).
    3. Lowercase the result.
    4. Replace every "/" with "_".
    5. Append "_" + method.lower().

    Requirements:
    - Verified on: POST /v1/API/{name} -> v1_api_name_post; GET /clients/startup -> clients_startup_get; DELETE /clients/profile -> clients_profile_delete.

    Constraints:
    - Pure function — no I/O, no parsing.

"Endpoint(method: str, path: str, request: dict[str, Any], response: dict[str, Any], query_params: dict[str, Any], description: str)":
  location: endpoint.py
  annotations: |
    A single endpoint extracted from a spec operation: method, path, and resolved request/response shapes.

    `method`: HTTP method, lowercased.
    `path`: path template with parameters in braces, e.g. /clients/{id}.
    `request`: resolved request-body schema (primary JSON content) or {}.
    `response`: {status_code: resolved_schema} for each response (primary JSON content).
    `query_params`: {param_name: schema} for query parameters only.
    `description`: operation description or "".

    Use `conventions` for pydantic model rules.

    Constraints:
    - `request`/`response`/`query_params` hold already-resolved schemas (Prance inlined refs — see `swax-openapi`), nullable-normalized to JSON-Schema union types by `extract_endpoints`.
  properties:
    "id -> str": |
      Stable identifier derived via `build_endpoint_id` from the endpoint's method and path. Computed field — not a constructor input.

"load_spec(spec_path: pathlib.Path) -> spec: dict[str, Any]":
  location: loader.py
  annotations: |
    Parse a spec file into a fully dereferenced dict via swax.openapi.

    `spec_path`: path to a .yaml/.yml/.json spec file (resolved from project root).
    `spec`: dereferenced specification dict with $ref inlined.

    Algorithm:
    1. Call swax.openapi.parse_spec(`spec_path`).
    2. On SpecParseError, raise click.ClickException carrying the path and reason.

    Requirements:
    - $ref must already be resolved by Prance — never resolve references manually downstream.

    Use `swax-openapi` for the parse_spec contract and error mapping.

"detect_spec_version(spec: dict[str, Any]) -> version: str":
  location: extract.py
  annotations: |
    Determine the spec format by inspecting the parsed spec's content, independent of the declarative config type.

    `spec`: dereferenced specification dict (output of `load_spec`).
    `version`: format identifier — "swagger" for Swagger 2.0, "openapi" for OpenAPI 3.x.

    Algorithm:
    1. If `spec` has a top-level swagger key (Swagger 2.0), return "swagger".
    2. Otherwise, if `spec` has a top-level openapi key (OpenAPI 3.x), return "openapi".
    3. Otherwise raise ValueError — the spec declares neither version, which contradicts both specifications.

    Requirements:
    - Detection is by spec content only — never by the declarative config type field.
    - A spec with neither a swagger nor an openapi top-level key is invalid; raise ValueError (a valid Swagger 2.0 spec must carry swagger, a valid OpenAPI 3.x spec must carry openapi).

    Constraints:
    - Pure function — no I/O, no parsing; raises ValueError on an unrecognized format.

"extract_endpoints(spec: dict[str, Any]) -> endpoints: list[Endpoint]":
  location: extract.py
  annotations: |
    Walk a parsed spec's operations and build an `Endpoint` for each method+path, routing field extraction by the detected format.

    `spec`: dereferenced specification dict (output of `load_spec`).
    `endpoints`: one `Endpoint` per declared operation.

    Algorithm:
    1. Read spec["paths"].
    2. Detect the spec format via `detect_spec_version`.
    3. For each path-item, for each HTTP method present in (get, post, put, delete, patch, options, head), take the operation.
    4. Build an `Endpoint` from the operation using the format-specific structure chosen by the detected version (see Requirements), normalizing every extracted schema to the JSON-Schema union nullable form (see Requirements).
    5. Compute each `Endpoint` id via `build_endpoint_id`.

    Requirements:
    - Skip non-method keys in path-items (parameters, summary).
    - Path-item parameters are inherited by all operations — merge with operation parameters when extracting query params.
    - Primary content type is application/json; absent fields default to {}.
    - OpenAPI 3.x: request from the operation requestBody content application/json schema; response from each responses[code] content application/json schema; query from each parameters[] entry whose in is query, via its nested schema.
    - Swagger 2.0: request from the parameter whose in is body, via its root schema; response from responses[code] schema directly (no content wrapper); query from each parameters[] entry whose in is query, via its inlined type/format/items/enum fields.
    - Each extracted schema is nullable-normalized to the JSON-Schema union form: OpenAPI nullable: true and Swagger x-nullable: true both become a type list including "null" (with an anyOf fallback when a single type cannot host the union); the originating key is dropped; recursion runs through properties, items, additionalProperties, and anyOf/oneOf/allOf. Required because the runtime jsonschema validator ignores both keywords, so an un-normalized fragment rejects null.

    Constraints:
    - Pure logic over `spec` — no I/O, no $ref resolution.
    - Both formats must yield the same normalized schema shape for equivalent operations.
    - A spec declaring neither a swagger nor an openapi version is invalid — `detect_spec_version` raises ValueError, which `extract_endpoints` propagates without swallowing.
    - Do not merge basePath/servers into path; path stays the path-item key.
    - Do not account for consumes/produces; media-type priority stays with application/json.
    - Do not extract formData or file-upload parameters (outside the query_params model).

    Use `swax-openapi` for the operation/field extraction patterns for both formats.

---

Author: Goga
CreatedAt: 02/07/26
Description: |
  Endpoint model, deterministic endpoint id, spec parsing via swax.openapi, and endpoint extraction for Swagger 2.0 and OpenAPI 3.x.
```

---

## Dependency Map

```
 goga_tool_pybuggy/spec   (MODIFIED — leaf: +detect_spec_version, ~extract_endpoints)
   ▲  Imports consumers use:
   ├── commands/info        ← load_spec, extract_endpoints, build_endpoint_id, Endpoint   (no change)
   ├── commands/list        ← load_spec, extract_endpoints                                 (no change)
   ├── commands/generate    ← load_spec, extract_endpoints, Endpoint                       (no change)
   └── output               ← Endpoint                                                     (no change)
 api/asserts                — consumes schemas inside Endpoint (jsonschema)                (no change)
```

Циклов нет: `spec` — leaf (0 Imports из ячеек проекта). Все связи однонаправлены (потребители → spec).

---

## Verification Checklist

**После имплементации каждого артефакта:**

- [ ] `swax-openapi.md`: Swagger 2.0 шаблоны экстракции (`in: body`, `responses[code].schema`, инлайн-поля `in: query`) корректны; раздел определения версии присутствует; OpenAPI 3.x шаблоны не изменены.
- [ ] `spec.md`: упомянуты оба формата + автоопределение; nullable-секция расширена на `x-nullable`.
- [ ] `CODEMANIFEST` (spec):
  - [ ] `detect_spec_version` объявлен как Routine с `location: extract.py`; фасад `__init__.py` экспортирует его через `__all__` (4 → 5).
  - [ ] `extract_endpoints` Algorithm содержит detect-version шаг; Requirements покрывают оба формата и `nullable`+`x-nullable`; Constraints включают format-equivalence и out-of-scope ограничения.
  - [ ] `build_endpoint_id`, `Endpoint`, `load_spec` — без изменений.
  - [ ] `Usages` ключи unchanged; каждый usage referenced в annotation (conventions/swax-openapi/click).
- [ ] `goga lint` для ячейки `spec` проходит без ошибок (`goga lint goga_tool_pybuggy/spec`).
- [ ] Тесты: `pytest tests/spec/test_extract.py` — существующие кейсы экстракции проходят: их фикстуры (минимальные dict без ключа версии) дополняются top-level ключом `openapi`, чтобы остаться валидными при строгом `detect_spec_version` (логика экстракции не меняется); новые Swagger 2.0 кейсы добавлены (inline-спеки как dict) и проходят; есть кейс эквивалентности нормализованных схем обоих форматов при одинаковой семантике; есть кейс, что спецификация без ключей `swagger`/`openapi` → `detect_spec_version` выбрасывает `ValueError`.
- [ ] Изоляция: `pytest` для `commands/info`, `commands/list`, `commands/generate`, `output` проходит без правок в их коде.

**Acceptance Criteria (канон) — покрытие:**

| # | Критерий | Покрытие |
|---|---|---|
| 1 | Swagger 2.0 → корректные request/response/query_params | ✓ Requirements `extract_endpoints` (Swagger 2.0 paths) |
| 2 | Эквивалентность Swagger 2.0 и OpenAPI 3.x | ✓ Constraint «same normalized schema shape» |
| 3 | `x-nullable` → union-форма, ключ удалён | ✓ Requirements nullable-нормализация |
| 4 | Поведение OpenAPI 3.x не меняется | ✓ Constraints + неизменные типы; фикстуры существующих тестов дополняются ключом `openapi` (логика экстракции без изменений) |
| 5 | Корректное определение версии | ✓ `detect_spec_version` |
| 6 | Swagger 2.0 тест-кейсы добавлены и проходят | ✓ Verification Checklist (tests) |
| 7 | Контракты + usage обновлены и согласованы | ✓ этот план (CODEMANIFEST + 2 usage) |
| 8 | `goga lint` для spec без ошибок | ✓ Verification Checklist (goga lint) |
| 9 | info/list/generate без правок работают со Swagger 2.0 | ✓ изоляция (форма `Endpoint` стабильна) |

Все 9 критериев покрыты архитектурой.

**Дополнительно (по итогам architecture-review):** контракт `detect_spec_version` уточнён — спецификация без top-level ключа `swagger`/`openapi` противоречит формату и обрабатывается выбросом `ValueError` (канонический встроенный тип по `conventions`; сохраняет чистоту функции), которое `extract_endpoints` пробрасывает. Следствие: существующие тестовые фикстуры `extract_endpoints` в `tests/spec/test_extract.py` (минимальные dict без ключа версии) дополняются top-level ключом `openapi` — логика экстракции не меняется; AC #4 переформулирован соответственно. Покрыто тест-кейсами в Verification Checklist выше (включая кейс `ValueError`).
