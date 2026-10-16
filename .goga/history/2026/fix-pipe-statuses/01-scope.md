# Scope Resolution Report

## Task Summary

The user reports that every pipeline run logs `skipping status registration` four times; the
statuses subsystem is the suspected area. Investigation located the source: the goga platform
assembles the topic status scale at every pipeline start (`goga/pipeline/run_pipeline.py`),
and four registrations of the pybuggy automate status line are skipped there because their
anchors do not resolve. The task is to make the four statuses register again.

## Candidate Cells

| Cell | Reason | Priority |
|------|--------|----------|
| `goga_tool_pybuggy/statuses` | Owns the automate registration routine carrying the defective anchor (`automate.py`) | 1 — runtime participation |
| `goga_tool_pybuggy` (root) | Subscribes the status routines to the platform (`reg_hooks.py`); package usage `assembly.md` documents the anchor table | 2 — usage participation |
| `tests/statuses` | Asserts the literal registration calls including the defective anchor (`test_automate.py`) | 3 — test participation |

## Included Dependencies

| Cell | Behavioral Relevance |
|------|---------------------|
| `goga_tool_pybuggy/api` | Context only: the automate pipeline whose artifacts the statuses track; no registration logic — not modified |

## Excluded Dependencies

| Cell | Exclusion Reason |
|------|------------------|
| `goga_tool_pybuggy/config` | No data flow: status registration is independent of the config and autonomy axes |
| `goga_tool_pybuggy/plugin`, `plugin/loaders` | Infrastructural-only: pytest plugin discovery, no status participation |
| `goga_tool_pybuggy/spec`, `output`, `sandbox/*` | No behavioral participation in status registration |
| `goga_tool_pybuggy/commands/*` | No behavioral participation in status registration |
| `goga_tool_pybuggy/matchcrest` | No behavioral participation in status registration |
| goga platform package (external) | Skip-with-warning on an unresolvable anchor is its documented, correct behavior — the defect is on the tool side |

## Usage Relationships

| Usage | Relevance |
|-------|-----------|
| `goga_tool_pybuggy/statuses/.usages/registration.md` | Documents the three lines generically; carries no anchor values — unaffected |
| `goga_tool_pybuggy/.usages/assembly.md` | Documents the full anchor table — directly affected (contains the `after specified` row) |
| `.goga/usages/github/goga/history/registering-hooks.md` | Platform reference for registration semantics — reference only |
| `.goga/usages/conventions.md` | Base coding/testing rules — applies to all edits |
| `docs/pipelines/api-automate.md` | Public docs promising the six automate statuses — names stay valid; verified no anchor strings |

## Semantic Participation Summary

The statuses cell registers the automate line through six `context.register` calls; the root
package subscribes those routines to the platform status action; the tests mirror the calls
literally. The anchor value `after="specified"` participates in platform anchor resolution and
is the single point of failure — the built-in axis (empty, todo, defined, discovered, backlog,
prototyped, designed, planned, done) has never contained a `specified` entry in any goga 2.0.x.

## Final Investigation Scope

- `goga_tool_pybuggy/statuses` (CODEMANIFEST, `automate.py`, cell usage review)
- `goga_tool_pybuggy/.usages/assembly.md` (anchor table)
- `tests/statuses/` (expectation + missing real-axis regression coverage)

## Scope Risks

- Over-scoping: "improving" the resolvable `after="designed"` anchor of `arch-prepared`
  (artifact twin `prototyped`) — outside the confirmed defect; the normative table mandates it
  and the assembled placement is identical either way (verified by simulation).
- Under-scoping: fixing only `automate.py` and missing the three documentation/contract
  surfaces that mirror the anchor string (CODEMANIFEST table, `assembly.md`, test expectation),
  or missing a regression test that resolves anchors against the real platform axis.

## Notes

The platform axis is identical in goga 2.0.0, 2.0.1, and 2.0.5 (checked from the published
wheels): `specified` never existed. The anchor is defective since authoring (commit 9d66ec5).
