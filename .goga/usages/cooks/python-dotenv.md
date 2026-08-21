# python-dotenv — loading .env into os.environ (library)

## Domain

`python-dotenv` is a library for reading `.env` files and applying their variables to `os.environ`. The root cell `goga_tool_pybuggy/` uses it to load the CLI environment uniformly before a command runs.

```python
from dotenv import dotenv_values, load_dotenv
```

This practice covers only the `python-dotenv` API. The root cell's `.usages/assembly.md` describes how the CLI applies the loading.

---

## Applying .env to os.environ

`load_dotenv` reads the file and applies key=value pairs to `os.environ`. With `override=False` (the default), variables already present in the environment are NOT overwritten:

```python
from dotenv import load_dotenv

load_dotenv("./my.env")                  # apply to os.environ; override=False by default
load_dotenv("./my.env", override=True)   # overwrite existing values (NOT used in pybuggy)
load_dotenv(".env")                      # implicit file from CWD
```

`load_dotenv` returns `True` when it finds and reads the file, and `False` when the file is absent — this distinguishes "an explicit file must exist" (absence → error) from "an implicit .env is optional" (absence → silent skip).

## Reading values without side effects

`dotenv_values` returns a `dict[str, str | None]` of pairs without touching `os.environ` — convenient for building a context object (`EnvContext.values`) and controlling application:

```python
from dotenv import dotenv_values

values = dotenv_values("./my.env")   # dict key→value; KEY= → ''; a bare key (no =) → None
```

## Behavior and limitations

- `override=False` (pybuggy behavior): variables already set in the environment (shell/CI) keep their values; `.env` does not overwrite them.
- `KEY=` (with `=`, empty value) → `''` in `dotenv_values` (an empty string, **not** `None`); a bare key `KEY` (no `=`) → `None` (the only `None` case); in `os.environ` both forms are set as `''`.
- The parser ignores comments (`# ...`) and blank lines; quotes around values are stripped.
- The library reads the file as UTF-8.
