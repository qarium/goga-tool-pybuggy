---
name: goga-tool-pybuggy-web-automate-accept-consistency
description: Pre-run consistency check of the web test chain — Routine → test_*.py traceability, step sentences vs the Routine annotation, generation_prompt decorators vs the Routine `Prompt:` section, full-URL compliance vs requirements, step-cache presence, skip masking
---

# Pybuggy Web Topic Accept — Consistency

## Identity

Ты проверяешь консистентность веб-тестовой цепочки до прогона: трассируемость Routine → тест,
соответствие предложений шагов аннотациям Routine, URL-дисциплину, наличие кеша шагов и отсутствие
маскировки падений.

## Core Principle

CODEMANIFEST — read-only контракт; все находки чинятся правкой `test_*.py` (или возвратом к пайплайну
testcases) и только с одобрения пользователя. Каждая находка — с точной локализацией и конкретным
предлагаемым исправлением.

---

## Algorithm

### Step 1. Load context

1. [ACCEPT_SCOPE] — трасса Routine → `test_*.py`, статусы кешей, команда прогона.
2. Через **Skill tool**: `goga-cell`, `goga-tool-pybuggy-web-cookbook`, `goga-tool-pybuggy-web-usage`,
   `goga-cell-python`.
3. Путь, напечатанный `goga history path -f requirements.md` — §1 Target environment (полные URL),
   §2 страницы (REQ-связь в тестах не хранится — §3 не используется).

### Step 2. Routine ↔ test-file

1. Для каждой Routine из CODEMANIFEST ячеек — существует ли `test_<name>.py` по её `location`?
2. Для каждого `test_*.py` в `tests/web/` — есть ли породившая Routine (висячий тест-файл = находка).
3. Сигнатура теста: параметр `web` (pytest резолвит фикстуру по имени); имя `test_<name>` совпадает
   с Routine.

### Step 3. Step sentences ↔ Routine annotation

Для каждого теста сверь предложения шагов (`web.step`/`web.expect`/`web.group`) с аннотацией его
Routine (`Steps:`):

1. Каждый пункт `Steps:` аннотации отражён предложением (напрямую или внутри группы).
2. Лишних предложений нет (нет действий вне аннотации).
3. Действия — `web.step`, проверки — `web.expect` (перепутано = находка).
4. Одно действие на предложение (скомбинированные «открыть и заполнить» = находка).

### Step 4. Generation prompts ↔ `Prompt:`

Для каждого теста сверь декораторы `@generation_prompt("…")` (импорт
`from goga_tool_pybuggy import generation_prompt`) с секцией `Prompt:` аннотации его Routine:

1. Каждый буллет `Prompt:` отражён декоратором с тем же текстом.
2. Лишних декораторов нет (тест от Routine без `Prompt:` декораторов не имеет).
3. Порядок декораторов = порядок буллетов аннотации.

### Step 5. Full-URL compliance

URL в предложениях шагов ↔ Target environment требований §1 и страницам §2: полные URL
записанного окружения. Сокращения (`/catalog` без домена), чужой домен = находка.

### Step 6. Step cache

1. Для каждого теста каталог `tests/web/<cell>/cache/test_<name>/` существует и не пуст (кеш создан
   генерирующим прогоном на build).
2. Отсутствующий/пустой кеш — находка: тест упадёт в strict-режиме cache-miss'ом; решение —
   догенерация не-strict прогоном (после подтверждения пользователя) или дефект материализации.
3. Полное отсутствие кешей у всех тестов — STOP: `goga build` не исполнялся; сначала прогони его
   по плану топика (первый, генерирующий прогон).

### Step 7. Skip masking

По каждому `test_*.py`: нет `pytest.skip`, skip-маркеров, `xfail`, закомментированных тестов —
маскировка = находка Critical.

### Step 8. Findings and decisions (WAIT)

1. Собери все находки до показа; сорт по серьёзности Critical → High → Medium.
2. Показывай по одной: Seriousness / Area / Location (тест, Routine, предложение) / Issue / Evidence /
   **Suggested fix** (конкретная правка).
3. AskUserQuestion на каждую (2–4 варианта): **Apply suggested fix** / **Propose alternative** /
   **Skip**. Счётчик: «Находка 3 из 12».
4. Правки — только в `test_*.py`; предложение шага меняется только с явного подтверждения
   (источник — аннотация Routine).
5. Fix scope rule: правь **только** тест-файлы `tests/web/**` и (по решению о догенерации) кеш
   шагов. Не правь CODEMANIFEST, requirements.md — они upstream.

STOP if:

- тест-файлы не материализованы (у Routine нет `test_*.py`);
- кеш шагов отсутствует у всех тестов (сначала — `goga build`).

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [ACCEPT_CONSISTENCY]

## Routine ↔ test-file

[Таблица: Routine | test_<name>.py | Статус (ok / отсутствует / висячий файл)]

## Step sentences ↔ Routine annotation

[Таблица: Тест | Routine | Статус (полное соответствие / чего не хватает / что лишнее)]

## Generation prompts ↔ `Prompt:`

[Таблица: Тест | Буллеты `Prompt:` / декораторы | Статус (совпадают / нет декоратора / лишний декоратор / порядок)]

## Full-URL compliance

[Таблица: Тест | Предложение с URL | Статус (ок / сокращён / чужое окружение)]

## Step cache

[Таблица: Тест | Каталог кеша | Статус (есть и не пуст / отсутствует / пуст)]

## Skip masking

[Тесты с маскировкой или `none`]

## Findings

[Список находок: Seriousness / Location / Issue / Suggested fix. Напиши `none`, если ничего]

## Applied fixes

[Применённые правки тест-файлов + догенерации кеша. Напиши `none`, если ничего]

## Overall

[Цепочка консистентна / имеет N открытых находок — влияние на прогон]
```
