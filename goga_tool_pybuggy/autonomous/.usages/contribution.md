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
