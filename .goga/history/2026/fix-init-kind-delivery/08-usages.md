# Usage Reconciliation Report

## Classification

| Usage File | Classification |
|---|---|
| `goga_tool_pybuggy/commands/init/.usages/init.md` | DIRECTLY AFFECTED |
| `goga_tool_pybuggy/commands/init/.usages/config-build.md` | DIRECTLY AFFECTED |
| `goga_tool_pybuggy/web/.usages/pybuggy-web.md` | INDIRECTLY AFFECTED |
| `.goga/usages/conventions.md` (base) | UNAFFECTED |

## Updated Usages

| Usage File | Changes Made | Reason |
|---|---|---|
| `init.md` | web-branch bullet names the explained provider/model prompts and the five-name browser choice; the flat-usage-file table row gains the per-kind gates (api pair ↔ `api.yml`, `pybuggy-web.md` ↔ `web.yml`, both for a `both` session); the sandbox row marked kind-neutral/always; the registration row rewritten to "conventions always; api pair only when api.yml was written; pybuggy-web only when web.yml was written" | the delivery/registration contract changed |
| `config-build.md` | the web-branch question list: purpose lines for provider and each model (both still required, re-asked when empty), the browser choice with the five names and the at-prompt rejection rationale | the survey prompts changed |

## Verified Usages

| Usage File | Verified? | Notes |
|---|---|---|
| `pybuggy-web.md` | YES | mentions the surveyed minimum generically and the playwright Dockerfile line — both still accurate; it never documented the browser question form, so no edit needed |
| `init.md` session sections, upgrade mode, programmatic usage | YES | unchanged behavior — the session seam, mode gates, and seams are untouched |
| `config-build.md` api branch / contribution / failure semantics | YES | unchanged behavior; the "question sets never cross" sentence remains true and now extends to usages/registrations via the manifest |

Docs outside cells (mirrored surfaces, per the project lockstep rule): `docs/cli/init.md` (stage-2 intro, two table rows, web-branch list, packaged-roots note) and `docs/getting-started.md` (survey summary, two table rows) re-synced; a repository-wide sweep for the retired wording ("always registered", "every packaged usage is copied", "seven stems", "still copies", old prompt texts) returns nothing outside `.goga/history/`.

## Canonical Patterns Status

Preserved — both files keep their domain statement, table structure, and programmatic-usage sections; only the statements that named the old contract changed. No canonical pattern was altered.

## Consistency Summary

**Consistent.** Cell usages, docs mirrors, manifest, and implementation describe the same kind-gated contract; `goga lint` (25 cells, 0 errors) passes after the updates.
