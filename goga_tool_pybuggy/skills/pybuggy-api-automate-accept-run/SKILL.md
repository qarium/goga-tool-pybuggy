---
name: goga-tool-pybuggy-api-automate-accept-run
description: Run the topic's test suite and triage each failure jointly with the user — apply an on-the-spot test fix or file a bug record in docs/bugs/<topic>.md with a detailed description and the test case
---
# Pybuggy API Topic Accept — Run

## Identity

You own the topic test run and the analysis of every failure. A failed test is a signal with one of two sources:
a defect in the test itself (materialization, asserts, data — fixed here) or a defect in the service under test
(the test is correct — file a bug record). Determine the source **jointly with the user**: the test and
the test case in front of you are arguments; the decision belongs to the human.

## Core Principle

**Run** the tests with the command from [ACCEPT_SCOPE], **triage** every failure with the user, and
**record** the result: a test fix (upon approval) or a bug record in `docs/bugs/<topic>.md`. Keep failures
visible — never apply skips or `xfail`, regardless of the triage outcome.

## Algorithm

### Step 1. Load context

1. [ACCEPT_SCOPE] — run command, run directory, TC → Routine → test trace.
2. [ACCEPT_CONSISTENCY] — applied fixes and outstanding findings.
3. `docs/testcases/<topic>.md` — test cases for matching failures.

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
- The SUT of the topic's target environment is unreachable or answers as the wrong version (a feature
  branch not deployed / deployment lag / wrong `--base-url`) → arguments for restoring the environment
  first (the environment STOP condition covers this) — do not classify the failure as a service bug
  before the environment is confirmed.

AskUserQuestion (2–4 options):

- **question**: "Test `test_<name>` failed: <one-line essence of the failure>. Where does it belong?"
- **header**: "Failure triage"
- **options**:
  - **label**: "Test fix", **description**: "Defect in the test — fix test_*.py here and rerun"
  - **label**: "Service bug", **description**: "The test is correct — file a record in docs/bugs/<topic>.md"
  - **label**: "Return to the test cases", **description**: "The test case is ambiguous — re-clarify it via the testcases pipeline"

### Step 5. Execute the triage decision

**Test fix** — with user approval:

1. Fix `test_<name>.py` (data, asserts, imports, materialization) against the Routine reference and the test case.
2. Rerun this test in isolation; if it fails again — repeat the triage (Step 4) with a fresh dossier.
3. Cap fix iterations at two per test; beyond that, mark the test unresolved (into the report; the verdict drops).

**Service bug** — after all failures are triaged, group the service-bug ones by cause and file them in
`docs/bugs/<topic>.md` (create the directory/file if missing; keep existing entries, append new ones).
**One record addresses one problem, not one test**: all tests failed due to the same cause land in one
record's failing-tests table; different causes — different records. A record for the same cause already
in the file (from an earlier run) gets the new tests appended to its table instead of a duplicate.

```md
## BUG-<topic>-<N>: <the problem concretely — what is wrong, one sentence>

- **Date:** <day/month/year>
- **Endpoint:** <METHOD /path> (tests/<spec>/<id>/)
- **Severity:** <max criticality of the failed cases: Critical/High/Medium/Low>

### Problem
<Concretely, 2–5 sentences: what the contract requires and what the SUT actually does (the key fact —
status, body, behavior). The established cause — one phrase. No retelling of the case steps.>

### Failing tests
[Table: test `tests/<spec>/<id>/test_<name>.py` — `test_<name>` | case TC-<N> | Routine | one-line failure essence]

### Evidence
<One factual piece of evidence: the SUT's actual response (status + body) or one test's assert output.
Full tracebacks are not duplicated — the record stays readable.>

### Notes
<Hypotheses about the cause, observations. Omit if none.>
```

Numbering `BUG-<topic>-<N>` — continuous across the file; take the next free number.

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
[List of created/updated records BUG-<topic>-<N> with paths. Empty if none]

## Unresolved
[Tests not closed by triage (fix iterations exhausted / handed to testcases). Empty if none]

## Rerun command
[Command to repeat the run after the service bugs are fixed]
```
