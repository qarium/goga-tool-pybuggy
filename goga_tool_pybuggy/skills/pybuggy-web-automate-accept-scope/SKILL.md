---
name: goga-tool-pybuggy-web-automate-accept-scope
description: Web topic artifact inventory for acceptance — cells, Routines, test_*.py files, step-cache directories, usage keys, and the strict-mode test run command
---

# Pybuggy Web Topic Accept — Scope

## Identity

Ты определяешь объём приёмки топика: перечисляешь существующие на диске артефакты, ячейки и Routine,
обнаруживаешь материализованные `test_*.py` и кеши шагов, определяешь команду прогона. Используешь
только факты с диска — никаких предположений.

## Algorithm

### Step 1. Collect the artifact inventory

Для текущего топика проверь существование и загрузи:

1. Путь, напечатанный `goga history path -f testcases.md` — кейсы (TC-<N>) и матрица REQ→TC.
2. Путь, напечатанный `goga history path -f arch.md` — план ячеек (контекст: ожидаемый состав
   ячеек/Routine для кросс-чека).
3. `tests/web/<cell>/CODEMANIFEST` — все ячейки топика. Источник истины о составе — CODEMANIFEST
   на диске (фактическое состояние); план arch.md — ожидание для кросс-чека.
4. Сгенерированные `test_<name>.py` — по `location` каждой Routine.
5. **Кеши шагов**: `tests/web/<cell>/test_<name>/` на каждый тест (создаются первым, генерирующим
   прогоном на `goga build`); зафиксируй наличие/отсутствие и наполненность каждого.
6. `conftest.py` в корне — проверь наличие (загрузка `.env` + pybuggy-плагин с веб-фикстурой).
7. Документ `.goga/tools/pybuggy/web.yml` — факт активации веб-рантайма.
8. Usage-файлы: базовый `.goga/usages/cooks/pybuggy/pybuggy-web.md` + cell-specific
   `.goga/usages/cooks/<key>.md` (ключи из Header каждой ячейки).
9. Путь, напечатанный `goga history path -f bugs.md` — проверь существующий файл багов (цель
   дописывания рекордов).

### Step 2. Extract Routines and build the trace

Из CODEMANIFEST каждой ячейки:

1. Имена Routine `test_<name>` и их `location: test_<name>.py`.
2. Соотнеси с кейсами из `goga history path -f testcases.md`: кейс покрыт напрямую Routine или
   вариантом параметризованной Routine (варианты — из аннотаций `Data:`/`Steps:`). Одна Routine
   может покрывать несколько кейсов.
3. Пометь Routine слитых ячеек: добавленные в существующую ячейку поверх прошлых топиков — в объём
   приёмки этого топика входят только Routine из текущего плана arch.md.
4. К каждой Routine — статус кеша шагов: каталог существует и не пуст / отсутствует.

### Step 3. Determine the run command

1. Базовая команда: `pytest <paths> -q --strict-mode`, где `<paths>` — каталоги ячеек топика
   (`tests/web/` целиком или `tests/web/<cell>/` по ячейке). Строгий режим оправдан: первый
   (генерирующий) прогон уже сделан на `goga build`, кеш на месте — strict даёт 0 LLM-вызовов и
   проверяет полноту кеша.
2. Если у какого-то теста кеш отсутствует — зафиксируй: прогон строгий, но cache-miss по этому
   тесту ожидаем (догенерация — по решению триажа в accept-run).
3. Зафиксируй корень прогона: каталог с `conftest.py` (pytest запускается оттуда).
4. Запиши окружение: браузер/endpoint из требований §1 (факты веб-рантайма), доступность сайта —
   не проверяй здесь (это делает run).

### Step 4. Acceptance scope viability checks

1. Найдена хотя бы одна ячейка с CODEMANIFEST.
2. Существует хотя бы один `test_<name>.py`.
3. `conftest.py` существует; отсутствует — зафиксируй в отчёте (Environment notes).
4. `.goga/tools/pybuggy/web.yml` существует; отсутствует — зафиксируй (веб-фикстура не
   зарегистрируется).

STOP if:

- артефакты топика не найдены (нет ни testcases, ни CODEMANIFEST-ячеек);
- сгенерированных тест-файлов нет вообще (фаза `goga build` не исполнялась).

---

## Output Format

Fill in every section. Empty sections are prohibited.

```md
# [ACCEPT_SCOPE]

## Data source

[Текущий топик и артефакты, из которых собран объём]

## Cells in scope

[Таблица: Ячейка (tests/web/<cell>/) | Routine | тест-файлы найдены (N/M) | кеш шагов (N/M) | Usage-ключи]

## Trace: testcase → Routine → test file

[Таблица: TC-<N> | Routine test_<name> | tests/web/<cell>/test_<name>.py | кеш test_<name>/ | Статус (materialized / not)]

## Uncovered testcases

[Кейсы без Routine — из матрицы testcases.md. Напиши `none`, если ничего]

## Run command

[Команда pytest (строгий режим: pytest tests/web/ -q --strict-mode) и каталог прогона (корень с conftest.py)]

## Environment notes

[conftest.py найден/отсутствует; web.yml найден/отсутствует; браузер/endpoint из требований §1;
существующий `goga history path -f bugs.md`; тесты без кеша шагов; прочие наблюдения]
```
