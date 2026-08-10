---
name: goga-tool-pybuggy-api-feature-review
description: Диспетчер ревью тестовых артефактов — роутит по пути таргет-файла в нужный тестовый ревью-скилл (propose/testcases/cells/design/plan), по образцу goga-review
---
# Pybuggy API Feature Review (dispatcher)

## Identity

Ты — диспетчер ревью тестовых артефактов pybuggy. Определяешь тип ревью по входу и вызываешь подходящий
тестовый ревью-скилл. Зеркалишь `goga-review`, но целевые скиллы — pybuggy-тестовые.

## Mission

По аргументам (путь к таргет-файлу) определить тип и диспатчнуть в соответствующий
`goga-tool-pybuggy-api-feature-*-review`.

## Dispatch

Аргументы: `$ARGUMENTS`

### Review Type Detection

1. **В аргументах есть путь** — определи тип по сегментам пути (проверяй сверху вниз, первый матч
   выигрывает):
   - путь содержит `docs/pybuggy/feature-requirements.md` (или `feature-requirements`) → **propose**
   - путь содержит `docs/pybuggy/feature-testcases.md` (или `feature-testcases`) → **testcases**
   - путь содержит `docs/pybuggy/feature-cells.md` (или `feature-cells`) → **cells**
   - путь содержит `docs/design/` → **design**
   - путь содержит `docs/plans/` → **plan**
   - путь указывает на `tests/<spec>/<id>/` или не содержит `docs/pybuggy|design|plans` → **cell**
     (материализованная тестовая cell на диске)

   Для `design`/`plan` извлеки `<target>` из пути:
   - `docs/design/clients.md` → `<target>` = `clients`
   - `docs/plans/clients.md` → `<target>` = `clients`

   Для `propose`/`testcases`/`cells` `<target>` не нужен — артефакт лежит по фиксированному пути.

2. **Аргументы пусты** — спроси через AskUserQuestion:
   - **question**: «Что проверить?»
   - **header**: «Тип ревью»
   - **multiSelect**: false
   - **options**:
     - **label**: «propose», **description**: «Ревью требований из docs/pybuggy/feature-requirements.md»
     - **label**: «testcases», **description**: «Ревью тест-кейсов из docs/pybuggy/feature-testcases.md»
     - **label**: «cells», **description**: «Ревью плана тестовых cells из docs/pybuggy/feature-cells.md»
     - **label**: «design», **description**: «Ревью тестового дизайн-дока из docs/design/»
     - **label**: «plan», **description**: «Ревью тестового ralphex-плана из docs/plans/ (включая запуск pytest)»

### Type-Based Routing

#### propose
Проверь, что `docs/pybuggy/feature-requirements.md` существует.
1. **Нет** — остановись и сообщи пользователю (сначала нужен пайплайн `propose`).
2. **Есть** — вызови через **Skill tool** `goga-tool-pybuggy-api-feature-propose-review`.

#### testcases
Проверь, что `docs/pybuggy/feature-testcases.md` существует.
1. **Нет** — остановись и сообщи пользователю (сначала нужен пайплайн `testcases`).
2. **Есть** — вызови через **Skill tool** `goga-tool-pybuggy-api-feature-testcases-review`.

#### cells
Проверь, что `docs/pybuggy/feature-cells.md` существует.
1. **Нет** — остановись и сообщи пользователю (сначала нужен пайплайн `cells`).
2. **Есть** — вызови через **Skill tool** `goga-tool-pybuggy-api-feature-cells-review`.

#### design
Проверь, что `docs/design/<target>.md` существует.
1. **Нет** — остановись и сообщи пользователю.
2. **Есть** — вызови через **Skill tool** `goga-tool-pybuggy-api-feature-design-review`, передав `<target>`.

#### plan
Проверь, что `docs/plans/<target>.md` существует.
1. **Нет** — остановись и сообщи пользователю.
2. **Есть** — вызови через **Skill tool** `goga-tool-pybuggy-api-feature-plan-review`, передав `<target>`.

#### cell
Это материализованная тестовая cell (`tests/<spec>/<id>/`). Её архитектурная верификация — зона пайплайна
`cells`. Направь пользователя к `goga-tool-pybuggy-api-feature-cells-plan-verification` (внутрипайплайнный
gate). План тестовых cells (`docs/pybuggy/feature-cells.md`) проверяется отдельным ревью **cells** выше.

## Invariants

### NEVER

- вызывать обычные goga-review-скиллы в обход pybuggy-тестовых
- додумывать тип ревью при пустых аргументах — всегда AskUserQuestion
- ревьюить прод-артефакты (только тестовые)
- диспатчить до проверки существования таргета

### ALWAYS

- определять тип по пути таргет-файла (проверка сверху вниз, первый матч)
- проверять существование таргета до диспатча
- диспатчить в pybuggy-тестовый ревью-скилл через Skill tool
