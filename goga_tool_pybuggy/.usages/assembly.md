# pybuggy — сборка и запуск CLI (composition root)

## Предметная область

Шаблоны потребления корневой ячейки `pybuggy/`: пакетный фасад, где определяется корневая Click-группа `main`
и собирается полный CLI. Аудитория — интеграторы, запускающие `pybuggy` (консольная команда или
`python -m pybuggy`), и внешние импортёры фасада (`from pybuggy import main`).

## Точка входа

Пакетный фасад `pybuggy` выставляет корневую группу `main`:

- Консольная команда (entry point в `pyproject.toml`):

      pybuggy endpoint list

- Модульный запуск (`pybuggy/__main__.py`):

      python -m pybuggy endpoint list

- Скаффолдинг артефактов по спеке (`endpoint generate`, опции `-s/--spec`, `-f/--force`):

      pybuggy endpoint generate -s shop
      pybuggy endpoint generate --spec shop --force

- Bootstrap consumer-usages (top-level `init`, без опций):

      pybuggy init
      python -m pybuggy init

- Программный импорт фасада:

      from pybuggy import main

## Сборка CLI

Сборка живёт в модуле `pybuggy/cli.py` (принадлежит корневой ячейке) и выполняется при импорте:

1. Определяется корневая группа `main`.
2. Создаётся подгруппа `endpoint`.
3. В `endpoint` регистрируются команды `pull_cmd`, `list_cmd`, `info_cmd`, `generate_cmd`
   (из `pybuggy/commands/{pull,list,info,generate}`).
4. Подгруппа `endpoint` добавляется в `main`.
5. На `main` напрямую регистрируется top-level команда `init_cmd` (из `pybuggy/commands/init`).
6. `main` экспортируется через `__all__`.

Top-level на `main`: `init`.
В `endpoint` входят: `pull`, `list`, `info`, `generate`.

## Статичный конфиг

Путь до конфига фиксирован (`.goga/tools/pybuggy/config.yml`, см. `pybuggy.config.CONFIG_PATH`).
Опции `--config` и pass-object нет — команды грузят конфиг сами через `load_config()` (без аргумента).

## Предусловия и побочные эффекты

- `import pybuggy` триггерит полную сборку CLI (импорт `click` и всех ячеек команд).
- Запуск команд требует валидный конфиг по фиксированному пути; загрузка и валидация — через
  `load_config` в подкоманде.
- `init` — top-level команда и НЕ требует конфиг pybuggy: работает с goga-project-конфигом потребителя
  (`<cwd>/.goga/config.yml`), читает usages из установленного пакета.