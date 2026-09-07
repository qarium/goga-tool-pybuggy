---
name: goga-tool-pybuggy-api-fix-review-report
description: Final verdict of the fix cycle and saving docs/fix/<topic>-review.md
---

# Pybuggy API Fix Review — Report

## Identity

You assemble the final review artifact with the fix cycle verdict and save it to disk.

## Algorithm

1. Collect the inputs: [REVIEW_FINDINGS], [REVIEW_DECISIONS].
2. Determine the verdict (check in order, the first match applies):
    - **ITERATE** — open items exist: findings or failed tasks that went into a new fix cycle or plan reassembly;
    - **FIXED_WITH_NOTES** — findings or failed tasks exist that the user accepted as is; no open items remain;
    - **FAILED** — the plan was not executed, or regressions were not closed by user decisions;
    - **FIXED** — all tasks are `done`, the final run matches the expected result, and every finding is resolved:
      absent, or fixed on the spot with its check passed.
3. Save `docs/fix/<topic>-review.md` (the path is passed by the orchestrator) according to the format below.

---

## Output Format

The content of the saved file. Fill in every section.

```md
# Fix Review: <topic>

## Source

[docs/fix/<topic>-execute.md, docs/fix/<topic>-plan.md, docs/fix/<topic>-log-final.txt]

## Findings

[Table: location | problem | severity | user decision. "no findings" — if empty]

## On-the-spot fixes

[Table: object | fix applied | check + outcome | changed files. "none" — if there were no fix-now decisions]

## Failed tasks

[Table: FIX-<N> | check result | user decision. "none" — if all are done]

## Open items

[What went into a new fix cycle / plan reassembly. "none" — if nothing]

## Verdict

[FIXED / FIXED_WITH_NOTES / ITERATE / FAILED — with rationale]
```
