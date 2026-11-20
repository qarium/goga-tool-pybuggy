---
name: goga-tool-pybuggy-web-automate-testcases-pages
description: Page-method extraction from the approved Routines — detects repeated parameter-free step sequences per page object (verbatim-identical sentences, no var markers, no varying literals), agrees the methods with the user (WAIT), writes them into the page modules pages/**, documents each page's API in .goga/usages/cooks/page-<name>.md, and updates the affected Routines (the sequence collapses to one goal sentence plus a Use page-<name> reference) so assembly wires the page usages into the CODEMANIFEST headers through the standard goga mechanism
---

# Pybuggy Web Topic Testcases — Pages

## Identity

You process the topic's pages against the designed Routines: find common steps worthy of
page-object methods, agree on them with the user, append the methods to the `pages/**`
modules, document each page's API in a usage file, and rewrite the affected Routines so
that the repeated sequence becomes a single goal sentence with a reference to the method.

## Core Principle

A page-object method is a page's reusable sentences: steps written once are shared by all
tests of that page (shared page cache — the first test generates it, the remaining tests
replay it without an LLM). A sequence qualifies as a method candidate only if it is
**non-parameterized**: the sentences are identical verbatim across all occurrences, with no
markers `{% var <name> %}` / `{{ <name> }}` and no literals that change between occurrences.
Any difference in the data means it is not a method: parameters are forbidden in page
methods (a method's sentences are phrased against the live DOM, not against the data of
the moment).

Forbidden in page methods:

- secrets — never;
- locators/selectors/testid — never (visible names).

---

## Algorithm

### Step 1. Load context

1. [ROUTINES_REPORT] — approved Routines (full annotations, `Steps:` sentences).
2. [TESTCASES_INTAKE] — requirements §2: pages, page-object bindings (the `page_<name>`
   fixture, the `<Name>Page` class, the `pages/**` module; "literal" navigation) and page
   details (banners, states — context for describing methods).
3. The `pages/**` modules on disk — existing page methods (reuse, not duplicates).
4. [TOOLS_REPORT] — occupied usage keys (the new `page-<name>` keys do not conflict).
5. Via the **Skill tool**: `goga-tool-pybuggy-web-usage` (page-method mechanics — the shared
   cache, wording against the live DOM), `goga-tool-pybuggy-web-cookbook`.

### Step 2. Detect the candidates

For each topic page **with a page object** (skip literal-navigation Routines):

1. Collect occurrences: sequences of 1–3 adjacent `Steps:` sentences from the page's
   Routines, bound to the page's behavior (not to the data of a specific test).
2. A candidate is a sequence that repeats:
   - in ≥ 2 Routines of the page, **or**
   - in **all** Routines that start on the page (the typical case: a banner that appears on
     every open — the steps that dismiss it).
3. **No-parameterization criterion (strict)**: all occurrences are verbatim-identical; none
   contains markers `{% var %}` / `{{ … }}`; the literals (visible button texts, entered
   values) do not differ between occurrences. A difference in even one data fragment
   discards the candidate — the steps stay in the Routines as is.
4. Check against the module's existing methods: a method with the same sentences already
   exists — the candidate becomes "reuse" (no new method is written); existing methods are
   never modified or deleted (their sentences may already be in the page cache).
5. Propose a name: `snake_case`, verb first, derived from the target state
   (`dismiss_cookie_banner`, `submit_login_form`).

### Step 3. WAIT — methods and Routine edits

1. Show the full candidates table as text: page (fixture) | method | sentences verbatim |
   Routines | status (new / reuse).
2. For each affected Routine — a "was → became" comparison: sequence → goal sentence + a
   `Use` line.
3. AskUserQuestion (one question per message, 2–4 options): "Approve" / "Edit" (state in
   text what to change) / "Reject" (the steps stay in the Routines as is).

### Step 4. Materialize

1. **Methods**: append the approved methods to the `pages/<…>_page.py` modules — the method
   body carries the sentences verbatim through the page surface (`self.step` /
   `self.expect`; a tightly coupled mini-scenario — `with self.group("<target state>"):`).
   Existing methods and the class activation semantics stay unchanged.
2. **Usage files**: create `.goga/usages/cooks/page-<name>.md` (only non-existing files;
   `<name>` — the page name from §2, kebab-case):
   - heading `# page-<name> — <page purpose in the topic>`;
   - sections: **Domain** (the page, its path, the `page_<name>` fixture, what the page
     does), **Enable** (wiring — the key into the cell's Header via the standard goga
     mechanism), **Usage** (methods: name → what it does behaviorally, in visible names;
     when to call), **Examples** (2–3 call fragments from a test/Routine);
   - locators/selectors/testid and secrets — forbidden;
   - write for an agent without topic context: a domain reference of the page and its API —
     fixture, path, methods (name → target state + sentences verbatim), when to call; topic
     identifiers (`REQ-<N>`, case/ticket numbers, links to artifact sections) never appear
     in the file — the coverage registry is session-scoped.
3. **Routines**: in the affected Routines, replace the repeated sequence with a single goal
   sentence ("Close the cookie banner") and add/extend the `Use …` section:
   ``Use `page-<name>` for <goal sentence> — method `<method>` ``. Apply only the edits
   approved in Step 3; keep the rest of the Routine content unchanged.
4. Update [ROUTINES_REPORT] (affected Routines only) — cell-map and assembly read it.

### Step 5. Produce the [PAGE_METHODS_REPORT]

STOP if:

- the `pages/<…>_page.py` module is missing on disk although §2 confirms the binding —
  return to the requirements pipeline (the pages stage);
- the user does not approve the methods after edit iterations.

No candidates found / all pages are literal — **not a STOP**: produce the report with
`none` sections and leave [ROUTINES_REPORT] unchanged.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [PAGE_METHODS_REPORT]

## Page Methods

| Page | Method | Sentences (verbatim) | Routines | Status |
|----------|-------|------------------------|--------|--------|
| PAGE-1 (page_login) | dismiss_cookie_banner | […] | test_…, test_… | created / reused |

[Approved methods. Write `none` if no candidates were found.]

## Usage Files

| key | path |
|-----|------|
| `page-login` | .goga/usages/cooks/page-login.md |

[Created usage files. Write `none` if none.]

## Routine Updates

| Routine | Was (sequence) | Became (goal sentence + Use) |
|---------|---------------------------|--------------------------------|
| test_… | […] | "Close the cookie banner" + ``Use `page-login` …`` |

[Affected Routines. Write `none` if the Routines did not change.]

## Reused Existing Methods

[Methods reused without writing new ones. Write `none` if none.]

## User Decision

[Approved / changed — what exactly the user confirmed]

## Warnings

[Rejected candidates (reason: parameterization / single occurrence), key conflicts.
Write `none` if none.]
```
