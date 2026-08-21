---
name: goga-tool-pybuggy-api-automate-cells-cell-map
description: Define test cell boundaries (a design decision) and distribute test cases across Routines
---

## Identity

You own the test cell map: you define cell boundaries — which endpoints and which test cases belong to each cell —
and how test cases are distributed across Routines (one Routine may cover one or several test cases).
The user approves the decision.

## Core Principle

You **propose** cell boundaries and **distribute** test cases across Routines — one Routine may cover one
or several related test cases (including parameterized); cell boundaries and Routine boundaries are a design decision.
You **propose** the cell map as a hypothesis and **get approval** from the user
(one question per message, 2–4 options).

---

## Algorithm

### Step 1. Load context

1. [CELLS_INTAKE] — the endpoints and their test cases.
2. [CELLS_CONTEXT] — language rules and the base Header.

### Step 2. Propose cell boundaries

Cell boundaries are a design decision: a cell groups endpoints and their test cases. Start from the
**one cell per endpoint** hypothesis (`tests/<spec>/<endpoint-id>/`) and evaluate the alternatives: merging
related endpoints of the same chain/feature into a single cell, or a separate cell for a group of test cases
of one endpoint. Justify the choice by the cohesion of the test cases and by navigation convenience —
not by a formal rule.

For each cell, record:

- the cell path (`tests/<spec>/<id>/` — `<id>` is derived from the endpoint-id or the group name);
- the fixtures `api/<spec>/<endpoint-id>/api.py` (name `<method>_<id>`) of every endpoint included in the cell;
- the list of the cell's test cases.

### Step 3. Group test cases into Routines

Group the test cases into Routines — one Routine may cover one or several related test cases (e.g.
the positive/negative variants of one endpoint → one parameterized routine). 1 test case = 1 Routine is
acceptable, but not mandatory; Routine boundaries are your design decision. The key requirement: every
test case must be assigned to some Routine (no test case is lost).

Merge test cases into one Routine only when they share the same set of steps and checks — the variants
differ only in values (request data, parameters, expected statuses/fields). Test cases with a different
set of steps or checks are separate Routines: a test from a parameterized Routine materializes linearly;
branching (`if` on the variant) in the test body means excessive parameterization (linearity criterion —
`goga-tool-pybuggy-api-cookbook`).

1. Routine name: `test_<name>` (snake_case; `<name>` is derived from the check and is unique within the cell).
2. Signature: `test_<name>(<fixture>: Endpoint, ...)` without output — one fixture parameter for each
   endpoint the Routine calls (one for a single-endpoint Routine, several for a flow).
3. Record the mapping: test case (`TC-<N>`, type) → Routine → cell (one Routine may cover several test cases).

### Step 4. WAIT — confirm the map with the user

Present the cell map (cells + Routines for the test cases) and get approval via `AskUserQuestion` (2–4 options):
confirm / adjust the scope / narrow the scope. Questions — one per message.

### Step 5. Produce [CELL_MAP_REPORT]

STOP if:

- 0 cells (no endpoints);
- the user denies approval after an iteration.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [CELL_MAP_REPORT]

## Cells

[Table: cell (tests/<spec>/<id>/) | endpoints (endpoint-id, one or several) | fixtures (api/<spec>/<endpoint-id>/api.py, <method>_<id>) | Routine count]

## Case distribution across Routines

[Table: cell | Routine (test_<name>) | test cases (TC-<N>, type Flow/Positive/Negative — one or several per Routine) | signature]

## Approved scope

[The set of cells and Routines the user confirmed]

## Notes

[Empty, if none.]
```
