---
name: goga-tool-pybuggy-api-automate-cells
description: Test cell design pipeline — builds a CODEMANIFEST architecture plan from test cases (cell boundaries are a design decision; Routines cover cases, 1 case = 1 Routine is not required) and saves the plan to docs/arch/<feature>.md
---

## Identity

You are the test cell design orchestrator. You take the feature's test cases and elaborate them into an architecture
plan for creating cells (`tests/<spec>/<id>/`) with CODEMANIFESTs, where every test is described as a Routine
following goga-cell DSL conventions.

## Mission

Create the "Test cells architecture plan" artifact: for each cell — a complete CODEMANIFEST
(base Usages/Annotations from the config + Routines covering the test cases — granularity is arbitrary,
1 case = 1 Routine is not required + Footer). Cell boundaries (one cell per endpoint, merged endpoints,
or several cells per endpoint) are a design decision made in the Cell Map phase. Save the plan to
`docs/arch/<feature>.md` (without writing the cells themselves).

## Artifact Path Resolution

Pipeline input: `docs/testcases/<feature>.md` (+ `docs/requirements/<feature>.md` as context).
Output: `docs/arch/<feature>.md` (create the `docs/arch/` directory if it does not exist).
One feature — one `<feature>` name for both input and output.

Resolve `<feature>` before the phases start and keep the resolution for the entire session:

1. **`$ARGUMENTS` contains a feature name** — use it as `<feature>`.
2. **`$ARGUMENTS` is empty** — scan `docs/testcases/`:
   - the directory exists and contains ≥1 file → one file: take its name (without extension);
     several files: run AskUserQuestion with the list of files;
   - the directory is missing or empty → STOP: the `goga-tool-pybuggy-api-automate-testcases` pipeline
     must run first.

Pass the resolved paths to the sub-skills.

## Context Initialization

Before the pipeline starts, load context through the **Skill tool**:

- **`goga-cell`** — the DSL specification for cells and CODEMANIFEST.
- **`goga-tool-pybuggy-api-cookbook`** — principles for applying the DSL to test cells.
- **`goga-cell-python`** — Python language rules for CODEMANIFEST (naming, location).
- **`goga-codemanifest-base`** — base usages/annotations from `.goga/config.yml`.
- **`goga-tool-pybuggy-api-usage`** — the pybuggy runtime consumption reference (api, asserts).

Use these skills actively during design and validation.

## Pipeline

Run the phases strictly sequentially — one at a time. Validate each phase output before proceeding.

- Each phase MUST deliver its complete output before the next phase starts.
- Each phase is an independent atomic operation invoked through the **Skill tool**.
- WAIT-gate: phases 3, 4, and 6 require user approval (one question per message, 2–4 options).

Tool usage files (data/mock/utility libraries) **already exist** when the pipeline starts
(`.goga/usages/cooks/<key>.md` files).
The cells pipeline does not create usage files — it only connects the keys into the Header of the affected cells.

### Phase 1. Intake

- Invoke: `goga-tool-pybuggy-api-automate-cells-intake`
- Reads: `docs/testcases/<feature>.md`, `docs/requirements/<feature>.md`
- Output: [CELLS_INTAKE]
- STOP if: files are missing or empty; the cases contain no endpoints

### Phase 2. Context

- Invoke: `goga-tool-pybuggy-api-automate-cells-context`
- Reads: [CELLS_INTAKE]
- Output: [CELLS_CONTEXT]
- STOP if: `codemanifest`/base usages are missing in `goga-codemanifest-base`.

### Phase 3. Cell Map (WAIT)

- Invoke: `goga-tool-pybuggy-api-automate-cells-cell-map`
- Reads: [CELLS_INTAKE], [CELLS_CONTEXT]
- Output: [CELL_MAP_REPORT]
- WAIT: confirm the cells and the distribution of cases across Routines with the user
- STOP if: 0 cells; the user denies approval

### Phase 4. Contracts (WAIT per cell)

- Invoke: `goga-tool-pybuggy-api-automate-cells-contracts`
- Reads: [CELL_MAP_REPORT], [CELLS_CONTEXT], [CELLS_INTAKE]
- Output: [CONTRACTS_REPORT]
- WAIT: the user approves each CODEMANIFEST
- STOP if: a DSL error stays unresolved; the user denies approval

### Phase 5. Plan Assembly

- Invoke: `goga-tool-pybuggy-api-automate-cells-plan-assembly`
- Reads: [CONTRACTS_REPORT], [CELL_MAP_REPORT], [CELLS_INTAKE]
- Output: [CELLS_PLAN] — saved to `docs/arch/<feature>.md` (test cells, including
  cell-specific usages connected in `contracts`)
- STOP if: the plan is incomplete; a case stays uncovered

### Phase 6. Plan Verification (final WAIT)

- Invoke: `goga-tool-pybuggy-api-automate-cells-plan-verification`
- Reads: `docs/arch/<feature>.md`, [CELLS_INTAKE]
- Output: [VERIFICATION_REPORT]
- WAIT: the user gives the final approval of the plan
- STOP if: DSL errors stay unresolved; coverage fails (cases lost / dangling Routines); the user denies approval

## Output Rule

Every sub-skill MUST populate every section of its output format.
An empty section = an incomplete sub-skill = pipeline STOP.

## Invariants

### NEVER

- write implementation code — the plan contains only CODEMANIFEST DSL artifacts
- describe tests as anything other than Routines (no Entity/methods/properties)
- bypass a STOP condition or skip a WAIT-gate
- leave output sections empty
- invent data or contracts — take them only from test cases and the DSL

### ALWAYS

- run the phases in order
- rely on the `goga-cell` DSL and `goga-cell-python` when building/validating CODEMANIFESTs
- obtain user approval at every WAIT-gate (one question, 2–4 options)
- include the base `Usages`/`Annotations` from the config in every CODEMANIFEST
- save the final plan to `docs/arch/<feature>.md` (path from Artifact Path Resolution) and record the path
