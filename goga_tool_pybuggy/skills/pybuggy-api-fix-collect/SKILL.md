---
name: goga-tool-pybuggy-api-fix-collect
description: Test-failure data collection
---

# Pybuggy API Fix — Collect

## Identity

You are the orchestrator of failure-data collection.

## Pipeline

The steps run strictly in sequence, one step at a time. The pipeline validates each step's output before the next step starts.

### Step 1. Intake

- Skill: `goga-tool-pybuggy-api-fix-collect-intake`
- Input: `$ARGUMENTS` — problem description
- Result: [FIX_INTAKE]
- STOP: the user provided no problem description and declined a local run; the environment is unavailable (pytest or the plugin fails to start, the SUT does not respond)

### Step 2. Analyze

- Skill: `goga-tool-pybuggy-api-fix-collect-analyze`
- Reads: [FIX_INTAKE]
- Result: [FIX_FAILURES]

### Step 3. Report

- Skill: `goga-tool-pybuggy-api-fix-collect-report`
- Reads: [FIX_INTAKE], [FIX_FAILURES]
- Result: [FIX_COLLECT] — saved to `docs/fix/<topic>-collect.md`

## Output Rule

Every sub-skill must fill in every section of its output format. An empty section = an incomplete sub-skill = a pipeline STOP.
