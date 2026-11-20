---
name: goga-tool-pybuggy-web-automate-accept-consistency
description: Pre-run consistency check of the web test chain — Routine → test_*.py traceability, step sentences vs the Routine annotation, generation_prompt decorators vs the Routine `Prompt:` section, page addressing compliance vs requirements (site pages as base_url-relative paths, external pages by full URLs), step-cache presence, skip masking
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
3. Путь, напечатанный `goga history path -f requirements.md` — §1 Base URL / Target environment,
   §2 страницы с адресами (пути/URL) — база сверки адресации (REQ-связь в тестах не хранится —
   §3 не используется).

### Step 2. Routine ↔ test-file

1. Для каждой Routine из CODEMANIFEST ячеек — существует ли `test_<name>.py` по её `location`?
2. Для каждого `test_*.py` в `tests/web/` — есть ли породившая Routine (висячий тест-файл = находка).
3. Сигнатура теста: фикстуры совпадают с сигнатурой Routine — фикстуры-страницы
   `page_<name>` (pytest резолвит по именам; каждая существует в `pages/<…>_page.py`);
   посторонняя фикстура в сигнатуре — находка; имя `test_<name>`
   совпадает с Routine.

### Step 3. Step sentences ↔ Routine annotation

Для каждого теста сверь предложения шагов (`page.step`/`page.expect`/`page.group` — поверхность
активированной страницы) с аннотацией его
Routine (`Steps:`):

1. Каждый пункт `Steps:` аннотации отражён предложением (напрямую или внутри группы) либо
   вызовом метода page-объекта (предложение-цель со ссылкой ``Use `page-<name>` — метод``);
   навигационное пункт — активацией `with page_<name>() as page:`.
2. Лишних предложений нет (нет действий вне аннотации).
3. Действия — `page.step`, проверки — `page.expect` (перепутано = находка; исключение —
   транзитные тосты/баннеры с временем жизни из §2 деталей: их подтверждение живёт в
   предложении-действии-триггере — это не перепутывание, см. cookbook).
4. Одно действие на предложение (скомбинированные «открыть и заполнить» = находка).

### Step 4. Generation prompts ↔ `Prompt:`

Для каждого теста сверь декораторы `@generation_prompt("…")` (импорт
`from goga_tool_pybuggy import generation_prompt`) с секцией `Prompt:` аннотации его Routine:

1. Каждый буллет `Prompt:` отражён декоратором с тем же текстом.
2. Лишних декораторов нет (тест от Routine без `Prompt:` декораторов не имеет).
3. Порядок декораторов = порядок буллетов аннотации.

### Step 5. Page addressing compliance

Адреса в предложениях шагов ↔ Base URL §1 и страницам §2 требований: страницы топика — путями
относительно base_url (как в §2), внешние страницы — полными URL чужого origin с пометкой
«внешняя». Голый host без схемы, путь не из §2, чужой домен без пометки = находка.

### Step 6. Step cache

1. Для каждого теста каталог `tests/web/<cell>/.cache/test_<name>/test_<name>/` существует и не пуст
   (кеш создан генерирующим прогоном на build; параметризованный кейс —
   `…/test_<name>[<param_id>]/`).
2. Для каждой страницы, чьи фикстуры/методы используют тесты (секции `Use page-<name>`), общий
   кеш `pages/.cache/<page>/` существует и не пуст — отсутствующий/пустой кеш страницы — находка:
   первый strict-прогон упадёт cache-miss'ом на активацию/методы страницы.
3. Отсутствующий/пустой кеш — находка: тест упадёт в strict-режиме cache-miss'ом; решение —
   догенерация не-strict прогоном (после подтверждения пользователя) или дефект материализации.
4. Полное отсутствие кешей у всех тестов — STOP: `goga build` не исполнялся; сначала прогони его
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

## Page addressing compliance

[Таблица: Тест | Предложение с адресом | Статус (ок — путь из §2 / внешний полный URL / путь не
из §2 / чужой origin без пометки)]

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
