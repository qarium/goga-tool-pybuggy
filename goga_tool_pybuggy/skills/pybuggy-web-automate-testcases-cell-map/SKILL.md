---
name: goga-tool-pybuggy-web-automate-testcases-cell-map
description: Cell map for approved Routines — proposes cell boundaries (a design decision — one cell per page, merged flow pages, or several cells per page) and the routine distribution; WAIT for user approval
---

# Pybuggy Web Topic Testcases — Cell Map

## Identity

Ты раскладываешь утверждённые рутины по клеткам. Это дизайн-решение: слаг ячейки становится
именем каталога `tests/web/<cell-name>/`.

## Core Principle

Ячейка — единица материализации и владения: `tests/web/<cell-name>/` + CODEMANIFEST. Стартовая
гипотеза — ячейка на страницу; объединение страниц одного флоу или дробление — осознанные
альтернативы. Предложи готовый вариант раскладки; пользователю не нравится — правь.

---

## Algorithm

### Step 1. Load context

1. [ROUTINES_REPORT] — утверждённые рутины (имена, стартовые страницы из первых шагов `Steps:`).
2. [TESTCASES_INTAKE] — §2 страницы (PAGE-<N> → URL), §9 существующее покрытие.
3. Существующие ячейки `tests/web/**` на диске — новые рутины тех же страниц примыкают к ним
   (merge-семантика на фазе assembly).

### Step 2. Propose the layout

1. Сгруппируй рутины по стартовой странице (адрес первого шага — путь относительно base_url или
   полный URL — ↔ §2).
2. Стартовая гипотеза: одна ячейка на страницу — слаг `kebab-case` от имени/URL страницы
   (`catalog`, `checkout`).
3. Альтернативы: сквозные рутины нескольких страниц одного флоу — ячейка флоу (`checkout-flow`);
   страница с большим числом разнородных рутин — дробление на несколько ячеек.
4. Для каждой ячейки: слаг + обоснование (одной строкой).

### Step 3. WAIT — user approval

AskUserQuestion (один вопрос за сообщение, 2–4 варианта):

- **question**: «Раскладка: <ячейки со слагами и списком рутин>. Утверждаем?»
- **options**: «Утверждаю» / «Объединить <…>» (если применимо) / «Разделить <…>» / «Другое»
  (уточнение текстом).

### Step 4. Produce the [CELL_MAP_REPORT]

STOP if:

- 0 клеток получилось;
- рутина осталась нераспределённой;
- пользователь не утверждает раскладку после итерации.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [CELL_MAP_REPORT]

## Cells

| Ячейка (slug) | Путь | Страницы | Routines | Обоснование |
|---------------|------|----------|----------|-------------|
| catalog | tests/web/catalog/ | PAGE-1 | test_search_finds_results, … | ячейка на страницу |

## Routine → Cell

| Routine | Ячейка |
|---------|--------|
| test_search_finds_results | catalog |

## User Decision

[Утверждено / изменено — что именно подтвердил пользователь]

## Notes

[Существующие ячейки tests/web/**, затронутые merge-семантикой assembly. Напиши `none`, если ничего.]
```
