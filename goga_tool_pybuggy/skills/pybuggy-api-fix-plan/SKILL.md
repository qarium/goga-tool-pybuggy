---
name: goga-tool-pybuggy-api-fix-plan
description: Building the cell fix plan from the analysis classification
---

# Pybuggy API Fix — Plan

## Identity

You are the orchestrator of fix-plan construction.

## Input

`docs/fix/<topic>-analysis.md` — the analysis artifact. `<topic>`: from `$ARGUMENTS`. The document is pinned
for the entire session and passed to every sub-skill.

## Pipeline

Run the steps strictly sequentially, one at a time. Validate each step's output before starting the next.

### Step 1. Build — WAIT

- Skill: `goga-tool-pybuggy-api-fix-plan-build`
- Reads: `docs/fix/<topic>-analysis.md`
- Result: [FIX_PLAN_ITEMS] — plan items grouped by cell, approved by the user
- WAIT: plan approval — iterate until the user confirms
- STOP: the analysis artifact is missing — return to the analyze stage; the user rejected the plan after an iteration

### Step 2. Report

- Skill: `goga-tool-pybuggy-api-fix-plan-report`
- Reads: [FIX_PLAN_ITEMS]
- Result: [FIX_PLAN] — saved to `docs/fix/<topic>-plan.md`

## Output Rule

Every sub-skill must fill in every section of its output format. An empty section = an incomplete sub-skill = a pipeline STOP.
