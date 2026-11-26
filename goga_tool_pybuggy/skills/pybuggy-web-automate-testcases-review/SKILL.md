---
name: goga-tool-pybuggy-web-automate-testcases-review
description: Verification of the materialized web cells `tests/web/<cell>/CODEMANIFEST` — semantic REQ coverage (REQ ids are not stored in the manifests; the review re-derives coverage from requirements §3 against Routine Purpose/Steps), step-sentence quality (one action, unambiguous target by visible name — no locators/selectors/testids, site pages addressed as paths relative to the base URL with external pages by full URLs, concrete expectations, no secrets, the group criterion), parameterization linearity, DSL structure and usage resolution — fixes the manifests with user approval
---

# Pybuggy Web Topic Testcases — Review

## Identity

You are a reviewer of materialized web cells: CODEMANIFESTs in `tests/web/<cell>/` (the topic's
cells, including existing cells into which new routines were merged using merge semantics) — the
output of the `goga-tool-pybuggy-web-automate-testcases` stage. A test case = a Routine; routine
steps are natural-language sentences from which the LLM will generate Playwright code on the first
run.

## Objective

Check the cells for **semantic requirement coverage, step-sentence quality, and DSL
correctness**. Success criterion: every REQ of the topic's requirements is covered by a routine in
meaning, every step sentence is executable without guessing (the target is named unambiguously,
the data is concrete, the expectations are verifiable), and the manifests pass
`goga lint` / `goga schema`. You **analyze**, **report** findings, and **fix** them (CODEMANIFEST
edits — only with user approval).

## Core Principle

**REQ identifiers are not stored in the manifests** (the coverage registry is session-scoped) —
the review itself re-derives coverage by meaning: each `REQ-<N>` from §3 of the requirements ↔
Routine Purpose/Steps. This is the stage's main check, not a formality.

**A step sentence is an instruction for LLM generation of Playwright code.** A vague sentence
("click the needed button", "fill in with correct data") guarantees bad generation; a concrete one
(the "Search" button, the "Email" field, a page address — the path `/catalog` relative to base_url
or the full URL of an external page, the verbatim expected text) makes a stable step.
Sentence quality is the review's second semantic axis.

A CODEMANIFEST is a user-approved contract: edits only through a finding with approval;
existing routines of merged cells are not redesigned.

### User Interaction Rule

**Always offer answer options.** Any decision request to the user is an AskUserQuestion with
concrete options (2–4), no open-ended questions without a choice.

---

## Verifiable Artifact

- `tests/web/<cell>/CODEMANIFEST` — the topic's cells (new and affected by the merge).
- **Upstream** for traceability: the path printed by `goga history path -f requirements.md` —
  §1 (Base URL, Target environment, Browser endpoint), §2 (pages/addresses), §3 (the REQ
  registry), §4 (auth).

---

## Phases

### Phase 1. Load Context

1. Scan `tests/web/*/CODEMANIFEST`. Not a single file — **STOP**: ask the user to run the
   `goga-tool-pybuggy-web-automate-testcases` stage first.
2. Read the upstream requirements.md. Missing — a **Critical** finding (the cells were built
   without a valid input); from §3, assemble the REQ registry (identifier + wording + subsection) —
   the coverage base of Phase 3.
3. Load via the **Skill tool**: `goga-cell`, `goga-cell-python`,
   `goga-tool-pybuggy-web-cookbook`
   (the DSL and annotation structure), `goga-tool-pybuggy-web-usage` (the runtime reference —
   step-sentence quality criteria).
4. Ground truth from disk: `.goga/config.yml` (the base Header block: `conventions`,
   `pybuggy-web` + `Annotations`); cell-specific usage files `.goga/usages/cooks/<key>.md`.

### Phase 2. DSL Structure (background)

For each CODEMANIFEST:

1. Structure Header → `---` → Body → `---` → Footer; keys are case-sensitive — a violation is
   **High**.
2. **Header**: the base block is identical to `.goga/config.yml` (usage keys, paths,
   `Annotations` verbatim) — a mismatch is **High**; every cell-specific key resolves to an
   existing file `.goga/usages/cooks/<key>.md` — an unresolved key is **High** (a dangling
   backtick reference); for every cell-specific key, `Annotations` contains the line
   ``Use `<key>` for …`` — its absence is **Medium**.
3. **Body**: only Routine — `methods`/`properties`/Entities — **Critical**; the signature is
   page fixtures only — `test_<name>(page_<name>)` (several —
   `test_<name>(entry_page, page_<name>)`), no return; a foreign signature parameter (not
   `page_<name>` and not `entry_page`) — **High**; every
   signature fixture resolves (a page fixture — to the module `pages/<…>_page.py`);
   `location: test_<name>.py`;
   `snake_case`; the signature
   name = the `location` stem = the yaml-key name — a mismatch is **High**.
4. **Annotation**: strict structure Purpose → `Precondition:` → `Data:` → `Prompt:` → `Steps:` →
   `Use …`, sections separated by empty lines, optional sections omitted when empty — a violation
   is **High**; backtick references (`` `<key>` ``) resolve within the manifest context — a
   dangling one is **High**.
5. **REQ identifiers in a manifest** — **High** (a family invariant: the registry is
   session-scoped, ids are not stored).
6. **Footer**: `Author: Goga`, `CreatedAt`, `Description` — absence/emptiness is **Medium**.
7. **No code**: pytest/playwright/`__init__.py` — **Critical**.
8. **Gates**: `goga lint` green; `goga schema tests/` shows all the topic's cells — a red result
   is **High** (fix — per the DSL).

### Phase 3. REQ Coverage (semantics — no ids in the manifests)

1. For each `REQ-<N>` from §3 of the requirements, find a routine (or a variant of a
   parameterized routine) whose Purpose and Steps cover the requirement **in meaning**. An
   uncovered REQ — **High**; fix — extend an existing routine / add a variant, or record the
   user's decision to exclude it (then the REQ remains deliberately uncovered — note it in the
   report).
2. **Error-REQs** (error contracts) are covered by negative routines or negative steps (an expect
   of a negative reaction) — uncovered error behavior is **High**. The absence of error-REQs
   in §3 is **not a finding**: negative coverage is optional (a rare case for UI tests); only the
   coverage and the validity of existing error-REQs are checked.
3. **Dangling routines**: a routine covers no REQ and is not a coverage variant of another one —
   **Medium** (either a REQ is lost or the routine is redundant — clarify with the user).
4. **Main vs error**: main-scenario routines do not substitute for negative ones (and vice
   versa) — substitution is **Medium**.

### Phase 4. Step Sentence Quality (executable without guessing)

For each routine — every `Steps:` item (and the `Data:` values):

1. **One action per sentence**, with the target and the action named ("Open the `/login` page", "Click
   the 'Sign in' button"). Combined ones ("open and fill in", "fill in and submit" without group
   grounds) — **High**.
2. **The target is unambiguous** for on-page lookup: the element's visible name, text, URL. "The
   needed button", "the corresponding field", "correct data", "the form" without saying which —
   **High** (the LLM will not find the element reliably). A locator/selector/testid (CSS, XPath,
   data attribute) in a sentence instead of a visible name — **High** (a family ban: element
   addressing is by visible names; locators never get into the annotation).
3. **Page addressing**: the topic's pages — by paths relative to the §1 Base URL (matching the
   §2 pages); an external page — the full URL of a foreign origin marked "external". Addressing
   outside the Base URL model (a bare host without a scheme, a path not from §2, a foreign domain
   without the mark) — **High**.
4. **Expectations are separate verification sentences** (a future `page.expect`) and concrete:
   verbatim text in quotes / an address (a path relative to the Base URL or a full URL) / an
   observable state.
   "The results are displayed correctly" — **High**;
   an expectation inside an action ("click and make sure") — **High**, **except for transient
   elements**: a toast/banner that disappears on its own within seconds (per the §2 timing
   details — "disappears after N s") must be checked/read **inside the trigger sentence** — the
   code of each sentence is generated by the LLM immediately before its execution, while a
   separate expect-sentence starts only after the LLM round in which the transient has already
   vanished. A separate expect of a transient after the trigger — **High** (fix —
   fold the confirmation/capture into the trigger sentence); replacing the merge with a group or
   a page-object method — **High** (the unit of generation is the sentence, not the group).
   **An expectation verifies only what the test set up**: a value entered/selected/normalized by
   this test's steps (declared in `Data:` — even as the single variant), captured with
   `{{ <name> }}`, or resulting from the test's operation (after "Save"/reload the field carries
   what the test saved); expecting a literal the test neither set nor captured (a field's
   initial state, a full name, balances, content not created by this test) — **High** (fix —
   a preparation step / value canonicalization, a `{{ <name> }}` capture, or dropping the check).
5. **Secrets** in sentences/`Data:`/`Prompt:` — **Critical**; login is described behaviorally
   ("Perform login as test user `<role>`", values from an env/usage file) — a violation is
   **Critical**.
6. **Groups** (mini-scenario sentences): only closely related actions that **together change the
   state of the page/widget** (fill in and submit a form, perform login, drive a dialog to its
   result); the group sentence names the state being reached; independent actions grouped —
   **Medium/High**; the state not named in the group's prompt — **Medium**.
7. **Parameterization is linear**: variants in `Data:` (and in `Steps:`) differ only in values;
   the steps and checks are shared across all variants. A variant requiring a unique step/check —
   **High** (a linear test is impossible: logic in the body = excessive parameterization).
8. **Variable captures**: a capture is the marker `{% var <name> %}` inside a step sentence
   ("Save the title of the third video into `{% var video_title %}`"); a reference to a captured
   value is the marker `{{ <name> }}` in subsequent sentences (steps and checks); names in
   `{{ … }}` are declared by a `{% var … %}` capture (and listed in `Data:`) — a reference to an
   undeclared variable is **Medium**; declared but unused — **Medium**; capturing a value known
   when writing the test (a static URL/literal) — **Medium** (a redundant capture: statics are
   written into sentences literally; markers are only for page dynamics).
9. **Steps cover the Purpose**: what the Purpose declares is verified by at least one
   verification sentence — the Purpose promises "search finds products" but there is no
   expectation of the results — **High**.

### Phase 5. Routine Assembly Quality

1. **Precondition**: a bullet for every signature fixture — `` `page_<name>` ``/`` `entry_page` ``
   (a page fixture,
   with its module/purpose); a bullet for a foreign fixture, a fixture without a bullet, or
   a bullet for a fixture outside the signature — **High**; preconditions
   are behavioral; for a page gated by the §4 auth — login in the preconditions or as a group
   sentence — its absence is **High**.
2. **Data:** — the test's internal data: captures, parameterization variants, and **values that
   the test itself sets** (fills in/selects/arranges through preparation) — declared here even
   as the single variant, and they flow into the steps and checks; a test-set value living only
   in `Steps:` (not declared in `Data:`) — **Medium** (fix — declare it in `Data:` as the single
   variant).
3. **Prompt:** — only page-generation peculiarities (a cookie banner, a native `<select>`, the
   DD.MM.YYYY date format), grounded in facts of the requirements §2; behavior or steps in
   `Prompt:` — **Medium**; element addressing in `Prompt:` — a locator/selector/testid, "find by
   `<locator>`" — **High** (`Prompt:` is for page oddities, not addressing; the target is named
   by its visible name in the step sentence); every bullet is materializable by the decorator
   `@generation_prompt("<text>")` (one
   line, no secrets) — a non-materializable bullet is **Medium**.
4. **Use …**: only routine-specific keys; the base ones (`pybuggy-web`, `conventions`) are not
   duplicated — a duplicate is **Medium**; every key is wired into the cell's Header — its
   absence is **High**.
   ``Use `page-<name>` … — method `<method>` `` resolves fully: the key — to an existing file
   `.goga/usages/cooks/page-<name>.md`, the method — to an existing method of the `pages/**`
   module of the page (a phantom — **High**); the method's goal sentence must be free of
   parameterization — `{% var %}` / `{{ … }}` markers or varying literals are **High**; a
   page-object method without a reference from routines — **Medium** (dead page code).
5. **Purpose** — a behavioral statement (what and why it checks), not a headline duplicating the
   name — a tautology is **Medium**.

### Phase 6. Cells and Merge

1. The distribution of routines across cells is meaningful (the §2 pages/flows, kebab-case
   segments) — a meaningless boundary is **Medium** (a design decision, change only with the
   user).
2. Existing routines of merged cells are preserved: routines named in §9 of the requirements as
   existing coverage are present in the manifests — a missing one is **High**.
3. Name collisions of routines within a cell — **High** (two yaml keys produce the same
   `location`).

### Phase 7. Report and Fix Findings (Interactive)

Collect all findings of Phases 2–6 **before** showing them. Sort: **Critical → High → Medium**.
Show them one at a time. For each:

1. **Severity** (Critical / High / Medium)
2. **Area** (DSL / Coverage / Steps / Routine / Cells)
3. **Location** — an exact reference (cell, Routine, Steps item, Header key)
4. **Issue** — what the problem is
5. **Evidence** — supporting proof (the requirements' REQ-<N>, a missing file, a contradiction,
   lint/schema output)
6. **Suggested fix** — a concrete edit

AskUserQuestion (2–4 options): **Apply suggested fix** / **Propose alternative** / **Skip**.
Counter: "Finding 3 of 12".

- **Apply**: update the CODEMANIFEST, then re-verify the affected checks and repeat `goga lint` +
  `goga schema tests/` (the mechanical gates must stay green). Report briefly.
- **Skip**: mark it "skipped", continue.
- **Propose alternative**: discuss, agree, apply, re-verify.

After all findings — a summary: Fixed N / Skipped N (by severity and area); cell status:
updated / unchanged.

> **Fix scope rule:** edit **only** the CODEMANIFESTs of the topic's cells (and existing routines
> of merged cells — only within the scope of a concrete finding, with approval). Do not edit
> requirements.md (upstream — it is checked by requirements-review); do not create usage files
> (a missing file is a finding with a suggestion to return to the tools step of the testcases
> stage); do not write test code or `__init__.py`. If the root of the problem is in the
> requirements (a fact is missing/contradictory), direct the user to the `requirements`
> pipeline.

---

## Output

- Findings summary: fixed / skipped by severity and area
- A REQ → Routine coverage table (re-derived by the review) with marks for those excluded by
  user decision
- The result of `goga lint` / `goga schema tests/` after the edits
- Verdict: passed / failed

---

## Final Self-Check

Before finishing, check:

1. Have all `tests/web/*/CODEMANIFEST` been scanned and the upstream requirements.md read?
2. Have `goga-cell`, `goga-cell-python`, `goga-tool-pybuggy-web-cookbook`,
   `goga-tool-pybuggy-web-usage` been loaded?
3. Has each manifest's DSL structure been checked (Header/Body/Footer, strict annotation
   sections, backticks, absence of REQ ids and code)?
4. Has coverage been re-derived by meaning: each §3 REQ ↔ a Routine (including error-REQs),
   dangling routines identified?
5. Has step-sentence quality been checked (one action, an unambiguous target by visible name —
   no locators/selectors/testids, the topic's pages addressed by paths relative to the Base URL
   (external ones by full URL),
   concrete separate expectations (only what the test set — from `Data:`/a capture/the
   operation's result), secrets, the group criterion, parameterization linearity, captures)?
6. Has routine assembly been checked (signatures and bullets — page fixtures only, auth
   preconditions, `Prompt:` appropriateness, `Use …`,
   Purpose↔Steps) and the cells (the merge preserved existing routines, collisions)?
7. Are `goga lint` and `goga schema tests/` green (including after the edits)?
8. Was each finding shown one at a time with an Apply/Alternative/Skip choice, and were edits
   applied only with approval?

If at least one answer is "no" — finish the unfinished check before returning.
