# Architecture Plan — `api.patch` pipeline

## Topic

Short name: **`api.patch` pipeline** — the third pybuggy line (user-requested modification of
existing API tests).

Plan path: `.goga/history/2026/patch-pipeline/arch.md` (topic `2026/patch-pipeline`).

Source task: `.goga/history/2026/patch-pipeline/task.md`; decisions: `adr.md` of the same topic.

## Implementation Order

1. **`goga_tool_pybuggy/statuses`** [MODIFIED] — leaf cell, no Imports; provides
   `register_patch_statuses` consumed later by the root.
2. **`goga_tool_pybuggy/autonomous`** [MODIFIED] — depends only on the unchanged
   `goga_tool_pybuggy/config` (`resolve_autonomy` + usage `autonomy`); provides
   `amend_workflow` and the `PipelineContribution` records.
3. **`goga_tool_pybuggy`** (root) [MODIFIED] — composition root; depends on `statuses`
   (now also `register_patch_statuses`), `autonomous`, and the unchanged cells
   (`commands/*`, `plugin`, `sandbox/data`); owns the six-fold hook subscription.

No cells are created; three existing cells are modified. `goga_tool_pybuggy/config` is
consumed unchanged.

---

## Artifacts

### Cell 1: `goga_tool_pybuggy/statuses` [MODIFIED]

**Changes against the current file:**

- ADD body Routine `"register_patch_statuses(context: object)"` (location `patch.py`) with
  the normative six-status table.
- CHANGE global Annotations: "two pybuggy topic-status lines — automate and fix" →
  "three pybuggy topic-status lines — automate, fix, and patch".
- CHANGE footer Description: add the patch line.
- Header `Usages` and `Imports`: unchanged (none).

**Target CODEMANIFEST** (`goga_tool_pybuggy/statuses/CODEMANIFEST`):

```yaml
Usages:
  conventions: .goga/usages/conventions.md
  goga-statuses: .goga/usages/github/goga/history/registering-hooks.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `goga-statuses` for the registration surface: register parameters, artifact path
  semantics, anchors, and skip-with-warning.

  The cell owns the three pybuggy topic-status lines — automate, fix, and patch. Each line
  registers through direct registration calls in its normative order; the lines are
  independent chains with no shared statuses. Use relative imports inside the cell.

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

"register_patch_statuses(context: object)":
  location: patch.py
  annotations: |
    Register the patch status line on the topic status scale — an independent chain anchored
    at the built-in empty status.

    `context`: the registration surface scoped to the tool.

    Algorithm:
    1. Register the patch intended status for the intent artifact, anchored above the
       built-in empty status.
    2. Register the remaining patch statuses in pipeline order — analyzed, applied, designed,
       planned, done — each anchored above the previously registered patch status.

    Requirements:
    - Registration order equals the normative table order; every anchor names an entry
      registered earlier in this run or a built-in status.
    - Artifact paths are relative to the topic directory; nested paths keep their directory part.
    - Registered names carry no tool prefix — the platform assigns the tool identity.

    Normative table (registration order):
    1. patch.intended → intent.md — after empty
    2. patch.analyzed → impact.md — after pybuggy.patch.intended
    3. patch.applied → apply.md — after pybuggy.patch.analyzed
    4. patch.designed → rework.md — after pybuggy.patch.applied
    5. patch.planned → workplan.md — after pybuggy.patch.designed
    6. patch.done → completed/workplan.md — after pybuggy.patch.planned

    Use `goga-statuses` for the register parameters and the anchor semantics.

---

Author: Goga
CreatedAt: 02/10/26
Description: |
  Topic-status registration cell — the automate, fix, and patch status lines of the pybuggy tool.
```

**`.usages/` file — `registration.md` [MODIFIED]**

Changes: three lines in the Domain sentence; add the `register_patch_statuses` bullet;
extend the subscribe example with the `patch` hook; "automate, fix, and patch are the stable
names"; "Every line is an add-only registration".

Target content (`goga_tool_pybuggy/statuses/.usages/registration.md`):

````markdown
# statuses — subscribing the pybuggy status lines

## Domain

Consumption patterns of the cell `goga_tool_pybuggy/statuses/`: the three topic-status
registration hooks that place pybuggy's automate, fix, and patch status lines on a topic's
status scale. Target audience: the package registration surface that subscribes platform
hooks, and maintainers wiring additional status lines.

## What the cell provides

- `register_automate_statuses(context)` — registers the automate line: the completed-accept
  status anchored at the built-in done status, plus the middle statuses in reverse pipeline
  order (plan, design, arch, testcases, requirements).
- `register_fix_statuses(context)` — registers the fix line: an independent chain anchored at
  the built-in empty status (collected, analyzed, planned, executed, reviewed).
- `register_patch_statuses(context)` — registers the patch line: an independent chain anchored
  at the built-in empty status (intended, analyzed, applied, designed, planned, done).

## Subscribe from the registration surface

```python
from goga_tool_pybuggy.statuses import (
    register_automate_statuses,
    register_fix_statuses,
    register_patch_statuses,
)


def register_hooks(hooks):
    hooks.subscribe("statuses", "register_statuses", "automate", register_automate_statuses)
    hooks.subscribe("statuses", "register_statuses", "fix", register_fix_statuses)
    hooks.subscribe("statuses", "register_statuses", "patch", register_patch_statuses)
```

- Hook names are local to the tool; `automate`, `fix`, and `patch` are the stable names.
- Each hook receives its registration surface by the parameter name `context`.
- The moments are independent — subscribing to a subset is legitimate.

## Preconditions and side effects relevant to the consumer

- Registration order inside each hook is normative — the consumer never reorders or filters
  the calls.
- Every line is an add-only registration against built-in statuses; a skipped registration
  (unresolvable anchor) logs a warning and never aborts the command.
- Statuses show qualified as `pybuggy.<name>` — the platform assigns the tool identity.
````

---

### Cell 2: `goga_tool_pybuggy/autonomous` [MODIFIED]

**Changes against the current file:**

- ADD body Entity `"PipelineContribution(identity: str, axis: str, window: list[str], build_artifact: str)"`
  (location `contributions.py`) with four properties and the normative contribution table
  (exactly two records: automate and patch).
- CHANGE `amend_workflow` annotation: identity gate resolves a `PipelineContribution` record
  (no record → silent no-op); autonomy resolves for the record's `axis`.
- CHANGE `build_autonomous_workflow` signature — now
  `(contribution: PipelineContribution) -> document: WorkflowDocument` — and annotation
  (document derives from the record; no per-pipeline branching).
- CHANGE global Annotations: qualifying identities (automate + patch), per-record constants.
- Header `Imports`/`Usages`: unchanged. Footer: unchanged.

**Target CODEMANIFEST** (`goga_tool_pybuggy/autonomous/CODEMANIFEST`):

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

  The cell owns the autonomous-run contribution: when the running pipeline is one of the
  qualifying identities — pybuggy:api.automate or pybuggy:api.patch (the installer's
  namespaced forms of the package's pipeline conventions, delivered as PipelineIdentity
  names) — and autonomy is enabled for its axis in the tool config, it contributes that
  pipeline's auto-approval window and build stage; every other run stays silent. Autonomy
  ends at commit-changes — the acceptance stage stays interactive. The windows, axes, and
  build entries are compile-time constants of the package — one `PipelineContribution`
  record per qualifying pipeline. Use relative imports inside the cell.

---

"PipelineContribution(identity: str, axis: str, window: list[str], build_artifact: str)":
  location: contributions.py
  annotations: |
    Compile-time record of one pipeline's autonomy contribution — the run identity it
    qualifies, its tool-config axis key, its auto-approval window, and the topic artifact
    its build stage runs on.

    `identity`: the qualifying run identity — the installer-namespaced pipeline name the
    platform delivers (e.g. pybuggy:api.patch).
    `axis`: the tool-config pipelines-axis key of the pipeline (e.g. api.patch).
    `window`: the ordered stage names that carry the auto-approval directive.
    `build_artifact`: the topic artifact the build stage builds (e.g. workplan.md).

    Requirements:
    - pydantic model with kw_only=True; pure data carrier with no behavior.
    - The package defines exactly two records — the normative contribution table:
      1. automate — identity pybuggy:api.automate, axis api.automate, window
         review-testcases, create-testcases, code-design, design-review, coding-plan,
         plan-review, commit-changes — build artifact plan.md
      2. patch — identity pybuggy:api.patch, axis api.patch, window
         review-impact, apply-manifests, code-design, design-review, coding-plan,
         plan-review, commit-changes — build artifact workplan.md
    - Both windows end at commit-changes; the build stage positions after the final window
      stage.

    Use `conventions` for the pydantic model rules.
  properties:
    "identity -> str": |
      The qualifying run identity — the installer-namespaced pipeline name the platform
      delivers.
    "axis -> str": |
      The pipelines-axis key of the pipeline in the tool config.
    "window -> list[str]": |
      The ordered stage names that carry the auto-approval directive.
    "build_artifact -> str": |
      The topic artifact the build stage builds.

"amend_workflow(context: object)":
  location: amendment.py
  annotations: |
    Contribute the autonomous workflow amendment when the run qualifies for autonomy.

    `context`: the amendment view delivered by the platform — the identity of the running
    pipeline and the contribute buffer.

    Algorithm:
    1. Read the identity of the running pipeline from `context` — a platform
       PipelineIdentity; the gate reads its discovered name attribute.
    2. Resolve the `PipelineContribution` record whose identity equals the discovered
       name among the package's compile-time records; when none matches, return without
       contributing — a silent no-op.
    3. Resolve autonomy for the record's axis via `resolve_autonomy`.
    4. When autonomy is disabled, return without contributing — a silent no-op.
    5. When autonomy is enabled, build the contribution via `build_autonomous_workflow`
       over the record and buffer it through `context`.

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

"build_autonomous_workflow(contribution: PipelineContribution) -> document: WorkflowDocument":
  location: workflow.py
  annotations: |
    Build the declarative autonomy contribution from a `PipelineContribution` record.

    `contribution`: the compile-time record of the qualifying pipeline.
    `document`: the platform `WorkflowDocument` — the auto-approval window and the build
    stage — built exactly as the equivalent authored workflow-file would parse.

    Algorithm:
    1. Build the stages mapping: each stage of `contribution`'s window carries the
       auto-approval directive.
    2. Build the extend entry for the build stage: positioned after the final stage of the
       window, the body carrying the build title, the script that runs the goga build of
       the topic's `contribution` artifact, the after-script cleanup of the .ralphex
       scratch tree, and the eight-hour timeout.
    3. Return the document.

    Requirements:
    - The window and the build entry derive from the record — no per-pipeline branching.
    - The document is a real platform `WorkflowDocument` (WorkflowStage /
      WorkflowExtendStage values) — the delivery reads it by attribute and the
      merge walks the typed fields; a plain mapping fails the checkpoint.
    - The document uses only the WorkflowDocument instruction vocabulary.
    - Deterministic and pure — identical output on every call.

    Constraints:
    - Do not emit per-stage prompt or description directives and do not modify stage
      skills — autonomy is purely the workflow-level instruction.
    - Do not emit directives for the acceptance stage — it stays interactive and
      manually launched.
    - No platform facade calls and no I/O; the platform models are imported at
      call time (the package must import without goga).

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

**`.usages/` file — `contribution.md` [MODIFIED]**

Changes: generalized description of `amend_workflow` (two qualifying identities, record
matching); new `PipelineContribution` bullet with the two records; `build_autonomous_workflow`
takes the record; preconditions name both axis keys.

Target content (`goga_tool_pybuggy/autonomous/.usages/contribution.md`):

````markdown
# autonomous — the autonomy contribution moment

## Domain

Consumption patterns of the cell `goga_tool_pybuggy/autonomous/`: the workflow-amendment
hook that contributes pybuggy's autonomous-run instructions to a qualifying run. Target
audience: the package registration surface that subscribes platform hooks, and maintainers
extending the contribution.

## What the cell provides

- `amend_workflow(context)` — the amendment moment: resolves the contribution record for the
  running pipeline and contributes the document when autonomy is enabled; a silent no-op
  otherwise. The gate reads the `name` of the platform-delivered `PipelineIdentity` — the
  discovered, installer-namespaced form (pybuggy:api.automate or pybuggy:api.patch) — and
  matches it against the compile-time contribution records.
- `PipelineContribution` — the record type of one pipeline's contribution: the qualifying run
  identity, the tool-config axis key, the auto-approval window, and the build artifact. The
  package ships two records:
  - automate — axis `api.automate`, window review-testcases … commit-changes, build over
    `plan.md`;
  - patch — axis `api.patch`, window review-impact … commit-changes, build over `workplan.md`.
- `build_autonomous_workflow(contribution)` — the pure builder of the contributed document:
  the record's auto-approval window and the build stage added after commit-changes (the
  topic build of the record's artifact, eight-hour timeout, scratch-tree cleanup). The
  acceptance stage is never part of the contribution. The builder returns a real platform
  `WorkflowDocument` (the models are imported at call time) — the delivery reads the buffer
  by attribute, so a plain mapping cannot be contributed.

## Subscribe from the registration surface

```python
from goga_tool_pybuggy.autonomous import amend_workflow


def register_hooks(hooks):
    hooks.subscribe("pipeline", "amend_workflow", "autonomy", amend_workflow)
```

- The hook name is local to the tool; `autonomy` is the stable name.
- The hook receives its amendment view by the parameter name `context`.

## Preconditions and side effects relevant to the consumer

- Autonomy is enabled per pipeline name in the tool config `pipelines` axis — the record's
  axis key (`api.automate`, `api.patch`); the hook is a silent no-op for every other
  pipeline and for every disabled configuration.
- A raised error inside the hook stops the command with a clean error naming pybuggy — the
  consumer never wraps the hook in error suppression.
- An authored project workflow wins per slot over the contribution — a project can
  re-enable interaction for any window stage or displace the build stage.
````

---

### Cell 3: `goga_tool_pybuggy` (root) [MODIFIED]

**Changes against the current file:**

- CHANGE `Imports`, statuses entry: `Types: [register_automate_statuses, register_fix_statuses]`
  → `Types: [register_automate_statuses, register_fix_statuses, register_patch_statuses]`.
- CHANGE `register_hooks` annotation: Algorithm step 3 added (subscribe
  `register_patch_statuses` under the hook name `patch`); steps renumbered to six;
  Constraint "beyond the five named hooks" → "beyond the six named hooks".
- Everything else (global Annotations, other types, embeddings, footer): unchanged.

**Target CODEMANIFEST** (`goga_tool_pybuggy/CODEMANIFEST`):

```yaml
Imports:
  - Types: [register_automate_statuses, register_fix_statuses, register_patch_statuses]
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
  - Types: [services]
    Usages: [data-operations]
    From: goga_tool_pybuggy/sandbox/data

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
  topic-status hooks, the onboarding participation hooks, and the autonomy amendment hook. Use relative imports
  inside the cell.

  The facade carries the sandbox capability surface: `services` for per-test data presets —
  one import source beside the plugin installation entry; the session sandbox fixture itself is
  product-owned through the plugin installation.
  Connected capability practices: `data-operations`.

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
    - python -m goga_tool_pybuggy runs via __main__.py, delegating to `main`.

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
    3. Subscribe `register_patch_statuses` to the same action under the hook name patch.
    4. Subscribe `declare_pybuggy_session` to the declare_session onboarding action under the hook name declare.
    5. Subscribe `amend_pybuggy_config` to the amend_config onboarding action under the hook name amend.
    6. Subscribe `amend_workflow` to the workflow amendment action of the pipeline domain under the hook name
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
    - Do not subscribe to any action beyond the six named hooks.

    Use `goga-hooks` for the facade callback contract and the failure behavior of registrations.
    Use `registration` for the status subscription pattern.
    Use `contribution` for the autonomy subscription pattern.
    Use `goga-onboarding-hooks` for the onboarding action subscriptions.

->install: {}

->services: {}

---

Author: Goga
CreatedAt: 08/07/26
Description: |
  Package composition root — owns the root CLI group main, assembles the endpoint subgroup
  (pull/list/info/generate/diff), registers the top-level `init` command, loads the .env environment
  before any command runs, and subscribes the pybuggy hooks — topic statuses, onboarding participation,
  and the autonomy workflow amendment — on the goga platform.
```

**`.usages/` files**

- `retries.md` — unchanged (not touched by this task).
- `assembly.md` [MODIFIED] — changes localized to "goga hooks platform integration":
  1. "subscribes five hooks to four addresses" → "subscribes six hooks to four addresses —
     the statuses registration action (three status lines), …";
  2. hook table gains the row
     `| patch | register_patch_statuses | statuses / register_statuses | the six patch-line statuses |`;
  3. autonomy no-op sentence → "…unless the running pipeline is one of the qualifying
     pipelines (`pybuggy:api.automate`, `pybuggy:api.patch`) with autonomy enabled for its
     axis in the tool config `pipelines` axis";
  4. topic-status table gains the six patch rows (see target content below);
  5. stacking paragraph gains: "…the patch chain stacks the same way above `empty` — an
     independent chain that never reorders the automate line."

Target content (`goga_tool_pybuggy/.usages/assembly.md`):

````markdown
# pybuggy — CLI assembly and execution (composition root)

## Domain

Consumption patterns of the root cell `goga_tool_pybuggy/`: a package facade that defines the root Click group
`main`, loads `.env` into `os.environ` before any command executes, assembles the full CLI, and exposes the
`register_hooks` callback of the goga hooks platform. The audience: integrators who launch `pybuggy`
(console command or `python -m goga_tool_pybuggy`), external importers of the facade
(`from goga_tool_pybuggy import main`), and the goga hooks platform (which imports and calls `register_hooks`).

## Entry point

The package facade `pybuggy` exposes the root group `main`:

- Console command (entry point in `pyproject.toml`):

      pybuggy endpoint list

- Module execution (`goga_tool_pybuggy/__main__.py`):

      python -m goga_tool_pybuggy endpoint list

- Global option `--env-file` (BEFORE the subcommand) — loads `.env` into `os.environ` before the command runs:

      pybuggy --env-file ./my.env endpoint list      # explicit file (must exist)
      pybuggy endpoint list                          # implicit .env from CWD (absence handled silently)

- Spec-driven artifact scaffolding (`endpoint generate`, options `-s/--spec`, `-f/--force`):

      pybuggy endpoint generate -s shop
      pybuggy endpoint generate --spec shop --force

- Drift report (`endpoint diff`, options `-s/--spec`, variadic endpoint-ids):

      pybuggy endpoint diff
      pybuggy endpoint diff -s shop clients_startup_get

- Project initialization and bootstrap (top-level `init`, three modes):

      pybuggy init                                  # bare onboarding (refused over an existing .goga/)
      pybuggy init <tpl> [--ref <git-ref>]          # scaffold a template, then onboard
      pybuggy init --upgrade [--ref <git-ref>]      # migrate a scaffolded template only

- Programmatic facade import:

      from goga_tool_pybuggy import main

## .env loading (global option --env-file and ctx.obj)

The root group `main` is the single load point for environment variables. The global option `--env-file` is
parsed at the group level, so the flag must come BEFORE the subcommand:

      pybuggy --env-file ./my.env <cmd>     # ✓ exit 0
      pybuggy <cmd> --env-file ./my.env     # ✗ exit 2 (No such option)

`load_env` in `env.py` implements two loading modes:

- **Explicit file** (`--env-file FILE`): the file must exist; otherwise a `click.ClickException` is raised.
  The file is loaded into `os.environ`.
- **Implicit `.env` from CWD** (flag absent): if `.env` exists in the CWD, it is loaded; if not, it is skipped
  silently (no error, no values).

`override=False` — variables already set in the environment are NOT overwritten. Loading completes BEFORE any
subcommand runs (eager callback of the root group).

The context object `ctx.obj` (type `EnvContext`, `env.py`) carries the resolved env-file path
(`env_path: str | None`) and the loaded values (`values: dict[str, str]`). Introducing a pass-object into the
root cell contract is deliberate: `ctx.obj` carries env context only; each command still loads its config
itself via `load_config()`.

> Note: the `pull` command receives `PYBUGGY_REF` through the `envvar=` binding of the `--ref` option in the
> click decorator (click reads `os.environ`), not from `ctx.obj` — loose coupling between cells is preserved.

## CLI assembly

Assembly lives in the `goga_tool_pybuggy/cli.py` module (owned by the root cell) and runs at import time:

1. Define the root group `main` (with the global option `--env-file` + an eager callback that loads the env).
2. Create the `endpoint` subgroup.
3. Register the commands `pull_cmd`, `list_cmd`, `info_cmd`, `generate_cmd`, `diff_cmd` on `endpoint`
   (from `goga_tool_pybuggy/commands/{pull,list,info,generate,diff}`).
4. Add the `endpoint` subgroup to `main`.
5. Register the top-level command `init_cmd` on `main` directly (from `goga_tool_pybuggy/commands/init`).
6. Export `main` via `__all__`. `load_env` and `EnvContext` are also available on the facade.

Top-level on `main`: `init`.
Registered under `endpoint`: `pull`, `list`, `info`, `generate`, `diff`.

## Static config

The config location is fixed by the platform path standard for tool configs (`.goga/tools/pybuggy/config.yml`);
the config cell reads the file through the platform facade. There is no `--config` option — commands load the
config themselves via `load_config()` (no argument). The pass-object `ctx.obj` exists but carries only the env
context (`EnvContext`), not the config.

## goga hooks platform integration

The facade exposes one more entry point beside the CLI: `register_hooks` — the callback the goga hooks
platform imports and calls when a command first reaches a hook checkpoint of the run (inspect the registry
with `goga hooks`). A plain `import goga_tool_pybuggy` never triggers it; the platform owns the call.

`register_hooks` lives in `goga_tool_pybuggy/reg_hooks.py` and subscribes six hooks to four addresses —
the statuses registration action (three status lines), the two onboarding actions, and the pipeline
amendment action:

| Hook name | Callable | Address | Registers / contributes |
|-----------|----------|---------|------------------------|
| `automate` | `register_automate_statuses` | statuses / register_statuses | the six automate-line statuses (including the completed-accept `automate.done`) |
| `fix` | `register_fix_statuses` | statuses / register_statuses | the five fix-line statuses |
| `patch` | `register_patch_statuses` | statuses / register_statuses | the six patch-line statuses |
| `declare` | `declare_pybuggy_session` | onboarding / declare_session | the pybuggy question block of the session survey |
| `amend` | `amend_pybuggy_config` | onboarding / amend_config | the `build.review.skip` amendment and the tool config file |
| `autonomy` | `amend_workflow` | pipeline / amend_workflow | the autonomous workflow amendment (auto-approval window + build stage) for a qualifying run |

The status hook callables live in `goga_tool_pybuggy/statuses`, the autonomy hook callable in
`goga_tool_pybuggy/autonomous`, the onboarding hook callables in `goga_tool_pybuggy/commands/init` — none is
re-exported on the package facade, only `register_hooks` is; the platform reaches them through its
subscription. The onboarding handlers return immediately when the session did not invite pybuggy
(`goga init` without `-t pybuggy`); the autonomy hook is a silent no-op unless the running pipeline is one of
the qualifying pipelines (`pybuggy:api.automate`, `pybuggy:api.patch`) with autonomy enabled for its axis in
the tool config `pipelines` axis.

The tool identity (`pybuggy`) is assigned by the platform from the package name — the package never names
itself. Every registered status is stored and shown qualified: `pybuggy.<name>`.

The registered topic statuses (artifact paths relative to the topic directory):

| Qualified status | Artifact | Anchors |
|------------------|----------|---------|
| `pybuggy.automate.done` | `completed/plan.md` | after `done` |
| `pybuggy.automate.coding-planned` | `plan.md` | after `planned`, before `pybuggy.automate.done` |
| `pybuggy.automate.code-designed` | `design.md` | after `specified`, before `pybuggy.automate.coding-planned` |
| `pybuggy.automate.arch-prepared` | `arch.md` | after `designed`, before `pybuggy.automate.code-designed` |
| `pybuggy.automate.testcases-designed` | `testcases.md` | after `backlog`, before `pybuggy.automate.arch-prepared` |
| `pybuggy.automate.requirements-created` | `requirements.md` | after `defined`, before `pybuggy.automate.testcases-designed` |
| `pybuggy.fix.collected` | `fix-collect.md` | after `empty` |
| `pybuggy.fix.analyzed` | `fix-analysis.md` | after `pybuggy.fix.collected` |
| `pybuggy.fix.planned` | `fix-plan.md` | after `pybuggy.fix.analyzed` |
| `pybuggy.fix.executed` | `fix-execute.md` | after `pybuggy.fix.planned` |
| `pybuggy.fix.reviewed` | `fix-review.md` | after `pybuggy.fix.executed` |
| `pybuggy.patch.intended` | `intent.md` | after `empty` |
| `pybuggy.patch.analyzed` | `impact.md` | after `pybuggy.patch.intended` |
| `pybuggy.patch.applied` | `apply.md` | after `pybuggy.patch.analyzed` |
| `pybuggy.patch.designed` | `rework.md` | after `pybuggy.patch.applied` |
| `pybuggy.patch.planned` | `workplan.md` | after `pybuggy.patch.designed` |
| `pybuggy.patch.done` | `completed/workplan.md` | after `pybuggy.patch.planned` |

The automate statuses register in reverse pipeline order: `automate.done` lands above the built-in `done`,
and each middle status anchors above its built-in twin and below the previously registered automate status
(the arch/design/plan artifacts are the same files as their built-in twins). The fix chain starts above the
built-in `empty` and stacks in pipeline order, every status anchored to its predecessor; the patch chain
stacks the same way above `empty` — an independent chain that never reorders the automate line.
Registration is add-only and never cached — package edits apply from the next run, without reinstall.

## Preconditions and side effects

- `import goga_tool_pybuggy` triggers the full CLI assembly (imports `click` and all command cells).
- Running a command requires a valid config at the fixed path; loading and validation happen via `load_config`
  in the subcommand.
- `--env-file` (explicit) or `.env` from the CWD (implicit) is loaded into `os.environ` (`override=False`)
  before the command runs; the values are available to all subcommands via `os.environ`
  (e.g. `PYBUGGY_REF` for `pull`).
- `init` is a top-level command and does NOT require the pybuggy config: it runs a goga onboarding session with
  pybuggy invited (an existing `.goga/config.yml` ends the session immediately) and then bootstraps the consumer's
  pybuggy environment (packaged usages, `conventions` slot, `build.review.skip`, Dockerfile install line, root
  conftest).

The facade also re-exports the sandbox capability surface — `services` (the per-test
data-preset decorator) — so consumer tests import it from the package root:
`from goga_tool_pybuggy import services`. The session sandbox fixture is product-owned through
the plugin installation and needs no facade import.
````

---

### Non-cell scope (outside this plan's artifacts)

Traced for the downstream stages (code-design / coding-plan), not artifacts of this plan:

- `goga_tool_pybuggy/pipelines/api.patch.yml` — 10-stage pipeline convention (skeleton is
  normative in the task file Notes);
- `goga_tool_pybuggy/skills/pybuggy-api-patch-*` — nine orchestrator skills
  (collect, analyze, review, apply, design, design-review, plan, plan-review, accept);
- `docs/pipelines/api-patch.md` (new) and `docs/pipelines/index.md` (modified);
- tests: `tests/statuses/test_patch.py` (normative table), `tests/autonomous/` (patch
  qualification/window/build; automate builder call-site update with assertions kept),
  `tests/test_reg_hooks.py` (six subscriptions, order);
- implementation files carrying the contracts: `statuses/patch.py` (new),
  `statuses/__init__.py` (export), `autonomous/contributions.py` (new),
  `autonomous/amendment.py`, `autonomous/workflow.py`, `autonomous/__init__.py` (export),
  `reg_hooks.py`.

---

## Dependency Map

```
 goga_tool_pybuggy/config [unchanged]
         │ resolve_autonomy + usage `autonomy`
         ▼
 goga_tool_pybuggy/autonomous [MODIFIED]
   PipelineContribution (NEW) · amend_workflow · build_autonomous_workflow
         │ amend_workflow + usage `contribution`
         │
         │    goga_tool_pybuggy/statuses [MODIFIED]
         │      register_automate_statuses · register_fix_statuses
         │      register_patch_statuses (NEW) + usage `registration`
         │              │
         └──────┐       │
                ▼       ▼
        goga_tool_pybuggy (ROOT) [MODIFIED]
          register_hooks — six subscriptions (new: statuses/patch)
          ↑ also imports (unchanged): commands/{pull,list,info,generate,diff,init},
            plugin (install), sandbox/data (services)
```

No cycles: `config` and `statuses` are leaves; `autonomous` depends only on `config`;
the root depends downward only.

## Verification Checklist

After **statuses**:

- `goga lint` passes on the cell; DSL structure valid (Header/Body/Footer, quoted keys).
- Facade `__init__.py` exports `register_patch_statuses` via `__all__`.
- `register_patch_statuses` registers exactly the six normative statuses in table order,
  every anchor resolvable (`empty`, then each predecessor); artifact paths keep the
  directory part for `completed/workplan.md`.
- `registration.md` matches the facade (three hooks, `patch` subscribe line).

After **autonomous**:

- `goga lint` passes; facade exports `PipelineContribution` (plus the two routines).
- Exactly two compile-time records exist, matching the normative contribution table;
  both windows end at `commit-changes`.
- The automate contribution is byte-identical in effect to the previous behavior: window
  `review-testcases` … `commit-changes`, build over `plan.md`, acceptance stage untouched
  (existing automate tests pass; only the builder call site gains the record argument).
- The patch contribution: window `review-impact`, `apply-manifests`, `code-design`,
  `design-review`, `coding-plan`, `plan-review`, `commit-changes`; build extend after
  `commit-changes` over `workplan.md`; 8h timeout; `.ralphex` after-script cleanup.
- Non-matching identity and disabled autonomy are silent no-ops; axis structural violation
  surfaces as the resolver's clean error naming pybuggy.
- `contribution.md` matches the generalized facade.

After **root**:

- `goga lint` passes; `goga schema` shows the statuses dependency of the root now carries
  `register_patch_statuses`.
- `reg_hooks` subscribes exactly six hooks; the `patch` subscription sits with the status
  group (after `fix`); module docstring count updated.
- `assembly.md` tables list six hooks and all three status lines.

Global:

- `pytest tests/ -x` and `ruff check` pass in the project virtualenv.
- Runtime smoke (after build): a `pybuggy:api.patch` run shows statuses qualified as
  `pybuggy.patch.*` and never reorders the automate line.
