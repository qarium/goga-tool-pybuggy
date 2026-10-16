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
