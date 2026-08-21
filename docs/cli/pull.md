# CLI — `pybuggy endpoint pull`

Downloads specs from git sources into local `location` directories.

```bash
pybuggy endpoint pull                          # pull all specs
pybuggy endpoint pull --spec client            # only a single spec
pybuggy endpoint pull --ref v2                 # a global ref for all pulled specs
pybuggy endpoint pull --spec client --ref v2
pybuggy endpoint pull --ref client:v1 --ref server:v2   # per-spec refs
pybuggy endpoint pull --ref v2 --ref server:v3          # global v2, server pinned to v3
```

## Options

| Option | Meaning |
|--------|---------|
| `--spec <name>` | Narrow the pull to a single spec |
| `--ref <ref>` | Repeatable. Without `:` — a **global** ref for all selected specs; `NAME:REF` — a **per-spec** override |

## The `PYBUGGY_REF` environment variable

`--ref` falls back to `PYBUGGY_REF` (bound via the click `envvar=`):

```bash
export PYBUGGY_REF=v2
pybuggy endpoint pull        # all specs at ref v2 (if there is no --ref / git.ref)
```

`PYBUGGY_REF` may live in the shell environment or in `.env` (the root CLI group loads
`.env` — implicitly from the CWD, or via the global `--env-file` flag — before the command
runs). An explicit `--ref` (global or per-spec) **fully overrides** it.

## Effective ref priority

Per spec, the first non-None value wins:

1. per-spec override (`NAME:REF`)
2. global `--ref` (explicit, or `PYBUGGY_REF` as its default)
3. `git.ref` from the [configuration](../configuration.md)
4. the remote default branch

A per-spec ref naming a spec absent from the configuration → `ClickException`. For specs
from different repositories, a global ref must exist in every repository — use per-spec
refs to vary them.

## Behavior

- A spec with a `git` block: shallow-clone of `git.url` (depth=1) at the effective ref
  into a temporary directory, then copy `git.location` → `<project_root>/<location>`
  (overwrite, idempotent).
- A spec without `git`: skipped (local-only) without an error.
- The config is loaded from the fixed path `.goga/tools/pybuggy/config.yml`.
- Clone failures and missing repo paths → `click.ClickException` (non-zero exit).

## Preconditions

- The config is valid and located at the fixed path.
- Tokens are not embedded in clone URLs — rely on git credential helpers.
- The repository is treated as read-only (no commits, no pushes).

## Programmatic usage

`run_pull` is the testable entry point (the Click wrapper only binds options):

```python
from goga_tool_pybuggy.commands.pull import run_pull

run_pull(spec_name=None)                                   # all specs
run_pull(spec_name="client")                               # one spec
run_pull(spec_name="client", ref="v2")                     # global ref
run_pull(spec_name=None, ref=(("client", "v1"), ("server", "v2")))  # per-spec
```

Note: `run_pull` does not read `PYBUGGY_REF` — the environment resolution lives in the
Click wrapper.
