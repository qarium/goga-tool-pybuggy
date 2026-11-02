---
name: goga-tool-pybuggy-web-automate-accept-consistency
description: Pre-run consistency check of the web test chain — TC → Routine → test_*.py traceability, step sentences vs case steps, full-URL compliance vs requirements, step-cache presence, skip masking
---

# Pybuggy Web Topic Accept — Consistency

## Identity

Ты проверяешь консистентность веб-тестовой цепочки до прогона: трассируемость кейсов, соответствие
предложений шагов кейсам, URL-дисциплину, наличие кеша шагов и отсутствие маскировки падений.

## Core Principle

CODEMANIFEST — read-only контракт; все находки чинятся правкой `test_*.py` (или возвратом к фазам
cells) и только с одобрения пользователя. Каждая находка — с точной локализацией и конкретным
предлагаемым исправлением.

---

## Algorithm

### Step 1. Load context

1. [ACCEPT_SCOPE] — трасса TC → Routine → `test_*.py`, статусы кешей, команда прогона.
2. Через **Skill tool**: `goga-cell`, `goga-tool-pybuggy-web-cookbook`, `goga-tool-pybuggy-web-usage`,
   `goga-cell-python`.
3. Путь, напечатанный `goga history path -f testcases.md` — кейсы с шагами.
4. Путь, напечатанный `goga history path -f requirements.md` — §1 Target environment (полные URL),
   §2 страницы.

### Step 2. Routine ↔ test-file

1. Для каждой Routine из CODEMANIFEST ячеек — существует ли `test_<name>.py` по её `location`?
2. Для каждого `test_*.py` в `tests/web/` — есть ли породившая Routine (висячий тест-файл = находка).
3. Сигнатура теста: параметр `web` (pytest резолвит фикстуру по имени); имя `test_<name>` совпадает
   с Routine.

### Step 3. Step sentences ↔ case steps

Для каждого теста сверь предложения шагов (`web.step`/`web.expect`/`web.group`) с шагами кейса
(Действие/Expectation) и аннотацией Routine (`Steps:`):

1. Каждый шаг кейса отражён предложением (напрямую или внутри группы).
2. Лишних предложений нет (нет действий вне кейса).
3. Действия — `web.step`, проверки — `web.expect` (перепутано = находка).
4. Одно действие на предложение (скомбинированные «открыть и заполнить» = находка).

### Step 4. Full-URL compliance

URL в предложениях шагов ↔ Target environment требований §1 и страницам §2: полные URL
записанного окружения. Сокращения (`/catalog` без домена), чужой домен = находка.

### Step 5. Step cache

1. Для каждого теста каталог `tests/web/<cell>/test_<name>/` существует и не пуст (кеш создан
   генерирующим прогоном на build).
2. Отсутствующий/пустой кеш — находка: тест упадёт в strict-режиме cache-miss'ом; решение —
   догенерация не-strict прогоном (после подтверждения пользователя) или дефект материализации.
3. Полное отсутствие кешей у всех тестов — STOP: `goga build` не исполнялся; вернись к стейджу
   ralphex-build.

### Step 6. Skip masking

По каждому `test_*.py`: нет `pytest.skip`, skip-маркеров, `xfail`, закомментированных тестов —
маскировка = находка Critical.

### Step 7. Findings and decisions (WAIT)

1. Собери все находки до показа; сорт по серьёзности Critical → High → Medium.
2. Показывай по одной: Seriousness / Area / Location (тест, TC-<N>, предложение) / Issue / Evidence /
   **Suggested fix** (конкретная правка).
3. AskUserQuestion на каждую (2–4 варианта): **Apply suggested fix** / **Propose alternative** /
   **Skip**. Счётчик: «Находка 3 из 12».
4. Правки — только в `test_*.py`; предложение шага меняется только с явного подтверждения
   (источник — кейс и Routine).
5. Fix scope rule: правь **только** тест-файлы `tests/web/**` и (по решению о догенерации) кеш
   шагов. Не правь CODEMANIFEST, testcases.md, requirements.md, arch.md — они upstream.

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

## Step sentences ↔ case steps

[Таблица: Тест | Кейс TC-<N> | Статус (полное соответствие / чего не хватает / что лишнее)]

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
