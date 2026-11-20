# statuses — subscribing the pybuggy status lines

## Domain

Consumption patterns of the cell `goga_tool_pybuggy/statuses/`: the four topic-status
registration hooks that place pybuggy's automate, web automate, fix, and patch status lines
on a topic's status scale. Target audience: the package registration surface that subscribes
platform hooks, and maintainers wiring additional status lines.

## What the cell provides

- `register_automate_statuses(context)` — registers the automate line: the completed-accept
  status anchored at the built-in done status, plus the middle statuses in reverse pipeline
  order (plan, design, arch, testcases, requirements).
- `register_web_statuses(context)` — registers the web automate line: the completed-accept
  status anchored at the built-in done status, plus the middle statuses in reverse pipeline
  order (plan, design, requirements). The web pipeline writes no testcases or arch artifacts,
  so the line carries no statuses for them; it shares its artifact names with the automate
  line and both apply independently.
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
    register_web_statuses,
)


def register_hooks(hooks):
    hooks.subscribe("statuses", "register_statuses", "api.automate", register_automate_statuses)
    hooks.subscribe("statuses", "register_statuses", "web.automate", register_web_statuses)
    hooks.subscribe("statuses", "register_statuses", "api.fix", register_fix_statuses)
    hooks.subscribe("statuses", "register_statuses", "api.patch", register_patch_statuses)
```

- Hook names are local to the tool; `api.automate`, `web.automate`, `api.fix`, and `api.patch`
  are the stable names.
- Each hook receives its registration surface by the parameter name `context`.
- The moments are independent — subscribing to a subset is legitimate.

## Preconditions and side effects relevant to the consumer

- Registration order inside each hook is normative — the consumer never reorders or filters
  the calls.
- Every line is an add-only registration against built-in statuses; a skipped registration
  (unresolvable anchor) logs a warning and never aborts the command.
- Statuses show qualified as `pybuggy.<name>` — the platform assigns the tool identity.
