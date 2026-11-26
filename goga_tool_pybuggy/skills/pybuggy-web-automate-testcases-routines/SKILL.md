---
name: goga-tool-pybuggy-web-automate-testcases-routines
description: Routines design — builds complete test Routines directly from the requirements (a test case IS a Routine — name, Purpose, Precondition, Data with parameterization by linearity, optional Prompt for per-test generation instructions (page quirks only — no locators/selectors, addressing is by visible names in step sentences), Steps as step sentences, Use; the REQ coverage registry is session-time, no REQ ids in the manifests); shows each Routine to the user and waits for approval
---

# Pybuggy Web Topic Testcases — Routines

## Identity

You design the topic's routines — complete, in one pass, with no intermediate case layer. Test case = Routine:
each routine carries step sentences (future `page.step(...)`/`page.expect(...)` running through a page fixture).
You show each routine to the user and wait for approval; apply edits when needed.

## Core Principle

- Build a routine only from facts in [TESTCASES_INTAKE] (§2 pages with final URLs, §3 REQ, §4 auth and
  preconditions, §6 integrations) — never invent elements or behavior.
- Locators/selectors/testids (including any left over in the session context from page exploration) never enter
  the annotation: address elements by their visible names in step sentences.
- Parameterization is this phase's decision: variants that share the same set of steps and checks (differing only
  in data) form one parameterized Routine; a different set of steps or checks requires separate Routines.

---

## Algorithm

### Step 1. Load context

1. [TESTCASES_INTAKE] — requirements.md and the base Header block.
2. [TOOLS_REPORT] — the available tools (keys of existing usage files).

### Step 2. Build the routine set

1. **Coverage registry**: every §3 REQ must be covered by at least one routine — record this in the Coverage
   table of this report. Exclude a REQ only with a user decision.
2. **Main behavior** → routines for the main scenarios: start address (path relative to base_url — from §2),
   precondition state (§4: authorization — behavioral), step sentences following the meaning of the requirement
   (one action per sentence), checks as separate expect sentences. A routine that starts on a page with a page
   object (§2 — the `page_<name>` binding) includes it:
   ``Use `page-<name>` `` — the navigation sentence ("Open the `/login` page") materializes as activation of
   `page_<name>()`; the runtime composes the URL from `site.base_url`.
3. **Error behavior** → negative routines — only when error-REQs exist in §3 (negative coverage in UI tests is a
   rare case: if the subsection is empty or the user deliberately excluded it, do not design negative routines
   and do not invent them): error condition → expected page reaction (validation text / empty state / 404).
4. **Parameterization by linearity**: identical steps/checks with different data → one Routine with variants in
   `Data:`; a different set of steps/checks → separate Routines.
5. **Name and location**: `test_<snake_case>` derived from the essence (`test_search_finds_results`); signature —
   the routine's page fixtures `test_<name>(page_<name>)` (for several — `test_<name>(entry_page, page_<name>)`:
   precondition/entry pages first, then target pages); `location: test_<name>.py`.
6. **Annotation** — strict structure (goga-cell / cookbook):
    - Purpose (what the routine checks and why — a behavioral statement of the requirement) →
    - `Precondition:` (one bullet per signature fixture: `` `page_<name>` `` — page fixture with module and path;
        + preconditions) →
    - `Data:` (variable captures; values the test sets itself — fills in/selects/produces through preparation —
      are declared here even with a single variant and flow from `Data:` into steps and checks; parameterization
      variants; omit if empty) →
    - `Prompt:` (per-test extra generation instructions — page quirks from §2 that hinder generation: cookie
      banner, native `<select>`, date format; page oddities only, no element addressing — locators/selectors/
      testids are forbidden in `Prompt:`, name the target by its visible name in the step sentence; one bullet =
      one `@generation_prompt` text; omit if there are no quirks) →
    - `Steps:` (numbered sentences) →
    - `Use …` (keys this routine uses: tools from [TOOLS_REPORT] and the routine pages' `page-<name>` —
      fixture/activation/methods; omit if neither is present).

   Insert a blank line between sections.
7. **Step sentence rules**:
    - one step = one action (name the target and the action);
    - the target is the element's visible name/text (locators, selectors, testids are forbidden in sentences —
      even those known from exploration);
    - the address of a page under test is a path relative to base_url (`/catalog`, from §2); use a full URL only
      for an external page (foreign origin);
    - secrets are forbidden (login — "Log in as test user `<role>`", values come from env/usage file);
    - every check is a separate expect sentence;
        - exception — transient toasts/banners that disappear on their own after N seconds (timing from the §2
          page details): their confirmation and value reading (the `{% var %}` capture) live in the trigger
          sentence itself — a separate expect sentence will not catch them: the sentence's code is generated by
          the LLM before execution, the transient disappears within one LLM round, and a page-object group/method
          does not help — the generation unit is the sentence;
    - an expectation may only check what the test set — a value from `Data:`, a `{{ <name> }}` capture, or the
      result of a test operation; expecting a literal the test never set or captured (a field's initial state,
      content not created by this test) is forbidden: the environment is shared, other tests or people will
      change the value, and the test will fail without an actual defect (the test must establish the background
      it needs itself — preparation steps/canonicalization);
    - capturing a value from the page uses the `{% var <name> %}` marker inside a step sentence ("Save the title
      of the third video into `{% var video_title %}`"); referencing the captured value uses the `{{ <name> }}`
      marker in subsequent sentences, steps, and checks ("Open the video `{{ video_title }}`"); a capture is
      appropriate only for values unknown at test-writing time (page dynamics) — write static values (URL,
      entered and expected literals) into sentences without markers;
    - a mini-scenario of 2–3 tightly coupled steps → one group sentence (`page.group`).
        - Group criterion: the set of actions **changes the state of the page or widget** — fill and submit a
          form, log in, drive a multi-step dialog to its result; the group sentence names the achieved state,
          the individual actions inside the group carry no separate meaning (a failed step is fixed next to the
          earliest affected one — diagnose across the whole group). Never merge independent actions into groups.

### Step 3. WAIT — approval per routine

Each routine follows a "show → decision" cycle, one routine per message. The order inside the message is strict:

1. **Text first**: print the routine in full as plain message text — name, signature, `location`, and the
   complete annotation (all sections). The printed routine is what the user approves; an AskUserQuestion without
   a routine printed before it = blind approval = a pipeline violation.
2. **Then the question**: AskUserQuestion (2–4 options) in the same message, after the routine text. The question
   names the routine ("Routine `test_<name>` — approve?"); do not duplicate the routine's content into the
   question or the options.
3. Never call AskUserQuestion before the routine text, and never hide the routine in thinking, the question
   description, or the options — it must be visible to the user in the message body.

Options:

- "Approve";
- "Edit" — what to change (apply it, print the full routine as text again, and ask again);
- "Reject" — the routine is not needed (return to the coverage registry: cover the REQ with another routine or
  exclude it with a user decision).

### Step 4. Produce the [ROUTINES_REPORT]

STOP if:

- no concrete routine can be designed at all (no facts about the pages);
- the REQ registry cannot be covered and the user does not confirm exclusions;
- the user does not approve a routine after iterations of edits.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [ROUTINES_REPORT]

## Routines

### test_<name> (location: test_<name>.py)

    "test_<name>(page_<name>)":
      location: test_<name>.py
      annotations: |
        [full annotation — Purpose, Precondition, Data, Prompt, Steps, Use]

**User Decision:** approved / edits: <what>

### test_<next_name> (location: test_<next_name>.py)

[…]

## Coverage

| REQ   | Routine(s) |
|-------|------------|
| REQ-1 | test_…     |

[Every §3 REQ is covered (or explicitly excluded with a user decision). The registry is session-time: REQ
identifiers are not stored in the CODEMANIFEST; the assembly stage verifies the registry against §3.]

## Open Questions

[What requires clarification. Write `none` if nothing.]
```
