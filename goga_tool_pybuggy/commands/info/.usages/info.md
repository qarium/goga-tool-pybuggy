# goga_tool_pybuggy.commands.info — команда endpoint info

## Предметная область

Шаблоны потребления cell `goga_tool_pybuggy/commands/info`: вывод деталей эндпоинта по его id (одному или
нескольким) в виде JSON. Аудитория — регистрация в CLI (`info_cmd`) и тесты (`run_info` напрямую).

## Вызов handler-функции

`run_info` — тестируемая точка входа (Click-обёртка `info_cmd` связывает позиционный variadic
`endpoint-ids` и опцию `--spec`, вызывает `run_info`):

    from goga_tool_pybuggy.commands.info import run_info

    run_info(["clients_startup_get"])                        # только указанный эндпоинт, поиск по всем spec
    run_info(["clients_startup_get"], spec_name="client")    # в одной spec
    run_info(["clients_startup_get", "health_get"])          # несколько эндпоинтов
    run_info()                                               # None/пусто — все эндпоинты выбранных spec

## Поведение

- По всем (или отфильтрованным `--spec`) спекам: разобрать → извлечь эндпоинты → собрать те, чей
  `id` входит в `endpoint_ids`.
- Нет совпадений → `click.ClickException` («endpoint not found: <id>»).
- Одно совпадение → JSON-объект; несколько (коллизия id в разных spec или несколько запрошенных id)
  → JSON-массив.
- Конфиг грузится из фиксированного пути через `load_config()`. Формат задаёт `goga_tool_pybuggy.output.render_info`.

## Фильтр по endpoint-id

Позиционный variadic-аргумент `endpoint-ids` ограничивает вывод подмножеством эндпоинтов по их id
(`Endpoint.id`, те же id, что в командах `endpoint list`/`endpoint generate` — строка вида
`clients_startup_get`):

    pybuggy endpoint info clients_startup_get health_get
    pybuggy endpoint info -s client clients_startup_get   # опция — до позиционных id

Эндпоинты отбираются только среди выбранных спек (`--spec` или все):

- Аргумент не передан — выводятся все эндпоинты выбранных спек (поведение не изменилось относительно
  «показать всё»).
- Пустой список / `None` у handler-а — то же самое (no-op фильтра = все).
- id найден хотя бы в одной выбранной спеке — выводятся только совпадающие эндпоинты.
- id не найден ни в одной выбранной спеке → `click.ClickException("endpoint not found: <id>")`,
  ненулевой exit; при нескольких отсутствующих id они перечисляются все (отсортированы), ничего не
  выводится.

У handler-а `run_info` фильтр — первый параметр `endpoint_ids: list[str] | None`. Валидация
выполняется до вывода, поэтому неизвестный id не печатает частичного результата.

## Предусловия

- Файлы spec должны быть в `location` (после `pull` или вручную).
- id эндпоинта строится по алгоритму `build_endpoint_id`.
- Конфиг валиден и лежит по фиксированному пути (см. `goga_tool_pybuggy.config`).
- Команда read-only — не модифицирует spec/конфиг.
