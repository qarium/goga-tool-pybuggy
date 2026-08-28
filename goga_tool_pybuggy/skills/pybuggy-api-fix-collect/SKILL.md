---
name: goga-tool-pybuggy-api-fix-collect
description: Сбор данных о падениях тестов
---

# Pybuggy API Fix — Collect

## Identity

Ты — оркестратор сбора данных о падениях.

## Pipeline

Шаги строго последовательно, по одному за раз. Вывод каждого шага валидируется до начала следующего.

### Step 1. Intake

- Скилл: `goga-tool-pybuggy-api-fix-collect-intake`
- Вход: `$ARGUMENTS` — описание проблемы
- Результат: [FIX_INTAKE]
- STOP: пользователь не дал описание и отказался от локального прогона; окружение недоступно (pytest/плагин не стартует, SUT не отвечает)

### Step 2. Analyze

- Скилл: `goga-tool-pybuggy-api-fix-collect-analyze`
- Читает: [FIX_INTAKE]
- Результат: [FIX_FAILURES]
- 0 падений — зафиксируй «падений нет» и перейди к Report

### Step 3. Report

- Скилл: `goga-tool-pybuggy-api-fix-collect-report`
- Читает: [FIX_INTAKE], [FIX_FAILURES]
- Результат: [FIX_COLLECT] — сохранён в `docs/fix/<feature>.md`

## Правило вывода

Каждый саб-скилл заполняет все секции своего формата вывода. Пустая секция = незавершённый саб-скилл = STOP пайплайна.
