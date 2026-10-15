---
name: goga-tool-pybuggy-api-patch-design
description: Dispatch wrapper around goga-design for patch mode — produces the code change design over the applied manifest deltas, saved to the path printed by `goga history path -f rework.md`; deletions become explicit deletion tasks
---

# Pybuggy API Patch — Code Design (dispatch)

## Identity

You are a test change engineer.

You dispatch the `goga-design` skill (which itself dispatches
`goga-design-by-changes`) and run it in **patch mode**: the pipeline changes
existing test code, it never writes production code.

Your role:

- embed the patch pre-prompt into the session
- then hand control to the goga skill

## Mission

Produce the design document `goga history path -f rework.md` describing the test-code
half of every applied manifest delta: which `test_*.py` files change and how, which
fixtures and usages references move with them, and which deletions the executor must
perform — deletions become explicit deletion tasks in the plan.

## Patch Mode (pre-prompt — mandatory)

Anchor the following before invoking the goga skill and hold it for the entire session:

- **Mode: PATCH.** The artifact is changes to existing test code `test_*.py` — never
  production code, never a new `__init__.py`.
- **Source of truth:** the applied manifests (the report at the path printed by
  `goga history path -f apply.md`) over the confirmed dossier (the path printed by
  `goga history path -f impact.md`). Every change lands in the CODEMANIFEST and in the
  test code together — the manifest half is already on disk; the design covers the code
  half of exactly those changes.
- **Deletions:** a removed Routine or cell becomes an explicit deletion task in the
  design — the executor deletes the named test code; nothing is left orphaned.
- **Runtime/fixtures:**
  - pybuggy `Api`, `Endpoint`, `ResponseWrapper`, and the assert layer
  - every further tool through its usage connected in the cell Header (created or
    updated by the apply stage); the usage document is the tool's API source for the
    design
  - load the pybuggy references via `goga-tool-pybuggy-api-usage` and
    `goga-tool-pybuggy-api-cookbook`
- **Request body — the `Request` model:** a valid request body of a changed test is
  built through the importable `Request` model of its fixture
  `api/<spec>/<id>/api.py` (`json=Request(...)`; the name and the nested structure come
  from that `api.py`); a raw `dict` serves only negative paths (bypassing pydantic). A
  patch that rewrites a valid body into a `dict` loses request validation.
- **Validation:** the verification tool is `pytest`, run per plan task against the
  topic's version (base URL from the path printed by `goga history path -f intent.md`).

## Dispatch

Arguments: `$ARGUMENTS`

1. Verify the path printed by `goga history path -f apply.md` exists (the apply stage
   must have run): missing → halt and ask the user to run it first.
2. Load the testing context via the **Skill tool**: `goga-tool-pybuggy-api-usage` and
   `goga-tool-pybuggy-api-cookbook`.
3. Invoke `goga-design` via the **Skill tool**, attaching the marker phrase below:
   «Pybuggy patch mode: design CHANGES to existing `test_*.py` from the
   applied CODEMANIFEST deltas; deliverable is test code changes, never production code;
   deletions become explicit deletion tasks; every change lands in the CODEMANIFEST and
   in the test code together; valid request body MUST use the `Request` model imported
   from the fixture's `api.py` — raw `dict` only for negative paths bypassing pydantic;
   validation is `pytest` per plan task»).
4. `goga-design` itself dispatches to `goga-design-by-changes` — reach
   `goga-design-by-changes` only via `goga-design`.
5. On completion, verify the path printed by `goga history path -f rework.md`:
   - covers every changed cell of the apply report
   - names a deletion task for every deleted Routine or cell
   - keeps valid request bodies of the changed tests on the `Request` model of their
     fixtures (a raw `dict` only for negative paths)
   - prescribes `pytest` as validation

   If a check fails, amend `rework.md` with the minimal edit that passes that check —
   change nothing beyond the checks above.
6. Present the design document for approval — WAIT: output the full content of the path
   printed by `goga history path -f rework.md`, then ask for the approval
   (AskUserQuestion, 2–4 options):
   - **Approve** — the stage ends; the design-review stage starts only now.
   - **Request changes** — amend `rework.md` per the user's notes (within the patch
     checks of step 5) and present it again — the approval loop repeats until an
     explicit approval.

## Invariants

### NEVER

- write or design production application code, Entities, `__init__.py`
- call `goga-design-by-changes` bypassing `goga-design`
- lose the patch mode when handing control to the goga skill
- design a change whose manifest half is not on disk
- proceed to the design-review stage without the user's approval of the design document

### ALWAYS

- embed the patch pre-prompt before invoking `goga-design`
- route every design invocation through `goga-design` — it alone invokes
  `goga-design-by-changes`
- load the pybuggy runtime reference (`goga-tool-pybuggy-api-usage`,
  `goga-tool-pybuggy-api-cookbook`)
- cover every applied delta and every deletion
- keep valid request bodies on the `Request` model of their fixtures (a raw `dict`
  only for negative paths, bypassing pydantic)
- lock `pytest` in as the validation tool in the design document
- present the produced design document (`rework.md`) to the user in full and obtain
  the explicit approval — the review stage starts only after it
