# Breaking Change Escalation Report

**Run**: Drift reconciliation (branch `web-tests`) · **Detected at**: pipeline Step 2 (Investigation)

## What Is Breaking

The reconciliation removes seven type declarations from three CODEMANIFEST bodies and adds one
embedding — the declared contract surface of the manifests shrinks:

| Cell | Removed declarations | Added |
|---|---|---|
| `goga_tool_pybuggy/api` | `CombineAuth()`, `AuthWrapper()` (auth.py) | — |
| `goga_tool_pybuggy/matchcrest/matchers` | `BaseMatcher::BaseValueMatcher(...)`, `BaseValueMatcher::BaseSetValueMatcher(...)` (value.py) | `->allow_failure: {}` |
| `goga_tool_pybuggy/plugins` | `loader_section_of`, `load_fixture_plugins` (discovery.py), `render_base_url` (render.py), `web_cache_path` (web_plugin.py) | — |

Under the goga-change policy this is a breaking change: manifest-defined guarantees are altered (the
contract text for those types leaves the manifests). The pipeline cannot decide this is acceptable.

## Why the Direction Is Still Manifest-Side

- The runtime code and every facade stay byte-identical; no consumer-visible API, path, format, or
  behavior changes (questions 1–4, 6 of the assessment: NO).
- The manifests themselves record the internal-by-design intent of all seven types
  ("stay internal to the cell" — api header; "Not exported through the facade" — matchers bases;
  facade docstrings of all three cells); declaring them as contract body types contradicts that
  intent and is exactly what `goga drift` reports.
- The alternative direction (export the seven names from `__all__`) widens the public API of three
  stable cells with no consumer need, contradicting the recorded design decisions.
- Behavioral documentation is preserved: the seven types' contracts already live in their code
  docstrings and remain described in prose annotations of the surviving contract types
  (`Endpoint._call` step 2, the matchers header, the plugin-class discovery/render/cache steps).

## Requested Decision

Override the STOP and authorize the manifest-side reconciliation (plan approval), or reject it.
