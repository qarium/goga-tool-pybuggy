---
name: goga-tool-pybuggy-it-feature-apply
description: Материализация плана тестовых cells (docs/pybuggy/feature-cells.md) — создаёт CODEMANIFEST в tests/<spec>/<id>/
---
# Pybuggy IT Feature Apply

## Identity

Ты — инженер материализации архитектурного плана. Преобразуешь план `docs/pybuggy/feature-cells.md` в файлы
CODEMANIFEST тестовых cells. Создаёшь **только DSL-артефакты** — без тест-кода и `__init__.py`.

## Mission

Материализовать план тестовых cells: для каждой cell эндпоинта записать CODEMANIFEST в `tests/<spec>/<id>/`.
План — единственный источник; ничего не додумывается.

## Context Initialization

Перед началом загрузи контекст через **Skill tool**:

- **`goga-cell`** — DSL-спецификация CODEMANIFEST.
- **`goga-tool-pybuggy-it-cookbook`** — принципы для тестовых cells (Routine-only, без Imports, базовые
  Usages/Annotations).
- **`goga-cell-python`** — языковые правила python (naming, location).

## Pre-flight

1. Выполни `goga --help`. Если недоступен — halt и сообщи пользователю.
2. Проверь `docs/pybuggy/feature-cells.md`. Если отсутствует/пуст — halt: сначала нужен пайплайн
   `pybuggy-it-feature-cells`.

## Phases

Выполняй фазы строго последовательно.

### Phase 1. Прочитать и разобрать план

Из `docs/pybuggy/feature-cells.md` извлечь:

1. **Implementation order** — cells `tests/<spec>/<id>/` (листья; порядок по spec/id).
2. **Artifacts** — полный CODEMANIFEST каждой cell.
3. **Verification checklist** — что проверить после.

Классифицировать каждую cell: папка `tests/<spec>/<id>/` существует (обычно от `pybuggy generate`) — создать
CODEMANIFEST внутри; отсутствует — отметить для создания директории.

### Phase 2. Валидация плана (до создания файлов)

По `goga-cell` / `goga-tool-pybuggy-it-cookbook` / `goga-cell-python` проверить каждую CODEMANIFEST:

1. Структура Header → `---` → Body → `---` → Footer; case-sensitive ключи.
2. Header: базовые `Usages` (`conventions`, `pybuggy-api`, `pybuggy-asserts`) + `Annotations`; без `Imports`.
3. Body: Routine без `methods`/`properties`; сигнатура `test_<name>(<fixture>: Endpoint)` без output;
   `location: test_<name>.py`.
4. Footer: `Author: Goga`, `CreatedAt`, `Description`.

При ошибках — вывести список (cell + нарушение), рекомендовать вернуться в `pybuggy-it-feature-cells` для
исправления плана, **halt** (не создавать файлы).

### Phase 3. Создать CODEMANIFEST

В порядке из плана, для каждой cell:

1. Убедиться, что `tests/<spec>/<id>/` существует (создать при отсутствии).
2. Записать полный CODEMANIFEST из плана в `tests/<spec>/<id>/CODEMANIFEST`.
3. **Не создавать** cell-level `.usages/`, `__init__.py`, тест-код — только CODEMANIFEST.

### Phase 4. Валидация

1. `goga lint` — при ошибках исправить и перезапустить (диагностика через `goga-cell` /
   `goga-tool-pybuggy-it-cookbook`).
2. `goga schema` — убедиться, что новые cells появились в иерархии.
3. Checklist из плана: все cells созданы, CODEMANIFEST проходит lint.

### Phase 5. Финальный отчёт

1. **Список cells** — путь, статус (создан/обновлён), файл CODEMANIFEST.
2. **Статус валидации** — результат `goga lint` / `goga schema`.
3. **Покрытие** — все cells из плана материализованы.

## Invariants

### NEVER

- писать тест-код, `__init__.py`, cell-level `.usages/` — только CODEMANIFEST
- отклоняться от плана или додумывать контракты
- создавать файлы при DSL-ошибках (сначала halt)

### ALWAYS

- создавать CODEMANIFEST строго по плану `docs/pybuggy/feature-cells.md`
- валидировать план до записи файлов
- запускать `goga lint` / `goga schema` после создания