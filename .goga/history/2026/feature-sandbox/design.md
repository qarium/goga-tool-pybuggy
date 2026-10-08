# Design Document: Sandbox — session-scoped isolated service testing inside pybuggy

Topic directory: `.goga/history/2026/feature-sandbox/`. Sources: `task.md`, `adr.md` (accepted
2026-10-06), `prd.md`, the architecture plan `arch.md` (materialized into the cells by the
apply-architecture stage), and the CODEMANIFEST tree of branch `feature/sandbox` (working tree).
Every contract statement below traces to a CODEMANIFEST annotation or a usage file; every design
decision the contracts leave open is marked **[decision]** and justified. User-approved decisions
(the `all:A` answer of the design dialog, question `q1`): the CODEMANIFEST fix in
`load_sandbox_config` (§ Applied Fixes) and design choices 2A/3A/4A (postgres startup payload,
enqueue-time preset validation, docker-restart resets).

## Contract Changes

### Changed CODEMANIFEST Files

- `goga_tool_pybuggy/sandbox/config/CODEMANIFEST` (created): 5 types — `SandboxConfig`
  (`sandbox_config.py`), `ServiceConfig` (`service.py`), `InstanceConfig` (`instance.py`),
  `StartupData` (`startup_data.py`), `load_sandbox_config` (`loader.py`); practices `conventions`,
  `ruamel-yaml`; leaf cell, no Imports. Amended during this design: `load_sandbox_config` gained
  Algorithm step 6 (service env placeholder validation) — see § Applied Fixes.
- `goga_tool_pybuggy/sandbox/engines/CODEMANIFEST` (created): 9 types — `DataOperation`
  (`operation.py`), `InstanceAddress` (`address.py`), `check_runtime` + `build_engine`
  (`runtime.py`), `BaseEngine` (`base.py`), and the four kind mutations `BaseEngine::PostgresEngine`
  (`postgres.py`), `BaseEngine::KafkaEngine` (`kafka.py`), `BaseEngine::VaultEngine` (`vault.py`),
  `BaseEngine::HttpEngine` (`http.py`); Imports `InstanceConfig` from `sandbox/config`; practices
  `conventions`, `testcontainers`, `psycopg`, `kafka-python`, `mokapi`, `vault-dev`, `wiremock`,
  `requests`. No `.usages/` directory (by plan).
- `goga_tool_pybuggy/sandbox/data/CODEMANIFEST` (created): 6 types — `DataBatch` (`batch.py`),
  `PostgresInstance` (`postgres.py`), `KafkaInstance` (`kafka.py`), `VaultInstance` (`vault.py`),
  `HttpInstance` (`http.py`), `services` (`presets.py`); Imports `DataOperation`, `InstanceAddress`
  from `sandbox/engines`; practice `conventions`.
- `goga_tool_pybuggy/sandbox/CODEMANIFEST` (created): 6 types — `Sandbox` (`sandbox.py`),
  `BaselineBoundary` (`baseline.py`), `ServiceContainer` (`service_container.py`),
  `render_service_env` (`env_render.py`), `activate_sandbox` + `active_sandbox` (`activation.py`);
  Imports from `sandbox/config` (4 types + usage `sandbox-file`), `sandbox/engines` (5 types),
  `sandbox/data` (5 types + usage `data-operations`); practices `conventions`, `testcontainers`,
  `jinja2`, `requests`, `pluginator`.
- `goga_tool_pybuggy/plugin/CODEMANIFEST` (modified): Imports gains the `sandbox` edge
  (`activate_sandbox`, `active_sandbox`, `Sandbox`, usage `sandbox-session`) and the `sandbox/config`
  edge (`SandboxConfig`); header annotation paragraph (sandbox activation); new property
  `sandbox_activation`; `configure()` gains step 3 (the `--base-url` + armed sandbox fail-fast) and
  its Requirement; `api()` step 1 replaced (sandbox base_url resolution), new step 3 (the
  first-request guard) and the read-time constraint; `install()` gains step 2 (arming) and the
  one-enablement-surface Requirement.
- `goga_tool_pybuggy/commands/init/CODEMANIFEST` (modified): `run_bootstrap` step 2 replaced —
  packaged usage roots are the api cell plus the sandbox subtree cells; matching Requirement and
  Constraint lines.
- `goga_tool_pybuggy/CODEMANIFEST` (root, modified): Imports gains `active_sandbox` + usage
  `sandbox-session` from `sandbox` and `services` + usage `data-operations` from `sandbox/data`;
  header annotation paragraph (the capability surface); embeddings `->active_sandbox: {}` and
  `->services: {}` after `->install: {}`.

### New Entities

- `SandboxConfig(service: ServiceConfig, instances: dict[str, InstanceConfig], data: StartupData)`
  — config/sandbox_config.py: root model of `.sandbox.yml`.
- `ServiceConfig(image: str, env: dict[str, str], port: int, health: str | None)` —
  config/service.py: the service-under-test entry.
- `InstanceConfig(name: str, kind: str, image: str | None)` — config/instance.py: one named
  dependency instance.
- `StartupData(vault, http, kafka, postgres)` — config/startup_data.py: the four startup data
  sections in fixed order.
- `load_sandbox_config(path: str | None) -> config: SandboxConfig | None` — config/loader.py:
  fail-fast reading and validation of `.sandbox.yml`.
- `DataOperation(instance: str, kind: str, action: str, payload: dict[str, object])` —
  engines/operation.py: the uniform data-operation unit (startup data, presets, in-test
  operations, journal entries).
- `InstanceAddress(host: str, port: int)` — engines/address.py: the mapped address of a started
  instance.
- `check_runtime()` — engines/runtime.py: pre-start container-runtime probe.
- `build_engine(config: InstanceConfig) -> engine: BaseEngine` — engines/runtime.py: kind →
  engine factory.
- `BaseEngine(config: InstanceConfig)` — engines/base.py: the per-instance contract — start,
  apply, record, reset, stop, `address`; owns the baseline journal.
- `BaseEngine::PostgresEngine` / `::KafkaEngine` / `::VaultEngine` / `::HttpEngine` — the four
  kind engines (container, data plane, wipe).
- `DataBatch()` — data/batch.py: the lazy per-test accumulator (`add`, `take`).
- `PostgresInstance` / `KafkaInstance` / `VaultInstance` / `HttpInstance` — data/{postgres,kafka,
  vault,http}.py: test-facing views declaring operations (`insert`, `produce`, `put`, `stub`).
- `services(...presets) -> decorator: Callable` — data/presets.py: the per-test data-preset
  decorator.
- `Sandbox(config: SandboxConfig)` — sandbox/sandbox.py: the session runtime — ordered start/stop,
  `clear`, `baseline`, `apply_pending`, `ensure_service`, the four view factories, `base_url`.
- `BaselineBoundary(sandbox: Sandbox)` — sandbox/baseline.py: the immediate-apply boundary
  (`open`/`close`).
- `ServiceContainer(config: ServiceConfig)` — sandbox/service_container.py: the service under
  test — start/stop/`alive`/`logs`, `host`/`port`.
- `render_service_env(env, addresses) -> rendered: dict[str, str]` — sandbox/env_render.py:
  placeholder rendering of the service environment.
- `activate_sandbox(context: dict[str, object]) -> config: SandboxConfig | None` —
  sandbox/activation.py: presence-gated arming + hook registration.
- `active_sandbox() -> sandbox: Sandbox | None` — sandbox/activation.py: the session sandbox
  lookup seam.

### Changed Entities

- `install(...kwargs)` — plugin/__init__.py: gains step 2 — arming the sandbox via
  `activate_sandbox` and keeping the activation on the plugin (steps renumbered 3–5).
- `ApiPlugin` — plugin/plugin.py: gains the `sandbox_activation` property (plain attribute; not a
  pluginator option).
- `ApiPlugin.configure()` — plugin/plugin.py: gains step 3 — the `--base-url` + armed sandbox
  fail-fast (steps renumbered 4–5).
- `ApiPlugin.api()` — plugin/plugin.py: step 1 resolves the base URL through `active_sandbox`;
  new step 3 guards the request path (apply pending batch + died-service check).
- `run_bootstrap(template_mode)` — commands/init/init.py: step 2 discovery root widened to the
  packaged usage roots (api cell + sandbox subtree cells).
- package facade `goga_tool_pybuggy/__init__.py` — re-exports `active_sandbox` and `services`
  (the two root embeddings).

### Deleted Entities

- None.

### Usages and Annotations Changes

- New project-level cooks (untracked, created by the task formulation): `testcontainers.md`,
  `psycopg.md`, `kafka-python.md`, `mokapi.md`, `vault-dev.md`, `wiremock.md` under
  `.goga/usages/cooks/`; all referenced from the engines/sandbox `Usages` headers; all exist and
  were read for this design.
- New cell-level usage files: `sandbox/.usages/sandbox-session.md`,
  `sandbox/config/.usages/sandbox-file.md`, `sandbox/data/.usages/data-operations.md`.
- `plugin/.usages/enable.md`: appended the `## Sandbox activation` section.
- `commands/init/.usages/init.md`: the bootstrap artifact-table row now names the packaged
  capability usages (the api cell and the sandbox subtree cells).
- `.usages/assembly.md` (root cell): the facade re-export note for `active_sandbox` / `services`.
- Root/plugin header `Annotations` gained the capability-surface paragraphs referencing
  `sandbox-session` / `data-operations`.

## Applied Fixes

### Fixed CODEMANIFEST Defects

- `goga_tool_pybuggy/sandbox/config/CODEMANIFEST`, `load_sandbox_config` (user-approved, item 1A
  of the design dialog): the algorithm validated only the `data` sections against configured
  instances, but `sandbox-file.md` promises that an unknown instance reference fails **before any
  container starts** — and without a load-time check an unknown `{{name.host}}` placeholder in
  `service.env` would surface only in `render_service_env`, after the mock containers are already
  running (contradicting the documented guarantee and the task acceptance criterion "invalid file
  fails the run before any container starts").
  Before — Algorithm steps 1–6, no placeholder validation; After — new step 6 "Validate the
  service env values — every instance placeholder name references a configured instance" and the
  Requirement "The service env placeholder names resolve against the configured instances — an
  unknown name fails before any container starts" (reason: interface ↔ usage-doc consistency).
  `render_service_env` strict rendering remains as defense in depth. `goga lint` re-run: 23 cells,
  0 errors; `goga contract`: no issues.

No other CODEMANIFEST defects were found: the four consistency dimensions (Interface↔Type,
Type↔Mutation, Interface↔Interface, Annotations↔Entity) verify clean — the kind mutations all
resolve against the local `BaseEngine`, the cross-cell type flow matches at every boundary
(verified per trace below), and all backtick references resolve (linter-verified).

## Entity Interaction and Data Flow

### Interaction Diagram

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

### Data Flows

**Startup flow** (entry: `pytest_sessionstart`): `SandboxConfig` → per-instance
`list[DataOperation]` (StartupData sections in the fixed order vault → http → kafka → postgres) →
`BaseEngine.start(startup)` (container + readiness + data plane + journaled startup) →
`dict[str, InstanceAddress]` → `render_service_env` → `dict[str, str]` rendered env →
`ServiceContainer.start(env)` → readiness → `Sandbox.base_url` (str). Failure at any step stops
and removes everything started so far, then re-raises.

**Declaration → apply flow** (entry: `pytest_runtest_setup`, then the guarded first request):
`services(...)` marker presets → `DataOperation`s enqueued into the fresh `DataBatch`; in-test
view calls (`insert`/`produce`/`put`/`stub`) append more `DataOperation`s; the guarded
`Api.request` drains the batch (`take()`), groups by instance preserving accumulation order, and
applies each group through the instance's `BaseEngine.apply`. Nothing executes at declaration
time.

**Baseline flow** (entry: consumer session fixture, `with sbx.baseline():`): inside the boundary
the sandbox hands views an immediate-routing batch — each declared operation runs
`engine.apply([op])` + `engine.record([op])` at declaration time. `close()` freezes the journals
(startup ops + boundary ops, in application order).

**Reset flow** (entry: consumer autouse fixture, `sandbox.clear()`): per engine — postgresql:
catalog discovery + `TRUNCATE ... RESTART IDENTITY CASCADE`, then journal replay; kafka/vault:
docker restart of the same container (address unchanged), readiness re-wait, data-plane client
rebuilt, then journal replay (the journaled kafka `spec` op replays as a no-op); http:
`POST /__admin/mappings/reset`, then journal replay. The service container is never restarted.

**Teardown flow** (entry: `pytest_sessionfinish`): `Sandbox.stop()` — service stop, then engines
in reverse start order, each guarded (safe when already stopped); `active_sandbox()` returns None
afterwards. Ryuk (testcontainers) is the crash-path safety net behind the explicit stop.

### Entity Dependencies

Design order (leaves first): `sandbox/config` → `sandbox/engines` → `sandbox/data` → `sandbox` →
`plugin` / root facade / `commands/init` scope. Runtime construction order inside the session:
engines (declaration order of `instances`) → service container → boundary (consumer) → per-test
batches. The plugin's `sandbox_activation` attribute is the only cross-cell state crossing the
plugin boundary (the armed `SandboxConfig`); everything else the plugin needs at runtime it reads
through `active_sandbox()`.

## Code Stack Trace

### Trace: `plugin.install` (conftest import time)

#### Chain
1. **Input**: consumer `conftest.py` top-level `from goga_tool_pybuggy import plugin;
   plugin.install()`; optional kwargs (`context`, `loaders`, defaults).
2. `context = call_context()` — resolves the conftest module globals through the one-level
   wrapper (pluginator contract) → checkpoint: same namespace pytest later scans for hooks ✓.
3. `activation = activate_sandbox(context)` — reads and validates `.sandbox.yml` (see next
   trace); registers `pytest_sessionstart` / `pytest_sessionfinish` / `pytest_runtest_setup`
   into `context` when the document is present; returns `SandboxConfig | None` → checkpoint:
   pluginator's `install_pytest_plugins` injects only `pytest_addoption` /
   `pytest_configure` / `pytest_collection_finish` — no key collisions ✓; an invalid document
   raises here, i.e. before pytest_configure, before any container ✓.
4. `kwargs.setdefault("loaders", [PackageLoader("api", required=False)])` — unchanged.
5. `plugin = ApiPlugin(**kwargs)` — synchronous fixture registration (unchanged).
6. `plugin.sandbox_activation = activation` — **[decision]** the manifest places arming (step 2)
   before construction (step 4), so the activation is held locally and assigned to the plugin
   after construction; `ApiPlugin.__init__` initializes `self.sandbox_activation = None` (plain
   attribute, not a `define.option` — it is not user-configurable) → checkpoint: assignment
   precedes `pytest_configure` (which calls `configure()`), so the fail-fast always sees the
   armed state ✓.
7. `install_pytest_plugins(plugin, context=kwargs["context"])` — same context as the sandbox
   hooks ✓.
8. **Output**: None — conftest namespace now carries the pluginator hooks plus (when armed) the
   three sandbox lifecycle hooks and `pytest_plugins`.

#### Checkpoint Summary
- Hook-namespace collision freedom: passed (disjoint hook names).
- Ordering (arm → construct → assign → install → configure): passed; `configure()` runs strictly
  after `install()` in the pluginator lifecycle.
- Inertness without the document: passed — `activate_sandbox` registers nothing and returns None.

### Trace: `activate_sandbox(context)` + the registered hooks

#### Chain
1. **Input**: `context: dict[str, object]` — the conftest namespace dict.
2. `config = load_sandbox_config(None)` — resolves `.sandbox.yml` in the CWD (the consumer
   repository root; pytest runs from there — documented in `enable.md` for loaders, same rule)
   → checkpoint: invalid document raises with the location and entry named, before anything is
   registered or started ✓.
3. `config is None` → register nothing, return None (fully inert) ✓.
4. Register hooks into `context`: `pytest_sessionstart(session)` — register the
   `pybuggy_services` marker (`session.config.addinivalue_line("markers", "pybuggy_services:
   per-test sandbox data presets (applied by the pybuggy sandbox)")` — the hook runs before
   collection, so applying the marker in test modules never emits `PytestUnknownMarkWarning`;
   `pytest_configure` is not usable here — pluginator injects its own into the same namespace
   after arming and would clobber it), build `Sandbox(config)`,
   `start()` (next trace), set the module-level active reference; `pytest_sessionfinish(session,
   exitstatus)` — `stop()` the active sandbox, clear the reference; `pytest_runtest_setup(item)`
   — fresh batch + preset enqueue (trace below). **[decision]** collision handling: if the
   namespace already defines one of the hook names, the sandbox wraps the prior callable
   (prior first, sandbox hook second) instead of clobbering it — a conftest that defines its own
   `pytest_sessionstart` keeps working; keys absent in practice in the documented pattern.
   → checkpoint: hooks are plain functions in the conftest namespace — pytest discovers them as
   conftest hook impls ✓; `pytest_sessionstart` runs after `pytest_configure` and before any
   fixture ✓.
5. Return `config` — the armed activation.
6. **Output**: `SandboxConfig | None`; side effect — three hooks in `context` when armed.

#### Checkpoint Summary
- Presence gating: passed (None ⇒ no keys touched, no imports executed at call time beyond the
  already-imported module).
- Fail-fast position: passed — validation precedes hook registration and any container.
- Session-start ordering vs fixtures: passed (sessionstart precedes collection and fixtures).

### Trace: `load_sandbox_config(path)`

#### Chain
1. **Input**: `path: str | None` (None ⇒ `.sandbox.yml` in CWD).
2. Absent document → return None (inert) ✓.
3. Parse with `ruamel.yaml` (round-trip `YAML()`; `preserve_quotes=True` is irrelevant for
   read-only validation but the practice pins the API) → unparsable document raises
   `ValueError` naming the location and the parse problem ✓.
4. Validate the service entry: `image`, `env`, `port` required; `health` optional (`str | None`);
   `env` values are strings → `ServiceConfig` ✓.
5. Validate instances: non-empty name; `kind ∈ {postgresql, kafka, vault, http}`; `grpc` fails
   with an explicit "not supported yet" error; `image` optional → `InstanceConfig` per name ✓.
6. Validate the data sections: every declaration targets an existing instance of the matching
   kind (vault section → vault instances, http → http, kafka → kafka, postgres → postgresql);
   the kafka spec paths are resolved here against the document directory (relative → absolute,
   absolute as-is — string resolution only, the file is not read), so no downstream consumer
   needs the document location ✓.
7. Validate the service env placeholders **[the applied fix; grammar tightened in review]**: every
   `{{ … }}` occurrence in a value must match the documented grammar `{{<name>.host}}` or
   `{{<name>.port}}` (whitespace-tolerant), with `<name>` a configured instance; a bare
   `{{<name>}}`, an unknown attribute, or an unknown name raises `ValueError` naming the env
   key, the value, and the document location ✓ — before any container starts.
8. **Output**: `SandboxConfig(service, instances, data)` — pydantic, kw_only; data sections
   default empty.

#### Checkpoint Summary
- Complete pre-start validation: passed (kinds, targets, placeholders, required fields, parse).
- Error actionability: passed (location + offending entry in every message).

### Trace: session start — `pytest_sessionstart` → `Sandbox.start()`

#### Chain
1. **Input**: the armed `SandboxConfig`.
2. `check_runtime()` — daemon probe via the testcontainers docker client (`DockerClient().client
   .ping()`); unreachable → `RuntimeError` naming the requirement ("a docker-compatible
   container runtime must be available in the environment running the tests") ✓ checkpoint:
   probe precedes the first container start; the failure is immediate, never a hang ✓.
3. Build engines: for each `(name, instance_config)` in `config.instances` (declaration order) →
   `build_engine(instance_config)`; unmapped kind is impossible here (validated at load) but the
   factory still fails readable for defense ✓.
4. Assemble per-instance startup operations from `StartupData` in the fixed section order —
   vault (`put`, payload `{path, data}`), http (`stub`, payload = the mapping object), kafka
   (`spec`, payload `{path}`), postgres (`insert`, payload `{sql}` — **[decision 2A]**, see the
   payload table in § Algorithm Design) → checkpoint: section order is the journal order per
   instance; kind/payload shapes match the `DataOperation` contract ✓.
5. Per instance: `engine.start(startup_ops)` — build the kind container (pinned image or the
   declared override, labels, published ports), start, wait readiness, open the data plane,
   apply the startup ops in order, journal them → checkpoint: `start` returns only after
   readiness + data applied + journaled; a failed start stops what it created ✓.
6. `addresses = {name: engine.address}` — read back from the container engine (mapped host +
   published port; never a fixed host port) ✓.
7. `rendered = render_service_env(config.service.env, addresses)` (trace below).
8. `ServiceContainer(config.service).start(rendered)` — generic container, rendered env,
   labels, published service port; readiness = the port, or the health path via `requests` when
   configured ✓.
9. `self.base_url = f"http://{service.host}:{service.port}"`; INFO log naming the resolved
   address and its source ("sandbox") ✓.
10. Progress logging at every step (INFO, lowercase event names, contextual `extra`) ✓.
11. Any exception → `self.stop()` (remove everything started so far) → re-raise ✓ checkpoint:
    "leaves nothing behind" holds on the failure path too.
12. **Output**: the running sandbox; `active_sandbox()` resolves it from here on.

#### Checkpoint Summary
- Ordering (runtime probe → instances+data → env render → service → readiness): matches the ADR
  startup order ✓.
- Type flow `InstanceAddress` → `render_service_env` → `dict[str, str]` → `ServiceContainer.
  start(env)`: passed.
- Cleanup-on-failure: passed (stop in except; Ryuk behind it).

### Trace: `BaseEngine.start` / `_execute` (per kind)

#### Chain
1. **Input**: `config: InstanceConfig`; `startup: list[DataOperation]`.
2. Common base: build container (kind hook), start + readiness wait (kind hook), open the
   data-plane connection (kind hook), then `apply(startup)` through the normal execution path
   and `journal.extend(startup)` → checkpoint: startup data is part of the baseline every reset
   replays ✓; `apply` itself never records ✓.
3. Postgres data plane: payload `{"sql": s}` → `cur.execute(s)`; payload `{"table": t, "rows":
   rs}` → `executemany` of a parameterized `INSERT INTO "<t>" ("<cols>") VALUES (%s, ...)`
   (column list from the first row's keys, insertion order; identifiers double-quoted, values
   bound server-side — never formatted) ✓ checkpoint: psycopg placeholder contract honored.
4. Kafka: the `spec` op is consumed by the container build — the AsyncAPI document (path from
   the payload — already absolute: the loader resolved it against the document directory at
   load) is volume-mounted at a fixed container path and passed as the container command
   argument; `_execute`
   on a `spec` op is a no-op (replay-safe) ✓; `produce` ops send via `KafkaProducer.send` and
   confirm at the batch boundary (`future.get(timeout=10)` per message, `flush(timeout=30)` per
   apply group) ✓ checkpoint: a broken bootstrap fails within the deadline — no hang ✓.
5. Vault: `put` → `requests.post("http://host:port/v1/secret/data/<path>", headers={"X-Vault-
   Token": DEV_TOKEN}, json={"data": data}, timeout=5)`; non-2xx → readable error naming the
   path ✓ checkpoint: the dev token is a fixed fixture credential (`"sandbox-root"`), never
   logged ✓.
6. Http: `stub` → `requests.post("http://host:port/__admin/mappings", json=mapping, timeout=5)`;
   non-2xx → readable error naming the operation ✓ checkpoint: mapping objects pass through
   untouched (matching/priority/delays/faults stay available) ✓.
7. Every `_execute` failure is wrapped: `instance '<name>': <action> failed: <cause>` —
   identifying the instance, the operation, and the cause ✓.
8. **Output**: a ready, data-applied, journaled instance; `address` readable.

#### Checkpoint Summary
- Journal semantics (startup ∈ journal; apply does not record): passed.
- Usages conformance (psycopg binding, kafka-python flush boundary, vault KV v2 path shape,
  wiremock admin endpoints): verified against the cooks ✓.

### Trace: `render_service_env(env, addresses)`

#### Chain
1. **Input**: `env: dict[str, str]` (raw values), `addresses: dict[str, InstanceAddress]`.
2. Context: `{name: {"host": address.host, "port": address.port}}` ✓ checkpoint: matches the
   documented `{{<instance>.host}}` / `{{<instance>.port}}` syntax ✓.
3. `jinja2.Environment(undefined=StrictUndefined)` renders each value; `UndefinedError` is
   wrapped into `ValueError` naming the env key and value ✓ (unreachable via the load-time
   validation — defense in depth).
4. Values without placeholders render to themselves ✓.
5. **Output**: `dict[str, str]` — fully rendered values for `ServiceContainer.start`.

#### Checkpoint Summary
- Strict rendering + naming the value: passed. No whitespace stripping (unlike
  `render_base_url` — env values are not URLs; the manifest does not require it).

### Trace: the baseline boundary — `Sandbox.baseline()` / `BaselineBoundary`

#### Chain
1. **Input**: the consumer session fixture: `with sbx.baseline():`.
2. `baseline()` constructs `BaselineBoundary(sandbox=self)`; **[decision]** `BaselineBoundary`
   implements `__enter__` → `open()` and `__exit__` → `close()` so the documented `with` form
   works; `open()`/`close()` remain the declared methods ✓.
3. `open()` switches the sandbox's declaration routing to immediate mode: from here on the
   batch object the view factories bind is a `BoundaryBatch` (a `DataBatch` subclass internal
   to `baseline.py`) whose `add(operation)` performs `engine.apply([operation])` followed by
   `engine.record([operation])` → checkpoint: operations apply at declaration time and land in
   the journal — exactly the boundary contract; `BaseEngine.apply` still does not record ✓;
   `take()` returns `[]` (nothing accumulates) ✓.
4. `close()` switches routing back to the lazy per-test batch; the journals are frozen simply
   because no further `record` calls happen (boundary closed) ✓ checkpoint: journal = startup
   ops + boundary ops in application order — the full session baseline ✓.
5. Exception inside the `with` block: `__exit__` still closes the boundary (mode restored), the
   exception propagates — author errors are not swallowed ✓.
6. **Output**: the boundary object; side effect — journaled baseline.

#### Checkpoint Summary
- View signatures untouched (`PostgresInstance(name, address, batch)` — the sandbox just hands
  out a different `batch` object while the boundary is open) — passed.
- Lazy contract outside the boundary preserved (`DataBatch.add` executes nothing) — passed.

### Trace: `pytest_runtest_setup(item)` — fresh batch + preset enqueue

#### Chain
1. **Input**: the pytest `Item`; the active sandbox (None when unarmed — hook returns
   immediately).
2. `sandbox.new_test_batch()` — replace the current `DataBatch` with a fresh one → checkpoint: a
   new test never sees a previous test's operations ✓.
3. For every `pybuggy_services` marker on the item (**[decision]** the `services` decorator
   applies `pytest.mark.pybuggy_services(presets={...})`): for each kind → instance name →
   declaration list, resolve the instance engine (kind must match; unknown name fails listing
   the configured instances — **[decision 3A]**: kinds are validated at decoration time where
   they are a static set; instance names are validated here, at enqueue, against the single
   config authority) and append `DataOperation(instance, kind, action_of_kind, payload=
   declaration)` to the batch, ahead of any in-test operation ✓ checkpoint: the declaration
   fields are exactly the view-operation fields (payload table) ✓.
4. **Output**: the test's batch pre-loaded with its presets; nothing executed.

#### Checkpoint Summary
- Presets precede in-test operations: passed (enqueue at setup; in-test declarations happen
  later).
- Unknown instance name: fails at setup with the configured instances listed — before the test
  body ✓.

### Trace: consumer reset fixture → `Sandbox.clear()`

#### Chain
1. **Input**: the consumer's autouse `_sandbox_reset(sandbox)` fixture calls `sandbox.clear()`
   before the test body.
2. For every engine (any deterministic order — instances are independent): `engine.reset()` →
   checkpoint: per-kind wipe + journal replay (trace below); the service container is untouched
   ✓.
3. **Output**: every instance at exactly the baseline state; test order cannot change outcomes.

#### Checkpoint Summary
- Reset does not restart the service: passed (constraint held by construction — `clear` only
  touches engines).

### Trace: per-kind `reset()` (wipe variants)

#### Chain
1. Postgres: discover user tables from `information_schema.tables` (BASE TABLE, schemas outside
   `pg_catalog`/`information_schema`) at reset time; one `TRUNCATE TABLE "s1"."t1", ...
   RESTART IDENTITY CASCADE`; replay the journal through `_execute` ✓ checkpoint: catalog
   discovery at every reset (mid-session DDL tolerated); FK ordering carried by CASCADE; the
   container is never restarted ✓.
2. Kafka (**[decision 4A]**): docker-restart the same container through the docker SDK object
   held under the testcontainers wrapper (`restart(timeout=10)`) — the published host port and
   container id are preserved, so the address baked into the service env stays valid; re-wait
   the HTTP health readiness; rebuild the producer against the same mapped address; replay the
   journal (the `spec` op is a no-op) ✓ checkpoint: address stability is what makes the
   ADR-accepted "services tolerate reconnect" trade-off workable; remove+recreate would change
   the random host port and silently break the service wiring — rejected ✓.
3. Vault: docker-restart the same container (in-memory storage wipes), re-wait `/v1/sys/health`,
   replay the journal over the same HTTP paths ✓.
4. Http: `POST /__admin/mappings/reset` (drops API-created mappings), replay the journal (the
   startup mappings + baseline re-POST) ✓.
5. **Output**: baseline state restored on every kind.

#### Checkpoint Summary
- "Wipe to the kind's empty state, then replay the journal through the same execution path as
  apply": passed for all four kinds.
- Restart kinds preserve their published address: passed (same container restarted).

### Trace: the `api` fixture — substitution + the request guard

#### Chain
1. **Input**: function-scoped fixture invocation; the resolved plugin options; the active
   sandbox (or None).
2. `sandbox = active_sandbox()`; `base_url = sandbox.base_url if sandbox is not None else
   self.base_url` → checkpoint: read-time choice between the rendered option value and the
   sandbox address; the option is neither rendered nor mutated here ✓; the option stays required
   and configure renders it exactly as before ✓.
3. `api = Api(base_url=base_url, headers=self.headers, timeout=self.timeout,
   assert_timeout=..., assert_delay=..., assert_field_class=..., assert_response_class=...)` —
   the remaining options unchanged ✓.
4. When a sandbox is active, wrap the request path: an instance-level attribute `api.request`
   shadows the class method with a closure that, before delegating, calls
   `sandbox.apply_pending()` and `sandbox.ensure_service()` and then invokes the original bound
   method → checkpoint: every request path in the cell funnels through `Api.request`
   (`Endpoint._call` line `raw = self.api.request(...)`) — the generated endpoint fixtures and
   direct `api.request` calls are both covered ✓; tests stay unaware of the apply point ✓;
   `apply_pending` drains on the first guarded request and is a no-op afterwards; the
   died-service check runs on every guarded request (cheap liveness check; the contract
   requires at least the first) ✓.
5. `yield api` — the test runs.
6. Teardown: `api.close()` (unchanged); the wrapper dies with the instance.
7. **Output**: the guarded `Api`.

#### Checkpoint Summary
- Sandbox precedence over the rendered value: passed.
- No rendering in the fixture: passed (constraint).

### Trace: `ApiPlugin.configure()` — the fail-fast path

#### Chain
1. **Input**: pluginator lifecycle call at `pytest_configure` (after `init_pytest_config` and
   plugin install).
2. Collect the CLI options the user actually typed (`invocation_params.args` tokens → normalized
   names → resolved values, None dropped) — unchanged ✓.
3. Typed `--base-url` → store its resolved value onto the `base_url` option (unchanged) ✓.
4. Fail fast: typed `--base-url` ∧ `self.sandbox_activation is not None` → raise
   `pytest.UsageError("--base-url was passed while the sandbox is active (.sandbox.yml present):
   the sandbox owns the service address — remove the flag or the document")` (**[decision]**:
   `pytest.UsageError` — the idiomatic config-phase abort; pytest presents it cleanly and stops
   before collection) → checkpoint: the error names both facts ✓; it precedes any container
   start (`pytest_sessionstart` runs after `pytest_configure`) and any test ✓.
5. Otherwise: build the rendering context (`os.environ` + typed CLI options) and render once via
   `render_base_url` — unchanged ✓.
6. **Output**: the rendered `base_url` option value, or an aborted run.

#### Checkpoint Summary
- Fail-fast position (configphase, pre-container, pre-test): passed.
- Non-sandbox behavior unchanged: passed (steps identical when `sandbox_activation is None`).

### Trace: `pytest_sessionfinish` → `Sandbox.stop()`

#### Chain
1. **Input**: session end (any exit path — success, failure, interrupt; SIGKILL is covered by
   Ryuk per the testcontainers practice).
2. `stop()`: stop the service container, then every engine in reverse start order — each call
   guarded (already-stopped is safe; attribute-missing after a failed start is safe) ✓.
3. Clear the active-sandbox module reference; `active_sandbox()` returns None afterwards ✓.
4. **Output**: nothing remains; an immediate rerun starts fresh.

#### Checkpoint Summary
- Stop on every exit path + idempotence: passed.

### Trace: `run_bootstrap` step 2 — packaged usage discovery

#### Chain
1. **Input**: `template_mode: bool`; CWD = the consumer project root.
2. Discover every `.usages/*.md` under the packaged usage roots — **[decision]** the existing
   `_walk` recursion is driven over two roots resolved via `importlib.resources`: the `goga_
   tool_pybuggy.api` package (as today — the walk also recurses into the `asserts` sub-package,
   so `asserts.md` keeps being collected exactly as today) and the `goga_tool_pybuggy.sandbox`
   package (the walk recurses into `sandbox/config` and `sandbox/data`; `engines` has no
   `.usages` and contributes nothing) → checkpoint: matches the manifest wording "the api cell
   and the cells of the sandbox subtree that carry usage files"; plugin/commands cells are not
   roots (constraint: do not copy beyond the packaged usage roots) ✓; stems are unique across
   the five collected (`api`, `asserts`, `sandbox-session`, `sandbox-file`, `data-operations`) ✓
   — review correction: four was a miscount, `asserts` rides the api-package root already
   today (`PYBUGGY_ANNOTATIONS` carries its hand-authored line).
3. Copy each to `.goga/usages/cooks/pybuggy/<stem>.md` — template mode: existing target skipped
   with an INFO log; bare mode: overwritten (unchanged mechanics) ✓.
4. Register usage keys `pybuggy-<stem>` via `register_usages` and annotation lines via
   `register_annotations` (step 7, unchanged mechanics) — `PYBUGGY_ANNOTATIONS` gains
   hand-authored lines for the three new stems ✓ checkpoint: "one distribution path, one
   registration path" — the sandbox usages land exactly like the api usages ✓.
5. **Output**: the four capability usage files in the consumer cooks directory + registered keys.

#### Checkpoint Summary
- Scope constraint (no usages beyond the packaged roots): passed.
- Stem uniqueness / registration parity: passed.

### Trace: root facade import

#### Chain
1. **Input**: `from goga_tool_pybuggy import active_sandbox, services` (the documented consumer
   import).
2. `goga_tool_pybuggy/__init__.py` adds `from .sandbox import active_sandbox` and
   `from .sandbox.data import services`; both join `__all__` ✓ checkpoint: the embeddings
   (`->active_sandbox: {}`, `->services: {}`) require exactly this re-export ✓.
3. Import weight: the sandbox package pulls testcontainers/psycopg/kafka-python at import time —
   all declared in the main dependency block (mandatory), so the import is always satisfiable;
   the CLI gains some import cost — accepted (conventions prefer explicit over lazy) ✓.
4. **Output**: importable capability surface; no behavior change for the CLI.

#### Checkpoint Summary
- Embedding → facade parity: passed.

## Algorithm Design

### Common payload table — `DataOperation` shapes **[decision 2A]**

| kind | action | payload keys | origin |
|---|---|---|---|
| postgresql | `insert` | `table: str`, `rows: list[dict]` | view `insert` / preset declaration |
| postgresql | `insert` | `sql: str` | startup section only (raw statement, executed as given) |
| kafka | `produce` | `topic: str`, `value: dict \| str`, `key: str \| None` | view `produce` / preset |
| kafka | `spec` | `path: str` | startup section only (mounted at container start; replay no-op) |
| vault | `put` | `path: str`, `data: dict` | view `put` / preset / startup |
| http | `stub` | the mapping object itself (`request`, `response`, …) | view `stub` / preset / startup |

The action set stays as fixed in the manifest (`insert`/`produce`/`put`/`stub` + startup-only
`spec`); the two postgres payload forms are discriminated by key (`sql` vs `table`+`rows`).

Note on the pseudocode below: every pydantic model here is `kw_only` (per `conventions` and the
manifests) — constructor calls are keyword-only; positional spellings such as
`DataOperation(name, "postgresql", …)` in schematic snippets stand for the keyword form.

### `SandboxConfig`, `ServiceConfig`, `InstanceConfig`, `StartupData` (config cell)

**Responsibility**: the declarative model of `.sandbox.yml` — pydantic, kw_only; data sections
default empty; the service entry required.

**Algorithm** (validation lives in the loader; the models carry field types and defaults):
```
1. StartupData field order IS the section order (vault, http, kafka, postgres)
   → declaration order within a section is preserved by list semantics
```

**Errors**: pydantic type errors surface through the loader's wrapping (location + entry named).

**Edge cases**: empty `instances` allowed (a service with no dependencies — only service +
optional data on nothing is then impossible by target validation); empty `data` sections default
empty; `health` None ⇒ port readiness only.

### `load_sandbox_config` (config cell)

**Responsibility**: read and validate `.sandbox.yml` fail-fast.

**Algorithm:**
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

**Errors:** `ValueError` with location + offending entry for every failure above.

**Edge cases:** empty file → parse produces None → treated as an invalid document (a sandbox
document must carry the service entry) — error names the location.

### `DataOperation`, `InstanceAddress` (engines cell)

**Responsibility**: the uniform operation unit (pydantic, kw_only; plain serializable payloads)
and the mapped address record (pydantic, kw_only). Addresses are always read back from the
container engine — never a fixed host port.

**Edge cases:** `payload` is plain data (`dict[str, object]`) — no callables, no models.

### `check_runtime` (engines cell)

**Responsibility**: probe daemon reachability before the first start.

**Algorithm:**
```
1. ping the daemon through the testcontainers docker client (docker SDK under it)
2. failure (DockerException, connection errors) → RuntimeError naming the requirement:
   "a docker-compatible container runtime must be available in the environment running the tests"
```

**Constraints:** no container is started here.

### `build_engine` (engines cell)

**Algorithm:**
```
1. kind → class: postgresql→PostgresEngine, kafka→KafkaEngine, vault→VaultEngine, http→HttpEngine
2. unmapped kind → EngineError listing the supported kinds (defense; the loader already rejects)
3. construct with the InstanceConfig — the image override reaches the engine via config.image
```

### `BaseEngine` (engines cell)

**Responsibility**: per-instance lifecycle + the baseline journal.

**Algorithm:**
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

**Errors:** `EngineError(RuntimeError)` — `instance '<name>': <action> failed: <cause>`; start
failures append the kind step that failed.

**Edge cases:** `apply([])` no-op; `reset()` with an empty journal = wipe only; `stop()` twice
safe; operations before start are impossible (views exist only after start).

### Kind engines

**`PostgresEngine`**
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
idempotent (e.g. CREATE TABLE IF NOT EXISTS) — the journal replays it after every TRUNCATE-based
reset and TRUNCATE keeps tables in place.

**`KafkaEngine`**
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

**`VaultEngine`**
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
Edge: writes create versions — irrelevant under restart-wipe.

**`HttpEngine`**
```
container: DockerContainer(config.image or "wiremock/wiremock:3.13.0"), port 8080
readiness: GET /__admin/health (3.x; fall back to GET /__admin/mappings) with deadline
plane:     requests, timeout=5
_execute:  stub → POST /__admin/mappings json=mapping (mapping passes through as given)
_wipe:     POST /__admin/mappings/reset
stop:      container.stop()
```

### `DataBatch` (data cell)

```
add(operation): append; nothing executes
take(): drained = list(ops); ops.clear(); return drained
```

### Instance views (data cell)

```
PostgresInstance(name, address, batch): properties name/host/port (from address)
  insert(table, rows)  → batch.add(DataOperation(name, "postgresql", "insert",
                                   {"table": table, "rows": rows}))
KafkaInstance:   produce(topic, value, key=None) → action "produce",
                  payload {"topic", "value", "key"}
VaultInstance:   put(path, data) → action "put", payload {"path", "data"}
HttpInstance:    stub(mapping) → action "stub", payload = mapping
```

### `services` (data cell)

```
services(**presets):                      # kind → instance name → declaration list
  1. every kind ∈ {postgresql, kafka, vault, http} → else ValueError at decoration
     (instance names are validated at enqueue — decision 3A)
  2. return decorator: item → apply pytest.mark.pybuggy_services(presets=presets)
     (nothing executes at decoration time)
```

### `Sandbox` (sandbox cell)

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

### `BaselineBoundary` + `BoundaryBatch` (sandbox cell)

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

### `ServiceContainer` (sandbox cell)

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

### `render_service_env` (sandbox cell)

```
1. context = {name: {"host": a.host, "port": a.port} for name, a in addresses.items()}
2. for each (key, value): rendered = jinja2 Environment(StrictUndefined).from_string(value)
   .render(context); UndefinedError → ValueError naming the env key and value
```

### `activate_sandbox` / `active_sandbox` (sandbox cell)

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

### Plugin changes (`ApiPlugin`, `install`)

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

### `run_bootstrap` step 2 (commands/init)

```
roots = [importlib.resources.files("goga_tool_pybuggy.api"),
         importlib.resources.files("goga_tool_pybuggy.sandbox")]
discovered = [(stem, text) for root in roots for (stem, text) in _walk(root)]
# copy + register unchanged; PYBUGGY_ANNOTATIONS += sandbox-session / sandbox-file /
# data-operations hand-authored lines
```

## Cross-cutting Concerns

- **Error handling**: fail-fast everywhere; no swallowing, no retries except where a practice
  pins them (kafka producer `retries=3`). Every error names its subject: the document location +
  entry (loader), the runtime requirement (`check_runtime`), the instance + operation + cause
  (`EngineError`), the died service + its output (`ensure_service`), both facts of the
  `--base-url` conflict (`pytest.UsageError`). Internal exception types: `EngineError(
  RuntimeError)` in engines/base.py; `ValueError` for loader/declaration validation; `RuntimeError`
  for runtime/died-service conditions; `pytest.UsageError` for the configphase conflict.
- **Logging**: `logging` per conventions — lowercase stable event names, contextual `extra`
  metadata, structured output. INFO: lifecycle (runtime check, instance starting/ready, startup
  data applied, env rendered, service starting/ready, base_url source, stopped). DEBUG: payload
  previews, rendered env values, guard invocations. ERROR: start/stop failures, died service.
  Never logged: the vault dev token (fixture credential), secret payloads (vault data), full
  env dumps in one line (per-key DEBUG only).
- **Validation**: complete at load (parse, service entry, kinds incl. the grpc rejection, data
  targets, env placeholders — all before any container); decoration-time kind check in
  `services`; enqueue-time instance-name resolution; strict render-time placeholders (defense
  in depth); runtime probe before the first container.
- **Caching**: none beyond the session-singleton active sandbox, the per-session engines/
  connections, and the per-test batch. No TTLs, no memoization of data.
- **Concurrency**: single-threaded pytest session; no thread-safety requirements (xdist and
  parallel sandboxes are out of scope per the task). Sequences: one sandbox per session; one
  batch per test.

## Usages Analysis

### `conventions`
- **What it provides**: mandatory Python rules — relative imports, pydantic kw_only models,
  structured logging, Google docstrings, test structure, dependency declaration.
- **Where used**: every touched cell (global annotations).
- **Why chosen**: project-wide mandate.
- **How exactly**: pydantic kw_only models for all data records; `logging` with `extra`;
  docstrings on all public surface; tests mirror `goga_tool_pybuggy/sandbox/…` under
  `tests/sandbox/…`.

### `ruamel-yaml`
- **What it provides**: the round-trip YAML API used for parsing `.sandbox.yml`.
- **Where used**: `load_sandbox_config` (config cell).
- **Why chosen**: the project's pinned YAML library for document reading.
- **How exactly**: `YAML()` instance, `yaml.load(path)`, None-for-empty handling; validation
  happens on the parsed mapping before model construction.

### `testcontainers`
- **What it provides**: container lifecycle — module/generic containers, readiness waiting,
  labels, Ryuk, the runtime requirement.
- **Where used**: `check_runtime`, `build_engine`, all kind engines, `ServiceContainer`.
- **Why chosen / how exactly**: `PostgresContainer` for postgres (module readiness, accessor-
  based host/port); `DockerContainer` + `with_exposed_ports` / `with_env` / `with_command` /
  `with_labels` (+ volume mount for the kafka spec) for the mocks and the service; `wait_for` /
  explicit probe loops with deadlines for generic readiness; Ryuk left enabled; stop removes.

### `psycopg`
- **What it provides**: the postgres data plane.
- **Where used**: `PostgresEngine`.
- **How exactly**: one autocommit session connection from container accessors
  (test/test/test); `%s`-bound parameters / `executemany`; catalog query + quoted-identifier
  TRUNCATE at reset; `conn.close()` at stop (no `with` scope — it is a transaction scope).

### `kafka-python`
- **What it provides**: producing into the kafka mock.
- **Where used**: `KafkaEngine`.
- **How exactly**: `KafkaProducer(bootstrap_servers=<mapped address>, acks="all", retries=3,
  json/str serializers)`; `send` + `future.get(timeout=10)`; `flush(timeout=30)` as the batch
  boundary; `close()` at stop; metadata failures surface on first use — deadlines everywhere.

### `mokapi`
- **What it provides**: the kafka mock contract — spec as the start argument, volume mount,
  health at `/health` (HTTP 8080), kafka listener 9092, restart-wipe semantics.
- **Where used**: `KafkaEngine`.
- **How exactly**: mount the AsyncAPI document at `/data/<name>`, pass as the command argument;
  readiness via the HTTP side; wipe via container restart.

### `vault-dev`
- **What it provides**: the vault dev-mode contract — env flags, fixed root token, KV v2 paths,
  health endpoint, restart-wipe semantics.
- **Where used**: `VaultEngine`.
- **How exactly**: `server -dev` + `VAULT_DEV_ROOT_TOKEN_ID`/`VAULT_DEV_LISTEN_ADDRESS` env;
  `X-Vault-Token` header; `POST /v1/secret/data/<path>` body `{"data": …}`; readiness
  `GET /v1/sys/health`.

### `wiremock`
- **What it provides**: the http mock contract — `POST /__admin/mappings`, mapping passthrough,
  `POST /__admin/mappings/reset`, readiness on the admin endpoint, near-miss visibility.
- **Where used**: `HttpEngine`.
- **How exactly**: mappings POSTed as given (priority/delays/faults pass through); reset =
  `mappings/reset` + replay; readiness `GET /__admin/health`.

### `requests`
- **What it provides**: the HTTP client for vault/wiremock data planes and health probes.
- **Where used**: `VaultEngine`, `HttpEngine`, `ServiceContainer` (health path).
- **How exactly**: `requests.post/get(url, headers=…, json=…, timeout=5)`; probe loops with
  deadlines for readiness.

### `jinja2`
- **What it provides**: the rendering engine for the service env placeholders (and, in the
  plugin, `base_url` — untouched).
- **Where used**: `render_service_env` (sandbox cell).
- **How exactly**: `Environment(undefined=StrictUndefined)`; context
  `{instance: {"host", "port"}}`; per-value render; failures name the env key.

### `pluginator`
- **What it provides**: the plugin framework — `install_pytest_plugins`, `call_context`,
  fixtures as plugin methods, the `configure()` lifecycle.
- **Where used**: plugin cell (install/fixture/configure) and sandbox cell (the hook
  registration follows the same namespace-injection pattern).
- **How exactly**: hooks land in the conftest namespace dict; `configure()` is a plain method
  called at configphase; the `api` fixture remains a plugin-class method.

### Imported Usages
- `sandbox-file` from `goga_tool_pybuggy/sandbox/config` — the `.sandbox.yml` authoring
  semantics (layout, placeholder syntax, section order, constraints); consumed by the sandbox
  cell annotations (`Sandbox`, `render_service_env`, `activate_sandbox`).
  Path: `goga_tool_pybuggy/sandbox/config/.usages/sandbox-file.md`.
- `data-operations` from `goga_tool_pybuggy/sandbox/data` — the laziness contract and the
  declaration shapes; consumed by `Sandbox.apply_pending` and re-exported to consumers via the
  root. Path: `goga_tool_pybuggy/sandbox/data/.usages/data-operations.md`.
- `sandbox-session` from `goga_tool_pybuggy/sandbox` — the consumer fixture patterns
  (activation, session fixture + baseline, autouse reset, api usage); consumed by the plugin and
  root annotations. Path: `goga_tool_pybuggy/sandbox/.usages/sandbox-session.md`.

## `.usages/` Update

### Cell: `goga_tool_pybuggy/sandbox`
- **`sandbox-session.md`** → current. The activation, baseline (`with sbx.baseline():`), reset,
  and api-substitution descriptions match the manifests (and this design). No additions needed.

### Cell: `goga_tool_pybuggy/sandbox/config`
- **`sandbox-file.md`** → current; with the applied manifest fix, the "unknown name fails
  validation" promise now holds at load time (the doc's "before any container starts" is
  satisfied). Review update: added the postgres idempotent-startup-SQL constraint line to the
  Startup data layer section (reset replays startup SQL over a TRUNCATE that keeps tables).

### Cell: `goga_tool_pybuggy/sandbox/engines`
- No `.usages/` directory (by plan). Nothing to create — the engines are consumed through the
  sandbox cell, not directly.

### Cell: `goga_tool_pybuggy/sandbox/data`
- **`data-operations.md`** → current. View/preset declaration shapes match the payload table.
  No changes.

### Cells: `goga_tool_pybuggy/plugin`, `goga_tool_pybuggy/commands/init`, root
- **`enable.md`** (Sandbox activation section), **`init.md`** (artifact-table row), **`assembly.md`**
  (facade note) → all current, updated by the apply-architecture stage; verified against the
  manifests during this design. No further updates.

## Test Stack Trace

### General Setup

- New test packages mirror the source: `tests/sandbox/`, `tests/sandbox/config/`,
  `tests/sandbox/engines/`, `tests/sandbox/data/` — each with `__init__.py`; shared fixtures in
  `tests/sandbox/conftest.py`.
- `tests/sandbox/conftest.py`:
  - `docker_available()` — session-scoped probe (`docker.from_env().ping()`); exposes the skip
    condition `requires_docker = pytest.mark.skipif(not docker_available(), reason="docker-
    compatible container runtime unavailable")` for engine/service integration tests.
  - `sandbox_yaml(tmp_path, monkeypatch, content)` — writes `.sandbox.yml` into `tmp_path`,
    `monkeypatch.chdir(tmp_path)`, returns the path (the canonical loader fixture).
  - `FakeEngine` / `FakeService` — recording stubs for `Sandbox` unit tests (apply/record/reset
    calls, alive/logs).
- Existing plugin/init tests extend in place (`tests/plugin/test_plugin.py`,
  `tests/commands/init/test_init.py` / `test_bootstrap.py`).
- No network in unit tests; container tests are docker-gated.

### Source File Registry

```
goga_tool_pybuggy/sandbox/config/{__init__,sandbox_config,service,instance,startup_data,loader}.py
goga_tool_pybuggy/sandbox/engines/{__init__,operation,address,runtime,base,postgres,kafka,vault,http}.py
goga_tool_pybuggy/sandbox/data/{__init__,batch,postgres,kafka,vault,http,presets}.py
goga_tool_pybuggy/sandbox/{__init__,sandbox,baseline,service_container,env_render,activation}.py
goga_tool_pybuggy/plugin/{__init__,plugin}.py            (modified)
goga_tool_pybuggy/commands/init/init.py                  (modified)
goga_tool_pybuggy/__init__.py                            (modified)
pyproject.toml                                           (dependencies)
```

---

### Positive Tests

#### `test_load_returns_validated_model_for_full_document`

**Setup**: `sandbox_yaml` with the `sandbox-file.md` example document (service image
`my-service:latest`, port 8080, health `/health`, env with three placeholders; instances db/
events/secrets/payments; all four data sections).

**Input**: `load_sandbox_config(None)`.

**Trace**:
```
load_sandbox_config(None)
  → resolve .sandbox.yml in CWD (tmp_path)           # document found
  → ruamel parse                                      # mapping
  → validate service/instances/data/placeholders     # all pass
  → SandboxConfig(service=ServiceConfig(image="my-service:latest", env={…}, port=8080,
                  health="/health"), instances={db: InstanceConfig(kind="postgresql", …), …},
                  data=StartupData(vault={secrets:[…]}, http={payments:[…]},
                                   kafka={events:"asyncapi.yaml"}, postgres={db:[…]}))
```

**Assertions**:
```
config is not None
config.service.image == "my-service:latest"; config.service.port == 8080
config.service.health == "/health"
set(config.instances) == {"db", "events", "secrets", "payments"}
config.instances["db"].kind == "postgresql"; config.instances["events"].image is None
config.data.kafka == {"events": str(tmp_path / "asyncapi.yaml")}   # resolved at load (D1 fix)
len(config.data.postgres["db"]) == 1
```

**Sufficiency**: pins the full happy-path parse — the schema every other behavior builds on.

---

#### `test_load_returns_none_without_document`

**Setup**: `tmp_path` via `monkeypatch.chdir`, no `.sandbox.yml`.

**Input**: `load_sandbox_config(None)`.

**Trace**: `resolve → absent → return None` (no exception, no file reads beyond the location).

**Assertions**: `config is None`.

**Sufficiency**: the inertness gate — presence-based activation depends on it.

---

#### `test_render_service_env_resolves_placeholders`

**Setup**: addresses `{"db": InstanceAddress(host="127.0.0.2", port=5432)}`.

**Input**: `render_service_env({"DATABASE_URL": "postgres://{{db.host}}:{{db.port}}/test",
"PLAIN": "no-placeholders"}, addresses)`.

**Trace**:
```
context = {"db": {"host": "127.0.0.2", "port": 5432}}
render "postgres://{{db.host}}:{{db.port}}/test" → "postgres://127.0.0.2:5432/test"
render "no-placeholders" → itself
```

**Assertions**:
```
rendered["DATABASE_URL"] == "postgres://127.0.0.2:5432/test"
rendered["PLAIN"] == "no-placeholders"
```

**Sufficiency**: the wiring mechanism of the whole capability — placeholder → mapped address.

---

#### `test_baseline_boundary_applies_immediately_and_journals`

**Setup**: `Sandbox` with `FakeEngine` (records `apply`/`record` lists); `sandbox.postgresql("db")`
view obtained inside the boundary.

**Input**: `with sandbox.baseline(): sandbox.postgresql("db").insert("customers",
rows=[{"id": 1}])`.

**Trace**:
```
baseline() → BaselineBoundary(sandbox) → __enter__ → open() → routing = BoundaryBatch
postgresql("db") → PostgresInstance(batch=BoundaryBatch)
insert(...) → batch.add(op) → engine.apply([op]); engine.record([op])   # immediate
__exit__ → close() → routing back to lazy
```

**Assertions**:
```
engine.applied == [op]; engine.journal == [op]     # applied AND journaled at declaration time
sandbox batch untouched (take() == [])
```

**Sufficiency**: the boundary semantics — immediate apply + journaling — the reset baseline
depends on.

---

#### `test_apply_pending_groups_by_instance_preserving_order`

**Setup**: `Sandbox` with two `FakeEngine`s ("db", "payments"); batch preloaded via views:
db-insert A, payments-stub B, db-insert C.

**Input**: `sandbox.apply_pending()`.

**Trace**:
```
ops = batch.take()                      # [A(db), B(payments), C(db)] — batch now empty
group: db → [A, C]; payments → [B]      # first-appearance order, per-instance order kept
engines["db"].apply([A, C]); engines["payments"].apply([B])
```

**Assertions**:
```
engines["db"].applied == [A, C]; engines["payments"].applied == [B]
batch.take() == []                      # drained
```

**Sufficiency**: the lazy-contract application point — grouping and ordering guarantee
"presets precede in-test operations" and foreign-key order.

---

#### `test_presets_decorator_marks_test_and_executes_nothing`

**Setup**: plain module namespace; `DataBatch` spy via `FakeEngine` sandbox not involved.

**Input**: `@services(postgresql={"db": [{"table": "customers", "rows": [{"id": 1}]}]})` over a
sample test function.

**Trace**:
```
services(**presets) → kind check passes → decorator
decorator(fn) → fn.pybuggy_services marker applied (presets payload); no I/O, no batch touched
```

**Assertions**:
```
marker = next(iter(getattr(fn, "pytestmark", [])).…) # the pybuggy_services marker exists
marker.kwargs["presets"]["postgresql"]["db"][0]["table"] == "customers"
```

**Sufficiency**: decoration is declarative only — laziness starts here.

---

#### `test_configure_renders_base_url_unchanged_without_sandbox`

**Setup**: `plugin = ApiPlugin(context={})` (the constructor initializes `sandbox_activation
= None` — it is not a constructor parameter); fake pytest config with
`invocation_params.args = []`; plugin config `base_url: "http://{{ENV_X}}/api"`; env `ENV_X=x`.

**Input**: `plugin.configure()`.

**Trace**: typed-CLI collection → no `--base-url` → no fail-fast → context = environ + typed
options → `render_base_url` → `http://x/api`.

**Assertions**: `plugin.base_url == "http://x/api"`.

**Sufficiency**: proves the sandbox integration changed nothing for unarmed suites.

---

#### `test_install_arms_sandbox_and_keeps_activation_on_plugin`

**Setup**: `monkeypatch.setattr` on the plugin module: `activate_sandbox = fake` (returns a sentinel
config, records the context); fake `install_pytest_plugins` (records plugin); empty context dict.

**Input**: `plugin.install()` (in a dummy module namespace via `call_context` monkeypatching —
following the existing install tests' pattern).

**Trace**:
```
install() → context defaulted → fake activate_sandbox(context) → sentinel
ApiPlugin(**kwargs) → plugin.sandbox_activation = sentinel → install_pytest_plugins(plugin, context)
```

**Assertions**:
```
fake called once with the same context object
plugin.sandbox_activation is sentinel
```

**Sufficiency**: the arming seam — same call enables plugin + sandbox; the configure check has
its input.

---

#### `test_api_fixture_substitutes_base_url_and_guards_first_request`

**Setup**: `monkeypatch.setattr(plugin_module, "active_sandbox", lambda: fake_sandbox)` where
`fake_sandbox.base_url = "http://10.0.0.1:9000"`, recording `apply_pending`/`ensure_service`;
plugin options `base_url="http://rendered/api"`.

**Input**: `next(plugin.api().__iter__())` — then call `api.request("GET", "/x")` with the
underlying `Api.request` stubbed (monkeypatch on the instance after construction is the code
under test — instead monkeypatch `Api.__init__`/request via a fake Api class or patch
`plugin_module.Api`).

**Trace**:
```
api fixture → active_sandbox() → fake → base_url = "http://10.0.0.1:9000"
Api constructed with that base_url → api.request wrapped by _sandbox_guard
api.request("GET", "/x") → guard → fake.apply_pending(); fake.ensure_service() → original
```

**Assertions**:
```
api.base_url == "http://10.0.0.1:9000"          # sandbox wins over the rendered option
fake.applied_pending == 1; fake.ensured == 1    # guard ran before the request
plugin.base_url option unchanged ("http://rendered/api")
```

**Sufficiency**: the consumer-facing integration — address substitution + the automatic apply
point, tests unaware.

---

#### `test_bootstrap_copies_and_registers_sandbox_usages`

**Setup**: existing bootstrap test harness (tmp CWD, fake `.goga` config writer); the real
installed-from-source package (importlib.resources resolves the repo tree).

**Input**: `run_bootstrap(template_mode=True)`.

**Trace**:
```
roots = [api package, sandbox package] → _walk collects api.md, asserts.md (pre-existing,
rides the api-package root), sandbox-session.md, sandbox-file.md, data-operations.md
→ copies to .goga/usages/cooks/pybuggy/<stem>.md
→ register_usages adds pybuggy-sandbox-session/-sandbox-file/-data-operations
→ register_annotations appends the hand-authored lines
```

**Assertions**:
```
all five files exist under tmp .goga/usages/cooks/pybuggy/   # incl. asserts.md — as today
usage keys pybuggy-sandbox-session, pybuggy-sandbox-file, pybuggy-data-operations registered
annotation lines present for each key
plugin/.usages and commands usages NOT copied        # scope constraint
```

**Sufficiency**: the documented distribution path — capability docs land in consumer projects.

---

#### `test_facade_exports_capability_surface`

**Setup**: none (import test).

**Input**: `from goga_tool_pybuggy import active_sandbox, services`.

**Trace**: root `__init__` → `.sandbox` facade → `activation.active_sandbox`; `.sandbox.data`
facade → `presets.services`.

**Assertions**:
```
callable(active_sandbox); callable(services)
"active_sandbox" and "services" in goga_tool_pybuggy.__all__
```

**Sufficiency**: the documented consumer import line — the embeddings made real.

---

#### `test_postgres_engine_roundtrip_start_apply_reset` (docker-gated)

**Setup**: `requires_docker`; `InstanceConfig(name="db", kind="postgresql", image=None)`; startup
ops `[DataOperation("db","postgresql","insert",{"sql": "CREATE TABLE orders (id int PRIMARY
KEY, n int)"})]`; baseline op recorded via `record([DataOperation(…, "insert", {"table":
"orders", "rows": [{"id": 1, "n": 5}]})])`.

**Input**: `engine.start(startup)`; `engine.apply([insert id=2])`; `engine.reset()`; then a
select through the engine connection helper (dev-only accessor) or a second apply + unique-
violation probe.

**Trace**:
```
start: PostgresContainer("postgres:16-alpine") → ready → psycopg connect (test/test/test)
       → execute CREATE TABLE → journal=[sql op]
apply: executemany INSERT (id=2)
reset: catalog discovers orders → TRUNCATE orders RESTART IDENTITY CASCADE
       → replay journal: CREATE TABLE (IF NOT EXISTS semantics by author's SQL) + INSERT id=1
```

**Assertions**:
```
after apply: table exists (no error)
after reset: querying id=2 finds nothing; id=1 (baseline) present — e.g. apply a duplicate
id=1 → UniqueViolation proves the baseline row exists and test rows are gone
```

**Sufficiency**: the whole postgres engine contract — readiness, both payload forms, wipe,
journal replay.

---

#### `test_vault_engine_put_and_restart_reset` / `test_http_engine_stub_and_admin_reset` /
`test_kafka_engine_spec_mount_and_restart_reset` (docker-gated)

**Setup** (vault): engine started empty; baseline `put("payment/api-key", {"api_key": "k"})`
recorded; a test `put("x/y", {"v": 1})` applied.
**Input**: `engine.reset()`.
**Trace**: restart same container → health re-wait → replay baseline put.
**Assertions**: `GET /v1/secret/data/x/y` → 404 (test write gone); `GET …/payment/api-key` →
200 with the baseline value; `engine.address` unchanged before/after reset.
**Sufficiency**: restart-wipe + replay + the address-stability guarantee the service env
depends on.

(http/kafka follow the same shape: stubs visible via `GET /__admin/mappings` then gone after
`mappings/reset` + only baseline mappings replayed; kafka spec op produces the configured
topics — a produce to a spec topic succeeds after restart.)

---

#### `test_service_container_readiness_and_liveness` (docker-gated; review addition)

**Setup**: `requires_docker`; `ServiceConfig(image="wiremock/wiremock:3.13.0", port=8080,
health=None, env={})` — the already-pinned image, no extra image needed; variant B runs the
same shape with `health="/__admin/health"`.

**Input**: `sc = ServiceContainer(cfg); sc.start(env={"K": "v"})`.

**Trace**:
```
DockerContainer(image) + with_exposed_ports(8080) + env + labels → start
→ readiness: variant A port probe loop (TCP, deadline 30s/0.5s) / variant B GET health until 2xx
→ host/port read back from the container engine (mapped values)
```

**Assertions**:
```
int(sc.port) > 0 and sc.host resolvable
requests.get(f"http://{sc.host}:{sc.port}/__admin/health", timeout=5).status_code == 200
sc.alive() is True; isinstance(sc.logs(), str)
sc.stop(); second sc.stop() does not raise; sc.alive() is False after stop
```

**Sufficiency**: the only real-container coverage of the service readiness loop (both branches:
port probe and health path), the mapped address that `base_url` is built from, and the
liveness/logs pair the died-service indication reads — the foundations of `Sandbox.base_url`
and `ensure_service`.

---

### Negative Tests

#### `test_load_fails_grpc_kind_with_not_supported_yet`

**Setup**: `sandbox_yaml` with `instances: {events: {kind: grpc}}` and a minimal valid service.

**Input**: `load_sandbox_config(None)`.

**Trace**: instance validation → kind `grpc` → explicit "not supported yet" error.

**Assertions**: `pytest.raises(ValueError, match="grpc.*not supported yet")`.

**Sufficiency**: the ADR-mandated explicit rejection (acceptance criterion).

---

#### `test_load_fails_unknown_env_placeholder_before_start` (the applied fix)

**Setup**: `sandbox_yaml` — service env `DATABASE_URL: "postgres://{{ghost.host}}:5432/x"`,
instances without `ghost`.

**Input**: `load_sandbox_config(None)`.

**Trace**: service/instances/data pass → placeholder scan finds `ghost` ∉ instances →
`ValueError` naming the env key and location — no container was ever touched (pure loader
call; no docker needed).

**Assertions**: `pytest.raises(ValueError, match="DATABASE_URL.*ghost")`.

**Sufficiency**: regression for the fixed defect — guarantees the pre-start failure promise.

---

#### `test_load_fails_bare_instance_placeholder` (review fix — full grammar)

**Setup**: `sandbox_yaml` — service env `KAFKA_BOOTSTRAP: "{{events}}"`, instance `events`
configured.

**Input**: `load_sandbox_config(None)`.

**Trace**: service/instances/data pass → grammar check: `{{events}}` carries no `.host`/`.port`
attribute → `ValueError` naming the env key, the value, and the location — at load, before any
container (the bare form would otherwise render a dict repr silently).

**Assertions**: `pytest.raises(ValueError, match="KAFKA_BOOTSTRAP.*events")`.

**Sufficiency**: pins the grammar edge — without the check the env value silently receives a
dict repr instead of an address.

---

#### `test_load_fails_unknown_placeholder_attribute` (review fix — full grammar)

**Setup**: `sandbox_yaml` — service env `DATABASE_URL: "postgres://{{db.hst}}:5432/x"`,
instance `db` configured.

**Input**: `load_sandbox_config(None)`.

**Trace**: service/instances/data pass → grammar check: attribute `hst` ∉ {host, port} →
`ValueError` naming the env key, the value, and the location — at load; previously this class
failed only at render time, after the mock containers had started.

**Assertions**: `pytest.raises(ValueError, match="DATABASE_URL.*hst")`.

**Sufficiency**: closes the last placeholder class that violated "invalid file fails before any
container starts".

---

#### `test_load_fails_data_targeting_unknown_instance`

**Setup**: `data.postgres: {"nodb": ["SELECT 1"]}` with no `nodb` instance.

**Input**: `load_sandbox_config(None)`.

**Assertions**: `pytest.raises(ValueError, match="nodb")`.

**Sufficiency**: target validation — misdirected startup data would otherwise fail at apply
time, after containers start.

---

#### `test_load_fails_missing_required_service_field` / `test_load_fails_unparsable_yaml`

**Setup**: (a) service without `port`; (b) content `":\n - ["`.

**Input**: `load_sandbox_config(None)`.

**Assertions**: (a) `ValueError` naming `port`; (b) `ValueError` naming the location and the
parse problem.

**Sufficiency**: required-field and parse failures are the remaining "invalid file" classes of
the acceptance criterion.

---

#### `test_load_fails_empty_document` (review addition)

**Setup**: `sandbox_yaml` writing an empty file (zero bytes).

**Input**: `load_sandbox_config(None)`.

**Trace**: document exists → ruamel parse of the empty content → `None` → not a mapping →
treated as an invalid document (a sandbox document must carry the service entry) → `ValueError`
naming the location.

**Assertions**: `pytest.raises(ValueError, match=".sandbox.yml")`.

**Sufficiency**: the empty-file edge the design names but did not test — parse-None must fail
actionably, not slip through as an absent document.

---

#### `test_configure_fails_fast_on_cli_base_url_with_armed_sandbox`

**Setup**: `plugin = ApiPlugin(context={})` then `plugin.sandbox_activation =
SandboxConfig-stub` (assigned post-construction — the `install()` pattern; the constructor
takes no such kwarg); fake pytest config
with `invocation_params.args = ["--base-url", "http://x"]` and resolved option `base_url`.

**Input**: `plugin.configure()`.

**Trace**: typed-CLI collection finds `base_url` → stored → `sandbox_activation` armed → raise.

**Assertions**: `pytest.raises(pytest.UsageError, match="--base-url.*sandbox")` — message names
both facts.

**Sufficiency**: the conflict guard — an explicit URL with a sandbox-owned address must abort
before any test or container.

---

#### `test_services_rejects_unknown_kind_at_decoration`

**Setup**: none.

**Input**: `@services(redis={"x": []})`.

**Assertions**: `pytest.raises(ValueError, match="redis")` raised at decoration (import time of
the test module).

**Sufficiency**: static kind validation — typos surface immediately at the decorator.

---

#### `test_preset_enqueue_fails_unknown_instance_listing_configured`

**Setup**: `Sandbox` with `FakeEngine("db")` only; an item stub carrying the marker
`pybuggy_services(presets={"postgresql": {"ghost": [{"table": "t", "rows": []}]}})`.

**Input**: the registered `pytest_runtest_setup` body (invoked directly with the item stub).

**Trace**: fresh batch → marker read → resolve engine "ghost" → missing → error listing
configured instances.

**Assertions**: `pytest.raises(ValueError, match="ghost.*db")`.

**Sufficiency**: enqueue-time validation (decision 3A) — unknown names fail before the test
body with the configured set listed.

---

#### `test_sandbox_view_kind_mismatch_lists_configured`

**Setup**: `Sandbox` with a `FakeEngine("db", kind="postgresql")`.

**Input**: `sandbox.kafka("db")`.

**Assertions**: `pytest.raises(ValueError, match="kafka.*db")`.

**Sufficiency**: the view factories' fail-fast contract.

---

#### `test_ensure_service_raises_naming_service_and_logs_when_died`

**Setup**: `Sandbox` with `FakeService(alive=False, logs="OOMKilled…")`.

**Input**: `sandbox.ensure_service()`.

**Assertions**: `pytest.raises(RuntimeError, match="died")` and the message contains the image
name and the log tail.

**Sufficiency**: the died-service indication — never a hang or an opaque connection error.

---

#### `test_check_runtime_fails_actionable_without_daemon`

**Setup**: monkeypatch the docker client factory to raise `DockerException`.

**Input**: `check_runtime()`.

**Assertions**: `pytest.raises(RuntimeError, match="docker-compatible container runtime")`.

**Sufficiency**: the actionable runtime-missing error (acceptance criterion).

---

#### `test_build_engine_fails_unmapped_kind`

**Setup**: `InstanceConfig(name="x", kind="grpc", image=None)` (bypassing the loader).

**Input**: `build_engine(config)`.

**Assertions**: `pytest.raises(EngineError, match="postgresql.*kafka.*vault.*http")`.

**Sufficiency**: defense in depth of the factory.

---

### Edge Case Tests

#### `test_batch_take_drains_and_repeat_is_empty`

**Setup**: `DataBatch()` with two ops added.

**Input**: `take()` twice.

**Assertions**: first `take()` returns both in order; second returns `[]`.

**Sufficiency**: one batch per test — draining semantics prevent cross-test leakage.

---

#### `test_activation_inert_without_document`

**Setup**: empty `tmp_path` chdir; fresh context dict.

**Input**: `activate_sandbox(ctx)`.

**Assertions**: returns None; `ctx` has none of the three hook keys; `active_sandbox()` is None.

**Sufficiency**: the acceptance criterion "without `.sandbox.yml` behaves exactly as today".

---

#### `test_activation_registers_hooks_with_document`

**Setup**: minimal valid `.sandbox.yml` in chdir'ed `tmp_path`.

**Input**: `activate_sandbox(ctx)`.

**Trace**: config loaded → three hooks registered (no container started) → config returned.

**Assertions**:
```
ctx has pytest_sessionstart / pytest_sessionfinish / pytest_runtest_setup (callables)
returned value is a SandboxConfig
no docker interaction (the hooks are not invoked)
```

Marker registration (review fix): invoking `ctx["pytest_sessionstart"]` with a stub
`session.config` calls `addinivalue_line("markers", "pybuggy_services: …")` **before** any
`Sandbox` start (monkeypatch `Sandbox` to observe the ordering).

**Sufficiency**: arming registers lifecycle only — containers belong to session start
(constraint "do not start containers here").

---

#### `test_activation_wraps_preexisting_hook` (review addition)

**Setup**: minimal valid `.sandbox.yml` in chdir'ed `tmp_path`; `ctx = {"pytest_sessionstart":
prior}` where `prior` is a recording sentinel callable; `Sandbox` monkeypatched to a recording
stub.

**Input**: `activate_sandbox(ctx)`; then invoke `ctx["pytest_sessionstart"](session_stub)`.

**Trace**: config loaded → the namespace already defines `pytest_sessionstart` → the sandbox
wraps it (prior first, sandbox second) instead of clobbering → invocation calls `prior`, then
the marker registration + `Sandbox` construction/start.

**Assertions**:
```
call order == ["prior", "sandbox"] (recorded sequence)
the original sentinel was called exactly once
Sandbox stub constructed exactly once (with the loaded config)
```

**Sufficiency**: the wrap-if-collision decision — a conftest defining its own
`pytest_sessionstart` keeps working, order guaranteed.

---

#### `test_sessionstart_failure_stops_everything_and_reraises`

**Setup**: `Sandbox` with one `FakeEngine` whose `start` raises; service `FakeService` recording
stop; simulate the sessionstart hook body (build + start).

**Input**: invoke the hook logic; expect the exception.

**Assertions**: exception propagates; every started engine and the service got `stop()`.

**Sufficiency**: "a failed start surfaces an actionable error and leaves nothing behind".

---

#### `test_reset_with_empty_journal_is_wipe_only`

**Setup**: docker-gated postgres engine started with no startup ops and nothing recorded; apply
one insert.

**Input**: `engine.reset()`.

**Assertions**: table empty after reset (wipe ran; replay of an empty journal added nothing).

**Sufficiency**: boundary of the replay step — no baseline declared still yields a clean state.

---

#### `test_bootstrap_template_mode_skips_existing_targets`

**Setup**: pre-create `.goga/usages/cooks/pybuggy/sandbox-session.md` with sentinel content;
run bootstrap twice in template mode.

**Assertions**: sentinel content intact; INFO logged; bare mode overwrites (counter-test with
`template_mode=False`).

**Sufficiency**: idempotence + the mode-dependent gate (unchanged behavior extended to the new
stems).

---

## Additional Instructions for the Implementation Agent

- **Dependencies** (`pyproject.toml`, main `[project.dependencies]`, minimum versions per
  conventions): add `testcontainers[postgres]>=4.0`, `psycopg[binary]>=3.1`,
  `kafka-python>=2.2`, `requests>=2.31`. No test-extra additions; docker-gated tests use
  `skipif`.
- **Packaging**: `[tool.setuptools.package-data]` currently lists `skills/**/*`,
  `pipelines/*.yml`, `assets/**/*` — the `.usages/*.md` files (api + the three sandbox cells)
  that `run_bootstrap` reads via `importlib.resources` are NOT covered. Add
  `".usages/*.md"` and `"**/.usages/*.md"` patterns and verify the built wheel carries them
  (build the wheel and list its contents; CODEMANIFEST stays excluded via MANIFEST.in).
- **Pinned defaults**: postgres `postgres:16-alpine`; kafka `mokapi/mokapi:0.28.0` (HTTP 8080 +
  kafka 9092); vault `hashicorp/vault:1.17` (port 8200, dev token constant `"sandbox-root"`,
  never logged); http `wiremock/wiremock:3.13.0` (port 8080). The instance `image` override
  replaces the pinned default verbatim. Labels on every container:
  `{"pybuggy-sandbox": "true"}`.
- **Restart resets** (decision 4A): kafka/vault `reset()` docker-restarts the SAME container via
  the docker SDK container object under the testcontainers wrapper (bindings preserved),
  re-waits readiness, rebuilds the data-plane client, then replays the journal. Never
  remove+recreate.
- **Postgres payload discrimination** (decision 2A): action `insert`; payload key `sql` →
  execute the statement as given; keys `table`+`rows` → parameterized insert (identifiers
  double-quoted, values bound).
- **Idempotent startup SQL**: postgres init statements replay on every per-test reset (journal
  replay over a TRUNCATE wipe that keeps tables) — write them idempotent (CREATE TABLE IF NOT
  EXISTS, INSERT ... ON CONFLICT, ...); documented in `sandbox-file.md`.
- **Preset marker**: `pytest.mark.pybuggy_services(presets={...})`; kinds validated at
  decoration, instance names at enqueue (decision 3A).
- **Python 3.10+**: pydantic kw_only models everywhere; relative intra-package imports; Google
  docstrings; structured logging with `extra`; `pytest.UsageError` for the configphase
  fail-fast; internal errors `EngineError(RuntimeError)` / `ValueError` / `RuntimeError` as
  mapped in § Cross-cutting Concerns.
- **Untouched contracts**: the configure-phase Jinja2 `base_url` rendering, the option
  resolution chain, and `render_base_url` are unchanged — the substitution seam is read-time
  only. The consumer `sandbox` session fixture and the autouse reset fixture remain documented
  conftest patterns (the product registers hooks, not fixtures).
- The single CODEMANIFEST edit of this design (the `load_sandbox_config` placeholder step) is
  already applied and lint-clean; make no further manifest changes without a new design pass.
