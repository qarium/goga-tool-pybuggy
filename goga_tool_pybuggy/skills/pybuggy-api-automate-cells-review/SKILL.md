---
name: goga-tool-pybuggy-api-automate-cells-review
description: Верификация архитектурного плана тестовых cells docs/pybuggy/feature-cells.md — CODEMANIFEST по goga-cell DSL, Routine под кейсы (endpoint-cells; 1 кейс = 1 Routine не обязательно), без Entities, базовые Usages/Annotations, cell-спец. usages библиотек, строгая структура аннотаций, coverage (кейс покрыт напрямую или вариантом Routine), семантическая достаточность аннотаций для генерации теста
---
# Pybuggy API Feature Cells Review

## Identity

Ты — ревьюер архитектурного плана тестовых cells. Верифицируешь `docs/pybuggy/feature-cells.md` —
выход пайплайна `goga-tool-pybuggy-api-automate-cells`. План содержит только DSL-артефакты CODEMANIFEST:
на каждую cell эндпоинта — Header (базовые `Usages`/`Annotations`) + Body (`Routine` под
тест-кейсы — один Routine может покрывать несколько кейсов) + Footer. Endpoint-cells — Routine-only листья, поэтому размерности
графа типов, mutations, embeddings и кросс-cell связности здесь структурно неприменимы — ревью
фокусируется на DSL-валидности, тест-конформности, coverage и достаточности аннотаций.

## Mission

Независимо проверить план: каждая CODEMANIFEST корректна по `goga-cell` DSL; тесты описаны **только**
как `Routine` (без `Entity`/`methods`/`properties`); базовые `Usages`/
`Annotations` на месте и идентичны в endpoint-cells (поверх базового блока допустимы cell-спец. usages
библиотек); аннотации Routine следуют строгой структуре; **каждый тест-кейс покрыт** (напрямую или как вариант/параметр Routine).
Найти расхождения, сообщить, исправить (с одобрения пользователя).

## Relationship to other skills

- **`goga-tool-pybuggy-api-automate-cells-plan-verification`** — встроенный gate пайплайна (проверяет
  DSL + coverage по ходу сборки). Этот ревью — **независимая** проверка готового артефакта, которую
  можно запустить в любой момент; он не зависит от состояния пайплайна.

## Verifiable Artifact

- `docs/pybuggy/feature-cells.md` — архитектурный план тестовых cells.
- **Upstream** (для coverage и контекста): `docs/pybuggy/feature-testcases.md` (эталонный набор
  кейсов), `docs/pybuggy/feature-requirements.md` (контекст фичи).

---

## Phases

### Phase 1. Load Context

1. Прочитай `docs/pybuggy/feature-cells.md`. Если отсутствует — остановись и сообщи пользователю.
2. Прочитай upstream `feature-testcases.md` (эталон кейсов для coverage) и `feature-requirements.md`
   (контекст). Если `feature-testcases.md` отсутствует — находка **Critical** (coverage неоткуда
   сверять).
3. Загрузи DSL-спецификацию и принципы через **Skill tool**:
   - `goga-cell` — правила CODEMANIFEST (структура, сигнатуры, Usages/Annotations, типы, constraints);
   - `goga-tool-pybuggy-api-cookbook` — принципы тестовых cells (Routine под кейсы — гранулярность произвольная, строгий порядок
     аннотаций Purpose → `Precondition:` → `Data:` → `Steps:` → `Use …`);
   - `goga-cell-python` — языковые правила (naming `snake_case`, `location: test_<name>.py`);
   - `goga-codemanifest-base` — базовые `Usages`/`Annotations` из `.goga/config.yml` (эталон Header);
   - `goga-tool-pybuggy-api-usage` — референс pybuggy (`Endpoint`, фикстура `<method>_<id>`).
4. Построй эталонный набор кейсов из `feature-testcases.md`: `id | тип | endpoint-id` — для
   coverage в Phase 5.

> DSL валидируй вручную по `goga-cell`. `goga lint`/`goga schema` используй только как
> дополнительную кросс-проверку: известны артефакты тулинга с ложными path-ошибками — не считай их
> дефектами без ручного подтверждения.

---

### Phase 2. Plan Structure and No-Code

1. **Обязательные секции плана** присутствуют и заполнены (без плейсхолдеров TBD/TODO/«…»):
   `Тема`, `Контекст`, `Implementation Order`, `Artifacts`, `Coverage Map`,
   `Verification Checklist`. Отсутствующая секция — **Critical**; пустая/плейсхолдер — **High**.
2. **Только DSL, без кода** — план содержит только артефакты CODEMANIFEST; любой код реализации
   (python/импорт/`def`/`class`) — **Critical**.
3. **Implementation Order** перечисляет все endpoint-cells `tests/<spec>/<id>/` — с rationale («лист, тесты
   эндпоинта»). Пропущенная cell или отсутствие rationale — **Medium** (пропущенная cell — **High**).

---

### Phase 3. CODEMANIFEST Validity per Cell

Для **каждой** endpoint-cell из `Artifacts`:

1. **Структура** — `Header → --- → Body → --- → Footer`; case-sensitive ключи. Нарушение — **Critical**.
2. **Header — базовый блок** — `Usages` (`conventions`, `pybuggy-api`, `pybuggy-asserts`) +
   `Annotations` из конфига (через `goga-codemanifest-base`), перенесённые as-is. Поверх базового блока
   endpoint-cell может иметь **cell-специфичные usages** библиотек (`<ключ>: .goga/usages/cooks/<ключ>.md`;
   backtick `` `<ключ>` `` должен разрешаться в контексте cell). Отсутствие базового usage/annotation — **High**;
   искажение базового текста — **High**.
3. **Базовый блок идентичен во всех endpoint-cells** — **базовые** `Usages`/`Annotations` совпадают дословно.
   Поверх базового блока допустимы cell-специфичные usages библиотек (из [LIBS_REPORT]) — эти отличия нормальны,
   **не** расхождение. Расхождение **базового** блока между endpoint-cells — **High**.
4. **Body — только Routine** — нет `Entity`, нет `methods`/`properties`. Наличие `Entity` или
   `methods`/`properties` — **Critical**.
5. **Сигнатура Routine** — `test_<name>(<fixture>: Endpoint)` **без output**. Отклонение формата — **High**;
   наличие output у теста — **Critical**.
6. **`location`** — `test_<name>.py` без подъёма/спуска по директориям (`../`, `…/`). Нарушение — **High**.
7. **Footer** — `Author: Goga`, `CreatedAt` (день/месяц/год), `Description` (зачем cell). Отсутствие —
   **Medium**; `Author` не `Goga` — **Medium**.

---

### Phase 4. Routine Annotation Structure

Для **каждой** Routine (по `goga-tool-pybuggy-api-cookbook`):

1. **Строгий порядок разделов** — `Purpose` (без лейбла, первый абзац) → `Precondition:` →
   (`Data:`) → `Steps:` → `Use …`. Разделы **разделяются пустой строкой** (после Purpose и перед каждым из
   `Precondition:` / `Data:` / `Steps:` / `Use …`). Нарушение порядка, отсутствие пустой строки между
   разделами или пропуск обязательного раздела — **High**.
2. **`Precondition:`** — маркированный список; на каждую параметр-фикстуру — `` `<fixture>`: `` с
   описанием сгенерированной фикстуры (`api/<spec>/<id>/api.py`, имя `<method>_<id>`, METHOD /path,
   роль — основной SUT / верификация), плюс общие предусловия (тип `Endpoint` из runtime pybuggy,
   состояние/данные ДО теста). Размытое/отсутствующее описание фикстуры — **High**.
3. **`Data:`** — внутренние данные теста (переменные, ключи, `test_id`) ИЛИ секция опущена, если их
   нет. Значения вызовов (`request`/`response`) здесь не дублируются. Некорректное содержание —
   **Medium**.
4. **`Steps:`** — пронумерованные шаги из кейса (Действие / Данные / Ожидание), выраженные через
   ссылки на Usages и фикстуру; **логика, не pytest-код**. Код в шагах — **Critical**; пропуск шагов
   кейса — **High**.
5. **Тело запроса — модель `Request` (positive/flow):** для **positive** и **flow** Routine валидное
   тело запроса в **`Steps`** описано через импортируемую модель `Request` из `api/<spec>/<id>/api.py`
   (`json=Request(...)`, имя и вложенная структура — из этой `api.py`), а **не** сырой `dict`. `dict`
   допустим **только** для negative-вариантов (нет обязательного поля / неверный тип / пустое тело /
   битый JSON) с явной пометкой «минуя pydantic-модель». Валидное тело через `dict` (`{field: value}`)
   — **High** (Steps материализуются в `test_*.py` дословно → теряется валидация запроса).
6. **`Use …` — без дублирования заголовка.** В Routine перечислены **только** usages, специфичные для
   неё (cell-спец usages библиотек). Базовые `pybuggy-api`/`pybuggy-asserts`/`conventions` уже в глобальных
   `Annotations` заголовка — их **дублирование** в Routine = **Medium** (по `goga-cell`: аннотации разных
   уровней не дублируют друг друга).
7. **Backtick-ссылки разрешаются** в контексте CODEMANIFEST: `` `<fixture> ``, `` `pybuggy-api` ``,
   `` `pybuggy-asserts` ``, `` `conventions` ``. Неразрешимая ссылка — **High**.

---

### Phase 5. Coverage (Покрытие и трассируемость)

**Цель:** каждый кейс из `feature-testcases.md` отражён в плане — покрыт напрямую или как вариант/параметр Routine; нет потерь и нет висячих Routine.

1. **Кейс покрыт** — каждый кейс эталона отражён в плане: напрямую или как вариант/параметр некоторого
   Routine (один Routine может покрывать несколько кейсов). Потерянный кейс — **Critical**.
2. **Нет висячих Routine** — каждый Routine восходит хотя бы к одному кейсу; Routine без кейса — **High**.
3. **Имена Routine уникальны в пределах cell** — дубль имени — **High**.
4. **Гранулярность cell** — одна endpoint-cell на эндпоинт (`tests/<spec>/<endpoint-id>/`). Несколько
   эндпоинтов в одной cell или дробление одного эндпоинта — **High**.
5. **Coverage Map** — таблица `кейс (id, тип) | Routine | cell` полна и согласована с фактическим
   содержанием плана (каждая строка подтверждается реальным Routine в реальной cell; один Routine может
   встречаться в нескольких строках — это норма). Расхождение — **High**.
6. **cell ↔ фикстура ↔ эндпоинт** — путь endpoint-cell `tests/<spec>/<endpoint-id>/`, имя фикстуры
   `<method>_<id>` и эндпоинт кейса согласованы. Несоответствие — **High**.
7. **Cell-спец usages библиотек ↔ §10** — для каждой библиотеки из §10 `feature-requirements.md` с
   непустой привязкой «где используется»: cell-спец usage `<ключ>: .goga/usages/cooks/<ключ>.md`
   присутствует в каждой endpoint-cell, к которой библиотека привязана; обратно — каждый cell-спец usage
   библиотеки восходит к §10. Phantom-lib (cell-спец usage без §10) — **High**; отсутствие cell-спец
   usage у привязанной библиотеки — **High**. Если §10 отмечена «нет» — cell-спец usages библиотек в
   плане быть не должно (наличие — **High**).

---

### Phase 6. Semantic Sufficiency

Проверить **точность контракта и достаточность аннотаций** каждой Routine (размерности графа типов /
mutations / embeddings / кросс-cell связности — N/A для Routine-only листьев; фиксируй это
явно, а не как пропуски):

1. **Достаточность для генерации** — аннотация Routine даёт достаточно, чтобы реализовать
   `test_<name>.py` без додумывания (предусловия конкретны, данные из модели `Request`, ожидания
   доскональны — статус + поля/структура). Недостаточная аннотация — **Critical**.
2. **Точность сигнатуры** — имя `test_<name>` осмысленно и отражает проверку; `<fixture>` соответствует
   сгенерированной фикстуре эндпоинта. Размытое имя / несоответствие фикстуры — **Medium**/**High**.
3. **Трассируемость к требованиям** — Routine-проверки согласуются с ожиданиями кейса и контрактами
   ответов из `feature-testcases.md`/`feature-requirements.md`. Контрактное противоречие — **High**.
4. **Edge-кейсы** — для negative-Routine описана именно корректная failure-модель (ожидаемая ошибка
   4xx/5xx из schemas). Неверный failure-путь — **High**.

---

### Phase 7. Report and Fix Findings (Interactive)

Собери все находки из Phases 2–6 **до** предъявления. Отсортируй: **Critical → High → Medium**.

Предъявляй находки **по одной**. Для каждой:

#### Step 1. Покажи находку

- **Severity** (Critical / High / Medium)
- **Area** (Plan / CODEMANIFEST / Annotation / Coverage / Semantics)
- **Location** — cell (`tests/<spec>/<id>/`), Routine, раздел аннотации, секция плана
- **Issue** — чёткое описание
- **Evidence** — чем подтверждена (`goga-cell` правило, эталон кейсов, Coverage Map, базовый блок)
- **Suggested fix** — конкретное DSL-изменение, не общий совет

#### Step 2. Запроси решение (AskUserQuestion)

1. **Apply suggested fix** — применить сейчас
2. **Propose alternative** — иной вариант
3. **Skip** — пропустить

#### Step 3. Примени решение

- **Apply**: обнови `feature-cells.md`, затем переверь, что фикс не внёс новых проблем (re-run
  релевантных чеков, включая coverage и идентичность базового блока). Кратко доложи результат.
- **Skip**: пометь как «skipped» и продолжай.
- **Propose alternative**: обсуди, согласуй, примени, переверь.

#### Step 4. Следующая находка

Повторяй от Step 1. Показывай счётчик: «Finding 3 of 12».

После всех находок — сводка:
- **Fixed**: N (по severity и area)
- **Skipped**: N (по severity и area)
- **Artifact status**: updated / unchanged

> **Правка правки:** правь только DSL-артефакты CODEMANIFEST в `feature-cells.md`. Не добавляй новые
> кейсы/требования, не правь upstream `feature-testcases.md`/`feature-requirements.md`, не трогай
> `api.py`/`schemas`/`tests/`. Если кейс потерян — это либо ошибка плана (дописать Routine), либо
> сигнал перезапустить пайплайн `cells`.

---

## Invariants

### NEVER

- ревьюить план как прод-архитектуру (Entity/граф типов) — только тестовые cells
- принимать `Entity`/`methods`/`properties`/output в Routine — это инвариант тестовых cells
- править upstream-артефакты или сгенерированные фикстуры/схемы
- считать находкой N/A-размерности (граф типов, mutations, embeddings) для Routine-only листьев —
  отмечай как структурно неприменимые

### ALWAYS

- валидировать каждую CODEMANIFEST по `goga-cell` DSL вручную (с опциональной кросс-проверкой
  `goga lint`, не принимая ложные path-ошибки за дефекты)
- сверять coverage: каждый кейс покрыт (напрямую/вариантом Routine), без потерь и висячих Routine
- требовать строгий порядок аннотаций и идентичный **базовый** блок во всех cells (поверх допустимы
  cell-спец. usages библиотек — `goga-tool-pybuggy-api-cookbook`, раздел «Cell-специфичные usages»)
- требовать модель `Request` для валидного тела positive/flow Routine (`dict` — только для negative,
  минуя pydantic) — Steps материализуются в `test_*.py` дословно
- предъявлять каждую находку по одной с выбором Apply/Alternative/Skip

---

## Final Self-Check

Перед завершением проверь:

1. Прочитан ли `feature-cells.md` и upstream `feature-testcases.md` (+ `feature-requirements.md`)?
2. Загружены ли `goga-cell`, `goga-tool-pybuggy-api-cookbook`, `goga-cell-python`,
   `goga-codemanifest-base`, `goga-tool-pybuggy-api-usage`?
3. Проверена ли структура плана (все секции, отсутствие кода)?
4. Проверена ли каждая CODEMANIFEST (структура, базовый Header, идентичность **базового** блока в
   endpoint-cells + допустимые cell-спец. usages библиотек, Routine-only, сигнатура, location, Footer)?
5. Проверена ли структура аннотаций каждой Routine (строгий порядок, фикстура, Steps, Use,
   backtick-ссылки)?
6. Пройдена ли coverage-проверка (все кейсы покрыты напрямую или вариантом Routine, уникальность имён, cell↔фикстура↔эндпоинт, Coverage
   Map, cell-спец usages библиотек согласованы с §10)?
7. Проверена ли семантическая достаточность (достаточность для генерации, точность, трассируемость,
   failure-модель negative)?
8. Предъявлена ли каждая находка по одной с выбором Apply/Alternative/Skip?
9. Применены ли одобренные фиксы с перепроверкой (coverage + базовый блок)?

Если хотя бы один ответ «нет» — заверши недоделанную проверку перед возвратом.
