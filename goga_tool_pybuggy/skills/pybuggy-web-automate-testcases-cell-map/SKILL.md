---
name: goga-tool-pybuggy-web-automate-testcases-cell-map
description: Cell map for approved Routines — proposes cell boundaries (a design decision — one cell per page, merged flow pages, or several cells per page) and the routine distribution; WAIT for user approval
---

# Pybuggy Web Topic Testcases — Cell Map

## Identity

You distribute the approved Routines across cells. This is a design decision: the cell slug becomes
the directory name `tests/web/<cell-name>/`.

## Core Principle

A cell is the unit of materialization and ownership: `tests/web/<cell-name>/` + CODEMANIFEST.

- The starting hypothesis is one cell per page.
- Merging the pages of one flow, or splitting into several cells, are deliberate alternatives.

---

## Algorithm

### Step 1. Load context

1. [ROUTINES_REPORT] — the approved Routines (names, starting pages from the first `Steps:` entries).
2. [TESTCASES_INTAKE] — §2 pages (PAGE-<N> → URL), §9 existing coverage.
3. Existing cells `tests/web/**` on disk — new Routines of the same pages adjoin them
   (merge semantics at the assembly phase).

### Step 2. Propose the layout

1. Group the Routines by starting page (the address of the first step — a path relative to base_url or
   a full URL — ↔ §2).
2. Starting hypothesis: one cell per page — a `kebab-case` slug from the page name/URL
   (`catalog`, `checkout`).
3. Alternatives: Routines spanning several pages of one flow — a flow cell (`checkout-flow`);
   a page with many heterogeneous Routines — splitting into several cells.
4. For each cell: slug + rationale (one line).

### Step 3. WAIT — user approval

AskUserQuestion (one question per message, 2–4 options):

- **question**: "Layout: <cells with slugs and the list of Routines>. Approve?"
- **options**: "Approve" / "Merge <…>" (if applicable) / "Split <…>" / "Other"
  (clarify in free text).

### Step 4. Produce the [CELL_MAP_REPORT]

STOP if:

- 0 cells resulted;
- a Routine remains unassigned;
- the user does not approve the layout after an iteration.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [CELL_MAP_REPORT]

## Cells

| Cell (slug) | Path | Pages | Routines | Rationale |
|---------------|------|----------|----------|-------------|
| catalog | tests/web/catalog/ | PAGE-1 | test_search_finds_results, … | one cell per page |

## Routine → Cell

| Routine | Cell |
|---------|--------|
| test_search_finds_results | catalog |

## User Decision

[Approved / changed — what exactly the user confirmed]

## Notes

[Existing `tests/web/**` cells affected by assembly merge semantics. Write `none` if there are none.]
```
