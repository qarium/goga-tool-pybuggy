---
name: goga-tool-pybuggy-web-automate-accept-scope
description: Web topic artifact inventory for acceptance — cells, Routines, test_*.py files, step-cache directories, usage keys, and the strict-mode test run command
---

# Pybuggy Web Topic Accept — Scope

## Identity

Ты определяешь объём приёмки топика. Используешь только факты с диска — никаких предположений:

- перечисляешь существующие на диске артефакты, ячейки и Routine;
- обнаруживаешь материализованные `test_*.py` и кеши шагов;
- определяешь команду прогона.

## Algorithm

### Step 1. Collect the artifact inventory

Для текущего топика проверь существование и загрузи:

1. Путь, напечатанный `goga history path -f requirements.md` — §1 Browser endpoint / Base URL /
   Target environment и §2 страницы с адресами (для сверки адресации).
2. `tests/web/<cell>/CODEMANIFEST` — все ячейки топика. Источник истины о составе — CODEMANIFEST
   на диске (фактическое состояние).
3. Сгенерированные `test_<name>.py` — по `location` каждой Routine.
4. **Кеши шагов** (создаются первым, генерирующим прогоном на `goga build`) — зафиксируй
   наличие/отсутствие и наполненность каждого:
   - кеш теста: `tests/web/<cell>/.cache/test_<name>/test_<name>/` на каждый тест
     (параметризованный кейс — `…/test_<name>[<param_id>]`);
   - общий кеш каждой используемой страницы: `pages/.cache/<page>/`.
5. **Page-объекты**: модули `pages/**` страниц топика (§2 — привязки `page_<name>` / литеральная
   навигация) — наличие модулей и заявленных методов (контракт — usage-файлы
   `.goga/usages/cooks/page-<name>.md`).
6. `conftest.py` в корне — проверь наличие (загрузка `.env` + pybuggy-плагин с веб-фикстурой).
7. Документ `.goga/tools/pybuggy/web.yml` — факт активации веб-рантайма.
8. Usage-файлы: базовый `.goga/usages/cooks/pybuggy/pybuggy-web.md` + cell-specific
   `.goga/usages/cooks/<key>.md` (ключи из Header каждой ячейки).
9. Путь, напечатанный `goga history path -f bugs.md` — проверь существующий файл багов (цель
   дописывания рекордов).

### Step 2. Extract Routines and build the trace

Из CODEMANIFEST каждой ячейки:

1. Имена Routine `test_<name>` и их `location: test_<name>.py`.
2. Построй трассу Routine → `test_<name>.py`: каждая Routine из CODEMANIFEST обязана иметь
   материализованный тест-файл.
3. К каждой Routine — статус кеша шагов: каталог существует и не пуст / отсутствует; для страниц,
   чьи фикстуры/методы использует рутина, — статус общего кеша `pages/.cache/<page>/`.

### Step 3. Determine the run command

1. Базовая команда: `pytest <paths> -q --strict-mode`, где `<paths>` — каталоги ячеек топика
   (`tests/web/` целиком или `tests/web/<cell>/` по ячейке). Строгий режим оправдан: первый
   (генерирующий) прогон уже сделан на `goga build`, кеш на месте — strict даёт 0 LLM-вызовов и
   проверяет полноту кеша.
2. Добавь суффикс из Browser endpoint требований §1: адрес от пользователя →
   `--browser-endpoint <адрес>`; «из конфига» — без флага. Прогоны и исследование используют
   один браузер.
3. Добавь аргументы рендера base_url из §1 требований, если заданы: env — префикс
   `ENV_NAME=… pytest …`; CLI — суффикс `--имя=значение` — прогон обязан рендерить
   `site.base_url` в адрес того же окружения топика.
4. Если у какого-то теста кеш отсутствует — зафиксируй: прогон строгий, но cache-miss по этому
   тесту ожидаем (догенерация — по решению триажа в accept-run).
5. Зафиксируй корень прогона: каталог с `conftest.py` (pytest запускается оттуда).
6. Запиши окружение: браузер/endpoint из требований §1 (Browser endpoint + факты веб-рантайма),
   доступность сайта — не проверяй здесь (это делает run).

### Step 4. Acceptance scope viability checks

1. Найдена хотя бы одна ячейка с CODEMANIFEST.
2. Существует хотя бы один `test_<name>.py`.
3. `conftest.py` существует; отсутствует — зафиксируй в отчёте (Environment notes).
4. `.goga/tools/pybuggy/web.yml` существует; отсутствует — зафиксируй (веб-фикстура не
   зарегистрируется).
5. STOP if: артефакты топика не найдены (нет ни requirements.md, ни CODEMANIFEST-ячеек)
   или сгенерированных тест-файлов нет вообще (фаза `goga build` не исполнялась).

---

## Output Format

Fill in every section. Empty sections are prohibited.

Каждое поле отчёта — только факты с диска.

```md
# [ACCEPT_SCOPE]

## Data source

[Текущий топик и артефакты, из которых собран объём]

## Cells in scope

[Таблица: Ячейка (tests/web/<cell>/) | Routine | тест-файлы найдены (N/M) | кеш шагов (N/M) | Usage-ключи]

## Trace: Routine → test file

[Таблица: Routine test_<name> | tests/web/<cell>/test_<name>.py | кеш
.cache/test_<name>/test_<name>/ | кеш страницы pages/.cache/<page>/ | Статус (materialized / not)]

## Run command

[Команда pytest (строгий режим: [ENV_NAME=…] pytest tests/web/ -q --strict-mode
[--browser-endpoint <адрес>] [--аргументы рендера base_url], если §1 требует суффиксов/префиксов)
и каталог прогона (корень с conftest.py)]

## Environment notes

[conftest.py найден/отсутствует; web.yml найден/отсутствует; браузер/endpoint из требований §1;
существующий `goga history path -f bugs.md`; тесты без кеша шагов; прочие наблюдения]
```
