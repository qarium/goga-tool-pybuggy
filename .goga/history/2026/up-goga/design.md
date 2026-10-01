# Design Document: `up-goga`

Topic: pybuggy onboarding migration to goga 2.0 (canonical session-participation model).
Contract input: the CODEMANIFEST changes of `goga_tool_pybuggy/commands/init` (rewritten) and `goga_tool_pybuggy` (root, revised) materialized by the apply-architecture stage from `.goga/history/2026/up-goga/arch.md`.

Environment facts verified during tracing (goga 2.0.1 host, `/opt/goga`):

- `goga.onboarding` exposes `InitLogic`, `Questionnaire`, `FileGenerator`, `ToolParticipation`, `Question`, `QuestionGroup`, `SessionAnswers`; the 1.x entities (`GogaConfigAnswers`, `InitAnswers`) are gone — the current `init.py` is dead code against 2.0.1 and fails at import.
- Engine ask semantics (`Questionnaire.ask_question`): kind `input` with `default=None` → required (re-asked until non-empty); `default=""` → Enter yields `""` (skippable); kind `choice` → `click.prompt(type=click.Choice(choices))`, always answered, default ignored; kind `confirm` → bool; kind `pairs` → mapping.
- Declaration surface (`ToolDeclaration`): `.invited: bool`, `.declare(item)` accepting `Question` or a one-level `QuestionGroup` (nested groups rejected with a warning), `.skip(path)`.
- Contribution surface (`ToolContribution`): `.invited: bool`, `.answers: dict` (core sections + own block under local names), `.answer(id, value)` with `value: str | bool | dict` at a dot-path, `.write_config(file, data)`.
- `SessionAnswers.amend(id, value)` merges mappings recursively / replaces scalars at a dot-path; `view_for(tool)` returns core + own local names; the answer space is nested mappings (no dotted keys stored).
- The generator writes buffered tool configs **verbatim** via `yaml.dump(data)` (`_write_tool_configs`) — a payload containing pydantic objects raises `RepresenterError` and the file is silently dropped with a warning. `build_config_data` must therefore emit plain mappings.
- `_build_config_document` maps only known core fields: the `build` block carries only `agent`/`env` (a `build.review.skip` amendment never reaches the generated config — the bootstrap's `ensure_review_skip` is the enforcement point), and the config `dockerfile` field is emitted from `docker_image.dockerfile` + `docker_image.base_image`. The generator likewise writes the Dockerfile only when BOTH answers exist (`generate`: `if dockerfile is not None and base_image is not None`), and the core confirm "Create Dockerfile?" defaults to **No** (`_survey_docker_image`) — a user declining it leaves no Dockerfile, no config `dockerfile` field, and neither docker_image answer recorded (the decline branch; see the `run_bootstrap` edge cases and the declined-Dockerfile test variant).
- The hooks platform delivers hook arguments **by name** (`context`, optional `self`); subscribe signature `hooks.subscribe(domain, action, name, hook)`.
- `goga install` version grammar: minor x-range `N.M.x` → pip `~=N.M.0`; the package version is setuptools-scm derived (`pyproject.toml`, `dynamic = ["version"]`, distribution `goga-tool-pybuggy`).

## Contract Changes

### Changed CODEMANIFEST Files

- `goga_tool_pybuggy/commands/init/CODEMANIFEST`: rewritten. Header — `Imports` added (`SpecEntry`, `GitEntry` + usage `configuration` from `goga_tool_pybuggy/config`; `PluginConfigKeys` from `goga_tool_pybuggy/plugin`); `Usages` now eight practices (added `goga-onboarding-hooks`, `goga-onboarding-questions`, `goga-onboarding-generator`); global `Annotations` rewritten for the engine-owned session + pybuggy-owned bootstrap split. Body — 17 routines across three files (`init.py`, `session.py`, `bootstrap.py`). Footer — `CreatedAt: 01/10/26`.
- `goga_tool_pybuggy/CODEMANIFEST`: revised. `Imports` of the init cell extended with `declare_pybuggy_session`, `amend_pybuggy_config`; `Usages` added `goga-onboarding-hooks`; global `Annotations` extended (one practice line, one onboarding-participation paragraph); `register_hooks` rewritten for four subscriptions. Footer untouched.

### New Entities

- `run_bootstrap(template_mode: bool) -> exit_code:int` — `init.py` — pybuggy-owned bootstrap orchestrator after the session (9 steps, mode-dependent gates).
- `run_session() -> exit_code:int` — `session.py` — runs one goga onboarding session in-process with pybuggy invited; the contract test seam.
- `declare_pybuggy_session(context: object)` — `session.py` — moment one of the participation contract: declares the pybuggy question block.
- `amend_pybuggy_config(context: object)` — `session.py` — moment two: buffers the config amendments and the tool config file.
- `pybuggy_questions() -> items:list[Question]` — `session.py` — builds the declarative question block (records + one one-level group).
- `build_config_data(answers: dict[str, object]) -> data:dict[str, object]` — `session.py` — pure mapping of the answer view into the tool config payload (plain serializable data).
- `build_config_amendments() -> amendments:dict[str, object]` — `session.py` — pure mapping into the buffered amendments of the consumer config (the single `build.review.skip` declared-intent amendment; review decision q2/A).
- `parse_specs(spec_answers: dict[str, object], extra_specs: str | None) -> specs:dict[str, SpecEntry]` — `session.py` — pure, lenient assembly of the specs mapping.

### Changed Entities

- `init_cmd` — annotation rewritten (three-mode surface wording); behavior unchanged (Click wrapper, `ctx.exit`).
- `run_init` — rewired: drives `run_session` then `run_bootstrap` instead of `run_onboarding`; exit-code contract refined (session code propagated as-is; bootstrap failure → 1).
- `resolve_init_mode` — contract text unchanged; implementation carried over verbatim.
- `ensure_review_executor_skip` → **`ensure_review_skip`** — renamed; enforced key path `build.review_executor.skip` → `build.review.skip`; behavior otherwise identical (round-trip, idempotent, returns `changed`).
- `install_pybuggy` — install line becomes dynamic, derived from the installed package version (no hardcoded `1.0.x`).
- `register_usages` / `register_annotations` — return labels typed (`added_keys`, `changed_keys`); behavior unchanged; relocated to `bootstrap.py`.
- `write_test_convention` / `write_pybuggy_conftest` — contract text tightened (pure-writer framing); relocated to `bootstrap.py`.
- `register_hooks` (root) — two onboarding subscriptions added next to the two statuses subscriptions.

### Deleted Entities

- `run_onboarding` — replaced by `run_bootstrap` (the session owns the goga config / tool config gates it implemented).
- `run_goga_init` — the 1.x per-field questionnaire flow; replaced by the engine session (`run_session`).
- `build_pybuggy_config` — imperative in-cell survey; replaced by the declarative block + `amend_pybuggy_config`.
- `write_pybuggy_config` — the cell no longer writes the tool config; the engine serializes the buffered payload (`build_config_data`).
- Old facade exports and private helpers disappear with them (see Algorithm Design → Module layout).

### Usages and Annotations Changes

- init cell: `goga-onboarding-hooks` / `goga-onboarding-questions` / `goga-onboarding-generator` connected (file form) and referenced from global annotations and from `declare_pybuggy_session` / `amend_pybuggy_config` / `pybuggy_questions` / `build_config_data`; `ruamel-yaml` usage narrowed to round-trip edits of the consumer `.goga/config.yml` (the commented-record emission practice is retired with `write_pybuggy_config`).
- root cell: `goga-onboarding-hooks` connected and referenced in global annotations and `register_hooks`.

## Applied Fixes

### Fixed CODEMANIFEST Defects

- None. The Phase 3 audit (four consistency dimensions, DSL syntax, cookbook principles) found no defects in the changed CODEMANIFESTs; `goga lint` reports only the pre-existing `goga-statuses` missing-file residue (accepted plan residue, out of scope). No edits to CODEMANIFEST were needed in this stage.

### Confirmed `.usages/` fix (user decision, question q1 — option A)

- `goga_tool_pybuggy/commands/init/.usages/init.md` — the bootstrap table row for the install line now reads "the pybuggy install RUN line in the project Dockerfile (the config `dockerfile` field, default `.goga/Dockerfile`)" instead of the categorical `.goga/Dockerfile`, matching the confirmed path-resolution design of `run_bootstrap` (below). Lint re-run: unchanged (1 pre-existing error).

### Review-stage fixes (design-review, user decisions q1/A–q4/A)

- **q1/A (High)** — the Dockerfile-decline branch is now an explicit design decision: the core confirm "Create Dockerfile?" defaults to No; a declined session fails at `run_bootstrap` step 8 (ERROR + 1) with steps 2–7 applied, recovery documented (engine fact about the both-answers requirement added; `run_bootstrap` edge cases; the declined-Dockerfile variant of `test_run_bootstrap_missing_dockerfile_fails_with_error`; MIGRATION.md item extended; `.usages/init.md` decline paragraph).
- **q2/A (Medium)** — `build_config_amendments` narrowed to the single `build.review.skip` declared-intent amendment (signature drops the unused `answers`; CODEMANIFEST + traces + algorithm + tests updated); the dead `docker_image.dockerfile` backstop removed; `.usages/init.md` / `.usages/config-build.md` corrected — the flag is enforced by the bootstrap (`ensure_review_skip`), the native `goga init -t pybuggy` session sets no flag. Lint after the CODEMANIFEST edit: unchanged (1 pre-existing error).
- **q3/A (Test Gap)** — the session smoke-test Setup now pins the exact scripted answer map (confirm answers incl. `Create Dockerfile?` → y, an explicit built-image value — no default exists in `tmp_path` without a git origin — and the offline guarantee: no answer activates the conventions download).
- **q4/A (Low)** — doc precision: `click` removed from the `bootstrap.py` dependency list (gates live in `init.py::run_bootstrap`); the `PackageNotFoundError` tier statement corrected (not in the catch tuple — propagates uncaught, unreachable in practice); `PYBUGGY_ANNOTATIONS` added to the `init.py` module layout.

## Entity Interaction and Data Flow

### Interaction Diagram

```
                                   pybuggy CLI (consumer terminal)
                                         |
                    pybuggy init [<tpl>] [--ref R] | --upgrade
                                         v
        +------------------------------ init_cmd (init.py, Click wrapper) ------+
        |  binds <tpl>/--ref/--upgrade, ctx.exit(code)                          |
        +-------------------------------|---------------------------------------+
                                        v
        +------------------------------ run_init (init.py) ----------------------+
        |  1 resolve_init_mode ------- (init.py, pure)                           |
        |  2 bare guard: .goga dir?                                               |
        |  3 upgrade --> Scaffold().upgrade(ref)          [goga.scaffold]        |
        |  4 template --> Scaffold().generate(tpl, ref)  [goga.scaffold]         |
        |  5 run_session() ------> session.py                                     |
        |  6 run_bootstrap(mode) -> init.py (steps via bootstrap.py writers)     |
        +----------------------------------------------------------------------+

  run_session:  InitLogic(Questionnaire, FileGenerator,                [goga.onboarding]
                ToolParticipation(invited=["pybuggy"])).run()
                     |  engine: existing .goga/config.yml? -> end session (0)
                     |  engine: registry.build_once() -> imports goga_tool_pybuggy.register_hooks
                     |            (root facade, statuses.py)
                     |                 subscribes: statuses/register_statuses x2
                     |                            onboarding/declare_session "declare"
                     |                            onboarding/amend_config   "amend"
                     |  moment 1: declare_pybuggy_session(context=ToolDeclaration)
                     |                 |-- not invited? return
                     |                 +-- context.declare(item) for item in pybuggy_questions()
                     |  engine surveys core tree + pybuggy block (click prompts, engine-owned)
                     |  moment 2: amend_pybuggy_config(context=ToolContribution)
                     |                 |-- not invited? return
                     |                 |-- context.answer(id, v) for build_config_amendments()
                     |                 +-- context.write_config("config.yml", build_config_data(answers))
                     |  engine: SessionAnswers.amend(...) commits, FileGenerator.generate(...)
                     |          -> .goga/config.yml, Dockerfile, .goga/tools/pybuggy/config.yml
                     v  exit code (tool failures soft: warning + drop, session continues)

  run_bootstrap (cwd):                                                    reuse of:
     copy packaged api usages -> .goga/usages/cooks/pybuggy/*.md         _walk/_discover_usages
     conventions slot skip-if-exists -> write_test_convention             bootstrap.py
     ensure_review_skip(.goga/config.yml)         build.review.skip       bootstrap.py (ruamel)
     install_pybuggy(<dockerfile from config>)    RUN goga install ...    bootstrap.py
     register_usages / register_annotations       codemanifest.*          bootstrap.py (ruamel)
     root conftest gate -> write_pybuggy_conftest                         bootstrap.py
     verify Dockerfile exists -> else ERROR + non-zero

  Native session (no pybuggy CLI): goga init -t pybuggy
     goga -> same registry -> same register_hooks -> same two onboarding hooks
```

### Data Flows

1. **CLI flow** — `init_cmd(ctx, tpl, ref, upgrade)` → `run_init(tpl, ref, upgrade)` → mode string → guard/engine codes → `run_session() -> int` → `run_bootstrap(template_mode: bool) -> int` → `ctx.exit(code)`.
2. **Declaration flow** — `pybuggy_questions() -> list[Question | QuestionGroup]` (fresh immutable records) → `declare_pybuggy_session` → `ToolDeclaration.questions` buffer → engine `assemble_session_plan` qualifies ids as `pybuggy.<local>` → survey asks them.
3. **Answer flow** — survey records into `SessionAnswers` at plan paths → `ToolContribution.answers = view_for("pybuggy")` (core sections + own block under local names) → `build_config_amendments()` / `build_config_data(answers)` → buffered via `context.answer` / `context.write_config` → engine commits amendments into the answer space (`SessionAnswers.amend`; the config mapper drops `build.review.skip` — declared intent, enforcement lives in the bootstrap) and serializes files.
4. **Artifact flow** — engine `FileGenerator.generate` writes `.goga/config.yml` (mapped core fields; `build.review.skip` dropped by the mapper — enforcement delegated to the bootstrap), the Dockerfile at `docker_image.dockerfile`, and `.goga/tools/pybuggy/config.yml` from the buffered plain payload; `CreatedFile` report echoed with tool attribution. Then `run_bootstrap` delivers the pybuggy-owned files.
5. **Platform flow** — goga (or the in-process session registry) imports `goga_tool_pybuggy.register_hooks` once per run (never cached), calls `hooks.subscribe(...)` × 4; the two statuses hooks keep their existing registration tables.

### Entity Dependencies

- `init.py` → `session.py` (`run_session`), `bootstrap.py` (six writers), `goga.scaffold.Scaffold`, `click`.
- `session.py` → `goga.onboarding` (`InitLogic`, `Questionnaire`, `FileGenerator`, `ToolParticipation`, `Question`, `QuestionGroup`), `...config` cell (`SpecEntry`, `GitEntry` via `parse_specs`), `...plugin` cell (`PluginConfigKeys`).
- `bootstrap.py` → `ruamel.yaml`, `importlib.metadata`, `importlib.resources`, `...config` cell re-export path for typed entries not needed (writers take plain values). No `click` import — every prompt/confirm gate lives in `run_bootstrap` (`init.py`).
- `statuses.py` (root) → `from .commands.init import amend_pybuggy_config, declare_pybuggy_session` (top-level relative import; the root facade already transitively imports `goga.onboarding` at package import through `cli.py` → `commands.init`, so no new import-time coupling is introduced).
- Cell facade `commands/init/__init__.py` re-exports all 17 routines; the root facade stays unchanged (`register_hooks` already exported).

## Code Stack Trace

All traces verified against the installed engine source (goga 2.0.1) and the current pybuggy implementation. Checkpoint verdicts: **passed** unless stated.

### Trace: `init_cmd`

1. **Input**: click invocation `pybuggy init [<tpl>] [--ref R] [--upgrade]`.
2. Decorators bind the surface: `@click.command("init")`, `@click.argument("tpl", required=False)`, `@click.option("--upgrade", is_flag=True, default=False)`, `@click.option("--ref", default=None)`, `@click.pass_context` → checkpoint: surface matches the contract (optional positional, two options) — passed (existing code reused).
3. Body delegates: `ctx.exit(run_init(tpl, ref, upgrade))` → checkpoint: exit code propagated via `ctx.exit` — passed.
4. **Output**: process exit code of `run_init`.

### Trace: `run_init`

1. **Input**: `(tpl: str | None, ref: str | None, upgrade: bool)`.
2. `resolve_init_mode(tpl, ref, upgrade)` → invalid combination raises `click.ClickException` (click prints, exit 1) → passed.
3. Bare guard: `mode == "bare" and Path(".goga").is_dir()` → echo `Project already initialized` to stderr, return 1 → checkpoint: directory-existence only (`.goga` regular file passes), zero prompts/writes on refusal — passed.
4. Upgrade: `return Scaffold().upgrade(ref)` → checkpoint: engine owns errors; code propagated as-is; no session, no bootstrap — passed.
5. Template: `code = Scaffold().generate(tpl, ref)`; non-zero → `return code` (no onboarding side effect) — passed.
6. `code = run_session()`; non-zero → `return code` — checkpoint: session exit code propagated unchanged, bootstrap skipped — passed.
7. `return run_bootstrap(template_mode=(mode == "template"))` → **Output**: 0 / 1 / propagated engine or session code.

### Trace: `resolve_init_mode`

Pure flag algebra (existing code carried over): reject `tpl and upgrade`; reject `ref and not tpl and not upgrade`; return `upgrade` / `template` / `bare`. Checkpoint: mirrors `goga init` rules, no I/O — passed.

### Trace: `run_session`

1. **Input**: none; operates on the process CWD.
2. `logic = InitLogic(questionnaire=Questionnaire(), generator=FileGenerator(), participation=ToolParticipation(invited=["pybuggy"]))` → checkpoint: constructor signature verified on the engine (`InitLogic(questionnaire, generator, participation)`); invited identity `pybuggy` is the platform-assigned tool identity of `goga_tool_pybuggy` — passed.
3. `return logic.run()` → engine steps: existing `.goga/config.yml` → immediate 0; registry build (imports `register_hooks` of every installed tool package — including pybuggy itself); declaration moment; plan + survey; amendment moment; generation; report echo; user abort → quiet 1; session error → one clean message + 1 → checkpoint: contract requirements (engine-owned questions; existing-config end; soft tool failures; artifact set) are exactly the engine's documented and verified behavior — passed.
4. **Output**: engine session exit code, propagated unchanged.

### Trace: `declare_pybuggy_session`

1. **Input**: `context` = `ToolDeclaration` wrapped in the platform's read-only proxy (delivered by name).
2. `if not context.invited: return` → checkpoint: `.invited` member verified on `ToolDeclaration`; the no-invitation branch calls nothing — passed.
3. `for item in pybuggy_questions(): context.declare(item)` → `declare` buffers `Question` records and one-level groups; engine qualifies ids with `pybuggy.` — checkpoint: local names unique among siblings (`base_url`, six scalars, `first_spec`, `extra_specs`; group children `name|type|location|git_url|git_location|git_ref`) — passed.
4. **Output**: none (buffer side effect on the declaration surface).

### Trace: `amend_pybuggy_config`

1. **Input**: `context` = `ToolContribution` proxy; `context.answers` = `view_for("pybuggy")` (core + own local names, deep copy).
2. `if not context.invited: return` — passed.
3. `answers = context.answers`; `for id, value in build_config_amendments().items(): context.answer(id, value)` → checkpoint: `answer(id: str, value: str|bool|dict)` accepts `True` (bool); the dot-path `build.review.skip` matches `SessionAnswers.amend` resolution — passed.
4. `context.write_config("config.yml", build_config_data(answers))` → checkpoint: engine writes `.goga/tools/pybuggy/config.yml` (tool dir from the platform identity); payload is plain serializable data (see `build_config_data`) so the verbatim `yaml.dump` succeeds — passed.
5. **Output**: buffered contribution; any exception propagates to the mediator, which drops the whole contribution with a warning naming pybuggy (soft) — matches the contract.

### Trace: `pybuggy_questions`

1. **Input**: none (pure).
2. Build ordered records (survey order = declaration order):
   - `Question(id="base_url", kind="input", prompt="Base URL (Jinja2 template, required)")` — no default → engine re-asks until non-empty → required ✓.
   - For every `PluginConfigKeys` member except `BASE_URL`, `HEADERS`, `LOADER`: `Question(id=member.value, kind="input", default="", prompt=_SCALAR_PROMPTS[member])` — Enter yields `""` → optional ✓ (prompt texts carried over from the existing `_SCALAR_PROMPTS`).
   - `QuestionGroup(id="first_spec", prompt="The first spec", children=[name(input, no default), type(choice ["swagger","openapi"]), location(input, no default), git_url(input, default=""), git_location(input, default=""), git_ref(input, default="")])` → checkpoint: one nesting level with simple children only — engine rule satisfied; `type` always answered (choice re-asks) ✓; empty `git_url` means no git source ✓.
   - `Question(id="extra_specs", kind="input", default="", prompt=...)` describing the compact form `name|type|location|git_url|git_location|git_ref` — passed.
3. **Output**: `items` — the records and the group in survey order. Note: `items` holds `Question` records plus one `QuestionGroup`; the signature label `list[Question]` reads "question records" per `goga-onboarding-questions` (both kinds are question records; no backtick annotation references `Question`, so the DSL reference rules are unaffected).

### Trace: `build_config_data`

1. **Input**: `answers` = the tool answer view (block answers under local names: `base_url`, scalar keys, `first_spec` mapping, `extra_specs` string).
2. `specs = parse_specs(answers.get("first_spec") or {}, answers.get("extra_specs") or None)` → typed entries.
3. Scalar walk in `PluginConfigKeys` declaration order: take `answers[member.value]`; drop empty/absent (`""`/`None`); coerce numeric members (`timeout`→float, `retries`→int, `assert_timeout`→int, `assert_delay`→float — carried over from `_NUMERIC_MEMBERS`); other scalars stay strings → checkpoint: `base_url` is required and therefore always present; a non-numeric numeric answer raises `ValueError` (soft-drop at the engine — documented contract behavior) — passed.
4. `data = {**scalars, "specs": {name: entry.model_dump(exclude_none=True) for name, entry in specs.items()}}` → checkpoint: **plain serializable data** — `SpecEntry`/`GitEntry` (pydantic) are dumped to mappings (`{"type","location"[,"git":{"url","location"[,"ref"]}]}`); `exclude_none` drops `git: None` (no git block) and `ref: None` — the verbatim `yaml.dump` of the engine succeeds; key order = plugin key order with `specs` last (matches the old writer's active-key order) — passed.
5. **Output**: the payload of `.goga/tools/pybuggy/config.yml`.

### Trace: `build_config_amendments`

1. **Input**: none (pure; the single amendment is unconditional).
2. `amendments = {"build.review.skip": True}` → checkpoint: the dot-path matches `SessionAnswers.amend` resolution; the value is within `str | bool` — passed. The amendment is the tool's **declared intent** in the answer space: `_build_config_document` emits only `agent`/`env` for the build block, so the flag reaches the consumer config exclusively through the bootstrap's `ensure_review_skip` (review decision q2/A — the former `docker_image.dockerfile` backstop amendment is removed: the generator requires both the dockerfile and the base_image answers, so a dockerfile-only amendment never made it write the Dockerfile or emit the config field; see the Dockerfile-decline branch).
3. **Output**: the single-entry dot-path → value mapping.

### Trace: `parse_specs`

1. **Input**: `spec_answers` = the `first_spec` group answer (local child names), `extra_specs` = the optional compact input (`None`/`""` when unanswered).
2. First spec strict: `name = spec_answers["name"].strip()` (non-empty), `type` ∈ {`swagger`, `openapi`}, `location` non-empty — else `ValueError`; `git_url` and `git_location` both non-empty → `GitEntry(url, location, ref)` with `ref = git_ref or None`; `SpecEntry(type=..., location=..., git=...)` → checkpoint: pydantic `Literal` type validated at construction; absent git url → `git=None` (no git block) — passed.
3. Extras lenient: for each non-empty line of `extra_specs.splitlines()`: `parts = [p.strip() for p in line.split("|")]`; malformed when `len(parts) < 3` or any of the first three empty or `parts[1]` not in {`swagger`, `openapi`} → `logger.warning` + skip; well-formed → build its `SpecEntry` (git fields from `parts[3:6]`, padded with `""`, same both-present attach rule); a name already in the mapping → keep the first, warn → checkpoint: a malformed line never fails the contribution; pydantic `ValidationError` is unreachable (type pre-validated) — passed.
4. **Output**: `specs` mapping — always holds at least the first spec (the group's required children make it structurally unavoidable).

### Trace: `run_bootstrap`

1. **Input**: `template_mode: bool`; operates on the process CWD.
2. `cwd = Path.cwd()`; discovery `discovered = _discover_usages(importlib.resources.files("goga_tool_pybuggy.api"))` — walks the installed api cell incl. subcells (e.g. `asserts`); internal development cells are never under `api`, so the constraint holds by construction → passed.
3. Usages copy → for each `(stem, text)`: target `.goga/usages/cooks/pybuggy/{stem}.md`; target exists and `template_mode` → INFO + skip; otherwise `mkdir(parents=True, exist_ok=True)` + `write_text` (bare mode overwrites) → passed.
4. Conventions slot → `.goga/usages/conventions.md` exists → INFO, untouched; absent → `write_test_convention(slot)` — skip-if-exists in BOTH modes → passed.
5. `ensure_review_skip(cwd/".goga"/"config.yml")` — always (also when the session ended immediately on an existing config) → passed.
6. Dockerfile resolution (user-confirmed design, q1/A): read the consumer config (`yaml.safe_load`) → `dockerfile` field → `dockerfile_path = Path(field)`; missing config/field → fallback `Path(".goga/Dockerfile")`; `install_pybuggy(dockerfile_path)` (no-op when absent) → checkpoint: honors a custom session answer (install line lands in the project's actual Dockerfile); default case matches the documented table row — passed.
7. `usage_keys = {"pybuggy-<stem>": ".goga/usages/cooks/pybuggy/<stem>.md", ..., "conventions": ".goga/usages/conventions.md"}` → `register_usages(config, usage_keys)`; `annotation_lines` from `_annotation_for(stem)` + `_CONVENTION_LINE` → `register_annotations(config, lines)`; log INFO added / WARNING skipped (existing `_log_registration` behavior) → passed.
8. Root conftest → `cwd/"conftest.py"` absent → `write_pybuggy_conftest`; exists → template: INFO skip; bare: `click.confirm(..., default=False)` — yes → overwrite, no → leave untouched (decline is not a failure) → passed.
9. `if not dockerfile_path.exists(): logger.error(...); return 1` → checkpoint: the mandatory-Dockerfile invariant at the resolved path; a `click.Abort` at the confirm propagates unswallowed (click handles it) — passed.
10. **Output**: 0. Step failures (steps 3–8 wrapped): `except (OSError, YAMLError, ValueError)` → `logger.error` + `return 1` (the old code raised `click.ClickException`; the contract now mandates a non-zero return — `run_init` maps it to its "failed bootstrap step" clause) → passed.

### Trace: `write_test_convention` (relocated, unchanged)

`importlib.resources.files("goga_tool_pybuggy") / "assets" / "conventions.md"` → `path.parent.mkdir(parents=True, exist_ok=True)` → `write_text` (always overwrites; no TTY, no existence check; never the cwd checkout, never the network) → checkpoint: deterministic, asset-pinned — passed.

### Trace: `ensure_review_skip`

Round-trip via ruamel (`preserve_quotes=True`): load existing config or start an empty `CommentedMap`; navigate/create `build` → `review` (each level `_ensure_map`, non-mapping → `ValueError`); `skip is True` → return `False` without writing; else set `skip = True`, dump, INFO, return `True` → checkpoint: key path `build.review.skip` is a documented project-config key (`project-configuration.md`: "the optional `build.review` key carries the review-pass settings (skip, ...)"); comments/order/quotes preserved; idempotent (no write when already true); `build.task_executor`/other siblings untouched — passed.

### Trace: `install_pybuggy`

1. `dockerfile_path` absent → return `None` (never creates the file).
2. `version = importlib.metadata.version("goga-tool-pybuggy")` (stdlib; the distribution name from `pyproject.toml`); `minor = ".".join(version.split(".")[:2])`; `line = f"RUN goga install pybuggy -v {minor}.x"` → checkpoint: derived from the installed package (no hardcoded pin); minor x-range is a valid `goga install` version form (`N.M.x` → `~=N.M.0`); dev/pre tails (e.g. `1.1.1.dev4+...`) still yield `1.1.x` — passed. `importlib.metadata.PackageNotFoundError` is an install corruption outside the routine's contract; it is NOT in the bootstrap catch tuple `(OSError, YAMLError, ValueError)` (it subclasses `ImportError`) — it propagates uncaught as a traceback, which is acceptable because it is unreachable in practice (the routine runs from inside the very package whose version it reads; review q4/A).
3. Line already in content → return `None`; else ensure trailing newline, append, write, INFO, return the line → checkpoint: only the install line is appended; idempotent — passed.

### Trace: `register_usages` (relocated, unchanged)

Round-trip: load or build `CommentedMap` with `codemanifest.usages`; skip present keys, insert missing, record; `mkdir` parent; dump; return added keys → checkpoint: existing keys never overwritten; creation from scratch verified against the ruamel practice — passed.

### Trace: `register_annotations` (relocated, unchanged)

Round-trip under `codemanifest.annotations` (literal block scalar): for each (key, line): find the first text line carrying the backtick reference — not found → append; identical → skip; differing → replace; foreign lines preserved; write back as `LiteralScalarString` → checkpoint: idempotent by reference; no reorder beyond the single replaced line — passed.

### Trace: `write_pybuggy_conftest` (relocated, unchanged)

Fixed `_CONFTEST_TEMPLATE` (`from dotenv import load_dotenv\n\nload_dotenv()\n\nfrom goga_tool_pybuggy import plugin\n\nplugin.install()\n`) → `mkdir` parent → `write_text` (always overwrites; deterministic; env loads before the plugin import, argumentless `load_dotenv` keeps `override=False`) → passed.

### Trace: `register_hooks` (root, `statuses.py`)

1. **Input**: `hooks` = the subscription surface delivered by the platform (imported from the package root; never cached).
2. Two statuses subscriptions (unchanged): `("statuses", "register_statuses", "automate", register_automate_statuses)`, `("statuses", "register_statuses", "fix", register_fix_statuses)`.
3. Two onboarding subscriptions (new): `("onboarding", "declare_session", "declare", declare_pybuggy_session)`, `("onboarding", "amend_config", "amend", amend_pybuggy_config)` — imported at module top via `from .commands.init import amend_pybuggy_config, declare_pybuggy_session` → checkpoint: addresses/names verified against `goga-onboarding-hooks` (`domain, action, name, hook`; hooks declare `context` by name and receive it by name); exactly four subscriptions, nothing beyond — passed.
4. **Output**: registry side effect; the handlers are not re-exported on the package facade (reachable only through the subscriptions).

## Algorithm Design

### Module layout (the contract's `location` values)

- `init.py` — `init_cmd`, `run_init`, `resolve_init_mode`, `run_bootstrap` + private helpers: `_BARE/_TEMPLATE/_UPGRADE`, `_walk`, `_discover_usages`, `_DOCKERFILE_DEFAULT = Path(".goga")/"Dockerfile"`, `PYBUGGY_ANNOTATIONS` (the per-stem annotation-line table read by `_annotation_for`, carried over), `_annotation_for`, `_CONVENTION_LINE`, `_resolve_dockerfile_path(config)`, `_log_registration`.
- `session.py` — `run_session`, `declare_pybuggy_session`, `amend_pybuggy_config`, `pybuggy_questions`, `build_config_data`, `build_config_amendments`, `parse_specs` + private: `_SCALAR_PROMPTS` (carried over), `_NUMERIC_MEMBERS` (carried over), `_GIT_FIELDS = 6`.
- `bootstrap.py` — `write_test_convention`, `ensure_review_skip`, `install_pybuggy`, `register_usages`, `register_annotations`, `write_pybuggy_conftest` + private: `_ensure_map` (carried over), `_CONFTEST_TEMPLATE`.
- Deleted from `init.py`: `run_onboarding`, `run_goga_init`, `build_pybuggy_config`, `write_pybuggy_config`, `ensure_review_executor_skip`, `_gate_existing`, `_write_root_conftest`, `_git_entry_to_map`, `_HEADERS_BLOCK`, `_LOADER_BLOCK`, `_COMPLEX_MEMBERS`, `_GIT_CHILD_INDENT`, `_INSTALL_LINE` (hardcoded), `_SCALAR_PROMPTS`/`_NUMERIC_MEMBERS` (move to `session.py`).
- `commands/init/__init__.py` — facade re-exports all 17 routines (alphabetical `__all__`, mirroring the old practice).
- `statuses.py` — extended `register_hooks` + the top-level relative import of the two onboarding handlers; statuses tables untouched.

### `run_bootstrap(template_mode)`

**Responsibility**: deliver the pybuggy files the session does not carry, with mode-dependent gates.

**Algorithm:**
```
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
```

**Errors:** write/parse failure in any step → ERROR log + exit 1; `click.Abort` at the confirm → propagates to click (quiet non-zero); missing Dockerfile at step 8 → ERROR + 1.

**Edge cases:** template mode never prompts (skip-with-INFO only); bare mode overwrites usages targets but asks for the conftest (decline → untouched, exit stays 0); existing conventions slot untouched in both modes; repeat run is a no-op (idempotent writers + skip-existing registrations). **Dockerfile-decline branch (user-confirmed decision q1/A of the review)**: the core confirm "Create Dockerfile?" defaults to No — a user declining it leaves no Dockerfile and no config `dockerfile` field (the generator requires both the dockerfile and the base_image answers; a `docker_image.dockerfile`-only amendment never makes it write one). The run then completes steps 2–7 and fails at step 8 (ERROR + 1): the declined-Dockerfile session is a **failed init by design** — the Dockerfile is mandatory for pybuggy (the 1.x flow guaranteed it by construction via a hardcoded path; the engine-owned session surfaces the decision to the user instead). Recovery for the half-initialized project: create the Dockerfile at the config `dockerfile` path (default `.goga/Dockerfile`) and re-run the registrations by hand, or remove `.goga` and re-run — a repeat bare `pybuggy init` is refused by the already-initialized guard. Documented in MIGRATION.md and `.usages/init.md`.

### `run_session`

```
logic = InitLogic(questionnaire=Questionnaire(), generator=FileGenerator(),
                  participation=ToolParticipation(invited=["pybuggy"]))
RETURN logic.run()
```

**Errors:** none caught here — engine exit codes and clean messages are propagated; tool contribution failures are soft inside the engine (warning + drop, session 0).
**Edge cases:** existing `.goga/config.yml` → engine returns 0 with zero side effects; uninvited pybuggy (never in this flow — pybuggy always invites itself) would make both hooks no-ops.

### `declare_pybuggy_session(context)`

```
IF NOT context.invited: RETURN
FOR item IN pybuggy_questions(): context.declare(item)
```

**Edge cases:** no skips are declared (pybuggy removes no core subtree); a duplicate local name would be rejected by the engine with a warning (defended by construction — ids fixed below).

### `pybuggy_questions`

```
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
```

**Edge cases:** `HEADERS`/`LOADER` never surveyed (documented as hand-added examples in `.usages/config-build.md`); the scalar set is data-driven from `PluginConfigKeys` — no key duplication.

### `build_config_data(answers)`

```
specs = parse_specs(answers.get("first_spec") or {}, answers.get("extra_specs") or None)
data = {}
FOR member IN PluginConfigKeys:
  IF member IN (HEADERS, LOADER): CONTINUE
  value = answers.get(member.value)
  IF value in (None, ""): CONTINUE                    # unanswered dropped, never written empty
  data[member.value] = _NUMERIC_MEMBERS[member](value) IF member IN _NUMERIC_MEMBERS ELSE value
data["specs"] = {name: entry.model_dump(exclude_none=True) FOR name, entry IN specs.items()}
RETURN data
```

**Errors:** a non-numeric numeric answer → `ValueError` → the engine drops the whole contribution with a warning (session continues, bootstrap still delivers its files).
**Edge cases:** plain serializable payload only (pydantic objects dumped); `base_url` always present (required question).

### `build_config_amendments()`

```
RETURN {"build.review.skip": True}
```

**Edge cases:** the single amendment is unconditional — the tool's declared intent in the answer space. The engine config mapper drops it (`_build_config_document` emits only `agent`/`env` for `build`), so the consumer-visible flag comes solely from the bootstrap's `ensure_review_skip` (q2/A). The former `docker_image.dockerfile` backstop is removed: the generator requires both the dockerfile and the base_image answers, so a dockerfile-only amendment never reached any artifact (both answers are recorded together or neither — see the Dockerfile-decline branch, review q1/A).

### `parse_specs(spec_answers, extra_specs)`

```
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
```

**Errors:** strict first spec → `ValueError` (soft contribution drop upstream); extras never raise.
**Edge cases:** extra line with extra `|`-fields beyond six → the first six fields win (`parts[3:6]`); whitespace-only lines skipped; name collision keeps the first spec.

### `ensure_review_skip(config_path)`

Identical to the old `ensure_review_executor_skip` with the key path `build → review → skip` (`_ensure_map` per level; `ValueError` when a level holds a non-mapping — never overwrites user data; no write when already `True`; INFO on change).

### `install_pybuggy(dockerfile_path)`

```
IF NOT dockerfile_path.exists(): RETURN None
line = f"RUN goga install pybuggy -v {'.'.join(importlib.metadata.version('goga-tool-pybuggy').split('.')[:2])}.x"
content = dockerfile_path.read_text(encoding="utf-8")
IF line IN content: RETURN None
IF content AND NOT content.endswith("\n"): content += "\n"
dockerfile_path.write_text(content + line + "\n", encoding="utf-8"); log INFO; RETURN line
```

### `register_usages` / `register_annotations` / `write_pybuggy_conftest` / `write_test_convention`

Carried over verbatim (relocation only); signatures gain typed return labels — no behavioral change.

### `register_hooks` (root)

```
hooks.subscribe("statuses", "register_statuses", "automate", register_automate_statuses)
hooks.subscribe("statuses", "register_statuses", "fix", register_fix_statuses)
hooks.subscribe("onboarding", "declare_session", "declare", declare_pybuggy_session)
hooks.subscribe("onboarding", "amend_config", "amend", amend_pybuggy_config)
```

## Cross-cutting Concerns

- **Error handling** — three tiers, never mixed: (1) CLI validation (flag combinations, explicit env-file) → `click.ClickException` (message + exit 1); (2) session tier — engine-owned clean codes and messages, propagated unchanged; a pybuggy contribution failure is soft (engine warning + drop, session 0); (3) bootstrap tier — step failures are ERROR-logged and mapped to a non-zero `run_bootstrap` return; `run_init` never wraps engine diagnostics; `click.Abort` always propagates to click.
- **Logging** — stdlib `logging`, module loggers, structured `extra` payloads, lowercase stable event names (per `conventions`): INFO — files copied/skipped, slot delivery, review-skip enforcement, install line added, registration results, session seam entry; WARNING — malformed extra spec lines, duplicate spec names, skipped registration keys (from `_log_registration`); ERROR — bootstrap step failure, missing Dockerfile after the session. No secrets in logs.
- **Validation** — `resolve_init_mode` (flag algebra, pure); `parse_specs` (strict first spec / lenient extras); `build_config_data` (numeric coercion; payload shape); engine-side survey validation (required inputs re-asked; choice restricted). Filesystem preconditions are checked only in orchestrators (`run_init` guard, `run_bootstrap` step 8), never in the pure writers.
- **Caching** — none. Registration is never cached by the platform (package edits apply from the next run); `pybuggy_questions` builds fresh immutable records per call (engine requirement).
- **Concurrency** — single-threaded CLI/session flow; no shared mutable state beyond the engine's own accumulators; no thread-safety requirements.

## Usages Analysis

### `conventions`
- **What it provides**: Python writing rules — relative imports, pydantic `kw_only` models, logging standard, Google docstrings, test structure/mocking rules, validation commands.
- **Where used**: every routine (docstrings, logging), all test scenarios below.
- **Why chosen**: project-wide mandatory practice.
- **How exactly**: module loggers with `extra`; `tests mirror source structure` → `tests/commands/init/test_{init,session,bootstrap}.py`; handler-direct-call CLI testing (no `CliRunner` in unit tests); `tmp_path` for file I/O.

### `click`
- **What it provides**: command/group/option binding, confirm gates, `ClickException` mapping.
- **Where used**: `init_cmd`, `resolve_init_mode` (exceptions), `run_init` (stderr echo), `run_bootstrap` (bare conftest gate).
- **Why chosen**: the CLI facade library of the project.
- **How exactly**: existing decorator set on `init_cmd`; `click.confirm(..., default=False)` gate; `click.echo(..., err=True)` guard message; `click.ClickException` for flag violations only.

### `ruamel-yaml`
- **What it provides**: round-trip YAML (comments, quotes, key order preserved); from-scratch `CommentedMap` documents; literal block scalars.
- **Where used**: `ensure_review_skip`, `register_usages`, `register_annotations`.
- **Why chosen**: consumer-owned `.goga/config.yml` must be amended point-wise without reformatting.
- **How exactly**: `YAML()` + `preserve_quotes=True`, `_ensure_map` navigation, idempotent skip-existing insert, reference-keyed annotation replacement, `LiteralScalarString` re-emit. The commented-record emission patterns (former `write_pybuggy_config`) are retired — the engine serializes plain data.

### `goga-scaffold`
- **What it provides**: `Scaffold().generate(template_input, ref_override)` / `Scaffold().upgrade(ref_override)` exit-code contract, state file semantics.
- **Where used**: `run_init` steps 3–4.
- **Why chosen**: the template engine of `goga init` parity.
- **How exactly**: engine constructed per call, codes propagated as-is, exceptions/diagnostics never wrapped.

### `goga-onboarding`
- **What it provides**: `InitLogic(questionnaire, generator, participation)` facade, session flow and behavior guarantees (existing-config end, soft tool failures, artifact set).
- **Where used**: `run_session`.
- **Why chosen**: the canonical 2.0 session orchestrator — the single entry point.
- **How exactly**: `InitLogic(...).run()` with `ToolParticipation(invited=["pybuggy"])`; no engine internals touched.

### `goga-onboarding-hooks`
- **What it provides**: the two onboarding actions, subscribe addresses, hook signature rules (context/self by name), moment member contracts, failure behavior.
- **Where used**: `declare_pybuggy_session`, `amend_pybuggy_config` (root `register_hooks` subscriptions).
- **Why chosen**: the participation contract is the core of the migration.
- **How exactly**: `hooks.subscribe("onboarding", "declare_session"|"amend_config", name, hook)`; `context.invited` guard; `declare`/`answer`/`write_config` buffer calls; exceptions left to propagate (mediator drops the contribution).

### `goga-onboarding-questions`
- **What it provides**: `Question`/`QuestionGroup` record kinds and fields, one-level nesting rule, answer addressing.
- **Where used**: `pybuggy_questions` (and the `first_spec` answer shape consumed by `parse_specs`).
- **Why chosen**: the declarative survey model replaces the imperative click survey.
- **How exactly**: records as specified in the algorithm above; required = absent default; optional = `default=""`; group answer = mapping of child ids.

### `goga-onboarding-generator`
- **What it provides**: `FileGenerator().generate(answers, contributions)` artifact order, verbatim tool-config serialization into `.goga/tools/<tool>/<file>`, created-file report.
- **Where used**: `build_config_data` (payload discipline), `amend_pybuggy_config` (`write_config("config.yml", ...)`).
- **Why chosen**: the engine is the single write path of tool configs.
- **How exactly**: plain-data payload (`model_dump(exclude_none=True)`), file name `config.yml` → `.goga/tools/pybuggy/config.yml`.

### Imported Usages

- `configuration` from `goga_tool_pybuggy/config` — schema compatibility of the payload (`specs` mapping with required entry fields; scalar plugin keys ignored on loading; default location `.goga/tools/pybuggy/config.yml`). Path: `goga_tool_pybuggy/config/.usages/configuration.md`. Also grounds the typed entries: `SpecEntry(type, location, git)` / `GitEntry(url, location, ref)` imported as `Types` from the same cell.
- Root cell: `goga-hooks` (facade callback + failure behavior), `goga-statuses` (statuses registration surface; **file currently missing on disk — pre-existing accepted residue**, path `.goga/usages/cooks/goga/history/registering-statuses.md`, renamed by a `goga sync` commit; refresh belongs to a `goga usages sync` run outside this task), `goga-onboarding-hooks` (see above).

## `.usages/` Update

### Cell: `goga_tool_pybuggy/commands/init`

#### Existing Files — Consistency

- **`init.md`** — rewritten by the apply stage; verified current against the traced contract (three modes, session semantics, bootstrap table, programmatic seams). Updates applied in this stage: (q1/A, prior decision) the install-line table row names the resolution rule — "in the project Dockerfile (the config `dockerfile` field, default `.goga/Dockerfile`)" — plus the review-stage decline-branch paragraph (a declined "Create Dockerfile?" confirm fails the command; recovery guidance); (q2/A) the session-delivery list corrected — the session delivers the questions and the tool config file; the `build.review.skip` flag lands via the bootstrap, and a native `goga init -t pybuggy` session sets no flag (no bootstrap runs); the dockerfile backstop sentence removed.
- **`config-build.md`** — rewritten by the apply stage; verified current: what is asked/not asked, compact-form grammar, contribution buffering, failure semantics, pure programmatic functions. Update applied in this stage (q2/A): the contribution section now describes the single `build.review.skip` amendment as declared intent (enforced by the bootstrap; the native-session gap noted) and drops the dockerfile-amendment bullet.

### Cell: `goga_tool_pybuggy` (root)

#### Existing Files — Consistency

- **`assembly.md`** — extended by the apply stage; verified current: the four-hook subscription table (statuses ×2 + onboarding ×2, callables' homes, no facade re-export, not-invited no-op) and the three-mode init entry. No updates needed.

### New Files

- None. The changed domains (init modes / config contribution / facade assembly) are each already covered by an existing file — supplement-in-place per the cookbook rules.

## Test Stack Trace

### General Setup

- Virtualenv with the test extra (`goga>=2.0.1,<2.1` after the pyproject change), `pytest`, `pytest-cov`.
- Unit style per `conventions`: handlers called directly (no `CliRunner` except wrapper-binding checks); file I/O via `tmp_path` + `monkeypatch.chdir(tmp_path)`; engine seams stubbed with `monkeypatch.setattr` on `goga_tool_pybuggy.commands.init.init` / `.session` attributes; prompts stubbed only where a routine legitimately prompts (`click.confirm`).
- Engine-verified fixtures: a `ToolDeclaration`-like recorder (attributes `invited`, lists `declared`, `skips`) and a `ToolContribution`-like recorder (`invited`, `answers`, `amendments`, `files`) — plain doubles asserting member usage, not engine internals.
- Logging assertions via `caplog`.

### Source File Registry

- `goga_tool_pybuggy/commands/init/init.py` → `tests/commands/init/test_init.py`
- `goga_tool_pybuggy/commands/init/session.py` → `tests/commands/init/test_session.py`
- `goga_tool_pybuggy/commands/init/bootstrap.py` → `tests/commands/init/test_bootstrap.py`
- composition (init_cmd ↔ run_init ↔ session/bootstrap ↔ cli registration) → `tests/commands/init/test_init_integration.py` (rewritten)
- `goga_tool_pybuggy/statuses.py` (`register_hooks`) → `tests/test_statuses.py` (new; root-package modules test directly under `tests/`)
- The stale `tests/__pycache__/test_statuses*.pyc` is an untracked artifact of a deleted local file — ignored.

---

### Positive Tests

#### `test_pybuggy_questions_returns_block_in_survey_order`

**Setup**: none (pure).
**Input**: `pybuggy_questions()`.
**Trace**:
```
pybuggy_questions()
  → Question(base_url)                    # first, no default → required
  → 6 scalar Questions                    # timeout, retries, assert_timeout, assert_delay,
                                          # assert_field_class, assert_response_class; default=""
  → QuestionGroup(first_spec, 6 children) # name/type(choice)/location/git_url/git_location/git_ref
  → Question(extra_specs, default="")
```
**Assertions**: `len(items) == 9`; `items[0].id == "base_url" and items[0].default is None`; scalar ids equal the `PluginConfigKeys` values in declaration order, each `default == ""`; the group `id == "first_spec"`, `children` ids `["name","type","location","git_url","git_location","git_ref"]`, `type` child `choices == ["swagger","openapi"]`; `items[-1].id == "extra_specs"`.
**Sufficiency**: pins the survey surface and order — the engine qualifies and asks exactly these records; a reordered/renamed block silently changes the consumer's UX and the answer keys consumed downstream.

#### `test_pybuggy_questions_covers_every_scalar_plugin_key`

**Setup**: import `PluginConfigKeys`.
**Input**: the block items.
**Trace**: collect question ids ∪ group children ids → compare against `{m.value for m in PluginConfigKeys} - {"headers","loader"}`.
**Assertions**: set equality; `HEADERS`/`LOADER` never present.
**Sufficiency**: the key set is data-driven — guards both against dropping a newly added scalar key and against hand-duplicating names.

#### `test_pybuggy_questions_holds_one_nesting_level`

**Setup**: none.
**Input**: the block items.
**Trace**: for each `QuestionGroup`, check every child is a `Question` (no nested group).
**Assertions**: the single group's children are all simple records.
**Sufficiency**: the engine rejects nested groups with a warning — a nested declaration would silently lose the questions.

#### `test_parse_specs_builds_first_spec_without_git`

**Setup**: `spec_answers = {"name": "shop", "type": "swagger", "location": "specs/shop.yaml", "git_url": "", "git_location": "", "git_ref": ""}`.
**Input**: `parse_specs(spec_answers, None)`.
**Trace**: strict validation passes → `SpecEntry(type="swagger", location=..., git=None)` → `{"shop": entry}`.
**Assertions**: single entry; `entry.type == "swagger"`, `entry.location == "specs/shop.yaml"`, `entry.git is None`.
**Sufficiency**: the minimal first-spec path — the structural "at least one spec" guarantee.

#### `test_parse_specs_attaches_git_when_url_and_location_present`

**Setup**: first spec with `git_url="https://git/repo.git"`, `git_location="specs/api.yaml"`, `git_ref="v2"`.
**Input**: `parse_specs(spec_answers, None)`.
**Trace**: both git fields present → `GitEntry(url, location, "v2")` attached.
**Assertions**: `entry.git.url/location/ref` match; a variant with empty `git_ref` yields `ref is None`; a variant with `git_url` but empty `git_location` yields `git is None`.
**Sufficiency**: pins the both-present attach rule shared by the first spec and extras.

#### `test_parse_specs_adds_wellformed_extra_line`

**Setup**: first spec as above.
**Input**: `extra_specs = "billing|openapi|specs/billing.yaml|https://git/b.git|specs/b.yaml|"`.
**Trace**: line split → 6 parts → `SpecEntry` under `"billing"` with git attached (`ref` empty → `None`).
**Assertions**: `set(specs) == {"shop", "billing"}`; billing entry fields exact.
**Sufficiency**: the compact form is the only extras channel — a regression here breaks multi-spec consumers.

#### `test_build_config_data_emits_plain_serializable_payload`

**Setup**: answers with `base_url="https://{{ HOST }}/api"`, `timeout="30"`, `retries="3"`, unanswered `assert_delay=""`, `first_spec` and one extra spec.
**Input**: `build_config_data(answers)`.
**Trace**: scalars coerced (`timeout` → `30.0` float, `retries` → `3` int) → specs dumped via `model_dump(exclude_none=True)` → `{"base_url": ..., "timeout": 30.0, "retries": 3, "specs": {...}}`.
**Assertions**: `data["timeout"] == 30.0 and isinstance(data["timeout"], float)`; `data["retries"] == 3`; `"assert_delay" not in data`; `data["specs"]["shop"] == {"type": "swagger", "location": "specs/shop.yaml"}` (no `git` key); every value is `str/int/float/dict` — `yaml.safe_dump(data)` succeeds with no `SpecEntry` objects present; key order `[base_url, timeout, retries, specs]`.
**Sufficiency**: the engine serializes buffered data verbatim — a pydantic object in the payload would make the engine silently drop the whole tool config (verified engine behavior); numeric typing matches the `ApiPlugin` option types.

#### `test_build_config_amendments_review_skip_declared_intent_only`

**Setup**: none (pure).
**Input**: `build_config_amendments()`.
**Trace**: returns the single declared-intent amendment unconditionally.
**Assertions**: result == `{"build.review.skip": True}` — exactly one entry, bool value.
**Sufficiency**: pins the amendment surface after review decision q2/A — the former `docker_image.dockerfile` backstop is gone (it never reached an artifact: the generator requires both dockerfile and base_image answers), and the surviving amendment is the tool's declared intent whose enforcement lives in the bootstrap.

#### `test_declare_pybuggy_session_declares_block_when_invited`

**Setup**: recorder context with `invited=True`.
**Input**: `declare_pybuggy_session(context)`.
**Trace**: guard passes → `context.declare(item)` per block item in order.
**Assertions**: `[i.id for i in context.declared]` equals the `pybuggy_questions()` id sequence (group included); `context.skips == []`.
**Sufficiency**: moment one wiring — a missing declaration silently drops the tool block from the survey.

#### `test_amend_pybuggy_config_buffers_contribution_when_invited`

**Setup**: recorder context, `invited=True`, `answers` = core + own block fixture.
**Input**: `amend_pybuggy_config(context)`.
**Trace**: guard → `context.answer("build.review.skip", True)` → `context.write_config("config.yml", <payload>)`.
**Assertions**: `context.amendments == [("build.review.skip", True)]` (the single amendment, q2/A); `context.files == [("config.yml", <payload>)]`; payload equals `build_config_data(answers)`.
**Sufficiency**: moment two wiring — the file name `config.yml` resolves to `.goga/tools/pybuggy/config.yml` at the engine.

#### `test_run_session_builds_engine_logic_with_pybuggy_invited`

**Setup**: `monkeypatch.setattr` on `goga_tool_pybuggy.commands.init.session.InitLogic` with a recorder class.
**Input**: `run_session()`.
**Trace**: constructor called with `Questionnaire()`, `FileGenerator()`, `ToolParticipation(invited=["pybuggy"])` instances → returns `logic.run()` result.
**Assertions**: kwargs types/names; `participation._invited == ["pybuggy"]` (or recorder equivalent); return value `7` propagated as `7`.
**Sufficiency**: the invited identity and the engine facade are the whole routine — a wrong identity makes both hooks no-ops forever.

#### `test_ensure_review_skip_enforces_key_and_preserves_config`

**Setup**: `tmp_path/config.yml` with comments and siblings (`build: {task_executor: {...}}`, `# keep me` comment).
**Input**: `ensure_review_skip(config)`.
**Trace**: round-trip load → create `build`/`review` levels → set `skip: True` → dump.
**Assertions**: returns `True`; re-loaded YAML has `build.review.skip is True`; `build.task_executor` intact; the `# keep me` comment still present; second call returns `False` and leaves the file byte-identical (mtime unchanged).
**Sufficiency**: the renamed key (`build.review.skip`) is the migration's consumer-visible config change; round-trip preservation and no-write idempotency are the contract's hard requirements.

#### `test_install_pybuggy_derives_minor_line_and_is_idempotent`

**Setup**: `tmp_path/Dockerfile` with `"FROM python:3.12\n"`; monkeypatch `importlib.metadata.version` → `"2.0.3"`.
**Input**: `install_pybuggy(dockerfile)` (twice).
**Trace**: version read → line `RUN goga install pybuggy -v 2.0.x` → appended with newline; second call finds the line → `None`.
**Assertions**: first returns the exact line and the file content equals `"FROM python:3.12\nRUN goga install pybuggy -v 2.0.x\n"`; second returns `None`, content unchanged; a dev-suffix version `"1.1.1.dev4+gabc"` yields `-v 1.1.x`.
**Sufficiency**: the ADR decision "install line derived from the package's own version line" — replaces the hardcoded `1.0.x` and pins the minor x-range grammar.

#### `test_register_usages_and_annotations_idempotent` (parametrized pair)

**Setup**: `tmp_path/config.yml` with existing `codemanifest.usages {"pybuggy-api": "old.md"}` and annotations block carrying a stale `pybuggy-api` line + a foreign line.
**Input**: `register_usages(config, {"pybuggy-api": "new.md", "conventions": ".goga/usages/conventions.md"})`; `register_annotations(config, {"pybuggy-api": "Use `pybuggy-api` ...", "conventions": "Use `conventions` ..."})`.
**Trace**: usages — `pybuggy-api` kept (`old.md`), `conventions` added; annotations — stale line replaced by reference, foreign line preserved, `conventions` appended.
**Assertions**: `added_keys == ["conventions"]`; `changed_keys == ["pybuggy-api", "conventions"]`; second run returns `[]`/`[]` and the file text is unchanged.
**Sufficiency**: relocation must not weaken the registration guarantees (never overwrite existing keys; reference-keyed idempotency).

#### `test_write_pybuggy_conftest_and_test_convention_emit_fixed_assets`

**Setup**: `tmp_path` targets.
**Input**: `write_pybuggy_conftest(p)`; `write_test_convention(p2)` (each twice).
**Trace**: conftest → fixed `_CONFTEST_TEMPLATE` text; convention → packaged asset text via `importlib.resources`.
**Assertions**: conftest content equals the pinned template string exactly; convention content equals the packaged asset (anchored by its `# Testing Convention: pytest...` first line); both overwrite on the second call.
**Sufficiency**: the two deterministic emitters — content drift here changes every consumer project silently.

#### `test_resolve_init_mode_table` (parametrized)

**Setup**: none (pure).
**Input**: `(None, None, False)`→`bare`; `("tpl", None, False)`→`template`; `("tpl", "v2", False)`→`template`; `(None, "v2", True)`→`upgrade`; `(None, None, True)`→`upgrade`.
**Trace**: direct calls.
**Assertions**: mode strings exact.
**Sufficiency**: the mode algebra unchanged by the migration — pins `goga init` parity.

#### `test_run_init_bare_runs_session_then_bootstrap`

**Setup**: `tmp_path` cwd (no `.goga`); monkeypatch `run_session` → recorder returning 0; `run_bootstrap` → recorder.
**Input**: `run_init(None, None, False)`.
**Trace**: mode bare → guard passes (no `.goga`) → session(0) → `run_bootstrap(template_mode=False)` → 0.
**Assertions**: both recorders called once, in order; `template_mode is False`; return 0.
**Sufficiency**: the rewired orchestration — old code called `run_onboarding`; the seams must now be session + bootstrap.

#### `test_run_init_template_passes_template_mode`

**Setup**: as above with `Scaffold.generate`/`Scaffold.upgrade` monkeypatched.
**Input**: `run_init("https://t.git#v1", None, False)`.
**Trace**: `Scaffold().generate("https://t.git#v1", None)` → 0 → session → `run_bootstrap(template_mode=True)`.
**Assertions**: generate called with `(tpl, None)`; `template_mode is True`; return 0.
**Sufficiency**: gate-style selection depends entirely on the propagated flag.

#### `test_run_bootstrap_full_pass_on_fresh_session_artifacts`

**Setup**: `tmp_path` cwd; pre-create session artifacts: `.goga/config.yml` (yaml text with `dockerfile: .goga/Dockerfile`), `.goga/Dockerfile` (`FROM x`); no conftest.
**Input**: `run_bootstrap(template_mode=False)`.
**Trace**: usages discovered from the installed package → copied; conventions slot written; review skip enforced; install line appended to `.goga/Dockerfile`; usage keys + annotation lines registered into the config; conftest written; Dockerfile exists → 0.
**Assertions**: return 0; `.goga/usages/cooks/pybuggy/api.md` and `asserts.md` exist with the packaged texts; `.goga/usages/conventions.md` exists; config has `build.review.skip is True`, `codemanifest.usages["pybuggy-api"]`/`["conventions"]`, annotation lines carrying the references; `conftest.py` equals the template; Dockerfile ends with the install line; caplog has no ERROR.
**Sufficiency**: the bootstrap happy path against realistic session output — the composite regression net for all nine steps.

#### `test_run_bootstrap_resolves_dockerfile_from_config_field`

**Setup**: session artifacts with `dockerfile: Dockerfile` (custom root path) and `Dockerfile` (`FROM x`) present; `.goga/Dockerfile` absent.
**Input**: `run_bootstrap(template_mode=True)`.
**Trace**: resolution reads the config field → install line appended to `./Dockerfile` → existence check passes.
**Assertions**: return 0; `Dockerfile` ends with the install line; `.goga/Dockerfile` was not created.
**Sufficiency**: the user-confirmed design (q1/A) — a custom Dockerfile answer must not turn a successful session into a failed init.

#### `test_register_hooks_subscribes_four_hooks`

**Setup**: recorder `hooks` object capturing `subscribe` calls (root facade import).
**Input**: `goga_tool_pybuggy.register_hooks(hooks)`.
**Trace**: four subscriptions in order.
**Assertions**: calls == `[("statuses","register_statuses","automate", register_automate_statuses), ("statuses","register_statuses","fix", register_fix_statuses), ("onboarding","declare_session","declare", declare_pybuggy_session), ("onboarding","amend_config","amend", amend_pybuggy_config)]`; the onboarding callables are the init-cell session objects (`from goga_tool_pybuggy.commands.init import ...` identity).
**Sufficiency**: the subscription table is the platform contract — a wrong address/name silently disables native `goga init -t pybuggy` participation (the current repo state) or the statuses.

---

### Negative Tests

#### `test_run_init_bare_guard_refuses_initialized_project`

**Setup**: `tmp_path` with `.goga/` directory; `run_session`/`run_bootstrap`/`Scaffold` monkeypatched to raise AssertionError if called.
**Input**: `run_init(None, None, False)` (capture stderr via `click.echo` monkeypatch or capsys).
**Trace**: mode bare → `.goga` is a dir → refusal.
**Assertions**: return 1; stderr contains `Project already initialized`; no recorder called; the `.goga` tree byte-identical after the call.
**Sufficiency**: the goga-parity guard — a repeat bare run must never modify files or prompt.

#### `test_run_init_guard_checks_directory_existence_only`

**Setup**: `tmp_path` with a `.goga` **regular file**; session/bootstrap recorders.
**Input**: `run_init(None, None, False)`.
**Trace**: `is_dir()` false → guard passes → session + bootstrap run.
**Assertions**: recorders called; return matches the stubbed codes.
**Sufficiency**: pins the contract requirement (a regular file does not trip the guard).

#### `test_run_init_invalid_flag_combinations_raise`

**Setup**: parametrized `(tpl, ref, upgrade)`: `("t", None, True)`, `(None, "v2", False)`.
**Input**: `run_init(...)`.
**Trace**: `resolve_init_mode` raises `click.ClickException`.
**Assertions**: `pytest.raises(click.ClickException)`; message present.
**Sufficiency**: CLI validation tier — exit 1 with a message, never a traceback.

#### `test_run_init_propagates_engine_and_session_codes`

**Setup**: parametrized — scaffold returns 3 (template mode; session/bootstrap must not run); session returns 4 (bootstrap must not run); upgrade returns 5.
**Input**: `run_init` per variant.
**Trace**: codes returned unchanged.
**Assertions**: returns 3 / 4 / 5; downstream recorders not called for the failing seam.
**Sufficiency**: "a non-zero scaffold or session exit code propagated as-is" and "no onboarding side effect on a failed scaffold".

#### `test_parse_specs_rejects_invalid_first_spec`

**Setup**: parametrized first-spec answers: empty name; `type="yaml"`; empty location.
**Input**: `parse_specs(spec_answers, None)`.
**Trace**: strict validation → `ValueError`.
**Assertions**: `pytest.raises(ValueError)` per variant.
**Sufficiency**: the strict tier — upstream this drops the contribution with a warning (session soft-failure), never a partially-valid config.

#### `test_parse_specs_skips_malformed_and_colliding_extra_lines`

**Setup**: first spec `shop`; `extra_specs = "billing|yaml|x.yaml\nbad|swagger\n| swagger | loc\nshop|openapi|other.yaml"` (bad type; too few fields; empty name; collision).
**Input**: `parse_specs(spec_answers, extra_specs)`.
**Trace**: each invalid line → WARNING + skip; collision keeps the first.
**Assertions**: `set(specs) == {"shop"}`; caplog has 4 warnings with `"malformed extra spec line skipped"`/`"duplicate spec name skipped"` events.
**Sufficiency**: the lenient tier — one bad line must never fail the whole contribution (and never produce a spec from it).

#### `test_declare_and_amend_no_invitation_call_nothing`

**Setup**: recorder contexts with `invited=False`.
**Input**: `declare_pybuggy_session(ctx)`; `amend_pybuggy_config(ctx)`.
**Trace**: guard returns immediately.
**Assertions**: `declared == []`, `skips == []`, `amendments == []`, `files == []`.
**Sufficiency**: the contract rule of the moments — pybuggy must stay silent in sessions that did not invite it (`goga init` without `-t pybuggy`).

#### `test_build_config_data_non_numeric_answer_raises`

**Setup**: answers with `timeout="abc"`.
**Input**: `build_config_data(answers)`.
**Trace**: float coercion → `ValueError`.
**Assertions**: `pytest.raises(ValueError)`.
**Sufficiency**: documents the soft-drop boundary — the engine discards the contribution with a warning; the session continues.

#### `test_run_bootstrap_missing_dockerfile_fails_with_error`

**Setup**: parametrized — (a) session artifacts with a config whose `dockerfile` field points at an absent file; (b) the declined-Dockerfile session: a config with **no** `dockerfile` field at all (the user answered No to "Create Dockerfile?" — neither docker_image answer recorded, the generator wrote no Dockerfile); no Dockerfile anywhere in both variants.
**Input**: `run_bootstrap(template_mode=False)`.
**Trace**: resolution — (a) config field → absent file; (b) no field → `.goga/Dockerfile` fallback; `install_pybuggy` no-op → step 8 existence check fails.
**Assertions**: return 1 per variant; caplog ERROR mentions the Dockerfile; conftest/usages side effects already applied (steps 2–7 ran); variant (b) additionally asserts `.goga/Dockerfile` was NOT created by the bootstrap.
**Sufficiency**: the mandatory-Dockerfile invariant at the resolved path — variant (b) pins the reachable decline branch (confirm default No): a declined session must end the command non-zero, never silently succeed (review decision q1/A).

#### `test_run_bootstrap_step_failure_maps_to_nonzero`

**Setup**: fresh artifacts; monkeypatch `register_usages` to raise `OSError`.
**Input**: `run_bootstrap(template_mode=False)`.
**Trace**: steps 2–4 succeed → step 6 raises → caught → ERROR → return 1.
**Assertions**: return 1; caplog ERROR with the cause; no `click.ClickException` raised (the tier changed from the old code).
**Sufficiency**: "A write failure in any step is logged (ERROR) and fails the command with a non-zero exit".

#### `test_install_pybuggy_noop_without_file`

**Setup**: absent Dockerfile path.
**Input**: `install_pybuggy(path)`.
**Assertions**: returns `None`; the file is not created.
**Sufficiency**: "Do not create the Dockerfile when the engine did not write it".

---

### Edge Case Tests

#### `test_run_bootstrap_template_mode_never_prompts`

**Setup**: cwd with every gated file pre-existing (usages targets, conventions slot, conftest, config, Dockerfile).
**Input**: `run_bootstrap(template_mode=True)`.
**Trace**: all gates take the skip branch.
**Assertions**: return 0; no `click.confirm` call (monkeypatched to raise); every pre-existing file byte-identical; INFO logs emitted.
**Sufficiency**: "Do not prompt about existing files in template mode — the template expresses the user's intent".

#### `test_run_bootstrap_bare_mode_gates`

**Setup**: pre-existing usages target (stale content) and conftest; confirm monkeypatched `False` then `True` (two runs).
**Input**: `run_bootstrap(template_mode=False)` twice.
**Trace**: usages target overwritten without asking; conftest decline → untouched; conftest confirm → overwritten.
**Assertions**: run 1 (decline): stale usages text replaced, conftest unchanged, return 0; run 2 (confirm): conftest equals the template.
**Sufficiency**: the bare overwrite/ask asymmetry (usages vs conftest) and "decline is not a failure".

#### `test_run_bootstrap_existing_config_session_end_still_enforces`

**Setup**: pre-existing full config (the template-brought-config case — session returned immediately); Dockerfile present.
**Input**: `run_bootstrap(template_mode=True)`.
**Trace**: no session artifacts assumed; review skip + registrations + install line still applied.
**Assertions**: return 0; `build.review.skip is True`; usage keys registered; install line appended.
**Sufficiency**: "runs on every pass, including when the session ended immediately on an existing config".

#### `test_run_bootstrap_idempotent_rerun`

**Setup**: run once on fresh artifacts; snapshot the tree (`{p: p.read_bytes()}` for all files).
**Input**: `run_bootstrap(template_mode=False)` again (conftest absent-branch not applicable — exists → confirm monkeypatched False).
**Trace**: every writer/gate takes the no-change branch.
**Assertions**: tree snapshot identical (no diffs, no mtime-only churn beyond content equality); returns 0.
**Sufficiency**: "Every step is idempotent; a repeat run changes nothing".

#### `test_run_bootstrap_empty_and_broken_config_variants`

**Setup**: variant A — absent `.goga/config.yml` (bootstrap before any session write is degenerate but must not crash: registrations create the minimal document; dockerfile falls back); variant B — empty file (ruamel `load` → `None` handling).
**Input**: `run_bootstrap(template_mode=True)` per variant.
**Assertions**: no exception (variant A: registrations create the file; variant B handled); Dockerfile fallback path used.
**Sufficiency**: ruamel `None`-document and from-scratch creation branches (documented library gotchas).

#### `test_amend_pybuggy_config_exception_drops_contribution_upstream`

**Setup**: recorder context whose `answers` trigger `build_config_data` `ValueError` (bad numeric), monkeypatched `context.answer` recorder.
**Input**: `amend_pybuggy_config(context)`.
**Trace**: `answer("build.review.skip", True)` buffered, then `build_config_data` raises.
**Assertions**: `pytest.raises(ValueError)`; `files == []` (the write never buffered).
**Sufficiency**: pins the partial-buffer boundary — the engine discards the whole contribution; the session and the bootstrap still complete (documented failure semantics).

#### `test_session_smoke_end_to_end_with_prompt_stubs`

**Setup** (`test_init_integration.py`): `tmp_path` cwd; monkeypatch `click.prompt`/`click.confirm` with a scripted answer map. The map must be pinned exactly (review q3/A) — confirms: `Download base convention` → n, `Add codemanifest usages?` → n, `Add codemanifest annotations?` → n, `Configure a build agent?` → n, **`Create Dockerfile?` → y** (default No — declining is the failed-init branch of q1/A), `Configure a pipeline agent?` → n, `Add tools?` → n, `Add usages records?` → n; inputs: `Language` → `python`, `Dockerfile path` → Enter (default `.goga/Dockerfile`), `Base image (FROM)` → Enter (the python-family default), **`Built image name` → an explicit value** (e.g. `pybuggy-smoke:latest` — `resolve_project_name()` returns None in `tmp_path` without a git origin, so this prompt carries NO default and Enter is impossible), then the pybuggy block: `base_url` → `https://{{ HOST }}/api`, scalars → Enter-skipped, first spec `shop|swagger|specs/shop.yaml` fields, `extra_specs` → `billing|openapi|specs/billing.yaml|https://git/b.git|specs/b.yaml|`; write a minimal swagger file at `specs/shop.yaml` and `specs/billing.yaml`. The test stays offline: no answer activates the conventions download (`generate_goga_config` fetches from GitHub only when the codemanifest usages carry `conventions`).
**Input**: `run_session()` (real engine; the registry imports the real `register_hooks` → real hooks).
**Trace**: engine surveys core + pybuggy block → moments delivered to the real pybuggy hooks → artifacts generated.
**Assertions**: return 0; `.goga/config.yml` exists with `language: python`; `.goga/tools/pybuggy/config.yml` equals the expected plain payload (`specs` with `shop` + `billing`, `base_url`, `git` block on billing only); Dockerfile exists at the answered path; stdout report names the tool config with `(tool: pybuggy)` attribution.
**Sufficiency**: the acceptance-level proof of the participation mechanism in-process — native `goga init -t pybuggy` equivalence without a TTY; guards the whole hook wiring against regressions in either the tool or the platform import path.

#### `test_init_cmd_binds_surface_and_propagates_exit`

**Setup**: introspect `init_cmd.__click_params__`/decorators; fake `ctx` object.
**Input**: decorator metadata; `init_cmd(ctx, None, None, False)` with `run_init` monkeypatched → 3.
**Trace**: wrapper delegates and calls `ctx.exit(3)`.
**Assertions**: params carry the optional positional `tpl`, flag `--upgrade`, option `--ref`; `ctx.exit` called with 3.
**Sufficiency**: the CLI surface is the consumer contract; the exit propagation is the wrapper's only job.

---

## Additional Instructions for the Implementation Agent

- Write the three cell modules in dependency order: `bootstrap.py` (relocations + `ensure_review_skip` rename + dynamic install line) → `session.py` (new) → `init.py` (rewrite, reusing the carried-over pieces) → facades (`commands/init/__init__.py`, `statuses.py` extension). Delete the dead routines and helpers in the same change; keep docstrings Google-style per `conventions` and the module-logger pattern.
- Keep the question ids, prompt texts, and the group id `first_spec` exactly as specified — they are the answer keys consumed by `parse_specs`/`build_config_data` and pinned by tests.
- The tool-config payload must contain only plain Python types before `context.write_config` — dump `SpecEntry`/`GitEntry` with `model_dump(exclude_none=True)` inside `build_config_data`; never buffer pydantic objects (the engine serializes verbatim and silently drops unserializable files).
- Amendments address exactly `build.review.skip` (declared intent — the engine mapper drops it; the bootstrap `ensure_review_skip` enforces the flag) — a dot-path into the engine answer space; never write the config file from the hooks.
- `run_bootstrap` resolves the Dockerfile from the consumer config `dockerfile` field with the `.goga/Dockerfile` fallback (user-confirmed decision q1/A); bootstrap step failures return 1 (ERROR-logged), they no longer raise `click.ClickException`.
- Project-level items in task scope, executed with the implementation (not part of the cells): `pyproject.toml` test extra `goga>=1.3.0,<1.4.0` → `goga>=2.0.1,<2.1`; rewrite `tests/commands/init/` per the test registry above (new `test_session.py`, `test_bootstrap.py`, new `tests/test_statuses.py`); `MIGRATION.md` at the repo root covering `build.review_executor.skip` → `build.review.skip`, the new `goga init -t pybuggy` path, and the Dockerfile-decline behavior change (1.x always created the Dockerfile; 2.0 surfaces the core confirm "Create Dockerfile?" defaulting to No — declining ends the command with a non-zero exit after the session artifacts are written; recovery: create the Dockerfile at the config `dockerfile` path or remove `.goga` and re-run); update `docs/getting-started.md`, `docs/cli/init.md`, `README.md`, plugin/pipelines pages off the 1.x model.
- Validation gate for the implementation: `ruff check goga_tool_pybuggy/` clean, `pytest tests/ -x` green on goga 2.0.1, `goga lint` no new findings (the pre-existing `goga-statuses` missing-file residue is accepted and tracked for `goga usages sync`), plus one manual consumer quickstart run (`goga install pybuggy` → `goga tool pybuggy init` → `goga pipeline pybuggy:api.automate`) as the accepted e2e evidence.
