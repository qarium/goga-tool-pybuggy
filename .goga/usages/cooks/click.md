# click — CLI-фасад (библиотека)

## Предметная область

`click` — библиотека для построения CLI в Python. Используется проектом для групп, подгрупп,
команд, опций/аргументов и единообразного маппинга доменных ошибок в ненулевой exit.

```python
import click
```

Эта практика описывает только API `click`. Как проект собирает из этого свой CLI — в клеточных
`.usages/` соответствующих ячеек (composition root, команды).

---

## Группы и подгруппы

Группа (`@click.group`) — корень дерева команд. Подгруппа — отдельная группа, добавленная в
родительскую через `add_command`. Так строятся вложенные команды `parent child ...`:

```python
@click.group()
def parent():
    """Root group."""


@click.group("child", help="Child subgroup.")
def child_group():
    """Child subgroup."""


parent.add_command(child_group)
```

- Имя группы — аргумент декоратора (`@click.group("child")`); без аргумента берётся имя функции.
- `help` группы показывается в `--help`.

---

## Команды, опции, аргументы

Команда (`@click.command`) — лист дерева. Опции — `@click.option`, позиционные аргументы —
`@click.argument`. Имя декорированной функции — это имя команды, если не задано явно.

```python
@click.command("pull")
@click.option("--spec", "spec_name", default=None, help="Filter by spec name.")
def pull_cmd(spec_name):
    """Pull specs."""
    ...
```

- `@click.option("--flag", "dest", default=None, ...)` — опция; `dest` задаёт имя параметра в callback.
- Булев флаг: `is_flag=True, default=False`.
- Короткая форма: `@click.option("-s", "--spec", "spec_name", ...)`.
- `@click.argument("endpoint_id")` — позиционный аргумент.

---

## Интерактивные запросы — confirm и prompt

`click.confirm` — вопрос да/нет (гейт опасного действия); `click.prompt` — запрос значения.
Используются в handler-ах для интерактивных гейтов и опросов:

```python
# Гейт перезаписи: файл существует — спрашиваем явное подтверждение (отказ по умолчанию)
if not path.exists() or click.confirm(f"{path} exists — rebuild it?", default=False):
    build(path)

# Запрос значения: default="" допускает пустой ввод (пропуск необязательного поля)
name = click.prompt("spec name", default="", show_default=False).strip()

# Выбор из фиксированного набора
spec_type = click.prompt("spec type", type=click.Choice(["swagger", "openapi"]))
```

- `default` у `confirm` — ответ по Enter; `default=False` — «отказ по умолчанию» для перезаписи и
  других опасных действий.
- `prompt` возвращает введённое значение; `type=click.Choice([...])` ограничивает набор допустимых
  ответов; `show_default=False` скрывает подсказку дефолта.
- Отказ в `confirm` — не ошибка: шаг пропускается, handler продолжает выполнение (exit 0).
- Прерывание (Ctrl-C) поднимает `click.Abort` — handler перехватывает его и возвращает ненулевой
  exit, не роняя процесс.

---

## Handler отделён от обёртки

Click-декоратор только связывает опции/аргументы и вызывает чистую handler-функцию. Это позволяет
тестировать логику **прямым вызовом** handler-а, без `CliRunner`:

```python
def run_pull(spec_name):
    """Pure handler — callable directly from tests."""
    ...


@click.command("pull")
@click.option("--spec", "spec_name", default=None)
def pull_cmd(spec_name):
    run_pull(spec_name)
```

---

## Маппинг доменных ошибок — ClickException

Доменные ошибки (не найдено, невалидный ввод, отказ внешней зависимости) маппятся в
`click.ClickException`. Click печатает сообщение и завершает процесс с ненулевым exit —
единообразное поведение для всех команд:

```python
if spec_name not in config.specs:
    raise click.ClickException(f"spec not found: {spec_name}")
```

---

## Тестирование CLI

- Handler-функции тестируются **прямым вызовом** (см. `conventions`, раздел CLI Testing), без `CliRunner`.
- git/FS — через `mock.patch`/`tmp_path`; чистая логика — без моков.