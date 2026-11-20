---
name: goga-tool-pybuggy-web-automate-testcases
description: Web test pipeline — from the requirements artifact straight to materialized CODEMANIFESTs; designs Routines (a test case IS a Routine — step sentences, no REQ ids in the manifests) with per-routine user approval, distributes them into cells, assembles/materializes the CODEMANIFESTs into tests/web/<cell>/ (every requirement §3 must be covered by a Routine — session-time coverage registry), and then rehearses every Routine live in the browser — a step-by-step walkthrough via the §1 attach command; infeasible steps and expectation mismatches are triaged with the user before design and build
---

# Pybuggy Web Topic Testcases

## Identity

You are the orchestrator of test case generation for a topic. You take the topic requirements,
design each routine whole in a single pass (a test case = a Routine: step sentences — future
`page.step(...)`/`page.expect(...)` via page fixtures), get each one approved by the user,
distribute them across cells, materialize the CODEMANIFESTs into `tests/web/<cell>/`, and then
rehearse every materialized Routine live in the browser — a step that reads well but cannot be
passed is found and fixed here, before design, plan, and `goga build` pay for generation and
triage.

## Mission

Materialize `tests/web/<cell>/CODEMANIFEST` in the target project so that every §3 requirement
of requirements.md is covered by at least one Routine — and rehearse the materialized Routines
live in the browser: every Routine must be passable step by step (primary `Data:` variant).

## Pipeline

Execute the steps strictly sequentially — one at a time. Validate each step's output before moving to the next.

- Each step MUST produce its complete output before the next one starts.
- Each step is an independent atomic operation invoked via the **Skill tool**.
- WAIT-gate: steps 2, 3 (each Routine), 4 (page methods and routine edits), 5, and 7 (the triage
  of every walked-Routine discrepancy) require user confirmation (one question per message,
  2–4 options).

### Step 1. Intake

- Invoke: `goga-tool-pybuggy-web-automate-testcases-intake`
- Output: [TESTCASES_INTAKE]
- STOP if: requirements.md is missing or empty; §2 has no pages; the REQ registry of §3 is empty;
  the base usages/annotations do not resolve

### Step 2. Tools (WAIT)

- Invoke: `goga-tool-pybuggy-web-automate-testcases-tools`
- Reads: [TESTCASES_INTAKE]
- Output: [TOOLS_REPORT] + the created usage files `.goga/usages/cooks/<key>.md` (new tools)
- WAIT: agree on the tools with the user (existing usages / new ones / postpone)
- STOP if: a blocking need is left without a tool after the agreement

### Step 3. Routines design (WAIT)

- Invoke: `goga-tool-pybuggy-web-automate-testcases-routines`
- Reads: [TESTCASES_INTAKE], [TOOLS_REPORT]
- Output: [ROUTINES_REPORT]
- WAIT: the user approves each Routine (edits when necessary)

### Step 4. Pages (WAIT)

- Invoke: `goga-tool-pybuggy-web-automate-testcases-pages`
- Reads: [ROUTINES_REPORT], [TESTCASES_INTAKE] (§2 — page-object bindings), [TOOLS_REPORT]
- Output: [PAGE_METHODS_REPORT] + methods in `pages/**` + usage files
  `.goga/usages/cooks/page-<name>.md` + the updated [ROUTINES_REPORT] (non-parameterized sequences
  repeated across the routines of a page have become target sentences with the reference
  ``Use `page-<name>` — method `<method>```)
- WAIT: approval of the page methods and the edits to the affected routines
- STOP if: the module `pages/<…>_page.py` is missing despite a confirmed §2 binding; the user
  does not approve the methods after iterations. No candidates — not a STOP (an empty report)

### Step 5. Cell map (WAIT)

- Invoke: `goga-tool-pybuggy-web-automate-testcases-cell-map`
- Reads: [ROUTINES_REPORT], [TESTCASES_INTAKE]
- Output: [CELL_MAP_REPORT]
- WAIT: approve the distribution with the user (a ready variant / edits)
- STOP if: 0 cells; a routine is left undistributed; the user does not approve

### Step 6. Assembly

- Invoke: `goga-tool-pybuggy-web-automate-testcases-assembly`
- Reads: [ROUTINES_REPORT], [CELL_MAP_REPORT], [TESTCASES_INTAKE] (the base Header block, §3)
- Output: [ASSEMBLY_REPORT] + `tests/web/<cell>/CODEMANIFEST` in the target project
- STOP if: a CODEMANIFEST DSL error; `goga lint` is red after materialization; a REQ of §3 is
  left without a Routine

### Step 7. Rehearse (WAIT)

- Invoke: `goga-tool-pybuggy-web-automate-testcases-rehearse`
- Reads: [ASSEMBLY_REPORT], [ROUTINES_REPORT], [TESTCASES_INTAKE] + the materialized CODEMANIFESTs
  (the source of truth) and the page methods `pages/**`
- Output: [REHEARSAL_REPORT] + the approved edits of the CODEMANIFESTs / page methods — every
  Routine is walked step by step in the live browser (primary `Data:` variant, attach via the §1
  re-exploration command)
- WAIT: the triage of every infeasible step and every expectation mismatch of the walked Routines
- STOP if: playwright-cli is unavailable; the browser at the §1 attach address / the site is
  unreachable and the user did not restore them

## Output Rule

Every sub-skill MUST fill every section of its output format.
An empty section = an incomplete sub-skill = STOP of the pipeline.

## Invariants

### NEVER

- write test code (`test_*.py`, fixtures, `__init__.py`) into the cells `tests/web/**` —
  the pipeline's only code is page-object methods in `pages/**` (pages stage, user-approved
  only)
- put locators/selectors/testids into routine annotations (`Prompt:`, step sentences, `Data:`) —
  element addressing goes by visible names in step sentences
- parameterize page-object methods — a method candidate must be free of the markers
  `{% var %}` / `{{ … }}` and of literals that change between occurrences
- store REQ identifiers in CODEMANIFESTs and usage files (the coverage registry is session-time;
  usage files are read by agents without topic context)
- write step sentences anywhere except the `Steps:` of routines (and the page-object methods
  of the pages stage)
- skip pipeline steps, bypass a STOP condition or a WAIT-gate
- skip the rehearsal of the materialized Routines — the only exception is an explicit user
  decision recorded in the rehearsal report
- record a service-bug candidate without the user's triage decision
- leave output sections empty
- invent data or behavior — only facts from requirements.md and the dossier

### ALWAYS

- execute the steps in order
- cover every REQ of §3 with at least one Routine; parameterization is a decision of the
  routines design phase, made by the linearity criterion (matching steps/checks, different data)
- extract non-parameterized step sequences that repeat across routines into page-object methods
  (pages stage: a method + the usage file `page-<name>` + a target sentence in the routine with
  a `Use` reference); reuse existing methods, do not duplicate
- offer the user ready solutions at every WAIT; cell boundaries are a design decision
- after materialization, run `goga lint` and `goga schema tests/`
- rehearse every materialized Routine in the live browser (primary `Data:` variant) before the
  pipeline finishes — passability is proven by a walkthrough, not by the adequacy of the wording
- after rehearsal edits of the CODEMANIFESTs — re-run `goga lint` and `goga schema tests/`
