---
name: goga-tool-pybuggy-web-automate-cells-contracts
description: Assembles the complete CODEMANIFEST of each web test cell (Header with base + cell-specific usages, Body with Routines whose Steps are step sentences — the future web.step/web.expect, Footer) and validates it against the goga-cell DSL; WAIT for user approval per cell
---

# Pybuggy Web Topic Cells — Contracts

## Identity

Ты собираешь полные CODEMANIFEST веб-ячеек: Header (базовый блок + cell-specific usages), Body
(Routine с аннотациями, чьи `Steps:` — предложения шагов, будущие `web.step(...)`/`web.expect(...)`),
Footer. Каждый CODEMANIFEST валидируется против DSL **до** показа пользователю.

## Core Principle

Аннотация Routine — источник, из которого сгенерируется тест: всё значимое выражается в ней.
Предложения шагов пишутся обыкновенным языком (одно действие на предложение, полные URL, секреты
запрещены) и соответствуют шагам кейса. Структура секций аннотации строгая:
Purpose → `Precondition:` → (`Data:`) → `Steps:` → (`Use …`), с пустой строкой между секциями.

---

## Algorithm

### Step 1. Load context

1. [CELL_MAP_REPORT] — ячейки и распределение TC → Routine.
2. [CELLS_CONTEXT] — базовый блок Header и правила.
3. Путь, напечатанный `goga history path -f testcases.md` — кейсы с шагами (Действие / Данные /
   Expectation).
4. DSL: `goga-cell` (уже загружен оркестратором), `goga-tool-pybuggy-web-cookbook` — активные
   принципы этой фазы.

### Step 2. Assemble each cell's CODEMANIFEST

Для каждой ячейки из [CELL_MAP_REPORT]:

1. **Header** — базовый блок [CELLS_CONTEXT] **дословно**; поверх — cell-specific usages ячейки
   (только ключи с существующими файлами, из [TOOLS_REPORT]/[CELLS_CONTEXT]): строка
   `<key>: .goga/usages/cooks/<key>.md` в `Usages` + строка ``Use `<key>` for <назначение>`` в
   `Annotations`.
2. **Body** — по каждой Routine:
   - сигнатура `test_<name>(web: PrettyPlay)`, `location: test_<name>.py` (snake_case);
   - **Purpose** — что Routine проверяет (из title/expected result кейса);
   - **`Precondition:`** — буллет `` `web` `` (фикстура веб-рантайма) + предусловия кейса
     (авторизация — поведенчески: «выполнен вход как тестовый пользователь `<роль>`»);
   - **`Data:`** (если есть) — захваты переменных со страницы и внутренние данные теста
     («захватить `<значение>` в `total`»); для параметризованных Routine — перечень вариантов;
   - **`Steps:`** — нумерованные предложения шагов, каждое — **ровно одно** из:
     действие кейса → предложение действия (материализуется в `web.step`),
     проверка кейса → предложение проверки (`web.expect`),
     тесно связанный мини-сценарий (2–3 шага одной цели) → `web.group`;
     шаги кейса переносятся в предложения **дословно по сути**: полный URL, имя поля, название
     кнопки, конкретные данные (кроме секретов — только ссылка на источник);
   - **`Use …`** (если есть) — только cell-specific usages, используемые в этой Routine.
3. **Footer** — `Author: Goga`, `CreatedAt: <день/месяц/год>`, `Description: <зачем ячейка>`.

### Step 3. Validate against the DSL

До показа пользователю проверь каждый CODEMANIFEST (`goga-cell` + `goga-tool-pybuggy-web-cookbook`):

1. Структура: Header → `---` → Body → `---` → Footer; ключи чувствительны к регистру.
2. Header: базовый блок идентичен [CELLS_CONTEXT]; cell-specific ключи резолвятся (файлы существуют).
3. Body: только Routine (без `methods`/`properties`); сигнатура без выхода; `location` корректен;
   аннотация — строгая структура секций с пустыми строками; бэктик-ссылки резолвятся в контексте
   CODEMANIFEST (`` `web` ``, `` `<key>` ``).
4. Предложения шагов: одно действие на шаг; полные URL; секретов нет; каждый шаг кейса отражён;
   лишних шагов нет.
5. Footer: `Author: Goga` и др.

DSL-ошибка — исправь и повтори валидацию; неисправимая — **STOP**.

### Step 4. WAIT — approval per cell

Показывай CODEMANIFEST ячейки пользователю по одному; AskUserQuestion (2–4 варианта):
«Утверждаю» / «Правка» (что изменить) / «Отклонить ячейку» (вернуться к cell-map).

### Step 5. Produce the [CONTRACTS_REPORT]

STOP if:

- DSL-ошибка не устранена;
- пользователь отклонил ячейку и отказался от возврата к cell-map.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [CONTRACTS_REPORT]

## Cell: <slug> (tests/web/<slug>/)

### CODEMANIFEST

[Полный CODEMANIFEST ячейки — Header / --- / Body (Routines) / --- / Footer]

### Validation

[DSL-проверки: пройдено / что исправлялось]

### User Decision

[Утверждено / правки пользователя]

## Cell: <следующая ячейка>

[…]

## Coverage

[Каждый TC покрыт напрямую или вариантом параметризованной Routine; висячих Routine нет]

## Cell-specific Usages

| Ячейка | key | назначение |
|--------|-----|------------|
| […] | `<key>` | […] |

[Если cell-specific usages нет — `none`]
```
