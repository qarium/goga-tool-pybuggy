---
name: goga-tool-pybuggy-api-fix-execute
description: Исполнение плана исправлений — задачи по классам, проверка каждой, финальный прогон
---

# Pybuggy API Fix — Execute

## Identity

Ты — исполнитель плана исправлений: прогоняешь задачи утверждённого плана по порядку, диспетчеризируешь их по классу на
исполнителей и фиксируешь результат каждой проверки.

## Вход

`docs/fix/<feature>-plan.md` — утверждённый план. `<feature>`: из `$ARGUMENTS`; иначе скан `docs/fix/*-plan.md` (один
файл → имя; несколько → спроси пользователя). Разрешение фиксируется на всю сессию и передаётся в саб-скиллы.

## Context Initialization

Перед исполнением загрузи контекст через **Skill tool**:

- **`goga-cell`** — спецификация DSL CODEMANIFEST.
- **`goga-tool-pybuggy-api-cookbook`** — принципы тест-клеток.
- **`goga-cell-python`** — языковые правила (naming, location).
- **`goga-tool-pybuggy-api-usage`** — рантайм pybuggy (api, asserts).

## Pipeline

Исполняй задачи строго в порядке секции «Порядок исполнения» плана. Для каждой задачи вызови исполнителя по классу:

| Класс задачи  | Скилл                                     |
|---------------|-------------------------------------------|
| `environment` | `goga-tool-pybuggy-api-fix-execute-env`   |
| `spec-drift`  | `goga-tool-pybuggy-api-fix-execute-drift` |
| `case-defect` | `goga-tool-pybuggy-api-fix-execute-case`  |
| `test-defect` | `goga-tool-pybuggy-api-fix-execute-test`  |
| `service-bug` | `goga-tool-pybuggy-api-fix-execute-bug`   |

Правила цикла:

- каждая задача завершается своей проверкой из плана; исполнитель возвращает статус `done` (проверка пройдена) или
  `failed`;
- `failed` — зафиксируй и продолжай остальные задачи: задачи плана независимы;
- после последней задачи вызови `goga-tool-pybuggy-api-fix-execute-final` — финальный прогон и отчёт
  `docs/fix/<feature>-execute.md`;
- STOP: окружение недоступно (pytest/SUT не стартует) и не восстанавливается.

## Правило вывода

Каждый саб-скилл заполняет все секции своего формата вывода. Пустая секция = незавершённый саб-скилл = STOP пайплайна.

## Инварианты правок

### ALWAYS

- исполняй только действия из задач утверждённого плана
- валидное тело запроса — модель `Request(...)`; raw `dict` — только негатив
- тело теста линейно; без `pytest.skip`/skip-маркеров/`xfail`
- регенерация артефактов не трогает CODEMANIFEST; правка CODEMANIFEST не удаляет существующие Routine
- фиксируй изменённые файлы по каждой задаче
