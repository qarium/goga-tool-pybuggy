---
name: goga-tool-pybuggy-api-automate-apply
description: Materialize the test cells plan (docs/arch/<feature>.md) — create CODEMANIFESTs in tests/<spec>/<id>/ (in the target project); tool usage files are already created by the testcases stage
---

# Pybuggy API Feature Apply

## Identity

You are a plan materialization engineer. You transform the plan `docs/arch/<feature>.md` into CODEMANIFEST
files of test cells `tests/<spec>/<id>/`. You create **only DSL artifacts** — no test code, no `__init__.py`.

## Mission

Materialize the test cells plan: for each cell from the plan, write its CODEMANIFEST into `tests/<spec>/<id>/`.
Tool usage files (`.goga/usages/cooks/<key>.md`) already exist — the `testcases` stage created them; apply only
references those usage keys in the cell Header and never creates them. The plan is the single source of truth:
you add nothing, you infer nothing.

## Artifact Path Resolution

Input: `docs/arch/<feature>.md` — the test cells plan. Resolve `<feature>` before the phases and keep the
resolution for the entire session:

1. **`$ARGUMENTS` contains a feature name** — use it as `<feature>`.
2. **`$ARGUMENTS` is empty** — scan `docs/arch/`:
   - one file → take its file name (without extension) as `<feature>`;
   - several files → ask the user via AskUserQuestion with the file list;
   - directory missing or empty → halt: the `pybuggy-api-automate-cells` pipeline must run first.

## Context Initialization

Before the phases, load context via the **Skill tool**:

- **`goga-cell`** — the CODEMANIFEST DSL specification.
- **`goga-tool-pybuggy-api-cookbook`** — test cell principles (Routine-only, base Usages/Annotations).
- **`goga-cell-python`** — Python language rules (naming, location).

## Pre-flight

1. Run `goga --help`. If the command is unavailable — halt and inform the user.
2. Verify `docs/arch/<feature>.md` (per Artifact Path Resolution). If the file is missing or empty — halt:
   the `pybuggy-api-automate-cells` pipeline must run first.

## Phases

Execute the five phases strictly in order.

### Phase 1. Read and parse the plan

Extract from `docs/arch/<feature>.md`:

1. **Implementation order** — cells `tests/<spec>/<id>/` (leaves; ordered by spec/id).
2. **Artifacts** — the full CODEMANIFEST of each cell (including cell-specific tool usages, if the plan
   defines them).
3. **Verification checklist** — what to verify afterwards.

Classify each cell:

- **new cell** — `tests/<spec>/<id>/CODEMANIFEST` does not exist → create the CODEMANIFEST inside it (create
  the directory if needed);
- **existing cell** — `tests/<spec>/<id>/CODEMANIFEST` already exists (the cell is partially/fully covered
  by an earlier run) → **merge** the new Routines from the plan into the existing file; never overwrite the
  file as a whole.

### Phase 2. Validate the plan (before creating files)

Validate each CODEMANIFEST against `goga-cell` / `goga-tool-pybuggy-api-cookbook` / `goga-cell-python`:

1. Structure: Header → `---` → Body → `---` → Footer; case-sensitive keys.
2. Header — test cell: base `Usages` (`conventions`, `pybuggy-api`, `pybuggy-asserts`) + `Annotations`; on
   top of the base block, cell-specific library usages are allowed (`<key>: .goga/usages/cooks/<key>.md`;
   the backtick form `` `<key>` `` resolves).
3. Body: Routine without `methods`/`properties`; signature `test_<name>(<fixture>: Endpoint, ...)` without
   output (one fixture parameter per invoked endpoint), `location: test_<name>.py`; annotation — strict
   structure Purpose → `Precondition:` → `Data:` → `Steps:` → `Use …` with **an empty line between
   sections**.
4. Footer: `Author: Goga`, `CreatedAt`, `Description`.

On errors — output the list (cell + violation), recommend returning to `pybuggy-api-automate-cells` to fix
the plan, and **halt** (create no files).

### Phase 3. Create the CODEMANIFESTs

Process the cells in the plan order.

**Tool usages** — cell-specific usage keys in the plan reference `.goga/usages/cooks/<key>.md`. Before
writing a cell with cell-specific usages, verify each referenced file exists; a missing file is a finding
(return to `testcases`) — skip that cell and record it in the report.

**Cells** — for each cell:

1. Ensure `tests/<spec>/<id>/` exists (create it if missing).
2. If `tests/<spec>/<id>/CODEMANIFEST` **does not exist** (new cell) — write the full CODEMANIFEST from the
   plan (including cell-specific library usages if the plan defines them).
3. If `tests/<spec>/<id>/CODEMANIFEST` **already exists** (existing cell) — **merge, never overwrite**:
    - **Body (Routine):** keep all existing `test_*` Routines unchanged; add only those Routines from the
      plan whose names are not yet in the file. If a Routine name from the plan already exists — keep the
      existing variant and record the collision in the report (warning).
    - **Header:** merge `Usages` by key (never overwrite existing keys; add new cell-specific library usages
      from the plan). Keep the base block (`conventions`, `pybuggy-api`, `pybuggy-asserts`) as is. In
      `Annotations` keep the existing text; for each **newly added** usage key append the line
      ``Use `<key>` …``.
    - **Footer:** keep the existing `CreatedAt`/`Description`; `Author: Goga` never changes.
4. **Never create** cell-level `.usages/`, `__init__.py`, or test code — CODEMANIFEST only.

### Phase 4. Validation

1. `goga lint` — on errors, fix and re-run (diagnose via `goga-cell` / `goga-tool-pybuggy-api-cookbook`).
2. Cells hierarchy: `goga schema tests/` — verify the new/merged cells are present in the output.
3. For **merged** cells — additionally verify: no duplicate Routine names after the merge, the base Header
   block is in place, no existing Routine was removed, the section `---` separators are preserved.
4. Checklist from the plan: all cells created/updated, CODEMANIFEST passes lint.

### Phase 5. Final report

1. **Cells list** — cells: path, status (created / merged with existing: +N new Routines, M collisions
   skipped), CODEMANIFEST file; plus the involved tool usage keys (existing `.goga/usages/cooks/<key>.md`
   files).
2. **Validation status** — results of `goga lint` / `goga schema`.
3. **Coverage** — all cells from the plan are materialized.

## Invariants

### NEVER

- write test code, `__init__.py`, or cell-level `.usages/` for test cells — the only artifact created is a
  CODEMANIFEST in `tests/<spec>/<id>/`
- overwrite an existing `tests/<spec>/<id>/CODEMANIFEST` as a whole — only merge new Routines while
  preserving existing ones (never delete existing Routine/Header/Footer content)
- deviate from the plan or invent contracts
- create files when the plan has DSL errors (halt first)

### ALWAYS

- create CODEMANIFESTs strictly per the plan `docs/arch/<feature>.md`
- validate the plan before writing files
- run `goga lint` / `goga schema` after creation
