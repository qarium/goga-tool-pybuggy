# Change Plan

## Task Classification

Type: bugfix — restore the contract-mandated registration of the four middle automate
statuses (user override of the breaking-change STOP recorded in
`breaking-escalation.md`).

## Affected Cells

| Cell | Files to Modify | What Changes |
|------|-----------------|--------------|
| `goga_tool_pybuggy/statuses` | `statuses/automate.py` | Anchor of `automate.code-designed`: `after="specified"` → `after="designed"` |
| `goga_tool_pybuggy/statuses` | `statuses/CODEMANIFEST` | Normative table row 3 anchor value corrected to `after designed` |
| `goga_tool_pybuggy` (root) | `.usages/assembly.md` | Anchor table row for `pybuggy.automate.code-designed` corrected |
| `tests/statuses` | `tests/statuses/test_automate.py` | Expected tuple updated; new real-axis resolution coverage added |

## Root Cause Analysis

`statuses/automate.py:19` anchors `automate.code-designed` `after="specified"` — a status
that exists in no goga 2.0.x built-in axis. The platform skips that registration and, in
cascade, the three chained below it — exactly the four `skipping status registration`
warnings reported on every pipeline run. The same unsatisfiable anchor is mirrored in the
CODEMANIFEST table, the package usage table, and the test expectation.

## Trace Summary

`register_hooks` → `register_automate_statuses` → `StatusRegistry.register` (add-only) →
platform `_placement_index` resolves anchors per entry in registration order → first
unresolvable anchor at `code-designed` drops it and everything chained via `before`.

## Change Strategy

1. `statuses/automate.py:19` — replace the anchor string `specified` with `designed` (the
   built-in twin of the `design.md` artifact, per the package usage's twin statement). No
   other line of the routine changes.
2. `statuses/CODEMANIFEST` — in `register_automate_statuses`, normative table row 3: change
   `after specified` to `after designed`. Current-state edit only; no other key, annotation,
   signature, or footer line moves.
3. `goga_tool_pybuggy/.usages/assembly.md` — anchor table row for
   `pybuggy.automate.code-designed`: `after specified` → `after designed`.
4. `tests/statuses/test_automate.py` — update the asserted tuple; add coverage that resolves
   every anchor of the three lines against the real platform axis and fails on any skip.
5. Verify: full regression suite, lint, facade import, real-environment scale assembly with
   zero warnings (reproduction script rerun), repository-wide search for `specified`
   leftovers naming the old anchor.

## Specification Impact

One value edit in the `register_automate_statuses` body of `statuses/CODEMANIFEST`
(normative table row 3). The contract's guarantees, signatures, registration order, and all
other anchors are unchanged. The edit removes an unsatisfiable value that violated the
contract's own Requirement line ("every anchor names an entry registered earlier in this run
or a built-in status").

## Usage Impact

- `goga_tool_pybuggy/.usages/assembly.md` — one table cell corrected (`after specified` →
  `after designed`). The surrounding twin-anchoring prose already matches the corrected
  state and stays.
- `statuses/.usages/registration.md`, `registering-hooks.md`, `docs/pipelines/api-automate.md`
  — no edits: they name no anchor values and their prose becomes accurate once the fix lands.

## Compatibility Verification

Not backward compatible in the strict sense — identical calls produce different delivered
registrations and `goga history status` names for automate topics change. Classified as a
breaking change at investigation; **the user explicitly overrode the STOP** and approved
this exact minimal scope (answer q2). No stored or generated artifact carries the old form;
the scale reassembles every run.

## Test Strategy

- Update `tests/statuses/test_automate.py` literal expectation to `("automate.code-designed",
  "design.md", "designed", "pybuggy.automate.coding-planned")` — keeps the call-order guard.
- Add `tests/statuses/test_scale_assembly.py` (integration): run the three registration
  routines through a real `StatusRegistry` over the real goga built-in axis, place entries
  with the platform's own placement logic, and assert zero skips plus the full expected
  24-entry scale in normative order; a second test drives the public
  `assemble_status_scale()` end-to-end (guarded by skipif when pybuggy is not an installed
  distribution) and asserts all 17 pybuggy statuses present and no `skipping status
  registration` records — the regression the current suite cannot see.
- Rerun the complete suite (`pytest tests/ -x`) — existing fix/patch/facade tests must stay
  green.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Hidden consumer depends on built-in fallback names for automate topics | Low | Medium | User-approved breaking change; documented in escalation and final report |
| Future axis drift in goga reintroduces unresolvable anchors | Low | Medium | New real-axis resolution test fails on any skip |
| Over-scoping the edit (touching the resolvable `arch-prepared` anchor) | Low | Low | Plan pins the exact one-token scope; simulation showed identical placement either way |
| Stale `specified` fragments left in unexpected documents | Medium | Low | Mandatory repository-wide text search after the edit |

---

# Change Execution Report

## Summary

Every pipeline run logged `skipping status registration` four times because the pybuggy
automate status line anchored `automate.code-designed` after `specified` — a status that
exists in no goga 2.0.x built-in axis. The platform skipped that registration and, in
cascade, the three statuses chained below it. The anchor was corrected to `designed` (the
built-in twin of the `design.md` artifact) across the code, the contract table, the package
usage table, and the test expectation; a real-axis regression test now fails on any future
dead anchor. Verified in a real goga 2.0.5 environment: 17/17 pybuggy statuses in the
assembled scale, zero warnings.

## Root Cause

`goga_tool_pybuggy/statuses/automate.py:19` —
`context.register("automate.code-designed", "design.md", after="specified", ...)`:
`specified` never existed in the platform axis (verified byte-identical across the goga
2.0.0/2.0.1/2.0.5 wheels); anchor resolution raised `unknown after anchor 'specified'` and
the entries for `arch-prepared`, `testcases-designed`, and `requirements-created` fell with
it via their `before` chains — exactly four skips per run. The defect was invisible to the
suite because the tests asserted the literal anchor strings without resolving them.

## Modified Cells

| Cell | Files Modified |
|---|---|
| `goga_tool_pybuggy/statuses` | `statuses/automate.py`, `statuses/CODEMANIFEST` |
| `goga_tool_pybuggy` (root) | `.usages/assembly.md` |
| `tests/statuses` | `tests/statuses/test_automate.py` (updated), `tests/statuses/test_scale_assembly.py` (new) |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| Anchor fix | `goga_tool_pybuggy/statuses/automate.py` | `after="specified"` → `after="designed"` on the `code-designed` registration (one line) |
| Contract sync | `goga_tool_pybuggy/statuses/CODEMANIFEST` | Normative table row 3 anchor corrected — current state, not changelog |
| Usage sync | `goga_tool_pybuggy/.usages/assembly.md` | Anchor-table cell corrected |
| Test sync | `tests/statuses/test_automate.py` | Expected tuple updated with the corrected anchor |

## Tests Added

| Test | File | What It Validates |
|---|---|---|
| `test_three_lines_place_completely_in_normative_order` | `tests/statuses/test_scale_assembly.py` | All 17 registrations resolve via the platform's own placement code over the real built-in axis; scale equals the 26-entry normative order; any dead anchor raises |
| `test_public_assembly_registers_all_pybuggy_statuses_without_warnings` | `tests/statuses/test_scale_assembly.py` | End-to-end `assemble_status_scale()`: all pybuggy statuses present, no `skipping status registration` records (skipif when not installed as a distribution) |

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| `goga_tool_pybuggy/statuses` | `register_automate_statuses` table row 3: `after specified` → `after designed` | `registration.md` verified accurate, no edit |
| `goga_tool_pybuggy` (root) | none | `assembly.md` anchor-table cell corrected |

## Validation Results

VERIFIED — full suite 1758 passed / 18 pre-existing skips; `ruff check` and format clean;
facade import ok; `goga lint` 24 cells 0 errors; real-environment reproduction shows zero
warnings and the complete scale; repository-wide search finds the old anchor only in
immutable history records.

## Compatibility Status

BREAKING (same-arguments behavior and status-name output for automate topics change — the
defect fix itself); user explicitly overrode the STOP and approved the exact minimal scope;
no stored or generated artifact carries the old form — the scale reassembles every run.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Consumers filtering `goga history status` by built-in names stop matching automate topics | Medium | User-approved breaking change; documented here and in `breaking-escalation.md` |
| Future goga axis drift reintroduces dead anchors | Low | New real-axis tests fail on any unresolvable anchor |
| Stale fragments of the old anchor | Low | Repository-wide search performed; only immutable history quotes it |

## Updated Files

- `goga_tool_pybuggy/statuses/automate.py`
- `goga_tool_pybuggy/statuses/CODEMANIFEST`
- `goga_tool_pybuggy/.usages/assembly.md`
- `tests/statuses/test_automate.py`
- `tests/statuses/test_scale_assembly.py` (new)
- `.goga/history/2026/fix-pipe-statuses/` — process artifacts 01–10, `breaking-escalation.md`, this document
