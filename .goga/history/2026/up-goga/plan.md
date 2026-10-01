# Plan: `up-goga` — pybuggy onboarding migration to goga 2.0 (session-participation model)

## Purpose

Migrate `goga_tool_pybuggy` from the dead 1.x onboarding flow to the goga 2.0 canonical
session-participation model. After implementation:

- `pybuggy init` drives the engine-owned onboarding session (`goga.onboarding.InitLogic`) with pybuggy
  invited, then runs a pybuggy-owned bootstrap that delivers the files the session does not carry;
- pybuggy participates in native `goga init -t pybuggy` sessions through two onboarding hooks
  (`declare_session` / `amend_config`) subscribed by the root facade callback;
- the init cell implements its rewritten contract: 17 routines across `init.py`, `session.py`,
  `bootstrap.py`, all importable from the cell facade;
- the tool config payload is plain serializable data (the engine serializes verbatim), the consumer
  config gains `build.review.skip: true` via the bootstrap, and the Dockerfile install line is derived
  from the installed package version;
- tests, `pyproject.toml` (test extra → `goga>=2.0.1,<2.1`), MIGRATION.md, and the public docs are
  rewritten off the 1.x model.

The most important gaps: the current `init.py` is dead code against goga 2.0.1 (imports the removed
`GogaConfigAnswers`/`InitAnswers`), so the whole package — and the entire test suite — fails at import;
the two 1.x-era init test files assert the deleted API. Strategy: toolchain baseline first, then cell
skeleton (restores importability), then TDD per module group in dependency order
(`bootstrap.py` → `session.py` → `init.py` → root `statuses.py`), integration tests last.

## Context

### Contract Surface

Cell `goga_tool_pybuggy/commands/init` — 17 routines (CODEMANIFEST rewritten; read-only). Facade
obligation for every routine: importable from `goga_tool_pybuggy.commands.init`. Python mapping:
snake_case functions, mandatory type hints, `__all__` on `commands/init/__init__.py` (alphabetical).

**Entity: `init_cmd(ctx: click.Context, tpl: str | None, ref: str | None, upgrade: bool)`**
- Type: function (Click wrapper). Declared `location`: `init.py`. Behavior unchanged from current code.
- Facade obligation: importable from `goga_tool_pybuggy.commands.init`; registered on the root group by `cli.py`.
- Semantic requirements: binds the optional positional `<tpl>`, the option `--ref`, the flag `--upgrade`;
  delegates to `run_init`; propagates the returned exit code via `ctx.exit`.
- Imported dependencies: `click` (usage). Annotation cascade: global annotations + entity annotation.

**Entity: `run_init(tpl: str | None, ref: str | None, upgrade: bool) -> exit_code:int`**
- Type: function. `location`: `init.py`. Changed: rewired from `run_onboarding` to `run_session` + `run_bootstrap`.
- Semantic requirements: resolve mode (`resolve_init_mode`); bare guard — `.goga` **directory** existence
  only, refusal echoes `Project already initialized` to stderr and returns 1 with zero prompts/writes;
  upgrade → `Scaffold().upgrade(ref)` code propagated as-is (no session, no bootstrap); template →
  `Scaffold().generate(tpl, ref)`, non-zero stops the command with no onboarding side effect; then
  `run_session()` (non-zero propagated unchanged, bootstrap skipped), then
  `return run_bootstrap(template_mode=(mode == "template"))`. Exit code: 0 success; 1 invalid flags /
  already-initialized / failed bootstrap step; engine or session codes propagated as-is.
- Constraints: never wrap engine exceptions or diagnostics; do not guard template/upgrade modes.

**Entity: `resolve_init_mode(tpl: str | None, ref: str | None, upgrade: bool) -> mode:str`**
- Type: function. `location`: `init.py`. Contract text unchanged; implementation carried over verbatim.
- Semantic requirements: reject `tpl and upgrade` and `ref without tpl and without upgrade` via
  `click.ClickException`; return `upgrade` / `template` / `bare`. Pure — no TTY, no I/O.

**Entity: `run_bootstrap(template_mode: bool) -> exit_code:int`**
- Type: function. `location`: `init.py`. New.
- Semantic requirements: 9-step post-session bootstrap with mode-dependent gates (template: skip-with-INFO;
  bare: `click.confirm(default=False)`); steps 2–7 wrapped in `except (OSError, YAMLError, ValueError)` →
  ERROR log + return 1 (no `click.ClickException` — tier changed from the old code); step 8 missing
  Dockerfile → ERROR + 1. Full algorithm in Task 7.
- Constraints: never copy usages of internal development cells; never merge into an existing conftest;
  never prompt in template mode; never create the Dockerfile.

**Entity: `run_session() -> exit_code:int`**
- Type: function. `location`: `session.py`. New — the contract test seam.
- Semantic requirements: build
  `InitLogic(questionnaire=Questionnaire(), generator=FileGenerator(), participation=ToolParticipation(invited=["pybuggy"]))`
  and return `logic.run()` unchanged. Engine-owned: existing `.goga/config.yml` ends the session (0, no side
  effects); tool contribution failures are soft (warning + drop, session 0); user abort → quiet 1.
- Constraints: no engine internals, no caught/wrapped engine errors.

**Entity: `declare_pybuggy_session(context: object)`**
- Type: function. `location`: `session.py`. New — participation moment one.
- Semantic requirements: `if not context.invited: return`; else
  `for item in pybuggy_questions(): context.declare(item)`. The no-invitation branch calls nothing.
- Constraints: never survey, prompt, or read answers.

**Entity: `amend_pybuggy_config(context: object)`**
- Type: function. `location`: `session.py`. New — participation moment two.
- Semantic requirements: `if not context.invited: return`; read `answers = context.answers`;
  `for id, value in build_config_amendments().items(): context.answer(id, value)`;
  `context.write_config("config.yml", build_config_data(answers))`. Exceptions propagate (the mediator
  drops the whole contribution with a warning naming pybuggy — soft).
- Constraints: never write files directly; never read another tool's answers.

**Entity: `pybuggy_questions() -> items:list[Question]`**
- Type: function. `location`: `session.py`. New — pure builder of the declarative question block.
- Semantic requirements (exact ids and order — they are the answer keys downstream):
  `base_url` (input, **no default** → engine re-asks until non-empty — required); then one input per
  `PluginConfigKeys` member except `BASE_URL`, `HEADERS`, `LOADER` (`default=""` → Enter yields `""` —
  optional; prompt texts from `_SCALAR_PROMPTS`); then `QuestionGroup(id="first_spec", prompt="The first
  spec", children=[name(input, no default), type(choice ["swagger","openapi"]), location(input, no default),
  git_url(input, default=""), git_location(input, default=""), git_ref(input, default="")])` — exactly one
  nesting level, simple children only; then `extra_specs` (input, `default=""`, compact form
  `name|type|location|git_url|git_location|git_ref`). Survey order = declaration order. Fresh records per call.
- Constraints: never survey `HEADERS`/`LOADER`; never duplicate plugin key names — iterate `PluginConfigKeys`.

**Entity: `build_config_data(answers: dict[str, object]) -> data:dict[str, object]`**
- Type: function. `location`: `session.py`. New — pure.
- Semantic requirements: `specs = parse_specs(answers.get("first_spec") or {}, answers.get("extra_specs") or None)`;
  scalar walk in `PluginConfigKeys` declaration order skipping `HEADERS`/`LOADER`, dropping `None`/`""` answers,
  coercing numeric members (`timeout`→float, `retries`→int, `assert_timeout`→int, `assert_delay`→float via
  `_NUMERIC_MEMBERS`); `data["specs"] = {name: entry.model_dump(exclude_none=True)}`. Payload is **plain
  serializable data** — never pydantic objects (the engine `yaml.dump`s buffered data verbatim and silently
  drops unserializable files). Key order: plugin key order with `specs` last. A non-numeric numeric answer
  raises `ValueError` (soft-drop upstream).
- Imported dependencies: `SpecEntry`/`GitEntry` (Types from `...config`), `PluginConfigKeys` (from `...plugin`),
  `configuration` (imported usage — schema compatibility).

**Entity: `build_config_amendments() -> amendments:dict[str, object]`**
- Type: function. `location`: `session.py`. New — pure (review decision q2/A).
- Semantic requirements: returns exactly `{"build.review.skip": True}` — the single declared-intent amendment,
  unconditional, no parameters. The engine config mapper drops it (`_build_config_document` emits only
  `agent`/`env` for the build block); consumer-visible enforcement is the bootstrap's `ensure_review_skip`.

**Entity: `parse_specs(spec_answers: dict[str, object], extra_specs: str | None) -> specs:dict[str, SpecEntry]`**
- Type: function. `location`: `session.py`. New — pure, lenient.
- Semantic requirements: first spec strict — non-empty `name`, `type` ∈ {`swagger`, `openapi`}, non-empty
  `location`, else `ValueError`; `GitEntry(url, location, ref)` attached only when `git_url` **and**
  `git_location` are both non-empty (`ref = git_ref or None`); extras lenient — each non-empty line split on
  `|`, malformed (`len(parts) < 3`, empty first/third part, invalid type) → WARNING + skip; duplicate name →
  keep the first + WARNING; the mapping always holds at least the first spec.
- Imported dependencies: `SpecEntry`, `GitEntry`.

**Entity: `write_test_convention(path: Path)`**
- Type: function. `location`: `bootstrap.py`. Relocated from `init.py`; contract text tightened (pure writer).
- Semantic requirements: read the packaged asset
  `importlib.resources.files("goga_tool_pybuggy") / "assets" / "conventions.md"` (never the cwd checkout, never
  the network); `mkdir(parents=True, exist_ok=True)`; `write_text` — always overwrites, no TTY, no existence check.

**Entity: `ensure_review_skip(config_path: Path) -> changed:bool`**
- Type: function. `location`: `bootstrap.py`. Renamed from `ensure_review_executor_skip`; key path
  `build.review_executor.skip` → `build.review.skip`; behavior otherwise identical.
- Semantic requirements: ruamel round-trip (`preserve_quotes=True`); load existing config or start an empty
  `CommentedMap`; navigate/create `build` → `review` (each level `_ensure_map`; a non-mapping level raises
  `ValueError` — never overwrites user data); `skip is True` → return `False` without writing; else set
  `skip = True`, dump, INFO, return `True`. Comments/order/quotes preserved; idempotent (no write when
  already true); siblings (e.g. `build.task_executor`) untouched.

**Entity: `install_pybuggy(dockerfile_path: Path) -> line:str | None`**
- Type: function. `location`: `bootstrap.py`. Changed: install line becomes dynamic.
- Semantic requirements: absent file → return `None` (never creates the file);
  `version = importlib.metadata.version("goga-tool-pybuggy")`; `minor = ".".join(version.split(".")[:2])`;
  `line = f"RUN goga install pybuggy -v {minor}.x"` (dev/pre tails like `1.1.1.dev4+gabc` still yield `1.1.x`);
  line already present → `None`; else ensure trailing newline, append, write, INFO, return the line. Only the
  install line is appended; idempotent. `PackageNotFoundError` is NOT in the bootstrap catch tuple — it
  propagates uncaught (unreachable in practice; review q4/A).

**Entity: `register_usages(config_path: Path, usage_keys: dict[str, str]) -> added_keys:list[str]`**
- Type: function. `location`: `bootstrap.py`. Relocated; return label typed; behavior unchanged.
- Semantic requirements: round-trip under `codemanifest.usages`; skip present keys, insert missing, record
  `added_keys`; create a minimal file when none exists; existing keys never overwritten; comments, key order,
  and quotes preserved.

**Entity: `register_annotations(config_path: Path, annotation_lines: dict[str, str]) -> changed_keys:list[str]`**
- Type: function. `location`: `bootstrap.py`. Relocated; return label typed; behavior unchanged.
- Semantic requirements: round-trip under `codemanifest.annotations` (literal block scalar); per (key, line):
  locate the first text line carrying the backtick reference — not found → append; identical → skip;
  differing → replace; foreign lines preserved; write back as `LiteralScalarString`. Idempotent by reference.

**Entity: `write_pybuggy_conftest(path: Path)`**
- Type: function. `location`: `bootstrap.py`. Relocated; contract text tightened (pure writer).
- Semantic requirements: fixed `_CONFTEST_TEMPLATE`
  (`from dotenv import load_dotenv\n\nload_dotenv()\n\nfrom goga_tool_pybuggy import plugin\n\nplugin.install()\n`)
  → `mkdir` parent → `write_text`, always overwrites; deterministic; no TTY, no existence check.

**Entity: `register_hooks(hooks: object)`** (root cell `goga_tool_pybuggy`, `location: statuses.py`)
- Type: function. Changed: two onboarding subscriptions added next to the two statuses subscriptions.
- Facade obligation: exposed on the ROOT facade via `__all__` (the platform imports it from the package root).
- Semantic requirements: exactly four subscriptions, in order:
  `("statuses", "register_statuses", "automate", register_automate_statuses)`,
  `("statuses", "register_statuses", "fix", register_fix_statuses)`,
  `("onboarding", "declare_session", "declare", declare_pybuggy_session)`,
  `("onboarding", "amend_config", "amend", amend_pybuggy_config)`;
  the onboarding handlers are imported at module top via
  `from .commands.init import amend_pybuggy_config, declare_pybuggy_session`; the platform delivers hook
  arguments **by name** (`context`). The handlers are NOT re-exported on the package facade.
- Constraints: nothing beyond the four subscriptions; statuses tables untouched.

Deleted entities (must not survive the rewrite): `run_onboarding`, `run_goga_init`, `build_pybuggy_config`,
`write_pybuggy_config`, `ensure_review_executor_skip`, and the private helpers `_gate_existing`,
`_write_root_conftest`, `_git_entry_to_map`, `_HEADERS_BLOCK`, `_LOADER_BLOCK`, `_COMPLEX_MEMBERS`,
`_GIT_CHILD_INDENT`, `_INSTALL_LINE` (hardcoded), `_ask_scalar_values`, `_ask_spec`, `_DOCKERFILE_PATH`;
`_SCALAR_PROMPTS`/`_NUMERIC_MEMBERS` move to `session.py`.

### Re-exports

- Cell facade `goga_tool_pybuggy/commands/init/__init__.py` — must expose **all 17 routines** through
  `__all__` (alphabetical). Source: the cell's own routines.
- Root facade `goga_tool_pybuggy/__init__.py` — unchanged by this plan (`register_hooks` already exported;
  the two onboarding handlers deliberately not on the facade — reachable only through the subscriptions).
- Root `->install: {}` embedding (plugin cell) — untouched by this plan.

### Usages Context

Init cell (header `Usages`; every entry is referenced by at least one task below):

- `conventions` — `.goga/usages/conventions.md`. Python writing rules: relative imports, pydantic `kw_only`,
  logging standard, Google docstrings, code formatting, test structure/naming/mocking rules, validation
  commands. Mandatory for ALL tasks; extracted into the plan-level **Mandatory Rules** section.
- `click` — `.goga/usages/cooks/click.md`. Command wrapper, flag validation, confirm gates,
  `ClickException` mapping. Tasks 6, 7 (and the bare conftest gate of `run_bootstrap`).
- `ruamel-yaml` — `.goga/usages/cooks/ruamel-yaml.md`. Round-trip YAML (comments, quotes, key order),
  from-scratch `CommentedMap`, literal block scalars. Tasks 3, 7. Narrowed to round-trip edits of the
  consumer `.goga/config.yml` — the commented-record emission practice is retired with `write_pybuggy_config`.
- `goga-scaffold` — `.goga/usages/cooks/goga/scaffold/scaffold-usage.md`. `Scaffold().generate(tpl, ref)` /
  `Scaffold().upgrade(ref)` exit-code contract. Task 6.
- `goga-onboarding` — `.goga/usages/cooks/goga/onboarding/onboarding-usage.md`. `InitLogic(questionnaire,
  generator, participation)` facade, session flow and behavior guarantees. Tasks 5, 9.
- `goga-onboarding-hooks` — `.goga/usages/cooks/goga/onboarding/registering-hooks.md`. The two onboarding
  actions, subscribe addresses, hook signature rules (context/self by name), moment member contracts,
  failure behavior. Tasks 5, 8, 9.
- `goga-onboarding-questions` — `.goga/usages/cooks/goga/onboarding/questions/question-records.md`.
  `Question`/`QuestionGroup` record kinds and fields, one-level nesting rule, answer addressing. Task 4.
- `goga-onboarding-generator` — `.goga/usages/cooks/goga/onboarding/generator/artifact-generation.md`.
  Artifact order, verbatim tool-config serialization into `.goga/tools/<tool>/<file>`, created-file report.
  Tasks 4, 5, 9.

Root cell (relevant entries): `goga-hooks` (facade callback + failure behavior), `goga-statuses` (statuses
registration surface — **file currently missing on disk, pre-existing accepted residue**), `goga-onboarding-hooks`
(see above). Task 8. The remaining root usages (`click`, `python-dotenv`, `conventions`) belong to entities
out of this plan's scope (`conventions` applies via the Mandatory Rules).

### Imported Usages

- `configuration` from cell `goga_tool_pybuggy/config` —
  source `goga_tool_pybuggy/config/.usages/configuration.md`. Schema compatibility of the tool-config payload
  (`specs` mapping with required entry fields; scalar plugin keys ignored on loading; default location
  `.goga/tools/pybuggy/config.yml`). Also grounds the typed entries `SpecEntry(type, location, git)` /
  `GitEntry(url, location, ref)` imported as `Types` from the same cell. Task 4.
- `init`, `config-build` from cell `goga_tool_pybuggy/commands/init` (imported by the root cell) — consumer
  documentation of the rewritten command; already current (see Local Usages); no task obligations.

### Local Usages

None planned. Per the design's `.usages/` Update section: the changed domains (init modes / config
contribution / facade assembly) are each already covered by an existing file — supplement-in-place was
applied during the design and design-review stages:

- `goga_tool_pybuggy/commands/init/.usages/init.md` — current (three modes, session semantics, bootstrap
  table with the Dockerfile-resolution row, decline-branch paragraph, delivery-list correction).
- `goga_tool_pybuggy/commands/init/.usages/config-build.md` — current (single `build.review.skip`
  declared-intent amendment, enforced by the bootstrap; native-session gap noted).
- `goga_tool_pybuggy/.usages/assembly.md` — current (four-hook subscription table, three-mode init entry).

Implementation tasks verify behavior **against** these files; they do not edit them.

### External Dependencies

- `goga>=2.0.1,<2.1` — engine: `goga.onboarding` (`InitLogic`, `Questionnaire`, `FileGenerator`,
  `ToolParticipation`, `Question`, `QuestionGroup`, `SessionAnswers`), `goga.scaffold.Scaffold`, hooks platform.
- `click>=8.0` (CLI), `ruamel.yaml>=0.18` (round-trip), `pydantic>=2.0` (via config cell models),
  `pyyaml>=6.0` (`yaml.safe_load` in Dockerfile resolution).
- stdlib: `importlib.metadata` (package version), `importlib.resources` (asset/usage discovery), `logging`.
- Test extra: `pytest>=8.0`, `pytest-cov>=5.0`, `ruff>=0.15.0`, `jinja2>=3.1`.
- Distribution `goga-tool-pybuggy`, version setuptools-scm derived (`pyproject.toml`, `dynamic = ["version"]`).

## Facts

Environment facts verified during design tracing (goga 2.0.1 host, `/opt/goga`) — transferred verbatim:

- `goga.onboarding` exposes `InitLogic`, `Questionnaire`, `FileGenerator`, `ToolParticipation`, `Question`,
  `QuestionGroup`, `SessionAnswers`; the 1.x entities (`GogaConfigAnswers`, `InitAnswers`) are gone — the
  current `init.py` is dead code against 2.0.1 and fails at import.
- Engine ask semantics (`Questionnaire.ask_question`): kind `input` with `default=None` → required
  (re-asked until non-empty); `default=""` → Enter yields `""` (skippable); kind `choice` →
  `click.prompt(type=click.Choice(choices))`, always answered, default ignored; kind `confirm` → bool;
  kind `pairs` → mapping.
- Declaration surface (`ToolDeclaration`): `.invited: bool`, `.declare(item)` accepting `Question` or a
  one-level `QuestionGroup` (nested groups rejected with a warning), `.skip(path)`.
- Contribution surface (`ToolContribution`): `.invited: bool`, `.answers: dict` (core sections + own block
  under local names), `.answer(id, value)` with `value: str | bool | dict` at a dot-path, `.write_config(file, data)`.
- `SessionAnswers.amend(id, value)` merges mappings recursively / replaces scalars at a dot-path;
  `view_for(tool)` returns core + own local names; the answer space is nested mappings (no dotted keys stored).
- The generator writes buffered tool configs **verbatim** via `yaml.dump(data)` (`_write_tool_configs`) — a
  payload containing pydantic objects raises `RepresenterError` and the file is silently dropped with a
  warning. `build_config_data` must therefore emit plain mappings.
- `_build_config_document` maps only known core fields: the `build` block carries only `agent`/`env` (a
  `build.review.skip` amendment never reaches the generated config — the bootstrap's `ensure_review_skip` is
  the enforcement point), and the config `dockerfile` field is emitted from `docker_image.dockerfile` +
  `docker_image.base_image`. The generator likewise writes the Dockerfile only when BOTH answers exist
  (`generate`: `if dockerfile is not None and base_image is not None`), and the core confirm
  "Create Dockerfile?" defaults to **No** (`_survey_docker_image`) — a user declining it leaves no Dockerfile,
  no config `dockerfile` field, and neither docker_image answer recorded (the decline branch; see the
  `run_bootstrap` edge cases and the declined-Dockerfile test variant).
- The hooks platform delivers hook arguments **by name** (`context`, optional `self`); subscribe signature
  `hooks.subscribe(domain, action, name, hook)`.
- `goga install` version grammar: minor x-range `N.M.x` → pip `~=N.M.0`; the package version is
  setuptools-scm derived (`pyproject.toml`, `dynamic = ["version"]`, distribution `goga-tool-pybuggy`).

Workspace facts (verified for this plan):

- goga 2.0.1 is installed at `/opt/goga` (`goga --version` → 2.0.1); its python has `goga.onboarding`
  importable but **no pytest/ruff and no pybuggy dependencies** (`swax` et al. missing) — the workspace has
  **no virtualenv**; one must be created and `pip install -e .[test]` run (conventions mandate a virtualenv).
- `pyproject.toml` test extra pins `goga>=1.3.0,<1.4.0` (stale); `ruff` configured as linter AND formatter
  (`[tool.ruff]` target py310 / line-length 120 / full rule selection; `[tool.ruff.format]` double quotes, LF).
- `goga lint` baseline: 17 cells, **1 error** — pre-existing `goga-statuses` missing-file residue
  (`.goga/usages/cooks/goga/history/registering-statuses.md`, renamed by a `goga sync` commit; refresh
  belongs to a `goga usages sync` run outside this plan). Accepted; no new findings allowed.
- `MIGRATION.md` does not exist; `docs/getting-started.md`, `docs/cli/init.md`, `README.md`,
  `docs/plugin/index.md`, `docs/pipelines/*.md` still describe the 1.x model.
- `tests/commands/init/test_init.py` (2718 lines) and `test_init_integration.py` (301 lines) import the
  deleted 1.x API; `tests/test_statuses.py` does not exist yet. A stale untracked
  `tests/__pycache__/test_statuses*.pyc` is a residue of a deleted local file — ignored.
- Because the root facade transitively imports the init cell (`cli.py` → `commands.init`), the **entire**
  test suite is red at baseline under goga≥2.0.1 — restored by Task 2 (skeleton).
- `tests/test_cli.py` asserts only that `init` is registered top-level (no handler invocation) — safe with
  skeleton stubs.
- Cell usage files (init.md, config-build.md, assembly.md) are current — see Local Usages.

## Gap Analysis

- **Missing contract entities**: `run_bootstrap` (init.py); `run_session`, `declare_pybuggy_session`,
  `amend_pybuggy_config`, `pybuggy_questions`, `build_config_data`, `build_config_amendments`, `parse_specs`
  (session.py — file does not exist); `bootstrap.py` does not exist (its six routines live in init.py today).
- **Missing facade exposure**: the cell facade still exports the old 13-name `__all__`; must become the 17
  new names; `statuses.py` lacks the `from .commands.init import ...` import and the two onboarding
  subscriptions.
- **Incorrect `location` placement**: `write_test_convention`, `ensure_review_skip`, `install_pybuggy`,
  `register_usages`, `register_annotations`, `write_pybuggy_conftest` currently in `init.py` → must move to
  `bootstrap.py`; `_SCALAR_PROMPTS`/`_NUMERIC_MEMBERS` → `session.py`.
- **API mismatches**: `ensure_review_executor_skip` → `ensure_review_skip` with key path
  `build.review_executor.skip` → `build.review.skip`; `install_pybuggy` hardcoded `1.0.x` line → dynamic
  minor x-range; `run_init` wired to `run_onboarding` → `run_session` + `run_bootstrap`;
  `register_usages`/`register_annotations` return labels typed (`added_keys`, `changed_keys`).
- **Behavioral mismatches**: bootstrap step failures must return 1 (ERROR-logged) instead of raising
  `click.ClickException`; Dockerfile resolved from the consumer config `dockerfile` field with the
  `.goga/Dockerfile` fallback (user-confirmed q1/A); the declined-Dockerfile session fails at bootstrap
  step 8 (ERROR + 1) with steps 2–7 applied; the tool config is written by the engine from a plain payload,
  not by the cell.
- **Existing code that can be reused** (carried over): `_walk`/`_discover_usages`, `PYBUGGY_ANNOTATIONS`,
  `_annotation_for`, `_CONVENTION_LINE`, `_log_registration`, `_ensure_map`, `_CONFTEST_TEMPLATE`,
  `_SCALAR_PROMPTS`, `_NUMERIC_MEMBERS`, `resolve_init_mode`, the `init_cmd` decorator set, the
  `_BARE`/`_TEMPLATE`/`_UPGRADE` constants, the `run_init` guard/scaffold skeleton.
- **Test coverage gaps**: everything per the Source File Registry — `tests/commands/init/test_session.py`
  (new), `tests/commands/init/test_bootstrap.py` (new), `tests/commands/init/test_init.py` (rewrite),
  `tests/commands/init/test_init_integration.py` (rewrite), `tests/test_statuses.py` (new).
- **Missing visibility in workspace or git**: no virtualenv; package not installed anywhere; the whole
  suite fails at import under goga≥2.0.1.

---

## Mandatory Rules

Extracted from the project convention (`.goga/usages/conventions.md`, usage key `conventions` — connected in
both changed CODEMANIFESTs) and **binding for every task in this plan**; where a rule comes from the
contract's Python language rules instead (M-R1.8 signature grammar), it is marked as such. The convention's
precedence applies: contract first, package boundary/facade second, these project conventions next,
language idioms last.

### R1. Coding Style (strictly from the project convention)

- **M-R1.1** Python 3.10+ only; `pyproject.toml` is the single configuration source.
- **M-R1.2** All execution happens inside a virtualenv — create it if missing (Task 1 owns creation; every
  later command runs through it).
- **M-R1.3** Imports: **relative** for all intra-package references; **absolute** only for stdlib and
  third-party. (`from ...config import SpecEntry`, `from ..plugin import PluginConfigKeys` — never
  `from goga_tool_pybuggy.config import ...` inside the package.)
- **M-R1.4** Data models: pydantic with `kw_only=True`; empty defaults for fields; `None` only for the
  explicit absence of a value. (This plan consumes existing models — no new models are planned.)
- **M-R1.5** Logging: stdlib `logging` with module loggers (`logger = logging.getLogger(__name__)`);
  every operational log carries contextual metadata via `extra={...}`; messages lowercase, concise, with
  **stable log event names**; no secrets/credentials/tokens/personal data in logs. Levels: INFO — lifecycle,
  state transitions, externally observable operations (files copied/skipped, slot delivery, review-skip
  enforcement, install line added, registration results); WARNING — abnormal but recoverable (malformed
  extra spec lines, duplicate spec names, skipped registration keys); ERROR — the operation cannot complete
  (bootstrap step failure, missing Dockerfile after the session).
- **M-R1.6** Function/method bodies: logical blocks separated by **one blank line** (initialization vs
  conditionals/loops; data preparation vs processing vs return).
- **M-R1.7** Docstrings: **mandatory** for all public functions/methods/classes, **Google style** — first
  line capitalized and ending with a period; `Args` when parameters exist; `Returns` when a value returns;
  `Raises` for exceptions beyond built-in behavior.
- **M-R1.8** Type hints mandatory; signature grammar per the Python language rules (`str`, `int`, `bool`,
  `list[T]`, `dict[str, T]`, `T | None`; no `*args`/`**kwargs`, no untyped `dict`/`list`).
- **M-R1.9** Dependencies: every third-party library in `pyproject.toml` with a minimum version; test
  libraries under `[project.optional-dependencies].test`.
- **M-R1.10** Naming: PascalCase classes, snake_case functions/methods/properties; names consistent with the
  contract vocabulary (the CODEMANIFEST signatures are the vocabulary).

### R2. Test Writing (strictly from the project convention)

- **M-R2.1** Tools: pytest (running), pytest-cov (coverage), ruff (linting and formatting test code).
- **M-R2.2** Tests mirror the source structure directly — `goga_tool_pybuggy/commands/init/session.py` →
  `tests/commands/init/test_session.py`; root-package modules test directly under `tests/`
  (`statuses.py` → `tests/test_statuses.py`). Each test directory carries `__init__.py`.
- **M-R2.3** Fixtures: local fixtures in `tests/commands/init/conftest.py` (the recorder doubles), shared
  fixtures in `tests/conftest.py`.
- **M-R2.4** Naming: files `test_<module>.py`; functions `test_<what>_<scenario>`
  (e.g. `test_parse_specs_skips_malformed_and_colliding_extra_lines`); class grouping `class Test<Component>:`.
- **M-R2.5** Coverage: unit tests for every public routine — main scenario plus typical data; edge cases for
  empty inputs (`None`, `""`, `[]`, `{}`), boundary values, invalid types, and expected exceptions via
  `pytest.raises`; integration tests **only** for interaction between modules/packages.
- **M-R2.6** CLI testing: call the command handler function directly via Python call — no `CliRunner` in
  unit tests (wrapper-binding checks inspect decorator metadata and use a fake `ctx`).
- **M-R2.7** Boundary/threshold/state tables: `@pytest.mark.parametrize` including each boundary.
- **M-R2.8** Mocks only at external boundaries: pure logic without mocks; file I/O **exclusively** through
  the `tmp_path` fixture (+ `monkeypatch.chdir(tmp_path)`); engine seams stubbed with
  `monkeypatch.setattr` at the import point (`goga_tool_pybuggy.commands.init.init` / `.session` attributes);
  prompts stubbed only where a routine legitimately prompts (`click.confirm`).
- **M-R2.9** Self-documenting test names; keep comments minimal.
- **M-R2.10** Assertions on logging via `caplog` (stable event names from M-R1.5).

### R3. Linter and Formatter Enforcement (all development stages and local commits)

- **M-R3.1** `ruff` is the project's single linter AND formatter, configured in `pyproject.toml`
  (target py310, line-length 120, the full rule selection incl. `I`, `N`, `UP`, `B`, `SIM`, `PL`, `PT`,
  `ARG`, `RUF`, `PTH`, `C90` max-complexity 10; format: double quotes, LF).
- **M-R3.2** End of EVERY task (the LINT step): `ruff check goga_tool_pybuggy/ tests/` clean — zero
  findings on task-touched paths; fix formatting and decompose if the complexity cap demands it.
- **M-R3.3** Every file a task creates or modifies must be format-clean: `ruff format --check <touched files>`
  (run `ruff format <touched files>` to apply). Never reformat files outside the task's scope; if a
  pre-existing deviation exists in an untouched file, report it instead of fixing it silently.
- **M-R3.4** Local commit gate: before ANY local commit during execution, the full gate must pass —
  `ruff check goga_tool_pybuggy/ tests/` AND `ruff format --check <files touched by the commit>` AND
  `pytest tests/ -x` (in the venv). A red lint, a formatting diff, or a failing test blocks the commit.
  This applies to every development stage: implementation, tests, docs, and final validation.
- **M-R3.5** `goga lint` at plan end: no new findings against the baseline (17 cells, 1 pre-existing
  `goga-statuses` missing-file error — accepted residue, tracked for `goga usages sync`).

### R4. REPL Cycle (continuous interactive evaluation, hot reloading, code migration)

The implementation workflow is structured around a live-evaluation loop, not write-blind-then-test:

- **M-R4.1 (Continuous interactive evaluation)** — every routine is evaluated in a live Python REPL
  (the Task 1 virtualenv) against the representative inputs from the design traces **as it is being
  implemented**: real argument values, real sample configs, real engine records. Nothing moves to "done"
  on faith; each behavior is observed in the REPL first.
- **M-R4.2 (Hot reloading)** — after each source edit, reload the module inside the same session
  (`importlib.reload(goga_tool_pybuggy.commands.init.session)` etc.) or re-exec the probe script; never
  evaluate against stale definitions. Keep one continuous session per task where practical — the session is
  the running evaluation bench, source edits flow into it via reload.
- **M-R4.3 (Code migration to source files)** — the REPL is a scratchpad, never a home: every verified
  snippet is migrated into the module at its contract `location`, wearing the convention outfit (Google
  docstring M-R1.7, module logger M-R1.5, type hints M-R1.8, blank-line blocks M-R1.6), the scratch is
  discarded, and the migrated code is re-verified through a FRESH interpreter import
  (`python -c "from goga_tool_pybuggy.commands.init import <name>; ..."`) before the task's tests run.
- **M-R4.4 (REPL complements TDD, never replaces it)** — the contract tests and logic tests of each task
  remain the authority; the REPL loop lives inside STEP 2 (implementation) and STEP 5 (debugging) of the
  ralphex protocol.
- **M-R4.5 (Engine facts stay live)** — when a routine's behavior depends on an engine fact (ask semantics,
  hook delivery, serialization), confirm it once in the REPL against the installed goga 2.0.1 (import the
  engine entity, inspect the member) instead of trusting memory.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the next. Within
> each coding task, contract tests are written first (TDD workflow). The **Mandatory Rules** section
> (R1–R4) applies to every task in full.

### Task 1: Toolchain baseline — virtualenv, goga 2.0.1 pin, stale 1.x test removal (infrastructure)

The repo has no virtualenv; the conventions require one (M-R1.2). The `pyproject.toml` test extra pins
`goga>=1.3.0,<1.4.0` while the engine host runs goga 2.0.1, and the current `init.py` is dead code against
2.0.1 (imports the removed `GogaConfigAnswers`/`InitAnswers`), so the whole package and the entire test
suite fail at import. This task prepares the toolchain and removes the two 1.x-era test files that assert
the deleted API (they will be recreated by Tasks 3–9 per the Source File Registry); it does not touch
`goga_tool_pybuggy/` sources.

**Usages relevant to this task:**
- `conventions`: virtualenv constraint (M-R1.2), dependency rules (M-R1.9), validation command table.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create the project virtualenv at `.venv` (`python3 -m venv .venv`) using the system Python 3.12
- [x] Edit `pyproject.toml`: in `[project.optional-dependencies].test` replace `goga>=1.3.0,<1.4.0` with
      `goga>=2.0.1,<2.1`
- [x] Install: `.venv/bin/python -m pip install -e .[test]`
- [x] Verify the engine surface in the venv (REPL, M-R4.5):
      `.venv/bin/python -c "from goga.onboarding import FileGenerator, InitLogic, Question, QuestionGroup, Questionnaire, SessionAnswers, ToolParticipation; from goga.scaffold import Scaffold"` — must succeed
- [x] Delete the stale 1.x test files `tests/commands/init/test_init.py` and
      `tests/commands/init/test_init_integration.py` (they import `run_goga_init` / `build_pybuggy_config` /
      `run_onboarding` / `write_pybuggy_config` / `ensure_review_executor_skip` — all deleted by this plan)
- [x] Verify facade accessibility (current, pre-skeleton state — expected to FAIL on the new names, this
      records the gap): `.venv/bin/python -c "import goga_tool_pybuggy"` — the documented dead-import gap;
      document the observed error in the task notes
      (observed: `ImportError: cannot import name 'GogaConfigAnswers' from 'goga.onboarding'` at
      `goga_tool_pybuggy/commands/init/init.py:19`; task notes in `.ralphex/progress/progress-plan.txt`)
- [x] Record the working-tree diff: `git status` shows exactly `pyproject.toml` modified and the two test
      files deleted — nothing else
- [x] Lint: `.venv/bin/ruff check goga_tool_pybuggy/` — clean (sources untouched; commit gate M-R3.4)

### Task 2: Cell skeleton — `session.py`/`bootstrap.py` modules, dead-code removal, 17-name facade (infrastructure)

Make the package importable under goga 2.0.1 and lay the contract's file structure (the `location` values).
Create `session.py` and `bootstrap.py`; rewrite `init.py`; rewrite the cell facade. All 17 public routines
exist with their FINAL signatures, full Google docstrings (M-R1.7), module loggers (M-R1.5), relative
imports (M-R1.3), and `raise NotImplementedError` bodies — Tasks 3–7 implement them. The carried-over
private helpers move to their final homes VERBATIM in this task (they are not stubbed):

Module layout (from the design — the contract's `location` values):
- `init.py` — `init_cmd`, `run_init`, `resolve_init_mode`, `run_bootstrap` (stubs except the carried-over
  `init_cmd` and `resolve_init_mode`, which are behavior-unchanged and may land complete) + private:
  `_BARE`/`_TEMPLATE`/`_UPGRADE`, `_walk`, `_discover_usages`,
  `_DOCKERFILE_DEFAULT = Path(".goga")/"Dockerfile"`, `PYBUGGY_ANNOTATIONS`, `_annotation_for`,
  `_CONVENTION_LINE`, `_resolve_dockerfile_path` (stub), `_log_registration`.
- `session.py` — `run_session`, `declare_pybuggy_session`, `amend_pybuggy_config`, `pybuggy_questions`,
  `build_config_data`, `build_config_amendments`, `parse_specs` (stubs) + private: `_SCALAR_PROMPTS`,
  `_NUMERIC_MEMBERS` (both carried over verbatim from `init.py`), `_GIT_FIELDS = 6`.
- `bootstrap.py` — `write_test_convention`, `ensure_review_skip`, `install_pybuggy`, `register_usages`,
  `register_annotations`, `write_pybuggy_conftest` (stubs) + private: `_ensure_map` (carried over verbatim),
  `_CONFTEST_TEMPLATE`.
- Deleted from `init.py` (this task, same change): `run_onboarding`, `run_goga_init`, `build_pybuggy_config`,
  `write_pybuggy_config`, `ensure_review_executor_skip`, `_gate_existing`, `_write_root_conftest`,
  `_git_entry_to_map`, `_HEADERS_BLOCK`, `_LOADER_BLOCK`, `_COMPLEX_MEMBERS`, `_GIT_CHILD_INDENT`,
  `_INSTALL_LINE`, `_ask_scalar_values`, `_ask_spec`, `_DOCKERFILE_PATH`, and the dead
  `from goga.onboarding import ... GogaConfigAnswers, InitAnswers` import (the live imports —
  `InitLogic`, `Questionnaire`, `FileGenerator`, `ToolParticipation`, `Question`, `QuestionGroup` — move to
  `session.py`).
- `commands/init/__init__.py` — facade re-exports all 17 routines (alphabetical `__all__`).
- `statuses.py` — NOT touched in this task (Task 8 owns `register_hooks`; it keeps compiling with its two
  current subscriptions).

**Usages relevant to this task:**
- `conventions`: relative imports (M-R1.3), docstrings (M-R1.7), logging module loggers (M-R1.5).
- `goga-onboarding`: the `InitLogic`/`ToolParticipation` import surface used by `session.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] REPL probe first (M-R4.1/M-R4.5): in the venv REPL, import
      `goga.onboarding` entities and inspect `InitLogic.__init__`, `ToolDeclaration`, `ToolContribution`
      members — confirm the import list the skeleton needs
- [x] Create `goga_tool_pybuggy/commands/init/session.py` — module docstring, logger, engine imports
      (`InitLogic`, `Questionnaire`, `FileGenerator`, `ToolParticipation`, `Question`, `QuestionGroup`),
      config/plugin imports (`from ...config import GitEntry, SpecEntry`, `from ..plugin import PluginConfigKeys`),
      the carried-over `_SCALAR_PROMPTS`/`_NUMERIC_MEMBERS`, `_GIT_FIELDS = 6`, and the 7 routine stubs with
      final signatures + Google docstrings + `raise NotImplementedError`
      (note: imports not yet used by the stubs — `InitLogic`/`Questionnaire`/`FileGenerator`/
      `ToolParticipation`/`QuestionGroup`/`GitEntry` — land in Tasks 4–5 with their bodies; ruff F401
      blocks unused imports at the per-task gate, see progress notes)
- [x] Create `goga_tool_pybuggy/commands/init/bootstrap.py` — module docstring, logger, imports
      (`import importlib.metadata`, `import importlib.resources`, `from pathlib import Path`,
      `from ruamel.yaml import YAML, YAMLError`, `from ruamel.yaml.comments import CommentedMap`,
      `from ruamel.yaml.scalarstring import LiteralScalarString`), the carried-over `_ensure_map` and
      `_CONFTEST_TEMPLATE`, and the 6 routine stubs with final signatures + Google docstrings +
      `raise NotImplementedError`
      (same F401 note: `importlib.metadata`/`importlib.resources`/`YAML`/`YAMLError`/`LiteralScalarString`
      land in Task 3; `_ensure_scalar` also relocated here — unlisted in the plan, consumer is
      `register_annotations`)
- [x] Rewrite `goga_tool_pybuggy/commands/init/init.py` — new module docstring (three-mode surface),
      delete every dead routine/helper listed above, keep/land `init_cmd` and `resolve_init_mode` complete
      (behavior unchanged), stub `run_init`/`run_bootstrap`, relocate the init-side private helpers
      (`_walk`, `_discover_usages`, `PYBUGGY_ANNOTATIONS`, `_annotation_for`, `_CONVENTION_LINE`,
      `_log_registration`, `_BARE`/`_TEMPLATE`/`_UPGRADE`, `_DOCKERFILE_DEFAULT`, `_resolve_dockerfile_path`
      stub); imports: `click`, `goga.scaffold.Scaffold`, `importlib.resources`, ruamel error types for the
      catch tuple, `from .bootstrap import ...` (six writers), `from .session import run_session`
      (same F401 note: `Scaffold`/`importlib.resources`/`YAMLError`/six writers/`run_session` land in
      Tasks 6–7)
- [x] Rewrite `goga_tool_pybuggy/commands/init/__init__.py` — re-export all 17 routines, alphabetical
      `__all__`: `amend_pybuggy_config, build_config_amendments, build_config_data, declare_pybuggy_session,
      ensure_review_skip, init_cmd, install_pybuggy, parse_specs, pybuggy_questions, register_annotations,
      register_usages, resolve_init_mode, run_bootstrap, run_init, run_session, write_pybuggy_conftest,
      write_test_convention`
- [x] Verify facade accessibility (fresh interpreter, M-R4.3):
      `.venv/bin/python -c "from goga_tool_pybuggy.commands.init import amend_pybuggy_config, build_config_amendments, build_config_data, declare_pybuggy_session, ensure_review_skip, init_cmd, install_pybuggy, parse_specs, pybuggy_questions, register_annotations, register_usages, resolve_init_mode, run_bootstrap, run_init, run_session, write_pybuggy_conftest, write_test_convention"`
      — all 17 importable; `import goga_tool_pybuggy` succeeds; `register_hooks` importable from the root
- [x] Run validation: `.venv/bin/python -m pytest tests/ -x` — green (package importability restored; the
      init-specific suites do not exist yet; `tests/test_cli.py` passes with the stubs — registration only)
      (observed: 848 passed)
- [x] Lint: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` and
      `.venv/bin/ruff format --check goga_tool_pybuggy/commands/init/` — clean (commit gate M-R3.4)

### Task 3: `bootstrap.py` writers — relocation with two deltas (TDD)

Implement the six bootstrap writers. Four are carried over verbatim from the old `init.py`
(`write_test_convention`, `register_usages`, `register_annotations`, `write_pybuggy_conftest`) — the
relocation must not weaken their guarantees. Two carry the migration's deltas:
`ensure_review_executor_skip` → **`ensure_review_skip`** (renamed; enforced key path
`build.review_executor.skip` → **`build.review.skip`** — a documented project-config key; behavior otherwise
identical: round-trip, idempotent, returns `changed`), and `install_pybuggy` (install line derived from the
installed package version — no hardcoded `1.0.x`).

Verified traces (from the design — implement to these):

```
ensure_review_skip: round-trip via ruamel (preserve_quotes=True): load existing config or start an empty
CommentedMap; navigate/create build → review (each level _ensure_map, non-mapping → ValueError); skip is True
→ return False without writing; else set skip = True, dump, INFO, return True. Key path build.review.skip is a
documented project-config key; comments/order/quotes preserved; idempotent (no write when already true);
build.task_executor/other siblings untouched.

install_pybuggy:
1. dockerfile_path absent → return None (never creates the file)
2. version = importlib.metadata.version("goga-tool-pybuggy") (the distribution name from pyproject.toml);
   minor = ".".join(version.split(".")[:2]); line = f"RUN goga install pybuggy -v {minor}.x"
   (minor x-range is a valid goga install version form, N.M.x → ~=N.M.0; dev/pre tails e.g. 1.1.1.dev4+...
   still yield 1.1.x). PackageNotFoundError is NOT in the bootstrap catch tuple — propagates uncaught,
   unreachable in practice.
3. Line already in content → return None; else ensure trailing newline, append, write, INFO, return the line.
```

`register_usages` / `register_annotations` / `write_pybuggy_conftest` / `write_test_convention`: carried over
verbatim (relocation only); signatures gain typed return labels (`added_keys: list[str]`,
`changed_keys: list[str]`) — no behavioral change. Registration guarantees: existing keys never overwritten;
reference-keyed annotation idempotency; fixed `_CONFTEST_TEMPLATE`; packaged asset via
`importlib.resources.files("goga_tool_pybuggy") / "assets" / "conventions.md"` (the `/` traversal keeps
Python 3.10 compatibility).

**Usages relevant to this task:**
- `conventions`: test structure (M-R2.2 — `tests/commands/init/test_bootstrap.py`), `tmp_path` file I/O
  (M-R2.8), docstrings/logging (M-R1.5/M-R1.7).
- `ruamel-yaml`: round-trip discipline — `YAML()` + `preserve_quotes=True`, `_ensure_map` navigation,
  idempotent skip-existing insert, reference-keyed annotation replacement, `LiteralScalarString` re-emit;
  from-scratch `CommentedMap` documents; the ruamel `load → None` (empty file) gotcha.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (in `tests/commands/init/test_bootstrap.py`, expected to fail against the stubs):
      facade import of the six names from `goga_tool_pybuggy.commands.init`; signatures —
      `ensure_review_skip(config_path: Path) -> bool`, `install_pybuggy(dockerfile_path: Path) -> str | None`,
      `register_usages(config_path: Path, usage_keys: dict[str, str]) -> list[str]`,
      `register_annotations(config_path: Path, annotation_lines: dict[str, str]) -> list[str]`,
      `write_pybuggy_conftest(path: Path) -> None`, `write_test_convention(path: Path) -> None`
      (inspect via `typing.inspect`/`__annotations__`)
- [ ] **REPL cycle** (M-R4.1/M-R4.2): in the venv REPL against a `tmp` sample config with comments and a
      `build.task_executor` sibling — round-trip `ensure_review_skip` twice, verify the comment survives,
      the sibling is intact, and the second call does not rewrite (mtime unchanged); derive the install line
      interactively for versions `"2.0.3"` and `"1.1.1.dev4+gabc"`; then migrate the verified code into
      `bootstrap.py` and re-verify via a fresh import (M-R4.3)
- [ ] **Code**: implement `ensure_review_skip` (rename + key path `build.review.skip`; round-trip,
      `_ensure_map` levels, idempotent no-write, INFO `"review executor skip enabled"`-style stable event —
      keep the existing event name for the renamed key)
- [ ] **Code**: implement `install_pybuggy` (dynamic minor x-range line; no-op when absent; idempotent;
      only the install line appended)
- [ ] **Code**: land the four carried-over writers in `bootstrap.py` verbatim
      (`write_test_convention`, `register_usages`, `register_annotations`, `write_pybuggy_conftest`) with
      typed return labels; delete their stubs
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/commands/init/test_bootstrap.py -v` —
      contract tests pass
- [ ] **Logic tests** (design scenarios, Setup/Assertions transferred):
      - `test_ensure_review_skip_enforces_key_and_preserves_config` — Setup: `tmp_path/config.yml` with
        comments and siblings (`build: {task_executor: {...}}`, `# keep me`); Assertions: returns `True`;
        re-loaded YAML has `build.review.skip is True`; `build.task_executor` intact; the `# keep me` comment
        still present; second call returns `False` and leaves the file byte-identical (mtime unchanged)
      - `test_install_pybuggy_derives_minor_line_and_is_idempotent` — Setup: `tmp_path/Dockerfile` with
        `"FROM python:3.12\n"`; monkeypatch `importlib.metadata.version` → `"2.0.3"`; run twice;
        Assertions: first returns the exact line and the file content equals
        `"FROM python:3.12\nRUN goga install pybuggy -v 2.0.x\n"`; second returns `None`, content unchanged;
        a dev-suffix version `"1.1.1.dev4+gabc"` yields `-v 1.1.x`
      - `test_install_pybuggy_noop_without_file` — absent Dockerfile path → returns `None`; the file is
        not created
      - `test_register_usages_and_annotations_idempotent` (parametrized pair) — Setup: `tmp_path/config.yml`
        with existing `codemanifest.usages {"pybuggy-api": "old.md"}` and an annotations block carrying a
        stale `pybuggy-api` line + a foreign line; Input: `register_usages(config, {"pybuggy-api": "new.md",
        "conventions": ".goga/usages/conventions.md"})`; `register_annotations(config, {"pybuggy-api":
        "Use \`pybuggy-api\` ...", "conventions": "Use \`conventions\` ..."})`; Assertions:
        `added_keys == ["conventions"]`; `changed_keys == ["pybuggy-api", "conventions"]`; second run returns
        `[]`/`[]` and the file text is unchanged
      - `test_write_pybuggy_conftest_and_test_convention_emit_fixed_assets` — conftest content equals the
        pinned template string exactly; convention content equals the packaged asset (anchored by its
        `# Testing Convention: pytest...` first line); both overwrite on the second call
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/ -x` — fix implementation code until all tests pass
      (do NOT fix test code)
- [ ] **Contract re-verification**: facade, API shape, and behavior of the six writers match the
      CODEMANIFEST annotations (round-trip preservation, idempotency, never-overwrite, no file creation)
- [ ] **Lint**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` +
      `.venv/bin/ruff format --check goga_tool_pybuggy/commands/init/bootstrap.py tests/commands/init/test_bootstrap.py`
      — clean (commit gate M-R3.4)

### Task 4: `session.py` pure builders — question block, payloads, spec parsing (TDD)

Implement the four pure routines: `pybuggy_questions`, `build_config_data`, `build_config_amendments`,
`parse_specs`. No I/O, no prompts — engine data in, plain data out. The question ids, prompt texts, and the
group id `first_spec` are **exactly** as specified — they are the answer keys consumed downstream and
pinned by tests.

Verified algorithm blocks (from the design — implement to these):

```
pybuggy_questions:
items = [Question(id="base_url", kind="input", prompt="Base URL (Jinja2 template, required)")]
FOR member IN PluginConfigKeys:                       # declaration order
  IF member IN (BASE_URL, HEADERS, LOADER): CONTINUE
  items.append(Question(id=member.value, kind="input", default="", prompt=_SCALAR_PROMPTS[member]))
items.append(QuestionGroup(id="first_spec", prompt="The first spec", children=[
    Question(id="name", kind="input", prompt="Spec name"),
    Question(id="type", kind="choice", prompt="Spec type", choices=["swagger", "openapi"]),
    Question(id="location", kind="input", prompt="Spec location (path from project root)"),
    Question(id="git_url", kind="input", default="", prompt="Git URL (empty — no git source)"),
    Question(id="git_location", kind="input", default="", prompt="Path inside the repository"),
    Question(id="git_ref", kind="input", default="", prompt="Git ref (branch/tag; empty — default branch)"),
]))
items.append(Question(id="extra_specs", kind="input", default="",
    prompt="Additional specs, one per line: name|type|location|git_url|git_location|git_ref"))
RETURN items
# items holds Question records plus one QuestionGroup; the signature label list[Question] reads
# "question records" per goga-onboarding-questions. Fresh immutable records per call.

build_config_data(answers):
specs = parse_specs(answers.get("first_spec") or {}, answers.get("extra_specs") or None)
data = {}
FOR member IN PluginConfigKeys:
  IF member IN (HEADERS, LOADER): CONTINUE
  value = answers.get(member.value)
  IF value in (None, ""): CONTINUE                    # unanswered dropped, never written empty
  data[member.value] = _NUMERIC_MEMBERS[member](value) IF member IN _NUMERIC_MEMBERS ELSE value
data["specs"] = {name: entry.model_dump(exclude_none=True) FOR name, entry IN specs.items()}
RETURN data
# plain serializable payload only — the engine yaml.dump()s buffered data verbatim and silently drops
# unserializable files; key order = plugin key order with specs last; a non-numeric numeric answer raises
# ValueError (soft-drop at the engine — documented contract behavior).

build_config_amendments():
RETURN {"build.review.skip": True}
# the single amendment is unconditional — the tool's declared intent in the answer space. The engine config
# mapper drops it (_build_config_document emits only agent/env for the build block), so the consumer-visible
# flag comes solely from the bootstrap's ensure_review_skip (review decision q2/A).

parse_specs(spec_answers, extra_specs):
specs = {}
name, spec_type, location = strict_first_spec(spec_answers)      # ValueError on any empty/invalid
git = GitEntry(url, location, ref) IF url AND repo_location ELSE None
specs[name] = SpecEntry(type=spec_type, location=location, git=git)
IF extra_specs:
  FOR line IN extra_specs.splitlines():
    IF NOT line.strip(): CONTINUE
    parts = [p.strip() FOR p IN line.split("|")]
    IF len(parts) < 3 OR NOT parts[0] OR parts[1] NOT IN ("swagger","openapi") OR NOT parts[2]:
        logger.warning("malformed extra spec line skipped", extra={"line": line}); CONTINUE
    git_url, git_loc, git_ref = (parts[3:6] + ["",""])[:3] if len(parts) > 3 else ("","","")
    IF parts[0] IN specs: logger.warning("duplicate spec name skipped", ...); CONTINUE
    specs[parts[0]] = SpecEntry(type=parts[1], location=parts[2],
                                git=GitEntry(git_url, git_loc, git_ref or None) IF git_url AND git_loc ELSE None)
RETURN specs
# strict first spec → ValueError (soft contribution drop upstream); extras never raise; a line with extra
# |-fields beyond six → the first six win; whitespace-only lines skipped; name collision keeps the first.
```

**Usages relevant to this task:**
- `goga-onboarding-questions`: `Question`/`QuestionGroup` record kinds and fields; required = absent default;
  optional = `default=""`; group answer = mapping of child ids; the one-level nesting rule.
- `goga-onboarding-generator`: payload discipline — plain-data payload, verbatim serialization.
- `configuration` (imported from `goga_tool_pybuggy/config`): schema compatibility — `specs` mapping with
  required entry fields; scalar plugin keys ignored on loading; typed entries `SpecEntry(type, location, git)` /
  `GitEntry(url, location, ref)`.
- `conventions`: pure logic tested without mocks (M-R2.8); naming (M-R2.4).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (in `tests/commands/init/test_session.py`, expected to fail against the stubs):
      facade import of the four names; signatures —
      `pybuggy_questions() -> list`, `build_config_data(answers: dict[str, object]) -> dict[str, object]`,
      `build_config_amendments() -> dict[str, object]`,
      `parse_specs(spec_answers: dict[str, object], extra_specs: str | None) -> dict[str, SpecEntry]`
- [ ] **REPL cycle** (M-R4.1–M-R4.3): in the venv REPL — construct the block and inspect order/ids/defaults;
      call `parse_specs` with the design sample (`shop|swagger|specs/shop.yaml` first spec + the billing extra
      line `billing|openapi|specs/billing.yaml|https://git/b.git|specs/b.yaml|`); call `build_config_data`
      on that answer view and verify with `yaml.safe_dump` that the payload serializes and contains no
      pydantic objects; migrate the verified bodies into `session.py`, re-verify via fresh import
- [ ] **Code**: implement `pybuggy_questions` (exact ids/prompts/order per the algorithm block; fresh
      records per call; data-driven scalar set from `PluginConfigKeys`)
- [ ] **Code**: implement `parse_specs` (strict first spec; lenient extras with WARNING events
      `"malformed extra spec line skipped"` / `"duplicate spec name skipped"` via `extra`)
- [ ] **Code**: implement `build_config_data` (drop unanswered; numeric coercion via `_NUMERIC_MEMBERS`;
      `model_dump(exclude_none=True)` specs; `specs` last)
- [ ] **Code**: implement `build_config_amendments` (single unconditional `build.review.skip` entry)
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/commands/init/test_session.py -v` —
      contract tests pass
- [ ] **Logic tests** (design scenarios, Setup/Assertions transferred):
      - `test_pybuggy_questions_returns_block_in_survey_order` — Assertions: `len(items) == 9`;
        `items[0].id == "base_url" and items[0].default is None`; scalar ids equal the `PluginConfigKeys`
        values in declaration order, each `default == ""`; the group `id == "first_spec"`, `children` ids
        `["name","type","location","git_url","git_location","git_ref"]`, `type` child
        `choices == ["swagger","openapi"]`; `items[-1].id == "extra_specs"`
      - `test_pybuggy_questions_covers_every_scalar_plugin_key` — collect question ids ∪ group children ids
        → set-equal `{m.value for m in PluginConfigKeys} - {"headers","loader"}`; `HEADERS`/`LOADER` never
        present
      - `test_pybuggy_questions_holds_one_nesting_level` — every `QuestionGroup` child is a simple `Question`
      - `test_parse_specs_builds_first_spec_without_git` — Setup:
        `{"name": "shop", "type": "swagger", "location": "specs/shop.yaml", "git_url": "", "git_location": "",
        "git_ref": ""}`; Assertions: single entry; `entry.type == "swagger"`,
        `entry.location == "specs/shop.yaml"`, `entry.git is None`
      - `test_parse_specs_attaches_git_when_url_and_location_present` — git attached when both present
        (`ref` from `git_ref`); empty `git_ref` → `ref is None`; `git_url` with empty `git_location` →
        `git is None`
      - `test_parse_specs_adds_wellformed_extra_line` — Input:
        `"billing|openapi|specs/billing.yaml|https://git/b.git|specs/b.yaml|"`; Assertions:
        `set(specs) == {"shop", "billing"}`; billing entry fields exact (empty ref → `None`)
      - `test_parse_specs_rejects_invalid_first_spec` (parametrized: empty name; `type="yaml"`; empty
        location) — `pytest.raises(ValueError)` per variant
      - `test_parse_specs_skips_malformed_and_colliding_extra_lines` — Input:
        `"billing|yaml|x.yaml\nbad|swagger\n| swagger | loc\nshop|openapi|other.yaml"`; Assertions:
        `set(specs) == {"shop"}`; caplog has 4 warnings with the two stable event names
      - `test_build_config_data_emits_plain_serializable_payload` — Setup: answers with
        `base_url="https://{{ HOST }}/api"`, `timeout="30"`, `retries="3"`, unanswered `assert_delay=""`,
        `first_spec` and one extra spec; Assertions: `data["timeout"] == 30.0 and isinstance(..., float)`;
        `data["retries"] == 3`; `"assert_delay" not in data`;
        `data["specs"]["shop"] == {"type": "swagger", "location": "specs/shop.yaml"}` (no `git` key); every
        value is `str/int/float/dict` — `yaml.safe_dump(data)` succeeds with no `SpecEntry` objects present;
        key order `[base_url, timeout, retries, specs]`
      - `test_build_config_data_non_numeric_answer_raises` — `timeout="abc"` → `pytest.raises(ValueError)`
      - `test_build_config_amendments_review_skip_declared_intent_only` — result ==
        `{"build.review.skip": True}` — exactly one entry, bool value
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/ -x` — fix implementation code until all tests pass
      (do NOT fix test code)
- [ ] **Contract re-verification**: facade, API shape, behavior match the CODEMANIFEST annotations (one
      nesting level; payload plain serializable; single amendment; lenient extras)
- [ ] **Lint**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` +
      `.venv/bin/ruff format --check goga_tool_pybuggy/commands/init/session.py tests/commands/init/test_session.py`
      — clean (commit gate M-R3.4)

### Task 5: `session.py` participation hooks + session seam (TDD)

Implement the three remaining session routines: `run_session`, `declare_pybuggy_session`,
`amend_pybuggy_config`. The hooks are the core of the migration — the two participation moments. Engine
fixtures are plain recorder doubles asserting member usage, not engine internals.

Verified traces (from the design — implement to these):

```
run_session:
logic = InitLogic(questionnaire=Questionnaire(), generator=FileGenerator(),
                  participation=ToolParticipation(invited=["pybuggy"]))
RETURN logic.run()
# invited identity "pybuggy" is the platform-assigned tool identity of goga_tool_pybuggy. Errors: none caught
# here — engine exit codes and clean messages are propagated; tool contribution failures are soft inside the
# engine (warning + drop, session 0).

declare_pybuggy_session(context):        # context = ToolDeclaration proxy, delivered by name
IF NOT context.invited: RETURN
FOR item IN pybuggy_questions(): context.declare(item)
# no skips are declared (pybuggy removes no core subtree); a duplicate local name would be rejected by the
# engine with a warning (defended by construction — ids fixed in Task 4).

amend_pybuggy_config(context):           # context = ToolContribution proxy; .answers = view_for("pybuggy")
IF NOT context.invited: RETURN
answers = context.answers
FOR id, value IN build_config_amendments().items(): context.answer(id, value)   # answer(id, value) accepts
                                                                                # str | bool | dict at a dot-path
context.write_config("config.yml", build_config_data(answers))  # engine writes .goga/tools/pybuggy/config.yml
# any exception propagates to the mediator, which drops the whole contribution with a warning naming pybuggy
# (soft) — the session and the bootstrap still complete.
```

**Usages relevant to this task:**
- `goga-onboarding-hooks`: the two onboarding actions, subscribe addresses, hook signature rules
  (context/self by name), moment member contracts (`.invited`, `.declare`, `.answers`, `.answer`,
  `.write_config`), failure behavior (mediator drops the contribution).
- `goga-onboarding`: `InitLogic(questionnaire, generator, participation)` facade, session semantics
  (existing-config end, soft tool failures, artifact set).
- `goga-onboarding-generator`: buffered tool config serialization — file name `config.yml` →
  `.goga/tools/pybuggy/config.yml` (tool dir from the platform identity); payload discipline from Task 4.
- `conventions`: engine seams stubbed with `monkeypatch.setattr` at the import point (M-R2.8); recorder
  fixtures in `tests/commands/init/conftest.py` (M-R2.3).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (in `tests/commands/init/test_session.py`, expected to fail against the stubs):
      facade import of the three names; signatures — `run_session() -> int`,
      `declare_pybuggy_session(context: object) -> None`, `amend_pybuggy_config(context: object) -> None`
- [ ] **REPL cycle** (M-R4.1/M-R4.5): in the venv REPL — import `goga.onboarding` and inspect
      `ToolParticipation`, `InitLogic.__init__` parameter names (constructor verified:
      `InitLogic(questionnaire, generator, participation)`); drive the two hooks by hand against the
      recorder doubles (declare the block, buffer the contribution); migrate the verified bodies into
      `session.py`, re-verify via fresh import
- [ ] **Code**: implement `run_session` (engine logic construction + `run()`; nothing caught, nothing wrapped)
- [ ] **Code**: implement `declare_pybuggy_session` (invited guard; declare every block item in order)
- [ ] **Code**: implement `amend_pybuggy_config` (invited guard; read `answers`; buffer
      `build_config_amendments()`; `write_config("config.yml", build_config_data(answers))`)
- [ ] Add the recorder doubles to `tests/commands/init/conftest.py`: a `ToolDeclaration`-like recorder
      (attributes `invited`, lists `declared`, `skips`) and a `ToolContribution`-like recorder (`invited`,
      `answers`, `amendments`, `files`) — plain doubles asserting member usage, not engine internals
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/commands/init/test_session.py -v` —
      contract tests pass
- [ ] **Logic tests** (design scenarios, Setup/Assertions transferred):
      - `test_declare_pybuggy_session_declares_block_when_invited` — recorder `invited=True`;
        Assertions: `[i.id for i in context.declared]` equals the `pybuggy_questions()` id sequence (group
        included); `context.skips == []`
      - `test_amend_pybuggy_config_buffers_contribution_when_invited` — recorder `invited=True`, `answers` =
        core + own block fixture; Assertions: `context.amendments == [("build.review.skip", True)]` (the
        single amendment, q2/A); `context.files == [("config.yml", <payload>)]`; payload equals
        `build_config_data(answers)`
      - `test_run_session_builds_engine_logic_with_pybuggy_invited` — `monkeypatch.setattr` on
        `goga_tool_pybuggy.commands.init.session.InitLogic` with a recorder class; Assertions: constructor
        called with `Questionnaire()`, `FileGenerator()`, `ToolParticipation(invited=["pybuggy"])`
        instances (kwargs types/names; `participation._invited == ["pybuggy"]` or recorder equivalent);
        return value `7` propagated as `7`
      - `test_declare_and_amend_no_invitation_call_nothing` — recorder contexts with `invited=False`;
        Assertions: `declared == []`, `skips == []`, `amendments == []`, `files == []`
      - `test_amend_pybuggy_config_exception_drops_contribution_upstream` — recorder context whose
        `answers` trigger `build_config_data` `ValueError` (bad numeric); Assertions:
        `pytest.raises(ValueError)`; `files == []` (the write never buffered)
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/ -x` — fix implementation code until all tests pass
      (do NOT fix test code)
- [ ] **Contract re-verification**: facade, API shape, behavior match the CODEMANIFEST annotations
      (engine-owned questions; no-invitation silence; buffered-only writes; propagated exceptions)
- [ ] **Lint**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` +
      `.venv/bin/ruff format --check goga_tool_pybuggy/commands/init/session.py tests/commands/init/` —
      clean (commit gate M-R3.4)

### Task 6: `init.py` CLI surface + orchestrator — `init_cmd`, `run_init`, `resolve_init_mode` (TDD)

`resolve_init_mode` is carried over verbatim (contract text unchanged); `init_cmd` keeps its decorator set
and behavior (annotation rewritten to the three-mode surface wording — Task 2 already landed it);
`run_init` is rewired: `run_session` then `run_bootstrap` instead of `run_onboarding`, with the refined
exit-code contract.

Verified trace (from the design — implement to this):

```
run_init(tpl, ref, upgrade):
1. resolve_init_mode(tpl, ref, upgrade) → invalid combination raises click.ClickException (click prints, exit 1)
2. Bare guard: mode == "bare" and Path(".goga").is_dir() → echo "Project already initialized" to stderr,
   return 1 (directory-existence only — a .goga regular file passes; zero prompts/writes on refusal)
3. Upgrade: return Scaffold().upgrade(ref) (engine owns errors; code propagated as-is; no session, no bootstrap)
4. Template: code = Scaffold().generate(tpl, ref); non-zero → return code (no onboarding side effect)
5. code = run_session(); non-zero → return code (session exit code propagated unchanged, bootstrap skipped)
6. return run_bootstrap(template_mode=(mode == "template"))
Output: 0 / 1 / propagated engine or session code.
```

`init_cmd` decorators: `@click.command("init")`, `@click.argument("tpl", required=False)`,
`@click.option("--upgrade", is_flag=True, default=False, ...)`, `@click.option("--ref", default=None, ...)`,
`@click.pass_context`; body `ctx.exit(run_init(tpl, ref, upgrade))`.

**Usages relevant to this task:**
- `click`: the command wrapper, flag validation via `ClickException` (flag violations ONLY), stderr echo
  (`click.echo(..., err=True)`).
- `goga-scaffold`: `Scaffold().generate(template_input, ref_override)` / `Scaffold().upgrade(ref_override)`
  exit-code contract — engine constructed per call, codes propagated as-is, exceptions/diagnostics never wrapped.
- `conventions`: CLI testing via direct handler calls (M-R2.6), parametrized tables (M-R2.7), `tmp_path` (M-R2.8).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (in `tests/commands/init/test_init.py`, expected to fail against the stubs):
      facade import of the three names; `init_cmd.__click_params__` surface (optional positional `tpl`,
      flag `--upgrade`, option `--ref`); `run_init` / `resolve_init_mode` signatures
- [ ] **REPL cycle** (M-R4.1/M-R4.2): in the venv REPL — exercise `resolve_init_mode` across the flag table;
      dry-drive `run_init` with `run_session`/`run_bootstrap` monkeypatched recorders (bare → session+bootstrap
      order, template flag propagation); migrate the verified `run_init` body into `init.py`, re-verify via
      fresh import
- [ ] **Code**: implement `run_init` per the trace above (session seam propagated; bootstrap last; no wrapping)
- [ ] **Code**: confirm `init_cmd` and `resolve_init_mode` complete (landed in Task 2; verify behavior —
      carried-over code, zero diffs expected beyond module moves)
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/commands/init/test_init.py -v` — contract
      tests pass
- [ ] **Logic tests** (design scenarios, Setup/Assertions transferred):
      - `test_resolve_init_mode_table` (parametrized) — `(None, None, False)`→`bare`; `("tpl", None, False)`→
        `template`; `("tpl", "v2", False)`→`template`; `(None, "v2", True)`→`upgrade`;
        `(None, None, True)`→`upgrade`
      - `test_run_init_bare_runs_session_then_bootstrap` — `tmp_path` cwd (no `.goga`); `run_session` → 0
        recorder, `run_bootstrap` recorder; Assertions: both called once, in order;
        `template_mode is False`; return 0
      - `test_run_init_template_passes_template_mode` — `Scaffold.generate`/`Scaffold.upgrade` monkeypatched;
        `run_init("https://t.git#v1", None, False)`; Assertions: `generate` called with `("https://t.git#v1", None)`;
        `template_mode is True`; return 0
      - `test_run_init_bare_guard_refuses_initialized_project` — `tmp_path` with `.goga/` directory;
        session/bootstrap/Scaffold monkeypatched to raise `AssertionError` if called; Assertions: return 1;
        stderr contains `Project already initialized`; no recorder called; the `.goga` tree byte-identical
      - `test_run_init_guard_checks_directory_existence_only` — `tmp_path` with a `.goga` **regular file**;
        Assertions: recorders called; return matches the stubbed codes
      - `test_run_init_invalid_flag_combinations_raise` (parametrized `("t", None, True)`,
        `(None, "v2", False)`) — `pytest.raises(click.ClickException)`; message present
      - `test_run_init_propagates_engine_and_session_codes` (parametrized) — scaffold returns 3 (template
        mode; session/bootstrap must not run); session returns 4 (bootstrap must not run); upgrade returns 5;
        Assertions: returns 3 / 4 / 5; downstream recorders not called for the failing seam
      - `test_init_cmd_binds_surface_and_propagates_exit` — introspect `init_cmd.__click_params__`; fake
        `ctx` object; `init_cmd(ctx, None, None, False)` with `run_init` monkeypatched → 3; Assertions:
        params carry the optional positional `tpl`, flag `--upgrade`, option `--ref`; `ctx.exit` called with 3
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/ -x` — fix implementation code until all tests pass
      (do NOT fix test code)
- [ ] **Contract re-verification**: facade, API shape, behavior match the CODEMANIFEST annotations (guard
      semantics, code propagation, no wrapping of engine diagnostics)
- [ ] **Lint**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` +
      `.venv/bin/ruff format --check goga_tool_pybuggy/commands/init/init.py tests/commands/init/test_init.py`
      — clean (commit gate M-R3.4)

### Task 7: `run_bootstrap` — the 9-step post-session orchestrator (TDD)

Implement `run_bootstrap(template_mode)` and its private helper `_resolve_dockerfile_path(config)`. This is
the pybuggy-owned delivery of the files the session does not carry, with mode-dependent gates, the
Dockerfile resolution (user-confirmed design q1/A), and the tier change (step failures → ERROR + return 1,
never `click.ClickException`).

Verified algorithm (from the design — implement to this):

```
run_bootstrap(template_mode):
1. cwd = Path.cwd()
2. discovered = _discover_usages(files("goga_tool_pybuggy.api"))
   FOR (stem, text) IN discovered:
     dest = cwd/.goga/usages/cooks/pybuggy/<stem>.md
     IF dest.exists() AND template_mode: log INFO("existing file kept untouched"); CONTINUE
     dest.parent.mkdir(parents=True, exist_ok=True); dest.write_text(text)   # bare: overwrite
3. slot = cwd/.goga/usages/conventions.md
   IF slot.exists(): log INFO           ELSE: write_test_convention(slot)
4. changed = ensure_review_skip(cwd/.goga/config.yml)          # always
5. dockerfile = _resolve_dockerfile_path(cwd/.goga/config.yml) # config field, fallback .goga/Dockerfile
   install_pybuggy(dockerfile)                                  # no-op when absent
6. added = register_usages(config, usage_keys(discovered))
   changed_ann = register_annotations(config, annotation_lines(discovered))
   _log_registration(...)                                       # INFO added, WARNING skipped
7. conftest = cwd/conftest.py
   IF NOT conftest.exists(): write_pybuggy_conftest(conftest)
   ELIF template_mode: log INFO
   ELSE: IF click.confirm("conftest.py exists — overwrite it?", default=False):
           write_pybuggy_conftest(conftest)
8. IF NOT dockerfile.exists(): log ERROR("Dockerfile missing after the session"); RETURN 1
9. RETURN 0
   — steps 2–7 wrapped: EXCEPT (OSError, YAMLError, ValueError) AS e: log ERROR; RETURN 1

_resolve_dockerfile_path(config): read the consumer config (yaml.safe_load) → dockerfile field →
   dockerfile_path = Path(field); missing config/field → fallback Path(".goga/Dockerfile")
   (honors a custom session answer — the install line lands in the project's actual Dockerfile).
```

**Edge cases (design, incl. user-confirmed decisions q1/A and q2/A):** template mode never prompts
(skip-with-INFO only); bare mode overwrites usages targets but asks for the conftest (decline → untouched,
exit stays 0); existing conventions slot untouched in both modes; repeat run is a no-op (idempotent writers
+ skip-existing registrations). **Dockerfile-decline branch**: the core confirm "Create Dockerfile?"
defaults to No — a user declining it leaves no Dockerfile and no config `dockerfile` field (the generator
requires both the dockerfile and the base_image answers). The run then completes steps 2–7 and fails at
step 8 (ERROR + 1): the declined-Dockerfile session is a **failed init by design**. Recovery for the
half-initialized project: create the Dockerfile at the config `dockerfile` path (default `.goga/Dockerfile`)
and re-run the registrations by hand, or remove `.goga` and re-run — a repeat bare `pybuggy init` is refused
by the already-initialized guard. Documented in MIGRATION.md (Task 10) and `.usages/init.md` (current).

**Usages relevant to this task:**
- `click`: the bare-mode conftest gate (`click.confirm(..., default=False)`); `click.Abort` propagates
  unswallowed to click.
- `ruamel-yaml`: via the Task 3 writers; the `None`-document and from-scratch creation gotchas for the
  config variants test.
- `conventions`: `tmp_path` + `monkeypatch.chdir` (M-R2.8), `caplog` assertions (M-R2.10), prompt stubs only
  where the routine legitimately prompts.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (in `tests/commands/init/test_init.py`, expected to fail against the stub):
      facade import of `run_bootstrap`; signature `run_bootstrap(template_mode: bool) -> int`;
      `_resolve_dockerfile_path` present in the module
- [ ] **REPL cycle** (M-R4.1/M-R4.2): in the venv REPL with a scratch cwd under `tmp_path` — pre-create the
      session artifacts (`.goga/config.yml` with `dockerfile: Dockerfile`, a root `Dockerfile` with
      `FROM x`), run `run_bootstrap(template_mode=True)` interactively, inspect every produced file
      (usages copies, conventions slot, `build.review.skip`, install line at the RESOLVED path, conftest);
      reload after each edit (M-R4.2); migrate verified code, re-verify via fresh import (M-R4.3)
- [ ] **Code**: implement `_resolve_dockerfile_path` (config `dockerfile` field via `yaml.safe_load`,
      fallback `_DOCKERFILE_DEFAULT`; missing/empty config → fallback)
- [ ] **Code**: implement `run_bootstrap` — the nine steps with the wrapped tier
      (`except (OSError, YAMLError, ValueError)` → `logger.error` + return 1), the mode gates, the final
      Dockerfile existence check (ERROR + 1)
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/commands/init/test_init.py -v` — contract
      tests pass
- [ ] **Logic tests** (design scenarios, Setup/Assertions transferred):
      - `test_run_bootstrap_full_pass_on_fresh_session_artifacts` — Setup: `tmp_path` cwd; pre-create
        `.goga/config.yml` (yaml text with `dockerfile: .goga/Dockerfile`), `.goga/Dockerfile` (`FROM x`);
        no conftest; `run_bootstrap(template_mode=False)`; Assertions: return 0;
        `.goga/usages/cooks/pybuggy/api.md` and `asserts.md` exist with the packaged texts;
        `.goga/usages/conventions.md` exists; config has `build.review.skip is True`,
        `codemanifest.usages["pybuggy-api"]`/`["conventions"]`, annotation lines carrying the references;
        `conftest.py` equals the template; Dockerfile ends with the install line; caplog has no ERROR
      - `test_run_bootstrap_resolves_dockerfile_from_config_field` — Setup: `dockerfile: Dockerfile` (custom
        root path) with `Dockerfile` (`FROM x`) present; `.goga/Dockerfile` absent;
        `run_bootstrap(template_mode=True)`; Assertions: return 0; `Dockerfile` ends with the install line;
        `.goga/Dockerfile` was not created
      - `test_run_bootstrap_missing_dockerfile_fails_with_error` (parametrized) — (a) a config whose
        `dockerfile` field points at an absent file; (b) the declined-Dockerfile session: a config with
        **no** `dockerfile` field at all; no Dockerfile anywhere; Assertions: return 1 per variant; caplog
        ERROR mentions the Dockerfile; conftest/usages side effects already applied (steps 2–7 ran);
        variant (b) additionally asserts `.goga/Dockerfile` was NOT created by the bootstrap
      - `test_run_bootstrap_step_failure_maps_to_nonzero` — monkeypatch `register_usages` to raise
        `OSError`; Assertions: return 1; caplog ERROR with the cause; no `click.ClickException` raised
        (the tier changed from the old code)
      - `test_run_bootstrap_template_mode_never_prompts` — cwd with every gated file pre-existing;
        `click.confirm` monkeypatched to raise; Assertions: return 0; no confirm call; every pre-existing
        file byte-identical; INFO logs emitted
      - `test_run_bootstrap_bare_mode_gates` — pre-existing usages target (stale content) and conftest;
        confirm monkeypatched `False` then `True` (two runs); Assertions: run 1 (decline): stale usages
        text replaced, conftest unchanged, return 0; run 2 (confirm): conftest equals the template
      - `test_run_bootstrap_existing_config_session_end_still_enforces` — pre-existing full config
        (template-brought-config case), Dockerfile present, `template_mode=True`; Assertions: return 0;
        `build.review.skip is True`; usage keys registered; install line appended
      - `test_run_bootstrap_idempotent_rerun` — run once on fresh artifacts; snapshot the tree
        (`{p: p.read_bytes()}`); run again (confirm monkeypatched False); Assertions: tree snapshot
        identical; returns 0
      - `test_run_bootstrap_empty_and_broken_config_variants` — variant A: absent `.goga/config.yml`
        (registrations create the minimal document; dockerfile falls back); variant B: empty file (ruamel
        `load` → `None` handling); Assertions: no exception; Dockerfile fallback path used
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/ -x` — fix implementation code until all tests pass
      (do NOT fix test code)
- [ ] **Contract re-verification**: facade, API shape, behavior match the CODEMANIFEST annotations (gates,
      idempotency, mandatory Dockerfile invariant, non-raising failure tier)
- [ ] **Lint**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` +
      `.venv/bin/ruff format --check goga_tool_pybuggy/commands/init/init.py tests/commands/init/test_init.py`
      — clean; decompose if the C90 complexity cap demands it (commit gate M-R3.4)

### Task 8: Root `register_hooks` — four subscriptions (TDD)

Extend `goga_tool_pybuggy/statuses.py`: `register_hooks` gains the two onboarding subscriptions next to the
two statuses subscriptions, importing the handlers at module top via
`from .commands.init import amend_pybuggy_config, declare_pybuggy_session` (top-level relative import; the
root facade already transitively imports `goga.onboarding` at package import through `cli.py` →
`commands.init`, so no new import-time coupling). The statuses tables stay untouched.

```
hooks.subscribe("statuses", "register_statuses", "automate", register_automate_statuses)
hooks.subscribe("statuses", "register_statuses", "fix", register_fix_statuses)
hooks.subscribe("onboarding", "declare_session", "declare", declare_pybuggy_session)
hooks.subscribe("onboarding", "amend_config", "amend", amend_pybuggy_config)
```

The subscription table is the platform contract — a wrong address/name silently disables native
`goga init -t pybuggy` participation or the statuses. The handlers are NOT re-exported on the package facade
(reachable only through the subscriptions).

**Usages relevant to this task:**
- `goga-hooks`: the facade callback contract and the failure behavior of registrations.
- `goga-statuses`: the registration surface of the two status hooks (file currently missing on disk —
  pre-existing accepted residue; the existing subscriptions are the working reference).
- `goga-onboarding-hooks`: the two onboarding actions, subscribe signature `subscribe(domain, action, name,
  hook)`, by-name argument delivery.
- `conventions`: direct handler call testing (M-R2.6); root-package module test at `tests/test_statuses.py`
  (M-R2.2).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Contract tests** (in `tests/test_statuses.py`, new file, expected to fail): `register_hooks` exposed
      on the root facade (`goga_tool_pybuggy.register_hooks`); signature `register_hooks(hooks: object) -> None`
- [ ] **REPL cycle** (M-R4.1/M-R4.5): in the venv REPL — import `goga_tool_pybuggy`, call `register_hooks`
      with a recorder `hooks` object, inspect the four captured calls; verify the onboarding callables are
      the init-cell session objects by identity (`from goga_tool_pybuggy.commands.init import ...`);
      migrate, re-verify via fresh import
- [ ] **Code**: extend `register_hooks` with the two onboarding subscriptions and the top-level relative
      import; module docstring updated (four subscriptions)
- [ ] **Interface verification**: `.venv/bin/python -m pytest tests/test_statuses.py -v` — contract tests pass
- [ ] **Logic tests** (design scenario):
      - `test_register_hooks_subscribes_four_hooks` — recorder `hooks` capturing `subscribe` calls (root
        facade import); Assertions: calls ==
        `[("statuses","register_statuses","automate", register_automate_statuses),
        ("statuses","register_statuses","fix", register_fix_statuses),
        ("onboarding","declare_session","declare", declare_pybuggy_session),
        ("onboarding","amend_config","amend", amend_pybuggy_config)]` in order; the onboarding callables are
        the init-cell session objects (`from goga_tool_pybuggy.commands.init import ...` identity)
- [ ] **Debugging**: `.venv/bin/python -m pytest tests/ -x` — fix implementation code until all tests pass
      (do NOT fix test code)
- [ ] **Contract re-verification**: exactly four subscriptions, nothing beyond; statuses tables untouched;
      handlers not on the package facade
- [ ] **Lint**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` +
      `.venv/bin/ruff format --check goga_tool_pybuggy/statuses.py tests/test_statuses.py` — clean
      (commit gate M-R3.4)

### Task 9: Integration tests — session smoke end-to-end + CLI composition (integration tests)

Rewrite `tests/commands/init/test_init_integration.py`: the acceptance-level proof of the participation
mechanism in-process (real engine session, real registry import of `register_hooks`, real hooks, stubbed
prompts) plus the CLI composition coverage (`init_cmd` ↔ `run_init` ↔ session/bootstrap ↔ `cli`
registration). This task writes tests only — the implementation is Tasks 2–8; failures found here are
fixed in the implementation, never in the contract.

Interaction flow under test (from the design — the native-session path):

```
Native session (no pybuggy CLI): goga init -t pybuggy
   goga → registry.build_once() → imports goga_tool_pybuggy.register_hooks (root facade, statuses.py)
   → hooks.subscribe × 4 (statuses/register_statuses ×2, onboarding/declare_session "declare",
     onboarding/amend_config "amend")
   → moment 1: declare_pybuggy_session(context=ToolDeclaration) — not invited? return; else
     context.declare(item) for item in pybuggy_questions()
   → engine surveys core tree + pybuggy block (click prompts, engine-owned)
   → moment 2: amend_pybuggy_config(context=ToolContribution) — not invited? return; else
     context.answer("build.review.skip", True); context.write_config("config.yml", build_config_data(answers))
   → engine: SessionAnswers.amend(...) commits, FileGenerator.generate(...)
     → .goga/config.yml, Dockerfile, .goga/tools/pybuggy/config.yml
   → exit code (tool failures soft: warning + drop, session continues)
```

**Usages relevant to this task:**
- `goga-onboarding`: session flow and behavior guarantees (existing-config end, soft tool failures, artifact set).
- `goga-onboarding-hooks` / `goga-onboarding-questions` / `goga-onboarding-generator`: the moments, record
  shapes, and artifact set asserted end-to-end.
- `conventions`: integration tests for module/package interaction placed per the structure rules (M-R2.2);
  `tmp_path` + `monkeypatch.chdir`; prompts stubbed via a scripted map (external boundary — the TTY).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create `tests/commands/init/test_init_integration.py` (rewrite)
- [ ] **`test_session_smoke_end_to_end_with_prompt_stubs`** — Setup (the answer map is pinned EXACTLY,
      review q3/A): `tmp_path` cwd; monkeypatch `click.prompt`/`click.confirm` with a scripted map —
      confirms: `Download base convention` → n, `Add codemanifest usages?` → n,
      `Add codemanifest annotations?` → n, `Configure a build agent?` → n, **`Create Dockerfile?` → y**
      (default No — declining is the failed-init branch of q1/A), `Configure a pipeline agent?` → n,
      `Add tools?` → n, `Add usages records?` → n; inputs: `Language` → `python`, `Dockerfile path` →
      Enter (default `.goga/Dockerfile`), `Base image (FROM)` → Enter (the python-family default),
      **`Built image name` → an explicit value** (e.g. `pybuggy-smoke:latest` — `resolve_project_name()`
      returns None in `tmp_path` without a git origin, so this prompt carries NO default and Enter is
      impossible), then the pybuggy block: `base_url` → `https://{{ HOST }}/api`, scalars → Enter-skipped,
      first spec `shop|swagger|specs/shop.yaml` fields, `extra_specs` →
      `billing|openapi|specs/billing.yaml|https://git/b.git|specs/b.yaml|`; write minimal swagger files at
      `specs/shop.yaml` and `specs/billing.yaml`; the test stays OFFLINE (no answer activates the
      conventions download — `generate_goga_config` fetches from GitHub only when the codemanifest usages
      carry `conventions`). Input: `run_session()` (real engine; the registry imports the real
      `register_hooks` → real hooks). Assertions: return 0; `.goga/config.yml` exists with
      `language: python`; `.goga/tools/pybuggy/config.yml` equals the expected plain payload (`specs` with
      `shop` + `billing`, `base_url`, `git` block on billing only); Dockerfile exists at the answered path;
      stdout report names the tool config with `(tool: pybuggy)` attribution
- [ ] **CLI composition coverage** — `init_cmd` (Click wrapper) → `run_init` → `run_session` +
      `run_bootstrap` chain on a fresh project with all seams stubbed (registration, delegation order,
      exit propagation), and the top-level `init` registration in `goga_tool_pybuggy.cli` (already asserted
      by `tests/test_cli.py` — do not duplicate; assert the composition only)
- [ ] Run validation: `.venv/bin/python -m pytest tests/commands/init/test_init_integration.py -v` then
      `.venv/bin/python -m pytest tests/ -x` — all green
- [ ] Lint: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` +
      `.venv/bin/ruff format --check tests/commands/init/test_init_integration.py` — clean (commit gate M-R3.4)

### Task 10: Documentation & migration notes (documentation)

Bring the consumer-facing text off the 1.x model. `MIGRATION.md` is new; the listed docs are updated in
place. Content requirements come from the design's Additional Instructions; the cell usage files
(`.usages/init.md`, `.usages/config-build.md`, `assembly.md`) are ALREADY current — read them as the
authoritative behavior description, do not edit them.

**Usages relevant to this task:**
- `conventions`: dependency/config documentation stays consistent with `pyproject.toml` (M-R1.1).
- Cell usage files (read-only reference): `goga_tool_pybuggy/commands/init/.usages/init.md` (three modes,
  session semantics, bootstrap table, decline branch), `.usages/config-build.md` (contribution semantics),
  `goga_tool_pybuggy/.usages/assembly.md` (four-hook table).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create `MIGRATION.md` at the repo root covering: `build.review_executor.skip` → `build.review.skip`
      (consumers re-run `pybuggy init --upgrade`-independent enforcement — the bootstrap sets the new key on
      the next run; the old key is not migrated automatically); the new native `goga init -t pybuggy` path
      (same session, same hooks, no bootstrap — the flag and the pybuggy-owned files land only through the
      pybuggy CLI); the Dockerfile-decline behavior change (1.x always created the Dockerfile by
      construction; 2.0 surfaces the core confirm "Create Dockerfile?" defaulting to No — declining ends
      the command with a non-zero exit after the session artifacts are written; recovery: create the
      Dockerfile at the config `dockerfile` path or remove `.goga` and re-run)
- [ ] Update `docs/getting-started.md`, `docs/cli/init.md`, `README.md` off the 1.x flow (engine-owned
      session, participation hooks, bootstrap table, three modes, dynamic install line)
- [ ] Update `docs/plugin/index.md` and `docs/pipelines/*.md` where they describe the 1.x onboarding model
- [ ] Verify consistency: `grep -rn "review_executor" README.md docs/ MIGRATION.md` — hits only inside
      MIGRATION.md's migration note; `grep -rn "1\.0\.x" README.md docs/` — no hardcoded install-line pins
- [ ] Run validation: `.venv/bin/python -m pytest tests/ -x` — still green (docs must not break collection)
- [ ] Lint: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — clean (commit gate M-R3.4)

### Task 11: Final validation gate — full suite, lint/format, goga lint, e2e evidence (acceptance)

The implementation gate from the design's Additional Instructions. Everything before this task must be
green; this task verifies the whole and collects the accepted e2e evidence.

**Usages relevant to this task:**
- `conventions`: the validation command table (the authoritative gate list).
- `goga-onboarding`: the session semantics the smoke test certifies.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Run the full test suite: `.venv/bin/python -m pytest tests/ -x` — green on goga 2.0.1
- [ ] Lint the whole tree: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — clean
- [ ] Format check every file touched by this plan: `.venv/bin/ruff format --check goga_tool_pybuggy/commands/init/
      goga_tool_pybuggy/statuses.py tests/commands/init/ tests/test_statuses.py` — clean (report any
      pre-existing deviation in untouched files instead of reformatting them, M-R3.3)
- [ ] Facade check (fresh interpreter): import all 17 names from `goga_tool_pybuggy.commands.init`;
      `from goga_tool_pybuggy import register_hooks`
- [ ] Contract drift check: `goga lint` — no new findings against the baseline (17 cells, 1 pre-existing
      `goga-statuses` missing-file error — accepted residue)
- [ ] E2E evidence (manual consumer quickstart, requires a consumer-grade environment — record the run or
      the environment gap in the task notes): `goga install pybuggy` → `goga tool pybuggy init` →
      `goga pipeline pybuggy:api.automate`; the in-process session smoke test
      (`test_session_smoke_end_to_end_with_prompt_stubs`) is the accepted offline equivalence evidence
- [ ] Final commit gate (M-R3.4): lint + format + full suite green before the closing local commit

---

## Validation Commands

All commands run in the Task 1 virtualenv (M-R1.2) unless noted.

- `pytest tests/ -x`: Run all tests (the convention's run-all command; green from Task 2 onward)
- `pytest tests/commands/init/test_<module>.py -v`: Run a specific module's tests (test_init / test_session / test_bootstrap / test_init_integration / test_statuses)
- `ruff check goga_tool_pybuggy/ tests/`: Lint check — zero findings on task-touched paths
- `ruff format --check <touched files>`: Format check on every file a task creates or modifies (never reformat unrelated files; report pre-existing deviations — M-R3.3)
- `python -c "from goga_tool_pybuggy.commands.init import amend_pybuggy_config, build_config_amendments, build_config_data, declare_pybuggy_session, ensure_review_skip, init_cmd, install_pybuggy, parse_specs, pybuggy_questions, register_annotations, register_usages, resolve_init_mode, run_bootstrap, run_init, run_session, write_pybuggy_conftest, write_test_convention"`: Verify that all 17 facade entities are importable
- `python -c "from goga_tool_pybuggy import register_hooks"`: Verify the root facade callback
- `goga lint`: CODEMANIFEST drift — no new findings vs the baseline (1 pre-existing `goga-statuses` error)

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location` (`init.py` ×4, `session.py` ×7, `bootstrap.py` ×6; root `register_hooks` in `statuses.py`)
- [ ] Every contract entity is accessible from the facade (17 names on `goga_tool_pybuggy.commands.init`; `register_hooks` on the root)
- [ ] Properties and methods match the declared API (signatures, typed returns, Python signature grammar)
- [ ] Descriptions are reflected in behavior (engine-owned session, soft contribution failures, plain-data payload, single `build.review.skip` amendment, mode gates, mandatory-Dockerfile invariant, idempotent writers)
- [ ] Contract dependencies are met (`SpecEntry`/`GitEntry`/`configuration` from the config cell; `PluginConfigKeys` from the plugin cell; engine imports per the verified facts)
- [ ] Re-exports are accessible from the facade
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task
- [ ] Integration tests exist where cross-entity scenarios require them (the session smoke test + CLI composition)
- [ ] All 40 planned test scenarios from the design's Test Stack Trace are implemented (21 positive, 11 negative, 8 edge)
- [ ] The deleted 1.x entities and helpers are gone; no dead code remains in the cell
- [ ] `pyproject.toml` test extra pins `goga>=2.0.1,<2.1`; the virtualenv exists and carries the installation
- [ ] MIGRATION.md exists with the three required items; docs are off the 1.x model
- [ ] Mandatory Rules R1–R4 were followed in every task (coding style, test rules, lint/format gates at every stage and before every local commit, REPL cycle)
- [ ] No package boundary was expanded; no new cells created
- [ ] `CODEMANIFEST` files were not modified (contract is read-only; cell `.usages/` files untouched)
- [ ] All validation commands pass (`pytest tests/ -x`, `ruff check`, `ruff format --check` on touched files, facade checks, `goga lint` no new findings)
- [ ] Every Usages entry is mentioned in at least one task (all 8 init-cell usages + root `goga-hooks`/`goga-statuses`/`goga-onboarding-hooks` + imported `configuration`)
