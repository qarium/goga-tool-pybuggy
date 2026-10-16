# Scope Resolution Report — Patch cycle 2 (init autonomy for api.patch)

## Task Summary

The `pybuggy init` onboarding survey asks the autonomy confirm only for `api.automate`
and writes a single axis entry into `.goga/tools/pybuggy/config.yml`. The `api.patch`
pipeline now ships its own autonomy axis (consumed by the generalized `autonomous` cell)
but is never offered during onboarding. Requested: ask about autonomy for `api.patch`
the same way as for `api.automate` and create the config entries for both pipelines —
`pipelines: {api.automate: {autonomous: true}, api.patch: {autonomous: true}}` — keeping
CODEMANIFEST/implementation/.usages triple consistency. Source: user answer to
`autonomous_execution.q1` (Patch flow, 2026-10-15), recorded in `todo.md`.

## Candidate Cells

| Cell | Reason | Priority |
|------|--------|----------|
| `goga_tool_pybuggy/commands/init` | Owns `survey_autonomy` (the confirm), `build_config_data` (the axis payload), and `amend_pybuggy_config` (the call site) — the entire behavioral change lives here | 1 — primary |
| `goga_tool_pybuggy/config` | Owns the axis contract (`resolve_autonomy`, `PipelineAutonomy`, `.usages/autonomy.md`) consumed by the new entry; read-path verification target | 2 — manifest/usage relevance |
| `goga_tool_pybuggy/autonomous` | Consumes the `api.patch` axis (`PATCH_CONTRIBUTION.axis`); the runtime effect target of the new entry | 3 — behavioral proximity (no modification expected) |
| `goga_tool_pybuggy` (root) | Subscribes `amend_pybuggy_config`; untouched by the payload change | 4 — indirect |

## Included Dependencies

| Cell | Behavioral Relevance |
|------|---------------------|
| `goga_tool_pybuggy/config` | `resolve_autonomy("api.patch")` must resolve True on the payload produced by the enabling path — the acceptance gate; the init CODEMANIFEST imports the `autonomy` usage from this cell |
| `goga_tool_pybuggy/autonomous` | `PATCH_CONTRIBUTION` already declares axis `api.patch`; its existence is why the onboarding entry is meaningful — verification only |

## Excluded Dependencies

| Cell | Exclusion Reason |
|------|------------------|
| `goga_tool_pybuggy/plugin` | Infrastructural only — plugin keys of the payload are untouched by the axis change |
| `goga_tool_pybuggy/statuses` | No data flow: status registration is independent of the autonomy axis |
| `goga_tool_pybuggy/commands/*` (diff/generate/info/list/pull) | No behavioral participation — they never read the `pipelines` section |
| `goga_tool_pybuggy/sandbox/**` | No manifest semantic involvement — sandbox runs read no axis |
| `goga_tool_pybuggy/spec` | Spec parsing unrelated to the axis |

## Usage Relationships

| Usage | Relevance |
|-------|-----------|
| `goga_tool_pybuggy/config/.usages/autonomy.md` | Describes the axis shape the payload must match; its example shows only `api.automate` — evaluation candidate at usage reconciliation (contract itself is per-pipeline-name and unchanged) |
| `goga_tool_pybuggy/commands/init/.usages/*` (if any) | None exist — the cell has no cell-level usage files; not affected |
| `conventions` (`.goga/usages/conventions.md`) | Base practice — code writing and testing rules apply to every touched file |

## Semantic Participation Summary

- `commands/init` **participates by modification**: the confirm prompt, the enabling branch of `build_config_data`, and their CODEMANIFEST annotations.
- `config` **participates by contract**: the payload's `pipelines` mapping must satisfy the entry shape the resolver validates (`autonomous` boolean only); no code change.
- `autonomous` **participates by consumption**: the added `api.patch` entry is exactly what `PATCH_CONTRIBUTION.axis` resolves at the amendment moment; no code change.
- Docs pages describing the onboarding survey (`docs/getting-started.md`, `docs/cli/init.md`) participate as package data mirroring the changed prompts; `docs/configuration.md` already documents both axes generically.

## Final Investigation Scope

- `goga_tool_pybuggy/commands/init/` — `session.py` (`survey_autonomy`, `build_config_data`, `amend_pybuggy_config`), `CODEMANIFEST`
- `goga_tool_pybuggy/config/` — `storage.py` (`resolve_autonomy`), `.usages/autonomy.md` (contract reference)
- `goga_tool_pybuggy/autonomous/` — `contributions.py` (axis keys), `amendment.py` (consumption path)
- Tests: `tests/commands/init/test_session.py`, `tests/commands/init/test_init_integration.py`, `tests/test_autonomy_integration.py`
- Docs: `docs/getting-started.md`, `docs/cli/init.md`

## Scope Risks

- **Under-scoping**: missing a test that pins the old single-axis payload (three suites assert it) would leave a red gate after implementation; all three are enumerated above.
- **Over-scoping**: rewriting `survey_autonomy` into a per-pipeline question framework, or regenerating axis keys from `CONTRIBUTIONS` (a new init→autonomous cell dependency), would exceed the requested minimal change; the axis keys stay literals mirroring the existing style.
- **Semantic ambiguity**: whether the onboarding asks one confirm covering both pipelines or two per-pipeline confirms — resolved with the user at plan approval.

## Notes

- The design freedom (single combined confirm vs per-pipeline confirms) is the only open
  decision; everything else is mechanical. The user's example shows both entries `true`
  as the outcome of the enabling path.
- The config schema already validates arbitrary pipeline-name entries (`test_storage.py`
  covers unknown names being ignored) — no schema work needed.
