# Plan: `web-generation-prompt`

<!-- topic: .goga/history/2026/web-generation-prompt/ — the per-test `generation_prompt` decorator -->

## Purpose

After implementation, the package provides the per-test generation-instruction declaration
surface for web tests: the `generation_prompt(text)` decorator (the `services`-decorator
pattern of the sandbox kind) attaches the `pybuggy_generation_prompt` marker and a
`usefixtures("web")` stamp to a test function; the web plugin registers the marker at
configphase and the `web` fixture collects the marked texts (written order), joins them with a
single newline, and appends them to the document `generation_prompt` of exactly the requesting
test via the new `prompt_extra` parameter of `build_pretty_config`. The root facade re-exports
the decorator next to `services`, so consumers write
`from goga_tool_pybuggy import generation_prompt`.

The most important gaps between contract and code:

- `goga_tool_pybuggy/web/pretty.py` has no `generation_prompt` routine; `build_pretty_config`
  has no `prompt_extra` parameter and no effective-prompt join step.
- `WebPlugin.configure()` does not register the `pybuggy_generation_prompt` marker;
  `WebPlugin.web()` does not collect marker texts.
- Neither facade (`web/__init__.py`, root `__init__.py`) re-exports `generation_prompt`.
- 17 design test scenarios have no coverage.
- **No virtualenv with the project dependency set exists in this workspace** — the toolchain
  must be created before anything can be evaluated (verified: the base interpreter has only
  pytest 9.2.0; the `/opt/goga` venv lacks pytest/prettyplay/pluginator; PyPI is reachable and
  `prettyplay`'s `PrettyConfig` carries the `generation_prompt: str` field, default `""`).

Strategy: implement leaf → root (`web` cell → `plugins` cell → root facade → final gate),
each package's coding tasks completed before the next, every coding task following the ralphex
TDD protocol (steps 0–8) with a REPL checkpoint inside it. The three `CODEMANIFEST` files, the
`.usages/` practice files, and `docs/web/configuration.md` are **already materialized in the
working tree** (the design stage applied the contract side) — they are read-only inputs here.
`pyproject.toml` already carries the `pytest>=9.0` floor — verify, do not modify.

## Mandatory Rules

> Extracted from the project convention `.goga/usages/conventions.md` (referenced as
> `conventions` by all three manifests) — R1–R3. R4 (the REPL cycle) is the ralphex execution
> protocol of this plan, equally binding on every coding task. **These rules are mandatory for
> every task.** A task
> is not complete unless its output satisfies all of them. Precedence when anything conflicts:
> the CODEMANIFEST contract first, the cell/facade boundaries second, these conventions next,
> language idioms last.

### R1. Coding Style Rules (strictly per `conventions`)

1. Python 3.10+ compatible code only; `pyproject.toml` is the single configuration source.
2. **All code execution happens inside the project virtualenv** (`/workspace/.venv`, created by
   Task 1) — every python/pytest/ruff invocation below uses the `.venv/bin/...` prefix. Create
   the venv if it is missing.
3. Imports: **relative** for all intra-package references; **absolute** only for stdlib and
   third-party (e.g. `import pytest`, `import typing as t`, `from prettyplay import ...`).
4. Type hints are mandatory on every public signature. Decorator factories return
   `t.Callable[..., t.Any]`. No `*args`/`**kwargs` and no ungenerified `list`/`dict` in
   signatures.
5. Naming: PascalCase for classes; snake_case for functions, methods, and properties.
6. Docstrings — **Google style**, mandatory on every public function/method/class: first line
   capitalized and ending with a period; `Args` / `Returns` / `Raises` sections as applicable;
   brief, professional, one point per comment. Do not restate the CODEMANIFEST algorithm in
   prose — the manifest owns it.
7. Logging: the `logging` library with module-level `logger = logging.getLogger(__name__)`;
   lowercase messages with structured `extra={...}` metadata. Secrets never appear in logs —
   the decorator text lands in LLM prompts and logs exactly like step sentences: the
   no-secrets rule extends to it (do not add log lines that print prompt texts).
8. Code formatting: inside function/method bodies, logical blocks are separated by **one blank
   line** (variable initialization vs conditions/loops, data preparation vs processing,
   processing vs return).
9. Data models are pydantic with `kw_only=True` and empty defaults — **this plan introduces no
   new models**; do not create any.

### R2. Test Writing Rules (strictly per `conventions`)

1. Tests mirror the source structure directly:
   `goga_tool_pybuggy/web/pretty.py` → `tests/web/test_pretty.py`,
   `goga_tool_pybuggy/plugins/web_plugin.py` → `tests/plugins/test_web_plugin.py`,
   root facade → `tests/test_facade.py`. Every test directory carries `__init__.py`
   (already present). **No new test files or packages beyond these three.**
2. Naming: files `test_<module>.py`; functions `test_<what>_<scenario>`; grouping
   `class Test<Component>:` — extend the existing classes.
3. Unit tests of pure logic are **mock-free**. Doubles only at external boundaries: reuse the
   established doubles of `tests/plugins/test_web_plugin.py` (`_FakePytestConfig`,
   `_wire_recording_prettyplay`, `_configured_plugin`, `_request_for`); the fixture tests
   force allure absent (`monkeypatch.setattr(allure_hooks_module, "allure", None)`).
4. Edge coverage is mandatory: empty inputs (`None`, `""`), invalid types, expected
   exceptions via `pytest.raises`; boundary/invalid-value tables via
   `@pytest.mark.parametrize`.
5. Self-documenting test names; one short docstring line per test stating the pinned behavior;
   comments minimal.
6. Test libraries stay declared under `[project.optional-dependencies] test` — already
   satisfied; do not edit `pyproject.toml`.
7. When tests and implementation disagree, **fix the implementation, not the test** (the tests
   below are contract-derived).

### R3. Lint and Format Enforcement (all development stages and local commits)

- The single linter/formatter is **ruff**, configured in `pyproject.toml`
  (`[tool.ruff]`: `target-version = "py310"`, `line-length = 120`; lint select
  `E,W,F,I,N,UP,B,SIM,PL,PLR,C4,DTZ,PT,ARG,RUF,PTH,C90`, mccabe `max-complexity = 10`;
  format: double quotes, LF line endings, magic trailing comma kept).
- Every task ends with, over the paths it touched (at minimum
  `goga_tool_pybuggy/web goga_tool_pybuggy/plugins tests/`):
  - `.venv/bin/ruff check <paths>` — zero findings;
  - `.venv/bin/ruff format --check <paths>` — clean (run `.venv/bin/ruff format <paths>` when
    it reports drift, then re-check).
- Import order (isort, rule `I`) is **contract-relevant**: the new import-line positions
  pinned in the tasks are exactly what `ruff check` expects — do not reorder.
- **Local commit gate (every stage)**: no local commit is made unless (a) `ruff check` is
  clean over the changed paths, (b) `ruff format --check` is clean over the changed paths,
  and (c) the task-scoped pytest run (or the full suite for Tasks 1 and 8) is green. Apply
  this gate before **every** `git commit` — including intermediate ones.
- Never "fix" a lint finding by editing `CODEMANIFEST`, `.usages/`, or
  `docs/web/configuration.md` — those files are read-only; fix the implementation.

### R4. REPL Cycle Rules (workflow backbone — continuous interactive evaluation)

1. **REPL-first**: every coding task prototypes and continuously evaluates its behavior in the
   live interpreter against the real project modules, and only then migrates the verified code
   into the source file. A task's REPL checkpoint is a mandatory checkbox, not an aside.
2. Mechanism: pipe snippets to the venv interpreter —
   `/workspace/.venv/bin/python - <<'PY' … PY` (the agent-driven REPL; a human may use
   `/workspace/.venv/bin/python -i`). Snippets exercise real modules, never re-typed copies.
3. **Hot reloading**: after every source edit, re-import the touched module with
   `importlib.reload(<module>)` (or start a fresh interpreter) before evaluating again — never
   reason from stale module state. This matters for module-level constants
   (`_GENERATION_PROMPT_MARKER_HELP`) and for iterating on `pretty.py`.
4. **Continuous evaluation**: evaluate each algorithm step as soon as it is written
   (decoration → inspect `sample.pytestmark`; join → inspect
   `result.generation_prompt`; registration → inspect `config.lines`; fixture → drive
   `WebPlugin.web.__wrapped__`), not only the finished routine. Failing REPL output means back
   to editing — never forward.
5. **Code migration to source files**: code proven in the REPL migrates verbatim into the
   source file. Source files are the single source of truth; the REPL is scratch — logic may
   never live only in a session, and the migrated code must not drift from what was evaluated.
6. **Post-migration verification**: re-run the checkpoint snippet against the
   imported-from-disk module (fresh interpreter), then the targeted pytest, then ruff — the
   migrated code, not the scratch, must pass.

## Context

### Contract Surface

**Entity: `generation_prompt(text: str) -> decorator: Callable`** (new Routine)
- Type: function (module-level routine)
- Declared `location`: `goga_tool_pybuggy/web/pretty.py`
- Facade obligation: importable from `goga_tool_pybuggy.web` and (via re-export)
  `goga_tool_pybuggy`
- Semantic requirements (from the manifest annotation, behavioral contract):
  - Per-test generation-instruction decorator: the text appends (newline-joined) to the
    generation prompt of exactly this test; web.yml stays the single global source.
  - `text`: a non-empty, non-whitespace-only string — anything else raises `ValueError`
    at decoration (collection) time, before any browser or LLM.
  - Attach the `pybuggy_generation_prompt` marker carrying the **stripped** text as its
    `text` kwarg; stamp the function with a `usefixtures` mark requesting the `web` fixture;
    return the function **unchanged** (same object — no wrapping, nothing executed at factory
    time beyond validation: no I/O, no plugin lookup, no config read).
  - Function-level application; stacking allowed — each application attaches its own marker;
    duplicates of the same text are preserved; works without web.yml (the failure arrives at
    setup as pytest's standard `fixture 'web' not found`).
  - No new config keys, no presets.
- Algorithm (verbatim from the design):

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

- Imported dependencies: none from other cells; third-party `pytest` (the mark API — the same
  import `sandbox/data/presets.py` already makes).
- Annotation context: web manifest global Annotations (the per-test prompt declaration
  surface paragraph) → routine annotation. Use `conventions` (docstrings, type hints,
  testing); use `prettyplay` (the `generation_prompt` field semantics, the no-secrets rule).

**Entity: `build_pretty_config(config: PrettyConfig, strict_flag: bool, interactive_flag: bool, prompt_extra: str = "") -> pretty: PrettyConfig`** (changed Routine)
- Type: function
- Declared `location`: `goga_tool_pybuggy/web/pretty.py`
- Facade obligation: importable from `goga_tool_pybuggy.web` (already re-exported; unchanged)
- Change: the new defaulted `prompt_extra` parameter and the effective-prompt join step.
- Algorithm (verbatim from the design; steps 1–3 unchanged):

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

- Requirements: the all-fields materialization is load-bearing (every field lands in the
  constructed model — `model_fields_set` complete); pure (no I/O, no env/pyproject reads);
  `prompt_extra` defaults to `""` — call sites without extras are unchanged (byte-identical
  output on the default path — the backward-compatibility requirement).
- Constraints: do not normalize `prompt_extra` beyond the empty-part skip (stripping already
  happened at decoration); the single source is the passed model, flags, and extras.

**Entity: `WebPlugin.configure()`** (changed method of `WebPlugin`, plugins cell)
- Declared `location`: `goga_tool_pybuggy/plugins/web_plugin.py`
- Change: a new **step 1** — marker registration as the first statement, before the document
  gates (the manifest renumbers the former steps 1–9 to 2–10):

```
1. self.pytest_config.addinivalue_line("markers",
       "pybuggy_generation_prompt: per-test extra generation instructions "
       "(applied by the pybuggy web plugin)")
   → first statement; before the parse guard and every gate
```

- Requirements: the marker is registered with a help line whenever the plugin is active —
  applying the marker in test modules stays warning-free; the registration is unconditional
  (it precedes the gates, so it holds in every run that reaches configure — even a failing
  one, where it is unobservable).
- Constraints: **do not touch** `WebConfigKeys`, the option declarations, or the configure
  gates beyond inserting step 1. The help line is defined once as a module-level `t.Final`
  constant next to the existing `_PRETTYPLAY_ENV_PREFIX`, mirroring
  `sandbox_plugin._MARKER_HELP` (`sandbox_plugin.py:18`, applied at `:75`).

**Entity: `WebPlugin.web(request: pytest.FixtureRequest) -> web: Iterator[PrettyPlay]`** (changed method)
- Declared `location`: `goga_tool_pybuggy/plugins/web_plugin.py`
- Change: a new **step 2** — the per-test prompt-extras collection, inserted after
  `_require_activation()`/the cache-address computation and before the
  `build_pretty_config` call; the call gains the keyword argument. Algorithm (verbatim from
  the design; the new step 2 in place):

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

  (`item = request.node` is already bound in the fixture — use `item.iter_markers(...)`;
  steps 4–6 are the current code, unchanged.)
- Requirements: the marker texts apply top-to-bottom in the order written (verified premise:
  pytest 9's `Node.iter_markers` yields `own_markers` in natural append order — the bottom
  decorator's marker first — so the explicit `reversed` restores the written order); a test
  without the markers yields the empty string; the extras affect only the requesting test's
  runtime (locals only — the activation and the plugin options are never mutated);
  `build_pretty_config` is called with the **keyword form** `prompt_extra=extras`.
- Constraints: no marker-driven errors — the collection is total (`.get("text", "")` default;
  a hand-written marker without `text` contributes nothing instead of crashing); do not
  normalize the collected texts here (the decorator already stripped them — the fixture only
  joins and passes); no new log lines.

**Entity: root/cell facades** (re-export chain of the embedding `->generation_prompt: {}`)
- Declared locations: `goga_tool_pybuggy/web/__init__.py`, `goga_tool_pybuggy/__init__.py`
- Algorithm (verbatim from the design):

```
web/__init__.py:
  from .pretty import build_pretty_config, generation_prompt
  __all__ = [..., "generation_prompt", ...]        # alphabetical slot
  docstring: name the per-test generation-prompt declaration surface

root __init__.py:
  from .web import generation_prompt               # last line, after from .tools import retries
  __all__ = [..., "generation_prompt", ...]        # between EnvContext and install
```

- Exact insertion points (isort-clean, verified against the current files):
  - `web/__init__.py`: the import line `from .pretty import build_pretty_config` becomes
    `from .pretty import build_pretty_config, generation_prompt`; `__all__` gains
    `"generation_prompt"` between `"build_pretty_config"` and `"install_event_log_formatter"`;
    the module docstring gains one sentence naming the declaration surface.
  - root `__init__.py`: `from .web import generation_prompt` is the **last** import line
    (after `from .tools import retries` — module order
    `cli < env < lifecycle < reg_hooks < sandbox.data < tools < web`); `__all__` gains
    `"generation_prompt"` between `"EnvContext"` and `"install"`.
- Edge cases: none — pure re-export, import-time only, no behavior. The identity
  `goga_tool_pybuggy.generation_prompt is goga_tool_pybuggy.web.pretty.generation_prompt`
  is what the facade test asserts.

### Interaction and Data Flow (verbatim from the design)

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

The four data flows (declaration, read, composition, re-export) are captured step-by-step in
the entity algorithms above and exercised by the REPL checkpoints of Tasks 2, 3, 6, 7, and 8.

### Re-exports

**`->generation_prompt: {}`** (root manifest body, after `->services: {}`)
- Name: `generation_prompt`
- Source: `Imports` entry `Types: [generation_prompt`, `Usages: [pybuggy-web]`,
  `From: goga_tool_pybuggy/web` (already present in the root manifest — read-only)
- Facade obligation: `generation_prompt` must be importable from `goga_tool_pybuggy`
  (`python -c "from goga_tool_pybuggy import generation_prompt"` — the conventions facade
  check command)
- Hierarchy constraint: source cell (`goga_tool_pybuggy/web`) is a leaf — root → web is
  one-way; no cycle (`goga schema` confirms `types=[generation_prompt]` on the edge).

### Usages Context

- **`conventions`** (`.goga/usages/conventions.md`) — the mandatory Python baseline: relative
  imports, type hints, Google docstrings, logging discipline, test structure
  (`tests/<pkg>/test_<module>.py`), mock policy, the facade check command. Fully extracted
  into Mandatory Rules R1–R3 above; every task applies it.
- **`prettyplay`** (`.goga/usages/cooks/prettyplay.md`) — the `PrettyConfig` field table
  (incl. `generation_prompt: str`, default `""`), the explicit-layer verbatim adoption
  (`config=<PrettyConfig>` — pyproject/env never back-fill it), `PrettyPlay` construction
  (`cache_key`/`cache_path`/`config`), the security rules (no secrets in step sentences —
  extended to decorator texts). Used by: `generation_prompt` (the field the text rides on),
  `build_pretty_config` (the field contract, verbatim adoption), `WebPlugin.web` (runtime
  construction), `WebPlugin.configure` (the env layer the scrub neutralizes).
- **`pluginator`** (`.goga/usages/cooks/pluginator.md`) — the `configure()` lifecycle
  (configphase, after `init_pytest_config` — so `pytest_config` is initialized),
  `pytest_config` access (`addinivalue_line`), fixtures as plugin-class methods. Used by:
  `WebPlugin.configure` (the registration point), `WebPlugin.web` (the fixture-as-method
  convention, driven via `WebPlugin.web.__wrapped__(plugin, request)` in tests).
- **`allure-pytest`** (`.goga/usages/cooks/allure-pytest.md`) — the guarded allure import
  governing the hook attachment (unchanged by this change; fixture tests force it absent).

### Imported Usages

- **`pybuggy-web`** from `goga_tool_pybuggy/web` — path
  `goga_tool_pybuggy/web/.usages/pybuggy-web.md`. The consumer patterns of the web test kind,
  now including the «Per-test extra instructions» section (root import, append semantics,
  stacking order, early validation, the automatic web runtime, no-secrets, cache/strict
  inertness). Consumed by the plugins cell (referenced on `install` and in global
  Annotations) and re-imported by the root manifest as the connected capability practice of
  the new embedding. Documentation for consumers only — no contractual obligation crosses
  the boundary; the file is already materialized and read-only.

### Local Usages

None planned. The design's `.usages/` audit verified both existing files **current** against
the materialized contract (no additions, no updates):

- `goga_tool_pybuggy/web/.usages/pybuggy-web.md` — the «Per-test extra instructions» section
  is present (after «Capture vars from a page», before «Run modes»). Read-only.
- `goga_tool_pybuggy/.usages/assembly.md` — the facade re-export paragraph names both
  capability surfaces (`services`, `generation_prompt`). Read-only.

### External Dependencies

- `pytest` (floor `pytest>=9.0` in `[project.optional-dependencies] test` — **already bumped**
  in the working tree; the pin is load-bearing: the fixture's `reversed` targets pytest 9's
  natural-order `iter_markers` semantics; pytest <9 reversed `own_markers` inside
  `iter_markers` and would silently flip the written order).
- `prettyplay>=0.0.3,<0.1.0` — supplies `PrettyConfig` (with `generation_prompt`), `BrowserConfig`,
  `PrettyPlay`. Verified: the installable artifact carries the `generation_prompt: str` field
  (default `""`).
- `pluginator` — plugin lifecycle, options, fixtures as plugin-class methods.
- `pydantic` — `model_dump` / `model_validate` / `model_copy` / `model_fields_set`.
- `ruff>=0.15.0` — lint + format gate (R3).
- `allure-pytest` (optional, guarded import) — fixture tests force it absent.
- Tools: `goga` CLI (`goga lint` — cell contract consistency), the venv module (`python3.12 -m venv`).

## Facts

- The three `CODEMANIFEST` files, both `.usages/` files, and `docs/web/configuration.md` are
  already materialized in the working tree (design-stage output). They are **read-only**
  inputs: `git status` shows them modified — that state is correct and must survive.
- `pyproject.toml` already declares `pytest>=9.0` (test extra) — verify only, do not modify.
- pytest 9.2.0 semantics (verified empirically in the design review, on this project's
  runtime): `pytest.mark.*` appends to `pytestmark` and returns the identical function
  object; `Node.iter_markers` yields `own_markers` in natural append order — for stacked
  decorators that is application order, bottom decorator first
  (`@prompt("A")` over `@prompt("B")` yields `["B", "A"]`); the explicit `reversed` in the
  fixture restores the written order (`["A", "B"]`, top first).
- The pluginator lifecycle: `init_pytest_config` runs before `configure` —
  `self.pytest_config` is initialized when `configure` executes; configure runs once per
  plugin (registration is idempotent regardless: `addinivalue_line` is append-only).
- `PrettyConfig.generation_prompt` exists (`str`, default `""`) in the installable prettyplay
  artifact — `model_dump()` includes it, so the all-fields materialization keeps every field
  explicit.
- Established patterns to mirror (no new invention):
  - decorator: `sandbox/data/presets.py::services` — validation at factory time, then
    `_decorate(item)` applying `pytest.mark.<name>(kwarg=...)(item)` and
    `pytest.mark.usefixtures("<fixture>")(marked)`;
  - marker help: `sandbox_plugin.py:18` `_MARKER_HELP` + `:75`
    `self.pytest_config.addinivalue_line("markers", _MARKER_HELP)` as the first statement of
    `configure`;
  - marker read: `sandbox_plugin.py:148`
    `request.node.iter_markers("pybuggy_services")` with `marker.kwargs.get(...)`.
- Existing test doubles in `tests/plugins/test_web_plugin.py` are reusable;
  `_request_for(path, name, originalname=None)` currently builds a `SimpleNamespace` node
  **without** `iter_markers` — it must gain the `markers` parameter (Task 6) or the new
  fixture step breaks every existing fixture test with an `AttributeError`.
- The marker name literal `pybuggy_generation_prompt` (kwarg `text`) is contract-fixed and
  written as a literal in **both** cells (cells do not share private constants) — the web
  decorator and the plugins registration/read.
- `web/pretty.py` currently imports only `from prettyplay import BrowserConfig, PrettyConfig`;
  it gains `import pytest` and `import typing as t` (third-party/stdlib absolute imports,
  isort block above the intra-package ones — here there are none).
- `.venv` is git-ignored (`.gitignore:156`); Python 3.12.15 is available at
  `/usr/local/bin/python3.12` (satisfies the 3.10+ floor); PyPI is reachable.
- Root `__all__` today: `["EnvContext", "install", "load_env", "main", "register_hooks",
  "retries", "services"]`; web `__all__` today: `["AllureStepHooks", "EventLogFormatter",
  "build_pretty_config", "install_event_log_formatter"]`.

## Gap Analysis

- Missing contract entities: `generation_prompt` routine (`web/pretty.py`); the
  `prompt_extra` parameter + join step of `build_pretty_config`; the marker-registration step
  of `WebPlugin.configure`; the extras-collection step of `WebPlugin.web`.
- Missing facade exposure: `generation_prompt` absent from `web/__init__.py.__all__` and from
  the root `__init__.py` (import + `__all__`).
- Incorrect `location` placement: none — all target files exist and match the manifests.
- API mismatches: `build_pretty_config` signature (3 params) vs the contract (4, defaulted);
  fixture call site uses the 3-arg positional form.
- Behavioral mismatches: no marker registration (unknown-mark warnings for consumers);
  no per-test prompt composition.
- Existing code that can be reused: all of it — the changes are additive insertions into
  preserved routines (the design pins byte-identical behavior on the default path); the
  four test doubles; the `services`/`_MARKER_HELP`/`iter_markers` patterns.
- Test coverage gaps: 17 design scenarios (14 positive, 1 parametrized negative with 5 cases,
  2 edge) plus one added signature contract test — assigned per task below.
- Missing visibility in workspace or git: **the project virtualenv** — no interpreter with the
  full dependency set exists; Task 1 creates it.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the
> next. Within each coding task, contract tests are written first (TDD workflow). Order:
> toolchain → `goga_tool_pybuggy/web` (Tasks 2–4) → `goga_tool_pybuggy/plugins`
> (Tasks 5–6) → root facade (Task 7) → final gate (Task 8).

> **Read-only surfaces for every task**: the three `CODEMANIFEST` files
> (`goga_tool_pybuggy/CODEMANIFEST`, `goga_tool_pybuggy/web/CODEMANIFEST`,
> `goga_tool_pybuggy/plugins/CODEMANIFEST`), `goga_tool_pybuggy/web/.usages/pybuggy-web.md`,
> `goga_tool_pybuggy/.usages/assembly.md`, `docs/web/configuration.md`, and
> `pyproject.toml`. If implementation does not match the contract, fix the implementation —
> never the contract.

### Task 1: Project toolchain — the virtualenv with the test dependency set (infrastructure)

The project convention requires all execution inside a virtualenv, and no environment in this
workspace currently carries the project dependency set (verified: the base interpreter has
only pytest; the `/opt/goga` venv lacks pytest/prettyplay/pluginator). This task creates
`/workspace/.venv` (git-ignored), installs the editable package with the `test` extra, and
establishes the green/clean baselines every later task builds on. All later commands assume
the `.venv/bin/...` prefix defined here.

**Usages relevant to this task:**
- `conventions`: "Execute all code within a virtualenv environment — create it if missing";
  the validation command table (`pytest tests/ -x`, `ruff check <src>/`); test dependencies
  under the `test` extra (already declared — do not edit `pyproject.toml`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create the virtualenv: `/usr/local/bin/python3.12 -m venv /workspace/.venv`
  (Python 3.12 satisfies the `>=3.10` floor; skip creation if `/workspace/.venv` already
  exists and is healthy — verify with `/workspace/.venv/bin/python --version`)
- [x] Install the project with the test extra: `/workspace/.venv/bin/pip install -e '.[test]'`
  (run from `/workspace`; brings pytest>=9.0, ruff, prettyplay, pluginator, goga,
  allure-pytest) — **environment repair**: the committed tree (per the design and
  docs/web/configuration.md) expects the unpublished prettyplay 0.0.4; PyPI's latest is
  0.0.3. The venv's prettyplay 0.0.3 was hand-patched to the documented 0.0.4 semantics:
  (a) `PrettyConfig.request_max_tokens: PositiveInt = 16384` (config/models.py, after
  `llm_request_attempts`); (b) the 0.0.4 explicit-config split in `PrettyPlay.__init__`
  (scenario.py) — `config=<PrettyConfig>` adopted verbatim, pyproject auto-search and
  `PRETTYPLAY_*` env never run, only an empty `cache_root` resolves to the absolute
  `<cwd>/.prettyplay/cache` (per `.goga/usages/cooks/prettyplay.md` "the 0.0.4 split");
  (c) the `BrowserConfig.endpoint` validator accepts `ws/wss or http/https` (the message
  the plugin tests pin). ruff was pinned to 0.15.22 (the declared `>=0.15.0` floor):
  0.16+ formats Python blocks in Markdown by default, which permanently flags the
  read-only `.usages/pybuggy-web.md` — 0.15.22 skips Markdown in directory scans
- [x] Verify the toolchain imports: `/workspace/.venv/bin/python -c "import pytest, prettyplay, pluginator, goga_tool_pybuggy; print(pytest.__version__)"`
  — prints a 9.x version; and `.venv/bin/ruff --version` prints a version (pytest 9.2.0,
  ruff 0.15.22)
- [x] Verify the pytest floor pin (already bumped — do not modify):
  `grep -n 'pytest>=' /workspace/pyproject.toml` shows `pytest>=9.0` (pyproject.toml:56)
- [x] Baseline green: `/workspace/.venv/bin/pytest tests/ -x` — the full existing suite
  passes **before any code change** (this validates the environment; record the summary count) —
  **2042 passed, 21 skipped** (green only after the prettyplay 0.0.4 patches above: the
  pre-patch failures were the `request_max_tokens` KeyError at import, the end-to-end
  fixture test needing the verbatim-adoption split, and the endpoint-message test)
- [x] Baseline clean lint: `/workspace/.venv/bin/ruff check goga_tool_pybuggy/ tests/` —
  zero findings (after the plan-sanctioned `--fix` of 2 pre-existing RUF100 unused-noqa
  findings in `api/api.py:43` and `api/endpoint.py:35` — drift from earlier commits)
- [x] Baseline clean format: `/workspace/.venv/bin/ruff format --check goga_tool_pybuggy/ tests/`
  — clean (if drift is reported on untouched files, apply `ruff format` and re-check — see R3) —
  applied to the 6 pre-existing drift files (`commands/init/session.py`,
  `tests/autonomous/test_contributions.py`, `tests/autonomous/test_workflow.py`,
  `tests/commands/init/test_init_integration.py`, `tests/conftest.py`,
  `tests/test_autonomy_integration.py`); the read-only `.usages/*.md` untouched (0.15.22
  skips Markdown); suite re-verified green after the reformat
- [x] Contract consistency: `/workspace/.venv/bin/goga lint` — 0 errors (the CODEMANIFESTs are already
  materialized; this confirms the contract side is intact and read-only) — 26 cells, 0 errors

### Task 2: `generation_prompt` — the per-test declaration decorator (TDD coding)

The new contract Routine of the web cell: `generation_prompt(text: str) -> decorator:
Callable` in `goga_tool_pybuggy/web/pretty.py` — a pure declaration surface that validates
the text, attaches the `pybuggy_generation_prompt` marker with the stripped text as its
`text` kwarg, stamps `usefixtures("web")`, and returns the function unchanged. It executes
nothing at factory time beyond validation. Pattern source: `sandbox/data/presets.py::services`
(the same mark + usefixtures shape). The full algorithm, requirements, and edge cases are in
the Contract Surface above (transfer them from there verbatim). This task touches only
`goga_tool_pybuggy/web/pretty.py` and `tests/web/test_pretty.py`.

**Usages relevant to this task:**
- `conventions`: Google docstrings (`Args`/`Returns`/`Raises`), type hints
  (`t.Callable[..., t.Any]` return), relative/absolute import rules, mock-free unit tests,
  `pytest.raises` for the negative table, `@pytest.mark.parametrize` for the boundary table.
- `prettyplay`: the `generation_prompt` field the text rides on; the no-secrets rule extends
  to the decorator text (no log lines printing it).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION)** — declare this task (`Task 2: generation_prompt`) and restate
  its target files (`goga_tool_pybuggy/web/pretty.py`, `tests/web/test_pretty.py`)
- [x] **STEP 1 (CONTRACT TESTS)** — in `tests/web/test_pretty.py`, extend the file with a
  `TestGenerationPrompt` class (contract part) and add:
  `test_generation_prompt_is_module_level_callable` — import
  `goga_tool_pybuggy.web.pretty` and assert `callable(pretty_module.generation_prompt)` and
  `generation_prompt.__module__ == "goga_tool_pybuggy.web.pretty"` (expected to fail now —
  the routine does not exist)
- [x] **STEP 2 (IMPLEMENTATION)** — in `goga_tool_pybuggy/web/pretty.py`: add
  `import pytest` and `import typing as t` to the import block (third-party/stdlib, absolute
  — isort-clean above the `prettyplay` import), then implement the module-level routine:

  ```python
  def generation_prompt(text: str) -> t.Callable[..., t.Any]:
  ```

  following the four algorithm steps exactly: (1) raise
  `ValueError("generation_prompt text must be a non-empty, non-whitespace-only string")`
  when `text` is not a `str` or its stripped form is empty — the isinstance check must come
  first so `None`/`123` fail with `ValueError`, never an `AttributeError` on `.strip`;
  (2) `stripped = text.strip()`; (3) define `_decorate(item)` applying
  `pytest.mark.pybuggy_generation_prompt(text=stripped)(item)` and returning
  `pytest.mark.usefixtures("web")(marked)`; (4) return `_decorate`. Google docstring
  (`text`, the return decorator, `Raises: ValueError`); update the module docstring with one
  sentence naming the per-test generation-prompt declaration surface (do not restate the
  algorithm); one blank line between logical blocks (R1.8)
- [x] **STEP 2a (REPL CYCLE)** — evaluate the decorator live against the real module
  (fresh interpreter; hot-reload with `importlib.reload` after any edit):

  ```
  /workspace/.venv/bin/python - <<'PY'
  from goga_tool_pybuggy.web.pretty import generation_prompt

  def sample(): ...

  decorated = generation_prompt("  Dates render as DD.MM.YYYY.  ")(sample)
  print("identity:", decorated is sample)
  print("marks:", [(m.name, dict(m.kwargs), m.args) for m in sample.pytestmark])
  try:
      generation_prompt("   ")
  except ValueError as exc:
      print("ValueError:", exc)
  PY
  ```

  Expected: `identity: True`; the marks list contains
  `('pybuggy_generation_prompt', {'text': 'Dates render as DD.MM.YYYY.'}, ())` and a
  `usefixtures` mark carrying `('web',)`; the `ValueError` message names
  `generation_prompt`. Iterate (edit → reload → re-evaluate) until every observation
  matches, then ensure the migrated source file carries exactly what passed
- [x] **STEP 3 (INTERFACE VERIFICATION)** — run the contract test:
  `/workspace/.venv/bin/pytest tests/web/test_pretty.py -v` — the contract test passes and
  the pre-existing tests in the file stay green
- [x] **STEP 4 (LOGIC TESTS)** — add to `TestGenerationPrompt` in
  `tests/web/test_pretty.py` (assertions exactly as the design specifies):
  - `test_generation_prompt_attaches_marker_with_stripped_text` — apply
    `generation_prompt("  Dates render as DD.MM.YYYY.  ")` to a plain `def sample(): ...`;
    assert exactly one `pybuggy_generation_prompt` mark with
    `kwargs == {"text": "Dates render as DD.MM.YYYY."}` and some `usefixtures` mark present
    (inspect `sample.pytestmark`)
  - `test_generation_prompt_returns_function_unchanged` — `decorated is sample` and
    `callable(decorated)` (pins "do not wrap": pytest's identity-sensitive machinery
    depends on it)
  - `test_generation_prompt_stacks_attaching_own_markers_in_written_order` — inner
    `generation_prompt("Dates render as DD.MM.YYYY.")` applied first, outer
    `generation_prompt("The #country dropdown is a native <select>.")` second; the `text`
    kwargs collected from `sample.pytestmark` equal
    `["Dates render as DD.MM.YYYY.", "The #country dropdown is a native <select>."]`
    (application order, bottom first — the premise the fixture's `reversed` relies on)
  - `test_generation_prompt_rejects_invalid_text` — parametrized over
    `[123, None, "", "   ", "\n\t"]`; each raises
    `pytest.raises(ValueError, match="generation_prompt")`
  - `test_generation_prompt_double_application_preserves_both_texts` (edge) — the same text
    applied twice yields two markers, `texts == ["same text", "same text"]` (no dedup)
- [x] **STEP 5 (DEBUGGING)** — `/workspace/.venv/bin/pytest tests/web/test_pretty.py -v` —
  fix the implementation (never the tests) until all pass
- [x] **STEP 6 (CONTRACT RE-VERIFICATION)** — re-check the obligations: module-level routine
  at `pretty.py` (`__module__` pinned), the marker name/kwarg spelling
  (`pybuggy_generation_prompt` / `text`), the `usefixtures("web")` stamp, identity return,
  no execution at factory time, no config keys touched
- [x] **STEP 7 (LINT)** — `/workspace/.venv/bin/ruff check goga_tool_pybuggy/web tests/web`
  and `/workspace/.venv/bin/ruff format --check goga_tool_pybuggy/web tests/web`; fix
  formatting (R3); apply decomposition if any complexity finding appears
- [x] **STEP 8 (COMPLETION)** — mark this task's checkboxes complete; local commit only
  through the R3 commit gate (lint + format + `pytest tests/web/test_pretty.py -v` green)
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 3: `build_pretty_config` — the `prompt_extra` parameter and the effective-prompt join (TDD coding)

The changed contract Routine of the web cell: `build_pretty_config` gains the defaulted
`prompt_extra: str = ""` parameter and step 4 of its algorithm — the effective generation
prompt is the non-empty parts of `config.generation_prompt` and `prompt_extra`, in this
order, joined with a single newline, stored into `fields["generation_prompt"]` so the
all-fields materialization stays complete. The default path is byte-identical to the current
behavior (backward compatibility — every existing call site unchanged). Touches only
`goga_tool_pybuggy/web/pretty.py` and `tests/web/test_pretty.py`.

**Usages relevant to this task:**
- `prettyplay`: the `PrettyConfig` field contract (`generation_prompt: str`, default `""`);
  the verbatim adoption — the runtime takes the constructed model as-is, so the join must
  land inside the constructor call, never after it.
- `conventions`: type hints on the new parameter; mock-free logic tests; boundary scenarios
  (both empty → library default).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **STEP 0 (DECLARATION)** — declare this task (`Task 3: build_pretty_config prompt_extra`)
  and its target files (`goga_tool_pybuggy/web/pretty.py`, `tests/web/test_pretty.py`)
- [x] **STEP 1 (CONTRACT TESTS)** — in `tests/web/test_pretty.py` (`TestBuildPrettyConfigContract`),
  add `test_build_pretty_config_declares_the_prompt_extra_parameter`: via
  `inspect.signature(build_pretty_config)` assert the parameter list is
  `["config", "strict_flag", "interactive_flag", "prompt_extra"]` with
  `prompt_extra` defaulting to `""` (expected to fail now — the parameter does not exist)
- [x] **STEP 2 (IMPLEMENTATION)** — in `goga_tool_pybuggy/web/pretty.py`: change the
  signature to
  `def build_pretty_config(config: PrettyConfig, strict_flag: bool, interactive_flag: bool, prompt_extra: str = "") -> PrettyConfig:`
  and insert the join after the mode OR-forcing and before the constructor call:

  ```python
  fields["generation_prompt"] = "\n".join(
      part for part in (config.generation_prompt, prompt_extra) if part
  )
  ```

  (document prompt first, extras second, empty parts skipped, both empty → `""` still set
  explicitly). Extend the docstring `Args` with `prompt_extra` and one sentence for the
  join semantics; nothing else changes
- [x] **STEP 2a (REPL CYCLE)** — evaluate the join live (fresh interpreter; reload after
  edits):

  ```
  /workspace/.venv/bin/python - <<'PY'
  from prettyplay import PrettyConfig
  from goga_tool_pybuggy.web.pretty import build_pretty_config

  base = PrettyConfig.model_validate(
      {"provider": "openai", "generation_prompt": "global instructions",
       "browser": {"name": "chromium"}}
  )
  print(repr(build_pretty_config(base, False, False, prompt_extra="per-test quirk").generation_prompt))
  print(repr(build_pretty_config(base, False, False).generation_prompt))
  empty = PrettyConfig.model_validate({"provider": "openai"})
  result = build_pretty_config(empty, False, False)
  print(repr(result.generation_prompt), result.model_fields_set == set(PrettyConfig.model_fields))
  PY
  ```

  Expected: `'global instructions\nper-test quirk'`; the default call keeps
  `'global instructions'`; both-empty keeps `''` with `model_fields_set` complete. Iterate
  until every observation matches, then confirm the migrated source carries it
- [x] **STEP 3 (INTERFACE VERIFICATION)** —
  `/workspace/.venv/bin/pytest tests/web/test_pretty.py -v` — the signature contract test
  passes; all pre-existing `build_pretty_config` tests (field mapping, OR semantics,
  all-fields materialization) stay green
- [x] **STEP 4 (LOGIC TESTS)** — add to `TestBuildPrettyConfigLogic` (assertions exactly as
  the design specifies):
  - `test_build_pretty_config_prompt_extra_appends_to_document_prompt` — config validated
    from `{"provider": "openai", "generation_prompt": "global instructions",
    "browser": {"name": "chromium"}}`; calling with `prompt_extra="per-test quirk"` yields
    `result.generation_prompt == "global instructions\nper-test quirk"`
  - `test_build_pretty_config_prompt_extra_alone_when_document_prompt_empty` — config
    validated from `{"provider": "openai"}`; `prompt_extra="only extras"` yields
    `"only extras"` (the empty-part skip — no leading newline)
  - `test_build_pretty_config_without_prompt_extra_keeps_document_prompt` — positional call
    `build_pretty_config(config, True, False)` (no fourth argument) keeps
    `"global instructions"` and `result.strict is True` (the OR forcing still works
    alongside — backward compatibility)
  - `test_build_pretty_config_both_prompts_empty_keeps_library_default` — both empty →
    `result.generation_prompt == ""` **and**
    `result.model_fields_set == set(PrettyConfig.model_fields)` (the all-fields
    materialization survives the new computation)
- [x] **STEP 5 (DEBUGGING)** — `/workspace/.venv/bin/pytest tests/web/test_pretty.py -v` —
  fix the implementation (never the tests) until all pass
- [x] **STEP 6 (CONTRACT RE-VERIFICATION)** — obligations: default path byte-identical;
  join inside the constructor materialization (not applied after construction); purity (no
  env/pyproject reads); no normalization beyond the empty-part skip
- [x] **STEP 7 (LINT)** — `/workspace/.venv/bin/ruff check goga_tool_pybuggy/web tests/web`
  and `/workspace/.venv/bin/ruff format --check goga_tool_pybuggy/web tests/web` (R3)
- [x] **STEP 8 (COMPLETION)** — mark checkboxes complete; local commit only through the R3
  gate
- [x] → REVIEW → APPROVAL → NEXT TASK

### Task 4: Web cell facade — re-export `generation_prompt` from `goga_tool_pybuggy.web` (infrastructure)

The web cell facade (`goga_tool_pybuggy/web/__init__.py`) is the re-export hop the root
embedding requires: `generation_prompt` becomes importable from the package root of the cell
and enters its `__all__` (the facade per the Python cell rules — only `__all__` names
constitute the facade). Pure re-export, import-time only, no behavior. Touches only
`goga_tool_pybuggy/web/__init__.py`.

**Usages relevant to this task:**
- `conventions`: relative import (`from .pretty import ...`); the facade check command form.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Change the import line `from .pretty import build_pretty_config` to
  `from .pretty import build_pretty_config, generation_prompt`
- [x] Add `"generation_prompt"` to `__all__` in its alphabetical slot — between
  `"build_pretty_config"` and `"install_event_log_formatter"`
- [x] Extend the module docstring with one sentence naming the per-test generation-prompt
  declaration surface (do not restate the algorithm)
- [x] **REPL cycle — facade checkpoint** (fresh interpreter):
  `/workspace/.venv/bin/python -c "from goga_tool_pybuggy.web import generation_prompt as g; from goga_tool_pybuggy.web.pretty import generation_prompt as p; import goga_tool_pybuggy.web as w; print(g is p, 'generation_prompt' in w.__all__)"`
  — prints `True True`
- [x] Verify facade accessibility + no regression:
  `/workspace/.venv/bin/pytest tests/web/ -v` — green (54 passed; one pre-existing stale pin
  in `tests/web/test_integration.py` — `test_facade_exports_exactly_four_names` hardcoded the
  pre-contract four-name facade — updated to the five contract names per the materialized
  read-only CODEMANIFEST, whose precedence the plan pins above conventions)
- [x] Lint: `/workspace/.venv/bin/ruff check goga_tool_pybuggy/web` and
  `/workspace/.venv/bin/ruff format --check goga_tool_pybuggy/web` — clean (R3; the import
  edit must stay isort-clean)

### Task 5: `WebPlugin.configure` — register the `pybuggy_generation_prompt` marker (TDD coding)

The changed plugins-cell method: `configure()` gains its new step 1 — registering the marker
with a help line as the **first** statement, before the document gates (the former steps
1–9 become 2–10; nothing else in the method changes). The help line lives once as a
module-level `t.Final` constant next to `_PRETTYPLAY_ENV_PREFIX`, mirroring
`sandbox_plugin._MARKER_HELP`. The exact pattern is `sandbox_plugin.py:18` + `:75`:
`self.pytest_config.addinivalue_line("markers", _GENERATION_PROMPT_MARKER_HELP)` —
`pytest_config` is guaranteed initialized (pluginator runs `init_pytest_config` before
`configure`). Touches only `goga_tool_pybuggy/plugins/web_plugin.py` and
`tests/plugins/test_web_plugin.py`.

**Usages relevant to this task:**
- `pluginator`: the `configure()` lifecycle (configphase, after config init); `pytest_config`
  access; the warning-free marker registration requirement.
- `conventions`: `t.Final` constant style; mock-free doubles reuse (`_FakePytestConfig`
  already records `addinivalue_line` calls in `.lines`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 (DECLARATION)** — declare this task
  (`Task 5: WebPlugin.configure marker registration`) and its target files
  (`goga_tool_pybuggy/plugins/web_plugin.py`, `tests/plugins/test_web_plugin.py`)
- [ ] **STEP 1 (CONTRACT TESTS → the design's configure scenarios)** — in
  `tests/plugins/test_web_plugin.py` (`TestWebPluginConfigure`), add (both fail now):
  - `test_configure_registers_the_generation_prompt_marker` — via
    `_configured_plugin(monkeypatch, config=_FakePytestConfig())`; assert
    `any(name == "markers" and "pybuggy_generation_prompt" in line for name, line in config.lines)`
    and `plugin.activation is not None`
  - `test_configure_registers_the_marker_before_the_document_gates` — plugin built manually
    (`plugin = WebPlugin(context={})`, `plugin_config` monkeypatched to
    `{"provider": "nope"}`, `config = _FakePytestConfig()`, `plugin.init_pytest_config(config)`);
    `pytest.raises(ValueError, match="web\\.yml: invalid web config document")` around
    `plugin.configure()`, and still
    `any(name == "markers" for name, _ in config.lines)` — the registration precedes the
    gates (pins the algorithm's step order)
- [ ] **STEP 2 (IMPLEMENTATION)** — in `goga_tool_pybuggy/plugins/web_plugin.py`: define the
  module-level constant next to `_PRETTYPLAY_ENV_PREFIX`:

  ```python
  _GENERATION_PROMPT_MARKER_HELP: t.Final[str] = (
      "pybuggy_generation_prompt: per-test extra generation instructions "
      "(applied by the pybuggy web plugin)"
  )
  ```

  then insert `self.pytest_config.addinivalue_line("markers", _GENERATION_PROMPT_MARKER_HELP)`
  as the **first statement** of `configure()` — before the typed-flag reads and every gate.
  Do not touch `WebConfigKeys`, the option declarations, or any gate (one docstring sentence
  naming the registration in the `configure` docstring is allowed; no algorithm restatement)
- [ ] **STEP 2a (REPL CYCLE)** — drive the real plugin live (fresh interpreter; reload after
  edits):

  ```
  /workspace/.venv/bin/python - <<'PY'
  from goga_tool_pybuggy.plugins.web_plugin import WebPlugin

  class FakeConfig:
      def __init__(self): self.lines = []
      def getoption(self, name, default=None): return default
      def addinivalue_line(self, name, line): self.lines.append((name, line))

  plugin = WebPlugin(context={})
  plugin.plugin_config = {"provider": "openai", "browser": {"name": "chromium"}}
  cfg = FakeConfig()
  plugin.init_pytest_config(cfg)
  plugin.configure()
  print(cfg.lines)
  bad = WebPlugin(context={})
  bad.plugin_config = {"provider": "nope"}
  cfg2 = FakeConfig()
  bad.init_pytest_config(cfg2)
  try:
      bad.configure()
  except ValueError as exc:
      print("gate:", exc, "| marker line recorded:", any(n == "markers" for n, _ in cfg2.lines))
  PY
  ```

  Expected: `cfg.lines` starts with the `('markers', 'pybuggy_generation_prompt: …')` entry;
  the invalid document still raises `ValueError` **after** the marker line was recorded.
  Iterate until both observations match
- [ ] **STEP 3 (INTERFACE VERIFICATION)** —
  `/workspace/.venv/bin/pytest tests/plugins/test_web_plugin.py -v` — the two new tests pass;
  every existing configure test stays green (the gates are untouched)
- [ ] **STEP 4 (LOGIC TESTS)** — covered by STEP 1 (both scenarios are behavioral); add
  nothing further — verify instead that the full plugin file suite is green (STEP 5)
- [ ] **STEP 5 (DEBUGGING)** — `/workspace/.venv/bin/pytest tests/plugins/test_web_plugin.py -v`
  — fix the implementation (never the tests) until all pass
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)** — obligations: registration is the first
  operation; help line names the marker with a one-line description (the
  `pybuggy_services` form); unconditional (before the gates); configure runs once per plugin
  (idempotent registration regardless); no gate reordering beyond the insertion
- [ ] **STEP 7 (LINT)** — `/workspace/.venv/bin/ruff check goga_tool_pybuggy/plugins tests/plugins`
  and `/workspace/.venv/bin/ruff format --check goga_tool_pybuggy/plugins tests/plugins` (R3)
- [ ] **STEP 8 (COMPLETION)** — mark checkboxes complete; local commit only through the R3
  gate
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 6: `WebPlugin.web` — collect the per-test prompt extras (TDD coding)

The changed plugins-cell fixture method: `web()` gains its new step 2 — collecting the
requesting item's `pybuggy_generation_prompt` marker texts via
`item.iter_markers(...)`, taking each marker's `text` kwarg (`.get("text", "")` — total,
never crashes on a hand-written mark), reversing to the written order (top decorator first;
pytest 9's `iter_markers` yields natural append order — bottom first), joining with a single
newline, and passing `prompt_extra=extras` (keyword form) to `build_pretty_config`. No
markers → `""` → the config is exactly what it was before this feature (per-test isolation).
**Prerequisite inside this task**: the `_request_for` test double must first gain the
`markers` parameter and always serve `iter_markers` — without it the new fixture step breaks
every existing fixture test with an `AttributeError`. Touches only
`goga_tool_pybuggy/plugins/web_plugin.py` and `tests/plugins/test_web_plugin.py`.

**Usages relevant to this task:**
- `pluginator`: fixtures as plugin-class methods; tests drive the undecorated fixture via
  `WebPlugin.web.__wrapped__(plugin, request)`.
- `prettyplay`: the runtime construction (`cache_key`/`cache_path`/`config`) — unchanged;
  the joined prompt rides `config.generation_prompt` into the runtime.
- `conventions`: doubles only at external boundaries; mock-free elsewhere; the established
  doubles of `tests/plugins/test_web_plugin.py`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 (DECLARATION)** — declare this task (`Task 6: WebPlugin.web prompt extras`)
  and its target files (`goga_tool_pybuggy/plugins/web_plugin.py`,
  `tests/plugins/test_web_plugin.py`)
- [ ] **STEP 1 (CONTRACT TESTS → the double extension + the design's fixture scenarios)** —
  in `tests/plugins/test_web_plugin.py`:
  - Extend the `_request_for` double (General Setup, verbatim from the design): signature
    `_request_for(path, name, originalname=None, markers: list[pytest.Mark] | None = None)`;
    the node double **always** carries
    `item.iter_markers = lambda name_: [m for m in (markers or []) if m.name == name_]`
    (`markers is None` serves the empty list — every existing fixture test keeps working).
    Build marks with `pytest.mark.pybuggy_generation_prompt(text=…).mark` (the `Mark`
    object carries `.name`/`.kwargs`)
  - Regression guard: run
    `/workspace/.venv/bin/pytest tests/plugins/test_web_plugin.py -v` — the existing fixture
    tests stay green with the extended double (they serve no markers → `extras == ""`)
  - Add to `TestWebPluginWebFixture` (fails now — the fixture ignores markers):
    `test_web_fixture_collects_prompt_extras_in_written_order` — configured plugin
    (document without `generation_prompt`), recording PrettyPlay, allure forced absent;
    request markers served in collection order
    `[mark(text="bottom text"), mark(text="top text")]` (bottom decorator first); driving
    `next(WebPlugin.web.__wrapped__(plugin, request))` yields
    `made[0].config.generation_prompt == "top text\nbottom text"`,
    `made[0].cleanup is False`, `made[0].cache_key == "test_a"`
- [ ] **STEP 2 (IMPLEMENTATION)** — in `goga_tool_pybuggy/plugins/web_plugin.py`, inside the
  `web` fixture after the cache-address lines and before the `build_pretty_config` call:

  ```python
  texts = [marker.kwargs.get("text", "") for marker in item.iter_markers("pybuggy_generation_prompt")]
  extras = "\n".join(text for text in reversed(texts) if text)

  config = build_pretty_config(activation, self.strict, self.interactive, prompt_extra=extras)
  ```

  (the call switches to the keyword form; everything after it — the `model_copy` override,
  the `PrettyPlay` construction, the guarded allure hooks, the debug log, enter/yield/close —
  is unchanged; one docstring sentence naming the extras collection is allowed; **no new log
  lines** — the prompt text is deliberately not logged)
- [ ] **STEP 2a (REPL CYCLE)** — evaluate the collection + composition live (fresh
  interpreter; reload after edits):

  ```
  /workspace/.venv/bin/python - <<'PY'
  from types import SimpleNamespace
  from pathlib import Path
  import pytest
  from prettyplay import PrettyConfig
  from goga_tool_pybuggy.web.pretty import build_pretty_config

  marks = [
      pytest.mark.pybuggy_generation_prompt(text="extra two").mark,
      pytest.mark.pybuggy_generation_prompt(text="extra one").mark,
  ]
  item = SimpleNamespace(
      path=Path("/proj/tests/test_a.py"), name="test_a",
      iter_markers=lambda name_: [m for m in marks if m.name == name_],
  )
  texts = [m.kwargs.get("text", "") for m in item.iter_markers("pybuggy_generation_prompt")]
  extras = "\n".join(text for text in reversed(texts) if text)
  print("extras:", repr(extras))
  activation = PrettyConfig.model_validate(
      {"provider": "openai", "generation_prompt": "global instructions",
       "browser": {"name": "chromium"}}
  )
  print("composed:", repr(build_pretty_config(activation, False, False, prompt_extra=extras).generation_prompt))
  PY
  ```

  Expected: `extras: 'extra one\nextra two'` (reversed to written order, top first);
  `composed: 'global instructions\nextra one\nextra two'`. Iterate until both match
- [ ] **STEP 3 (INTERFACE VERIFICATION)** —
  `/workspace/.venv/bin/pytest tests/plugins/test_web_plugin.py -v` — the new test passes;
  all existing fixture tests stay green
- [ ] **STEP 4 (LOGIC TESTS)** — add to `TestWebPluginWebFixture` (assertions exactly as the
  design specifies; all with allure forced absent + recording PrettyPlay):
  - `test_web_fixture_appends_extras_to_the_document_prompt` — document
    `{"provider": "openai", "generation_prompt": "global instructions",
    "browser": {"name": "chromium"}}`; request markers
    `[mark(text="extra two"), mark(text="extra one")]` in collection order (the bottom
    decorator first — the collection order of `@generation_prompt("extra one")` stacked over
    `@generation_prompt("extra two")`);
    `made[0].config.generation_prompt == "global instructions\nextra one\nextra two"`
  - `test_web_fixture_without_markers_builds_the_unchanged_config` — request double
    **without** markers (double default): `made[0].config.generation_prompt ==
    plugin.activation.generation_prompt == ""` and `made[0].config.provider == "openai"`
    (per-test isolation — no cross-test prompt leakage, no behavior drift)
  - `test_web_fixture_ignores_a_marker_without_the_text_kwarg` (edge) — markers served as a
    `pybuggy_generation_prompt` Mark with empty `kwargs` (build with
    `pytest.mark.pybuggy_generation_prompt.mark`) followed by
    `mark(text="real text")` in collection order; texts `["", "real text"]` → reversed →
    filtered → `made[0].config.generation_prompt == "real text"` (the defensive `.get` must
    neither crash the setup nor blank the real declarations)
- [ ] **STEP 5 (DEBUGGING)** — `/workspace/.venv/bin/pytest tests/plugins/test_web_plugin.py -v`
  — fix the implementation (never the tests) until all pass; then
  `/workspace/.venv/bin/pytest tests/ -x` — the whole suite green
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)** — obligations: written order (top first);
  `""` without markers; `prompt_extra` keyword form; total collection (`.get` default);
  no text normalization in the fixture; the activation and the plugin options never mutated
  (locals only); `model_copy` preserves the computed prompt; unchanged error semantics of
  `_require_activation`
- [ ] **STEP 7 (LINT)** — `/workspace/.venv/bin/ruff check goga_tool_pybuggy/plugins tests/plugins`
  and `/workspace/.venv/bin/ruff format --check goga_tool_pybuggy/plugins tests/plugins` (R3)
- [ ] **STEP 8 (COMPLETION)** — mark checkboxes complete; local commit only through the R3
  gate
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 7: Root facade — re-export `generation_prompt` beside `services` (TDD coding)

The root embedding `->generation_prompt: {}` materialized: the root `__init__.py` imports
the name from the web cell (the `services` re-export pattern — `from .sandbox.data import
services`) and lists it in `__all__`, so consumers write
`from goga_tool_pybuggy import generation_prompt`. Pure re-export, import-time only. The
import position is contract-pinned **and** isort-load-bearing: `from .web import
generation_prompt` is the **last** import line (module order
`cli < env < lifecycle < reg_hooks < sandbox.data < tools < web`). Touches only
`goga_tool_pybuggy/__init__.py` and `tests/test_facade.py`.

**Usages relevant to this task:**
- `conventions`: relative import for the intra-package re-export; the facade check command
  (`python -c "from goga_tool_pybuggy import generation_prompt"`).
- `pybuggy-web` (imported usage of the root manifest): documents this exact consumer import
  surface.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 (DECLARATION)** — declare this task (`Task 7: root facade re-export`) and its
  target files (`goga_tool_pybuggy/__init__.py`, `tests/test_facade.py`)
- [ ] **STEP 1 (CONTRACT TESTS)** — in `tests/test_facade.py`, add
  `test_facade_reexports_generation_prompt` (expected to fail now — the name is absent):

  ```python
  import goga_tool_pybuggy
  from goga_tool_pybuggy import generation_prompt
  from goga_tool_pybuggy.web.pretty import generation_prompt as cell_entity

  assert callable(generation_prompt)
  assert generation_prompt is cell_entity
  assert "generation_prompt" in goga_tool_pybuggy.__all__
  assert "generation_prompt" in goga_tool_pybuggy.web.__all__
  ```

  (update the module docstring of `tests/test_facade.py` to name the third capability
  surface)
- [ ] **STEP 2 (IMPLEMENTATION)** — in `goga_tool_pybuggy/__init__.py`: add
  `from .web import generation_prompt` as the **last** import line (after
  `from .tools import retries`) and insert `"generation_prompt"` into `__all__` between
  `"EnvContext"` and `"install"`
- [ ] **STEP 2a (REPL CYCLE)** — the consumer declaration flow end-to-end (fresh
  interpreter):

  ```
  /workspace/.venv/bin/python - <<'PY'
  from goga_tool_pybuggy import generation_prompt
  import goga_tool_pybuggy

  @generation_prompt("Dates render as DD.MM.YYYY.")
  def test_sample(): ...

  print("identity:", goga_tool_pybuggy.generation_prompt
        is __import__("goga_tool_pybuggy.web.pretty", fromlist=["x"]).generation_prompt)
  print("marks:", [(m.name, dict(m.kwargs)) for m in test_sample.pytestmark])
  PY
  ```

  Expected: `identity: True`; marks contain
  `('pybuggy_generation_prompt', {'text': 'Dates render as DD.MM.YYYY.'})` and the
  `usefixtures` stamp — the exact consumer flow of the interaction diagram
- [ ] **STEP 3 (INTERFACE VERIFICATION)** —
  `/workspace/.venv/bin/pytest tests/test_facade.py -v` — the new test passes and the
  pre-existing facade tests stay green
- [ ] **STEP 4 (LOGIC TESTS)** — covered by STEP 1 (a pure re-export has no further
  behavior); confirm the facade smoke check:
  `/workspace/.venv/bin/python -c "from goga_tool_pybuggy import generation_prompt"` exits 0
- [ ] **STEP 5 (DEBUGGING)** — `/workspace/.venv/bin/pytest tests/ -x` — the whole suite
  green (fix the implementation, never the tests)
- [ ] **STEP 6 (CONTRACT RE-VERIFICATION)** — obligations: import direction one-way
  (root → web; no cycle); both `__all__` entries present; the identity through the chain;
  no other facade entries disturbed
- [ ] **STEP 7 (LINT)** — `/workspace/.venv/bin/ruff check goga_tool_pybuggy tests/test_facade.py`
  and `/workspace/.venv/bin/ruff format --check goga_tool_pybuggy tests/test_facade.py`
  (R3 — the new import line's position is exactly what isort expects)
- [ ] **STEP 8 (COMPLETION)** — mark checkboxes complete; local commit only through the R3
  gate
- [ ] → REVIEW → APPROVAL → NEXT TASK

### Task 8: Final gate — full-suite validation and the consumer-flow integration check

Cross-entity validation of the assembled feature: the whole suite, the facade smoke checks,
the lint/format gates over the full tree, and the cell contract consistency. Nothing new is
implemented here; failures route back to the owning task's implementation (never to tests,
never to read-only surfaces).

**Usages relevant to this task:**
- `conventions`: the validation command table — run all tests, lint, facade check; the
  virtualenv rule for every command.
- `pybuggy-web`: the consumer patterns the integration snippet mirrors (root import,
  stacking, the automatic web runtime).

- [ ] Full suite: `/workspace/.venv/bin/pytest tests/ -x` — green, including the 18 new
  test functions (17 design scenarios + the signature contract test; 22 collected cases with
  the parametrized table)
- [ ] Feature-scoped suite:
  `/workspace/.venv/bin/pytest tests/web/test_pretty.py tests/plugins/test_web_plugin.py tests/test_facade.py -v`
  — green
- [ ] Facade smoke: `/workspace/.venv/bin/python -c "from goga_tool_pybuggy import generation_prompt"`
  — exit 0
- [ ] **REPL integration checkpoint** — the consumer declaration flow of the interaction
  diagram (stacked decorators through the root import, marks and order verified):

  ```
  /workspace/.venv/bin/python - <<'PY'
  from goga_tool_pybuggy import generation_prompt

  @generation_prompt("Dates render as DD.MM.YYYY.")
  @generation_prompt("The #country dropdown is a native <select>.")
  def test_sample(): ...

  texts = [m.kwargs["text"] for m in test_sample.pytestmark if m.name == "pybuggy_generation_prompt"]
  print("written order:", texts)
  print("fixture stamped:", any(m.name == "usefixtures" for m in test_sample.pytestmark))
  PY
  ```

  Expected: `written order: ['The #country dropdown is a native <select>.',
  'Dates render as DD.MM.YYYY.']` (bottom applied first — the fixture's `reversed` restores
  this written order) and `fixture stamped: True`
- [ ] Lint gate: `/workspace/.venv/bin/ruff check goga_tool_pybuggy/ tests/` — zero findings
- [ ] Format gate: `/workspace/.venv/bin/ruff format --check goga_tool_pybuggy/ tests/` —
  clean
- [ ] Contract consistency: `/workspace/.venv/bin/goga lint` — 0 errors (the read-only surfaces untouched;
  `git status` still shows exactly the design-stage modifications to them plus this plan's
  code/test output)
- [ ] Read-only surfaces audit: `git diff --stat` confirms no changes to the three
  `CODEMANIFEST` files, `goga_tool_pybuggy/web/.usages/pybuggy-web.md`,
  `goga_tool_pybuggy/.usages/assembly.md`, `docs/web/configuration.md`, and `pyproject.toml`
  beyond what the working tree already carried at Task 1
- [ ] Final local commit through the R3 gate (lint + format + full suite green)

---

## Validation Commands

All commands run inside the project virtualenv (R1.2) from `/workspace`:

- `/workspace/.venv/bin/pytest tests/ -x`: Run all tests (the conventions "run all" command)
- `/workspace/.venv/bin/pytest tests/web/test_pretty.py tests/plugins/test_web_plugin.py tests/test_facade.py -v`:
  Run the feature-scoped suite (the three touched test files)
- `/workspace/.venv/bin/pytest tests/web/test_pretty.py -v`: Run a specific module's tests
- `/workspace/.venv/bin/ruff check goga_tool_pybuggy/ tests/`: Lint check (the conventions lint command)
- `/workspace/.venv/bin/ruff format --check goga_tool_pybuggy/ tests/`: Format check (apply
  `ruff format <paths>` on drift, then re-check)
- `/workspace/.venv/bin/python -c "from goga_tool_pybuggy import generation_prompt"`:
  Facade accessibility (the conventions facade check — the embedding `->generation_prompt: {}`)
- `/workspace/.venv/bin/goga lint`: Cell contract consistency across the tree (0 errors expected; CODEMANIFESTs
  are read-only)

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`: `generation_prompt`
      and `build_pretty_config` in `goga_tool_pybuggy/web/pretty.py`; the configure/web
      changes in `goga_tool_pybuggy/plugins/web_plugin.py`; the re-exports in both facades
- [ ] Every contract entity is accessible from the facade:
      `from goga_tool_pybuggy import generation_prompt` and
      `from goga_tool_pybuggy.web import generation_prompt` both resolve to
      `goga_tool_pybuggy.web.pretty.generation_prompt`
- [ ] Properties and methods match the declared API: the `prompt_extra: str = ""` parameter;
      the marker registration as configure step 1; the extras collection as web-fixture
      step 2
- [ ] Descriptions are reflected in behavior: decoration-time validation, stripped-text
      marker kwarg, `usefixtures("web")` stamp, identity return, stacking in written order,
      append semantics with empty-part skip, per-test isolation, warning-free marker use
- [ ] Contract dependencies are met: root → web re-export hop through the web cell facade;
      plugins → web keyword call at the existing import
- [ ] Re-exports are accessible from the facade (the `->generation_prompt: {}` embedding)
- [ ] Every coding task followed the TDD workflow (contract tests → code → REPL checkpoint →
      verification → logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task
      (18 new test functions; 22 collected cases)
- [ ] The REPL cycle (R4) ran inside every coding task: live evaluation, hot reload after
      edits, verbatim migration into the source files, post-migration re-verification
- [ ] The lint/format gates (R3) passed at the end of every task and before every local
      commit
- [ ] The coding style (R1) and test writing rules (R2) hold on every touched file
- [ ] No package boundary was expanded (no new cells, no new packages, no new test files
      beyond the three existing ones)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only); the `.usages/` files,
      `docs/web/configuration.md`, and `pyproject.toml` are untouched beyond the
      design-stage working-tree state
- [ ] All validation commands pass (the full suite, lint, format, facade smoke, `goga lint`)
- [ ] Every Usages entry is applied in at least one task: `conventions` (R1–R3, every task),
      the ralphex REPL protocol (R4, every coding task),
      `prettyplay` (Tasks 2, 3, 6), `pluginator` (Tasks 5, 6), `allure-pytest`
      (Task 6 — forced absent in fixture tests), `pybuggy-web` (Tasks 7, 8 — the consumer
      import surface)
