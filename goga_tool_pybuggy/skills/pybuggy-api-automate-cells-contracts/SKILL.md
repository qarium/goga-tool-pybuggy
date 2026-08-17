---
name: goga-tool-pybuggy-api-automate-cells-contracts
description: Сборка CODEMANIFEST каждой тестовой cell и DSL-валидация
---

## Identity

Ты отвечаешь за сборку полного CODEMANIFEST каждой тестовой cell: Header (базовые Usages + Annotations),
Body (Routine под тест-кейсы — один Routine может покрывать несколько кейсов) и Footer. Каждая cell проходит
DSL-валидацию и утверждается
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

Если cell использует инструмент (из Предусловий кейсов `[CELLS_INTAKE]`): добавить в `Usages` запись
`<ключ>: .goga/usages/cooks/<ключ>.md` и в `Annotations` строку ``Use `<ключ>` for <подготовка
данных/моки/утилиты>`` — поверх базового блока, только в затронутых cells. Базовый блок не менять.

Cell-специфичные usages инструментов (библиотеки данных/моков/утилит) подключаются **здесь**: usage-файлы
`.goga/usages/cooks/<ключ>.md` уже созданы, поэтому ключ можно сразу добавить в `Usages` Header затронутой cell и
ссылаться backtick'ом. Ключи берутся из Предусловий кейсов (`[CELLS_INTAKE]`) и §8 требований.

### Step 3. Собрать Body — Routine под кейсы

Для каждой cell, на каждый Routine из [CELL_MAP_REPORT] (один Routine может покрывать один или несколько
кейсов): если Routine покрывает >1 кейса, вырази параметризацию в аннотации — перечисли варианты в `Data:`
и/или `Steps`; имя Routine `test_<name>` и `location: test_<name>.py` остаются одни на Routine.

1. Сигнатура: `test_<name>(<fixture>: Endpoint)`, `location: test_<name>.py`.
2. `annotations` — собрать по строгой структуре из `goga-tool-pybuggy-api-cookbook` (порядок разделов
   фиксирован: Purpose → `Precondition:` → `Data:` → `Steps:` → `Use …`; **разделы разделяются пустой
   строкой** — после Purpose и перед каждым из `Precondition:` / `Data:` / `Steps:` / `Use …`):
    - **Purpose** — что проверяет (из title/описания кейса), без лейбла. Первый абзац.
    - `Precondition:` — маркированный список: на каждую параметр-фикстуру — `` `<fixture>`: `` с описанием
      сгенерированной фикстуры `api/<spec>/<id>/api.py` (имя `<method>_<id>`, METHOD /path, роль — основной SUT
      или верификация); плюс общие предусловия кейса (тип параметров `Endpoint` из pybuggy runtime,
      состояние/данные ДО теста из [CELLS_INTAKE]). Если дата-сетап выполняется инструментом — указать ключ
      backtick-ссылкой `` `<ключ>` `` (ключ уже подключён в `Usages` Header этой cell на Step 2 — ссылка
      разрешается сразу).
    - `Data:` — маркированный список данных, создаваемых внутри теста (внутренние переменные, ключи, `test_id`
      и т.п.); значения вызовов (`request`/`response`) остаются в `Steps`. Опускается, если таких данных нет.
    - `Steps:` — пронумерованные шаги из кейса (Действие / Данные / Ожидание); логика, без кода.
      **Тело запроса:** валидное (positive/flow) описывай через модель `Request(...)` (импорт из `api.py`
      фикстуры) — **текстом, без backtick-ссылки** (модель внешняя относительно CODEMANIFEST; backtick только
      на `` `<fixture>` ``); невалидное (negative — нет обязательного поля, неверный тип, пустое тело, битый JSON) —
      **сырым `dict`** с пометкой «минуя pydantic-модель» (иначе `ValidationError` до отправки запроса, и SUT
      не будет протестирован). **Не описывай валидное тело `dict`-нотацией** `{field: value}` — `Steps`
      материализуются в `test_*.py` дословно, и `dict` потеряет валидацию запроса.
    - Usages-ссылки (`Use …`) — **только специфичные для Routine**: cell-спец usages библиотек (напр.
      ``Use `faker` for генерации test_id``). Базовые `pybuggy-api`/`pybuggy-asserts`/`conventions` уже в
      глобальных `Annotations` заголовка — **не дублируй** их в Routine (по `goga-cell`: аннотации разных
      уровней не дублируют друг друга). Раздел `Use …` опускается, если специфичных usages нет.

### Step 4. Собрать Footer

`Author: Goga`, `CreatedAt` (день/месяц/год), `Description` (зачем эта cell).

### Step 5. DSL-валидация

Проверить каждую CODEMANIFEST через `goga-cell`:

1. Структура: Header → `---` → Body → `---` → Footer; case-sensitive ключи.
2. Header: корректные `Usages`/`Annotations`.
3. Body: Routine без `methods`/`properties`; сигнатура с типом параметра; `location` — `<file>.py` без
   подъёма/спуска по директориям.
4. Backtick-ссылки разрешаются в контексте CODEMANIFEST (`<fixture>`, `pybuggy-api`, `pybuggy-asserts`,
   `conventions`, cell-спец ключи инструментов из `Usages` Header).
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
