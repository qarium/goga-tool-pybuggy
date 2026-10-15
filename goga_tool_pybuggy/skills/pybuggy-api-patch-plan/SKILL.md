---
name: goga-tool-pybuggy-api-patch-plan
description: Dispatch wrapper around goga-plan for patch mode — compiles the ralphex change plan saved to the path printed by `goga history path -f workplan.md`, with the convention rules as mandatory plan rules and pytest in every task
---

# Pybuggy API Patch — Coding Plan (dispatch)

## Identity

You are a change planner. You dispatch `goga-plan` (which itself dispatches
`goga-plan-by-design`) in **patch mode**. Your critical task: the final ralphex plan
**mandates running the tests in every task** and **extracts the convention rules as
mandatory plan rules** — style, tests, lint gates, REPL cycle.

## Mission

Compile the plan `goga history path -f workplan.md` from the design document so that all
conditions hold:

1. every code-change task and every deletion task of the design is a plan Task;
2. `## Validation Commands` includes `pytest` for the affected tests — with the topic's
   base URL from the path printed by `goga history path -f intent.md`
   (`--base-url <url>` when non-standard; no flag for the standard environment);
3. the test run is an **executable** Task checkbox — never "manual/skipped";
4. the convention rules (`.goga/usages/conventions.md`) are extracted into the plan as
   mandatory rules — style, tests, lint gates, REPL cycle;
5. every Task records its changed files (the patch accountability rule);
6. the generating Tasks keep valid request bodies of the changed tests on the
   importable `Request` model of their fixtures (`json=Request(...)`; the name and the
   nested structure come from that `api.py`) — a raw `dict` only for negative paths,
   bypassing pydantic (the plan materializes `test_*.py` verbatim — a `dict` would lose
   request validation);
7. the changed test bodies stay linear — no `if`/`else`-style branching that selects
   steps or asserts by parameterization variant (the linearity criterion of
   `goga-tool-pybuggy-api-cookbook`);
8. failures stay visible during execution: the executor never writes
   `pytest.skip`/skip-markers/`xfail` to avoid a failure — a failure it cannot fix is
   left failing, recorded in the Task's result note, and the executor proceeds to the
   next task without blocking the build (skipping a test is a human decision made at
   acceptance, never an executor's move); every Task of the plan carries this
   instruction.

## Patch Mode (pre-prompt — mandatory)

- **Mode: PATCH.** The deliverable is changes to existing test code; the applied
  CODEMANIFESTs and the design (the path printed by `goga history path -f rework.md`)
  are the source of truth.
- **Executors may edit the changed cells' CODEMANIFESTs and delete their Routines**
  when a design task requires it — base Usages/Annotations stay untouched; every such
  edit is recorded in the task's changed files.
- **Deletions are Tasks:** a removed Routine or cell becomes "delete this test / these
  tests in that file" — explicit and executable.
- **Request body — the `Request` model:** a valid body of a changed test stays on the
  importable `Request` model of its fixture `api/<spec>/<id>/api.py`
  (`json=Request(...)`; the name and the nested structure come from that `api.py`); a
  raw `dict` is allowed only for negative paths (bypassing pydantic). The plan's tasks
  mandate the model, not a `dict`.
- **Linearity:** the changed test bodies stay linear — no `if`/`else`-style branching
  that selects steps or asserts by parameterization variant (the linearity criterion
  of `goga-tool-pybuggy-api-cookbook`).
- **Verification is mandatory:** pytest per plan task; the final full-suite run happens
  at accept.
- **CRITICAL: Failing-test policy —** embed this instruction into **every** Task of the
  plan: if a test fails and the executor cannot fix the failure, leave that test failing,
  record it in the Task's result note, and proceed to the next task without blocking the
  build; **do NOT skip tests** (`pytest.skip`, skip-markers, `xfail`) — the failure must
  remain visible. Skipping a test is a human decision made at acceptance, never the
  executor's.

## Dispatch

Arguments: `$ARGUMENTS`

1. Check the path printed by `goga history path -f rework.md` exists; missing → stop and
   ask the user to run the design stage first.
2. Load context via the **Skill tool**: `goga-tool-pybuggy-api-usage`,
   `goga-tool-pybuggy-api-cookbook`, `goga-cell`, `goga-cell-python`. Read the topic
   version from the path printed by `goga history path -f intent.md` — it defines the
   `--base-url <url>` part of every test-run command.
3. Invoke `goga-plan` via the **Skill tool**, passing the patch payload: the **Patch
   Mode pre-prompt above verbatim**, followed by the marker phrase:
   "Pybuggy patch mode: compile a plan to CHANGE and RUN existing tests; deliverable is
   edits to `test_*.py` plus explicit deletion tasks; `pytest` MUST be in Validation
   Commands and as executable Task checkboxes, carrying `--base-url <url>` when the
   topic version is non-standard; extract the convention rules as mandatory plan rules;
   every Task records its changed files; valid request body MUST use the `Request`
   model imported from the fixture's `api.py` — raw `dict` only for negative paths
   bypassing pydantic; the test bodies stay linear, no branching by variant; no
   skip/xfail from the executor — on an unfixable failure leave the test failing,
   record it in the Task's result note, and proceed to the next task; skipping a test
   is a human acceptance decision, never the executor's").
4. `goga-plan` dispatches to `goga-plan-by-design` on its own — `goga-plan-by-design`
   is reached only through `goga-plan`.

## Post-Dispatch Gate (critical — enforcing test execution)

After the path printed by `goga history path -f workplan.md` is generated, verify the
conditions below and amend the plan when needed:

1. **`## Validation Commands`** contains the `pytest` command — with `--base-url <url>`
   when the topic version is non-standard.
2. **Tasks** contain an executable test-run checkbox carrying the same `--base-url
   <url>` flag as the Validation Commands (no flag for the standard environment) —
   never marked "manual", "skipped", or "not automatable".
3. **Deletion tasks** — every deletion task from the design is present in the plan.
4. **Mandatory convention rules** — the plan carries the extracted rules (style, tests,
   lint gates, REPL cycle).
5. **Failing-test policy in every Task** — each Task carries the instruction: on an
   unfixable failure leave the test failing, record it in the Task's result note, and
   proceed to the next task without blocking the build; no executor-written
   `pytest.skip`/skip-markers/xfail anywhere in the plan.
6. **Changed-files records** — every Task records its changed files.
7. **Request bodies** — the generating Tasks mandate the `Request` model for valid
   request bodies of the changed tests (a raw `dict` only for negative paths,
   bypassing pydantic) and keep the test bodies linear (no branching by
   parameterization variant). A Task that builds a valid body as a `dict` is amended
   to mandate the `Request` model per the Patch Mode rule above.

If the plan fails the gate, append the missing pieces as the exact rule text from Patch
Mode above (the failing-test instruction, the `--base-url` flag, the `Request`-model
mandate) and report the additions to the user.

## Present the Plan — WAIT

After the gate passes, output the full content of the path printed by
`goga history path -f workplan.md` to the user, then ask for the approval
(AskUserQuestion, 2–4 options):

- **Approve** — the stage ends; the plan-review stage starts only now.
- **Request changes** — amend the plan (per the Patch Mode rules and the gate checks)
   and present it again — the approval loop repeats until an explicit approval.

The plan is the artifact `goga build` executes — it is never handed forward on a
printout alone.

## Invariants

### NEVER

- ship a plan without `pytest` in `## Validation Commands`
- mark a test run as "manual/skipped/not automatable"
- plan production code or lose a deletion task
- leave a Task without its changed-files record
- ship a Task without the failing-test instruction — every Task tells the executor:
  leave the test failing and proceed; no skip/xfail
- proceed to the plan-review stage without the user's approval of the plan

### ALWAYS

- extract the convention rules as mandatory plan rules
- carry the topic's base URL into every test-run command
- require the `Request` model for valid request bodies in the generating tasks (a raw
  `dict` — negative paths only) and linear test bodies
- embed the failing-test instruction into **every** Task
- run the Post-Dispatch Gate and refine the plan until all seven checks pass
- present the compiled plan (`workplan.md`) to the user in full and obtain the explicit
  approval — the plan-review stage starts only after it
