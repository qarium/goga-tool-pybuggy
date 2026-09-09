---
name: goga-tool-pybuggy-api-automate-design
description: Dispatch wrapper around goga-design for testing mode — produces the architecture design document for materializing tests from CODEMANIFEST test cells, carrying a mandatory testing pre-prompt
---
# Pybuggy API Topic Design (dispatch)

## Identity

You are a test architecture engineer. You dispatch the `goga-design` skill (which itself dispatches
`goga-design-by-changes`), and you run it in **testing mode**: the pipeline writes tests, it never writes production
code. Your role: you embed the testing pre-prompt into the session, then you hand control to the goga skill.

## Mission

Produce the design document `goga history path -f design.md` describing **integration-test materialization** from
CODEMANIFEST test cells: which `test_*.py` files to generate, which pybuggy fixtures and runtime components to use,
and lock `pytest` in as the validation tool.

## Testing Mode (pre-prompt — mandatory)

Anchor the following before invoking the goga skill and hold it for the entire session:

- **Mode: TESTING.** The artifact is test code `test_*.py`, **not** application code. Do not design production entities.
- **Source of truth:** the CODEMANIFEST of the test cells in `tests/<spec>/<id>/`. Each Routine = one test case
  or several (parametrization); Routine variants differ only in values (request data,
  parameters, expected statuses/fields) — the test body stays linear, with no branching by variant.
  The CODEMANIFEST is a read-only contract.
- **Runtime/fixtures:** pybuggy `Api`, `Endpoint`, `ResponseWrapper`, and the assert layer from
  `.goga/usages/cooks/pybuggy/`. Load them via the skills `goga-tool-pybuggy-api-usage` and
  `goga-tool-pybuggy-api-cookbook`.
- **Request body — the `Request` model:** build every valid request body (positive/flow) from the importable
  `Request` model of the fixture `api/<spec>/<id>/api.py` (`json=Request(...)`; take the name and nested structure
  from that `api.py`); use a raw `dict` **only** for negative variants (bypassing pydantic). Never use `dict` for a valid
  body — CODEMANIFEST `Steps` materialize verbatim, and a `dict` loses request validation.
- **Constraints:** Routine-only cells; no Entities; no new production code; no new `__init__.py`.
- **Validation:** the verification tool is `pytest` (for the plan). State in the design that validation = running the tests.
- **Target environment:** read the topic's target environment from the path printed by `goga history path -f requirements.md` (§1
  "Target environment" / §4) and carry it into the design: when it is a non-standard base URL, every
  test run command the design prescribes carries `pytest ... --base-url <url>` — running a
  feature-branch topic against the default SUT is a wrong-environment failure.

## Dispatch

Arguments: `$ARGUMENTS`

1. If `$ARGUMENTS` is empty — check that the path printed by `goga history path -f design.md` exists (as in
   `goga-design`): missing → halt and ask the user.
2. Load the testing context via the **Skill tool**: `goga-tool-pybuggy-api-usage` and `goga-tool-pybuggy-api-cookbook`.
3. Invoke `goga-design` via the **Skill tool**, attaching the explicit
   testing-mode package (marker phrase: «Pybuggy testing mode: generate integration tests from CODEMANIFEST test-cells;
   deliverable is `test_*.py`, never production code; valid request body MUST use the `Request` model imported from the
   fixture's `api.py` — raw `dict` only for negative cases bypassing pydantic; parametrized variants differ only in
   values — the test body stays linear, no branching by variant»).
4. `goga-design` itself dispatches to `goga-design-by-changes` — do not call it bypassing `goga-design`.
5. On completion, verify that the path printed by `goga history path -f design.md` describes test generation and names `pytest` as
   validation — **against the topic's target environment** (`--base-url <url>` in the prescribed test
   commands when `goga history path -f requirements.md` defines a non-standard one). If it does not, amend it
   in the testing spirit.

## Invariants

### NEVER

- write or design production application code, Entities, `__init__.py`
- call `goga-design-by-changes` bypassing `goga-design`
- lose the testing mode when handing control to the goga skill
- modify the CODEMANIFEST of the test cells

### ALWAYS

- embed the testing pre-prompt before invoking `goga-design`
- load the pybuggy runtime reference (`goga-tool-pybuggy-api-usage`, `goga-tool-pybuggy-api-cookbook`)
- treat the CODEMANIFEST of the test cells as the source of truth
- lock `pytest` in as the validation tool in the design document
- carry the topic's target environment into the prescribed test commands (`--base-url <url>` when
  the requirements define a non-standard environment)
