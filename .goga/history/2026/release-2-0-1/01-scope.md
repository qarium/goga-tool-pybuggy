# Scope Resolution Report

## Task Summary

Spec names declared in `.goga/tools/pybuggy/config.yml` may contain hyphens (`specs.some-spec:`). The `generate` command uses the raw spec name as a filesystem segment, producing `api/some-spec/…` directories (and matching test placement). A hyphenated segment is not importable as a Python module, so the generated artifacts break. Requested outcome: normalize `-` to `_` for generated module paths — either when `init` writes the spec name or when `generate` derives directories — so all generated paths are valid Python package names.

## Candidate Cells

| Cell | Reason | Priority |
|---|---|---|
| goga_tool_pybuggy/commands/generate | Creates `api/<name>/…` and test artifacts from spec names (`generate.py:395` `cwd / "api" / name / safe_id` — endpoint ids are sanitized, spec names are not) | 1 — runtime participation |
| goga_tool_pybuggy/commands/diff | Compares spec contract against `api/<name>` tree and detects orphan dirs; must agree with whatever segment naming `generate` produces | 2 — manifest + runtime relevance |
| goga_tool_pybuggy/config | `SpecEntry` / `load_config` define the spec-name data model; candidate normalization/validation point | 3 — data flow participation |
| goga_tool_pybuggy/commands/init | Writes spec entries into config (`parse_specs`, `build_config_data`); alternative normalization point per user | 4 — data flow participation |
| goga_tool_pybuggy/commands/pull | Stores downloaded specs at paths possibly derived from spec name; consistency check | 5 — verify only |

## Included Dependencies

| Cell | Behavioral Relevance |
|---|---|
| goga_tool_pybuggy/config | Direct dependency of generate/diff/pull; owns `SpecEntry` and the specs mapping the name flows through |

## Excluded Dependencies

| Cell | Exclusion Reason |
|---|---|
| goga_tool_pybuggy/spec | Endpoint-level parsing and id building; endpoint ids already sanitized downstream — no spec-name participation |
| goga_tool_pybuggy/api | Runtime cell consumed by generated code; its contract does not depend on the directory segment naming |
| goga_tool_pybuggy/output | Formatting of endpoint command results; no name→path participation |
| goga_tool_pybuggy/plugin, sandbox, autonomous, matchcrest, statuses, commands/info, commands/list | Infrastructural-only; no data flow touching spec-name-derived paths |

## Usage Relationships

| Usage | Relevance |
|---|---|
| goga_tool_pybuggy/commands/generate/.usages/generate.md | Documents generated tree layout (`api/<spec>/…`) — must reflect normalized naming |
| goga_tool_pybuggy/commands/diff/.usages/diff.md | Documents artifact-tree comparison semantics tied to `api/<spec>` |
| goga_tool_pybuggy/config/.usages/configuration.md | Documents spec-name semantics in config.yml |
| goga_tool_pybuggy/commands/init/.usages/config-build.md, init.md | Document how init writes spec entries |

## Semantic Participation Summary

- `commands/generate` — the defect site: spec name flows unsanitized into `api/<name>` segment and test placement; importability breaks.
- `commands/diff` — reads the same segment to locate the artifact tree and detect orphans; any naming change must be mirrored or diff reports false orphans/missing.
- `config` — owns the name field; decides whether normalization happens at read time (model) or stays at consumers.
- `commands/init` — the entry point that lets hyphenated names into config; the user's alternative fix site.
- `commands/pull` — verify-only: local spec storage path derivation must stay consistent if naming rules change.

## Final Investigation Scope

- goga_tool_pybuggy/commands/generate
- goga_tool_pybuggy/commands/diff
- goga_tool_pybuggy/config
- goga_tool_pybuggy/commands/init
- goga_tool_pybuggy/commands/pull (consistency verification only)

## Scope Risks

- Under-scoping: fixing only `generate` while `diff` keeps raw-name expectations would produce false orphan/missing reports for hyphenated specs.
- Over-scoping: normalizing names inside `config.SpecEntry` would silently rewrite the config key space (CLI `--spec some-spec` filters, `pull` destinations), risking a breaking change for existing configs.
- Pre-existing hyphenated trees (`api/some-spec/`) in consumer projects would become orphans after the fix; migration/cleanup behavior must be considered in the plan.

## Notes

- Endpoint-level sanitization already exists (`sanitize_id` in `commands/diff/artifacts.py`, `safe_id` in generate) — reuse its convention (non-word → `_`) for the spec-level segment rather than inventing a second rule.
- User explicitly allowed either fix site (init-time or generate-time); the plan should pick the minimal-risk one.
