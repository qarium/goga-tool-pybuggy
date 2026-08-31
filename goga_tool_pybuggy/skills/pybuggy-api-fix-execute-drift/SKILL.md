---
name: goga-tool-pybuggy-api-fix-execute-drift
description: Исполнение задачи класса spec-drift — приведение клетки под новую спеку
---
# Pybuggy API Fix Execute — Drift

## Идентичность

Ты исполняешь одну задачу класса `spec-drift`: приводишь клетку под новую спеку по шагам, конкретизированным в задаче плана.

## Алгоритм

1. Возьми задачу `FIX-<N>` (класс `spec-drift`) из плана: эндпоинты, клетка, тесты и изменения уже прописаны в задаче.
2. Выполни шаги задачи по порядку:
   1. артефакты: `goga tool pybuggy endpoint pull`; `goga tool pybuggy endpoint generate <endpoint-id> [...] -f`;
   2. Routine: обнови затронутые секции аннотаций в CODEMANIFEST клетки;
   3. тесты: правь `test_<name>.py` под новые аннотации.
3. Прогони проверки задачи:
   - `goga tool pybuggy endpoint diff <endpoint-id> [...]` — пустой;
   - `goga lint` клетки;
   - `pytest tests/<spec>/<id>/ -q` — зелёный.
4. `done` — только если пройдены все три проверки.
5. Сформируй [FIX_TASK_RESULT].

---

## Формат вывода

Заполни каждую секцию. Пустые секции запрещены.

```md
# [FIX_TASK_RESULT]

## Задача
[FIX-<N>, класс `spec-drift`, клетка + эндпоинты]

## Статус
[done — все проверки пройдены / failed — какая проверка и почему]

## Результат проверки
[diff-итог + lint-итог + команда pytest и итог]

## Изменённые файлы
[api.py, schemas, CODEMANIFEST, test_*.py — по факту правок]

## Замечания
[что осталось нездоровым. Пусто, если ничего]
```
