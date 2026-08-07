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

> Примечание: команда `pull` получает `PYBUGGY_REF` через `envvar=` опции `--ref` в декораторе click (click читает
> `os.environ`; см. `commands/pull`), а не из `ctx.obj` — слабая связность между ячейками сохранена.

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
