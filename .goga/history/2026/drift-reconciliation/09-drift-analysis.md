# Specification Drift Analysis

## Manifest Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `goga_tool_pybuggy/api` | `CombineAuth`/`AuthWrapper` declared in the body, absent from the facade (schema_only) | **Resolved** — declarations removed; header/`Endpoint._call` keep the behavior in prose; parity verified |
| `goga_tool_pybuggy/matchcrest/matchers` | `BaseValueMatcher`/`BaseSetValueMatcher` declared, absent from the facade (schema_only) | **Resolved** — declarations removed; header already documents the bases' role; parity verified |
| `goga_tool_pybuggy/matchcrest/matchers` | `allow_failure` in the facade, absent from the body (codegraph_only) | **Resolved** — declared as the re-export routine (sibling embedding is prohibited by `embedded_type_has_low_level`; full declaration is the sanctioned form); parity verified |
| `goga_tool_pybuggy/plugins` | `load_fixture_plugins`/`loader_section_of`/`render_base_url`/`web_cache_path` declared, absent from the facade (schema_only) | **Resolved** — declarations removed; consuming annotations keep the behavior in prose; parity verified |

Whole-repo confirmation: `goga drift` → `[]`; programmatic comparison of `goga schema` types vs
`__init__.py __all__` for every cell → no mismatch.

## Usage Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| api | `api.md` already stated the pair is internal/not part of the facade — matched the code, contradicted the old manifest | **Resolved** (by the manifest change; usage untouched and now fully aligned) |
| matchers, plugins | none found | N/A — no drift |
| project cooks (`resq.md`, `jinja2.md`) | behavioral mentions remain true (code unchanged) | N/A — no drift |

## Behavioral Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| all three | none — no executable code changed; the seven types keep code, call sites, and semantics | N/A — no drift |

## Algorithmic Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| all three | none — surviving algorithm annotations describe the same code paths as before (link rewording only); the new `allow_failure` annotation matches the utils implementation | N/A — no drift |

## Resolution Status

**All drift resolved.** The declared view and the code-derived view agree per cell, in both
directions, with `goga lint` clean (26 cells, 0 errors). No unresolved manifest, usage, behavioral,
or algorithmic drift remains.
