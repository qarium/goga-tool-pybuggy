---
name: goga-tool-pybuggy-api-automate-accept-consistency
description: Pre-run consistency check of the test case → Routine → test_*.py chain — traceability, signatures, location, skip masking, Request model
---
# Pybuggy API Feature Accept — Consistency

## Identity

You own the static consistency check of artifacts before the test run: every Routine CODEMANIFEST
is materialized in `test_<name>.py`, every test file matches its Routine, every test case traces
to a test. CODEMANIFEST is the read-only source of truth; discrepancies are fixed on the `test_*.py`
side or by returning to the cells/apply pipelines.

## Core Principle

You **verify** `test_*.py` against the Routines of their cells and **record** findings. CODEMANIFEST stays untouched:
on desync, either the test file is fixed (with user approval) or a return to
`pybuggy-api-automate-cells` / `pybuggy-api-automate-apply` is recorded.

## Algorithm

### Step 1. Load context

1. [ACCEPT_SCOPE] — cells, Routines, test files, TC → Routine trace.
2. Via the **Skill tool**: `goga-cell`, `goga-tool-pybuggy-api-cookbook`, `goga-tool-pybuggy-api-usage`,
   `goga-cell-python`.
3. Read the CODEMANIFEST of every cell and every `test_<name>.py`.

### Step 2. Routine ↔ test-file

For every Routine of every cell:

1. The file `tests/<spec>/<id>/test_<name>.py` exists and is located at the `location` from CODEMANIFEST.
2. The file defines the function `test_<name>`; the name matches the Routine.
3. Signature: the `<fixture>` fixture parameter typed as `Endpoint` (or as CODEMANIFEST prescribes);
   the fixture is imported from `api/<spec>/<id>/api.py`.
4. Extra test functions in the file beyond the Routine (one file per Routine) — a finding.

### Step 3. Request body — Request model

For every test according to its case (Flow/Positive/Negative from `docs/testcases/<feature>.md`):

1. A valid body (positive/flow) is materialized through the importable `Request` model from
   `api/<spec>/<id>/api.py` (`json=Request(...)`).
2. A raw `dict` for a valid body — a finding (request pydantic validation is lost).
3. A raw `dict` for negative variants — the norm (bypassing pydantic, as the cases prescribe).

### Step 4. Skip masking and lost steps

1. `test_*.py` contains no `pytest.skip`, skip-markers, or `xfail` — any occurrence = a
   **Critical** finding (failure masking).
2. The test body is linear: logical constructs (`if`/`else`, match/case, ternaries) that select steps
   or asserts by the parameterization variant — a **High** finding (excessive Routine parameterization:
   diverging variants must live in separate Routines; the linearity criterion is
   `goga-tool-pybuggy-api-cookbook`).
3. The steps of the Routine's `Steps:` annotation are reflected in the test body (calls, checks); a skipped
   case step is a finding (Severity by impact: a lost contract check — High).
4. The case checks (status, fields, structure, invariants) are present in the asserts — compare against
   the expectations section of the case in `docs/testcases/<feature>.md`.

### Step 5. Usage references

1. Cell-specific usage keys of the Header cell: the files `.goga/usages/cooks/<key>.md` exist.
2. The fixtures and tools used in `test_*.py` match the connected keys.

### Step 6. Findings and decisions

Every finding gets a severity and an action:

- **Critical** — a Routine without a test file; `pytest.skip`/skip-markers/`xfail`; a test function
  without a Routine.
- **High** — a valid body via `dict`; a lost case step; a lost contract check; a broken
  fixture import.
- **Medium** — extra test functions in the file; a missing cooks file for a key.

Actions per finding (via AskUserQuestion, one question per message, 2–4 options):

1. **Fix `test_*.py` here** — edit the test file in the test key (following the Routine's DSL reference).
2. **Return to `pybuggy-api-automate-cells` / `-apply`** — on structural discrepancies (Routines missing
   for cases, cells do not match the plan).
3. **Accept as is** — with an explicit risk record in the report.

STOP if:
- test files are not materialized at all — acceptance is impossible until `goga build`;
- the user chose a return to cells/apply for Critical findings (the acceptance pipeline terminates
  early).

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [ACCEPT_CONSISTENCY]

## Routine ↔ test-file
[Table: Routine | test file | Function name | Signature/fixture | Status]

## Request model compliance
[Table: Test | Case (Flow/Positive/Negative) | Body via Request/dict | Policy compliance]

## Skip masking
[List of pytest.skip/skip-markers/xfail occurrences with file and line. Empty if none]

## Steps & assertions coverage
[Table: Test | Case steps reflected | Contract checks present | Gaps]

## Usage references
[Table: Cell | Key | File .goga/usages/cooks/<key>.md exists]

## Findings
[Table: File | Finding | Severity (Critical/High/Medium) | Action (fix here / return to cells/apply / accept)]

## Applied fixes
[Edits to test_*.py made with user approval: file | what changed | reason. Empty if none]

## Overall
[CONSISTENT / CONSISTENT_WITH_FIXES / INCONSISTENT — with justification]
```
