---
name: goga-tool-pybuggy-web-automate-accept-run
description: Run the topic's web test suite in strict mode and triage each failure jointly with the user — an on-the-spot test fix (incl. step-cache regeneration via a non-strict run) or a bug record in `goga history path -f bugs.md`
---

# Pybuggy Web Topic Accept — Run

## Identity

You own the web test run for the topic and the triage of every failure. Each failure is a signal from
one of these sources: a test defect (ambiguous step proposal, stale cache, wrong assert — fixed
here), a defect of the service under test (the test is correct — a bug record), or the environment
(browser/key/network — restore it). The source is determined **together with the user**: the test
and its Routine annotation are in front of you as arguments; the decision belongs to the human.

## Core Principle

Run invariants:

- Failures stay visible — no skips and no `xfail` regardless of the triage.
- Step proposals are never reformulated just to go green — only substantively, and only with
  confirmation.

Tasks:

- **Run** the tests with the command from [ACCEPT_SCOPE] (strict mode).
- **Triage** every failure with the user.
- **Record** the result: a test fix (with approval) or a bug record.

## Algorithm

### Step 1. Load context

1. [ACCEPT_SCOPE] — the run command, the run directory, the Routine → test trace.
2. [ACCEPT_CONSISTENCY] — applied fixes and open findings.
3. The path printed by `goga history path -f requirements.md` — the §3 requirement statements as
   triage arguments; Routine annotations — from the cells' CODEMANIFESTs ([ACCEPT_SCOPE]).

### Step 2. Run

1. Execute the command from [ACCEPT_SCOPE] from the directory containing `conftest.py` (strict
   mode — the cache was generated at build, no LLM calls are needed).
2. Record the full result: passed / failed / errors for each test.
3. A cache-miss in strict mode for a test with a missing cache (known from consistency) —
   classify it as the separate outcome **CACHE_MISS**: one non-strict run of that test to
   regenerate the cache (`pytest tests/web/<cell>/test_<name>.py -q` — without
   `--strict-mode`, but with the browser suffix from [ACCEPT_SCOPE] if one is set; the LLM
   provider must be available), record the regeneration, then rerun in strict mode.
4. The environment is unavailable (pytest/the web plugin does not start; the browser at the
   Browser endpoint address is unavailable; the site does not respond) — STOP, but only after an
   explicit question to the user: restore the environment and continue / finish the acceptance
   with the verdict REJECTED (the run is impossible).

### Step 3. Classify outcomes

Each test gets an outcome:

- **PASSED** — green; the annotation's expectation is confirmed.
- **FAILED** — an assertion mismatch: the Routine annotation's expectation vs. the actual page
  behavior. A service-bug candidate if both the expectation and the test are correct.
- **ERROR** — the test never reached the assertion: imports, a fixture, materialization, a
  cache-miss in strict mode. A test/environment-defect candidate.
- **CACHE_MISS** — the step was not found in the strict-mode cache; resolved by regeneration
  (Step 2.3) or it points to a proposal defect.

### Step 4. Failure triage (WAIT — every failed test)

Process every unclosed test (FAILED/ERROR/CACHE_MISS after regeneration), one test per message.
Assemble a dossier: the test, the Routine annotation (Purpose + `Steps:` from the CODEMANIFEST),
the actual result (assert/traceback/screenshot evidence), and the §3 requirement statement as
context.

Dossier analysis (arguments for the user, not a decision made for them):

- The annotation is correct (the expectation is confirmed by the requirements/user), and the
  test matches it → the service's behavior violates the expectation → arguments for a service
  bug.
- The test distorts the annotation (wrong data, wrong assertion, an extra step) → arguments for
  a test fix.
- The step proposal is ambiguous (the LLM generated the wrong thing / the element is not found
  reliably) → arguments for refining the proposal (with the user; the source is the annotation) +
  regenerating the step's cache.
- The evidence is insufficient (the annotation's expectation is imprecise, the page behavior is
  ambiguous) → arguments for returning to the testcases pipeline (routines design).
- The site/environment is unreachable or responds from the wrong environment → restore the
  environment first; do not classify it as a service bug until the environment is confirmed.

AskUserQuestion (2–4 options):

- **question**: "Test `test_<name>` failed: <one-line failure summary>. Where does it belong?"
- **header**: "Failure triage"
- **options**:
  - **label**: "Fix the test", **description**: "Test defect — edit test_*.py here and rerun"
  - **label**: "Service bug", **description**: "The test is correct — write a record to `goga history path -f bugs.md`"
  - **label**: "Back to routines", **description**: "The annotation/requirement is ambiguous — re-clarify via the testcases pipeline"
  - **label**: "Restore environment", **description**: "Browser/LLM key/site unavailable — restore and rerun"

### Step 5. Execute the triage decision

**Fix the test** — with the user's approval:

1. Step-proposal defect:
   - refine the wording with the user; update the proposal in `test_*.py`;
   - if the generation is broken — delete the step's cache file at
     `tests/web/<cell>/.cache/test_<name>/test_<name>/` and regenerate it with a non-strict run
     (the cache is never edited by hand);
   - the cache file of a page method/activation step lives in the shared cache
     `pages/.cache/<page>/<method>/` — deleting it affects **all** tests calling that method (regeneration — a
     non-strict run of any test of that page).
2. Any other defect (assert/data/import) — fix `test_<name>.py` according to the Routine
   annotation.
3. Rerun the test in isolation (strict); if it fails again — repeat the triage (Step 4) with a
   fresh dossier.
4. The limit is two fix iterations per test; after that — unresolved (into the report; the
   verdict drops).

**Service bug** — after triaging all failures:

1. Group the failing tests by cause and write them to `goga history path -f bugs.md` (create the
   file if it is missing; preserve existing records and append the new ones).
2. **One record — one problem, not one test**: all tests that failed for the same cause go into
   one record's table; different causes — different records.
3. If the file already contains a record with the same cause — extend its table with the tests
   instead of creating a duplicate.

```md
## BUG-<topic>-<N>: <the problem, concretely — what is wrong, in one sentence>

- **Date:** <day/month/year>
- **Page/Flow:** <PAGE-<N> `<URL>`> (tests/web/<cell>/)
- **Severity:** <the highest severity among the failed tests: Critical/High/Medium/Low>

### Problem
<Concretely, 2–5 sentences: what the Routine annotation requires and what the page actually does
(the key fact — text/URL/state). The established cause — in one phrase. Do not retell the steps.>

### Failing tests
[Table: test `tests/web/<cell>/test_<name>.py` — `test_<name>` | Routine | one-line failure summary]

### Evidence
<One factual argument: the actual page text/URL/state or the assert output of one test.
Full tracebacks are not duplicated — the record stays readable.>

### Notes
<Hypotheses about the cause, observations. Omit if there are none.>
```

The `BUG-<topic>-<N>` numbering is sequential across the file; take the next free number.

**Back to routines** — record it in the report (the test stays failed; the annotation goes to the
`goga-tool-pybuggy-web-automate-testcases` pipeline — routines design); continue triaging the
remaining failures.

**Restore environment** — restore it (the browser at the Browser endpoint address, the LLM key in
env, site availability) and rerun the suite; this is neither a bug nor a test defect.

### Step 6. Run summary

After all failures are processed (no skips and no `xfail` — every failure stays in the totals):

1. The totals: passed / fixed (fixed and rerun to green) / bugs (bug records) / unresolved.
2. The list of created/updated bug records with their numbers.
3. Cache regeneration facts (which steps, by which run).
4. The rerun command for the user (after the service bugs are fixed) — strict, with the browser
   suffix from [ACCEPT_SCOPE] if one is set.

STOP if:

- the run environment is unavailable and the user did not restore it;
- an ERROR failure blocks the entire pytest collection (some tests never ran) — after the
  blocker is removed, repeat the full run.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [ACCEPT_RUN]

## Run command
[The executed command (strict) and the run directory]

## Test results
[Table: Test | Cell | Routine | Run outcome (PASSED/FAILED/ERROR/CACHE_MISS) | Outcome after triage (passed/fixed/bug/unresolved)]

## Triage log
[Table: Test | Classification (Test defect / Service bug / Environment / Ambiguous→routines) | User decision | Action]

## Fixed tests
[Table: File | What was fixed (edit / step-cache regeneration) | Rerun result. Write `none` if nothing]

## Cache regeneration
[Regenerated steps: test / step / non-strict run. Write `none` if nothing]

## Bug records
[List of created/updated BUG-<topic>-<N> records with paths. Write `none` if nothing]

## Unresolved
[Tests not closed by triage (fix limit exhausted / handed over to routines design). Write `none` if nothing]

## Rerun command
[The rerun command after the service bugs are fixed — strict, with the browser suffix
from [ACCEPT_SCOPE] if one is set]
```
