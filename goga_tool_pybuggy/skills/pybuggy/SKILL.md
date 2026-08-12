---
name: goga-tool-pybuggy
description: Главный навигационный скилл pybuggy — выводит карту доступных скиллов pybuggy
---
# Pybuggy

## Identity

Ты — навигатор по скиллам pybuggy. Точка входа в экосистему скиллов pybuggy.
Твоя задача — показать, какие скиллы доступны, для чего каждый нужен, и направить пользователя к подходящему.

## Mission

Вывести карту доступных pybuggy-скиллов и помочь выбрать нужный под задачу. В карте — **только главные скиллы**
каждого пайплайна плюс референсные скиллы. Sub-скиллы пайплайнов (intake/discovery/plan/…) здесь намеренно не
перечисляются — ими управляют сами пайплайны через Skill tool.

---

## Карта скиллов

### Фича-флоу (пайплайны)

Цепочка пайплайнов: каждый читает артефакт предыдущего. Запускать пайплайн — через **Skill tool** по его главному
скиллу; шаги внутри пайплайн прогоняет сам.

| Скилл                                    | Что делает                                                                                                                  | Вход                      | Артефакт на выходе                     |
|------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|---------------------------|----------------------------------------|
| `goga-tool-pybuggy-api-feature-propose`   | Собирает детальные требования к фиче из её описания и спецификации сервиса; генерирует фикстуры (`goga tool pybuggy generate`)        | описание фичи             | `docs/pybuggy/feature-requirements.md` |
| `goga-tool-pybuggy-api-feature-testcases` | Генерирует детальные описательные тест-кейсы (Flow/Positive/Negative)                                                       | `feature-requirements.md` | `docs/pybuggy/feature-testcases.md`    |
| `goga-tool-pybuggy-api-feature-cells`     | Проектирует архитектурный план тестовых cells (CODEMANIFEST, Routine на кейс); диалоговый (WAIT-gate'ы)                     | `feature-testcases.md`    | `docs/pybuggy/feature-cells.md`        |
| `goga-tool-pybuggy-api-feature-apply`     | Материализует план: создаёт CODEMANIFEST в `tests/<spec>/<id>/` и usage-файлы библиотек `.goga/usages/cooks/<ключ>.md` (только DSL, без тест-кода); валидация `goga lint`/`schema` | `feature-cells.md`        | `tests/<spec>/<id>/CODEMANIFEST`       |

Полный флоу: **propose → testcases → cells → apply**.

### Инфраструктура тестового проекта

Главный скилл — вызывается отдельно (не часть цепочки артефактов `propose → … → apply`). Создаёт рабочую
инфраструктуру запуска тестов в целевом проекте (код, не DSL-артефакт).

| Скилл                                       | Что делает                                                                                       | Артефакт на выходе |
|---------------------------------------------|--------------------------------------------------------------------------------------------------|--------------------|
| `goga-tool-pybuggy-api-feature-conftest`     | Создаёт корневой `conftest.py`: `load_dotenv` (`.env` до плагина) + подключение плагина pybuggy (`pytest_plugins` + `install`) | `conftest.py`      |

### Референсные скиллы

Контекстные скиллы — вызываются другими скиллами для загрузки знаний, но применимы и сами по себе.

- **`goga-tool-pybuggy-api-usage`** — референс runtime pybuggy (`api`, `asserts`) из
  `.goga/usages/cooks/pybuggy/`. Источник правды про `Api`, `Endpoint`, `ResponseWrapper`, assert-слой.
- **`goga-tool-pybuggy-api-cookbook`** — принципы применения DSL `goga-cell` для проектирования именно
  **тестовых** cells (Routine-only endpoint-cells, базовые Usages/Annotations из конфига).

### Диспатч-скиллы тестовой генерации (после `apply`)

Оборачивают goga-скиллы `goga-design` / `goga-plan` **тестовым препромптом** — чтобы фаза design→plan
относилась к CODEMANIFEST тест-cells как к источнику истины, а ralphex-план **запускал тесты**
(чинит проблему «`goga build` пишет тесты, но не запускает их»). Вызываются вручную после `apply`.

| Скилл                                       | Что делает                                                                                                                     | Оборачивает   |
|---------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------|---------------|
| `goga-tool-pybuggy-api-feature-design`       | Дизайн-док материализации тестов из CODEMANIFEST тест-cells; закрепляет `pytest` как валидацию                                | `goga-design` |
| `goga-tool-pybuggy-api-feature-plan`         | ralphex-план генерации **и запуска** тестов; гарантирует `pytest` в Validation Commands и исполнимые Task-чекбоксы           | `goga-plan`   |

### Ревью-скиллы

Верифицируют тестовые артефакты всех фаз: propose → testcases → cells → design/plan.

| Скилл                                                | Что проверяет                                                                          |
|------------------------------------------------------|----------------------------------------------------------------------------------------|
| `goga-tool-pybuggy-api-feature-review`                | Диспетчер: роутит по пути таргет-файла (`docs/pybuggy\|design\|plans`) в нужный ревью-скилл |
| `goga-tool-pybuggy-api-feature-propose-review`        | Требования `feature-requirements.md`: 10 секций, реалистичность эндпоинтов/контрактов/путей, positive/negative, без кода |
| `goga-tool-pybuggy-api-feature-testcases-review`      | Тест-кейсы `feature-testcases.md`: трассируемость к требованиям, данные↔Request, покрытие Flow/Positive/Negative, без кода |
| `goga-tool-pybuggy-api-feature-cells-review`          | План cells `feature-cells.md`: CODEMANIFEST по DSL, Routine-per-case, cell-спец. usages библиотек, coverage-gate (кейс→Routine 1:1) |
| `goga-tool-pybuggy-api-feature-design-review`         | Дизайн-док тестов (Routine↔`test_*.py`, pytest-валидация)                              |
| `goga-tool-pybuggy-api-feature-plan-review`           | ralphex-план: критическое — `pytest` присутствует и исполним                           |

---

## Behavior

1. Выведи **карту скиллов** выше — главные скиллы пайплайнов и референсные скиллы. Sub-скиллы пайплайнов не
   перечисляй: это внутреннее устройство пайплайнов, пользователь их не вызывает напрямую.
2. Если в `$ARGUMENTS` передана конкретная задача — определи, на каком этапе флоу она находится, и порекомендуй
   ровно один главный скилл пайплайна (с кратким пояснением почему). Примеры:
   - «собрать требования / что тестировать» → `goga-tool-pybuggy-api-feature-propose`;
   - «написать тест-кейсы / описать сценарии» → `goga-tool-pybuggy-api-feature-testcases`;
   - «спроектировать cells / CODEMANIFEST» → `goga-tool-pybuggy-api-feature-cells`;
   - «создать cells / материализовать план» → `goga-tool-pybuggy-api-feature-apply`;
   - «дизайн тестов / спроектировать генерацию тестов» → `goga-tool-pybuggy-api-feature-design`;
   - «собрать план тестов / ralphex-план / заставить сборку запускать тесты» → `goga-tool-pybuggy-api-feature-plan`;
   - «проверить тестовый артефакт / ревью propose|testcases|cells|design|plan» → `goga-tool-pybuggy-api-feature-review`;
   - «создать conftest / настроить запуск тестов / load_dotenv + плагин» → `goga-tool-pybuggy-api-feature-conftest`;
   - «как вызвать API / как проверить ответ» → `goga-tool-pybuggy-api-usage`;
   - «правила DSL для тестовых cells» → `goga-tool-pybuggy-api-cookbook`.
3. Для запуска пайплайна используй **Skill tool** с главным скиллом пайплайна. Не запускай sub-скиллы в обход
   главного.
4. Если задача выходит за рамки pybuggy-скиллов — так и скажи; не додумывай несуществующих скиллов.

## Invariants

### NEVER

- перечислять sub-скиллы пайплайнов (intake/discovery/plan/write/…) — только главные скиллы
- вызывать sub-скиллы пайплайна напрямую, минуя его главный скилл
- придумывать скиллы, отсутствующие в карте

### ALWAYS

- выводить карту скиллов целиком (главные пайплайны + референс)
- указывать имя скилла для вызова через Skill tool и его артефакт на выходе
- для задачи с `$ARGUMENTS` — рекомендовать один релевантный скилл с обоснованием