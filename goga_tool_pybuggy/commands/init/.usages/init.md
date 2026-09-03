# goga_tool_pybuggy.commands.init — goga project initialization (bare, template, upgrade) and bootstrap of the consumer's pybuggy environment

## Domain

The `pybuggy init` command **initializes the goga project** and **bootstraps the pybuggy test environment** in the
directory where it is invoked. It operates in three modes selected by the CLI arguments:

- **bare** (`pybuggy init`) — interactive onboarding of a fresh or existing project;
- **template** (`pybuggy init <tpl> [--ref <git-ref>]`) — scaffold a copier-compatible template project first, then
  run the onboarding with silent-skip gates;
- **upgrade** (`pybuggy init --upgrade [--ref <git-ref>]`) — migrate a previously scaffolded project to a newer
  template version; no onboarding.

The audience is the integrator wiring pybuggy into their project (`goga install pybuggy`), and the consumer's goga agent.

## CLI surface

- `pybuggy init` — bare onboarding.
- `pybuggy init <tpl>` — template onboarding. `<tpl>` is a local path or a git URL of a copier-compatible template
  project, optionally carrying a `#ref` fragment (`https://host/repo.git#v2`).
- `--ref <git-ref>` — overrides the template ref: beats the URL fragment in template mode; sets the migration target
  in upgrade mode.
- `--upgrade` — template migration only (the template source is read from `.goga/scaffold.yml`).

Flag rules (mirroring `goga init`): `<tpl>` and `--upgrade` are mutually exclusive; `--ref` requires `<tpl>` or
`--upgrade`. Violations print an error message and exit with code 1.

The command stays interactive: the goga questionnaire (bare/template onboarding without an existing `.goga/config.yml`)
and the copier TUI (template questions) require a TTY.

## Template mode

Scaffolding runs first (`goga.scaffold` engine, copier underneath): the template is rendered into the current working
directory; only `project_name` is injected programmatically — the remaining template questions are asked
interactively. A failed scaffold stops the command with the engine's exit code — no onboarding side effects are
applied.

After a successful scaffold the onboarding pipeline runs with **silent-skip gates**: a file that already exists
(`.goga/config.yml`, `.goga/tools/pybuggy/config.yml`, `conftest.py`, the conventions slot, the copied usages) is left
untouched with an INFO log and no interactive confirmation; a missing file is created through the normal flow —
including the interactive goga questionnaire when the template brought no `.goga/config.yml`.

Idempotent augmentations of existing files always run — they are additive and are the only way pybuggy integrates
itself into an arbitrary template:

- `build.review_executor.skip: true` in `.goga/config.yml` (round-trip, comments preserved);
- the `RUN goga install pybuggy -v 1.0.x` line in `.goga/Dockerfile` (a natural no-op when the Dockerfile is absent);
- the pybuggy usage keys and annotation lines registered in `.goga/config.yml`.

## Upgrade mode

Only the template migration runs (copier run_update via the `.goga/scaffold.yml` state file); no onboarding prompts
appear, nothing else is written. The state file is persisted by the template itself (the answers-file entry) — a
template without one leaves `--upgrade` unusable: the engine reports the missing state file with a non-zero exit.
Engine preconditions (a clean git repository, a git-trackable template, a non-decreasing version) surface as non-zero
exits; the command propagates them without wrapping.

## The conventions slot — skip-if-exists

The file `.goga/usages/conventions.md` is created from the package asset **only when absent** — in every mode. An
existing file (brought by a template or created/modified by any earlier run) is left untouched with an INFO log. The
registration of the `conventions` usage key and the annotation line is idempotent and always runs.

## Bare mode

- The goga project initializes in-process via the `goga` package (the language is fixed to `python`; the Dockerfile is
  mandatory: `FROM {base}` + the appended `RUN goga install pybuggy -v 1.0.x` line; no base-convention download —
  initialization is offline). When `.goga/config.yml` already exists, re-creation is offered via a confirmation
  (default `no`); declining skips the questionnaire.
- The tool config `.goga/tools/pybuggy/config.yml` is built interactively when absent; a rebuild of an existing file
  is offered via a confirmation (default `no`). The prompted keys: base_url (required, a Jinja2 template), the
  optional scalars (timeout, retries, assert_timeout, assert_delay, assert_field_class, assert_response_class), and
  at least one spec (name, type swagger|openapi, location, optional git block). headers/loader are written as
  commented examples, not prompted.
- The consumer usages of the `api` cell (`api.md`, `asserts.md`, and any future sub-cell usages) are copied to
  `.goga/usages/cooks/pybuggy/` and registered in `.goga/config.yml` (keys `pybuggy-api`, `pybuggy-asserts`, ...);
  annotation lines are registered by backtick reference. Idempotent: existing keys are skipped, a matched annotation
  line is replaced, an unmatched one is appended, foreign lines are preserved.
- The root `conftest.py` is created from a fixed template (`load_dotenv()` then `plugin.install()`); an existing file
  is overwritten only on confirmation (default `no`).

## Entry point

- Console command (top-level, not under `endpoint`): `pybuggy init [<tpl>] [--ref <git-ref>] [--upgrade]`
- Module run: `python -m goga_tool_pybuggy init [<tpl>] [--ref <git-ref>] [--upgrade]`
- Programmatic facade import:
      from goga_tool_pybuggy.commands.init import run_init, run_onboarding, resolve_init_mode, run_goga_init, init_cmd, register_usages, register_annotations, ensure_review_executor_skip, write_test_convention

## Exit codes

- `0` — success.
- `1` — invalid flag combination (`<tpl>` with `--upgrade`; `--ref` without `<tpl>`/`--upgrade`); goga-init canceled/failed.
- The scaffold engine's non-zero code — propagated unchanged (a failed scaffold or migration); a failed scaffold
  leaves no onboarding side effects.
- Usages bootstrap errors (incl. convention delivery) and conftest write errors → `click.ClickException`
  (non-zero exit).

## Programmatic usage (tests/scripts)

`run_init(tpl, ref, upgrade)` uses cwd as the output root and **returns an exit code (int)**; the flags mirror the CLI:

      import pytest
      from goga_tool_pybuggy.commands.init import run_init

      def test_bare_onboarding(tmp_path, monkeypatch):
          monkeypatch.chdir(tmp_path)
          monkeypatch.setattr('goga_tool_pybuggy.commands.init.init.run_goga_init', lambda: 0)
          monkeypatch.setattr('goga_tool_pybuggy.commands.init.init.build_pybuggy_config', lambda: 0)
          assert run_init(tpl=None, ref=None, upgrade=False) == 0    # bare mode — no flags
          assert (tmp_path / '.goga/usages/conventions.md').exists()
          assert (tmp_path / 'conftest.py').exists()

      def test_failed_scaffold_stops_onboarding(tmp_path, monkeypatch):
          monkeypatch.chdir(tmp_path)
          monkeypatch.setattr('goga_tool_pybuggy.commands.init.init.Scaffold', StubScaffold)  # generate -> 1
          assert run_init(tpl='https://host/repo.git', ref=None, upgrade=False) == 1
          assert not (tmp_path / '.goga/usages/conventions.md').exists()      # no onboarding side effects

The mode resolution is pure and directly testable via `resolve_init_mode` (returns `bare` / `template` / `upgrade`;
raises `click.ClickException` on an invalid combination). The onboarding pipeline is isolated in
`run_onboarding(template_mode)` — the gate semantics (silent skip vs confirmation) are testable without stubbing the
scaffold engine:

      def test_conventions_skip_if_exists(tmp_path, monkeypatch):
          monkeypatch.chdir(tmp_path)
          (tmp_path / '.goga/usages/conventions.md').write_text('template convention')
          monkeypatch.setattr('goga_tool_pybuggy.commands.init.init.run_goga_init', lambda: 0)
          monkeypatch.setattr('goga_tool_pybuggy.commands.init.init.build_pybuggy_config', lambda: 0)
          assert run_onboarding(template_mode=True) == 0
          assert (tmp_path / '.goga/usages/conventions.md').read_text() == 'template convention'  # untouched

The scaffold engine is stubbed with `monkeypatch` at the import point (`Scaffold`) — tests never invoke real copier,
the network, or a TTY. For direct usages registration without discovery/copying — `register_usages`; for annotation
lines — `register_annotations` (round-trip, idempotent by backtick reference, returns `changed_keys`); for enforcing
`build.review_executor.skip: true` on an arbitrary config — `ensure_review_executor_skip`; the convention write — the
pure `write_test_convention` (always overwrites the given path; whether it runs is the orchestrator's decision).

## Preconditions and side effects

- Requires the installed `goga` package (a pybuggy dependency) — onboarding and the scaffold engine.
- Writes to `<cwd>/.goga/` (config, the Dockerfile install line, usages, the tool config) and `<cwd>/conftest.py`; the
  scaffold engine renders template files into `<cwd>` and may persist `.goga/scaffold.yml` (template-owned; must not
  be git-ignored in a scaffolded project).
- The `conventions` slot is created only when absent, in every mode.
- Reads usages and the convention asset from the **installed** `goga_tool_pybuggy` package (`importlib.resources`),
  not from cwd.
- No network calls in bare onboarding; template/upgrade modes reach the template source (a git URL) through the
  engine.
- Copies only the `api` cell usages; internal development cells (`config`/`spec`/`output`/...) are not copied.
