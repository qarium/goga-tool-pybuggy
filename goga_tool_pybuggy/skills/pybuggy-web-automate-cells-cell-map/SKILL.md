---
name: goga-tool-pybuggy-web-automate-cells-cell-map
description: Web test cell boundaries (a design decision — one cell per page, merged flow pages, or several cells per page) and the distribution of cases across Routines by the linearity criterion; WAIT for user approval
---

# Pybuggy Web Topic Cells — Cell Map

## Identity

Ты проектируешь границы веб-тест-ячеек и распределяешь кейсы по Routine. Это дизайн-решение:
текстовый слаг ячейки становится именем каталога `tests/web/<cell-name>/`.

## Core Principle

Ячейка — единица материализации и владения: `tests/web/<cell-name>/` + CODEMANIFEST. Стартовая
гипотеза — **ячейка на страницу**; объединение страниц одного флоу или дробление — осознанные
альтернативы, которые предлагаешь пользователю. Кейсы раскладываются по Routine по критерию
линейности: одна Routine — совпадающий набор шагов и проверок (варианты различаются только данными).

---

## Algorithm

### Step 1. Load context

1. Прочитай путь, напечатанный `goga history path -f testcases.md` — все кейсы TC-<N> (с полями
   `requirements`, `page`, шагами).
2. [CELLS_CONTEXT] — базовый блок и правила.

### Step 2. Propose the cell hypothesis

1. Сгруппируй кейсы по стартовой странице (поле `page`).
2. Стартовая гипотеза: одна ячейка на страницу — слаг `kebab-case` от имени/URL страницы
   (`catalog`, `checkout`).
3. Рассмотри альтернативы:
   - **Объединение**: кейсы Flow, проходящие через несколько страниц одного флоу, — ячейка флоу
     (`checkout-flow`), чтобы сквозные Routine жили вместе;
   - **Дробление**: страница с многородовыми кейсами (поиск + карточка + отзывы) — отдельные ячейки
     на группы кейсов, если ячейка на страницу стала бы слишком крупной;
   - Существующие ячейки `tests/web/**` (из §9) — новые кейсы одной страницы примыкают к ним
     (merge при apply).
4. Для каждой ячейки предложи слаг и обоснование (одной строкой).

### Step 3. Distribute the cases across Routines

1. По каждой ячейке сгруппируй кейсы в Routine по критерию линейности:
   - кейсы с идентичным набором шагов/проверок, различающиеся данными (значения полей, ожидаемые
     тексты) — одна параметризованная Routine;
   - разный набор шагов/проверок — разные Routine.
2. Имя Routine: `test_<snake_case>` от сути кейса (`test_search_finds_results`,
   `test_search_empty_query_shows_hint`).
3. Проверь: каждый кейс покрыт (напрямую или как вариант параметризованной Routine); висячих
   Routine нет.

### Step 4. WAIT — user approval

AskUserQuestion (один вопрос за сообщение, 2–4 варианта):

- **question**: «Границы ячеек: <список ячеек со слагами>. Утверждаем?»
- **options**: «Утверждаю» / «Объединить <…>» (если применимо) / «Разделить <…>» / «Другое»
  (уточнение текстом).

### Step 5. Produce the [CELL_MAP_REPORT]

STOP if:

- 0 ячеек получилось;
- пользователь не утверждает границы после итерации;
- кейс остался нераспределённым.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [CELL_MAP_REPORT]

## Cells

| Ячейка (slug) | Путь | Страницы | Кейсы | Обоснование |
|---------------|------|----------|-------|-------------|
| catalog | tests/web/catalog/ | PAGE-1 | TC-1, TC-2, TC-3 | ячейка на страницу |

## TC → Routine → Cell

| TC | Routine | Параметризация | Ячейка |
|----|---------|----------------|--------|
| TC-1 | test_search_finds_results | — | catalog |
| TC-2, TC-3 | test_search_query_variant | варианты: данные запроса | catalog |

## User Decision

[Утверждено / изменено — что именно подтвердил пользователь]

## Notes

[Существующие ячейки tests/web/**, затронутые merge-семантикой apply. Напиши `none`, если ничего.]
```
