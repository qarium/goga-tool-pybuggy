---
name: goga-tool-pybuggy-api-fix-execute-final
description: Final run of all the topic's tests and the execution report docs/fix/<topic>-execute.md
---

# Pybuggy API Fix Execute — Final

## Identity

You perform the final run of all the topic's tests after executing the plan and assemble the execution report.

## Algorithm

1. Run all the topic's tests:
   `pytest <paths of all the topic's cells> -q [--base-url <url>] 2>&1 | tee docs/fix/<topic>-log-final.txt`
   (a repeated run overwrites the log; `--base-url <url>` comes from the topic version in `docs/fix/<topic>-collect.md`
   when the environment is non-standard). The cell pool is the union of the cells from `docs/fix/<topic>-plan.md` and
   `docs/fix/<topic>-collect.md`; record the totals (passed/failed/errors/skipped).
2. Collect the results of all tasks: the `done` / `failed` statuses from the executors' [FIX_TASK_RESULT].
3. Save `docs/fix/<topic>-execute.md` (the path is passed by the orchestrator) according to the format below.

---

## Output format

The content of the saved file. Fill in every section.

```md
# Fix Execute: <topic>

## Source

[docs/fix/<topic>-plan.md]

## Tasks

[Table: FIX-<N> | class | status (done/failed) | check result | changed files]

## Final run

[command | log docs/fix/<topic>-log-final.txt | totals passed/failed/errors/skipped]

## Changed files

[full list: test_*.py, CODEMANIFEST, api/, docs/bugs/]

## Summary

[done X, failed Y — input for the review stage]
```
