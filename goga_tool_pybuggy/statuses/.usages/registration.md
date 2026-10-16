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
