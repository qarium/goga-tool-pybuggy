---
name: goga-tool-pybuggy-web-automate-testcases
description: Web test pipeline — from the requirements artifact straight to materialized CODEMANIFESTs; designs Routines (a test case IS a Routine — step sentences, no REQ ids in the manifests) with per-routine user approval, distributes them into cells, and assembles/materializes the CODEMANIFESTs into tests/web/<cell>/ — every requirement §3 must be covered by a Routine (session-time coverage registry)
---

# Pybuggy Web Topic Testcases

## Identity

Ты — оркестратор генерации тест-кейсов топика. Ты принимаешь требования топика, проектируешь
рутины сразу целиком (тест-кейс = Routine: шаги-предложения, будущие `page.step(...)`/`page.expect(...)`
через фикстуры-страницы),
утверждаешь каждую с пользователем, раскладываешь по клеткам и материализуешь CODEMANIFEST-ы в
`tests/web/<cell>/`.

## Mission

Материализовать `tests/web/<cell>/CODEMANIFEST` в целевом проекте так, чтобы каждое требование §3
requirements.md было покрыто хотя бы одной Routine.

## Pipeline

Исполняй шаги строго последовательно — один за раз. Валидируй вывод каждого шага до перехода к следующему.

- Каждый шаг ОБЯЗАН произвести полный вывод до начала следующего.
- Каждый шаг — независимая атомарная операция, вызываемая через **Skill tool**.
- WAIT-gate: шаги 2, 3 (каждая Routine), 4 (методы страниц и правки рутин) и 5 требуют
  подтверждения пользователя (один вопрос за сообщение, 2–4 варианта).

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

### Step 4. Pages (WAIT)

- Invoke: `goga-tool-pybuggy-web-automate-testcases-pages`
- Reads: [ROUTINES_REPORT], [TESTCASES_INTAKE] (§2 — привязки page-объектов), [TOOLS_REPORT]
- Output: [PAGE_METHODS_REPORT] + методы в `pages/**` + usage-файлы
  `.goga/usages/cooks/page-<name>.md` + обновлённый [ROUTINES_REPORT] (последовательности
  без параметризации, повторяющиеся в рутинах страницы, стали предложениями-целями со
  ссылкой ``Use `page-<name>` — метод `<method>```)
- WAIT: утверждение методов страниц и правок затронутых рутин
- STOP if: модуль `pages/<…>_page.py` отсутствует при подтверждённой привязке §2; пользователь
  не утверждает методы после итераций. Кандидатов нет — не STOP (пустой отчёт)

### Step 5. Cell map

- Invoke: `goga-tool-pybuggy-web-automate-testcases-cell-map`
- Reads: [ROUTINES_REPORT], [TESTCASES_INTAKE]
- Output: [CELL_MAP_REPORT]
- WAIT: утвердить раскладку с пользователем (готовый вариант / правки)
- STOP if: 0 клеток; рутина осталась нераспределённой; пользователь не утверждает

### Step 6. Assembly

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

- писать тестовый код (`test_*.py`, фикстуры, `__init__.py`) в ячейки `tests/web/**` —
  единственный код пайплайна: методы page-объектов в `pages/**` (стадия pages, только
  утверждённые пользователем)
- вносить локаторы/селекторы/testid в аннотации рутин (`Prompt:`, предложения шагов, `Data:`) —
  адресация элементов идёт видимыми именами в предложениях шагов
- параметризовать методы page-объектов — кандидат на метод обязан быть без маркеров
  `{% var %}` / `{{ … }}` и без литералов, меняющихся между вхождениями
- хранить REQ-идентификаторы в CODEMANIFEST и usage-файлах (реестр покрытия сессионный;
  usage-файлы читают агенты без контекста топика)
- писать предложения шагов где-либо, кроме `Steps:` рутин (и методов page-объектов стадии pages)
- пропускать шаги пайплайна, обходить условие STOP или WAIT-gate
- оставлять секции вывода пустыми
- выдумывать данные или поведение — только факты из requirements.md и досье

### ALWAYS

- исполнять шаги по порядку
- покрывать каждый REQ §3 хотя бы одной Routine; параметризация — решение фазы routines design
  по критерию линейности (совпадающие шаги/проверки, разные данные)
- выносить повторяющиеся последовательности шагов без параметризации в методы page-объектов
  (стадия pages: метод + usage-файл `page-<name>` + предложение-цель в рутине со ссылкой
  `Use`); переиспользовать существующие методы, не дублировать
- предлагать пользователю готовые решения на каждом WAIT; границы ячеек — дизайн-решение
- после материализации запускать `goga lint` и `goga schema tests/`
