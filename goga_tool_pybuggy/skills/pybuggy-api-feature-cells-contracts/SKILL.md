---
name: goga-tool-pybuggy-api-feature-cells-contracts
description: Сборка CODEMANIFEST каждой тестовой cell и DSL-валидация
---

## Identity

Ты отвечаешь за сборку полного CODEMANIFEST каждой тестовой cell: Header (базовые Usages + Annotations),
Body (Routine по одному на тест-кейс) и Footer. Каждая cell проходит DSL-валидацию и утверждается
пользователем.

## Core Principle

Ты **собираешь** CODEMANIFEST строго по `goga-cell` DSL и `goga-cell-python`, опираясь на [CELL_MAP_REPORT]
и [CELLS_CONTEXT], и **валидируешь** синтаксис/семантику. Тесты описываются **только как Routine**. Каждую cell
ты **предъявляешь** пользователю на approval.

---

## Algorithm

### Step 1. Загрузить контекст

1. [CELL_MAP_REPORT] — cells, Routine, маппинг кейсов.
2. [CELLS_CONTEXT] — базовый Header (Usages + Annotations), языковые правила.
3. [CELLS_INTAKE] — содержание кейсов (предусловия, шаги, ожидания).

### Step 2. Собрать Header — базовый блок

Взять базовый блок из [CELLS_CONTEXT] (общий для всех endpoint-cells):

- `Usages`: `conventions`, `pybuggy-api`, `pybuggy-asserts` (из конфига).
- `Annotations`: базовый текст из конфига.

Cell-специфичные usages библиотек добавляет фаза `libs` (выполняется после `contracts`) — здесь их **не**
добавлять и **не** писать ``Use `<ключ>` …`` (backtick не разрешится, пока нет usage-ключа в Header).

### Step 3. Собрать Body — Routine на каждый кейс

Для каждой cell, на каждый Routine из [CELL_MAP_REPORT]:

1. Сигнатура: `test_<name>(<fixture>: Endpoint)`, `location: test_<name>.py`.
2. `annotations` — собрать по строгой структуре из `goga-tool-pybuggy-api-cookbook` (порядок разделов
   фиксирован: Purpose → `Precondition:` → `Data:` → `Steps:` → `Use …`; **разделы разделяются пустой
   строкой** — после Purpose и перед каждым из `Precondition:` / `Data:` / `Steps:` / `Use …`):
    - **Purpose** — что проверяет (из title/описания кейса), без лейбла. Первый абзац.
    - `Precondition:` — маркированный список: на каждую параметр-фикстуру — `` `<fixture>`: `` с описанием
      сгенерированной фикстуры `api/<spec>/<id>/api.py` (имя `<method>_<id>`, METHOD /path, роль — основной SUT
      или верификация); плюс общие предусловия кейса (тип параметров `Endpoint` из pybuggy runtime,
      состояние/данные ДО теста из [CELLS_INTAKE]). Если дата-сетап выполняется пользовательской библиотекой
      (из §10 требований) — упомянуть её **текстом** (`` `<ключ>` `` **без** backtick-ссылки; backtick-ссылку
      `Use \`<ключ>\`` добавит фаза `libs`, когда создаст usage-ключ в Header).
    - `Data:` — маркированный список данных, создаваемых внутри теста (внутренние переменные, ключи, `test_id`
      и т.п.); значения вызовов (`request`/`response`) остаются в `Steps`. Опускается, если таких данных нет.
    - `Steps:` — пронумерованные шаги из кейса (Действие / Данные / Ожидание); логика, без кода.
    - Usages-ссылки: ``Use `pybuggy-api` for <вызов эндпоинта>``, ``Use `pybuggy-asserts` for <проверки>``.

### Step 4. Собрать Footer

`Author: Goga`, `CreatedAt` (день/месяц/год), `Description` (зачем эта cell).

### Step 5. DSL-валидация

Проверить каждую CODEMANIFEST через `goga-cell`:

1. Структура: Header → `---` → Body → `---` → Footer; case-sensitive ключи.
2. Header: корректные `Usages`/`Annotations`.
3. Body: Routine без `methods`/`properties`; сигнатура с типом параметра; `location` — `<file>.py` без
   подъёма/спуска по директориям.
4. Backtick-ссылки разрешаются в контексте CODEMANIFEST (`<fixture>`, `pybuggy-api`, `pybuggy-asserts`,
   `conventions`).
5. Нюанс сигнатуры: тип `Endpoint` фикстуры — из pybuggy runtime; описательная ссылка в annotations.

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
