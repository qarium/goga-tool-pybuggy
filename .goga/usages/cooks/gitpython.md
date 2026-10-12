# GitPython — shallow-cloning remote sources for pybuggy

## Domain

This document describes a pattern for accessing a remote git repository from pybuggy. Two consumers share it: `pybuggy endpoint pull` (spec files) and the sandbox migrations source (a remote folder of migration files). `pybuggy` treats every repository as **read-only**: shallow-clone into a temporary directory, read, copy or consume the required file/subdirectory, delete the clone. No commit/push.

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


def install_spec(
    repo_url: str, git_location: str, local_location: pathlib.Path, project_root: pathlib.Path
) -> pathlib.Path:
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

## Second consumer — the sandbox migrations source

The sandbox document declares a remote migrations folder on a postgresql service entry:
a `location` path inside the repository plus `git: {url, ref}` (`ref` optional). Resolution
reuses the same shallow-clone context manager:

```python
with clone_repo(url, ref) as repo_root:
    migrations_dir = repo_root / location
    if not migrations_dir.is_dir():
        raise MigrationError(...)  # the sandbox error family, not ClickException
    # read the migration files from the clone — nothing is copied into the consumer repo
```

Consumer conventions:
- The clone is consumed in place and deleted afterwards — unlike `pull`, nothing lands in the
  consumer repository; the migration files exist only for the session's apply.
- Ambient credentials only (ssh-agent, credential helper, gitconfig) — **never** embed tokens in
  the URL; the scheme allowlist is the same as pull's (https/http/git/ssh), but the sandbox
  enforces it strictly: an scp-style URL with an empty scheme is rejected — rewrite it as
  `ssh://git@host/path` (pull historically bypasses the check for empty schemes; do not copy
  that bypass here).
- `ref` is a branch or tag name; `None` means the remote default branch.

## Error mapping

Each consumer maps `GitCommandError` into its own failure family — the clone pattern is shared, the CLI layer is not:

- `endpoint pull` maps to `click.ClickException` for a uniform non-zero exit (see the `click.md` cook).
- The sandbox maps to its engine error family (`EngineError`-style readable failures) naming the service and the failed step — the sandbox runs inside pytest, not a CLI process.

A missing `git.location` inside the clone raises the consumer's error with a message including the offending path.

---

## Testing

- Mock `Repo.clone_from` at the import site (`mock.patch("goga_tool_pybuggy.<...>.Repo.clone_from")`) — never perform real cloning in tests (see `.goga/usages/conventions.md`, Mocks section).
- Test copying/path resolution on `tmp_path` using a pseudo-"clone" (a fixture subdirectory).
