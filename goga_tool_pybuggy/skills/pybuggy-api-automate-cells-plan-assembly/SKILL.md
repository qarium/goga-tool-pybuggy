---
name: goga-tool-pybuggy-api-automate-cells-plan-assembly
description: Сборка и сохранение архитектурного плана тестовых cells в docs/arch/<feature>.md
---

## Identity

Ты отвечаешь за сборку архитектурного плана тестовых cells из утверждённых CODEMANIFEST и сохранение его в
`docs/arch/<feature>.md`. План содержит только DSL-артефакты (CODEMANIFEST), без кода реализации.

## Core Principle

Ты **синтезируешь** [CONTRACTS_REPORT], [CELL_MAP_REPORT] и [CELLS_INTAKE] в единый план: порядок создания
cells, полный CODEMANIFEST каждой cell, карту покрытия кейсов и чек-лист верификации. Ты **сохраняешь**
результат в `docs/arch/<feature>.md`.

---

## Algorithm

### Step 1. Загрузить контекст

1. [CONTRACTS_REPORT] — утверждённые CODEMANIFEST всех тестовых cells (включая cell-спец usages
   инструментов, подключённые в `contracts`).
2. [CELL_MAP_REPORT] — cells, Routine, маппинг кейсов.
3. [CELLS_INTAKE] — фича, версия/env.

### Step 2. Implementation Order

Cells `tests/<spec>/<id>/` — порядок по `spec`/`<id>`. Для каждой cell указать rationale:
какие эндпоинты и кейсы она покрывает.

### Step 3. Artifacts

Привести полный CODEMANIFEST каждой cell в порядке создания (из [CONTRACTS_REPORT]) — включая
cell-спец usages инструментов в Header, если `contracts` их подключил. Cell-level `.usages/` у
тестовых cells отсутствуют; usage-файлы инструментов — проект-level в `.goga/usages/cooks/`, в плане не проектируются.

### Step 4. Coverage Map

Построить карту: кейсы (`TC-<N>`, тип) → Routine → cell (один Routine может покрывать несколько кейсов).
Убедиться, что все кейсы из [CELLS_INTAKE] покрыты — напрямую или как вариант/параметр Routine
(ни один не потерян).

### Step 5. Verification Checklist

Сформировать чек-лист проверок после реализации каждой cell (DSL-синтаксис, naming/location, presence
базовых Usages/Annotations, coverage).

### Step 6. Сохранить план

Собрать документ по Output Format и сохранить в `docs/arch/<feature>.md` (путь передаёт оркестратор пайплайна
через Artifact Path Resolution; создать `docs/arch/`, если отсутствует).

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

[docs/arch/<feature>.md — подтверждение сохранения]

## Тема

[Фича и путь docs/arch/<feature>.md]

## Контекст

[Входы: docs/testcases/<feature>.md, docs/requirements/<feature>.md; базовые Usages/Annotations из конфига;
версия/env]

## Implementation Order

[Упорядоченный список cells tests/<spec>/<id>/ с rationale]

## Artifacts

### tests/<spec>/<id>/

[Полный CODEMANIFEST в DSL]

[Повторить для каждой cell]

## Cell-спец usages (инструменты)

[Таблица: cell (tests/<spec>/<id>/) | подключённые usage-ключи | Annotations-строки. «нет» — если ни одна
cell не использует инструменты (usage-ключи, кроме базового блока, отсутствуют во всех cells).]

## Coverage Map

[Таблица: кейс (TC-<N>, тип) | Routine | cell — все кейсы покрыты напрямую или как вариант Routine; один Routine может встречаться в нескольких строках]

## Verification Checklist

[Проверки после реализации каждой cell]
```
