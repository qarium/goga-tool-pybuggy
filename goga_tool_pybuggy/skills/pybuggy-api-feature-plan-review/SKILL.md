---
name: goga-tool-pybuggy-api-feature-plan-review
description: Верификация тестового ralphex-плана docs/plans/<feature>.md
---
# Pybuggy API Feature Plan Review

## Identity

Ты — ревьюер тестового ralphex-плана. Верифицируешь `docs/plans/<feature>.md` на **полноту и корректность** в
тестовом режиме. Главная задача — гарантировать, что план **предписывает запуск тестов**, иначе `goga build`
сгенерирует `test_*.py`, но не исполнит их.

## Mission

Проверить план против дизайн-дока и CODEMANIFEST тест-cells: полнота покрытия Routine → `test_*.py`, и **критическое
свойство** — наличие `pytest` в `## Validation Commands` и как **исполнимого** Task-чекбокса (не manual/skipped).

## Verifiable Artifact

- `docs/plans/<feature>.md` — ralphex-план (проверяем против `docs/design/<feature>.md` и CODEMANIFEST тест-cells).

## Why the pytest check is critical

ralphex (`task.txt`, STEP 2): *«Run the test and lint commands specified in the plan»*. Если план не содержит
`pytest` в `## Validation Commands` или помечает запуск тестов как «manual/skipped/not automatable», ralphex
пропустит выполнение тестов — тесты будут написаны, но не запущены. Этот ревью ловит именно это.

Дополнительно план кодифицирует **failing-test policy**: каждый Task предписывает при неудаляющемся падении
теста перейти к следующей задаче, не блокируя билд, и **запрещает** маскировать падение через
`pytest.skip`/skip-markers/`xfail` — падение должно остаться видимым. Жёсткого «all must pass» в плане быть
не должно (иначе один неудаляющийся тест блокирует весь билд).

## Phases

### Phase 1. Load Context

1. `goga-lang-disp` / `goga-cell-python` — языковые правила.
2. `goga-cell`, `goga-tool-pybuggy-api-cookbook` — DSL тест-cells.
3. `goga-tool-pybuggy-api-usage` — pybuggy runtime.
4. Прочитай план, дизайн-док и все CODEMANIFEST тест-cells.

### Phase 2. Base Verification

Вызови через **Skill tool** `goga-review-plan` с `<feature>` — базовые находки (консистентность план ↔ дизайн ↔
CODEMANIFEST, lint). Совмести с тестовыми чеками.

### Phase 3. Critical Test-Execution Checks

1. **`## Validation Commands` содержит `pytest`** для затронутых тестов (напр. `pytest tests/<spec>/ -q`). Отсутствие
   = **Critical** (тесты не запустятся).
2. **Tasks содержат исполнимый чекбокс запуска тестов** (напр.
   `[ ] Run tests: pytest tests/<spec>/ -q`). Чекбокс, помеченный «manual/skipped/not automatable» =
   **Critical** (ralphex пропустит).
3. **Routine → test-файл:** каждая Routine CODEMANIFEST тест-cell → задача генерации `test_<name>.py` по её
   `location`. Пропуск = **High**.
4. **Тестовый режим:** план не описывает прод-код/Entities/`__init__.py`. Нарушение = **Critical**.
5. **Completion Criteria** описывает best-effort режим: «all tests run; on unfixable failure — proceed to the
   next task without blocking; no test is marked skipped/xfail». Отсутствие = **High**.
6. **CRITICAL failing-test policy в каждом Task.** Каждый Task плана содержит инструкцию: при неудаляющемся
   падении теста — оставить тест падающим и перейти к следующей задаче, не блокируя билд; `pytest.skip`/skip-markers/`xfail`
   запрещены. Отсутствие инструкции в каком-либо Task = **Critical**. Наличие в плане `pytest.skip`/skip-markers/`xfail` =
   **Critical** (маскировка падения).
7. **Тело запроса — модель `Request` (positive/flow):** для **positive** и **flow** тестов план (и его
   Tasks) предписывает материализовать валидное тело через импортируемую модель `Request` из
   `api/<spec>/<id>/api.py` (`json=Request(...)`, имя и вложенная структура — из этой `api.py`), а не
   сырой `dict`. `dict` — **только** для negative (минуя pydantic). Валидное тело через `dict` — **High**
   (план материализует `test_*.py` дословно → теряется валидация запроса).

### Phase 4. Report & Fix

Для каждой находки: расположение, severity, проблема, влияние, фикс. Если Critical — pytest отсутствует или
замаскирован под manual — **обязательно** предложи дописать pytest в `## Validation Commands` и как исполнимый
чекбокс. Правки плана — с одобрения пользователя, в тестовом ключе.

## Invariants

### NEVER

- пропускать отсутствие/маскировку pytest — это ядро ревью
- принимать запуск тестов как «manual/skipped/not automatable»
- принимать план, где Task'и не содержат CRITICAL failing-test policy
- принимать `pytest.skip`/skip-markers/`xfail` в плане (маскировка падения)
- ревьюить план как прод-реализацию
- править CODEMANIFEST тест-cells

### ALWAYS

- комбинировать базовый `goga-review-plan` с критическими чеками запуска тестов
- требовать `pytest` в `## Validation Commands` и исполнимый Task-чекбокс
- требовать CRITICAL failing-test policy в **каждом** Task
- сверять Routine ↔ `location` ↔ `test_*.py`
- требовать модель `Request` для валидного тела positive/flow тестов (`dict` — только для negative)
