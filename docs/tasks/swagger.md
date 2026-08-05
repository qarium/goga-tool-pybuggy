# Поддержка спецификаций Swagger 2.0 в экстракции эндпоинтов

## Current State

Ячейка `goga_tool_pybuggy/spec` разбирает спецификации и извлекает из них эндпоинты.

- **Разбор (`load_spec` → `swax.openapi.parse_spec`, под капотом Prance)** уже прозрачно поддерживает и Swagger 2.0, и OpenAPI 3.x: `$ref` разрешаются для обоих форматов, парсинг менять не нужно (см. `.goga/usages/cooks/swax-openapi.md`).
- **Конфиг (`config/spec_entry.py`, `SpecEntry.type`)** уже допускает значения `swagger` и `openapi` (`Literal["swagger", "openapi"]`) — формат декларативен и не влияет на разбор.
- **Слой экстракции (`extract_endpoints` в `extract.py`)** написан строго под структуру OpenAPI 3.0: request читается из `requestBody.content.application/json.schema`, response — из `responses[code].content.application/json.schema`, query-параметры — из вложенного `parameters[].schema`, nullable-нормализация обрабатывает только OpenAPI-ключевое слово `nullable`.

В результате на спецификации в формате Swagger 2.0 экстракция возвращает пустые или некорректные `request`/`response`/`query_params`, потому что у Swagger другая структура: request body задаётся параметром с `in: body` и корневым `schema`, response — как `responses[code].schema` напрямую без обёртки `content`, поля типа (`type`/`format`/`items`) инлайнятся в сам параметр (нет вложенного `schema`), nullable обозначается через `x-nullable`, а media-типы описываются на уровне операции/корня через `consumes`/`produces`.

## Description

Расширить экстракцию эндпоинтов так, чтобы из спецификаций и Swagger 2.0, и OpenAPI 3.x извлекалась одна и та же нормализованная модель `Endpoint` (method, path, request, response, query_params, description). Формат определяется по версии спецификации (`swagger: "2.0"` против `openapi: "3.x"`), после чего поля извлекаются по структуре соответствующего формата. Реализация — чистая логика над уже разобранным dict, без новых внешних зависимостей и без изменений парсинга.

## Scope

**In scope:**
- Определение версии спецификации (Swagger 2.0 vs OpenAPI 3.x) внутри экстракции.
- Извлечение request, response и query-параметров для Swagger 2.0 по его структуре (`in: body`, `responses[code].schema`, инлайн-поля параметра) в дополнение к существующей логике OpenAPI 3.x.
- Расширение nullable-нормализации: ключевое слово Swagger `x-nullable` обрабатывается наравне с OpenAPI `nullable` и приводится к той же JSON-Schema union-форме.
- Обновление контрактов `CODEMANIFEST` ячейки `spec` под оба формата (включая контракт определения версии, если требуется).
- Обновление usage-файлов: `.goga/usages/cooks/swax-openapi.md` (шаблоны экстракции Swagger 2.0) и `goga_tool_pybuggy/spec/.usages/spec.md` (Swagger-семантика на выходе).
- Покрытие Swagger 2.0 тест-кейсами в `tests/spec/test_extract.py` (inline-спеки как dict, без моков).

**Out of scope:**
- Изменения парсинга (`parse_spec` уже поддерживает оба формата).
- Новые CLI-команды.
- Изменение downstream-потребителей (`info`, `list`, `generate`) — форма `Endpoint` не меняется.
- Склейка `basePath`/`servers` в `path` (значение `path` остаётся ключом path-item, как сейчас для OpenAPI).
- Поддержка параметров `in: formData` и file-upload (вне текущей модели `query_params`).
- Учёт media-типов `consumes`/`produces` — приоритет остаётся за `application/json`, как в текущей реализации.

## Acceptance Criteria

- На спецификации Swagger 2.0 `extract_endpoints` возвращает список `Endpoint` с корректно заполненными `request` (из параметра `in: body`), `response` (из `responses[code].schema`) и `query_params` (из инлайн-полей параметров `in: query`).
- `extract_endpoints` извлекает эквивалентное содержимое для Swagger 2.0 и OpenAPI 3.x при одинаковой семантике операций (одинаковые method, path, формы схем request/response/query_params).
- Ключевое слово `x-nullable` (Swagger) приводится к той же JSON-Schema union-форме (`type` со списком, включающим `"null"`, либо anyOf-фолбэк), что и OpenAPI `nullable`; ключ `x-nullable` удаляется из нормализованных схем.
- Поведение для OpenAPI 3.x не изменяется — все существующие тесты `tests/spec/test_extract.py` проходят без правок.
- Версия спецификации определяется корректно (`swagger: "2.0"` → Swagger-путь извлечения; `openapi: "3.x"` → существующий OpenAPI-путь).
- Тест-кейсы Swagger 2.0 добавлены в `tests/spec/test_extract.py` и проходят.
- Контракты `CODEMANIFEST` ячейки `spec` и usage-файлы (`swax-openapi.md`, `spec.md`) обновлены и согласованы с реализацией.
- `goga lint` для ячейки `spec` проходит без ошибок.
- Команды `info`, `list`, `generate` корректно работают со спецификацией Swagger 2.0 без изменений в их коде (проверяется через форму `Endpoint`).

## Stack

- **Frameworks:** —
- **Libraries:** `swax.openapi` (Prance, парсинг — существует), `pydantic` (модель `Endpoint` — существует), `click` (маппинг ошибок — существует), `pytest` (тестирование — существует), `jsonschema` (runtime-валидатор схем, мотивирует nullable-нормализацию — существует)
- **Infrastructure:** —
- **Язык:** Python 3.13

## External Dependencies

| Компонент | Usage file | Статус |
|-----------|-----------|--------|
| swax.openapi | `.goga/usages/cooks/swax-openapi.md` | обновляется (добавляются шаблоны экстракции Swagger 2.0) |
| pydantic | (через `.goga/usages/conventions.md`) | существующий, без изменений |
| click | `.goga/usages/cooks/click.md` | существующий, без изменений |
| jsonschema | `.goga/usages/cooks/jsonschema.md` | существующий, без изменений |
| pytest | (через `.goga/usages/conventions.md`) | существующий, без изменений |

Новые внешние зависимости: нет.

## Risks and Constraints

- **Несимметричность форматов:** структуры Swagger 2.0 и OpenAPI 3.x различаются сильнее, чем «немного» (request body, response body, расположение схем параметров, nullable). Экстракция должна приводить оба формата к идентичной нормализованной форме — иначе downstream-валидаторы (`jsonschema`) и генераторы получат расходящиеся схемы.
- **nullable-нормализация:** `x-nullable` встречается реже и формально менее стандартизован, чем OpenAPI `nullable`; нужно единое поведение рекурсивной нормализации (свойства, items, additionalProperties, anyOf/oneOf/allOf) для обоих ключевых слов.
- **Отсутствие файловых фикстур:** тесты строят спеки inline как dict (нет `.yaml`/`.json` фикстур). Тест-кейсы Swagger 2.0 должны следовать тому же паттерну.
- **Декларативность `SpecEntry.type`:** поле `type` в конфиге не управляет разбором/экстракцией; определение версии должно опираться на содержимое спецификации, а не на это поле.
- **Сохранение поведения OpenAPI:** изменения не должны сломать существующие тесты и поведение для OpenAPI 3.x.

## Scope Estimate

Единая задача (без декомпозиции). Работа когезивна и локализована в одной ячейке `spec`: определение версии + экстракция для двух форматов + расширение nullable-нормализации + тесты + обновление контрактов и usage-файлов. Декомпозиция не даёт подзадач с самостоятельной ценностью.

## Existing Architecture

- **Затронутая ячейка:** `goga_tool_pybuggy/spec` (контракты `extract_endpoints` и `_normalize_nullable`; при необходимости новый контракт определения версии). `Endpoint` и `build_endpoint_id` не меняются.
- **Связи между ячейками (consumers):** `extract_endpoints` и `load_spec` используются командами `commands/info`, `commands/list`, `commands/generate`; рендеринг идёт через ячейку `goga_tool_pybuggy/output` (`render_info`/`render_list`, тип `Endpoint`). Поскольку форма `Endpoint` сохраняется, эти потребители изолированы от изменений и продолжают работать со спецификациями Swagger 2.0 без правок.
- **Парсинг:** `load_spec` → `swax.openapi.parse_spec` (Prance) — уже поддерживает оба формата, остаётся как есть.
- **Конфигурация:** `config/spec_entry.py` (`SpecEntry.type`) уже допускает `swagger`; изменений не требует.

## Notes

- Решение по стеку (подтверждено пользователем): Вариант A — чистая логика над разобранным dict, без новых зависимостей и без библиотеки-конвертера Swagger → OpenAPI.
- Решение по media-типам (подтверждено пользователем): приоритет остаётся за `application/json`; `consumes`/`produces` не учитываются.
- Решение по путям (подтверждено пользователем): `basePath`/`servers` не склеиваются в `path`; значение `path` — ключ path-item как есть.
- Решение по скоупу (подтверждено пользователем): единая задача без декомпозиции.
- Обновление существующих usage-файлов (`swax-openapi.md`, `spec.md`) и контрактов `CODEMANIFEST` входит в скоуп задачи как часть работы, а не как создание новых cook-файлов (новых внешних зависимостей нет).
