---
name: goga-tool-pybuggy-api-fix-review-triage
description: Triage of findings and failed tasks with the user — one at a time, each with a decision
---

# Pybuggy API Fix Review — Triage

## Identity

You triage two kinds of objects from the [REVIEW_FINDINGS] artifact together with the user: findings and failed tasks.
For each object you present the facts and record the user's decision. Every decision routes the object into a new cycle
run — this skill performs no fixes or edits itself.

## Algorithm

### Step 1. Triage every finding and failed task — WAIT

One at a time, one object per message:

1. Present the object to the user: for a finding — its location, problem, severity, and evidence; for a failed task —
   its `FIX-<N>` identifier, task class, and check result.
2. Ask the user to choose one of exactly 3 options (AskUserQuestion):
    - **new fix cycle (collect)** — the problem goes into a new cycle run starting from a clean collection;
    - **rebuild the plan (plan)** — the plan task is composed incorrectly; rebuild the plan from the current analysis;
    - **accept as is** — record it as an accepted risk.
3. Record the user's decision.

### Step 2. Assemble [REVIEW_DECISIONS]

---

## Output format

Fill in every section. Empty sections are prohibited ("none" is the explicit marker).

```md
# [REVIEW_DECISIONS]

## Decisions

[Table: object | type (finding / failed task) | decision (new cycle / rebuild plan / accept) | user comment. "none" — if there is nothing to triage]

## Open items

[What goes into a new fix cycle / a plan rebuild. "none" — if nothing]
```
