---
name: goga-tool-pybuggy-api-fix-analyze-report
description: Assemble the final analysis artifact and save it to the path printed by `goga history path -f fix-analysis.md`
---
# Pybuggy API Fix Analyze — Report

## Identity

You assemble the final analysis artifact and save it to disk.

## Algorithm

1. Collect the pipeline inputs: [FIX_EVIDENCE] and [FIX_CLASSIFICATION].
2. Target path: `goga history path -f fix-analysis.md`.
3. Save the document in the format below (a re-run overwrites the file).

---

## Output format

The content of the saved file. Fill in every section — empty sections are forbidden.

```md
# Fix Analysis: <topic>

## Source
[Path to the collect report `goga history path -f fix-collect.md` and the run log `goga history path -f fix-log.txt`]

## Dossier and Evidence
[Table built from [FIX_EVIDENCE]. Columns: test | Routine | diff (empty/drift) | test↔Routine (matches/distorts) | Routine↔contract (matches/contradicts) | rerun (consistently-failing/intermittent/green/skipped/omitted) | class hypothesis]

## Classification
[Table built from [FIX_CLASSIFICATION]. Columns: test | class | rationale | user decision | plan direction]

## Class Distribution
[Failure class → number of tests]
```
