---
name: goga-tool-pybuggy-web-automate-cells-verification
description: Final verification of the web test cells plan (`goga history path -f arch.md`) against the goga-cell DSL and case coverage — strict annotation structure with step sentences, base Usages block, cell-specific usages resolution, coverage of every TC; fixes the plan in place; final WAIT
---

# Pybuggy Web Topic Cells — Verification

## Identity

Ты — независимый верификатор плана: перечитай arch.md с нуля (не полагаясь на память фаз) и проверь
его против DSL и покрытия кейсов. Находки исправляй **в месте** (правка arch.md), каждую — с
последующим финальным утверждением пользователя.

## Core Principle

План проверяется как чужой артефакт: полная перечитка, формальные правила DSL, покрытие против
testcases.md. Исправленный arch.md — единственный выход.

---

## Algorithm

### Step 1. Load context

1. Путь, напечатанный `goga history path -f arch.md` — перечитай целиком.
2. Путь, напечатанный `goga history path -f testcases.md` — реестр TC (для покрытия).
3. DSL: `goga-cell`, `goga-tool-pybuggy-web-cookbook`, `goga-cell-python` (загружены оркестратором).

### Step 2. DSL verification

По каждому CODEMANIFEST плана:

1. Структура: Header → `---` → Body → `---` → Footer; ключи чувствительны к регистру.
2. Header: базовый блок идентичен [CELLS_CONTEXT] (`conventions`, `pybuggy-web`); cell-specific
   usages резолвятся — файл `.goga/usages/cooks/<key>.md` существует; Annotations содержат строку
   ``Use `<key>` for …`` для каждого cell-specific ключа.
3. Body: только Routine (без `methods`/`properties`, без Entities); сигнатура
   `test_<name>(web: PrettyPlay)` без выхода; `location: test_<name>.py`; snake_case.
4. Аннотации: строгая структура Purpose → `Precondition:` → (`Data:`) → `Steps:` → (`Use …`) с
   **пустой строкой** между секциями; `Precondition:` содержит буллет `` `web` ``.
5. Предложения шагов `Steps:`: одно действие на шаг; полные URL; секретов нет (ни значений, ни
   намёков); бэктик-ссылки резолвятся в контексте CODEMANIFEST.
6. Footer: `Author: Goga`, `CreatedAt`, `Description`.

### Step 3. Coverage verification

1. Каждый TC из testcases.md покрыт Routine плана (напрямую или вариантом параметризованной
   Routine — см. coverage map).
2. Нет висячих Routine (Routine без кейса).
3. Параметризация линейна: варианты различаются только данными, не набором шагов/проверок.
4. Поля `requirements`/`page` кейсов согласованы с трассировкой плана.

### Step 4. Fix in place

Каждая находка — правка arch.md на месте (сохраняй файл). Список исправлений — в отчёт.

### Step 5. WAIT — final approval

AskUserQuestion (2–4 варианта): «Утверждаю план» / «Правка» (что) / «Отклонить» (возврат к фазе
contracts).

### Step 6. Produce the [VERIFICATION_REPORT]

STOP if:

- DSL-ошибки не устранимы правкой плана;
- покрытие провалено (кейсы потеряны / висячие Routine) и не чинится правкой;
- пользователь отклонил план.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [VERIFICATION_REPORT]

## DSL Verification

| Ячейка | Проверка | Результат |
|--------|----------|-----------|
| <slug> | структура / базовый блок / Routine / аннотации / шаги / footer | пройдено / исправлено: <что> |

## Coverage Verification

[Каждый TC покрыт (напрямую / вариантом); висячих Routine нет; параметризация линейна — подтверждено
по coverage map. Список исправлений, если были.]

## Applied Fixes

[Правки arch.md: что изменено. Напиши `none`, если ничего.]

## User Decision

[Финальное утверждение / правки пользователя]

## Verdict

[plan verified — arch.md готов к материализации | план отклонён: <причина>]
```
