---
name: goga-tool-pybuggy-web-playwright-cli
description: playwright-cli command reference for the pybuggy web skills — named sessions (attach/detach to a running browser via CDP or a Playwright server), navigation, accessibility snapshots with refs, find, eval, interactions, console/network, tabs, authorization state save/load, the output dir; the single source of the command vocabulary — loaded by requirements-explore, testcases-rehearse, and requirements-review instead of an embedded dictionary
---

# playwright-cli — command reference for the web skills

## Purpose

The single source of the playwright-cli vocabulary for the pybuggy web skills: page exploration
(`goga-tool-pybuggy-web-automate-requirements-explore`), live rehearsal of Routines
(`goga-tool-pybuggy-web-automate-testcases-rehearse`), and targeted live re-verification of facts
(`goga-tool-pybuggy-web-automate-requirements-review`). These skills load this reference via the
**Skill tool** instead of embedding the command dictionary.

If the upstream `playwright-cli` skill is available in the environment (installed by
`playwright-cli install --skills --global`), it carries the full reference; this document is the
minimal working set agreed upon by the pybuggy skills.

## Sessions

- Every stage works in a **named session**: the `-s=<name>` flag. Commands of one session share the
  page state; the pybuggy stages use `pybuggy-explore` (the requirements exploration and every
  re-attach through the §1 re-exploration command).
- Every command below is written short — in practice it carries the session prefix:
  `playwright-cli -s=<session> <command>`.
- `playwright-cli list` — list of open sessions.
- `playwright-cli --version` — availability check (the CLI is installed at `goga install`).

## Connection

- `PLAYWRIGHT_MCP_OUTPUT_DIR=<dir> playwright-cli -s=<session> attach --cdp=<url>` — attach to an
  already running browser over CDP (an `http(s)://` address); a `ws(s)://` address — the
  `--endpoint=` flag instead of `--cdp=` (a Playwright server). The browser is always external —
  local binaries are not needed.
- `PLAYWRIGHT_MCP_OUTPUT_DIR` — the directory for session artifacts (screenshots/traces); the
  pybuggy stages point it at `<topic history>/playwright/`.
- An address with `host.docker.internal` used inside a Docker container resolves to the host IP via
  `getent hosts host.docker.internal` (outside Linux `getent` returns nothing — use the name as is).
- `detach` — disconnect from the attached browser without closing it. Hygiene: at the end of the
  work and on any STOP — the user's browser stays open.

## Page

- `goto <url>` — navigation; prints the final URL (after redirects) and the page title;
- `go-back` — back; `reload` — reload;
- `snapshot [--depth=N] [ref]` — accessibility snapshot with refs `e<N>` (the snapshot is printed
  automatically after every command; start with `--depth=4`, deepen only for key widgets);
- `find "text"` / `find --regex "/…/i"` — search over the snapshot (like grep -C) — the way to
  explore large snapshots without reading them whole;
- `--raw eval "<js>" [ref]` — evaluate JS in the page (no status and snapshot in the output;
  waiting/polling constructions — a Promise + `setTimeout` — are allowed); when extracting lists,
  truncate with `.slice(0,50)`, strings — `.slice(0,120)`;
- `console` — console messages; `requests` — the page's network requests;
- `tab-list` / `tab-select 0` — tabs (keep one; a pop-up/new window — record it, then return).

## Interactions

- `click e<N>` / `fill e<N> "text"` / `press Enter` / `select e<N> "val"` / `check e<N>` —
  interactions with an element by its snapshot ref (the ref comes from `snapshot`/`find`).

## Authorization state

- `state-save auth.json` / `state-load auth.json` — save/load the authorization state (the file
  lives in the CLI working directory; exploration and rehearsal only — in tests the login is
  replayed with suggested steps). Secrets never enter reports and artifacts.
