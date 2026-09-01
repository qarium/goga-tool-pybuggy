---
name: goga-tool-pybuggy-api-fix-analyze
description: Анализ причин падений — по каждому тесту причина и класс, интерактивно с пользователем
---

# Pybuggy API Fix — Analyze

## Identity

Ты — оркестратор анализа причин падений.

## Вход

`docs/fix/<topic>-collect.md` — репорт collect. `<topic>`: из `$ARGUMENTS`; Документ фиксируется на всю сессию и
передаётся в саб-скиллы.

## Pipeline

Шаги строго последовательно, по одному за раз. Вывод каждого шага валидируется до начала следующего.

### Step 1. Diagnose

- Скилл: `goga-tool-pybuggy-api-fix-analyze-diagnose`
- Читает: `docs/fix/<topic>-collect.md`
- Результат: [FIX_EVIDENCE] — по каждому падению досье, доказательства, гипотеза класса
- STOP: collect-репорт или лог недоступен; 0 падений в репорте — «падений нет», завершить пайплайн

### Step 2. Classify — WAIT

- Скилл: `goga-tool-pybuggy-api-fix-analyze-classify`
- Читает: [FIX_EVIDENCE]
- Результат: [FIX_CLASSIFICATION] — по каждому падению класс, основание, решение, план-направление
- WAIT: по каждому падению — вопрос пользователю
- STOP: пользователь прервал разбор

### Step 3. Report

- Скилл: `goga-tool-pybuggy-api-fix-analyze-report`
- Читает: [FIX_EVIDENCE], [FIX_CLASSIFICATION]
- Результат: [FIX_ANALYSIS] — сохранён в `docs/fix/<topic>-analysis.md`

## Правило вывода

Каждый саб-скилл заполняет все секции своего формата вывода. Пустая секция = незавершённый саб-скилл = STOP пайплайна.
