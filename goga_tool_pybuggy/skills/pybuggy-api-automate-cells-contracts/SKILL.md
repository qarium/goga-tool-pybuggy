---
name: goga-tool-pybuggy-api-automate-cells-contracts
description: Assembles the complete CODEMANIFEST of each test cell (Header, Body with Routines, Footer) and validates it against the DSL
---

## Identity

You are responsible for assembling the complete CODEMANIFEST of every test cell: Header (base Usages + Annotations),
Body (Routines covering the test cases — one Routine may cover several cases), and Footer. Every cell passes
DSL validation and user approval.

## Core Principle

You **assemble** each CODEMANIFEST strictly per the `goga-cell` DSL and `goga-cell-python`, relying on the
[CELL_MAP_REPORT] and [CELLS_CONTEXT] artifacts, and you **validate** its syntax and semantics. Describe tests
**only as Routines**. You **present** every cell to the user for approval.

---

## Algorithm

### Step 1. Load context

1. [CELL_MAP_REPORT] — cells, Routines, case mapping.
2. [CELLS_CONTEXT] — base Header (Usages + Annotations), language rules.
3. [CELLS_INTAKE] — case content (preconditions, steps, expectations).

### Step 2. Assemble the Header — base block

Take the base block from [CELLS_CONTEXT] (shared by all test cells):

- `Usages`: `conventions`, `pybuggy-api`, `pybuggy-asserts` (from the config).
- `Annotations`: base text from the config.

If a cell uses a tool (per the case preconditions in [CELLS_INTAKE]), add on top of the base block — only in the
affected cells — a `<key>: .goga/usages/cooks/<key>.md` entry to `Usages` and a ``Use `<key>` for <data
setup/mocks/utilities>`` line to `Annotations`. Never modify the base block.

Connect cell-specific tool usages (data/mock/utility libraries) **here**: the usage files
`.goga/usages/cooks/<key>.md` already exist, so add the key directly to the affected cell's Header `Usages` and
reference it with a backtick. Take the keys from the case preconditions ([CELLS_INTAKE]) and §8 of the requirements.

### Step 3. Assemble the Body — Routines covering the cases

For each cell, take every Routine from [CELL_MAP_REPORT] (one Routine may cover one or several cases). When a
Routine covers >1 case, express the parameterization in its annotation — enumerate the variants in `Data:` and/or
`Steps`; the Routine name `test_<name>` and `location: test_<name>.py` stay single per Routine. Variants of one
Routine must fit a single linear `Steps` sequence — identical steps and checks, differing only in values. Variants
that diverge in steps or checks become separate Routines (split the grouped Routine from the map; record the
deviation in the report notes) — `if` branches in the body of the materialized test mean excessive
parameterization.

1. Signature: `test_<name>(<fixture>: Endpoint, ...)` — one fixture parameter per endpoint the Routine calls;
   `location: test_<name>.py`.
2. `annotations` — build per the strict structure from `goga-tool-pybuggy-api-cookbook` (section order is fixed:
   Purpose → `Precondition:` → `Data:` → `Steps:` → `Use …`; **separate sections with a blank line** — after Purpose
   and before each of `Precondition:` / `Data:` / `Steps:` / `Use …`):
    - **Purpose** — what the Routine verifies (from the case title/description), no label. First paragraph.
    - `Precondition:` — bulleted list: for each fixture parameter — `` `<fixture>`: `` with a description of the
      generated fixture `api/<spec>/<id>/api.py` (name `<method>_<id>`, METHOD /path, role — primary SUT or
      verification); plus the case's common preconditions (the `Endpoint` parameter type from the pybuggy runtime,
      the state/data BEFORE the test from [CELLS_INTAKE]). When a tool performs the data setup, reference the key
      in backticks `` `<key>` `` (Step 2 already connected the key to this cell's Header `Usages` — the reference
      resolves immediately).
    - `Data:` — bulleted list of data created inside the test (internal variables, keys, `test_id`, etc.); call
      values (`request`/`response`) stay in `Steps`. Omit it when no such data exists.
    - `Steps:` — numbered steps from the case (Action / Data / Expectation); logic, no code.
      **Request body:** describe a valid body (positive/flow) through the `Request(...)` model (imported from the
      fixture's `api.py`) — **as plain text, without a backtick reference** (the model is external to the
      CODEMANIFEST; backticks only on `` `<fixture>` ``); describe an invalid body (negative — a required field
      missing, a wrong type, an empty body, broken JSON) as a **raw `dict`** with the note "bypassing the pydantic
      model" (otherwise a `ValidationError` fires before the request is sent, and the SUT never gets tested).
      **Never describe a valid body in `dict` notation** `{field: value}` — `Steps` materialize into `test_*.py`
      verbatim, and a `dict` would lose request validation.
    - Usages references (`Use …`) — **only Routine-specific ones**: cell-specific library usages (e.g.
      ``Use `faker` for test_id generation``). The base `pybuggy-api`/`pybuggy-asserts`/`conventions` already sit
      in the Header's global `Annotations` — **do not duplicate** them in the Routine (per `goga-cell`: annotations
      at different levels never duplicate each other). Omit the `Use …` section when no specific usages exist.

### Step 4. Assemble the Footer

`Author: Goga`, `CreatedAt` (day/month/year), `Description` (why this cell exists).

### Step 5. DSL validation

Validate every CODEMANIFEST against `goga-cell`:

1. Structure: Header → `---` → Body → `---` → Footer; case-sensitive keys.
2. Header: correct `Usages`/`Annotations`.
3. Body: a Routine without `methods`/`properties`; the signature declares a parameter type; `location` —
   `<file>.py` with no directory traversal.
4. Backtick references resolve within the CODEMANIFEST context (`<fixture>`, `pybuggy-api`, `pybuggy-asserts`,
   `conventions`, the cell-specific tool keys from the Header `Usages`).
5. Signature nuance: the fixture's `Endpoint` type comes from the pybuggy runtime; the annotation carries the
   descriptive reference.

### Step 6. WAIT — approval per cell

Present each cell's CODEMANIFEST (one at a time) and get approval through `AskUserQuestion`: accept or adjust.
One question per message.

### Step 7. Produce [CONTRACTS_REPORT]

STOP if:

- a DSL error survives an iteration;
- a cell's approval is denied after an iteration.

---

## Output Format

Populate every section. Empty sections are forbidden.

```md
# [CONTRACTS_REPORT]

## Cells and their CODEMANIFESTs

### tests/<spec>/<id>/

[Complete CODEMANIFEST in DSL: Header (Usages + Annotations) → --- → Body (Routine) → --- → Footer]

[Repeat the block for each cell]

## DSL validation results

[Per cell: PASS status / list of fixed errors]

## Approved cells

[List of cells that passed approval]

## Notes

[Fixture type nuance, assumptions, etc. Empty if none.]
```
