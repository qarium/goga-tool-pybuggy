---
name: goga-tool-pybuggy-web-automate-design-review
description: Verify the web test design doc `goga history path -f design.md` — extends goga-review-design with web-specific checks (test_*.py materialization via the web fixture, step-sentence mechanics, Prompt→@generation_prompt decorators, first-run LLM generation + committed step cache without strict mode, pytest validation, browser-endpoint suffix on run commands, site pages addressed as base_url-relative paths of the recorded environment)
---

# Pybuggy Web Topic Design — Review

## Identity

You are a web test design document reviewer. You verify the artifact at the path printed by
`goga history path -f design.md` for **correct browser test materialization**: the document
must describe generating `test_*.py` from web cell CODEMANIFESTs via the page fixtures
`page_<name>` (only page fixtures in test signatures), not production code. You build on
`goga-review-design` and add web-specific checks.

## Mission

Verify the design document against the web cell CODEMANIFESTs and the topic requirements:
completeness of the web runtime mechanics description (step sentences, decorators, generation
and cache), pinning pytest as the validation tool, and addressing the topic pages as paths
relative to the base_url of the recorded environment. Find discrepancies, report them, and fix
them (with user approval).

## Verifiable Artifact

- The path printed by `goga history path -f design.md` — the design document (cross-checked
  against the web cell CODEMANIFESTs in `tests/web/<cell>/` and requirements.md).

## Phases

### Phase 1. Load Context

1. `goga-lang-disp` / `goga-cell-python` — the test language rules.
2. `goga-tool-pybuggy-web-usage`, `goga-tool-pybuggy-web-cookbook` — the web runtime and the
   test cell DSL.
3. Read the design document, every web cell CODEMANIFEST it references, and
   requirements.md (§1 Base URL / Target environment / Browser endpoint, §2 pages, §4 auth).

### Phase 2. Base Verification

Invoke `goga-review-design` via the **Skill tool** — the base findings (design ↔ CODEMANIFEST
consistency). Merge them with the Phase 3 checks.

### Phase 3. Web-Specific Checks

1. **Test mode:** the design describes generating `test_*.py` via the page fixtures
   `page_<name>` (only page fixtures in test signatures); production code,
   Entities, a new `__init__.py` — **Critical**.
2. **Routine ↔ test file:** every Routine of every web cell is mapped in the design document
   as generating `test_<name>.py` bound to its `location` — a mismatch is **Critical**.
3. **Step mechanics:** the design prescribes materializing every item of a `Steps:` annotation
   into exactly one sentence:
    - an action → `page.step("…")`;
    - a check → `page.expect("…")`;
    - a mini-scenario (a set of actions changing the state of the page/widget) →
      `with page.group("<achieved state>"):`;
    - variable captures are stated with their markers: `{% var <name> %}` captures a value in
      a step sentence, `{{ <name> }}` substitutes the captured value into subsequent sentences
      (references from `Data:`) — marker distortion is **High**;
    - sentences are **string literals**: `{{ … }}` / `{{ vars.<name> }}` markers verbatim,
      python values enter only via the `vars={...}` kwarg — prescribing f-strings/format in
      sentences or values in sentence text is **High**;
    - distortion or absence of the mechanics is **High**.
4. **Per-test instructions:** the `Prompt:` annotation section is materialized with
   `@generation_prompt("<bullet>")` decorators (import
   `from goga_tool_pybuggy import generation_prompt`;
   decorator order = bullet order; texts verbatim; routines without `Prompt:` carry no
   decorators) — distortion is **High**; prescribing a different mechanism is **High**.
5. **Generation and cache:** the design fixes:
    - the first test run generates the Playwright code of the sentences via an LLM
      (provider/model from `web.yml`);
    - the cache is written to `tests/web/<cell>/.cache/test_<name>/test_<name>/`:
        - a parameterized case — `…/test_<name>[<param_id>]/`;
        - page method sentences — the shared cache `pages/.cache/<page>/<method>/` (the step binds to the method; the
          activation — `__call__`);
    - the cache is committed to the repository;
    - the first run — **without** `--strict-mode`;
    - the build's repeat run — without it too; accept and CI — with `--strict-mode`;
    - absence or distortion is **High**; prescribing strict on any build run is **Critical**
      (a guaranteed cache-miss without generation).
6. **Validation:** pytest is the verification tool; its absence is **High** (goga build will
   not run the tests). Run commands: when the Browser endpoint is "address from the user"
   (requirements §1) — the suffix `--browser-endpoint <address>`; "from the config" — no
   flag. A violation is **High** (runs will go against the wrong browser).
7. **Environment:**
    - Base URL and the target environment are carried over from requirements §1/§2;
    - the topic pages are addressed as **paths relative to base_url** (external pages — full
      URLs with the "external" label);
    - a path that does not cross-check against the §2 pages, or a foreign origin without the
      label — **High**;
    - an environment change is prescribed as a change of `site.base_url` (+ one non-strict
      run), not of step sentences — anything else is **High**.
8. **Secrets:** the design prescribes no secrets in sentences/prompts; login is described
   behaviorally ("Perform login as the test user `<role>`") — prescribing a secret is
   **Critical**.
9. **Constraints:** cells consist of Routines only; the CODEMANIFEST is a read-only contract;
   the design does not modify annotations — a violation is **High**.
10. **Page methods:**
    - a target sentence referencing ``Use `page-<name>` — method `<method>` `` is materialized
      by a call to `page_<name>.<method>()` — the methods are already written in `pages/**`
      by the pages stage of the testcases pipeline (the contract is the `page-<name>.md`
      usage files);
    - inline steps are not generated for such a sentence (the sentences live in the method;
      the cache is shared across the method);
    - a navigation sentence with a path is materialized by activating `page_<name>()`
      (the URL comes from `site.base_url` at runtime);
    - the method call lands **inside the activation block** the navigation step opened
      (`with page_<name>() as page:`) — the fixture parameter is the page object and the
      activation call is what navigates; a method call prescribed as opening the page or placed
      outside the activation block is **High** (the method's sentences run on whatever page is
      currently open);
    - a full inline URL — external pages and query-string addresses only;
    - prescribing inline steps for a target sentence or for path-based navigation is **High**
      (duplicated generation, loss of the shared page cache, a path without base_url);
    - the absence of these rules when such sentences are present in the CODEMANIFEST is
      **High**.

### Phase 4. Report and Fix Findings (Interactive)

> **Fix scope rule:** edit **only** `goga history path -f design.md`. The web cell CODEMANIFESTs
> are read-only; a design ↔ manifest discrepancy is fixed in the design document (or by
> returning to the testcases stage, if the design is the correct one — decide with the user).
> requirements.md is upstream.

- Collect all findings (base + Phase 3) **before** presenting them; sort them
  **Critical → High → Medium**.
- Show one at a time: Severity / Area (Base / Test-mode / Runtime / Generation-cache /
  Validation / Environment) / Location / Issue / Impact / Suggested fix.
- AskUserQuestion (2–4 options): **Apply suggested fix** / **Propose alternative** / **Skip** —
  with a "Finding 3 of 12" counter.

---

## Output

- Findings summary: fixed / skipped by severity and area
- The updated `goga history path -f design.md` (if edits were applied)
- Verdict: passed / failed

---

## Final Self-Check

Before finishing, verify:

1. Have you read design.md, all web cell CODEMANIFESTs, and requirements.md?
2. Have you invoked `goga-review-design` and merged its findings with the web checks?
3. Have you verified the test mode (`test_*.py`, no production code) and the Routine ↔
   `location` ↔ `test_<name>.py` trace?
4. Have you verified the step mechanics (`page.step`/`page.expect`/`page.group` via the page
   surface, captures), the materialization of `Prompt:` with `@generation_prompt` decorators,
   and the materialization of the target sentence via a page object method call
   (`page_<name>.<method>()` per `Use page-<name>`, without inline steps)?
5. Have you verified the generation and cache policy (first run via LLM without strict, the
   committed cache, the build's repeat run without strict, accept/CI — strict)?
6. Is pytest pinned as the validation tool; do the run commands carry the
   `--browser-endpoint` suffix when the address comes from the user; are the topic pages
   addressed as paths relative to the base_url of the recorded environment?
7. Was each finding shown one at a time with an Apply/Alternative/Skip choice; were the
   edits applied only in design.md?

If at least one answer is "no" — complete the unfinished check before returning.
