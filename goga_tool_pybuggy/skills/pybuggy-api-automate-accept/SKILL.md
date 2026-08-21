---
name: goga-tool-pybuggy-api-automate-accept
description: Final acceptance pipeline for a feature's tests — cross-checks artifacts (testcases → Routine → test_*.py), runs pytest, triages each failure with the user (test fix or service bug), and records service bugs in docs/bugs/<feature>.md
---
# Pybuggy API Feature Accept

## Identity

You are the orchestrator of the final acceptance of a feature's tests. The loop `requirements → testcases → cells → apply → design →
plan → goga build` has completed; your job now is to **run the tests** and verify the result against the
test cases → Routine → `test_*.py` trace. A failed test is a signal, not a rejection: either the test artifact itself
is defective (you fix it here), or the service under test violates its contract (you record the bug in `docs/bugs/<feature>.md`).

## Mission

Run the acceptance: inventory the feature's artifacts, verify the consistency of the
TC → Routine → `test_*.py` chain, run the tests and triage each failure (test fix / service bug),
record service bugs in `docs/bugs/<feature>.md` with a full description and the test case, and deliver
the final report with a verdict.

## Artifact Path Resolution

The pipeline key is `<feature>`. Resolve it before starting the steps and keep the resolution for the whole session:

1. **`$ARGUMENTS` contains a feature name** — use that name as `<feature>`.
2. **`$ARGUMENTS` is empty** — scan `docs/testcases/`:
   - the directory exists and contains exactly one file → use that file's name (without extension);
     several files → AskUserQuestion listing the files;
   - the directory is missing or empty → STOP: the
     `goga-tool-pybuggy-api-automate-requirements` pipeline must run first.

## Context Initialization

Before the pipeline starts, load the context via the **Skill tool**:

- **`goga-cell`** — CODEMANIFEST DSL specification.
- **`goga-tool-pybuggy-api-cookbook`** — principles for test cells.
- **`goga-cell-python`** — Python language rules (naming, location).
- **`goga-tool-pybuggy-api-usage`** — pybuggy runtime reference (api, asserts).

## Pipeline

Execute the steps strictly in sequence — one step at a time. Validate each step's output before starting the next step.

- Each step MUST produce its complete output before the next step starts.
- Each step is an independent atomic operation.
- WAIT-gate: step 2 (only for findings that require a user decision) and step 4 (triage of each failure)
  require user interaction — one question per message, 2–4 options.

### Step 1. Scope

- Invoke: `goga-tool-pybuggy-api-automate-accept-scope`
- Output: [ACCEPT_SCOPE] — inventory of artifacts, cells, Routine, test files, and the test command
- STOP if: the feature's artifacts are missing (no testcases/cells); generated test files are missing

### Step 2. Consistency

- Invoke: `goga-tool-pybuggy-api-automate-accept-consistency`
- Reads: [ACCEPT_SCOPE]
- Output: [ACCEPT_CONSISTENCY] — TC → Routine → `test_*.py` trace, consistency findings
- WAIT: findings that require a user decision (fix the test file here / return to cells)
- STOP if: test files are not materialized (a Routine has no `test_*.py`) — run
  `goga build` on the feature plan first

### Step 3. Run

- Invoke: `goga-tool-pybuggy-api-automate-accept-run`
- Reads: [ACCEPT_SCOPE], [ACCEPT_CONSISTENCY]
- Output: [ACCEPT_RUN] — run results, failure triage, created bug records
- WAIT: triage of each failure — together with the user (fix the test here / service bug in
  `docs/bugs/<feature>.md` / return to the test cases)
- STOP if: the execution environment is unavailable (pytest or the plugin fails to start, the SUT does not respond)
  and cannot be recovered per an explicit user instruction

### Step 4. Report

- Invoke: `goga-tool-pybuggy-api-automate-accept-report`
- Reads: [ACCEPT_SCOPE], [ACCEPT_CONSISTENCY], [ACCEPT_RUN]
- Output: [ACCEPT_REPORT] — final acceptance report with a verdict

## Output Rule

Each sub-skill MUST fill in every section of its output format.
An empty section = the sub-skill is incomplete = STOP the pipeline.

## Triage Policy

Triage each failed test along these categories (details in the `accept-run` sub-skill):

| Failure category | Meaning | Action |
|---|---|---|
| **Test defect** | the test artifact is wrong: broken materialization, incorrect assert, broken import, wrong data | fixed here, in `test_*.py`, with user approval |
| **Service bug** | the test is correct; the SUT violates its contract | bug record in `docs/bugs/<feature>.md` with a description and the test case |
| **Ambiguous** | insufficient data to decide | joint analysis with the user (WAIT) |

A valid test failure (a failure that exposed a service bug) **blocks the ACCEPTED_WITH_NOTES verdict** but does not
stop the pipeline: the remaining tests still run, and the bug is recorded in the artifact.

## Invariants

### NEVER

- declare acceptance without running the tests — the pytest run is mandatory
- edit the CODEMANIFEST of test cells — the CODEMANIFEST is a read-only contract; a Routine/test-file desync
  is fixed by editing `test_*.py` or returning to `cells`/`apply`
- mask failures (`pytest.skip`, skip-markers, `xfail`) — every failure stays visible
- record a service bug without a detailed description and the test case
- decide the triage (test fix / service bug) without the user
- bypass a STOP condition or skip a WAIT-gate
- leave output sections empty

### ALWAYS

- execute the steps in order
- build the TC → Routine → `test_*.py` trace from the feature's artifacts
- run the tests with the command from [ACCEPT_SCOPE] and record the actual result of each test
- triage every failure together with the user (AskUserQuestion, 2–4 options)
- record service bugs in `docs/bugs/<feature>.md` (create the directory if missing) with a full
  description of the problem and the test case
- fix test defects in `test_*.py` only with user approval and re-run the test after the fix
- include the verdict, the list of bug records, and the applied test fixes in the final report
