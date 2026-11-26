---
name: goga-tool-pybuggy-web-automate-accept-scope
description: Web topic artifact inventory for acceptance — cells, Routines, test_*.py files, step-cache directories, usage keys, and the strict-mode test run command
---

# Pybuggy Web Topic Accept — Scope

## Identity

You determine the acceptance scope of the topic. You use only facts from disk — no assumptions:

- you enumerate the artifacts, cells, and Routines existing on disk;
- you detect materialized `test_*.py` files and step caches;
- you determine the run command.

## Algorithm

### Step 1. Collect the artifact inventory

For the current topic, verify existence and load:

1. The path printed by `goga history path -f requirements.md` — §1 Browser endpoint / Base URL /
   Target environment, and §2 pages with addresses (for cross-checking addressing).
2. `tests/web/<cell>/CODEMANIFEST` — all topic cells. The source of truth for the composition is
   the CODEMANIFEST on disk (actual state).
3. Generated `test_<name>.py` files — by each Routine's `location`.
4. **Step caches** (created by the first, generating run at `goga build`) — record the
   presence/absence and fill state of each:
    - test cache: `tests/web/<cell>/.cache/test_<name>/test_<name>/` per test
      (a parameterized case — `…/test_<name>[<param_id>]`);
    - the shared cache of each page in use: `pages/.cache/<page>/<method>/` (per method, `__call__` for activation).
5. **Page objects**: the `pages/**` modules of the topic's pages (§2 — `page_<name>` bindings /
   literal navigation) — the presence of the modules and of the declared methods (the contract is
   the usage files `.goga/usages/cooks/page-<name>.md`).
6. `conftest.py` in the root — verify presence (`.env` loading + the pybuggy plugin with the web
   fixture).
7. The document `.goga/tools/pybuggy/web.yml` — the fact of web runtime activation.
8. Usage files: base `.goga/usages/cooks/pybuggy/pybuggy-web.md` + cell-specific
   `.goga/usages/cooks/<key>.md` (keys from each cell's Header).
9. The path printed by `goga history path -f bugs.md` — check for an existing bugs file (target
   for appending records).

### Step 2. Extract Routines and build the trace

From each cell's CODEMANIFEST:

1. Routine names `test_<name>` and their `location: test_<name>.py`.
2. Build the trace Routine → `test_<name>.py`: every Routine from a CODEMANIFEST must have a
   materialized test file.
3. For each Routine — the step cache status: the directory exists and is not empty / is missing;
   for the pages whose fixtures/methods the Routine uses — the status of the shared cache
   `pages/.cache/<page>/<method>/` (per method).

### Step 3. Determine the run command

1. Base command: `pytest <paths> -q --strict-mode`, where `<paths>` are the topic's cell
   directories (`tests/web/` as a whole, or `tests/web/<cell>/` per cell). Strict mode is
   justified: the first (generating) run has already been done at `goga build` and the cache is
   in place — strict yields 0 LLM calls and checks cache completeness.
2. Add the suffix from the Browser endpoint of the §1 requirements: an address from the user →
   `--browser-endpoint <address>`; 'from the config' — without the flag. Runs and exploration
   use the same browser.
3. Add the base_url rendering arguments from §1 of the requirements, if set: env — the prefix
   `ENV_NAME=… pytest …`; CLI — the suffix `--name=value` — the run must render `site.base_url`
   to the address of the same topic environment.
4. If some test's cache is missing — record it: the run is strict, but a cache-miss for that test
   is expected (follow-up generation — by the triage decision in accept-run).
5. Record the run root: the directory that contains `conftest.py` (pytest runs from there).
6. Record the environment: browser/endpoint from the §1 requirements (Browser endpoint + web
   runtime facts); do not check site availability here (run does that).

### Step 4. Acceptance scope viability checks

1. At least one cell with a CODEMANIFEST is found.
2. At least one `test_<name>.py` exists.
3. `conftest.py` exists; if missing, record this in the report (Environment notes).
4. `.goga/tools/pybuggy/web.yml` exists; if missing, record this (the web fixture will not
   register).
5. STOP if: the topic's artifacts are not found (neither requirements.md nor CODEMANIFEST cells
   exist) or there are no generated test files at all (the `goga build` phase was not executed).

---

## Output Format

Fill in every section. Empty sections are prohibited.

Every report field — only facts from disk.

```md
# [ACCEPT_SCOPE]

## Data source

[The current topic and the artifacts the scope was assembled from]

## Cells in scope

[Table: Cell (tests/web/<cell>/) | Routine | test files found (N/M) | step cache (N/M) | Usage keys]

## Trace: Routine → test file

[Table: Routine test_<name> | tests/web/<cell>/test_<name>.py | test cache .cache/test_<name>/test_<name>/ | page cache pages/.cache/<page>/ | Status (materialized / not)]

## Run command

[The pytest command (strict mode: [ENV_NAME=…] pytest tests/web/ -q --strict-mode
[--browser-endpoint <address>] [--base_url rendering arguments], if §1 requires
suffixes/prefixes) and the run directory (the root containing conftest.py)]

## Environment notes

[conftest.py found/missing; web.yml found/missing; browser/endpoint from the §1 requirements;
existing `goga history path -f bugs.md`; tests without a step cache; other observations]
```
