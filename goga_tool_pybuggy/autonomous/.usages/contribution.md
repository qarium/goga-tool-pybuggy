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
