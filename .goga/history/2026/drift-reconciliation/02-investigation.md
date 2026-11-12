# Investigation Report

## Task Summary

`goga drift` (goga 2.1.0) reports four type-level entries — 7 type names — of disagreement between the
declared view (CODEMANIFEST bodies) and the code-derived view (Python cell facades). The task is to
reconcile the two views so the report becomes empty while preserving the documented design intent of
each cell and triple consistency (CODEMANIFEST ↔ implementation ↔ usages).

## Candidate Cells

| Cell | Reason | Priority |
|---|---|---|
| `goga_tool_pybuggy/api` | schema_only: `AuthWrapper`, `CombineAuth` | 1 (direct) |
| `goga_tool_pybuggy/matchcrest/matchers` | schema_only: `BaseSetValueMatcher`, `BaseValueMatcher`; codegraph_only: `allow_failure` | 1 (direct) |
| `goga_tool_pybuggy/plugins` | schema_only: `load_fixture_plugins`, `loader_section_of`, `render_base_url`, `web_cache_path` | 1 (direct) |
| `goga_tool_pybuggy/matchcrest` | embedding precedent (`->allow_failure: {}`, no drift) | 2 (reference) |
| `goga_tool_pybuggy/matchcrest/utils` | provider of the `allow_failure` import | 2 (dependency) |

## Tracing Summary

Drift mechanics (verified in goga 2.1.0 source, `goga/codegraph/analysis/units.py::_python_facade` and
`goga/schema/schema.py::_type_names`):

- the code-derived view takes the cell's type set from the Python facade — `__init__.py` `__all__`
  (or public declarations when no `__all__`);
- the declared view takes entities + routines of the CODEMANIFEST body (embeddings included — an
  embedded `->X: {}` is an entity with `embedded=True` and lands in the type set);
- drift entries are the two-directional set difference, per cell.

Call flows of the drifted names (all code paths unchanged by this task):

- **api**: `Endpoint._call` (endpoint.py:117 `_resolve_call_auth`) builds `CombineAuth()`, adds the
  stored `Api` auth and the call-level auth (wrapping non-AuthBase callables in `AuthWrapper`),
  and passes the chain as the request auth. Both classes live in `auth.py`; the facade
  (`__init__.py`) deliberately does not re-export them (facade docstring: "internal to the cell and
  are not re-exported"); the manifest header says the same ("stay internal to the cell") yet the body
  declares both as contract types — the contradiction drift reports.
- **matchers (bases)**: `BaseValueMatcher` (value.py:15) and `BaseSetValueMatcher` (value.py:28) are
  abstract bases of the concrete value matchers; not in `__all__`; their own manifest annotations say
  "Not exported through the facade" — same contradiction.
- **matchers (allow_failure)**: `__init__.py` re-exports `allow_failure` (imported from `..utils`)
  in `__all__` (line 86) — a deliberate consumer-facing re-export — but the manifest body never
  declares it. The parent `matchcrest` cell shows the intended form: `->allow_failure: {}` (parent
  CODEMANIFEST line 76) with the same utils import in its header.
- **plugins**: `loader_section_of`/`load_fixture_plugins` (discovery.py:21,42) are called by every
  plugin constructor; `render_base_url` (render.py:11) by `ApiPlugin.configure` (api_plugin.py:187);
  `web_cache_path` (web_plugin.py:130) by the `web` fixture (web_plugin.py:438). None is a facade
  member; the facade exposes only the three plugin classes, the two key-set classes, and `install`.

## Data Flow Analysis

No data flow changes: all seven types keep their code, call sites, and behavior. What moves is
documentation altitude only:

- the behavioral contracts of the internal types (algorithms, requirements) already exist in the code
  docstrings (auth.py:35-103, value.py:15-36, discovery.py, render.py, web_plugin.py:130) — verified
  Google-style docstrings present;
- the manifest-level context that references them (header annotations, plugin-class annotations,
  `Endpoint._call` step 2) keeps describing their behavior in prose — only the backtick link form
  must go (links must resolve per the `AnnotationLinksExists` lint rule);
- the `allow_failure` embedding adds a declaration, moving nothing.

## Manifest Algorithm Analysis

- api `Endpoint._call` Algorithm step 2 describes the combine/wrap/raise behavior — stays, reworded
  from link form to plain text (`CombineAuth`/`AuthWrapper` backticks dropped).
- matchers `BaseMatcher::BaseValueMatcher` (any/in_array modifiers, ValueError rule) and
  `BaseValueMatcher::BaseSetValueMatcher` (iterability validation) — the declarations are removed;
  their contracts already live in the code docstrings and the global annotation ("BaseValueMatcher/
  BaseSetValueMatcher are internal bases (not in the facade) supplying the any/in_array constructor
  modifiers and the iterable-value contract for value matchers" — matchers CODEMANIFEST header).
- plugins `loader_section_of`/`load_fixture_plugins` (guarded read + shared discovery), `render_base_url`
  (Jinja2 StrictUndefined + match_re + whitespace normalization), `web_cache_path` (per-test cache
  addressing) — declarations removed; the consuming plugin-class annotations retain the behavior in
  prose (ApiPlugin.configure steps, SandboxPlugin/WebPlugin discovery steps, the web fixture's cache
  addressing requirement).
- The `ImportIsUsed` rule stays satisfied everywhere: matchers' `allow_failure` import gains embedding
  evidence; plugins' `BaseLoader`/`PackageLoader`/`ModuleLoader` imports stay used by plugin
  signatures; `jinja2` usage stays referenced in global annotations (plugins CODEMANIFEST line 46).

## Affected Usages

| Usage | Cell | Classification | Reason |
|---|---|---|---|
| `.usages/api.md` (api) | api | INDIRECTLY AFFECTED | Lines 31, 295 already state `CombineAuth`/`AuthWrapper` are internal — verify wording still matches the manifest after removal (no contract-surface claim to fix) |
| `.usages/matchers.md` (matchers) | matchcrest/matchers | NOT AFFECTED | No mention of the bases or the re-export — verified by search |
| `.usages/configuration.md`, `.usages/enable.md` (plugins) | plugins | NOT AFFECTED | No mention of the four routines — verified by search |
| `.goga/usages/cooks/resq.md` (project) | — | NOT AFFECTED | Names `CombineAuth`/`AuthWrapper` as the AuthBase mechanism foundation in api — remains factually true (code unchanged) |
| `.goga/usages/cooks/jinja2.md` (project) | — | NOT AFFECTED | Describes the whitespace normalization `render_base_url` performs — routine stays in the code |
| docs pages | — | NOT AFFECTED | No mentions of any of the seven names — verified by search |

## Rejected Hypotheses

| Hypothesis | Rejection Evidence |
|---|---|
| H2: the facades should expand — add the seven names to `__all__` (code-side fix) | Contradicts the design intent recorded in both manifests ("stay internal to the cell", "Not exported through the facade") and the facade docstrings; no consumer, usage, or docs reference needs them importable; widening the public API of stable cells is the larger change |
| H3: suppress via configuration (`lint.ignore` / drift filters) | `lint.ignore` excludes directories (vendored trees), not types; no in-repo precedent; drift is contract enforcement — suppressing it hides, not fixes, the inconsistency |
| H4: the drift tool mis-sees the types (tooling bug) | Reproduced deterministically; mechanics read from the goga source: facade vs body types — the tool is correct, the manifests diverge from the facades |

## Confirmed Root Cause

Two authoring defects in the CODEMANIFEST files, not in the code:

1. **Internal types declared as contract types** (api: `CombineAuth`/`AuthWrapper`; matchers:
   `BaseValueMatcher`/`BaseSetValueMatcher`; plugins: the four internal routines). The manifests
   document these types in their bodies while the facades — by recorded design — exclude them. Since
   the declared view and the code-derived view must agree per cell, every internal-type declaration
   is a permanent schema_only drift entry.
2. **A missing embedding** (matchers): the facade deliberately re-exports `allow_failure` from
   `matchcrest/utils`, and the header imports it, but the body lacks the `->allow_failure: {}`
   embedding the parent cell carries — a codegraph_only drift entry.

Evidence chain: goga 2.1.0 `compare_views` (set difference of the two indexes) →
`_python_facade` (`__all__` of `__init__.py`) → `_type_names` (entities+routines of the body) →
per-cell verification of the three facades and bodies → in-repo precedent (matchcrest parent:
embedding + facade re-export ⇒ no drift).

## Confidence Level

**HIGH** — deterministic causality verified against the tool source; every affected declaration,
backtick reference, mutation chain, import, usage file, and test pin enumerated; the reconciliation
direction is corroborated by the manifests' own recorded intent and the parent-cell precedent.

## Breaking Change Assessment

| # | Question | Answer | Evidence |
|---|---|---|---|
| 1 | Existing call with same arguments produces different behavior? | **NO** | No runtime code changes; the seven types keep code, call sites, and semantics |
| 2 | Existing file paths change? | **NO** | No file moves; three manifests edited in place |
| 3 | Output format change? | **NO** | CLI output formats unchanged; `goga schema`/`drift` content reflects the corrected declarations (the task's goal) |
| 4 | Return value semantics change? | **NO** | No code signatures touched |
| 5 | Manifest-defined guarantees altered? | **YES** | The declared contract surface of three CODEMANIFESTs changes: 7 type declarations removed (their contracts remain in code docstrings + prose annotations), 1 embedding added |
| 6 | Existing tests break? | **NO** | No test reads the manifests (the single CODEMANIFEST mention in tests is a docstring quote); facades and code untouched; `goga lint` re-checked after the change |

**BREAKING CHANGE DETECTED** (question 5). Per the goga-change policy the pipeline STOPs here; the
manifest contract surface shrinks and only the user can authorize that direction. Escalation report
written to `breaking-escalation.md`; override + plan approval requested from the user.
