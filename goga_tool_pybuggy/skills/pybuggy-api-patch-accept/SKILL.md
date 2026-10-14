---
name: goga-tool-pybuggy-api-patch-accept
description: Final acceptance of the patch run — consistency check (every change landed in the CODEMANIFEST and the test code together), the final full-suite run, failure triage with the user and `bugs.md`, the report saved to the path printed by `goga history path -f accept.md`
---

# Pybuggy API Patch — Accept Result

## Identity

You are the orchestrator of the final acceptance of a patch run. The chain
`collect-intent → analyze-impact → review-impact → apply-manifests → code-design →
design-review → coding-plan → plan-review → build` has completed; your job now is to
verify the defining rule — every change landed in the CODEMANIFEST and in the test code
together — and to run the full suite. The run may have started on red tests; every
failure you meet is surfaced to the user, never masked.

## Mission

Run the acceptance: verify the manifest ↔ test-code consistency, run the final full
suite, triage every failure with the user, record service bugs in the path printed by
`goga history path -f bugs.md`, and deliver the report with a verdict.

## Paths

Pre-flight: check that the path printed by `goga history path -f workplan.md` exists.
- **Missing** — STOP: the plan stage must run first.
- **Exists** — proceed.

## Context Initialization

Before the pipeline starts, load the context via the **Skill tool**:

- **`goga-cell`** — the CODEMANIFEST DSL specification.
- **`goga-tool-pybuggy-api-cookbook`** — principles for test cells.
- **`goga-cell-python`** — Python language rules (naming, location).
- **`goga-tool-pybuggy-api-usage`** — the pybuggy runtime reference (api, asserts).

## Pipeline

Execute the steps strictly in sequence — one step at a time. Validate each step's output
before the next step starts. WAIT-gates: steps 2 and 3 require user interaction — one
question per message, 2–4 options.

### Step 1. Scope

1. Inventory the patch artifacts: the intent document, the dossier, the apply report,
   the design, the plan.
2. Collect the changed files: from the plan's per-task records and from the tree
   (`git status` / `git diff` against the run's starting point).
3. Determine the full-suite run command: `pytest <paths> -q` from the directory
   containing `conftest.py`, with `--base-url <url>` when the topic version (the intent
   document) is non-standard; sandbox-bound tests additionally require a
   docker-compatible container runtime.
- STOP if: the plan is missing; no changed files exist (nothing to accept).

### Step 2. Consistency — WAIT

1. Every manifest delta of the apply report landed in the test code: each edited or
   added Routine has its `test_*.py` matching the new annotations; each deleted Routine
   or cell has its test code deleted.
2. No orphans: no `test_*.py` without a Routine and no Routine without its test file.
3. No failure masking: no `pytest.skip`/skip-markers/xfail in the changed files.
4. Every changed file is recorded in the plan's tasks.
- WAIT: findings that require a user decision (fix the file here / return to the plan).

### Step 3. Run — WAIT

1. Execute the full-suite command, saving the output:
   `pytest <paths> -q [--base-url <url>] 2>&1 | tee "$(goga history path -f accept-log.txt)"`
   (a re-run overwrites the log).
2. Record the result of every test: passed / failed / errors.
3. Triage every failure with the user, one test per message (AskUserQuestion, 2–4
   options) — the categories of the Triage Policy below.
- STOP if: the execution environment is unavailable (pytest or the plugin fails to
  start, the SUT does not respond, the sandbox fails to start — no docker-compatible
  runtime, image pull failure, probe timeout, migrations failure) and cannot be
  recovered per an explicit user instruction.

### Step 4. Report

Save the final report to the path printed by `goga history path -f accept.md`: summary,
consistency findings and applied fixes, the run results and triage log, bug records,
open items, the verdict. Fill in every section; an empty section = an incomplete step =
a pipeline STOP.

## Triage Policy

Triage each failed test along these categories:

| Failure category | Meaning | Action |
|---|---|---|
| **Patch defect** | the change itself is wrong (broken edit, wrong assert, lost import) | fixed here, in `test_*.py` and the manifest together when the two must move, with user approval; re-run after |
| **Pre-existing red** | the failure predates the patch run | surfaced to the user and recorded; not repaired by patch (repair is a new intent) |
| **Service bug** | the test is correct; the SUT violates its contract | bug record in the path printed by `goga history path -f bugs.md` — one record per problem, with the failing tests listed |
| **Ambiguous** | insufficient data to decide | joint analysis with the user (WAIT) |

A valid test failure (a failure that exposed a service bug or a pre-existing red)
**blocks the ACCEPTED verdict** but does not stop the pipeline: the remaining tests
still run, and the failure is recorded in the report.

## Invariants

### NEVER

- declare acceptance without the full-suite run — it is mandatory
- mask failures (`pytest.skip`, skip-markers, `xfail`) — every failure stays visible
- decide a triage (patch defect / service bug) without the user
- record a service bug without a concrete problem statement and the list of failing
  tests

### ALWAYS

- verify the manifest ↔ test-code togetherness before the run
- triage every failure together with the user (AskUserQuestion, 2–4 options)
- record service bugs in the path printed by `goga history path -f bugs.md`: one record
  per problem; the same cause found again — extend the existing record's failing-tests
  table
- include the verdict, the list of bug records, and the applied fixes in the final
  report
