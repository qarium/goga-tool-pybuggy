# Architecture Plan — Per-test `generation_prompt` decorator for web tests

Implements `.goga/history/2026/web-generation-prompt/task.md` (ADR decisions 10–15 of
`.goga/history/2026/web-generation-prompt/adr.md`). Approved through the prototype pipeline:
design decisions — decorator in the web cell (`pretty.py`), `prompt_extra` parameter of
`build_pretty_config`, strip-at-decoration with single-`\n` joins skipping empty operands.

## Topic

Short name: per-test `generation_prompt` decorator (test-specific extra generation
instructions for web tests, appended to `web.yml:generation_prompt`).

Plan path: `.goga/history/2026/web-generation-prompt/arch.md`.

## Implementation Order

1. **`goga_tool_pybuggy/web`** (MODIFIED) — leaf cell: declares no project Imports. Owns the
   new `generation_prompt` Routine and the modified `build_pretty_config`; both other cells
   consume its surface, so it lands first.
2. **`goga_tool_pybuggy/plugins`** (MODIFIED) — depends on web (existing Imports edge:
   `build_pretty_config`, `install_event_log_formatter`, `AllureStepHooks`, usage
   `pybuggy-web`). The WebPlugin consumes the new `prompt_extra` parameter and registers the
   marker. Independent of the root cell.
3. **`goga_tool_pybuggy`** (root, MODIFIED) — composition root; re-exports the decorator via
   a new Imports entry + embedding (the `services` pattern). Designed last: its Imports
   reference the finished web contract.

No cells are created; three existing cells are modified along the established `services`
decorator pattern.

## Artifacts

### Cell 1: `goga_tool_pybuggy/web` (MODIFIED)

#### CODEMANIFEST changes

**ADD** — body entry, placed immediately after the `build_pretty_config` entry:

```yaml
"generation_prompt(text: str) -> decorator: Callable":
  location: pretty.py
  annotations: |
    Per-test generation-instruction decorator: declare test-specific extra instructions that
    append (newline-joined) to the generation prompt of exactly this test — web.yml stays the
    single global source, the decorator carries only the extras (see `prettyplay` for the
    generation_prompt field the text rides on).

    `text`: the instruction text — a non-empty, non-whitespace-only string.
    `decorator`: the marker decorator applied to a test function.

    Algorithm:
    1. Validate at decoration: `text` must be a str whose stripped form is non-empty — a
       non-string, empty, or whitespace-only value raises ValueError (visible at collection,
       before any browser or LLM).
    2. Attach the pybuggy_generation_prompt marker carrying the stripped text as its `text`
       kwarg.
    3. Stamp the function with a usefixtures mark requesting the web fixture — the marked test
       always gets the web runtime, with or without an explicit web parameter.
    4. Return the function unchanged.

    Requirements:
    - Function-level application; stacking allowed — each application attaches its own marker,
      and the texts concatenate in the order written (the plugins-cell web fixture collects
      them).
    - Pure declaration — no I/O, no plugin lookup, no config read; works without web.yml (the
      failure then arrives at setup as pytest's standard fixture-not-found).

    Constraints:
    - Do not wrap the function body and do not execute anything at decoration time.
    - No new config keys and no presets — the web.yml key set stays fixed.

    Use `conventions` for docstrings, type hints, and testing.
    Use `prettyplay` for the generation_prompt semantics and the no-secrets rule.
```

**REPLACE** — the `build_pretty_config` body entry in full:

```yaml
"build_pretty_config(config: PrettyConfig, strict_flag: bool, interactive_flag: bool, prompt_extra: str = \"\") -> pretty: PrettyConfig":
  location: pretty.py
  annotations: |
    Materialize the validated web config with the resolved strict and interactive modes and
    the per-test prompt extras — the single construction point of the prettyplay settings
    layer.

    `config`: the validated web config (the activation).
    `strict_flag`: the effective strict override — True forces strict even when the document
      says false.
    `interactive_flag`: the effective interactive override — the same form.
    `prompt_extra`: the per-test extra generation instructions (the decorator texts, already
      joined by the caller); empty means no extras.
    `pretty`: the explicitly constructed prettyplay config.

    Algorithm:
    1. Compute the effective modes: strict = config.strict or strict_flag; interactive =
       config.interactive or interactive_flag — a CLI flag forces the mode on, never off.
    2. Compute the effective generation prompt: join the non-empty parts of
       config.generation_prompt and `prompt_extra`, in this order, with a single newline.
    3. Construct the explicit object — every field, the browser group included, passed as a
       constructor argument; generation_prompt receives the computed join.

    Requirements:
    - The all-fields construction is load-bearing: every field lands in the constructed model,
      and the runtime adopts the result verbatim; an empty or None field keeps the library
      model default (see `prettyplay`).
    - Pure — no I/O, no environment reads.
    - `prompt_extra` defaults to the empty string — call sites without extras are unchanged.

    Constraints:
    - Do not read env or pyproject here — the single source is the passed model and flags.
    - Do not normalize `prompt_extra` beyond the empty-part skip — the texts are stripped and
      joined by the caller.

    Use `prettyplay` for the PrettyConfig and browser config field contract.
    Use `conventions` for type hints.
```

**ADD** — global `Annotations` paragraph, inserted after the pytest-integration paragraph
(ending «...no base_url templating, no sandbox binding in v1.»), before `Constraints:`:

```
The cell also carries the per-test prompt declaration surface: the `generation_prompt`
decorator (the pattern of the sandbox `services` decorator) attaches the
pybuggy_generation_prompt marker and a usefixtures("web") stamp to a test function — a pure
declaration; this cell registers nothing on its own. The marker registration and the per-test
read live in the plugins cell (the WebPlugin configure step and the web fixture). Decorator
text, like step sentences, lands in LLM prompts and logs — the no-secrets rule extends to it
(documented in this cell's consumer usage doc).
```

**CHANGE** — footer `Description` in full:

```yaml
Description: |
  Web library cell — the prettyplay capability's library surface: the prettyplay settings
  materialization of the validated web config (no mirror model — the cell declares no config
  models of its own), the per-test generation-prompt decorator, the Allure step reporting
  hooks, and the console event log formatter. The web plugin itself (the web fixture, the
  strict/interactive options), the web config key set, and the document validation live in the
  plugins cell (goga_tool_pybuggy/plugins), activated by its installation gate on the presence
  of the web config document.
```

Header `Usages`, footer `Author`/`CreatedAt`, and the remaining body entries
(`AllureStepHooks`, `EventLogFormatter`, `install_event_log_formatter`) are unchanged. No
deletions.

#### `.usages/` files

**File:** `goga_tool_pybuggy/web/.usages/pybuggy-web.md` (MODIFIED)

**ADD** — section «Per-test extra instructions», inserted after «Capture vars from a page»,
before «Run modes»:

````markdown
## Per-test extra instructions

Some tests need test-specific instructions (an unusual selector, a page quirk) that must not
leak into the global prompt. Declare them with the `generation_prompt` decorator — imported
from the package root:

```python
from goga_tool_pybuggy import generation_prompt


@generation_prompt("A cookie banner (#onetrust) covers the page on every navigation — dismiss it before any interaction.")
def test_checkout(web):
    web.step("Open https://shop.example.com/checkout")
```

- The text **appends** to `web.yml:generation_prompt` (newline-joined) for this test only — the
  file stays the single project-wide source, the decorator carries only the extras; other
  tests are unaffected.
- The marked test gets the web runtime even without an explicit `web` parameter (an automatic
  `usefixtures("web")` stamp). Without `web.yml` it fails at setup with pytest's standard
  "fixture 'web' not found" — the same as any web test.
- Stack decorators; texts apply top-to-bottom in the order written:

```python
@generation_prompt("The #country dropdown is a native <select> — use select_option.")
@generation_prompt("Dates render as DD.MM.YYYY.")
def test_order_form(web):
    ...
```

- Validation is early: a non-string, empty, or whitespace-only text raises `ValueError` at
  collection — before any browser or LLM. The text is trimmed at decoration.
- **Never put secrets in the text** — it lands in LLM prompts and logs, exactly like step
  sentences.
- The prompt participates only in generation (a cache miss): changing the text never
  regenerates already-cached steps — delete the step's cache file to force regeneration on
  the next non-strict run. In `--strict-mode` runs the decorator is inert (zero LLM calls).
````

Tracked consumers outside the plan: `goga_tool_pybuggy/commands/init` imports the
`pybuggy-web` usage of this cell (and `WebConfigKeys` from the plugins cell). The usage
change is an additive section and the web config key set is untouched — no contract or
bootstrap impact on the init cell; the import graph will flag it only as a consumer of
the changed practice.

### Cell 2: `goga_tool_pybuggy/plugins` (MODIFIED)

#### CODEMANIFEST changes

**REPLACE** — the `configure()` method annotation of `WebPlugin` in full (new step 1; former
steps 1–9 renumbered 2–10 with unchanged content; one new Requirement):

```yaml
"configure()": |
  Compose the resolved option values into the activation, apply the CLI authority to the mode
  options and the typed endpoint to the browser group, scrub the library's env layer, install
  the prettyplay event log formatter, and register the pybuggy_generation_prompt marker. Runs
  after the standard option loading — only the operations the standard pluginator loading
  cannot express land here.

  Algorithm:
  1. Register the pybuggy_generation_prompt marker with a help line (the pattern of the
     sandbox plugin's pybuggy_services) — applying the marker in test modules stays
     warning-free whenever the plugin is active; the registration runs before the document
     gates, at configphase, before any collection.
  2. Read the typed CLI flags raw (--strict-mode, --interactive, --browser-endpoint) — the
     mode flags carry authority over the document values: the pluginator chain resolves the
     document before the CLI, so the typed forcing cannot ride the chain (see `pluginator`
     for the config-time CLI sources; the pattern of --base-url).
  3. Gate the document under a parse guard: an unparsable document (the config reader's parse
     error) surfaces as the clean error naming the web config document — the pattern of the
     sandbox plugin; never a raw reader traceback. A non-mapping parse fails with the explicit
     mapping error naming the document. The gates run before any option read, so the option
     chain below never meets a broken reader.
  4. Drop the foreign sections from the document copy — the web autonomy axis (pipelines, a
     section keyed by pipeline name, consumed by the tool's own autonomy resolver, never by
     the plugin) and the fixture-discovery section (loader, consumed at install time by the
     constructor's discovery) — and reject an empty remaining copy with the explicit
     empty-document error (the document must carry at least the surveyed minimum — the
     provider and the browser name).
  5. Collect the unknown document keys — everything outside the WebConfigKeys config members;
     they ride into the validation so the library forbid rule names a mistyped key (never a
     silent no-op).
  6. Apply the endpoint authority: when the user typed --browser-endpoint, inject the typed
     value into a copy of the resolved browser directive value (creating the group when the
     directive carries none or a null one) — the typed value applies verbatim, an empty string
     included (it forces the local launch over a document endpoint); the read document is
     never mutated.
  7. Validate the composed document — every resolved directive option value, the injected
     browser group, and the unknown keys — into the activation via PrettyConfig.model_validate:
     the library model with the library validators, so a structural or a semantic violation
     (an off-matrix browser name, an invalid endpoint — a typed one included) fails with its
     clean error at configphase (the pydantic detail chained).
  8. Re-store the resolved strict and interactive options from the validated activation plus
     the typed flags — never from the raw routed parse: a string-typed "false"/"no" the model
     coerces to false must not surface as true.
  9. Scrub the PRETTYPLAY_* environment variables of the process (one INFO log naming them) —
     web.yml is the single configuration source; the library's env layer never overrides it.
  10. Install the prettyplay event log formatter via `install_event_log_formatter`.

  Requirements:
  - Runs once at pytest configphase, before any collection and before any fixture invocation.
  - An unparsable document fails at configphase with the clean error naming web.yml — never a
    raw reader traceback.
  - A non-mapping or empty document fails with its explicit error naming web.yml — the same
    gate order the former web-cell validation routine carried.
  - A typed --browser-endpoint passes the same activation gate: an invalid endpoint fails at
    configphase with the document error, never at a browser start.
  - The endpoint injection, the pipelines drop, and the unknown-key collection work on copies —
    the document object the reader supplied is never mutated.
  - The env scrub is permanent for the run and race-free — configphase is single-threaded; the
    variables exist only for the library's env layer.
  - The formatter is installed unconditionally with the plugin active — it is not allure-gated.
  - The pybuggy_generation_prompt marker is registered with a help line whenever the plugin is
    active — applying it in test modules is warning-free.

  Use `pluginator` for the configure lifecycle and the config-time CLI sources.
  Use `prettyplay` for the env layer the scrub neutralizes and the validators of the gate.
```

**REPLACE** — the `web(request)` method annotation of `WebPlugin` in full (new step 2; step 3
extended with `prompt_extra`; former steps 3–5 renumbered 4–5 unchanged; one new Requirement,
one new Constraint):

```yaml
"web(request: pytest.FixtureRequest) -> web: Iterator[PrettyPlay]": |
  Function-scope generator fixture: build the per-test prettyplay runtime and close it after
  the test.

  `request`: the fixture request of the test being set up.
  web: the opened prettyplay runtime the test consumes — step, expect, group, run_on_page (see
  `prettyplay`).

  Algorithm:
  1. Compute the cache address: the root is the activation cache_root when set, otherwise the
     absolute directory of the requesting test's own module file (from the item — never the
     cwd); the per-test path is `web_cache_path` of request.node; the cache key is the item's
     name (parametrize-aware).
  2. Collect the per-test prompt extras: read the requesting item's
     pybuggy_generation_prompt markers and take each marker's `text` kwarg. The natural
     collection order of the stacked markers is last-applied-first (the bottom decorator's
     marker lands first in the item's mark list) — reverse it to the order written (top
     decorator first), then join the texts with a single newline; a test without the
     markers yields the empty string.
  3. Build the explicit prettyplay config via `build_pretty_config` from the activation, the
     resolved strict and interactive options, and the joined extras as prompt_extra.
  4. Construct the prettyplay runtime with the cache key, the path, and the config, with
     cleanup disabled (the persistence mode of the committed-cache workflow: every cached file
     of the test's key is kept — a run that fails mid-test must not destroy the cached steps
     it never reached, so the next strict replay stays green; a stale step is removed by
     deleting its file).
  5. When allure is importable (see `allure-pytest`), attach `AllureStepHooks` to the runtime.
     Open the runtime (the context manager), yield it, close it on finalization.

  Requirements:
  - A --strict-mode run makes zero LLM calls — a cache miss fails the test.
  - The step cache lands next to the test file and is committable; the addressing never depends
    on the cwd — tests running outside the project root resolve their paths from the item
    itself.
  - The marked prompt extras affect only the requesting test's runtime — the activation and
    the options are never mutated; a test without the decorator builds exactly the config it
    built before.

  Constraints:
  - No base_url templating and no sandbox binding — web steps carry full URLs.
  - Do not construct `AllureStepHooks` when the guarded import reports allure absent.
  - Do not normalize the collected texts here — the decorator already stripped them; the
    fixture only joins and passes.

  Use `pluginator` for the fixture-as-method convention.
  Use `prettyplay` for the runtime construction and the cache addressing contract.
  Use `conventions` for type hints.
```

**CHANGE** — `WebPlugin` type-level annotation, first paragraph: replace the enumeration
ending «...the plugin option of every web config directive, Allure step reporting, and the
prettyplay event log formatter.» with «...the plugin option of every web config directive,
Allure step reporting, the prettyplay event log formatter, and the
pybuggy_generation_prompt marker registration of the per-test generation-prompt decorator
(the pybuggy_services pattern of the sandbox plugin).»

**CHANGE** — global `Annotations`, web-activation paragraph: replace the enumeration ending
«...Allure step reporting, and the prettyplay event log formatter.» with «...Allure step
reporting, the prettyplay event log formatter, and the pybuggy_generation_prompt marker
registration (the carrier of the per-test generation-prompt decorator — the
pybuggy_services pattern).»

Header (Imports/Usages), all properties, the constructor Algorithm, all other body entries,
and the footer are unchanged. No deletions. No `.usages/` changes (the decorator is not on
the plugins facade; its consumer documentation is the `pybuggy-web.md` section of the web
cell).

### Cell 3: `goga_tool_pybuggy` (root, MODIFIED)

#### CODEMANIFEST changes

**ADD** — `Imports` entry, after the sandbox/data block:

```yaml
  - Types:
      - generation_prompt
    Usages:
      - pybuggy-web
    From: goga_tool_pybuggy/web
```

**ADD** — global `Annotations` paragraph, after the sandbox capability paragraph («The facade
carries the sandbox capability surface: ...»):

```
The facade carries the web prompt surface: `generation_prompt` for per-test extra generation
instructions of web tests — re-exported from the web cell (the `services` re-export pattern);
the web runtime itself is product-owned through the plugin installation (the web fixture), and
the decorator's texts append to the web config's generation_prompt for the decorated test
only. Connected capability practices: `pybuggy-web`.
```

**ADD** — body embedding, after `->services: {}`:

```yaml
->generation_prompt: {}
```

Header `Usages`, all body type declarations, and the footer are unchanged. No deletions.

#### `.usages/` files

**File:** `goga_tool_pybuggy/.usages/assembly.md` (MODIFIED)

**REPLACE** — the final paragraph in full:

```markdown
The facade also re-exports the capability surfaces of the test kinds — `services` (the
per-test data-preset decorator of the sandbox kind) and `generation_prompt` (the per-test
extra generation-instructions decorator of the web kind) — so consumer tests import them from
the package root: `from goga_tool_pybuggy import services`, `from goga_tool_pybuggy import
generation_prompt`. The session sandbox fixture and the web runtime fixture are product-owned
through the plugin installation and need no facade import.
```

### Non-cell documentation artifact

**File:** `docs/web/configuration.md` (MODIFIED)

**ADD** — section after «## The surveyed minimum», immediately before «## Related» (the
consumer how-to lands after the key reference material, as the last content section):

````markdown
## Per-test extra instructions

The `generation_prompt` key above is the project-wide baseline. A single test can add its own
instructions with the `generation_prompt` decorator — imported from the package root:

```python
from goga_tool_pybuggy import generation_prompt


@generation_prompt("A cookie banner (#onetrust) covers the page on every navigation — dismiss it before any interaction.")
def test_checkout(web):
    web.step("Open https://shop.example.com/checkout")
```

- The text appends to the `generation_prompt` key (newline-joined) for this test only — the
  file stays the single project-wide source; other tests are unaffected.
- Stack decorators — texts apply top-to-bottom in the order written.
- Validation is early: a non-string, empty, or whitespace-only text raises `ValueError` at
  collection, before any browser or LLM.
- The marked test gets the web runtime automatically (an automatic `usefixtures("web")` stamp);
  without `web.yml` it fails at setup with pytest's standard "fixture 'web' not found".
- **Never put secrets in the text** — it lands in LLM prompts and logs, exactly like step
  sentences.
- The prompt participates only in generation (a cache miss): changing the text never
  regenerates already-cached steps — delete the step's cache file to force regeneration. In
  `--strict-mode` runs the decorator is inert.
````

## Dependency Map

```
                 ┌────────────────────────────┐
                 │  goga_tool_pybuggy (root)  │
                 │  facade: main, retries,    │
                 │  ->services, ->install,    │
                 │  ->generation_prompt ◄─────┼── NEW Imports + embedding
                 └──────┬──────────────┬──────┘
        services,       │              │ generation_prompt +
        data-operations │              │ pybuggy-web (NEW Imports entry)
        (existing)      ▼              ▼
     ┌──────────────────────┐   ┌────────────────────────────┐
     │ goga_tool_pybuggy/   │   │    goga_tool_pybuggy/web   │
     │ sandbox/data         │   │ build_pretty_config  (MOD) │
     │ services             │   │ generation_prompt    (NEW) │
     └──────────────────────┘   │ AllureStepHooks, fmt, ...  │
                                └─────────────┬──────────────┘
                     build_pretty_config, install_event_log_formatter,
                     AllureStepHooks, pybuggy-web (existing Imports)
                                              │
                                              ▼
                                ┌────────────────────────────┐
                                │ goga_tool_pybuggy/plugins  │
                                │ WebPlugin (MOD): configure │
                                │   marker registration; web │
                                │   fixture marker read →    │
                                │   prompt_extra             │
                                └────────────────────────────┘
```

No circular dependencies. Build order: web → plugins → root.

## Verification Checklist

After each artifact, in the implementation order above:

**`goga_tool_pybuggy/web`**
- [ ] `goga lint` passes on the modified CODEMANIFEST (DSL syntax, references resolve).
- [ ] `tests/web/test_pretty.py`: decoration-time validation (non-string / empty /
      whitespace-only → `ValueError`; text stored stripped); marker attached with the `text`
      kwarg; `usefixtures("web")` stamped; `build_pretty_config` join semantics (empty file
      prompt → extras only; empty extras → file prompt only; both → file + `\n` + extras;
      neither → empty; all-fields construction preserved).
- [ ] Facade check: `python -c "from goga_tool_pybuggy.web import generation_prompt"`.

**`goga_tool_pybuggy/plugins`**
- [ ] `goga lint` passes on the modified CODEMANIFEST.
- [ ] `tests/plugins/test_web_plugin.py`: the marker is registered with a help line when the
      plugin is active (warning-free application); the fixture collects `text` kwargs of the
      item's `pybuggy_generation_prompt` markers in written order (top decorator first — the
      reverse of pytest's natural bottom-first marker order), joins
      with a single `\n`, and passes the result as `prompt_extra`; a test without the decorator
      builds the unchanged config; the activation is never mutated. LLM-free, browser-free.

**`goga_tool_pybuggy` (root)**
- [ ] `goga lint` passes on the modified root CODEMANIFEST; `goga schema` shows the new
      dependency edge root → web (`generation_prompt`, `pybuggy-web`).
- [ ] `tests/test_facade.py`: `from goga_tool_pybuggy import generation_prompt` works.

**Documentation**
- [ ] `pybuggy-web.md` carries the new section (append semantics, stacking, early validation,
      no-secrets, no cache invalidation).
- [ ] `assembly.md` final paragraph names both capability re-exports.
- [ ] `docs/web/configuration.md` carries the decorator section beside the key table.

**Final gate (whole task)**
- [ ] `pytest tests/ -x` green in a venv — no network, no browser, no LLM.
- [ ] Acceptance criteria 1–9 of the task verified (facade import; auto web runtime; per-test
      append; stacking order; early `ValueError`; marker warning-free; standard
      fixture-not-found without `web.yml`; strict-mode inert; docs updated).
- [ ] `WebConfigKeys` untouched — no new web.yml keys.
