# Usage Reconciliation Report

## Classification

| Usage File | Classification |
|---|---|
| goga_tool_pybuggy/commands/generate/.usages/generate.md | DIRECTLY AFFECTED |
| goga_tool_pybuggy/commands/diff/.usages/diff.md | DIRECTLY AFFECTED |
| goga_tool_pybuggy/commands/list/.usages/list.md | DIRECTLY AFFECTED |
| goga_tool_pybuggy/config/.usages/configuration.md | INDIRECTLY AFFECTED (updated with a clarifying note) |
| goga_tool_pybuggy/commands/init/.usages/init.md, config-build.md | INDIRECTLY AFFECTED (verified, no change) |
| goga_tool_pybuggy/plugin/.usages/enable.md | INDIRECTLY AFFECTED (verified, no change) |
| goga_tool_pybuggy/api/.usages/api.md | INDIRECTLY AFFECTED (verified, no change) |
| Remaining project/cell usages | UNAFFECTED |

## Updated Usages

| Usage File | Changes Made | Reason |
|---|---|---|
| generate.md | Artifact tree uses `<spec.dir>`; one stated sanitization rule for both segments; hyphen example (`some-spec` → `api/some_spec/…`); raw-key/`--spec` note; collision paragraph covers spec-name collisions; `--force` marker paths use `<spec.dir>` | Document the changed write path and guard |
| diff.md | New paragraph in Subject domain defining `api/<spec.dir>/` and noting raw pre-fix trees are outside the sanitized root | Document the changed read path |
| list.md | Status-mode bullet defines `api/<name>/` as the sanitized segment with the rule and an example | Document the changed read path |
| configuration.md | One self-contained sentence: name keys are free-form; filesystem consumers derive an identifier segment | Prevent the original misunderstanding at its source |

## Verified Usages

| Usage File | Verified? | Notes |
|---|---|---|
| init.md / config-build.md | YES | Describe `name` as a required free-form answer with duplicate-warning; no format claims to update |
| plugin/.usages/enable.md | YES | `api/<spec>/<id>/api.py` discovery claim stays true — and now holds for hyphenated names too |
| api/.usages/api.md | YES | Example path comment remains a valid generic layout reference |
| generate.md examples (`shop`) | YES | Identifier names unchanged; all runnable examples intact (full suite green) |

## Canonical Patterns Status

Preserved. Handler-invocation snippets, artifact-tree presentation, `--force`/`--spec`/filter sections, and error-channel wording keep their structure; only the segment-derivation rule was added/defined.

## Consistency Summary

Consistent. `goga lint` after updates: 24 cells, 0 errors. Every directly-affected usage states the same single sanitization rule as the three CODEMANIFESTs and the implementation.
