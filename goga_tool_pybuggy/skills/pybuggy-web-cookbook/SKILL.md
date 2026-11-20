---
name: goga-tool-pybuggy-web-cookbook
description: Principles for applying the goga-cell DSL to design web test cells
---
# Pybuggy Web Cookbook

## Purpose

This document defines the principles for applying the `goga-cell` DSL to design **web test**
cells. The document adapts `goga-cookbook` and keeps only the parts relevant to web tests: each
test is a `Routine` that carries the base `Usages`/`Annotations` from the project configuration;
test steps are natural-language sentences that materialize through the page fixture surface
(`page.step(...)`/`page.expect(...)`).

Other skills invoke this skill to load the web test cell design context.

## Behavior

The calling skill applies these principles in its own context. It does not restate
`goga-cookbook` in full and does not describe the internals of other skills — it uses these
principles to make design decisions about web test cells.

---

# Principles of web test cell design

## Context

Web tests are a standalone project that uses pybuggy as its framework. A web test cell is a
directory containing a CODEMANIFEST inside the test tree:

```
tests/web/<cell-name>/
└── CODEMANIFEST
```

Cell boundaries are a design decision of the cell-map phase: one cell per page, merging the pages
of a single user flow into one cell, or several cells per page — all variants are acceptable.

Artifact locations:
- materialized tests live alongside (`tests/web/<cell-name>/test_<name>.py`);
- the step cache lives in `tests/web/<cell-name>/.cache/test_<name>/test_<name>/`
  (a parameterized case — `…/test_<name>/test_<name>[<param_id>]/`);
- the sentence cache of page-object methods is shared and lives in `pages/.cache/<page>/`.

## Test cell CODEMANIFEST

### Design order

1. **Header** — the base `Usages` + `Annotations` (the contract operates in the context of the
   project's base practices).
2. **Body** — `Routine`: a test case IS a Routine (do not design a separate case layer); one
   Routine can cover several REQ through parameterization; parameterization is a decision of the
   routines design phase.
3. **Footer** — `Author`, `CreatedAt`, `Description`.

### Header

The cell takes the **base block** of `Usages` and `Annotations` from `.goga/config.yml` (via
`goga-codemanifest-base`); the base block is **identical for all web test cells**:

- `Usages`: `conventions`, `pybuggy-web` (paths under `.goga/usages/`).
- `Annotations`: instructions of the form ``Use `pybuggy-web` for ...``.

On top of the base block, a cell may declare **cell-specific usages** — see the
"Cell-specific usages (tools)" section below.

### Cell-specific usages (tools)

A web test cell that uses a data preparation tool, mock, or utility receives a cell-specific
usage **on top of the base block**:

```yaml
Usages:
  conventions: .goga/usages/conventions.md          # base block — identical in all cells
  pybuggy-web: .goga/usages/cooks/pybuggy/pybuggy-web.md
  faker: .goga/usages/cooks/faker.md                # cell-specific (only where used)
```

- Add a usage key to the Header **only when the file exists** — `.goga/usages/cooks/<key>.md`
  must be on disk before cell design starts.
- Connecting a tool requires two entries: the line `<key>: .goga/usages/cooks/<key>.md` in
  `Usages` plus the line ``Use `<key>` for <data preparation/mocks/utilities>`` in the
  `Annotations` of the affected cell.
  The backtick link `` `<key>` `` resolves immediately: the key is already declared in that
  cell's `Usages`.
- Keep the base block **unchanged**. A cell-specific usage exists only in cells that use the
  tool — its presence in some cells and absence in others is **not** a divergence.
- REQ coverage and Routine granularity remain **unaffected** (usage tools belong to
  Header/Annotations, not to Routine).
- A typical web tool is a usage file with "test credentials / how to log in" (the login mechanism
  and the source of credentials, **without secret values**) or an API-based data preparation
  library.
- The page usage file `page-<name>` is the page-object API (the `page_<name>` fixture, methods):
  - the pages stage of the testcases pipeline creates it when a repeated **parameterless**
    sequence of routine steps (sentences identical verbatim, without
    `{% var %}` / `{{ … }}` markers) is extracted into a page-object method;
  - the affected routine collapses the sequence into a single goal sentence and references the
    method: `` Use `page-login` for closing the cookie banner — the `dismiss_cookie_banner` method ``;
  - connect it in the cell's Header the standard way (key + the line ``Use `<key>` for …``).

### Body — Routine

A web test is a `Routine` (no `methods`/`properties`); a test case IS a Routine; one Routine can
cover several REQ through parameterization:

```yaml
"test_<name>(page_<name>)":
  location: test_<name>.py
  annotations: |
    ...
```

- Signature: `test_<name>(<fixtures>)` — no return value (a test returns nothing); the parameters
  are **page fixtures** `page_<name>` (one — `test_<name>(page_drivers_list)`; several —
  `test_<name>(entry_page, page_drivers_list)`: precondition (entry) pages first, then target
  pages). In the materialized test, `def test_<name>(page_drivers_list):` without a type
  annotation is acceptable — pytest resolves fixtures by name;
  the type annotation is the CODEMANIFEST contract.
- Use `snake_case` naming and `location: test_<name>.py` (the `goga-cell-python` rules).
- Parameterization: when one Routine covers several REQ/variants, list them in the annotation — in
  `Data:` and/or `Steps`; the CODEMANIFEST does not describe the parameterization mechanism (for
  example, `@pytest.mark.parametrize`) — that mechanism appears when test code is generated from
  the Routine. One Routine maps to one `test_<name>.py` (several cases → one file). Declare the
  single variant in `Data:` as well — it declares the values the test sets (the single source for
  steps and checks), not just a multi-variant mechanism.
- The parameterization criterion is linearity: merge into one Routine only REQ variants that
  share the same set of steps and checks — variants differ in values (entered data, expected
  texts), not in which steps and checks run. A different set of steps or checks requires a
  separate Routine: a test materialized from a parameterized Routine is linear, so logical
  constructs in the test body (`if`/`else` and the like) indicate excessive parameterization.

### Footer

- `Author` — always `Goga`.
- `CreatedAt` — day/month/year.
- `Description` — why the cell exists (which pages/flows/topic it tests).

## Routine annotation standard

The Routine annotation must contain enough information to implement the test without
clarification. Web tests use a **strict structure** of ordered sections. The order is fixed:
**Purpose → `Precondition:` → `Data:` → `Prompt:` → `Steps:` → `Use …`**.

A blank line separates the sections: a blank line follows Purpose and precedes each of
`Precondition:` / `Data:` / `Prompt:` / `Steps:` / `Use …`. Two adjacent sections without a blank
line between them violate the structure.

**1. Purpose — no label.** The section states what the Routine checks and why — a behavioral
statement of the requirement in your own words. It is the first paragraph of the annotation.

**2. `Precondition:` — fixtures and preconditions.** A bullet list (`- `): one bullet **per
signature fixture** — a page fixture `` `page_<name>` `` (module `pages/<…>_page.py`, path,
purpose; the document `.goga/tools/pybuggy/web.yml` activates the web runtime) — plus common
preconditions (authorization — behavioral, for example
"logged in as test user `<role>`"; the system state/data BEFORE the test, per the case).
Always wrap the fixture name in backticks.

**3. `Data:` — data created inside the test.** A bullet list of the test's internal data: value
captures from the page (a capture is the `{% var <name> %}` marker inside a step sentence; a
reference to a captured value is `{{ <name> }}` in subsequent sentences) and **values the test
sets itself** — fills in, selects, or produces through preparation: declare them here as a
parameterization variant, **even when there is a single variant**, and let them flow from `Data:`
into steps and checks — a single source (a step enters a value from `Data:`, a check expects the
same value). Values the test does not create do not belong in `Data:`. Omit the section when
there is no such data.

**4. `Prompt:` — per-test extra generation instructions.** A bullet list (`- `) of page quirks
that hinder step generation (a cookie banner overlaying the page, a native `<select>` instead of
a custom dropdown, the DD.MM.YYYY date format) — only facts from the requirements (§2 pages).
These are page oddities only, **not element addressing**: locators, selectors, and testids (CSS,
XPath, data attributes) are forbidden in `Prompt:` — as in every other annotation section; name
the target of an action by its visible name in the step sentence itself (visible names are the
page's stable user contract; locators bind the annotation to the markup). Each bullet
materializes as a `@generation_prompt("<text>")` decorator above the test — import
`from goga_tool_pybuggy import generation_prompt`; decorator order = bullet order; the texts are
verbatim. Omit the section when there are no quirks; secrets in bullets are forbidden (the text
lands in the LLM provider's prompt and in the repository).

**5. `Steps:` — numbered test steps.** Steps come from the test case (Action / Data / Expected).
Each `Steps:` item materializes into **exactly one step sentence**:
an action → `page.step("<sentence>")`, a check → `page.expect("<sentence>")`,
a mini-scenario of several tightly coupled steps → `with page.group("<achieved state>"):`
(through the surface of the activated page). Logic, not code —
express steps in plain language (one action per sentence; name the target and the action),
without pytest/playwright code. A numbered list (`1. `).

Step sentence rules (from `pybuggy-web`):
- one step = one action; the sentence names the target and the action ("Open `https://…`",
  "Fill the “Email” field with the value …", "Click the “Log in” button"); name the target by its
  visible name/text — locators, selectors, and testids are forbidden in sentences;
- express navigation to a page of the site under test as a sentence with a path ("Open the
  `/login` page"); it materializes as activation of the page fixture `page_<name>()` — the
  runtime composes the URL from `site.base_url`; use a full URL in a sentence only for external
  pages and query addresses;
- a group (`page.group`) is a mini-scenario of 2–3 tightly coupled actions that **together change
  the state of the page or widget** (fill and submit a form, log in, drive a dialog to its
  result): the group sentence names the achieved state; the actions inside it carry no individual
  meaning — the group heals next to the earliest affected step; never merge independent actions
  into groups;
- the address of a page under test is a path relative to base_url (`/catalog`, as in §2 of the
  requirements); a full URL is for external pages (foreign origin) and addresses outside the site
  only; switching environments means changing `site.base_url` in web.yml (+ one run without
  `--strict-mode`); step sentences do not change;
- write expectations as separate `page.expect` sentences ("The page displays the text …",
  "The URL became `https://…/orders`"); **exception — transient elements**: a toast/banner that
  appears from an action and disappears on its own within seconds (timing from §2 of the
  requirements) is checked (and read — the `{% var %}` capture) **inside the trigger sentence**:
  "Click the “Save” button — a “Changes saved” toast appears in the top left corner". The LLM
  generates the code of each sentence immediately before that sentence executes: a separate
  expect sentence starts executing only after the LLM round in which the transient has already
  disappeared — the step is doomed (the toast will not reappear without a new trigger); a group
  or a page-object method does not help — the generation unit is the sentence, not the group;
- **an expectation verifies only what the test set**: a value entered/selected/produced by this
  test's steps (declared in `Data:` — even a single variant), captured from the page
  (`{{ <name> }}`), or resulting from a test operation (after "Save" the field carries what the
  test entered; after reload — what the test saved); a bare expectation of a literal the test
  never set or captured (a field's initial state, full names, balances, content not created by
  this test) is forbidden — the environment is shared, other tests or people will change the
  value, and the test will fail without an actual defect; the test establishes the background it
  needs itself (preparation steps/canonicalization);
- capture a value from the page with the `{% var <name> %}` marker inside a step sentence ("Save
  the title of the third video into `{% var video_title %}`"); reference the captured value with
  the `{{ <name> }}` marker in subsequent sentences — steps and checks ("Open the video
  `{{ video_title }}`"); use a capture **only** for values unknown at test-writing time (page
  dynamics: the title of the N-th element, a generated order number) — write static values (URLs,
  entered and expected literals) into sentences without markers;
- **secrets are forbidden in sentences** (everything lands in the LLM provider's prompt and in
  the repository): describe login behaviorally — "Log in as test user `<role>`";
  take secret values from env/usage files and never write them into steps.

**6. `Use …` — only Routine-specific usages.** The section closes the annotation and lists the
usages used **in this Routine** that the header's global `Annotations` do not already cover. The
base practices (`pybuggy-web`, `conventions`) are already linked in the CODEMANIFEST header's
`Annotations` — **do not duplicate** them in the Routine. Only cell-specific tool usages belong
here (for example, ``Use `faker` for test_id generation``). Omit the section when the Routine has
no specific usages. Backtick links must resolve in the CODEMANIFEST context.

**Not used** in tests: `Requirements:`/`Constraints:` (when needed, their content moves from the
case into `Precondition:`/`Data:`); `Algorithm:` is replaced by `Steps:`.

## Step cache and run modes (important for design and acceptance)

- The **first run** of the test creates the cache: the LLM generates Playwright code for each
  sentence and writes the cache files:
  - inline test steps — `tests/web/<cell>/.cache/test_<name>/test_<name>/`;
  - a parameterized case — `…/test_<name>/test_<name>[<param_id>]/`;
  - page-object method steps — in the page's shared cache `pages/.cache/<page>/`.
  Commit the cache to the repository.
- Run the first run **without** `--strict-mode` (strict = 0 LLM calls — a new step fails in
  strict mode). Run repeated runs and CI **with** `--strict-mode` (replay from the cache).
- Never edit the cache by hand; to regenerate a step, delete its cache file and let the next
  non-strict run recreate it.
- The Routine annotation is the source the test is generated from: a marker/decorator or a detail
  that exists only in code is lost at the next regeneration from the Routine — express everything
  significant in the annotation.

Example:

```yaml
"test_search_finds_results(page_catalog)":
  location: test_search_finds_results.py
  annotations: |
    Checks that search on the catalog page finds products by query and shows the results.

    Precondition:
    - `page_catalog`: the catalog page fixture (pages/catalog_page.py, path /catalog;
      the web runtime is activated by the document .goga/tools/pybuggy/web.yml).
    - The catalog is available without authorization.

    Data:
    - Search query: "laptop" — the single variant; entered by step 2, expected by steps 3–4.

    Steps:
    1. Open the catalog page /catalog.
    2. Fill the search field with the value "laptop" and click the "Find" button.
    3. The results page displays at least one product with the text "laptop".
    4. The results page URL is /catalog?q=laptop.

    Use <usages> specific to the Routine
```

Here steps 1–2 materialize as `page.step(...)` (step 1 — activation
`with page_catalog() as page:`), steps 3–4 — as `page.expect(...)`.
