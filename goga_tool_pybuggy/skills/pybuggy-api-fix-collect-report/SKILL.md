---
name: goga-tool-pybuggy-api-fix-collect-report
description: Assemble the collect report and save it to docs/fix/<topic>-collect.md
---
# Pybuggy API Fix Collect — Report

## Identity

You assemble the final collect report from the step results and save it to disk.

## Algorithm

1. Collect the inputs: [FIX_INTAKE], [FIX_FAILURES].
2. Target path: `docs/fix/<topic>-collect.md` (the orchestrator passes it).
3. Save the document in the format below (create `docs/fix/` if it does not exist; a re-run overwrites the file).
4. Transfer the topic version from [FIX_INTAKE] to the artifact (the "Topic Version" section).
5. Keep full tracebacks in the log `docs/fix/<topic>-log.txt` — the report needs only the path to the log.

---

## Output Format

The content of the saved file. Fill in every section.

```md
# Fix Report: <topic>

## Data Source
[description / local run]

## Topic Version
[Spec branch: default / <ref> / local | Environment: standard / <url> | Log divergence: none / <what was found> — from [FIX_INTAKE]. The subsequent cycle stages (analyze/plan/execute/review) read the topic version only from this section]

## Problem Description (verbatim)
[from [FIX_INTAKE]; "not provided" if missing]

## Run
[Command: ... | Log: docs/fix/<topic>-log.txt | Exit code: ... | Totals: passed X, failed Y, errors Z, skipped W. "no run was performed" if the source was description-only]

## Failed Tests
[Table: test | cell (tests/<spec>/<id>/) | file | outcome (FAILED/ERROR/SKIPPED) | category | summary. "no failures" if empty]

## Full Tracebacks
[the log `docs/fix/<topic>-log.txt` or "in the description data, see above"]

## Totals
[N failed/masked tests, distribution by category | "no failures"]
```
