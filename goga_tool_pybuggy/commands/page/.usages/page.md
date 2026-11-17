# goga_tool_pybuggy.commands.page — page generate command

## Subject domain

The cell `goga_tool_pybuggy/commands/page` provides scaffolding for the web test kind: it generates
a `pages/` page-object module per tested-site path — a `BasePage` subclass carrying its `path`
attribute plus its function-scoped pytest fixture — and empty `__init__.py` package markers on
every directory along the module path.
Consumers: CLI registration (`page_generate_cmd`) and tests (`run_page_generate` directly; the
pure renderer `render_page_module` directly for text checks).

## Handler function invocation

`run_page_generate` is the testable entry point; the Click wrapper `page_generate_cmd` binds the
positional arguments and the flag and calls `run_page_generate`:

    from goga_tool_pybuggy.commands.page import run_page_generate

    run_page_generate("/login")                    # names derived from the path
    run_page_generate("/admin/api/v1/mocks")       # nested directories from the path
    run_page_generate("/login", "login")           # the name drives the names
    run_page_generate("/login", "login", force=True)  # overwrite an existing module

`render_page_module` is a pure function with the signature `(path, class_name, fixture_name) ->
str`; it returns the full module text. Tests use it to verify content without writing to disk:

    from goga_tool_pybuggy.commands.page import render_page_module

    module_text = render_page_module("/login", "LoginPage", "page_login")  # str; deterministic

## Observable behavior

The handler validates the input (before any write), derives the names, renders the module text,
and writes the artifact tree under the current working directory:

    pages/__init__.py                        # empty package marker, created only when missing
    pages/<dir>/__init__.py                  # one per path directory, created only when missing
    pages/<dir...>/<stem>_page.py            # the page-object module

Directories come from the path segments minus the last one; the file stem is the given name (whole)
or the last path segment. The fixture name is `page_` plus the given name or all path segments
joined by `_`; the class name is the CamelCase stem plus `Page`.

| Invocation | Module file | Fixture | Class |
|------------|-------------|---------|-------|
| `page generate /admin/api/v1/mocks` | `pages/admin/api/v1/mocks_page.py` | `page_admin_api_v1_mocks` | `MocksPage` |
| `page generate /login login` | `pages/login_page.py` | `page_login` | `LoginPage` |
| `page generate /admin/login auth` | `pages/admin/auth_page.py` | `page_auth` | `AuthPage` |

Every path segment and the name are sanitized to a Python identifier segment by one rule: every
character outside the word-character class becomes `_`, and a leading digit is prefixed with `_`
(`/v1.0/settings` → the directory `v1_0`; the name `my-page` → the stem `my_page`). A leading-digit
stem keeps the underscore through every derived name (the file `_2fa_page.py`, the fixture
`page__2fa`, the class `_2faPage`). The class `path` attribute always carries the verbatim input
path — never the sanitized segments.

## Contents of the page module

The module is a fixed-shape literal (double quotes, no formatter runs over it):

```python
import pytest

from goga_tool_pybuggy.web import BasePage
from prettyplay import PrettyPlay


class LoginPage(BasePage):
    pass


@pytest.fixture(scope="function")
def page_login(web: PrettyPlay) -> LoginPage:
    return LoginPage(web, "/login")
```

The class carries behavior only — the address lives in the fixture, bound at construction. The
generated subclass is the working form of a page object: it inherits `BasePage` and is the place
to **encapsulate the page's logic as methods** — closing a cookie banner, a form flow, adding to
cart — added by hand next to the generated skeleton:

```python
class LoginPage(BasePage):
    def dismiss_cookie_banner(self) -> None:
        self()
        with self.group("Dismiss the cookie banner"):
            self.step("Close the cookie banner")

        self.expect("The cookie banner is gone")
```

A method runs its steps through the proxied surface (`self.step`, `self()` to re-open) — the
test reads as domain actions, the sentences live next to their page (see the pybuggy-web
usage). Everything a method renders into a sentence reaches the LLM prompt and the committed
cache — no secrets in step sentences.

## --force semantics

- Without `-f` (`force=False`): the handler silently skips an existing module file (no console
  output) and creates it when missing. The behavior is idempotent.
- With `-f` (`force=True`): the handler overwrites the module file.
- `__init__.py` markers are created only when missing and are **never overwritten — even with
  `-f`**: a consumer project may keep re-exports in its `pages/` package markers. This is the
  deliberate difference from the api-side `endpoint generate`, whose flag regenerates the markers.

## Special cases

- A path without a leading slash (`login`, empty) → `click.ClickException`.
- A path without a non-empty segment (`/`, `//`) → `click.ClickException`; a trailing slash
  collapses (`/login/` behaves as `/login`).
- A blank name (`"   "`) → `click.ClickException`.
- Every rejection happens before any write — a rejected input leaves no `pages/` tree behind.
- A path containing a double quote renders through the escaped literal form — the module always
  compiles.

## Preconditions

- Only the current working directory is used (`Path.cwd()`); no config, no spec, no web.yml —
  the path is the single input.
- The generated module imports `goga_tool_pybuggy.web` (`BasePage`) and `prettyplay`
  (`PrettyPlay`) in the consumer project, not inside pybuggy itself.
- The generated fixtures load automatically: `pages/` is the web kind's default fixture package
  (the mirror of the api kind's `api/`) — the web plugin discovers the modules at installation;
  `install(loaders=[])` disables the default.
