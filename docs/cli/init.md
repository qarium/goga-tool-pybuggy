# CLI — `pybuggy init`

Initializes the goga project and bootstraps the consumer's pybuggy environment. Top-level
command (not under `endpoint`); also available as `python -m goga_tool_pybuggy init`.

```bash
pybuggy init
```

## What the command does

1. **Goga project initialization** (in-process, offline). Creates `.goga/config.yml` when
   missing; when present — asks whether to re-create it (default: no). The language is
   fixed to `python`; the goga "Download base convention" question is not asked — no
   network calls. The mandatory `.goga/Dockerfile` is generated with the appended line
   `RUN goga install pybuggy -v 1.0.x`.
2. **Conventions slot**. `.goga/usages/conventions.md` is overwritten with the package
   asset — **always**, with no confirmations (package-owned file; local edits are not
   preserved). A legacy goga-downloaded convention migrates automatically.
3. **Review-executor flag**. `.goga/config.yml` is brought to
   `build.review_executor.skip: true` — idempotently and round-trip (comments, key order
   and the remaining `build` content are preserved).
4. **Usages registration**. `api.md`/`asserts.md` are copied to
   `.goga/usages/cooks/pybuggy/` and registered in `codemanifest.usages` under
   `pybuggy-api`/`pybuggy-asserts`; annotation lines with backtick references are replaced
   or appended in `codemanifest.annotations`. Idempotent; user-defined keys are preserved.
5. **Tool config build** (interactive). Builds `.goga/tools/pybuggy/config.yml` — see below.
6. **Root conftest**. Generates `<cwd>/conftest.py` from the fixed template
   (`load_dotenv()` → `plugin.install()`); on an existing file — only on confirmation.

## Interactive tool-config build

`pybuggy init` builds `.goga/tools/pybuggy/config.yml` immediately when the file is
missing, after a confirmation (default: no) when it exists.

What is prompted:

- Scalar plugin keys, one at a time: `base_url` (required, a Jinja2 URL template — empty
  input is re-prompted), `timeout`, `data_key`, `error_key`, `retries`, `assert_timeout`,
  `assert_delay`, `assert_field_class`, `assert_response_class`. Optional keys are skipped
  with Enter.
- `headers` and `loader` are **not** prompted — written as commented examples.
- `specs`: for each spec — `name`, `type` (`swagger`|`openapi`), `location` (required),
  and an optional git block (`url`, `location`, `ref`). Multiple specs are supported;
  **at least one spec is required**.

Skipped optional scalars are emitted as commented entries (`# key:`); `specs` is emitted
as active YAML. The generated file is valid for [configuration](../configuration.md)
loading.

## Idempotency

A repeated `pybuggy init` asks before re-creating the goga config, the tool config, and
`conftest.py` (all default: no). When everything is refused, the copied `.md` files
(including `conventions.md`) are still refreshed from the package, the
`build.review_executor.skip` flag is ensured, and registration no-ops. There are no
`--force`/`--dry-run` flags.

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success (project ready or already ready + conventions + usages) |
| goga code (`1`) | Goga initialization canceled/failed — conventions slot, the review-executor flag and usages are **not** delivered |
| non-zero (`ClickException`) | Usages bootstrap or conftest write error |

## Programmatic usage

```python
from goga_tool_pybuggy.commands.init import (
    run_init, run_goga_init, init_cmd, register_usages, register_annotations,
    ensure_review_executor_skip, write_test_convention,
    build_pybuggy_config, write_pybuggy_config, write_pybuggy_conftest,
)

run_init()   # uses cwd as the output root; returns an exit code (int)
```

The interactive steps are isolated in testable seams (`run_goga_init`,
`build_pybuggy_config`); the pure parts (`write_test_convention`,
`write_pybuggy_config`, `write_pybuggy_conftest`) always write without TTY checks.

## Preconditions and side effects

- Requires the installed `goga` package (a pybuggy dependency).
- Writes to `<cwd>/.goga/` (config, usages, Dockerfile), `<cwd>/conftest.py`, and
  `.goga/tools/pybuggy/config.yml`.
- Reads assets from the **installed** package (`importlib.resources`), not from the
  checkout directory.
- No network calls; only copies the `api` cell usages — internal development cells
  (`config`/`spec`/`output`/…) are not copied.
