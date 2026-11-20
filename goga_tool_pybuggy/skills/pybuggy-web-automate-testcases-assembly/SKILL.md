---
name: goga-tool-pybuggy-web-automate-testcases-assembly
description: Assembles and materializes the cells — builds each cell's complete CODEMANIFEST from the approved Routines (Header base block + cell-specific usages, Body, Footer), validates against the goga-cell DSL, writes tests/web/<cell>/CODEMANIFEST (merge for existing cells), then runs goga lint / goga schema and verifies every REQ §3 is covered by a Routine
---

# Pybuggy Web Topic Testcases — Assembly

## Identity

Ты собираешь и материализуешь клетки: из утверждённых рутин и раскладки строишь полный CODEMANIFEST
каждой ячейки и записываешь его в `tests/web/<cell>/CODEMANIFEST`. После записи — механические
гейты: `goga lint`, `goga schema` и REQ-покрытие.

## Core Principle

Сборка детерминирована: внутренности рутин уже утверждены пользователем (routines design),
раскладка утверждена (cell map) — здесь не проектируется ничего нового. Создаётся **только** CODEMANIFEST,
cell-level `.usages/`.

---

## Algorithm

### Step 1. Load context

1. [ROUTINES_REPORT] — утверждённые рутины (полные аннотации) и сессионный реестр покрытия REQ.
2. [CELL_MAP_REPORT] — ячейки и раскладка Routine → ячейка.
3. [TESTCASES_INTAKE] — базовый блок Header и requirements.md (§3 — реестр REQ для проверки
   покрытия).
4. DSL: `goga-cell` / `goga-cell-python` / `goga-tool-pybuggy-web-cookbook` (загружены intake).

### Step 2. Assemble each cell's CODEMANIFEST

Для каждой ячейки из [CELL_MAP_REPORT]:

1. **Header** — базовый блок из [TESTCASES_INTAKE] **дословно**; поверх — cell-specific usages:
   ключи из секций `Use …` рутин ячейки, только с существующими файлами
   `.goga/usages/cooks/<key>.md`. Подключение — строка `<key>: .goga/usages/cooks/<key>.md`
   в `Usages` + строка ``Use `<key>` for <назначение>`` в `Annotations`.
2. **Body** — рутины ячейки **дословно** из [ROUTINES_REPORT]: сигнатура (фикстуры-страницы
   `page_<name>`), `location`, аннотация.
3. **Footer** — `Author: Goga`, `CreatedAt: <день/месяц/год>`, `Description: <зачем ячейка>`.

### Step 3. Validate against the DSL (до записи)

По каждому CODEMANIFEST (`goga-cell` + `goga-tool-pybuggy-web-cookbook`):

1. Структура: Header → `---` → Body → `---` → Footer; ключи чувствительны к регистру.
2. Header: базовый блок идентичен [TESTCASES_INTAKE]; cell-specific ключи резолвятся (файлы есть).
3. Body: только Routine (без `methods`/`properties`, без Entities); сигнатура без выхода;
   `location: test_<name>.py`; snake_case; аннотация — строгая структура секций с пустыми строками;
   бэктик-ссылки (`` `<key>` ``) резолвятся в контексте CODEMANIFEST.
4. Footer: `Author: Goga`, `CreatedAt`, `Description`.

DSL-ошибка — исправь и повтори валидацию; неисправимая — **STOP** (файлов не создавать).

### Step 4. Write the CODEMANIFESTs

Обрабатывай ячейки в порядке [CELL_MAP_REPORT]:

1. **Новая ячейка** — создай `tests/web/<slug>/CODEMANIFEST` (каталог при необходимости).
2. **Существующая ячейка** — **сливай, не перезаписывай**:
   - перед записью сохрани копию существующего файла (для возможного отката);
   - Body: существующие `test_*` Routine не трогай — добавь только новые рутины; имя из плана уже
     есть — сохрани существующий вариант, зафиксируй коллизию в отчёте (warning);
   - Header: слей `Usages` по ключам (базовый блок не меняй; добавь новые cell-specific);
     в `Annotations` для каждого нового ключа — строка ``Use `<key>` …``;
   - Footer: сохрани существующие `CreatedAt`/`Description`; `Author: Goga` не меняется.
3. Никогда не создавай `__init__.py`, тестовый код, cell-level `.usages/` — единственный
   артефакт — CODEMANIFEST.

### Step 5. Mechanical gates

1. `goga lint` — красный → исправь и повтори.
2. `goga schema tests/` — новые/слитые ячейки присутствуют в выводе.
3. **REQ-покрытие** (сессионный реестр) — механическая сверка множеств:
   - реестр требований: все `REQ-<N>` из §3 requirements.md;
   - из Coverage-таблицы [ROUTINES_REPORT]: покрытые REQ + исключённые (исключение валидно только
     с зафиксированным решением пользователя);
   - условие: `покрытые ∪ исключённые = реестр` — без пропусков, дублей и пересечений, и каждая
     Routine из Coverage найдена по имени в материализованных CODEMANIFEST.
   Провал → **STOP** (возврат к routines design). Реестр не персистится: связь «требование →
   рутина» живёт только в сессии; повторный запуск пайплайна строит реестр заново из §3.

### Step 6. Produce the [ASSEMBLY_REPORT]

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [ASSEMBLY_REPORT]

## Cells

| Ячейка | Путь              | Статус (создана / слита: +N Routine, M коллизий) | Usage-ключи |
|--------|-------------------|--------------------------------------------------|-------------|
| […]    | tests/web/<slug>/ | […]                                              | […]         |

## Validation

[Результаты `goga lint` / `goga schema tests/`]

## REQ Coverage

| REQ   | Routine(s) | Ячейка  |
|-------|------------|---------|
| REQ-1 | test_…     | catalog |

[Каждый REQ §3 покрыт; висячих рутин нет.]

## Warnings

[Коллизии имён Routine, пропущенные cell-specific usages. Напиши `none`, если ничего.]
```

## Invariants

### NEVER

- писать тестовый код, `__init__.py`, cell-level `.usages/` — единственный создаваемый артефакт —
  CODEMANIFEST в `tests/web/<slug>/`
- перезаписывать существующий `tests/web/<slug>/CODEMANIFEST` целиком — только слияние новых Routine
  с сохранением существующих
- проектировать новые рутины или менять утверждённые аннотации — они утверждены пользователем
- создавать файлы при DSL-ошибках (сначала halt)

### ALWAYS

- валидировать каждый CODEMANIFEST до записи
- запускать `goga lint` и `goga schema tests/` после материализации
- проверять REQ-покрытие по материализованным файлам против §3 requirements.md
