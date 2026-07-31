# pybuggy.commands.pull — команда endpoint pull

## Предметная область

Шаблоны потребления cell `pybuggy/commands/pull`: скачивание spec из git-источников в локальные `location`. Аудитория — регистрация в CLI (`pull_cmd`) и тесты (`run_pull` напрямую).

## Вызов handler-функции

`run_pull` — тестируемая точка входа (Click-обёртка `pull_cmd` только связывает опции и вызывает `run_pull`):

    from pybuggy.commands.pull import run_pull

    run_pull(spec_name=None)              # тянуть все спеки
    run_pull(spec_name="client")          # только одну spec
    run_pull(spec_name="client", ref="v2")  # та же spec, но с переопределением ref (глобальный ref)
    run_pull(spec_name=None, ref=(("client", "v1"), ("server", "v2")))  # per-spec ref в одном вызове

CLI-форма (`pull_cmd`):

    pybuggy endpoint pull                       # тянуть все спеки
    pybuggy endpoint pull --spec client         # только одну spec
    pybuggy endpoint pull --ref v2              # переопределить ref для всех тянущихся спек (глобальный)
    pybuggy endpoint pull --spec client --ref v2
    pybuggy endpoint pull --ref client:v1 --ref server:v2   # разные ref для разных spec в одном вызове
    pybuggy endpoint pull --ref v2 --ref server:v3          # глобальный v2, но server — на v3

`--ref` повторяемый (`multiple=True`) и парсится `SmartParam`:
- без `:` — **глобальный** ref, применяется ко всем выбранным spec;
- `NAME:REF` — **per-spec** override только для spec `NAME`.

Глобальный ref (как CLI, так и прямая строка `ref="v2"`) по-прежнему применяется ко всем выбранным spec за один вызов (в отличие от `git.ref` в конфиге, который задаётся per-spec). Если нужны разные ref для разных spec — передайте несколько `NAME:REF` в одном вызове (или, как раньше, серией `--spec` + `--ref`).

## Поведение

- Spec с `git` → shallow-clone `git.url` (depth=1) во временную директорию по **эффективному ref**, копирование `git.location` → `<project_root>/<location>` (перезапись, идемпотентно).
- Приоритет эффективного ref (per-spec): per-spec override (`NAME:REF`) → глобальный `--ref`/`ref` (если передан) → `git.ref` из конфигурации → default branch. `None` на любом уровне означает переход к следующему; `None` в `git.ref` ⇒ default branch.
- Глобальный `--ref`/`ref` (строка или значение без `:`) применяется **ко всем** выбранным spec за один вызов, но per-spec `NAME:REF` перебивает его для указанной spec. Per-spec ref, имя которого отсутствует в конфигурации, → `click.ClickException` («unknown spec in --ref»). Spec, присутствующая в конфиге, но отсечённая `--spec`, ошибки не вызывает (её per-spec ref просто не применяется). Для конфигов со spec из разных репозиториев: глобальный `--ref` без `--spec` применяется к каждому репозиторию и требует, чтобы ветка/тег существовали во всех них; per-spec `NAME:REF` снимает это требование для остальных репозиториев.
- Spec без `git` → skip с WARNING («no remote source; treated as local»), без ошибки.
- `--spec <name>` сужает до одной spec.
- Конфиг грузится из фиксированного пути (`.goga/tools/pybuggy/config.yml`) через `load_config()`.
- Ошибки клона/отсутствия пути → `click.ClickException` (единый ненулевой exit).

## Предусловия

- Конфиг валиден и лежит по фиксированному пути (см. `pybuggy.config`).
- Токены в clone-URL не встраиваются — полагайтесь на git credential helpers.
- Репозиторий — read-only (без commit/push).