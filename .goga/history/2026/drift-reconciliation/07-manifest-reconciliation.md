# Manifest Reconciliation Report

## Cells Reconciled

| Cell | Manifest Updated? | Sections Changed |
|---|---|---|
| `goga_tool_pybuggy/api` | Yes | Header Annotations (facade sentence, call-level auth sentence), body (2 declarations removed), footer Description |
| `goga_tool_pybuggy/matchcrest/matchers` | Yes | Imports.Types (allow_failure dropped), body (2 declarations removed, allow_failure routine added) |
| `goga_tool_pybuggy/plugins` | Yes | Imports.Types (PackageLoader/ModuleLoader dropped), body (4 declarations removed), surviving entity annotations de-linked |

## Algorithm Consistency

- **api**: surviving algorithm text unchanged except step 2 of `Endpoint._call`, which still matches
  endpoint.py:117-139 (`_resolve_call_auth`: direct AuthBase add, wrap protocol/callable in
  AuthWrapper, TypeError on unsupported) — match.
- **matchers**: the new `allow_failure` routine annotation matches the code chain (utils.py:85-95
  `@wraps` wrapper, logs and returns None on any Exception; bound at base.py:8; facade `__all__`
  line 86; applied to `__save_report__` at base.py:123) — match. The removed base declarations'
  behavior (any/in_array modifiers, iterability validation) lives on in value.py:15-36 and stays
  referenced by the header annotation — no manifest claim remains that contradicts code.
- **plugins**: reworded discovery/render/cache steps match discovery.py:21-42+, render.py:11+,
  web_plugin.py:130+ (guarded section read, shared discovery into `pytest_plugins`, single Jinja2
  render with StrictUndefined + whitespace stripping, per-test cache addressing) — match.

## Operational Flow Consistency

All three cells: the operational flows described by surviving annotations are the pre-change flows —
no code path changed, so every flow statement was already consistent; only link forms and the
declared type set moved. Consistent.

## Guarantees Verification

- api: `Api`/`Endpoint`/`ResponseWrapper`/`Expect`/`AssertField`/`Auth` guarantees untouched and
  facade-reachable — preserved. The removed declarations' guarantees (auth pair chaining order,
  wrapper delegation) remain true in code and are described in `Endpoint._call` — preserved.
- matchers: all facade matcher guarantees untouched; `allow_failure` facade guarantee now declared
  (previously an undeclared facade member) — improved.
- plugins: plugin-class guarantees untouched; the four internal routines' guarantees remain in code
  docstrings and the consuming annotations — preserved.

## Practices Consistency

Base usages/annotations intact in all three (`conventions` present in each `Usages` directive and
referenced first in each global `Annotations`); relative-import, docstring, and type-hint practice
statements unaffected. `goga lint` validates syntax, links, imports, mutations, and embeddings:
**26 cells, 0 errors**.

## Semantic Consistency Summary

**Consistent.** Declared view == code-derived view per cell (`goga drift` empty; programmatic
schema-vs-facade parity over all cells: no mismatch). No implementation contradicts any manifest
claim; no unplanned behavioral change (the diff contains no executable code).
