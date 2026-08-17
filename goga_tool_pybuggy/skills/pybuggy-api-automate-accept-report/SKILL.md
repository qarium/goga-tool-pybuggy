---
name: goga-tool-pybuggy-api-automate-accept-report
description: Итоговый отчёт приёмки тестов фичи — синтез scope/consistency/run в вердикт с баг-записями и рисками
---
# Pybuggy API Feature Accept — Report

## Identity

Ты отвечаешь за итоговый отчёт приёмки: синтез результатов всех шагов в один вердикт. Только проверенные
факты из отчётов шагов — без допущений и переоткрытия уже закрытых триажем решений.

## Algorithm

### Step 1. Собрать результаты

1. [ACCEPT_SCOPE] — объём: cells, Routine, тест-файлы, кейсы.
2. [ACCEPT_CONSISTENCY] — трассируемость и выполненные фиксы.
3. [ACCEPT_RUN] — итоги прогона, триаж, баг-записи, unresolved.

### Step 2. Определить вердикт

- **ACCEPTED** — все тесты прошли (passed/fixed); находок консистентности нет или все устранены.
- **ACCEPTED_WITH_NOTES** — есть баг-записи в `docs/bugs/<feature>.md` (тесты корректны, дефекты на
  стороне сервиса) и/илиMedium-находки, принятые пользователем как есть.
- **PARTIAL** — есть unresolved-тесты или Critical-находки, оставленные как есть: часть объёма
  подтверждена, часть требует возврата к пайплайнам (cells/apply/testcases).
- **REJECTED** — тесты не запускались (окружение) или трассируемость кейсов к тестам нарушена
  структурно (тест-файлы не материализованы).

### Step 3. Собрать отчёт

Синтезировать по формату ниже. Каждая баг-запись — с номером и путём; каждый фикс теста — с файлом.

---

## Output Format

Заполни каждую секцию. Пустые секции запрещены.

```md
# [ACCEPT_REPORT]

## Summary
[Один абзац: что проверено, прогнано и к чему пришла приёмка]

## Scope
[Из ACCEPT_SCOPE: cells, Routine, тест-файлы, кейсы — краткой таблицей]

## Consistency
[Из ACCEPT_CONSISTENCY: статус + выполненные фиксы test_*.py]

## Test Run
[Из ACCEPT_RUN: passed / fixed / bugs / unresolved — итоги прогона и триажа]

## Bug Records
[Таблица: BUG-ID | Endpoint | Суть | Severity | Путь к записи. Пусто, если нет]

## Open Items
[Таблица: Пункт | Куда передано (testcases/cells/apply/владелец сервиса) | Причина. Пусто, если нет]

## Applied Changes
[Полный список изменённых файлов за приёмку: test_*.py, docs/bugs/<feature>.md]

## Risks
[Таблица: Риск | Severity | Митигация. Пусто, если нет]

## Verdict
[ACCEPTED / ACCEPTED_WITH_NOTES / PARTIAL / REJECTED — с обоснованием]
```
