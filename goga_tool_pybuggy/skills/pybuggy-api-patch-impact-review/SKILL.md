---
name: goga-tool-pybuggy-api-patch-impact-review
description: Review of the impact dossier with the user — per intent group, verification of the selection against the tree and of the prescribed deltas against the DSL (annotation structure, signatures, backtick resolution, base block), then confirmation; the confirmed dossier (the path printed by `goga history path -f impact.md`) is the stage output
---

# Pybuggy API Patch — Review Impact

## Identity

You are the reviewer of the impact dossier: you verify every intent group against the
tree on disk and the `goga-cell` DSL, then walk the groups with the user, confirm or
adjust the selection and the deltas, and deliver the confirmed dossier that the apply
stage executes. The stage produces no separate artifact — the confirmation updates the
dossier itself.

## Input

`goga history path -f impact.md` — the impact dossier. It is pinned for the entire
session.

## Context Initialization

Before the review, load the context via the **Skill tool**:

- **`goga-cell`** — the CODEMANIFEST DSL specification.
- **`goga-tool-pybuggy-api-cookbook`** — test-cell principles (the strict annotation
  structure, the base block, tools wiring).
- **`goga-cell-python`** — language rules (naming, location).
- **`goga-tool-pybuggy-api-usage`** — the pybuggy runtime (api, asserts).
- **`goga-codemanifest-base`** — the base Usages/Annotations block from `.goga/config.yml`
  (the reference for what the Header deltas may never touch).

## Pipeline

The steps run strictly in sequence. The review is interactive — the user confirms every
group.

### Step 1. Verify

- Reads: the path printed by `goga history path -f impact.md`, the CODEMANIFESTs and
  test files it names, the tree state
- STOP: the dossier is missing — the analyze stage must run first.
- Cross-check each group against the facts: the selection matches the scope constraints
  from the path printed by `goga history path -f intent.md`; every named file exists;
  every manifest delta names the Routines it touches; deletions and cell moves are
  listed explicitly.
- Validate every prescribed delta against `goga-cell` / `goga-tool-pybuggy-api-cookbook` /
  `goga-cell-python` — the apply stage materializes the dossier verbatim, so a
  structurally broken delta must be caught here, before the user confirms it:
  1. **Annotation deltas** (edits and additions) keep the strict section order
     Purpose → `Precondition:` → (`Data:`) → `Steps:` → (`Use …`), the sections
     separated by a blank line; the fixture parameters keep their backticked
     `Precondition:` bullets.
  2. **Signature deltas** keep the format `test_<name>(<fixture>: Endpoint, ...)`
     without output; a wired tool's fixture parameter is typed per its usage file.
  3. **Backtick references resolve** — every `` `<key>` `` the deltas reference is
     wired by the group's Header delta or already present in the cell's Header.
  4. **The base block stays untouched** — no delta edits or removes a base usage key or
     the base `Annotations` (the reference set comes from `goga-codemanifest-base`).
- Record every violation as a finding with a severity — **Critical** (a delta would
  break the DSL structure: a wrong section order, an unresolvable backtick, a touched
  base block, a malformed signature), **High** (a named file does not exist; a delta
  names no Routine; a deletion or cell move is not explicit), **Medium** (a cookbook
  deviation that does not break the DSL — a missing blank line between sections, an
  omitted `Data:` where internal data exists).
- No groups in the dossier at all — **STOP**: nothing to review; the analyze stage must
  run first.

### Step 2. Triage — WAIT

- One intent group per message (AskUserQuestion, 2–4 options):
  - **Confirm** — the group is correct as analyzed;
  - **Adjust the scope** — narrow or widen the selection (the user names what changes);
  - **Drop** — the intent leaves this run (recorded in the dossier).
- A group with findings from Step 1 is presented with its findings — one finding at a
  time with its severity and a suggested fix (apply the fix to the dossier / propose an
  alternative / skip):
  - skip is available for Medium findings only.
  - a Critical or High finding is resolved before the group's confirmation.
  - the group is re-verified after a fix before its confirmation.
- **Adjust triggers re-analysis:** the adjusted scope selection is re-resolved against
  the tree — the affected tests, cells, manifests, and usages are rebuilt for the new
  selection, exactly as the analyze stage computes them (an adjustment rebuilds every
  delta from scratch for the new selection).
  - the rebuilt group is presented for confirmation again — a further adjustment
    starts the same rebuild cycle.
- Deletion deltas get an explicit confirmation question of their own — a removed Routine
  or cell returns only as a new intent.
- Cell moves get one too — the move renames the cell path; confirm the pair
  (old path → new path) explicitly.
- The usages delta gets its own confirmation:
  every new usage file (the key, the purpose, the API source — user / dependency file /
  deferred) and every usage-file update is confirmed by name. An unconfirmed tool's
  key never reaches a cell.

### Step 3. Confirm the dossier

1. Apply the confirmed adjustments to the path printed by `goga history path -f
   impact.md` — every group ends the stage with its final decision (confirmed as-is /
   adjusted and re-confirmed / dropped).
2. The confirmed dossier is the stage output; the apply stage executes exactly it.
3. All groups dropped — **STOP**: nothing to apply; inform the user.
4. Present the confirmed dossier for approval — WAIT: output the final content of the
   path printed by `goga history path -f impact.md` (every group with its decision),
   then ask for the approval (AskUserQuestion, 2–4 options):
   - **Approve** — the stage ends; the apply stage starts only now.
   - **Request changes** — the named group re-enters the Step 2 triage (adjust /
     rebuild / re-confirm); the dossier is presented for approval again — the loop
     repeats until an explicit approval.

   The user approves the exact state the apply stage will execute — the pipeline never
   moves on a printed dossier alone.

## Output Rule

Every dossier group ends the stage with an explicit decision. A group without a
decision = an incomplete review = a pipeline STOP.

## Invariants

### NEVER

- confirm a group without the user — one decision per message
- apply adjustments anywhere but the dossier itself
- let a deletion or a cell move pass unconfirmed
- let a DSL-invalid delta reach the apply stage
- end the stage without the user's approval of the confirmed dossier

### ALWAYS

- cross-check the dossier against the intent document and the tree on disk
- validate the prescribed deltas against `goga-cell` / `goga-tool-pybuggy-api-cookbook`
  before the user confirms them
- re-resolve the scope of an adjusted group before its re-confirmation
- record every decision in the dossier (confirmed / adjusted / dropped)
- confirm every new usage file and every usage-file update by name — an unconfirmed
  tool never reaches the apply stage
- present the confirmed dossier for approval — the final content with every group's
  decision; the apply stage starts only after the explicit approval

## Final Self-Check

Before finishing, verify:

1. Was the dossier read, and every group cross-checked against the intent document and
   the tree (files exist, deltas name Routines, deletions and cell moves explicit)?
2. Were the prescribed deltas validated against the DSL/cookbook (annotation structure,
   signature format, backtick resolution, base block untouched) with severities?
3. Was every group confirmed by the user — one decision per message, deletions and cell
   moves with a question of their own, the usages delta by name?
4. Was every adjusted group re-analyzed for its new selection and re-confirmed?
5. Does every group carry its final decision (confirmed as-is / adjusted and
   re-confirmed / dropped) in the dossier?
6. Was the confirmed dossier — its final content with every decision — presented to the
   user and explicitly approved?

If at least one answer is "no" — complete the unfinished check before you return.
