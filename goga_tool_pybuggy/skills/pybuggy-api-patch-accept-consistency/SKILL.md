---
name: goga-tool-pybuggy-api-patch-accept-consistency
description: Pre-run consistency check of the patch run — every manifest delta landed in the test code together, no orphans, no failure masking, usage keys resolve, Request model, linearity; findings with severities triaged with the user
---

# Pybuggy API Patch Accept — Consistency

## Identity

You own the static consistency check before the run:

- every applied manifest delta landed in the test code;
- every file is mapped to its Routine;
- every failure stays visible;
- every wired usage key resolves.

The confirmed dossier and the apply report are the expected state; the tree is the
actual state; you reconcile the two.

## Core Principle

- Fixes to test files are applied only with user approval.
- A structural desync returns to the patch stages.

You **verify** `test_*.py` against the applied manifests and **record** findings with
severities.

## Algorithm

### Step 1. Load context

1. [ACCEPT_SCOPE] — the changed cells, files, and the patch artifacts.
2. Via the **Skill tool**:
   - `goga-cell`
   - `goga-tool-pybuggy-api-cookbook`
   - `goga-tool-pybuggy-api-usage`
   - `goga-cell-python`
3. Read:
   - the CODEMANIFEST of every changed cell;
   - every changed `test_<name>.py`;
   - the apply report (the expected deltas);
   - the dossier.

### Step 2. Manifest ↔ test-code togetherness

1. Every manifest delta of the apply report landed in the test code: each edited or
   added Routine has its `test_*.py` matching the new annotations; each deleted Routine
   or cell has its test code deleted; each moved cell has its `test_*.py` files at the
   new path and none left at the old one.
2. Orphans: every `test_*.py` maps to a Routine, and every Routine maps to its test
   file.
3. Failure visibility: every changed test runs and reports its own verdict — the
   changed files are free of `pytest.skip`/skip-markers/xfail.
4. Every changed file is recorded in the plan's tasks.
5. Signature edits materialized: a tool's fixture parameter wired by a delta appears in
   the test function's parameters, typed per the tool's usage file.

### Step 3. Usage and request-body compliance

1. Usages consistency: every usage key wired into a changed cell Header has its file
   present (`.goga/usages/cooks/<key>.md`) and is actually consumed by the changed
   tests per the file's documented API — new, updated, and existing tools alike.
2. Request bodies: every valid body of the changed tests is built through the `Request`
   model of its fixture (`json=Request(...)`); a raw `dict` appears only in negative
   paths (per the `pybuggy-api` usage).
3. Linearity: every step and assert of the changed tests runs identically for each
   parameterization variant (the linearity criterion of
   `goga-tool-pybuggy-api-cookbook`; branching that selects steps or asserts by
   variant breaks this).

### Step 4. Findings and decisions — WAIT

Every finding gets a severity and an action:

- **Critical** — a Routine of an applied delta without its test file; `pytest.skip`/
  skip-markers/xfail; a test function without a Routine; a moved cell with test files
  left at the old path.
- **High** — a valid body via `dict`; a lost case step or contract check; a broken
  fixture import; a wired usage key missing its file, or a key the changed tests do
  not consume.
- **Medium** — extra test functions beyond the Routine; a changed file absent from the
  plan records.

Actions per finding (via AskUserQuestion, one question per message, 2–4 options):

1. **Fix `test_*.py` here** — edit the test file following the patch pipeline
   conventions (the Routine's DSL reference; the manifest moves with it when the two
   must move together).
2. **Return to the plan** — on structural discrepancies (tasks missing for changed
   files, deltas without their code half beyond a local fix).
3. **Accept as is** — with an explicit risk record in the report.

Re-verify after every applied fix (the fix introduced no new finding).

STOP if:
- the test files of the applied deltas are not materialized at all — acceptance is
  impossible until `goga build` on the topic workplan;
- the user chose a return to the plan for Critical findings (the acceptance pipeline
  terminates early).

---

## Output Format

Fill in every section; when a section has nothing to report, write `none`.

```md
# [ACCEPT_CONSISTENCY]

## Manifest ↔ test-code togetherness

[Table: Delta (from the apply report) | Test file | Status (landed / missing / partial)]

## Orphans and masking

[test_*.py without a Routine / Routine without a test file / skip-xfail occurrences
with file and line. Write `none` if there is nothing]

## Usage and request-body compliance

[Table: Test | usage keys consumed (resolves/consumed) | body via Request/dict |
policy compliance]

## Findings

[Table: File | Finding | Severity (Critical/High/Medium) | Action (fix here / return to
the plan / accept)]

## Applied fixes

[Edits to test_*.py and manifests made with user approval: file | what changed |
reason. Write `none` if there is nothing]

## Overall

[CONSISTENT / CONSISTENT_WITH_FIXES / INCONSISTENT — with justification]
```
