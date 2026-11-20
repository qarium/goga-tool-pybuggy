# Per-test generation prompt decorator for web tests

## Current State

- `web.yml:generation_prompt` (`WebConfigKeys.GENERATION_PROMPT`) is the single project-wide
  source of extra generation instructions: prettyplay appends its value to the generation prompt
  of every web test of the project (`docs/web/configuration.md`, the prettyplay usage).
- A test needing test-specific instructions (unusual selectors, page quirks) has no per-test
  channel today: the text either pollutes the global prompt or is lost.
- The delivery pattern already exists in the codebase: the `services` decorator
  (`goga_tool_pybuggy/sandbox/data`, `presets.py`) — decoration-time validation, the
  `pybuggy_services` marker plus an automatic `usefixtures("sandbox")` stamp, the root-facade
  export (`from goga_tool_pybuggy import services`), and the marker registration with a help
  line in `SandboxPlugin.configure()`.
- The `WebPlugin` `web` fixture is function-scoped and builds the per-test config through
  `build_pretty_config` from the activation — the per-test seam the decorator needs already
  exists.
- No `pybuggy_generation_prompt` marker and no `generation_prompt` decorator exist in the code
  today.

## Description

Deliver per-test generation instructions through a `generation_prompt(text)` decorator exposed
on the package facade, implementing decisions 10–15 of the ADR
`.goga/history/2026/web-generation-prompt/adr.md` (a refinement of the parent web-tests ADR).
The decorator text **appends** (newline-joined) to `web.yml:generation_prompt` for that test
only — the file stays the single global source; the decorator carries only the test-specific
extras.

Target API (approved usage examples):

```python
from goga_tool_pybuggy import generation_prompt


@generation_prompt("A cookie banner (#onetrust) covers the page on every navigation — dismiss it before any interaction.")
def test_checkout(web):
    web.step("Open https://shop.example.com/checkout")
```

Stacking — texts append to the file prompt in the order written:

```python
@generation_prompt("The #country dropdown is a native <select> — use select_option.")
@generation_prompt("Dates render as DD.MM.YYYY.")
def test_order_form(web): ...
```

Early validation — the error surfaces at collection, before any browser or LLM:

```python
@generation_prompt("   ")  # ValueError: empty / whitespace-only text
```

## Scope

**In scope:**
- The `generation_prompt(text)` decorator exposed on the root facade
  (`from goga_tool_pybuggy import generation_prompt`, the pattern of `services`/`retries`).
- Decoration-time validation: a non-string, empty, or whitespace-only text raises `ValueError`
  at collection time.
- Under the decorator: the `pybuggy_generation_prompt` marker plus an automatic
  `usefixtures("web")` stamp — the marked test always gets the web runtime.
- Function-level application only; stacking allowed — texts concatenate in the order written.
- `WebPlugin`: registers the `pybuggy_generation_prompt` marker with a help line in
  `configure()` (the `pybuggy_services` pattern); the `web` fixture reads the test's marker(s)
  and applies the marked text to that test's runtime only, appended (newline-joined) to the
  activation's `generation_prompt`.
- Documentation: the `pybuggy-web.md` usage doc (`goga_tool_pybuggy/web/.usages/`) and
  `docs/web/configuration.md`.
- CODEMANIFEST updates of the touched cells (contract types and annotations) alongside the code.
- Repository tests covering the decorator and the fixture seam — LLM-free and browser-free.

**Out of scope:**
- A `classification_prompt` decorator (ADR D14).
- Cache invalidation on prompt changes (ADR D15) — regeneration stays the manual cache-file
  deletion of the committed-cache workflow.
- New `web.yml` keys, named presets, init changes (ADR D13).
- Class- or module-level application (ADR D12).
- Implementation mechanics finalized at the design stage: marker read order, join
  normalization details, cell placement of the decorator (the ADR explicitly defers these).

## Acceptance Criteria

- `from goga_tool_pybuggy import generation_prompt` works; the decorator applies to test
  functions.
- A marked test runs with the web runtime even without an explicit `web` parameter (the auto
  `usefixtures` stamp).
- The marked text reaches only that test's generation prompt, appended after
  `web.yml:generation_prompt` (newline-joined); other tests are unaffected.
- Multiple decorators on one test concatenate their texts in the order written.
- A non-string, empty, or whitespace-only text raises `ValueError` at decoration (collection)
  time.
- The `pybuggy_generation_prompt` marker is registered with a help line when the WebPlugin is
  active; applying the marker in test modules is warning-free.
- Without `web.yml` a marked test fails at setup with pytest's standard "fixture 'web' not
  found" — the same failure mode as any web test; no new gate or error is introduced.
- In strict mode the prompt is inert: zero LLM calls, no behavior change.
- `pybuggy-web.md` and `docs/web/configuration.md` document the decorator: usage, the append
  semantics, stacking, early validation, and the no-secrets rule.
- The repository test suite passes without network, browser, or LLM.

## Stack

- **Frameworks:** pytest (markers, `usefixtures`), pluginator (plugin lifecycle — the marker
  registration in `configure()`)
- **Libraries:** prettyplay (the existing `PrettyConfig.generation_prompt` field, append
  semantics), pydantic (existing config models)
- **Infrastructure:** none

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| prettyplay | `.goga/usages/cooks/prettyplay.md` | existing |
| pluginator | `.goga/usages/cooks/pluginator.md` | existing |
| pytest | `.goga/usages/conventions.md` (testing rules) | existing |
| pydantic | `.goga/usages/conventions.md` (data model rules) | existing |

Synced usage files are managed by `goga usages sync` — reference them read-only, never create or update them in the task.

## Risks and Constraints

- Decorator text lands in LLM prompts and logs — the existing no-secrets rule of step sentences
  extends to it (documented in both target documents).
- No cache invalidation: changing the decorator text never regenerates already-cached steps;
  regeneration stays the manual cache-file deletion — documented to avoid user confusion.
- The decorator requires an active WebPlugin (`web.yml` present): without it a marked test
  fails at setup with fixture-not-found (accepted, mirrors any web test).
- `WebConfigKeys` is a fixed value set (do not add, remove, or rename members) — the decorator
  must not introduce config keys.
- Marker read order, join normalization, and cell placement remain design-stage decisions; this
  task pins only the behavior.
- Repository tests must stay LLM- and browser-free.

## Scope Estimate

Single task — one decorator, the marker registration, the fixture seam, documentation, and
tests; ~3 cells touched; mirrors the existing `services` pattern; no independent subsystems. No
decomposition.

## Existing Architecture

- **Root facade `goga_tool_pybuggy`** — the export surface: `services` (embedded from
  `goga_tool_pybuggy/sandbox/data`) and `retries` (local) already live there;
  `generation_prompt` joins them.
- **`goga_tool_pybuggy/web`** — the web library surface; `build_pretty_config` materializes the
  per-test config from the activation (the likely decorator home; final placement decided at
  design).
- **`goga_tool_pybuggy/plugins`** — `WebPlugin.configure()` registers the marker (the
  `pybuggy_services` pattern of `SandboxPlugin`); the function-scoped `web` fixture reads the
  test's markers and applies the text to that test's runtime.
- Tests mirror the source structure under `tests/` (conventions).

## Notes

- Input document: `.goga/history/2026/web-generation-prompt/adr.md` (decisions 10–15; the
  parent ADR is `.goga/history/2026/web-tests/adr.md`, decisions 1–9).
- Formulation approved by the user in the specify dialog (current state, hypothesis, code
  examples, stack, single-task estimate).
- `docs/web/configuration.md` already documents the `generation_prompt` key row; the decorator
  gets its own section there.
