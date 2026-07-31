# goga_tool_pybuggy.commands.list — команда endpoint list

## Предметная область

Шаблоны потребления cell `goga_tool_pybuggy/commands/list`: вывод эндпоинтов, сгруппированных по spec. Аудитория — регистрация в CLI (`list_cmd`) и тесты (`run_list` напрямую).

## Вызов handler-функции

`run_list` — тестируемая точка входа (Click-обёртка `list_cmd` связывает опции и вызывает `run_list`):

    from goga_tool_pybuggy.commands.list import run_list

    run_list(spec_name=None)        # все спеки
    run_list(spec_name="client")    # одна spec

## Поведение

Для каждой (отфильтрованной) spec: разобрать файл в `location` → извлечь эндпоинты → напечатать текстовый блок:

    client (.specs/openapi/client/client-openapi.yaml)
    * clients_startup_get -> [GET] /clients/startup

Конфиг грузится из фиксированного пути через `load_config()`. Формат задаёт `goga_tool_pybuggy.output.render_list`.

## Предусловия

- Файлы spec должны быть в `location` (после `pull` или вручную).
- Конфиг валиден и лежит по фиксированному пути (см. `goga_tool_pybuggy.config`).
- Команда read-only — не модифицирует spec/конфиг.