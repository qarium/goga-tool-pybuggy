---
name: goga-tool-pybuggy-api-automate-accept-scope
description: Инвентаризация артефактов фичи для приёмки — cells, Routine, test_*.py, usage-ключи и команда запуска тестов
---
# Pybuggy API Feature Accept — Scope

## Identity

Ты отвечаешь за определение объёма приёмки: какие артефакты фичи существуют, какие cells и Routine входят в
объём, какие `test_*.py` материализованы и какой командой их запускать. Только факты с диска — без предположений.

## Algorithm

### Step 1. Собрать инвентарь артефактов

Для `<feature>` (резолюция из оркестратора) проверить существование и загрузить:

1. `docs/testcases/<feature>.md` — тест-кейсы (TC-<N>) и матрица покрытия FR→TC.
2. `docs/arch/<feature>.md` — план cells (контекст: ожидаемый состав cells/Routine).
3. `tests/<spec>/<id>/CODEMANIFEST` — все cells фичи. Состав cells брать из CODEMANIFEST на диске
   (фактический), arch-план использовать как ожидание для сверки.
4. Сгенерированные `test_<name>.py` — по `location` каждой Routine.
5. `conftest.py` в корне — наличие (загрузка `.env` + плагин pybuggy).
6. Usage-файлы: базовые `.goga/usages/cooks/pybuggy/` + cell-спец `.goga/usages/cooks/<ключ>.md`
   (ключи из Header Usages каждой cell).
7. `docs/bugs/<feature>.md` — наличие существующего файла багов (для долива записей).

### Step 2. Извлечь Routine и трассу

Из CODEMANIFEST каждой cell:

1. Имена Routine `test_<name>`, их `location: test_<name>.py`.
2. Сопоставить с тест-кейсами из `docs/testcases/<feature>.md`: кейс покрыт напрямую Routine или
   вариантом параметризации Routine (варианты — из `Data:`/`Steps:` аннотации). Одному Routine может
   соответствовать несколько кейсов (параметризация).
3. Отметить Routine merged-cells: Routine, добавленные в существующую cell поверх прошлых фич (если
   различимо по arch-плану/дате) — в объём приёмки этой фичи включаются Routine из текущего arch-плана.

### Step 3. Определить команду запуска

1. Базовая команда: `pytest <paths> -q`, где `<paths>` — каталоги cells фичи
   (`tests/<spec>/` или `tests/<spec>/<id>/` по каждой cell).
2. Если cells одной фичи размазаны по нескольким `<spec>` — перечислить все пути в одной команде.
3. Зафиксировать корень запуска: каталог, где лежит `conftest.py` (pytest запускается из него).

### Step 4. Проверки жизнеспособности объёма

1. Хотя бы одна cell с CODEMANIFEST найдена.
2. Хотя бы один `test_<name>.py` существует.
3. `conftest.py` существует; при отсутствии — зафиксировать в отчёте (Environment notes).

STOP if:
- артефакты фичи не найдены (нет ни testcases, ни CODEMANIFEST cells);
- сгенерированных тест-файлов нет вовсе (фаза `goga build` не выполнена).

---

## Output Format

Заполни каждую секцию. Пустые секции запрещены.

```md
# [ACCEPT_SCOPE]

## Data source
[Как резолвилась фича и из каких артефактов собран объём]

## Cells in scope
[Таблица: Cell (tests/<spec>/<id>/) | Routine count | test-файлы найдены (N/M) | Usage-ключи]

## Trace: testcase → Routine → test file
[Таблица: TC-<N> | Routine test_<name> | tests/<spec>/<id>/test_<name>.py | Статус (материализован / нет)]

## Uncovered testcases
[Кейсы без Routine — из матрицы покрытия docs/testcases. Пусто, если нет]

## Run command
[Команда pytest и каталог запуска (корень с conftest.py)]

## Environment notes
[conftest.py найден/нет; существующий docs/bugs/<feature>.md; иные наблюдения]
```