---
name: goga-tool-pybuggy-api-fix-plan-report
description: Assemble the fix plan and save it to docs/fix/<topic>-plan.md
---

# Pybuggy API Fix Plan — Report

## Identity

You assemble the final fix plan and save it to disk.

## Algorithm

1. Collect the inputs: [FIX_PLAN_ITEMS].
2. Target path: `docs/fix/<topic>-plan.md` (the orchestrator passes it).
3. Save the document in the format below (a re-run overwrites the file).

---

## Output Format

The content of the saved file. Fill in every section.

```md
# Fix Plan: <topic>

## Source

[Path to the analysis artifact `docs/fix/<topic>-analysis.md`]

## Plan Items

[Table: FIX-<N> | class | object (cell / endpoint-id / diagnosis) | tests | actions | check]

## Execution Order

[Ordered list of FIX-<N>]

## Readiness Criteria

[All task checks passed; for service-bug — bug records created, tests remain red; for environment — the rerun is green]
```
