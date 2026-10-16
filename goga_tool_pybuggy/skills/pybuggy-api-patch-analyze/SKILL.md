---
name: goga-tool-pybuggy-api-patch-analyze
description: Impact analysis over the collected intents — settles the dependency usages (`goga usages sync` / `status`), then builds per intent group the dossier of affected tests, fixtures, manifests, and usages deltas (new tools, API updates, Header wiring), saved to the path printed by `goga history path -f impact.md`
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
- **`goga-codemanifest-base`** — the base Usages/Annotations block from
  `.goga/config.yml` (base keys are excluded from tool candidates — Header deltas wire
  cell-specific keys only).

## Pipeline

The steps run strictly in sequence, one step at a time:

- the pipeline validates each step's output before the next step starts

### Step 1. Read the intents

- Reads: the path printed by `goga history path -f intent.md`
- STOP: the intent document is missing — the collect stage must run first.
- Resolve the document's "Open questions" — answer each from the tree where the facts
  allow it; otherwise ask the user (AskUserQuestion, 2–4 options). A question that
  stays open is carried into the dossier's risks with its status.

### Step 2. Ensure dependency usages — WAIT

External tools and libraries are documented in `.goga/usages/`:

- hand-authored in `.goga/usages/cooks/`
- synced read-only in `.goga/usages/<group>/<dep>/`

Settle the dependency usages before resolving the scope — the dossier must reflect
the settled state.

1. `goga usages sync` — materialize missing dependency usages; existing ones stay as is
   (sync fills gaps only).
2. `goga usages status` — dependency usage state; a non-zero exit means drift, not a
   failure.
3. An `out of date` dep — run `goga usages status --info`:
   - changed files irrelevant to the topic's testing — proceed with the local state;
   - changed files relevant — ask the user: refresh via
     `goga usages -g <group> -d <dep> sync --force` or continue with the local state;
     record the decision in the dossier.

### Step 3. Resolve the scope selections

For every intent, resolve its scope constraints (spec / directory / marker) against the
tree on disk:

1. Affected tests — the `test_*.py` files and, where the constraints reach inside a
   file, the individual tests (by name, marker, or invoked endpoint).
2. Affected cells and manifests — the `tests/<spec>/<id>/CODEMANIFEST` of every selected
   test; the Routines whose annotations the intent touches. For a cell move, record
   both paths — the source and the target.
3. Affected fixtures — `api/<spec>/<id>/api.py` and the data fixtures/tools the selected
   tests consume.
4. Affected usages references — the `.goga/usages/cooks/<key>.md` keys connected by the
   selected cells.
5. Tool needs of the intents — the tools an intent introduces or re-binds. A tool is
   **anything new the changed tests consume**:

   - a library
   - a fixture
   - a dataset
   - a decorator/marker
   - a pattern (per `goga-tool-pybuggy-api-cookbook`)

   For every tool, look up its usage among the existing ones (`.goga/usages/`): an
   existing usage is used as is and wired into the cell; a tool with no usage file is
   a candidate for a **new usage** (the key, purpose, and API source agreed at the
   review stage); a tool whose API the intent changes — its usage file is a candidate
   **update**.

### Step 4. Build the dossier

Per intent group, record:

1. The selection — what is in, what is explicitly out.
2. The manifest delta — one entry per change, marked with its task kind:
   - Routine signature edits — a signature edit lands whenever an intent wires a
     fixture-providing tool into (or out of) a Routine: the signature gains (or drops)
     the tool's fixture parameter, typed per the tool's usage file, together with its
     `Precondition:` bullet
   - Routine annotation edits
   - Routine additions
   - Routine deletions — deletions become deletion tasks in the plan
   - Cell moves — moves become move tasks; a cell move records the pair — the old path
     `tests/<specA>/<id>/` → the new path `tests/<specB>/<id>/`:
     - the manifest lands at the new path with the fixture references in its
       annotations updated to the new spec paths
     - the old manifest is removed
     - the moved `test_*.py` files are part of the test-code delta preview
   - Header usages changes — cell-specific keys only
3. The test-code delta preview — what must change in each `test_*.py` for the manifest
   delta to land (the defining rule: every change lands in the CODEMANIFEST and in the
   test code together).
4. The usages delta — per tool:
   - the new usage files to create (`.goga/usages/cooks/<key>.md` — the key, the
     purpose, the intents served, the API source: user / dependency file / requires
     clarification)
   - the usage files to update (the tool API the intent changes)
   - the usage keys to add/remove in cell Headers (existing usages wired into cells
     included) — cell-specific keys only; the base Usages/Annotations keys from
     `.goga/config.yml` stay untouched in every Header delta
5. Risks — shared fixtures/tools whose change reaches tests outside the selection.

### Step 5. Produce the dossier

Save the dossier to the path printed by `goga history path -f impact.md` (a repeated
patch cycle overwrites it). Fill in every section:

- an empty section = an incomplete step = a pipeline STOP

### Step 6. Present the dossier for approval — WAIT

The stage's deliverable is the dossier's content, not its path. Output the full content
of the saved dossier to the user — every intent group with its selection, deltas,
usages delta, and risks — then ask for the approval (AskUserQuestion, 2–4 options):

- **Approve** — the stage ends; the review-impact stage starts only now.
- **Request changes** — the user names what to change; re-resolve the affected
  selections and deltas, save, and present the dossier again — the approval loop
  repeats until an explicit approval.

The pipeline never moves to the next stage on a printed artifact alone.

## Invariants

### NEVER

- analyze without the intent document — it is the single input
- widen or narrow a scope silently — record what the constraints selected
- hide a deletion or a cell move — every removed Routine and every moved cell is an
  explicit dossier entry
- proceed to the review stage without the user's approval of the dossier

### ALWAYS

- build one dossier group per intent section
- keep the base Usages/Annotations block intact — Header deltas wire cell-specific keys
  only
- ground every entry in facts read from disk (files, manifests, usages) — no guesses
- record the usages delta of every intent group — files to create/update, keys to wire
- present the saved dossier to the user in full and obtain the explicit approval — the
  review stage starts only after it
