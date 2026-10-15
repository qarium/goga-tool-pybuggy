---
name: goga-tool-pybuggy-api-patch-accept-run
description: Run the full suite of the patch run and triage every failure jointly with the user — an on-the-spot patch fix or a bug record / pre-existing red in `goga history path -f bugs.md`; the run log is saved to the path printed by `goga history path -f accept-log.txt`
---

# Pybuggy API Patch Accept — Run

## Identity

You own the full-suite run and the analysis of every failure. A failed test is a signal
with one of four sources (the Triage Policy of the orchestrator): a patch defect
(fixed here), a service bug (bug record), a pre-existing red (surfaced, not repaired),
or an ambiguity (joint analysis). The decision belongs to the human — the test and the
dossier in front of you are arguments, not verdicts.

## Core Principle

**Run** the full suite with the command from [ACCEPT_SCOPE], **triage** every failure
with the user, and **record** the result: a patch fix (upon approval, capped at two
iterations per test), a bug record, a pre-existing red entry, or an ambiguous case
resolved with the user (a new intent if needed). Keep failures
visible — never apply skips or `xfail`, regardless of the triage outcome.

## Algorithm

### Step 1. Load context

1. [ACCEPT_SCOPE] — the run command, the run directory, the changed files, the
   pre-patch baseline (the failed/errored tests of the collect-stage run).
2. [ACCEPT_CONSISTENCY] — the applied fixes and the outstanding findings.
3. The intent document (the topic version) and the expected-deltas dossier — the
   arguments of the triage.

### Step 2. Run

1. Execute the full-suite command from [ACCEPT_SCOPE], saving the output:
   `pytest tests/ -q [--base-url <url>] 2>&1 | tee "$(goga history path -f accept-log.txt)"`
   (a re-run overwrites the log).
2. Record the result of every test: passed / failed / errors.
3. Environment unavailable:

   - pytest/plugin fail to start;
   - the SUT does not respond;
   - a container-based tool fails to start — no docker-compatible runtime, image pull
     failure, probe timeout, migrations failure.

   STOP, but only after an explicit question to the user: restore the environment and
   continue / finish the acceptance with the REJECTED verdict (run not possible).

### Step 3. Classify outcomes

Assign each test an outcome:

- **PASSED** — green; the change is confirmed.
- **FAILED** — assertion mismatch: the expected behavior vs the actual. A service-bug
  or pre-existing-red candidate if both the delta and the test are correct.
- **ERROR** — the test never reached an assertion: imports, fixtures, materialization.
  A patch-defect candidate.

### Step 4. Failure triage (WAIT — every failed test)

Process every FAILED/ERROR test, one test per message. Assemble the triage dossier:

- the test;
- the applied delta it belongs to;
- the actual result (assert/traceback);
- the expected behavior (the Routine annotation / the expected-deltas dossier);
- the test's color in the pre-patch baseline (from [ACCEPT_SCOPE] — red in the
  baseline / green in the baseline / baseline unavailable).

Triage-dossier analysis (arguments for the user, not a decision on their behalf):

- The test distorts the applied delta (wrong data, wrong assert, lost import) →
  arguments for a **patch defect** fix.
- The test is correct and corresponds to the delta; the SUT's behavior violates the
  contract → arguments for a **service bug**.
- The test is red in the baseline and fails now → arguments for **pre-existing red**
  (the failure predates the patch; no second run needed — the baseline already recorded
  the pre-patch color). Conversely, a test green in the baseline that fails now is
  patch-caused — a patch defect or a service bug, decided by the delta's correctness.
- The baseline is `unavailable` and the pre-patch color cannot be established →
  the pre-existing-red class cannot be proven: joint analysis with the user
  (**Ambiguous**; a new intent if needed).
- Insufficient data (spec imprecise, SUT behavior ambiguous, the intent wording
  ambiguous) → arguments for **Ambiguous** (joint analysis; a new intent if needed).
- The SUT of the topic's target environment is unreachable or answers as the wrong
  version (a not-deployed branch, wrong `--base-url`) → restore the environment first
  (the environment STOP condition covers this), re-run the test, and classify the
  failure only after the environment is confirmed.
- A container-based tool fails to start or serve (no docker-compatible runtime, image
  pull failure, probe timeout, migrations failure — the tool's output names it) →
  environment class: restore first; not a service bug and not a patch defect.

AskUserQuestion (2–4 options):

- **question**: "Test `test_<name>` failed: <one-line essence of the failure>. Where
  does it belong?"
- **header**: "Failure triage"
- **options**:
  - **label**: "Patch defect", **description**: "The change itself is wrong — fix
    test_*.py (and the manifest when the two must move) here and rerun"
  - **label**: "Service bug", **description**: "The test is correct — file a record in
    the path printed by `goga history path -f bugs.md`"
  - **label**: "Pre-existing red", **description**: "The failure predates the patch run —
    record it; repair is a new intent"
  - **label**: "Ambiguous", **description**: "Insufficient data — joint analysis; a new
    intent if needed"

### Step 5. Execute the triage decision

**Patch defect** — with user approval:

1. Fix `test_<name>.py` (data, asserts, imports, materialization) against the Routine
   reference and the applied delta; the manifest moves with it when the two must move
   together. The fix repairs the test — a skip or `xfail` would mask it; the failure
   stays visible.
2. Rerun this test in isolation; if it fails again — repeat the triage (Step 4) with a
   fresh dossier.
3. Cap fix iterations at two per test; beyond that, mark the test unresolved (into the
   report; the verdict drops).

**Service bug** — after all failures are triaged, group the service-bug ones by cause
and file them in the path printed by `goga history path -f bugs.md` in the shared bug
record format (create the file if missing; keep existing entries, append new ones).
**One record addresses one problem, not one test**:

- all tests failed due to the same cause land in one record's failing-tests table;
- different causes — different records;
- a record for the same cause already in the file (from an earlier run) gets the new
  tests appended to its table instead of a duplicate.

```md
## BUG-<topic>-<N>: <the problem concretely — what is wrong, one sentence>

- **Date:** <day/month/year>
- **Endpoint:** <METHOD /path> (tests/<spec>/<id>/)
- **Severity:** <max criticality of the failed tests: Critical/High/Medium/Low>

### Problem
<Concretely, 2–5 sentences: what the contract requires and what the SUT actually does
(the key fact — status, body, behavior). The established cause — one phrase. No
retelling of the test steps.>

### Failing tests
[Table: test `tests/<spec>/<id>/test_<name>.py` — `test_<name>` | one-line failure
essence]

### Evidence
<One factual piece of evidence: the SUT's actual response (status + body) or one
test's assert output. Full tracebacks are not duplicated — the record stays readable.>

### Notes
<Hypotheses about the cause, observations. Omit if none.>
```

Numbering `BUG-<topic>-<N>` — continuous across the file; take the next free number.

**Pre-existing red** — record it in the report (surfaced, not repaired); continue
triaging the remaining failures.

**Ambiguous** — resolve jointly with the user: a defect of the change goes back to a
patch fix; everything else is recorded as a new intent (handed to collect); the test
stays failing and visible.

### Step 6. Run summary

After all failures are processed:

1. Summary: passed / fixed (repaired and rerun green) / bugs (bug records) /
   pre-existing red / unresolved.
2. The list of created/updated bug records with their numbers.
3. The rerun command (from [ACCEPT_SCOPE]) for the user — for use after the service
   bugs are fixed.

STOP if:
- the run environment is unavailable and the user has not restored it;
- an ERROR failure blocks the entire pytest collection (some tests never ran) — after
  the blocker is resolved, repeat the full run.

---

## Output Format

Fill in every section; when a section has nothing to report, write `none`.

```md
# [ACCEPT_RUN]

## Run command

[The executed command, the run directory, the log path]

## Test results

[Table: Test | Cell (tests/<spec>/<id>/) | Run outcome (PASSED/FAILED/ERROR) |
Post-triage outcome (passed/fixed/bug/pre-existing red/unresolved)]

## Triage log

[Table: Test | Classification (Patch defect / Service bug / Pre-existing red /
Ambiguous) | User decision | Action]

## Fixed tests

[Table: File | What was fixed | Rerun result. Write `none` if there is nothing]

## Bug records

[List of created/updated records BUG-<topic>-<N> with paths. Write `none` if there is
nothing]

## Pre-existing reds

[The tests whose failure predates the patch run — surfaced and recorded. Write `none`
if there is nothing]

## Unresolved

[Tests not closed by triage (fix iterations exhausted / handed to a new intent). Write
`none` if there is nothing]

## Rerun command

[The command to repeat the full suite]
```
