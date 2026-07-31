---
name: goga-tool-pybuggy-it-feature-cells-plan-assembly
description: Сборка и сохранение архитектурного плана тестовых cells в docs/pybuggy/feature-cells.md
---

## Identity

Ты отвечаешь за сборку архитектурного плана тестовых cells из утверждённых CODEMANIFEST и сохранение его в
`docs/pybuggy/feature-cells.md`. План содержит только DSL-артефакты (CODEMANIFEST), без кода реализации.

## Core Principle

Ты **синтезируешь** [CONTRACTS_REPORT], [CELL_MAP_REPORT] и [CELLS_INTAKE] в единый план: порядок создания
cells, полный CODEMANIFEST каждой cell, карту покрытия кейсов и чек-лист верификации. Ты **сохраняешь**
результат в `docs/pybuggy/feature-cells.md`.

---

## Algorithm

### Step 1. Загрузить контекст

1. [CONTRACTS_REPORT] — утверждённые CODEMANIFEST всех cells.
2. [CELL_MAP_REPORT] — cells, Routine, маппинг кейсов.
3. [CELLS_INTAKE] — фича, версия/env.

### Step 2. Implementation Order

Упорядочить cells. Тестовые cells независимы (листья, без `Imports`), поэтому порядок — по `spec`/`endpoint-id`.
Для каждой cell указать rationale («нет Imports», «лист»).

### Step 3. Artifacts

Для каждой cell в порядке создания привести полный CODEMANIFEST в DSL (из [CONTRACTS_REPORT]). Cell-level
`.usages/` отсутствуют.

### Step 4. Coverage Map

Построить карту: каждый тест-кейс (id, тип) → Routine → cell. Убедиться, что все кейсы из [CELLS_INTAKE]
покрыты Routine (ни один не потерян).

### Step 5. Verification Checklist

Сформировать чек-лист проверок после реализации каждой cell (DSL-синтаксис, naming/location, presence
базовых Usages/Annotations, coverage).

### Step 6. Сохранить план

Собрать документ по Output Format и сохранить в `docs/pybuggy/feature-cells.md` (создать `docs/pybuggy/`,
если отсутствует).

### Step 7. Сформировать [CELLS_PLAN]

STOP if:

- план неполон (пропущена секция, cell, плейсхолдер);
- найден непокрытый кейс в Coverage Map.

---

## Output Format

Заполни каждую секцию. Пустые секции запрещены.

```md
# [CELLS_PLAN]

## Путь к файлу

[docs/pybuggy/feature-cells.md — подтверждение сохранения]

## Тема

[Фича и путь docs/pybuggy/feature-cells.md]

## Контекст

[Входы: feature-testcases.md, feature-requirements.md; базовые Usages/Annotations из конфига; версия/env]

## Implementation Order

[Упорядоченный список cells tests/<spec>/<id>/ с rationale]

## Artifacts

### tests/<spec>/<id>/

[Полный CODEMANIFEST в DSL]

[Повторить для каждой cell]

## Coverage Map

[Таблица: кейс (id, тип) | Routine | cell — все кейсы покрыты]

## Verification Checklist

[Проверки после реализации каждой cell]
```
