# Plan: `env-cli`

## Purpose

Implement the **env-cli** feature — a single mechanism for loading environment variables into the pybuggy CLI.

After implementation the package must provide:

1. a **global `--env-file` option** on the root click group `main`, parsed eagerly **before** any subcommand (eager-callback), whose callback stores an `EnvContext` on `ctx.obj`;
2. **`.env` loading into `os.environ` with `override=False`** (already-set variables are never overwritten), via `python-dotenv`;
3. a **context object `EnvContext`** (pydantic, `kw_only=True`) carrying the resolved env-file path and the loaded key→value pairs;
4. a new **`PYBUGGY_REF` precedence level** in `pull`'s `_effective_ref`, read from `os.environ`, sitting strictly between the global `--ref` and the configured `git.ref`.

Most important gaps between contract and code (verified against the working tree):

- `EnvContext` and `load_env` are declared in `goga_tool_pybuggy/CODEMANIFEST` (location `env.py`) but **`env.py` does not exist** — the two contract entities are unimplemented.
- `__init__.py` `__all__` is `["install", "main", "retries"]` — `EnvContext`/`load_env` are **not exposed on the facade**.
- `cli.py::main` has **no `--env-file` option and no eager-callback** (contract `main()` Algorithm steps 2–3 are missing).
- `pull.py::_effective_ref` resolves only `per-spec → global_ref → git_ref`; the **`PYBUGGY_REF` level is missing**, and `pull.py` does **not `import os`**.

Overall strategy: a minimal-diff, contract-driven implementation across **two existing cells** — `commands/pull` (leaf, modified first) and `ROOT` (`goga_tool_pybuggy`). The two cells are coupled **only at runtime via `os.environ`** (`PYBUGGY_REF`); no new `Imports` edges, no new cells, no package-boundary expansion. `CODEMANIFEST` and `.usages/` files are **read-only** for the implementation (already materialized and audited — see design §2, §6). `python-dotenv>=1.2.2`, `click>=8.0`, `pydantic>=2.0` are already in `pyproject.toml` — no dependency changes.

---

## Context

### Contract Surface

**Entity: `main()`**  (ROOT — `location: cli.py`, MODIFY)
- Type: `class` — root click group (callable command group), exposed via `__all__`.
- Facade obligation: importable from `goga_tool_pybuggy` (entry point `pybuggy = "goga_tool_pybuggy:main"`).
- Mutations: none.
- This task covers contract `main()` **Algorithm steps 2–3** (the new parts):
  - step 2: attach the global `--env-file` option to `main` (`is_eager=True` — evaluated before any subcommand);
  - step 3: in the eager-callback, call `load_env(value)` and store the returned `EnvContext` on `ctx.obj`.
- Steps 1, 4–8 (root group, endpoint subgroup, command registration, `init` top-level) **already exist** in `cli.py` and must remain unchanged.
- Requirements carried into the task (verbatim from CODEMANIFEST):
  - `--env-file` is parsed at the group level → it **MUST precede the subcommand** (`pybuggy --env-file ./my.env endpoint pull`); after the subcommand is a click usage error.
  - env is loaded and `ctx.obj` is set **before** any subcommand is invoked.
- Constraints carried into the task: `--env-file` is the only global option added by this feature; do **not** introduce a `--config` option.
- Imported dependencies: `load_env`, `EnvContext` from the same cell (`from .env import EnvContext, load_env` — relative import).
- Annotation context: global `click` (group + `--env-file` eager-callback), `python-dotenv` (the `.env` loading performed by `load_env`).

**Entity: `load_env(env_file: str | None) -> ctx: EnvContext`**  (ROOT — `location: env.py`, NEW)
- Type: `function` (Routine) — exposed via `__all__`.
- Facade obligation: importable from `goga_tool_pybuggy`.
- Signature: `load_env(env_file)` → `EnvContext`. `env_file: str | None` (explicit path from `--env-file`, or `None` for the implicit `.env` in CWD).
- Behavioral contract (CODEMANIFEST `Algorithm`, carried verbatim into the task):
  1. Resolve the path: if `env_file` is not None, treat it as explicit — it **MUST exist**, otherwise raise `click.ClickException`; if `env_file` is None, use `.env` in the CWD and, when absent, load nothing (silent, no error).
  2. When a resolved file exists, parse it into `values` (key→value) and apply it to `os.environ` with `override=False` (already-set variables are never overwritten) via `python-dotenv`.
  3. Return an `EnvContext` with the resolved path (or `None`) and the loaded key→value values.
- Requirements (verbatim): `override=False` (already-set variables never overwritten); an explicit `--env-file` must point at a readable **regular** file — a missing file **or a non-regular file (e.g. a directory)** raises `click.ClickException`; an implicit `.env` that is absent or not a regular file in the CWD is **silent** (no error, empty values, `env_path=None`); env loading happens before any subcommand runs.
- Constraints (verbatim): do **not** read `PYBUGGY_REF` or any other specific variable here — loading is generic; consumers read `os.environ` themselves.
- Imported dependencies: `python-dotenv` (`dotenv_values`, `load_dotenv`), `click` (`ClickException`), `pathlib.Path`, `pydantic` (indirectly, via `EnvContext`).
- Annotation context: `python-dotenv` (.env parsing + os.environ application), `conventions` (code/test rules). Note: `dotenv_values` returns `dict[str, str | None]` — `KEY=` → `''` (directly, not `None`); a **bare** key without `=` → `None`. The contract `EnvContext.values` requires `dict[str, str]`, so the bare-key `None` is coerced to `""`.

**Entity: `EnvContext(env_path: str | None, values: dict[str, str])`**  (ROOT — `location: env.py`, NEW)
- Type: `class` (pydantic `BaseModel`) — exposed via `__all__`.
- Facade obligation: importable from `goga_tool_pybuggy`.
- Pure data carrier — **no behavior beyond two properties**.
- Properties:
  - `env_path -> str | None` — resolved env-file path; `None` when no file was loaded.
  - `values -> dict[str, str]` — loaded key→value pairs from the env-file.
- Requirements (verbatim): pydantic model with `kw_only=True` (all data models are pydantic per `conventions`); defaults `env_path=None`, `values={}`; exposed on the ROOT facade via `__all__` (available to consumers/tests).
- Constraints (verbatim): pure data carrier — no behavior beyond the two properties.
- Imported dependencies: `pydantic` (`BaseModel`, `ConfigDict`).

**Entity: `run_pull(spec_name, ref)`**  (pull — `location: pull.py`, MODIFY behavior only)
- Type: `function` — handler, importable from `goga_tool_pybuggy.commands.pull`. **Signature and facade exposure unchanged.**
- This task covers contract `run_pull` **Algorithm 4b** — the new `PYBUGGY_REF` precedence level inside `_effective_ref`:
  `per-spec → global --ref → PYBUGGY_REF (os.environ) → git.ref → None (default branch)`.
- Requirement carried into the task (verbatim): `PYBUGGY_REF` is read from `os.environ`; populated by the root CLI group before the command runs; its presence is optional (absent ⇒ fall through to the next precedence level).
- Constraint carried into the task (verbatim): `PYBUGGY_REF` **never overrides a per-spec or explicit global `--ref`**; it sits strictly between the global ref and the configured `git.ref`.
- The change is localized to `_effective_ref` (and `import os`); the rest of `run_pull` (clone+copy, `_validate_*`, `_resolve_refs`, `_validate_per_spec_refs`) is **untouched**.

**Unchanged entities (in scope-area but not modified by env-cli):** `retries` (ROOT), `pull_cmd`, `SmartParam` (pull), `->install: {}` (ROOT re-export). No task modifies them.

### Re-exports

- `->install: {}` (ROOT) — unchanged. Source: `install` from `goga_tool_pybuggy/plugin` via `Imports`. Facade obligation: `install` must remain importable from `goga_tool_pybuggy` (already satisfied; **do not touch**).
- `EnvContext` and `load_env` are **first-class facade members** of the ROOT cell (declared at `location: env.py`), exposed through `__all__` — they are not re-export blocks (`->`) but must be importable from `goga_tool_pybuggy`. This is the facade obligation implemented in **Task 2**.

### Usages Context

- **`conventions`** (`.goga/usages/conventions.md`) — project-wide code/test rules: pydantic `kw_only=True` for data models; `typing.Optional` for nullable types (ruff `UP045` is ignored in `pyproject.toml`); relative intra-package imports; Google-style docstrings on all public functions/methods/classes; CLI handlers tested by **direct Python call** (no `CliRunner` except for click-parsing behavior); test layout `tests/<package>/test_<module>.py`; deps pinned in `pyproject.toml`. Relevant to **all** tasks.
- **`click`** (`.goga/usages/cooks/click.md`) — click 8.x group/option/**eager-callback**/`ClickException`; in click 8.x `Context.obj` is auto-inherited by child contexts when not set. Relevant to **Task 2** (`load_env` raises `ClickException`) and **Task 3** (`main` group + `--env-file` eager-callback).
- **`python-dotenv`** (`.goga/usages/cooks/python-dotenv.md`) — `dotenv_values(path)` returns `dict[str, str | None]` (no side effects); `load_dotenv(path, override=False)` writes into `os.environ` without overwriting existing vars. Relevant to **Task 2** (`load_env`).
- **`gitpython`** (`.goga/usages/cooks/gitpython.md`, pull cell) — `Repo.clone_from(depth=1, branch=ref)` shallow-clone as a context manager. **Unchanged** by env-cli (used by the pre-existing `clone_repo`); referenced only because **Task 4** mocks `clone_repo` for the `PYBUGGY_REF` integration tests.

### Imported Usages

- None new for env-cli. The pull cell imports `configuration` from `goga_tool_pybuggy/config` (`.usages/configuration.md`) — **unchanged**; existing `run_pull` integration tests already exercise config loading.

### Local Usages

No local usage-file tasks. Design §6 (consistency of `.usages/`) confirms both cell-level usage files are already materialized and audited, matching the updated contracts — no new files, no edits:

- `goga_tool_pybuggy/.usages/assembly.md` — describes `main`, `load_env`, `EnvContext`, `--env-file` before the subcommand, `override=False` (matches ROOT contracts). **Status: existing, up to date — do not modify.**
- `goga_tool_pybuggy/commands/pull/.usages/pull.md` — documents the `PYBUGGY_REF` env variable and the precedence `per-spec → global --ref → PYBUGGY_REF → git.ref → default branch` (matches `run_pull` Algorithm 4b). **Status: existing, up to date — do not modify.**

### External Dependencies

- **python-dotenv** (`dotenv_values`, `load_dotenv`) — third-party; `>=1.2.2` pinned in `pyproject.toml`. Used by `load_env`.
- **click** (`group`, `option`, eager `callback`, `ClickException`, `Context.obj` inheritance; `click.testing.CliRunner` for one parsing-behavior test) — `>=8.0` pinned.
- **pydantic** (`BaseModel`, `ConfigDict`) — `>=2.0` pinned. Used by `EnvContext`.
- **gitpython** (`Repo.clone_from`) — `>=3.1` pinned; **mocked** at the import point in Task 4 integration tests (`goga_tool_pybuggy.commands.pull.pull.clone_repo`).
- **pytest** (`monkeypatch`, `tmp_path`, `pytest.raises`, `CliRunner`) — test-only, under `[project.optional-dependencies].test`.

---

## Facts

- `goga_tool_pybuggy/env.py` does **not** exist; `EnvContext` and `load_env` are unimplemented.
- `goga_tool_pybuggy/__init__.py` `__all__ == ["install", "main", "retries"]` — no `EnvContext`/`load_env`.
- `goga_tool_pybuggy/cli.py::main` is `@click.group() def main()` with no options; `endpoint_group` and command registration exist and are unchanged.
- `goga_tool_pybuggy/commands/pull/pull.py` does **not** `import os`; `_effective_ref` returns `per_spec[name]` → `global_ref` → `git_ref` (three levels).
- `run_pull` already calls `_effective_ref(name, entry.git.ref, global_ref, per_spec)` — the new `PYBUGGY_REF` level is inserted inside `_effective_ref`; `run_pull`'s call site is unchanged.
- ROOT ↔ pull are coupled **only at runtime via `os.environ`** (`PYBUGGY_REF`); there is **no new `Imports` edge and no cycle** (verified against both CODEMANIFEST `Imports` and source).
- `tests/commands/pull/test_pull.py` **already exists** (~21 KB) and already contains: `test_run_pull_importable_from_facade`, `test_run_pull_signature` (the pull **contract tests** — they must keep passing), and a reusable stub pattern — `monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)` to point `load_config` at a `tmp_path` config + `with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone`. **No `tests/commands/pull/conftest.py`** exists; the existing tests are self-contained per test (no shared fixture needed).
- `tests/test_cli.py` **already exists** and asserts command registration (`init` top-level, pull/list/info/generate under `endpoint`); it must keep passing and is **not** modified by env-cli.
- `tests/test_env.py` and `tests/test_cli_env.py` do **not** exist (NEW).
- `python-dotenv>=1.2.2`, `click>=8.0`, `pydantic>=2.0` are present in `pyproject.toml` — no dependency changes.
- `pyproject.toml` ruff config: `target-version = "py310"`, `line-length = 120`; `UP045` ignored (use `typing.Optional`), `N999` ignored (entity modules are PascalCase per `location`). Tests under `tests/**/*.py` have per-file ignores (`S101`, `ARG001/2`, `PLR2004`, `RUF001`, `PLC0415`).

## Gap Analysis

- **Missing contract entities:** `EnvContext`, `load_env` (`env.py` absent).
- **Missing facade exposure:** `EnvContext`, `load_env` not in `__all__`.
- **Missing behavior (ROOT):** `main()` `--env-file` eager option + eager-callback (Algorithm steps 2–3).
- **Missing behavior (pull):** `PYBUGGY_REF` precedence level in `_effective_ref` (Algorithm 4b); `pull.py` lacks `import os`.
- **Behavioral gaps to cover:** `override=False` invariant; silent implicit `.env`; bare-key `None → ""` coercion; directory-as-`--env-file` error; `ctx.obj` auto-inheritance in click 8.x; `PYBUGGY_REF` precedence vs per-spec/global/`git.ref`; empty `PYBUGGY_REF` fall-through.
- **Test coverage gaps:** scenarios T1–T15 from design §7 are all unimplemented.
- **Existing code to reuse (minimal diff):** `cli.py::main` group + endpoint registration; `_effective_ref`/`run_pull`/`clone_repo` in pull; the existing `test_pull.py` stub pattern (`CONFIG_PATH_ATTR` + `clone_repo` patch) for the new integration test; existing `test_cli.py` registration assertions (keep).
- **No package-boundary expansion:** no new cells, no new `Imports`, no new `.usages/` files, no `CODEMANIFEST`/`.usages` edits.

---

## Tasks

> **Cell ordering:** leaf (`commands/pull`) first, then ROOT — ROOT imports `pull_cmd` from pull. Within each coding task, contract tests are written first (TDD workflow). **One ralphex task per iteration.**

### Task 1: `PYBUGGY_REF` precedence level in `_effective_ref` (TDD coding — pull cell)

Modify `goga_tool_pybuggy/commands/pull/pull.py` to implement contract `run_pull` **Algorithm 4b**: insert a `PYBUGGY_REF` precedence level — read from `os.environ` — strictly **between** the global ref and the configured `git.ref`. The contract surface of `run_pull` is unchanged (signature and facade exposure stay identical); only internal behavior changes inside `_effective_ref` plus `import os`.

**Code Stack Trace to implement (verbatim from design §4.4):**

> `_effective_ref(name, git_ref, global_ref, per_spec)` must resolve: `per-spec → global → PYBUGGY_REF(os.environ) → git.ref`.
>
> ```python
> import os  # add to the module's existing imports
>
> def _effective_ref(name, git_ref, global_ref, per_spec):
>     """Resolve the effective ref: per-spec → global → PYBUGGY_REF(os.environ) → git.ref."""
>     if name in per_spec:
>         return per_spec[name]
>
>     if global_ref is not None:
>         return global_ref
>
>     pybuggy_ref = os.environ.get("PYBUGGY_REF")
>     if pybuggy_ref:
>         return pybuggy_ref
>
>     return git_ref
> ```
>
> Effective-ref trace (spec `client`, `git.ref="main"`, no `--ref`, no per-spec):
> 1. `name in per_spec` → False. 2. `global_ref is not None` → False. 3. `os.environ.get("PYBUGGY_REF")` → `"v2"` (if `.env` held `PYBUGGY_REF=v2`) → return `"v2"`. 4. (no/empty `PYBUGGY_REF`) → return `git_ref="main"`; `None` → default branch.
>
> **Empty-string decision:** `PYBUGGY_REF` counts as "set" only when present **and non-empty** (truthiness check `if pybuggy_ref:`). `PYBUGGY_REF=` (empty) is treated as unset → fall through to `git.ref` (an empty ref is meaningless as an override and would be a clone error).
>
> **Contract checkpoints:** per-spec and explicit global `--ref` are **not** overridden by `PYBUGGY_REF` (checked earlier) ✓; `PYBUGGY_REF` overrides `git.ref` ✓; absence/`None` at any level → continue ✓. The rest of `run_pull` (clone+copy, `_validate_*`, `_resolve_refs`, `_validate_per_spec_refs`) is **unchanged**.

**Usages relevant to this task:**
- `conventions`: keep the existing Google-style docstring on `_effective_ref`; update it to state the 4-level precedence. Use `typing.Optional` (already used in the file). Relative imports unchanged. Tests call the handler/helper **directly** (no `CliRunner`); isolate `os.environ` with `monkeypatch`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this is Task 1 — `PYBUGGY_REF` precedence in `_effective_ref` (`pull.py`).
- [x] **Contract tests**: verify the pull contract surface is intact — `run_pull` is importable from the facade `goga_tool_pybuggy.commands.pull` and its signature `(spec_name, ref=None)` is unchanged. (The existing `test_run_pull_importable_from_facade` and `test_run_pull_signature` in `tests/commands/pull/test_pull.py` already cover this — confirm they still pass after the edit; no new contract test is required because the contract surface of `run_pull` did not change.)
- [x] **Code**: add `import os` to the existing imports of `goga_tool_pybuggy/commands/pull/pull.py`.
- [x] **Code**: in `_effective_ref`, insert the `PYBUGGY_REF` level between the `global_ref` check and the `return git_ref` — `pybuggy_ref = os.environ.get("PYBUGGY_REF")`; `if pybuggy_ref: return pybuggy_ref`. Update the docstring to the 4-level precedence `per-spec → global → PYBUGGY_REF → git.ref`.
- [x] **Interface verification**: run `pytest tests/commands/pull/test_pull.py::test_run_pull_importable_from_facade tests/commands/pull/test_pull.py::test_run_pull_signature -v` — both must pass (contract surface intact).
- [x] **Logic tests** (append to `tests/commands/pull/test_pull.py`; import the helper directly: `from goga_tool_pybuggy.commands.pull.pull import _effective_ref`; isolate env via `monkeypatch`):
  - **T7 — `test_effective_ref_uses_pybuggy_ref_when_no_override`** (Positive): Setup `monkeypatch.setenv("PYBUGGY_REF","v2")`; call `_effective_ref("client", git_ref="main", global_ref=None, per_spec={})`; assert result `"v2"`. (Base scenario: `PYBUGGY_REF` fills the gap between global ref and git.ref.)
  - **T8 — `test_effective_ref_global_ref_overrides_pybuggy_ref`** (Precedence): Setup `monkeypatch.setenv("PYBUGGY_REF","v2")`; call with `global_ref="v3"`; assert `"v3"` (NOT `"v2"`) — explicit global `--ref` beats `PYBUGGY_REF`.
  - **T9 — `test_effective_ref_per_spec_overrides_pybuggy_ref`** (Precedence): Setup `monkeypatch.setenv("PYBUGGY_REF","v2")`; call with `per_spec={"client":"v1"}`; assert `"v1"` — per-spec is top priority.
  - **T10 — `test_effective_ref_pybuggy_ref_overrides_git_ref`** (Precedence): Setup `monkeypatch.setenv("PYBUGGY_REF","v2")`; call with `git_ref="main"`, `global_ref=None`, `per_spec={}`; assert `"v2"` (NOT `"main"`) — key semantics of the new level.
  - **T11 — `test_effective_ref_empty_pybuggy_ref_falls_through`** (Edge): Setup `monkeypatch.setenv("PYBUGGY_REF","")`; call with `git_ref="main"`, `global_ref=None`, `per_spec={}`; assert `"main"` — empty `PYBUGGY_REF` is treated as unset (truthiness).
- [x] **Debugging**: run `pytest tests/commands/pull/test_pull.py -v` — fix implementation code until all tests pass (do NOT fix test code).
- [x] **Contract re-verification**: confirm `_effective_ref` still returns the prior-level result when `PYBUGGY_REF` is unset (no regression for the pre-existing 3-level behavior); confirm the `run_pull` call site is unchanged.
- [x] **Lint**: `ruff check goga_tool_pybuggy/commands/pull/pull.py` and `ruff format goga_tool_pybuggy/commands/pull/pull.py` — fix formatting/decompose if necessary. (ruff check passes; the only `ruff format` flags are pre-existing multi-line defs already present at HEAD under ruff 0.16.1 — none introduced by this change.)

### Task 2: Create `env.py` (`EnvContext` + `load_env`) and expose on the facade (TDD coding — ROOT cell)

Create `goga_tool_pybuggy/env.py` with two new contract entities — `EnvContext` (pydantic Entity) and `load_env` (Routine) — and add them to the ROOT facade via `__all__` in `__init__.py`. Both entities share `location: env.py`; `EnvContext` is the data carrier returned by `load_env`, so the two are implemented together. `EnvContext` must be importable from `goga_tool_pybuggy` (contract requirement: "Exposed on the ROOT facade via `__all__`") — hence the `__init__.py` edit is part of this task so the facade contract test passes within it.

**Code Stack Trace to implement (verbatim from design §4.2–4.3):**

> **`load_env(env_file: Optional[str]) -> EnvContext`:**
> 1. **In:** `env_file` — explicit path from `--env-file`, or `None` (implicit `.env` in CWD).
> 2. **Resolve path (Algorithm 1):**
>    - `env_file is not None` → **explicit**: `path = Path(env_file)`; it must be a readable **regular** file (`is_file()`): if `not path.exists()` → `raise click.ClickException(f"env file not found: {env_file}")`; if it exists but is not a file (e.g. a directory) → `raise click.ClickException(f"env file is not a regular file: {env_file}")`.
>    - `env_file is None` → **implicit**: `path = Path(".env")`; if `not path.is_file()` (absent **or** not a regular file, e.g. a directory named `.env`) → `return EnvContext()` (silent, `env_path=None`, `values={}`).
> 3. **Read values:** `raw = dotenv_values(str(path))` → `dict[str, str | None]` (no side effects; `python-dotenv` 1.2.2). Semantics: `KEY=val` → `'val'`; `KEY=` (with `=`, empty value) → `''` (**not** `None`); a **bare** key `KEY` (no `=`) → `None`. Coerce `None → ""` (needed for bare keys — otherwise the `dict[str, str]` contract would break): `values = {k: (v if v is not None else "") for k, v in raw.items()}`.
> 4. **Apply to `os.environ` (Algorithm 2):** `load_dotenv(str(path), override=False)` — `override=False` passed **explicitly** (contract invariant); already-set variables are not overwritten.
> 5. **Out:** `return EnvContext(env_path=str(path), values=values)`.
>
> **Two-representation distinction (intentional):** `EnvContext.values` = the file's contents (all pairs, including those that did not overwrite an existing env var); `os.environ` after `load_dotenv(override=False)` = the file applied **without** overwriting already-set vars. No inconsistency.
>
> Target `env.py` implementation (verbatim):
>
> ```python
> """Environment loading for the pybuggy CLI: .env → os.environ (override=False)."""
>
> from pathlib import Path
> from typing import Optional
>
> import click
> from dotenv import dotenv_values, load_dotenv
> from pydantic import BaseModel, ConfigDict
>
>
> class EnvContext(BaseModel):
>     """Context object carrying the resolved env-file path and loaded key→value pairs.
>
>     Stored on click ctx.obj by main(); pure data carrier.
>     """
>
>     model_config = ConfigDict(kw_only=True)
>
>     env_path: Optional[str] = None
>     values: dict[str, str] = {}
>
>
> def load_env(env_file: Optional[str]) -> EnvContext:
>     """Resolve the env-file, load it into os.environ (override=False), and return EnvContext.
>
>     Args:
>         env_file: explicit path from --env-file, or None for the implicit .env in CWD.
>
>     Returns:
>         EnvContext with the resolved path and loaded key→value pairs.
>
>     Raises:
>         click.ClickException: when an explicit --env-file points at a missing file.
>     """
>     if env_file is not None:
>         path = Path(env_file)
>         if not path.exists():
>             raise click.ClickException(f"env file not found: {env_file}")
>         if not path.is_file():
>             raise click.ClickException(f"env file is not a regular file: {env_file}")
>     else:
>         path = Path(".env")
>         if not path.is_file():
>             return EnvContext()
>
>     values = {k: (v if v is not None else "") for k, v in dotenv_values(str(path)).items()}
>     load_dotenv(str(path), override=False)
>
>     return EnvContext(env_path=str(path), values=values)
> ```
>
> **Checkpoints:** `Optional[str]` per `conventions` (ruff `UP045` ignored) ✓; `kw_only=True` via `ConfigDict` ✓; mutable-default `values={}` is safe in pydantic v2 (deep-copied per instance; `Field(default_factory=dict)` is the alternative) ✓; relative import `from .env import ...` in `cli.py` ✓.

**Facade export (verbatim from design §4.3):**

> `__init__.py` (MODIFY):
> ```python
> from .cli import main
> from .env import EnvContext, load_env
> from .plugin import install
> from .tools import retries
>
> __all__ = ["EnvContext", "install", "load_env", "main", "retries"]
> ```

**Usages relevant to this task:**
- `python-dotenv`: `dotenv_values(path)` for reading pairs (no side effects); `load_dotenv(path, override=False)` to apply into `os.environ` without overwriting.
- `conventions`: pydantic `kw_only=True`; `typing.Optional[str]` for nullable `env_path`; relative import `from .env import ...`; Google-style docstrings on `EnvContext` and `load_env`; deps already in `pyproject.toml`. Test `load_env` by **direct call**; FS via `tmp_path`; isolate `os.environ` via `monkeypatch.delenv(..., raising=False)` / `setenv` and `monkeypatch.chdir`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION)**: declare this is Task 2 — create `env.py` (`EnvContext` + `load_env`) and expose on the ROOT facade.
- [x] **Contract tests** (new file `tests/test_env.py`; expected to fail at this stage): `EnvContext` importable from the facade (`from goga_tool_pybuggy import EnvContext`); `EnvContext` is a `pydantic.BaseModel` subclass; `load_env` importable from the facade (`from goga_tool_pybuggy import load_env`); `load_env` is callable with one positional arg and returns an `EnvContext` (`inspect.signature` → one parameter `env_file`).
- [x] **Code**: create `goga_tool_pybuggy/env.py` with the `EnvContext` model and the `load_env` routine exactly as specified above (resolve via `is_file()`, bare-key `None → ""` coercion, `load_dotenv(..., override=False)`, `ClickException` on explicit missing **or non-regular** file).
- [x] **Code**: modify `goga_tool_pybuggy/__init__.py` — add `from .env import EnvContext, load_env` and include `"EnvContext"`, `"load_env"` in `__all__` (alphabetical, as above).
- [x] **Interface verification**: run `pytest tests/test_env.py -v` for the contract tests above and `python -c "from goga_tool_pybuggy import EnvContext, load_env; import inspect; assert inspect.signature(load_env).parameters.get('env_file') is not None"` — facade import + shape must pass.
- [x] **Logic tests** (append to `tests/test_env.py`; isolate env + cwd via `monkeypatch`):
  - **T6 — `test_env_context_defaults`** (Edge — model): call `EnvContext()`; assert `env_path is None`, `values == {}`, and `ctx.model_config.get("kw_only") is True` (constructor is kw-only).
  - **T1 — `test_load_env_explicit_file_applies_and_returns_context`** (Positive): `tmp_path/.env` with `PYBUGGY_REF=v2\nDEBUG=1`; `monkeypatch.delenv` for both; `monkeypatch.chdir(tmp_path)`; call `load_env(str(tmp_path / ".env"))`; assert `ctx.env_path.endswith(".env")`, `ctx.values == {"PYBUGGY_REF":"v2","DEBUG":"1"}`, `os.environ["PYBUGGY_REF"]=="v2"`, `os.environ["DEBUG"]=="1"`.
  - **T2 — `test_load_env_explicit_missing_file_raises_clickexception`** (Negative): `pytest.raises(click.ClickException)` on `load_env(str(tmp_path / "nope.env"))`; message contains "env file not found".
  - **T3 — `test_load_env_implicit_dotenv_absent_is_silent`** (Edge): empty `tmp_path` (no `.env`); `monkeypatch.chdir(tmp_path)`; `monkeypatch.delenv("PYBUGGY_REF")`; call `load_env(None)`; assert `ctx.env_path is None`, `ctx.values == {}`, no exception, `os.environ` unchanged (`PYBUGGY_REF` absent).
  - **T4 — `test_load_env_does_not_override_existing_env_var`** (Edge — override=False): `tmp_path/.env` with `PYBUGGY_REF=fromfile`; `monkeypatch.setenv("PYBUGGY_REF","fromshell")`; `monkeypatch.chdir(tmp_path)`; call `load_env(None)`; assert `ctx.values == {"PYBUGGY_REF":"fromfile"}` AND `os.environ["PYBUGGY_REF"]=="fromshell"` (not overwritten).
  - **T5 — `test_load_env_key_without_value_coerced_to_empty`** (Edge — `KEY=` and bare key): `tmp_path/.env` with `EMPTY=\nBARE\nFULL=x` (`EMPTY=` with `=` empty value; `BARE` bare key); `monkeypatch.chdir(tmp_path)`; call `load_env(None)`; assert `ctx.values["EMPTY"]==""` (direct `''`), `ctx.values["BARE"]==""` (via `None→""` coercion), `ctx.values["FULL"]=="x"`; all values are `str` (no `None`).
  - **T5b — `test_load_env_explicit_directory_raises_clickexception`** (Negative — directory as `--env-file`): `tmp_path/subdir/` (existing dir); `monkeypatch.chdir(tmp_path)`; `pytest.raises(click.ClickException)` on `load_env(str(tmp_path / "subdir"))`; message contains "not a regular file" (raised before `dotenv_values`/`load_dotenv`).
- [x] **Debugging**: run `pytest tests/test_env.py -v` — fix implementation code until all tests pass (do NOT fix test code).
- [x] **Contract re-verification**: confirm `EnvContext` is pydantic with `kw_only=True`, defaults `env_path=None`/`values={}`; confirm `load_env` returns `EnvContext` for both explicit and implicit paths; confirm `load_env` does **not** read `PYBUGGY_REF` specifically (generic loading only — constraint).
- [x] **Lint**: `ruff check goga_tool_pybuggy/env.py goga_tool_pybuggy/__init__.py` and `ruff format goga_tool_pybuggy/env.py goga_tool_pybuggy/__init__.py` — fix formatting/decompose if necessary.

### Task 3: `--env-file` eager option + eager-callback on `main` (TDD coding — ROOT cell)

Modify `goga_tool_pybuggy/cli.py` to implement contract `main()` **Algorithm steps 2–3**: attach the global `--env-file` option (eager) to `main`, and define `_load_env_callback`, which calls `load_env(value)` and stores the returned `EnvContext` on `ctx.obj`. `_load_env_callback` is an **internal helper** (not a contract entity) realizing the `main()` eager-callback step. The existing `endpoint_group` and command registration are untouched.

**Code Stack Trace to implement (verbatim from design §4.1):**

> **Trace:** `pybuggy --env-file ./my.env endpoint pull`:
> 1. click parses group options; `--env-file` is declared `is_eager=True` with `callback=_load_env_callback` → callback fires **before** the subcommand is chosen/invoked.
> 2. `_load_env_callback(ctx, _param, value)`: `ctx.obj = load_env(value)`; `return value` (the option value is passed through unchanged — it is only needed to trigger env loading).
> 3. `load_env(value)` (Task 2) returns `EnvContext`; side effect — writes `os.environ` (`override=False`).
> 4. `ctx.obj` is inherited by child contexts (click 8.x: `Context.obj` auto-inherits from `parent.obj` when not set); `click>=8.0` in `pyproject.toml` guarantees this — subcommands see the same `EnvContext`.
> 5. Subcommand invocation (`pull`): `run_pull` reads `os.environ["PYBUGGY_REF"]` (Task 1) — the value `load_env` put there (if `.env` held it).
> 6. **Option order:** because `--env-file` is parsed at the group level, it must come **before** the subcommand (`... endpoint pull --env-file f` → exit 2 "No such option") — click behavior, asserted by T14.
>
> Target `cli.py` fragment (verbatim):
>
> ```python
> import click
>
> from .commands.generate import generate_cmd
> from .commands.info import info_cmd
> from .commands.init import init_cmd
> from .commands.list import list_cmd
> from .commands.pull import pull_cmd
> from .env import EnvContext, load_env
>
>
> def _load_env_callback(ctx: click.Context, _param: click.Parameter, value: str | None) -> str | None:
>     """Eager-callback: load .env into os.environ and store EnvContext on ctx.obj."""
>     ctx.obj = load_env(value)
>     return value
>
>
> @click.group()
> @click.option(
>     "--env-file",
>     "env_file",
>     default=None,
>     callback=_load_env_callback,
>     is_eager=True,
>     help="Path to a .env file loaded into os.environ (override=False) before the command runs.",
> )
> def main(env_file: str | None) -> None:
>     """pybuggy — CLI tool for work with OpenAPI/Swagger endpoints."""
> ```
>
> **Checkpoints:** `value: str | None` matches `load_env` input ✓; `ctx.obj` is `EnvContext` ✓; inheritance via click 8.x ✓. The existing `endpoint_group` and command registration do **not** change.
>
> **Edge:** the eager-callback fires on every group invocation (even without `--env-file` → `value=None` → implicit `.env` from CWD); for `--help` click short-circuits — harmless. `invoke_without_command` is not set (existing behavior "`pybuggy` with no subcommand → help, exit 2" is preserved).

**Usages relevant to this task:**
- `click`: declare the `--env-file` option with `is_eager=True` and `callback=_load_env_callback`; `ctx.obj` auto-inherits to child contexts (click 8.x). Test the eager-callback by **direct call** (per `conventions`, no `CliRunner`); `CliRunner` is justified **only** for the click-parsing-behavior test (option-order, exit 2).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 (DECLARATION)**: declare this is Task 3 — `--env-file` eager option + `_load_env_callback` on `main` (`cli.py`).
- [ ] **Contract tests** (new file `tests/test_cli_env.py`; expected to fail at this stage): `main` is importable and is a click command/group (`isinstance(main, click.BaseCommand)`); `main` has an `--env-file` option in its params (e.g. `"env_file"` in `main.params` names, or `"--env-file"` in `main.get_help_option(...)`); `_load_env_callback` exists in `goga_tool_pybuggy.cli`.
- [ ] **Code**: add the relative import `from .env import EnvContext, load_env` to `cli.py`.
- [ ] **Code**: define `_load_env_callback(ctx, _param, value)` (`ctx.obj = load_env(value); return value`) and decorate `main` with `@click.option("--env-file", "env_file", default=None, callback=_load_env_callback, is_eager=True, help=...)`. Add the `env_file: str | None` parameter to `main`. Leave `endpoint_group` and command registration unchanged.
- [ ] **Interface verification**: run `pytest tests/test_cli_env.py -v` for the contract tests above; additionally run the pre-existing `pytest tests/test_cli.py -v` to confirm command registration is intact (no regression).
- [ ] **Logic tests** (append to `tests/test_cli_env.py`):
  - **T13 — `test_env_file_callback_sets_ctx_obj`** (Direct handler call — preferred): `tmp_path/.env` with `PYBUGGY_REF=v2`; `monkeypatch.chdir(tmp_path)`; build a fake ctx (`types.SimpleNamespace(obj=None)`); call `_load_env_callback(ctx, param=None, value=str(tmp_path / ".env"))` directly; assert `isinstance(ctx.obj, EnvContext)`, `ctx.obj.values["PYBUGGY_REF"]=="v2"`, `os.environ["PYBUGGY_REF"]=="v2"`, and the return value equals the input `value`.
  - **T14 — `test_env_file_option_must_precede_subcommand`** (CLI-parsing behavior — `CliRunner` justified): with a `click.testing.CliRunner` and isolated env, invoke `runner.invoke(main, ["endpoint", "pull", "--env-file", "x.env"])` (option AFTER the subcommand); assert `result.exit_code == 2` and the output contains "No such option".
- [ ] **Debugging**: run `pytest tests/test_cli_env.py -v` — fix implementation code until all tests pass (do NOT fix test code).
- [ ] **Contract re-verification**: confirm `main` is still the package entry point (`from goga_tool_pybuggy import main`); confirm `endpoint`/`init` registration unchanged (the pre-existing `tests/test_cli.py` assertions still pass); confirm `_load_env_callback` stores an `EnvContext` on `ctx.obj` and passes `value` through.
- [ ] **Lint**: `ruff check goga_tool_pybuggy/cli.py` and `ruff format goga_tool_pybuggy/cli.py` — fix formatting/decompose if necessary.

### Task 4: Integration tests for the env-cli runtime coupling (integration — ROOT ↔ pull)

Verify the cross-entity / cross-cell runtime coupling that the env-cli feature depends on: `PYBUGGY_REF` flows from `load_env` (ROOT writes `os.environ`) through to `run_pull` (pull reads `os.environ`) and into the git clone ref. These are integration tests (mock only at the external boundary — the git clone), not unit tests, and do not replace the per-entity contract/logic tests from Tasks 1–3.

**Usages relevant to this task:**
- `conventions`: integration tests covering multiple packages go directly under `tests/` (`tests/test_cli_env.py`); mock only at the external boundary — patch `clone_repo` at its import point (`goga_tool_pybuggy.commands.pull.pull.clone_repo`); FS via `tmp_path`; isolate `os.environ` via `monkeypatch` (`delenv`/`setenv`); point `load_config` at a temp config via the existing `CONFIG_PATH_ATTR` stub pattern from `tests/commands/pull/test_pull.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **T12 — `test_run_pull_reads_pybuggy_ref_from_environ`** (Integration via handler — append to `tests/commands/pull/test_pull.py`): Setup `monkeypatch.setenv("PYBUGGY_REF","v2")`; a config with one spec `client` (`git.ref=None`, `git.url=...`, `git.location=spec.yml`) pointed at via the existing `monkeypatch.setattr(CONFIG_PATH_ATTR, config_path)` pattern; `with patch("goga_tool_pybuggy.commands.pull.pull.clone_repo") as mock_clone:` with a fake repo root. Input: `run_pull(spec_name="client")` (no `ref`). Assert the mocked clone was called with `ref="v2"` (assert on the mock call args). Sufficiency: `run_pull` really reads `PYBUGGY_REF` from `os.environ` and passes it to clone. (Reuse the existing `clone_repo`-patch + `CONFIG_PATH_ATTR` stub pattern already in `test_pull.py`; **no `conftest.py` needed**.)
- [ ] **T15 — `test_load_env_then_run_pull_env_coupling`** (End-to-end runtime coupling ROOT↔pull — append to `tests/test_cli_env.py`): Setup `tmp_path/.env` with `PYBUGGY_REF=v2`; `monkeypatch.delenv("PYBUGGY_REF")`; a temp config + mocked `clone_repo` (same pattern as T12). Input: first `load_env(str(tmp_path / ".env"))`, then `run_pull(spec_name="client")`. Assert: after `load_env`, `os.environ["PYBUGGY_REF"]=="v2"`; the mocked clone is called with `ref="v2"`. Sufficiency: proves the feature's foundation — the runtime bridge ROOT → `os.environ` → pull through `PYBUGGY_REF` (loose coupling, no `Imports`).
- [ ] **Run validation**: `pytest tests/test_cli_env.py tests/commands/pull/test_pull.py -v` — all integration tests (plus the prior logic tests in those files) pass.
- [ ] **Full-suite regression**: `pytest tests/ -x` — the entire suite (including the pre-existing `test_cli.py`, `test_pull.py`, `test_cli_integration.py`, etc.) passes.

---

## Validation Commands

> All commands run inside the project virtualenv (create if missing), Python 3.10+.

- `pytest tests/test_env.py -v`: env entity tests (`EnvContext`, `load_env` — T1–T6, T5b).
- `pytest tests/commands/pull/test_pull.py -v`: pull precedence tests (`_effective_ref` — T7–T11; `run_pull` contract + T12 integration; existing pull suite).
- `pytest tests/test_cli_env.py -v`: `main` eager-callback + option-order (T13, T14) + runtime coupling (T15).
- `pytest tests/ -x`: run all tests (full-suite regression).
- `ruff check goga_tool_pybuggy/ tests/`: lint source and tests.
- `ruff format goga_tool_pybuggy/ tests/`: format source and tests.
- `python -c "from goga_tool_pybuggy import EnvContext, load_env, main"`: facade accessibility (all feature entities importable from the package root).

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`: `EnvContext`, `load_env` in `goga_tool_pybuggy/env.py`; `main` eager-callback in `goga_tool_pybuggy/cli.py`; `run_pull` Algorithm 4b behavior in `goga_tool_pybuggy/commands/pull/pull.py`.
- [x] Every feature entity is accessible from the facade: `EnvContext`, `load_env`, `main` importable from `goga_tool_pybuggy` (`__all__` updated).
- [x] Properties and methods match the declared API: `EnvContext.env_path -> str | None`, `EnvContext.values -> dict[str, str]`; `load_env(env_file: Optional[str]) -> EnvContext`; `run_pull(spec_name, ref=None)` signature unchanged.
- [ ] Descriptions are reflected in behavior: `override=False` invariant; silent implicit absent `.env`; bare-key `None → ""` coercion; directory-as-`--env-file` → `ClickException`; `--env-file` must precede the subcommand (exit 2); `PYBUGGY_REF` precedence `per-spec → global → PYBUGGY_REF → git.ref → None` with empty-string fall-through.
- [x] Contract dependencies are met: `load_env`/`EnvContext` from `env.py`; `click`, `python-dotenv`, `pydantic` from `pyproject.toml`; `os.environ` runtime bridge (no new `Imports`).
- [x] Re-exports are accessible from the facade: `install` still importable from `goga_tool_pybuggy` (unchanged); `EnvContext`/`load_env` importable as first-class facade members.
- [ ] Every coding task (Tasks 1–3) followed the TDD workflow (contract tests → code → interface verification → logic tests → debugging → contract re-verification → lint).
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task (T1–T14); integration tests (Task 4: T12, T15) cover the cross-entity / cross-cell runtime coupling.
- [ ] Integration tests exist for the cross-cell scenario (ROOT ↔ pull via `PYBUGGY_REF`).
- [ ] No package boundary was expanded (no new cells, no new `Imports` edges, no new `.usages/` files).
- [ ] `CODEMANIFEST` and `.usages/` files were not modified (contract is read-only — already materialized and audited).
- [ ] All validation commands pass (`pytest tests/ -x`, `ruff check`, `ruff format`, facade import).
- [ ] Every Usages entry is referenced in at least one task: `conventions` (Tasks 1–4), `click` (Tasks 2–4), `python-dotenv` (Task 2), `gitpython` (Task 4, mocked).
