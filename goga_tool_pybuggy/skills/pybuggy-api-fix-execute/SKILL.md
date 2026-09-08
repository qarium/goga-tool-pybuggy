---
name: goga-tool-pybuggy-api-fix-execute
description: Fix-plan execution — tasks dispatched by class, per-task verification, final run
---

# Pybuggy API Fix — Execute

## Identity

You are the fix-plan executor: run the approved plan's tasks in order, dispatch each task by class to the matching
executor, and record the outcome of every check.

## Input

`goga history path -f fix-plan.md` — the approved plan. `<topic>`: the current topic of the history tree (`goga history path`), or a topic named in `$ARGUMENTS`. The document is pinned
for the entire session and passed to every sub-skill.

## Context Initialization

Before execution, load the context via the **Skill tool**:

- **`goga-cell`** — the CODEMANIFEST DSL specification.
- **`goga-tool-pybuggy-api-cookbook`** — test-cell principles.
- **`goga-cell-python`** — language rules (naming, location).
- **`goga-tool-pybuggy-api-usage`** — the pybuggy runtime (api, asserts).

## Pipeline

Execute tasks strictly in the order defined by the plan's "Execution Order" section. For each task, invoke the
class-specific executor:

| Task class    | Skill                                     |
|---------------|-------------------------------------------|
| `environment` | `goga-tool-pybuggy-api-fix-execute-env`   |
| `spec-drift`  | `goga-tool-pybuggy-api-fix-execute-drift` |
| `case-defect` | `goga-tool-pybuggy-api-fix-execute-case`  |
| `test-defect` | `goga-tool-pybuggy-api-fix-execute-test`  |
| `service-bug` | `goga-tool-pybuggy-api-fix-execute-bug`   |

Loop rules:

- every task ends with its check from the plan; the executor returns status `done` (check passed) or
  `failed`;
- the attempt budget is 3 per task, for every class. One attempt = one executor call (actions + check); the executor
  performs exactly one attempt per call and never repeats actions or the check internally;
- on `failed` with attempts remaining, re-invoke the same task's executor, passing the attempt number, the previous
  failure reason, and the work already done: the next attempt must correct the actions, not repeat them blindly;
- on `failed` after the 3rd attempt, close the task as permanently `failed`: further calls of this task are
  forbidden; record the attempt exhaustion and continue with the remaining tasks;
- after the last task, invoke `goga-tool-pybuggy-api-fix-execute-final` — the final run and the report
  `goga history path -f fix-execute.md`;
- STOP: pytest/SUT fails to start at all and the `environment` task has exhausted its 3 attempts — the checks of the
  remaining tasks are unreliable; record the stop for the review stage.

## Output Rule

Every sub-skill must fill in every section of its output format. An empty section = an incomplete sub-skill = a pipeline
STOP.

## Edit Invariants

### ALWAYS

- execute only the actions defined by the approved plan's tasks
- take the topic version (spec branch ref + environment base URL) from the path printed by `goga history path -f fix-collect.md`; pull with
  `--ref <ref>` for a feature ref; run pytest checks with `--base-url <url>` for a non-standard environment
- allow at most 3 attempts per task: after the third failed attempt the task is closed as `failed` and repeats are
  forbidden
- build valid request bodies with the `Request(...)` model; use a raw `dict` for negative cases only
- keep the test body linear; no `pytest.skip`/skip markers/`xfail`
- artifact regeneration must not touch the CODEMANIFEST; a CODEMANIFEST edit must not delete existing Routines
- record the changed files for every task
