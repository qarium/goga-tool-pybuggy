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
4. Read the plan, the design doc, the apply report; the topic version from the path
   printed by `goga history path -f intent.md` (it defines whether test-run commands
   must carry `--base-url <url>`).

### Phase 2. Base Verification

Invoke `goga-review-plan` via the **Skill tool**. It produces base findings: plan ↔
design consistency and lint. Combine these with the patch checks of Phase 3.

### Phase 3. Critical Checks

1. **`## Validation Commands` contains `pytest`** for the affected tests, with
   `--base-url <url>` when the topic version is non-standard. Missing pytest = **Critical**
   — the changes will not be verified.
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
6. **No failure masking:** any occurrence of `pytest.skip`/skip-markers/xfail in the
   plan = **Critical** — failure masking.
7. **Test mode:** the plan describes no production code, no Entities, no new
   `__init__.py`. A violation = **Critical**.

### Phase 4. Report & Fix

For every finding, report five fields: location, severity, problem, impact, fix. For a
Critical pytest absence or masked checkbox, propose the concrete fix: add pytest to
`## Validation Commands` and an executable checkbox for it. Apply plan edits only after
user approval, within the patch scope.

## Invariants

### NEVER

- overlook a missing or masked pytest — this check is the core of the review
- accept a plan without the deletion tasks or the changed-files records
- accept `pytest.skip`/skip-markers/xfail in the plan
- review the plan as a production implementation

### ALWAYS

- combine base `goga-review-plan` findings with the critical patch checks
- require executable pytest checkboxes with the topic's environment flag
- require the mandatory convention rules and the per-task changed-files records
