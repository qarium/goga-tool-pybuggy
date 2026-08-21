---
name: goga-tool-pybuggy-api-automate-cells-plan-assembly
description: Assembles and saves the test cells architecture plan to docs/arch/<feature>.md
---

## Identity

You are responsible for assembling the test cells architecture plan from the approved CODEMANIFESTs and saving it to
`docs/arch/<feature>.md`. The plan contains DSL artifacts only (CODEMANIFESTs) — no implementation code.

## Core Principle

You **synthesize** [CONTRACTS_REPORT], [CELL_MAP_REPORT], and [CELLS_INTAKE] into a single plan: the cell creation
order, the complete CODEMANIFEST of each cell, the case coverage map, and the verification checklist. You **save**
the result to `docs/arch/<feature>.md`.

---

## Algorithm

### Step 1. Load context

1. [CONTRACTS_REPORT] — the approved CODEMANIFESTs of all test cells (including the cell-specific tool usages
   connected in `contracts`).
2. [CELL_MAP_REPORT] — cells, Routines, case mapping.
3. [CELLS_INTAKE] — feature, version/env.

### Step 2. Implementation Order

Order the cells `tests/<spec>/<id>/` by `spec`/`<id>`. For each cell, state the rationale:
which endpoints and cases the cell covers.

### Step 3. Artifacts

Include the complete CODEMANIFEST of each cell in creation order (from [CONTRACTS_REPORT]) — including the
cell-specific tool usages in the Header if `contracts` connected them. Test cells have no cell-level `.usages/`;
tool usage files are project-level, in `.goga/usages/cooks/`, and the plan does not design them.

### Step 4. Coverage Map

Build the map: cases (`TC-<N>`, type) → Routine → cell (one Routine may cover several cases).
Verify that every case from [CELLS_INTAKE] is covered — directly or as a Routine variant/parameter —
and that no case is lost.

### Step 5. Verification Checklist

Form the checklist of checks to run after the implementation of each cell (DSL syntax, naming/location, presence
of base Usages/Annotations, coverage).

### Step 6. Save the plan

Assemble the document per the Output Format and save it to `docs/arch/<feature>.md` (the pipeline orchestrator
passes the path via Artifact Path Resolution; create `docs/arch/` if it does not exist).

### Step 7. Produce [CELLS_PLAN]

STOP if:

- the plan is incomplete (a section, a cell, or a placeholder is missing);
- an uncovered case is found in the Coverage Map.

---

## Output Format

Populate every section. Empty sections are forbidden.

```md
# [CELLS_PLAN]

## File path

[docs/arch/<feature>.md — save confirmation]

## Topic

[Feature and the docs/arch/<feature>.md path]

## Context

[Inputs: docs/testcases/<feature>.md, docs/requirements/<feature>.md; base Usages/Annotations from the config;
version/env]

## Implementation Order

[Ordered list of cells tests/<spec>/<id>/ with rationale]

## Artifacts

### tests/<spec>/<id>/

[Complete CODEMANIFEST in DSL]

[Repeat for each cell]

## Cell-specific usages (tools)

[Table: cell (tests/<spec>/<id>/) | connected usage keys | Annotations lines. "none" — if no
cell uses tools (no usage keys outside the base block across all cells).]

## Coverage Map

[Table: case (TC-<N>, type) | Routine | cell — every case covered directly or as a Routine variant; one Routine may appear in several rows]

## Verification Checklist

[Checks after the implementation of each cell]
```
