# goga_tool_pybuggy.commands.init — инициализация goga-проекта и bootstrap pybuggy-окружения потребителя

## Предметная область

Команда `pybuggy init` под капотом **инициализирует goga-проект** (создаёт при отсутствии `.goga/config.yml`; при
наличии — спрашивает, пересоздавать ли), **занимает слот `conventions`** тестовой конвенцией pybuggy и доставляет
consumer-usages ячейки `api` (и её подклеток) в проект, где она вызвана, чтобы goga-агент потребителя знал, как
пользоваться goga_tool_pybuggy, и генерирует корневой `conftest.py` целевого проекта (фиксированный шаблон; при
наличии файла — перезапись только по подтверждению), чтобы плагин включался в pytest-набор потребителя той же
командой. Аудитория — интегратор, подключающий pybuggy в свой проект (`goga install pybuggy`), и goga-агент
потребителя.

Инициализация goga-проекта выполняется in-process пакетом `goga` (per-field методы `goga.onboarding.Questionnaire` +
`FileGenerator.generate`; `InitLogic` не используется): интерактивный опрос + генерация `.goga/config.yml`
(language/build/pipeline/codemanifest), обязательно Dockerfile (`.goga/Dockerfile`, в который после генерации
дописывается установка `pybuggy` — `RUN goga install pybuggy -v 0.1.x`). Вопрос «Download base convention»
интегратору не задаётся: ключ `conventions` не попадает в ответы goga — скачивание языковой конвенции не выполняется,
инициализация проходит офлайн и завершается созданием `.goga/config.yml`.

Слот `conventions` (файл `.goga/usages/conventions.md` + ключ `codemanifest.usages` + строка аннотации) занимает
тестовая конвенция pybuggy: ассет `assets/conventions.md` установленного пакета копируется в
`.goga/usages/conventions.md`. Файл — package-owned наравне с `api.md`/`asserts.md`: **всегда** перезаписывается
версией пакета при каждом `pybuggy init`, без подтверждений и проверок существования; проекты с иным содержимым
слота (вкл. goga-конвенцию) мигрируют автоматически.

Затем команда копирует cell-usages `api.md`/`asserts.md` в `.goga/usages/cooks/pybuggy/` и регистрирует их
в `.goga/config.yml` под `codemanifest.usages` ключами `pybuggy-api`/`pybuggy-asserts` (а слот `conventions` — ключом
`conventions`), а также регистрирует `codemanifest.annotations`: строка с бэктик-ссылкой
(`pybuggy-api`/`pybuggy-asserts`/`conventions`) при наличии заменяется актуальной строкой, при отсутствии —
добавляется; строки без совпавшей ссылки сохраняются дословно. Источник usages — установленный пакет (не cwd);
поведение идемпотентно.

---

## Построение .goga/tools/pybuggy/config.yml

Помимо инициализации goga-проекта и bootstrap usages, `pybuggy init` интерактивно строит конфигурацию инструмента
`.goga/tools/pybuggy/config.yml` (плагинные опции + секция `specs`): при отсутствии файла — сразу, при наличии — после
подтверждения.

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

## Генерация <cwd>/conftest.py

Финальный шаг команды: создаёт корневой `conftest.py` целевого проекта по фиксированному шаблону (дословно):

```python
from dotenv import load_dotenv

load_dotenv()

from goga_tool_pybuggy import plugin

plugin.install()
```

`load_dotenv()` без аргументов (`override=False` — переменные CI/оператора не перезаписываются) вызывается до
`install()` — опции плагина резолвятся из `os.environ`. Если файл существует — `run_init` спрашивает `click.confirm`
(по умолчанию `no`); при отказе шаг пропускается с INFO-логом, остальной init завершается успешно (exit 0). Решение о
перезаписи живёт в оркестраторе `run_init`; чистая запись изолирована в `write_pybuggy_conftest` (программно доступна
в фасаде, всегда пишет переданный путь, без TTY — тестируется напрямую).

---

## Точка входа

- Консольная команда (top-level, не под `endpoint`): `pybuggy init`
- Модульный запуск: `python -m goga_tool_pybuggy init`
- Программный импорт фасада:
      from goga_tool_pybuggy.commands.init import run_init, run_goga_init, init_cmd, register_usages, register_annotations, write_test_convention

---

## Шаблон: первый запуск в свежем (не-goga) проекте

В проекте без `.goga/config.yml`:
1. Команда **интерактивно** инициализирует goga-проект (вопросы об агенте/образе/...; язык зафиксирован `python`;
   вопрос «Download base convention» не задаётся — сетевых вызовов нет, инициализация офлайн).
2. По завершении создаётся полный `.goga/config.yml`, затем доставляется тестовая конвенция и регистрируются usages.

      cd my-consumer-project
      pybuggy init        # → опросник goga (без базовой конвенции), затем слот conventions + регистрация usages

Результат:
- `.goga/config.yml` — полный goga-конфиг (включая top-level поле `dockerfile`) + блок `codemanifest.usages` с
  `conventions`/`pybuggy-api`/`pybuggy-asserts` + блок `codemanifest.annotations` со ссылающимися строками (строка
  `conventions`: «Use `conventions` for test code: pytest configuration, logging, and Allure reporting.»).
- `.goga/Dockerfile` — обязательный Dockerfile: `FROM {dockerfile_base_image}` + `RUN goga install pybuggy -v 0.1.x`
  (установка pybuggy через goga-installer с захардкоженной версией `0.1.x`; дописывается после генерации goga),
  всегда создаётся при goga-init.
- `.goga/usages/conventions.md` — тестовая конвенция pybuggy (текст ассета пакета).
- `.goga/usages/cooks/pybuggy/api.md`, `.goga/usages/cooks/pybuggy/asserts.md`.
- `<cwd>/conftest.py` — корневой conftest потребителя: фиксированный шаблон `load_dotenv()` → `plugin.install()`
  (см. «Генерация <cwd>/conftest.py»).

---

## Шаблон: запуск в уже инициализированном goga-проекте

Если `.goga/config.yml` уже существует — `run_init` спрашивает `click.confirm` (по умолчанию `no`), пересоздавать ли
goga-проект (перезапись `.goga/config.yml`; пользовательские codemanifest-записи сверх pybuggy могут быть потеряны).
При отказе опросник goga **не запускается**; слот `conventions` всё равно приводится к версии пакета, затем
выполняется round-trip регистрация usages. Аналогично для `.goga/tools/pybuggy/config.yml`:

      # .goga/config.yml до запуска (с пользовательскими ключами)
      codemanifest:
        usages:
          conventions: .goga/usages/conventions.md   # ключ остаётся (skip-existing)
        annotations: |
          Use `conventions` for code writing rules and testing.   # legacy-goga строка — будет заменена
      # pybuggy init → спрашивает пересоздание goga/pybuggy конфигов; при отказе: .goga/usages/conventions.md
      # перезаписывается ассетом пакета, ключ conventions пропускается (уже есть), legacy-строка аннотации
      # заменяется строкой pybuggy («Use `conventions` for test code: ...»), добавляются pybuggy-api/pybuggy-asserts;
      # прочие строки аннотаций и комментарии на месте

---

## Идемпотентность

Повторный `pybuggy init` в уже инициализированном проекте: `run_init` спрашивает, пересоздавать ли goga-конфиг,
pybuggy-конфиг и перезаписывать ли `conftest.py` (`click.confirm`, по умолчанию `no`); при отказе всех — goga-init,
сборка pybuggy-конфига и запись conftest пропускаются, существующий `conftest.py` не изменяется; скопированные `.md`
(вкл. `conventions.md`) перезаписываются версиями пакета; уже зарегистрированные ключи пропускаются; строки
аннотаций заменяются на идентичные (no-op) либо дописываются. Флаги `--force`/`--dry-run` не предусмотрены.

---

## Exit codes

- `0` — успех (goga-проект готов/уже был готов + слот conventions + usages зарегистрированы).
- ненулевой код goga (`1`) — отмена/ошибка инициализации goga: в этом случае слот `conventions` и usages **не
  доставляются/не регистрируются**, `pybuggy init` завершается кодом goga.
- Ошибки bootstrap usages (вкл. доставка конвенции) и ошибки записи conftest → `click.ClickException` (ненулевой exit).

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
          assert (tmp_path / ".goga/usages/conventions.md").exists()    # слот занят тестовой конвенцией
          assert (tmp_path / ".goga/usages/cooks/pybuggy/api.md").exists()
          assert (tmp_path / "conftest.py").exists()   # финальный шаг — фиксированный шаблон

      def test_goga_cancel_aborts(tmp_path, monkeypatch):
          monkeypatch.chdir(tmp_path)
          monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", lambda: 1)  # отмена
          assert run_init() == 1
          assert not (tmp_path / ".goga/usages/conventions.md").exists()   # слот не доставляется
          assert not (tmp_path / ".goga/usages/cooks/pybuggy/api.md").exists()
          assert not (tmp_path / "conftest.py").exists()

Доставка тестовой конвенции изолирована в чистой `write_test_convention` (без TTY, без проверок существования) —
тестируется напрямую:

      from goga_tool_pybuggy.commands.init import write_test_convention

      def test_convention_written(tmp_path):
          target = tmp_path / ".goga" / "usages" / "conventions.md"
          write_test_convention(target)                    # создаёт файл (и родительские директории)
          assert target.read_text() == ASSET_TEXT          # текст ассета установленного пакета
          target.write_text("locally modified")
          write_test_convention(target)                    # повторный вызов — всегда перезапись
          assert target.read_text() == ASSET_TEXT

Для прямой регистрации usages без discovery/копирования — `register_usages` (контракт не изменился); для регистрации
строк аннотаций в `codemanifest.annotations` — `register_annotations` (round-trip, идемпотентно по бэктик-ссылке:
совпавшая строка заменяется при отличии текста, иначе no-op; возвращает `changed_keys`). Интерактивное построение
`.goga/tools/pybuggy/config.yml` изолировано в `build_pybuggy_config`; чистую эмиссию YAML тестируют напрямую через
`write_pybuggy_config`; чистую запись conftest — через `write_pybuggy_conftest` (образцы — в разделах выше).

---

## Предусловия и побочные эффекты

- Требует установленный пакет `goga` (зависимость pybuggy) — для in-process инициализации goga-проекта.
- Пишет в `<cwd>/.goga/` (создаёт `.goga/usages/`, `.goga/usages/cooks/pybuggy/`, `.goga/config.yml`); пишет
  `<cwd>/.goga/usages/conventions.md` — **всегда** перезаписывается ассетом пакета (package-owned).
- Сетевые вызовы в init отсутствуют. Residual-случай: ручной ввод имени `conventions` в опроснике goga
  («Add codemanifest usages?») снова триггерит скачивание в goga (затем файл перезапишется ассетом); фильтрация
  осознанно не вводится.
- Пишет `<cwd>/conftest.py` (фиксированный шаблон `load_dotenv()` → `plugin.install()`; при наличии файла — только по
  подтверждению `click.confirm`, отказ → пропуск с INFO-логом). Наличие `goga_tool_pybuggy`/`python-dotenv` в окружении
  pytest потребителя не проверяется — выяснится при запуске тестов.
- Дописывает в сгенерированный `.goga/Dockerfile` строку `RUN goga install pybuggy -v 0.1.x` (версия не резолвится
  динамически).
- Читает usages и ассет конвенции из **установленного** пакета `goga_tool_pybuggy` (`importlib.resources`), не из cwd —
  работает после `goga install pybuggy`, а не только из checkout.
- Discovery рекурсивен по `.usages/*.md` под ячейкой `api` — будущие подклетки подключаются без правки команды;
  ассет конвенции доставляется отдельно (пакет `assets`, не api).
- Копирует только usages ячейки `api`; внутренние ячейки разработки (`config`/`spec`/`output`/...) не копируются.
- goga-init запускается при отсутствии `.goga/config.yml` (эвристика «не инициализирован») либо при согласии на
  пересоздание (`click.confirm`, по умолчанию `no`).
- Цели записи — goga-project-конфиг `.goga/config.yml` (блоки `codemanifest.usages` и `codemanifest.annotations`),
  `.goga/usages/conventions.md`, `.goga/usages/cooks/pybuggy/*.md`, `.goga/tools/pybuggy/config.yml` и корневой
  `<cwd>/conftest.py`.
