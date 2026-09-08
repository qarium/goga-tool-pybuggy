---
name: goga-tool-pybuggy-api-fix-analyze
description: Failure root-cause analysis — for each failed test, determine the cause and the failure class interactively with the user
---

# Pybuggy API Fix — Analyze

## Identity

You are the orchestrator of failure root-cause analysis.

## Input

`goga history path -f fix-collect.md` — the collect report. `<topic>` is the current topic of the history tree (`goga history path`), or a topic named in `$ARGUMENTS`. The document is pinned
for the entire session and passed to every sub-skill.

## Pipeline

The steps run strictly in sequence, one step at a time. The pipeline validates each step's output before the next step starts.

### Step 1. Diagnose

- Skill: `goga-tool-pybuggy-api-fix-analyze-diagnose`
- Reads: the path printed by `goga history path -f fix-collect.md`
- Result: [FIX_EVIDENCE] — per failure: dossier, evidence, class hypothesis
- STOP: the collect report or the log is unavailable; 0 failures in the report — output "no failures" and terminate the pipeline

### Step 2. Classify — WAIT

- Skill: `goga-tool-pybuggy-api-fix-analyze-classify`
- Reads: [FIX_EVIDENCE]
- Result: [FIX_CLASSIFICATION] — per failure: class, justification, resolution, plan direction
- WAIT: ask the user one question per failure
- STOP: the user aborted the triage

### Step 3. Report

- Skill: `goga-tool-pybuggy-api-fix-analyze-report`
- Reads: [FIX_EVIDENCE], [FIX_CLASSIFICATION]
- Result: [FIX_ANALYSIS] — saved to the path printed by `goga history path -f fix-analysis.md`

## Output Rule

Every sub-skill must fill in every section of its output format. An empty section = an incomplete sub-skill = a pipeline STOP.
