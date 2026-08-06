# Design Document — env-cli (Загрузка `.env` в CLI pybuggy)

> Дизайн-документ (архитектурная спецификация реализации) фичи **env-cli**. Описывает **что** и **как**
> реализовать на уровне кода по изменённым контрактам CODEMANIFEST. Это **не** код и **не** execution-plan —
> это полная проработка деталей реализации, трассировка стека вызовов, сквозные вопросы и тест-сценарии.
>
> Имя файла = имя ветки = имя фичи (`env-cli`), согласно указанию stage. Источник плана ячеек:
> [`docs/arch/env-cli.md`](../arch/env-cli.md). Контракты уже материализованы в CODEMANIFEST этапом
> `apply-architecture`; настоящий документ — следующий шаг (дизайн кода) перед генерацией/планом.

---

## 1. Тема и Scope

**env-cli** — единый механизм загрузки переменных окружения в CLI pybuggy:

1. глобальная опция `--env-file` на корневой click-группе `main` (eager-callback, ДО подкоманды);
2. загрузка `.env` в `os.environ` с `override=False`;
3. контекст-объект `ctx.obj` типа `EnvContext` (разрешённый путь + загруженные значения);
4. env-переменная `PYBUGGY_REF` как новый уровень приоритета git-ref в команде `pull`.

### Затронутые ячейки и изменения CODEMANIFEST (Phase 2)

Scope образуют только изменения фичи env-cli. Изменения собраны из working-tree (материализованы этапом
`apply-architecture`) — committed-дифф `0.0.x...HEAD` здесь **не** используется как источник scope.

| Ячейка | Файл CODEMANIFEST | Режим | Суть изменения |
|---|---|---|---|
| ROOT | `goga_tool_pybuggy/CODEMANIFEST` | MODIFY | +Usage `python-dotenv`; расширены Annotations; `main()` Algorithm (eager-callback `ctx.obj = load_env(env_file)` + Requirements/Constraints); +Routine `load_env`; +Entity `EnvContext`; Footer Description. |
| pull | `goga_tool_pybuggy/commands/pull/CODEMANIFEST` | MODIFY | `run_pull` Algorithm 4b — уровень `PYBUGGY_REF` между global `--ref` и `GitEntry` ref; +Requirements/Constraints маркеры. Header/`pull_cmd`/`SmartParam`/Footer без изменений. |

**Вне scope (явное исключение):** committed-изменение `goga_tool_pybuggy/spec/CODEMANIFEST` (коммит
`1a12161`, нормализация дефисов в endpoint-id) — отдельный неродственный фикс, к env-cli **не относится** и в
дизайн не входит.

### Карта зависимостей (Phase 2)

`goga schema` неавторитетен (396 предсуществующих AST-ошибок, см. отчёт `apply-architecture`), карта построена
вручную по `Imports` и подтверждена исходниками:

```text
   config (leaf)                            plugin (leaf)
       ▲                                        ▲
       │ Imports: load_config, Config,          │ Imports: install
       │         SpecEntry, GitEntry,           │ (embedding ->install в ROOT)
       │         usage `configuration`
       │
   commands/pull ◄── Imports(pull_cmd) ── ROOT (goga_tool_pybuggy/)
   run_pull reads os.environ["PYBUGGY_REF"]     │
        ▲                                       │ main() eager-callback:
        │ runtime os.environ                    │   load_env(env_file) -> EnvContext
        │ (override=False)                      │   writes os.environ; ctx.obj = EnvContext
        └───────────────────────────────────────┘
                (runtime-связь через os.environ — НЕ Imports)
```

- **Новых import-рёбер фича не вводит.** ROOT по-прежнему импортирует `pull_cmd`/`list_cmd`/`info_cmd`/`generate_cmd`/`init_cmd`/`install`; pull по-прежнему импортирует `load_config`/`Config`/`SpecEntry`/`GitEntry` + usage `configuration` из `config`.
- ROOT→pull связаны только runtime-связью через `os.environ` (ROOT пишет, pull читает `PYBUGGY_REF`), без перекрёстных `Imports`. Слабая связность сохранена.
- Циклов нет (листья `config`/`plugin` → `commands/*` → ROOT).

---

## 2. Валидация контрактов (Phase 3) — вердикт: CLEAN

Контракт уже материализован из прошедшего ревью плана. Аудит четырёх измерений консистентности:

1. **Interface ↔ Type** — `load_env -> ctx: EnvContext`; тип `EnvContext` объявлен в той же ячейке (ROOT).
   Свойства `EnvContext` (`env_path -> str | None`, `values -> dict[str, str]`) совпадают с параметрами
   конструктора `EnvContext(env_path, values)`. `main()` хранит результат `load_env` в `ctx.obj`. **PASS.**

2. **Type ↔ Mutation** — мутаций (`::`) в изменяемой части нет; `retries` и embedding `->install: {}` не
   тронуты. **PASS.**

3. **Interface ↔ Interface** — поток типов корректен: `env_file: str | None` → `load_env` → `EnvContext` →
   `ctx.obj`; дочерние контексты click наследуют `ctx.obj` (см. §4.1). pull читает `os.environ` (строка), без
   контрактной зависимости от `EnvContext`. **PASS.**
   - **Деталь реализации (НЕ дефект контракта):** `dotenv_values` возвращает `dict[str, str | None]`
     (`KEY=` → `''`; голый ключ без `=` → `None`), а контракт `EnvContext.values` требует `dict[str, str]`.
     Дизайн коэрцит `None → ""` (см. §4.2), удовлетворяя контракту `dict[str, str]`. Контракт внутренне
     консистентен; правка не нужна.

4. **Annotations ↔ Entity** — все бэктик-ссылки разрешимы в контексте документа. `load_config`/`values`/`.env`
   в аннотациях ROOT — литералы той же lint-категории (`annotation_links_exists`), что 17 предсуществующих в
   проекте (см. отчёт `apply-architecture`); правка нарушила бы консистентность ячейки с остальным проектом и
   отвергнута. **PASS (с принятой lint-оговоркой).**

**Gap-анализ:**
- Пропущенных сущностей нет (`load_env`, `EnvContext` объявлены; `main` расширен).
- `location` корректны: `env.py` на уровне корневой ячейки (без обхода каталогов), `cli.py`, `pull.py` —
  аналогично.
- Импортированные usages существуют: `configuration.md`, `gitpython.md`, `click.md`, `conventions.md`,
  `python-dotenv.md` — все резолвятся.
- Повторное использование кода: `cli.py::main` (добавить опцию + eager-callback), `pull.py::_effective_ref`
  (вставить уровень `PYBUGGY_REF`). Чистый минимальный diff.

**Дефектов контракта, требующих правки CODEMANIFEST или вопроса пользователю, не обнаружено.**
Согласно Phase 3 Step 4 — шаг одобрения пропускается; дизайн выполняется автономно.

---

## 3. Сквозные вопросы (Phase 4 Step 4)

| Концерн | Решение |
|---|---|
| **Обработка ошибок** | Единый паттерн проекта: доменные ошибки → `click.ClickException` (ненулевой exit, единое сообщение). Применяется в `load_env` (явный `--env-file` на отсутствующий файл → `ClickException`) и остаётся без изменений в `pull` (clone/unknown-spec/path-traversal). Новых классов ошибок нет. |
| **Валидация** | `load_env`: для **явного** файла — проверка существования (`Path.exists()`); для **неявного** `.env` — отсутствие тихо пропускается. `override=False` — инвариант применения в `os.environ`. Никакой валидации **содержимого** пар (значения грузятся как есть). |
| **Логирование** | Не добавляется. Существующий `cli.py`/`pull.py` используют `click.echo`, а не `logging`; `load_env` следует тому же минималистичному паттерну (тихая загрузка, без побочного вывода). `conventions` (logging) формально применимы к операциям, но контракт `load_env` логирование не требует — добавление нарушило бы принцип минимального diff и поведение «silent implicit .env». |
| **Кеширование** | Нет. |
| **Параллелизм** | Нет. CLI однопоточный; побочный эффект — запись `os.environ` — происходит синхронно в eager-callback до любой подкоманды. |

---

## 4. Трассировка стека вызовов (Phase 4 Step 1)

Дизайн оперирует целевым контрактом (CODEMANIFEST уже обновлён). Реализация ещё не приведена к контракту —
ниже описывается **как именно** её изменить. Для каждой точки входа: вход → шаги → внешние вызовы → выход.

### 4.1 `main()` — `goga_tool_pybuggy/cli.py` (MODIFY)

**Текущее состояние:** `@click.group() def main()` без опций; определена `endpoint_group`, команды
регистрированы. `--env-file`/eager-callback отсутствуют.

**Целевое поведение (контракт `main()`):** корневая группа с глобальной eager-опцией `--env-file`, чей
callback вызывает `load_env(value)` и кладёт результат в `ctx.obj`.

**Трассировка:**

1. **Точка входа:** `pybuggy --env-file ./my.env endpoint pull` (CLI) либо программный `main()`
   (`from goga_tool_pybuggy import main`).
2. **Парсинг опций группы:** click парсит групповые опции. `--env-file` объявлен с `is_eager=True` и
   `callback=_load_env_callback` → callback срабатывает **до** выбора/инвокации подкоманды.
3. **Eager-callback** `_load_env_callback(ctx, _param, value)`:
   - `ctx.obj = load_env(value)`;
   - `return value` (значение опции пробрасывается дальше без изменений; оно нужно только для загрузки env).
4. **`load_env(value)`** — см. §4.2. Возвращает `EnvContext`; побочный эффект — запись в `os.environ`
   (`override=False`).
5. **`ctx.obj` наследуется дочерними контекстами:** в click 8.x `Context.obj` авто-наследуется от родителя,
   если не установлен (`@property` падает к `parent.obj`). Зависимость `click>=8.0` в `pyproject.toml` это
   гарантирует. Поэтому подкоманды видят тот же `EnvContext` на `ctx.obj`.
6. **Инвокация подкоманды** (`pull`): `run_pull` читает `os.environ["PYBUGGY_REF"]` (см. §4.4) — то значение,
   которое `load_env` туда положил (если `.env` его содержал).
7. **Порядок опций:** т.к. `--env-file` парсится на уровне группы, он обязан идти **до** подкоманды
   (`pybuggy --env-file f endpoint pull` ✓; `... endpoint pull --env-file f` → exit 2 «No such option»).
   Это поведение click, подтверждается тестом (§7, тест `test_env_file_option_must_precede_subcommand`).

**Структура реализации** (целевой `cli.py`, фрагмент):

```python
import click

from .commands.generate import generate_cmd
from .commands.info import info_cmd
from .commands.init import init_cmd
from .commands.list import list_cmd
from .commands.pull import pull_cmd
from .env import EnvContext, load_env


def _load_env_callback(ctx: click.Context, _param: click.Parameter, value: str | None) -> str | None:
    """Eager-callback: load .env into os.environ and store EnvContext on ctx.obj."""
    ctx.obj = load_env(value)
    return value


@click.group()
@click.option(
    "--env-file",
    "env_file",
    default=None,
    callback=_load_env_callback,
    is_eager=True,
    help="Path to a .env file loaded into os.environ (override=False) before the command runs.",
)
def main(env_file: str | None) -> None:
    """pybuggy — CLI tool for work with OpenAPI/Swagger endpoints."""
```

> Чекпойнты: тип `value: str | None` совпадает с входом `load_env` ✓; `ctx.obj` — `EnvContext` ✓;
> наследование через click 8.x ✓. Существующие `endpoint_group` и регистрация команд не меняются.

**Edge:** eager-callback срабатывает при любом вызове группы (даже без `--env-file`, `value=None` → неявный
`.env` из CWD); для `--help` click прерывает поток — безвредно. `invoke_without_command` не выставляется
(существующее поведение «`pybuggy` без подкоманды → help, exit 2» сохраняется).

### 4.2 `load_env(env_file: str | None) -> ctx: EnvContext` — `goga_tool_pybuggy/env.py` (NEW)

**Трассировка:**

1. **Вход:** `env_file` — явный путь из `--env-file`, либо `None` (неявный `.env` в CWD).
2. **Резолвинг пути (Algorithm 1):**
   - `env_file is not None` → **явный**: `path = Path(env_file)`; он обязан быть читаемым **обычным файлом**
     (`is_file()`): если `not path.exists()` → `raise click.ClickException(f"env file not found: {env_file}")`;
     если существует, но не файл (например каталог) →
     `raise click.ClickException(f"env file is not a regular file: {env_file}")`.
   - `env_file is None` → **неявный**: `path = Path(".env")`; если `not path.is_file()` (отсутствует **или** не
     обычный файл — например каталог с именем `.env`) → `return EnvContext()` (тихо, `env_path=None`, `values={}`).
3. **Чтение значений:** `raw = dotenv_values(str(path))` → `dict[str, str | None]` (без побочных эффектов,
   API `python-dotenv` 1.2.2). Семантика значений: `KEY=val` → `'val'`; `KEY=` (с `=`, пустое значение) → `''`
   (**не** `None` — пустая строка напрямую); голый ключ `KEY` (без `=`) → `None`. Коэрцит `None → ""` нужен
   именно для голых ключей — иначе контракт `dict[str, str]` нарушился бы:
   `values = {k: (v if v is not None else "") for k, v in raw.items()}`.
4. **Применение в `os.environ` (Algorithm 2):** `load_dotenv(str(path), override=False)` — `override=False`
   передаётся **явно** (инвариант контракта). Уже заданные переменные не перезаписываются.
5. **Выход:** `return EnvContext(env_path=str(path), values=values)`.

**Семантическое различие двух представлений (осознанное):**
- `EnvContext.values` = содержимое **файла** (все пары, включая те, что не перезаписали существующее окружение).
- `os.environ` после `load_dotenv(override=False)` = файл, применённый **без** перезаписи уже заданного.

Это разные взгляды по контракту (`values` — «загруженные пары файла»; `os.environ` — «применённое окружение»).
Несоответствия нет.

**Структура реализации** (`env.py`):

```python
"""Environment loading for the pybuggy CLI: .env → os.environ (override=False)."""

from pathlib import Path
from typing import Optional

import click
from dotenv import dotenv_values, load_dotenv
from pydantic import BaseModel, ConfigDict


class EnvContext(BaseModel):
    """Context object carrying the resolved env-file path and loaded key→value pairs.

    Stored on click ctx.obj by main(); pure data carrier.
    """

    model_config = ConfigDict(kw_only=True)

    env_path: Optional[str] = None
    values: dict[str, str] = {}


def load_env(env_file: Optional[str]) -> EnvContext:
    """Resolve the env-file, load it into os.environ (override=False), and return EnvContext.

    Args:
        env_file: explicit path from --env-file, or None for the implicit .env in CWD.

    Returns:
        EnvContext with the resolved path and loaded key→value pairs.

    Raises:
        click.ClickException: when an explicit --env-file points at a missing file.
    """
    if env_file is not None:
        path = Path(env_file)
        if not path.exists():
            raise click.ClickException(f"env file not found: {env_file}")
        if not path.is_file():
            raise click.ClickException(f"env file is not a regular file: {env_file}")
    else:
        path = Path(".env")
        if not path.is_file():
            return EnvContext()

    values = {k: (v if v is not None else "") for k, v in dotenv_values(str(path)).items()}
    load_dotenv(str(path), override=False)

    return EnvContext(env_path=str(path), values=values)
```

> Чекпойты: `Optional[str]` (по `conventions`, не `str | None`; ruff `UP045` игнорируется) ✓;
> `kw_only=True` через `ConfigDict` ✓; mutable-default `values={}` безопасен в pydantic v2 (deep-copy на
> инстанс; альтернатива — `Field(default_factory=dict)`) ✓; относительный импорт `from .env import ...` в
> `cli.py` ✓.

### 4.3 `EnvContext(env_path, values)` — `goga_tool_pybuggy/env.py` (NEW)

Pydantic-модель, `kw_only=True`, дефолты `env_path=None`, `values={}`. Чистый носитель данных — два свойства
`env_path`, `values`, без поведения. Экспонируется на фасаде ROOT через `__all__` (для потребителей/тестов).

`__init__.py` (MODIFY) — экспорт `load_env`, `EnvContext`:

```python
from .cli import main
from .env import EnvContext, load_env
from .plugin import install
from .tools import retries

__all__ = ["EnvContext", "install", "load_env", "main", "retries"]
```

### 4.4 `run_pull(...)` — `goga_tool_pybuggy/commands/pull/pull.py` (MODIFY)

**Текущее состояние:** `_effective_ref(name, git_ref, global_ref, per_spec)` резолвит `per_spec → global_ref →
git_ref`. Уровня `PYBUGGY_REF` нет. `import os` в модуле отсутствует.

**Целевое поведение (контракт Algorithm 4b):** вставить уровень `PYBUGGY_REF` строго **между** global ref и
`GitEntry` ref:
`per-spec → global --ref → PYBUGGY_REF (os.environ) → git.ref → None (default branch)`.

**Изменение** (минимальный diff в `_effective_ref`):

```python
import os  # добавить к существующим импортам модуля

def _effective_ref(name, git_ref, global_ref, per_spec):
    """Resolve the effective ref: per-spec → global → PYBUGGY_REF(os.environ) → git.ref."""
    if name in per_spec:
        return per_spec[name]

    if global_ref is not None:
        return global_ref

    pybuggy_ref = os.environ.get("PYBUGGY_REF")
    if pybuggy_ref:
        return pybuggy_ref

    return git_ref
```

**Трассировка эффективного ref** (на примере spec `client` с `git.ref="main"`, без `--ref`, без per-spec):
1. `name in per_spec` → False.
2. `global_ref is not None` → False (флаг не передан).
3. `os.environ.get("PYBUGGY_REF")` → `"v2"` (если `.env` содержал `PYBUGGY_REF=v2`) → возвращаем `"v2"`.
4. (если `PYBUGGY_REF` нет/пусто) → возвращаем `git_ref="main"`; `None` → default branch.

**Решение по пустой строке:** `PYBUGGY_REF` считается «заданной» при наличии и **непустоте** (truthiness-проверка
`if pybuggy_ref:`). `PYBUGGY_REF=` (пусто) трактуется как незаданная → переход к `git.ref`. Это прагматичный
выбор (пустой ref бессмысленен как override и был бы ошибкой клона).

**Чекпойнты контракта:** per-spec и явный global `--ref` **не** перебиваются `PYBUGGY_REF` (они проверяются
раньше) ✓; `PYBUGGY_REF` перебивает `git.ref` ✓; отсутствие/`None` на любом уровне → переход дальше ✓.
Остальная логика `run_pull` (clone+copy, `_validate_*`, `_resolve_refs`, `_validate_per_spec_refs`) **не
меняется**.

### 4.5 `pull_cmd`, `SmartParam.convert` — без изменений

`pull_cmd` связывает `--spec`/`--ref` и вызывает `run_pull`; `SmartParam.convert` парсит токен `--ref`.
Контракт и реализация не затронуты фичей.

---

## 5. Анализ взаимодействий и практик (Phase 4 Step 2–3)

### 5.1 Анализ трассировки

- **Новые сущности и взаимодействия:** `load_env` + `EnvContext` (ROOT); runtime-связь ROOT→`os.environ`→pull
  через `PYBUGGY_REF`. Это **мост через `os.environ`**, а не через `Imports` — слабая связность сохранена.
- **Паттерны:** eager-callback click (загрузка env до подкоманды); pydantic context-object (`kw_only=True`);
  handler-обёртка (уже есть: `run_pull` тестируется напрямую, `pull_cmd` только связывает опции).
- **Сквозной поток данных:** `--env-file` (CLI) → `load_env` → `os.environ` + `EnvContext` → `ctx.obj` →
  (подкоманда) → `run_pull` читает `os.environ["PYBUGGY_REF"]`.
- **Edge-кейсы, выявленные трассировкой:** явный отсутствующий файл; неявный отсутствующий `.env`;
  `override=False` (предсуществующая переменная); `KEY=` (пустое значение → `None` → `""`); пустой
  `PYBUGGY_REF`; `PYBUGGY_REF` против per-spec/global/`git.ref`.

### 5.2 Usages-анализ

| Практика | Где | Что даёт | Почему выбрана | Как применяется |
|---|---|---|---|---|
| `python-dotenv` | ROOT (файл `.goga/usages/cooks/python-dotenv.md`) | `dotenv_values`, `load_dotenv(override=False)` | Сторонняя библиотека для `.env` | `dotenv_values` → `values`; `load_dotenv(override=False)` → применение в `os.environ` |
| `click` | ROOT, pull (файл) | group/option/**eager-callback**/command/`ClickException` | CLI-фасад проекта | `--env-file` eager-callback в `main`; опции/`ClickException` в pull (без изменений) |
| `conventions` | ROOT, pull (файл) | pydantic `kw_only`, относительные импорты, `Optional`, CLI-тестирование прямым вызовом, docstrings, deps в pyproject | Единые правила кода/тестов | `EnvContext` pydantic `kw_only`; `Optional[str]`; `from .env import ...`; тесты `load_env`/`run_pull` напрямую |
| `gitpython` | pull (файл) | `Repo.clone_from(depth=1, branch=ref)`, контекстный менеджер | Shallow-clone | Без изменений (`clone_repo`) |
| `configuration` | pull (импортировано из `config/.usages/configuration.md`) | `load_config()` + модели конфига | Доступ к конфигу | Без изменений |

Каждая подключённая практика имеет минимум одну ссылку из аннотации (глобальной/типовой). Неподключённых или
нессылочных практик нет.

---

## 6. Консистентность `.usages/` (Phase 4 Step 6) — без изменений

Оба `.usages/` материализованы этапом `apply-architecture` и сверены с диском (содержимое совпадает с планом):

- **`goga_tool_pybuggy/.usages/assembly.md`** — добавлена секция «Загрузка .env»; обновлены «Точка входа»,
  «Сборка CLI», «Статичный конфиг» (pass-object несёт env, не конфиг), «Предусловия». Описанные API (`main`,
  `load_env`, `EnvContext`, `--env-file` ДО подкоманды, `override=False`) **совпадают** с контрактами ROOT.
  Нет ссылок CODEMANIFEST `Usages` на собственный `.usages/` (последнее — нарушение; здесь его нет). **OK.**
- **`goga_tool_pybuggy/commands/pull/.usages/pull.md`** — добавлена секция «Env-переменная `PYBUGGY_REF`»;
  обновлён приоритет в «Поведение» (`per-spec → global --ref → PYBUGGY_REF → git.ref → default branch`).
  Совпадает с `run_pull` Algorithm 4b. **OK.**

Изменения в пределах существующих доменов (дополнение), новые домены не появились → новых `.usages/`-файлов не
создаётся, существующие править не нужно.

---

## 7. Тест-сценарии (Phase 4 Step 5)

Тесты — deliverable. Каждый сценарий содержит 6 обязательных элементов: **Name / Setup / Input / Trace /
Assertions / Sufficiency**. Размещение по `conventions`: `tests/module/test_<file>.py`; handler-функции
тестируются **прямым вызовом** (без `CliRunner`); FS — `tmp_path`; внешние зависимости — `mock.patch` в точке
импорта. `os.environ`-тесты изолируются через `monkeypatch.delenv(..., raising=False)` и восстановление.

### 7.1 `tests/test_env.py` — `load_env`, `EnvContext`

**T1 — `test_load_env_explicit_file_applies_and_returns_context`** (Positive)
- **Setup:** `tmp_path/.env` с `PYBUGGY_REF=v2\nDEBUG=1`; `monkeypatch.delenv` для `PYBUGGY_REF`, `DEBUG`;
  `monkeypatch.chdir(tmp_path)`.
- **Input:** `load_env(str(tmp_path / ".env"))`.
- **Trace:** `env_file` не None → `Path(...).exists()` True → `dotenv_values` → `{PYBUGGY_REF:"v2",DEBUG:"1"}`
  → коэрцит (без изменений) → `load_dotenv(..., override=False)` пишет в `os.environ` → `EnvContext(env_path=.../".env", values={...})`.
- **Assertions:** `ctx.env_path.endswith(".env")`; `ctx.values == {"PYBUGGY_REF":"v2","DEBUG":"1"}`;
  `os.environ["PYBUGGY_REF"]=="v2"`; `os.environ["DEBUG"]=="1"`.
- **Sufficiency:** Доказывает ядро фичи — явный файл грузится в `os.environ` и возвращается в `EnvContext`.

**T2 — `test_load_env_explicit_missing_file_raises_clickexception`** (Negative)
- **Setup:** путь к несуществующему файлу `tmp_path/nope.env`.
- **Input:** `load_env(str(tmp_path / "nope.env"))`.
- **Trace:** `env_file` не None → `not path.exists()` True → `raise click.ClickException`.
- **Assertions:** `with pytest.raises(click.ClickException):` (сообщение содержит «env file not found»).
- **Sufficiency:** Фиксирует контракт «явный файл обязан существовать» — регресс на тихое падение/невидимую ошибку.

**T3 — `test_load_env_implicit_dotenv_absent_is_silent`** (Edge)
- **Setup:** пустой `tmp_path` (без `.env`); `monkeypatch.chdir(tmp_path)`; `monkeypatch.delenv("PYBUGGY_REF")`.
- **Input:** `load_env(None)`.
- **Trace:** `env_file is None` → `Path(".env").exists()` False → `return EnvContext()`.
- **Assertions:** `ctx.env_path is None`; `ctx.values == {}`; `pytest.not_raises` (исключения нет);
  `os.environ` не изменился (`PYBUGGY_REF` не появился).
- **Sufficiency:** Контракт «неявный отсутствующий `.env` — тихо, без ошибки» (Acceptance Criterion).

**T4 — `test_load_env_does_not_override_existing_env_var`** (Edge — override=False)
- **Setup:** `tmp_path/.env` с `PYBUGGY_REF=fromfile`; `monkeypatch.setenv("PYBUGGY_REF","fromshell")`;
  `monkeypatch.chdir(tmp_path)`.
- **Input:** `load_env(None)` (неявный `.env` из CWD).
- **Trace:** `.env` существует → `dotenv_values` → `values={"PYBUGGY_REF":"fromfile"}` →
  `load_dotenv(..., override=False)` НЕ перезаписывает предсуществующее.
- **Assertions:** `ctx.values == {"PYBUGGY_REF":"fromfile"}` (значение из файла);
  `os.environ["PYBUGGY_REF"]=="fromshell"` (окружение не перезаписано).
- **Sufficiency:** Доказывает инвариант `override=False` и корректность раздельного представления
  `values` vs `os.environ` (Acceptance Criterion).

**T5 — `test_load_env_key_without_value_coerced_to_empty`** (Edge — `KEY=` и голый ключ)
- **Setup:** `tmp_path/.env` с `EMPTY=\nBARE\nFULL=x` (`EMPTY=` — с `=`, пустое значение; `BARE` — голый ключ
  без `=`); `monkeypatch.chdir(tmp_path)`.
- **Input:** `load_env(None)`.
- **Trace:** `dotenv_values` → `{"EMPTY":"","BARE":None,"FULL":"x"}` (`EMPTY=` → `''` напрямую, **без** `None`;
  `BARE` → `None`) → коэрцит `None→""` срабатывает на `BARE` → `{"EMPTY":"","BARE":"","FULL":"x"}`.
- **Assertions:** `ctx.values["EMPTY"]==""` (без коэрцита, `''` из `KEY=`); `ctx.values["BARE"]==""` (через
  коэрцит `None→""`); `ctx.values["FULL"]=="x"`; тип `dict[str,str]` (без `None` ни в одном значении).
- **Sufficiency:** Доказывает, что коэрцит `None→""` реально срабатывает — на голом ключе `BARE` (единственная
  форма, дающая `None` в `python-dotenv` 1.2.2). Без голого ключа ветка коэрцита не выполнялась бы (`KEY=`→`''`),
  и удаление коэрцита прошло бы незамеченным, ломая контракт `dict[str, str]` для голых ключей.

**T5b — `test_load_env_explicit_directory_raises_clickexception`** (Negative — каталог как `--env-file`)
- **Setup:** `tmp_path/subdir/` (существующий каталог); `monkeypatch.chdir(tmp_path)`.
- **Input:** `load_env(str(tmp_path / "subdir"))`.
- **Trace:** `env_file` не None → `Path(subdir).exists()` True → `path.is_file()` False (это каталог) →
  `raise click.ClickException("env file is not a regular file: ...")` (до `dotenv_values`/`load_dotenv`).
- **Assertions:** `with pytest.raises(click.ClickException):` (сообщение содержит «not a regular file»).
- **Sufficiency:** Фиксирует усиленную проверку `is_file()`: каталог (или иной не-файл) как явный `--env-file`
  → понятная ошибка вместо тихой пустой загрузки. Регресс на молчаливое принятие каталога (см. Q3 ревью).

**T6 — `test_env_context_defaults`** (Edge — модель)
- **Setup:** без файла, без окружения.
- **Input:** `EnvContext()`.
- **Trace:** pydantic создаёт инстанс с дефолтами.
- **Assertions:** `ctx.env_path is None`; `ctx.values == {}`; `ctx.model_config.get("kw_only") is True` (или
  конструктор `EnvContext(env_path=..., values=...)` — только kw).
- **Sufficiency:** Фиксирует дефолты и `kw_only` модели (контракт `EnvContext`).

### 7.2 `tests/commands/pull/test_pull.py` — приоритет `PYBUGGY_REF`

**T7 — `test_effective_ref_uses_pybuggy_ref_when_no_override`** (Positive)
- **Setup:** `monkeypatch.setenv("PYBUGGY_REF","v2")`.
- **Input:** `_effective_ref("client", git_ref="main", global_ref=None, per_spec={})`.
- **Trace:** `per_spec` miss → `global_ref is None` → `os.environ.get("PYBUGGY_REF")=="v2"` → return `"v2"`.
- **Assertions:** результат `"v2"`.
- **Sufficiency:** Базовый сценарий нового уровня — `PYBUGGY_REF` заполняет «провал» между global ref и git.ref.

**T8 — `test_effective_ref_global_ref_overrides_pybuggy_ref`** (Precedence)
- **Setup:** `monkeypatch.setenv("PYBUGGY_REF","v2")`.
- **Input:** `_effective_ref("client", git_ref="main", global_ref="v3", per_spec={})`.
- **Trace:** `per_spec` miss → `global_ref="v3"` (not None) → return `"v3"` (до проверки `PYBUGGY_REF`).
- **Assertions:** результат `"v3"` (НЕ `"v2"`).
- **Sufficiency:** Доказывает: явный global `--ref` перебивает `PYBUGGY_REF` (контракт Algorithm 4b).

**T9 — `test_effective_ref_per_spec_overrides_pybuggy_ref`** (Precedence)
- **Setup:** `monkeypatch.setenv("PYBUGGY_REF","v2")`.
- **Input:** `_effective_ref("client", git_ref="main", global_ref=None, per_spec={"client":"v1"})`.
- **Trace:** `per_spec["client"]=="v1"` → return `"v1"`.
- **Assertions:** результат `"v1"`.
- **Sufficiency:** Per-spec override — высший приоритет; `PYBUGGY_REF` его не перебивает.

**T10 — `test_effective_ref_pybuggy_ref_overrides_git_ref`** (Precedence)
- **Setup:** `monkeypatch.setenv("PYBUGGY_REF","v2")`.
- **Input:** `_effective_ref("client", git_ref="main", global_ref=None, per_spec={})`.
- **Trace:** `per_spec` miss → `global_ref None` → `PYBUGGY_REF=="v2"` → return `"v2"` (раньше `git_ref`).
- **Assertions:** результат `"v2"` (НЕ `"main"`).
- **Sufficiency:** Доказывает: `PYBUGGY_REF` перебивает `git.ref` — ключевая семантика нового уровня.

**T11 — `test_effective_ref_empty_pybuggy_ref_falls_through`** (Edge)
- **Setup:** `monkeypatch.setenv("PYBUGGY_REF","")`.
- **Input:** `_effective_ref("client", git_ref="main", global_ref=None, per_spec={})`.
- **Trace:** `per_spec` miss → `global_ref None` → `os.environ.get("PYBUGGY_REF")==""` → falsy → return `"main"`.
- **Assertions:** результат `"main"`.
- **Sufficiency:** Фиксирует решение по пустой строке (truthiness): `PYBUGGY_REF=` трактуется как незаданная.

**T12 — `test_run_pull_reads_pybuggy_ref_from_environ`** (Integration via handler)
- **Setup:** `monkeypatch.setenv("PYBUGGY_REF","v2")`; конфиг с одной spec `client` (`git.ref=None`,
  `git.url=...`, `git.location=spec.yml`); `mock.patch` для `clone_repo`/`Repo.clone_from` и FS-копирования
  (или фикстура репо в `tmp_path`).
- **Input:** `run_pull(spec_name="client")` (без `ref`).
- **Trace:** `load_config` → select `client` → `_resolve_refs(None)` → `(None,{})` →
  `_effective_ref("client", git_ref=None, global_ref=None, per_spec={})` → `PYBUGGY_REF=="v2"` →
  clone по ref `"v2"` → копирование.
- **Assertions:** замоканный clone вызван с `ref="v2"` (assert на mock call args).
- **Sufficiency:** Сквозная проверка: `run_pull` реально читает `PYBUGGY_REF` из `os.environ` и передаёт в clone.

### 7.3 `tests/test_cli_env.py` — eager-callback и порядок опции

**T13 — `test_env_file_callback_sets_ctx_obj`** (Direct handler call — preferred)
- **Setup:** `tmp_path/.env` с `PYBUGGY_REF=v2`; `monkeypatch.chdir(tmp_path)`; фейковый `ctx`
  (`types.SimpleNamespace(obj=None)`).
- **Input:** `_load_env_callback(ctx, param=None, value=str(tmp_path/".env"))` (прямой вызов callback).
- **Trace:** callback → `ctx.obj = load_env(value)` → `EnvContext` → `return value`.
- **Assertions:** `isinstance(ctx.obj, EnvContext)`; `ctx.obj.values["PYBUGGY_REF"]=="v2"`;
  `os.environ["PYBUGGY_REF"]=="v2"`; возвращено исходное `value`.
- **Sufficiency:** Тестирует eager-callback напрямую (по `conventions` — без `CliRunner`), фиксируя связку
  опция→`load_env`→`ctx.obj`.

**T14 — `test_env_file_option_must_precede_subcommand`** (CLI-parsing behavior — CliRunner оправдан)
- **Setup:** `click.testing.CliRunner`; изолированное окружение.
- **Input:** `runner.invoke(main, ["endpoint", "pull", "--env-file", "x.env"])` (опция ПОСЛЕ подкоманды).
- **Trace:** click парсит подкоманду `endpoint pull`, опция `--env-file` не принадлежит `pull` →
  `UsageError` «No such option: --env-file» → exit 2.
- **Assertions:** `result.exit_code == 2`; в выводе есть «No such option».
- **Sufficiency:** Acceptance Criterion «`--env-file` ДО подкоманды»; поведение click-парсинга, поэтому `CliRunner`.

**T15 — `test_load_env_then_run_pull_env_coupling`** (End-to-end runtime coupling ROOT↔pull)
- **Setup:** `tmp_path/.env` с `PYBUGGY_REF=v2`; `monkeypatch.delenv("PYBUGGY_REF")`; конфиг + замоканный clone.
- **Input:** `load_env(str(tmp_path/".env"))`, затем `run_pull(spec_name="client")`.
- **Trace:** `load_env` пишет `PYBUGGY_REF=v2` в `os.environ` → `run_pull` → `_effective_ref` читает `"v2"`.
- **Assertions:** после `load_env` `os.environ["PYBUGGY_REF"]=="v2"`; clone вызван с `ref="v2"`.
- **Sufficiency:** Доказывает фундамент фичи — runtime-мост ROOT→`os.environ`→pull через `PYBUGGY_REF`
  (слабая связность без `Imports`).

---

## 8. Реализационные дельты (сводка для этапа plan/build)

| Файл | Режим | Изменение |
|---|---|---|
| `goga_tool_pybuggy/env.py` | **NEW** | `EnvContext` (pydantic, `kw_only=True`) + `load_env(env_file)` (резолвинг через `is_file()`, `dotenv_values`+коэрцит голых ключей, `load_dotenv(override=False)`, `ClickException` на явный отсутствующий **или не-файл** (каталог)). |
| `goga_tool_pybuggy/cli.py` | MODIFY | `import os`-аналог `from .env import EnvContext, load_env`; добавить `@click.option("--env-file", ..., is_eager=True, callback=_load_env_callback)` на `main`; определить `_load_env_callback` (`ctx.obj = load_env(value); return value`). Регистрация команд без изменений. |
| `goga_tool_pybuggy/__init__.py` | MODIFY | экспорт `load_env`, `EnvContext` в `__all__`. |
| `goga_tool_pybuggy/commands/pull/pull.py` | MODIFY | `import os`; в `_effective_ref` вставить уровень `PYBUGGY_REF` (`os.environ.get("PYBUGGY_REF")`, truthiness) между `global_ref` и `git_ref`. |
| `tests/test_env.py` | **NEW** | T1–T6 (`load_env`, `EnvContext`). |
| `tests/commands/pull/test_pull.py` | **NEW** | T7–T12 (`PYBUGGY_REF` приоритет + `run_pull` integration); `tests/commands/pull/__init__.py`, `conftest.py` по `conventions`. |
| `tests/test_cli_env.py` | **NEW** | T13–T15 (eager-callback, порядок опции, runtime-мост). |

> К CODEMANIFEST и `.usages/` изменений **нет** — они уже материализованы этапом `apply-architecture` и
> прошли аудит (§2, §6). `pyproject.toml` уже содержит `python-dotenv>=1.2.2` (подтверждено).

---

## 9. Verification Checklist (по Acceptance Criteria фичи)

- [x] **Контракт чист** (§2): Interface↔Type, Type↔Mutation, Interface↔Interface, Annotations↔Entity — PASS.
- [x] **Нет новых Imports-рёбер / циклов** (§1): ROOT↔pull связаны только через `os.environ`.
- [x] **`--env-file` ДО подкоманды** (§4.1, T14): парсится на уровне группы → exit 2 при нарушении порядка.
- [x] **Тихий неявный `.env`** (§4.2, T3): отсутствие → `EnvContext(None, {})`, без ошибки.
- [x] **`override=False`** (§4.2, T4): предсуществующие переменные не перезаписываются.
- [x] **`ctx.obj = EnvContext(path, values)`** (§4.1, §4.3, T13): eager-callback → наследование ctx.obj в click 8.x.
- [x] **`PYBUGGY_REF` в `run_pull`** (§4.4, T7–T12): уровень между global ref и `git.ref`.
- [x] **`python-dotenv>=1.2.2`** в deps (§8): уже в `pyproject.toml`.
- [x] **Handler-тестирование** (§7): `load_env`/`run_pull`/callback тестируются прямым вызовом; `CliRunner`
      только для поведения парсинга опций (T14).
- [x] **`.usages/` консистентны** (§6): assembly.md / pull.md описывают актуальный контракт; правок не нужно.
