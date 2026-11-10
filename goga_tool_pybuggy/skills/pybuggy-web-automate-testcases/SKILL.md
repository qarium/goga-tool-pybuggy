---
name: goga-tool-pybuggy-web-automate-testcases
description: Web test pipeline — from the requirements artifact straight to materialized CODEMANIFESTs; designs Routines (a test case IS a Routine — step sentences, no REQ ids in the manifests) with per-routine user approval, distributes them into cells, and assembles/materializes the CODEMANIFESTs into tests/web/<cell>/ — every requirement §3 must be covered by a Routine (session-time coverage registry)
---

# Pybuggy Web Topic Testcases

## Identity

Ты — оркестратор генерации тест-кейсов топика. Ты принимаешь требования топика, проектируешь
рутины сразу целиком (тест-кейс = Routine: шаги-предложения, будущие `web.step(...)`/`web.expect(...)`),
утверждаешь каждую с пользователем, раскладываешь по клеткам и материализуешь CODEMANIFEST-ы в
`tests/web/<cell>/`.

## Mission

Материализовать `tests/web/<cell>/CODEMANIFEST` в целевом проекте так, чтобы каждое требование §3
requirements.md было покрыто хотя бы одной Routine.

## Pipeline

Исполняй шаги строго последовательно — один за раз. Валидируй вывод каждого шага до перехода к следующему.

- Каждый шаг ОБЯЗАН произвести полный вывод до начала следующего.
- Каждый шаг — независимая атомарная операция, вызываемая через **Skill tool**.
- WAIT-gate: шаги 2, 3 (каждая Routine) и 4 требуют подтверждения пользователя (один вопрос за
  сообщение, 2–4 варианта).

### Step 1. Intake

- Invoke: `goga-tool-pybuggy-web-automate-testcases-intake`
- Output: [TESTCASES_INTAKE]
- STOP if: requirements.md отсутствует или пуст; в §2 нет страниц; реестр REQ §3 пуст;
  базовые usages/annotations не резолвятся

### Step 2. Tools

- Invoke: `goga-tool-pybuggy-web-automate-testcases-tools`
- Reads: [TESTCASES_INTAKE]
- Output: [TOOLS_REPORT] + созданные usage-файлы `.goga/usages/cooks/<key>.md` (новые инструменты)
- WAIT: согласовать инструменты с пользователем (существующие usages / новые / отложить)
- STOP if: блокирующая потребность осталась без инструмента после согласования

### Step 3. Routines design

- Invoke: `goga-tool-pybuggy-web-automate-testcases-routines`
- Reads: [TESTCASES_INTAKE], [TOOLS_REPORT]
- Output: [ROUTINES_REPORT]
- WAIT: пользователь утверждает каждую Routine (правки при необходимости)

### Step 4. Cell map

- Invoke: `goga-tool-pybuggy-web-automate-testcases-cell-map`
- Reads: [ROUTINES_REPORT], [TESTCASES_INTAKE]
- Output: [CELL_MAP_REPORT]
- WAIT: утвердить раскладку с пользователем (готовый вариант / правки)
- STOP if: 0 клеток; рутина осталась нераспределённой; пользователь не утверждает

### Step 5. Assembly

- Invoke: `goga-tool-pybuggy-web-automate-testcases-assembly`
- Reads: [ROUTINES_REPORT], [CELL_MAP_REPORT], [TESTCASES_INTAKE] (базовый блок Header, §3)
- Output: [ASSEMBLY_REPORT] + `tests/web/<cell>/CODEMANIFEST` в целевом проекте
- STOP if: DSL-ошибка CODEMANIFEST; `goga lint` красный после материализации; REQ §3 остался
  без Routine

## Output Rule

Каждый суб-скилл ОБЯЗАН заполнить каждую секцию своего формата вывода.
Пустая секция = незавершённый суб-скилл = STOP пайплайна.

## Invariants

### NEVER

- писать тестовый код (pytest, playwright, фикстуры, `__init__.py`)
- вносить локаторы/селекторы/testid в аннотации рутин (`Prompt:`, предложения шагов, `Data:`) —
  адресация элементов идёт видимыми именами в предложениях шагов
- хранить REQ-идентификаторы в CODEMANIFEST
- писать предложения шагов где-либо, кроме `Steps:` рутин
- пропускать шаги пайплайна, обходить условие STOP или WAIT-gate
- оставлять секции вывода пустыми
- выдумывать данные или поведение — только факты из requirements.md и досье

### ALWAYS

- исполнять шаги по порядку
- покрывать каждый REQ §3 хотя бы одной Routine; параметризация — решение фазы routines design
  по критерию линейности (совпадающие шаги/проверки, разные данные)
- предлагать пользователю готовые решения на каждом WAIT; границы ячеек — дизайн-решение
- после материализации запускать `goga lint` и `goga schema tests/`
