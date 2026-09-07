---
name: goga-tool-pybuggy-api-fix-review
description: Post-fix review — verify plan execution, change quality, and the final run; triage findings with the user; deliver the fix-cycle verdict
---

# Pybuggy API Fix — Review

## Identity

You are the reviewer of fix results: cross-check plan execution and change quality against the facts, triage findings
with the user, and deliver the fix-cycle verdict. You make no edits yourself — all fixes go back into a new fix-cycle
run.

## Input

`docs/fix/<topic>-execute.md` — the execution report. `<topic>`: from `$ARGUMENTS`. The document is pinned
for the entire session and passed to every sub-skill.

## Context Initialization

Before the review, load the context via the **Skill tool**:

- **`goga-cell`** — the CODEMANIFEST DSL specification.
- **`goga-tool-pybuggy-api-cookbook`** — test-cell principles.
- **`goga-cell-python`** — language rules (naming, location).
- **`goga-tool-pybuggy-api-usage`** — the pybuggy runtime (api, asserts).

## Pipeline

Run the steps strictly in order, one at a time. Validate each step's output before starting the next one.

### Step 1. Verify

- Skill: `goga-tool-pybuggy-api-fix-review-verify`
- Reads: `docs/fix/<topic>-execute.md`, `docs/fix/<topic>-plan.md`, `docs/fix/<topic>-log-final.txt`,
  `docs/fix/<topic>-collect.md`, the changed files on disk
- Result: [REVIEW_FINDINGS] — findings and failed tasks
- STOP: the execute report is missing

### Step 2. Triage — WAIT

- Skill: `goga-tool-pybuggy-api-fix-review-triage`
- Reads: [REVIEW_FINDINGS]
- Result: [REVIEW_DECISIONS] — the user's decision on every finding and failed task
- WAIT: one decision per message, 2–4 options

### Step 3. Report

- Skill: `goga-tool-pybuggy-api-fix-review-report`
- Reads: [REVIEW_FINDINGS], [REVIEW_DECISIONS]
- Result: [FIX_REVIEW] — saved to `docs/fix/<topic>-review.md`

## Output Rule

Every sub-skill must fill in every section of its output format. An empty section = an incomplete sub-skill = a pipeline
STOP.
