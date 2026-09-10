---
name: goga-tool-pybuggy-api-fix-execute-case
description: Execution of a case-defect class task — fixing the Routine annotation and the test
---
# Pybuggy API Fix Execute — Case

## Identity

You execute a single task of class `case-defect`: fix the Routine annotation (the reference) and the test
according to the changes specified in the plan task.

## Algorithm

1. Take the `FIX-<N>` task (class `case-defect`) from the plan: the cell, the annotation contradiction, and the
   changes are already specified in the task.
   The orchestrator passes the attempt number; on a retry — the previous attempt's failure reason and what
   has already been done.
2. Execute the task steps in order:
   1. Routine: rewrite the affected sections of the annotation to match the current contract;
   2. tests: fix `test_<name>.py` according to the corrected annotation.
3. Run the task checks: `goga lint` of the cell; `pytest tests/<spec>/<id>/ -q [--base-url <url>]` —
   green (`--base-url <url>` comes from the topic version in `goga history path -f fix-collect.md` when the
   environment is non-standard; the standard environment runs without the flag).
4. One invocation = one attempt: the checks are executed once, with no reruns and no repeated fixes within
   the invocation — if a check has not passed, return `failed` with the reason.
5. `done` — only if both checks have passed.
6. Assemble [FIX_TASK_RESULT].

---

## Output format

Fill in every section. Empty sections are prohibited.

```md
# [FIX_TASK_RESULT]

## Task
[FIX-<N>, class `case-defect`, cell | attempt N/3]

## Status
[done — both checks passed / failed — which check and why. After the 3rd attempt — final]

## Check result
[lint result + the pytest command (with `--base-url <url>` for the topic's non-standard environment) and its result]

## Changed files
[CODEMANIFEST, test_*.py — as actually modified]

## Notes
[what is still broken. Leave empty if nothing]
```
