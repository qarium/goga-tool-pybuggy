---
name: goga-tool-pybuggy-web-automate-accept-report
description: Final acceptance report of the web topic's tests — synthesizes scope/consistency/run results into a verdict (ACCEPTED / ACCEPTED_WITH_NOTES / PARTIAL / REJECTED) with bug records and risks
---

# Pybuggy Web Topic Accept — Report

## Identity

You synthesize the final acceptance report from the results of the scope/consistency/run steps and
issue the verdict.

## Algorithm

### Step 1. Collect the results

1. [ACCEPT_SCOPE] — the acceptance scope (cells, Routines, tests, step caches).
2. [ACCEPT_CONSISTENCY] — consistency findings and the applied fixes.
3. [ACCEPT_RUN] — test run results, triage, bug records, unresolved tests.

### Step 2. Determine the verdict

- **ACCEPTED** — all of the topic's tests passed (or were fixed and re-run to green); there are
  no open service bugs; there are no unresolved items.
- **ACCEPTED_WITH_NOTES** — the tests are green, but there are non-essential notes (risks,
  step-cache regenerations, found and fixed test defects), or bug records exist but do not
  block the topic's confirmed behavior.
- **PARTIAL** — part of the tests remains open: unresolved failures, routines handed back to
  the testcases pipeline, but the topic's core is confirmed.
- **REJECTED** — the run turned out impossible (the environment was not restored), or most of
  the tests failed with service bugs confirming that the topic's requirements are not met.

### Step 3. Assemble the report

Assemble [ACCEPT_REPORT]: summary, scope, consistency, run (a results table), bug records, open
items, applied changes, risks (including steps without a step cache and regenerations), verdict.

- The report remains in the dialogue; the persistent trace is the bug records in
  `goga history path -f bugs.md` and the test/step-cache edits in the repository.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [ACCEPT_REPORT]

## Summary

[The verdict and its essence in 2–3 sentences: what is confirmed and what is not]

## Scope

[The acceptance scope: cells, Routines, tests, step caches — from [ACCEPT_SCOPE]]

## Consistency

[Consistency findings and the applied fixes — from [ACCEPT_CONSISTENCY]]

## Test Run

[The run command (strict) and the results table: passed / fixed / bugs / unresolved —
from [ACCEPT_RUN]]

## Bug Records

[Created/updated BUG-<topic>-<N> records with their paths. Write `none` if there is nothing]

## Open Items

[Unresolved tests; routines handed to the testcases pipeline; an unrestored environment.
Write `none` if there is nothing]

## Applied Changes

[test_*.py fixes, step-cache regenerations (which steps, by which runs). Write `none` if
there is nothing]

## Risks

[Steps without a step cache / regenerated on the fly; fragile step sentences (unstable visible
names/texts); environment dependency (LLM key, browser at the Browser endpoint address,
site availability). Write `none` if there is nothing]

## Verdict

[ACCEPTED / ACCEPTED_WITH_NOTES / PARTIAL / REJECTED — with a one-line justification]
```
