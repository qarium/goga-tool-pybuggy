# CLI — `goga tool pybuggy page generate`

Scaffolds a page-object module for the web test kind: a `BasePage` subclass carrying its `path`
attribute plus its function-scoped pytest fixture, under `pages/` of the current working
directory — the web counterpart of [endpoint generate](generate.md).

```bash
goga tool pybuggy page generate /admin/api/v1/mocks
goga tool pybuggy page generate /login login
goga tool pybuggy page generate /login login -f
```

## Options and arguments

| Element | Meaning |
|---------|---------|
| `path` (positional, required) | the tested-site page path; must start with `/` and carry at least one non-empty segment — `login` or `/` fail with `path must start with '/'` / `path carries no non-empty segment` |
| `name` (positional, optional) | the page name driving the fixture and class names; absent derives them from the path; a blank value fails with `name must not be blank` |
| `-f`, `--force` | overwrite an existing page-object module; `__init__.py` markers are created only when missing |

## Artifact tree

```
pages/__init__.py                       # empty package marker, created only when missing
pages/admin/__init__.py
pages/admin/api/__init__.py
pages/admin/api/v1/__init__.py
pages/admin/api/v1/mocks_page.py        # the page-object module
```

Directories come from the path segments minus the last one; the module file is
`<stem>_page.py` where the stem is the given `name` (whole) or the last path segment. Every
segment and the name are sanitized to a Python identifier segment (non-word characters become
`_`, a leading digit is prefixed with `_`) — every directory of the tree is importable and the
derived names never disagree. The class `path` attribute always carries the verbatim input path.

| Invocation | Module file | Fixture | Class |
|------------|-------------|---------|-------|
| `page generate /admin/api/v1/mocks` | `pages/admin/api/v1/mocks_page.py` | `page_admin_api_v1_mocks` | `MocksPage` |
| `page generate /login login` | `pages/login_page.py` | `page_login` | `LoginPage` |
| `page generate /admin/login auth` | `pages/admin/auth_page.py` | `page_auth` | `AuthPage` |
| `page generate /login user_profile` | `pages/user_profile_page.py` | `page_user_profile` | `UserProfilePage` |

## Contents of the page module

A fixed-shape literal — no formatter runs over it (the shape never varies):

```python
import pytest

from goga_tool_pybuggy.web import BasePage
from prettyplay import PrettyPlay


class LoginPage(BasePage):
    path = "/login"


@pytest.fixture(scope="function")
def page_login(web: PrettyPlay) -> LoginPage:
    return LoginPage(web)
```

The fixture requests the `web` runtime and builds the page; `goto()` opens the full URL — see
[Web — Overview](../web/index.md#tested-site-pages-basepage).

## `--force` semantics

- Without `-f`: an existing module file is silently skipped (no console output); missing files
  and directories are created. The behavior is idempotent.
- With `-f`: the module file regenerates over an existing one.
- `__init__.py` markers are created only when missing and are **never overwritten — even with
  `-f`**: a consumer project may keep re-exports in its `pages/` package markers. This is the
  deliberate difference from [endpoint generate](generate.md#force-semantics), whose flag
  regenerates the markers.

## Special cases

| Case | Behavior |
|------|----------|
| path without a leading slash (`login`, empty) | `path must start with '/': ...` |
| path without a non-empty segment (`/`, `//`) | `path carries no non-empty segment: ...` |
| trailing slash (`/login/`) | empty segments drop — behaves exactly as `/login` |
| blank name (`"   "`) | `name must not be blank` |
| non-word characters (`/v1.0/settings`, name `my-page`) | sanitized (`v1_0/`, `MyPagePage`, `page_my_page`); the class `path` attribute keeps the verbatim path |
| leading digit (name `2fa`) | the underscore survives everywhere: `_2fa_page.py`, `page__2fa`, `_2faPage` |
| a path containing a quote | the literal renders escaped — the module always compiles |

Every rejection happens before any write — a rejected input leaves no `pages/` tree behind.

## Preconditions

- Only the current working directory is used: no spec, no `api.yml`, no `web.yml` — the path is
  the single input.
- The generated module imports `goga_tool_pybuggy.web` and `prettyplay` in the consumer project.
