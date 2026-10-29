# Scope Resolution Report

## Task Summary

User-reported defects in the `pybuggy init` onboarding flow around the surveyed test kind (`api` / `web` / `both`): (1) with api-only selected, the web usage (`pybuggy-web.md`) is delivered into the target and the web usage/annotation land in the consumer `.goga/config.yml` under `codemanifest.usages`/`codemanifest.annotations`; (2) with web-only selected, the api usages are delivered and registered unconditionally, and the web branch asks LLM questions the user cannot answer (Provider, Generation model, Classification model — required free-text with no context); (3) the Browser name question is free-text while the runtime accepts a fixed set (chromium, firefox, webkit, chrome, msedge — the runtime's "must be one of" rejection). Expected: delivery, registration, and questions match the selected kind; the browser question presents the valid choices.

## Candidate Cells

| Cell | Reason | Priority |
|------|--------|----------|
| `goga_tool_pybuggy/commands/init` | Owns the kind-gated session surveys (`session.py`), the packaged-usage distribution and registration gating (`init.py`), and the web-kind bootstrap steps (`bootstrap.py`) — every reported symptom passes through this cell | 1 (primary) |
| `goga_tool_pybuggy/web` | Owns `WebConfig`/`BrowserSettings` semantics — the browser-name valid set and the provider/model requirements the init questions must mirror | 2 |
| `goga_tool_pybuggy/config` | Owns the api.yml spec models; candidate only because the api-kind delivery shares its config surface | 3 |

## Included Dependencies

| Cell | Behavioral Relevance |
|------|---------------------|
| `goga_tool_pybuggy/web` (via `commands/init` imports `WebConfigKeys`) | The surveyed web minimum and the browser-choice question mirror `WebConfigKeys`/`BrowserSettings`; a browser-name choice list must stay consistent with the web cell's documented browser semantics |
| `goga_tool_pybuggy/plugin` (imported for `PluginConfigKeys`) | Type-only: the api scalar prompts walk `PluginConfigKeys`; no behavioral change expected in the plugin cell itself |

## Excluded Dependencies

| Cell | Exclusion Reason |
|------|------------------|
| `goga_tool_pybuggy/config` | No behavioral participation: the api config document is written correctly for the api kind; the defect is in delivery/registration/question gating, not in the spec models |
| `goga_tool_pybuggy/plugin` | Infrastructural-only for this defect: the web plugin's activation gate already keys on the written `web.yml` (kind-gated); no plugin contract change anticipated |
| `goga_tool_pybuggy/api` | Owns the api usages being distributed, but the usages' content and contract are correct; the defect is which of them ship per kind — an `init` cell concern |
| `goga_tool_pybuggy/sandbox/*` | Sandbox usages are download-only and kind-neutral; no reported symptom touches them |
| `goga_tool_pybuggy/commands/{pull,diff,info,list,generate}`, `matchcrest`, `statuses`, `output`, `autonomous`, `spec` | No data-flow or manifest participation in the init delivery path |

## Usage Relationships

| Usage | Relevance |
|-------|-----------|
| `goga_tool_pybuggy/commands/init/.usages/init.md` | Documents the session question flow and per-kind branches — must reflect the corrected gating and questions |
| `goga_tool_pybuggy/commands/init/.usages/config-build.md` | Documents the surveyed keys incl. `browser_name` — must reflect the choice form |
| `goga_tool_pybuggy/web/.usages/pybuggy-web.md` | The delivered web practice — references browser names; checked for consistency if the browser question becomes a choice |
| `docs/cli/init.md`, `docs/getting-started.md` (outside cells) | User-facing description of the init flow; updated in lockstep per project memory rules |

## Semantic Participation Summary

`goga_tool_pybuggy/commands/init` participates directly: `session.py` owns `survey_web_config` (the LLM questions and the free-text browser question) and the kind-gated `amend_pybuggy_config`; `init.py` owns `_USAGE_ROOTS`/`_REGISTERED_USAGE_ROOTS` (the unconditional api registration and the unconditional download of every root's usages) and the `web_written` gate of `_register_web_kind`. `goga_tool_pybuggy/web` participates as the semantic source of the browser-name constraint (`BrowserSettings.name`) and the provider/model requirement (`WebConfig`) that the questions must mirror. No other cell carries behavior named by the defect.

## Final Investigation Scope

- `goga_tool_pybuggy/commands/init` (primary — code, CODEMANIFEST, `.usages/`)
- `goga_tool_pybuggy/web` (secondary — semantics only unless the browser choice touches its manifest)
- tests mirroring the init flow: `tests/commands/init/`, `tests/web/` (as needed)

## Scope Risks

- **Under-scoping**: the "must be one of: chromium, …" message provenance (runtime prettyplay vs. our validation) is not yet established; if the browser validation must live in `validate_web_config`, the web cell moves from semantic-only to code-modified.
- **Over-scoping**: tempting to rework the whole kind model (e.g. let the kind answer cross the session boundary); must stay minimal — gate what already exists, do not redesign the session seam.
- **Behavioral compatibility**: changing which usages register per kind changes the written consumer config for identical answers — an observable-output change that needs the breaking-change assessment (Step 4) and possibly user confirmation, since it is precisely the requested fix.

## Notes

- The exact user-reported registration with api-only (web usage in `codemanifest.usages`/`annotations`) is not yet explained by the code read: `_register_web_kind` is gated on `web.yml` presence, which the api branch never writes. Reproduction under Step 2 must establish whether the gate leaks (e.g. engine-side write, stale file, or the user reading the unconditional download as registration).
- prettyplay (the web runtime) is not installed in this environment; its browser-name error text cannot be grepped locally — treat its accepted set (chromium, firefox, webkit, chrome, msedge) as runtime-given, evidenced by the user report.
