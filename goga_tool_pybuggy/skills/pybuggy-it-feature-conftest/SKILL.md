---
name: goga-tool-pybuggy-it-feature-conftest
description: Создаёт корневой conftest.py целевого тестового проекта — загрузка .env (load_dotenv) и подключение плагина pybuggy (pytest_plugins + install) до старта pytest
---
# Pybuggy IT Feature Conftest

## Identity

Ты отвечаешь за создание **корневого `conftest.py`** в целевом (тестовом) проекте — единой точки, которую
pytest гарантированно выполняет до сбора и запуска тестов. Это инфраструктура запуска набора: загрузка
переменных окружения из `.env` и подключение плагина pybuggy.

Это **рабочий код** (`conftest.py`), а не DSL-артефакт CODEMANIFEST. `tests/` **не является клеткой** —
инфраструктура запуска описывается кодом, а не контрактом.

## Mission

Создать `conftest.py` в **корне целевого проекта** (там, где запускается pytest), который:
1. загружает `.env` через `dotenv.load_dotenv` (с `override=False`) **до** подключения плагина;
2. подключает плагин pybuggy — `pytest_plugins = ["goga_tool_pybuggy.plugin"]` **плюс** явный вызов
   `goga_tool_pybuggy.plugin.install()`.

## Context Initialization

Перед началом загрузи контекст через **Skill tool**:

- **`goga-tool-pybuggy-it-usage`** — референс runtime pybuggy (как подключается плагин).
- **`.goga/usages/cooks/pluginator.md`** и **`.goga/usages/cooks/python-dotenv.md`** — паттерны установки
  плагина (`install()` + `pytest_plugins`) и семантика `load_dotenv` (`override=False`).

## Pre-flight

1. Убедись, что работаешь в **целевом проекте** (там, где будет запускаться pytest и где лежат `tests/`), а не
   в репо самой тулзы pybuggy.
2. Проверь наличие `conftest.py` в корне проекта. Если файл существует — **не перезаписывай без подтверждения**
   пользователя (предложи дополнить/слить).

## Phases

Выполняй фазы строго последовательно.

### Phase 1. Проверить зависимости

1. `goga_tool_pybuggy` импортируется (плагин установлен в окружении целевого проекта). Если нет — halt:
   сначала установите pybuggy в целевой проект.
2. `dotenv` импортируется (`python-dotenv`). Если нет — halt: добавьте зависимость.

### Phase 2. Сформировать conftest.py

Записать `conftest.py` в корень проекта с содержимым (фиксированный шаблон — не выдумывается):

```python
"""Корневой conftest тестового набора pybuggy.

Загружает .env и подключает плагин pybuggy до старта pytest.
"""
from dotenv import load_dotenv

# (1) .env — ДО плагина: опции плагина (QA_BASE_URL, QA_API_TIMEOUT, ...) резолвятся из os.environ.
load_dotenv()  # неявный .env из CWD; override=False — переменные shell/CI не перезаписываются

# (2) Плагин pybuggy: pytest_plugins + явный install().
#     Одного pytest_plugins НЕ достаточно — install() не вызывается на верхнем уровне модуля плагина.
pytest_plugins = ["goga_tool_pybuggy.plugin"]

import goga_tool_pybuggy.plugin

goga_tool_pybuggy.plugin.install()
```

Если существующий `conftest.py` содержит пользовательский код — **слить**: добавить блоки (1) и (2), сохранив
пользовательский контент. Спросить пользователя при конфликте.

### Phase 3. Проверить

1. `python -c "import conftest"` в корне проекта (синтаксис + импорты). При ошибках — halt и сообщить.
2. Опционально: запустить `pytest --collect-only` (без выполнения тестов) — плагин должен подключиться без
   ошибок.

### Phase 4. Финальный отчёт

1. Путь к созданному/обновлённому `conftest.py`.
2. Что включено (load_dotenv + pytest_plugins + install).
3. Статус проверки (`import conftest` / `pytest --collect-only`).

## Invariants

### NEVER

- перезаписывать существующий `conftest.py` без подтверждения пользователя
- менять порядок: `load_dotenv` **всегда до** `install()` (опции плагина резолвятся из `os.environ`)
- опускать явный `install()` — одного `pytest_plugins` недостаточно
- использовать `override=True` в `load_dotenv` (CI/оператор теряют возможность фиксировать окружение)
- создавать `conftest.py` в репо самой тулзы pybuggy (только в целевом проекте)

### ALWAYS

- создавать `conftest.py` в **корне целевого проекта**
- сохранять пользовательский контент при слиянии с существующим `conftest.py`
- проверять синтаксис/импорты после записи
