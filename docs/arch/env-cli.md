# Architecture Plan — env-cli (Загрузка `.env` в CLI pybuggy)

## Topic

**`env-cli`** — единый механизм загрузки переменных окружения в CLI pybuggy: глобальная опция `--env-file` на
корневой click-группе, загрузка `.env` в `os.environ` (`override=False`), контекст-объект `ctx.obj`, и переменная
`PYBUGGY_REF` в цепочке резолвинга git-ref команды `pull`.

Путь плана: `docs/arch/env-cli.md`.

---

## Implementation Order

От листьев к корню (cells без зависимостей — первыми):

1. **`goga_tool_pybuggy/commands/pull`** (extend) — **MODIFY first.**
   Обоснование: потребитель `PYBUGGY_REF`; зависит только от `config` (через существующий Imports, без изменений).
   `run_pull` читает `os.environ` (runtime-глобал), поэтому не зависит от ROOT-ячейки на уровне Imports.
2. **`goga_tool_pybuggy/` (ROOT)** (extend) — **MODIFY last.**
   Обоснование: composition root; владеет `main()`, новой опцией `--env-file`, типами `load_env`/`EnvContext`.
   Импортирует все командные ячейки (включая `pull`) — собирается после них.
3. **Сопутствующие проектные артефакты** — выполняются вместе с п.2:
   - `.goga/usages/cooks/python-dotenv.md` (CREATE) — должен существовать, т.к. ROOT `Usages` ссылается на него как `python-dotenv`.
   - `pyproject.toml` (MODIFY, non-DSL) — объявление зависимости `python-dotenv>=1.2.2`.

---

## Artifacts

### Cell: `goga_tool_pybuggy/commands/pull` (MODIFY)

#### Diff
- **CHANGE** `run_pull` annotation: Algorithm 4b — вставить уровень `PYBUGGY_REF` между global `--ref` и `GitEntry` ref.
- **ADD** в `run_pull` Requirements: маркер про чтение `PYBUGGY_REF` из `os.environ` (опциональна).
- **ADD** в `run_pull` Constraints: `PYBUGGY_REF` строго между global ref и `git.ref`, не перебивает per-spec/explicit global.
- **NO CHANGE**: Header (Imports/Usages/Annotations), `pull_cmd`, `SmartParam`, Footer.
- **MODIFY** `.usages/pull.md` — новая секция «Env-переменная `PYBUGGY_REF`» + обновлён приоритет в «Поведение».

#### Full CODEMANIFEST (`goga_tool_pybuggy/commands/pull/CODEMANIFEST`)

```yaml
Imports:
  - Types: [load_config, Config, SpecEntry, GitEntry]
    Usages: [configuration]
    From: goga_tool_pybuggy/config

Usages:
  conventions: .goga/usages/conventions.md
  gitpython: .goga/usages/cooks/gitpython.md
  click: .goga/usages/cooks/click.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `gitpython` for shallow-clone as a context manager and copy-to-local semantics.
  Use `click` for the command wrapper (options) and mapping domain errors to ClickException.
  Use `configuration` from Imports for loading and iterating the config.

  Use relative imports inside the cell.
  The handler `run_pull` is the testable entry point; the Click wrapper pull_cmd only binds options and calls `run_pull` (CLI tests call `run_pull` directly).
  Map domain errors (clone failure, missing repo path) to click.ClickException for a uniform non-zero exit.

---

"run_pull(spec_name: Optional[str], ref: Optional[str | tuple])":
  location: pull.py
  annotations: |
    Handler for the endpoint pull command: download specs from their git sources into their local location, idempotently.

    `spec_name`: optional filter; when set pull only that spec, otherwise pull all specs.
    `ref`: optional git ref override. Accepts: None (no override); a global ref string applied to every selected spec; or a tuple of items where each item is a global ref string or a (spec_name, ref) pair (per-spec override, produced by `SmartParam`). A plain string remains a global override (backward compatible with direct handler calls).

    Algorithm:
    1. Load the config via `load_config` and iterate its specs.
    2. Select specs: all `Config` specs, or only `spec_name` when provided.
    3. Normalize the ref override into a global ref and a per-spec map; a per-spec name absent from the config raises click.ClickException.
    4. For each selected entry:
       a. If the entry git field is None, skip it silently (local-only spec).
       b. Otherwise resolve the effective ref: per-spec override for this name wins, else the global ref,
          else PYBUGGY_REF from os.environ (when set), else the `GitEntry` ref, else None.
          Shallow-clone the `GitEntry` url into a temp dir (depth=1) at the effective ref
          (None = remote default branch), copy the `GitEntry` location -> project-root / `SpecEntry` location (overwrite, idempotent).
    5. On clone failure or missing repo path, raise click.ClickException with a clear message.

    Requirements:
    - Idempotent — repeated runs overwrite the target files.
    - `SpecEntry` location is project-root-relative; create parent dirs as needed.
    - PYBUGGY_REF is read from os.environ; populated by the root CLI group before the command runs; its presence is optional (absent ⇒ fall through to the next precedence level).

    Constraints:
    - Treat the repo as read-only — no commit/push.
    - Do not embed tokens in clone URLs — rely on git credential helpers (see `gitpython`).
    - PYBUGGY_REF never overrides a per-spec or explicit global --ref; it sits strictly between the global ref and the configured git.ref.

    Use `gitpython` for the clone+copy pattern and error mapping.
    Use `configuration` from Imports for config access.

"pull_cmd(spec_name: Optional[str], ref: tuple)":
  location: pull.py
  annotations: |
    Click command wrapper for the endpoint pull subcommand; binds the --spec and --ref options and delegates to `run_pull`.

    `spec_name`: optional spec filter, bound from --spec.
    `ref`: tuple of --ref values, each parsed by `SmartParam` (multiple=True); a value without ':' is a global ref, 'NAME:REF' is a per-spec pair. Empty tuple when --ref is absent (no override). Passed straight to `run_pull`.

    Use `click` for the command wrapper and option binding.

"SmartParam()":
  location: pull.py
  annotations: |
    A click.ParamType that parses a single --ref value into either a global ref or a per-spec (name, ref) override. Sets the click ParamType name to smart-ref.

    Use `click` for the ParamType base and the convert callback contract.
    Use `conventions` for type hints and relative imports.
  methods:
    "convert(value: str | None, param, ctx) -> ref: str | tuple[str, str] | None": |
      Parse one --ref token; click calls convert once per value (multiple=True).

      `value`: the raw --ref token supplied by click.
      `ref`: None for None/'' (no override); the value unchanged when it has no ':' (global ref); the (name, ref) pair when it is 'NAME:REF', splitting on the first ':' only so the ref value may itself contain ':'.

      Use `click` for the convert callback contract.

---

Author: Goga
CreatedAt: 08/07/26
Description: |
  endpoint pull command handler — downloads specs from git sources into local paths.
```

#### .usages file: `goga_tool_pybuggy/commands/pull/.usages/pull.md` (MODIFY)

```md
# goga_tool_pybuggy.commands.pull — команда endpoint pull

## Предметная область

Шаблоны потребления cell `goga_tool_pybuggy/commands/pull`: скачивание spec из git-источников в локальные `location`.
Аудитория — регистрация в CLI (`pull_cmd`) и тесты (`run_pull` напрямую).

## Вызов handler-функции

`run_pull` — тестируемая точка входа (Click-обёртка `pull_cmd` только связывает опции и вызывает `run_pull`):

    from goga_tool_pybuggy.commands.pull import run_pull

    run_pull(spec_name=None)                                    # тянуть все спеки
    run_pull(spec_name="client")                               # только одну spec
    run_pull(spec_name="client", ref="v2")                     # та же spec, глобальный ref
    run_pull(spec_name=None, ref=(("client", "v1"), ("server", "v2")))  # per-spec ref

CLI-форма (`pull_cmd`):

    pybuggy endpoint pull                       # тянуть все спеки
    pybuggy endpoint pull --spec client         # только одну spec
    pybuggy endpoint pull --ref v2              # глобальный ref для всех тянущихся спек
    pybuggy endpoint pull --spec client --ref v2
    pybuggy endpoint pull --ref client:v1 --ref server:v2   # разные ref для разных spec
    pybuggy endpoint pull --ref v2 --ref server:v3          # глобальный v2, но server — на v3

`--ref` повторяемый (`multiple=True`) и парсится `SmartParam`:
- без `:` — **глобальный** ref, применяется ко всем выбранным spec;
- `NAME:REF` — **per-spec** override только для spec `NAME`.

## Env-переменная PYBUGGY_REF

Git-ref можно задать через env-переменную `PYBUGGY_REF` (без опции команды). Она действует как глобальный ref по
умолчанию, когда ни per-spec, ни явный глобальный `--ref` не заданы — удобно для CI и единого ref сразу для нескольких
репозиториев:

    export PYBUGGY_REF=v2
    pybuggy endpoint pull                      # все спеки по ref v2 (если нет --ref/git.ref)
    PYBUGGY_REF=v2 pybuggy endpoint pull --spec client

`PYBUGGY_REF` заполняется корневой группой CLI при загрузке `.env` (см. корневую ячейку) и читается `run_pull` из
`os.environ`. Она **не** перебивает per-spec (`NAME:REF`) и явный глобальный `--ref` — только заполняет «провал»
между ними и `git.ref`.

## Поведение

- Spec с `git` → shallow-clone `git.url` (depth=1) во временную директорию по **эффективному ref**, копирование
  `git.location` → `<project_root>/<location>` (перезапись, идемпотентно).
- Приоритет эффективного ref (per-spec): per-spec override (`NAME:REF`) → глобальный `--ref`/`ref` (если передан) →
  env-переменная `PYBUGGY_REF` (если задана в окружении) → `git.ref` из конфигурации → default branch.
  Отсутствие/`None` на любом уровне ⇒ переход к следующему; `None` в `git.ref` ⇒ default branch.
- Глобальный `--ref`/`ref` применяется ко всем выбранным spec за один вызов, но per-spec `NAME:REF` перебивает его для
  указанной spec. Per-spec ref с именем, отсутствующим в конфигурации, → `click.ClickException`. Для конфигов со spec из
  разных репозиториев: глобальный `--ref` без `--spec` применяется к каждому репозиторию и требует, чтобы ветка/тег
  существовали во всех них; `PYBUGGY_REF` и per-spec `NAME:REF` снимают это требование для остальных репозиториев.
- Spec без `git` → skip (local-only), без ошибки.
- `--spec <name>` сужает до одной spec.
- Конфиг грузится из фиксированного пути (`.goga/tools/pybuggy/config.yml`) через `load_config()`.
- Ошибки клона/отсутствия пути → `click.ClickException` (единый ненулевой exit).

## Предусловия

- Конфиг валиден и лежит по фиксированному пути (см. `goga_tool_pybuggy.config`).
- Токены в clone-URL не встраиваются — полагайтесь на git credential helpers.
- Репозиторий — read-only (без commit/push).
- `PYBUGGY_REF` опциональна; корневая группа CLI загружает `.env` (явный `--env-file` или `.env` из CWD) до запуска
  команды, поэтому `PYBUGGY_REF` может быть задана как в окружении оболочки, так и через `.env`.
```

---

### Cell: `goga_tool_pybuggy/` (ROOT) (MODIFY)

#### Diff
- **ADD** Header `Usages`: `python-dotenv: .goga/usages/cooks/python-dotenv.md`.
- **CHANGE** Header `Annotations`: добавить `Use \`python-dotenv\` ...`; расширить строку `click` (упомянуть `--env-file` eager-callback); расширить описание роли ячейки (загрузка .env до подкоманд).
- **CHANGE** Body `main()` annotation: Algorithm (глобальная опция `--env-file` + eager-callback `ctx.obj = load_env(env_file)`), Requirements (флаг до подкоманды, ctx.obj до подкоманды), Constraints (no `--config`, только `--env-file`).
- **ADD** Body Routine `load_env(env_file: str | None) -> ctx: EnvContext` (location `env.py`).
- **ADD** Body Entity `EnvContext(env_path: str | None, values: dict[str, str])` (location `env.py`) + properties `env_path`, `values`.
- **NO CHANGE** Body `retries(...)`, embedding `->install: {}`; Header `Imports`.
- **CHANGE** Footer `Description` (добавить упоминание загрузки .env).
- **MODIFY** `.usages/assembly.md` — новая секция «Загрузка .env», обновлены «Точка входа»/«Сборка CLI»/«Статичный конфиг»/«Предусловия».

#### Full CODEMANIFEST (`goga_tool_pybuggy/CODEMANIFEST`)

```yaml
Imports:
  - Types: [pull_cmd]
    From: goga_tool_pybuggy/commands/pull
  - Types: [list_cmd]
    From: goga_tool_pybuggy/commands/list
  - Types: [info_cmd]
    From: goga_tool_pybuggy/commands/info
  - Types: [generate_cmd]
    From: goga_tool_pybuggy/commands/generate
  - Types: [init_cmd]
    From: goga_tool_pybuggy/commands/init
  - Types: [install]
    From: goga_tool_pybuggy/plugin

Usages:
  conventions: .goga/usages/conventions.md
  click: .goga/usages/cooks/click.md
  python-dotenv: .goga/usages/cooks/python-dotenv.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `click` for the root group, the endpoint subgroup, command registration, the top-level init command, and the global --env-file option with its eager-callback.
  Use `python-dotenv` for loading the .env file into os.environ with override=False.

  This cell is the package composition root: it owns the root group `main`, loads the .env environment before any subcommand runs, and assembles the full CLI.
  Use relative imports inside the cell.

---

"main()":
  location: cli.py
  annotations: |
    Root Click group of the pybuggy CLI; exposes the global --env-file option, the endpoint subgroup with the pull/list/info/generate commands, and the top-level init command.

    Algorithm:
    1. Define the `main` root group via `click`.
    2. Attach the global --env-file option to `main` (eager — evaluated before any subcommand).
    3. In the eager-callback: call `load_env` (passing the --env-file value) and store the returned `EnvContext` on ctx.obj.
    4. Define the endpoint subgroup via `click`.
    5. Register `pull_cmd`, `list_cmd`, `info_cmd`, `generate_cmd` on the endpoint subgroup.
    6. Attach the endpoint subgroup to `main`.
    7. Register `init_cmd` on `main` directly (top-level — not under the endpoint subgroup).
    8. Export `main` via __all__.

    Requirements:
    - The global --env-file flag is parsed at the group level, so it MUST precede the subcommand (e.g. pybuggy --env-file ./my.env endpoint pull); placing it after the subcommand is a click usage error.
    - The env is loaded and ctx.obj is set before any subcommand is invoked.
    - Assembly runs at package import (in __init__.py), before any subcommand is invoked.
    - The package entry point resolves to this `main` (pyproject: pybuggy = "goga_tool_pybuggy:main").
    - python -m goga_tool_pybuggy runs via __main__.py (from goga_tool_pybuggy import main; main()).

    Constraints:
    - Do not introduce a --config option; config loading stays per-command via `load_config`.
    - --env-file is the only global option added by this feature.

    Use `click` for the group, subgroup, and the --env-file eager-callback.
    Use `python-dotenv` for the .env loading performed by `load_env`.

"load_env(env_file: str | None) -> ctx: EnvContext":
  location: env.py
  annotations: |
    Resolve the env-file, load its key→value pairs into os.environ (override=False), and return an `EnvContext` carrying the resolved path and the loaded values.

    `env_file`: explicit path from --env-file, or None (implicit `.env` in CWD).
    `ctx`: the `EnvContext` stored on ctx.obj by `main`.

    Algorithm:
    1. Resolve the path: if `env_file` is not None, treat it as explicit — it MUST exist, otherwise raise click.ClickException; if `env_file` is None, use `.env` in the CWD and, when it is absent, load nothing (silent, no error).
    2. When a resolved file exists, parse it into `values` (key→value) and apply it to os.environ with override=False (already-set variables are never overwritten) via `python-dotenv`.
    3. Return an `EnvContext` with the resolved path (or None) and the loaded key→value values.

    Requirements:
    - override=False — already-set environment variables are never overwritten.
    - An explicit --env-file pointing at a missing file raises click.ClickException.
    - An implicit `.env` absent from the CWD is silent (no error, empty values, env_path None).
    - env loading happens before any subcommand runs.

    Constraints:
    - Do not read PYBUGGY_REF or any other specific variable here — loading is generic; consumers read os.environ themselves.

    Use `python-dotenv` for .env parsing and os.environ application.
    Use `conventions` for code writing rules and testing.

"EnvContext(env_path: str | None, values: dict[str, str])":
  location: env.py
  annotations: |
    Context-object stored on click ctx.obj by `main`; carries the resolved env-file path and the loaded key→value pairs.

    `env_path`: resolved env-file path; None when no file was loaded (silent absent implicit `.env`).
    `values`: loaded key→value pairs from the env-file.

    Requirements:
    - pydantic model with kw_only=True (all data models are pydantic per `conventions`); defaults env_path=None, values={}.
    - Exposed on the ROOT facade via __all__ (available to consumers/tests).

    Constraints:
    - Pure data carrier — no behavior beyond the two properties.
  properties:
    "env_path -> str | None": |
      Resolved env-file path; None when no file was loaded.
    "values -> dict[str, str]": |
      Loaded key→value pairs from the env-file.

"retries(max_runs: int, *, min_passes: int | None, delay: int | float | None) -> decorator: Callable":
  location: tools.py
  annotations: |
    Decorator-factory that wraps the flaky library to rerun a test up to `max_runs` times, requiring `min_passes` successes, with an optional `delay` between reruns. Exposed on the package facade for consumer test suites.

    `max_runs`: maximum number of test runs (required, positive int)
    `min_passes`: minimum successful runs required for the test to pass; when None, flaky derives its own default
    `delay`: seconds to sleep between reruns; when None, reruns run immediately and no rerun filter is applied
    `decorator`: the flaky decorator to apply to a test function

    Algorithm:
    1. Build a rerun filter: None when `delay` is None; otherwise a callable that sleeps `delay` seconds and returns True (unconditional rerun).
    2. Delegate to flaky with `max_runs`, `min_passes`, and the rerun filter, and return its decorator.

    Requirements:
    - `max_runs` must be a positive int.
    - The rerun filter is wired in only when `delay` is not None, so a None delay never reaches the sleep.

    Constraints:
    - The rerun filter always returns True — reruns are unconditional up to `max_runs`.

    Use `conventions` for code writing rules and testing.

->install: {}

---

Author: Goga
CreatedAt: 08/07/26
Description: |
  Package composition root — owns the root CLI group main, assembles the endpoint subgroup
  (pull/list/info/generate), registers the top-level `init` command, and loads the .env environment before any command runs.
```

#### .usages file: `goga_tool_pybuggy/.usages/assembly.md` (MODIFY)

```md
# pybuggy — сборка и запуск CLI (composition root)

## Предметная область

Шаблоны потребления корневой ячейки `goga_tool_pybuggy/`: пакетный фасад, где определяется корневая Click-группа
`main`, загружается `.env` в `os.environ` до запуска команды, и собирается полный CLI. Аудитория — интеграторы,
запускающие `pybuggy` (консольная команда или `python -m goga_tool_pybuggy`), и внешние импортёры фасада
(`from goga_tool_pybuggy import main`).

## Точка входа

Пакетный фасад `pybuggy` выставляет корневую группу `main`:

- Консольная команда (entry point в `pyproject.toml`):

      pybuggy endpoint list

- Модульный запуск (`goga_tool_pybuggy/__main__.py`):

      python -m goga_tool_pybuggy endpoint list

- Глобальная опция `--env-file` (ДО подкоманды) — загрузка `.env` в `os.environ` перед запуском команды:

      pybuggy --env-file ./my.env endpoint list      # явный файл (должен существовать)
      pybuggy endpoint list                          # неявный .env из CWD (отсутствие — тихо)

- Скаффолдинг артефактов по спеке (`endpoint generate`, опции `-s/--spec`, `-f/--force`):

      pybuggy endpoint generate -s shop
      pybuggy endpoint generate --spec shop --force

- Bootstrap consumer-usages (top-level `init`, без опций):

      pybuggy init
      python -m goga_tool_pybuggy init

- Программный импорт фасада:

      from goga_tool_pybuggy import main

## Загрузка .env (глобальная опция --env-file и ctx.obj)

Корневая группа `main` — единая точка загрузки переменных окружения. Глобальная опция `--env-file` парсится на
уровне группы, поэтому флаг обязан идти ДО подкоманды:

      pybuggy --env-file ./my.env <cmd>     # ✓ exit 0
      pybuggy <cmd> --env-file ./my.env     # ✗ exit 2 (No such option)

Два режима загрузки (через `load_env` в `env.py`):

- **Явный файл** (`--env-file FILE`): файл обязан существовать, иначе `click.ClickException`. Грузится в `os.environ`.
- **Неявный `.env` из CWD** (флаг отсутствует): если `.env` есть в CWD — грузится; если нет — тихо (без ошибки, без значений).

`override=False` — уже заданные в окружении переменные НЕ перезаписываются. Загрузка выполняется ДО запуска любой
подкоманды (eager-callback корневой группы).

Контекст-объект `ctx.obj` (тип `EnvContext`, `env.py`) несёт разрешённый путь env-файла (`env_path: str | None`) и
загруженные значения (`values: dict[str, str]`). Это осознанное введение pass-object в контракт root-ячейки (ранее
«нет pass-object») — он носит env-контекст; конфиг по-прежнему грузится командами сами через `load_config()`.

> Примечание: команда `pull` читает env-переменную `PYBUGGY_REF` напрямую из `os.environ` (см. `commands/pull`), а не
> из `ctx.obj` — слабая связность между ячейками сохранена.

## Сборка CLI

Сборка живёт в модуле `goga_tool_pybuggy/cli.py` (принадлежит корневой ячейке) и выполняется при импорте:

1. Определяется корневая группа `main` (с глобальной опцией `--env-file` + eager-callback загрузки env).
2. Создаётся подгруппа `endpoint`.
3. В `endpoint` регистрируются команды `pull_cmd`, `list_cmd`, `info_cmd`, `generate_cmd`
   (из `goga_tool_pybuggy/commands/{pull,list,info,generate}`).
4. Подгруппа `endpoint` добавляется в `main`.
5. На `main` напрямую регистрируется top-level команда `init_cmd` (из `goga_tool_pybuggy/commands/init`).
6. `main` экспортируется через `__all__`. На фасаде также доступны `load_env`, `EnvContext`.

Top-level на `main`: `init`.
В `endpoint` входят: `pull`, `list`, `info`, `generate`.

## Статичный конфиг

Путь до конфига фиксирован (`.goga/tools/pybuggy/config.yml`, см. `goga_tool_pybuggy.config.CONFIG_PATH`).
Опции `--config` нет — команды грузят конфиг сами через `load_config()` (без аргумента). Pass-object `ctx.obj`
существует, но несёт только env-контекст (`EnvContext`), а не конфиг.

## Предусловия и побочные эффекты

- `import goga_tool_pybuggy` триггерит полную сборку CLI (импорт `click` и всех ячеек команд).
- Запуск команд требует валидный конфиг по фиксированному пути; загрузка и валидация — через `load_config` в подкоманде.
- `--env-file` (явный) или `.env` из CWD (неявный) грузятся в `os.environ` (`override=False`) до запуска команды;
  значения доступны всем подкомандам через `os.environ` (например `PYBUGGY_REF` для `pull`).
- `init` — top-level команда и НЕ требует конфиг pybuggy: работает с goga-project-конфигом потребителя
  (`<cwd>/.goga/config.yml`), читает usages из установленного пакета.
```

---

### Supporting project artifacts (non-cell)

#### `.goga/usages/cooks/python-dotenv.md` (CREATE)

```md
# python-dotenv — загрузка .env в os.environ (библиотека)

## Предметная область

`python-dotenv` — библиотека для чтения `.env`-файлов и применения переменных в `os.environ`. Используется корневой
ячейкой `goga_tool_pybuggy/` для единой загрузки окружения CLI до запуска команды.

```python
from dotenv import dotenv_values, load_dotenv
```

Эта практика описывает только API `python-dotenv`. Как CLI применяет загрузку — в клеточной `.usages/assembly.md`
корневой ячейки.

---

## Применение .env в os.environ

`load_dotenv` читает файл и применяет пары key=value в `os.environ`. `override=False` (по умолчанию) — уже заданные в
окружении переменные НЕ перезаписываются:

```python
from dotenv import load_dotenv

load_dotenv("./my.env")                  # применить в os.environ; override=False по умолчанию
load_dotenv("./my.env", override=True)   # перезаписать существующие (НЕ используется в pybuggy)
load_dotenv(".env")                      # неявный файл из CWD
```

`load_dotenv` возвращает `True`, если файл найден и прочитан, и `False`, если файл отсутствует — это позволяет
различать «явный файл обязан существовать» (отсутствие → ошибка) и «неявный .env опционален» (отсутствие → тихо).

## Чтение значений без побочных эффектов

`dotenv_values` возвращает `dict[str, str | None]` пар без записи в `os.environ` — удобно для формирования
контекст-объекта (`EnvContext.values`) и контроля применения:

```python
from dotenv import dotenv_values

values = dotenv_values("./my.env")   # dict key→value; None → переменная без значения
```

## Поведение и ограничения

- `override=False` (поведение pybuggy): переменные, уже заданные в окружении (shell/CI), не перезаписываются значениями из `.env`.
- Ключ без значения (`KEY=`) → `None` в `dotenv_values`; в `os.environ` задаётся пустая строка.
- Комментарии (`# ...`) и пустые строки игнорируются; кавычки вокруг значений снимаются.
- Файл читается как UTF-8.
```

#### `pyproject.toml` (MODIFY — dependency declaration, non-DSL)

- **ADD** в `[project] dependencies` зависимость `python-dotenv` с минимальной версией:
  ```toml
  "python-dotenv>=1.2.2",
  ```
- Минимальная версия `1.2.2` = текущая в venv (фиксирует транзитивную зависимость как контрактную; по `conventions`:
  каждая сторонняя библиотека объявляется с минимальной версией).
- Никаких других изменений в `pyproject.toml`.

---

## Dependency Map

```text
   config (leaf)                            plugin (leaf)
       ▲                                        ▲
       │ Imports: load_config, Config,          │ Imports: install
       │         SpecEntry, GitEntry,           │ (embedding ->install в ROOT)
       │         usage `configuration`          │
       │                                        │
   commands/pull ◄── Imports(pull_cmd) ── ROOT (goga_tool_pybuggy/)
   run_pull reads os.environ["PYBUGGY_REF"]     │
            ▲                                  │ main() eager-callback:
            │ runtime os.environ               │   load_env(env_file) -> EnvContext
            │ (override=False)                 │   writes os.environ; ctx.obj = EnvContext
            └──────────────────────────────────┘
                  (runtime-связь через os.environ — НЕ Imports)
```

- **Новых import-рёбер фича не вводит.**
- ROOT → `load_env` → пишет `os.environ` (`override=False`) → `ctx.obj = EnvContext`.
- pull ← читает `os.environ["PYBUGGY_REF"]` (новый уровень приоритета ref).
- Слабая связность ROOT↔pull сохранена (через `os.environ`, без перекрёстных Imports).

Порядок leaf→root: `config`/`plugin` (leaves) → `commands/*` → `ROOT` (composition root). Циклов нет.

---

## Verification Checklist

- [ ] **pull CODEMANIFEST**: `run_pull` Algorithm 4b содержит уровень `PYBUGGY_REF` между global `--ref` и `GitEntry` ref; добавлены Requirements/Constraints маркеры про `PYBUGGY_REF`. Header/`pull_cmd`/`SmartParam`/footer не изменены.
- [ ] **ROOT CODEMANIFEST**: Header `Usages` содержит `python-dotenv`; Header `Annotations` ссылается на `python-dotenv` и `--env-file`; `main()` Algorithm включает eager-callback `ctx.obj = load_env(env_file)`; объявлены `load_env` (Routine) и `EnvContext` (Entity) в `env.py`; `retries`/`->install` не изменены; DSL `location`-правило соблюдено (`env.py` на уровне корневой ячейки).
- [ ] **`.goga/usages/cooks/python-dotenv.md`**: создан; описывает `load_dotenv` (`override=False`), `dotenv_values`, поведение; ссылается на корневую `assembly.md` для применения.
- [ ] **`.usages/assembly.md`**: добавлена секция загрузки `.env`; «Статичный конфиг» уточнён (pass-object несёт env, не конфиг); примеры `--env-file` ДО подкоманды.
- [ ] **`.usages/pull.md`**: добавлена секция «Env-переменная `PYBUGGY_REF`»; приоритет в «Поведение» обновлён.
- [ ] **`pyproject.toml`**: `python-dotenv>=1.2.2` добавлен в `[project] dependencies`.
- [ ] **Нет новых Imports-рёбер**: pull читает `os.environ`, не импортирует ROOT; циклов нет.
- [ ] **DSL-синтаксис**: ключи в точной нотации (case-sensitive), `---` разделяют Header/Body/Footer, `location` с расширением без обхода каталогов.
- [ ] **Acceptance Criteria** (все 7): `--env-file` до подкоманды; тихий неявный `.env`; `override=False`; `ctx.obj = EnvContext(path, values)`; `PYBUGGY_REF` в `run_pull`; `python-dotenv>=1.2.2` в deps; поддержка handler-тестирования (`load_env`, `run_pull` напрямую).
- [ ] `goga lint` (когда неродственные AST-проблемы разрешатся) — без новых ошибок по изменённым ячейкам.
