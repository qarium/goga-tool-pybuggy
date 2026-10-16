# Usage Reconciliation Report

## Classification

| Usage File | Classification |
|---|---|
| `goga_tool_pybuggy/.usages/assembly.md` | DIRECTLY AFFECTED |
| `goga_tool_pybuggy/statuses/.usages/registration.md` | INDIRECTLY AFFECTED |
| `.goga/usages/github/goga/history/registering-hooks.md` | UNAFFECTED (platform reference) |
| `.goga/usages/conventions.md` | UNAFFECTED (base, read-only) |
| `docs/pipelines/api-automate.md` | INDIRECTLY AFFECTED (public docs) |

## Updated Usages

| Usage File | Changes Made | Reason |
|---|---|---|
| `goga_tool_pybuggy/.usages/assembly.md` | Anchor-table row of `pybuggy.automate.code-designed`: `after specified` → `after designed` | The row documented an anchor that can never resolve; now names the built-in twin of `design.md`. The surrounding prose (twin anchoring, reverse order, add-only registration) was verified accurate and untouched. |

## Verified Usages

| Usage File | Verified? | Notes |
|---|---|---|
| `statuses/.usages/registration.md` | Yes | Names no anchor values; the "skipped registration logs a warning" statement stays truthful and now applies to zero pybuggy entries; subscription example matches `reg_hooks.py` |
| `registering-hooks.md` | Yes | Platform semantics unchanged; anchors-must-resolve rule is the rule the fix now obeys |
| `docs/pipelines/api-automate.md` | Yes | The six-status table and "anchors above its built-in twin" prose become true at runtime; no anchor strings to update; `goga history status` usage snippets unaffected |
| `conventions.md` | Yes | Base practice; all edits comply (docstrings, venv, test structure, lint) |

## Canonical Patterns Status

Preserved — no recipe, example, or canonical pattern changed shape; the single corrected
table cell aligns the document with the behavior the pattern always described.

## Consistency Summary

Consistent. `goga lint` validates all CODEMANIFEST usage references (cells 24, errors 0);
repository-wide search finds the old anchor only in immutable history records of past
processes and in this change's evidence reports.
