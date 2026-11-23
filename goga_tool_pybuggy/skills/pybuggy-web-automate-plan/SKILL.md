---
name: goga-tool-pybuggy-web-automate-plan
description: Dispatch wrapper around goga-plan for web testing mode — compiles the ralphex test-materialization plan; guarantees an executable test-run checkbox in every generating Task WITHOUT --strict-mode, because the first run is when the LLM generates the Playwright step code and writes the committed step cache
---

# Pybuggy Web Topic Plan (dispatch)

## Identity

You are a web test materialization planner. You dispatch `goga-plan` in **web testing mode**.

**Critical objective:** guarantee that the final ralphex plan **mandates running every test in the task without `--strict-mode`**.

## Why this fixes `goga build`

ralphex (`task.txt`, STEP 2 VALIDATE): *"Run the test and lint commands specified in the plan"*. ralphex runs the tests **only** when the plan explicitly lists the `pytest` commands in `## Validation Commands` and provides executable checkboxes in the Task. For web tests this matters even more than for API tests: without a run there is not only no verification — **there are no steps at all**. Sentences (`page.step(...)`/`page.expect(...)`) turn into Playwright code only on the first run (by the LLM). Without a run there is no step cache either — and without that cache strict acceptance is impossible. The standard `goga-plan` targets production code and does not build pytest validation into the plan → tests get written but are never executed and never cached. This dispatch wrapper forcibly injects pytest (without strict) into the plan.

## Mission

Compile the ralphex plan `goga history path -f plan.md` from the design document and the web-cell CODEMANIFESTs so that the following conditions hold:

1. each Routine of a web cell maps to a Task that generates the corresponding `test_*.py`;
2. `## Validation Commands` contains `pytest tests/web/ -q` (or a per-cell command) — **without**
   `--strict-mode`;
3. each generating Task carries a **test-run block** of three mandatory elements:
   - **an executable checkbox with the run command** (not "manual/skipped") so that ralphex executes it —
     step generation happens exactly at that moment;
   - **a browser connection line**: `--browser-endpoint <address>` in the executable form of the
     Browser endpoint from requirements §1; "from config" — the note "browser from `web.yml`", without the flag;
   - **an explicit CRITICAL prohibition of `--strict-mode`** in the Task text.

   ralphex executes tasks verbatim and on its own: without the connection line it will launch with
   the wrong browser, and without the prohibition it may add strict;
4. **no** command or checkbox in the plan contains `--strict-mode` — strict mode on the first run
   means a guaranteed cache-miss with no generation;
5. the plan mandates preserving the step cache (`tests/web/<cell>/.cache/test_<name>/test_<name>/`,
   a parameterized case — `…/test_<name>[<param_id>]/`; the shared page-method cache
   `pages/.cache/<page>/<method>/`) — never delete, clean, or gitignore it; the cache is committed to the
   repository;
6. **every** Task in the plan carries the CRITICAL failing-test instruction with three parts:
   - **Diagnose first — parse the pytest log**: the run output/log (wherever the environment
     writes it) is the first evidence source. Classify the failure: a provider/generation error
     (no code produced) / a cache-miss / an execution failure (element not found, wrong element,
     assertion mismatch, timeout, navigation). Read the failed sentence and its generated code
     (the cache file — reading is allowed, editing is not). When the cause is not in the log —
     look at the live page: playwright-cli attach at the Browser endpoint (requirements §1) →
     `goto` → `find` the sentence's visible name / `snapshot` (read-only) → `detach` after.
   - **Fix by cause — do everything possible so the steps are generated and the tests are
     written**: a test failure at build is an implementation defect (the scenario and its
     expectations were rehearsed live before build) — so **fix the test `test_*.py`, not the
     contract**: reformat the failing step (adapt the sentence wording to what the page actually
     has), adjust the glue (fixtures, order, `vars`, waits, activation blocks), and when a step's
     wording/execution changed — delete its stale cache file and regenerate it with one non-strict
     run (the cache is **never edited by hand**). A provider/generation error → check the
     key/model (web.yml) and retry the non-strict run — not a sentence problem; the environment →
     restore it. The **CODEMANIFEST, `pages/**`, and requirements stay read-only**; skipped tests
     (`pytest.skip`, skip markers, `xfail`) are **forbidden**. Limit — **3 refinement iterations
     per test** (each = cause → targeted fix → isolated re-run; blind retries do not count toward
     a fix and only burn time).
   - **Abandon (last resort)**: only after all sanctioned options are exhausted and the test still
     fails after 3 iterations — leave the test failing, record the cause and the fact in the Task
     report (was → became), and move on to the next task without blocking the build. An element
     that does not exist / a flow that does not hold is **not fixable at build** — the same
     fallback (it goes to accept triage). Recurring refinements of the same step are candidates
     for `Prompt:` bullets / annotation updates via the user.

   This constraint carries the same weight as the read-only CODEMANIFEST.

## Testing Mode (pre-prompt — mandatory)

- **Mode: TESTING.** The deliverable is test code (`test_*.py`), not production code. The web-cell
  CODEMANIFEST is a read-only contract and the source of truth.
- **Runtime:** page fixtures `page_<name>` (activation `with page_<name>() as page:`, the surface
  `page.step`/`page.expect`/`page.group`), variable captures, per-test `@generation_prompt`
  decorators (materialize the annotation's `Prompt:` section), the cache next to the test, the
  modes `--strict-mode`/`--interactive`/`--browser-endpoint`. Load
  `goga-tool-pybuggy-web-usage` and `goga-tool-pybuggy-web-cookbook`.
- **Step sentences:** one step = one action; the address of a page of the site under test is a path
  relative to base_url (`/catalog`, from requirements §2; a full URL — only for an external page);
  expectations go in separate `page.expect`;
  secrets are forbidden (login is "Perform login as test user `<role>`").
- **Linear parameterization:** variants of one Routine (declared in its `Data:`/`Steps:`) differ
  only in values — the test body is linear, and the steps and checks are shared across all variants.
- **TDM inverted:** there is no separate "implementation code" — the test files are the implementation.
- **Step generation:** the first run of each test generates the Playwright code for the sentences
  via the LLM and writes the cache to `tests/web/<cell>/.cache/test_<name>/test_<name>/`
  (page-method sentences — the shared cache `pages/.cache/<page>/<method>/`, the activation — `__call__`); the cache is committed. The
  first run goes without `--strict-mode`; repeat/CI runs — with `--strict-mode`.
- **Executable form of the Browser endpoint address:** write the address from requirements §1 into
  the commands in a form that is executable in the current environment: a loopback address
  (`127.0.0.1`/`localhost`) inside a Docker container (`test -f /.dockerenv`) →
  `host.docker.internal` (IP via `getent hosts host.docker.internal`, empty output — use the name
  as is); otherwise — verbatim. The plan is compiled and executed by ralphex in the same
  environment: a form that is correct at compile time is correct at run time.
- **CRITICAL: strict prohibition in every task —** every generating Task carries an explicit
  textual prohibition: the first run goes **without** `--strict-mode` — the LLM generates the
  Playwright code for the sentences and writes the cache exactly then; strict on the first run =
  a guaranteed cache-miss with no generation. The flag's absence from the commands is not enough —
  ralphex, when it retries a failed test on its own, may add the flag.
- **CRITICAL: Diagnose before fixing —** parse the pytest log/run output (wherever the environment
  writes it) before touching anything: classify the failure (a provider/generation error — no code
  produced; a cache-miss; an execution failure — element not found, wrong element, assertion
  mismatch, timeout, navigation), read the failed sentence and its generated code (the cache file —
  reading is allowed, editing is not). When the cause is not in the log — look at the live page
  (playwright-cli attach at the Browser endpoint, requirements §1: `goto` + `find` the sentence's
  visible name + `snapshot`, read-only, `detach` after).
- **CRITICAL: Implementation refinement policy —** embed this instruction into **every** Task of
  the plan: a test failure at build is an implementation defect (the scenario and its expectations
  were rehearsed live before build) — the agent must **do everything possible so that the steps
  are generated and the tests are written**: fix the test `test_*.py`, not the contract — reformat
  the failing step (adapt the sentence wording to what the page actually has), fix the glue
  (fixtures, order, `vars`, waits, activation blocks), retry the generation (delete the step's
  stale cache file + one non-strict run; the cache is **never edited by hand**); a
  provider/generation error → check the key/model (web.yml) and retry the non-strict run — not a
  sentence problem; the environment → restore it, not a refinement. The CODEMANIFEST, `pages/**`,
  and requirements stay read-only; **do NOT skip tests** (`pytest.skip`, skip markers, `xfail`) —
  the failure must remain visible. Limit — **3 refinement iterations per test** (each = cause →
  targeted fix → isolated re-run; blind retries do not count); only after all sanctioned options
  are exhausted — leave the test failing, record the cause and the fact in the Task report
  (was → became), and move on to the next task without blocking the build. An element that does
  not exist / a flow that does not hold is **not fixable at build** — the same fallback (it goes
  to accept triage). Recurring refinements of the same step are candidates for `Prompt:` bullets /
  annotation updates via the user. This constraint carries the same weight as the read-only
  CODEMANIFEST.

## Dispatch

Arguments: `$ARGUMENTS`

1. Verify that the path printed by `goga history path -f design.md` exists, as in `goga-plan`;
   if it is missing → stop and ask the user to run the design stage first.
2. Load the context via the **Skill tool**: `goga-tool-pybuggy-web-usage`,
   `goga-tool-pybuggy-web-cookbook`, `goga-cell`, `goga-cell-python`. Read the Base URL and the
   topic's target environment from the path printed by `goga history path -f requirements.md`
   (§1/§4) — the topic's pages in the Tasks are addressed as paths relative to base_url (external
   pages — by full URLs); switching the environment means switching `site.base_url`, not the step
   sentences.
3. Call `goga-plan` via the **Skill tool**, passing the web testing mode payload (marker phrase:
   "Pybuggy web testing mode: compile a plan to GENERATE and RUN browser UI tests from CODEMANIFEST
   web-cells; deliverable is `test_*.py` using page-object fixtures (`page_<name>`) with step sentences;
   `pytest tests/web/ -q` MUST be in Validation Commands and as executable Task checkboxes —
   WITHOUT `--strict-mode` (the first run generates the Playwright steps via the LLM and writes the
   step cache next to the test; the cache is committed); every generating Task carries the browser
   connection line — `--browser-endpoint <address>` in the executable form of the Browser endpoint
   (requirements §1; a 'browser from web.yml config' note when no flag) — and an explicit CRITICAL
   prohibition of `--strict-mode` in the Task text; every generating Task references the Routine
   `location` from the CODEMANIFEST; one action per step sentence, site pages addressed as paths
   relative to the base URL with external pages by full URLs; CRITICAL in EVERY
   Task: do everything possible so that the steps are generated and the tests are written —
   parse the pytest log, find out what the problem is (provider/generation error, cache-miss,
   execution failure), try reformatting the step in `test_*.py` (adapt the sentence wording to
   the actual page, fix the glue), retry the generation (delete the step's stale cache file +
   one non-strict run); never edit the cache by hand; the CODEMANIFEST and `pages/**` stay
   read-only; a provider error is retried, not reworded; limit 3 targeted refinement iterations
   per test — only after all options are exhausted leave the test failing, record the cause in
   the Task report, and proceed to the next task; do NOT skip/xfail tests; do not block the
   build").
4. `goga-plan` dispatches `goga-plan-by-design` itself — do not call it bypassing `goga-plan`.

## Post-Dispatch Gate (critical — enforcing step generation)

After `goga history path -f plan.md` has been generated, verify the conditions below and amend the
plan where necessary:

1. **`## Validation Commands`** contains a run command of the form `pytest tests/web/ -q` (or
   `pytest tests/web/<cell>/ -q` for a specific cell) — **without** `--strict-mode`. If the
   command is missing, add it.
2. **No command or checkbox in the plan contains `--strict-mode`.** If found, remove the flag: the
   first run must generate the steps and write the cache; strict on the first run = a guaranteed
   cache-miss.
3. **Browser connection:** when the address comes from the user (the Browser endpoint of
   requirements §1), every run command — in Validation Commands and in Task checkboxes — carries
   `--browser-endpoint <address>` in the executable form (the Testing Mode rule); "from config" —
   without the flag.
4. **Tasks** contain a run checkbox that is **executable** (for example
   `[ ] Run tests: pytest tests/web/<cell>/ -q`) in every generating task — the steps are
   generated exactly at that moment. Never mark a run as "manual", "skipped", or "not automatable" —
   ralphex skips such items. Every generating Task must also carry the **browser connection
   line** (`--browser-endpoint <address>` | "browser from `web.yml`") and an **explicit CRITICAL
   prohibition of `--strict-mode`** — if missing, add them.
5. Every Task that generates a `test_*.py` references the `location` field from the CODEMANIFEST
   of the corresponding web cell.
6. **The cache instruction** is present in the plan: the directories
   `tests/web/<cell>/.cache/test_<name>/test_<name>/` (and the shared `pages/.cache/<page>/<method>/`) are
   created by the first run; never delete, clean, or gitignore them; after the run, make sure the
   cache files have appeared. If missing, add it.
7. **Address cross-check:** page addresses in the Tasks ↔ requirements §2 (paths relative to
   base_url); Base URL ↔ §1; external pages — full URLs of a foreign origin marked "external"; the
   run commands carry the base_url render arguments (env/CLI) from §1 if any are specified.
8. **CRITICAL refinement policy in every Task**: the diagnose instruction (parse the pytest log/run
   output — wherever the environment writes it; classify the failure; read the step's cached code
   read-only; a live-page check via playwright-cli when the cause is not in the log) + the
   "do everything possible" refinement instruction (reformat the step in `test_*.py`, fix the
   glue, retry the generation via a stale-cache deletion + one non-strict run; never edit the
   cache by hand; CODEMANIFEST/`pages/**` read-only; limit 3 targeted iterations) + the abandon
   fallback (only after all options are exhausted — leave failing, record the cause in the Task
   report, move on). Verify that `pytest.skip`/skip markers/`xfail` appear nowhere in the plan.
9. **Run preconditions** are named next to the commands: the provider's LLM key in the
   environment, and the reachability of the target URLs and of the browser address from the
   Browser endpoint (§1).
10. **Completion Criteria** describe best-effort: "all tests have been run; on an unfixable
   failure — move to the next task without blocking the build; no test is marked skipped/xfail;
   the step cache is saved".

If the plan fails the gate, add the missing items per the requirements of the Testing Mode section
and report the additions to the user.

## Invariants

### NEVER

- deliver a plan without `pytest` in `## Validation Commands`
- let `--strict-mode` into **any** command or checkbox of the plan — the first run generates the
  steps
- mark the test run as "manual/skipped/not automatable"
- plan production code
- lose the web testing mode when handing over control
- prescribe deleting/cleaning/gitignoring the step cache wholesale — the only sanctioned cache
  deletion is the stale file of a changed step, followed by one non-strict regeneration
- mask a failure with `pytest.skip`/skip markers/`xfail` — the failure must remain visible
- let a Task instruct editing the CODEMANIFEST, `pages/**`, or the cache by hand — the refinement
  surface is `test_*.py` only
- deliver a Task without the CRITICAL refinement policy (fix the test, limit 3, then abandon)

### ALWAYS

- embed the web testing pre-prompt before calling `goga-plan`
- guarantee the run block in every generating Task: an executable run checkbox without strict (the
  moment of step generation), a browser connection line in executable form, and an explicit
  prohibition of `--strict-mode`
- include the step-cache preservation instruction in the plan (the cache is committed to the
  repository)
- run the Post-Dispatch Gate and keep reworking the plan until pytest validation without strict is
  in place
- build the plan on the web-cell CODEMANIFESTs and their `location` fields
- load the web runtime reference and the DSL
- embed the CRITICAL refinement policy (parse the pytest log and diagnose; reformat the step and
  fix the glue in `test_*.py`; retry the generation via a stale-cache deletion + one non-strict
  run, never hand-edited; do everything possible so the steps are generated and the tests are
  written; limit 3 targeted iterations; abandon only after all options are exhausted) into
  **every** Task of the plan
