---
name: goga-tool-pybuggy-api-fix-review-verify
description: Static verification of plan execution — completeness, readiness criteria, quality of the changes, regressions
---

# Pybuggy API Fix Review — Verify

## Identity

You verify the fix results against the plan and the facts: completeness of plan execution, readiness criteria, the
quality of the changes in the changed files, and regressions. You record findings — the user makes the decisions on
them at triage.

## Algorithm

### Step 1. Completeness of execution

Verify that every `FIX-<N>` task from `docs/fix/<topic>-plan.md` has a status (`done`/`failed`) recorded in
`docs/fix/<topic>-execute.md`; any missing task is an omission.

### Step 2. Plan readiness criteria

1. The task checks from the plan have passed (per the execute report).
2. `service-bug` — records are created in `docs/bugs/<topic>.md` according to the
   `goga-tool-pybuggy-api-fix-execute-bug` template, and the tests are genuinely red.
3. The final run (`docs/fix/<topic>-log-final.txt`) matches the expected result: all tests are green except the
   `service-bug` tests that have bug records.

### Step 3. Quality of the changes, per changed file

From the "Changed files" section of the execute report, check each file:

1. `test_*.py` — a valid body via `Request(...)`; a raw `dict` in negative cases only; no `pytest.skip`, skip markers,
   or `xfail`; the body is linear; the test matches the Routine annotation of its cell.
2. CODEMANIFEST — DSL validity (section structure, order, blank lines between sections); existing Routines are not
   removed.
3. `api/` artifacts — `goga tool pybuggy endpoint diff <endpoint-id>` is empty for the affected endpoints (when the
   topic has a ref from `docs/fix/<topic>-collect.md`: the spec on disk must be at the topic's ref, otherwise the diff
   is unreliable).
4. `docs/bugs/<topic>.md` — records according to the `goga-tool-pybuggy-api-fix-execute-bug` template, with sequential
   numbering.

### Step 4. Regressions

New red tests in the final run compared to the original `docs/fix/<topic>-collect.md` — every regression is a finding.

### Step 5. Assemble [REVIEW_FINDINGS]

Severity: `Critical` (masked failures, lost Routines, plan not executed), `High` (Edit Invariants violation, regression,
run mismatch), `Medium` (incomplete records, deviations from the template).

---

## Output Format

Fill in every section. Empty sections are prohibited ("no findings" / "none" — an explicit mark).

```md
# [REVIEW_FINDINGS]

## Completeness of execution

[every FIX-<N> with its status / omissions as findings]

## Final run vs expectation

[matches / discrepancies with a list]

## Findings

[Table: location (file/task/run) | problem | severity (Critical/High/Medium) | evidence. "no findings" — if empty]

## Failed tasks

[Table: FIX-<N> | class | check result. "none" — if all are done]

## Regressions

[Tests green in collect and red in the final run. "none" — if empty]
```
