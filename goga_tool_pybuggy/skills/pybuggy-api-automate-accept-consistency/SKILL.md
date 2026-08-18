---
name: goga-tool-pybuggy-api-automate-accept-consistency
description: Сверка консистентности цепочки тест-кейс → Routine → test_*.py перед запуском — трассируемость, сигнатуры, location, skip-маскировка, модель Request
---
# Pybuggy API Feature Accept — Consistency

## Identity

Ты отвечаешь за статическую сверку консистентности артефактов до запуска тестов: каждая Routine CODEMANIFEST
материализована в `test_<name>.py`, каждый тест-файл соответствует своей Routine, каждый кейс трассируется
до теста. CODEMANIFEST — эталон только для чтения; расхождения лечатся на стороне `test_*.py` или возвратом
к пайплайнам cells/apply.

## Core Principle

Ты **сверяешь** `test_*.py` с Routine их cells и **фиксируешь** находки. CODEMANIFEST остаётся нетронутым:
при рассинхроне чинится тест-файл (с одобрения пользователя) либо фиксируется возврат к
`pybuggy-api-automate-cells` / `pybuggy-api-automate-apply`.

## Algorithm

### Step 1. Загрузить контекст

1. [ACCEPT_SCOPE] — cells, Routine, тест-файлы, трасса TC → Routine.
2. Через **Skill tool**: `goga-cell`, `goga-tool-pybuggy-api-cookbook`, `goga-tool-pybuggy-api-usage`,
   `goga-cell-python`.
3. Прочитать CODEMANIFEST каждой cell и каждый `test_<name>.py`.

### Step 2. Routine ↔ test-file

Для каждой Routine каждой cell:

1. Файл `tests/<spec>/<id>/test_<name>.py` существует и лежит по `location` из CODEMANIFEST.
2. В файле определена функция `test_<name>`; имя совпадает с Routine.
3. Сигнатура: параметр-фикстура `<fixture>` с типом `Endpoint` (или как предписывает CODEMANIFEST);
   импорт фикстуры из `api/<spec>/<id>/api.py`.
4. Лишние тест-функции в файле сверх Routine (файл на Routine один) — находка.

### Step 3. Тело запроса — модель Request

Для каждого теста по его кейсу (Flow/Positive/Negative из `docs/testcases/<feature>.md`):

1. Валидное тело (positive/flow) материализовано через импортируемую модель `Request` из
   `api/<spec>/<id>/api.py` (`json=Request(...)`).
2. Сырой `dict` для валидного тела — находка (теряется pydantic-валидация запроса).
3. Сырой `dict` для negative-вариантов — норма (минуя pydantic, как предписывают кейсы).

### Step 4. Skip-маскировка и потерянные шаги

1. В `test_*.py` отсутствуют `pytest.skip`, skip-markers, `xfail` — любое вхождение = находка
   **Critical** (маскировка падения).
2. Тело теста линейно: логические конструкции (`if`/`else`, match/case, тернарники), выбирающие шаги
   или ассерты по варианту параметризации, — находка **High** (избыточная параметризация Routine:
   расходящиеся варианты должны жить в отдельных Routine; критерий линейности —
   `goga-tool-pybuggy-api-cookbook`).
3. Шаги `Steps:` аннотации Routine отражены в теле теста (вызовы, проверки); пропущенный шаг кейса —
   находка (Severity по влиянию: потерянная проверка контракта — High).
4. Проверки кейса (статус, поля, структура, инварианты) присутствуют в ассертах — сверить с разделом
   ожиданий кейса в `docs/testcases/<feature>.md`.

### Step 5. Usage-ссылки

1. Cell-спец usage-ключи Header cell: файлы `.goga/usages/cooks/<ключ>.md` существуют.
2. Фикстуры и инструменты, использованные в `test_*.py`, соответствуют подключённым ключам.

### Step 6. Findings и решения

Каждой находке — severity и действие:

- **Critical** — Routine без тест-файла; `pytest.skip`/skip-markers/`xfail`; тест-функция без Routine.
- **High** — валидное тело через `dict`; потерянный шаг кейса; потерянная проверка контракта; битый
  импорт фикстуры.
- **Medium** — лишние тест-функции в файле; отсутствующий cooks-файл ключа.

Действия по находкам (через AskUserQuestion, один вопрос за сообщение, 2–4 варианта):

1. **Починить `test_*.py` здесь** — правка тест-файла в тестовом ключе (по DSL-эталону Routine).
2. **Вернуться к `pybuggy-api-automate-cells` / `-apply`** — при структурных расхождениях (не хватает
   Routine под кейсы, cells не совпадают с планом).
3. **Принять как есть** — с явной фиксацией риска в отчёте.

STOP if:
- тест-файлы не материализованы вовсе — приёмка невозможна до `goga build`;
- пользователь выбрал возврат к cells/apply для Critical-находок (пайплайн приёмки завершается досрочно).

---

## Output Format

Заполни каждую секцию. Пустые секции запрещены.

```md
# [ACCEPT_CONSISTENCY]

## Routine ↔ test-file
[Таблица: Routine | test-файл | Имя функции | Сигнатура/фикстура | Статус]

## Request model compliance
[Таблица: Тест | Кейс (Flow/Positive/Negative) | Тело через Request/dict | Соответствие политике]

## Skip masking
[Список вхождений pytest.skip/skip-markers/xfail с файлом и строкой. Пусто, если нет]

## Steps & assertions coverage
[Таблица: Тест | Шаги кейса отражены | Проверки контракта присутствуют | Пропуски]

## Usage references
[Таблица: Cell | Ключ | Файл .goga/usages/cooks/<ключ>.md существует]

## Findings
[Таблица: Файл | Находка | Severity (Critical/High/Medium) | Действие (чинить здесь / возврат к cells/apply / принять)]

## Applied fixes
[Правки test_*.py, выполненные с одобрения пользователя: файл | что изменено | причина. Пусто, если нет]

## Overall
[CONSISTENT / CONSISTENT_WITH_FIXES / INCONSISTENT — с обоснованием]
```