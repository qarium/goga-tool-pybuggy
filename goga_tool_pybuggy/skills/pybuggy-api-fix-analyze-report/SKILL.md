---
name: goga-tool-pybuggy-api-fix-analyze-report
description: Сборка артефакта анализа и сохранение в docs/fix/<feature>-analysis.md
---
# Pybuggy API Fix Analyze — Report

## Идентичность

Ты собираешь итоговый артефакт анализа и сохраняешь его на диск.

## Алгоритм

1. Собери входы: [FIX_EVIDENCE], [FIX_CLASSIFICATION].
2. Путь: `docs/fix/<feature>-analysis.md` (передаёт оркестратор).
3. Сохрани документ по формату ниже (повторный запуск — перезапись).

---

## Формат вывода

Содержимое сохраняемого файла. Заполни каждую секцию.

```md
# Fix Analysis: <feature>

## Источник
[путь к collect-репорту `docs/fix/<feature>-collect.md` и логу `docs/fix/<feature>-log.txt`]

## Классификация
[Таблица: тест | класс | основание | решение пользователя | план-направление]

## Распределение по классам
[Класс → количество]
```
