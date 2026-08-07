# python-dotenv — загрузка .env в os.environ (библиотека)

## Предметная область

`python-dotenv` — библиотека для чтения `.env`-файлов и применения переменных в `os.environ`. Используется корневой
ячейкой `goga_tool_pybuggy/` для единой загрузки окружения CLI до запуска команды.

```python
from dotenv import dotenv_values, load_dotenv
```

Эта практика описывает только API `python-dotenv`. Как CLI применяет загрузку — в клеточной `.usages/assembly.md`
корневой ячейки.

---

## Применение .env в os.environ

`load_dotenv` читает файл и применяет пары key=value в `os.environ`. `override=False` (по умолчанию) — уже заданные в
окружении переменные НЕ перезаписываются:

```python
from dotenv import load_dotenv

load_dotenv("./my.env")                  # применить в os.environ; override=False по умолчанию
load_dotenv("./my.env", override=True)   # перезаписать существующие (НЕ используется в pybuggy)
load_dotenv(".env")                      # неявный файл из CWD
```

`load_dotenv` возвращает `True`, если файл найден и прочитан, и `False`, если файл отсутствует — это позволяет
различать «явный файл обязан существовать» (отсутствие → ошибка) и «неявный .env опционален» (отсутствие → тихо).

## Чтение значений без побочных эффектов

`dotenv_values` возвращает `dict[str, str | None]` пар без записи в `os.environ` — удобно для формирования
контекст-объекта (`EnvContext.values`) и контроля применения:

```python
from dotenv import dotenv_values

values = dotenv_values("./my.env")   # dict key→value; KEY= → ''; голый ключ (без =) → None
```

## Поведение и ограничения

- `override=False` (поведение pybuggy): переменные, уже заданные в окружении (shell/CI), не перезаписываются значениями из `.env`.
- `KEY=` (с `=`, пустое значение) → `''` в `dotenv_values` (пустая строка, **не** `None`); голый ключ `KEY`
  (без `=`) → `None` (единственный случай `None`); в `os.environ` обе формы задаются как `''`.
- Комментарии (`# ...`) и пустые строки игнорируются; кавычки вокруг значений снимаются.
- Файл читается как UTF-8.
