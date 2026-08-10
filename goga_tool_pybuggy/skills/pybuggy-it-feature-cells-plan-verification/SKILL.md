---
name: goga-tool-pybuggy-it-feature-cells-plan-verification
description: Финальная верификация плана тестовых cells против DSL и покрытия кейсов
---

## Identity

Ты отвечаешь за финальную верификацию плана: проверяешь, что каждая CODEMANIFEST в `docs/pybuggy/feature-cells.md`
корректна по `goga-cell` DSL, все тест-кейсы покрыты Routine, а базовые Usages/Annotations на месте. Решение
утверждается пользователем.

## Core Principle

Ты **независимо проверяешь** план против `goga-cell` DSL и входных тест-кейсов, **исправляешь** найденные
несоответствия и **получаешь финальное approval** пользователя на план.

---

## Algorithm

### Step 1. Загрузить контекст

1. `docs/pybuggy/feature-cells.md` — проверяемый план.
2. [CELLS_INTAKE] — эталонный набор кейсов для coverage.
3. `goga-cell` / `goga-cell-python` — правила валидации.

### Step 2. DSL-валидация каждой CODEMANIFEST

По `goga-cell` проверить для каждой cell:

1. Структура: Header → `---` → Body → `---` → Footer; case-sensitive ключи.
2. Header (endpoint-cell): базовый блок `Usages` (`conventions`, `pybuggy-api`, `pybuggy-asserts`) +
   `Annotations` из конфига; поверх него допустимы **cell-специфичные usages** библиотек
   (`<ключ>: .goga/usages/cooks/<ключ>.md` — материализуются `apply`; backtick `` `<ключ>` `` разрешается в
   контексте cell).
3. Body: Routine без `methods`/`properties`; сигнатура `test_<name>(<fixture>: Endpoint)` без output,
   `location: test_<name>.py`.
4. Backtick-ссылки разрешаются в контексте CODEMANIFEST.
5. Footer: `Author: Goga`, `CreatedAt`, `Description`.

### Step 3. Coverage-проверка

Сравнить Routine в плане с кейсами из [CELLS_INTAKE]:

1. Каждый кейс → ровно один Routine.
2. Нет потерянных и нет «лишних» Routine без кейса.
3. Имена Routine уникальны в пределах cell.

### Step 4. Базовый блок

Убедиться, что **базовые** `Usages`/`Annotations` присутствуют и идентичны во всех endpoint-cells (из конфига).
Поверх базового блока допустимы **cell-специфичные usages** библиотек (из [LIBS_REPORT]) — их наличие в одних
cell и отсутствие в других **не** расхождение.

### Step 5. Исправить несоответствия

Исправить найденные ошибки напрямую в `docs/pybuggy/feature-cells.md` (только DSL-артефакты; без добавления
новых требований/кейсов).

### Step 6. WAIT — финальное approval

Представить финальный (исправленный) план и [VERIFICATION_REPORT] пользователю, через `AskUserQuestion`
получить подтверждение.

### Step 7. Сформировать [VERIFICATION_REPORT]

STOP if:

- нерешённые DSL-ошибки после итерации;
- провал coverage-gate (кейсы потеряны/лишние Routine);
- финальное approval denied.

---

## Output Format

Заполни каждую секцию. Пустые секции запрещены.

```md
# [VERIFICATION_REPORT]

## Результат DSL-валидации

[На каждую cell: PASS / список исправленных ошибок]

## Coverage

[Кол-во кейсов vs кол-во Routine; статус: все покрыты / расхождения]

## Базовый блок

[Статус: Usages/Annotations идентичны во всех cells / расхождения]

## Внесённые исправления

[Что исправлено в docs/pybuggy/feature-cells.md. Пусто, если ничего.]

## Финальный статус

[PASS / FAIL + путь к утверждённому плану]
```
