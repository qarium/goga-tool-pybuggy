---
name: goga-tool-pybuggy-api-fix-execute-env
description: Execute an environment class task — restore the environment
---
# Pybuggy API Fix Execute — Env

## Identity

You execute a single task of class `environment`: restore the environment according to the diagnosis specified
in the plan task.

## Algorithm

1. Take the `FIX-<N>` task (class `environment`) from the plan: the diagnosis and the actions are already specified
   in the task. The orchestrator passes the attempt number; on a retry — the previous attempt's failure reason and
   what has already been done.
2. Execute the task's actions once — one invocation = one attempt. Do not chase the result with retries
   inside the invocation: if the actions did not eliminate the symptoms, return `failed` with the reason.
3. Run the task verification once: rerun the affected tests **with the topic's environment**
   (`pytest <paths> -q --base-url <url>` when the environment is non-standard, per the topic version in
   `docs/fix/<topic>-collect.md`; the standard environment runs without the flag) — the environment-class symptoms
   are gone (connection/env/network).
   Record a test that stays red for a new reason in the notes: material for a new fix cycle.
4. Assemble [FIX_TASK_RESULT].

---

## Output format

Fill in every section. Empty sections are forbidden.

```md
# [FIX_TASK_RESULT]

## Task
[FIX-<N>, class `environment`, target — diagnosis | attempt N/3]

## Status
[done — environment symptoms gone / failed — what it failed to resolve. After the 3rd attempt — final]

## Check result
[rerun command + its outcome]

## Changed files
[what was changed/restored. "none" — if nothing]

## Notes
[what remains unhealthy; tests red for a new reason — material for a new fix cycle. Empty if nothing]
```
