# goga — in-process инициализация goga-проекта (Python API)

## Предметная область

Пакет `goga` предоставляет Python-API для интерактивной инициализации goga-проекта — то же, что делает CLI-команда
`goga init`, но in-process. Аудитория — ячейки pybuggy, которые под капотом инициализируют goga-проект
(напр. `goga_tool_pybuggy/commands/init`). API сборочное: `Questionnaire` опрашивает поля конфига по одному, `FileGenerator`
пишет файлы по собранным ответам.

## Контракт инициализации

Типы из `goga.init`:

- `Questionnaire()` — интерактивный опросник через click. Без аргументов конструктора. Предоставляет per-field методы
  (по одному на каждое поле конфига) — pybuggy оркестрирует их вручную:
  - `ask_language() -> str` — один из python/golang/kotlin/swift/javascript (**pybuggy НЕ вызывает — язык хардкод**).
  - `ask_base_convention() -> tuple[dict | None, str | None]` — пара (usages_prefill, annotations_prefill).
  - `ask_codemanifest_usages(prefill: dict | None = None) -> dict | None`.
  - `ask_codemanifest_annotations(prefill: str | None = None) -> str | None`.
  - `ask_agent() -> str`.
  - `ask_image(language: str) -> str` — Docker-образ; список подсказок ограничен `_IMAGE_MAP[language]`
    (для `python` — `qarium/goga-python-3.10:1.1` … `qarium/goga-python-3.14:1.1`); **default — последний**;
    принимает произвольный ввод.
  - `ask_dockerfile_path() -> str | None` — путь к Dockerfile (default `.goga/Dockerfile`) или None (пропуск).
    **pybuggy НЕ вызывает** — Dockerfile обязателен, `dockerfile_path` хардкодится как `.goga/Dockerfile`.
  - `ask_env(agent: str) -> dict | None`.
  - `ask_pipeline_agent(agent: str) -> str`.
  - `ask_pipeline_env(pipeline_agent: str) -> dict | None`.
  - Оркестраторы `ask_goga_config() -> GogaConfigAnswers` и `ask() -> InitAnswers` (полный универсальный поток —
    **pybuggy НЕ использует**, т.к. они зовут `ask_language`).
- `FileGenerator()` — генератор файлов проекта. Без аргументов конструктора.
  - `generate(answers: InitAnswers) -> None` — пишет `.goga/config.yml`; при `dockerfile_path` сначала создаёт Dockerfile
    `FROM {image}`; при `codemanifest_usages` со ключом `"conventions"` скачивает конвенцию языка (requests) в
    `.goga/usages/conventions.md`. Бросает `RuntimeError` при сбое скачивания (config.yml НЕ создаётся).
- `InitLogic(questionnaire, generator).run() -> int` — оркестратор «полный универсальный поток»; **pybuggy НЕ
  использует** (требует `ask_language`). Приведён только как референс error-handling: ловит `click.Abort`→1,
  `Exception`→log+echo+1.

Контейнеры ответов (frozen dataclasses, `kw_only=True`):

- `GogaConfigAnswers` — поля: `language: str`, `agent: str`, `image: str`, `pipeline_agent: str`,
  `pipeline_env: dict | None`, `env: dict | None`, `codemanifest_usages: dict | None`,
  `codemanifest_annotations: str | None`, `dockerfile_path: str | None`.
- `InitAnswers` — поле `goga_config: GogaConfigAnswers`.

## Генерируемые файлы (side effects, в cwd)

- `.goga/config.yml` — полный goga-конфиг (language, image, dockerfile, build, pipeline, codemanifest).
- `.goga/usages/conventions.md` — если `codemanifest_usages` содержит `"conventions"` (скачивается через requests).
- `Dockerfile` (по пути `dockerfile_path`) — `FROM {image}`; создаётся когда `dockerfile_path` задан (со стороны pybuggy
  он передаётся всегда — Dockerfile обязателен).

## Шаблон: in-process вызов (per-field сборка)

      from goga.init import FileGenerator, GogaConfigAnswers, InitAnswers, Questionnaire

      questionnaire = Questionnaire()
      generator = FileGenerator()

      language = "python"  # хардкод — pybuggy это Python-проект; ask_language НЕ вызывается

      usages_prefill, annotations_prefill = questionnaire.ask_base_convention()
      codemanifest_usages = questionnaire.ask_codemanifest_usages(usages_prefill)
      codemanifest_annotations = questionnaire.ask_codemanifest_annotations(annotations_prefill)
      agent = questionnaire.ask_agent()
      image = questionnaire.ask_image(language)        # python-only набор: 3.10–3.14
      dockerfile_path = ".goga/Dockerfile"             # хардкод — Dockerfile обязателен; ask_dockerfile_path НЕ вызывается
      env = questionnaire.ask_env(agent)
      pipeline_agent = questionnaire.ask_pipeline_agent(agent)
      pipeline_env = questionnaire.ask_pipeline_env(pipeline_agent)

      config = GogaConfigAnswers(
          language=language,
          agent=agent,
          image=image,
          pipeline_agent=pipeline_agent,
          pipeline_env=pipeline_env,
          env=env,
          dockerfile_path=dockerfile_path,
          codemanifest_usages=codemanifest_usages,
          codemanifest_annotations=codemanifest_annotations,
      )

      try:
          generator.generate(InitAnswers(goga_config=config))  # 0 успех
      except click.Abort:
          ...  # отмена пользователя → вернуть 1
      except Exception:
          ...  # сбой генерации → залогировать + вернуть 1

## Особенности для вызывающей стороны

- **Интерактивен** (TTY-промпты через click). В тестах вызывающая сторона подменяет точку вызова (monkeypatch), чтобы
  не поднимать промпты (реальные `Questionnaire()`/`FileGenerator()` в тестах не поднимаются — TTY/сеть; только mocks).
- Возвращает **число, не бросает исключение** при отмене/сбое (`click.Abort`→1, прочая `Exception`→log+echo+1 —
  паритет со старым `InitLogic.run()`); диагностику вызывающая сторона печатает сама.
- `InitLogic`/`ask`/`ask_goga_config` **не используются** — оркестрация per-field вручную фиксирует `language="python"`
  и ограничивает набор образов.
- Это внешний пакет — подключается в CODEMANIFEST через `Usages`, **не** через `Imports` (Imports связывает только
  ячейки проекта); абсолютный импорт наверху модуля, third-party группа isort.

## Зависимости

- Требует `goga` в `pyproject.toml` зависимостей вызывающего пакета.
- В dev `goga` резолвится из `.libs/goga` симлинком в `site-packages` (dev-snapshot новее 1.1.2, метаданных версии
  нет); **НЕ `uv sync`** — он пересоздаст зависимости и вернёт устаревший резолвер.
