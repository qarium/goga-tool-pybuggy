# goga_tool_pybuggy.commands.init — построение .goga/tools/pybuggy/config.yml

## Предметная область

Шаг команды `pybuggy init`, который на каждом вызове интерактивно строит файл конфигурации инструмента
`.goga/tools/pybuggy/config.yml` (плагинные опции + секция specs). Аудитория — интегратор, подключающий pybuggy,
и goga-агент потребителя.

## Что опрашивается

- Скалярные ключи плагина (источник — `PluginConfigKeys`, скалярные члены): base_url (обязательный, Jinja2-шаблон),
  timeout, data_key, error_key, retries, assert_timeout, assert_delay, assert_field_class, assert_response_class.
  Каждый опрашивается по одному; необязательные можно пропустить (Enter).
- headers и loader НЕ опрашиваются — записываются закомментированными примерами.
- specs — интерактивно: имя, type (swagger|openapi), location (обязательно), опциональный git (url, location, ref);
  поддерживается несколько спек.

## Перезапись и подтверждение

Если `.goga/tools/pybuggy/config.yml` уже существует — выводится подтверждение (y/N). При отказе (N) файл сохраняется,
шаг пропускается, остальной `init` продолжается. При согласии (y) файл перегенерируется.

## Программный usage (тесты/скрипты)

Интерактив изолирован в `build_pybuggy_config` (testable-seam, в `__all__`) — возвращает exit code, не бросает.
Тесты подменяют точку вызова (monkeypatch), как `run_goga_init`. Чистую эмиссию (активные значения + закомментированные
записи) тестируют напрямую через `write_pybuggy_config` (без TTY): передают `scalar_values` (с пропусками) и `specs` и
проверяют YAML.

## Предусловия и побочные эффекты

- Пишет в `<cwd>/.goga/tools/pybuggy/config.yml` (создаёт родительский каталог).
- Сгенерированный файл валиден для config-ячейки (`load_config`/`Config`): присутствует specs, обязательные поля
  `SpecEntry`; скалярные плагинные ключи игнорируются `Config` (extra=ignore).
- Источник перечня ключей — `PluginConfigKeys` (data-driven, без дублирования).
