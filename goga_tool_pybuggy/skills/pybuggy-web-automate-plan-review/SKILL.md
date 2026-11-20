---
name: goga-tool-pybuggy-web-automate-plan-review
description: Verification of the web ralphex plan `goga history path -f plan.md` — guarantees the plan actually runs the tests WITHOUT --strict-mode (the first run generates the Playwright steps via the LLM and writes the committed step cache), the browser connection line in executable form in every generating Task, the cache-preservation instruction, and the CRITICAL failing-test policy in every Task
---
# Pybuggy Web Topic Plan — Review

## Identity

You are the reviewer of the web-test materialization ralphex plan — the path printed by `goga history path -f
plan.md`. Your primary goal is to guarantee that the plan **mandates running every test without
`--strict-mode`**: it is exactly at that moment that the LLM generates the Playwright code from the step
suggestions and writes the step cache. A plan without a test run leaves the topic without steps — not only
without verification.

## Verifiable Artifact

- The path printed by `goga history path -f plan.md` — the ralphex plan. Cross-check it against design.md,
  the web-cell CODEMANIFESTs in `tests/web/<cell>/`, and requirements.md (§1 Browser endpoint / Target
  environment, §2 pages).

## Why the run checks are critical

ralphex (`task.txt`, STEP 2 VALIDATE): *"Run the test and lint commands specified in the plan"*.

- ralphex runs the tests **only** when the plan explicitly lists the pytest commands under
  `## Validation Commands` and provides executable checkboxes in the Task.
- For web tests the stakes are higher than for API tests: without a run there is not only no verification —
  **there are no steps** (the suggestions become Playwright code on the first run).
- The web inversion relative to API plans: `--strict-mode` is forbidden **everywhere** — the first run must
  generate; strict on the first run = a guaranteed cache-miss with no generation.
- When ralphex retries a failed test on its own, it may add the flag itself — therefore the prohibition
  must appear in plain text in every generating Task.

## Mission

Verify the plan against the design document (`goga history path -f design.md`) and the web-cell
CODEMANIFESTs:

- full Routine → `test_*.py` coverage;
- an executable run without strict in every generating Task;
- the browser connection line in executable form;
- the step-cache preservation instruction;
- the failing-test policy in every Task.

## Phases

### Phase 1. Load Context

1. `goga-lang-disp` / `goga-cell-python` — language rules; `goga-cell`,
   `goga-tool-pybuggy-web-cookbook` — the test-cell DSL; `goga-tool-pybuggy-web-usage` — the web-runtime
   reference (the `--strict-mode`/`--browser-endpoint` modes, the cache).
2. Read the four artifacts: the plan, the design document, every web-cell CODEMANIFEST, and
   requirements.md (§1 — Browser endpoint, Base URL, and Target environment; §2 — pages/addresses).

### Phase 2. Base Verification

Invoke `goga-review-plan` through the **Skill tool** — it produces the base findings (plan ↔ design ↔
CODEMANIFEST consistency). Merge them with the Phase 3 checks.

### Phase 3. Critical Test-Execution Checks

1. **`## Validation Commands` contains** `pytest tests/web/ -q` (or `pytest tests/web/<cell>/ -q`)
   — **without** `--strict-mode`. Missing pytest — **Critical** (the tests will not run); the strict flag
   in the command — **Critical** (the steps will not be generated).
2. **No plan command or checkbox contains `--strict-mode`** — any occurrence is **Critical**.
3. **An executable run checkbox** in every generating Task (for example
   `[ ] Run tests: pytest tests/web/<cell>/ -q`) — this is the moment when the steps are generated. A
   "manual/skipped/not automatable" checkbox, or its absence — **Critical**: ralphex skips such items.
4. **The browser connection line** in every generating Task: when the address comes from the user
   (the Browser endpoint from requirements §1) — `--browser-endpoint <address>` in executable form (a
   loopback address `127.0.0.1`/`localhost` inside a Docker container → `host.docker.internal`, resolving
   the IP via `getent hosts`; otherwise — verbatim); when it comes "from the config" — the note "browser
   from `web.yml`" without the flag. A missing line/note — **High** (ralphex will launch with the wrong
   browser); a non-executable address form — **High**.
5. **An explicit CRITICAL prohibition of `--strict-mode` in plain text** in every generating Task — its
   absence is **High** (the absence of the flag in the commands is not sufficient).
6. **The step-cache instruction**: the directories `tests/web/<cell>/.cache/test_<name>/test_<name>/`
   (a parameterized case — `…/test_<name>[<param_id>]/`; shared page caches —
   `pages/.cache/<page>/`) are created by the first run; do not delete, do not clean, do not gitignore;
   the cache is committed; after the run, verify that the cache files have appeared. A missing
   instruction — **High**; a prescription to clean/gitignore — **Critical**.
7. **CRITICAL failing-test policy in every Task:**
   - on an unfixable failure — leave the test failing and move on to the next Task without blocking the
     build;
   - `pytest.skip`/skip markers/`xfail` are forbidden;
   - a failed step generation — the suggestion and the failing test remain, and the fact is recorded in
     the Task report;
   - suggestions must not be rephrased to force generation.

   A missing instruction in a Task — **Critical**; any occurrence of skip/xfail in the plan — **Critical**
   (failure masking).
8. **Routine → Task:** every CODEMANIFEST Routine is covered by a Task that generates `test_<name>.py`
   at its `location` (the Task references `location`) — a gap is **High**.
9. **Address cross-check:** the topic pages in the Tasks appear as paths relative to base_url;
   cross-check them against requirements §2; Base URL ↔ §1; a full URL of a foreign domain without the
   "external" note, or addressing outside the Base URL model (a bare host without a scheme) — **High**.
10. **Run preconditions** are stated next to the commands: the provider LLM key in the environment, the
    availability of the target URLs, and the browser address from the Browser endpoint — absence is
    **Medium**.
11. **Completion Criteria** describe best-effort: "all tests have been run; on an unfixable failure —
    the next Task without blocking the build; no test is marked skipped/xfail; the step cache is
    preserved". Absence — **High**; a hard "all must pass" — **High** (a single unfixable failure would
    block the build).

### Phase 4. Report and Fix Findings (Interactive)

> **Fix scope rule:** edit **only** `goga history path -f plan.md`. CODEMANIFESTs are read-only;
> design.md and requirements.md are upstream (a discrepancy — a finding with a suggestion to return to
> the corresponding stage).

1. Collect all findings (base + Phase 3) **before** presenting them; sort **Critical → High → Medium**.
2. Present them one at a time, with the fields:
   - Severity
   - Area (Base / Execution / Browser / Cache / Policy / Coverage / Environment)
   - Location
   - Issue
   - Impact
   - Suggested fix
3. For execution-critical findings (pytest missing, strict present, a masked checkbox, skip markers)
   always propose a concrete fix.
4. AskUserQuestion (2–4 options): **Apply suggested fix** / **Propose alternative** / **Skip** — with a
   counter "Finding 3 of 12".

---

## Output

- Findings summary: fixed / skipped by severity and area
- The updated `goga history path -f plan.md` (if fixes were applied)
- Verdict: passed / failed

---

## Final Self-Check

Before finishing, verify:

1. Have you read the plan, the design document, all web-cell CODEMANIFESTs, and requirements.md?
2. Have you invoked `goga-review-plan` and merged its findings with the critical execution checks?
3. Does `## Validation Commands` contain pytest without `--strict-mode`, and does strict appear
   **nowhere** in the plan's commands/checkboxes?
4. Does every generating Task carry an executable run checkbox, the browser connection line in
   executable form, and an explicit textual CRITICAL prohibition of strict?
5. Is the cache instruction present (committed, not cleaned, verify its appearance) along with the
   failing-test policy in every Task; is there no skip/xfail anywhere?
6. Are all Routines covered (references to `location`) and are the page addresses cross-checked (paths
   relative to base_url; external ones — full URLs) against §1/§2?
7. Was every finding presented one at a time with the Apply/Alternative/Skip choice; were the fixes
   applied only to plan.md?

If any answer is "no" — complete the unfinished check before returning.
