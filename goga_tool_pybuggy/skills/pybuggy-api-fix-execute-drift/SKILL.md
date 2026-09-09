---
name: goga-tool-pybuggy-api-fix-execute-drift
description: Execute a spec-drift class task — align the cell to the new spec
---
# Pybuggy API Fix Execute — Drift

## Identity

You execute exactly one task of class `spec-drift`: you align the cell to the new spec by following the steps that the plan task specifies.

## Algorithm

1. Take the `FIX-<N>` task (class `spec-drift`) from the plan: the task already specifies the endpoints, the cell, the tests, and the changes.
   The orchestrator passes you the attempt number; on a retry it also passes the previous attempt's failure reason and what has already been done.
2. Execute the task steps in this order:
   1. artifacts: run `goga tool pybuggy endpoint pull` with the ref from the topic version
      (`goga history path -f fix-collect.md`, section "Topic Version": feature-ref → `--ref <ref>` /
      `--ref <spec>:<ref>`; default branch → omit `--ref`; local → skip pull);
      then run `goga tool pybuggy endpoint generate <endpoint-id> [...] -f`;
   2. Routine: update the affected annotation sections in the cell CODEMANIFEST;
   3. tests: update `test_<name>.py` to match the new annotations.
3. Run the task checks:
   - `goga tool pybuggy endpoint diff <endpoint-id> [...]` — must be empty **under the topic ref**;
   - `goga lint` on the cell;
   - `pytest tests/<spec>/<id>/ -q [--base-url <url>]` — must be green (`--base-url <url>` — from the topic
     version when the environment is non-standard; standard — omit the flag).
4. One invocation = one attempt: the checks are run exactly once, without restarts or repeated edits within the invocation —
   if any check fails, return `failed` with the reason.
5. Return `done` only if all three checks pass.
6. Produce [FIX_TASK_RESULT].

---

## Output format

Fill in every section. Empty sections are forbidden.

```md
# [FIX_TASK_RESULT]

## Task
[FIX-<N>, class `spec-drift`, cell + endpoints | attempt N/3]

## Status
[done — all checks passed / failed — which check and why. After the 3rd attempt — final]

## Check result
[diff outcome + lint outcome + the pytest command (with `--base-url <url>` for the topic's non-standard environment) and its outcome]

## Changed files
[api.py, schemas, CODEMANIFEST, test_*.py — as actually modified]

## Notes
[what remains unhealthy. Empty if nothing]
```
