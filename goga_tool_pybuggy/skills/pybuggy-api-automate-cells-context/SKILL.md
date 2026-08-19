---
name: goga-tool-pybuggy-api-automate-cells-context
description: Загрузка контекста проектирования — базовые usages/annotations, референс pybuggy, правила языка
---

## Identity

Ты отвечаешь за сбор контекста проектирования тестовых cells: базовых Usages/Annotations из конфигурации
проекта, референса pybuggy runtime и языковых правил. Этот контекст един для всех тестовых cells.

## Core Principle

Ты **загружаешь** контекст через скиллы и **фиксируешь** то, что пойдёт в каждую CODEMANIFEST: базовый блок
`Usages` + `Annotations`, референс pybuggy и языковые правила. Скиллы вызываются ради их контента — ты не
пересказываешь, как они устроены внутри.

---

## Algorithm

### Step 1. Загрузить контекст проектирования через Skill tool

Вызови скиллы ради их контента (для чего):

1. `goga-codemanifest-base` — базовые `Usages` и `Annotations` проекта из `.goga/config.yml`.
2. `goga-cell-python` — языковые правила python для CODEMANIFEST (naming, location).
3. `goga-tool-pybuggy-api-usage` — референс потребления runtime pybuggy (`api`, `asserts`).

### Step 2. Зафиксировать базовый блок Header

Из `goga-codemanifest-base` взять единый **базовый** блок `Usages` (`conventions`, `pybuggy-api`,
`pybuggy-asserts`) + `Annotations` — общий для всех тестовых cells. Cell-специфичные usages инструментов поверх базового
блока подключает фаза `contracts` (здесь их не проектировать).

### Step 3. Зафиксировать языковые правила python

Из `goga-cell-python` — ключевые ориентиры для тестовых Routine: naming `snake_case`,
`location: test_<name>.py`.

### Step 4. Зафиксировать референс pybuggy

Из `goga-tool-pybuggy-api-usage` — способ вызова эндпоинта (сгенерированная фикстура `api/<spec>/<id>/api.py`,
имя `<method>_<id>`) и проверок ответа.

### Step 5. Сформировать [CELLS_CONTEXT]

Зафиксировать готовый «базовый блок» Header CODEMANIFEST (Usages + Annotations), одинаковый для всех тестовых
cells, референс pybuggy и языковые ориентиры.

STOP if:

- `goga-codemanifest-base` недоступен или `codemanifest`/базовые usages (`pybuggy-api`, `pybuggy-asserts`)
  отсутствуют.

---

## Output Format

Заполни каждую секцию. Пустые секции запрещены.

```md
# [CELLS_CONTEXT]

## Базовые Usages (из конфига)

[Таблица: ключ | путь (.goga/usages/...) | предметная область]

## Базовый блок Header CODEMANIFEST

[Готовый YAML-блок Usages + Annotations, единый для всех тестовых cells]

## Языковые ориентиры (python)

[Naming snake_case, location test_<name>.py — кратко]

## Референс pybuggy (для annotations Routine)

[Способ вызова эндпоинта (фикстура) и проверок — кратко]

## Замечания

[Отсутствующие опции конфига и т.п. Пусто, если нет.]
```