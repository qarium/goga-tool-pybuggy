---
name: goga-tool-pybuggy-web-automate-requirements-report
description: Assemble the final "Detailed web topic requirements" artifact (the site.base_url directive of web.yml with its render arguments, pages addressed as paths relative to the base URL with their page-object bindings, functional requirements) and save it to the path printed by `goga history path -f requirements.md`
---

# Pybuggy Web Topic Requirements — Report

## Identity

You synthesize the final [TOPIC_SPEC] artifact from the conclusions of all previous steps and save it to a file.

## Constraints

- Include only verified facts — from the [EXPLORE_REPORT] dossier and the user's decision from
  [ELABORATION_REPORT]. Do not invent anything.
- Locators/selectors (CSS, XPath, testid, addressing attributes) are not carried into the artifact:
  the §2 pages and the §3 requirements name elements by their visible names and texts — test steps
  address elements by visible names. The only exception is the login mechanism in §4 Auth
  ("submit `<button/locator>`").
- **There are no secret values in the artifact, and there must be none.**
- Every section of the artifact is filled in; empty sections are forbidden.

## Algorithm

1. Gather the conclusions of all previous steps: [INTAKE_REPORT], [EXPLORE_REPORT], [ELABORATION_REPORT],
   [PAGES_REPORT].
2. Synthesize them into a single [TOPIC_SPEC] artifact.
3. Assign every §3 requirement a stable identifier `REQ-<N>` — the session coverage registry of the
   routines design phase references it. Rules:
    - number sequentially within §3, starting at 1, with no gaps or duplicates;
    - numbering follows the subsection order: "Main behavior" → "Error behavior (contract)" →
      "Acceptance criteria" → "Constraints and boundaries"; omit the "Error behavior (contract)"
      subsection entirely when there are no negative facts (per the elaborate/user decision —
      negative coverage is a rare case in UI tests, its absence is the norm), and continue the
      numbering across the remaining subsections;
    - identifiers are introduced only in §3 — §4 (preconditions) and §5 (roles) stay textual.
4. Assign every §2 page a stable identifier `PAGE-<N>` (in the order of [EXPLORE_REPORT]); routines
   (start addresses) and cell boundaries reference it. Rules:
    - a page's address in §2 is a path relative to the Base URL (`/…`, a topic page) or a full URL
      (an external page); the final URL is the one after redirects; take both from the
      [EXPLORE_REPORT] dossier;
    - carry over the page-object binding (fixture `page_<name>`, class `<Name>Page`, module
      `pages/**`) and the literal navigation from [PAGES_REPORT] (the Page Objects and Literal
      Navigation tables);
    - below the §2 table — a details subsection for every page (carried over from the
      [EXPLORE_REPORT] dossier);
    - the §2 details are the recorded factual base: the requirements review cross-checks REQs
      against it, and re-exploration updates it.
5. Include only verified facts — from the [EXPLORE_REPORT] dossier and the user's decision from
   [ELABORATION_REPORT] (invariants go into the Constraints block).
6. Copy the web runtime facts from [INTAKE_REPORT] into §1 ("Web runtime") and §4 — **verbatim**
   (provider, generation model — the LLM facts of step generation). Downstream pipelines read them
   from there.
7. Copy base_url from [INTAKE_REPORT] (the Base URL sections — the `site.base_url` directive of
   web.yml — and Run Arguments) into §1 ("Base URL") and §4 — verbatim:
    - the value or the Jinja2 template;
    - the render arguments: env `<name=value>` / CLI `--<name>=<value>` with the topic environment's
      values; CLI options require registering `pytest_addoption` in `conftest.py`;
    - the topic environment's address after rendering.

   Web test addressing rule: topic pages are addressed by **paths relative to the Base URL**
   (external pages — by full URLs); switching the environment means switching `site.base_url`
   (+ one run without `--strict-mode` — the navigation steps regenerate), while the page addressing
   stays unchanged.
    - Every recorded run command is `pytest tests/web/<cell>/ -q` (without `--strict-mode` on the
      first run) + the Browser Endpoint suffix (see below), if one is set, + the Base URL render
      arguments (`ENV_NAME=… pytest …` prefix / `--name=value` suffix).
    - Copy the Browser Endpoint decision from [INTAKE_REPORT] into §1 ("Browser endpoint") and §4:
      an address from the user adds the suffix `--browser-endpoint <address>` to every recorded run
      command; "from config" — no suffix.
    - Exploration and runs use the same browser.
    - Also carry over into §1, verbatim, the executed attach command from [EXPLORE_REPORT] (the
      "Re-attach command" section) — the "re-exploration command": the requirements review runs it
      when a fact is unclear, disputed, or concerns the UI and cannot be verified on disk.
8. Copy the topic description from the "Original Request" section of [INTAKE_REPORT] into §1
   verbatim — the testcases stage matches this description against the pages dossier.
9. Copy the authorization mechanism from [INTAKE_REPORT]/[EXPLORE_REPORT] into §4 ("Auth")
   verbatim: the mechanism (none / form `<URL>` fields `<name>` submit `<button>` / SSO), the
   credential source (env `<names>` / the user).
10. Copy the project usages registry into §8: scan `.goga/usages/` of the target project
    (key | path | role | purpose — a reference inventory of the available assets, with no tool
    selection; selection happens at the testcases stage, tools step).
11. Copy the coverage status from [EXPLORE_REPORT]/[INTAKE_REPORT] into §9: which pages existing
    tests `tests/web/**` already cover, which Routines exist, and the action for each —
    reuse / extend / regenerate.
12. Check before saving: every section is filled in (no empty sections); only verified facts,
    nothing invented; elements are named by visible names/texts — no locators/selectors (except the
    submit of the §4 Auth login mechanism); no secret values.
13. Save [TOPIC_SPEC] to the path printed by `goga history path -f requirements.md`
    (overwrite the file on repeated runs).

---

## Output Format

Save the result to the path printed by `goga history path -f requirements.md`. The file content
follows the format below. Fill in every section.

```md
### Detailed web topic requirements: [Topic name]

**1. Context and goal:**

- **Service:** [A brief description of the site/service]
- **Topic description (verbatim):** [The user's original request — from the intake "Original Request"]
- **Topic goal:** [The refined goal]
- **Web runtime:** [Verbatim from .goga/tools/pybuggy/web.yml: provider, generation_model —
  the LLM facts of step generation]
- **Browser endpoint:** ["from config" (`browser.endpoint: <value>`) | `<ws(s)://… | http(s)://…>`
  from the user; run command suffix: no flag | `--browser-endpoint <address>` — the browser
  address for exploration and runs, not the site under test]
- **Re-exploration command:** [the verbatim attach command from the exploration dossier —
  the requirements review runs it to reopen pages when facts are unclear/disputed or UI remarks
  arise]
- **Base URL:** [`site.base_url` of web.yml, verbatim: `<value/template>`; render arguments:
  not needed | env `<name=value>` (run command prefix) | CLI `--<name>=<value>` (run command
  suffix; requires registering `pytest_addoption` in conftest.py) — the source of the tested
  site's address; rendered at run start, an unknown variable fails the run; the topic
  environment's address after rendering: `<full URL>`]
- **Target environment:** [The topic environment: prod/stage/feature deploy; the environment
  address is the rendered Base URL. Addressing rule: topic pages — paths relative to the Base URL,
  external pages — full URLs; switching the environment means switching `site.base_url` (+ one run
  without `--strict-mode`), the page addressing stays unchanged; recorded run commands —
  `pytest tests/web/<cell>/ -q` (first run without `--strict-mode`) + the Browser endpoint suffix +
  the Base URL render arguments]

**2. Topic pages:**

| PAGE | Address (path `/…` | full URL) | Final URL | Title | Purpose | Page object | Role in the topic |
|------|--------------------------------|--------------|-------|------------|-------------|---------------|
| PAGE-1 | /catalog | https://…/catalog | […] | […] | page_catalog | […] |

[A full URL in the "Address" column — external pages only (a foreign origin), marked "external" in
"Role in the topic"; internal pages — paths relative to the Base URL. The "Page object" column —
the fixture `page_<name>` from [PAGES_REPORT] (class `<Name>Page`, module `pages/**`) or
"literal" — navigation by full URL in a step sentence (foreign origin / query address / root
page).]

Page details (carried over from the [EXPLORE_REPORT] dossier — the recorded factual base for
review and re-exploration):

**PAGE-1 — details**

- Page object: fixture `page_<name>`, class `<Name>Page`, module `pages/<…>_page.py` | literal
  navigation (full URL in a step sentence)
- Key elements (a textual description of the elements, for example: the red button in the top-left
  corner...): […]
- Forms and validations: […] — verbatim validation texts
- Observable states: empty / error / loading / toast banners (verbatim text, the appearance event,
  disappear after N s) — what it looks like, verbatim texts
- API endpoints: [method + path]
- Technical specifics: [pop-up, cookie banner, redirects — or `none`]

**PAGE-2 — details**

[…]

Note: the step cache of the materialized tests lives in
`tests/web/<cell>/.cache/test_<name>/test_<name>/` (a parameterized case —
`…/test_<name>[<param_id>]/`; page-method sentences — the shared cache `pages/.cache/<page>/<method>/`) and
is committed to the repository. Page elements are described by visible names/texts — locators,
selectors, and testid never get into the artifact (except the §4 Auth login mechanism).

**3. Functional requirements:**

Every requirement carries a stable identifier `REQ-<N>` (sequential numbering within §3 in the
subsection order, with no gaps or duplicates) — the registry for Routine traceability.

- **Main behavior:**
    - `REQ-1` — [Scenario/rule: condition → expected page behavior]
- **Error behavior (contract):** [optional — only observed/user-named errors; no negative facts —
  the subsection is omitted entirely]
    - `REQ-<N>` — [Error condition → expected reaction: validation text / empty state / 404]
- **Acceptance criteria:**
    - `REQ-<N>` — [Criterion]
- **Constraints and boundaries:**
    - `REQ-<N>` — [What the topic does not do]

**4. Preconditions and environment:**

- Business preconditions (data/states — as a need): [...]
- **Auth:** [mechanism: no authorization | form `<URL>`, fields `<name>`, submit `<button/locator>`
  | SSO; credential source: env `<names>` / the user. NO secret values]
- Base URL: [repeat of item §1 — the value/template from web.yml, the render arguments, the topic
  environment's address after rendering]
- Target environment: [the topic environment — repeat of item §1]
- Web runtime: [verbatim from web.yml — repeat of item §1]
- Browser endpoint: [repeat of item §1 — "from config" | address + the `--browser-endpoint
  <address>` suffix]

**5. Roles and permissions:**

[Who can / cannot perform the scenarios (roles, authorization statuses)]

**6. Integration aspects:**

- [Pages' API endpoints (method + path), external scripts/widgets, cookie banners, pop-ups]

**7. Links and resources:**

- [Documentation, mockups, links — if any]

**8. Available project usages:**

| key     | path             | role                                              | purpose                     |
|---------|------------------|---------------------------------------------------|-----------------------------|
| `<key>` | [.goga/usages/…] | [runtime reference / data-mocks-utilities / other] | [subject area — a phrase] |

The registry is the result of scanning `.goga/usages/` of the target project. It is a **reference
inventory of the available assets**, not a tool selection: the test needs are reconciled with the
tools (existing or new) at the testcases stage — the usage files of new libraries
(`.goga/usages/cooks/<key>.md`) are created there as well. If `.goga/usages/` is empty — write
"no usages".

**9. Already covered by tests:**

[A table: page/flow | status (not covered / partial / full) | existing Routines in `tests/web/**`
(name → Flow/Positive/Negative) | action (reuse / extend — filling the gaps / regenerate)]. The
section is **optional**: if nothing is covered — write "no coverage".
```
