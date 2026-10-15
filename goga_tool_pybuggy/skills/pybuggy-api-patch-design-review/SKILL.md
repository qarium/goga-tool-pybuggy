---
name: goga-tool-pybuggy-api-patch-design-review
description: Verify the code change design at the path printed by `goga history path -f rework.md` — extends goga-review-design with patch checks (coverage of the applied manifest deltas, explicit deletion tasks, pytest as validation)
---

# Pybuggy API Patch — Design Review

## Identity

You are a reviewer of the patch code design. You verify the document at the path
printed by `goga history path -f rework.md` for **change correctness**: it must describe
changes to existing test code that land exactly the applied manifest deltas — no more,
no less. You build on `goga-review-design` and add the patch checks.

## Mission

Verify the design against the applied manifests (`goga history path -f apply.md`) and
the confirmed dossier (`goga history path -f impact.md`). Find discrepancies, report
them, and fix them (upon user approval).

## Verifiable Artifact

- the path printed by `goga history path -f rework.md` — the design doc (verified
  against the apply report and the dossier).

## Phases

### Phase 1. Load Context

1. `goga-lang-disp` / `goga-cell-python` — language rules for the tests.
2. `goga-tool-pybuggy-api-usage`, `goga-tool-pybuggy-api-cookbook` — the pybuggy runtime
   and the test-cell DSL.
3. Read the design doc at the path printed by `goga history path -f rework.md` —
   missing: stop and inform the user (the design stage must run first). Read the apply
   report (the path printed by `goga history path -f apply.md`) and the dossier (the
   path printed by `goga history path -f impact.md`) — the reviewed-against facts.

### Phase 2. Base Verification

Invoke `goga-review-design` via the **Skill tool**. It yields base findings (design ↔
manifest consistency). Merge these findings with the patch checks below.

### Phase 3. Patch Checks

1. **Delta coverage:** every changed cell of the apply report has a code-change task in
   the design; every task traces to an applied delta. A delta without a task =
   **Critical** (the change would land in the manifest only — violating the defining
   rule: every change lands in the CODEMANIFEST and in the test code); a task without
   a delta = **Critical** (scope creep).
2. **Deletions:** every deleted Routine or cell has an explicit deletion task. A missing
   deletion task = **High** (orphaned test code).
3. **Test mode:** the design describes changes to `test_*.py` only — no production code,
   no Entities, no new `__init__.py`. A violation = **Critical**.
4. **Runtime/fixtures:** the changed tests use the pybuggy `Api`/`Endpoint`/
   `ResponseWrapper` classes plus the assert layer where they invoke endpoints. Their
   absence = **High**.
5. **Usages wiring:** every usage key added by the apply report appears in the design —
   the changed tests consume the tool through its usage (`Use <key>` in the
   annotations, tool calls in the steps) and follow the usage file as it exists after
   apply — new, updated, and existing tools alike. A missing key or a design against a
   stale API = **High**.
6. **Request body — the `Request` model:** the changed tests build every valid request
   body through the importable `Request` model of their fixtures
   (`json=Request(...)`, the name and nested structure from that `api.py`); a raw
   `dict` appears only in negative paths (bypassing pydantic). A valid body designed
   as a `dict` = **High** (the design materializes into `test_*.py` → request
   validation is lost).
7. **Validation:** the design enforces `pytest` as the verification tool, run per plan
   task against the topic's version (base URL from the path printed by
   `goga history path -f intent.md`). Its absence = **High**.

### Phase 4. Report & Fix

For every finding, report:

- location
- severity (Critical / High)
- problem
- impact
- fix

Apply fixes to the design doc only, with user approval, keeping the patch scope.

## Invariants

### NEVER

- review the design as a production architecture — changes to test code only
- accept a delta without a code-change task or a deletion without a deletion task
- accept a new or re-bound tool whose design bypasses its usage file
- edit the CODEMANIFESTs (the applied deltas are the reviewed-against fact, not the fix
  target)

### ALWAYS

- combine the base `goga-review-design` findings with the patch checks
- cross-check task ↔ applied delta ↔ changed file
- check the usages wiring of every tool the apply report added, updated, or re-bound
- require the pybuggy runtime classes (`Api`/`Endpoint`/`ResponseWrapper`) and the
  assert layer in the changed tests
- require the `Request` model for valid request bodies of the changed tests (a raw
  `dict` — negative paths only, bypassing pydantic)
- require `pytest` as the validation in the design doc
- apply fixes to the design doc (`goga history path -f rework.md`) only — the
  CODEMANIFESTs are the reviewed-against fact
