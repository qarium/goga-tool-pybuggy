---
name: goga-tool-pybuggy-api-cookbook
description: Principles for applying the goga-cell DSL to design test cells
---
# Pybuggy API Cookbook

## Purpose

Principles for applying the `goga-cell` DSL to design **test** cells. This document adapts `goga-cookbook`
and keeps only what is relevant to tests: tests are described as `Routine` with base
`Usages`/`Annotations` from the project config.

Other skills invoke this skill to load test cell design context.

## Behavior

The invoking skill applies these principles in its own context. The invoking skill must not restate
`goga-cookbook` in full and must not describe the internals of other skills — it uses these principles
to make design decisions about test cells.

---

# Test cell design principles

## Context

Tests are a separate project that uses pybuggy as its framework. A test cell is a folder of tests
created by `goga tool pybuggy generate`:

```
tests/<spec>/<endpoint-id>/
└── CODEMANIFEST
```

Generation creates one directory per endpoint — `tests/<spec>/<endpoint-id>/` — as the starting structure.
The `cells` pipeline (cell-map phase) owns cell boundaries as a design decision: one cell per endpoint,
merging related endpoints into a single cell, or several cells per endpoint are all valid. Fixtures remain
per-endpoint (`api/<spec>/<endpoint-id>/api.py`) — a cell only wires in the ones it needs.

## Test cell CODEMANIFEST

### Design order

1. **Header** — base `Usages` + `Annotations` (the contract operates in the context of the project's base practices).
2. **Body** — `Routine` for test cases: one Routine may cover one or several related cases
   (including parameterized ones); 1 case = 1 Routine is valid but not mandatory.
3. **Footer** — `Author`, `CreatedAt`, `Description`.

### Header

The **base block** of `Usages` and `Annotations` is taken from `.goga/config.yml` (via `goga-codemanifest-base`) and
is **identical for all test cells**:

- `Usages`: `conventions`, `pybuggy-api`, `pybuggy-asserts` (paths in `.goga/usages/`).
- `Annotations`: instructions of the form ``Use `pybuggy-api` for ...``, ``Use `pybuggy-asserts` for ...``.

On top of the base block, a cell may have **cell-specific usages** — see the "Cell-specific usages
(tools)" section below.

### Cell-specific usages (tools)

A test cell that uses a data preparation, mock, or utility tool receives a cell-specific usage
**on top of the base block**:

```yaml
Usages:
  conventions: .goga/usages/conventions.md          # base block — identical in all cells
  pybuggy-api: .goga/usages/cooks/pybuggy/api.md
  pybuggy-asserts: .goga/usages/cooks/pybuggy/asserts.md
  faker: .goga/usages/cooks/faker.md                # cell-specific (only where used)
```

- A usage key is added to the Header **only when the file exists** — `.goga/usages/cooks/<key>.md`
  must be on disk before cell design starts.
- Wiring a tool in requires two entries: a `<key>: .goga/usages/cooks/<key>.md` line in `Usages` + a
  ``Use `<key>` for <data preparation/mocks/utilities>`` line in the `Annotations` of the affected cell. The backtick
  reference `` `<key>` `` resolves immediately: the key is already declared in that cell's `Usages`.
- The base block stays **unchanged**. A cell-specific usage exists only in cells that use
  the tool — its presence in some cells and absence in others is **not** a discrepancy.
- Coverage (case coverage) and Routine granularity remain **unaffected** (tool usages belong to
  Header/Annotations, not Routine).

### Body — Routine

A test is a `Routine` (no `methods`/`properties`); one Routine may cover one or several
cases via parameterization — the mapping 1 case = 1 Routine is valid but not mandatory:

```yaml
"test_<name>(<fixture>: Endpoint, ...)":
  location: test_<name>.py
  annotations: |
    ...
```

- Signature: `test_<name>(<fixture>: Endpoint, ...)` — without output (a test returns nothing); declare one
  fixture parameter per endpoint the Routine calls (one for a single-endpoint Routine, several
  for a flow).
- `<fixture>` is a generated fixture from `api/<spec>/<id>/api.py` (name `<method>_<id>`); the Routine
  receives as many fixtures as endpoints it calls.
- Naming is `snake_case`, `location: test_<name>.py` (`goga-cell-python` rules).
- Parameterization: when one Routine covers several cases, the variants (parameters) are listed in
  the annotation — in `Data:` and/or `Steps`; CODEMANIFEST does not describe the parameterization mechanism
  (e.g. `@pytest.mark.parametrize`) — it emerges when test code is generated from the Routine. One Routine maps to
  one `test_<name>.py` (several cases → one file).
- The parameterization criterion is linearity: merge into one Routine only cases with a matching set
  of steps and checks — variants differ in values (request data, parameters, expected statuses/fields),
  but not in which steps and checks run. Cases with a different set of steps or checks become
  separate Routines: a test materialized from a parameterized Routine is linear, so logical
  constructs in the test body (`if`/`else` and the like, selecting steps/checks per variant) indicate excessive
  parameterization.

### Footer

- `Author` — always `Goga`.
- `CreatedAt` — day/month/year.
- `Description` — why this cell exists (which endpoints/feature it tests).

## Routine annotation standard

A Routine annotation must be sufficient for implementation without clarification. Tests use a **strict
structure** of ordered sections. The section order is fixed:
**Purpose → `Precondition:` → `Data:` → `Steps:` → `Use …`**.

Sections **are separated by a blank line**: a blank line follows Purpose and precedes each of
`Precondition:` / `Data:` / `Steps:` / `Use …`. Two adjacent sections without a blank line between them violate
the structure.

**1. Purpose — no label.** The section states what the Routine verifies (from the test case
`title`/description). It is the first paragraph of the annotation.

**2. `Precondition:` — fixtures and preconditions.** A bulleted list (`- `): each fixture parameter with
a description of the generated artifact (`api/<spec>/<id>/api.py`, name `<method>_<id>`, METHOD /path, role —
primary SUT or verification), plus general preconditions (the `Endpoint` parameter type from the pybuggy
runtime, system state/data BEFORE the test as stated by the case). The fixture name must carry a backtick.

**3. `Data:` — data created inside the test.** A bulleted list of the test's internal data: variables,
keys, computed values (e.g. `test_id`) that are not tied to a single call. Concrete call values
(`request`/`response`) stay inside `Steps`. Omit the section when no such data exists.

**4. `Steps:` — numbered test steps.** Steps come from the test case (Action / Data / Expectation). Logic, not
code — actions are expressed through references to Usages and the fixture, without pytest code. Numbered
list (`1. `).

**5. `Use …` — only Routine-specific usages.** The section closes the annotation and lists the usages used
**in this Routine** that the header's global `Annotations` do not already cover. Base practices
(`pybuggy-api`, `pybuggy-asserts`, `conventions`) are already linked in the CODEMANIFEST header's `Annotations` — **do not
duplicate** them in the Routine (per `goga-cell`: annotations at different levels do not duplicate each other). Only
cell-specific tool usages belong here (e.g. ``Use `faker` for generating test_id``). Omit the section
when the Routine has no specific usages. Backtick references must resolve within the CODEMANIFEST context.

**Not used** for tests: `Requirements:`/`Constraints:` (their content moves from the case into
`Precondition:`/`Data:` as needed); `Algorithm:` is replaced by `Steps:`.

**Request body — the `Request` model vs `dict` (important).** `Steps` materialize into `test_*.py` verbatim,
so the way the request body is described determines the generated code:

- **Valid body (positive/flow, correct data):** describe it through the **importable `Request` model** from
  the fixture `api/<spec>/<id>/api.py` — `json=Request(...)`. The model name and the nested structure (including
  nested models when it is composite — e.g. `Request1`/`Response`) come from that same `api.py`; specify the
  `Request(...)` model in `Steps` — **as plain text, without a backtick reference** (the model is external to
  the test cell's CODEMANIFEST: it is neither a signature variable nor `Imports`/`Usages`; a backtick reference
  to it is unresolvable under the `goga-cell` DSL). The backtick stays only on the fixture
  `` `<fixture>` `` (it appears in the signature). This is the **primary path** — it matches `pybuggy-api`.
- **Invalid body (negative — missing required field, wrong type, empty body, malformed JSON):** describe it
  as a **raw `dict`**, bypassing the pydantic model (a pydantic-validated body would raise `ValidationError`
  before the request is sent, and the SUT would never be tested). Always mark it explicitly: "raw `dict`,
  bypassing the pydantic model". This **exception** applies only to negative.

**Never** describe a valid body in dict notation (`{field: value}`) — `Steps` would materialize as
`json={...}`, request validation would be lost, and the positive check would stop testing the request
contract.

Example:

```yaml
"test_create_order_returns_201(create_order: Endpoint)":
  location: test_create_order_returns_201.py
  annotations: |
    Verifies successful order creation — status 201 and the presence of id in the response.

    Precondition:
    - `create_order`: generated fixture api/orders/create_order/api.py (POST /orders), primary SUT.
    - The fixture parameter has type `Endpoint` (pybuggy runtime) — passed into the test as a ready callable route.

    Data:
    - `order_id` is generated by the service in the creation response and used in checks.

    Steps:
    1. Call the endpoint with a valid body — model Request(item="A", qty=2) (imported from the fixture's api.py).
    2. Check status 201 and the id field in the response.

    Use <usages> specific to the Routine usages
```
