# Design Document: `web-generation-prompt`

<!-- topic: .goga/history/2026/web-generation-prompt/ -->

## Contract Changes

### Changed CODEMANIFEST Files

- `goga_tool_pybuggy/web/CODEMANIFEST`: new global Annotations paragraph (the per-test prompt
  declaration surface); `build_pretty_config` gains the defaulted `prompt_extra: str = ""`
  parameter and the effective-prompt join step; new Routine `generation_prompt`; footer
  Description mentions the per-test generation-prompt decorator.
- `goga_tool_pybuggy/plugins/CODEMANIFEST`: global Annotations and the `WebPlugin` type
  annotation enumerate the `pybuggy_generation_prompt` marker registration;
  `WebPlugin.configure()` gains step 1 (marker registration before the document gates, steps
  1–9 renumbered 2–10) plus a warning-free requirement; `WebPlugin.web()` gains step 2
  (marker collection → joined `prompt_extra`), a per-test isolation requirement, and a
  no-normalization constraint.
- `goga_tool_pybuggy/CODEMANIFEST`: new Imports entry (`generation_prompt` + `pybuggy-web`
  from `goga_tool_pybuggy/web`); new global Annotations paragraph (the web prompt surface);
  new body embedding `->generation_prompt: {}` after `->services: {}`.

### New Entities

- `generation_prompt(text: str) -> decorator: Callable` — the per-test generation-instruction
  decorator; location `pretty.py` (the web cell). A pure declaration surface: validates the
  text, attaches the `pybuggy_generation_prompt` marker, stamps `usefixtures("web")`, returns
  the function unchanged.

### Changed Entities

- `build_pretty_config(config, strict_flag, interactive_flag, prompt_extra: str = "")` —
  computes the effective generation prompt (non-empty parts of `config.generation_prompt` and
  `prompt_extra`, in this order, single-newline-joined) and passes it into the constructed
  model; the default keeps every existing call site unchanged.
- `WebPlugin.configure()` — registers the `pybuggy_generation_prompt` marker with a help line
  as its first operation (before the document gates).
- `WebPlugin.web()` — collects the requesting item's `pybuggy_generation_prompt` marker texts,
  reverses to the written order, joins with a single newline, passes as `prompt_extra`.

### Deleted Entities

- None.

### Usages and Annotations Changes

- `goga_tool_pybuggy/web/.usages/pybuggy-web.md`: new consumer section «Per-test extra
  instructions» (after «Capture vars from a page», before «Run modes»).
- `goga_tool_pybuggy/.usages/assembly.md`: the facade re-export paragraph now names both
  capability surfaces — `services` and `generation_prompt`.
- `docs/web/configuration.md`: new section «Per-test extra instructions» (after «The surveyed
  minimum», before «Related»).
- Root and plugins global Annotations: the web prompt surface and the marker registration
  enumerations (see above).

## Applied Fixes

### Fixed CODEMANIFEST Defects

- None. The Phase 3 audit (DSL rules, cookbook principles, the four consistency dimensions)
  found no defects: `goga lint` reports 0 errors across 26 cells; every backtick reference
  resolves in its own manifest context; no import cycles (web is a leaf; the new root → web
  edge and the existing plugins → web edge point the same direction). One contract premise
  was verified empirically rather than assumed — see the `WebPlugin.web` trace.

## Entity Interaction and Data Flow

### Interaction Diagram

```
consumer test module (collection time)
  │  from goga_tool_pybuggy import generation_prompt      ← root facade re-export
  │  @generation_prompt("...")                            ← decoration: validate + mark
  ▼
root __init__.py ──► web/__init__.py ──► web/pretty.py::generation_prompt
                                                   │  pytest.mark.pybuggy_generation_prompt(text=…)
                                                   │  pytest.mark.usefixtures("web")
                                                   ▼
                                            test function (same object, marked)

pytest configphase
  plugins/web_plugin.py::WebPlugin.configure()
    1. addinivalue_line("markers", help)   ← marker registered (collection stays warning-free)
    2–10. document gates → activation (PrettyConfig) → env scrub → formatter

pytest test setup (per requesting test)
  plugins/web_plugin.py::WebPlugin.web(request)
    item.iter_markers("pybuggy_generation_prompt") ──► [bottom … top] (application order)
      reverse ──► written order (top first) ──► "\n".join ──► prompt_extra
    build_pretty_config(activation, strict, interactive, prompt_extra=extras)
      effective = "\n".join(non-empty(config.generation_prompt, prompt_extra))
      ──► PrettyConfig (every field explicit)
      ──► PrettyPlay(cache_key, cache_path, cleanup=False, config)
             ──► generation_prompt rides into the LLM prompt on a cache miss only
```

### Data Flows

- **Declaration flow** (collection time): `text: str` → `generation_prompt` validates
  (str, stripped non-empty) → stripped text → marker kwarg `text` → the item's mark list
  (application order: the bottom decorator's marker first) → `usefixtures("web")` stamp.
- **Read flow** (test setup): item markers → `WebPlugin.web` collects `text` kwargs →
  reversed to written order → single-newline join → `prompt_extra: str`.
- **Composition flow** (test setup): `config.generation_prompt` (from web.yml via the
  activation) + `prompt_extra` → non-empty parts joined single-newline → the constructed
  `PrettyConfig.generation_prompt` → adopted verbatim by `PrettyPlay` → the provider prompt
  at generation time (a cache miss; inert in `--strict-mode`).
- **Re-export flow** (import time): `web/pretty.py` → `web/__init__.py.__all__` → root
  `__init__.py.__all__` → consumer import `from goga_tool_pybuggy import generation_prompt`.

### Entity Dependencies

- `goga_tool_pybuggy/web` (leaf) defines both routines; depends only on `prettyplay`
  (+ `pytest` for the mark API — the same import the `services` decorator of
  `sandbox/data/presets.py` already makes).
- `goga_tool_pybuggy/plugins` → `goga_tool_pybuggy/web` (`build_pretty_config`,
  `install_event_log_formatter`, `AllureStepHooks`; unchanged set — the fixture gains a
  keyword argument at an existing import).
- `goga_tool_pybuggy` (root) → `goga_tool_pybuggy/web` (new edge: the `generation_prompt`
  re-export embedding; `pybuggy-web` imported usage).
- Implementation order: web (`pretty.py`, then the cell facade) → plugins (`web_plugin.py`)
  → root facade → tests. No cycles; `goga schema` confirms root deps include
  `goga_tool_pybuggy/web: types=[generation_prompt]`.

## Code Stack Trace

### Trace: `generation_prompt` (web/pretty.py)

#### Chain

1. **Input**: a consumer test module executes `@generation_prompt("…")` at import (pytest
   collection). The import resolves through the root facade → `web/__init__.py` →
   `web/pretty.py`.
2. **Step**: validate `text` — `isinstance(text, str)` and `text.strip()` non-empty; a
   non-string, empty, or whitespace-only value raises `ValueError` → checkpoint: contract
   algorithm step 1; the failure is visible at collection, before any browser or LLM ✓.
3. **Step**: compute `stripped = text.strip()` — the single normalization the surface
   performs (the fixture and `build_pretty_config` normalize nothing further) → checkpoint:
   the decorator owns stripping, per the plugins-cell constraint ✓.
4. **Step**: define and return the inner `_decorate(item)` closure → checkpoint: nothing
   executes at factory time beyond validation — pure declaration, no I/O, no plugin lookup,
   no config read ✓.
5. **Step**: inside `_decorate` — `pytest.mark.pybuggy_generation_prompt(text=stripped)(item)`
   appends the marker to the function's mark list; `pytest.mark.usefixtures("web")(marked)`
   appends the fixture stamp and returns **the same function object** → checkpoint: verified
   empirically on pytest 9.2.0 — `pytest.mark.*` application appends to `pytestmark` in call
   order and returns the identical object; stacking appends bottom-decorator-first ✓.
6. **Output**: the decorated test function — unmodified body, carrying the
   `pybuggy_generation_prompt(text=…)` marker and the `usefixtures("web")` stamp.

#### Checkpoint Summary

- Decoration-time validation: passed (ValueError before any runtime dependency).
- Marker/stamp attachment: passed (verified: same object, append order preserved).
- Marker-name agreement with the plugins cell (`pybuggy_generation_prompt`, kwarg `text`):
  passed (both manifests name both).
- Behavior without web.yml: passed — the declaration itself needs nothing registered
  (`pytest.mark.NAME` works unregistered; an unknown-mark warning may appear, the same
  property the `services` marker carries when its plugin is inactive); the failure arrives at
  setup as pytest's standard `fixture 'web' not found`, exactly as the usage docs state.

### Trace: `build_pretty_config` (web/pretty.py)

#### Chain

1. **Input**: `WebPlugin.web` calls
   `build_pretty_config(activation, self.strict, self.interactive, prompt_extra=extras)` —
   the activation is a validated `PrettyConfig`; `extras` is a possibly-empty str.
2. **Step**: `fields = config.model_dump()` — every model field, `generation_prompt: str`
   included (default `''`, per the `prettyplay` field table) → checkpoint: field exists in
   prettyplay 0.0.4 ✓.
3. **Step**: `browser = BrowserConfig(**fields.pop("browser"))` — unchanged.
4. **Step**: mode OR-forcing (`strict`, `interactive`) — unchanged → checkpoint: contract
   algorithm step 1 preserved ✓.
5. **Step**: compute the effective generation prompt —
   `"\n".join(part for part in (config.generation_prompt, prompt_extra) if part)` — and store
   into `fields["generation_prompt"]` → checkpoints:
   - document prompt + extras → `doc + "\n" + extras` (append semantics) ✓;
   - extras only → extras alone ✓;
   - document prompt only (extras `""`) → unchanged value — byte-identical to the previous
     behavior, the backward-compatibility requirement ✓;
   - both empty → `""` — the library default, and the all-fields materialization still sets
     every field explicitly (`model_fields_set` complete) ✓;
   - no normalization beyond the empty-part skip — the contract constraint ✓ (stripping
     already happened at decoration).
6. **Output**: `PrettyConfig(browser=browser, **fields)` — the complete effective settings;
   the runtime adopts it verbatim (`config=<PrettyConfig>` layer of prettyplay 0.0.4).

#### Checkpoint Summary

- Join semantics vs the three manifests and both usage docs: passed (single newline,
  document-first order, empty-part skip).
- All-fields materialization preserved: passed (the join replaces one field value; nothing
  leaves the constructor call).
- Purity: passed (no env, no pyproject, no I/O — single source is the passed model, flags,
  and extras).

### Trace: `WebPlugin.configure` (plugins/web_plugin.py)

#### Chain

1. **Input**: pluginator's injected `pytest_configure` calls `plugin.configure()` after
   `init_pytest_config` and pluginmanager registration — configphase, before collection.
2. **Step (new)**: `self.pytest_config.addinivalue_line("markers", _GENERATION_PROMPT_MARKER_HELP)`
   as the first statement → checkpoints:
   - the exact pattern of the sandbox plugin (`sandbox_plugin.py:75`,
     `_MARKER_HELP`); `pytest_config` is guaranteed initialized (pluginator calls configure
     only after `init_pytest_config`) ✓;
   - registration precedes the document gates: even when the document fails below, the line
     is registered (the run fails anyway — unobservable; and in every successful run the
     marker is registered before collection, so applying it in test modules is
     warning-free) ✓;
   - the help line names the marker with a one-line description, mirroring
     `"pybuggy_services: per-test sandbox data presets (applied by the pybuggy sandbox)"` ✓.
3. **Steps 2–10**: read the typed flags; parse/mapping/empty gates; foreign-section drop;
   unknown-key collection; endpoint authority; `PrettyConfig.model_validate` activation;
   mode re-store; `PRETTYPLAY_*` scrub; `install_event_log_formatter()` — all unchanged
   (verified against the current implementation; only the numbering shifted).
4. **Output**: activation set, marker registered, env scrubbed, formatter installed.

#### Checkpoint Summary

- Lifecycle fit: passed (configphase, single-threaded; registration is idempotent — pytest
  deduplicates nothing here, but configure runs once per plugin).
- Gate ordering: passed (registration is failure-independent).

### Trace: `WebPlugin.web` (plugins/web_plugin.py)

#### Chain

1. **Input**: pytest sets up a test requesting `web` (explicit parameter or the
   `usefixtures("web")` stamp of the decorator).
2. **Step**: `activation = self._require_activation()`; cache address from the item
   (`web_cache_path`, `item.name`) — unchanged.
3. **Step (new)**: collect the extras —
   `texts = [marker.kwargs.get("text", "") for marker in request.node.iter_markers("pybuggy_generation_prompt")]`,
   then `extras = "\n".join(text for text in reversed(texts) if text)` → checkpoints:
   - **marker order premise verified empirically** (pytest 9.2.0, the project's environment):
     `Node.iter_markers` yields `own_markers` in natural append order — for stacked
     decorators that is application order, the bottom decorator first
     (`@prompt("A")` over `@prompt("B")` yields `["B", "A"]`); `reversed` restores the
     written order (`["A", "B"]`, top first). The manifest's premise — "the bottom
     decorator's marker lands first in the item's mark list — reverse it to the order
     written" — is factually correct on this pytest line ✓. (Historical note for the
     implementer: pytest <9 reversed `own_markers` inside `iter_markers`; the explicit
     `reversed` here targets the current, natural-order semantics the contract pins.)
   - `iter_markers` is the sandbox-pattern read (`sandbox_plugin.py:148`), filters by name,
     and includes parent-scoped occurrences — harmless and consistent ✓;
   - `.get("text", "")` is defensive only: the decorator always attaches the kwarg; a
     hand-written `pytest.mark.pybuggy_generation_prompt` without `text` contributes
     nothing (skipped by the truthiness filter) instead of crashing the join ✓;
   - skipping empty strings is not text normalization — it is the join's part selection;
     the texts themselves pass through untouched (constraint honored) ✓;
   - no markers → `extras == ""` — "a test without the markers yields the empty string" ✓.
4. **Step**: `config = build_pretty_config(activation, self.strict, self.interactive,
   prompt_extra=extras)` → checkpoint: keyword form against the new defaulted parameter;
   type str ✓ (Trace: build_pretty_config).
5. **Step**: `cache_root` item-root override via `model_copy(update=…)` when the activation
   carries none → checkpoint: `model_copy` preserves every field — the computed
   `generation_prompt` survives the copy ✓.
6. **Step**: `PrettyPlay(item.name, web_cache_path(item), cleanup=False, config=config)`;
   guarded allure hooks; enter/yield/close — unchanged.
7. **Output**: the opened per-test runtime whose config carries the per-test effective
   generation prompt; the activation and the plugin options are never touched (locals only).

#### Checkpoint Summary

- Type flow decorator → fixture → builder: passed (`text` kwarg str → extras str →
  `prompt_extra` str → `PrettyConfig.generation_prompt` str).
- Per-test isolation: passed (no shared state mutation; the second decorated test in a run
  rebuilds its own config).
- Order semantics: passed (empirically verified premise; written order guaranteed).

### Trace: root facade re-export (`goga_tool_pybuggy/__init__.py`)

#### Chain

1. **Input**: consumer executes `from goga_tool_pybuggy import generation_prompt`.
2. **Step**: root `__init__.py` — `from .web import generation_prompt` (after the `.tools`
   import, the last line — alphabetical by module:
   `cli < env < lifecycle < reg_hooks < sandbox.data < tools < web`) and
   `"generation_prompt"` in `__all__` (alphabetical: between `EnvContext` and `install`)
   → checkpoint: the `services` re-export pattern (`from .sandbox.data import services`)
   followed exactly ✓.
3. **Step**: `web/__init__.py` — `from .pretty import build_pretty_config, generation_prompt`
   (or a separate import line) and `"generation_prompt"` in `__all__`; the module docstring
   names the declaration surface → checkpoint: the cell facade is the re-export hop the root
   embedding requires ✓.
4. **Output**: `goga_tool_pybuggy.generation_prompt is
   goga_tool_pybuggy.web.pretty.generation_prompt` — the identity the facade test asserts.

#### Checkpoint Summary

- Import direction: passed (root → web one-way; no cycle).
- Facade check command (conventions): `python -c "from goga_tool_pybuggy import generation_prompt"`.

## Algorithm Design

### `generation_prompt` (web/pretty.py)

**Responsibility**: the per-test generation-instruction declaration surface — validate the
text, attach the marker, stamp the fixture; execute nothing.

**Algorithm:**
```
1. IF NOT isinstance(text, str) OR text.strip() == "":
   - raise ValueError("generation_prompt text must be a non-empty, non-whitespace-only string")
2. stripped = text.strip()
3. DEFINE _decorate(item):
   a. marked = pytest.mark.pybuggy_generation_prompt(text=stripped)(item)
      → appends the marker (application order: bottom decorator first when stacked)
   b. RETURN pytest.mark.usefixtures("web")(marked)
      → appends the fixture stamp; returns the same function object
4. RETURN _decorate
```

**Errors:**
- `ValueError` → raised at decoration (collection time) for a non-string / empty /
  whitespace-only `text` → the consumer sees the failure before any browser or LLM starts.

**Edge Cases:**
- Stacked application → each application validates independently and attaches its own marker;
  duplicates of the same text are preserved (two identical markers → the text joins twice).
- Applied to a non-test callable → harmless: the marks sit on the function; pytest simply
  never collects it.
- Function already carrying other marks → append-only; existing marks untouched.

### `build_pretty_config` (web/pretty.py)

**Responsibility**: the single construction point of the prettyplay settings layer — now
including the per-test effective generation prompt.

**Algorithm:**
```
1. fields = config.model_dump()                    → every field, browser group included
2. browser = BrowserConfig(**fields.pop("browser"))
3. fields["strict"]      = config.strict      or strict_flag
   fields["interactive"] = config.interactive or interactive_flag
   → a flag forces its mode on, never off (unchanged)
4. fields["generation_prompt"] = "\n".join(
       part for part in (config.generation_prompt, prompt_extra) if part)
   → document prompt first, extras second, single newline; empty parts skipped;
     both empty → "" (the library default, still set explicitly)
5. RETURN PrettyConfig(browser=browser, **fields)   → adopted verbatim by the runtime
```

**Errors:**
- None new — pydantic constructor errors remain impossible here (every value comes from a
  validated model or is a str join).

**Edge Cases:**
- `prompt_extra=""` (default or no markers) → output identical to the pre-change behavior —
  the backward-compatibility requirement.
- Only extras, empty document prompt → the extras are the whole prompt.
- Multi-line texts inside a single decorator → preserved verbatim (no re-wrapping; the strip
  at decoration removed only the outer whitespace).

### `WebPlugin.configure` (plugins/web_plugin.py)

**Responsibility**: configphase composition — now preceded by the marker registration.

**Algorithm (the new step; 2–10 unchanged):**
```
1. self.pytest_config.addinivalue_line("markers",
       "pybuggy_generation_prompt: per-test extra generation instructions "
       "(applied by the pybuggy web plugin)")
   → first statement; before the parse guard and every gate
```

**Errors:**
- None from the registration itself. Every later gate failure (unparsable / non-mapping /
  empty / invalid document) behaves exactly as before — the marker line is already
  registered, which is unobservable in a failing run.

**Edge Cases:**
- Repeated configure → cannot happen (pluginator calls it once); `addinivalue_line` is
  append-only and cheap regardless.

### `WebPlugin.web` (plugins/web_plugin.py)

**Responsibility**: the per-test runtime build — now parameterized by the requesting test's
declared prompt extras.

**Algorithm (steps 1–6; the new step 2 in place):**
```
1. activation = self._require_activation()
   root = activation.cache_root or str(item.path.parent.resolve())
2. texts = [marker.kwargs.get("text", "") 
            for marker in request.node.iter_markers("pybuggy_generation_prompt")]
   extras = "\n".join(text for text in reversed(texts) if text)
   → written order (top decorator first); "" when no markers
3. config = build_pretty_config(activation, self.strict, self.interactive,
                                prompt_extra=extras)
4. IF NOT activation.cache_root:
   - config = config.model_copy(update={"cache_root": root})
5. runtime = PrettyPlay(item.name, web_cache_path(item), cleanup=False, config=config)
   IF allure is importable: runtime.add_hooks(AllureStepHooks(runtime))
6. WITH runtime AS play: YIELD play   → close on finalization
```

**Errors:**
- `RuntimeError` (unchanged) when configure never ran — the extras step sits after
  `_require_activation`, so the failure semantics are unchanged.
- No marker-driven errors: the collection is total (`.get` default) and the join cannot
  fail on strings.

**Edge Cases:**
- A marker without the `text` kwarg (hand-written mark) → contributes nothing.
- Marketers on parametrized tests → each item carries the same function-level markers; every
  parameter case gets the same extras (the cache key differs, the prompt does not).

### Root/cell facades (`goga_tool_pybuggy/__init__.py`, `goga_tool_pybuggy/web/__init__.py`)

**Responsibility**: the re-export chain of the embedding `->generation_prompt: {}`.

**Algorithm:**
```
web/__init__.py:
  from .pretty import build_pretty_config, generation_prompt
  __all__ = [..., "generation_prompt", ...]        # alphabetical slot
  docstring: name the per-test generation-prompt declaration surface

root __init__.py:
  from .web import generation_prompt               # last line, after from .tools import retries
  __all__ = [..., "generation_prompt", ...]        # between EnvContext and install
```

**Edge Cases:** none — pure re-export, import-time only, no behavior.

## Cross-cutting Concerns

- **Error handling**: the only new error is the decoration-time `ValueError` (early, loud,
  names the requirement). The fixture and the builder are total — they never fail on
  marker-shaped input. Existing configure-time document errors are unchanged.
- **Validation**: decoration time (type + stripped non-emptiness, the single normalization);
  configphase document validation unchanged; no validation is added to the read path (the
  decorator guarantees the shape; the `.get` default keeps the fixture total).
- **Logging**: no new log lines. The existing fixture `debug` ("web runtime built", extras
  `cache_key`/`cache_root`) is unchanged; the prompt text itself is deliberately not logged
  (it already reaches provider prompts and the repository per the documented contract —
  log lines would only duplicate the surface).
- **Caching**: the effective prompt participates only in generation (a cache miss); cached
  steps replay without any prompt read. Changing a decorator text never invalidates cache
  files — regeneration requires deleting the step's file (documented in both usage docs).
  In `--strict-mode` the whole surface is inert: zero LLM calls, the prompt is still
  composed but never consumed.
- **Concurrency**: configphase registration is single-threaded; the fixture's marker read is
  per-test and read-only. No shared mutable state is introduced.
- **Security**: the no-secrets rule extends to the decorator text — it lands in LLM prompts
  and logs exactly like step sentences (stated in all three docs and both manifests).

## Usages Analysis

### `conventions`
- **What it provides**: Python code rules — relative imports, pydantic models, Google-style
  docstrings, logging discipline, test structure (`tests/<pkg>/test_<module>.py`),
  mock policy, the facade check command.
- **Where used**: `generation_prompt` (docstrings, type hints, testing), `build_pretty_config`
  (type hints), the facades, and every test file in the registry below.
- **Why chosen**: the project-wide mandatory baseline.
- **How exactly**: `t.Callable[..., t.Any]` return type; `Args`/`Returns`/`Raises` docstring
  sections; module-level routines; tests mirror `goga_tool_pybuggy/web/pretty.py` →
  `tests/web/test_pretty.py`.

### `prettyplay`
- **What it provides**: the `PrettyConfig` field table (incl. `generation_prompt: str,
  default ''`), the explicit-layer verbatim adoption, `PrettyPlay` construction, the
  security rules.
- **Where used**: `generation_prompt` (the field the text rides on; the no-secrets rule),
  `build_pretty_config` (the field contract, the verbatim adoption), `WebPlugin.web` (the
  runtime construction), `WebPlugin.configure` (the env layer the scrub neutralizes).
- **Why chosen**: the library whose settings layer this feature extends.
- **How exactly**: the join lands in `PrettyConfig.generation_prompt`; the runtime receives
  the model through `config=` — verbatim, pyproject/env never back-fill it.

### `pluginator`
- **What it provides**: the `configure()` lifecycle (configphase, after
  `init_pytest_config`), `pytest_config` access, fixtures as plugin-class methods.
- **Where used**: `WebPlugin.configure` (the registration point), `WebPlugin.web` (the
  fixture-as-method convention).
- **Why chosen**: the marker registration needs an initialized pytest config — exactly what
  the lifecycle guarantees.
- **How exactly**: `self.pytest_config.addinivalue_line("markers", help)` — the sandbox
  plugin's proven pattern at the same lifecycle point.

### `allure-pytest`
- **What it provides**: the guarded allure import governing the hook attachment.
- **Where used**: `WebPlugin.web` step 5 (unchanged by this change).
- **Why chosen / how**: unchanged; listed because the fixture annotation now numbers the
  step inside the merged step 5.

### Imported Usages
- `pybuggy-web` from `goga_tool_pybuggy/web` (consumed by `goga_tool_pybuggy/plugins` and
  re-imported by the root) — the consumer patterns of the web test kind, now including the
  decorator section. Path: `goga_tool_pybuggy/web/.usages/pybuggy-web.md`.
  - The plugins cell references it on `install` and in global Annotations (consumer
    patterns); the root references it as the connected capability practice of the new
    embedding. Traceable cross-cell links; no contractual obligations cross the boundary.

## `.usages/` Update

### Cell: `goga_tool_pybuggy/web`

#### Existing Files — Consistency
- **`pybuggy-web.md`** → `goga_tool_pybuggy/web/.usages/pybuggy-web.md`
  - Status: **current** — the new «Per-test extra instructions» section (present in the
    working tree) matches the materialized contract: root import, append semantics, stacking
    order, early validation, the automatic web runtime, no-secrets, cache/strict inertness.
  - Additions needed: none.
  - Updates needed: none.

### Cell: `goga_tool_pybuggy`

#### Existing Files — Consistency
- **`assembly.md`** → `goga_tool_pybuggy/.usages/assembly.md`
  - Status: **current** — the final paragraph names both capability re-exports
    (`services`, `generation_prompt`) with both import forms.
  - Additions needed / Updates needed: none.

### Cell: `goga_tool_pybuggy/plugins`

No `.usages/` changes — per the applied architecture plan, the plugins cell's consumer
practices for the web kind live in the web cell's `pybuggy-web.md`.

## Test Stack Trace

### General Setup

- Unit tests are mock-free (pure logic); the plugin tests reuse the existing doubles of
  `tests/plugins/test_web_plugin.py`:
  - `_FakePytestConfig` — already records `addinivalue_line` calls in `.lines`; serves the
    typed flags.
  - `_wire_recording_prettyplay` — patches the module's `PrettyPlay` seam; the built config
    is inspectable at `made[0].config`.
  - `_configured_plugin(monkeypatch, document=…, config=…)` — drives a plugin through
    `configure`.
  - `_request_for(path, name, originalname=None)` — **extend with a `markers: list[pytest.Mark]
    | None = None` parameter**: the node double **always** carries
    `item.iter_markers = lambda name_: [m for m in (markers or []) if m.name == name_]`
    (the collected order the double serves is the collection order the fixture receives;
    `markers is None` serves the empty list, so every existing fixture test keeps working
    without an `AttributeError`). Build marks with
    `pytest.mark.pybuggy_generation_prompt(text=…).mark` (the `Mark` object carries
    `.name`/`.kwargs`).
- `allure` is forced absent (`monkeypatch.setattr(allure_hooks_module, "allure", None)`)
  in fixture tests — the hook branch is out of scope here.

### Source File Registry

- `goga_tool_pybuggy/web/pretty.py` — `generation_prompt` (new), `build_pretty_config`
  (changed).
- `goga_tool_pybuggy/web/__init__.py` — the cell facade re-export.
- `goga_tool_pybuggy/plugins/web_plugin.py` — `WebPlugin.configure` (new step 1),
  `WebPlugin.web` (new step 2).
- `goga_tool_pybuggy/__init__.py` — the root facade re-export.
- `pyproject.toml` — the test dependency floor bump (`pytest>=8.0` → `pytest>=9.0`) pinning
  the marker-order semantics the fixture's `reversed` relies on.
- Test files: `tests/web/test_pretty.py`, `tests/plugins/test_web_plugin.py`,
  `tests/test_facade.py`.

---

### Positive Tests

#### `test_generation_prompt_is_module_level_callable`

**Setup**: none (pure import).

**Input**: the `goga_tool_pybuggy.web.pretty` module.

**Trace**:
```
import goga_tool_pybuggy.web.pretty as pretty_module
  → assert callable(pretty_module.generation_prompt)   # entry point exists
  → from goga_tool_pybuggy.web.pretty import generation_prompt
  → assert generation_prompt.__module__ == "goga_tool_pybuggy.web.pretty"
```

**Assertions**:
```
callable(pretty_module.generation_prompt) is True
generation_prompt.__module__ == "goga_tool_pybuggy.web.pretty"
```

**Sufficiency**: pins the contract location (`pretty.py`, module-level) — the facade chain
and the CODEMANIFEST `location` depend on it.

---

#### `test_generation_prompt_attaches_marker_with_stripped_text`

**Setup**: none.

**Input**: `generation_prompt("  Dates render as DD.MM.YYYY.  ")` applied to a plain
function `def sample(): ...`.

**Trace**:
```
decorator = generation_prompt("  Dates render as DD.MM.YYYY.  ")
  → validation passes (str, stripped non-empty)
  → stripped = "Dates render as DD.MM.YYYY."
decorator(sample)
  → pytest.mark.pybuggy_generation_prompt(text=stripped)(sample)   # marker appended
  → pytest.mark.usefixtures("web")(marked)                          # stamp appended
  → returns the same function object
marks = [m for m in sample.pytestmark if m.name == "pybuggy_generation_prompt"]
```

**Assertions**:
```
len(marks) == 1
marks[0].kwargs == {"text": "Dates render as DD.MM.YYYY."}
any(m.name == "usefixtures" for m in sample.pytestmark) is True
```

**Sufficiency**: the marker contract (name + `text` kwarg + stripping) and the fixture
stamp — the two halves every downstream consumer reads.

---

#### `test_generation_prompt_returns_function_unchanged`

**Setup**: none.

**Input**: `generation_prompt("A")` applied to a function object `sample`.

**Trace**:
```
decorated = generation_prompt("A")(sample)
  → both mark applications append in place and return the same object
```

**Assertions**:
```
decorated is sample
callable(decorated) is True
```

**Sufficiency**: pins "Return the function unchanged / do not wrap" — prevents a wrapper
implementation that would break pytest's identity-sensitive machinery (e.g. parametrize
name resolution).

---

#### `test_generation_prompt_stacks_attaching_own_markers_in_written_order`

**Setup**: none.

**Input**:
```
inner  = generation_prompt("Dates render as DD.MM.YYYY.")(sample)   # applied first
outer  = generation_prompt("The #country dropdown is a native <select>.")(inner)
```

**Trace**:
```
inner application  → pytestmark gains {text: "Dates render as DD.MM.YYYY."}       (first)
outer application  → pytestmark gains {text: "The #country dropdown …"}            (second)
texts = [m.kwargs["text"] for m in sample.pytestmark if m.name == "pybuggy_generation_prompt"]
```

**Assertions**:
```
texts == ["Dates render as DD.MM.YYYY.", "The #country dropdown is a native <select>."]
```

**Sufficiency**: pins the attach order (application order, bottom first) — the premise the
fixture's `reversed` relies on; a reordering here or there silently flips the joined prompt.

---

#### `test_build_pretty_config_prompt_extra_appends_to_document_prompt`

**Setup**: `config = PrettyConfig.model_validate({"provider": "openai",
"generation_prompt": "global instructions", "browser": {"name": "chromium"}})`.

**Input**: `build_pretty_config(config, False, False, prompt_extra="per-test quirk")`.

**Trace**:
```
build_pretty_config(config, False, False, "per-test quirk")
  → model_dump() → generation_prompt="global instructions"
  → join(["global instructions", "per-test quirk"], "\n")
  → PrettyConfig(generation_prompt="global instructions\nper-test quirk", …)
```

**Assertions**:
```
result.generation_prompt == "global instructions\nper-test quirk"
```

**Sufficiency**: the headline semantics — the decorator appends to the web.yml baseline for
this test only, document first.

---

#### `test_build_pretty_config_prompt_extra_alone_when_document_prompt_empty`

**Setup**: `config = PrettyConfig.model_validate({"provider": "openai"})` (default
`generation_prompt=""`).

**Input**: `build_pretty_config(config, False, False, prompt_extra="only extras")`.

**Trace**:
```
join(("", "only extras")) → skips the empty part → "only extras"
```

**Assertions**:
```
result.generation_prompt == "only extras"
```

**Sufficiency**: the empty-part skip — a project without a global prompt still gets the
per-test instructions, with no leading newline.

---

#### `test_build_pretty_config_without_prompt_extra_keeps_document_prompt`

**Setup**: `config = PrettyConfig.model_validate({"provider": "openai",
"generation_prompt": "global instructions"})`.

**Input**: `build_pretty_config(config, True, False)` (positional call, no fourth argument).

**Trace**:
```
prompt_extra defaults to "" → join(["global instructions"]) → "global instructions"
```

**Assertions**:
```
result.generation_prompt == "global instructions"
result.strict is True        # the OR forcing still works alongside
```

**Sufficiency**: backward compatibility — every pre-existing call site (and the default
path of the fixture) builds exactly the config it built before.

---

#### `test_build_pretty_config_both_prompts_empty_keeps_library_default`

**Setup**: `config = PrettyConfig.model_validate({"provider": "openai"})`.

**Input**: `build_pretty_config(config, False, False)`.

**Trace**:
```
join(("", "")) → no parts → ""
```

**Assertions**:
```
result.generation_prompt == ""
result.model_fields_set == set(PrettyConfig.model_fields)   # all-fields materialization intact
```

**Sufficiency**: the load-bearing explicit construction must survive the new field
computation — an implementation that skipped setting the field would break the verbatim
adoption guarantee.

---

#### `test_configure_registers_the_generation_prompt_marker`

**Setup**: `config = _FakePytestConfig()`; `_configured_plugin(monkeypatch, config=config)`.

**Input**: the configured plugin's fake pytest config.

**Trace**:
```
plugin.configure()
  → addinivalue_line("markers", help) recorded in config.lines
  → document gates pass (VALID_DOCUMENT)
```

**Assertions**:
```
any(name == "markers" and "pybuggy_generation_prompt" in line for name, line in config.lines) is True
plugin.activation is not None
```

**Sufficiency**: the registration requirement — applying the decorator's marker in test
modules stays warning-free whenever the plugin is active.

---

#### `test_configure_registers_the_marker_before_the_document_gates`

**Setup**: `plugin = WebPlugin(context={})` with `plugin_config` monkeypatched to an
unparsable-shaped invalid document `{"provider": "nope"}`; `config = _FakePytestConfig()`;
`plugin.init_pytest_config(config)`.

**Input**: `plugin.configure()` (expected to raise).

**Trace**:
```
configure()
  → addinivalue_line recorded                                  (step 1 — first)
  → PrettyConfig.model_validate fails → ValueError raised      (step 7)
```

**Assertions**:
```
pytest.raises(ValueError, match="web\\.yml: invalid web config document")
any(name == "markers" for name, _ in config.lines) is True
```

**Sufficiency**: pins the algorithm's step order — the registration precedes the gates, so
it is unconditional in every run that reaches configure.

---

#### `test_web_fixture_collects_prompt_extras_in_written_order`

**Setup**: `plugin = _configured_plugin(monkeypatch)` (document without
`generation_prompt`); `made = _wire_recording_prettyplay(monkeypatch)`; allure forced
absent; request double with markers served in collection order
`[mark(text="bottom text"), mark(text="top text")]` (bottom decorator first).

**Input**: `next(WebPlugin.web.__wrapped__(plugin, request))`.

**Trace**:
```
web.__wrapped__(plugin, request)
  → iter_markers("pybuggy_generation_prompt") → ["bottom text", "top text"]  (natural order)
  → reversed → ["top text", "bottom text"]                                   (written order)
  → join → "top text\nbottom text"
  → build_pretty_config(activation, strict, interactive, prompt_extra="top text\nbottom text")
  → PrettyPlay(…, config=config)
```

**Assertions**:
```
made[0].config.generation_prompt == "top text\nbottom text"
made[0].cleanup is False
made[0].cache_key == "test_a"
```

**Sufficiency**: the ordering contract — the stacked texts apply top-to-bottom in the order
written; guards against the double-reversal regression (pytest 9 already yields natural
order; an implementer copying an old `iter_markers`-reverses assumption would flip it).

---

#### `test_web_fixture_appends_extras_to_the_document_prompt`

**Setup**: `plugin = _configured_plugin(monkeypatch, document={"provider": "openai",
"generation_prompt": "global instructions", "browser": {"name": "chromium"}})`; recording
PrettyPlay; request markers `[mark(text="extra two"), mark(text="extra one")]` in collection
order (the bottom decorator first — the collection order of `@generation_prompt("extra one")`
stacked over `@generation_prompt("extra two")`).

**Input**: `next(WebPlugin.web.__wrapped__(plugin, request))`.

**Trace**:
```
texts = ["extra two", "extra one"]     (collection order: bottom decorator first)
extras = "extra one\nextra two"        (reversed → written order, top first)
build_pretty_config(…, prompt_extra=extras)
  → "global instructions\nextra one\nextra two"
```

**Assertions**:
```
made[0].config.generation_prompt == "global instructions\nextra one\nextra two"
```

**Sufficiency**: the end-to-end composition — web.yml baseline plus decorator extras in one
newline-joined string.

---

#### `test_web_fixture_without_markers_builds_the_unchanged_config`

**Setup**: `plugin = _configured_plugin(monkeypatch)` (document without
`generation_prompt`); recording PrettyPlay; request double **without** markers.

**Input**: `next(WebPlugin.web.__wrapped__(plugin, request))`.

**Trace**:
```
iter_markers yields nothing → extras = ""
build_pretty_config(activation, strict, interactive, prompt_extra="")
  → generation_prompt == "" (the default)
```

**Assertions**:
```
made[0].config.generation_prompt == plugin.activation.generation_prompt == ""
made[0].config.provider == "openai"
```

**Sufficiency**: the per-test isolation requirement — an undecorated test builds exactly the
config it built before this feature existed (no cross-test prompt leakage, no behavior
drift).

---

#### `test_facade_reexports_generation_prompt`

**Setup**: none (pure import).

**Input**: the root and web facades.

**Trace**:
```
import goga_tool_pybuggy
from goga_tool_pybuggy import generation_prompt
from goga_tool_pybuggy.web.pretty import generation_prompt as cell_entity
```

**Assertions**:
```
callable(generation_prompt) is True
generation_prompt is cell_entity
"generation_prompt" in goga_tool_pybuggy.__all__
"generation_prompt" in goga_tool_pybuggy.web.__all__
```

**Sufficiency**: the embedding `->generation_prompt: {}` — the consumer import surface
(`from goga_tool_pybuggy import generation_prompt`) promised by both usage docs.

---

### Negative Tests

#### `test_generation_prompt_rejects_invalid_text` (parametrized)

**Setup**: none.

**Input** (parametrize table): `123` (non-string), `None` (null), `""` (empty), `"   "`
(whitespace-only), `"\n\t"` (whitespace-only, escaped forms).

**Trace**:
```
generation_prompt(<invalid>)
  → isinstance/strip check fails (None and 123 fail the isinstance branch before .strip())
  → raise ValueError
```

**Assertions**:
```
with pytest.raises(ValueError, match="generation_prompt"):
    generation_prompt(<invalid>)
```

**Sufficiency**: the early-validation contract — a mistyped decorator argument fails at
collection, before any browser or LLM; prevents silent no-op declarations. `None` covers the
mandatory empty-input edge of `conventions` and guards a validation rewritten so that `None`
escapes with an `AttributeError` on `.strip` instead of the `ValueError`.

---

### Edge Case Tests

#### `test_web_fixture_ignores_a_marker_without_the_text_kwarg`

**Setup**: configured plugin + recording PrettyPlay; request markers served as
`[mark_without_kwargs]` (a `pybuggy_generation_prompt` Mark with empty `kwargs`) followed by
`[mark(text="real text")]` in collection order.

**Input**: `next(WebPlugin.web.__wrapped__(plugin, request))`.

**Trace**:
```
texts = ["", "real text"] → reversed → ["real text", ""] → filter → ["real text"]
extras = "real text"
```

**Assertions**:
```
made[0].config.generation_prompt == "real text"
```

**Sufficiency**: the defensive `.get` — a hand-written `pytest.mark.pybuggy_generation_prompt`
without `text` must not crash the fixture setup nor blank the real declarations.

---

#### `test_generation_prompt_double_application_preserves_both_texts`

**Setup**: none.

**Input**: `generation_prompt("same text")` applied twice around one function.

**Trace**:
```
two applications → two markers, each {"text": "same text"}
fixture side (covered above) → join → "same text\nsame text"
```

**Assertions**:
```
texts = [m.kwargs["text"] for m in sample.pytestmark if m.name == "pybuggy_generation_prompt"]
texts == ["same text", "same text"]
```

**Sufficiency**: duplicates are preserved, not deduplicated — the decorator is a pure
declaration accumulator; silent dedup would hide a copy-paste error.

---

## Additional Instructions for the Implementation Agent

- Implement in the order web → plugins → root facade → tests (the import direction); the
  final gate is `pytest tests/ -x` plus the facade smoke check
  `python -c "from goga_tool_pybuggy import generation_prompt"`.
- `web/pretty.py` gains `import pytest` and `import typing as t` — the exact import shape of
  `sandbox/data/presets.py` (pytest arrives transitively via `pytest-concurrency`; the
  `services` precedent already relies on it).
- Keep the marker name literal `pybuggy_generation_prompt` in both cells (the web-cell
  decorator and the plugins-cell registration/read) — cells do not share private constants;
  the name is contract-fixed, the sandbox pattern writes it the same way.
- In the plugins cell define the help line once as a module-level `t.Final` constant next to
  the existing `_PRETTYPLAY_ENV_PREFIX` — mirroring `sandbox_plugin._MARKER_HELP`.
- Call `build_pretty_config` from the fixture with the keyword form
  (`prompt_extra=extras`) — the parameter is positional-or-keyword, but the keyword form
  keeps the call site self-documenting against future parameters.
- Update the two module docstrings you touch (`web/pretty.py`, `web/__init__.py`) — mention
  the declaration surface in one sentence each; do not restate the algorithm (the
  CODEMANIFEST owns it).
- Do not touch `WebConfigKeys` (the key set is fixed — no new config keys), the option
  declarations, or the configure gates beyond inserting step 1.
- The existing `_request_for` double in `tests/plugins/test_web_plugin.py` must gain the
  `markers` parameter and **always serve `iter_markers`** (empty when `markers is None`; see
  General Setup) — without it the new fixture step breaks every existing fixture test with
  an `AttributeError`.
- Docstring style: Google sections (`Args`/`Returns`/`Raises`), first line capitalized and
  ending with a period — per `conventions`.
- The written-order semantics of the marker collection pins pytest 9 — `iter_markers` yields
  `own_markers` in natural append order there, while pytest <9 reversed them inside
  `iter_markers` (the explicit `reversed` targets the current semantics): the test dependency
  floor in `pyproject.toml` is bumped `pytest>=8.0` → `pytest>=9.0` as part of this change.
