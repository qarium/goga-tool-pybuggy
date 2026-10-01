# Architecture Plan — pybuggy onboarding migration to goga 2.0

## Topic

Short name: **pybuggy onboarding migration to goga 2.0 (canonical session-participation model)**
Plan path: `.goga/history/2026/up-goga/arch.md`

Scope: rebuild of `goga_tool_pybuggy/commands/init` on the goga 2.0 onboarding model and the matching revision of the
package facade `goga_tool_pybuggy`. Reference-only cells (`config`, `plugin`, `api`, `spec`, `output`, `matchcrest`,
the other command cells) are untouched. goga stays an environment precondition — never a runtime dependency.

## Implementation Order

1. **`goga_tool_pybuggy/commands/init`** (modified — rewritten). First: it imports only from the unchanged leaves
   `goga_tool_pybuggy/config` (SpecEntry, GitEntry, usage `configuration`) and `goga_tool_pybuggy/plugin`
   (PluginConfigKeys); nothing imports it except the root, which is revised after it.
2. **`goga_tool_pybuggy` (root)** (modified). Second: its Imports pull `init_cmd`, `declare_pybuggy_session`,
   `amend_pybuggy_config` and the usages `init`, `config-build` from `commands/init`, so the provider contract must
   exist first.

## Artifacts

### Cell 1: `goga_tool_pybuggy/commands/init` — MODIFIED (rewritten)

Files of the cell: `CODEMANIFEST`, `.usages/init.md`, `.usages/config-build.md`; implementation files implied by
`location`: `init.py` (command + orchestrator), `session.py` (session participation), `bootstrap.py` (writers).

#### CODEMANIFEST (full content — rewrite the file)

```yaml
Imports:
  - Types:
      - SpecEntry
      - GitEntry
    Usages:
      - configuration
    From: goga_tool_pybuggy/config
  - Types:
      - PluginConfigKeys
    From: goga_tool_pybuggy/plugin

Usages:
  conventions: .goga/usages/conventions.md
  click: .goga/usages/cooks/click.md
  ruamel-yaml: .goga/usages/cooks/ruamel-yaml.md
  goga-scaffold: .goga/usages/cooks/goga/scaffold/scaffold-usage.md
  goga-onboarding: .goga/usages/cooks/goga/onboarding/onboarding-usage.md
  goga-onboarding-hooks: .goga/usages/cooks/goga/onboarding/registering-hooks.md
  goga-onboarding-questions: .goga/usages/cooks/goga/onboarding/questions/question-records.md
  goga-onboarding-generator: .goga/usages/cooks/goga/onboarding/generator/artifact-generation.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `click` for the command wrapper, flag validation, and mapping domain errors to click.ClickException.
  Use `ruamel-yaml` for round-trip edits of the consumer .goga/config.yml (comments, quotes, and key order preserved).
  Use `goga-scaffold` for template generation and migration.
  Use `goga-onboarding` for the session run: the invited participation, the survey, the artifact generation, and the existing-config session semantics.
  Use `goga-onboarding-hooks` for the two participation moments and the hook context members.
  Use `goga-onboarding-questions` for the question records of the pybuggy block.
  Use `goga-onboarding-generator` for the buffered tool config serialization and the created-file report.

  Top-level bootstrap command pybuggy init — three modes resolved from the flags. Bare (no arguments) runs only in a
  not-yet-initialized directory: an existing .goga directory is refused up front ("Project already initialized" on
  stderr, exit code 1, no prompts, no file modifications). Template (<tpl> with optional --ref) scaffolds the template
  project first; a failed scaffold stops the command without onboarding side effects; after a successful scaffold the
  onboarding session runs and the pybuggy bootstrap applies with skip-if-exists gates. Upgrade (--upgrade with
  optional --ref) runs the template migration only — no onboarding.

  Order of actions: resolve the mode, apply the bare guard, run the scaffold engine in template and upgrade modes,
  run the onboarding session, close with the pybuggy bootstrap. The session is engine-owned: the core questions and
  the pybuggy block are surveyed by the engine, and the tool config file and the config amendments are committed
  through the participation mechanism; an existing .goga/config.yml ends the session immediately and is never
  rewritten. The bootstrap owns the pybuggy files the session does not carry: the packaged usages copy, the
  `conventions` slot, the build.review.skip enforcement, the Dockerfile install line, the usage and annotation
  registrations, and the root conftest. Use relative imports inside the cell.

---

"init_cmd(ctx: click.Context, tpl: str | None, ref: str | None, upgrade: bool)":
  location: init.py
  annotations: |
    Click command wrapper for the top-level init command; binds the CLI surface — the optional positional <tpl>, the
    option --ref <git-ref>, and the flag --upgrade — delegates to `run_init`, and propagates the returned exit code
    via ctx.exit.

    `ctx`: Click execution context used to control the process exit code.
    `tpl`: template source — local path or git URL, optionally carrying a #ref fragment; absent in bare/upgrade modes.
    `ref`: git ref override; None keeps the template's own ref resolution.
    `upgrade`: migrate a previously scaffolded project instead of onboarding.

    Use `click` for the command wrapper.

"run_init(tpl: str | None, ref: str | None, upgrade: bool) -> exit_code:int":
  location: init.py
  annotations: |
    Handler for the init command — the testable entry point: resolves the operation mode, applies the
    already-initialized guard in bare mode, drives the template scaffold engine in template and upgrade modes, runs
    the onboarding session, and closes with the pybuggy bootstrap.

    `tpl`: template source; None in bare and upgrade modes.
    `ref`: git ref override; overrides the URL fragment in template mode and the migration target in upgrade mode.
    `upgrade`: run template migration only.
    `exit_code`: 0 on success; 1 for an invalid flag combination, the already-initialized refusal, or a failed
    bootstrap step; a non-zero scaffold or session exit code propagated as-is.

    Algorithm:
    1. Resolve the mode via `resolve_init_mode` — an invalid flag combination raises click.ClickException (exit 1).
    2. Bare mode only: when the current working directory holds a .goga directory, echo "Project already initialized"
       to stderr and return 1 — before any engine runs and before any file is touched. Template and upgrade modes are
       never guarded.
    3. Upgrade mode: run the template migration via the scaffold engine with `ref` and return its exit code — no
       session, no bootstrap.
    4. Template mode: scaffold the template into the current working directory with `tpl` and `ref`; a non-zero code
       stops the command with that code — no onboarding side effect is applied.
    5. Run the onboarding session via `run_session`; propagate a non-zero code.
    6. Return the result of `run_bootstrap` with template_mode set according to the resolved mode.

    Requirements:
    - The guard checks directory existence only; a .goga regular file does not trip it.
    - A guard refusal performs zero prompts and zero file writes.
    - The scaffold engine owns its error handling: the routine receives only the exit code and never wraps engine
      exceptions or diagnostics.
    - In template mode no bootstrap side effect is applied when the scaffold failed.

    Constraints:
    - Do not run the session or the bootstrap in upgrade mode — no prompts, no file augmentation.
    - Do not guard template or upgrade mode — the guard is bare-only.
    - Do not delete, move, or modify .goga on refusal — refuse and exit.
    - Do not inject answers into the template beyond project_name — the engine resolves it.

    Use `resolve_init_mode`, `run_session`, `run_bootstrap`. Use `goga-scaffold` for the engine contract.
    Use `click` for the ClickException propagation and the stderr echo. Use `conventions` for logging and testing.

"resolve_init_mode(tpl: str | None, ref: str | None, upgrade: bool) -> mode:str":
  location: init.py
  annotations: |
    Pure resolution of the init mode from the CLI flags — validates the flag combination and maps it to exactly one
    mode.

    `tpl`: template source from the positional argument; None when absent.
    `ref`: git ref override; None when absent.
    `upgrade`: True when --upgrade is set.
    `mode`: the resolved mode — bare, template, or upgrade.

    Algorithm:
    1. Reject <tpl> combined with --upgrade — raise click.ClickException (mutually exclusive, exit 1).
    2. Reject --ref without <tpl> and without --upgrade — raise click.ClickException (exit 1).
    3. Return upgrade when --upgrade is set; template when <tpl> is given; bare otherwise.

    Requirements:
    - Flag rules mirror the goga init command: <tpl>/--upgrade mutual exclusion, --ref placement validation.
    - Invalid combinations surface as click.ClickException; valid input never raises.
    - Pure — no TTY, no I/O, no side effects.

    Use `click` for the ClickException mapping. Use `conventions` for type hints and testing.

"run_bootstrap(template_mode: bool) -> exit_code:int":
  location: init.py
  annotations: |
    pybuggy-owned bootstrap after the onboarding session: deliver the files the session does not carry. The gate style
    depends on `template_mode`: template gates silently skip an existing file with an INFO log; bare gates ask via
    click.confirm (default no) before touching one.

    `template_mode`: True — a scaffolded template occupies the target directory; existing files are left untouched.
    `exit_code`: 0 on success; non-zero on a failed step.

    Algorithm:
    1. Resolve the output root as the current working directory.
    2. Discover every .usages/*.md under the api cell of the installed package; copy each into
       .goga/usages/cooks/pybuggy/<stem>.md — template mode: an existing target is skipped with an INFO log; bare
       mode: an existing target is overwritten.
    3. Deliver the `conventions` slot: when .goga/usages/conventions.md does not exist, call `write_test_convention`;
       when it exists, log INFO and leave the file untouched.
    4. Enforce build.review.skip: true via `ensure_review_skip` — idempotent; runs on every pass, including when the
       session ended immediately on an existing config.
    5. Augment the Dockerfile via `install_pybuggy` — idempotent; a no-op when the file is absent.
    6. Register the usage keys via `register_usages` and the annotation lines via `register_annotations` — idempotent.
    7. Deliver the root conftest: when conftest.py does not exist, call `write_pybuggy_conftest`; when it exists —
       template mode: log INFO and skip; bare mode: ask via click.confirm (default no) and overwrite only on yes.
    8. Verify the Dockerfile exists; when it does not, log ERROR and return non-zero.
    9. Return 0.

    Requirements:
    - After every successful run the consumer config carries build.review.skip: true; the pybuggy usage keys and
      annotation lines are registered; the packaged usages are copied; the `conventions` slot is occupied when it was
      absent; the root conftest exists.
    - The pure writers always (over)write when called — every existence check and confirmation lives here.
    - Every step is idempotent; a repeat run changes nothing.
    - A write failure in any step is logged (ERROR) and fails the command with a non-zero exit.

    Constraints:
    - Do not copy usages of internal development cells (config, spec, output, matchcrest, plugin, commands).
    - Do not merge into an existing conftest — either a confirmed overwrite (bare) or a skip.
    - Do not prompt about existing files in template mode — the template expresses the user's intent.
    - Do not create the Dockerfile when the engine did not write it — report and fail.

    Use `write_test_convention`, `ensure_review_skip`, `install_pybuggy`, `register_usages`, `register_annotations`,
    `write_pybuggy_conftest`. Use `click` for the bare-mode gates. Use `conventions` for logging and testing.

"run_session() -> exit_code:int":
  location: session.py
  annotations: |
    Run one goga onboarding session in-process with pybuggy invited — the contract test seam. The engine surveys the
    core questions and the pybuggy block, commits the tool contributions, and generates the project artifacts.

    `exit_code`: the engine session exit code (0 success, non-zero a session error), propagated unchanged.

    Algorithm:
    1. Build the session logic with the engine questionnaire, the engine file generator, and the participation
       mediator holding pybuggy as the invited tool.
    2. Run the session and return its exit code.

    Requirements:
    - The session is engine-owned: questions are asked by the engine, never by this cell.
    - An existing .goga/config.yml ends the session immediately — no questions, no tool events, no artifacts; the
      exit code stays 0.
    - A failing tool contribution is discarded by the engine with a warning; the session continues and returns 0.
    - The consumer artifacts after a successful session: .goga/config.yml, the Dockerfile, and the buffered pybuggy
      tool config file.

    Constraints:
    - Do not orchestrate the engine internals — the session logic object is the single entry point.
    - Do not catch or wrap engine errors — propagate the exit code.

    Use `goga-onboarding` for the session facade and semantics. Use `conventions` for logging and testing.

"declare_pybuggy_session(context: object)":
  location: session.py
  annotations: |
    Declaration moment of the participation contract: declare the pybuggy question block on the session context so the
    engine surveys it after the core questions, under a heading with the tool identity.

    `context`: the declaration surface delivered by the platform.

    Algorithm:
    1. Return immediately when the session did not invite this tool.
    2. Declare every item of `pybuggy_questions` on the context.

    Requirements:
    - The no-invitation branch calls nothing — the contract rule of the moment.
    - Local question names are unique among siblings; the engine qualifies them with the tool identity.

    Constraints:
    - Do not survey, prompt, or read answers — the engine asks the declared records itself.

    Use `pybuggy_questions`. Use `goga-onboarding-hooks` for the member contract of the moment.
    Use `goga-onboarding-questions` for the record shapes.

"amend_pybuggy_config(context: object)":
  location: session.py
  annotations: |
    Amendment moment of the participation contract: read the isolated answer view and buffer the pybuggy contribution —
    the config amendments and the tool config file.

    `context`: the amendment surface delivered by the platform.

    Algorithm:
    1. Return immediately when the session did not invite this tool.
    2. Read the answer view from the context.
    3. Buffer every entry of `build_config_amendments` as a config amendment.
    4. Buffer the tool config file with `build_config_data`.

    Requirements:
    - The answer view carries the core answers plus this tool's own answers under local names.
    - An exception raised here drops the whole contribution with a warning naming the tool — the session continues.

    Constraints:
    - Do not write files directly — the engine serializes and writes the buffered config.
    - Do not read another tool's answers — they are never visible.

    Use `build_config_amendments`, `build_config_data`. Use `goga-onboarding-hooks` for the member contract and the
    failure behavior. Use `goga-onboarding-generator` for the buffered file serialization.

"pybuggy_questions() -> items:list[Question]":
  location: session.py
  annotations: |
    Build the declarative pybuggy question block — the survey of the tool configuration, asked by the engine.

    `items`: the question records of the block, in survey order.

    Algorithm:
    1. Declare base_url as a required input — a Jinja2 template string.
    2. Declare every scalar member of `PluginConfigKeys` except HEADERS and LOADER as an optional input, each prompt
       stating what the field is for.
    3. Declare the first-spec group: name (input), type (choice swagger|openapi), location (input), and the optional
       git fields (input; an empty git url means no git source).
    4. Declare extra_specs as one optional input carrying the additional specs, one per line, in the compact form
       name|type|location|git_url|git_location|git_ref.

    Requirements:
    - The block holds exactly one nesting level — groups carry simple children only.
    - base_url is required and its answer is a Jinja2 template; the remaining scalars are optional.
    - The first-spec group makes at least one spec structurally unavoidable: its answer is always recorded.

    Constraints:
    - Do not survey HEADERS or LOADER — they stay documented as hand-added examples in the cell usage file.
    - Do not duplicate plugin key names — iterate `PluginConfigKeys`.

    Use `goga-onboarding-questions` for the record kinds and the nesting rule. Use `PluginConfigKeys` for the scalar
    key set. Use `conventions` for type hints and testing.

"build_config_data(answers: dict[str, object]) -> data:dict[str, object]":
  location: session.py
  annotations: |
    Pure mapping of the tool answer view into the tool config file payload: the specs mapping and the answered scalar
    keys.

    `answers`: the tool answer view — the block answers under local names.
    `data`: the serializable payload of .goga/tools/pybuggy/config.yml.

    Algorithm:
    1. Build the specs mapping via `parse_specs` from the first-spec group answer and the extra_specs answer.
    2. Collect the answered scalar keys from the `PluginConfigKeys` members, dropping unanswered ones.
    3. Return the payload: the specs mapping plus the active scalar keys.

    Requirements:
    - The payload satisfies the config schema (see `configuration`): a specs mapping whose entries carry the required
      fields; the scalar plugin keys are ignored on loading.
    - The payload is plain serializable data — the engine writes the YAML.

    Constraints:
    - Do not prompt or touch the filesystem — pure.
    - Do not emit commented records — the engine serializes plain data; the documented examples live in the cell usage
      file.

    Use `parse_specs`. Use `PluginConfigKeys` for the scalar key set. Use `configuration` for schema compatibility.
    Use `conventions` for type hints and testing.

"build_config_amendments(answers: dict[str, object]) -> amendments:dict[str, object]":
  location: session.py
  annotations: |
    Pure mapping of the tool answer view into the buffered config amendments of the consumer .goga/config.yml.

    `answers`: the tool answer view.
    `amendments`: the amendment paths and values.

    Algorithm:
    1. Amend build.review.skip to true — the review pass is skipped in pybuggy-initialized projects.
    2. Amend the dockerfile path to .goga/Dockerfile when the core answers carry no dockerfile path.

    Requirements:
    - The amendments are path→value pairs the platform merges into the answer space before generation.
    - A present dockerfile answer is never substituted.

    Constraints:
    - Do not amend keys outside the two named paths.
    - Do not write the config file — amendments are buffered on the context.

    Use `goga-onboarding-hooks` for the amendment semantics. Use `conventions` for type hints and testing.

"parse_specs(spec_answers: dict[str, object], extra_specs: str | None) -> specs:dict[str, SpecEntry]":
  location: session.py
  annotations: |
    Pure, lenient assembly of the specs mapping: the first-spec group answer plus the extra_specs compact lines.

    `spec_answers`: the first-spec group answer under local names.
    `extra_specs`: the optional compact input; None or empty when unanswered.
    `specs`: the specs mapping keyed by spec name.

    Algorithm:
    1. Validate the first spec strictly — a non-empty name, a type of swagger or openapi, a non-empty location — and
       build its `SpecEntry`, attaching a `GitEntry` when the git url and location are present.
    2. For every non-empty line of `extra_specs`: split it on the field separator; a malformed line is skipped with a
       WARNING; a well-formed line becomes its `SpecEntry` under its name.
    3. Return the mapping.

    Requirements:
    - The mapping always holds at least the first spec.
    - A spec name collision between the first spec and an extra line keeps the first spec and warns.
    - An absent git url yields no git block.

    Constraints:
    - Do not fail the whole contribution on a malformed extra line — skip it and warn.
    - Do not prompt — pure.

    Use `SpecEntry` and `GitEntry` for the entry shapes. Use `configuration` for the schema. Use `conventions` for
    logging and testing.

"write_test_convention(path: Path)":
  location: bootstrap.py
  annotations: |
    Pure writer of the consumer's test convention file — occupies the `conventions` slot with the pybuggy test
    convention shipped inside the installed package. No TTY, no existence check: always (over)writes `path`.

    `path`: target file path (<cwd>/.goga/usages/conventions.md).

    Algorithm:
    1. Read the packaged asset conventions.md from the installed goga_tool_pybuggy package — never the cwd checkout,
       never the network.
    2. Ensure the parent directory of `path` exists.
    3. Write the asset text to `path`, overwriting unconditionally.

    Requirements:
    - The written content equals the packaged asset text verbatim; output deterministic.

    Constraints:
    - Do not survey or prompt — pure; the delivery gate lives in the bootstrap orchestrator.
    - Do not check for, merge into, or diff an existing file.

    Use `conventions` for type hints, structured logging, and testing.

"ensure_review_skip(config_path: Path) -> changed:bool":
  location: bootstrap.py
  annotations: |
    Round-trip edit of the consumer .goga/config.yml enforcing build.review.skip: true — the flag telling the engine to
    skip the review pass. Pure (no TTY); the bootstrap calls it unconditionally on every pass.

    `config_path`: path to the consumer .goga/config.yml.
    `changed`: true when the flag was added or corrected (file written); false when it already held true.

    Algorithm:
    1. Load the config round-trip when it exists; otherwise start an empty document.
    2. Navigate to build.review, creating each missing mapping level.
    3. When skip already holds true, return false without writing.
    4. Set skip to true, write the document back, log INFO; return true.

    Requirements:
    - The enforced value is exactly true — a present false (or non-boolean) value is corrected.
    - The rest of the config — comments, key order, quotes — is preserved verbatim.
    - Idempotent: when the flag already holds true the file is not written at all.

    Constraints:
    - Do not touch keys outside build.review.skip.
    - Do not prompt — pure; the run gate lives in the bootstrap orchestrator.

    Use `ruamel-yaml` for the round-trip load/modify/dump. Use `conventions` for logging and testing.

"install_pybuggy(dockerfile_path: Path) -> line:str | None":
  location: bootstrap.py
  annotations: |
    Append the pybuggy-install RUN line to the consumer Dockerfile, pinning the version to the installed package's own
    version line so the consumer's test image carries pybuggy.

    `dockerfile_path`: path to the consumer Dockerfile.
    `line`: the appended install line; None when nothing was appended.

    Algorithm:
    1. No-op (return None) when the Dockerfile does not exist — never create the file here.
    2. Derive the install line from the installed package version.
    3. When the line is already present, return None (idempotent).
    4. Ensure the content ends with a newline, append the line, write the file back; log INFO; return the line.

    Requirements:
    - The line installs pybuggy through the goga installer, pinned to the running package version.
    - The existing Dockerfile content is preserved; only the install line is appended.
    - Idempotent within a single Dockerfile.

    Constraints:
    - Do not create the Dockerfile when absent — only augment an existing one.
    - Do not hardcode the version — it is derived from the installed package.

    Use `conventions` for logging and testing.

"register_usages(config_path: Path, usage_keys: dict[str, str]) -> added_keys:list[str]":
  location: bootstrap.py
  annotations: |
    Round-trip edit of the consumer .goga/config.yml under codemanifest.usages: register each entry of `usage_keys`,
    skipping keys already present, and creating a minimal file when none exists.

    `config_path`: path to the consumer .goga/config.yml.
    `usage_keys`: mapping of usage key to the relative path of the usage file to register (pybuggy-<stem> →
    .goga/usages/cooks/pybuggy/<stem>.md; conventions → .goga/usages/conventions.md).
    `added_keys`: the keys actually added (pre-existing keys skipped).

    Algorithm:
    1. Load the config round-trip when it exists; otherwise build a fresh document with the codemanifest.usages map.
    2. For each (key, value): when the key is already present, skip it; otherwise insert it and record the key.
    3. Ensure the parent directory exists and write the document back.
    4. Return the added keys.

    Requirements:
    - Existing keys are never overwritten; comments, key order, and quotes are preserved.

    Constraints:
    - Do not touch keys outside codemanifest.usages.

    Use `ruamel-yaml` for the round-trip edit. Use `conventions` for type hints and testing.

"register_annotations(config_path: Path, annotation_lines: dict[str, str]) -> changed_keys:list[str]":
  location: bootstrap.py
  annotations: |
    Round-trip edit of the consumer .goga/config.yml under codemanifest.annotations: register each annotation line by
    its backtick reference — an identical line is left as-is, a differing line carrying the reference is replaced, a
    missing line is appended. Lines carrying no registered reference are preserved verbatim.

    `config_path`: path to the consumer .goga/config.yml.
    `annotation_lines`: mapping of reference key to one annotation line carrying that backtick reference.
    `changed_keys`: the keys whose line was appended or replaced.

    Algorithm:
    1. Load the config round-trip when it exists; otherwise build a fresh document.
    2. For each (key, line): locate the first text line carrying the reference; not found → append; identical → skip;
       differing → replace.
    3. Write the text back as a literal block scalar under codemanifest.annotations and dump the document.

    Requirements:
    - Idempotent by backtick reference: a repeat run with the same lines changes nothing.

    Constraints:
    - Do not touch keys outside codemanifest.annotations.
    - Do not remove or reorder lines beyond the single replaced line per reference.

    Use `ruamel-yaml` for the round-trip edit and the block-scalar construction. Use `conventions` for testing.

"write_pybuggy_conftest(path: Path)":
  location: bootstrap.py
  annotations: |
    Pure emitter of the target project's root conftest.py from a fixed template — the file that wires the pybuggy
    plugin into the consumer's pytest run. No TTY, no existence check: always (over)writes `path`.

    `path`: target file path (<cwd>/conftest.py).

    The template content is fixed verbatim (a module-level constant): load the environment, then import and install
    the plugin — the environment loads before the plugin import so plugin options resolve from os.environ, and the
    argumentless load keeps override=False so CI-exported variables win.

    Algorithm:
    1. Ensure the parent directory of `path` exists.
    2. Write the fixed template to `path`, overwriting unconditionally.

    Requirements:
    - Output deterministic — no parameterization, no placeholders, no version resolution.

    Constraints:
    - Do not verify the consumer environment — absence surfaces when the consumer runs pytest.

    Use `conventions` for type hints, structured logging, and testing.

---

Author: Goga
CreatedAt: 01/10/26
Description: |
  Init command cell — initializes the consumer's goga project (bare, from a template, or a template upgrade) and
  bootstraps the pybuggy test environment.
```

#### `.usages/init.md` (full content — rewrite the file)

```md
# goga_tool_pybuggy.commands.init — goga project initialization and pybuggy bootstrap

## Domain

The `pybuggy init` command **initializes the goga project** and **bootstraps the pybuggy test environment** in the
directory where it is invoked. It operates in three modes selected by the CLI arguments:

- **bare** (`pybuggy init`) — interactive onboarding of a fresh project; refused (exit 1) when `.goga/` already
  exists — the same already-initialized guard `goga init` applies;
- **template** (`pybuggy init <tpl> [--ref <git-ref>]`) — scaffold a copier-compatible template project first, then
  run the onboarding session and the pybuggy bootstrap with skip-if-exists gates;
- **upgrade** (`pybuggy init --upgrade [--ref <git-ref>]`) — migrate a previously scaffolded project to a newer
  template version; no onboarding.

The audience is the integrator wiring pybuggy into their project (`goga install pybuggy`), and the consumer's goga
agent.

## CLI surface

- `pybuggy init` — bare onboarding.
- `pybuggy init <tpl>` — template onboarding. `<tpl>` is a local path or a git URL of a copier-compatible template
  project, optionally carrying a `#ref` fragment (`https://host/repo.git#v2`).
- `--ref <git-ref>` — overrides the template ref: beats the URL fragment in template mode; sets the migration target
  in upgrade mode.
- `--upgrade` — template migration only (the template source is read from `.goga/scaffold.yml`).

Flag rules (mirroring `goga init`): `<tpl>` and `--upgrade` are mutually exclusive; `--ref` requires `<tpl>` or
`--upgrade`. Violations print an error message and exit with code 1.

The command stays interactive: the onboarding session (the core goga questions plus the pybuggy block) and the
copier TUI (template questions) require a TTY.

## The onboarding session

`pybuggy init` and a native `goga init -t pybuggy` run the **same** engine session with pybuggy invited. The engine
asks the core goga questions and then the pybuggy block under a heading with the tool name; pybuggy never prompts on
its own.

Session semantics that shape the modes:

- An existing `.goga/config.yml` ends the session immediately — no questions, no tool events, no artifacts.
  Whoever created the config first wins; it is never rewritten.
- In bare mode this case is unreachable through the CLI: the already-initialized guard refuses first.
- In template mode it is the expected path when the template brings its own `.goga/config.yml`: the session returns
  at once and only the bootstrap below runs.
- A failing tool contribution is soft: the engine discards it with a warning naming pybuggy and continues; the
  session still returns 0.

Through the session pybuggy delivers three things: its questions (the tool configuration survey), its tool config
file `.goga/tools/pybuggy/config.yml`, and the `build.review.skip: true` amendment. When the core answers carry no
Dockerfile path, pybuggy amends it to `.goga/Dockerfile`.

## The pybuggy bootstrap

After the session (bare and template modes only), the command delivers the files the session does not carry:

| Artifact | Gate |
|---|---|
| `.goga/usages/cooks/pybuggy/<stem>.md` — the packaged api usages | template: skip existing (INFO); bare: overwrite |
| `.goga/usages/conventions.md` — the `conventions` slot | skip-if-exists in both modes |
| `build.review.skip: true` in `.goga/config.yml` | always enforced, idempotent |
| the pybuggy install RUN line in `.goga/Dockerfile` | appended when the file exists, idempotent |
| the pybuggy usage keys and annotation lines in `.goga/config.yml` | always registered, idempotent |
| `conftest.py` at the project root | template: skip existing (INFO); bare: ask, default no |

A Dockerfile missing after the session fails the command with a non-zero exit — pybuggy requires one to carry its
install line.

## Upgrade mode

Only the template migration runs (copier run_update via the `.goga/scaffold.yml` state file); no onboarding prompts
appear, nothing else is written. A template without a persisted answers-file entry leaves `--upgrade` unusable: the
engine reports the missing state file with a non-zero exit, which the command propagates without wrapping. Engine
preconditions (a clean git repository, a git-trackable template, a non-decreasing version) surface as non-zero
exits.

## Programmatic usage (tests/scripts)

`run_init` is the testable entry point: it takes the three CLI values and returns an exit code, never raising.
`run_session` and `run_bootstrap` are the seams behind it — stub them with monkeypatch to avoid the TTY and the
filesystem. `resolve_init_mode` is pure and safe to call directly.
```

#### `.usages/config-build.md` (full content — rewrite the file)

```md
# goga_tool_pybuggy.commands.init — the pybuggy tool configuration survey and contribution

## Domain

The onboarding step that collects the pybuggy tool configuration and delivers it as the tool's session contribution:
the file `.goga/tools/pybuggy/config.yml`. The questions are declared by pybuggy and asked by the goga onboarding
engine — in `pybuggy init` and in a native `goga init -t pybuggy` session alike. The audience is the integrator
wiring pybuggy in, and the consumer's goga agent.

## What is asked

- `base_url` — **required**. A Jinja2 template string rendered once before the test run; a plain URL is a valid
  template that renders to itself.
- The optional scalar plugin keys, one input each, skippable with Enter: `timeout`, `retries`, `assert_timeout`,
  `assert_delay`, `assert_field_class`, `assert_response_class`.
- The first spec, field by field: `name`, `type` (a choice of `swagger` or `openapi`), `location`, and the optional
  git fields `git_url`, `git_location`, `git_ref` — an empty `git_url` means no git source.
- `extra_specs` — optional. Additional specs, one per line, in the compact form:

      name|type|location|git_url|git_location|git_ref

  A line carrying fewer than the three required fields (name, type, location) is malformed. A malformed line is
  skipped with a warning — the rest of the contribution is unaffected. A name colliding with the first spec keeps
  the first spec and warns. The first spec is validated strictly, so at least one spec always lands in the config.

## What is not asked

`headers` and `loader` are never surveyed, and the tool config is serialized as plain YAML — the file carries only
the answered values. The two complex sections stay documented as hand-added examples (add them to the file
yourself when needed):

      # headers:                        # optional section, hand-added: mapping of header name to value/template
      #   X-Api-Key: "{{ API_KEY }}"
      # loader:                         # optional section, hand-added: packages/modules structure
      #   packages: [api]

## The contribution

The answers never touch the filesystem directly — the amendment hook buffers the contribution and the engine
commits it:

- the tool config file `.goga/tools/pybuggy/config.yml` — the specs mapping plus the answered scalar keys
  (unanswered keys are dropped, never written empty);
- the `build.review.skip: true` amendment to the consumer `.goga/config.yml`;
- the dockerfile amendment — when the core answers carry no Dockerfile path, it is amended to `.goga/Dockerfile`.

## Failure and re-run semantics

- An exception raised while building the contribution drops the whole contribution with a warning naming pybuggy —
  the session continues and returns 0; the pybuggy bootstrap then still delivers its own files.
- An existing `.goga/config.yml` ends the session immediately — no questions, no contribution. Whoever created the
  config first wins: the tool config file is never rewritten by a later session.

## Programmatic usage (tests/scripts)

`parse_specs`, `build_config_data`, and `build_config_amendments` are pure mappings from the answer view — test
them directly with dict inputs, no TTY and no filesystem. `pybuggy_questions` is likewise pure: assert the record
shapes and the survey order against the `PluginConfigKeys` members.

## Preconditions and side effects

- Writes `.goga/tools/pybuggy/config.yml` through the engine (the parent directory is created).
- The generated file is valid for configuration loading: `specs` is present with the required entry fields; the
  scalar plugin keys are ignored on loading (extra=ignore).
- The key list is data-driven from `PluginConfigKeys` — no duplication.
```

### Cell 2: `goga_tool_pybuggy` (root) — MODIFIED (revised)

#### CODEMANIFEST — diff against the current file

Header:
- CHANGE the `Imports` entry for `goga_tool_pybuggy/commands/init`: `Types: [init_cmd]` becomes `Types: [init_cmd, declare_pybuggy_session, amend_pybuggy_config]` (Usages `[init, config-build]` unchanged).
- ADD the `Usages` key `goga-onboarding-hooks: .goga/usages/cooks/goga/onboarding/registering-hooks.md`.
- ADD to `Annotations` the line `Use `goga-onboarding-hooks` for the two onboarding action subscriptions and the member contract of the participation moments.`
- ADD to `Annotations` the paragraph `Onboarding participation: the facade callback subscribes one hook per participation moment to the onboarding actions; the declaration hook supplies the tool's questions, the amendment hook its config amendments and tool config file.`

Body:
- REPLACE the annotation of `register_hooks(hooks: object)` (`location: statuses.py`) wholesale — the new text subscribes four hooks (two statuses + declare_session + amend_config) and drops the requirement `Only the two topic-status hooks are subscribed`.
- UNCHANGED: `main`, `load_env`, `EnvContext`, `retries`, `register_automate_statuses`, `register_fix_statuses`, `->install: {}`.

Footer: UNCHANGED.

#### CODEMANIFEST — full resulting content

```yaml
Imports:
  - Types: [pull_cmd]
    Usages: [pull]
    From: goga_tool_pybuggy/commands/pull
  - Types: [list_cmd]
    Usages: [list]
    From: goga_tool_pybuggy/commands/list
  - Types: [info_cmd]
    Usages: [info]
    From: goga_tool_pybuggy/commands/info
  - Types: [generate_cmd]
    Usages: [generate]
    From: goga_tool_pybuggy/commands/generate
  - Types: [diff_cmd]
    Usages: [diff]
    From: goga_tool_pybuggy/commands/diff
  - Types: [init_cmd, declare_pybuggy_session, amend_pybuggy_config]
    Usages: [init, config-build]
    From: goga_tool_pybuggy/commands/init
  - Types: [install]
    Usages: [enable, configuration]
    From: goga_tool_pybuggy/plugin

Usages:
  conventions: .goga/usages/conventions.md
  click: .goga/usages/cooks/click.md
  python-dotenv: .goga/usages/cooks/python-dotenv.md
  goga-hooks: .goga/usages/cooks/goga/hooks/registering-hooks.md
  goga-statuses: .goga/usages/cooks/goga/history/registering-statuses.md
  goga-onboarding-hooks: .goga/usages/cooks/goga/onboarding/registering-hooks.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `click` for the root group, the endpoint subgroup, command registration, the top-level init command, and the global --env-file option with its eager-callback.
  Use `python-dotenv` for loading the .env file into os.environ with override=False.
  Use `goga-hooks` for the facade callback contract, the hook signatures, and the failure behavior of registrations.
  Use `goga-statuses` for the registration surface: register parameters, artifact path semantics, anchors, and skip-with-warning.
  Use `goga-onboarding-hooks` for the two onboarding action subscriptions and the member contract of the participation moments.
  Connected practices describe how consumers use the composed commands and the plugin: `pull`, `list`, `info`, `generate`, `diff`, `init`, `config-build`, `enable`, `configuration`.

  This cell is the package composition root: it owns the root group `main`, loads the .env environment before any subcommand runs, and assembles the full CLI.
  Topic statuses: the facade callback subscribes one hook per pipeline line to the statuses registration action; each hook applies its line through direct registration calls in the normative order.
  Onboarding participation: the facade callback subscribes one hook per participation moment to the onboarding actions; the declaration hook supplies the tool's questions, the amendment hook its config amendments and tool config file.
  Use relative imports inside the cell.

---

"main(env_file: str | None)":
  location: cli.py
  annotations: |
    Root Click group of the pybuggy CLI; exposes the global --env-file option, the endpoint subgroup with the pull/list/info/generate/diff commands, and the top-level init command.

    `env_file`: value of the global --env-file option injected by click (None when the flag is absent).

    Algorithm:
    1. Define the `main` root group via `click`.
    2. Attach the global --env-file option to `main` (eager — evaluated before any subcommand).
    3. In the eager-callback: call `load_env` (passing the --env-file value) and store the returned `EnvContext` on ctx.obj.
    4. Define the endpoint subgroup via `click`.
    5. Register `pull_cmd`, `list_cmd`, `info_cmd`, `generate_cmd`, `diff_cmd` on the endpoint subgroup.
    6. Attach the endpoint subgroup to `main`.
    7. Register `init_cmd` on `main` directly (top-level — not under the endpoint subgroup).
    8. Export `main` via __all__.

    Requirements:
    - The global --env-file flag is parsed at the group level, so it MUST precede the subcommand (e.g. pybuggy --env-file ./my.env endpoint pull); placing it after the subcommand is a click usage error.
    - The env is loaded and ctx.obj is set before any subcommand is invoked.
    - Assembly runs at package import (in __init__.py), before any subcommand is invoked.
    - The package entry point resolves to this `main` (pyproject: pybuggy = "goga_tool_pybuggy:main").
    - python -m goga_tool_pybuggy runs via __main__.py (from goga_tool_pybuggy import main; main()).

    Constraints:
    - Do not introduce a --config option; config loading stays per-command via load_config.
    - --env-file is the only global option of the CLI.

    Use `click` for the group, subgroup, and the --env-file eager-callback.
    Use `python-dotenv` for the .env loading performed by `load_env`.

"load_env(env_file: str | None) -> ctx: EnvContext":
  location: env.py
  annotations: |
    Resolve the env-file, load its key→value pairs into os.environ (override=False), and return an `EnvContext` carrying the resolved path and the loaded values.

    `env_file`: explicit path from --env-file, or None (implicit .env in CWD).
    `ctx`: the `EnvContext` stored on ctx.obj by `main`.

    Algorithm:
    1. Resolve the path: if `env_file` is not None, treat it as explicit — it MUST exist, otherwise raise click.ClickException; if `env_file` is None, use .env in the CWD and, when it is absent, load nothing (silent, no error).
    2. When a resolved file exists, parse it into values (key→value) and apply it to os.environ with override=False (already-set variables are never overwritten) via `python-dotenv`.
    3. Return an `EnvContext` with the resolved path (or None) and the loaded key→value values.

    Requirements:
    - override=False — already-set environment variables are never overwritten.
    - An explicit --env-file must point at a readable regular file; a missing file or a non-regular file (e.g. a directory) raises click.ClickException.
    - An implicit .env that is absent or not a regular file in the CWD is silent (no error, empty values, env_path None).
    - env loading happens before any subcommand runs.

    Constraints:
    - Do not read PYBUGGY_REF or any other specific variable here — loading is generic; consumers read os.environ themselves (directly, or via click's envvar on their options, e.g. pull's --ref).

    Use `python-dotenv` for .env parsing and os.environ application.
    Use `conventions` for code writing rules and testing.

"EnvContext(env_path: str | None, values: dict[str, str])":
  location: env.py
  annotations: |
    Context-object stored on click ctx.obj by `main`; carries the resolved env-file path and the loaded key→value pairs.

    `env_path`: resolved env-file path; None when no file was loaded (silent absent implicit .env).
    `values`: loaded key→value pairs from the env-file.

    Requirements:
    - pydantic model with kw_only=True (all data models are pydantic per `conventions`); defaults env_path=None, values={}.
    - Exposed on the ROOT facade via __all__ (available to consumers/tests).

    Constraints:
    - Pure data carrier — no behavior beyond the two properties.
  properties:
    "env_path -> str | None": |
      Resolved env-file path; None when no file was loaded.
    "values -> dict[str, str]": |
      Loaded key→value pairs from the env-file.

"retries(max_runs: int, *, min_passes: int | None, delay: int | float | None) -> decorator: Callable":
  location: tools.py
  annotations: |
    Decorator-factory that wraps the flaky library to rerun a test up to `max_runs` times, requiring `min_passes` successes, with an optional `delay` between reruns. Exposed on the package facade for consumer test suites.

    `max_runs`: maximum number of test runs (required, positive int)
    `min_passes`: minimum successful runs required for the test to pass; when None, flaky derives its own default
    `delay`: seconds to sleep between reruns; when None, reruns run immediately and no rerun filter is applied
    `decorator`: the flaky decorator to apply to a test function

    Algorithm:
    1. Build a rerun filter: None when `delay` is None; otherwise a callable that sleeps `delay` seconds and returns True (unconditional rerun).
    2. Delegate to flaky with `max_runs`, `min_passes`, and the rerun filter, and return its decorator.

    Requirements:
    - `max_runs` must be a positive int.
    - The rerun filter is wired in only when `delay` is not None, so a None delay never reaches the sleep.

    Constraints:
    - The rerun filter always returns True — reruns are unconditional up to `max_runs`.

    Use `conventions` for code writing rules and testing.

"register_hooks(hooks: object)":
  location: statuses.py
  annotations: |
    Subscribe the pybuggy hooks to the goga hooks platform: the topic-status hooks on the statuses registration
    action and the onboarding participation hooks on the two onboarding actions.

    `hooks`: the subscription surface delivered by the platform.

    Algorithm:
    1. Subscribe `register_automate_statuses` to the statuses registration action under the hook name automate.
    2. Subscribe `register_fix_statuses` to the same action under the hook name fix.
    3. Subscribe `declare_pybuggy_session` to the declare_session onboarding action under the hook name declare.
    4. Subscribe `amend_pybuggy_config` to the amend_config onboarding action under the hook name amend.

    Requirements:
    - The subscription addresses are the statuses domain registration action and the two onboarding actions.
    - Hook names are stable and unique within the tool.
    - The onboarding handlers receive their `context` by name — the platform delivers the values by name.
    - Subscribing to a subset of the actions is legitimate — the moments are independent.
    - Exposed on the ROOT facade via __all__ — the platform imports it from the package root.

    Constraints:
    - Do not subscribe to any action beyond the four named hooks.

    Use `goga-hooks` for the facade callback contract and the failure behavior of registrations.
    Use `goga-statuses` for the registration surface of the status hooks.
    Use `goga-onboarding-hooks` for the member contract of the two participation moments.

"register_automate_statuses(context: object)":
  location: statuses.py
  annotations: |
    Register the automate status line on the topic status scale.

    `context`: the registration surface scoped to the tool.

    Algorithm:
    1. Register the completed-accept status for the completed plan artifact, anchored above the built-in done status.
    2. Register the middle automate statuses in reverse pipeline order — plan, design, arch, testcases, requirements — each anchored above its built-in twin and below the previously registered automate status.

    Requirements:
    - Registration order equals the normative table order; every before anchor names an automate-line entry registered earlier in this run.
    - Artifact paths are relative to the topic directory; nested paths keep their directory part.
    - Registered names carry no tool prefix — the platform assigns the tool identity; anchor values follow the table exactly: built-in anchors are bare, own-status anchors carry the tool prefix.
    - Not part of the package facade — reachable only through the automate hook subscribed by `register_hooks`.

    Normative table (registration order):
    1. automate.done → completed/plan.md — after done
    2. automate.coding-planned → plan.md — after planned, before pybuggy.automate.done
    3. automate.code-designed → design.md — after specified, before pybuggy.automate.coding-planned
    4. automate.arch-prepared → arch.md — after designed, before pybuggy.automate.code-designed
    5. automate.testcases-designed → testcases.md — after backlog, before pybuggy.automate.arch-prepared
    6. automate.requirements-created → requirements.md — after defined, before pybuggy.automate.testcases-designed

"register_fix_statuses(context: object)":
  location: statuses.py
  annotations: |
    Register the fix status line on the topic status scale — an independent chain anchored at the built-in empty status.

    `context`: the registration surface scoped to the tool.

    Algorithm:
    1. Register the fix collect status for the collect artifact, anchored above the built-in empty status.
    2. Register the remaining fix statuses in pipeline order — analyzed, planned, executed, reviewed — each anchored above the previously registered fix status.

    Requirements:
    - Registration order equals the normative table order; every after anchor names an entry registered earlier in this run or a built-in status.
    - Artifact paths are relative to the topic directory.
    - Registered names carry no tool prefix — the platform assigns the tool identity.
    - Not part of the package facade — reachable only through the fix hook subscribed by `register_hooks`.

    Normative table (registration order):
    1. fix.collected → fix-collect.md — after empty
    2. fix.analyzed → fix-analysis.md — after pybuggy.fix.collected
    3. fix.planned → fix-plan.md — after pybuggy.fix.analyzed
    4. fix.executed → fix-execute.md — after pybuggy.fix.planned
    5. fix.reviewed → fix-review.md — after pybuggy.fix.executed

->install: {}

---

Author: Goga
CreatedAt: 08/07/26
Description: |
  Package composition root — owns the root CLI group main, assembles the endpoint subgroup
  (pull/list/info/generate/diff), registers the top-level `init` command, loads the .env environment
  before any command runs, and registers the pybuggy topic statuses on the goga status scale.
```

#### `.usages/assembly.md` — diff (extend the file, do not rewrite it)

**1) The `init` entry in the entry-point list** (was: "Consumer-usages bootstrap (top-level `init`, no options)"):

```md
- Project initialization and bootstrap (top-level `init`, three modes):

      pybuggy init                                  # bare onboarding (refused over an existing .goga/)
      pybuggy init <tpl> [--ref <git-ref>]          # scaffold a template, then onboard
      pybuggy init --upgrade [--ref <git-ref>]      # migrate a scaffolded template only
```

**2) The `register_hooks` subscription table** (was: only the two status hooks) — the lead phrase and the table:

```md
`register_hooks` subscribes four hooks to three addresses — the statuses registration action and the two
onboarding actions:

| Hook name | Callable | Address | Registers |
|-----------|----------|---------|-----------|
| `automate` | `register_automate_statuses` | statuses / register_statuses | the six automate-line statuses (including the completed-accept `automate.done`) |
| `fix` | `register_fix_statuses` | statuses / register_statuses | the five fix-line statuses |
| `declare` | `declare_pybuggy_session` | onboarding / declare_session | the pybuggy question block of the session survey |
| `amend` | `amend_pybuggy_config` | onboarding / amend_config | the `build.review.skip` amendment and the tool config file |

Both status hook callables live in `goga_tool_pybuggy/statuses.py`; both onboarding hook callables live in
`goga_tool_pybuggy/commands/init` — none is re-exported on the package facade, only `register_hooks` is; the
platform reaches them through its subscription. The onboarding handlers return immediately when the session did
not invite pybuggy (`goga init` without `-t pybuggy`).
```

**3) The `init` precondition** (the last Preconditions bullet):

```md
- `init` is a top-level command and does NOT require the pybuggy config: it runs a goga onboarding session with
  pybuggy invited (an existing `.goga/config.yml` ends the session immediately) and then bootstraps the consumer's
  pybuggy environment (packaged usages, `conventions` slot, `build.review.skip`, Dockerfile install line, root
  conftest).
```

#### `.usages/retries.md` — UNCHANGED.

## Dependency Map

```
goga_tool_pybuggy/config ────(SpecEntry, GitEntry; usage `configuration`)────► goga_tool_pybuggy/commands/init
goga_tool_pybuggy/plugin ────(PluginConfigKeys)─────────────────────────────► goga_tool_pybuggy/commands/init
goga_tool_pybuggy/commands/init ──(init_cmd, declare_pybuggy_session,
                                    amend_pybuggy_config; usages `init`, `config-build`)──► goga_tool_pybuggy (root)
goga_tool_pybuggy/plugin ────(install; usages `enable`, `configuration`)────► goga_tool_pybuggy (root)
```

No cycles: `config` and `plugin` import nothing from `commands/init` or the root. Platform facades (`goga.onboarding`,
`goga.scaffold`) are environment dependencies connected through project-level usages only — never cell Imports.

## Verification Checklist

After implementing the `commands/init` cell:
- `goga lint goga_tool_pybuggy/commands/init/` passes; the CODEMANIFEST parses with the three sections in order.
- Every backtick reference inside the CODEMANIFEST resolves to a usage key, an imported type/usage, a local type, or a signature variable.
- The cell facade resolves: `from goga_tool_pybuggy.commands.init import init_cmd, run_init, run_session, declare_pybuggy_session, amend_pybuggy_config, build_config_data, build_config_amendments, parse_specs, resolve_init_mode, run_bootstrap`.
- `run_session` drives the engine session with pybuggy invited; no per-field questionnaire orchestration and no direct generator call remain.
- The tool config file is written only through the buffered contribution; no local YAML emitter for it remains.
- `.usages/init.md` and `.usages/config-build.md` match the delivered content; both are imported by the root CODEMANIFEST.

After implementing the root cell:
- `goga lint goga_tool_pybuggy/` reports no NEW findings: the only accepted residue is the pre-existing
  missing-file error for the `goga-statuses` usage (`registering-statuses.md` absent from the synced tree) —
  that one is tracked for a `goga usages sync` refresh outside this task. `register_hooks` subscribes exactly
  four hooks (two statuses + declare_session + amend_config).
- `goga hooks` shows the two onboarding subscriptions; a native `goga init -t pybuggy` session surveys the pybuggy block, writes `.goga/tools/pybuggy/config.yml`, and amends `build.review.skip: true`.
- `.usages/assembly.md` carries the three extended fragments; `retries.md` untouched.

Project-level checks (later stages):
- `pyproject.toml`: the `test` extra pins `goga>=2.0.1,<2.1`; no goga runtime dependency is added.
- `pytest tests/ -x` green on goga 2.0.1; parity stubs use the 2.0 signatures; an automated smoke test covers `init` + endpoint generate in a temporary directory.
- `MIGRATION.md` exists at the repository root and covers the `build.review_executor.skip` to `build.review.skip` rename and the native `goga init -t pybuggy` path.
- Docs pages no longer describe the 1.x model; `ruff check goga_tool_pybuggy/` is clean.
