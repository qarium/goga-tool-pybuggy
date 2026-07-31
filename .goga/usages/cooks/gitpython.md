# GitPython — клонирование репозитория со спеками для `endpoint pull`

## Предметная область

Шаблон доступа к удалённому git-репозиторию со спецификациями для команды `goga_tool_pybuggy endpoint pull`. `pybuggy` обращается с репозиторием как с **read-only**: shallow-clone во временную директорию, чтение, копирование нужного файла/подкаталога в локальный `location`, удаление клона. Никаких commit/push.

Идиома зеркалирует cell `swax/git/` (`clone_specs` как context manager), но реализована **внутри pybuggy** (cell `swax.git` не используется — только `swax.openapi`).

---

## Shallow-clone как context manager

`Repo.clone_from(..., depth=1)` — нужен только последний коммит. Временный каталог удаляется при выходе из `with` (нормальном или с исключением):

```python
import contextlib
import pathlib
import tempfile
from collections.abc import Iterator

from git import Repo
from git.exc import GitCommandError


@contextlib.contextmanager
def clone_repo(repo_url: str, ref: str | None = None) -> Iterator[pathlib.Path]:
    """Shallow-clone repo_url into a temp dir and yield its root; cleanup on exit."""
    with tempfile.TemporaryDirectory(prefix="pybuggy-") as tmp_name:
        tmp_root = pathlib.Path(tmp_name)

        try:
            # branch=None ⇒ GitPython не добавляет --branch ⇒ клонируется default branch.
            Repo.clone_from(repo_url, str(tmp_root), depth=1, branch=ref)
        except GitCommandError as exc:
            raise click.ClickException(f"failed to clone {repo_url}: {exc}") from exc

        yield tmp_root
```

Соглашения потребителя:
- `repo_url` — clone URL. Для приватных репозиториев полагаться на git credential helpers; **не встраивать** токены в URL.
- `ref` — git ref (имя ветки или тега) для shallow-clone через `branch=` (git `--branch`). `None` ⇒ default branch. Голый commit SHA shallow-resolve'ится не всегда — использовать имена веток/тегов.
- Использовать `with` обязательно — путь за пределами блока невалиден (каталог удалён).

---

## Копирование спеки в локальный location

Внутри `with` находим `git.location` (путь в репо — файл или подкаталог) и копируем в локальный `location` (путь от корня проекта):

```python
import shutil


def install_spec(repo_url: str, git_location: str, local_location: pathlib.Path, project_root: pathlib.Path) -> pathlib.Path:
    """Clone repo, copy git_location -> project_root/local_location, return target path."""
    destination = project_root / local_location

    with clone_repo(repo_url) as repo_root:
        source = repo_root / git_location
        if not source.exists():
            raise click.ClickException(f"spec path not found in repo: {git_location}")

        destination.parent.mkdir(parents=True, exist_ok=True)

        if source.is_dir():
            shutil.copytree(source, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(source, destination)

    return destination
```

Соглашения потребителя:
- `git_location` (`specs.<name>.git.location`) — путь в репозитории (файл или подкаталог).
- `local_location` (`specs.<name>.location`) — путь от корня проекта до файла спеки; именно он показывается в заголовке `list`.
- Идемпотентность: повторный `pull` перезаписывает (`dirs_exist_ok=True` / `shutil.copy2`).

---

## Маппинг ошибок

`GitCommandError` → `click.ClickException` для единообразного ненулевого exit (см. cook `click.md`). Отсутствие `git.location` в клоне — тоже `ClickException` с понятным путём.

---

## Тестирование

- `Repo.clone_from` мокать в точке импорта (`mock.patch("goga_tool_pybuggy.<...>.Repo.clone_from")`) — реальное клонирование в тестах не выполнять (см. `.goga/usages/conventions.md`, раздел Mocks).
- Копирование/разрешение путей тестировать на `tmp_path` с псевдо-«клоном» (поддиректория-фикстура).
