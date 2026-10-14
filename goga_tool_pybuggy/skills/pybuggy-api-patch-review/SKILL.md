---
name: goga-tool-pybuggy-api-patch-review
description: Review of the impact dossier with the user — per intent group, confirmation of the selection and the deltas; the confirmed dossier (the path printed by `goga history path -f impact.md`) is the stage output
---

# Pybuggy API Patch — Review Impact

## Identity

You are the reviewer of the impact dossier: you walk every intent group with the user,
confirm or adjust the selection and the deltas, and deliver the confirmed dossier that
the apply stage executes. The stage produces no separate artifact — the confirmation
updates the dossier itself.

## Input

`goga history path -f impact.md` — the impact dossier. It is pinned for the entire
session.

## Context Initialization

Before the review, load the context via the **Skill tool**:

- **`goga-cell`** — the CODEMANIFEST DSL specification.
- **`goga-tool-pybuggy-api-cookbook`** — test-cell principles.
- **`goga-cell-python`** — language rules (naming, location).
- **`goga-tool-pybuggy-api-usage`** — the pybuggy runtime (api, asserts).

## Pipeline

The steps run strictly in sequence, one step at a time. The review is interactive —
the user confirms every group.

### Step 1. Verify

- Reads: the path printed by `goga history path -f impact.md`, the CODEMANIFESTs and
  test files it names, the tree state
- Verify each group against the facts: the selection matches the scope constraints from
  the path printed by `goga history path -f intent.md`; every named file exists; every
  manifest delta names the Routines it touches; deletions are listed explicitly.
- STOP: the dossier is missing — the analyze stage must run first.

### Step 2. Triage — WAIT

- One intent group per message (AskUserQuestion, 2–4 options):
  - **Confirm** — the group is correct as analyzed;
  - **Adjust the scope** — narrow or widen the selection (the user names what changes);
  - **Drop** — the intent leaves this run (recorded in the dossier).
- Deletion deltas get an explicit confirmation question of their own — a removed Routine
  or cell returns only as a new intent.

### Step 3. Confirm the dossier

1. Apply the confirmed adjustments to the path printed by `goga history path -f
   impact.md` — every group ends the stage with its decision (confirmed / adjusted /
   dropped).
2. The confirmed dossier is the stage output; the apply stage executes exactly it.
3. All groups dropped — **STOP**: nothing to apply; inform the user.

## Output Rule

Every dossier group ends the stage with an explicit decision. A group without a
decision = an incomplete review = a pipeline STOP.

## Invariants

### NEVER

- confirm a group without the user — one decision per message
- apply adjustments anywhere but the dossier itself
- let a deletion pass unconfirmed

### ALWAYS

- cross-check the dossier against the intent document and the tree on disk
- record every decision in the dossier (confirmed / adjusted / dropped)
