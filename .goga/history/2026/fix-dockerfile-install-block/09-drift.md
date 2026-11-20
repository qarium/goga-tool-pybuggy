# Specification Drift Analysis

## Manifest Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `goga_tool_pybuggy/commands/init` | `install_pybuggy` contract still prescribed the single-line x-range pin and the metadata derivation while the implementation writes the root-user block (introduced by the fix itself) | yes — lockstep rewrite in the same change; verified in 07-manifests.md; `goga lint` 25/0 |
| `goga_tool_pybuggy/commands/init` | `install_playwright` contract lacked the root-section anchor semantics | yes — algorithm/requirements updated with the anchor, relocation, and fallback |

## Usage Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `commands/init` `.usages/init.md` | artifact table pinned the retired line form and end-of-file playwright placement | yes — rewritten to the block form with gates; "install block" wording |
| `commands/init` `.usages/config-build.md` | "the same x-range the Dockerfile install line pins" cross-reference | yes — replaced with the bulk-install reading relationship |
| docs mirrors (`docs/cli/init.md`, `docs/getting-started.md`) | derivation paragraph and table rows pinned the retired form | yes — rewritten; repo-wide grep finds no stale fragment |

## Behavioral Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `commands/init` | intended drift: the bootstrap's written Dockerfile content changes for identical inputs (the defect fix, approved override) — final behavior verified against the user's prescribed target byte-for-byte in a live REPL check: api kind = `FROM …` + the exact 4-line block; web kind = the block with the playwright line inside the root section; a pre-fix project (old single line + stranded playwright line) is repaired into the same layout on re-run | yes — intended, approved, pinned by tests |

## Algorithmic Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `commands/init` | `install_pybuggy` algorithm changed (presence-of-block check, in-place replacement, no version derivation) and `install_playwright` gained anchor/relocate steps — the manifest now describes exactly these steps (07-manifests.md consistency pass, incl. the sharpened no-op condition) | yes |
| base practices (`.goga/usages/conventions.md`) | none — the rewrite follows the conventions (mirrored tests, venv execution, naming, docstrings); `ruff check` 0 errors, `ruff format` clean | yes — no drift |

## Resolution Status

**All drift resolved.** Every drift found is the intended, user-approved change reconciled in one lockstep
pass; no unresolved manifest, usage, behavioral, or algorithmic drift remains. Gates at the time of this
analysis: full suite 1973 passed / 21 skipped; `bootstrap.py` coverage 100% (statements and branches);
`goga lint` 25 cells, 0 errors; repo-wide search for the retired line form empty outside its intentional
use as replacement-test input.
