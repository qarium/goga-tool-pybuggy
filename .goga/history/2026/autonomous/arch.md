# Architecture Plan — Autonomous runs of the `api.automate` pipeline

Implements the task at `.goga/history/2026/autonomous/task.md` (ADR: `.goga/history/2026/autonomous/adr.md`).

## Topic

**Autonomous runs of `api.automate` (pybuggy autonomy contribution)** — plan path:
`.goga/history/2026/autonomous/arch.md` (printed by `goga history path -f arch.md`).

Non-cell follow-ups tracked by the task (not artifacts of this plan): the docs sections
(`docs/pipelines/api-automate.md` "Autonomous runs", `docs/cli/init.md`) and the test tree
mirroring the source per the project conventions.

## Implementation Order

| # | Cell | Created / Modified | Rationale |
|---|------|--------------------|-----------|
| 1 | `goga_tool_pybuggy/statuses` | **created** | Leaf — no Imports; the root subscribes its hooks. |
| 2 | `goga_tool_pybuggy/config` | **modified** | Leaf — no Imports; grows the pipelines axis and the platform read; consumed by `autonomous` and the command cells. |
| 3 | `goga_tool_pybuggy/autonomous` | **created** | Depends only on `config` (resolve_autonomy + autonomy usage). |
| 4 | `goga_tool_pybuggy/commands/init` | **modified** | Depends on `config`/`plugin` (unchanged edges); grows the autonomy question and the conditional payload key. |
| 5 | `goga_tool_pybuggy` (root) | **modified** | Composition root — imports statuses, autonomous, commands/*, plugin; subscribes all five hooks from `reg_hooks.py`. |

## Artifacts

---

### 1. Cell `goga_tool_pybuggy/statuses` (created)

#### CODEMANIFEST — `goga_tool_pybuggy/statuses/CODEMANIFEST`

```yaml
Usages:
  conventions: .goga/usages/conventions.md
  goga-statuses: .goga/usages/github/goga/history/registering-hooks.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `goga-statuses` for the registration surface: register parameters, artifact path
  semantics, anchors, and skip-with-warning.

  The cell owns the two pybuggy topic-status lines — automate and fix. Each line registers
  through direct registration calls in its normative order; the lines are independent
  chains with no shared statuses. Use relative imports inside the cell.

---

"register_automate_statuses(context: object)":
  location: automate.py
  annotations: |
    Register the automate status line on the topic status scale.

    `context`: the registration surface scoped to the tool.

    Algorithm:
    1. Register the completed-accept status for the completed plan artifact, anchored above
       the built-in done status.
    2. Register the middle automate statuses in reverse pipeline order — plan, design, arch,
       testcases, requirements — each anchored above its built-in twin and below the
       previously registered automate status.

    Requirements:
    - Registration order equals the normative table order; every anchor names an entry
      registered earlier in this run or a built-in status.
    - Artifact paths are relative to the topic directory; nested paths keep their directory part.
    - Registered names carry no tool prefix — the platform assigns the tool identity.

    Normative table (registration order):
    1. automate.done → completed/plan.md — after done
    2. automate.coding-planned → plan.md — after planned, before pybuggy.automate.done
    3. automate.code-designed → design.md — after specified, before pybuggy.automate.coding-planned
    4. automate.arch-prepared → arch.md — after designed, before pybuggy.automate.code-designed
    5. automate.testcases-designed → testcases.md — after backlog, before pybuggy.automate.arch-prepared
    6. automate.requirements-created → requirements.md — after defined, before pybuggy.automate.testcases-designed

    Use `goga-statuses` for the register parameters and the anchor semantics.

"register_fix_statuses(context: object)":
  location: fix.py
  annotations: |
    Register the fix status line on the topic status scale — an independent chain anchored
    at the built-in empty status.

    `context`: the registration surface scoped to the tool.

    Algorithm:
    1. Register the fix collect status for the collect artifact, anchored above the built-in
       empty status.
    2. Register the remaining fix statuses in pipeline order — analyzed, planned, executed,
       reviewed — each anchored above the previously registered fix status.

    Requirements:
    - Registration order equals the normative table order; every anchor names an entry
      registered earlier in this run or a built-in status.
    - Artifact paths are relative to the topic directory.
    - Registered names carry no tool prefix — the platform assigns the tool identity.

    Normative table (registration order):
    1. fix.collected → fix-collect.md — after empty
    2. fix.analyzed → fix-analysis.md — after pybuggy.fix.collected
    3. fix.planned → fix-plan.md — after pybuggy.fix.analyzed
    4. fix.executed → fix-execute.md — after pybuggy.fix.planned
    5. fix.reviewed → fix-review.md — after pybuggy.fix.executed

    Use `goga-statuses` for the register parameters and the anchor semantics.

---

Author: Goga
CreatedAt: 02/10/26
Description: |
  Topic-status registration cell — the automate and fix status lines of the pybuggy tool.
```

#### .usages — `goga_tool_pybuggy/statuses/.usages/registration.md` (created)

```md
# statuses — subscribing the pybuggy status lines

## Domain

Consumption patterns of the cell `goga_tool_pybuggy/statuses/`: the two topic-status
registration hooks that place pybuggy's automate and fix status lines on a topic's status
scale. Target audience: the package registration surface that subscribes platform hooks,
and maintainers wiring additional status lines.

## What the cell provides

- `register_automate_statuses(context)` — registers the automate line: the completed-accept
  status anchored at the built-in done status, plus the middle statuses in reverse pipeline
  order (plan, design, arch, testcases, requirements).
- `register_fix_statuses(context)` — registers the fix line: an independent chain anchored at
  the built-in empty status (collected, analyzed, planned, executed, reviewed).

## Subscribe from the registration surface

```python
from goga_tool_pybuggy.statuses import register_automate_statuses, register_fix_statuses


def register_hooks(hooks):
    hooks.subscribe("statuses", "register_statuses", "automate", register_automate_statuses)
    hooks.subscribe("statuses", "register_statuses", "fix", register_fix_statuses)
```

- Hook names are local to the tool; `automate` and `fix` are the stable names.
- Each hook receives its registration surface by the parameter name `context`.
- The moments are independent — subscribing to a subset is legitimate.

## Preconditions and side effects relevant to the consumer

- Registration order inside each hook is normative — the consumer never reorders or filters
  the calls.
- Both lines are add-only registrations against built-in statuses; a skipped registration
  (unresolvable anchor) logs a warning and never aborts the command.
- Statuses show qualified as `pybuggy.<name>` — the platform assigns the tool identity.
```

---

### 2. Cell `goga_tool_pybuggy/config` (modified)

Modification summary:
- **add** — type `PipelineAutonomy` (`pipeline_autonomy.py`), type `resolve_autonomy` (`storage.py`), usage file `.usages/autonomy.md`;
- **change** — `load_config` signature narrowed to `load_config() -> config: Config` with the platform raw read and the absent-file clean error; header loses the inline `pyyaml` practice and gains `goga-tool-config`; global annotations updated to the current state; footer Description updated;
- **delete** — the `CONFIG_PATH` constant and its facade export on the config cell `__all__` — the platform facade owns the location; the absent-file error names the platform-standard location;
- **unchanged** — `GitEntry`, `SpecEntry`, `Config`, `.usages/configuration.md` stays (content updated).

#### CODEMANIFEST — `goga_tool_pybuggy/config/CODEMANIFEST` (current state in full)

```yaml
Usages:
  conventions: .goga/usages/conventions.md
  goga-tool-config: .goga/usages/github/goga/config/tool-configuration.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `goga-tool-config` for reading the tool config file through the platform facade.

  All pydantic models use kw_only=True (Python 3.10+).
  Use typing.Optional (not X | None) for fields meaning explicit absence.
  Use relative imports inside the cell.
  The tool config file is the single source of both reading routines: each obtains the raw
  parse through the platform facade; the platform import resolves at call time so goga
  never becomes a runtime dependency.

---

"GitEntry(url: str, location: str, ref: Optional[str])":
  location: git_entry.py
  annotations: |
    Remote source of a spec — clone URL, in-repo path, and optional git ref.

    `url`: clone URL consumed by the consumer's shallow-clone flow (no embedded tokens).
    `location`: path inside the repository (file or subdirectory) to copy from.
    `ref`: optional git ref (branch or tag name) to clone; when None the remote default branch is cloned.

    Use `conventions` for pydantic model rules.

  Requirements:
    - `ref` is Optional — when None the consumer clones the remote default branch.

  Constraints:
    - `url` must be a valid clone target for GitPython (no embedded tokens).
    - `ref` should be a branch or tag name; a bare commit SHA is not guaranteed to resolve under a shallow clone.

"SpecEntry(type: Literal['swagger','openapi'], location: str, git: Optional[GitEntry])":
  location: spec_entry.py
  annotations: |
    One spec entry of the pybuggy config: declared format, local path, and optional remote source.

    `type`: declared spec format — constrained to 'swagger'/'openapi' via Literal; pydantic rejects other values at validation time.
    `location`: local path (from project root) to the spec file — shown in the consumer's list output and used as the copy target.
    `git`: optional remote source; when absent the spec is treated as local-only and the consumer skips it silently.

    Use `conventions` for pydantic model rules.

  Requirements:
    - `git` is Optional — a spec may already be present locally without a remote.

  Constraints:
    - `type` declares the format but does not drive parsing — Prance auto-detects the version at parse time.

"Config(specs: dict[str, SpecEntry])":
  location: config.py
  annotations: |
    Root configuration of pybuggy, stored at .goga/tools/pybuggy/config.yml.

    `specs`: mapping of spec name to its `SpecEntry`; the name is the dict key, surfaced by consumers.

    Use `conventions` for pydantic model rules.

  Constraints:
    - `specs` is required — a config without specs is invalid.

"load_config() -> config: Config":
  location: storage.py
  annotations: |
    Read the pybuggy tool config and validate it into a `Config` model.

    `config`: the parsed and validated configuration.

    Algorithm:
    1. Read the raw content of the tool config file through the platform facade.
    2. When the file is absent, fail with a clean error naming the tool config location.
    3. Validate the raw mapping into `Config`.

    Requirements:
    - The file location follows the platform path standard for tool configs.
    - The platform facade import resolves at call time — goga stays out of the runtime
      dependencies.

    Use `goga-tool-config` for the facade contract and the absence semantics.
    Use `conventions` for pydantic validation rules.

"PipelineAutonomy(autonomous: bool)":
  location: pipeline_autonomy.py
  annotations: |
    One entry of the `pipelines` axis of the tool config: the autonomy flag of a single
    pipeline name.

    `autonomous`: whether the pipeline runs unattended.

    Requirements:
    - pydantic model with kw_only=True.
    - The record admits exactly the `autonomous` member — a key outside the member set
      fails validation (a mistyped key must surface, not silently disable autonomy).

    Use `conventions` for pydantic model rules.
  properties:
    "autonomous -> bool": |
      Whether the pipeline named by the entry's dict key runs unattended.

"resolve_autonomy(pipeline: str) -> enabled: bool":
  location: storage.py
  annotations: |
    Resolve whether autonomy is enabled for the running pipeline, validating the whole
    `pipelines` axis of the tool config on the way.

    `pipeline`: the identity of the running pipeline.
    `enabled`: True only when the axis carries an enabling entry for `pipeline`.

    Algorithm:
    1. Read the raw content of the tool config file through the platform facade.
    2. When the file is absent or holds no `pipelines` section, return False.
    3. Validate the axis: every entry must be a mapping validatable into `PipelineAutonomy`.
    4. Look up `pipeline` in the axis: an absent name returns False; a present name returns
       its `autonomous` value.

    Requirements:
    - A structural violation — a non-mapping `pipelines`, a non-mapping entry, or a record
      not validatable into `PipelineAutonomy` — fails with a clean error naming pybuggy.
    - Absent file, absent section, absent name, and `autonomous: false` all mean disabled.
    - Names other than `pipeline` are ignored — the axis is permissive toward unknown
      pipeline names.

    Constraints:
    - Do not interpret config sections other than `pipelines`.
    - Do not cache the read — each call obtains a fresh raw parse.

    Use `goga-tool-config` for the facade contract and the absence semantics.
    Use `conventions` for pydantic validation rules.

---

Author: Goga
CreatedAt: 02/07/26
Description: |
  pybuggy configuration models and reading routines for .goga/tools/pybuggy/config.yml —
  the specs schema and the pipelines autonomy axis.
```

#### .usages — `goga_tool_pybuggy/config/.usages/configuration.md` (updated, current state in full)

```md
# goga_tool_pybuggy.config — Configuration Loading

## Domain

Cell `goga_tool_pybuggy/config` provides consumption patterns for loading `.goga/tools/pybuggy/config.yml` into typed models and accessing spec entries. Target audience: consumer commands and the CLI facade.

## Loading the configuration

```python
from goga_tool_pybuggy.config import load_config

config = load_config()  # the fixed location .goga/tools/pybuggy/config.yml
```

The `load_config` function obtains the raw parse of the tool config file through the goga tool-config facade and validates the result into the `Config` model. An absent file fails with a clean error naming the tool config location; an invalid configuration raises a pydantic validation error.

## Accessing spec entries

```python
for name, entry in config.specs.items():
    location = entry.location  # project-root-relative path to the spec file
    git = entry.git  # Optional[GitEntry]; None → local spec
    clone_url = git.url  # clone URL (no embedded tokens)
    repo_path = git.location  # path inside the repository
    repo_ref = git.ref  # Optional[str]; branch/tag to clone; None → default branch
```

- `name` (the dict key) is used by consumers for output and for the `--spec` filter.
- `entry.git` can be `None` — the consumer treats such a spec as local and skips it with a WARNING.
- `git.ref` is the default ref for cloning; the consumer can override it with the `--ref` option (priority order: `--ref` > `git.ref` > default branch).

## Preconditions

- The file location follows the platform path standard for tool configs (`.goga/tools/<tool>/<filename>`); the platform resolves it.
- The `type` field is declarative — it does not affect parsing (Prance auto-detects the version).
```

#### .usages — `goga_tool_pybuggy/config/.usages/autonomy.md` (created)

```md
# goga_tool_pybuggy.config — Pipeline Autonomy Resolution

## Domain

Cell `goga_tool_pybuggy/config` resolves the `pipelines` axis of `.goga/tools/pybuggy/config.yml`: which pipeline names run unattended. Target audience: workflow-amendment consumers that gate their contribution on the autonomy flag.

## The config axis

```yaml
pipelines:
  api.automate:
    autonomous: true
```

- The key axis is per pipeline name; an entry carries exactly one boolean member `autonomous`.
- Absent file, absent `pipelines` section, absent name, and `autonomous: false` all mean disabled.

## Resolve autonomy for the running pipeline

```python
from goga_tool_pybuggy.config import resolve_autonomy

enabled = resolve_autonomy("api.automate")  # bool
```

- The whole axis is validated on every call; a structural violation (a non-mapping `pipelines` or entry, a record not matching the entry shape) raises a clean error naming pybuggy — call it from the amendment moment so the failure surfaces as the platform's clean stop.
- Unknown pipeline names are ignored — entries for other pipelines never fail the call.
- No caching: each call obtains a fresh raw parse.

## Preconditions

- The raw file content is obtained through the goga tool-config facade; interpreting the axis is this cell's consumer-side contract.
```

---

### 3. Cell `goga_tool_pybuggy/autonomous` (created)

#### CODEMANIFEST — `goga_tool_pybuggy/autonomous/CODEMANIFEST`

```yaml
Imports:
  - Types:
      - resolve_autonomy
    Usages:
      - autonomy
    From: goga_tool_pybuggy/config

Usages:
  conventions: .goga/usages/conventions.md
  goga-pipeline-hooks: .goga/usages/github/goga/pipeline/registering-hooks.md
  goga-workflow-document: .goga/usages/github/goga/pipeline/workflow/parse-workflow.md
  goga-compile-flow: .goga/usages/github/goga/pipeline/compiler/compile-flow.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `goga-pipeline-hooks` for the amendment moment: the view reads, the contribute
  buffer, and the failure behavior.
  Use `goga-workflow-document` for the instruction vocabulary of the contributed document.
  Use `goga-compile-flow` for the compiled effects of the directives and the stage-body
  key translation.

  The cell owns the autonomous-run contribution: when the running pipeline is api.automate
  and autonomy is enabled in the tool config, it contributes the fixed auto-approval window
  and the build stage; every other run stays silent. Autonomy ends at commit-changes — the
  acceptance stage stays interactive. The stage window and the build entry are compile-time
  constants of the package. Use relative imports inside the cell.

---

"amend_workflow(context: object)":
  location: amendment.py
  annotations: |
    Contribute the autonomous workflow amendment when the run qualifies for autonomy.

    `context`: the amendment view delivered by the platform — the identity of the running
    pipeline and the contribute buffer.

    Algorithm:
    1. Read the identity of the running pipeline from `context`.
    2. Resolve autonomy for that identity via `resolve_autonomy`.
    3. When autonomy is disabled, return without contributing — a silent no-op.
    4. When autonomy is enabled, build the contribution via `build_autonomous_workflow`
       and buffer it through `context`.

    Requirements:
    - The no-op branch contributes nothing and raises nothing.
    - Any error raised here propagates — the platform stops the command with a clean error
      naming pybuggy and discards the whole contribution.

    Constraints:
    - Do not catch errors to force the no-op branch — autonomy never disables silently.
    - Do not read or alter the authored workflow — merge precedence belongs to the platform.
    - Do not touch stage prompts, skills, or the acceptance stage.

    Use `goga-pipeline-hooks` for the view contract and the contribute semantics.
    Use `autonomy` for the resolver consumption pattern.
    Use `conventions` for logging and testing.

"build_autonomous_workflow() -> document: dict[str, object]":
  location: workflow.py
  annotations: |
    Build the declarative autonomy contribution from the package compile-time constants.

    `document`: the WorkflowDocument-shaped contribution — the auto-approval window and
    the build stage.

    Algorithm:
    1. Build the stages mapping: each stage of the fixed window — review-testcases,
       create-testcases, code-design, design-review, coding-plan, plan-review,
       commit-changes — carries the auto-approval directive.
    2. Build the extend entry for the build stage: positioned after commit-changes, the
       body carrying the build title, the script that runs the goga build of the topic's
       plan.md, the after-script cleanup of the .ralphex scratch tree, and the eight-hour
       timeout.
    3. Return the document mapping.

    Requirements:
    - The window and the build entry are compile-time constants of the package.
    - The document uses only the WorkflowDocument instruction vocabulary.
    - Deterministic and pure — identical output on every call.

    Constraints:
    - Do not emit per-stage prompt or description directives and do not modify stage
      skills — autonomy is purely the workflow-level instruction.
    - Do not emit directives for the acceptance stage — it stays interactive and
      manually launched.
    - No platform calls and no I/O.

    Use `goga-workflow-document` for the accepted document structure and the extend-entry
    keys.
    Use `goga-compile-flow` for the compiled effects of the directives.
    Use `conventions` for type hints and testing.

---

Author: Goga
CreatedAt: 02/10/26
Description: |
  Autonomy contribution cell — the autonomous workflow amendment of a qualifying run.
```

#### .usages — `goga_tool_pybuggy/autonomous/.usages/contribution.md` (created)

```md
# autonomous — the autonomy contribution moment

## Domain

Consumption patterns of the cell `goga_tool_pybuggy/autonomous/`: the workflow-amendment
hook that contributes pybuggy's autonomous-run instructions to a qualifying run. Target
audience: the package registration surface that subscribes platform hooks, and maintainers
extending the contribution.

## What the cell provides

- `amend_workflow(context)` — the amendment moment: resolves autonomy for the running
  pipeline and contributes the document when enabled; a silent no-op otherwise.
- `build_autonomous_workflow()` — the pure builder of the contributed document: the
  seven-stage auto-approval window (review-testcases, create-testcases, code-design,
  design-review, coding-plan, plan-review, commit-changes) and the build stage added after
  commit-changes (the topic plan build, eight-hour timeout, scratch-tree cleanup). The
  acceptance stage is never part of the contribution.

## Subscribe from the registration surface

```python
from goga_tool_pybuggy.autonomous import amend_workflow


def register_hooks(hooks):
    hooks.subscribe("pipeline", "amend_workflow", "autonomy", amend_workflow)
```

- The hook name is local to the tool; `autonomy` is the stable name.
- The hook receives its amendment view by the parameter name `context`.

## Preconditions and side effects relevant to the consumer

- Autonomy is enabled per pipeline name in the tool config `pipelines` axis; the hook is a
  silent no-op for every other pipeline and for every disabled configuration.
- A raised error inside the hook stops the command with a clean error naming pybuggy — the
  consumer never wraps the hook in error suppression.
- An authored project workflow wins per slot over the contribution — a project can
  re-enable interaction for any window stage or displace the build stage.
```

---

### 4. Cell `goga_tool_pybuggy/commands/init` (modified)

Modification summary:
- **add** — `autonomy` to `Imports.Usages` of the `config` edge; Algorithm step 4 + Requirements line in `pybuggy_questions`; Algorithm step 3–4 + axis Requirements line in `build_config_data`; the autonomy entries in `.usages/config-build.md`;
- **change** — nothing else;
- **delete** — nothing;
- **unchanged** — global Annotations, the other 17 contracts, footer, `.usages/init.md`.

#### CODEMANIFEST — `goga_tool_pybuggy/commands/init/CODEMANIFEST` (current state in full)

```yaml
Imports:
  - Types:
      - SpecEntry
      - GitEntry
    Usages:
      - configuration
      - autonomy
    From: goga_tool_pybuggy/config
  - Types:
      - PluginConfigKeys
    From: goga_tool_pybuggy/plugin

Usages:
  conventions: .goga/usages/conventions.md
  click: .goga/usages/cooks/click.md
  ruamel-yaml: .goga/usages/cooks/ruamel-yaml.md
  goga-scaffold: .goga/usages/github/goga/scaffold/scaffold-usage.md
  goga-onboarding: .goga/usages/github/goga/onboarding/onboarding-usage.md
  goga-onboarding-hooks: .goga/usages/github/goga/onboarding/registering-hooks.md
  goga-onboarding-questions: .goga/usages/github/goga/onboarding/questions/question-records.md
  goga-onboarding-generator: .goga/usages/github/goga/onboarding/generator/artifact-generation.md

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
  the pybuggy block are surveyed by the engine, the core convention section is skipped (the pybuggy session never
  offers the goga base-convention download — the `conventions` slot is the bootstrap's delivery), and the additional
  specs are surveyed by the tool itself at the amendment moment — a confirm-gated repeated group is beyond the
  declarative engine records. The tool config file and the config amendments are committed through the participation
  mechanism; an existing .goga/config.yml ends the session immediately and is never rewritten. The bootstrap owns
  the pybuggy files the session does not carry: the packaged usages copy, the tool-config example documentation,
  the `conventions` slot, the build.review.skip enforcement, the Dockerfile install line, the usage and annotation
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
    3. Document the absent plugin members of .goga/tools/pybuggy/config.yml as commented example records via
       `document_config_examples` — idempotent; a no-op when the session wrote no tool config.
    4. Deliver the `conventions` slot: when .goga/usages/conventions.md does not exist, call `write_test_convention`;
       when it exists, log INFO and leave the file untouched.
    5. Enforce build.review.skip: true via `ensure_review_skip` — idempotent; runs on every pass, including when the
       session ended immediately on an existing config.
    6. Resolve the Dockerfile path from the consumer config dockerfile field (fallback .goga/Dockerfile), then
       augment it via `install_pybuggy` — idempotent; a no-op when the file is absent.
    7. Register the usage keys via `register_usages` and the annotation lines via `register_annotations` — idempotent.
    8. Deliver the root conftest: when conftest.py does not exist, call `write_pybuggy_conftest`; when it exists —
       template mode: log INFO and skip; bare mode: ask via click.confirm (default no) and overwrite only on yes.
    9. Verify the Dockerfile exists; when it does not, log ERROR and return non-zero.
    10. Return 0.

    Requirements:
    - After every successful run the consumer config carries build.review.skip: true; the pybuggy usage keys and
      annotation lines are registered; the packaged usages are copied; the tool config carries the commented examples
      of its absent optional members (when the session wrote it); the `conventions` slot is occupied when it was
      absent; the root conftest exists.
    - The pure writers always (over)write when called — every existence check and confirmation lives here.
    - Every step is idempotent; a repeat run changes nothing.
    - A write failure in any step is logged (ERROR) and fails the command with a non-zero exit.

    Constraints:
    - Do not copy usages of internal development cells (config, spec, output, matchcrest, plugin, commands).
    - Do not merge into an existing conftest — either a confirmed overwrite (bare) or a skip.
    - Do not prompt about existing files in template mode — the template expresses the user's intent.
    - Do not create the Dockerfile when the engine did not write it — report and fail.

    Use `write_test_convention`, `document_config_examples`, `ensure_review_skip`, `install_pybuggy`,
    `register_usages`, `register_annotations`, `write_pybuggy_conftest`. Use `click` for the bare-mode gates.
    Use `conventions` for logging and testing.

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
    engine surveys it after the core questions, under a heading with the tool identity, and skip the core convention
    section.

    `context`: the declaration surface delivered by the platform.

    Algorithm:
    1. Return immediately when the session did not invite this tool.
    2. Declare every item of `pybuggy_questions` on the context.
    3. Skip the core convention section — a pybuggy session never offers the goga base-convention download; the
       `conventions` slot is delivered by the bootstrap with the packaged pybuggy test convention.

    Requirements:
    - The no-invitation branch calls nothing — the contract rule of the moment.
    - Local question names are unique among siblings; the engine qualifies them with the tool identity.
    - The skip no-ops with an engine warning when the section is already absent (an existing conventions file).

    Constraints:
    - Do not survey, prompt, or read answers — the engine asks the declared records itself.

    Use `pybuggy_questions`. Use `goga-onboarding-hooks` for the member contract of the moment.
    Use `goga-onboarding-questions` for the record shapes.

"amend_pybuggy_config(context: object)":
  location: session.py
  annotations: |
    Amendment moment of the participation contract: survey the additional specs, read the isolated answer view, and
    buffer the pybuggy contribution — the config amendments and the tool config file.

    `context`: the amendment surface delivered by the platform.

    Algorithm:
    1. Return immediately when the session did not invite this tool.
    2. Read the answer view from the context (the survey never touches it — the two reads are
       independent).
    3. Survey the additional specs via `survey_extra_specs` (the confirm-gated per-field follow-up).
    4. Buffer every entry of `build_config_amendments` as a config amendment.
    5. Buffer the tool config file with `build_config_data`.

    Requirements:
    - The answer view carries the core answers plus this tool's own answers under local names.
    - An exception raised here — including a cancelled extra-spec prompt — drops the whole contribution with a warning
      naming the tool; the session continues.

    Constraints:
    - Do not write files directly — the engine serializes and writes the buffered config.
    - Do not read another tool's answers — they are never visible.

    Use `survey_extra_specs`, `build_config_amendments`, `build_config_data`. Use `goga-onboarding-hooks` for the
    member contract and the failure behavior. Use `goga-onboarding-generator` for the buffered file serialization.

"pybuggy_questions() -> items:list[Question]":
  location: session.py
  annotations: |
    Build the declarative pybuggy question block — the survey of the tool configuration, asked by the engine.

    `items`: the question records of the block, in survey order.

    Algorithm:
    1. Declare base_url as a required input — a Jinja2 template string.
    2. Declare every scalar member of `PluginConfigKeys` except BASE_URL, HEADERS, and LOADER as an optional input,
       each prompt stating what the field is for (BASE_URL is the required base_url input of step 1).
    3. Declare the first-spec group: name (input), type (choice swagger|openapi), location (input), and the optional
       git fields (input; an empty git url means no git source).
    4. Declare the autonomy confirm — a boolean question, defaulting to disabled, asked last: whether the
       api.automate pipeline runs unattended.

    Requirements:
    - The block holds exactly one nesting level — groups carry simple children only.
    - base_url is required and its answer is a Jinja2 template; the remaining scalars are optional.
    - The first-spec group makes at least one spec structurally unavoidable: its answer is always recorded.
    - The autonomy question defaults to disabled; its boolean answer is recorded on every survey.

    Constraints:
    - Do not survey HEADERS or LOADER — the bootstrap documents them as commented example records in the tool config.
    - Do not declare a compact additional-specs record — the additional specs are surveyed by `survey_extra_specs` at
      the amendment moment (a confirm-gated repeated group is beyond the declarative records).
    - Do not duplicate plugin key names — iterate `PluginConfigKeys`.

    Use `goga-onboarding-questions` for the record kinds and the nesting rule. Use `PluginConfigKeys` for the scalar
    key set. Use `autonomy` for the axis the answer gates. Use `conventions` for type hints and testing.

"survey_extra_specs() -> specs:list[dict[str, object]]":
  location: session.py
  annotations: |
    Interactively survey the additional specs — the confirm-gated per-field follow-up of the pybuggy block, asked by
    the tool at the amendment moment (right after the engine survey asked the first-spec group).

    `specs`: the surveyed specs — one mapping per accepted spec, keyed by the first-spec field names.

    Algorithm:
    1. Ask "Add another spec?" as a confirm (default no); a decline ends the survey with no specs.
    2. For each accepted spec ask the fields in the first-spec order: name (required — an empty entry re-asks with a
       required prompt), type (a swagger|openapi choice), location (required — re-asked when empty), then the optional
       git fields (input; an empty git url means no git source, an empty git ref the default branch).
    3. Repeat the confirm after every accepted spec until declined; return the collected mappings.

    Requirements:
    - The prompt texts mirror the first-spec group so both surveys read as one flow.
    - Required fields are validated at the prompt — an empty name or location never reaches the payload.

    Constraints:
    - Do not validate spec semantics here — `parse_specs` owns the entry assembly.
    - Do not catch click.Abort — a cancelled prompt propagates so the engine mediator drops the whole contribution
      with a warning (the session continues).

    Use `conventions` for logging-free TTY practices and testing.

"build_config_data(answers: dict[str, object], extra_specs: list[dict[str, object]] | None) -> data:dict[str, object]":
  location: session.py
  annotations: |
    Pure mapping of the tool answer view into the tool config file payload: the specs mapping, the answered scalar
    keys, and the conditional pipelines axis entry.

    `answers`: the tool answer view — the block answers under local names.
    `extra_specs`: the `survey_extra_specs` mappings; None when the gate was declined.
    `data`: the serializable payload of .goga/tools/pybuggy/config.yml.

    Algorithm:
    1. Build the specs mapping via `parse_specs` from the first-spec group answer and the surveyed extra specs.
    2. Collect the answered scalar keys from the `PluginConfigKeys` members, dropping unanswered ones.
    3. Read the autonomy answer; when it enables autonomy, add the pipelines axis entry — the api.automate record
       with autonomous true.
    4. Return the payload: the specs mapping plus the active scalar keys and, when enabled, the axis entry.

    Requirements:
    - The payload satisfies the config schema (see `configuration`): a specs mapping whose entries carry the required
      fields; the scalar plugin keys are ignored on loading.
    - The axis entry matches the pipelines contract (see `autonomy`); the entry is absent on a disabling or absent
      answer — existing projects stay untouched until the user opts in.
    - The payload is plain serializable data — the engine writes the YAML.

    Constraints:
    - Do not prompt or touch the filesystem — pure.
    - Do not emit commented records — the commented examples of the absent members are added by
      `document_config_examples` in the bootstrap.

    Use `parse_specs`. Use `PluginConfigKeys` for the scalar key set. Use `configuration` for schema compatibility.
    Use `autonomy` for the axis shape. Use `conventions` for type hints and testing.

"build_config_amendments() -> amendments:dict[str, object]":
  location: session.py
  annotations: |
    Pure mapping into the buffered config amendments of the consumer .goga/config.yml.

    `amendments`: the amendment paths and values.

    Algorithm:
    1. Amend build.review.skip to true — the review pass is skipped in pybuggy-initialized projects.

    Requirements:
    - The amendments are path→value pairs the platform merges into the answer space before generation.
    - The build.review.skip amendment is the tool's declared intent in the session answer space: the engine
      config mapper emits only agent/env for the build block, so the flag reaches the consumer config through
      `ensure_review_skip` of the bootstrap — the single enforcement point.

    Constraints:
    - Do not amend keys outside the named path.
    - Do not write the config file — amendments are buffered on the context.

    Use `goga-onboarding-hooks` for the amendment semantics. Use `conventions` for type hints and testing.

"parse_specs(spec_answers: dict[str, object], extra_specs: list[dict[str, object]] | None) -> specs:dict[str, SpecEntry]":
  location: session.py
  annotations: |
    Pure, lenient assembly of the specs mapping: the first-spec group answer plus the surveyed extra specs.

    `spec_answers`: the first-spec group answer under local names.
    `extra_specs`: the `survey_extra_specs` mappings; None when the gate was declined.
    `specs`: the specs mapping keyed by spec name.

    Algorithm:
    1. Validate the first spec strictly — a non-empty name, a type of swagger or openapi, a non-empty location — and
       build its `SpecEntry`, attaching a `GitEntry` when the git url and location are present.
    2. For every surveyed extra mapping: build its `SpecEntry`; a malformed record (unreachable through the prompt
       validation) is skipped with a WARNING; a well-formed record lands under its name.
    3. Return the mapping.

    Requirements:
    - The mapping always holds at least the first spec.
    - A spec name collision between the first spec and a surveyed extra keeps the first spec and warns.
    - An absent git url yields no git block.

    Constraints:
    - Do not fail the whole contribution on a malformed extra record — skip it and warn.
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

"document_config_examples(config_path: Path) -> documented:list[str]":
  location: bootstrap.py
  annotations: |
    Round-trip edit of .goga/tools/pybuggy/config.yml documenting the absent plugin members as commented example
    records — the option surface the engine's plain serialization does not carry.

    `config_path`: path to the tool config file.
    `documented`: the record texts added; empty when nothing was added.

    Algorithm:
    1. No-op (return an empty list) when the file is absent or holds no mapping.
    2. Walk the `PluginConfigKeys` members in declaration order; a member absent as an active key whose record marker
       is not already in the file text accumulates its example record (the headers/loader complex blocks, the
       optional scalars as skipped records).
    3. Pin the accumulated records, in walk order, before the next active key via the before-comment — specs is the
       terminal anchor — so every record sits where its key would appear.
    4. Write the document back only when at least one record was added.

    Requirements:
    - Idempotent by marker detection: a repeat run over its own output adds nothing.
    - Active keys and their values are never modified — only comments are added.
    - A member the user activated keeps its active key and is never documented.

    Constraints:
    - Do not create the file when absent — only document an existing tool config.
    - Do not touch keys or comments beyond the added records.

    Use `PluginConfigKeys` for the member walk. Use `ruamel-yaml` for the round-trip edit. Use `conventions` for
    testing.

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
    2. Derive the install line from the installed package version; an unreadable distribution metadata (a
       metadata-less source-tree run) raises ValueError — the caller's wrapped tier maps it to a clean ERROR and a
       non-zero exit, never a raw traceback.
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

#### .usages — `goga_tool_pybuggy/commands/init/.usages/config-build.md` (updated, current state in full)

```md
# goga_tool_pybuggy.commands.init — the pybuggy tool configuration survey and contribution

## Domain

The onboarding step that collects the pybuggy tool configuration and delivers it as the tool's session contribution:
the file `.goga/tools/pybuggy/config.yml`. The questions are declared by pybuggy and asked by the goga onboarding
engine — in `pybuggy init` and in a native `goga init -t pybuggy` session alike. The additional specs are the one
exception: a confirm-gated repeated group is beyond the declarative engine records, so pybuggy asks them itself at
the amendment moment, right after the engine survey. The audience is the integrator wiring pybuggy in, and the
consumer's goga agent.

## What is asked

- `base_url` — **required**. A Jinja2 template string rendered once before the test run; a plain URL is a valid
  template that renders to itself.
- The optional scalar plugin keys, one input each, skippable with Enter: `timeout`, `retries`, `assert_timeout`,
  `assert_delay`, `assert_field_class`, `assert_response_class`.
- The first spec, field by field: `name`, `type` (a choice of `swagger` or `openapi`), `location`, and the optional
  git fields `git_url`, `git_location`, `git_ref` — an empty `git_url` means no git source.
- `autonomous` — **asked last**. A confirm (default no): enable the autonomous runs of the `api.automate` pipeline.
- The additional specs, asked by pybuggy at the amendment moment: `Add another spec?` (confirm, default no) gates
  the block; each accepted spec is asked field by field in the first-spec order (`name` required and re-asked when
  empty, `type` a swagger/openapi choice, `location` required, then the optional git fields); the confirm repeats
  after every spec until declined. A name colliding with an earlier spec keeps the earlier spec and warns. The
  first spec is validated strictly, so at least one spec always lands in the config.

## What is not asked

`headers` and `loader` are never surveyed — the tool config is serialized as plain YAML carrying only the answered
values, and the `pybuggy init` bootstrap then documents the unanswered members as commented example records in the
file itself (uncomment and fill them when needed):

      # headers: example (skipped complex member)   # emitted by the bootstrap
      #   X-Example: value
      #   default request headers dict
      # timeout: (skipped optional scalar)
      # loader: example (skipped complex member)
      #   packages:
      #     - api
      #   modules: []

## The contribution

The answers never touch the filesystem directly — the amendment hook surveys the additional specs, buffers the
contribution, and the engine commits it:

- the tool config file `.goga/tools/pybuggy/config.yml` — the specs mapping plus the answered scalar keys
  (unanswered keys are dropped, never written empty; the bootstrap adds their commented examples afterwards), plus
  the `pipelines` axis entry — the `api.automate` record with `autonomous: true` — when the autonomy confirm was
  enabled; absent otherwise;
- the `build.review.skip: true` amendment — the tool's declared intent in the session answer space. The engine's
  config mapper does not carry the flag into the generated `.goga/config.yml`; the `pybuggy init` bootstrap
  enforces it afterwards (`ensure_review_skip`). A native `goga init -t pybuggy` session runs no bootstrap and
  sets no flag — add it by hand or run the bootstrap programmatically.

## Failure and re-run semantics

- An exception raised while building the contribution — including a Ctrl-C at the additional-spec prompts — drops
  the whole contribution with a warning naming pybuggy; the session continues and returns 0; the pybuggy bootstrap
  then still delivers its own files.
- An existing `.goga/config.yml` ends the session immediately — no questions, no contribution. Whoever created the
  config first wins: the tool config file is never rewritten by a later session.

## Programmatic usage (tests/scripts)

`parse_specs`, `build_config_data`, and `build_config_amendments` are pure mappings from the answer view — test
them directly with dict inputs, no TTY and no filesystem (`extra_specs` is the list of surveyed mappings, or None
for a declined gate). `pybuggy_questions` is likewise pure: assert the record shapes and the survey order against
the `PluginConfigKeys` members. `survey_extra_specs` is the one TTY routine — stub `click.prompt`/`click.confirm`
of the session module to script it in tests.

## Preconditions and side effects

- Writes `.goga/tools/pybuggy/config.yml` through the engine (the parent directory is created).
- The generated file is valid for configuration loading: `specs` is present with the required entry fields; the
  scalar plugin keys are ignored on loading (extra=ignore).
- The `pipelines` axis entry is written only on an enabling answer — the disabling default leaves the axis absent,
  so an onboarded project stays interactive until the user opts in.
- The key list is data-driven from `PluginConfigKeys` — no duplication.
```

#### .usages — `goga_tool_pybuggy/commands/init/.usages/init.md` — unchanged (current file stays as-is).

---

### 5. Cell `goga_tool_pybuggy` (root, modified)

Modification summary:
- **add** — Imports edges `goga_tool_pybuggy/statuses` (Types: register_automate_statuses, register_fix_statuses; Usages: registration) and `goga_tool_pybuggy/autonomous` (Types: amend_workflow; Usages: contribution); step 5 of `register_hooks`; the autonomy rows in `.usages/assembly.md`;
- **change** — `register_hooks` location `statuses.py` → `reg_hooks.py`, Algorithm to five subscriptions, Constraints to five hooks; global Annotations (hook-registration paragraph, connected-practices list); footer Description (subscription zone);
- **delete** — body contracts `register_automate_statuses`, `register_fix_statuses` (moved to the statuses cell); header usage `goga-statuses` (consumed by the statuses cell now); the `statuses.py` module — its contracts split between `reg_hooks.py` and the statuses cell (the package `statuses/` becomes the sole carrier of the name);
- **unchanged** — `main`, `load_env`, `EnvContext`, `retries`, `->install`, `.usages/retries.md`.

#### CODEMANIFEST — `goga_tool_pybuggy/CODEMANIFEST` (current state in full)

```yaml
Imports:
  - Types: [register_automate_statuses, register_fix_statuses]
    Usages: [registration]
    From: goga_tool_pybuggy/statuses
  - Types: [amend_workflow]
    Usages: [contribution]
    From: goga_tool_pybuggy/autonomous
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
  goga-hooks: .goga/usages/github/goga/hooks/registering-hooks.md
  goga-onboarding-hooks: .goga/usages/github/goga/onboarding/registering-hooks.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `click` for the root group, the endpoint subgroup, command registration, the top-level init command, and the
  global --env-file option with its eager-callback.
  Use `python-dotenv` for loading the .env file into os.environ with override=False.
  Use `goga-hooks` for the facade callback contract, the hook signatures, and the failure behavior of registrations.
  Use `goga-onboarding-hooks` for the two onboarding action subscriptions.
  Connected practices describe how consumers use the composed commands, the plugin, and the subscribed hooks:
  `pull`, `list`, `info`, `generate`, `diff`, `init`, `config-build`, `enable`, `configuration`, `registration`,
  `contribution`.

  This cell is the package composition root: it owns the root group `main`, loads the .env environment before any
  subcommand runs, and assembles the full CLI.
  Hook registration: the facade callback subscribes the tool's hooks to the platform actions from one place — the
  topic-status hooks of the statuses cell, the onboarding participation hooks, and the autonomy amendment hook of
  the autonomous cell. Use relative imports inside the cell.

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
  location: reg_hooks.py
  annotations: |
    Subscribe the pybuggy hooks to the goga hooks platform: the topic-status hooks, the onboarding participation
    hooks, and the autonomy amendment hook.

    `hooks`: the subscription surface delivered by the platform.

    Algorithm:
    1. Subscribe `register_automate_statuses` to the statuses registration action under the hook name automate.
    2. Subscribe `register_fix_statuses` to the same action under the hook name fix.
    3. Subscribe `declare_pybuggy_session` to the declare_session onboarding action under the hook name declare.
    4. Subscribe `amend_pybuggy_config` to the amend_config onboarding action under the hook name amend.
    5. Subscribe `amend_workflow` to the workflow amendment action of the pipeline domain under the hook name
       autonomy.

    Requirements:
    - The subscription addresses are the statuses domain registration action, the two onboarding actions, and the
      pipeline domain amendment action.
    - Hook names are stable and unique within the tool.
    - The onboarding and amendment handlers receive their context argument by name — the platform delivers the
      values by name.
    - Subscribing to a subset of the actions is legitimate — the moments are independent.
    - Exposed on the ROOT facade via __all__ — the platform imports it from the package root.

    Constraints:
    - Do not subscribe to any action beyond the five named hooks.

    Use `goga-hooks` for the facade callback contract and the failure behavior of registrations.
    Use `registration` for the status subscription pattern.
    Use `contribution` for the autonomy subscription pattern.
    Use `goga-onboarding-hooks` for the onboarding action subscriptions.

->install: {}

---

Author: Goga
CreatedAt: 08/07/26
Description: |
  Package composition root — owns the root CLI group main, assembles the endpoint subgroup
  (pull/list/info/generate/diff), registers the top-level `init` command, loads the .env environment
  before any command runs, and subscribes the pybuggy hooks — topic statuses, onboarding participation,
  and the autonomy workflow amendment — on the goga platform.
```

#### .usages — `goga_tool_pybuggy/.usages/assembly.md` (updated section; all other sections stay verbatim)

The section `## goga hooks platform integration` is replaced with:

```md
## goga hooks platform integration

The facade exposes one more entry point beside the CLI: `register_hooks` — the callback the goga hooks
platform imports and calls when a command first reaches a hook checkpoint of the run (inspect the registry
with `goga hooks`). A plain `import goga_tool_pybuggy` never triggers it; the platform owns the call.

`register_hooks` lives in `goga_tool_pybuggy/reg_hooks.py` and subscribes five hooks to four addresses —
the statuses registration action, the two onboarding actions, and the pipeline amendment action:

| Hook name | Callable | Address | Registers / contributes |
|-----------|----------|---------|------------------------|
| `automate` | `register_automate_statuses` | statuses / register_statuses | the six automate-line statuses (including the completed-accept `automate.done`) |
| `fix` | `register_fix_statuses` | statuses / register_statuses | the five fix-line statuses |
| `declare` | `declare_pybuggy_session` | onboarding / declare_session | the pybuggy question block of the session survey |
| `amend` | `amend_pybuggy_config` | onboarding / amend_config | the `build.review.skip` amendment and the tool config file |
| `autonomy` | `amend_workflow` | pipeline / amend_workflow | the autonomous workflow amendment (auto-approval window + build stage) for a qualifying run |

The status hook callables live in `goga_tool_pybuggy/statuses`, the autonomy hook callable in
`goga_tool_pybuggy/autonomous`, the onboarding hook callables in `goga_tool_pybuggy/commands/init` — none is
re-exported on the package facade, only `register_hooks` is; the platform reaches them through its
subscription. The onboarding handlers return immediately when the session did not invite pybuggy
(`goga init` without `-t pybuggy`); the autonomy hook is a silent no-op unless the running pipeline is
`api.automate` with autonomy enabled in the tool config `pipelines` axis.

The tool identity (`pybuggy`) is assigned by the platform from the package name — the package never names
itself. Every registered status is stored and shown qualified: `pybuggy.<name>`.
```

The status tables and the registration-order paragraphs that follow in the current file stay verbatim, as do the
Domain, Entry point, .env loading, CLI assembly, and Preconditions sections.
The section `## Static config` is replaced with:

```md
## Static config

The config location is fixed by the platform path standard for tool configs (`.goga/tools/pybuggy/config.yml`);
the config cell reads the file through the platform facade. There is no `--config` option — commands load the
config themselves via `load_config()` (no argument). The pass-object `ctx.obj` exists but carries only the env
context (`EnvContext`), not the config.
```

`.usages/retries.md` — unchanged.

## Dependency Map

```
statuses (NEW, leaf)    config (MOD, leaf)      plugin (unchanged)
      │                      │                      │
      │ Types:[reg_*_statuses]│ Types:[resolve_autonomy]
      │ Usages:[registration]│ Usages:[autonomy]
      ▼                      ▼                      │
   root ◄───────────── autonomous (NEW)             │
      │                      ▲                      │
      │ Types:[amend_workflow]                      │
      │ Usages:[contribution]                       │
      │                                              │
      ├── Types:[init_cmd, declare_pybuggy_session, amend_pybuggy_config]
      │   Usages:[init, config-build] → commands/init (MOD) ──► config (Types/Usages), plugin (PluginConfigKeys)
      ├── Types:[*_cmd] Usages:[*] → commands/{pull,list,info,generate,diff} (unchanged) ──► config
      └── Types:[install] Usages:[enable, configuration] → plugin
```

No cell imports the root; `statuses` and `config` are import-free leaves; `autonomous` depends only on `config`.

## Verification Checklist

After implementing each artifact, verify:

- [ ] `goga schema` shows `goga_tool_pybuggy/statuses` and `goga_tool_pybuggy/autonomous` with their types and `.usages` files, and the root lists the two new dependency edges.
- [ ] `goga lint` passes on all five CODEMANIFEST files (key casing, section order, `location` flatness, signature forms).
- [ ] Every practice connected in a header (`Usages` or `Imports.Usages`) is referenced by at least one annotation in that file — including `registration`, `contribution`, `autonomy`.
- [ ] No annotation uses "X from Imports" phrasing; no annotation references functionality outside its CODEMANIFEST context.
- [ ] Footer `Description` of each manifest states the responsibility zone only.
- [ ] `resolve_autonomy` behavior: absent file/section/name and `autonomous: false` → False; non-mapping `pipelines`/entry or a record with extra keys → clean error naming pybuggy; unknown pipeline names never fail.
- [ ] `build_autonomous_workflow` output uses only WorkflowDocument vocabulary: seven `stages` entries with `approve: auto`, one `extend` entry `build` with `after: [commit-changes]` and the body carrying title/script/after-script/timeout; nothing for `accept-result`.
- [ ] `register_hooks` (reg_hooks.py) subscribes exactly five hooks; the platform import of `register_hooks` from the package root still resolves (`python -c "from goga_tool_pybuggy import register_hooks"`).
- [ ] `goga_tool_pybuggy/statuses.py` no longer exists — the `statuses/` package is the sole carrier of the name.
- [ ] The five command cells still import `load_config`, `Config`, `SpecEntry`, `GitEntry` and the `configuration` usage from `goga_tool_pybuggy/config` unchanged.
- [ ] `goga_tool_pybuggy.config` no longer exports `CONFIG_PATH`; the command test tree migrates the config seam from the `CONFIG_PATH` monkeypatch to the platform `load_tool_config` root override (`goga-tool-config`).
- [ ] `pybuggy_questions` returns the autonomy confirm as the last simple child (default False); `build_config_data` emits the `pipelines` key only on an enabling answer.
- [ ] Usage files are self-contained (no cross-practice references), consumer-perspective, and match the CODEMANIFEST signatures by name.
- [ ] Acceptance: `pytest tests/ -x` green, `ruff check goga_tool_pybuggy/` clean.
