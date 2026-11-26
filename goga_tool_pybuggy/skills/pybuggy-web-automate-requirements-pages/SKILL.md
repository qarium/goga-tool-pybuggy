---
name: goga-tool-pybuggy-web-automate-requirements-pages
description: Binds the confirmed topic pages to page objects — derives each page's path against the site base URL, agrees the page names with the user (WAIT), scaffolds the modules via `goga tool pybuggy page generate` (pages/** — a BasePage subclass plus its page_<name> fixture), and produces the page-artifact registry for requirements §2
---

# Pybuggy Web Topic Requirements — Pages

## Identity

You bind the topic's confirmed pages to pybuggy page objects. For each page you:

- derive its path relative to the site base URL;
- agree on the page name with the user;
- generate the module with the command `goga tool pybuggy page generate`;
- record the artifacts.

The artifacts become the addressing for Routine navigation steps (the activation call `page_<name>()`):

- fixture `page_<name>`;
- class `<Name>Page`;
- module `pages/**`.

## Core Principle

- A page object is the only way to navigate to pages of the site under test.
- The base URL lives in the `site.base_url` directive (web.yml); each page adds its own path.
- Derive the path only from the final URLs of the [EXPLORE_REPORT] dossier.
- The page name is the user's decision (the fixture and the class form a contract that Routines and cells reference).
- External pages (a different origin) and addresses with query parameters never become page objects — their navigation
  stays a step proposal carrying the full URL.

---

## Algorithm

### Step 1. Load context

1. [INTAKE_REPORT] — `site.base_url` from web.yml (verbatim, a Jinja2 template).
2. [EXPLORE_REPORT] — PAGE-<N> dossiers: final URLs after redirects.
3. [ELABORATION_REPORT] — the confirmed set of pages (Page Purposes).

### Step 2. Derive the paths

For each confirmed PAGE-<N>, from its final URL:

1. **Origin check**: compare the origin of the final URL (scheme+host+port) with the origin of the site
   base URL. For a `site.base_url` template without placeholders, compare directly; with placeholders,
   compare against the base of the environment the exploration ran in (the origin of the dossier's final
   URLs) and record the correspondence. A different origin means an **external page**: the page object
   does not apply, navigation is literal (the full URL goes into the step proposal).
2. **Path**: the part of the final URL after the origin, with a leading `/`; the query part and the fragment
   (`?…`, `#…`) are stripped (a page is its path part; the query is created by the test's actions). A path
   with no non-empty segment (a root page, `""` after the slash) — the CLI does not generate it
   (`path carries no non-empty segment`): mark the root page as literal (its full URL is the base itself).
3. **Propose a name**: a short `snake_case` name from the page's purpose in the dossier (`login`,
   `catalog`, `checkout`); a single word is the best choice. The name drives the artifact naming:
   fixture `page_<name>`, class `<Name>Page`, module `pages/[<path segments except the
   last>]<name>_page.py` (without a name, the last path segment itself becomes the file stem:
   `/admin/api/v1/mocks` → `pages/admin/api/v1/mocks_page.py`; with name=`auth` for
   `/admin/login` → `pages/admin/auth_page.py`).

### Step 3. WAIT — agree on the names

Show the entire table as text, then AskUserQuestion (one question, 2–4 options):

- **question**: "Page objects: <table>. Approve?"
- **options**: "Approve" / "Edit names" (which — clarify in text) / "Exclude page"
  (literal navigation; which — clarify).

Table: PAGE | path | name | fixture | class | module.

### Step 4. Generate the modules

From the target project root (the directory containing `.goga/`):

1. For each approved row, run `goga tool pybuggy page generate <path> <name>`
   (without `-f`).
2. An existing module is skipped silently — read it:
    - the fixture constructs the class with the same `path`, and the fixture and the class carry
      the expected names → "exists, valid" (the scenario methods inside are preserved — never
      touch them);
    - a mismatch (different path/names) — a warning in the report;
    - overwrite only on the user's explicit decision (`-f` erases the scenario methods).
3. Verify the artifacts on disk: the module file exists, `__init__.py` markers are present along the
   path, and the fixture/class match the table. Fixture loading is automatic: `pages/` is the default
   fixture package of the web kind (the web plugin discovers the modules itself; no `loader:`
   section is needed).

### Step 5. Produce the [PAGES_REPORT]

STOP if:

- `site.base_url` is not set or is empty — return to intake (the directive is mandatory there);
- the CLI `goga tool pybuggy page generate` is unavailable or fails with a validation error;
- the user does not approve the names after edit iterations.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [PAGES_REPORT]

## Site Base URL

[site.base_url from web.yml, verbatim (the template); the origin of the explored environment: <scheme://host[:port]>]

## Page Objects

| PAGE   | Path   | Name  | Fixture    | Class     | Module              | Status                  |
|--------|--------|-------|------------|-----------|---------------------|-------------------------|
| PAGE-1 | /login | login | page_login | LoginPage | pages/login_page.py | created / exists, valid |

[Confirmed page objects. The status is the outcome of the generation step.]

## Literal Navigation

| PAGE / URL | Reason                                      |
|------------|---------------------------------------------|
| https://…  | external origin / query address / root page |

[Pages and addresses without a page object — navigation by the full URL in the step proposal. Write
`none` if there are none.]

## User Decision

[Approved / changed — state exactly what the user confirmed]

## Warnings

[Collisions with existing modules, overwrites, path oddities. Write `none` if nothing.]
```
