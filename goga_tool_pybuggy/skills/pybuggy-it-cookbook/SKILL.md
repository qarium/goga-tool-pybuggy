---
name: goga-tool-pybuggy-it-cookbook
description: Принципы применения DSL goga-cell для проектирования тестовых cells
---
# Pybuggy IT Cookbook

## Purpose

Принципы применения DSL `goga-cell` при проектировании **тестовых** cells. Это адаптация `goga-cookbook`,
оставляющая только релевантное для тестов: тесты описываются как `Routine`, без `Imports`, с базовыми
`Usages`/`Annotations` из конфига проекта.

Этот скилл вызывается другими скиллами для контекста проектирования тестовых cells.

## Behavior

Применяй принципы в контексте вызывающего скилла. Не пересказывай `goga-cookbook` целиком и не описывай, как
устроены другие скиллы — используй принципы для проектных решений по тестовым cells.

---

# Принципы проектирования тестовых cells

## Контекст

Тесты — отдельный проект, использующий pybuggy как фреймворк. Каждая тестовая cell — это папка тестов
эндпоинта, созданная `pybuggy generate`:

```
tests/<spec>/<endpoint-id>/
└── CODEMANIFEST
```

Гранулярность фиксирована: **один эндпоинт — одна cell**. Решения «когда создавать cell» и «насколько крупной
быть cell» здесь не применяются — cell уже определена генерацией.

## CODEMANIFEST тестовой cell

### Порядок дизайна

1. **Header** — базовые `Usages` + `Annotations` (контракт работает в контексте базовых практик проекта).
2. **Body** — `Routine` на каждый тест-кейс.
3. **Footer** — `Author`, `CreatedAt`, `Description`.

### Header

`Usages` и `Annotations` берутся из `.goga/config.yml` (через `goga-codemanifest-base`) и едины для всех
тестовых cells:

- `Usages`: `conventions`, `pybuggy-api`, `pybuggy-asserts` (пути в `.goga/usages/`).
- `Annotations`: инструкции вида `Use \`pybuggy-api\` for ...`, `Use \`pybuggy-asserts\` for ...`.
- Без `Imports`.

### Body — Routine

Тест — это `Routine` (без `methods`/`properties`), по одному на тест-кейс:

```yaml
"test_<name>(<fixture>: Endpoint)":
  location: test_<name>.py
  annotations: |
    ...
```

- Сигнатура: `test_<name>(<fixture>: Endpoint)` — без output (тест ничего не возвращает).
- `<fixture>` — сгенерированная фикстура `api/<spec>/<id>/api.py` (имя `<method>_<id>`).
- Naming `snake_case`, `location: test_<name>.py` (правила `goga-cell-python`).

### Footer

- `Author` — всегда `Goga`.
- `CreatedAt` — день/месяц/год.
- `Description` — зачем эта cell (тесты какого эндпоинта/фичи).

## Standard аннотаций Routine

Аннотация Routine должна быть достаточна для реализации без уточнений. Для тестов используются:

**1. Purpose — без лейбла.** Что проверяет Routine (из `title`/описания тест-кейса).

**2. `Algorithm:` — для шагов теста.** Пронумерованные шаги из тест-кейса (Действие / Данные / Ожидание).
Логика, не код — шаги выражают действия через ссылки на Usages и фикстуру, без pytest-кода.

**3. References.** Backtick-ссылки на: параметр-фикстуру (`` `<fixture>` ``), практики (`pybuggy-api`,
`pybuggy-asserts`, `conventions`). Каждая ссылка должна разрешаться в контексте CODEMANIFEST.

**Не используется** для тестов: `Requirements:`/`Constraints:` переносятся из кейса по мере необходимости,
но основа — Purpose + `Algorithm:`.

Пример:

```yaml
"test_create_order_returns_201(create_order: Endpoint)":
  location: test_create_order_returns_201.py
  annotations: |
    Проверяет успешное создание заказа — статус 201 и наличие id в ответе.

    `create_order`: сгенерированная фикстура api/orders/create_order/api.py

    Algorithm:
    1. Вызвать эндпоинт с валидным телом заказа
    2. Проверить статус 201 и поле id в ответе

    Use `pybuggy-api` for вызова эндпоинта
    Use `pybuggy-asserts` for проверок ответа
```
