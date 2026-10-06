# Plan: `feature-sandbox` — session-scoped isolated service testing inside pybuggy

Topic directory: `.goga/history/2026/feature-sandbox/`. Compiled from the verified design
document `design.md` (post design-review, 9 fixes applied) and the CODEMANIFEST tree of branch
`feature/sandbox`. Executed by ralphex through Claude Code, one task per iteration.

## Purpose

Implement the sandbox capability: session-scoped isolated service testing inside pybuggy, driven
by a `.sandbox.yml` document in the consumer repository. After implementation the package
provides:

- four new cells — `goga_tool_pybuggy/sandbox/config` (declarative model + fail-fast loader),
  `sandbox/engines` (per-kind instance engines: container, data plane, baseline journal, reset),
  `sandbox/data` (lazy declaration surface: views, batch, presets), `sandbox` (session runtime:
  ordered lifecycle, service container, env rendering, pytest activation);
- plugin integration — `install()` arms the sandbox, `configure()` fails fast on the
  `--base-url` conflict, the `api` fixture substitutes the sandbox address and guards every
  request (apply pending batch + died-service check);
- `pybuggy init` bootstrap distribution of the sandbox usage files;
- root facade re-exports `active_sandbox` and `services`.

The most important gaps between contract and code: the entire sandbox subtree exists only as
CODEMANIFEST + `.usages/` files (no Python), the plugin/init/root cells lack the sandbox
integration, `pyproject.toml` lacks the new dependencies and the `.usages` package-data patterns.

Overall implementation strategy: leaf-first cell order (config → engines → data → sandbox →
plugin / commands-init / root), strict TDD per entity (contract tests first), docker-gated
integration coverage for container behavior, REPL-driven development loop (Mandatory Rules R4),
ruff lint/format gates at every stage and before every local commit (Mandatory Rules R3).

## Context

### Contract Surface

#### Cell `goga_tool_pybuggy/sandbox/config` (leaf; practices `conventions`, `ruamel-yaml`)

**Entity: `SandboxConfig(service, instances, data)`** — Type: class; `location: sandbox_config.py`;
facade: importable from `goga_tool_pybuggy.sandbox.config`. Properties: `service -> ServiceConfig`
(the service-under-test entry), `instances -> dict[str, InstanceConfig]` (keyed by instance name;
several instances of one kind allowed), `data -> StartupData` (startup data layer). Requirements:
pydantic model, `kw_only`; data sections default empty; the service entry is required.

**Entity: `ServiceConfig(image, env, port, health)`** — Type: class; `location: service.py`.
Properties: `image -> str`, `env -> dict[str, str]` (values may carry instance address
placeholders), `port -> int`, `health -> str | None` (None ⇒ port readiness only).

**Entity: `InstanceConfig(name, kind, image)`** — Type: class; `location: instance.py`.
Properties: `name -> str` (addressable key + placeholder name), `kind -> str` (postgresql, kafka,
vault, http), `image -> str | None` (override; None keeps the product-pinned default).
Constraint: no kind outside the four supported ones.

**Entity: `StartupData(vault, http, kafka, postgres)`** — Type: class; `location: startup_data.py`.
Properties: `vault -> dict[str, list[dict[str, object]]]` (instance → secret declarations),
`http -> dict[str, list[dict[str, object]]]` (instance → mapping declarations),
`kafka -> dict[str, str]` (instance → AsyncAPI spec path; converts to one startup spec operation
per kafka instance), `postgres -> dict[str, list[str]]` (instance → init SQL; each statement
converts to one startup insert operation carrying the `sql` key). Requirements: sections default
empty; declaration order is application order. Constraint: do not reorder declarations.

**Routine: `load_sandbox_config(path: str | None) -> config: SandboxConfig | None`** —
`location: loader.py`. Fail-fast read+validate of `.sandbox.yml` (None ⇒ CWD). Validation:
parse, service entry, instance kinds (grpc → explicit "not supported yet"), data-section
targets, service env placeholders. Every failure names the document location and the offending
entry. Constraints: no defaulting/repairing; read nothing beyond the named document.

#### Cell `goga_tool_pybuggy/sandbox/engines` (Imports: `InstanceConfig` from `sandbox/config`)

**Entity: `DataOperation(instance, kind, action, payload)`** — Type: class; `location:
operation.py`. The uniform operation unit (startup data, presets, in-test operations, journal
entries). Properties: `instance -> str`, `kind -> str`, `action -> str` (insert / produce / put /
stub + startup-only `spec`), `payload -> dict[str, object]` (plain serializable data). Fixed
action set per kind; the startup-only postgresql insert carries a raw `sql` payload key instead
of `table`+`rows`.

**Entity: `InstanceAddress(host, port)`** — Type: class; `location: address.py`. The mapped
address of a started instance. Addresses are always read back from the container engine — never
a fixed host port.

**Routine: `check_runtime()`** — `location: runtime.py`. Pre-start daemon probe; unreachable →
`RuntimeError` naming the requirement. Constraint: probe only, start nothing.

**Routine: `build_engine(config: InstanceConfig) -> engine: BaseEngine`** — `location:
runtime.py`. Kind → engine factory; unmapped kind fails listing the supported kinds; the image
override reaches the engine via `config.image`.

**Entity: `BaseEngine(config)`** — Type: class; `location: base.py`. Property `address ->
InstanceAddress`. Methods: `start(startup: list[DataOperation])` (container + readiness + data
plane + journaled startup; failed start leaves nothing behind), `apply(operations)` (execute in
order; never records), `record(operations)` (journal extend), `reset()` (kind wipe + journal
replay through the apply path), `stop()` (remove container, close plane; safe when stopped).
Constraints: engines own dependency instances only; no operations before start completes.

**Mutations**: `BaseEngine::PostgresEngine` (`postgres.py`), `BaseEngine::KafkaEngine`
(`kafka.py`), `BaseEngine::VaultEngine` (`vault.py`), `BaseEngine::HttpEngine` (`http.py`) —
each kind implements container build/readiness/data plane/wipe (see Tasks 8–11 for the full
per-kind contracts).

#### Cell `goga_tool_pybuggy/sandbox/data` (Imports: `DataOperation`, `InstanceAddress` from `sandbox/engines`)

**Entity: `DataBatch()`** — Type: class; `location: batch.py`. Methods: `add(operation)`
(append; nothing executes), `take() -> operations: list[DataOperation]` (drain in accumulation
order). One batch per test; accumulation order is the per-instance application order.

**Entities: `PostgresInstance(name, address, batch)` / `KafkaInstance` / `VaultInstance` /
`HttpInstance`** — Type: class; `location: postgres.py` / `kafka.py` / `vault.py` / `http.py`.
Properties: `name -> str`, `host -> str`, `port -> int` (from `address`). Methods (declare only,
lazy): `insert(table, rows)`, `produce(topic, value, key)`, `put(path, data)`, `stub(mapping)`.
Mapping objects pass through as given.

**Routine: `services(...presets) -> decorator: Callable`** — `location: presets.py`. Per-test
data-preset decorator (kind → instance name → declaration list). Kinds validated at decoration;
instance names resolve at enqueue against the sandbox configuration (decision 3A). Constraint:
nothing executes at decoration time.

#### Cell `goga_tool_pybuggy/sandbox` (Imports: 4 types + `sandbox-file` from config; 5 types from engines; 5 types + `data-operations` from data)

**Entity: `Sandbox(config)`** — Type: class; `location: sandbox.py`. Property `base_url -> str`.
Methods: `start()` (runtime probe → engines with startup ops in fixed section order → env render
→ service start/readiness → base_url; visible progress; failure stops+raises), `stop()`
(everything removed on every exit path; idempotent), `clear()` (reset every engine; service keeps
running), `baseline() -> BaselineBoundary`, `apply_pending()` (take batch, group by instance
preserving order, apply per engine), `ensure_service()` (died-service error naming the service +
its output), view factories `postgresql/kafka/vault/http(name)` (unknown name or kind mismatch
fails fast listing the configured instances). Owns one `DataBatch` per test via `new_test_batch`.

**Entity: `BaselineBoundary(sandbox)`** — Type: class; `location: baseline.py`. Methods
`open()` / `close()`; supports the `with` form. Inside the boundary operations apply immediately
and land in the journals; closing freezes the journals as the session baseline.

**Entity: `ServiceContainer(config)`** — Type: class; `location: service_container.py`.
Properties `host -> str`, `port -> int`. Methods: `start(env)` (rendered env; readiness = port or
health path), `stop()`, `alive() -> bool`, `logs() -> str`. Constraint: never restarted on reset.

**Routine: `render_service_env(env, addresses) -> rendered: dict[str, str]`** — `location:
env_render.py`. Strict jinja2 rendering of the service env values against
`{name: {"host", "port"}}`; unknown placeholder fails naming the value.

**Routines: `activate_sandbox(context) -> config: SandboxConfig | None` and
`active_sandbox() -> sandbox: Sandbox | None`** — `location: activation.py`. Presence-gated
arming: load config, register `pytest_sessionstart` / `pytest_sessionfinish` /
`pytest_runtest_setup` into `context` (wrap a pre-existing same-name callable, prior first);
None ⇒ fully inert. `active_sandbox()` is the module-level session lookup seam (same object every
call; lookup only). Constraint: no containers start here.

#### Changed entities (existing cells)

- `install(...kwargs)` — `plugin/__init__.py`: new step 2 — arm via `activate_sandbox(context)`,
  keep the activation on the plugin (`plugin.sandbox_activation = activation` after construction);
  steps renumbered.
- `ApiPlugin` — `plugin/plugin.py`: new property `sandbox_activation -> SandboxConfig | None`
  (plain attribute initialized to None in `__init__`; not a pluginator option).
- `ApiPlugin.configure()` — new step 3: typed `--base-url` ∧ armed sandbox ⇒ `pytest.UsageError`
  naming both facts (steps renumbered 4–5).
- `ApiPlugin.api()` — step 1 resolves base_url through `active_sandbox()` (read-time choice);
  new step 3: guard the request path (`apply_pending` + `ensure_service` before the original
  request).
- `run_bootstrap(template_mode)` — `commands/init/init.py`: step 2 discovery root widened to the
  packaged usage roots — the api cell plus the sandbox subtree cells.
- root facade `goga_tool_pybuggy/__init__.py` — re-exports `active_sandbox` (from `.sandbox`)
  and `services` (from `.sandbox.data`).

### Re-exports

- `->active_sandbox: {}` — source: `Imports` entry `active_sandbox` from
  `goga_tool_pybuggy/sandbox` (root CODEMANIFEST line 200). Facade obligation: importable from
  `goga_tool_pybuggy`.
- `->services: {}` — source: `Imports` entry `services` from `goga_tool_pybuggy/sandbox/data`
  (root CODEMANIFEST line 202). Facade obligation: importable from `goga_tool_pybuggy`.
- Cell facades (`__all__`): config — `SandboxConfig`, `ServiceConfig`, `InstanceConfig`,
  `StartupData`, `load_sandbox_config`; engines — `DataOperation`, `InstanceAddress`,
  `check_runtime`, `build_engine`, `BaseEngine`, `PostgresEngine`, `KafkaEngine`, `VaultEngine`,
  `HttpEngine`; data — `DataBatch`, `PostgresInstance`, `KafkaInstance`, `VaultInstance`,
  `HttpInstance`, `services`; sandbox — `Sandbox`, `BaselineBoundary`, `ServiceContainer`,
  `render_service_env`, `activate_sandbox`, `active_sandbox`.

### Usages Context

- `conventions` (`.goga/usages/conventions.md`): mandatory Python rules — relative imports,
  pydantic `kw_only` models, structured logging, Google docstrings, test structure, dependency
  declaration. Used by every touched cell. Extracted in full into **Mandatory Rules** below —
  they override any stylistic preference of the implementing agent.
- `ruamel-yaml` (`.goga/usages/cooks/ruamel-yaml.md`): round-trip YAML API for parsing
  `.sandbox.yml` — `YAML()` instance, `yaml.load(path)`, None-for-empty handling; validation on
  the parsed mapping before model construction. Used by `load_sandbox_config`.
- `testcontainers` (`.goga/usages/cooks/testcontainers.md`): container lifecycle —
  `PostgresContainer` (module readiness, accessor-based host/port), `DockerContainer` +
  `with_exposed_ports` / `with_env` / `with_command` / `with_labels` (+ volume mount for the
  kafka spec), `wait_for` / explicit probe loops with deadlines, Ryuk left enabled, stop removes.
  Used by `check_runtime`, `build_engine`, all kind engines, `ServiceContainer`.
- `psycopg` (`.goga/usages/cooks/psycopg.md`): postgres data plane — one autocommit session
  connection from container accessors (test/test/test); `%s`-bound parameters / `executemany`;
  catalog query + quoted-identifier TRUNCATE at reset; `conn.close()` at stop (no `with` scope —
  it is a transaction scope). Used by `PostgresEngine`.
- `kafka-python` (`.goga/usages/cooks/kafka-python.md`): `KafkaProducer(bootstrap_servers=<mapped
  address>, acks="all", retries=3, json/str serializers)`; `send` + `future.get(timeout=10)`;
  `flush(timeout=30)` as the batch boundary; `close()` at stop; deadlines everywhere. Used by
  `KafkaEngine`.
- `mokapi` (`.goga/usages/cooks/mokapi.md`): kafka mock contract — spec as the start argument,
  volume mount, health at `/health` (HTTP 8080), kafka listener 9092, restart-wipe semantics.
  Used by `KafkaEngine`.
- `vault-dev` (`.goga/usages/cooks/vault-dev.md`): vault dev-mode contract — env flags, fixed
  root token, KV v2 paths (`/v1/secret/data/<path>`), health endpoint (`/v1/sys/health`),
  restart-wipe semantics. Used by `VaultEngine`.
- `wiremock` (`.goga/usages/cooks/wiremock.md`): http mock contract — `POST /__admin/mappings`
  (passthrough), `POST /__admin/mappings/reset`, readiness `GET /__admin/health` (3.x; fall back
  to `GET /__admin/mappings`), near-miss visibility. Used by `HttpEngine`.
- `requests` (`.goga/usages/cooks/requests.md`): HTTP client for vault/wiremock data planes and
  health probes — `requests.post/get(url, headers=…, json=…, timeout=5)`; probe loops with
  deadlines. Used by `VaultEngine`, `HttpEngine`, `ServiceContainer`.
- `jinja2` (`.goga/usages/cooks/jinja2.md`): `Environment(undefined=StrictUndefined)`; context
  `{instance: {"host", "port"}}`; per-value render; failures name the env key. Used by
  `render_service_env` (the plugin's configure-phase `render_base_url` stays untouched).
- `pluginator` (`.goga/usages/cooks/pluginator.md`): `install_pytest_plugins`,
  `call_context`, fixtures as plugin-class methods, the `configure()` lifecycle. Hooks land in
  the conftest namespace dict; `configure()` is a plain method called at configphase. Used by
  the plugin cell and the sandbox hook registration.

### Imported Usages

- `sandbox-file` from `goga_tool_pybuggy/sandbox/config` — path
  `goga_tool_pybuggy/sandbox/config/.usages/sandbox-file.md`. The `.sandbox.yml` authoring
  semantics (layout, placeholder syntax `{{<name>.host}}` / `{{<name>.port}}`, section order,
  constraints). Consumed by the sandbox cell annotations (`Sandbox`, `render_service_env`,
  `activate_sandbox`).
- `data-operations` from `goga_tool_pybuggy/sandbox/data` — path
  `goga_tool_pybuggy/sandbox/data/.usages/data-operations.md`. The laziness contract and the
  declaration shapes. Consumed by `Sandbox.apply_pending` and re-exported to consumers via the
  root.
- `sandbox-session` from `goga_tool_pybuggy/sandbox` — path
  `goga_tool_pybuggy/sandbox/.usages/sandbox-session.md`. The consumer fixture patterns
  (activation, session fixture + baseline, autouse reset, api usage). Consumed by the plugin and
  root annotations.

### Local Usages

None to create or modify. The design's `.usages/` Update section verified all cell usage files
current: `sandbox-session.md`, `sandbox-file.md` (incl. the idempotent-startup-SQL line added in
review), `data-operations.md` exist and match the manifests; `sandbox/engines` has no `.usages/`
by plan; `plugin/.usages/enable.md`, `commands/init/.usages/init.md`, root `.usages/assembly.md`
were updated by the apply-architecture stage. No usage-file tasks.

### External Dependencies

New main dependencies (Task 2; minimum versions per conventions): `testcontainers[postgres]>=4.0`,
`psycopg[binary]>=3.1`, `kafka-python>=2.2`, `requests>=2.31`. Existing dependencies reused:
`ruamel.yaml`, `jinja2`, `pydantic`, `pluginator`. No test-extra additions; docker-gated tests
use `skipif`. Pinned container defaults: postgres `postgres:16-alpine`; kafka
`mokapi/mokapi:0.28.0` (HTTP 8080 + kafka 9092); vault `hashicorp/vault:1.17` (port 8200, dev
token constant `"sandbox-root"`, never logged); http `wiremock/wiremock:3.13.0` (port 8080).
Labels on every container: `{"pybuggy-sandbox": "true"}`.

### Interaction Diagram (verbatim from the design)

```
consumer conftest            plugin cell                       sandbox cell (session runtime)
──────────────────           ────────────                      ─────────────────────────────
plugin.install() ───────────▶ install()
                             │  context = call_context()
                             │  activation = activate_sandbox(context) ──▶ activation.py
                             │        │                                      │ load_sandbox_config
                             │        │                                      ▼
                             │        │                          .sandbox.yml ─▶ config cell
                             │        │                                      │ SandboxConfig | None
                             │        │◀── SandboxConfig | None ─────────────┘
                             │        │ registers pytest_sessionstart /
                             │        │ pytest_sessionfinish / pytest_runtest_setup
                             │        │ into context (conftest namespace)
                             │  plugin.sandbox_activation = activation
                             │  ApiPlugin(context, loaders)
                             │  install_pytest_plugins(plugin, context)
                             ▼
pytest lifecycle ───────────▶ ApiPlugin.configure()
                             │  typed --base-url ∧ armed ──▶ pytest.UsageError (fail fast)
                             │
pytest_sessionstart ───────────────────────────────────────────▶ Sandbox(config).start()
                                                                 │ check_runtime (engines)
                                                                 │ build_engine ×N (engines)
                                                                 │ engine.start(startup ops) ×N
                                                                 │   ── startup ops built from
                                                                 │      StartupData (config)
                                                                 │ render_service_env(env, addresses)
                                                                 │ ServiceContainer(config).start(env)
                                                                 │ base_url = http://host:port
                                                                 │ active_sandbox() ─▶ the Sandbox

test phase (per test)
pytest_runtest_setup ──────────────────────────────────────────▶ fresh DataBatch (data cell)
  @services(...) marker ─────▶ enqueue preset DataOperations ──▶ batch.add
consumer reset fixture ───────▶ sandbox.clear() ─▶ engine.reset() ×N (wipe + journal replay)
sandbox.postgresql("db") ─────▶ PostgresInstance(name, address, batch) (data cell)
  .insert(...) ───────────────▶ batch.add(DataOperation)        (lazy — nothing executes)
api fixture (plugin) ─────────▶ base_url := active_sandbox().base_url
  Api.request guarded ────────▶ sandbox.apply_pending() ─▶ batch.take ─▶ engine.apply ×N
                             └▶ sandbox.ensure_service() ─▶ ServiceContainer.alive/logs
pytest_sessionfinish ──────────────────────────────────────────▶ Sandbox.stop()
                                                                 │ service.stop(); engine.stop() ×N
```

Cell dependency direction (no cycles; sandbox subtree never imports plugin/api/root):

```
root ─▶ sandbox ─▶ config (leaf)
 │ │      └─────▶ engines ─▶ config
 │ └─▶ sandbox/data ─▶ engines
 └─▶ plugin ─▶ sandbox, sandbox/config, api, plugin/loaders
commands/init ─▶ plugin (PluginConfigKeys)          [run_bootstrap scope extension only]
```

### Data Flows (verbatim summaries from the design)

- **Startup flow** (entry: `pytest_sessionstart`): `SandboxConfig` → per-instance
  `list[DataOperation]` (StartupData sections in the fixed order vault → http → kafka →
  postgres) → `BaseEngine.start(startup)` (container + readiness + data plane + journaled
  startup) → `dict[str, InstanceAddress]` → `render_service_env` → `dict[str, str]` rendered env
  → `ServiceContainer.start(env)` → readiness → `Sandbox.base_url` (str). Failure at any step
  stops and removes everything started so far, then re-raises.
- **Declaration → apply flow** (entry: `pytest_runtest_setup`, then the guarded first request):
  `services(...)` marker presets → `DataOperation`s enqueued into the fresh `DataBatch`; in-test
  view calls append more `DataOperation`s; the guarded `Api.request` drains the batch (`take()`),
  groups by instance preserving accumulation order, applies each group through the instance's
  `BaseEngine.apply`. Nothing executes at declaration time.
- **Baseline flow** (entry: consumer session fixture, `with sbx.baseline():`): inside the
  boundary the sandbox hands views an immediate-routing batch — each declared operation runs
  `engine.apply([op])` + `engine.record([op])` at declaration time. `close()` freezes the
  journals (startup ops + boundary ops, in application order).
- **Reset flow** (entry: consumer autouse fixture, `sandbox.clear()`): per engine — postgresql:
  catalog discovery + `TRUNCATE ... RESTART IDENTITY CASCADE`, then journal replay; kafka/vault:
  docker restart of the same container (address unchanged), readiness re-wait, data-plane client
  rebuilt, then journal replay (the journaled kafka `spec` op replays as a no-op); http:
  `POST /__admin/mappings/reset`, then journal replay. The service container is never restarted.
- **Teardown flow** (entry: `pytest_sessionfinish`): `Sandbox.stop()` — service stop, then
  engines in reverse start order, each guarded; `active_sandbox()` returns None afterwards. Ryuk
  (testcontainers) is the crash-path safety net behind the explicit stop.

## Facts

- The design passed `goga-review-design`: all 15 code-stack traces hold, 9 fixes applied;
  `goga lint` reports 23 cells, 0 errors; `goga contract` reports no issues.
- `goga_tool_pybuggy/sandbox/` exists with CODEMANIFEST + `.usages/` only — no Python files
  anywhere in the subtree (untracked in git).
- The three cell usage files (`sandbox-session.md`, `sandbox-file.md`, `data-operations.md`)
  exist and are current; all project cooks referenced by the manifests exist under
  `.goga/usages/cooks/`.
- The existing tests tree mirrors the source (`tests/plugin/`, `tests/commands/init/`, …) with
  `__init__.py` per directory and `tests/conftest.py` present; `tests/sandbox/` does not exist.
- No virtualenv exists in the repo yet (`python3` is 3.12.15 at `/opt/goga/bin/python3`);
  conventions require creating one and executing everything inside it.
- `pyproject.toml`: main dependencies lack `testcontainers` / `psycopg` / `kafka-python` /
  `requests`; `[tool.setuptools.package-data]` lists `skills/**/*`, `pipelines/*.yml`,
  `assets/**/*` — no `.usages` patterns (packaged usage files would be missing from the wheel);
  ruff configured (`target-version = "py310"`, `line-length = 120`, rule sets E/W/F/I/N/UP/B/
  SIM/PL/PLR/C4/DTZ/PT/ARG/RUF/PTH/C90, mccabe max-complexity 10, per-file ignores for tests);
  pytest `testpaths = ["tests"]`, `addopts = "-v --tb=short"`.
- `plugin/__init__.py` `install()` has no arming step; `plugin/plugin.py` has no
  `sandbox_activation`; `configure()` lacks the fail-fast; the `api()` fixture reads
  `self.base_url` directly.
- `commands/init/init.py` discovers packaged usages from the single root
  `goga_tool_pybuggy.api`; the `_walk` recursion also collects `asserts.md` (the `asserts`
  sub-package rides the api root today — five stems total after the change, not four).
- Root `goga_tool_pybuggy/__init__.py` does not export `active_sandbox` / `services`.
- Docker availability is not guaranteed in the execution environment — container-dependent
  tests must be `skipif`-gated (`requires_docker`).

## Gap Analysis

- Missing contract entities: all 26 sandbox entities across the four new cells (the entire
  subtree is unimplemented).
- Missing facade exposure: all four cell facades (`sandbox/config`, `sandbox/engines`,
  `sandbox/data`, `sandbox`) and the two root re-exports.
- Incorrect `location` placement: none — no code exists to place.
- API mismatches: `install()` (no arming step), `ApiPlugin` (no `sandbox_activation` property),
  `ApiPlugin.configure()` (no fail-fast step 3), `ApiPlugin.api()` (no substitution / guard),
  `run_bootstrap` (single discovery root).
- Behavioral mismatches: same five surfaces; everything else in the touched cells is unchanged
  by contract.
- Existing code that can be reused: `render_base_url` in `plugin/render.py` (reference pattern
  for the jinja2 `Environment` — not shared code, separate cells); `PackageLoader` default in
  `install()`; the existing install tests' `call_context` monkeypatching pattern
  (`tests/plugin/test_install.py`); the bootstrap test harness
  (`tests/commands/init/test_bootstrap.py`); `_walk` / `_discover_usages` in `init.py`.
- Test coverage gaps: the entire sandbox surface; the plugin sandbox tests, the bootstrap
  sandbox-usages tests, and the root facade test do not exist.
- Missing visibility: `goga_tool_pybuggy/sandbox/` is untracked (`??` in git status) — it lands
  in git with the first task commit.

## Mandatory Rules

Rules extracted from the project convention `.goga/usages/conventions.md` (plus the Python cell
rules). They are **mandatory for every task and every stage of this plan** — the contract is
followed first, then these conventions, then language idioms.

### R1. Coding Style Rules (strictly per project convention)

1. Python 3.10+ only. All configuration lives in `pyproject.toml`.
2. Execute ALL code (tests, REPL, probes, builds) inside a virtualenv; create it if missing
   (Task 1). Never run the project with the system interpreter.
3. Imports: relative imports for all intra-package references; absolute imports only for stdlib
   and third-party packages. An absolute import within the same package is forbidden.
4. Data models: pydantic for all data models; every model class uses `kw_only=True`; set empty
   defaults (empty string, zero, empty dict/list) for all fields — `None` only for fields that
   represent the explicit absence of a value (`health`, `image`).
5. Logging: the `logging` library with a module-level `logger = logging.getLogger(__name__)`;
   operational logs carry contextual metadata via `extra={...}`, are machine-readable, and use
   lowercase, concise, stable event names. Level policy: DEBUG — intermediate state, payload
   previews, rendered env values, guard invocations; INFO — lifecycle events (runtime check,
   instance starting/ready, startup data applied, env rendered, service starting/ready, base_url
   source, stopped); WARNING — recoverable abnormality; ERROR — start/stop failures, died
   service; CRITICAL — immediate operator intervention only. Never log secrets, credentials, or
   tokens — the vault dev token `"sandbox-root"` and vault secret payloads are never logged; env
   dumps go per-key at DEBUG, never as one line.
6. Formatting inside function/method bodies: logical blocks are separated by one blank line
   (variable initialization vs conditionals/loops; data preparation vs processing; processing vs
   return).
7. Docstrings: Google style, mandatory on all public functions, methods, and classes; first
   line capitalized and ending with a period; `Args` / `Returns` / `Raises` sections as
   applicable; brief, professional, one point per comment.
8. Type hints are mandatory. Allowed signature types: `str`, `int`, `float`, `bool`, `list[T]`,
   `dict[str, T]`, `T | None`. Forbidden: `*args` / `**kwargs` (the single documented exception:
   `services(...presets)`), `dict` / `list` without generics.
9. Every third-party library is declared in `pyproject.toml` with a minimum version.
10. Naming: PascalCase classes, snake_case functions/methods/properties; internal helpers keep
    support-intent names, tests name entity + scenario + expectation.

### R2. Test Writing Rules (strictly per project convention)

1. pytest; test code compatible with Python 3.10+; executed in the virtualenv.
2. Tests mirror the source structure directly: `goga_tool_pybuggy/sandbox/config/loader.py` →
   `tests/sandbox/config/test_loader.py`; sandbox-cell root modules →
   `tests/sandbox/test_<module>.py`. Every new test directory contains `__init__.py`. Local
   fixtures live in `tests/<package>/conftest.py`, shared fixtures in `tests/conftest.py`.
   Integration tests covering multiple root packages go directly in `tests/`.
3. Naming: files `test_<module>.py`; functions `test_<what>_<scenario>` (e.g.
   `test_complexity_with_empty_input`); grouping `class Test<Component>:`.
4. Coverage: unit tests for every public function/method/class (main scenario + typical data);
   edge cases — empty inputs (`None`, `""`, `[]`, `{}`), boundary values (`0`, negative, very
   large), invalid types, expected exceptions via `pytest.raises`; integration tests only for
   interaction between modules/packages. Contract tests (facade accessibility, API shape,
   signatures) are written FIRST in each coding task and expected to fail initially (TDD).
5. Boundary tests (thresholds, ranges, state transitions) use `@pytest.mark.parametrize` with a
   table of values including each boundary.
6. Mocks only at external boundaries: pure logic tested without mocks; file I/O exclusively via
   the `tmp_path` fixture; subprocesses via `mock.patch` of the subprocess call; external
   dependencies patched at the import point.
7. Container-dependent tests are gated with `pytest.mark.skipif` (`requires_docker`); no network
   in unit tests.
8. Self-documenting test names; keep comments minimal.
9. Test libraries are declared in `[project.optional-dependencies]` under the `test` key.

### R3. Lint and Format Enforcement (all development stages and local commits)

1. ruff is the single linter and formatter for source and test code (configuration already in
   `pyproject.toml`: target py310, line-length 120, the full rule selection, mccabe
   max-complexity 10).
2. Every development stage — writing contract tests, implementing, writing logic tests,
   debugging — keeps the tree lint-clean: run `ruff check goga_tool_pybuggy/ tests/` after each
   stage, not only at task end. Apply `ruff format` to touched files whenever formatting drift
   appears.
3. Every task ends with the lint gate: `ruff check goga_tool_pybuggy/ tests/` exits 0.
4. Local commits: before EVERY local commit (task commit, fix commit, wip commit), run
   `ruff check goga_tool_pybuggy/ tests/` — committing lint findings is forbidden; fix first,
   then commit. This gate applies to every ralphex task commit in this plan.
5. When the complexity gates (C90/PLR) trip, decompose inside the current cell (internal helpers
   are allowed; new cells are not).

### R4. REPL Cycle Rules (continuous interactive evaluation, hot reloading, code migration)

1. The workflow of every coding task is a REPL loop: **prototype → evaluate → migrate →
   re-verify**, repeated per entity.
2. **Prototype**: exercise every non-trivial behavior fragment in an interactive Python session
   inside the virtualenv (`.venv/bin/python -i`, or a heredoc `.venv/bin/python - <<'PY'`) with
   real inputs — sample `.sandbox.yml` content, real placeholder strings, real SQL/payload
   shapes, real container API calls — BEFORE the code lands in source files.
3. **Evaluate**: compare the observed REPL output against the design trace expectations;
   iterate in the REPL until the behavior matches. During debugging, reproduce the failing input
   in the REPL with the exact test data before fixing anything.
4. **Hot reloading**: keep one REPL session per task where practical; after source edits,
   re-import with `importlib.reload(module)` instead of restarting the session. Use the focused
   test file (`pytest tests/<mirror>/test_<module>.py -x -v`) as the fast feedback loop and the
   full suite at task end.
5. **Code migration to source files**: the verified REPL snippet is a prototype — migrate it
   into the target `location` file in convention-complete form (docstrings, type hints,
   blank-line block separation, structured logging). No behavior ships REPL-only: every verified
   fragment lands in a source file or a test.
6. **Scratch hygiene**: prototypes live in the REPL or under `/tmp` — never as files inside the
   repo; nothing scratch is committed.
7. Docker-dependent prototypes (engine containers, service container) run in the REPL only when
   the container runtime is available; otherwise verify against the traced pseudocode and the
   fake-based unit tests.

### R5. Contract Discipline

1. `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. If the
   implementation does not match the contract, fix the implementation — never the contract. The
   single manifest fix of the design is already applied; no further manifest changes without a
   new design pass.
2. Facade obligations: every contract entity is importable from its cell package root via
   `__all__`; only identifiers in `__all__` constitute the facade.
3. Traceability: every implementation unit and test maps to a contract entity / property /
   method / described requirement (the per-task entity lists carry the mapping).
4. No new cells; internal helpers stay inside the current cell; `location` placement is obeyed
   exactly; relative imports inside the package.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the
> next. Within each coding task, contract tests are written first (TDD workflow). Cell order:
> `sandbox/config` → `sandbox/engines` → `sandbox/data` → `sandbox` → `plugin` →
> `commands/init` → root facade → end-to-end validation. Every task follows the Mandatory Rules
> (R1–R5); the lint gate of each task is also the pre-commit gate (R3.4).

---

### Task 1: Workspace bootstrap — virtualenv, sandbox package skeleton, mirrored test tree (infrastructure)

Prepare the execution environment and the empty package/test skeleton the config cell lands in.
The `sandbox/` directory exists with CODEMANIFEST + `.usages/` only; Python package markers are
missing. The virtualenv does not exist yet — conventions require creating it and running
everything inside it (R1.2).

**Usages relevant to this task:**
- `conventions`: virtualenv execution, pyproject-based configuration, package/test tree
  mirroring (`goga_tool_pybuggy/sandbox/config/*.py` → `tests/sandbox/config/test_*.py`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create the virtualenv: `python3 -m venv .venv` and install the project editable with the
  test extra: `.venv/bin/pip install -e '.[test]'`; verify `.venv/bin/python -c "import
  goga_tool_pybuggy"` succeeds
- [x] Create `goga_tool_pybuggy/sandbox/__init__.py` — package marker with a module docstring
  only (the 6-name facade is populated in Task 22, after all sandbox-cell entities exist)
- [x] Create `goga_tool_pybuggy/sandbox/config/__init__.py` — docstring + `__all__ = []`
  (populated progressively by Tasks 3–4)
- [x] Create `tests/sandbox/__init__.py` and `tests/sandbox/config/__init__.py`
- [x] Verify package importability: `.venv/bin/python -c "import goga_tool_pybuggy.sandbox;
  import goga_tool_pybuggy.sandbox.config"`
- [x] Verify the existing suite still passes: `.venv/bin/pytest tests/ -x` (baseline green)
- [x] Lint gate (also the pre-commit gate for this task's commit): `.venv/bin/ruff check
  goga_tool_pybuggy/ tests/` — exit 0

### Task 2: Dependencies and packaged usage data in `pyproject.toml` (infrastructure)

Declare the new runtime dependencies and the package-data patterns so the sandbox imports are
always satisfiable and `run_bootstrap` finds the packaged `.usages/*.md` files via
`importlib.resources` in a built wheel. From the design's Additional Instructions.

**Usages relevant to this task:**
- `conventions`: all third-party libraries in `pyproject.toml` with minimum versions (R1.9).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Add to `[project.dependencies]` (main block): `testcontainers[postgres]>=4.0`,
  `psycopg[binary]>=3.1`, `kafka-python>=2.2`, `requests>=2.31`; no test-extra additions
- [x] Extend `[tool.setuptools.package-data]` with `".usages/*.md"` and `"**/.usages/*.md"` so
  the api cell and the three sandbox cells' usage files ship in the wheel
- [x] Reinstall into the venv: `.venv/bin/pip install -e '.[test]'`; verify imports:
  `.venv/bin/python -c "import testcontainers, psycopg, kafka, requests"`
- [x] Build the wheel and verify contents: the wheel carries `api/.usages/api.md`,
  `api/asserts/.usages/asserts.md`, `sandbox/.usages/sandbox-session.md`,
  `sandbox/config/.usages/sandbox-file.md`, `sandbox/data/.usages/data-operations.md` — and no
  `CODEMANIFEST` files (exclusion via MANIFEST.in holds)
- [x] Lint gate: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0

### Task 3: Config data models — `SandboxConfig`, `ServiceConfig`, `InstanceConfig`, `StartupData` (TDD)

Implements the four declarative models of `.sandbox.yml` in the config cell. All pydantic,
`kw_only`; data sections default empty; the service entry is required. Validation lives in the
loader (Task 4) — the models carry field types, defaults, and section order only.

**Contract entities**: `SandboxConfig` (`sandbox_config.py`), `ServiceConfig` (`service.py`),
`InstanceConfig` (`instance.py`), `StartupData` (`startup_data.py`) — all importable from
`goga_tool_pybuggy.sandbox.config`.

**Usages relevant to this task:**
- `conventions`: pydantic `kw_only` data models, empty defaults (`None` only for explicit
  absence: `health`, `image`), Google docstrings, relative imports.

**Design algorithm (config cell):**
```
1. StartupData field order IS the section order (vault, http, kafka, postgres)
   → declaration order within a section is preserved by list semantics
```
Errors: pydantic type errors surface through the loader's wrapping (location + entry named).
Edge cases: empty `instances` allowed; empty `data` sections default empty; `health` None ⇒ port
readiness only.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 3 is being executed
- [x] **Contract tests** (expected to fail now): `tests/sandbox/config/test_sandbox_config.py`,
  `test_service.py`, `test_instance.py`, `test_startup_data.py` — for each model: importable
  from `goga_tool_pybuggy.sandbox.config`; constructible with keyword arguments only; declared
  properties return the declared types (`service -> ServiceConfig`,
  `instances -> dict[str, InstanceConfig]`, `data -> StartupData`; `image -> str`,
  `env -> dict[str, str]`, `port -> int`, `health -> str | None`; `name -> str`, `kind -> str`,
  `image -> str | None`; the four StartupData section types)
- [x] **REPL prototype (R4)**: in the venv REPL construct each model with sample keyword data
  (e.g. `ServiceConfig(image="my-service:latest", env={"A": "b"}, port=8080, health=None)`);
  observe defaults and field order (`StartupData.model_fields` order is vault, http, kafka,
  postgres); then migrate
- [x] **Code**: create `goga_tool_pybuggy/sandbox/config/{sandbox_config,service,instance,startup_data}.py`
  with the pydantic `kw_only` models (type-hinted fields, empty-dict defaults for the `data`
  sections and `env`, `str | None` for `health`/`image`, Google docstrings, relative imports)
- [x] **Code**: expose all four models on the cell facade — `sandbox/config/__init__.py`
  imports + `__all__ = ["SandboxConfig", "ServiceConfig", "InstanceConfig", "StartupData"]`
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/config/ -x -v` — all contract
  tests pass
- [x] **Logic tests**: keyword-only construction (positional construction raises `TypeError`);
  `data` sections and `env` default to `{}`; `health`/`image` default to `None`; `StartupData`
  field order is vault → http → kafka → postgres; several instances of one kind are allowed in
  `instances`
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation code until all tests pass
  (do NOT fix test code); reproduce failures in the REPL first (R4.3)
- [x] **Contract re-verification**: facade, API shape, and behavior match the four entity
  declarations
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format` touched files if drift
- [x] **Completion**: mark all checkboxes complete; submit for review → approval → next task

### Task 4: `load_sandbox_config` — fail-fast reading and validation of `.sandbox.yml` (TDD)

Implements the loader routine in the config cell: parse with ruamel.yaml, validate everything
before any container could start, resolve kafka spec paths, enforce the full placeholder grammar.

**Contract entity**: `load_sandbox_config(path: str | None) -> config: SandboxConfig | None`
(`loader.py`), importable from `goga_tool_pybuggy.sandbox.config`.

**Usages relevant to this task:**
- `ruamel-yaml`: `YAML()` instance, `yaml.load(path)`, None-for-empty handling; validation on
  the parsed mapping before model construction.
- `conventions`: `ValueError` messages naming the offending entry; `tmp_path` for the file
  fixture; kw_only construction of the models.

**Design algorithm (verbatim):**
```
1. resolve location: path or CWD/.sandbox.yml; absent → return None
2. parse (ruamel.yaml round-trip API); parse failure → ValueError(location, problem)
3. validate service entry: image/env/port required, health optional
4. validate instances: non-empty names; kind ∈ {postgresql, kafka, vault, http};
   kind == grpc → ValueError("kind 'grpc' is not supported yet");
   image optional override
5. validate data sections: every declaration targets an existing instance of the matching kind;
   resolve the kafka spec paths against the document directory — relative paths become absolute,
   absolute paths stay as-is (string resolution only; the file is not read)
6. validate service env placeholders against the full grammar: every {{ … }} occurrence in a
   value must be {{ <name>.host }} or {{ <name>.port }} with <name> a configured instance —
   a bare name, an unknown attribute, or an unknown name → ValueError(env key, value, location)
7. return SandboxConfig
```
Errors: `ValueError` with location + offending entry for every failure above. Edge case: empty
file → parse produces None → treated as an invalid document (a sandbox document must carry the
service entry) — error names the location. Constraints: no defaulting/repairing; read nothing
beyond the named document.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 4 is being executed
- [x] **Contract tests**: `tests/sandbox/config/test_loader.py` — importable from the facade;
  signature `(path: str | None)`; returns `SandboxConfig | None`
- [x] Create the shared loader fixture `sandbox_yaml(tmp_path, monkeypatch, content)` in
  `tests/sandbox/conftest.py` — writes `.sandbox.yml` into `tmp_path`, `monkeypatch.chdir`,
  returns the path
- [x] **REPL prototype (R4)**: in the venv REPL parse the `sandbox-file.md` example document
  with ruamel.yaml (write it to a `/tmp` file first); observe the parsed mapping shape, the
  None result for empty content, and the exception type for unparsable content; prototype the
  placeholder grammar regex against `"postgres://{{db.host}}:{{db.port}}/x"`, `"{{events}}"`,
  `"{{db.hst}}"`; then migrate
- [x] **Code**: create `goga_tool_pybuggy/sandbox/config/loader.py` implementing the 7-step
  algorithm (structured INFO log on successful load; every `ValueError` names the location and
  the offending entry)
- [x] **Code**: expose `load_sandbox_config` on the cell facade (`__all__` now carries all five
  names)
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/config/ -x -v` — pass
- [x] **Logic tests** (design test stack, verbatim scenarios):
  `test_load_returns_validated_model_for_full_document` (the `sandbox-file.md` example: service
  image `my-service:latest`, port 8080, health `/health`, three placeholders; instances
  db/events/secrets/payments; all four data sections; asserts `config.data.kafka ==
  {"events": str(tmp_path / "asyncapi.yaml")}` — resolved at load);
  `test_load_returns_none_without_document`;
  `test_load_fails_grpc_kind_with_not_supported_yet` (`ValueError, match="grpc.*not supported
  yet"`); `test_load_fails_unknown_env_placeholder_before_start` (match `"DATABASE_URL.*ghost"`);
  `test_load_fails_bare_instance_placeholder` (`"{{events}}"` → match `"KAFKA_BOOTSTRAP.*events"`);
  `test_load_fails_unknown_placeholder_attribute` (`{{db.hst}}` → match `"DATABASE_URL.*hst"`);
  `test_load_fails_data_targeting_unknown_instance` (match `"nodb"`);
  `test_load_fails_missing_required_service_field` (missing `port` named);
  `test_load_fails_unparsable_yaml` (content `":\n - ["` → location + problem named);
  `test_load_fails_empty_document` (zero bytes → match `".sandbox.yml"`)
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green (do NOT fix
  test code); reproduce failures in the REPL with the exact fixture content first (R4.3)
- [x] **Contract re-verification**: loader algorithm, requirements, and constraints hold —
  validation completes before anything starts; every message names location + entry
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

---

### Task 5: Engines cell skeleton and docker-gated test fixtures (infrastructure)

Create the engines cell package, its progressive facade, the mirrored test package, and the
docker availability fixtures every container-dependent test in the plan reuses.

**Usages relevant to this task:**
- `testcontainers`: the docker client probe pattern for availability detection
  (`docker.from_env().ping()` wrapped in try/except).
- `conventions`: shared fixtures in `tests/sandbox/conftest.py`; `skipif` for unavailable
  external dependencies.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create `goga_tool_pybuggy/sandbox/engines/__init__.py` — docstring + `__all__ = []`
  (populated progressively by Tasks 6–12)
- [x] Create `tests/sandbox/engines/__init__.py`
- [x] Extend `tests/sandbox/conftest.py` with `docker_available()` (session-scoped probe) and
  the module-level skip condition `requires_docker = pytest.mark.skipif(not docker_available(),
  reason="docker-compatible container runtime unavailable")`
- [x] Verify: `.venv/bin/python -c "import goga_tool_pybuggy.sandbox.engines"` and
  `.venv/bin/pytest tests/sandbox/ -q` (fixtures collect cleanly)
- [x] Lint gate (pre-commit): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0

### Task 6: `DataOperation` and `InstanceAddress` models (TDD)

The uniform operation unit and the mapped address record of the engines cell.

**Contract entities**: `DataOperation(instance, kind, action, payload)` (`operation.py`),
`InstanceAddress(host, port)` (`address.py`) — importable from
`goga_tool_pybuggy.sandbox.engines`.

**Usages relevant to this task:**
- `conventions`: pydantic `kw_only`, plain serializable payloads, Google docstrings.

**Common payload table (verbatim from the design — decision 2A):**

| kind | action | payload keys | origin |
|---|---|---|---|
| postgresql | `insert` | `table: str`, `rows: list[dict]` | view `insert` / preset declaration |
| postgresql | `insert` | `sql: str` | startup section only (raw statement, executed as given) |
| kafka | `produce` | `topic: str`, `value: dict \| str`, `key: str \| None` | view `produce` / preset |
| kafka | `spec` | `path: str` | startup section only (mounted at container start; replay no-op) |
| vault | `put` | `path: str`, `data: dict` | view `put` / preset / startup |
| http | `stub` | the mapping object itself (`request`, `response`, …) | view `stub` / preset / startup |

The action set stays fixed (`insert`/`produce`/`put`/`stub` + startup-only `spec`); the two
postgres payload forms are discriminated by key (`sql` vs `table`+`rows`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 6 is being executed
- [x] **Contract tests**: `tests/sandbox/engines/test_operation.py`, `test_address.py` — both
  importable from the facade; kw_only construction; property types (`instance/kind/action ->
  str`, `payload -> dict[str, object]`; `host -> str`, `port -> int`)
- [x] **REPL prototype (R4)**: construct sample operations of every payload-table row in the
  REPL (e.g. `DataOperation(instance="db", kind="postgresql", action="insert",
  payload={"sql": "CREATE TABLE …"})`); confirm payloads hold plain data only (no callables,
  no models)
- [x] **Code**: create `goga_tool_pybuggy/sandbox/engines/{operation,address}.py` (pydantic
  `kw_only` models; `port: int` — addresses carry the published host-side port)
- [x] **Code**: expose both on the engines facade (`__all__` += the two names)
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/engines/ -x -v` — pass
- [x] **Logic tests**: positional construction raises `TypeError`; payload round-trips plain
  dicts/lists/strs; edge — empty payload dict is valid
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [x] **Contract re-verification**: models match the entity declarations
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 7: `BaseEngine` and `EngineError` — the per-instance contract (TDD)

The common engine base: lifecycle, the baseline journal, reset semantics, the wrapped error
type. Kind engines (Tasks 8–11) implement the internal kind hooks this base calls.

**Contract entity**: `BaseEngine(config: InstanceConfig)` (`base.py`) — `address` property;
`start(startup: list[DataOperation])`, `apply(operations)`, `record(operations)`, `reset()`,
`stop()`. Internal exception `EngineError(RuntimeError)` lives in `base.py`.

**Usages relevant to this task:**
- `testcontainers`: container lifecycle and the Ryuk cleanup safety net behind the explicit stop.
- `conventions`: structured logging, type hints, Google docstrings.

**Design algorithm (verbatim):**
```
__init__: store config; journal = []; started = False
start(startup):
  1. build kind container (pinned image unless config.image; labels; published ports)
  2. start + wait kind readiness
  3. open the kind data-plane connection
  4. _execute(startup ops in order); journal.extend(startup)
  5. on any failure: stop() (remove the container) then re-raise
apply(operations):
  for op in operations: _execute(op)   # order preserved; never records
record(operations): journal.extend(operations)
reset():
  1. _wipe()            # kind-specific empty state
  2. for op in journal: _execute(op)   # same execution path as apply
stop():
  close the data plane; container.stop(); started = False   # safe when already stopped
address (property): InstanceAddress(host=get_container_host_ip(),
                                    port=int(get_exposed_port(<kind port>)))
```
Errors: `EngineError(RuntimeError)` — `instance '<name>': <action> failed: <cause>`; start
failures append the kind step that failed. Edge cases: `apply([])` no-op; `reset()` with an
empty journal = wipe only; `stop()` twice safe; operations before start are impossible (views
exist only after start).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 7 is being executed
- [x] **Contract tests**: `tests/sandbox/engines/test_base.py` — `BaseEngine` and `EngineError`
  importable from the facade; `EngineError` subclasses `RuntimeError`; the five methods and the
  `address` property exist with the declared signatures
- [x] **REPL prototype (R4)**: in the REPL drive a minimal fake subclass (kind hooks recording
  calls, `_execute` appending to a list): call `start` → `apply` → `record` → `reset` → `stop`
  → `stop` again; observe journal contents and call order against the algorithm above; then
  migrate the base class
- [x] **Code**: create `goga_tool_pybuggy/sandbox/engines/base.py` — `EngineError(RuntimeError)`
  and `BaseEngine` with the internal kind hooks (`_build_container`, `_wait_ready`,
  `_open_plane`, `_execute`, `_wipe`, `_close_plane` — names are internal design freedom);
  `_execute` failures wrap into `EngineError` as `instance '<name>': <action> failed: <cause>`
- [x] **Code**: expose `BaseEngine` (and `EngineError` for internal cross-module use) on the
  engines facade
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/engines/ -x -v` — pass
- [x] **Logic tests** (fake subclass, no mocks): `apply` preserves order and never records;
  `record` extends the journal; `reset` runs `_wipe` then replays the journal through
  `_execute`; `apply([])` is a no-op; `reset()` with an empty journal runs the wipe only;
  `stop()` is safe twice; a raising `_execute` surfaces as `EngineError` with the
  `instance '<name>': <action> failed: <cause>` message; a failing start calls `stop()` and
  re-raises
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [x] **Contract re-verification**: journal semantics (startup ∈ journal; apply does not
  record), stop safety, error shape
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 8: `BaseEngine::PostgresEngine` — real postgres instance (TDD)

The postgresql kind engine: module container, one autocommit psycopg session, both insert
payload forms, catalog-driven TRUNCATE wipe.

**Contract entity**: `BaseEngine::PostgresEngine(config)` (`postgres.py`).

**Usages relevant to this task:**
- `psycopg`: `psycopg.connect(host, port, user="test", password="test", dbname="test",
  autocommit=True)` — one session connection; `%s`-bound parameters / `executemany`; catalog
  query + quoted-identifier TRUNCATE; `conn.close()` at stop (no `with` scope — it is a
  transaction scope).
- `testcontainers`: `PostgresContainer(config.image or "postgres:16-alpine")`, labels, module
  readiness (start returns after the server accepts connections).

**Design contract (verbatim):**
```
container: PostgresContainer(config.image or "postgres:16-alpine"), labels;
           module readiness (accepts connections)
plane:     psycopg.connect(host, port, user="test", password="test", dbname="test",
           autocommit=True) — one session connection
_execute:  payload{sql} → cur.execute(sql)
           payload{table,rows} → executemany('INSERT INTO "<t>" ("<c1>",…) VALUES (%s,…)', rows)
           (empty rows → skip the statement — a no-op)
_wipe:     catalog discovery (information_schema, BASE TABLE, non-system schemas) at reset time
           → TRUNCATE TABLE "s"."t", … RESTART IDENTITY CASCADE (identifiers quoted, one stmt)
stop:      conn.close(); container.stop()
```
Errors: psycopg errors carry the server message (`.diag.message_primary`) into the EngineError
wrap. Edge: empty catalog (no user tables) → skip TRUNCATE (replay only); startup SQL must be
idempotent (e.g. `CREATE TABLE IF NOT EXISTS`) — the journal replays it after every
TRUNCATE-based reset and TRUNCATE keeps tables in place. Constraint: never format SQL with
interpolated values — parameters are bound server-side; identifiers are double-quoted.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 8 is being executed
- [x] **Contract tests**: `tests/sandbox/engines/test_postgres.py` — `PostgresEngine`
  importable from the facade; subclasses `BaseEngine`; inherits the contract surface
- [x] **REPL prototype (R4, docker-gated)**: with the runtime available, start a
  `PostgresContainer("postgres:16-alpine")` in the REPL; connect via psycopg accessors
  (test/test/test, autocommit); execute `executemany` of a parameterized insert; run the catalog
  discovery query against `information_schema.tables`; observe the mapped host/port accessors;
  then migrate (if docker is unavailable, verify the SQL fragments against the psycopg cook and
  proceed — the docker-gated tests below will cover the live behavior)
- [x] **Code**: create `goga_tool_pybuggy/sandbox/engines/postgres.py` implementing the kind
  hooks: container (`config.image or "postgres:16-alpine"`, labels `{"pybuggy-sandbox":
  "true"}`), module readiness, the autocommit plane, `_execute` for both payload forms (column
  list from the first row's keys in insertion order; empty rows → no-op), `_wipe` (catalog
  discovery at reset time, one `TRUNCATE TABLE "s"."t", … RESTART IDENTITY CASCADE`, skip when
  no user tables), stop closing the connection then the container
- [x] **Code**: expose `PostgresEngine` on the engines facade
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/engines/test_postgres.py -x
  -v` (unit/contract parts) — pass
- [x] **Logic tests** (design test stack, docker-gated via `requires_docker`):
  `test_postgres_engine_roundtrip_start_apply_reset` — `InstanceConfig(name="db",
  kind="postgresql", image=None)`; startup ops `[DataOperation("db","postgresql","insert",
  {"sql": "CREATE TABLE orders (id int PRIMARY KEY, n int)"})]`; baseline recorded via `record`
  (insert `{"id": 1, "n": 5}`); apply insert id=2; `reset()`; assert the baseline row survives
  and the test row is gone (duplicate id=1 apply → `UniqueViolation` proves the baseline row
  exists); `test_reset_with_empty_journal_is_wipe_only` — engine started with no startup ops,
  one insert applied, reset leaves the table empty
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [x] **Contract re-verification**: readiness-before-return, parameter binding, catalog reset,
  idempotent-startup-SQL note observed
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 9: `BaseEngine::KafkaEngine` — mokapi kafka mock instance (TDD)

The kafka kind engine: generic container with the spec mounted and passed as the command
argument, HTTP health readiness, kafka-python producer plane, restart-based wipe.

**Contract entity**: `BaseEngine::KafkaEngine(config)` (`kafka.py`).

**Usages relevant to this task:**
- `mokapi`: spec as the start argument, volume mount at a fixed container path, health at
  `/health` (HTTP 8080), kafka listener 9092, restart-wipe semantics.
- `kafka-python`: `KafkaProducer(bootstrap_servers=<mapped address>, acks="all", retries=3,
  json/str serializers)`; `send` + `future.get(timeout=10)`; `flush(timeout=30)` as the batch
  boundary; `close()` at stop; deadlines everywhere.
- `testcontainers`: `DockerContainer` + `with_exposed_ports` + volume mount + `with_command`.

**Design contract (verbatim):**
```
container: DockerContainer(config.image or "mokapi/mokapi:0.28.0"),
           ports 8080 (HTTP) + 9092 (kafka) published,
           spec file volume-mounted at /data/<name> (the payload path — already absolute: the
           loader resolved it against the document directory at load), with_command("/data/<name>")
readiness: GET http://host:http_port/health with deadline (probe loop, 30s / 0.5s)
plane:     KafkaProducer(bootstrap_servers=host:kafka_port, acks="all", retries=3,
           value/key serializers: json→utf-8 / str→utf-8)
_execute:  spec → no-op;  produce → send(topic, key, value); future.get(timeout=10);
           after the apply group: flush(timeout=30)
_wipe:     docker-restart the SAME container (SDK restart, timeout=10) → ports preserved;
           re-wait health; rebuild the producer
stop:      producer.close(); container.stop()
```
Errors: `KafkaTimeoutError`/`KafkaError` from `future.get` map into the EngineError wrap — a
broken bootstrap fails within the deadline. Edge: value may be `dict` (json-serialized) or `str`.
The `spec` op is consumed by the container build; `_execute` on a `spec` op is a no-op
(replay-safe). Decision 4A: restart the same container via the docker SDK object under the
testcontainers wrapper (bindings preserved); never remove+recreate.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 9 is being executed
- [x] **Contract tests**: `tests/sandbox/engines/test_kafka.py` — `KafkaEngine` importable from
  the facade; subclasses `BaseEngine`
- [x] **REPL prototype (R4, docker-gated)**: start a `DockerContainer("mokapi/mokapi:0.28.0")`
  with both ports published in the REPL; probe `/health`; construct a `KafkaProducer` against
  the mapped 9092; send one message and confirm via `future.get`; restart the container through
  the SDK object and confirm the published port survives; then migrate
  (docker runtime unavailable in this environment — live probing deferred to the docker-gated
  test; the kafka-python signatures, the serializer invocation incl. the None-key path, the
  DockerContainer build chain, and the SDK `restart(timeout=…)` surface were REPL-verified
  against the cooks, and the full lifecycle was REPL-replayed over fake seams)
- [x] **Code**: create `goga_tool_pybuggy/sandbox/engines/kafka.py` implementing the kind hooks
  per the contract above (spec mount consumed from the startup ops at container build; health
  probe loop with deadline 30s/0.5s; producer rebuilt after restart; `spec` execution no-op)
- [x] **Code**: expose `KafkaEngine` on the engines facade
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/engines/test_kafka.py -x -v` —
  pass
- [x] **Logic tests** (docker-gated): `test_kafka_engine_spec_mount_and_restart_reset` — engine
  started with a startup `spec` op pointing at a tmp AsyncAPI document; a `produce` to a spec
  topic succeeds; after `reset()` the address is unchanged, a produce still succeeds (topology
  returned from the spec on boot), and journaled baseline produces replay
  (written; skips here without a docker runtime — plus fake-driven unit coverage of build,
  readiness, plane, execution, flush boundary, restart-wipe, and stop safety that runs
  everywhere)
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [x] **Contract re-verification**: spec mount + command argument, deadline-bounded produce,
  restart-wipe with address stability
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 10: `BaseEngine::VaultEngine` — vault dev-mode secrets mock (TDD)

The vault kind engine: dev-mode container with the fixed root token, KV v2 HTTP plane,
restart-based wipe.

**Contract entity**: `BaseEngine::VaultEngine(config)` (`vault.py`).

**Usages relevant to this task:**
- `vault-dev`: `server -dev` + `VAULT_DEV_ROOT_TOKEN_ID`/`VAULT_DEV_LISTEN_ADDRESS` env;
  `X-Vault-Token` header; `POST /v1/secret/data/<path>` body `{"data": …}`; readiness
  `GET /v1/sys/health`; restart-wipe semantics (in-memory storage).
- `requests`: data-plane HTTP with `timeout=5`; probe loops with deadlines.
- `testcontainers`: `DockerContainer` + `with_env` + `with_command`.

**Design contract (verbatim):**
```
container: DockerContainer(config.image or "hashicorp/vault:1.17"),
           port 8200, env VAULT_DEV_ROOT_TOKEN_ID="sandbox-root" (constant; never logged),
           VAULT_DEV_LISTEN_ADDRESS="0.0.0.0:8200", command "server -dev"
readiness: GET /v1/sys/health → 200 (deadline loop)
plane:     requests with headers {"X-Vault-Token": "sandbox-root"}, timeout=5
_execute:  put → POST /v1/secret/data/<path> body {"data": data}; non-2xx → error naming path
_wipe:     docker-restart the SAME container; re-wait health
stop:      container.stop()   (requests needs no close)
```
Edge: writes create versions — irrelevant under restart-wipe. The dev token is a fixed fixture
credential (`"sandbox-root"`), never logged (R1.5). A failed write maps to a readable error
naming the path.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 10 is being executed
- [x] **Contract tests**: `tests/sandbox/engines/test_vault.py` — `VaultEngine` importable from
  the facade; subclasses `BaseEngine`
- [x] **REPL prototype (R4, docker-gated)**: start the vault dev container in the REPL; confirm
  `/v1/sys/health` goes 200; `PUT`/`POST` a secret at `/v1/secret/data/x/y` with the token
  header; read it back; restart the container and confirm the secret is gone while the port
  stays; then migrate
  (docker runtime unavailable in this environment — live probing deferred to the docker-gated
  test; the docker SDK string-command shlex split (`"server -dev"` → `["server", "-dev"]`), the
  `with_env`/`with_command` build chain, the KV v2 URL/payload shapes, and the error-body
  mapping were REPL-verified against the cooks, and the full lifecycle was REPL-replayed over
  fake seams)
- [x] **Code**: create `goga_tool_pybuggy/sandbox/engines/vault.py` per the contract above
- [x] **Code**: expose `VaultEngine` on the engines facade
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/engines/test_vault.py -x -v` —
  pass
- [x] **Logic tests** (docker-gated): `test_vault_engine_put_and_restart_reset` — baseline
  `put("payment/api-key", {"api_key": "k"})` recorded; a test `put("x/y", {"v": 1})` applied;
  after `reset()`: `GET /v1/secret/data/x/y` → 404 (test write gone), `GET
  …/payment/api-key` → 200 with the baseline value, `engine.address` unchanged before/after
  (written; skips here without a docker runtime — plus fake-driven unit coverage of build, dev
  env, readiness, KV v2 execution, error mapping, restart-wipe, journal replay, and stop safety
  that runs everywhere, including a token-never-logged check)
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [x] **Contract re-verification**: dev-mode env contract, KV v2 paths, token never logged
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 11: `BaseEngine::HttpEngine` — wiremock http mock instance (TDD)

The http kind engine: wiremock container, admin-API stub plane, mappings-reset wipe.

**Contract entity**: `BaseEngine::HttpEngine(config)` (`http.py`).

**Usages relevant to this task:**
- `wiremock`: `POST /__admin/mappings` (mapping passthrough — priority/delays/faults stay
  available), `POST /__admin/mappings/reset`, readiness `GET /__admin/health` (3.x; fall back
  to `GET /__admin/mappings`), near-miss visibility.
- `requests`: admin plane with `timeout=5`.
- `testcontainers`: `DockerContainer` + `with_exposed_ports`.

**Design contract (verbatim):**
```
container: DockerContainer(config.image or "wiremock/wiremock:3.13.0"), port 8080
readiness: GET /__admin/health (3.x; fall back to GET /__admin/mappings) with deadline
plane:     requests, timeout=5
_execute:  stub → POST /__admin/mappings json=mapping (mapping passes through as given)
_wipe:     POST /__admin/mappings/reset
stop:      container.stop()
```
Mapping objects pass through untouched. A failed POST surfaces as a readable error naming the
operation.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 11 is being executed
- [x] **Contract tests**: `tests/sandbox/engines/test_http.py` — `HttpEngine` importable from
  the facade; subclasses `BaseEngine`
- [x] **REPL prototype (R4, docker-gated)**: start the wiremock container in the REPL; confirm
  `/__admin/health`; POST a mapping (with a priority or delay to confirm passthrough); request
  the stubbed path; POST `mappings/reset` and confirm the stub is gone; then migrate
  (docker runtime unavailable in this environment — live probing deferred to the docker-gated
  test; the readiness loop incl. the 404→mappings fallback, the mapping-label/failure-text
  builders, and the admin URL shapes were REPL-verified against the cooks, and the full
  lifecycle was REPL-replayed over fake seams)
- [x] **Code**: create `goga_tool_pybuggy/sandbox/engines/http.py` per the contract above
- [x] **Code**: expose `HttpEngine` on the engines facade
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/engines/test_http.py -x -v` —
  pass
- [x] **Logic tests** (docker-gated): `test_http_engine_stub_and_admin_reset` — stubs visible
  via `GET /__admin/mappings` while active; after `reset()` the API-created mappings are gone
  and only the journaled baseline mappings replay
  (written; skips here without a docker runtime — plus fake-driven unit coverage of build,
  readiness incl. the fallback and connection-retry paths, mapping passthrough, error naming,
  mappings-reset wipe, journal replay, and stop safety that runs everywhere)
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [x] **Contract re-verification**: mapping passthrough, admin reset, readiness fallback
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 12: `check_runtime` and `build_engine` — probe and factory, engines facade completion (TDD)

The pre-start runtime probe and the kind → engine factory; completes the engines facade.

**Contract entities**: `check_runtime()` (`runtime.py`) — probe only, `RuntimeError` naming the
requirement on failure; `build_engine(config: InstanceConfig) -> engine: BaseEngine`
(`runtime.py`) — kind → class mapping, unmapped kind fails listing the supported kinds, the
image override reaches the engine via `config.image`.

**Usages relevant to this task:**
- `testcontainers`: daemon reachability through the testcontainers docker client
  (`DockerClient().client.ping()`).
- `conventions`: type hints; `mock.patch` at the import point for the daemon-failure test.

**Design algorithms (verbatim):**
```
check_runtime:
1. ping the daemon through the testcontainers docker client (docker SDK under it)
2. failure (DockerException, connection errors) → RuntimeError naming the requirement:
   "a docker-compatible container runtime must be available in the environment running the tests"

build_engine:
1. kind → class: postgresql→PostgresEngine, kafka→KafkaEngine, vault→VaultEngine, http→HttpEngine
2. unmapped kind → EngineError listing the supported kinds (defense; the loader already rejects)
3. construct with the InstanceConfig — the image override reaches the engine via config.image
```

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 12 is being executed
- [x] **Contract tests**: `tests/sandbox/engines/test_runtime.py` — both routines importable
  from the facade; `build_engine` returns a `BaseEngine` subclass per kind
- [x] **REPL prototype (R4)**: call `check_runtime()` in the REPL; observe the ping path and
  (with docker absent or the client monkeypatched) the actionable message; call `build_engine`
  for each of the four kinds and for a fabricated `kind="grpc"` config
  (docker runtime unavailable in this environment — the absent-daemon path was observed live
  against the real testcontainers client: the DockerClient constructor raises DockerException
  while fetching the server version, so the probe wraps construction and ping together; the
  ping-success and factory-failure paths were REPL-verified over a faked client, and
  build_engine was REPL-driven for all four kinds plus the fabricated grpc config)
- [x] **Code**: create `goga_tool_pybuggy/sandbox/engines/runtime.py` implementing both
  routines per the algorithms above
- [x] **Code**: complete the engines facade — `__all__ = ["DataOperation", "InstanceAddress",
  "check_runtime", "build_engine", "BaseEngine", "PostgresEngine", "KafkaEngine",
  "VaultEngine", "HttpEngine"]`; verify each name importable (ruff RUF022 requires the
  isort-sorted spelling of the same nine names; `EngineError` stays importable from the
  package via the explicit re-export alias, outside `__all__` per the contract facade)
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/engines/ -x -v` — pass; facade
  check: `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.engines import DataOperation,
  InstanceAddress, check_runtime, build_engine, BaseEngine, PostgresEngine, KafkaEngine,
  VaultEngine, HttpEngine"`
- [x] **Logic tests**: `test_check_runtime_fails_actionable_without_daemon` — monkeypatch the
  docker client factory to raise `DockerException`; `pytest.raises(RuntimeError,
  match="docker-compatible container runtime")`; `test_build_engine_fails_unmapped_kind` —
  `InstanceConfig(name="x", kind="grpc", image=None)` (bypassing the loader);
  `pytest.raises(EngineError, match="postgresql.*kafka.*vault.*http")`; positive: each kind
  returns the matching class; the image override reaches `engine.config.image`
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [x] **Contract re-verification**: probe-before-start positioning, factory defense, image
  override flow
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

---

### Task 13: Data cell skeleton (infrastructure)

Create the data cell package, its progressive facade, and the mirrored test package.

**Usages relevant to this task:**
- `conventions`: package/test tree mirroring (`goga_tool_pybuggy/sandbox/data/*.py` →
  `tests/sandbox/data/test_*.py`).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create `goga_tool_pybuggy/sandbox/data/__init__.py` — docstring + `__all__ = []`
  (populated by Tasks 14–16)
- [x] Create `tests/sandbox/data/__init__.py`
- [x] Verify: `.venv/bin/python -c "import goga_tool_pybuggy.sandbox.data"`
- [x] Lint gate (pre-commit): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0

### Task 14: `DataBatch` — the lazy per-test accumulator (TDD)

**Contract entity**: `DataBatch()` (`batch.py`) — methods `add(operation: DataOperation)` (append;
nothing executes) and `take() -> operations: list[DataOperation]` (drain in accumulation order;
empty afterwards). One batch per test; accumulation order is the per-instance application order.

**Usages relevant to this task:**
- `conventions`: pure logic tested without mocks; kw_only n/a here (plain class); type hints.

**Design algorithm (verbatim):**
```
add(operation): append; nothing executes
take(): drained = list(ops); ops.clear(); return drained
```

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 14 is being executed
- [x] **Contract tests**: `tests/sandbox/data/test_batch.py` — `DataBatch` importable from the
  facade; both methods with the declared signatures
- [x] **REPL prototype (R4)**: drive add/add/take/take in the REPL; observe drain semantics;
  then migrate
- [x] **Code**: create `goga_tool_pybuggy/sandbox/data/batch.py`; expose `DataBatch` on the
  facade
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/data/ -x -v` — pass
- [x] **Logic tests**: `test_batch_take_drains_and_repeat_is_empty` — two ops added; first
  `take()` returns both in order; second returns `[]`
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [x] **Contract re-verification**: laziness (add executes nothing) and drain semantics
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 15: Instance views — `PostgresInstance`, `KafkaInstance`, `VaultInstance`, `HttpInstance` (TDD)

The four test-facing declarative views. Each takes `(name, address, batch)`, exposes
`name`/`host`/`port` from the address, and declares exactly one operation into the batch.

**Contract entities**: the four view classes in `data/{postgres,kafka,vault,http}.py`.

**Usages relevant to this task:**
- `data-operations` (imported usage, `sandbox/data/.usages/data-operations.md`): the laziness
  contract and the declaration shapes the views must produce.
- `conventions`: pure logic without mocks (a tiny recording `DataBatch` subclass as the test
  double is data, not a mock).

**Design contract (verbatim):**
```
PostgresInstance(name, address, batch): properties name/host/port (from address)
  insert(table, rows)  → batch.add(DataOperation(name, "postgresql", "insert",
                                   {"table": table, "rows": rows}))
KafkaInstance:   produce(topic, value, key=None) → action "produce",
                  payload {"topic", "value", "key"}
VaultInstance:   put(path, data) → action "put", payload {"path", "data"}
HttpInstance:    stub(mapping) → action "stub", payload = mapping
```
Payload construction is keyword-only (`kw_only` models — the schematic positional spellings
stand for the keyword form). Requirements: operations declare only — execution happens when the
session facade applies the batch. `insert`: one call targets one table; rows apply in list
order; for foreign-key chains across tables declare parents first. `stub`: mapping passes
through as given (matching, priority, delays, faults stay available).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 15 is being executed
- [x] **Contract tests**: `tests/sandbox/data/test_postgres.py`, `test_kafka.py`,
  `test_vault.py`, `test_http.py` — all four importable from the facade; constructor signature
  `(name, address, batch)`; properties `name`/`host`/`port`; the one declaring method each
- [x] **REPL prototype (R4)**: with a recording batch and an `InstanceAddress`, call each view
  method in the REPL; inspect the produced `DataOperation` against the payload table; then
  migrate
- [x] **Code**: create the four view modules in `goga_tool_pybuggy/sandbox/data/` per the
  contract above; expose all four on the facade
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/data/ -x -v` — pass
- [x] **Logic tests**: each view method appends exactly one `DataOperation` with the correct
  `instance`, `kind`, `action`, and payload shape to the batch; properties read from the
  address; nothing else is touched (batch receives no execution call)
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [x] **Contract re-verification**: declaration shapes match the payload table exactly
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 16: `services` — the per-test data-preset decorator (TDD)

**Contract entity**: `services(...presets) -> decorator: Callable` (`presets.py`) — kind-named
arguments carrying instance-targeted declarations; marks the test with the presets.

**Usages relevant to this task:**
- `conventions`: the documented `...presets` arbitrary-arguments form is the single allowed
  `**kwargs` exception; pure logic without mocks.

**Design contract (verbatim):**
```
services(**presets):                      # kind → instance name → declaration list
  1. every kind ∈ {postgresql, kafka, vault, http} → else ValueError at decoration
     (instance names are validated at enqueue — decision 3A)
  2. return decorator: item → apply pytest.mark.pybuggy_services(presets=presets)
     (nothing executes at decoration time)
```
Requirements: presets apply only to the test declaring them; declaration order within one
instance is the application order. Constraint: do not execute anything at decoration time.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 16 is being executed
- [x] **Contract tests**: `tests/sandbox/data/test_presets.py` — `services` importable from the
  facade; callable with keyword presets returning a decorator
- [x] **REPL prototype (R4)**: decorate a sample function in the REPL; inspect
  `fn.pytestmark` / the marker kwargs; confirm no I/O occurred; then migrate
- [x] **Code**: create `goga_tool_pybuggy/sandbox/data/presets.py` per the contract; expose
  `services` on the facade; final data facade — `__all__ = ["DataBatch", "PostgresInstance",
  "KafkaInstance", "VaultInstance", "HttpInstance", "services"]`
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/data/ -x -v` — pass; facade
  check: `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.data import DataBatch,
  PostgresInstance, KafkaInstance, VaultInstance, HttpInstance, services"`
- [x] **Logic tests**: `test_presets_decorator_marks_test_and_executes_nothing` — the
  `pybuggy_services` marker exists with `presets` payload
  (`marker.kwargs["presets"]["postgresql"]["db"][0]["table"] == "customers"`);
  `test_services_rejects_unknown_kind_at_decoration` — `@services(redis={"x": []})` raises
  `ValueError` matching `"redis"` at decoration
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [x] **Contract re-verification**: decoration-time kind validation (decision 3A), marker shape,
  zero execution
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

---

### Task 17: Sandbox cell test fixtures — `FakeEngine`, `FakeService` (infrastructure)

The recording stubs every sandbox-cell unit test drives (the cell's modules land in Tasks
18–22; the facade completes in Task 22). Design General Setup: `FakeEngine` / `FakeService` —
recording stubs for `Sandbox` unit tests (apply/record/reset calls, alive/logs).

**Usages relevant to this task:**
- `conventions`: shared fixtures in `tests/sandbox/conftest.py`; test doubles as plain fakes
  (not mocks) for pure-logic tests.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Extend `tests/sandbox/conftest.py` with `FakeEngine` (records `applied`, `journaled`,
  `reset_count`, `started`/`stopped`; configurable `kind`, a raising `start`, and a configurable
  `address` — an `InstanceAddress` instance — so the sandbox view factories can bind views to
  the fake) and `FakeService` (records `started`/`stopped`; configurable `alive` and `logs`) —
  plain classes exposed as fixtures
- [x] Verify collection: `.venv/bin/pytest tests/sandbox/ -q`
- [x] Lint gate (pre-commit): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0

### Task 18: `render_service_env` — strict placeholder rendering (TDD)

**Contract entity**: `render_service_env(env: dict[str, str], addresses:
dict[str, InstanceAddress]) -> rendered: dict[str, str]` (`env_render.py`).

**Usages relevant to this task:**
- `jinja2`: `Environment(undefined=StrictUndefined)`; per-value render.
- `sandbox-file` (imported usage): the placeholder syntax `{{<instance>.host}}` /
  `{{<instance>.port}}`.

**Design algorithm (verbatim):**
```
1. context = {name: {"host": a.host, "port": a.port} for name, a in addresses.items()}
2. for each (key, value): rendered = jinja2 Environment(StrictUndefined).from_string(value)
   .render(context); UndefinedError → ValueError naming the env key and value
```
Values without placeholders render to themselves. No whitespace stripping (unlike
`render_base_url` — env values are not URLs). The `UndefinedError` wrap is defense in depth —
unreachable via the load-time validation.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 18 is being executed
- [x] **Contract tests**: `tests/sandbox/test_env_render.py` — importable from
  `goga_tool_pybuggy.sandbox.env_render` (facade exposure lands with Task 22); signature and
  return type
- [x] **REPL prototype (R4)**: build the context for `{"db": InstanceAddress(host="127.0.0.2",
  port=5432)}` in the REPL; render `"postgres://{{db.host}}:{{db.port}}/test"` and
  `"no-placeholders"`; trigger `UndefinedError` on `{{ghost.host}}` and observe the wrap; then
  migrate
- [x] **Code**: create `goga_tool_pybuggy/sandbox/env_render.py` per the algorithm
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/test_env_render.py -x -v` —
  pass
- [x] **Logic tests**: `test_render_service_env_resolves_placeholders` —
  `rendered["DATABASE_URL"] == "postgres://127.0.0.2:5432/test"`, `rendered["PLAIN"] ==
  "no-placeholders"`; negative: an unknown placeholder raises `ValueError` naming the env key
  and the value
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [x] **Contract re-verification**: strict rendering, context shape, error naming
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 19: `ServiceContainer` — the service under test (TDD)

**Contract entity**: `ServiceContainer(config: ServiceConfig)` (`service_container.py`) —
properties `host -> str`, `port -> int`; methods `start(env: dict[str, str])` (rendered env;
readiness = port probe or health path), `stop()` (safe when already stopped), `alive() -> bool`,
`logs() -> str`.

**Usages relevant to this task:**
- `testcontainers`: `DockerContainer(config.image)`, `with_exposed_ports(config.port)`, `env=`,
  labels, start; mapped host/port read back after start.
- `requests`: health-path readiness probing (`GET http://host:port<health>` until 2xx,
  deadline).

**Design contract (verbatim):**
```
start(env): DockerContainer(config.image), with_exposed_ports(config.port),
            env=rendered values, labels → start → readiness:
            config.health is None → port probe loop (TCP connect, deadline 30s/0.5s)
            else → GET http://host:port<health> via requests until 2xx (deadline)
stop():    container.stop(); safe when already stopped
alive():   container status check (SDK reload → running?)
logs():    container logs (str) — the died-service diagnostic payload
host/port: mapped values read back after start
```
Requirements: readiness completes before start returns; the container is labeled
(`{"pybuggy-sandbox": "true"}`) and removed on stop; a died service is detectable and its
output readable. Constraint: never restarted on reset.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 19 is being executed
- [x] **Contract tests**: `tests/sandbox/test_service_container.py` — the class and its method/
  property surface (facade exposure lands with Task 22)
- [x] **REPL prototype (R4, docker-gated)**: start the container for the pinned
  `wiremock/wiremock:3.13.0` image with port 8080 in the REPL (no extra image needed); observe
  the port-probe readiness loop, the mapped host/port, `alive()`, `logs()`, stop-twice safety;
  repeat with `health="/__admin/health"` for the health branch; then migrate
  (docker runtime unavailable in this environment — live probing deferred to the docker-gated
  test; the DockerContainer build chain (construction fetches the server version eagerly, so the
  module-seam patch pattern is required), the `_tcp_port_open` helper against a live and a
  closed local socket, both readiness deadline loops over fake requests/time, the
  reload→status liveness semantics, and the bytes→str log decode were REPL-verified, and the
  full lifecycle was REPL-replayed over fake seams)
- [x] **Code**: create `goga_tool_pybuggy/sandbox/service_container.py` per the contract
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/test_service_container.py -x
  -v` — pass
- [x] **Logic tests** (docker-gated, review-added scenario):
  `test_service_container_readiness_and_liveness` — variant A: `ServiceConfig(image=
  "wiremock/wiremock:3.13.0", port=8080, health=None, env={})`; `sc.start(env={"K": "v"})`;
  assert `int(sc.port) > 0`, `sc.host` resolvable, `requests.get(f"http://{sc.host}:{sc.port}
  /__admin/health", timeout=5).status_code == 200`, `sc.alive() is True`,
  `isinstance(sc.logs(), str)`, `sc.stop()`; second `sc.stop()` does not raise; `sc.alive()` is
  False after stop. Variant B: the same shape with `health="/__admin/health"` (health-path
  readiness branch)
  (written; skips here without a docker runtime — plus fake-driven unit coverage of build, both
  readiness branches incl. the deadline failures, mapped address, before-start guard, liveness
  reload, logs decode, and stop safety that runs everywhere)
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [x] **Contract re-verification**: both readiness branches, mapped address, liveness/logs pair,
  stop safety
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 20: `Sandbox` — the session runtime core (TDD)

**Contract entity**: `Sandbox(config: SandboxConfig)` (`sandbox.py`) — property `base_url`;
methods `start()`, `stop()`, `clear()`, `baseline()`, `apply_pending()`, `ensure_service()`,
`new_test_batch()`, view factories `postgresql/kafka/vault/http(name)`.

**Usages relevant to this task:**
- `sandbox-file` (imported usage): the configuration semantics driving startup.
- `data-operations` (imported usage): the laziness contract of `apply_pending`.
- `testcontainers` / `check_runtime` / `build_engine` / `StartupData`: the startup composition.
- `conventions`: structured INFO progress logging at every startup step.

**Design algorithm (verbatim):**
```
__init__(config): engines = {name: build_engine(ic) for name, ic in config.instances.items()}
                  service = ServiceContainer(config.service); _batch = DataBatch();
                  _boundary_open = False; _boundary_batch = None
start():  check_runtime → per instance (declaration order): engine.start(startup ops from
          StartupData in the fixed order) → render_service_env(service.env, addresses) →
          service.start(rendered) → base_url; INFO progress each step; on failure: stop+raise
stop():   service.stop(); engines stopped in reverse order (each guarded); idempotent
clear():  for engine: engine.reset()                       # service untouched
baseline(): return BaselineBoundary(self)
new_test_batch(): _batch = DataBatch()                      # called by the runtest_setup hook
_current_batch(): _boundary_batch if _boundary_open else _batch
apply_pending():
  1. ops = _batch.take()
  2. group ops by instance preserving accumulation order (dict of lists)
  3. for each group: engines[instance].apply(group)
ensure_service():
  if not service.alive():
      raise RuntimeError(f"the service under test (image {config.service.image}) died; "
                         f"its output:\n{service.logs()}")   # names the service + the output
postgresql/kafka/vault/http(name):
  engine = engines.get(name); kind must match → else ValueError listing configured instances
  return <Kind>Instance(name=name, address=engine.address, batch=_current_batch())
base_url: f"http://{service.host}:{service.port}"            # readable after start
```
Startup op assembly (fixed section order vault → http → kafka → postgres): vault (`put`, payload
`{path, data}`), http (`stub`, payload = the mapping object), kafka (`spec`, payload `{path}`),
postgres (`insert`, payload `{sql}` — decision 2A). Start trace (from the design): runtime probe
→ engines in declaration order with their startup ops → `addresses = {name: engine.address}` →
`rendered = render_service_env(...)` → `ServiceContainer.start(rendered)` → `self.base_url =
f"http://{service.host}:{service.port}"` with an INFO log naming the resolved address and its
source ("sandbox"); any exception → `self.stop()` → re-raise. Edge cases: empty `instances`
allowed (a service with no dependencies); `ensure_service` is a no-op while the service runs.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 20 is being executed
- [x] **Contract tests**: `tests/sandbox/test_sandbox.py` — the class surface (facade exposure
  lands with Task 22); `base_url` readable after start
- [x] **REPL prototype (R4)**: drive a `Sandbox` built over `FakeEngine`s and a `FakeService`
  in the REPL (monkeypatch `build_engine`/`ServiceContainer` in the module namespace): call
  `start`, `apply_pending`, `clear`, `stop`; observe ordering and call records against the
  algorithm; then migrate
  (verified end to end in the venv REPL over four FakeEngines + a FakeService: start ordering,
  startup-op assembly per section, rendered-env hand-off, grouping apply, kind/unknown-name
  failures, clear/new_test_batch, died-service error, reverse-order stop, and the
  failed-start cleanup all matched the design trace before migration)
- [x] **Code**: create `goga_tool_pybuggy/sandbox/sandbox.py` per the algorithm (monkeypatchable
  seams: `build_engine`, `ServiceContainer`, `render_service_env` referenced at module level)
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/test_sandbox.py -x -v` — pass
- [x] **Logic tests** (fakes): `test_apply_pending_groups_by_instance_preserving_order` — two
  FakeEngines ("db", "payments"); batch preloaded via views db-insert A, payments-stub B,
  db-insert C; `apply_pending()` → `engines["db"].applied == [A, C]`,
  `engines["payments"].applied == [B]`, `batch.take() == []` (drained);
  `test_sandbox_view_kind_mismatch_lists_configured` — `sandbox.kafka("db")` over a
  postgresql-kind FakeEngine → `ValueError` matching `"kafka.*db"`;
  `test_ensure_service_raises_naming_service_and_logs_when_died` — FakeService(alive=False,
  logs="OOMKilled…") → `RuntimeError` matching `"died"` containing the image name and the log
  tail; plus: view factories hand out views bound to the current batch; `new_test_batch`
  replaces the batch; `clear()` resets every engine and never touches the service; `stop()`
  stops the service then the engines in reverse order, idempotent
  (FakeService gained configurable `host`/`port` in `tests/sandbox/conftest.py` — the
  `base_url` reads need a mapped service address; `baseline()` carries a local import with a
  `noqa: PLC0415` until `baseline.py` lands in Task 21, then it can hoist to module level)
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [x] **Contract re-verification**: ordering, grouping, fail-fast views, died-service error,
  per-test batch ownership
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 21: `BaselineBoundary` + `BoundaryBatch` — the immediate-apply boundary (TDD)

**Contract entities**: `BaselineBoundary(sandbox: Sandbox)` (`baseline.py`) with `open()` /
`close()`; internal `BoundaryBatch(DataBatch)` in the same file.

**Usages relevant to this task:**
- `conventions`: internal helpers stay inside the cell; exception propagation (author errors
  are not swallowed).

**Design algorithm (verbatim):**
```
BoundaryBatch(DataBatch):                    # internal, baseline.py
  add(operation): engines[op.instance].apply([op]); engines[op.instance].record([op])
  take(): return []
BaselineBoundary(sandbox):
  open():  sandbox._boundary_batch = BoundaryBatch(sandbox.engines);
           sandbox._boundary_open = True
  close(): sandbox._boundary_open = False; sandbox._boundary_batch = None
  __enter__: open(); return self        # supports `with sbx.baseline():`
  __exit__: close(); propagate exceptions
```
Design trace: `open()` switches the sandbox's declaration routing to immediate mode — the batch
object the view factories bind is the `BoundaryBatch` whose `add` performs `engine.apply([op])`
followed by `engine.record([op])`; `take()` returns `[]`; `close()` switches routing back; the
journals are frozen because no further `record` calls happen; journal = startup ops + boundary
ops in application order. An exception inside the `with` block still closes the boundary and
propagates. View signatures are untouched — the sandbox just hands out a different `batch`
object while the boundary is open.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Declaration**: state that Task 21 is being executed
- [ ] **Contract tests**: `tests/sandbox/test_baseline.py` — the class, `open`/`close`, and the
  context-manager protocol
- [ ] **REPL prototype (R4)**: with a FakeEngine sandbox, open the boundary in the REPL, obtain
  `sandbox.postgresql("db")`, call `insert`, and observe `applied`/`journal` and the untouched
  lazy batch; then migrate
- [ ] **Code**: create `goga_tool_pybuggy/sandbox/baseline.py` per the algorithm
- [ ] **Interface verification**: `.venv/bin/pytest tests/sandbox/test_baseline.py -x -v` — pass
- [ ] **Logic tests**: `test_baseline_boundary_applies_immediately_and_journals` — with
  FakeEngine recording `apply`/`record`: inside `with sandbox.baseline():` a view
  `insert("customers", rows=[{"id": 1}])` → `engine.applied == [op]` and `engine.journal ==
  [op]` (applied AND journaled at declaration time), the sandbox's lazy batch untouched
  (`take() == []`); after `close()` views are lazy again; an exception raised inside the `with`
  block propagates AND the boundary closes (routing restored)
- [ ] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [ ] **Contract re-verification**: immediate apply + journaling, freeze-on-close, exception
  propagation, lazy contract outside the boundary
- [ ] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [ ] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 22: `activate_sandbox` / `active_sandbox` and the sandbox facade completion (TDD)

The presence-gated activation and the registered lifecycle hooks (including the per-test preset
enqueue), plus the completion of the sandbox cell facade.

**Contract entities**: `activate_sandbox(context: dict[str, object]) -> config:
SandboxConfig | None` and `active_sandbox() -> sandbox: Sandbox | None` (`activation.py`).

**Usages relevant to this task:**
- `pluginator`: hook registration into the caller namespace (the same namespace-injection
  pattern as `install_pytest_plugins`).
- `sandbox-file` (imported usage): the activation document semantics.
- `conventions`: type hints; `tmp_path` + `monkeypatch.chdir` for document fixtures.

**Design algorithm (verbatim):**
```
activate_sandbox(context):
  1. config = load_sandbox_config(None); None → return None (inert)
  2. register hooks into context (wrap a pre-existing same-name callable: prior first):
     pytest_sessionstart(session):  session.config.addinivalue_line("markers",
                                     "pybuggy_services: per-test sandbox data presets "
                                     "(applied by the pybuggy sandbox)")   # pre-collection:
                                     # the marker must be known before test modules import
                                     sbx = Sandbox(config)
                                     try: sbx.start()  except: sbx.stop(); raise
                                     module._ACTIVE = sbx
     pytest_sessionfinish(session, exitstatus):
                                     sbx = module._ACTIVE
                                     if sbx: try: sbx.stop() finally: module._ACTIVE = None
     pytest_runtest_setup(item):    sbx = module._ACTIVE; None → return
                                     sbx.new_test_batch()
                                     enqueue pybuggy_services markers (kind/name validated)
  3. return config
active_sandbox(): return module._ACTIVE        # same object every call within a session
```
Marker registration decision (review fix 7): the marker is registered in `pytest_sessionstart`
(runs pre-collection) so applying the marker in test modules never emits
`PytestUnknownMarkWarning`; `pytest_configure` is not usable — pluginator injects its own into
the same namespace after arming and would clobber it. Collision handling: if the namespace
already defines one of the hook names, the sandbox wraps the prior callable (prior first,
sandbox hook second) instead of clobbering. Enqueue (decision 3A): for every
`pybuggy_services` marker on the item, for each kind → instance name → declaration list,
resolve the instance engine (kind must match; unknown name fails listing the configured
instances) and append `DataOperation(instance, kind, action_of_kind, payload=declaration)` to
the batch, ahead of any in-test operation.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Declaration**: state that Task 22 is being executed
- [ ] **Contract tests**: `tests/sandbox/test_activation.py` — both routines importable from
  `goga_tool_pybuggy.sandbox` (facade completed below); return types
- [ ] **REPL prototype (R4)**: with a minimal valid `.sandbox.yml` in a `/tmp` cwd (chdir in the
  REPL): call `activate_sandbox(ctx)` on a fresh dict; inspect the three registered callables
  and the returned config; invoke `ctx["pytest_runtest_setup"]` with an item stub carrying the
  marker and observe the enqueued batch; reset the module state afterwards; then migrate
- [ ] **Code**: create `goga_tool_pybuggy/sandbox/activation.py` per the algorithm (module-level
  `_ACTIVE` reference; hooks as plain functions assigned into `context`)
- [ ] **Code**: complete the sandbox facade — `goga_tool_pybuggy/sandbox/__init__.py` with
  `__all__ = ["Sandbox", "BaselineBoundary", "ServiceContainer", "render_service_env",
  "activate_sandbox", "active_sandbox"]`; verify: `.venv/bin/python -c "from
  goga_tool_pybuggy.sandbox import Sandbox, BaselineBoundary, ServiceContainer,
  render_service_env, activate_sandbox, active_sandbox"`
- [ ] **Interface verification**: `.venv/bin/pytest tests/sandbox/ -x -v` — pass
- [ ] **Logic tests**: `test_activation_inert_without_document` — empty `tmp_path` chdir, fresh
  context: returns None; `ctx` has none of the three hook keys; `active_sandbox()` is None;
  `test_activation_registers_hooks_with_document` — minimal valid document: `ctx` has the three
  callables, the returned value is a `SandboxConfig`, no docker interaction (hooks not
  invoked); invoking `ctx["pytest_sessionstart"]` with a stub `session.config` calls
  `addinivalue_line("markers", "pybuggy_services: …")` **before** any `Sandbox` start
  (monkeypatch `Sandbox` to observe the ordering — review fix);
  `test_activation_wraps_preexisting_hook` — `ctx = {"pytest_sessionstart": prior}` (recording
  sentinel), `Sandbox` monkeypatched to a recording stub: invoking the registered hook calls
  `prior` first then the sandbox body (recorded order `["prior", "sandbox"]`), the sentinel
  called exactly once, the Sandbox stub constructed exactly once with the loaded config;
  `test_preset_enqueue_fails_unknown_instance_listing_configured` — Sandbox with FakeEngine
  ("db") only; an item stub carrying `pybuggy_services(presets={"postgresql": {"ghost":
  [{"table": "t", "rows": []}]}})`; invoking the registered setup hook raises `ValueError`
  matching `"ghost.*db"`
- [ ] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [ ] **Contract re-verification**: presence gating, fail-fast position (invalid document
  raises before anything is registered or started), wrap-if-collision, enqueue-time validation
- [ ] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [ ] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 23: Integration tests — sandbox session lifecycle over fakes

Cross-entity scenarios spanning activation + Sandbox + batch + views + boundary with the fake
engine/service stubs: the armed session flow and the failure-cleanup guarantee.

**Usages relevant to this task:**
- `conventions`: integration tests for module interaction; fakes over mocks; `tmp_path`.
- `sandbox-session` / `data-operations` (imported usages): the consumer-visible lifecycle the
  integration asserts.

**Scenario context (from the design's flow traces)**: startup flow (sessionstart →
`Sandbox.start()` → base_url), declaration → apply flow (presets precede in-test operations;
the guarded request drains the batch grouped by instance), teardown flow (sessionfinish →
stop in reverse order; `active_sandbox()` returns None afterwards), and the failure path ("a
failed start surfaces an actionable error and leaves nothing behind").

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Create `tests/sandbox/test_session_lifecycle.py`
- [ ] `test_sessionstart_failure_stops_everything_and_reraises` — Sandbox with one FakeEngine
  whose `start` raises; FakeService recording stop; simulate the sessionstart hook body
  (construct + start): the exception propagates AND every started engine and the service got
  `stop()`
- [ ] Armed flow over fakes: a valid document; `activate_sandbox(ctx)`; invoke
  `ctx["pytest_sessionstart"]` (Sandbox/engine seams faked) → `active_sandbox()` resolves the
  started sandbox; a marked item through `ctx["pytest_runtest_setup"]` enqueues presets ahead
  of in-test view declarations; `apply_pending()` applies groups in order; a raising operation
  surfaces a readable error identifying it; `ctx["pytest_sessionfinish"]` stops everything and
  clears `active_sandbox()`
- [ ] Test edge case: presets precede in-test operations within one instance group (first
  preset op, then the in-test op, in `engine.applied` order)
- [ ] Run validation: `.venv/bin/pytest tests/sandbox/ -x -v`
- [ ] Lint gate (pre-commit): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0

---

### Task 24: Plugin integration — arming, fail-fast, and the guarded api fixture (TDD)

The plugin-cell changes: `install()` step 2 (arming), the `sandbox_activation` property,
`configure()` step 3 (fail-fast), `api()` substitution + request guard.

**Contract entities (changed)**: `install(...kwargs)` (`plugin/__init__.py`); `ApiPlugin`
properties `sandbox_activation` (`plugin/plugin.py`); `ApiPlugin.configure()`; `ApiPlugin.api()`.

**Usages relevant to this task:**
- `pluginator`: `install_pytest_plugins` / `call_context` (install), the `configure()`
  lifecycle (configphase, after config init and install), fixtures as plugin-class methods.
- `sandbox-session` (imported usage): the consumer fixture patterns behind the substitution.
- `conventions`: Google docstrings; `mock.patch` at the import point for the seam tests.

**Design contract (verbatim):**
```
ApiPlugin.__init__: … unchanged …; self.sandbox_activation: SandboxConfig | None = None
install(**kwargs):
  kwargs.setdefault("context", call_context()); kwargs.setdefault("loaders", […])
  activation = activate_sandbox(kwargs["context"])
  plugin = ApiPlugin(**kwargs); plugin.sandbox_activation = activation
  install_pytest_plugins(plugin, context=kwargs["context"])
ApiPlugin.configure():
  … collect typed CLI options; apply the typed --base-url (unchanged) …
  if typed --base-url and self.sandbox_activation is not None:
      raise pytest.UsageError("--base-url was passed while the sandbox is active "
                              "(.sandbox.yml present); the sandbox owns the service address")
  … build context; render_base_url (unchanged) …
ApiPlugin.api():
  sandbox = active_sandbox(); base = sandbox.base_url if sandbox else self.base_url
  api = Api(base_url=base, …options unchanged…)
  if sandbox is not None: api.request = _sandbox_guard(api.request, sandbox)
  yield api; api.close()
_sandbox_guard(original, sandbox):
  def guarded(method, url_path, **kwargs):
      sandbox.apply_pending(); sandbox.ensure_service()
      return original(method, url_path, **kwargs)
```
Ordering (design trace): arm (step 2) → construct → assign → `install_pytest_plugins` → (later,
pluginator lifecycle) `configure()` — the assignment precedes `pytest_configure`, so the
fail-fast always sees the armed state. The instance-level `api.request` wrapper covers every
request path in the cell (`Endpoint._call` funnels through `self.api.request(...)`); the
died-service check runs on every guarded request; `apply_pending` drains on the first guarded
request and is a no-op afterwards. `sandbox_activation` is a plain attribute (not a
`define.option` — it is not user-configurable). Untouched contracts (design "Untouched
contracts"): the configure-phase Jinja2 `base_url` rendering, the option resolution chain, and
`render_base_url` — the substitution seam is read-time only.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Declaration**: state that Task 24 is being executed
- [ ] **Contract tests** (extend `tests/plugin/test_plugin.py` and `tests/plugin/test_install.py`):
  `ApiPlugin` exposes `sandbox_activation` (None after plain construction — it is not a
  constructor kwarg); `install()` calls `activate_sandbox` with the defaulted context and keeps
  the activation on the plugin
- [ ] **REPL prototype (R4)**: in the REPL construct `ApiPlugin(context={})`; assign a stub
  `sandbox_activation`; drive a fake pytest config with `invocation_params.args = ["--base-url",
  "http://x"]` through `configure()` and observe the `pytest.UsageError`; then drive the api
  fixture seam with `active_sandbox` monkeypatched to a fake (base_url + recording
  apply_pending/ensure_service) and observe the guard order; then migrate
- [ ] **Code**: `plugin/plugin.py` — initialize `self.sandbox_activation = None` in
  `__init__`; `configure()` gains the fail-fast step (renumber the remaining steps); `api()`
  resolves the base URL through `active_sandbox()` and wraps `api.request` with the guard when
  a sandbox is active
- [ ] **Code**: `plugin/__init__.py` — `install()` gains the arming step before construction:
  `activation = activate_sandbox(kwargs["context"])` … `plugin.sandbox_activation = activation`
  (import `activate_sandbox` from `..sandbox` relatively)
- [ ] **Interface verification**: `.venv/bin/pytest tests/plugin/ -x -v` — pass
- [ ] **Logic tests** (design test stack):
  `test_configure_renders_base_url_unchanged_without_sandbox` — `ApiPlugin(context={})`
  (constructor leaves `sandbox_activation = None`), fake config with empty args, option
  `base_url: "http://{{ENV_X}}/api"`, env `ENV_X=x` → `plugin.base_url == "http://x/api"`;
  `test_configure_fails_fast_on_cli_base_url_with_armed_sandbox` — assign a SandboxConfig stub
  post-construction (the `install()` pattern; the constructor takes no such kwarg), fake config
  with `args = ["--base-url", "http://x"]` → `pytest.raises(pytest.UsageError,
  match="--base-url.*sandbox")`;
  `test_install_arms_sandbox_and_keeps_activation_on_plugin` — monkeypatch
  `plugin_module.activate_sandbox = fake` (returns a sentinel, records the context); fake
  `install_pytest_plugins`; `install()` → fake called once with the same context object,
  `plugin.sandbox_activation is sentinel`;
  `test_api_fixture_substitutes_base_url_and_guards_first_request` — monkeypatch
  `plugin_module.active_sandbox` to a fake sandbox (`base_url = "http://10.0.0.1:9000"`,
  recording `apply_pending`/`ensure_service`); patch `plugin_module.Api` with a fake class;
  drive the fixture (`next(plugin.api().__iter__())`) then `api.request("GET", "/x")` →
  `api.base_url == "http://10.0.0.1:9000"` (sandbox wins), guard ran before the request
  (`applied_pending == 1`, `ensured == 1`), the `base_url` option value unchanged
  (`"http://rendered/api"`)
- [ ] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [ ] **Contract re-verification**: arming seam, fail-fast position (pre-container, pre-test),
  read-time substitution, guard coverage; non-sandbox behavior unchanged
- [ ] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [ ] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 25: `run_bootstrap` — packaged usage discovery over the sandbox subtree (TDD)

The commands/init change: step 2 of `run_bootstrap` discovers every `.usages/*.md` under the
packaged usage roots — the api cell plus the sandbox subtree cells.

**Contract entity (changed)**: `run_bootstrap(template_mode)` (`commands/init/init.py`) — step 2
only; matching Requirement and Constraint lines are already in the manifest.

**Usages relevant to this task:**
- `conventions`: CLI/bootstrap testing via direct handler calls; `tmp_path` for the CWD.

**Design trace (verbatim):**
```
roots = [importlib.resources.files("goga_tool_pybuggy.api"),
         importlib.resources.files("goga_tool_pybuggy.sandbox")]
discovered = [(stem, text) for root in roots for (stem, text) in _walk(root)]
# copy + register unchanged; PYBUGGY_ANNOTATIONS += sandbox-session / sandbox-file /
# data-operations hand-authored lines
```
The existing `_walk` recursion is driven over the two roots: the `goga_tool_pybuggy.api`
package (as today — the walk also recurses into the `asserts` sub-package, so `asserts.md`
keeps being collected exactly as today) and the `goga_tool_pybuggy.sandbox` package (the walk
recurses into `sandbox/config` and `sandbox/data`; `engines` has no `.usages` and contributes
nothing). Stems are unique across the five collected (`api`, `asserts`, `sandbox-session`,
`sandbox-file`, `data-operations`) — four was a miscount, `asserts` rides the api-package root
already today (`PYBUGGY_ANNOTATIONS` carries its hand-authored line). Copy mechanics unchanged:
template mode skips an existing target with an INFO log; bare mode overwrites. Registration
unchanged: usage keys `pybuggy-<stem>` via `register_usages`, annotation lines via
`register_annotations`, `PYBUGGY_ANNOTATIONS` gains hand-authored lines for the three new
stems. Constraint: do not copy usages beyond the packaged usage roots (plugin/commands cells
are not roots).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Declaration**: state that Task 25 is being executed
- [ ] **Contract tests** (extend `tests/commands/init/test_bootstrap.py`): after
  `run_bootstrap(template_mode=True)` the five stems exist under
  `.goga/usages/cooks/pybuggy/` and the three new `pybuggy-<stem>` keys + annotation lines are
  registered
- [ ] **REPL prototype (R4)**: in the REPL walk `importlib.resources.files(
  "goga_tool_pybuggy.sandbox")` with the existing `_walk` and list the collected stems;
  confirm exactly `sandbox-session`, `sandbox-file`, `data-operations`; then migrate
- [ ] **Code**: `commands/init/init.py` — drive `_discover_usages` over the two roots (api +
  sandbox) and merge the results; extend `PYBUGGY_ANNOTATIONS` with the three hand-authored
  lines
- [ ] **Interface verification**: `.venv/bin/pytest tests/commands/init/ -x -v` — pass
- [ ] **Logic tests** (design test stack): `test_bootstrap_copies_and_registers_sandbox_usages`
  — existing bootstrap harness (tmp CWD, fake `.goga` config writer): all five files exist
  under tmp `.goga/usages/cooks/pybuggy/` (incl. `asserts.md` — as today); usage keys
  `pybuggy-sandbox-session`, `pybuggy-sandbox-file`, `pybuggy-data-operations` registered;
  annotation lines present for each key; plugin/`.usages` and commands usages NOT copied (scope
  constraint); `test_bootstrap_template_mode_skips_existing_targets` — pre-create
  `.goga/usages/cooks/pybuggy/sandbox-session.md` with sentinel content; run bootstrap twice in
  template mode → sentinel intact, INFO logged; bare mode (`template_mode=False`) overwrites
  (counter-test)
- [ ] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [ ] **Contract re-verification**: two-root scope, five-stem collection, registration parity
  ("one distribution path, one registration path"), unchanged copy gates
- [ ] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [ ] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 26: Root facade — re-export `active_sandbox` and `services` (TDD)

The two root embeddings made real: `from goga_tool_pybuggy import active_sandbox, services`
(the documented consumer import).

**Contract entities (changed)**: package facade `goga_tool_pybuggy/__init__.py` — adds
`from .sandbox import active_sandbox` and `from .sandbox.data import services`; both join
`__all__`.

**Usages relevant to this task:**
- `conventions`: relative imports; `__all__` as the facade definition.

**Design trace (verbatim)**: "Import weight: the sandbox package pulls
testcontainers/psycopg/kafka-python at import time — all declared in the main dependency block
(mandatory), so the import is always satisfiable; the CLI gains some import cost — accepted
(conventions prefer explicit over lazy)."

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **Declaration**: state that Task 26 is being executed
- [ ] **Contract tests**: create `tests/test_facade.py` —
  `test_facade_exports_capability_surface`: `from goga_tool_pybuggy import active_sandbox,
  services`; `callable(active_sandbox)`; `callable(services)`; `"active_sandbox"` and
  `"services"` in `goga_tool_pybuggy.__all__` (expected to fail now)
- [ ] **REPL prototype (R4)**: after the edit, import both names in the REPL and confirm the
  resolution path (root → `.sandbox` facade → `activation.active_sandbox`; root →
  `.sandbox.data` facade → `presets.services`)
- [ ] **Code**: extend `goga_tool_pybuggy/__init__.py` with the two relative imports and the
  two `__all__` entries (alphabetical placement)
- [ ] **Interface verification**: `.venv/bin/pytest tests/test_facade.py -x -v` — pass
- [ ] **Logic tests**: the import test itself is the behavioral assertion (embeddings → facade
  parity); also assert the CLI import path still works: `.venv/bin/python -c "from
  goga_tool_pybuggy import main"`
- [ ] **Debugging**: `.venv/bin/pytest tests/ -x` — fix implementation until green
- [ ] **Contract re-verification**: both embeddings importable; no behavior change for the CLI
- [ ] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0
- [ ] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 27: End-to-end validation — full suite, facade audit, packaging re-check

The final gate across all cells: everything green, every facade importable, the wheel carries
the usage files, the manifests untouched.

**Usages relevant to this task:**
- `conventions`: validation commands (run all tests, lint, facade checks) — the plan's
  Validation Commands section.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Full suite: `.venv/bin/pytest tests/ -x` — all tests pass (docker-gated tests run when
  the runtime is available, skip otherwise)
- [ ] Lint gate (pre-commit for the final commit): `.venv/bin/ruff check goga_tool_pybuggy/
  tests/` — exit 0
- [ ] Facade audit — every cell facade importable in one command each (config, engines, data,
  sandbox, root; see Validation Commands)
- [ ] Packaging re-check: rebuild the wheel; confirm the five packaged usage files and no
  CODEMANIFEST inside
- [ ] Manifest integrity (read-only): `goga lint` (23 cells, 0 errors) and `goga contract` (no
  issues) — confirms no CODEMANIFEST was modified during implementation
- [ ] Coverage sanity (optional, informational): `.venv/bin/pytest tests/ --cov=goga_tool_pybuggy
  --cov-report=term-missing` — review the sandbox subtree for untested branches

---

## Validation Commands

All commands run in the virtualenv (created in Task 1; conventions require it). Python 3.10+
compatibility required throughout.

- `.venv/bin/pytest tests/ -x`: Run all tests
- `.venv/bin/pytest tests/sandbox/ -v` (and per-file `pytest tests/<mirror>/test_<module>.py
  -v`): Run a specific scope — the focused feedback loop of the REPL cycle (R4.4)
- `.venv/bin/ruff check goga_tool_pybuggy/ tests/`: Lint check — the task-end gate AND the
  pre-local-commit gate (R3)
- `.venv/bin/ruff format goga_tool_pybuggy/ tests/`: Formatter (apply to touched files when
  drift appears)
- `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.config import SandboxConfig,
  ServiceConfig, InstanceConfig, StartupData, load_sandbox_config"`: Facade check — config cell
- `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.engines import DataOperation,
  InstanceAddress, check_runtime, build_engine, BaseEngine, PostgresEngine, KafkaEngine,
  VaultEngine, HttpEngine"`: Facade check — engines cell
- `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.data import DataBatch,
  PostgresInstance, KafkaInstance, VaultInstance, HttpInstance, services"`: Facade check —
  data cell
- `.venv/bin/python -c "from goga_tool_pybuggy.sandbox import Sandbox, BaselineBoundary,
  ServiceContainer, render_service_env, activate_sandbox, active_sandbox"`: Facade check —
  sandbox cell
- `.venv/bin/python -c "from goga_tool_pybuggy import active_sandbox, services"`: Facade
  check — root re-exports
- `goga lint` / `goga contract`: manifest integrity (read-only; informational — the contracts
  must remain untouched)

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location`
- [ ] Every contract entity is accessible from its cell facade (`__all__`), and
  `active_sandbox` / `services` from the root facade
- [ ] Properties and methods match the declared API (signatures, types per the Python rules)
- [ ] Descriptions are reflected in behavior (algorithms, requirements, constraints from the
  manifests and the design traces)
- [ ] Contract dependencies are met (Imports resolve; no cycles; sandbox subtree never imports
  plugin/api/root)
- [ ] Re-exports are accessible from the facade
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification →
  logic tests → debugging → re-verification → lint)
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task;
  all 38 design test scenarios exist (5 of them docker-gated via `requires_docker`)
- [ ] Integration tests exist where cross-entity scenarios require them (Task 23)
- [ ] No package boundary was expanded (no new cells; internal helpers stay inside their cell)
- [ ] `CODEMANIFEST` files were not modified (contract is read-only; verified by `goga lint` /
  `goga contract` in Task 27)
- [ ] All validation commands pass
- [ ] Every Usages entry is mentioned in at least one task (see the Usages Context mapping:
  conventions — every task; ruamel-yaml — Task 4; testcontainers — Tasks 5, 7–12, 19;
  psycopg — Task 8; kafka-python — Task 9; mokapi — Task 9; vault-dev — Task 10; wiremock —
  Task 11; requests — Tasks 10, 11, 19; jinja2 — Task 18; pluginator — Tasks 22, 24;
  imported sandbox-file — Tasks 18, 20, 22; data-operations — Tasks 15, 20, 23;
  sandbox-session — Tasks 23, 24)
- [ ] The Mandatory Rules were followed throughout: R1 coding style, R2 test rules, R3 lint and
  format gates at every development stage and before every local commit, R4 REPL cycle
  (prototype → evaluate → migrate → re-verify) with no scratch code left in the repo, R5
  contract discipline
