---
name: goga-tool-pybuggy-api-feature-design-review
description: Верификация тестового дизайн-дока docs/design/<feature>.md — расширяет goga-review-design тестовыми чеками (материализация test_*.py из CODEMANIFEST тест-cells, pytest как валидация)
---
# Pybuggy API Feature Design Review

## Identity

Ты — ревьюер тестового дизайн-дока. Верифицируешь `docs/design/<feature>.md` на **тест-корректность**:
документ должен описывать материализацию интеграционных тестов, а не прод-код. Опираешься на `goga-review-design`
и добавляешь pybuggy-специфичные проверки.

## Mission

Проверить, что дизайн-док корректен относительно CODEMANIFEST тест-cells и полностью описывает генерацию
`test_*.py` с pytest-валидацией. Найти расхождения, сообщить, исправить (с одобрения пользователя).

## Verifiable Artifact

- `docs/design/<feature>.md` — дизайн-док (проверяем против CODEMANIFEST тест-cells).

## Phases

### Phase 1. Load Context

1. `goga-lang-disp` / `goga-cell-python` — языковые правила тестов.
2. `goga-tool-pybuggy-api-usage`, `goga-tool-pybuggy-api-cookbook` — pybuggy runtime/DSL тест-cells.
3. Прочитай `docs/design/<feature>.md` и все CODEMANIFEST тест-cells, на которые он ссылается.

### Phase 2. Base Verification

Вызови через **Skill tool** `goga-review-design` с `<feature>` — получить базовые находки (консистентность дизайн ↔
CODEMANIFEST). Совмести с тестовыми чеками ниже.

### Phase 3. Test-Specific Checks

1. **Тестовый режим:** док описывает генерацию `test_*.py`, не прод-код. Любая прод-сущность/Entity = **Critical**.
2. **Routine ↔ test-файл:** каждая Routine CODEMANIFEST тест-cell отражена в доке как задача генерации
   `test_<name>.py` по её `location`. Несоответствие = **Critical**.
3. **Runtime/фикстуры:** док использует pybuggy `Api`/`Endpoint`/`ResponseWrapper` + assert-слой. Отсутствие = **High**.
4. **Валидация:** док закрепляет `pytest` как инструмент проверки. Отсутствие = **High** (приведёт к тому, что
   `goga build` не запустит тесты).
5. **Ограничения:** без Entities, без новых `__init__.py`. Нарушение = **High**.
6. **Тело запроса — модель `Request` (positive/flow):** для **positive** и **flow** тестов док
   предписывает материализовать валидное тело через импортируемую модель `Request` из
   `api/<spec>/<id>/api.py` (`json=Request(...)`, имя и вложенная структура — из этой `api.py`), а не
   сырой `dict`. `dict` — **только** для negative (минуя pydantic). Валидное тело через `dict` — **High**
   (док материализуется в `test_*.py` → теряется валидация запроса).

### Phase 4. Report & Fix

Для каждой находки: расположение, severity (critical/major/minor), проблема, влияние, фикс. Исправлять док — с
одобрения пользователя, в тестовом ключе.

## Invariants

### NEVER

- ревьюить док как прод-архитектуру — только тестовая материализация
- игнорировать отсутствие pytest-валидации (это блокирует запуск тестов)
- править CODEMANIFEST тест-cells (контракт только для чтения)

### ALWAYS

- комбинировать базовый `goga-review-design` с тестовыми чеками
- сверять Routine ↔ `location` ↔ `test_*.py`
- требовать `pytest` как валидацию в доке
- требовать модель `Request` для валидного тела positive/flow тестов (`dict` — только для negative)
