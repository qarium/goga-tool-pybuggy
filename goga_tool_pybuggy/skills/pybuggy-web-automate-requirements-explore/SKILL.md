---
name: goga-tool-pybuggy-web-automate-requirements-explore
description: Live page exploration via playwright-cli — attaches to the browser from Browser Endpoint ([INTAKE_REPORT]) in a named session, resolves the topic environment's base URL (rendering the Jinja2 template with the recorded run arguments when needed) and composes full target URLs from the base URL and the page paths, builds per-page dossiers (page addresses — paths relative to the base URL plus final URLs after redirects, key elements with visible names, forms and validations, navigation map, observable states, console/network findings including API endpoints; no locators/selectors — test addressing is by visible names), handles auth without recording secrets, and produces [EXPLORE_REPORT]
---

# Pybuggy Web Topic Requirements — Explore

## Identity

You are a page explorer. You open the target pages of the live site via playwright-cli and collect
a factual dossier for each page:

- page address (path relative to base_url / full URL for an external one);
- final URL after redirects;
- purpose;
- key elements with visible names;
- forms with validations;
- navigation map;
- observable states;
- console and network errors (including the page's API endpoints).

The dossier is the only source of facts about the pages for all subsequent steps.

---

## playwright-cli command dictionary

This skill is self-contained: the minimal set of commands used is embedded below. If the
`playwright-cli` skill is available in the environment, load it via the Skill tool for the full
reference.

- `PLAYWRIGHT_MCP_OUTPUT_DIR=<dir> playwright-cli -s=pybuggy-explore attach --cdp=<url>` —
  attach to an already running browser at the address from Browser Endpoint ([INTAKE_REPORT]);
  `ws(s)://` — the `--endpoint=` flag instead of `--cdp=`;
- `playwright-cli -s=pybuggy-explore goto <url>` — navigation; prints the final URL and the page title;
- `playwright-cli -s=pybuggy-explore snapshot [--depth=N] [ref]` — accessibility snapshot with refs `e<N>`
  (the snapshot is printed automatically after every command);
- `playwright-cli -s=pybuggy-explore find "text"` / `find --regex "/…/i"` — search over the snapshot (like grep -C);
- `playwright-cli -s=pybuggy-explore --raw eval "<js>" [ref]` — evaluate JS in the page (no status
  and snapshot in the output);
- `playwright-cli -s=pybuggy-explore click e<N> | fill e<N> "text" | press Enter | select e<N> "val" | check e<N>` — interactions;
- `playwright-cli -s=pybuggy-explore console` — console messages; `requests` — the page's network requests;
- `playwright-cli -s=pybuggy-explore go-back` — back; `reload` — reload;
- `playwright-cli -s=pybuggy-explore tab-list | tab-select 0` — tabs (keep one);
- `playwright-cli -s=pybuggy-explore state-save auth.json` / `state-load auth.json` — save/load
  the authorization state;
- `playwright-cli -s=pybuggy-explore detach` — disconnect from the attached browser without closing it;
- `playwright-cli list` — list of open sessions.

---

## Core Principle

- **Facts come only from live pages.**
- Everything written in [EXPLORE_REPORT] has been observed by you in the browser session; user statements
  live in [INTAKE_REPORT] and are compared with the observations at the elaborate stage — here they are
  not "corrected".
- Secrets are never written into the report.

## Session Strategy

- One named session for the entire exploration: an `attach` connection at the address from Browser Endpoint
  ([INTAKE_REPORT]) — the browser is always external, local binaries are not needed.
- One tab: record a pop-up/new window via `tab-list` under "Technical findings" and return with `tab-select 0`.
- Hygiene: at the end of the work — and on any STOP — run `detach` (it does not close the user's
  browser).
  On a session crash, restart (`detach`, then `attach` + `state-load auth.json` if authorization
  was performed); after 2 unsuccessful restarts — **STOP**.

## Budget

Time and context limits (exhausting the budget is NOT a STOP: whatever is left uncovered goes into
"Not explored"):

- **Target pages — always all of them**: build a full dossier for each; they are never limited by
  the budget.
- **Adjacent URLs**: no more than `max(8, 4 × <number of target pages>)` unique URLs beyond the targets —
  following key links, auth pages, redirect chains.
- **Crawl depth**: no more than 2 hops from each target page.
- **Interactions per page**: no more than 5 (clicks/submits); forms — no more than 3.
- **Snapshots**: start with `--depth=4`; detail (`snapshot e<N>` or `--depth=8`) — only for key
  widgets; explore large outputs with `find`, not by reading them whole.
- **eval extractions**: truncate lists with `.slice(0,50)`, strings — `.slice(0,120)`.

---

## Pre-flight

### Step 0. Checks before exploration

1. **CLI availability**: run `playwright-cli --version`. If unavailable — **STOP** (the CLI is installed at
   `goga install`).
2. **Browser endpoint**: the Browser Endpoint section from [INTAKE_REPORT] must contain an address
   ("from the config" or from the user) — the exploration **connects to it** via `attach`
   (bootstrap — item 5 below). If the section is missing / has no address — **STOP** (return
   to intake).
3. **Base URL and target addresses**: take the Base URL section (the `site.base_url` directive of web.yml —
   a config fact), Run Arguments, and the Target Pages table from [INTAKE_REPORT]. If the Base URL /
   Target Pages sections are empty — **STOP**: return to intake.
   - **Rendering base_url**: a simple URL — as is; a Jinja2 template — substitute the argument values from
     Run Arguments (env and CLI together) and obtain the topic environment's address. If the template does
     not render (unknown variable, no values) — **STOP**: return to intake for the values.
   - **Assembling full URLs**: give each target page a full address: the path `/…` is joined to
     base_url (a single slash at the junction), a full URL is taken as is. A path with an empty segment (`/`)
     means base_url itself. Record the assembled table — only full URLs are explored.
4. **Skill reference**: try to load `playwright-cli` via the Skill tool (if unavailable — continue
   with the embedded dictionary).
5. **Session bootstrap** — commands pre-executed before the first `goto`, in a single Bash call
   (env and variables do not survive between calls):

   ```bash
   PLAYWRIGHT_MCP_OUTPUT_DIR="$(goga history path 2>/dev/null)/playwright" \
     playwright-cli -s=pybuggy-explore attach --cdp=<address from Browser Endpoint>
   ```

   - `PLAYWRIGHT_MCP_OUTPUT_DIR` — session artifacts (screenshots/traces) are written to
     `<topic history>/playwright/`;
   - an `http(s)://` address — CDP → `--cdp=`; `ws(s)://` — Playwright server → `--endpoint=` instead of
     `--cdp=`; an address with `host.docker.internal` inside Docker resolves to the host IP via
     `getent hosts host.docker.internal` (outside Linux `getent` returns nothing — use the name as is);
   - attach unavailable (browser not running / port closed) — **STOP** with AskUserQuestion:
     "start the browser with remote debugging at this address" / "another address (return to intake)" —
     how to proceed?
6. **Reachability**: in the attached session, run `goto` on the first URL. On timeout/DNS/5xx — one retry
   (`reload`). On failure — **STOP** with AskUserQuestion: "the URL is wrong" / "the environment is not
   started" / "VPN/access is required" — how to proceed?

## Algorithm

### Step 1. Initialization

Pre-flight (Step 0) → the session is attached (`attach`), the first URL is loaded.

### Step 2. Dossier for each target page (PAGE-<N>)

For each URL from Target Pages (a full dossier — for every page, without exceptions):

1. **Navigate**: `goto <full URL from the assembled table>` — record the **final URL** (after
   redirects), the title from the page status, and the **page address**: the path relative to base_url
   (a topic page; reread the post-redirect final URL as a path) or the full URL (an external
   page).
2. **Structure**: `snapshot --depth=4` — determine the page's purpose and key regions.
3. **Headings**:
   `--raw eval "JSON.stringify([...document.querySelectorAll('h1,h2,h3')].slice(0,20).map(h => h.tagName + ': ' + h.textContent.trim().slice(0,120)))"`.
4. **Links**:
   `--raw eval "JSON.stringify([...new Set([...document.querySelectorAll('a[href]')].map(a => a.href))].slice(0,50))"`.
5. **Forms and validations**:
   `--raw eval "JSON.stringify([...document.querySelectorAll('form')].slice(0,5).map(f => ({action: f.action, method: f.method, fields: [...f.querySelectorAll('input,select,textarea')].slice(0,30).map(el => ({name: el.name, type: el.type, required: el.required, placeholder: (el.placeholder||'').slice(0,60), pattern: el.pattern || '', maxLength: el.maxLength || ''}))})))"`.
6. **Key interactive elements**: select 3–7 refs from the snapshot (main CTAs, filters, tabs,
   toggles) and record the triple "purpose + visible name (text/label) + ref". Locators
   (CSS/XPath, testid) are not collected in the dossier: element addressing in web tests goes by
   visible names, and locators never enter the topic's artifacts.
7. **Console and network**: `console` (errors) and `requests` (failed requests 4xx/5xx — method
   URL → status).
   Separately list the **page's API endpoints** (XHR/fetch: method + path) — the main source of facts for
   requirements §6.
8. **Observable states**:
   - empty state — record how it looks (if observed);
   - error state — one safe submit of an empty form (if a form exists and the submit is harmless),
     record the validation texts verbatim;
   - loading state — only if it was observed;
   - pop-up banners/toast notifications that appear and disappear on their own (on page load
     or after an action): record the verbatim text, the appearance event, and the **timing — after
     how many seconds the banner disappears**. Measurement: `find "<banner text>"` immediately after
     the event, then repeated checks with a pause (`sleep N` between calls) until it disappears — the
     period from appearance to disappearance; for more precision — `--raw eval` with element-presence
     polling (Promise +
     `setTimeout`), returning the appearance and disappearance times in seconds.
9. **Adjacent page traversal**: 1–2 key clicks from item 6; each transition — a line "action (click
   `<element>`) → `<final URL>`" in the navigation map; return with `go-back`. A new significant page
   within the crawl depth — a mini-dossier (heading + links + purpose); a full dossier — only for
   target pages.
10. **Auth wall**: a redirect to `/login`, a login form in the snapshot, or 401 in `requests` — go to
    the Auth block, then continue the dossier.

### Step 3. Auth (if a wall exists)

1. No wall — record `Auth: none`.
2. A wall exists — WAIT (AskUserQuestion): "Test credentials are needed for the exploration. How do we
   proceed?" —
   "I will enter them now" / "From env `<names>`" / "Skip the closed pages".
3. Log in within the session: `snapshot` → `fill e<N> "<login>"`, `fill e<M> "<password>"`, `click e<K>`
   (or `press Enter`). **Secrets are never written into the report** — only the mechanism: "form
   `<URL>`, fields `<name>`,
   submit `<button — visible name>`; source `<env/user>`".
4. `state-save auth.json` — state for reuse between pages and session restarts
   (the file stays in the CLI working directory; exploration only — in tests the login is replayed
   with suggested steps).
5. Captcha/2FA — WAIT: "Complete the login manually in the open session window, then answer 'done'";
   refusal — **STOP**.

### Step 4. Comparison with expectations (without decisions)

For each page, compare the observed with the "What the user says" column from [INTAKE_REPORT]:
list the discrepancies in the "Discrepancies with user expectations" section of the dossier — without
edits or conclusions (decisions are made by the elaborate stage with the user).

### Step 5. Completion

Disconnect from the session (`detach`). Assemble [EXPLORE_REPORT] — including the verbatim executed
attach command (with the resolved address) in the "Re-attach command" section: the report stage copies
it into §1 of the artifact, and the requirements review executes it for repeated exploration.

STOP if:

- playwright-cli is unavailable;
- `.goga/tools/pybuggy/web.yml` is missing;
- `site.base_url` is missing in web.yml (intake did not record it — ask the user to
  define the directive in web.yml: `goga tool pybuggy init` kind web/both, or manually);
- the base_url template does not render with the values from Run Arguments (and the user did not
  supply them);
- the address from Browser Endpoint is unavailable for attach, and the user did not offer another
  address;
- the site is unreachable after the retry (and the user did not explain how to proceed);
- all target pages are behind authorization, and no credentials are provided;
- captcha/2FA without manual bypass;
- session crash after 2 restarts.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [EXPLORE_REPORT]

## Explored pages

### PAGE-1: <short name>

- **Address:** <path relative to base_url (`/…`) — a topic page | full URL — an external page>;
  final URL: <full, after redirects> (entered: <assembled full URL>)
- **Title:** <title>
- **Purpose:** <1–2 sentences — what this page is>
- **Key elements:** (addressing by visible names; locators — CSS/XPath, testid — are not recorded)

  | Element (visible name) | Purpose | ref |
  |-----------------------|------------|-----|
  | […]                   | […]        | e12 |

- **Forms:** for each: action, method; fields `name / type / required / validations (placeholder, pattern, maxLength)`
- **Navigation:** `action (click <element>) → <final URL>` (for site pages — also the path
  relative to base_url) — for each transition
- **Observable states:** empty / error (validation texts verbatim) / loading / pop-up banners-toasts (verbatim text, appearance event, disappear after N s) — what they look like and how to reproduce them
- **Network and console:** console errors; failed requests (method URL → status); the page's API endpoints (method + path)
- **Discrepancies with user expectations:** <statement from [INTAKE_REPORT] ↔ observation; or `none`>

### PAGE-2: …

## Auth

[none | mechanism: form `<URL>`, fields `<name>`, submit `<button — visible name>`; credentials source `<env-names/user>`;
session state saved: yes/no. NO secret values]

## Re-attach command

[Verbatim executed attach command (with the PLAYWRIGHT_MCP_OUTPUT_DIR prefix and the resolved
address) — the report stage copies it into §1 of the artifact; the requirements review executes it
for repeated exploration of the pages when facts are unclear or disputed]

## Budget

[target pages: X/X (all); adjacent URLs: used/limit; crawl depth: used/limit;
interactions: used/limit; exhausted: yes/no]

## Not explored

[URL + reason (crawl limit / auth / crash) — or `none`]

## Technical findings

[redirects, pop-ups/new windows, cookie banners, special requirements (WebGL/geolocation/fonts) — what affects the tests; or `none`]
```
