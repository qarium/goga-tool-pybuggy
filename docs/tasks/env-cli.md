# Загрузка .env в CLI pybuggy

## Current State

- Корневая click-группа `main` (`cli.py`) имеет пустое тело; `ctx.obj` **не используется нигде** в проекте.
- Контракт root-ячейки (`.usages/assembly.md`) фиксирует: нет опции `--config`, нет pass-object — команды сами грузят конфиг через `load_config()` без аргумента.
- Ни одна команда не читает env-переменные; `os.environ` сегодня читается только в ячейке `plugin` (pytest-plugin), не в CLI.
- Резолвинг git-ref в `pull`: per-spec `--ref` → глобальный `--ref` → config `git.ref` → remote-ветка по умолчанию; env-переменные не учитываются.
- `python-dotenv` **не объявлен** в `pyproject.toml` (присутствует в venv транзитивно, версия 1.2.2).
- В `.goga/usages/cooks/` **отсутствует** usage-файл `python-dotenv.md`.

## Description

Единая точка загрузки переменных окружения в CLI pybuggy. Корневая click-группа парсит глобальную опцию `--env-file`, грузит dotenv в `os.environ` (`override=False`) и кладёт контекст-объект в `ctx.obj`. Дополнительно переменная `PYBUGGY_REF` из окружения задаёт git-ref для команды `pull`.

Поведение:

- `pybuggy --env-file ./my.env <cmd>` → грузится явно указанный файл; если файл не существует — ошибка (`click.ClickException`). Опция `--env-file` — глобальная на корневой группе `main`, поэтому флаг обязан идти ДО подкоманды (click парсит опции группы на уровне группы).
- `pybuggy <cmd>` (без флага) → читается `.env` из CWD, если есть; если отсутствует — тихо (без ошибки).
- Загруженные значения попадают в `os.environ` **до** выполнения команды; `override=False` — уже заданные переменные окружения не перезаписываются.
- `ctx.obj` — контекст-объект, несущий разрешённый путь env-файла и загруженные значения.
- `PYBUGGY_REF` — приоритет резолвинга ref в `pull`: **per-spec `--ref` → глобальный `--ref` → `PYBUGGY_REF` → config `git.ref` → remote-ветка по умолчанию**.

## Scope

**In scope:**

- **root-ячейка** (`goga_tool_pybuggy/cli.py` + `CODEMANIFEST` + `.usages/assembly.md`): глобальная опция `--env-file`, загрузка `.env` в `os.environ`, контекст-объект в `ctx.obj`.
- **ячейка `pull`** (`commands/pull`): резолвинг `PYBUGGY_REF` в цепочку git-ref.
- Объявление зависимости `python-dotenv` в `pyproject.toml` (`[project] dependencies`) с минимальной версией.
- Создание usage-файла `.goga/usages/cooks/python-dotenv.md`.

**Out of scope:**

- Команды `init`, `list`, `info`, `generate` (env не читают).
- Интеграция env-значений в YAML-конфиг (ячейка `config`).
- Per-spec env-переменные (поддерживается только глобальная `PYBUGGY_REF`).

## Acceptance Criteria

- `pybuggy --env-file ./my.env <cmd>` грузит переменные из указанного файла в `os.environ` до запуска команды (флаг `--env-file` идёт до подкоманды — глобальная опция корневой группы).
- `pybuggy <cmd>` без флага тихо читает `.env` из CWD при его наличии.
- `override=False`: уже заданные в окружении переменные не перезаписываются.
- `ctx.obj` содержит разрешённый путь env-файла и загруженные значения.
- `pybuggy endpoint pull` резолвит git-ref с учётом `PYBUGGY_REF` по оговорённому приоритету.
- `python-dotenv` объявлен в `[project] dependencies` с минимальной версией.
- Существующие CLI-тесты проходят; добавлены тесты загрузки `.env` (явный/неявный файл, `override`, отсутствие) и резолвинга `PYBUGGY_REF`.

## Stack

- **Frameworks:** `click` (root-группа, глобальная опция, контекст-объект).
- **Libraries:** `python-dotenv` (загрузка `.env`).
- **Infrastructure:** — (отсутствует).

## External Dependencies

| Component        | Usage file                          | Status   |
|------------------|-------------------------------------|----------|
| `python-dotenv`  | `.goga/usages/cooks/python-dotenv.md` | created  |

## Risks and Constraints

- Введение `ctx.obj` нарушает действующий контракт root-ячейки «нет pass-object» — `CODEMANIFEST` и `.usages/assembly.md` должны быть обновлены синхронно с реализацией.
- Термин «env» семантически нагружен в проекте (pytest-опция `--env` в ячейке `plugin` для шаблонизации `base_url`). Синтаксической коллизии нет, но требуется ясность в документации.
- `python-dotenv` сегодня присутствует в venv лишь транзитивно — явное объявление зависимости фиксирует её как часть контракта.
- Поведение при отсутствии файла детерминировано: явно указанный `--env-file` не найден → ошибка; неявный `.env` в CWD отсутствует → тихо.

## Scope Estimate

Одиночная задача. Затронуты две ячейки (root + `pull`) плюс объявление зависимости и один usage-файл. Декомпозиция не требуется.

## Existing Architecture

Затронутые ячейки и точки интеграции:

- **ROOT** (`goga_tool_pybuggy/`) — владеет `main()`, точка интеграции глобальной опции `--env-file` и контекст-объекта `ctx.obj`.
- **commands/pull** — потребитель: резолвинг `PYBUGGY_REF` в цепочку git-ref.

Интеграционные требования: контракт root-ячейки обновляется (pass-object вводится осознанно); `pull` читает `os.environ`. Остальные ячейки (`init`, `list`, `info`, `generate`, `config`, `spec`, `output`, `api`, `plugin`, `matchcrest`) не затрагиваются.

## Notes

- Имя env-переменной: `PYBUGGY_REF` (префикс `PYBUGGY_`, по аналогии с конвенцией `QA_*` в ячейке `plugin`).
- Содержимое контекст-объекта `ctx.obj`: разрешённый путь env-файла + загруженные значения (key→value).
- Ограничение этапа: задача не содержит примеров кода и архитектурных схем — только контракт и границы.
