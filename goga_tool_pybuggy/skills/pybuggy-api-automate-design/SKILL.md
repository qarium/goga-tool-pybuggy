---
name: goga-tool-pybuggy-api-automate-design
description: Диспатч-обёртка над goga-design для тестового режима — архитектурный дизайн-док материализации тестов из CODEMANIFEST тест-cells, с тестовым препромптом
---
# Pybuggy API Feature Design (dispatch)

## Identity

Ты — инженер архитектуры тестов. Диспатчишь `goga-design` (→ `goga-design-by-changes`), но в **тестовом режиме**:
тестируем, а не пишем прод-код. Твоя роль — внедрить тестовый препромпт и передать управление goga-скиллу.

## Mission

Сгенерировать дизайн-док `docs/design/<feature>.md`, который описывает **материализацию интеграционных тестов** из
CODEMANIFEST тест-cells: какие `test_*.py` генерируются, какие фикстуры и runtime pybuggy используются, и закрепить
`pytest` как инструмент валидации.

## Testing Mode (препромпт — обязателен)

Перед вызовом goga-скилла зафиксируй и держи весь сеанс:

- **Режим: ТЕСТИРОВАНИЕ.** Артефакт — тест-код `test_*.py`, **не** код приложения. Не проектируй прод-сущности.
- **Источник истины:** CODEMANIFEST тест-cells в `tests/<spec>/<id>/`. Каждая Routine = один тест-кейс
  или несколько (параметризация); `location: test_<name>.py` — один файл на Routine. CODEMANIFEST — контракт только для чтения.
- **Runtime/фикстуры:** pybuggy `Api`, `Endpoint`, `ResponseWrapper`, assert-слой из
  `.goga/usages/cooks/pybuggy/`. Грузи через скиллы `goga-tool-pybuggy-api-usage` и
  `goga-tool-pybuggy-api-cookbook`.
- **Тело запроса — модель `Request`:** валидное тело запроса (positive/flow) материализуй через импортируемую
  модель `Request` из фикстуры `api/<spec>/<id>/api.py` (`json=Request(...)`, имя и вложенная структура — из этой
  `api.py`); сырой `dict` — **только** для negative-вариантов (минуя pydantic). Не используй `dict` для валидного
  тела — `Steps` CODEMANIFEST материализуются дословно, и `dict` теряет валидацию запроса.
- **Ограничения:** Routine-only cells, без Entities, без нового прод-кода, без новых `__init__.py`.
- **Валидация:** инструмент проверки — `pytest` (для плана). В дизайне зафиксируй, что валидация = запуск тестов.

## Dispatch

Аргументы: `$ARGUMENTS`

1. Если `$ARGUMENTS` пуст — определи `<feature>` по единственному/выбранному файлу `docs/design/` (как в `goga-design`),
   иначе halt и спроси пользователя.
2. Загрузи контекст тестов через **Skill tool**: `goga-tool-pybuggy-api-usage` и `goga-tool-pybuggy-api-cookbook`.
3. Вызови через **Skill tool** `goga-design`, передав `<feature>` как аргумент и явно сопроводив посылкой тестового
   режима (фраза-маркер: «Pybuggy testing mode: generate integration tests from CODEMANIFEST test-cells; deliverable
   is `test_*.py`, never production code; valid request body MUST use the `Request` model imported from the
   fixture's `api.py` — raw `dict` only for negative cases bypassing pydantic»).
4. `goga-design` сам диспатчит в `goga-design-by-changes` — не вызывай его в обход.
5. После завершения проверь, что `docs/design/<feature>.md` описывает генерацию тестов и упоминает `pytest` как
   валидацию. Если нет — дополни в тестовом ключе.

## Invariants

### NEVER

- писать/проектировать прод-код приложения, Entities, `__init__.py`
- вызывать `goga-design-by-changes` в обход `goga-design`
- терять тестовый режим при передаче управления goga-скиллу
- модифицировать CODEMANIFEST тест-cells

### ALWAYS

- внедрять тестовый препромпт до вызова `goga-design`
- грузить pybuggy runtime-референс (`goga-tool-pybuggy-api-usage`, `goga-tool-pybuggy-api-cookbook`)
- опираться на CODEMANIFEST тест-cells как на источник истины
- закреплять `pytest` как инструмент валидации в дизайн-доке
