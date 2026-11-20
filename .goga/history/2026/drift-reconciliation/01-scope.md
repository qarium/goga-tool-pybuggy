# Scope Resolution Report

## Task Summary

`goga drift` reports four type-level entries (7 type names) of disagreement between the declared view
(CODEMANIFEST bodies) and the code-derived view (Python cell facades — `__init__.py` `__all__`):

| Cell | Kind | Types |
|---|---|---|
| `goga_tool_pybuggy/api` | schema_only | `AuthWrapper`, `CombineAuth` |
| `goga_tool_pybuggy/matchcrest/matchers` | schema_only | `BaseSetValueMatcher`, `BaseValueMatcher` |
| `goga_tool_pybuggy/matchcrest/matchers` | codegraph_only | `allow_failure` |
| `goga_tool_pybuggy/plugins` | schema_only | `load_fixture_plugins`, `loader_section_of`, `render_base_url`, `web_cache_path` |

The task: reconcile the two views so `goga drift` returns an empty report, preserving triple consistency
(CODEMANIFEST ↔ implementation ↔ `.usages/*.md`) and the documented design intent of each cell.

## Candidate Cells

| Cell | Reason | Priority |
|---|---|---|
| `goga_tool_pybuggy/api` | drift subject — `CombineAuth`/`AuthWrapper` declared in manifest, absent from facade | 1 (direct) |
| `goga_tool_pybuggy/matchcrest/matchers` | drift subject — both directions: internal bases declared but not in facade; `allow_failure` in facade but not declared | 1 (direct) |
| `goga_tool_pybuggy/plugins` | drift subject — four internal routines declared but not in facade | 1 (direct) |
| `goga_tool_pybuggy/matchcrest` | reference precedent — parent cell re-exports `allow_failure` with the `->allow_failure: {}` embedding and produces no drift | 2 (reference) |
| `goga_tool_pybuggy/matchcrest/utils` | provider of the `allow_failure` import consumed by matchers | 2 (dependency) |

## Included Dependencies

| Cell | Behavioral Relevance |
|---|---|
| `goga_tool_pybuggy/matchcrest/utils` | Owns `allow_failure`; the matchers manifest already imports it — the embedding target must exist there (verified: declared in its CODEMANIFEST, no drift on that cell) |
| `goga_tool_pybuggy/plugins/loaders` | `BaseLoader`/`PackageLoader`/`ModuleLoader` appear in the plugins manifest imports; after removing the `load_fixture_plugins` routine the import stays used by `ApiPlugin`/`SandboxPlugin`/`WebPlugin` signatures — no change needed, verified against the `ImportIsUsed` lint rule |

## Excluded Dependencies

| Cell | Exclusion Reason |
|---|---|
| `goga_tool_pybuggy/api/asserts` | No drift; `AssertConfig` is internal there but declared as an embedded/imported shape consistent with its facade — not a drift subject (schema view reports no discrepancy for it) |
| `goga_tool_pybuggy/web`, `goga_tool_pybuggy/sandbox/*` | Referenced only through unchanged plugin behavior; no drift entries; no manifest semantic involvement in the seven type names |
| All other cells | No drift entries, no data flow participation in the affected declarations |

## Usage Relationships

| Usage | Relevance |
|---|---|
| `goga_tool_pybuggy/api/.usages/api.md` | Already documents `CombineAuth`/`AuthWrapper` as internal and not re-exported — aligned with the reconciliation direction; verify wording stays accurate after the manifest change |
| `goga_tool_pybuggy/matchcrest/matchers/.usages/matchers.md` | No mention of `BaseValueMatcher`/`BaseSetValueMatcher`/`allow_failure` re-export — verify no update needed |
| `goga_tool_pybuggy/plugins/.usages/configuration.md`, `.usages/enable.md` | No mention of the four internal routines — verify no update needed |
| `.goga/usages/conventions.md` (base) | Mandatory code-writing/testing rules for any code-side touch |

## Semantic Participation Summary

- **api**: `CombineAuth`/`AuthWrapper` exist in `auth.py`, are used by `Endpoint._call`, and are deliberately
  not re-exported (facade docstring + manifest annotations both state "internal to the cell"). The manifest
  declaring them as body types contradicts the facade — the drift.
- **matchcrest/matchers**: `BaseValueMatcher`/`BaseSetValueMatcher` are internal abstract bases in `value.py`
  ("Not exported through the facade" per their own annotations) — same contradiction. Conversely `allow_failure`
  is deliberately re-exported through the matchers facade (present in `__all__`, imported from `utils`) but the
  manifest body never declares it — the parent `matchcrest` cell shows the intended form: the `->allow_failure: {}`
  embedding.
- **plugins**: the four routines live in `discovery.py`/`render.py`/`web_plugin.py`, are consumed by the plugin
  classes, and are not facade members; the manifest declares them as body routines — same contradiction.

## Final Investigation Scope

- `goga_tool_pybuggy/api` (CODEMANIFEST; `__init__.py` docstring context)
- `goga_tool_pybuggy/matchcrest/matchers` (CODEMANIFEST; facade)
- `goga_tool_pybuggy/plugins` (CODEMANIFEST; facade)
- Reference cells: `goga_tool_pybuggy/matchcrest` (embedding precedent), `goga_tool_pybuggy/matchcrest/utils` (import source)

## Scope Risks

- **Over-scoping**: touching code facades (`__all__` expansions) would change the public API surface of three
  cells without need — the manifests themselves document the internal-by-design intent, so the reconciliation
  direction is manifest-side (remove internal declarations, add the one missing embedding), not code-side.
- **Under-scoping**: removing declarations orphan their backtick references (`AnnotationLinksExists` lint rule)
  and the `BaseValueMatcher::BaseSetValueMatcher` mutation chain (`MutationExists` rule); every remaining
  annotation that references a removed type must be reworded in the same change. Usages files and docs pages
  that name the internal types as contract surface must be swept for consistency.

## Notes

- Drift mechanics verified in the goga 2.1.0 source: the codegraph view takes the Python facade
  (`__init__.py` `__all__` or public declarations) as the cell's type set; the schema view takes
  entities + routines of the CODEMANIFEST body (embeddings included as entities with `embedded=True`).
  An empty `goga drift` therefore means: body types == facade members, per cell, per direction.
- The `matchcrest` parent cell (`->allow_failure: {}` embedding + facade re-export) is the in-repo
  precedent for the codegraph_only direction; no precedent exists yet for schema_only removal — this
  run establishes it.
- No code-behavior change is anticipated: all seven types exist in code and keep their behavior; only
  the declared contract surface and its mirrors move.
