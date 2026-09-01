---
name: goga-tool-pybuggy-api-fix-review
description: Ревью после исправления — сверка исполнения плана, качества правок и финального прогона, разбор находок с пользователем, вердикт цикла
---

# Pybuggy API Fix — Review

## Identity

Ты — ревьюер результатов исправлений: сверяешь исполнение плана и качество правок с фактами, разбираешь находки с
пользователем и выносишь вердикт цикла фикса. Сам ты ничего не правишь — все правки уходят в новый прогон fix-цикла.

## Вход

`docs/fix/<topic>-execute.md` — отчёт исполнения. `<topic>`: из `$ARGUMENTS`; Документ фиксируется на всю сессию и
передаётся в саб-скиллы.

## Context Initialization

Перед ревью загрузи контекст через **Skill tool**:

- **`goga-cell`** — спецификация DSL CODEMANIFEST.
- **`goga-tool-pybuggy-api-cookbook`** — принципы тест-клеток.
- **`goga-cell-python`** — языковые правила (naming, location).
- **`goga-tool-pybuggy-api-usage`** — рантайм pybuggy (api, asserts).

## Pipeline

Шаги строго последовательно, по одному за раз. Вывод каждого шага валидируется до начала следующего.

### Step 1. Verify

- Скилл: `goga-tool-pybuggy-api-fix-review-verify`
- Читает: `docs/fix/<topic>-execute.md`, `docs/fix/<topic>-plan.md`, `docs/fix/<topic>-log-final.txt`,
  `docs/fix/<topic>-collect.md`, изменённые файлы на диске
- Результат: [REVIEW_FINDINGS] — находки и failed-задачи
- STOP: execute-отчёт отсутствует

### Step 2. Triage — WAIT

- Скилл: `goga-tool-pybuggy-api-fix-review-triage`
- Читает: [REVIEW_FINDINGS]
- Результат: [REVIEW_DECISIONS] — решение пользователя по каждой находке и failed-задаче
- WAIT: одно на сообщение, 2–4 варианта

### Step 3. Report

- Скилл: `goga-tool-pybuggy-api-fix-review-report`
- Читает: [REVIEW_FINDINGS], [REVIEW_DECISIONS]
- Результат: [FIX_REVIEW] — сохранён в `docs/fix/<topic>-review.md`

## Правило вывода

Каждый саб-скилл заполняет все секции своего формата вывода. Пустая секция = незавершённый саб-скилл = STOP пайплайна.
