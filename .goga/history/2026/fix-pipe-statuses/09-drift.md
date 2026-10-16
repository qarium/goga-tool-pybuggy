# Specification Drift Analysis

## Manifest Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `goga_tool_pybuggy/statuses` | Normative table row 3 anchored `code-designed` after a nonexistent `specified`, contradicting the table's own Requirement line and the implementation's resolvable reality | Yes — anchor corrected to `designed` in both manifest and code; `goga lint` clean |

## Usage Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `goga_tool_pybuggy` (root) | `assembly.md` anchor table documented the unsatisfiable anchor | Yes — one cell corrected; surrounding twin-anchoring prose now matches observed assembly |
| `goga_tool_pybuggy/statuses` | `registration.md` described skip-with-warning as an ambient possibility while four entries always skipped | Yes — verified: text stays truthful with zero skips; no edit needed |
| docs | `api-automate.md` promised six statuses the platform never delivered | Yes — verified: delivery restored; document needed no edit |

## Behavioral Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `goga_tool_pybuggy/statuses` | Four middle automate statuses silently dropped from every assembled scale; four warnings per pipeline run (the reported defect) | Yes — intended drift from broken to contract behavior, user-approved breaking-change override; reproduction now shows 17/17 statuses, 0 warnings |

## Algorithmic Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `goga_tool_pybuggy/statuses` | None — registration algorithm, order, artifacts, and the reverse-pipeline pattern unchanged; only the one anchor value moved to the value the algorithm's own rule requires | Yes (n/a) |

## Resolution Status

All drift resolved. Base practices (`conventions`) verified not drifting from the reconciled
manifest. No unresolved manifest, usage, behavioral, or algorithmic drift remains.
