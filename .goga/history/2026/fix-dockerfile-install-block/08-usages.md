# Usage Reconciliation Report

## Classification

| Usage File | Classification |
|---|---|
| `goga_tool_pybuggy/commands/init/.usages/init.md` | DIRECTLY AFFECTED (documents the bootstrap artifacts incl. the Dockerfile install step) |
| `goga_tool_pybuggy/commands/init/.usages/config-build.md` | DIRECTLY AFFECTED (cross-referenced the Dockerfile install pin from the tools amendment) |
| `docs/cli/init.md` (documentation mirror, not a cell usage) | DIRECTLY AFFECTED |
| `docs/getting-started.md` (documentation mirror) | DIRECTLY AFFECTED |
| `.goga/usages/conventions.md` (base) | INDIRECTLY AFFECTED (read-only reference for the rewrite) |
| all other cell `.usages/` files | UNAFFECTED |

## Updated Usages

| Usage File | Changes Made | Reason |
|---|---|---|
| `.usages/init.md` | artifact-table row: the single `RUN goga install pybuggy -v <major.minor>.x` line → the four-line root-user block with its gates (append / replace previous single-line install in place / idempotent; bulk install reads the project `tools:` pin); playwright row: placement inside the root section, repin, relocation; "carry its install line" → "carry its install block" | the written artifact changed |
| `.usages/config-build.md` | tools-amendment sentence: "the same x-range the Dockerfile install line pins" → "the x-range the image-build bulk `goga install` reads from the copied project, while the Dockerfile install block carries no version" | the cross-reference described the retired pin |
| `docs/cli/init.md` | artifact table rows; the "install line is derived from the installed pybuggy version" paragraph → the block description (root user, project copy, project `tools:` pin as the single version source); side-effects bullets ("install block"; tools pin derived at session time) | same |
| `docs/getting-started.md` | artifact-table row → the block form | same |

## Verified Usages

| Usage File | Verified? | Notes |
|---|---|---|
| `.usages/init.md` | yes | the tools-record paragraph (lines 87-90) keeps the x-range wording — correct, the record still pins `<N.M>.x`; no other install-step references remain |
| `.usages/config-build.md` | yes | remaining x-range mention describes the record itself — accurate |
| root `goga_tool_pybuggy/CODEMANIFEST` import of `init`/`config-build` | yes | imports the two updated usages; no stale references |
| base `conventions` | yes | read-only; the rewrite followed it (mirrored tests, `tmp_path`, naming, docstrings) |

## Canonical Patterns Status

**Preserved.** The usage files keep their structure (domain statement → artifact tables → semantics); no
canonical pattern changed — only the values describing the corrected artifact. The consumer-facing
workflow (`goga install pybuggy` as the manual install command in README/docs) is untouched — it
describes the user's own environment, not the generated Dockerfile.

## Consistency Summary

**Consistent.** Repo-wide text search over `goga_tool_pybuggy/`, `tests/`, `docs/`, `README.md` finds no
stale fragment of the old line form (the single remaining occurrence is the *input* of the stale-line
replacement test — intentional), and no "install line"/"Dockerfile pin" phrasing survives in the
touched mirrors. `goga lint` after the updates: 25 cells, 0 errors.
