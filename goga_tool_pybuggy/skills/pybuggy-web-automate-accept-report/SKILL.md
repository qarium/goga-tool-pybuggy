---
name: goga-tool-pybuggy-web-automate-accept-report
description: Final acceptance report of the web topic's tests — synthesizes scope/consistency/run results into a verdict (ACCEPTED / ACCEPTED_WITH_NOTES / PARTIAL / REJECTED) with bug records and risks
---

# Pybuggy Web Topic Accept — Report

## Identity

Ты синтезируешь финальный отчёт приёмки из результатов шагов scope/consistency/run и выдаёшь вердикт.

## Algorithm

### Step 1. Collect the results

1. [ACCEPT_SCOPE] — объём приёмки (ячейки, Routine, тесты, кеши).
2. [ACCEPT_CONSISTENCY] — находки консистентности и применённые правки.
3. [ACCEPT_RUN] — результаты прогона, триаж, баг-рекорды, неразрешённые.

### Step 2. Determine the verdict

- **ACCEPTED** — все тесты топика прошли (или починены и перезапущены в зелёный); открытых багов
  сервиса нет; неразрешённых нет.
- **ACCEPTED_WITH_NOTES** — тесты в зелёном, но есть несущественные замечания (риски, догенерации
  кеша, найденные и исправленные дефекты тестов), либо баг-рекорды есть, но не блокируют
  подтверждённое поведение топика.
- **PARTIAL** — часть тестов не закрыта: неразрешённые падения, рутины переданы обратно в
  пайплайн testcases, но ядро топика подтверждено.
- **REJECTED** — прогон оказался невозможен (окружение не восстановлено) либо большинство тестов
  упало с багами сервиса, подтверждающими невыполнение требований топика.

### Step 3. Assemble the report

Собери [ACCEPT_REPORT]: сводка, объём, консистентность, прогон (таблица итогов), баг-рекорды,
открытые пункты, применённые изменения, риски (включая шаги без кеша и догенерации), вердикт.

- Отчёт остаётся в диалоге; персистентный след — баг-рекорды в
  `goga history path -f bugs.md` и правки тестов/кеша в репозитории.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [ACCEPT_REPORT]

## Summary

[Вердикт и его суть в 2–3 предложениях: что подтверждено, что нет]

## Scope

[Объём приёмки: ячейки, Routine, тесты, кеши шагов — из [ACCEPT_SCOPE]]

## Consistency

[Находки консистентности и применённые правки — из [ACCEPT_CONSISTENCY]]

## Test Run

[Команда прогона (strict) и таблица итогов: passed / fixed / bugs / unresolved — из [ACCEPT_RUN]]

## Bug Records

[Созданные/обновлённые рекорды BUG-<topic>-<N> с путями. Напиши `none`, если ничего]

## Open Items

[Неразрешённые тесты; рутины, переданные в пайплайн testcases; невосстановленное окружение.
Напиши `none`, если ничего]

## Applied Changes

[Правки test_*.py, регенерации кеша шагов (какие шаги, какими прогонами). Напиши `none`, если ничего]

## Risks

[Шаги без кеша/догенерированные; хрупкие предложения (нестабильные видимые имена/тексты); зависимость
от окружения (LLM-ключ, браузер по адресу Browser endpoint, доступность сайта). Напиши `none`, если ничего]

## Verdict

[ACCEPTED / ACCEPTED_WITH_NOTES / PARTIAL / REJECTED — с одной строкой обоснования]
```
