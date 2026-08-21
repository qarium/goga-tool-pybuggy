# GitPython — cloning the specs repository for `endpoint pull`

## Domain

This document describes a pattern for accessing a remote git repository that stores specifications for the `pybuggy endpoint pull` command. `pybuggy` treats the repository as **read-only**: shallow-clone into a temporary directory, read, copy the required file/subdirectory to the local `location`, delete the clone. No commit/push.

The idiom mirrors cell `swax/git/` (`clone_specs` as a context manager), but is implemented **inside pybuggy** (cell `swax.git` is not used — only `swax.openapi`).

---

## Shallow-clone as context manager

`Repo.clone_from(..., depth=1)` fetches only the latest commit. The temporary directory is deleted when the `with` block exits (normally or via an exception):

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
            # branch=None ⇒ GitPython omits --branch ⇒ the default branch is cloned.
            Repo.clone_from(repo_url, str(tmp_root), depth=1, branch=ref)
        except GitCommandError as exc:
            raise click.ClickException(f"failed to clone {repo_url}: {exc}") from exc

        yield tmp_root
```

Consumer conventions:
- `repo_url` — the clone URL. For private repositories, rely on git credential helpers; **never embed** tokens in the URL.
- `ref` — a git ref (branch or tag name) for the shallow clone via `branch=` (git `--branch`). `None` ⇒ default branch. A bare commit SHA does not reliably shallow-resolve — use branch or tag names.
- Always use `with` — outside the block the yielded path is invalid (the directory is deleted).

---

## Copying a spec to the local location

Inside the `with` block, resolve `git.location` (a repository path — file or subdirectory) and copy it to the local `location` (a path relative to the project root):

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

Consumer conventions:
- `git_location` (`specs.<name>.git.location`) — the path within the repository (file or subdirectory).
- `local_location` (`specs.<name>.location`) — the project-root-relative path to the spec file; this is the value the `list` header displays.
- Idempotency: a repeated `pull` overwrites the target (`dirs_exist_ok=True` / `shutil.copy2`).

---

## Error mapping

Map `GitCommandError` → `click.ClickException` to produce a uniform non-zero exit (see the `click.md` cook). A missing `git.location` inside the clone also raises a `ClickException` whose message includes the offending path.

---

## Testing

- Mock `Repo.clone_from` at the import site (`mock.patch("goga_tool_pybuggy.<...>.Repo.clone_from")`) — never perform real cloning in tests (see `.goga/usages/conventions.md`, Mocks section).
- Test copying/path resolution on `tmp_path` using a pseudo-"clone" (a fixture subdirectory).
