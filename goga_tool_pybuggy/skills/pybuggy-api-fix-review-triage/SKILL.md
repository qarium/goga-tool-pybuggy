---
name: goga-tool-pybuggy-api-fix-review-triage
description: Triage of findings and failed tasks with the user — one at a time, each with a decision
---

# Pybuggy API Fix Review — Triage

## Identity

You triage two kinds of objects from the [REVIEW_FINDINGS] artifact together with the user: findings and failed tasks.
For each object you present the facts and record the user's decision. The decision routes the object into a new cycle
run, a plan rebuild, an accepted risk, or a fix made in this step.

## Algorithm

### Step 1. Triage every finding and failed task — WAIT

One at a time, one object per message:

1. Present the object to the user: for a finding — its location, problem, severity, and evidence; for a failed task —
   its `FIX-<N>` identifier, task class, and check result.
2. Ask the user to choose the resolution (AskUserQuestion; put the recommended option first — see the recommendation
   rules):
   - a **finding** — exactly 4 options:
     - **fix now** — a small local fix, applied on the spot and verified by a cheap check (see "Fix-now boundary");
     - **accept as is** — record it as an accepted risk;
     - **rebuild the plan (plan)** — the plan task is composed incorrectly; rebuild the plan from the current analysis;
     - **new fix cycle (collect)** — the problem goes into a new cycle run starting from a clean collection;
   - a **failed task** — exactly 3 options: new fix cycle / rebuild the plan / accept as is. No "fix now": the task's
     3 attempts are exhausted, and an on-the-spot fix would circumvent the attempt budget.
3. Recommendation rules — which option to put first:
   - the fix is a bounded local edit with a cheap direct check — a broken traceability link, an incomplete record, a
     template deviation in a documentation artifact → **fix now**;
   - the finding predates the cycle, was consciously accepted by the plan, or is a Medium observation outside plan
     execution → **accept as is**;
   - the analysis holds, but the plan task was composed incorrectly → **rebuild the plan**;
   - the facts are stale — regressions, Edit Invariants violations, masked failures, a changed spec or environment →
     **new fix cycle**.
4. On **fix now**: apply the fix at once, run its check once, record the fix, the check outcome, and the changed
   files. If the fix outgrows the "Fix-now boundary" or its check fails — do not force it: leave the state honest and
   re-ask the user with the remaining options (rebuild the plan / new fix cycle / accept as is).
5. Record the user's decision.

### Step 2. Assemble [REVIEW_DECISIONS]

---

## Output format

Fill in every section. Empty sections are prohibited ("none" is the explicit marker).

```md
# [REVIEW_DECISIONS]

## Decisions

[Table: object | type (finding / failed task) | decision (fix now / new cycle / rebuild plan / accept) | user comment. "none" — if there is nothing to triage]

## On-the-spot fixes

[Table: object | fix applied | check + outcome | changed files. "none" — if there were no fix-now decisions]

## Open items

[What goes into a new fix cycle / a plan rebuild. "none" — if nothing]
```