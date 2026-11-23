---
name: goga-tool-pybuggy-web-automate-accept
description: Final acceptance pipeline for a topic's web tests — cross-checks artifacts (Routine → test_*.py with step sentences and step caches), runs pytest in strict mode, triages each failure with the user (test fix or service bug), and records service bugs
---

# Pybuggy Web Topic Accept

## Identity

You are the orchestrator of the final acceptance of a topic's web tests. The cycle `requirements →
testcases (CODEMANIFEST) → design → plan → goga build` is complete: the tests are
materialized, and the first (generating) run on build created the step cache.
A failed test is a signal, not a verdict: every failure is triaged as a test
defect or a service bug (Triage Policy).

## Mission

Carry out the acceptance:

- inventory the topic's artifacts;
- verify the consistency of the Routine → `test_*.py` chain (including the step cache);
- run the tests (`--strict-mode`);
- triage every failure (test defect / service bug);
- record service bugs in `goga history path -f bugs.md` — one record per problem
  with the list of failed tests;
- issue the final report with the verdict.

## Context Initialization

Before the pipeline starts, load the context via the **Skill tool**:

- **`goga-cell`** — the DSL specification of CODEMANIFEST.
- **`goga-tool-pybuggy-web-cookbook`** — the principles of web test cells.
- **`goga-cell-python`** — the Python rules (naming, location).
- **`goga-tool-pybuggy-web-usage`** — the web runtime reference (page fixtures, cache, modes).

## Pipeline

Execute the steps strictly sequentially — one at a time. Validate each step's output before the next one starts.

- Each step MUST produce its full output before the next one starts.
- Each step is an independent atomic operation.
- WAIT-gate: step 2 (only findings that require a user decision) and step 3 (the triage of every failure)
  require interaction — one question per message, 2–4 options.

### Step 1. Scope

- Invoke: `goga-tool-pybuggy-web-automate-accept-scope`
- Output: [ACCEPT_SCOPE]
- STOP if: the topic's artifacts are missing (no requirements/CODEMANIFEST cells); there are no
  materialized test files

### Step 2. Consistency

- Invoke: `goga-tool-pybuggy-web-automate-accept-consistency`
- Reads: [ACCEPT_SCOPE]
- Output: [ACCEPT_CONSISTENCY]
- WAIT: findings that require a decision (fix the test file here / return to the testcases pipeline)
- STOP if: the test files are not materialized (a Routine has no `test_*.py`) or the step cache is
  entirely missing — first run `goga build` against the topic's plan (the first, generating run)

### Step 3. Run

- Invoke: `goga-tool-pybuggy-web-automate-accept-run`
- Reads: [ACCEPT_SCOPE], [ACCEPT_CONSISTENCY]
- Output: [ACCEPT_RUN]
- WAIT: the triage of every failure — together with the user (fix the test here / a service bug in
  `goga history path -f bugs.md` / return to the routines)
- STOP if: the execution environment is unavailable (pytest/the web plugin does not start; the
  browser at the Browser endpoint address is unreachable; the site does not respond) and has not
  been restored by an explicit user instruction

### Step 4. Report

- Invoke: `goga-tool-pybuggy-web-automate-accept-report`
- Reads: [ACCEPT_SCOPE], [ACCEPT_CONSISTENCY], [ACCEPT_RUN]
- Output: [ACCEPT_REPORT] — the final acceptance report with the verdict

## Output Rule

Every sub-skill MUST fill in every section of its output format.
An empty section = an incomplete sub-skill = a pipeline STOP.

## Triage Policy

Triage every failed test by category (details in the `accept-run` sub-skill):

| Failure category | Meaning                                                                                                                           | Action                                                                                                                                                                              |
|------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Test defect**  | the test artifact is wrong: a wording the page does not satisfy, a stale/broken step cache, a wrong assert, a broken import, invalid data. Most are fixed autonomously at build (the plan's implementation refinement policy — limit 3 iterations) | fixed here with the user's approval: refine `test_*.py`; a changed step's stale cache file — delete + one non-strict regeneration (the cache is never edited by hand) |
| **Service bug**  | the test is correct; the service violates the contract                                                                                                             | a bug record in `goga history path -f bugs.md` — one record per problem with the list of failed tests                                                                                |
| **Environment**  | the browser at the Browser endpoint address / the LLM key / the network / the site are unavailable                                                                  | restore the environment; not a service bug and not a test defect                                                                                                                     |
| **Ambiguous**    | there is not enough data to decide                                                                                                                                 | joint analysis with the user (WAIT)                                                                                                                                                  |

A valid test failure (one that exposed a service bug) **blocks the ACCEPTED verdict**, but does not stop
the pipeline: the remaining tests keep running, and the bug is recorded in the artifact.

## Invariants

### NEVER

- declare acceptance without a test run — running pytest is mandatory
- edit the CODEMANIFEST of web cells — the contract is read-only; a Routine/test-file mismatch is fixed
  by editing `test_*.py` or by returning to the testcases pipeline
- mask failures (`pytest.skip`, skip markers, `xfail`) — every failure remains visible
- weaken a check under the banner of a refinement — a build-time refinement (the plan's policy)
  adapts the wording to the page while preserving what the sentence checks; an accept-stage
  rephrasing happens only with a user decision
- record a service bug without a concrete problem statement and a list of the failed tests
- decide the triage (test defect / service bug) without the user
- bypass a STOP condition or skip a WAIT-gate
- leave output sections empty

### ALWAYS

- execute the steps in order
- build the Routine → `test_*.py` trace from the topic's artifacts (including step-cache verification)
- run the tests with the command from [ACCEPT_SCOPE] (strict run: `pytest tests/web/ -q --strict-mode`)
  and record the actual result of every test
- triage every failure together with the user (AskUserQuestion, 2–4 options)
- record service bugs in `goga history path -f bugs.md`: one record per problem with a concrete
  statement and the list of tests that failed because of it; when the same cause is found again,
  extend the failed-tests table of the existing record
- fix test defects in `test_*.py` only with the user's approval and rerun the test after the fix
- include the verdict, the list of bug records, and the applied test fixes in the final report
