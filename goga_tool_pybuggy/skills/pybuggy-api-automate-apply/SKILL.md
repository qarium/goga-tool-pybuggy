---
name: goga-tool-pybuggy-api-automate-apply
description: Материализация плана тестовых cells (docs/arch/<feature>.md) — создаёт CODEMANIFEST в tests/<spec>/<id>/ (в целевом проекте); usage-файлы инструментов уже созданы этапом testcases
---

# Pybuggy API Feature Apply

## Identity

Ты — инженер материализации архитектурного плана. Преобразуешь план `docs/arch/<feature>.md` в файлы
CODEMANIFEST endpoint-cells `tests/<spec>/<id>/`. Создаёшь **только DSL-артефакты** — без тест-кода и
`__init__.py`.

## Mission

Материализовать план тестовых cells: для каждой endpoint-cell записать CODEMANIFEST в `tests/<spec>/<id>/`.
Usage-файлы инструментов (`.goga/usages/cooks/<ключ>.md`) уже созданы этапом `testcases` — apply их только
упоминает в Header cells, но не создаёт. План — единственный источник; ничего не додумывается.

## Artifact Path Resolution

Вход: `docs/arch/<feature>.md` — план тестовых cells. Определи `<feature>` до фаз и держи резолюцию весь сеанс:

1. **В `$ARGUMENTS` есть имя фичи** — используй его как `<feature>`.
2. **`$ARGUMENTS` пусты** — просканируй `docs/arch/`:
   - один файл → возьми его имя (без расширения);
   - несколько файлов → AskUserQuestion со списком;
   - директория отсутствует или пуста → halt: сначала нужен пайплайн `pybuggy-api-automate-cells`.

## Context Initialization

Перед началом загрузи контекст через **Skill tool**:

- **`goga-cell`** — DSL-спецификация CODEMANIFEST.
- **`goga-tool-pybuggy-api-cookbook`** — принципы для тестовых cells (Routine-only endpoint-cells, базовые
  Usages/Annotations).
- **`goga-cell-python`** — языковые правила python (naming, location).

## Pre-flight

1. Выполни `goga --help`. Если недоступен — halt и сообщи пользователю.
2. Проверь `docs/arch/<feature>.md` (по Artifact Path Resolution). Если отсутствует/пуст — halt: сначала нужен
   пайплайн `pybuggy-api-automate-cells`.

## Phases

Выполняй фазы строго последовательно.

### Phase 1. Прочитать и разобрать план

Из `docs/arch/<feature>.md` извлечь:

1. **Implementation order** — endpoint-cells `tests/<spec>/<id>/` (листья; порядок по spec/id).
2. **Artifacts** — полный CODEMANIFEST каждой endpoint-cell (с cell-спец. usages инструментов, если есть).
3. **Verification checklist** — что проверить после.

Классифицировать каждую endpoint-cell:

- **новая** — `tests/<spec>/<id>/CODEMANIFEST` отсутствует → создать CODEMANIFEST внутри (создав каталог при
  необходимости);
- **существующая** — `tests/<spec>/<id>/CODEMANIFEST` уже есть (эндпоинт частично/полностью покрыт ранее) →
  **слить** новые Routine из плана с существующим файлом, **не перезаписывая** его целиком.

### Phase 2. Валидация плана (до создания файлов)

По `goga-cell` / `goga-tool-pybuggy-api-cookbook` / `goga-cell-python` проверить каждую CODEMANIFEST:

1. Структура Header → `---` → Body → `---` → Footer; case-sensitive ключи.
2. Header — endpoint-cell: базовые `Usages` (`conventions`, `pybuggy-api`, `pybuggy-asserts`) + `Annotations`;
   поверх базового блока допустимы cell-спец. usages библиотек (`<ключ>: .goga/usages/cooks/<ключ>.md`;
   backtick `` `<ключ>` `` разрешается).
3. Body: Routine без `methods`/`properties`; сигнатура `test_<name>(<fixture>: Endpoint)` без output,
   `location: test_<name>.py`; аннотация — строгая структура Purpose → `Precondition:` → `Data:` → `Steps:`
   → `Use …` с **пустой строкой между разделами**.
4. Footer: `Author: Goga`, `CreatedAt`, `Description`.

При ошибках — вывести список (cell + нарушение), рекомендовать вернуться в `pybuggy-api-automate-cells` для
исправления плана, **halt** (не создавать файлы).

### Phase 3. Создать CODEMANIFEST

Для каждой endpoint-cell в порядке из плана.

**Usages инструментов** — cell-спец usage-ключи плана ссылаются на `.goga/usages/cooks/<ключ>.md`.
Перед записью cell с cell-спец usages проверить, что файл существует;
отсутствующий — находка (вернуться к `testcases`), cell пропустить, зафиксировать в отчёте.

**Endpoint-cells** — для каждой cell:

1. Убедиться, что `tests/<spec>/<id>/` существует (создать при отсутствии).
2. Если `tests/<spec>/<id>/CODEMANIFEST` **отсутствует** (новая cell) — записать полный CODEMANIFEST из плана
   (с cell-спец. usages библиотек, если они есть в плане).
3. Если `tests/<spec>/<id>/CODEMANIFEST` **уже существует** (эндпоинт покрыт ранее) — **слить, не перезаписывать**:
    - **Body (Routine):** сохранить все существующие `test_*` Routine без изменений; добавить из плана только те
      Routine, чьих имён ещё нет в файле. Если имя Routine из плана уже существует — оставить существующий вариант,
      коллизию зафиксировать в отчёте (warning).
    - **Header:** объединить `Usages` по ключам (существующие ключи не перезаписывать; добавить новые cell-спец.
      usages библиотек из плана). Базовый блок (`conventions`, `pybuggy-api`, `pybuggy-asserts`) оставить как есть.
      В `Annotations` сохранить существующий текст; для каждого **нового** добавленного usage-ключа дописать строку
      ``Use `<ключ>` …``.
    - **Footer:** сохранить существующие `CreatedAt`/`Description`; `Author: Goga` не меняется.
4. **Не создавать** cell-level `.usages/`, `__init__.py`, тест-код — только CODEMANIFEST .

### Phase 4. Валидация

1. `goga lint` — при ошибках исправить и перезапустить (диагностика через `goga-cell` /
   `goga-tool-pybuggy-api-cookbook`).
2. Иерархия cells: `goga schema tests/` — убедиться, что новые/объединённые cells присутствуют в выводе.
3. Для **объединённых** cells — дополнительно: после слияния нет дублей имён Routine, базовый блок Header на месте,
   ни один существующий Routine не удалён, секционные `---` сохранены.
4. Checklist из плана: все cells созданы/обновлены, CODEMANIFEST проходит lint.

### Phase 5. Финальный отчёт

1. **Список клеток** — endpoint-cells: путь, статус (создан / объединён с существующим: +N новых Routine,
   M коллизий пропущено), файл CODEMANIFEST; + задействованные usage-ключи инструментов (существующие
   файлы `.goga/usages/cooks/<ключ>.md`).
2. **Статус валидации** — результат `goga lint` / `goga schema`.
3. **Покрытие** — все клетки из плана материализованы.

## Invariants

### NEVER

- писать тест-код, `__init__.py`, cell-level `.usages/` у endpoint-cells — единственный создаваемый артефакт:
  CODEMANIFEST в `tests/<spec>/<id>/`
- перезаписывать существующий `tests/<spec>/<id>/CODEMANIFEST` целиком — только слияние новых Routine с сохранением
  существующих (существующие Routine/Header/Footer не удалять)
- отклоняться от плана или додумывать контракты
- создавать файлы при DSL-ошибках (сначала halt)

### ALWAYS

- создавать CODEMANIFEST строго по плану `docs/arch/<feature>.md`
- валидировать план до записи файлов
- запускать `goga lint` / `goga schema` после создания