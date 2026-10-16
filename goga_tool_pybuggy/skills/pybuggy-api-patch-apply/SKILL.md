---
name: goga-tool-pybuggy-api-patch-apply
description: Apply the confirmed deltas — validate them against the DSL before writing, then edit, add, delete, and move Routines/cells in the affected CODEMANIFESTs, create/update the tool usage files `.goga/usages/cooks/<key>.md`, and wire the usage keys into Headers (no test code); the report of changed CODEMANIFESTs and usage files is saved to the path printed by `goga history path -f apply.md`
---

# Pybuggy API Patch — Apply Manifests

## Identity

You are a manifest materialization engineer. You apply the confirmed dossier to the
CODEMANIFESTs of the affected cells:

- annotation edits
- signature edits
- Routine additions
- Routine deletions
- cell moves
- Header usages changes

You materialize the confirmed usages delta: the new `.goga/usages/cooks/<key>.md` files
and the updates to the files whose tool API the patch changes. You write **manifests
and usage files only** — no test code: the test-code half of every change lands through
the plan and build stages (the defining rule: every change lands in the CODEMANIFEST
and in the test code together — this stage writes the manifest half and leaves the tree
consciously out of sync until the build).

## Mission

Validate the confirmed dossier against the DSL **before** writing anything, apply every
confirmed group of it to the manifests and usage files on disk, validate the result
with `goga lint`, and record the changed CODEMANIFESTs and usage files in the apply
report.

## Paths

Input: the path printed by `goga history path -f impact.md` — the confirmed dossier.

Pre-flight:
- the dossier is missing — halt: the review stage must run first.
- `goga --help` is unavailable — halt and inform the user.

## Context Initialization

Before the phases, load context via the **Skill tool**:

- **`goga-cell`** — the CODEMANIFEST DSL specification.
- **`goga-tool-pybuggy-api-cookbook`** — test cell principles (the strict annotation
  structure, the base block, tools wiring).
- **`goga-cell-python`** — Python language rules (naming, location).
- **`goga-codemanifest-base`** — the base Usages/Annotations block from
  `.goga/config.yml` (the base block this stage never touches).

## Phases

Execute the phases strictly in order.

### Phase 1. Validate the deltas (before writing)

The dossier is materialized verbatim — a structurally broken delta must be caught
before any file changes. Validate every prescribed delta of every confirmed group
against `goga-cell` / `goga-tool-pybuggy-api-cookbook` / `goga-cell-python`:

1. **Annotation deltas** (edits and additions) keep the strict section order
   Purpose → `Precondition:` → (`Data:`) → `Steps:` → (`Use …`), the sections separated
   by a blank line; the fixture parameters keep their backticked `Precondition:`
   bullets.
2. **Signature deltas** keep the format `test_<name>(<fixture>: Endpoint, ...)` without
   output; a wired tool's fixture parameter is typed per its usage file;
   `location: test_<name>.py` without directory traversal.
3. **Backtick references resolve** — every `` `<key>` `` a delta references is wired by
   the group's Header delta or already present in the cell's Header.
4. **The base block stays intact** — every base usage key and the base `Annotations`
   text passes through every delta unchanged (the reference set comes from
   `goga-codemanifest-base`).
5. **No name collisions** — a Routine addition does not collide with a Routine already
   in the target manifest. A collision means the dossier did not account for the
   existing manifest — an error, never a merge.
6. Every named file exists; every deletion and cell move names its target explicitly
   (a move names both paths — the old one and the new one).

On errors — output the list (cell + violation), recommend returning to the review
stage with the findings, and **halt** (change no files).

### Phase 2. Apply the deltas

For every confirmed group of the dossier, in order:

1. **Annotation edits** — update the affected Routine annotations in
   `tests/<spec>/<id>/CODEMANIFEST` exactly as the dossier prescribes.
2. **Signature edits** — when the dossier wires a fixture-providing tool into or out of a
   Routine, update the Routine signature exactly as the dossier prescribes: the tool's
   fixture parameter (typed per the tool's usage file) is added or dropped together with
   its `Precondition:` bullet.
3. **Routine additions** — add the new Routines with their full annotations (per
   `goga-cell` / `goga-tool-pybuggy-api-cookbook` structure). The Phase 1 no-collision
   check holds: a name already present in the manifest is never silently overwritten —
   on a late collision (the manifest changed since the dossier), keep the existing
   Routine, skip the addition, and record the collision in the report.
4. **Routine deletions** — remove the deleted Routines from the manifest; an emptied
   cell (no Routines left) has its CODEMANIFEST removed with it — record both in the
   report.
5. **Cell moves** — for the recorded pair (the old path `tests/<specA>/<id>/` → the
   new path `tests/<specB>/<id>/`): write the manifest at the new path with the fixture
   references in its annotations updated to the new spec paths, remove the old
   manifest, and remove the old directory when it holds no other files; record both
   paths in the report. The moved `test_*.py` files are not touched here — they are
   the plan's move tasks (the defining rule).
6. **Usage files** — create the new `.goga/usages/cooks/<key>.md` files exactly as the
   confirmed dossier prescribes: the structure Domain → How to call → Behavior → What
   NOT to do; the content from the dossier's recorded API source (the user's data or
   the project's dependency file) — never invented; an unknown API keeps the
   "requires clarification" mark. An existing usage is used as is (wired as a key),
   never rewritten outside a confirmed update. Update the usage files whose tool API
   the confirmed dossier changes.
7. **Header usages changes** — add/remove the wired usage keys; never touch the
   base block (the base `Usages` keys and `Annotations` per `goga-codemanifest-base`).
   Before wiring a key, verify its file exists (the files
   created in this phase included) — a missing file is a finding, skip the key and
   record it in the report. Each newly added key appends the line ``Use `<key>` …`` to
   the cell's Header `Annotations`; each removed key drops its line.

Executors may edit CODEMANIFESTs and delete Routines — but only what the confirmed
dossier names, nothing else.

### Phase 3. Validation

1. `goga lint` — on errors, fix them within the dossier's scope (edits confined to the
   files and deltas the dossier names) and re-run; an error outside that scope is a
   finding — record it in the report and halt for a dossier revision (diagnose via
   `goga-cell` / `goga-tool-pybuggy-api-cookbook`; the tooling may produce false path
   errors — re-check the flagged path on disk before classifying the error as a
   defect).
2. `goga schema tests/` — the cells hierarchy reflects the deletions, additions, and
   moves.
3. The base block is present and intact in every changed manifest (per
   `goga-codemanifest-base`) — no edit removed a base key or the base `Annotations`
   text.

### Phase 4. Report

Save the apply report to the path printed by `goga history path -f apply.md`:

- per cell — what changed (edited signatures, edited / added / deleted Routines,
  moved cells with both paths, wired usage keys)
- the usage files created or updated (`.goga/usages/cooks/<key>.md`)
- the validation results
- the consciously out-of-sync test files (their code half lands through the plan)

Fill in every section; an empty section = an incomplete phase = a pipeline STOP.

Then present the report: output the full content of the saved apply report to the user
as the stage's closing message — what changed in which cells, the usage files created or
updated, the validation results, and the consciously out-of-sync test files awaiting
their code half. Never close the stage with the path alone.

## Invariants

### NEVER

- write test code, `__init__.py`, or fixtures — manifests and usage files only
- write a file before the deltas pass the Phase 1 validation — on an error, halt
- overwrite an existing Routine through an addition — a name collision is an error
  (Phase 1) or a recorded skip (Phase 2), never a silent merge
- invent tool API content — only the dossier's recorded API source; unknown stays
  "requires clarification"
- apply a delta the dossier does not name, or skip one it does (the sole exception:
  the recorded late-collision skip of Phase 2)
- hardcode the base block keys — read them from `goga-codemanifest-base`
- leave the tree silently out of sync — the report names every file awaiting its code
  half

### ALWAYS

- validate the dossier against the DSL/cookbook before writing any file
- apply exactly the confirmed dossier
- create a usage file before wiring its key into a Header
- run `goga lint` / `goga schema` after the changes and verify the base block integrity
- record every changed CODEMANIFEST and every created/updated usage file in the apply
  report
- present the saved apply report to the user in full — the stage never ends with the
  path alone
