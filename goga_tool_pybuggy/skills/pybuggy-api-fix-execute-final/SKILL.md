---
name: goga-tool-pybuggy-api-fix-execute-final
description: Финальный прогон всех тестов фичи и отчёт исполнения docs/fix/<feature>-execute.md
---
# Pybuggy API Fix Execute — Final

## Идентичность

Ты делаешь финальный прогон всех тестов фичи после исполнения плана и собираешь отчёт исполнения.

## Алгоритм

1. Прогони все тесты фичи: `pytest <пути всех клеток фичи> -q 2>&1 | tee docs/fix/<feature>-log-final.txt`
   (повторный запуск — перезапись). Пул клеток — объединение клеток из `docs/fix/<feature>-plan.md` и
   `docs/fix/<feature>-collect.md`; зафиксируй итог (passed/failed/errors/skipped).
2. Собери результаты всех задач: статусы `done` / `failed` из [FIX_TASK_RESULT] исполнителей.
3. Сохрани `docs/fix/<feature>-execute.md` (путь передаёт оркестратор) по формату ниже.

---

## Формат вывода

Содержимое сохраняемого файла. Заполни каждую секцию.

```md
# Fix Execute: <feature>

## Источник

[docs/fix/<feature>-plan.md]

## Задачи

[Таблица: FIX-<N> | класс | статус (done/failed) | результат проверки | изменённые файлы]

## Финальный прогон

[команда | лог docs/fix/<feature>-log-final.txt | итог passed/failed/errors/skipped]

## Изменённые файлы

[полный перечень: test_*.py, CODEMANIFEST, api/, docs/bugs/]

## Итог

[done X, failed Y — вход для review-стадии]
```
