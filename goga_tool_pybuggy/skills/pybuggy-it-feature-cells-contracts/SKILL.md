---
name: goga-tool-pybuggy-it-feature-cells-contracts
description: Сборка CODEMANIFEST каждой тестовой cell и DSL-валидация
---

## Identity

Ты отвечаешь за сборку полного CODEMANIFEST каждой тестовой cell: Header (базовые Usages + Annotations),
Body (Routine по одному на тест-кейс) и Footer. Каждая cell проходит DSL-валидацию и утверждается
пользователем.

## Core Principle

Ты **собираешь** CODEMANIFEST строго по `goga-cell` DSL и `goga-cell-python`, опираясь на [CELL_MAP_REPORT]
и [CELLS_CONTEXT], и **валидируешь** синтаксис/семантику. Тесты описываются **только как Routine**; `Imports`
не заводятся (фикстура — не cell). Каждую cell ты **предъявляешь** пользователю на approval.

---

## Algorithm

### Step 1. Загрузить контекст

1. [CELL_MAP_REPORT] — cells, Routine, маппинг кейсов.
2. [CELLS_CONTEXT] — базовый Header (Usages + Annotations), языковые правила.
3. [CELLS_INTAKE] — содержание кейсов (предусловия, шаги, ожидания).

### Step 2. Собрать Header (единый для всех cells)

Взять базовый блок из [CELLS_CONTEXT]:

- `Usages`: `conventions`, `pybuggy-api`, `pybuggy-asserts` (из конфига).
- `Annotations`: базовый текст из конфига.
- Без `Imports`.

### Step 3. Собрать Body — Routine на каждый кейс

Для каждой cell, на каждый Routine из [CELL_MAP_REPORT]:

1. Сигнатура: `test_<name>(<fixture>: Endpoint)`, `location: test_<name>.py`.
2. `annotations`:
    - **Purpose** — что проверяет (из title/описания кейса), без лейбла.
    - `` `<fixture>`: `` — описание сгенерированной фикстуры `api/<spec>/<id>/api.py` (имя `<method>_<id>`).
    - `Algorithm:` — пронумерованные шаги из кейса (Действие / Данные / Ожидание); логика, без кода.
    - Usages-ссылки: ``Use `pybuggy-api` for <вызов эндпоинта>``, ``Use `pybuggy-asserts` for <проверки>``.

### Step 4. Собрать Footer

`Author: Goga`, `CreatedAt` (день/месяц/год), `Description` (зачем эта cell).

### Step 5. DSL-валидация

Проверить каждую CODEMANIFEST через `goga-cell`:

1. Структура: Header → `---` → Body → `---` → Footer; case-sensitive ключи.
2. Header: корректные `Usages`/`Annotations`; нет `Imports`.
3. Body: Routine без `methods`/`properties`; сигнатура с типом параметра; `location` — `<file>.py` без
   подъёма/спуска по директориям.
4. Backtick-ссылки разрешаются в контексте CODEMANIFEST (`<fixture>`, `pybuggy-api`, `pybuggy-asserts`,
   `conventions`).
5. Нюанс сигнатуры: тип `Endpoint` фикстуры — из pybuggy runtime; если валидация требует resolve типа без
   `Imports` — оставить описательную ссылку в annotations (формальный импорт не заводить).

### Step 6. WAIT — approval per cell

Предъявить CODEMANIFEST каждой cell (по одной) и через `AskUserQuestion` получить approval: принять /
скорректировать. Вопросы — по одному за сообщение.

### Step 7. Сформировать [CONTRACTS_REPORT]

STOP if:

- DSL-ошибка, не устранённая после итерации;
- approval denied для cell после итерации.

---

## Output Format

Заполни каждую секцию. Пустые секции запрещены.

```md
# [CONTRACTS_REPORT]

## Cells и их CODEMANIFEST

### tests/<spec>/<id>/

[Полный CODEMANIFEST в DSL: Header (Usages + Annotations) → --- → Body (Routine) → --- → Footer]

[Повторить блок для каждой cell]

## Результат DSL-валидации

[На каждую cell: статус PASS/список исправленных ошибок]

## Утверждённые cells

[Список cells, прошедших approval]

## Замечания

[Нюанс с типом фикстуры, допущения и т.п. Пусто, если нет.]
```
