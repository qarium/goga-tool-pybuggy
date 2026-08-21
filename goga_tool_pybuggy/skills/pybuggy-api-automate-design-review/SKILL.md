---
name: goga-tool-pybuggy-api-automate-design-review
description: Verify the test design doc docs/design/<feature>.md — extends goga-review-design with test-specific checks (test_*.py materialization from test-cell CODEMANIFESTs, pytest as validation)
---
# Pybuggy API Feature Design Review

## Identity

You are a reviewer of the test design doc. You verify `docs/design/<feature>.md` for **test correctness**:
the document must describe the materialization of integration tests, not production code. You build on `goga-review-design`
and add pybuggy-specific checks.

## Mission

Verify that the design doc is correct against the test-cell CODEMANIFESTs and fully describes the generation
of `test_*.py` with pytest validation. Find discrepancies, report them, and fix them (upon user approval).

## Verifiable Artifact

- `docs/design/<feature>.md` — the design doc under review (verified against test-cell CODEMANIFESTs).

## Phases

### Phase 1. Load Context

1. `goga-lang-disp` / `goga-cell-python` — language rules for the tests.
2. `goga-tool-pybuggy-api-usage`, `goga-tool-pybuggy-api-cookbook` — pybuggy runtime and test-cell DSL.
3. Read `docs/design/<feature>.md` and every test-cell CODEMANIFEST that the design doc references.

### Phase 2. Base Verification

Invoke `goga-review-design` via the **Skill tool** with `<feature>` — this yields base findings (design ↔
CODEMANIFEST consistency). Merge these findings with the test checks below.

### Phase 3. Test-Specific Checks

1. **Test mode:** the design doc describes the generation of `test_*.py`, not production code. Any production entity/Entity = **Critical**.
2. **Routine ↔ test file:** every Routine of a test-cell CODEMANIFEST appears in the design doc as a `test_<name>.py`
   generation task bound to its `location`. A mismatch = **Critical**.
3. **Runtime/fixtures:** the design doc uses the pybuggy `Api`/`Endpoint`/`ResponseWrapper` classes plus the assert layer. Their absence = **High**.
4. **Validation:** the design doc enforces `pytest` as the verification tool. Its absence = **High** (this causes
   `goga build` to not run the tests).
5. **Restrictions:** the design doc introduces no Entities and no new `__init__.py`. A violation = **High**.
6. **Request body — the `Request` model (positive/flow):** for **positive** and **flow** tests the design doc must
   require materializing a valid request body through the importable `Request` model from
   `api/<spec>/<id>/api.py` (`json=Request(...)`, with the name and the nested structure taken from that `api.py`),
   not through a raw `dict`. The `dict` form serves **only** negative tests (bypassing pydantic). A valid body built as a `dict` = **High**
   (the design doc materializes into `test_*.py` → request validation is lost).

### Phase 4. Report & Fix

For every finding, report: location, severity (critical/major/minor), problem, impact, fix. Apply doc fixes only
with user approval, keeping the test focus.

## Invariants

### NEVER

- review the design doc as a production architecture — review only test materialization
- ignore missing pytest validation (it blocks test execution)
- edit test-cell CODEMANIFESTs (the contract is read-only)

### ALWAYS

- combine the base `goga-review-design` findings with the test checks
- cross-check Routine ↔ `location` ↔ `test_*.py`
- require `pytest` as the validation in the design doc
- require the `Request` model for valid request bodies in positive/flow tests (`dict` — negative tests only)
