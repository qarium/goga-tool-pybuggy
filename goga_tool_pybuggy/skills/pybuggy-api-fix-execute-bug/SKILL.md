---
name: goga-tool-pybuggy-api-fix-execute-bug
description: Execute a service-bug class task — write a bug record to the path printed by `goga history path -f bugs.md`
---
# Pybuggy API Fix Execute — Bug

## Identity

You execute one task of class `service-bug`: you write a bug record for the service from the dossier already
specified in the plan task.

## Algorithm

1. Take the `FIX-<N>` task (class `service-bug`) from the plan: the problem, the failed tests, and the dossier are
   already written in the task. The orchestrator passes the attempt number.
2. Append the record `BUG-<topic>-<N>` to the path printed by `goga history path -f bugs.md` (sequential numbering; keep the existing records
   intact, append the new one to the end of the file) using the template below. One record covers one problem and
   all tests that failed because of it; keep the full traceback in `goga history path -f fix-log.txt`. The file is created
   with the header `# Bugs — <topic>` and a brief description (1–2 lines); records are appended under it.
3. Task verification: the record is created. Red tests are the expected outcome, not a failure. One call = one
   attempt: if the record is not created, return `failed` with the reason — do not re-read and re-write the file
   in a loop.
4. Produce [FIX_TASK_RESULT].

## Record template

```md
## BUG-<topic>-<N>: <the problem stated concretely — what is wrong, in one sentence>

- **Date:** <day/month/year>
- **Endpoint:** <METHOD /path> (tests/<spec>/<id>/)
- **Severity:** <the highest severity among the failed cases: Critical/High/Medium/Low>

### Problem
<Concrete, 2–5 sentences: what the contract/spec requires and what the service actually does (the key fact —
status, body, behavior). The established cause — in one phrase.>

### Failing tests
[Table: test `tests/<spec>/<id>/test_<name>.py` — `test_<name>` | case TC-<N> | Routine | essence of the failure]

### Evidence
<One factual piece of evidence: the actual service response (status + body) or the assert output of one of the
tests. <Traceback/assert output in full from the path printed by `goga history path -f fix-log.txt`.>

### Notes
<Hypotheses, control experiments, observations. Omit if empty.>
```

---

## Output format

Fill in every section. Empty sections are forbidden.

```md
# [FIX_TASK_RESULT]

## Task
[FIX-<N>, class `service-bug`, problem + failed tests | attempt N/3]

## Status
[done — record created / failed — what prevented it. Final after the 3rd attempt]

## Verification result
[record number BUG-<topic>-<N> + file path; tests red — expected]

## Changed files
[`goga history path -f bugs.md`]

## Remarks
[what remains unhealthy. Empty if nothing]
```
