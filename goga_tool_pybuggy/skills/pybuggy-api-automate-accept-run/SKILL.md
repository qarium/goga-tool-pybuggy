---
name: goga-tool-pybuggy-api-automate-accept-run
description: Run the feature's test suite and triage each failure jointly with the user — apply an on-the-spot test fix or file a bug record in docs/bugs/<feature>.md with a detailed description and the test case
---
# Pybuggy API Feature Accept — Run

## Identity

You own the feature test run and the analysis of every failure. A failed test is a signal with one of two sources:
a defect in the test itself (materialization, asserts, data — fixed here) or a defect in the service under test
(the test is correct — file a bug record). Determine the source **jointly with the user**: the test and
the test case in front of you are arguments; the decision belongs to the human.

## Core Principle

**Run** the tests with the command from [ACCEPT_SCOPE], **triage** every failure with the user, and
**record** the result: a test fix (upon approval) or a bug record in `docs/bugs/<feature>.md`. Keep failures
visible — never apply skips or `xfail`, regardless of the triage outcome.

## Algorithm

### Step 1. Load context

1. [ACCEPT_SCOPE] — run command, run directory, TC → Routine → test trace.
2. [ACCEPT_CONSISTENCY] — applied fixes and outstanding findings.
3. `docs/testcases/<feature>.md` — test cases for matching failures.

### Step 2. Run

1. Execute the command from [ACCEPT_SCOPE] (from the directory containing `conftest.py`).
2. Capture the complete result: passed / failed / errors per test.
3. Environment unavailable (pytest/plugin fail to start, SUT does not respond) — STOP, but only after an
   explicit question to the user: restore the environment and continue / finish the acceptance with the verdict "run not possible".

### Step 3. Classify outcomes

Assign each test an outcome:

- **PASSED** — green; the test case is confirmed.
- **FAILED** — assertion mismatch: the test case's expectation vs the SUT's actual behavior. Service bug candidate
  if both the test case and the test are correct.
- **ERROR** — the test never reached an assertion: imports, fixtures, materialization. Test defect candidate.

### Step 4. Failure triage (WAIT — every failed test)

Process every FAILED/ERROR test, one test per message. Assemble a dossier: the test, the test case (from `docs/testcases`),
the actual result (assert/traceback), the test case's expectation, the Routine annotation.

Dossier analysis (arguments for the user, not a decision on their behalf):

- The test case is correct and the test corresponds to it → the SUT's behavior violates the contract → arguments for a service bug.
- The test distorts the test case (wrong data, wrong assert, wrong endpoint) → arguments for a test fix.
- Insufficient data (spec imprecise, SUT behavior ambiguous) → arguments for returning to the test cases.

AskUserQuestion (2–4 options):

- **question**: "Test `test_<name>` failed: <one-line essence of the failure>. Where does it belong?"
- **header**: "Failure triage"
- **options**:
  - **label**: "Test fix", **description**: "Defect in the test — fix test_*.py here and rerun"
  - **label**: "Service bug", **description**: "The test is correct — file a record in docs/bugs/<feature>.md"
  - **label**: "Return to the test cases", **description**: "The test case is ambiguous — re-clarify it via the testcases pipeline"

### Step 5. Execute the triage decision

**Test fix** — with user approval:

1. Fix `test_<name>.py` (data, asserts, imports, materialization) against the Routine reference and the test case.
2. Rerun this test in isolation; if it fails again — repeat the triage (Step 4) with a fresh dossier.
3. Cap fix iterations at two per test; beyond that, mark the test unresolved (into the report; the verdict drops).

**Service bug** — file it in `docs/bugs/<feature>.md` (create the directory/file if missing; keep existing
entries, append new ones):

```md
## BUG-<feature>-<N>: <brief essence>

- **Date:** <day/month/year>
- **Endpoint:** <METHOD /path> (tests/<spec>/<id>/)
- **Severity:** <criticality per the test case: Critical/High/Medium/Low>
- **Test:** `tests/<spec>/<id>/test_<name>.py` — `test_<name>` (status: FAILED)
- **Test case:** TC-<N> "<title>" from docs/testcases/<feature>.md

### Problem description
<In detail: what the contract/test case expects and what actually happens. Include the actual
result: response status, body/fields, assert text — everything that shows the divergence.>

### Reproduction steps
<Numbered steps from the test case: action → data → expectation; the last step is the SUT's actual result.>

### Test case
<Full content of test case TC-<N>: preconditions, data, steps, expectations — a copy from
docs/testcases/<feature>.md, so the bug reads without opening other files.>

### Actual result
<Traceback/assert output in full>

### Notes
<Hypotheses about the cause, observations. Omit if none.>
```

Numbering `BUG-<feature>-<N>` — continuous across the file; take the next free number.

**Return to the test cases** — log it in the report (the test stays failing, the test case goes to the
`pybuggy-api-automate-testcases` pipeline); continue triaging the remaining failures.

### Step 6. Run summary

After all failures are processed:

1. Summary: passed / fixed (repaired and rerun green) / bugs (bug records) / unresolved (not resolved).
2. List of created/updated bug records with their numbers.
3. Rerun command for the user (for use after the service bugs are fixed).

STOP if:
- the run environment is unavailable and the user has not restored it;
- an ERROR failure blocks the entire pytest collection (some tests never ran) — after the blocker is
  resolved, repeat the full run.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [ACCEPT_RUN]

## Run command
[The executed command and the run directory]

## Test results
[Table: Test | Cell | Test case TC-<N> | Run outcome (PASSED/FAILED/ERROR) | Post-triage outcome (passed/fixed/bug/unresolved)]

## Triage log
[Table: Test | Classification (Test defect / Service bug / Ambiguous→testcases) | User decision | Action]

## Fixed tests
[Table: File | What was fixed | Rerun result. Empty if none]

## Bug records
[List of created/updated records BUG-<feature>-<N> with paths. Empty if none]

## Unresolved
[Tests not closed by triage (fix iterations exhausted / handed to testcases). Empty if none]

## Rerun command
[Command to repeat the run after the service bugs are fixed]
```
