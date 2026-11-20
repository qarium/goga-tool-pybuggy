# Usage Reconciliation Report

## Classification

| Usage File | Classification |
|---|---|
| `goga_tool_pybuggy/api/.usages/api.md` | INDIRECTLY AFFECTED (names the auth pair) |
| `goga_tool_pybuggy/matchcrest/matchers/.usages/matchers.md` | UNAFFECTED (no mention of the bases or the re-export) |
| `goga_tool_pybuggy/plugins/.usages/configuration.md` | UNAFFECTED (no mention of the four routines) |
| `goga_tool_pybuggy/plugins/.usages/enable.md` | UNAFFECTED (no mention of the four routines) |
| `goga_tool_pybuggy/matchcrest/utils/.usages/helpers.md` | UNAFFECTED (documents the utils decorator itself — cell and declaration untouched) |
| `.goga/usages/cooks/resq.md` | UNAFFECTED (names the pair as the AuthBase mechanism in api — still true) |
| `.goga/usages/cooks/jinja2.md` | UNAFFECTED (describes the whitespace normalization render_base_url performs — routine unchanged in code) |
| `.goga/usages/conventions.md` (base) | UNAFFECTED (read-only base practice) |

## Updated Usages

| Usage File | Changes Made | Reason |
|---|---|---|
| — | none | No usage documents any of the seven names as facade/contract surface |

## Verified Usages

| Usage File | Verified? | Notes |
|---|---|---|
| `api.md` | Yes | The facade table lists exactly the six facade names; the pair is explicitly stated internal and "not part of the facade" — precisely the reconciled state; the `auth=` kwarg recipe (combine order, TypeError) matches endpoint.py |
| `matchers.md` | Yes | Consumer patterns address the concrete facade matchers only |
| `plugins/.usages/configuration.md`, `enable.md` | Yes | Consumer patterns address plugin options/flags and install(); no internal routine referenced |
| `helpers.md` | Yes | Decorator contract lives in utils, which still declares and exports it |
| `resq.md`, `jinja2.md` | Yes | Behavioral statements remain true (code unchanged) |

## Canonical Patterns Status

Preserved — no example, parameter description, or canonical recipe changed; the reconciliation
touched no consumer-facing surface.

## Consistency Summary

**Consistent.** `goga lint` after reconciliation: 26 cells, 0 errors (usage references of all
manifests resolve).
