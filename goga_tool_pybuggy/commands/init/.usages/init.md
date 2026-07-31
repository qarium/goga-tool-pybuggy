# pybuggy.commands.init — инициализация goga-проекта и bootstrap consumer-usages ячейки api

## Предметная область

Команда `pybuggy init` под капотом **инициализирует goga-проект** (если он ещё не создан) и затем доставляет
consumer-usages ячейки `api` (и её подклеток) в проект, где она вызвана, чтобы goga-агент потребителя знал, как
пользоваться pybuggy. Аудитория — интегратор, подключающий pybuggy в свой проект (`pip install pybuggy`), и goga-агент
потребителя.

Инициализация goga-проекта выполняется in-process пакетом `goga` (per-field методы `goga.init.Questionnaire` +
`FileGenerator.generate`; `InitLogic` не используется): интерактивный опрос + генерация `.goga/config.yml`
(language/build/pipeline/codemanifest), `.goga/usages/conventions.md`, опционально Dockerfile. Затем команда копирует
cell-usages `api.md`/`asserts.md` в `.goga/usages/cooks/pybuggy/` и регистрирует их
в `.goga/config.yml` под `codemanifest.usages` ключами `pybuggy-api`/`pybuggy-asserts`, а также дополняет
`codemanifest.annotations` ссылающейся строкой на каждый usage (`` `pybuggy-api` `` / `` `pybuggy-asserts` `` с кратким
описанием назначения); существующий текст аннотаций сохраняется. Источник usages — установленный пакет (не cwd);
поведение идемпотентно.

---

## Точка входа

- Консольная команда (top-level, не под `endpoint`): `pybuggy init`
- Модульный запуск: `python -m pybuggy init`
- Программный импорт фасада:
      from pybuggy.commands.init import run_init, run_goga_init, init_cmd, register_usages, register_annotations

---

## Шаблон: первый запуск в свежем (не-goga) проекте

В проекте без `.goga/config.yml`:
1. Команда **интерактивно** инициализирует goga-проект (вопросы об агенте/образе/...; язык зафиксирован `python`).
2. По завершении создаётся полный `.goga/config.yml`, затем регистрируются usages pybuggy.

      cd my-consumer-project
      pybuggy init        # → опросник goga, затем регистрация pybuggy usages

Результат:
- `.goga/config.yml` — полный goga-конфиг + блок `codemanifest.usages` с `pybuggy-api`/`pybuggy-asserts` + блок
  `codemanifest.annotations` со ссылающимися строками.
- `.goga/usages/cooks/pybuggy/api.md`, `.goga/usages/cooks/pybuggy/asserts.md`.

---

## Шаблон: запуск в уже инициализированном goga-проекте

Если `.goga/config.yml` уже существует — опросник goga **не запускается**; сразу round-trip регистрация usages
(существующие ключи/комментарии сохранены):

      # .goga/config.yml до запуска (с пользовательскими ключами)
      codemanifest:
        usages:
          conventions: .goga/usages/conventions.md   # не затирается
      # pybuggy init → добавляет pybuggy-api, pybuggy-asserts; conventions и комментарий на месте

---

## Идемпотентность

Повторный `pybuggy init` в уже инициализированном проекте: goga-init пропускается, скопированные `.md` перезаписываются
(актуальные cell-usages пакета), уже зарегистрированные ключи и уже ссылающиеся аннотации пропускаются. Флаги
`--force`/`--dry-run` не предусмотрены.

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
      from pybuggy.commands.init import run_init

      def test_init_in_fresh_project(tmp_path, monkeypatch):
          monkeypatch.chdir(tmp_path)
          # заглушить интерактивный goga init, чтобы тесты не зависели от TTY:
          monkeypatch.setattr("pybuggy.commands.init.init.run_goga_init", lambda: 0)
          assert run_init() == 0
          assert (tmp_path / ".goga/usages/cooks/pybuggy/api.md").exists()

      def test_goga_cancel_aborts(tmp_path, monkeypatch):
          monkeypatch.chdir(tmp_path)
          monkeypatch.setattr("pybuggy.commands.init.init.run_goga_init", lambda: 1)  # отмена
          assert run_init() == 1
          assert not (tmp_path / ".goga/usages/cooks/pybuggy/api.md").exists()  # usages не пишутся

Для прямой регистрации usages без discovery/копирования — `register_usages` (контракт не изменился); для дописывания
ссылающихся аннотаций в `codemanifest.annotations` — `register_annotations` (round-trip, идемпотентно по бэктик-ссылке).

---

## Предусловия и побочные эффекты

- Требует установленный пакет `goga` (зависимость pybuggy) — для in-process инициализации goga-проекта.
- Пишет в `<cwd>/.goga/` (создаёт `.goga/usages/cooks/pybuggy/`, `.goga/config.yml`).
- Читает usages из **установленного** пакета `pybuggy.api` (`importlib.resources`), не из cwd — работает после
  `pip install pybuggy`, а не только из checkout.
- Discovery рекурсивен по `.usages/*.md` под ячейкой `api` — будущие подклетки подключаются без правки команды.
- Копирует только usages ячейки `api`; внутренние ячейки разработки (`config`/`spec`/`output`/...) не копируются.
- goga-init запускается только при отсутствии `.goga/config.yml` (эвристика «инициализирован»).
- Цель — goga-project-конфиг `.goga/config.yml` (блоки `codemanifest.usages` и `codemanifest.annotations`),
  НЕ `.goga/tools/pybuggy/config.yml`.