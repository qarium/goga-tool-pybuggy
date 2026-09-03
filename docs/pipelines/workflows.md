# Workflows

Any pipeline shipped with pybuggy can be adjusted to your project without forking or
copying the pipeline-file. The goga
[workflow mechanism](https://qarium.github.io/goga/pipelines/workflows/) layers
project-specific behavior on top of a compiled pipeline at run time: it can inject a
top-level prompt, override the agent or prompt of specific stages, and expand a stage
into N chained copies via `loop`.

This page is a short orientation. The complete reference — document shape, compiler
passes, and the error catalog — lives in the
[goga documentation](https://qarium.github.io/goga/pipelines/workflows/).

## Workflow file

Workflow files live in the consumer project:

```
.goga/workflows/<name>.yml
```

When the file name matches the pipeline name, goga applies it automatically. For
example, the [`api.automate`](api-automate.md) pipeline is launched with
`goga pipeline pybuggy:api.automate`, so its auto-matched workflow file is:

```
.goga/workflows/pybuggy:api.automate.yml
```

## What a workflow can change

| Key                     | Effect                                                                                                                                |
|-------------------------|---------------------------------------------------------------------------------------------------------------------------------------|
| `prompt` (top level)    | Injected as the first directive of the compiled pipeline — e.g. an "answer in Russian" directive.                                     |
| `stages.<stage>.agent`  | The CLI agent that runs the stage (`claude`, `codex`, `opencode`, …); other stages keep the default agent.                            |
| `stages.<stage>.prompt` | Additional per-stage context. It has a *lower* precedence than the stage's own prompt: it frames the intent rather than replacing it. |
| `stages.<stage>.loop`   | Iteration count (`>= 1`); `>= 2` expands the stage into N chained copies (`<stage>-1`, …, `<stage>-N`).                               |

`<stage>` is the name of a stage in the target pipeline — see the
[Stages](api-automate.md#stages) table of the pipeline you customize. A name that
matches no stage of the pipeline is silently skipped, so one workflow file can cover
several pipelines.

> **Requirements in a workflow prompt:** free-form prose is treated as background, not
> as a directive. To make a workflow `prompt` carry enforceable requirements, use the
> labeled-block format goga prompts already use — `Requirements:` / `Constraints:`.

## How a workflow is applied

The compiler applies the workflow to the compiled pipeline in deterministic passes,
before the output stages are built:

1. **Per-stage overrides (in place)** — `agent` rewrites the stage command to the
   chosen CLI agent's wrapper; `prompt` is attached as per-stage context.
2. **Loop expansion** — a stage with `loop >= 2` is replaced by N chained copies
   (`<stage>-1`, …, `<stage>-N`), each depending on the previous one; stages that
   depend on the expanded name are rewritten to its last copy.
3. **Agent-mode resolution** — unchanged by the workflow: a stage's own `agents` field
   (the roles that organize work *inside* the stage) is orthogonal to the workflow
   `agent` (which CLI agent *runs* the stage).

## Example

A workflow for the [`api.automate`](api-automate.md) pipeline — a language directive,
enforceable requirements for the requirements stage, and acceptance run twice on
another agent:

```yaml
# .goga/workflows/pybuggy:api.automate.yml
prompt: |
  Answer in Russian language.

stages:
  create-requirements:
    prompt: |
      Requirements elicitation for the topic under test.

      Requirements:
      - Every functional requirement REQ-<N> describes error behavior as a contract.
      - Bind each statement of the user's topic description to an REQ-<N>.

      Constraints:
      - No code examples in the requirements artifact.
  accept-result:
    agent: codex   # run this stage on a different CLI agent
    loop: 2        # two chained passes
```

## Invocation modes

| Mode       | Invocation                                   | Behavior                                                        |
|------------|----------------------------------------------|-----------------------------------------------------------------|
| Auto-match | `goga pipeline <pipeline>`                   | Applies `.goga/workflows/<pipeline>.yml` silently if it exists. |
| Explicit   | `goga pipeline <pipeline> --workflow custom` | Applies `.goga/workflows/custom.yml` — any workflow name works. |
| Disable    | `goga pipeline <pipeline> --no-workflow`     | Runs the pipeline without any workflow.                         |

When a workflow applies, the launcher prints `Pipeline running with workflow "<name>"`.