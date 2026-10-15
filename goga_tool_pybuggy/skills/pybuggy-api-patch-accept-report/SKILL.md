---
name: goga-tool-pybuggy-api-patch-accept-report
description: Final acceptance report of the patch run — synthesizes scope/consistency/run results into a verdict (ACCEPTED / ACCEPTED_WITH_NOTES / PARTIAL / REJECTED), saved to the path printed by `goga history path -f accept.md`
---

# Pybuggy API Patch Accept — Report

## Identity

You own the final acceptance report: you synthesize the results of all pipeline steps
into a single verdict.

- Use only verified facts from the step reports.
- Treat every triage decision as final.
- Report each outcome exactly as recorded.

## Algorithm

### Step 1. Collect the results

1. [ACCEPT_SCOPE] — the scope: the changed cells, files, the run command.
2. [ACCEPT_CONSISTENCY] — the togetherness status and the applied fixes.
3. [ACCEPT_RUN] — the run results, the triage outcomes, the bug records, the
   pre-existing reds, the unresolved tests.

### Step 2. Determine the verdict

- **ACCEPTED** — the whole suite is green (passed or fixed); no unresolved consistency
  findings; no unresolved tests.
- **ACCEPTED_WITH_NOTES** — every patch change landed and every patch-touched test is
  green or triaged; service-bug records and/or pre-existing reds are recorded (those
  defects sit outside the patch's accountability), and/or findings are accepted as is.
- **PARTIAL** — unresolved tests remain (the fix cap exhausted, or handed back to a
  stage); part of the changes is confirmed, the rest returns (collect / design / plan).
- **REJECTED** — the suite did not run (environment failure), or the manifest ↔
  test-code consistency is structurally broken (the changes are not materialized).

Any recorded bug record, pre-existing red, or finding accepted as is caps the verdict
at ACCEPTED_WITH_NOTES.

### Step 3. Assemble the report

Synthesize the report from the verified facts collected in Step 1, using the format
below:

- Include the BUG-ID (`BUG-<topic>-<N>`) and the record path for every bug record.
- Include the file for every fix.
- Save the report to the path printed by `goga history path -f accept.md`.
- Fill in every section; an empty section = an incomplete step = a pipeline STOP.

---

## Output Format

```md
# [ACCEPT_REPORT]

## Summary

[One paragraph: what was verified, what ran, the outcome]

## Scope

[From ACCEPT_SCOPE: the changed cells, files, the run command — as a concise table]

## Consistency

[From ACCEPT_CONSISTENCY: the togetherness status + the fixes applied to the test files
and manifests]

## Test Run

[From ACCEPT_RUN: passed / fixed / bugs / pre-existing red / unresolved — the run and
triage results]

## Bug Records

[Table: BUG-ID | Endpoint | Summary | Severity | Record path. Write `none` if there is
nothing]

## Open Items

[Table: Item | Handed to (collect/analyze/design/plan/service owner) | Reason.
Write `none` if there is nothing]

## Applied Changes

[Every file changed during acceptance: test_*.py, manifests, the path printed by
`goga history path -f bugs.md`]

## Risks

[Table: Risk | Severity | Mitigation. Write `none` if there is nothing]

## Rerun command

[The command to repeat the full suite]

## Verdict

[ACCEPTED / ACCEPTED_WITH_NOTES / PARTIAL / REJECTED — with justification]
```
