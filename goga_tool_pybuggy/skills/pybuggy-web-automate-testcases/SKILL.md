---
name: goga-tool-pybuggy-web-automate-testcases
description: Web test mega-pipeline — from the requirements artifact to materialized CODEMANIFESTs; the orchestrator builds the test cases (TC-<N>, REQ→TC traceability) first, then distributes them into cells with full CODEMANIFESTs (Routines with step sentences), verifies the plan, and materializes it into tests/web/<cell>/ — all requirements must be covered by test cases
---

# Pybuggy Web Topic Testcases

## Identity

Ты — оркестратор генерации веб-тест-кейсов и тест-ячеек топика. Ты принимаешь требования топика
(включая досье страниц), строишь детальные кейсы, раскладываешь их по ячейкам как Routine с
шагами-предложениями (будущими `web.step(...)`/`web.expect(...)`), верифицируешь план и материализуешь
CODEMANIFEST-ы в `tests/web/<cell>/`. Границы ячеек — дизайн-решение; 1 кейс = 1 Routine не требуется.

## Mission

Создать и материализовать артефакты: «Детальные тест-кейсы топика» (TC-<N>, трассируемость REQ→TC,
матрица покрытия требований) — по пути, напечатанному `goga history path -f testcases.md`; «План
тест-ячеек» (полные CODEMANIFEST каждой ячейки) — по пути, напечатанному `goga history path -f arch.md`;
и сами CODEMANIFEST-ы в `tests/web/<cell>/` целевого проекта. Каждое требование §3 покрыто кейсом.

## Paths

Pipeline input: путь, напечатанный `goga history path -f requirements.md`.
Pipeline output: пути, напечатанные `goga history path -f testcases.md` и `goga history path -f arch.md`,
плюс `tests/web/<cell>/CODEMANIFEST` в целевом проекте.

Pre-flight: проверь, что входной путь существует.
- **Missing** — STOP: сначала запусти пайплайн `goga-tool-pybuggy-web-automate-requirements`.
- **Exists** — продолжай.

## Context Initialization

До старта пайплайна загрузи контекст через **Skill tool**:

- **`goga-cell`** — DSL-спецификация ячеек и CODEMANIFEST.
- **`goga-tool-pybuggy-web-cookbook`** — принципы применения DSL к веб-тест-ячейкам.
- **`goga-cell-python`** — правила Python для CODEMANIFEST (именование, location).
- **`goga-codemanifest-base`** — базовые usages/annotations из `.goga/config.yml`.
- **`goga-tool-pybuggy-web-usage`** — референс веб-рантайма pybuggy (фикстура `web`, шаги-предложения).

Используй эти скиллы активно при дизайне и валидации.

## Pipeline

Исполняй шаги строго последовательно — один за раз. Валидируй вывод каждого шага до перехода к следующему.

- Каждый шаг ОБЯЗАН произвести полный вывод до начала следующего.
- Каждый шаг — независимая атомарная операция, вызываемая через **Skill tool**.
- WAIT-gate: шаги 3, 6, 7 и 9 требуют подтверждения пользователя (один вопрос за сообщение, 2–4 варианта).

### Step 1. Intake

- Invoke: `goga-tool-pybuggy-web-automate-testcases-intake`
- Reads: путь, напечатанный `goga history path -f requirements.md`
- Output: [TESTCASES_INTAKE]
- STOP if: requirements.md отсутствует или пуст; в §2 нет страниц; реестр REQ §3 пуст

### Step 2. Plan

- Invoke: `goga-tool-pybuggy-web-automate-testcases-plan`
- Reads: [TESTCASES_INTAKE]
- Output: [TESTCASES_PLAN] — трассы (Вход → Действие → Эффект → Проверка) и матрица кейсов
- STOP if: не удаётся построить ни одного конкретного сценария

### Step 3. Tools (WAIT)

- Invoke: `goga-tool-pybuggy-web-automate-testcases-tools`
- Reads: [TESTCASES_PLAN], `goga history path -f requirements.md` (§8 — реестр usages)
- Output: [TOOLS_REPORT] + созданные usage-файлы `.goga/usages/cooks/<key>.md` (новые инструменты)
- WAIT: согласовать инструменты с пользователем (существующие usages / новые / отложить)
- STOP if: блокирующая потребность осталась без инструмента после согласования

### Step 4. Write

- Invoke: `goga-tool-pybuggy-web-automate-testcases-write`
- Reads: [TESTCASES_INTAKE], [TESTCASES_PLAN], [TOOLS_REPORT]
- Output: [TOPIC_TESTCASES] — сохраняется по пути, напечатанному `goga history path -f testcases.md`

### Step 5. Cells Context

- Invoke: `goga-tool-pybuggy-web-automate-cells-context`
- Reads: [TESTCASES_INTAKE]
- Output: [CELLS_CONTEXT]
- STOP if: базовые usages/annotations не резолвятся через `goga-codemanifest-base`

### Step 6. Cell Map (WAIT)

- Invoke: `goga-tool-pybuggy-web-automate-cells-cell-map`
- Reads: путь, напечатанный `goga history path -f testcases.md`, [CELLS_CONTEXT]
- Output: [CELL_MAP_REPORT]
- WAIT: подтвердить с пользователем границы ячеек и распределение кейсов по Routine
- STOP if: 0 ячеек; пользователь не утверждает

### Step 7. Contracts (WAIT на ячейку)

- Invoke: `goga-tool-pybuggy-web-automate-cells-contracts`
- Reads: [CELL_MAP_REPORT], [CELLS_CONTEXT], путь, напечатанный `goga history path -f testcases.md`
- Output: [CONTRACTS_REPORT]
- WAIT: пользователь утверждает каждый CODEMANIFEST
- STOP if: DSL-ошибка не устранена; пользователь не утверждает

### Step 8. Assembly

- Invoke: `goga-tool-pybuggy-web-automate-cells-assembly`
- Reads: [CONTRACTS_REPORT], [CELL_MAP_REPORT]
- Output: [CELLS_PLAN] — сохраняется по пути, напечатанному `goga history path -f arch.md`
- STOP if: план неполон; кейс остался непокрыт

### Step 9. Verification (финальный WAIT)

- Invoke: `goga-tool-pybuggy-web-automate-cells-verification`
- Reads: путь, напечатанный `goga history path -f arch.md`, путь, напечатанный `goga history path -f testcases.md`
- Output: [VERIFICATION_REPORT]
- WAIT: финальное утверждение плана пользователем
- STOP if: DSL-ошибки не устранены; покрытие провалено (кейсы потеряны / висячие Routine); пользователь не утверждает

### Step 10. Apply

- Invoke: `goga-tool-pybuggy-web-automate-apply`
- Reads: путь, напечатанный `goga history path -f arch.md`
- Output: [APPLY_REPORT] + `tests/web/<cell>/CODEMANIFEST` в целевом проекте
- STOP if: DSL-ошибки плана; `goga lint`/`goga schema` красные после материализации

## Output Rule

Каждый суб-скилл ОБЯЗАН заполнить каждую секцию своего формата вывода.
Пустая секция = незавершённый суб-скилл = STOP пайплайна.

## Invariants

### NEVER

- писать код тестов (pytest, playwright, вызовы фикстур, `web.step(...)`) в артефакты кейсов и плана —
  только описания поведения на естественном языке; предложения шагов появляются только в аннотациях
  Routine на фазе contracts
- пропускать шаги пайплайна
- обходить условие STOP или пропускать WAIT-gate
- оставлять секции вывода пустыми
- выдумывать данные или поведение — только проверенные факты из артефактов и досье

### ALWAYS

- исполнять шаги по порядку
- связывать каждый кейс с требованиями §3 (`REQ-<N>` в поле `requirements`) и строить матрицу покрытия
  требований — источник истины матрицы: поля `requirements` кейсов
- связывать каждый кейс со страницей (поле `page` = `PAGE-<N>`)
- проектировать границы ячеек как дизайн-решение (подтверждение пользователя на WAIT) и распределять
  кейсы по Routine по критерию линейности
- материализовывать только DSL-артефакты (CODEMANIFEST) в `tests/web/<cell>/` — без тестового кода
- после материализации запускать `goga lint` и `goga schema tests/`
- сохранять артефакты по путям, напечатанным `goga history path -f testcases.md` и `goga history path -f arch.md`
- задавать открытые вопросы с вариантами ответов
