# goga_tool_pybuggy.commands.init — инициализация goga-проекта и bootstrap consumer-usages ячейки api

## Предметная область

Команда `pybuggy init` под капотом **инициализирует goga-проект** (создаёт при отсутствии `.goga/config.yml`; при
наличии — спрашивает, пересоздавать ли) и затем доставляет consumer-usages ячейки `api` (и её подклеток) в проект, где
она вызвана, чтобы goga-агент потребителя знал, как пользоваться goga_tool_pybuggy. Аудитория — интегратор,
подключающий pybuggy в свой проект (`pip install pybuggy`), и goga-агент потребителя.

Инициализация goga-проекта выполняется in-process пакетом `goga` (per-field методы `goga.init.Questionnaire` +
`FileGenerator.generate`; `InitLogic` не используется): интерактивный опрос + генерация `.goga/config.yml`
(language/build/pipeline/codemanifest), `.goga/usages/conventions.md`, опционально Dockerfile. Затем команда копирует
cell-usages `api.md`/`asserts.md` в `.goga/usages/cooks/pybuggy/` и регистрирует их
в `.goga/config.yml` под `codemanifest.usages` ключами `pybuggy-api`/`pybuggy-asserts`, а также дополняет
`codemanifest.annotations` ссылающейся строкой на каждый usage (`` `pybuggy-api` `` / `` `pybuggy-asserts` `` с кратким
описанием назначения); существующий текст аннотаций сохраняется. Источник usages — установленный пакет (не cwd);
поведение идемпотентно.

---

## Построение .goga/tools/pybuggy/config.yml

Помимо инициализации goga-проекта и bootstrap usages, `pybuggy init` интерактивно строит конфигурацию инструмента
`.goga/tools/pybuggy/config.yml` (плагинные опции + секция `specs`): при отсутствии файла — сразу, при наличии — после
подтверждения (см. «Перезапись» в `.usages/config-build.md`).

Что опрашивается (интерактивный шаг, изолированный в `build_pybuggy_config`):
- Скалярные ключи плагина: `base_url` (обязательный — Jinja2-шаблон URL; пустой ввод переспрашивается и не может быть
  пропущен), `timeout`, `data_key`, `error_key`, `retries`, `assert_timeout`, `assert_delay`, `assert_field_class`,
  `assert_response_class` — каждый по одному; необязательные можно пропустить (Enter → пропуск).
- `headers` и `loader` НЕ опрашиваются — записываются закомментированными примерами.
- `specs`: для каждой spec последовательно опрашиваются имя, `type` (`swagger`|`openapi`), `location` (обязательно) и
  опциональный git-блок (`url`, `location`, `ref`); поддерживается несколько specs. Требуется **минимум одна** spec —
  конфиг без specs невалиден (первое имя spec переспрашивается, пока не введено, как `base_url`).

Перезапись: если `.goga/tools/pybuggy/config.yml` **отсутствует** — он строится без вопросов; если **существует** —
`run_init` спрашивает `click.confirm` (по умолчанию `no`), пересобирать ли его, и пересобирает только при `yes`. При
отказе шаг пропускается, остальной `init` продолжается (exit 0). Решение о пересоздании живёт в оркестраторе `run_init`;
сам `build_pybuggy_config` (и программный вызов напрямую) всегда перезаписывает файл без проверок.

Эмиссия (`write_pybuggy_config`, чистая, без TTY): активные значения пишутся как `key: value`; пропущенные необязательные
скаляры, а также `headers` и `loader` — закомментированными записями (`# key:`) с пояснением; `specs` — активным YAML.
Сгенерированный файл валиден для config-ячейки (`load_config`/`Config`): присутствует `specs` с обязательными полями
`SpecEntry`; скалярные плагинные ключи игнорируются `Config` (extra=ignore).

---

## Точка входа

- Консольная команда (top-level, не под `endpoint`): `pybuggy init`
- Модульный запуск: `python -m goga_tool_pybuggy init`
- Программный импорт фасада:
      from goga_tool_pybuggy.commands.init import run_init, run_goga_init, init_cmd, register_usages, register_annotations

---

## Шаблон: первый запуск в свежем (не-goga) проекте

В проекте без `.goga/config.yml`:
1. Команда **интерактивно** инициализирует goga-проект (вопросы об агенте/образе/...; язык зафиксирован `python`).
2. По завершении создаётся полный `.goga/config.yml`, затем регистрируются usages goga_tool_pybuggy.

      cd my-consumer-project
      pybuggy init        # → опросник goga, затем регистрация pybuggy usages

Результат:
- `.goga/config.yml` — полный goga-конфиг + блок `codemanifest.usages` с `pybuggy-api`/`pybuggy-asserts` + блок
  `codemanifest.annotations` со ссылающимися строками.
- `.goga/usages/cooks/pybuggy/api.md`, `.goga/usages/cooks/pybuggy/asserts.md`.

---

## Шаблон: запуск в уже инициализированном goga-проекте

Если `.goga/config.yml` уже существует — `run_init` спрашивает `click.confirm` (по умолчанию `no`), пересоздавать ли
goga-проект (перезапись `.goga/config.yml`; пользовательские codemanifest-записи сверх pybuggy могут быть потеряны).
При отказе опросник goga **не запускается**; сразу round-trip регистрация usages (существующие ключи/комментарии
сохранены). Аналогично для `.goga/tools/pybuggy/config.yml`: при наличии спрашивается, пересобирать ли его:

      # .goga/config.yml до запуска (с пользовательскими ключами)
      codemanifest:
        usages:
          conventions: .goga/usages/conventions.md   # не затирается
      # pybuggy init → спрашивает пересоздание goga/pybuggy конфигов; при отказе добавляет pybuggy-api,
      # pybuggy-asserts; conventions и комментарий на месте

---

## Идемпотентность

Повторный `pybuggy init` в уже инициализированном проекте: `run_init` спрашивает, пересоздавать ли goga-конфиг и
pybuggy-конфиг (`click.confirm`, по умолчанию `no`); при отказе обоих — goga-init и сборка pybuggy-конфига
пропускаются, скопированные `.md` перезаписываются (актуальные cell-usages пакета), уже зарегистрированные ключи и уже
ссылающиеся аннотации пропускаются. Флаги `--force`/`--dry-run` не предусмотрены.

---

## Exit codes

- `0` — успех (goga-проект готов/уже был готов + usages зарегистрированы).
- ненулевой код goga (`1`) — отмена/ошибка инициализации goga: в этом случае usages **не регистрируются**, `pybuggy init`
  завершается кодом goga.
- Ошибки bootstrap usages → `click.ClickException` (ненулевой exit).

---

## Программный usage (тесты/скрипты)

`run_init()` оперирует cwd как корнем вывода и **возвращает exit code (int)**:

      import pytest
      from goga_tool_pybuggy.commands.init import run_init

      def test_init_in_fresh_project(tmp_path, monkeypatch):
          monkeypatch.chdir(tmp_path)
          # заглушить интерактивный goga init, чтобы тесты не зависели от TTY:
          monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", lambda: 0)
          # заглушить интерактивное построение .goga/tools/pybuggy/config.yml (шаг run_init №3):
          monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.build_pybuggy_config", lambda: 0)
          assert run_init() == 0
          assert (tmp_path / ".goga/usages/cooks/pybuggy/api.md").exists()

      def test_goga_cancel_aborts(tmp_path, monkeypatch):
          monkeypatch.chdir(tmp_path)
          monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", lambda: 1)  # отмена
          assert run_init() == 1
          assert not (tmp_path / ".goga/usages/cooks/pybuggy/api.md").exists()  # usages не пишутся

Для прямой регистрации usages без discovery/копирования — `register_usages` (контракт не изменился); для дописывания
ссылающихся аннотаций в `codemanifest.annotations` — `register_annotations` (round-trip, идемпотентно по бэктик-ссылке).
Интерактивное построение `.goga/tools/pybuggy/config.yml` изолировано в `build_pybuggy_config` (testable-seam, в `__all__`;
возвращает exit code, не бросает — стабится monkeypatch по образцу `run_goga_init`); чистую эмиссию YAML тестируют напрямую
через `write_pybuggy_config` (без TTY): передают `scalar_values` (с пропусками) и `specs`, проверяют результат.

---

## Предусловия и побочные эффекты

- Требует установленный пакет `goga` (зависимость pybuggy) — для in-process инициализации goga-проекта.
- Пишет в `<cwd>/.goga/` (создаёт `.goga/usages/cooks/pybuggy/`, `.goga/config.yml`).
- Читает usages из **установленного** пакета `goga_tool_pybuggy.api` (`importlib.resources`), не из cwd — работает после
  `pip install pybuggy`, а не только из checkout.
- Discovery рекурсивен по `.usages/*.md` под ячейкой `api` — будущие подклетки подключаются без правки команды.
- Копирует только usages ячейки `api`; внутренние ячейки разработки (`config`/`spec`/`output`/...) не копируются.
- goga-init запускается при отсутствии `.goga/config.yml` (эвристика «не инициализирован») либо при согласии на
  пересоздание (`click.confirm`, по умолчанию `no`), когда файл существует.
- Цели записи — goga-project-конфиг `.goga/config.yml` (блоки `codemanifest.usages` и `codemanifest.annotations`)
  и `.goga/tools/pybuggy/config.yml` (плагинные опции + specs; строится при отсутствии или подтверждённом пересоздании;
  см. раздел «Построение .goga/tools/pybuggy/config.yml»).