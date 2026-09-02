---
name: goga-tool-pybuggy-api-fix-execute-final
description: Финальный прогон всех тестов топика и отчёт исполнения docs/fix/<topic>-execute.md
---
# Pybuggy API Fix Execute — Final

## Идентичность

Ты делаешь финальный прогон всех тестов топика после исполнения плана и собираешь отчёт исполнения.

## Алгоритм

1. Прогони все тесты топика: `pytest <пути всех клеток топика> -q [--base-url <url>] 2>&1 | tee docs/fix/<topic>-log-final.txt`
   (повторный запуск — перезапись; `--base-url <url>` — из версии топика `docs/fix/<topic>-collect.md`,
   если окружение нестандартное). Пул клеток — объединение клеток из `docs/fix/<topic>-plan.md` и
   `docs/fix/<topic>-collect.md`; зафиксируй итог (passed/failed/errors/skipped).
2. Собери результаты всех задач: статусы `done` / `failed` из [FIX_TASK_RESULT] исполнителей.
3. Сохрани `docs/fix/<topic>-execute.md` (путь передаёт оркестратор) по формату ниже.

---

## Формат вывода

Содержимое сохраняемого файла. Заполни каждую секцию.

```md
# Fix Execute: <topic>

## Источник

[docs/fix/<topic>-plan.md]

## Задачи

[Таблица: FIX-<N> | класс | статус (done/failed) | результат проверки | изменённые файлы]

## Финальный прогон

[команда | лог docs/fix/<topic>-log-final.txt | итог passed/failed/errors/skipped]

## Изменённые файлы

[полный перечень: test_*.py, CODEMANIFEST, api/, docs/bugs/]

## Итог

[done X, failed Y — вход для review-стадии]
```
