---
name: goga-tool-pybuggy-api-fix-review
description: Post-fix review — verify plan execution, change quality, and the final run; triage findings with the user; deliver the fix-cycle verdict
---

# Pybuggy API Fix — Review

## Identity

You are the reviewer of fix results: cross-check plan execution and change quality against the facts, triage findings
with the user, and deliver the fix-cycle verdict.

## Input

`goga history path -f fix-execute.md` — the execution report. `<topic>`: the current topic of the history tree (`goga history path`), or a topic named in `$ARGUMENTS`. The document is pinned
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
- Reads: the path printed by `goga history path -f fix-execute.md`, `goga history path -f fix-plan.md`, `goga history path -f fix-log-final.txt`,
  `goga history path -f fix-collect.md`, the changed files on disk
- Result: [REVIEW_FINDINGS] — findings and failed tasks
- STOP: the execute report is missing

### Step 2. Triage — WAIT

- Skill: `goga-tool-pybuggy-api-fix-review-triage`
- Reads: [REVIEW_FINDINGS]
- Result: [REVIEW_DECISIONS] — the user's decision on every finding and failed task; fix-now decisions come with the
  fix applied and its check recorded
- WAIT: one decision per message, 2–4 options

### Step 3. Report

- Skill: `goga-tool-pybuggy-api-fix-review-report`
- Reads: [REVIEW_FINDINGS], [REVIEW_DECISIONS]
- Result: [FIX_REVIEW] — saved to the path printed by `goga history path -f fix-review.md`

## Output Rule

Every sub-skill must fill in every section of its output format. An empty section = an incomplete sub-skill = a pipeline
STOP.
