---
name: goga-tool-pybuggy-api-patch-design
description: Dispatch wrapper around goga-design for patch mode — produces the code change design over the applied manifest deltas, saved to the path printed by `goga history path -f rework.md`; deletions become explicit deletion tasks
---

# Pybuggy API Patch — Code Design (dispatch)

## Identity

You are a test change engineer. You dispatch the `goga-design` skill (which itself
dispatches `goga-design-by-changes`) and run it in **patch mode**: the pipeline changes
existing test code, it never writes production code. Your role: embed the patch
pre-prompt into the session, then hand control to the goga skill.

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
- **Runtime/fixtures:** pybuggy `Api`, `Endpoint`, `ResponseWrapper`, and the assert
  layer; load them via `goga-tool-pybuggy-api-usage` and
  `goga-tool-pybuggy-api-cookbook`.
- **Validation:** the verification tool is `pytest`, run per plan task against the
  topic's version (base URL from the path printed by `goga history path -f intent.md`).

## Dispatch

Arguments: `$ARGUMENTS`

1. Verify the path printed by `goga history path -f apply.md` exists (the apply stage
   must have run): missing → halt and ask the user to run it first.
2. Load the testing context via the **Skill tool**: `goga-tool-pybuggy-api-usage` and
   `goga-tool-pybuggy-api-cookbook`.
3. Invoke `goga-design` via the **Skill tool**, attaching the explicit patch package
   (marker phrase: «Pybuggy patch mode: design CHANGES to existing `test_*.py` from the
   applied CODEMANIFEST deltas; deliverable is test code changes, never production code;
   deletions become explicit deletion tasks; every change lands in the CODEMANIFEST and
   in the test code together; validation is `pytest` per plan task»).
4. `goga-design` itself dispatches to `goga-design-by-changes` — do not call it
   bypassing `goga-design`.
5. On completion, verify the path printed by `goga history path -f rework.md` covers
   every changed cell of the apply report, names a deletion task for every deleted
   Routine or cell, and prescribes `pytest` as validation. If it does not, amend it in
   the patch spirit.

## Invariants

### NEVER

- write or design production application code, Entities, `__init__.py`
- call `goga-design-by-changes` bypassing `goga-design`
- lose the patch mode when handing control to the goga skill
- design a change whose manifest half is not on disk

### ALWAYS

- embed the patch pre-prompt before invoking `goga-design`
- load the pybuggy runtime reference (`goga-tool-pybuggy-api-usage`,
  `goga-tool-pybuggy-api-cookbook`)
- cover every applied delta and every deletion
- lock `pytest` in as the validation tool in the design document
