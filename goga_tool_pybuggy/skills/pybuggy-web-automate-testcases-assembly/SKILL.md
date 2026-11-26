---
name: goga-tool-pybuggy-web-automate-testcases-assembly
description: Assembles and materializes the cells — builds each cell's complete CODEMANIFEST from the approved Routines (Header base block + cell-specific usages, Body, Footer), validates against the goga-cell DSL, writes tests/web/<cell>/CODEMANIFEST (merge for existing cells), then runs goga lint / goga schema and verifies every REQ §3 is covered by a Routine
---

# Pybuggy Web Topic Testcases — Assembly

## Identity

You assemble and materialize cells: from the approved Routines and the cell map you build each cell's
complete CODEMANIFEST and write it to `tests/web/<cell>/CODEMANIFEST`. After the write — the
mechanical gates: `goga lint`, `goga schema`, and REQ coverage.

## Core Principle

Assembly is deterministic: the Routine internals are already approved by the user (routines design),
the layout is approved (cell map) — nothing new is designed here. **Only** the CODEMANIFEST is created.

---

## Algorithm

### Step 1. Load context

1. [ROUTINES_REPORT] — approved Routines (full annotations) and the session REQ coverage registry.
2. [CELL_MAP_REPORT] — cells and the Routine → cell assignment.
3. [TESTCASES_INTAKE] — the Header base block and requirements.md (§3 — the REQ registry for
   coverage verification).
4. DSL: `goga-cell` / `goga-cell-python` / `goga-tool-pybuggy-web-cookbook` (loaded by intake).

### Step 2. Assemble each cell's CODEMANIFEST

For each cell from [CELL_MAP_REPORT]:

1. **Header** — the base block from [TESTCASES_INTAKE] **verbatim**; on top of it — cell-specific
   usages: keys from the `Use …` sections of the cell's Routines, only those with existing
   `.goga/usages/cooks/<key>.md` files. Attach each key with the line
   `<key>: .goga/usages/cooks/<key>.md` in `Usages` + the line ``Use `<key>` for <purpose>`` in
   `Annotations`.
2. **Body** — the cell's Routines **verbatim** from [ROUTINES_REPORT]: signature (page fixtures
   `page_<name>`), `location`, annotation.
3. **Footer** — `Author: Goga`, `CreatedAt: <day/month/year>`, `Description: <cell purpose>`.

### Step 3. Validate against the DSL (before writing)

For each CODEMANIFEST (`goga-cell` + `goga-tool-pybuggy-web-cookbook`):

1. Structure: Header → `---` → Body → `---` → Footer; keys are case-sensitive.
2. Header: the base block is identical to [TESTCASES_INTAKE]; cell-specific keys resolve (the
   files exist).
3. Body:
    - Routine only (no `methods`/`properties`, no Entities);
    - signature with no output;
    - `location: test_<name>.py`; snake_case;
    - annotation — strict section structure with blank lines;
    - backtick references (`` `<key>` ``) resolve in the CODEMANIFEST context.
4. Footer: `Author: Goga`, `CreatedAt`, `Description`.

A DSL error — fix it and repeat the validation; an unfixable one — **STOP** (create no files).

### Step 4. Write the CODEMANIFESTs

Process the cells in [CELL_MAP_REPORT] order:

1. **New cell** — create `tests/web/<slug>/CODEMANIFEST` (the directory if necessary).
2. **Existing cell** — **merge, do not overwrite**:
    - before writing, save a copy of the existing file (for a possible rollback);
    - Body: do not touch existing `test_*` Routines — add only the new Routines; a name from the
      plan already exists — keep the existing variant and record the collision in the report
      (warning);
    - Header: merge `Usages` by keys (keep the base block unchanged; add the new cell-specific
      ones); in `Annotations` — the line ``Use `<key>` …`` for each new key;
    - Footer: preserve the existing `CreatedAt`/`Description`; `Author: Goga` stays unchanged.
3. Never create `__init__.py`, test code, or a cell-level `.usages/` — the only artifact is the
   CODEMANIFEST.

### Step 5. Mechanical gates

1. `goga lint` — red → fix and rerun.
2. `goga schema tests/` — the new/merged cells are present in the output.
3. **REQ coverage** (session registry) — a mechanical set comparison:
    - requirements registry: all `REQ-<N>` from §3 of requirements.md;
    - from the Coverage table in [ROUTINES_REPORT]: covered REQs plus excluded ones (an exclusion
      is valid only with a recorded user decision);
    - condition: `covered ∪ excluded = registry` — no gaps, duplicates, or overlaps, and every
      Routine from Coverage is found by name in the materialized CODEMANIFESTs.
      Failure → **STOP** (return to routines design). The registry is not persisted: the
      "requirement → Routine" link lives only in the session; a rerun of the pipeline rebuilds the
      registry from §3.

### Step 6. Produce the [ASSEMBLY_REPORT]

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [ASSEMBLY_REPORT]

## Cells

| Cell  | Path              | Status (created / merged: +N Routine, M collisions) | Usage keys  |
|-------|-------------------|-----------------------------------------------------|-------------|
| […]   | tests/web/<slug>/ | […]                                                 | […]         |

## Validation

[Results of `goga lint` / `goga schema tests/`]

## REQ Coverage

| REQ   | Routine(s) | Cell    |
|-------|------------|---------|
| REQ-1 | test_…     | catalog |

[Every §3 REQ is covered; there are no orphaned Routines.]

## Warnings

[Routine name collisions, skipped cell-specific usages. Write `none` if there are none.]
```

## Invariants

### NEVER

- write test code, `__init__.py`, or a cell-level `.usages/` — the only artifact created is the
  CODEMANIFEST in `tests/web/<slug>/`
- overwrite an existing `tests/web/<slug>/CODEMANIFEST` wholesale — only merge new Routines while
  preserving the existing ones
- design new Routines or change approved annotations — the user has approved them
- create files on DSL errors (halt first)

### ALWAYS

- validate every CODEMANIFEST before writing
- run `goga lint` and `goga schema tests/` after materialization
- verify REQ coverage of the materialized files against §3 of requirements.md
