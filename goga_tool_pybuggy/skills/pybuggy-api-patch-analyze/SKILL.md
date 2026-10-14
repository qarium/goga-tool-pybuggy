---
name: goga-tool-pybuggy-api-patch-analyze
description: Impact analysis over the collected intents — for each intent group, the dossier of affected tests, fixtures, manifests, and usages references, saved to the path printed by `goga history path -f impact.md`
---

# Pybuggy API Patch — Analyze Impact

## Identity

You are the orchestrator of impact analysis: you resolve every collected intent to the
concrete artifacts it touches — tests, fixtures, manifests, usages references — and
build the impact dossier that the later stages rework.

## Input

`goga history path -f intent.md` — the intent document. It is pinned for the entire
session; every intent section becomes its own group of the dossier.

## Context Initialization

Before the analysis, load the context via the **Skill tool**:

- **`goga-cell`** — the CODEMANIFEST DSL specification.
- **`goga-tool-pybuggy-api-cookbook`** — test-cell principles.
- **`goga-cell-python`** — language rules (naming, location).
- **`goga-tool-pybuggy-api-usage`** — the pybuggy runtime (api, asserts).

## Pipeline

The steps run strictly in sequence, one step at a time. The pipeline validates each
step's output before the next step starts.

### Step 1. Read the intents

- Reads: the path printed by `goga history path -f intent.md`
- STOP: the intent document is missing — the collect stage must run first.

### Step 2. Resolve the scope selections

For every intent, resolve its scope constraints (spec / directory / marker) against the
tree on disk:

1. Affected tests — the `test_*.py` files and, where the constraints reach inside a
   file, the individual tests (by name, marker, or invoked endpoint).
2. Affected cells and manifests — the `tests/<spec>/<id>/CODEMANIFEST` of every selected
   test; the Routines whose annotations the intent touches.
3. Affected fixtures — `api/<spec>/<id>/api.py` and the data fixtures/tools the selected
   tests consume.
4. Affected usages references — the `.goga/usages/cooks/<key>.md` keys connected by the
   selected cells.

### Step 3. Build the dossier

Per intent group, record:

1. The selection — what is in, what is explicitly out.
2. The manifest delta — Routine annotation edits, Routine additions, Routine deletions,
   Header usages changes; deletions are marked explicitly (they become deletion tasks in
   the plan).
3. The test-code delta preview — what must change in each `test_*.py` for the manifest
   delta to land (the defining rule: every change lands in the CODEMANIFEST and in the
   test code together).
4. Risks — shared fixtures/tools whose change reaches tests outside the selection.

### Step 4. Produce the dossier

Save the dossier to the path printed by `goga history path -f impact.md` (a repeated
patch cycle overwrites it). Fill in every section; an empty section = an incomplete
step = a pipeline STOP.

## Invariants

### NEVER

- analyze without the intent document — it is the single input
- widen or narrow a scope silently — record what the constraints selected
- hide a deletion — every removed Routine or case is an explicit dossier entry

### ALWAYS

- build one dossier group per intent section
- ground every entry in facts read from disk (files, manifests, usages) — no guesses
