---
name: goga-tool-pybuggy-web-automate-accept-consistency
description: Pre-run consistency check of the web test chain — Routine → test_*.py traceability, step sentences vs the Routine annotation, generation_prompt decorators vs the Routine `Prompt:` section, page addressing compliance vs requirements (site pages as base_url-relative paths, external pages by full URLs), step-cache presence, skip masking
---

# Pybuggy Web Topic Accept — Consistency

## Identity

You verify the consistency of the web test chain before the run: Routine → test traceability,
step sentences matching the Routine annotations, page addressing compliance, step-cache
presence, and no skip masking of failures.

## Core Principle

- The CODEMANIFEST is a read-only contract.
- Every finding is fixed by editing `test_*.py` (or by returning to the testcases pipeline),
  and only with the user's approval.
- Every finding carries a precise location and a concrete suggested fix.
- Edit only the test files `tests/web/**` and (by the re-generation decision) the step cache;
  do not edit CODEMANIFEST and requirements.md — they are upstream.
- Build-time refinements of the test (the plan's implementation refinement policy) are expected:
  the review classifies them — a wording adaptation that preserves semantics vs. a semantic
  change (Step 3).
- Fill in every section of the report; empty sections are forbidden.

STOP:

- test files are not materialized (a Routine has no `test_*.py`);
- the step cache is missing for every test (run `goga build` first).

---

## Algorithm

### Step 1. Load context

1. [ACCEPT_SCOPE] — the Routine → `test_*.py` trace, cache statuses, the run command.
2. Via the **Skill tool**: `goga-cell`, `goga-tool-pybuggy-web-cookbook`, `goga-tool-pybuggy-web-usage`,
   `goga-cell-python`.
3. The path printed by `goga history path -f requirements.md` — §1 Base URL / Target environment,
   §2 pages with addresses (paths/URLs) — the baseline for the addressing check (no REQ linkage
   is stored in the tests — §3 is not used).

### Step 2. Routine ↔ test-file

1. For every Routine from the cells' CODEMANIFESTs — does `test_<name>.py` exist at its `location`?
2. For every `test_*.py` in `tests/web/` — is there a Routine that produced it (a dangling test
   file = a finding).
3. Test signature: the fixtures match the Routine signature — page fixtures
   `page_<name>` (pytest resolves them by name; each one exists in `pages/<…>_page.py`);
   an extraneous fixture in the signature is a finding; the `test_<name>`
   name matches the Routine.

### Step 3. Step sentences ↔ Routine annotation

For every test, compare the step sentences (`page.step`/`page.expect`/`page.group` — the surface
of the activated page) with the annotation of its
Routine (`Steps:`). The build agent may have refined the test (the implementation layer): an
adapted step wording is an expected outcome of the refinement policy, not a defect by itself —
classify each divergence:

1. Every `Steps:` item of the annotation is reflected by a sentence (directly or inside a group),
   a refined wording of it, or a page-object method call (a goal sentence with the reference
   ``Use `page-<name>` — method``); a navigation item — by the activation `with page_<name>() as
   page:`. An annotation step with no counterpart at all — **High** (a check was dropped).
2. **Refinement drift** (was → became): the wording differs from the annotation but the semantics
   are preserved (the same target, the same expectation — adapted to the page) — **Medium**; each
   one goes to the review decision: absorb into the annotation through the user (patch pipeline) /
   revert the test. A refinement that changes what is checked (a different expectation, a weakened
   check, a different target) — **High**.
3. Extra sentences with no annotation counterpart — **High**, unless they are the refined form of
   an annotation step (see item 2).
4. Actions are `page.step`, checks are `page.expect` (mixed up = a finding; the exception is
   transient toasts/banners with a lifetime from the §2 details: their acknowledgment lives in
   the trigger action sentence — this is not a mix-up, see the cookbook).
5. One action per sentence (a combined "open and fill" = a finding).

### Step 4. Generation prompts ↔ `Prompt:`

For every test, compare the `@generation_prompt("…")` decorators (the import
`from goga_tool_pybuggy import generation_prompt`) with the `Prompt:` section of the annotation
of its Routine:

1. Every `Prompt:` bullet is reflected by a decorator with the same text.
2. There are no extra decorators (a test of a Routine without `Prompt:` has no decorators).
3. The order of the decorators = the order of the annotation bullets.

### Step 5. Page addressing compliance

Compare the addresses in the step sentences with the Base URL of §1 and the pages of §2 of the
requirements:

1. Topic pages — as paths relative to base_url (as in §2).
2. External pages — as full URLs of a foreign origin with the "external" mark.

Findings:

- a bare host without a scheme;
- a path not from §2;
- a foreign domain without the mark.

### Step 6. Step cache

1. For every test, the directory `tests/web/<cell>/.cache/test_<name>/test_<name>/` exists and is
   not empty (the cache is created by the generating run at build; a parameterized case —
   `…/test_<name>[<param_id>]/`).
2. For every page whose fixtures/methods the tests use (`Use page-<name>` sections), the shared
   cache `pages/.cache/<page>/<method>/` exists and is not empty (per method, `__call__` for the
   activation) — a missing/empty method cache is a finding:
   the first strict run will fail with a cache-miss on the page activation/methods.
3. A missing/empty cache is a finding: the test will fail with a cache-miss in strict mode; the
   resolution is re-generation via a non-strict run (after the user's confirmation) or a
   materialization defect.
4. A complete absence of caches for every test is a STOP: `goga build` was not executed; run it
   first according to the topic's plan (the first, generating run).
5. **Orphan cache**: a build-time refinement may have changed a step's wording — the old
   sentence's cache file then stays behind. A cache file whose sentence no longer exists in the
   test — **Medium** (fix — delete the stale file; the cache is never edited by hand: deletion +
   one non-strict regeneration is the sanctioned mutation).

### Step 7. Skip masking

For every `test_*.py`: no `pytest.skip`, skip markers, `xfail`, commented-out tests —
masking = a Critical finding.

### Step 8. Findings and decisions (WAIT)

1. Collect all findings before showing them; sort by Seriousness Critical → High → Medium.
2. Show them one at a time: Seriousness / Area / Location (test, Routine, sentence) / Issue /
   Evidence / **Suggested fix** (a concrete edit).
3. AskUserQuestion for each one (2–4 options): **Apply suggested fix** / **Propose alternative** /
   **Skip**. Counter: "Finding 3 of 12".
4. Edits — only in `test_*.py` and (by the re-generation decision) the step cache; do not edit
   CODEMANIFEST and requirements.md (see Core Principle). A step sentence changes only with
   explicit confirmation (the source is the Routine annotation).

---

## Output Format

Fill in every section.

```md
# [ACCEPT_CONSISTENCY]

## Routine ↔ test-file

[Table: Routine | test_<name>.py | Status (ok / missing / dangling file)]

## Step sentences ↔ Routine annotation

[Table: Test | Routine | Status (full match / refined wording — semantics preserved / semantic
drift / what is missing / what is extra)]

## Generation prompts ↔ `Prompt:`

[Table: Test | `Prompt:` bullets / decorators | Status (match / missing decorator / extra
decorator / order)]

## Page addressing compliance

[Table: Test | Sentence with an address | Status (ok — a path from §2 / an external full URL /
a path not from §2 / a foreign origin without the mark)]

## Step cache

[Table: Test | Cache directory | Status (present and non-empty / missing / empty)]

## Skip masking

[Tests with masking or `none`]

## Findings

[List of findings: Seriousness / Location / Issue / Suggested fix. Write `none` if there is
nothing]

## Applied fixes

[Applied test-file edits + cache re-generations. Write `none` if there is nothing]

## Overall

[The chain is consistent / has N open findings — the impact on the run]
```
