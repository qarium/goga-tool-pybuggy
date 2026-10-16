# Investigation Report

## Task Summary

The user reports four `skipping status registration` warnings in the log of every pipeline run
and suspects the statuses subsystem. The requested outcome: the warnings disappear and the
intended statuses register. Evidence shows the four skips are the four middle statuses of the
pybuggy automate line, dropped in cascade by a single unresolvable anchor.

## Candidate Cells

| Cell | Reason | Priority |
|------|--------|----------|
| `goga_tool_pybuggy/statuses` | Carries the defective anchor in `automate.py` | 1 |
| `goga_tool_pybuggy` (root) | `reg_hooks.py` subscription; `assembly.md` anchor table | 2 |
| `tests/statuses` | Asserts the defective anchor literally; no real-axis coverage | 3 |

## Tracing Summary

Every pipeline start calls `assemble_status_scale()` (goga platform). The platform emits the
`statuses/register_statuses` action; pybuggy's `register_hooks` subscribes the three line
routines. All 17 registrations enter the per-tool registry; assembly resolves anchors entry by
entry against the growing list. Reproduced in a venv with real goga 2.0.5 + editable pybuggy:
exactly four warnings, captured with reasons:

```
status=pybuggy.automate.code-designed     reason=unknown after anchor 'specified'
status=pybuggy.automate.arch-prepared     reason=unknown before anchor 'pybuggy.automate.code-designed'
status=pybuggy.automate.testcases-designed   reason=unknown before anchor 'pybuggy.automate.arch-prepared'
status=pybuggy.automate.requirements-created reason=unknown before anchor 'pybuggy.automate.testcases-designed'
```

The assembled scale is missing the four statuses; `goga history status` therefore never
reports them for automate topics.

## Data Flow Analysis

Registration data (name, artifact path, anchors) flows one way: routine → `StatusRegistry`
(add-only, no validation of anchor resolvability) → assembly placement loop. The platform
resolves `after`/`before` per entry in registration order; one unresolvable anchor removes
only that entry, but every later entry chained to it via `before` falls with it. The fix and
patch lines are anchored at the built-in `empty` and chain internally — unaffected.

## Manifest Algorithm Analysis

The `register_automate_statuses` contract mandates six registrations and states the
requirement: "every anchor names an entry registered earlier in this run or a built-in
status". Its own normative table row 3 violates that requirement: `automate.code-designed →
design.md — after specified`. The built-in axis (empty, todo, defined, discovered, backlog,
prototyped, designed, planned, done) contains no `specified` — verified identical in goga
2.0.0, 2.0.1, 2.0.5 wheels; the anchor was unsatisfiable from authoring (commit 9d66ec5).
The package usage `assembly.md` ("the arch/design/plan artifacts are the same files as their
built-in twins") and the docs ("each automate status anchors above its built-in twin") fix
the intended anchor: `design.md` ↔ built-in `designed`.

## Affected Usages

| Usage | Cell | Classification | Reason |
|---|---|---|---|
| `.usages/assembly.md` | goga_tool_pybuggy (root) | DIRECTLY AFFECTED | Anchor table row carries `after specified` |
| `statuses/.usages/registration.md` | goga_tool_pybuggy/statuses | INDIRECTLY AFFECTED | Documents skip-with-warning behavior; text stays truthful, no edit needed |
| `.goga/usages/github/goga/history/registering-hooks.md` | project | INDIRECTLY AFFECTED | Platform reference consumed by the manifest; unchanged |
| `docs/pipelines/api-automate.md` | project docs | INDIRECTLY AFFECTED | Promises the six statuses; becomes true after the fix; no anchor strings to edit |

## Rejected Hypotheses

- "A goga upgrade renamed a built-in status" — rejected: the axis is byte-identical across
  2.0.0/2.0.1/2.0.5; `specified` never existed.
- "The platform emits the warnings spuriously" — rejected: warnings carry per-status reasons
  naming the exact unknown anchors; the platform's skip-with-warning is documented behavior.
- "The fix/patch lines also carry dead anchors" — rejected: reproduction shows all 11
  fix/patch entries placed; only the automate cascade skips.
- "Wrong subscription order in `reg_hooks.py`" — rejected: order only affects placement, not
  resolvability; entries resolve against built-ins regardless.

## Confirmed Root Cause

`goga_tool_pybuggy/statuses/automate.py:19` anchors `automate.code-designed`
`after="specified"` — a status that exists in no goga 2.0.x built-in axis. The platform skips
that entry and, in cascade, the three entries chained below it (`arch-prepared`,
`testcases-designed`, `requirements-created`), producing exactly the four observed warnings
per run and silently dropping the four statuses from every topic scale. The contract table
and the package usage table carry the same unsatisfiable anchor; the test suite asserts it
literally, which is why the defect stayed invisible. Evidence chain: reproduction (4 warnings
+ missing scale entries) → captured skip reasons → axis verification across published wheels →
simulation with the corrected anchor `after="designed"` yields zero skips and the complete,
correctly ordered scale.

## Confidence Level

HIGH — deterministic causality reproduced end-to-end in a real goga 2.0.5 environment; the
corrected variant simulated against the platform's own placement code with zero skips.

## Breaking Change Assessment

1. Existing function call with same arguments produces different behavior? **YES** —
   `register_automate_statuses(context)` called identically will deliver six accepted
   registrations instead of two accepted + four skipped; the assembled scale gains four
   entries.
2. Will existing file paths change? **NO** — artifact paths registered are unchanged.
3. Will output format change? **YES** — `goga history status` output for topics carrying
   `requirements.md`/`testcases.md`/`arch.md`/`design.md` of the automate chain now reports
   the pybuggy status names instead of falling back to built-in resolution; the four warnings
   disappear from run logs.
4. Will return value semantics change? **NO** — the routine returns `None` as before.
5. Will manifest-defined guarantees be altered? **YES (text)** — the normative table's anchor
   value for row 3 changes from the unsatisfiable `specified` to `designed`; the guarantee
   "six statuses register" becomes deliverable rather than altered in intent.
6. Will existing tests break? **YES** — `tests/statuses/test_automate.py` asserts the literal
   anchor `specified` and must be updated with the fix.

**BREAKING CHANGE DETECTED** — per policy the pipeline halts; see Breaking Change Escalation.
What concretely changes for consumers: automation filtering `goga history status` by the
built-in names (`designed`, `planned`, …) for pybuggy automate topics will see those topics
migrate to the `pybuggy.automate.*` names at their next status resolution. Nothing is stored
or generated: the scale is assembled fresh every run ("never cached"), so the change applies
from the next pipeline run after the package edit — no staged rollout is possible or needed.
