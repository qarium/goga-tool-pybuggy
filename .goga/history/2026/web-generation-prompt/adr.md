# Per-test generation prompt decorator for web tests

A refinement of the web test kind embedded by the decisions 1–9 of
`.goga/history/2026/web-tests/adr.md` (the parent ADR of the web-tests topic).

`web.yml` carries one project-wide `generation_prompt` — the extra generation instructions
every test of the project shares. Some tests need test-specific instructions (unusual
selectors, page quirks) that must not leak into the global prompt. We decided to deliver
them through a per-test decorator, in the pattern of the sandbox `services` decorator.

## Decisions

10. **The decorator is named `generation_prompt` and lives on the facade** (the
    `from goga_tool_pybuggy import generation_prompt` pattern of `services` and `retries`).
    Under it the decorator attaches the `pybuggy_generation_prompt` marker and
    `usefixtures("web")` — the marked test always gets the web runtime, so a prompt on a
    test that forgot to request `web` cannot be silently ignored. The plugin registers the
    marker with a help line (the pattern of `pybuggy_services`).
11. **The decorator text appends to `web.yml:generation_prompt`** (newline-separated
    concatenation), never replaces it: the file stays the single global source and the
    decorator carries only the test-specific extras — the same layering prettyplay itself
    applies ("extra instructions appended to the generation prompt").
12. **Function level only, stacking allowed.** The decorator applies to test functions;
    class/module-level application is not supported. Multiple decorators on one test
    concatenate their texts in the order written.
13. **Inline text with early validation.** The decorator carries the instruction text
    inline — no named presets in `web.yml`, no new config key, no init changes. An empty,
    whitespace-only, or non-string text raises `ValueError` at decoration time — visible
    at collection, before any browser or LLM.
14. **Generation only.** No `classification_prompt` decorator; revisited only if a need
    appears.
15. **No cache invalidation.** The step cache is addressed by test and step sentence; the
    prompt participates only in generation (a cache miss). Changing the decorator text
    never regenerates already-cached steps — regeneration stays the manual cache-file
    deletion of the committed-cache workflow.

## Considered options

- **Append vs replace the file prompt.** Chose append: replacing silently loses the
  global constraints; a test needing a different global base is a config question, not a
  decorator question.
- **Named presets declared in `web.yml` vs inline text.** Chose inline: instructions are
  short, presets would add a config section and indirection without a live need.
- **Auto `usefixtures("web")` vs trusting the test to request the fixture.** Chose
  the auto fixture: mirrors `services` and turns a silent no-op into an explicit failure.
- **Prompt-identity cache invalidation vs none.** Chose none: committed-cache stability
  outweighs prompt freshness; editing a prompt is a conscious cache deletion.

## Consequences

- The decorator requires an active WebPlugin (`web.yml` present): without it the marked
  test fails at setup with pytest's fixture-not-found — the same behavior as any web test.
- In strict mode the prompt is inert (zero LLM calls) and harmless.
- Decorator text lands in LLM prompts and logs — no secrets in it (the existing
  step-sentence rule extends to it).
- The `web` fixture applies the marked text to that test's runtime only (the
  function-scoped `PrettyPlay` already carries a per-test config).
- Documented in the `pybuggy-web` usage doc and `docs/web/configuration.md`; repository
  tests stay LLM- and browser-free.
- Implementation mechanics (marker read order, join normalization, cell placement of the
  decorator) are decided at the design stage.
