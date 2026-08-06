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
