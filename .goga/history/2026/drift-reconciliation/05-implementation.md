# Implementation Log

## Modified Files

| File | Change |
|---|---|
| `goga_tool_pybuggy/api/CODEMANIFEST` | Removed the `CombineAuth()` and `AuthWrapper(...)` body declarations; header and `Endpoint._call` step 2 reworded to keep the behavior description with plain-text names; footer Description updated to the new contract surface |
| `goga_tool_pybuggy/matchcrest/matchers/CODEMANIFEST` | Removed the `BaseMatcher::BaseValueMatcher(...)` and `BaseValueMatcher::BaseSetValueMatcher(...)` declarations; declared the re-exported `allow_failure(f: Callable) -> wrapped: Callable` routine (location base.py, annotation pointing to `helpers`); dropped `allow_failure` from the utils `Imports.Types` (the body routine is now the link target; the remaining three helper imports stay referenced) |
| `goga_tool_pybuggy/plugins/CODEMANIFEST` | Removed the four internal routine declarations (`loader_section_of`, `load_fixture_plugins`, `render_base_url`, `web_cache_path`); de-linked their names in the surviving ApiPlugin/SandboxPlugin/WebPlugin/web-fixture annotations (prose kept, backticks dropped); dropped `PackageLoader`/`ModuleLoader` from the loaders `Imports.Types` (`BaseLoader` stays — used by plugin signatures) |

## Stabilization Iterations

1. First pass placed `->allow_failure: {}` in the matchers body (the parent-cell precedent). `goga lint`
   rejected it: `embedded_type_has_low_level` — embeddings may only originate from packages nested
   below the current one; utils is a sibling of matchers. Corrected by declaring the re-export as a
   full routine (the platform's sanctioned form for a sibling-sourced facade name) and dropping the
   now-conflicting unaliased import (`annotation` name-conflict rule would fire on a same-name
   non-embedded declaration).
2. Same lint run exposed two knock-ons of the plugins removals: `import_is_used` flagged
   `PackageLoader`/`ModuleLoader` (their only link evidence lived in the removed
   `load_fixture_plugins` annotation) — fixed by narrowing the import entry to `BaseLoader`; and
   `annotation_links_exists` flagged the dotted link `` `Endpoint._call` `` introduced by the first
   api rewording — fixed to plain text.

No source code, facade, test, docs, or usage files were modified (verified by `git diff` — exactly
the three CODEMANIFEST files plus this run's artifact directory).
