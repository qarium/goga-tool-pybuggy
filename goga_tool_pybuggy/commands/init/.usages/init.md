# goga_tool_pybuggy.commands.init — goga project initialization and bootstrap of the consumer's pybuggy environment

## Domain

Under the hood, the `pybuggy init` command **initializes the goga project** (creates `.goga/config.yml` when
missing; when present — asks whether to re-create it), **occupies the `conventions` slot** with the pybuggy test
convention, and delivers the consumer-usages of the `api` cell (and its sub-cells) into the project where the
command is invoked — so that the consumer's goga agent knows how to use goga_tool_pybuggy — and generates the
target project's root `conftest.py` (a fixed template; when the file exists — overwrite only on confirmation),
so that the same command enables the plugin in the consumer's pytest suite. The audience is the integrator
wiring pybuggy into their project (`goga install pybuggy`), and the consumer's goga agent.

Goga project initialization runs in-process via the `goga` package (per-field methods of
`goga.onboarding.Questionnaire` + `FileGenerator.generate`; `InitLogic` is not used): an interactive
questionnaire + generation of `.goga/config.yml` (language/build/pipeline/codemanifest), with the Dockerfile
mandatory (`.goga/Dockerfile`, into which the `pybuggy` installation is appended after generation —
`RUN goga install pybuggy -v 1.0.x`). The "Download base convention" question is not asked of the integrator:
the `conventions` key never enters the goga answers — the language convention download does not happen,
initialization runs offline and finishes by creating `.goga/config.yml`.

The `conventions` slot (the file `.goga/usages/conventions.md` + the `codemanifest.usages` key + the annotation
line) is occupied by the pybuggy test convention: the `assets/conventions.md` asset of the installed package is
copied to `.goga/usages/conventions.md`. The file is package-owned on par with `api.md`/`asserts.md`: it is
**always** overwritten with the package version on every `pybuggy init`, with no confirmations and no existence
checks; projects with different slot content (incl. a goga convention) migrate automatically.

Then the command copies the cell-usages `api.md`/`asserts.md` to `.goga/usages/cooks/pybuggy/` and registers
them in `.goga/config.yml` under `codemanifest.usages` with the keys `pybuggy-api`/`pybuggy-asserts` (and the
`conventions` slot — with the key `conventions`), and also registers `codemanifest.annotations`: a line with a
backtick reference (`pybuggy-api`/`pybuggy-asserts`/`conventions`) is replaced with the current line when
present, added when absent; lines without a matched reference are preserved verbatim. The usages source is the
installed package (not cwd); the behavior is idempotent.

On top of that, the command **always** brings `.goga/config.yml` to the mandatory
`build.review_executor.skip: true` state (a goga flag: skip the review-executor stage during build). The fix is
idempotent and round-trip (ruamel.yaml): missing `build`/`review_executor` mappings are created; the remaining
`build` content (e.g. `task_executor` with env anchors), comments, and key order are preserved verbatim; an
installed `skip: false` is corrected to `true`; with `skip: true` already set, the file is not written at all
(byte-identical). The block is added to an existing config as well — including when goga project re-creation is
refused — so projects initialized earlier migrate automatically.

---

## Building .goga/tools/pybuggy/config.yml

Besides goga project initialization and the usages bootstrap, `pybuggy init` interactively builds the tool
configuration `.goga/tools/pybuggy/config.yml` (plugin options + the `specs` section): immediately when the file
is missing, after confirmation when it exists.

What is prompted (the interactive step isolated in `build_pybuggy_config`):
- Scalar plugin keys: `base_url` (required — a Jinja2 URL template; empty input is re-prompted and cannot be
  skipped), `timeout`, `data_key`, `error_key`, `retries`, `assert_timeout`, `assert_delay`,
  `assert_field_class`, `assert_response_class` — one at a time; optional keys can be skipped
  (Enter → skip).
- `headers` and `loader` are NOT prompted — written as commented examples.
- `specs`: for each spec, name, `type` (`swagger`|`openapi`), `location` (required), and an optional git block
  (`url`, `location`, `ref`) are prompted in sequence; multiple specs are supported. **At least one** spec is
  required — a config without specs is invalid (the first spec name is re-prompted until entered, same as
  `base_url`).

Overwriting: when `.goga/tools/pybuggy/config.yml` **does not exist**, it is built without questions; when it
**exists**, `run_init` asks via `click.confirm` (default `no`) whether to rebuild it, and rebuilds only on
`yes`. On refusal the step is skipped and the rest of `init` continues (exit 0). The re-creation decision lives
in the `run_init` orchestrator; `build_pybuggy_config` itself (and a direct programmatic call) always
overwrites the file without checks.

Emission (`write_pybuggy_config`, pure, no TTY): active values are written as `key: value`; skipped optional
scalars plus `headers` and `loader` — as commented entries (`# key:`) with an explanation; `specs` — as active
YAML. The generated file is valid for the config cell (`load_config`/`Config`): `specs` is present with the
required `SpecEntry` fields; scalar plugin keys are ignored by `Config` (extra=ignore).

---

## Generating <cwd>/conftest.py

The final step of the command: creates the target project's root `conftest.py` from a fixed template (verbatim):

```python
from dotenv import load_dotenv

load_dotenv()

from goga_tool_pybuggy import plugin

plugin.install()
```

`load_dotenv()` without arguments (`override=False` — CI/operator variables are not overwritten) is called
before `install()` — plugin options resolve from `os.environ`. When the file exists, `run_init` asks via
`click.confirm` (default `no`); on refusal the step is skipped with an INFO log, and the rest of init completes
successfully (exit 0). The overwrite decision lives in the `run_init` orchestrator; the pure write is isolated
in `write_pybuggy_conftest` (programmatically available on the facade, always writes the given path, no TTY —
tested directly).

---

## Entry point

- Console command (top-level, not under `endpoint`): `pybuggy init`
- Module run: `python -m goga_tool_pybuggy init`
- Programmatic facade import:
      from goga_tool_pybuggy.commands.init import run_init, run_goga_init, init_cmd, register_usages, register_annotations, ensure_review_executor_skip, write_test_convention

---

## Template: first run in a fresh (non-goga) project

In a project without `.goga/config.yml`:
1. The command **interactively** initializes the goga project (questions about agent/image/...; the language is
   fixed to `python`; the "Download base convention" question is not asked — no network calls, initialization
   is offline).
2. On completion, the full `.goga/config.yml` is created, then the test convention is delivered, the
   `build.review_executor.skip: true` flag is set, and the usages are registered.

      cd my-consumer-project
      pybuggy init        # → goga questionnaire (without base convention), then conventions slot + review_executor flag + usages registration

Result:
- `.goga/config.yml` — the full goga config (including the top-level `dockerfile` field) + the
  `build.review_executor.skip: true` block + the `codemanifest.usages` block with
  `conventions`/`pybuggy-api`/`pybuggy-asserts` + the `codemanifest.annotations` block with referencing lines
  (the `conventions` line: "Use `conventions` for test code: pytest configuration, logging, and Allure
  reporting.").
- `.goga/Dockerfile` — the mandatory Dockerfile: `FROM {dockerfile_base_image}` + `RUN goga install pybuggy -v
  1.0.x` (pybuggy installed via the goga-installer with the hardcoded version `1.0.x`; appended after goga
  generation), always created on goga-init.
- `.goga/usages/conventions.md` — the pybuggy test convention (the text of the installed package's asset).
- `.goga/usages/cooks/pybuggy/api.md`, `.goga/usages/cooks/pybuggy/asserts.md`.
- `<cwd>/conftest.py` — the consumer's root conftest: the fixed template `load_dotenv()` → `plugin.install()`
  (see "Generating <cwd>/conftest.py").

---

## Template: run in an already initialized goga project

When `.goga/config.yml` already exists, `run_init` asks via `click.confirm` (default `no`) whether to re-create
the goga project (overwriting `.goga/config.yml`; user codemanifest entries beyond pybuggy may be lost). On
refusal, the goga questionnaire **does not run**; the `conventions` slot is still brought to the package
version, `build.review_executor.skip: true` is added to the config (when missing), then the round-trip usages
registration runs. Likewise for `.goga/tools/pybuggy/config.yml`:

      # .goga/config.yml before the run (with user keys)
      codemanifest:
        usages:
          conventions: .goga/usages/conventions.md   # the key stays (skip-existing)
        annotations: |
          Use `conventions` for code writing rules and testing.   # legacy-goga line — will be replaced
      # pybuggy init → asks to re-create the goga/pybuggy configs; on refusal: .goga/usages/conventions.md
      # is overwritten with the package asset, build.review_executor.skip: true is added to the config (when missing),
      # the conventions key is skipped (already present), the legacy annotation line
      # is replaced with the pybuggy line ("Use `conventions` for test code: ..."), pybuggy-api/pybuggy-asserts
      # are added; the remaining annotation lines and comments stay in place

---

## Idempotency

A repeated `pybuggy init` in an already initialized project: `run_init` asks whether to re-create the goga
config, the pybuggy config, and whether to overwrite `conftest.py` (`click.confirm`, default `no`); when all
are refused, goga-init, the pybuggy config build, and the conftest write are skipped, the existing
`conftest.py` is not modified; the copied `.md` files (incl. `conventions.md`) are overwritten with the package
versions; `build.review_executor.skip: true` already set leaves the file unwritten (no-op); already registered
keys are skipped; annotation lines are replaced with identical ones (no-op) or appended. The flags
`--force`/`--dry-run` are not provided.

---

## Exit codes

- `0` — success (goga project ready/already ready + conventions slot + usages registered).
- A non-zero goga code (`1`) — goga initialization canceled/failed: in this case the `conventions` slot, the
  `build.review_executor` flag, and the usages are **not delivered/registered**, and `pybuggy init` exits with
  the goga code.
- Usages bootstrap errors (incl. convention delivery) and conftest write errors → `click.ClickException`
  (non-zero exit).

---

## Programmatic usage (tests/scripts)

`run_init()` uses cwd as the output root and **returns an exit code (int)**:

      import pytest
      from goga_tool_pybuggy.commands.init import run_init

      def test_init_in_fresh_project(tmp_path, monkeypatch):
          monkeypatch.chdir(tmp_path)
          # stub the interactive goga init so tests do not depend on a TTY:
          monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", lambda: 0)
          # stub the interactive building of .goga/tools/pybuggy/config.yml (run_init step #3):
          monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.build_pybuggy_config", lambda: 0)
          assert run_init() == 0
          assert (tmp_path / ".goga/usages/conventions.md").exists()    # the slot is occupied by the test convention
          assert (tmp_path / ".goga/usages/cooks/pybuggy/api.md").exists()
          assert (tmp_path / "conftest.py").exists()   # the final step — the fixed template

      def test_goga_cancel_aborts(tmp_path, monkeypatch):
          monkeypatch.chdir(tmp_path)
          monkeypatch.setattr("goga_tool_pybuggy.commands.init.init.run_goga_init", lambda: 1)  # canceled
          assert run_init() == 1
          assert not (tmp_path / ".goga/usages/conventions.md").exists()   # the slot is not delivered
          assert not (tmp_path / ".goga/usages/cooks/pybuggy/api.md").exists()
          assert not (tmp_path / "conftest.py").exists()

Test convention delivery is isolated in the pure `write_test_convention` (no TTY, no existence checks) — tested
directly:

      from goga_tool_pybuggy.commands.init import write_test_convention

      def test_convention_written(tmp_path):
          target = tmp_path / ".goga" / "usages" / "conventions.md"
          write_test_convention(target)                    # creates the file (and parent directories)
          assert target.read_text() == ASSET_TEXT          # the installed package's asset text
          target.write_text("locally modified")
          write_test_convention(target)                    # a repeated call — always an overwrite
          assert target.read_text() == ASSET_TEXT

For direct usages registration without discovery/copying — `register_usages`; for registering annotation lines
in `codemanifest.annotations` — `register_annotations` (round-trip, idempotent by backtick reference: a matched
line is replaced when the text differs, otherwise no-op; returns `changed_keys`); for enforcing
`build.review_executor.skip: true` on an arbitrary config — `ensure_review_executor_skip` (round-trip,
idempotent: returns `True` on change, `False` when the flag is already set, the file is not written). The
interactive building of `.goga/tools/pybuggy/config.yml` is isolated in `build_pybuggy_config`; test the pure
YAML emission directly via `write_pybuggy_config`; the pure conftest write — via `write_pybuggy_conftest`
(samples — in the sections above).

---

## Preconditions and side effects

- Requires the installed `goga` package (a pybuggy dependency) — for the in-process goga project
  initialization.
- Writes to `<cwd>/.goga/` (creates `.goga/usages/`, `.goga/usages/cooks/pybuggy/`, `.goga/config.yml`);
  writes `<cwd>/.goga/usages/conventions.md` — **always** overwritten with the package asset (package-owned).
- No network calls in init. Residual case: manually entering the name `conventions` in the goga questionnaire
  ("Add codemanifest usages?") triggers the goga download again (the file is then overwritten with the asset);
  filtering is deliberately not introduced.
- Writes `<cwd>/conftest.py` (the fixed template `load_dotenv()` → `plugin.install()`; when the file exists —
  only on `click.confirm` confirmation, refusal → skip with an INFO log). The presence of
  `goga_tool_pybuggy`/`python-dotenv` in the consumer's pytest environment is not checked — it surfaces at
  test run time.
- Appends the line `RUN goga install pybuggy -v 1.0.x` to the generated `.goga/Dockerfile` (the version is not
  resolved dynamically).
- Reads the usages and the convention asset from the **installed** `goga_tool_pybuggy` package
  (`importlib.resources`), not from cwd — works after `goga install pybuggy`, not only from a checkout.
- Discovery recurses over `.usages/*.md` under the `api` cell — future sub-cells plug in without touching the
  command; the convention asset is delivered separately (the `assets` package, not api).
- Copies only the `api` cell usages; internal development cells (`config`/`spec`/`output`/...) are not copied.
- goga-init runs when `.goga/config.yml` is missing (the "not initialized" heuristic) or on consent to
  re-creation (`click.confirm`, default `no`).
- Write targets — the goga-project config `.goga/config.yml` (the `build.review_executor`, `codemanifest.usages`,
  and `codemanifest.annotations` blocks), `.goga/usages/conventions.md`, `.goga/usages/cooks/pybuggy/*.md`,
  `.goga/tools/pybuggy/config.yml`, and the root `<cwd>/conftest.py`.
