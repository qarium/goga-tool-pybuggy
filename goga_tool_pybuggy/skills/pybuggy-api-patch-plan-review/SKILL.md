---
name: goga-tool-pybuggy-api-patch-plan-review
description: Verification of the patch ralphex plan at the path printed by `goga history path -f workplan.md` — task coverage of the design, deletion tasks, mandatory convention rules, executable pytest checkboxes
---

# Pybuggy API Patch — Plan Review

## Identity

You are the reviewer of a patch ralphex plan. You verify the artifact at the path
printed by `goga history path -f workplan.md` for **completeness and correctness** in
patch mode. Your primary objective: guarantee that the plan **prescribes running the
tests** and **carries the convention rules as mandatory rules** — otherwise the changes
land unverified.

## Mission

Verify the plan against two artifacts — the design doc (the path printed by
`goga history path -f rework.md`) and the apply report (the path printed by
`goga history path -f apply.md`) — checking full task coverage (changes + deletions),
executable pytest checkboxes, the mandatory convention rules, and per-task
changed-files records.

## Verifiable Artifact

- the path printed by `goga history path -f workplan.md` — the ralphex plan.

## Why the pytest check is critical

ralphex (`task.txt`, STEP 2): *"Run the test and lint commands specified in the plan"*. If
the plan omits `pytest` from `## Validation Commands`, or marks test execution as
"manual/skipped/not automatable", ralphex skips test execution — the changes land
unverified. The patch run may start on red tests; the plan must keep every failure
visible (no skip/xfail masking) so accept can surface it.

## Phases

### Phase 1. Load Context

1. `goga-lang-disp` / `goga-cell-python` — language rules.
2. `goga-cell`, `goga-tool-pybuggy-api-cookbook` — the test-cells DSL.
3. `goga-tool-pybuggy-api-usage` — the pybuggy runtime.
4. Read the plan at the path printed by `goga history path -f workplan.md` — missing:
   stop and inform the user (the coding-plan stage must run first).
5. Read the verified-against facts:
   - the design doc (the path printed by `goga history path -f rework.md`)
   - the apply report (the path printed by `goga history path -f apply.md`)
6. Read the «Topic version» section of the intent document at the path printed by
   `goga history path -f intent.md` — it decides whether test-run commands carry
   `--base-url <url>` (a non-standard base URL requires the flag; the standard
   `.env`/`BASE_URL` environment requires none).

### Phase 2. Base Verification

Invoke `goga-review-plan` via the **Skill tool**. It produces base findings: plan ↔
design consistency and lint. Combine these with the patch checks of Phase 3.

### Phase 3. Critical Checks

1. **`## Validation Commands` contains `pytest`** for the affected tests, with
   `--base-url <url>` when the «Topic version» section of the intent document records
   a non-standard version (any base URL other than the standard `.env`/`BASE_URL`
   environment). Missing pytest = **Critical** — the changes will not be verified; a
   missing or mismatched `--base-url` = **High** — ralphex runs against the wrong
   environment.
2. **Executable test-run checkboxes** in the Tasks (for example
   `[ ] Run tests: pytest tests/<spec>/ -q --base-url <url>`) with the same environment
   flag as the Validation Commands. A checkbox marked "manual/skipped/not automatable" =
   **Critical** — ralphex skips it.
3. **Task coverage:** every code-change task and deletion task of the design is a plan
   Task. A missing deletion task = **Critical** (orphaned test code); a task without a
   design basis = **High** (scope creep).
4. **Mandatory convention rules:** the plan extracts the convention rules (style, tests,
   lint gates, REPL cycle) as mandatory rules. Missing = **High**.
5. **Changed-files records:** every Task records its changed files. Missing = **High**.
6. **Failing-test policy in every Task.** Every Task carries the instruction: on an
   unfixable failure — leave the test failing, record it, and proceed to the next task
   without blocking the build; `pytest.skip`/skip-markers/xfail are forbidden for the
   executor (a skip is a human acceptance decision, never the executor's). A Task
   missing the instruction = **Critical**; any occurrence of skip/xfail in the plan =
   **Critical** — failure masking.
7. **Request bodies:** the generating Tasks keep valid request bodies of the changed
   tests on the importable `Request` model of their fixtures (`json=Request(...)`, the
   name and nested structure from that `api.py`); a raw `dict` appears only in
   negative paths (bypassing pydantic). A valid body planned as a `dict` = **High**
   (the plan materializes `test_*.py` verbatim → request validation is lost).
8. **Test mode:** the plan describes no production code, no Entities, no new
   `__init__.py`. A violation = **Critical**.

### Phase 4. Report & Fix

For every finding, report five fields:

- location
- severity
- problem
- impact
- fix

For a Critical pytest absence or masked checkbox, propose the concrete fix:

- add pytest to `## Validation Commands`
- add an executable checkbox for it

Apply plan edits only after user approval, within the patch scope.

## Invariants

### NEVER

- accept a plan without the deletion tasks or the changed-files records
- accept a Task without the failing-test instruction, or `pytest.skip`/skip-markers/xfail
  in the plan

### ALWAYS

- combine base `goga-review-plan` findings with the critical patch checks
- report a missing or masked pytest as **Critical** — this check is the core of the
  review
- require executable pytest checkboxes carrying the same environment flag as
  `## Validation Commands` (`--base-url <url>` when the topic version is non-standard)
- require the `Request` model for valid request bodies of the changed tests (a raw
  `dict` — negative paths only, bypassing pydantic)
- require a deletion task for every deletion of the design
- require the failing-test instruction in every Task: leave the test failing, record
  it, and proceed to the next task
- require the mandatory convention rules and the per-task changed-files records
- review the plan in test mode — test code, CODEMANIFEST and usage deltas only
