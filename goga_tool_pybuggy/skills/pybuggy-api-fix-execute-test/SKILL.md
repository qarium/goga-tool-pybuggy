---
name: goga-tool-pybuggy-api-fix-execute-test
description: Execution of a test-defect class task — fixing the test according to the Routine annotation
---
# Pybuggy API Fix Execute — Test

## Identity

You execute a single task of class `test-defect`: fix the test according to the reference — the Routine annotation —
and the changes specified in the plan task.

## Algorithm

1. Take the `FIX-<N>` task (class `test-defect`) from the plan: the test and the changes are already specified in the
   task. The orchestrator passes the attempt number; on a retry — the previous attempt's failure reason and what
   has already been done.
2. Apply the changes to `test_<name>.py` as defined by the task (the reference is the Routine annotation).
3. Run the task check once: `pytest tests/<spec>/<id>/ -q [--base-url <url>]` — green
   (`--base-url <url>` comes from the topic version in `docs/fix/<topic>-collect.md` when the environment is
   non-standard; the standard environment runs without the flag). One invocation = one attempt: do not re-edit the
   test and do not rerun pytest within the invocation to force a green result — if the check has not passed, return
   `failed` with the reason.
4. Assemble [FIX_TASK_RESULT].

---

## Output format

Fill in every section. Empty sections are prohibited.

```md
# [FIX_TASK_RESULT]

## Task
[FIX-<N>, class `test-defect`, test + cell | attempt N/3]

## Status
[done — pytest green / failed — what was not accomplished. After the 3rd attempt — final]

## Check result
[the pytest command (with `--base-url <url>` for the topic's non-standard environment) + the result]

## Changed files
[test_*.py — as actually modified]

## Notes
[what is still broken. Leave empty if nothing]
```
