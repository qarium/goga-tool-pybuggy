# Plan: `feature-upd-sandbox` — document relocation, inline kafka topics, configurable readiness, naming swap

Topic directory: `.goga/history/2026/feature-upd-sandbox/`. Compiled from the reviewed design
document `design.md` (post design-review, 6 fixes applied) and the CODEMANIFEST tree of branch
`feature/upd-sandbox` (working tree — the manifests are the contract; the implementation at HEAD
`2906069` is the pre-change state). Executed by ralphex through Claude Code, one task per
iteration.

## Purpose

Rework the existing sandbox capability in place. After implementation the package provides:

- the sandbox document relocated to `.goga/tools/pybuggy/sandbox.yml` (cwd-only resolution, no
  upward search; a stale root `.sandbox.yml` is never read), with top-level key diagnostics
  (`service` → `instance`, `instances` → `services`, unknown keys listed);
- inline kafka topics: `TopicConfig` declarations on the kafka service entry; the AsyncAPI
  document is generated in memory (AsyncAPI 2.6.0, no message schemas) and travels into the
  container through the docker API — the startup `spec` action and `data.kafka` section are gone;
- configurable readiness: `ProbeConfig` (timeout 30.0 / interval 0.5 defaults, optional
  health path on the instance entry only); every readiness loop — engines and the instance
  container — runs bounded by the declared values and fails with `EngineError` naming the
  target, the waited check, and the expired deadline;
- the vocabulary swap: `instance` names the entry under test, `service` names a dependency —
  models, engines, session runtime, logs, docstrings, tests, docs, and cooks;
- the public Python API surface is unchanged: same class names, same view factories, same
  `active_sandbox` / `services` re-exports.

The most important gaps between contract and code: `probe.py` / `topic.py` do not exist;
`InstanceConfig` / `ServiceConfig` carry the old (swapped) subjects; the loader resolves the
root `.sandbox.yml` with the old validation algorithm; three engines hand-roll readiness loops
with module constants and `RuntimeError` expiry; `KafkaEngine` consumes startup spec paths;
`Sandbox` / `ServiceContainer` wire the old field names; docs, cooks, and plugin texts name the
former path.

Overall implementation strategy: leaf-first cell order (config → engines → data → sandbox →
plugin/init → docs/cooks → integration → validation), strict TDD per entity (contract tests
first), REPL-driven development loop (Mandatory Rules R4), ruff lint/format gates at every
development stage and before every local commit (Mandatory Rules R3). The design is a
coordinated vocabulary swap across four cells — see the Migration Ledger for how the full-suite
green gate is sequenced.

## Context

### Contract Surface

#### Cell `goga_tool_pybuggy/sandbox/config` (leaf; practices `conventions`, `ruamel-yaml`)

**Entity: `SandboxConfig(instance: InstanceConfig, services: dict[str, ServiceConfig], data: StartupData)`**
- Type: class; Declared `location`: `sandbox_config.py`
- Facade obligation: importable from `goga_tool_pybuggy.sandbox.config`
- Properties: `instance -> InstanceConfig` (the instance-under-test entry), `services ->
  dict[str, ServiceConfig]` (dependency service entries keyed by name; several services of one
  kind allowed), `data -> StartupData` (the startup data layer declarations)
- Semantic requirements: pydantic model, `kw_only`; the data sections default empty; the
  instance entry is required.

**Entity: `InstanceConfig(image: str, env: dict[str, str], port: int, probe: ProbeConfig | None)`**
- Type: class; `location: instance.py`; facade: cell facade
- Properties: `image -> str` (container image of the instance under test), `env -> dict[str, str]`
  (values may carry service address placeholders resolved at sandbox start), `port -> int` (the
  container port the service serves on), `probe -> ProbeConfig | None` (readiness declaration —
  health path and wait bounds; None keeps the default wait: port readiness with the default
  deadline and interval)
- Requirements: pydantic model, `kw_only`. Constraint: the probe path applies only here — the
  single readiness check with a configurable path.

**Entity: `ServiceConfig(name: str, kind: str, image: str | None, topics: list[TopicConfig], probe: ProbeConfig | None)`**
- Type: class; `location: service.py`; facade: cell facade
- Properties: `name -> str` (the key tests address the service by and the placeholder name used
  inside the instance env values), `kind -> str` (postgresql, kafka, vault, or http), `image ->
  str | None` (override; None keeps the product-pinned default of the kind), `topics ->
  list[TopicConfig]` (kafka topic declarations — required and non-empty for the kafka kind,
  rejected for every other kind), `probe -> ProbeConfig | None` (wait bounds for this service's
  readiness check)
- Requirements: pydantic model, `kw_only`; a kafka entry without topics is invalid — the mock
  would open no listener. Constraints: no kind outside the four supported ones; no probe path
  here — the path belongs to the instance-under-test entry only.

**Entity: `StartupData(vault: dict[str, list[dict[str, object]]], http: dict[str, list[dict[str, object]]], postgres: dict[str, list[str]])`**
- Type: class; `location: startup_data.py`; facade: cell facade
- Properties: `vault` (service name → secret declarations (path, data)), `http` (service name →
  stub mapping declarations (request, response)), `postgres` (service name → init SQL statements;
  each statement converts to one startup insert operation whose payload carries the `sql` key,
  executed as given)
- Requirements: sections default empty; declarations target services by name; within a section
  the declaration order is the application order. Constraints: do not reorder declarations; no
  kafka section — the kafka topology is declared inline on the service entry. Field order is
  vault → http → postgres (the application order at start).

**Entity: `ProbeConfig(timeout: float = 30.0, interval: float = 0.5, path: str | None = None)`** (new)
- Type: class; `location: probe.py` (new file); facade: cell facade (new facade name)
- Properties: `timeout -> float` (the readiness deadline in seconds; an expired deadline fails
  with an actionable error), `interval -> float` (the seconds between readiness attempts), `path
  -> str | None` (the health-check path — accepted only on the instance-under-test entry)
- Requirements: pydantic model, `kw_only`; the defaults reproduce the established wait exactly:
  timeout 30.0, interval 0.5; both bounds are positive; the interval never exceeds the timeout.

**Entity: `TopicConfig(name: str, partitions: int = 1)`** (new)
- Type: class; `location: topic.py` (new file); facade: cell facade (new facade name)
- Properties: `name -> str` (the topic name the mock opens and tests produce into), `partitions
  -> int` (the topic partition count; 1 when omitted)
- Requirements: pydantic model, `kw_only`; a non-empty topic name; `partitions` is a positive
  integer.

**Routine: `load_sandbox_config(path: str | None) -> config: SandboxConfig | None`**
- `location: loader.py`; facade: cell facade
- Reads and validates `.goga/tools/pybuggy/sandbox.yml` under the pybuggy tools home of the
  consumer service test repository. `path`: explicit document location; None resolves
  `.goga/tools/pybuggy/sandbox.yml` in the current working directory. Returns the validated
  model; None when the document is absent — the sandbox stays fully inert.
- Algorithm (verbatim from the contract):
  1. Resolve the document location — the current working directory only, no upward search; an
     absent document returns None.
  2. Parse the document; an unparsable document fails with an error naming the location and the
     parse problem.
  3. Apply the top-level key diagnostics — a "service" key fails naming the rename to
     "instance"; an "instances" key fails naming the rename to "services"; any other unknown
     top-level key fails as unknown.
  4. Validate the instance entry — image, env, port are required; the probe is optional with
     the path confined to this entry.
  5. Validate every service entry — a non-empty unique name matching the template identifier
     grammar — letters, digits, underscores, not starting with a digit (it names the
     `{{<name>.host}}` / `{{<name>.port}}` placeholders); a kind of postgresql, kafka, vault, or
     http; the grpc kind fails with an explicit "not supported yet" error; an optional image
     override; kafka entries declare a non-empty topics list; non-kafka entries declare none;
     the probe carries no path.
  6. Validate the startup data sections — every declaration targets an existing service of the
     matching kind; a kafka section fails as removed — the topology is declared inline on the
     service entry.
  7. Validate the instance env values — every service placeholder name references a configured
     service.
  8. Return the model.
- Requirements: validation completes fully before anything is started — no container is created
  for an invalid document; instance env placeholder names resolve against the configured
  services; the probe bounds are validated; every failure message names the document location
  and the offending entry. Constraints: do not default or repair invalid entries — fail fast;
  do not read anything beyond the named document.
- Imported dependencies: `ruamel-yaml` practice for document parsing.

#### Cell `goga_tool_pybuggy/sandbox/engines` (Imports: `ServiceConfig` from `goga_tool_pybuggy/sandbox/config`)

**Entity: `DataOperation(instance: str, kind: str, action: str, payload: dict[str, object]`)** — Type:
class; `location: operation.py`; facade: cell facade. `instance`: the target service name;
`action`: insert, produce, put, or stub (the startup-only `spec` action is gone; the startup-only
postgresql insert carries a raw `sql` payload key). Payloads are plain serializable data;
postgresql rows may carry `$ref` / `$lookup` dicts as top-level values — resolved only at
execution, the payload is never rewritten.

**Entity: `InstanceAddress(host: str, port: int)`** — Type: class; `location: address.py`;
facade: cell facade. The mapped address of one started service; read back from the container
engine after start — a fixed host port is never assumed. Unchanged by this design.

**Routine: `check_runtime()`** — `location: runtime.py`. Pre-start daemon probe; unreachable →
`RuntimeError` naming the requirement. Probe only, start nothing. Unchanged.

**Routine: `build_engine(config: ServiceConfig) -> engine: BaseEngine`** — `location: runtime.py`.
Kind → engine factory (postgresql, kafka, vault, http); an unmapped kind fails with the
supported kinds listed; the image override, the topic declarations, and the readiness
declaration of `config` reach the built engine.

**Entity: `EngineError()`** — `location: base.py`; facade: cell facade. The failure type of
every engine operation — the engine-specific `RuntimeError` subtype. The message names the
service, the failed operation or lifecycle step, and the underlying cause. **An expired
readiness deadline surfaces as this type — the message names the target, the waited check, and
the expired deadline.**

**Entity: `BaseEngine(config: ServiceConfig)`** — Type: class; `location: base.py`; facade: cell
facade. Property `address -> InstanceAddress`. Methods: `start(startup: list[DataOperation],
network: Network | None)` (container + readiness **within the declared deadline at the declared
interval** + data plane + journaled startup; a failed start surfaces an actionable error and
leaves nothing behind), `apply(operations)` (execute in order; never records), `record(operations)`
(journal extend), `reset()` (kind wipe + journal replay through the apply path), `stop()` (remove
container, close plane; safe when stopped). Requirements: readiness completes before start
returns, bounded by the readiness declaration — expiry is an actionable failure, never a hang.
Constraints: engines own dependency services only; no operations before start completes.

**Mutations** (each implements container build / readiness / data plane / wipe for its kind):
- `BaseEngine::PostgresEngine(config: ServiceConfig)` — `postgres.py`. Module container with the
  product-pinned default image; module readiness wrapped in the declared deadline. Data plane:
  SQL over psycopg — insert resolves `$ref` / `$lookup`, applies rows one by one inside one
  transaction with RETURNING into the per-table symbol stream; startup raw sql executes as
  given, opaque. Wipe: catalog-driven TRUNCATE ... RESTART IDENTITY CASCADE at reset time; the
  container is never restarted. Constraint: never format SQL with interpolated values.
- `BaseEngine::KafkaEngine(config: ServiceConfig)` — `kafka.py`. The inline topic declarations
  of `config` are consumed at build — the AsyncAPI document is generated in memory from the
  declared topics, its kafka servers are rewritten to the client-reachable mapped address of a
  reserved fixed port, the patched copy travels into the container through the docker api, and
  its in-container path is passed as the start argument; bootstrap, metadata and the instance
  env name one and the same address; readiness waits for the HTTP health side within the
  declared deadline at the declared interval. **An empty topic declaration is an invalid state —
  the engine fails fast**, the mock would open no kafka listener; document validation rejects it
  first. A produce into a topic not declared on the entry fails with a readable error naming the
  service and its declared topics. Wipe: restart the container — the fixed port binding and the
  generated document survive the restart. Requirements: the generated document stays internal —
  never written to the consumer repository, never exposed to authors.
- `BaseEngine::VaultEngine(config: ServiceConfig)` — `vault.py`. Official vault image in dev
  mode; reserved fixed host port; readiness waits for the health endpoint within the declared
  deadline at the declared interval. KV v2 over HTTP with the token header. Wipe: restart the
  container and replay the baseline. The dev token is a fixed test credential — never logged.
- `BaseEngine::HttpEngine(config: ServiceConfig)` — `http.py`. Http mock image with the admin
  port published; readiness waits for the admin endpoint within the declared deadline at the
  declared interval. Stub mappings over the admin API; unmatched requests get a visible
  near-miss response. Wipe: reset the mappings over the admin API and replay the baseline.

**Routine: `validate_insert_rows(rows: object, context: str)`** — `location: refs.py`;
facade: cell facade. Declaration-time grammar validation of insert rows. Unchanged by this
design.

#### Cell `goga_tool_pybuggy/sandbox/data` (Imports: `DataOperation`, `InstanceAddress`, `validate_insert_rows` from engines)

Unchanged entities: `DataBatch()` (`batch.py`; `add` / `take`), `PostgresInstance(name, address,
batch)` (`postgres.py`; `insert(table, rows)`), `VaultInstance` (`vault.py`; `put(path, data)`),
`HttpInstance` (`http.py`; `stub(mapping)`) — properties `name` / `host` / `port` on all views.

Changed entities:
- **`KafkaInstance(name: str, address: InstanceAddress, batch: DataBatch)`** — `location:
  kafka.py`. Method `produce(topic: str, value: dict[str, object] | str, key: str | None)` — the
  topic **must be declared on the kafka service entry of the sandbox document**.
- **`services(...presets: dict[str, dict[str, list[dict[str, object]]]]) -> decorator: Callable`**
  — `location: presets.py`. `presets`: kind → service name → declaration list. Validation at
  decoration (four supported kinds; `validate_insert_rows` on postgresql rows); names resolve at
  enqueue against the sandbox document. The tightened contract type finally matches the runtime
  nesting. Constraint: nothing executes at decoration time.

#### Cell `goga_tool_pybuggy/sandbox` (Imports: 4 types + `sandbox-file` from config; 6 types from engines; 5 types + `data-operations` from data)

**Entity: `Sandbox(config: SandboxConfig)`** — `location: sandbox.py`; facade: cell facade.
Property `base_url -> str`. Methods: `start()` — Algorithm (verbatim): 1. probe the container
runtime availability via `check_runtime`; 2. create the sandbox network; 3. start every
configured service engine — built with `build_engine` — with its startup data as
`DataOperation` entries taken from the `StartupData` sections **in the fixed order — vault
secrets, http mappings, then postgres init**; 4. render the instance environment values against
the started service addresses; 5. start the instance container and wait for readiness — the
port, or the health path when declared — within the readiness declaration's deadline at its
interval; an expired deadline fails with an actionable error; 6. log the startup progress at
every step, and the resolved service address with its source. `stop()` (everything removed on
every exit path; safe when already stopped), `clear()` (reset every engine; the instance
container keeps running), `baseline() -> boundary: BaselineBoundary`, `apply_pending()` (take
batch, group by service preserving order, apply per engine; runs before the first service call
of a test), `ensure_service()` (died-instance fail-fast naming the service and attaching its
output), `new_test_batch()`, view factories `postgresql/kafka/vault/http(name)` (unknown name or
kind mismatch fails fast listing the configured services).

**Entity: `BaselineBoundary(sandbox: Sandbox)`** — `location: baseline.py`. `open()` / `close()`;
immediate apply + journal inside the boundary; journals freeze on close. Unchanged by this
design (vocabulary only).

**Entity: `ServiceContainer(config: InstanceConfig)`** — `location: service_container.py`.
Properties `host -> str`, `port -> int`. Methods: `start(env: dict[str, str], network: Network |
None)`, `stop()`, `alive() -> alive: bool`, `logs() -> output: str`. Requirements: **readiness
completes before start returns — the port, or the health path when declared, within the declared
deadline at the declared interval; an expired deadline fails as `EngineError`** — an actionable
failure naming the instance and the waited check, never a hang. Constraints: never restarted on
reset.

**Routine: `render_service_env(env: dict[str, str], addresses: dict[str, InstanceAddress]) -> rendered: dict[str, str]`**
— `location: env_render.py`. Strict jinja2 rendering; context `{service name: {host, port}}`;
unknown placeholder fails naming the value. Unchanged behavior.

**Routines: `activate_sandbox(context: dict[str, object]) -> config: SandboxConfig | None` and
`active_sandbox() -> sandbox: Sandbox | None`** — `location: activation.py`. Presence-gated
arming via `load_sandbox_config`; registers session start/stop and the per-test preset enqueue
into `context`; None ⇒ fully inert. `active_sandbox()` is the lookup seam. Constraint: no
containers start here.

#### Companion surfaces (no contract change; text-level duties from the design)

- `goga_tool_pybuggy/plugin/__init__.py` `install` docstring — names the new document path.
- `goga_tool_pybuggy/plugin/plugin.py` `configure` fail-fast text — names the new document path.
- `goga_tool_pybuggy/commands/init/init.py` `PYBUGGY_ANNOTATIONS["sandbox-file"]` — names the
  new path and the new key vocabulary.
- Author docs sweep + cooks (see Task 15).

### Re-exports

- Cell facade `sandbox/config` — `__all__` grows to `["InstanceConfig", "ProbeConfig",
  "SandboxConfig", "ServiceConfig", "StartupData", "TopicConfig", "load_sandbox_config"]`
  (alphabetical; two new names).
- Cell facades `sandbox/engines` (11 names incl. `EngineError`), `sandbox/data` (6 names),
  `sandbox` (6 names) — unchanged.
- Root `goga_tool_pybuggy` re-exports `active_sandbox` (from `.sandbox`) and `services` (from
  `.sandbox.data`) — unchanged.

### Usages Context

- `conventions` (`.goga/usages/conventions.md`): mandatory Python rules — virtualenv execution,
  relative imports, pydantic `kw_only` models, structured logging, blank-line block formatting,
  Google docstrings, type-hint grammar, test structure and classification, dependency
  declaration. Used by every touched cell. **Extracted in full into Mandatory Rules below —
  they override any stylistic preference of the implementing agent.**
- `ruamel-yaml` (`.goga/usages/cooks/ruamel-yaml.md`): round-trip YAML API for parsing the
  sandbox document and for serializing the generated AsyncAPI document (`YAML()` instance;
  `yaml.load(path)`; serialize into `StringIO`, encode UTF-8). Used by `load_sandbox_config`
  and `KafkaEngine` document generation.
- `testcontainers` (`.goga/usages/cooks/testcontainers.md`): container lifecycle — module and
  generic containers, labels, fixed port reservation, restart-based wipe, `with_command`,
  `with_copy_into_container` (docker-API transfer of the generated document), the runtime probe,
  Ryuk safety net. Used by `check_runtime`, `build_engine`, all kind engines, `ServiceContainer`.
- `psycopg` (`.goga/usages/cooks/psycopg.md`): postgres data plane — autocommit session
  connection, `%s`-bound parameters, catalog-driven TRUNCATE reset; now also the engine-owned
  readiness probe `psycopg.connect(host, port, user, password, dbname, connect_timeout=2)`.
  Used by `PostgresEngine`.
- `kafka-python` (`.goga/usages/cooks/kafka-python.md`): producer against the mapped bootstrap
  address; `send` + `future.get(timeout=DELIVERY_TIMEOUT)`; `flush` as the batch boundary;
  `close()` at stop. Used by `KafkaEngine`.
- `mokapi` (`.goga/usages/cooks/mokapi.md`): kafka mock contract — AsyncAPI document as the
  start argument, `/health` readiness (HTTP 8080), kafka listener 9092, restart-wipe semantics,
  topics/partitions from the AsyncAPI channels and the kafka channel binding. Used by
  `KafkaEngine`.
- `vault-dev` (`.goga/usages/cooks/vault-dev.md`): vault dev-mode contract — env flags, fixed
  dev root token, KV v2 paths, `/v1/sys/health` readiness, restart-wipe semantics. Used by
  `VaultEngine`.
- `wiremock` (`.goga/usages/cooks/wiremock.md`): http mock contract — admin mappings API,
  mappings reset, admin health readiness (404 → mappings fallback), near-miss visibility. Used
  by `HttpEngine`.
- `requests` (`.goga/usages/cooks/requests.md`): HTTP client for the vault/http data planes and
  health probes — `requests.get/post(url, headers=…, json=…, timeout=5)`; probe loops with
  deadlines. Used by `VaultEngine`, `HttpEngine`, `ServiceContainer`.
- `jinja2` (`.goga/usages/cooks/jinja2.md`): `Environment(undefined=StrictUndefined)`; context
  `{service: {"host", "port"}}`; per-value render. Used by `render_service_env`.
- `pluginator` (`.goga/usages/cooks/pluginator.md`): `install_pytest_plugins`, `call_context`,
  the `configure()` lifecycle; hooks land in the conftest namespace dict. Used by the plugin
  cell and the sandbox hook registration.

### Imported Usages

- `sandbox-file` from `goga_tool_pybuggy/sandbox/config` — path
  `goga_tool_pybuggy/sandbox/config/.usages/sandbox-file.md`. The sandbox document authoring
  semantics (new layout, inline topics, probe tables, document-locating section, placeholder
  syntax). Consumed by the sandbox cell annotations (`Sandbox`, `render_service_env`,
  `activate_sandbox`). Already materialized and verified against the manifest by the design —
  read it as the authoring reference; do not modify.
- `data-operations` from `goga_tool_pybuggy/sandbox/data` — path
  `goga_tool_pybuggy/sandbox/data/.usages/data-operations.md`. The laziness contract and the
  declaration shapes (declared-topics produce note, new path). Consumed by
  `Sandbox.apply_pending`. Already materialized and verified — read-only.

### Local Usages

None to create or modify. The four cell-level `.usages/` files (`sandbox-file.md`,
`data-operations.md`, `sandbox-session.md`, plugin `enable.md`) were materialized by
apply-architecture and re-verified against the manifests during the design (§ Usages /
`.usages/` Consistency): block-style YAML throughout, no references to the former path or former
keys. No usage-file tasks.

### External Dependencies

None new. `pyproject.toml` already declares `testcontainers[postgres]>=4.15`, `psycopg[binary]>=3.1`,
`kafka-python>=3.0`, `requests>=2.31`, `ruamel.yaml>=0.18`, `jinja2>=3.1`, `pydantic>=2.0`,
`pluginator`; `.usages` package-data patterns already present. The in-memory AsyncAPI generation
uses plain serializable structures + ruamel — no new libraries. Pinned container defaults stay:
postgres `postgres:16-alpine`; kafka `mokapi/mokapi:0.28.0` (HTTP 8080 + kafka 9092); vault
`hashicorp/vault:1.17` (port 8200, dev token constant, never logged); http
`wiremock/wiremock:3.13.0` (port 8080). Labels on every container: `{"pybuggy-sandbox": "true"}`.

### Code Stack Traces (verbatim from the design — verified knowledge; the tasks implement these chains)

1. **`activate_sandbox(context)`** → `load_sandbox_config(None)` → resolves
   `cwd/.goga/tools/pybuggy/sandbox.yml` → absent → `None` → inert return, no hooks (presence
   gate; stale root document never read). Present → parse → top-level diagnostics → instance
   entry (image/env/port/probe) → services (name grammar, kind, topics incl. duplicates and
   non-kafka rejection, probe without path) → data sections (no kafka; targets resolve; vault
   shape) → placeholders (env names ⊆ services) → `SandboxConfig` → hooks registered → config
   kept armed. Type flow: `SandboxConfig` → `Sandbox(config)` constructor — shapes match.
2. **`Sandbox.start()`** → `check_runtime` → network → per service (declaration order):
   `build_engine(ServiceConfig)` → `engine.start(startup ops, network)` → container (image
   override / labels / port / network alias) → readiness within declared bounds (D5/D3/D4
   paths) → data plane open → startup ops applied + journaled (vault → http → postgres per
   engine) → `addresses[name] = engine.address` → `render_service_env(config.instance.env,
   addresses)` (strict Jinja2; defense in depth) → `ServiceContainer.start(rendered, network)`
   → probe-bounded readiness (D10) → logs. Checkpoint: `StartupData` section payload shapes
   match the `DataOperation` payload contracts (`put` {path,data}, `stub` mapping, `insert`
   {sql}).
3. **`KafkaEngine` build/produce/reset** — topics from `config.topics` (validated non-empty at
   load, re-checked at start) → generated 2.6.0 document with the reserved mapped address →
   docker-API transfer → command argument → `/health` bounded wait → producer against the same
   address; `produce` topic gate (D9); reset restarts, binding+document survive, re-wait
   bounded, baseline replays. Checkpoint: bootstrap = metadata = `{{events.host}}:{{events.port}}`
   — one address (the existing pipeline property preserved).
4. **Per-test flow** — `pytest_runtest_setup` → `new_test_batch()` → preset enqueue (names via
   `_require_service`) → view declarations lazy → first api request → `apply_pending` → batch
   take → group by service → `engine.apply` (postgres insert resolves `$ref`/`$lookup` at
   execution; payload never rewritten) → request proceeds. Checkpoint: preset nesting
   `kind → name → declarations` matches the tightened `services` type and the enqueue loop.
5. **Reset flow** — `clear()` → per engine `reset()` → wipe (truncate / restart / mappings
   reset) → journal replay rebuilds state; instance container untouched.

### Verified External Facts (verbatim from the design — do not re-derive, re-confirm in the REPL per M-R4.5)

1. **mokapi topics and partitions.** mokapi derives kafka topics from AsyncAPI channels and the
   partition count from the **kafka channel binding** `partitions` ("Sets the number of
   partition for the channel. Default value is 1" — mokapi kafka configuration docs). In
   AsyncAPI 2.6 the channel key is the topic name; in 3.0 the channel carries `address` with
   the topic name. The kafka server entry stays `servers.<name>` with `protocol: kafka` and the
   load-bearing `host:port`. mokapi validates produced messages against declared payload
   schemas — the generated document must declare **no** message payloads, or arbitrary test
   values get rejected.
2. **testcontainers 4.15 postgres module readiness.** `PostgresContainer.start()` (via
   `DbContainer.start`) runs `self._connect()` after the container runs — a fresh internal
   `ExecWaitStrategy` (psql exec probe) whose timeout/interval come from the global
   `testcontainers_config` defaults and **cannot be re-parameterized from outside** (the
   strategy object is constructed inside `_connect`). `DockerContainer.waiting_for(...)` does
   not reach it. Bounding the module wait by declared values therefore requires either an
   executor-wrapped `start()` or disabling `_connect` — decision D3 chooses the latter.

### Design Decisions (binding for implementation; verbatim condensations)

- **D1** — probe/topic constraints live in the models, surfaced with document scope by the
  loader: pydantic validators (`ProbeConfig` bounds; `ServiceConfig` model validator rejecting
  `probe.path is not None` with "the probe path is accepted only on the instance entry"); the
  loader's `_build_model` wraps any `ValidationError` into `ValueError(f"{location}: {scope}:
  {details}")` — one enforcement point per rule, every failure names the document location and
  the offending entry.
- **D3** — bounded module readiness via a private module subclass + engine-owned psycopg probe:
  `_PostgresContainer(PostgresContainer)` whose `_connect` is a no-op ("readiness probing is
  engine-owned, bounded by the declared deadline"), and a real `PostgresEngine._wait_ready`
  probing `psycopg.connect(host, port, user, password, dbname, connect_timeout=2)` in the D5
  loop, closing the probe connection on success (the session connection opens in `_open_plane`
  as today). Honors both the declared timeout and interval; default equivalence 30.0/0.5.
- **D4** — generated document shape: AsyncAPI **2.6.0** (channel key = topic name); `info
  {title: <service name>, version: "1.0.0"}`; one server `kafka: {protocol: kafka, host:
  "<host>:<reserved port>"}`; one channel per topic `<topic name>: {bindings: {kafka:
  {partitions: <partitions>}}}`; **no messages/payload schemas**. Serialized to UTF-8 bytes
  with the existing ruamel `YAML()` into a `StringIO`; never written to disk anywhere.
- **D5** — bounded probe loop helper: private `_probe_until(timeout, interval, attempt,
  failure)` computing `deadline = monotonic() + timeout` internally: while `monotonic() <
  deadline` — run `attempt()`; on True return; sleep `interval`. Expiry raises
  `RuntimeError(f"{failure} within {timeout:g}s")`. Lifecycle wrappers convert it into
  `EngineError`.
- **D6** — readiness bounds accessor: `_readiness_bounds` property returns
  `(probe.timeout, probe.interval)` of `self.config.probe or ProbeConfig()`. Single default
  source — no probe declared → 30.0 / 0.5 by construction.
- **D7** — duplicate topic names within one service entry are rejected ("duplicate topic
  '<name>' — each topic name must be unique within the service entry"): duplicates would
  silently collapse the generated AsyncAPI channels.
- **D8** — structured-log extras swap with the contract vocabulary: engines emit
  `extra={"service": name, "kind": kind}` and events "service starting" / "service ready" /
  "service stopped"; `DataOperation.instance` and `EngineError` message wording "service
  '<name>'" follow. Event names stay stable and unique across the sandbox.
- **D9** — produce topic gate: `topic not in {t.name for t in self.config.topics}` →
  `EngineError("service '<name>': topic '<topic>' is not declared on the kafka service entry
  (declared topics: <sorted names>)")`.
- **D10** — `ServiceContainer` readiness: `probe = self.config.probe or ProbeConfig()`;
  path-only semantics: `probe.path is None` → TCP port loop, else health-endpoint 2xx loop at
  `http://{host}:{port}{path}`; both loops run the declared `probe.timeout` / `probe.interval`;
  expiry raises `EngineError` directly (imported from `..engines`) — "the instance under test
  (image <image>) did not become ready: <check description> within <timeout>s".

## Facts

- The design passed `goga-review-design`: all five code-stack traces hold; 6 review fixes
  applied to the design document. `goga lint` reports 23 cells, 0 errors; `goga schema`
  dependency map matches the plan (config ← engines ← data ← sandbox ← plugin).
- The branch working tree already carries the materialized contract: the four sandbox
  CODEMANIFESTs and the four cell `.usages/` files are modified-but-uncommitted (the
  apply-architecture stage wrote them; the design verified them). They are the read-only
  contract input and land in git with the first task commit.
- The Python implementation at HEAD `2906069` is the pre-change state: loader resolves
  `Path.cwd() / ".sandbox.yml"` (`_DOCUMENT_NAME`); `SandboxConfig(service, instances, data)`;
  old `ServiceConfig(image, env, port, health)` is the under-test entry; old `InstanceConfig(name,
  kind, image)` is the dependency entry; `StartupData` has a `kafka` section (spec paths
  resolved by `_resolve_spec_path`); engines take the old `InstanceConfig`; `vault.py` /
  `http.py` carry `READINESS_TIMEOUT = 30.0` / `READINESS_INTERVAL = 0.5` module constants and
  raise bare `RuntimeError` on expiry; `KafkaEngine` consumes startup spec paths
  (`_spec_paths`, `_specs`, `_patch_specs`).
- `probe.py` and `topic.py` do not exist; the config facade exports 5 names.
- All other facades are already at their target shape: engines 11 names (incl. `EngineError`,
  `validate_insert_rows`), sandbox 6 names, root re-exports `active_sandbox` / `services`.
- `tests/sandbox/` mirrors the source tree (config / engines / data subpackages + six root
  module suites + `test_session_lifecycle.py`); `tests/sandbox/conftest.py` provides
  `docker_available()` / `requires_docker`, the `sandbox_yaml` fixture (currently writing
  `.sandbox.yml` at the `tmp_path` root), and the `FakeEngine` / `FakeService` / `FakeNetwork`
  doubles (old vocabulary in docstrings/doubles).
- `pyproject.toml`: all needed dependencies already declared with minimum versions; ruff
  configured (`target-version = "py310"`, `line-length = 120`, rule sets E/W/F/I/N/UP/B/SIM/PL/
  PLR/C4/DTZ/PT/ARG/RUF/PTH/C90, mccabe max-complexity 10, per-file ignores for tests; format:
  double quotes, LF); pytest `testpaths = ["tests"]`, `addopts = "-v --tb=short"`.
- No virtualenv exists in the repo (`.venv` absent) — conventions require creating one and
  executing everything inside it (M-R1.2).
- Docker is NOT available in the execution environment — container-dependent tests skip via
  `requires_docker`; docker-gated REPL probes are unavailable (M-R4.5 fallback applies).
- The external facts the contract depends on were verified against the actual library sources
  during design (§ Verified External Facts) — the installed wheels are
  `testcontainers[postgres]>=4.15` and the mokapi image `mokapi/mokapi:0.28.0`.

## Gap Analysis

- Missing contract entities: `ProbeConfig` (`config/probe.py`), `TopicConfig` (`config/topic.py`).
- Missing facade exposure: `ProbeConfig`, `TopicConfig` on the config cell facade.
- Incorrect `location` placement: none — every changed entity keeps its `location`; two new
  files at their declared locations.
- API mismatches vs the current code: `SandboxConfig` (field swap instance/services),
  `InstanceConfig` (repurposed to the under-test entry + `probe`), `ServiceConfig` (repurposed
  to the dependency entry + `topics` + `probe`, D1 path validator), `StartupData` (no kafka
  field), `load_sandbox_config` (new path, top-level diagnostics, topics/kind/data/placeholders
  validation; `_read_service`/`_read_instances` → `_read_instance`/`_read_services`;
  `_resolve_spec_path` deleted), `DataOperation` (action set without `spec`), `BaseEngine` /
  `build_engine` / kind engines (`ServiceConfig`, readiness bounds), `ServiceContainer`
  (`InstanceConfig`, probe readiness, `EngineError` expiry), `services(...presets)` (tightened
  annotation), `KafkaInstance.produce` (declared-topics docstring).
- Behavioral mismatches: hand-rolled readiness loops with 30/0.5 constants in three engines +
  `ServiceContainer` → D5/D6 probe-bounded loops with `EngineError` expiry; postgres module
  wait unbounded-by-declaration → D3; kafka spec-file pipeline → in-memory generation (D4) with
  produce gate (D9) and fail-fast empty declaration; `Sandbox._startup_operations` includes a
  kafka section → vault → http → postgres only; `_require_instance` → `_require_service`;
  plugin/init texts name the former path.
- Existing code that can be reused: the loader helper skeleton (`_parse_document`, `_read_*`,
  `_build_model`, `_validate_placeholders`, the name-grammar and placeholder regexes, the
  `_INSTANCE_NAME` rationale comment), the `_run_step` lifecycle wrappers and journal machinery
  in `base.py`, `reserve_port`, kafka serializers / producer lifecycle / restart wipe, postgres
  `$ref`/`$lookup` resolution and catalog-driven truncate, wiremock 404→mappings readiness
  fallback, plugin arming machinery, the conftest doubles and `requires_docker` pattern, the
  pinned container defaults and labels.
- Test coverage gaps: all 31 design scenarios plus the model-level units — the current suites
  assert the old vocabulary (old document keys, old constructor shapes, spec-based kafka,
  constants-based readiness) and are reworked per cell.
- Missing visibility in workspace or git: the CODEMANIFEST + `.usages/` modifications are
  uncommitted — they land with the Task 1 commit; no other untracked assets.

## Mandatory Rules

Extracted from the project convention `.goga/usages/conventions.md` (usage key `conventions` —
connected in every touched CODEMANIFEST) plus the Python cell rules where marked. They are
**mandatory for every task and every development stage of this plan**; the convention's
precedence applies: contract first, package boundary/facade second, these project conventions
next, language idioms last.

### R1. Coding Style Rules (strictly per project convention)

- **M-R1.1** Python 3.10+ only; `pyproject.toml` is the single configuration source.
- **M-R1.2** Execute ALL code (tests, REPL, probes, checks) inside a virtualenv — Task 1
  creates it; every later command runs through `.venv/bin/…`. Never run the project with the
  system interpreter.
- **M-R1.3** Imports: **relative** for all intra-package references; **absolute** only for
  stdlib and third-party (`from ..config import ProbeConfig`, `from ..config.service import
  ServiceConfig` — never `from goga_tool_pybuggy.sandbox.config import …` inside the package).
- **M-R1.4** Data models: pydantic with `kw_only=True` (`model_config = ConfigDict(kw_only=True)`
  or the 3.10+ `kw_only` syntax per existing style); empty defaults (empty dict/list, zero) for
  fields — `None` only for the explicit absence of a value (`probe: ProbeConfig | None`,
  `image: str | None`, `path: str | None`).
- **M-R1.5** Logging: stdlib `logging` with module loggers (`logger = logging.getLogger(__name__)`);
  every operational log carries contextual metadata via `extra={...}`; messages lowercase,
  concise, with **stable log event names**. Vocabulary per D8: engines emit
  `extra={"service": name, "kind": kind}` with events "service starting" / "service ready" /
  "service stopped"; the instance container logs name the instance/image. Levels: DEBUG —
  intermediate state, payload previews, branch decisions ("engine built"); INFO — lifecycle
  ("sandbox document loaded", startup progress, base_url source, stopped); WARNING —
  recoverable abnormality; ERROR — start/stop failures, died instance; CRITICAL — none in this
  plan. **No secrets in logs** — the vault dev token and vault secret payloads are never
  logged (unchanged invariant).
- **M-R1.6** Function/method bodies: logical blocks separated by **one blank line** (variable
  initialization vs conditionals/loops; data preparation vs processing; processing vs return).
- **M-R1.7** Docstrings: **mandatory** for all public functions, methods, and classes,
  **Google style** — first line capitalized and ending with a period; `Args` when parameters
  exist; `Returns` when a value returns; `Raises` for exceptions beyond built-in behavior
  (`ValueError` from the loader, `EngineError` expiry clauses).
- **M-R1.8** Type hints mandatory; signature grammar per the Python language rules: `str`,
  `int`, `float`, `bool`, `list[T]`, `dict[str, T]`, `T | None`; forbidden `*args` / `**kwargs`
  (the single documented exception: `services(...presets)`) and bare `dict` / `list`.
- **M-R1.9** Dependencies: every third-party library in `pyproject.toml` with a minimum
  version — **this plan adds none**; do not add any.
- **M-R1.10** Naming: PascalCase classes, snake_case functions/methods/properties; names
  consistent with the contract vocabulary — **`instance` = the entry under test, `service` = a
  dependency** (the CODEMANIFEST signatures are the vocabulary); internal helpers keep
  support-intent names (`_probe_until`, `_readiness_bounds`, `_PostgresContainer`).

### R2. Test Writing Rules (strictly per project convention)

- **M-R2.1** Tools: pytest (running), pytest-cov (coverage), ruff (linting and formatting test
  code); test code compatible with Python 3.10+; executed in the virtualenv.
- **M-R2.2** Tests mirror the source structure directly: `goga_tool_pybuggy/sandbox/config/
  loader.py` → `tests/sandbox/config/test_loader.py`; sandbox-cell root modules →
  `tests/sandbox/test_<module>.py`. Every test directory carries `__init__.py` (all exist
  already). Local fixtures in `tests/<package>/conftest.py`, shared fixtures in
  `tests/conftest.py`.
- **M-R2.3** Naming: files `test_<module>.py`; functions `test_<what>_<scenario>`; class
  grouping `class Test<Component>:` where a module groups multiple components.
- **M-R2.4** Coverage: unit tests for every public function/method/class — main scenario plus
  typical data; edge cases — empty inputs (`None`, `""`, `[]`, `{}`), boundary values (`0`,
  negative, very large), invalid types, expected exceptions via `pytest.raises` with `match=`
  asserting the exact message wording. **Contract tests (facade accessibility, API shape,
  signatures) are written FIRST in each coding task and expected to fail initially (TDD).**
- **M-R2.5** Boundary tests (thresholds, ranges, state transitions) use
  `@pytest.mark.parametrize` with a table of values including each boundary — probe bounds are
  parametrized, and the legal boundary (`interval == timeout`) rides along as its own test so a
  `<=` → `<` comparator regression cannot hide behind green negative tests.
- **M-R2.6** Mocks only at external boundaries: unit suites stay **mock-free** (pure logic);
  file I/O exclusively via the `tmp_path` fixture (+ `monkeypatch.chdir`); external dependencies
  (`requests.get`, `psycopg.connect`, docker) patched at the import point with
  `monkeypatch.setattr`.
- **M-R2.7** Container-dependent tests are gated with `requires_docker`
  (`pytest.mark.skipif`); no network in unit tests. Docker is unavailable in the execution
  environment — the gated suites must collect and skip cleanly.
- **M-R2.8** Self-documenting test names; keep comments minimal.
- **M-R2.9** Test libraries live in `[project.optional-dependencies]` under the `test` key —
  already satisfied; no additions.

### R3. Lint and Format Enforcement (all development stages and local commits)

- **M-R3.1** `ruff` is the project's single linter AND formatter, configured in
  `pyproject.toml` (target py310, line-length 120, the full rule selection incl. `I`, `N`, `UP`,
  `B`, `SIM`, `PL`, `PLR`, `C4`, `DTZ`, `PT`, `ARG`, `RUF`, `PTH`, `C90` max-complexity 10;
  format: double quotes, LF, magic trailing comma on).
- **M-R3.2** Every development stage — writing contract tests, implementing, writing logic
  tests, debugging — keeps the touched paths lint-clean: run `ruff check` after each stage, not
  only at task end.
- **M-R3.3** Every task ends with the LINT gate: `.venv/bin/ruff check goga_tool_pybuggy/
  tests/` exits 0, and every file the task touched is format-clean (`.venv/bin/ruff format
  --check <touched files>`; apply `ruff format` to touched files when drift appears). Never
  reformat files outside the task's scope.
- **M-R3.4** **Local commit gate — enforced before EVERY local commit of this plan** (task
  commits, fix commits, wip commits alike):
  - lint + format always: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` exit 0 AND
    `ruff format --check` on the commit's touched files;
  - tests: `pytest tests/ -x` green in the venv — **from Task 14 onward** (all suites
    migrated). During the migration window (Tasks 3–13) the full suite is knowingly red in the
    not-yet-migrated suites (the design is a coordinated vocabulary swap; at Task 13 the sole
    remaining red file is `tests/sandbox/test_session_lifecycle.py`, reworked in Task 14); the
    commit gate there is the task's authoritative migrated suites per the Migration Ledger,
    run green in the venv. Committing lint findings or a red authoritative suite is forbidden;
    "fixing" a not-yet-migrated suite outside its own task is equally forbidden (scope creep —
    its rework belongs to its task).
- **M-R3.5** `goga lint` at plan end: 23 cells, 0 errors — no new findings against the
  baseline.
- **M-R3.6** When the complexity gates (C90 / PLR) trip, decompose inside the current cell
  (internal helpers are allowed; new cells are not).

### R4. REPL Cycle Rules (continuous interactive evaluation, hot reloading, code migration to source files)

The workflow of every coding task is a live-evaluation loop — **prototype → evaluate → migrate
→ re-verify**, repeated per entity — not write-blind-then-test:

- **M-R4.1 (Continuous interactive evaluation)** — exercise every non-trivial behavior
  fragment in an interactive Python session inside the virtualenv (`.venv/bin/python -i`, or a
  heredoc `.venv/bin/python - <<'PY'`) with real inputs **before and while it lands in source
  files**: sample `.goga/tools/pybuggy/sandbox.yml` documents (valid and each invalid variant),
  real placeholder strings, probe-loop timings (sub-second `timeout`/`interval` pairs), the
  AsyncAPI document as serialized YAML bytes, `psycopg.connect` keyword shapes, producer send
  signatures. Nothing moves to "done" on faith; each behavior is observed first.
- **M-R4.2 (Hot reloading)** — keep one REPL session per task where practical; after source
  edits re-import with `importlib.reload(module)` instead of restarting the session, and never
  evaluate against stale definitions. Use the focused test file
  (`.venv/bin/pytest tests/<mirror>/test_<module>.py -x -v`) as the fast feedback loop; the full
  authoritative set at task end.
- **M-R4.3 (Code migration to source files)** — the REPL is a scratchpad, never a home: every
  verified snippet is migrated into the module at its contract `location` wearing the
  convention outfit (Google docstring M-R1.7, module logger M-R1.5, type hints M-R1.8,
  blank-line blocks M-R1.6); the scratch is discarded; the migrated code is re-verified through
  a FRESH interpreter import (`.venv/bin/python -c "from goga_tool_pybuggy.sandbox.config
  import ProbeConfig; …"`) before the task's tests run. No behavior ships REPL-only: every
  verified fragment lands in a source file or a test.
- **M-R4.4 (Scratch hygiene)** — prototypes live in the REPL or under `/tmp`; never as files
  inside the repo; nothing scratch is committed.
- **M-R4.5 (REPL complements TDD; external facts stay live)** — the contract tests and logic
  tests of each task remain the authority; the REPL loop lives inside STEP 2 (implementation)
  and STEP 5 (debugging) of the ralphex protocol, and during debugging the failing input is
  reproduced in the REPL with the exact test data before anything is fixed. Load-bearing
  external facts (§ Verified External Facts) are re-confirmed once in the REPL against the
  installed wheels (`import testcontainers.postgres; inspect PostgresContainer._connect`;
  `from testcontainers.core.container import DockerContainer; inspect with_copy_into_container`)
  instead of trusting memory. Docker-dependent prototypes run in the REPL only when the
  container runtime is available — it is not in this environment, so those fragments are
  verified against the traced design and the fake/mock-based unit tests, and the live behavior
  is carried by the `requires_docker`-gated suites.

### R5. Contract Discipline

- **M-R5.1** `CODEMANIFEST` files are read-only contract definitions. Do NOT modify them. The
  working-tree manifests of this branch ARE the contract; if the implementation does not match,
  fix the implementation — never the contract. No manifest changes without a new design pass.
- **M-R5.2** Facade obligations: every contract entity is importable from its cell package
  root via `__all__`; only identifiers in `__all__` constitute the facade. This plan grows the
  config facade to seven names; all other facades stay byte-stable.
- **M-R5.3** Traceability: every implementation unit and test maps to a contract entity /
  property / method / described requirement — the per-task entity lists carry the mapping.
- **M-R5.4** No new cells; internal helpers stay inside the current cell (`_probe_until`,
  `_readiness_bounds`, `_PostgresContainer`, the private document generator); `location`
  placement is obeyed exactly; relative imports inside the package.
- **M-R5.5** The public Python API surface is unchanged: same class names, same view
  factories, same root re-exports — renames (`_require_instance` → `_require_service`,
  `_read_service` → `_read_instance`, `_read_instances` → `_read_services`) are
  private-vocabulary only.

---

## Tasks

> **Package ordering rule**: coding tasks for each package are completed before starting the
> next. Within each coding task, contract tests are written first (TDD workflow). Cell order:
> `sandbox/config` → `sandbox/engines` → `sandbox/data` → `sandbox` → `plugin`/`commands-init`
> texts → docs/cooks → integration → final validation. Every task follows the Mandatory Rules
> (R1–R5) in full; the lint gate of each task is also the pre-commit gate (M-R3.4).

> **Migration Ledger** — the design swaps the vocabulary (`instance`/`service` subjects,
> document path and keys) across four cells at once; intermediate full-suite green is
> unattainable without transitional shims the contract forbids. Therefore each task's
> **authoritative suites** (run green at task end and before its commit) are:
>
> | After task | Authoritative suites (cumulative) |
> |---|---|
> | Task 1 | all (baseline) |
> | Task 2 | all (additive change) |
> | Task 3 | `tests/sandbox/config/{test_instance,test_service,test_sandbox_config,test_startup_data}.py` |
> | Task 4 | `tests/sandbox/config/` |
> | Task 5 | + `tests/sandbox/engines/{test_base,test_runtime,test_operation}.py` |
> | Task 6 | + `tests/sandbox/engines/test_postgres.py` |
> | Task 7 | + `tests/sandbox/engines/{test_vault,test_http,test_address,test_refs}.py` |
> | Task 8 | + `tests/sandbox/engines/test_kafka.py` (engines cell complete) |
> | Task 9 | + `tests/sandbox/data/` |
> | Task 10 | + `tests/sandbox/test_service_container.py` |
> | Task 11 | + `tests/sandbox/{test_sandbox,test_baseline,test_env_render}.py` |
> | Task 12 | + `tests/sandbox/test_activation.py` |
> | Task 13 | + `tests/plugin/` (every suite migrated except `tests/sandbox/test_session_lifecycle.py` — the sole permitted red file at Task 13's commit, reworked next) |
> | Tasks 14–16 | **full suite restored: `pytest tests/ -x` green from Task 14 on** |
>
> Suites below the ledger row are known-red by design until their own task; do not touch them
> outside their task (M-R3.4). `tests/sandbox/conftest.py` is updated in Task 4 of the rework
> (the `sandbox_yaml` fixture flip) and its doubles are vocabulary-updated in the tasks that
> consume them (Tasks 10–12).

---

### Task 1: Workspace bootstrap — virtualenv, contract commit, baseline green (infrastructure)

Prepare the execution environment. The repo has no virtualenv (conventions require one,
M-R1.2); the branch working tree carries the materialized contract (four CODEMANIFESTs + four
`.usages/` files, modified-uncommitted) which lands in git here as the read-only contract
input. Nothing else changes.

**Usages relevant to this task:**
- `conventions`: virtualenv execution (M-R1.2); pyproject-based configuration (M-R1.1).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Create the virtualenv: `python3 -m venv .venv` and install the project editable with the
  test extra: `.venv/bin/pip install -e '.[test]'`; verify `.venv/bin/python -c "import
  goga_tool_pybuggy"` succeeds
- [x] Verify the current suite baseline is green: `.venv/bin/pytest tests/ -x`
  (1458 passed, 0 failed; environment note — docker IS reachable here and runs inside a
  proxied-socket container, so container-gated tests execute and need
  `TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal` prefixed to every pytest run; recorded in
  the progress log)
- [x] Verify the contract baseline: `goga lint` → 23 cells, 0 errors
- [x] Commit the already-materialized contract files (the four sandbox CODEMANIFESTs + the four
  cell `.usages/` files) unchanged — they are this plan's read-only input
  (already committed unchanged in `4a67ad7` before the loop started; all 8 paths verified
  tracked, working tree clean — nothing further to commit)
- [x] Lint gate (pre-commit, M-R3.4): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0

### Task 2: `ProbeConfig` and `TopicConfig` — the new declaration models (TDD)

Two new pydantic models in the config cell, at their new locations, exported from the facade.
Purely additive — nothing existing changes yet.

**Contract entities**: `ProbeConfig(timeout: float = 30.0, interval: float = 0.5, path: str |
None = None)` (`probe.py`, new file), `TopicConfig(name: str, partitions: int = 1)` (`topic.py`,
new file) — both importable from `goga_tool_pybuggy.sandbox.config`.

**Usages relevant to this task:**
- `conventions`: pydantic `kw_only` data models, empty/None defaults (M-R1.4), Google
  docstrings, relative imports, boundary parametrization in tests (M-R2.5).

**Design details (binding):**
- `ProbeConfig`: `timeout`/`interval` strictly positive (`Field(gt=0)`); `interval <= timeout`
  enforced by a `model_validator(mode="after")` raising "the probe interval (default 0.5) must
  not exceed the timeout — declare a smaller interval alongside a sub-second timeout" (the
  message names the default interval so a sub-second-timeout error is actionable). The defaults
  reproduce the established wait exactly: 30.0 / 0.5 (D6's single default source).
- `TopicConfig`: `name: str` with `Field(min_length=1)`; `partitions: int = 1` with
  `Field(gt=0)`.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 2 is being executed
- [x] **Contract tests** (expected to fail now): `tests/sandbox/config/test_probe.py` (new),
  `tests/sandbox/config/test_topic.py` (new) — both importable from the facade; kw_only
  construction; property types `timeout -> float`, `interval -> float`, `path -> str | None`,
  `name -> str`, `partitions -> int`
  (written first; failed with ImportError on the missing facade names before implementation —
  TDD red confirmed)
- [x] **REPL prototype (R4)**: in the venv REPL construct `ProbeConfig()`, `ProbeConfig(timeout=45.0)`,
  `ProbeConfig(timeout=0.3, interval=0.05)`, `TopicConfig(name="orders.events")`,
  `TopicConfig(name="payments.events", partitions=6)`; observe defaults (30.0 / 0.5 / None; 1)
  and the validator rejections (`timeout=0`, `interval=-1`, `interval=60, timeout=30`,
  `interval == timeout` accepted, empty topic name, `partitions=0`); then migrate
  (all constructions and rejections observed live in a venv heredoc REPL, including the exact
  D-message wording of the interval validator; then migrated)
- [x] **Code**: create `goga_tool_pybuggy/sandbox/config/probe.py` and `topic.py` with the
  pydantic `kw_only` models and validators exactly as above
- [x] **Code**: expose both on the cell facade — `__all__ = ["InstanceConfig", "ProbeConfig",
  "SandboxConfig", "ServiceConfig", "StartupData", "TopicConfig", "load_sandbox_config"]`
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/config/test_probe.py
  tests/sandbox/config/test_topic.py -x -v` — pass; fresh-interpreter facade check (M-R4.3):
  `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.config import ProbeConfig, TopicConfig"`
  (29 passed; fresh-interpreter import ok)
- [x] **Logic tests**: defaults (30.0 / 0.5 / None; partitions 1); partial override keeps the
  rest; bound rejections parametrized per M-R2.5 (`timeout=0`, negative interval,
  `interval > timeout`, empty name, `partitions=0`, `partitions=-1`); **legal boundary**
  `ProbeConfig(timeout=30.0, interval=30.0)` constructs (guards the `<=` comparator);
  positional construction raises `TypeError` (kw_only); path-free construction valid
- [x] **Debugging**: `.venv/bin/pytest tests/ -x` — still fully green (additive change; this is
  the last task with that luxury — see the Migration Ledger)
  (1487 passed, 0 failed = 1458 baseline + 29 new)
- [x] **Contract re-verification**: model requirements match the entity declarations (defaults
  reproduce the established wait; bounds positive; interval never exceeds timeout)
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 3: Entry models rework — `InstanceConfig`/`ServiceConfig` swap subjects, `SandboxConfig` fields, `StartupData` without kafka (TDD)

The heart of the vocabulary swap in the config cell: `instance.py` becomes the under-test entry,
`service.py` the dependency entry (with topics and the D1 path validator), `sandbox_config.py`
takes `instance`/`services`, `startup_data.py` drops the kafka section (field order vault →
http → postgres is the application order at start).

**Contract entities**: `InstanceConfig(image, env, port, probe)` (`instance.py`, repurposed),
`ServiceConfig(name, kind, image, topics, probe)` (`service.py`, repurposed), `SandboxConfig(instance,
services, data)` (`sandbox_config.py`), `StartupData(vault, http, postgres)` (`startup_data.py`)
— facade importability unchanged (same five names plus Task 2's two).

**Usages relevant to this task:**
- `conventions`: pydantic `kw_only`, empty defaults, `None` only for explicit absence (M-R1.4);
  Google docstrings reflecting the new subjects; relative imports.

**Design details (binding):**
- `InstanceConfig` (under-test entry): `image: str`, `env: dict[str, str] = {}`, `port: int`,
  `probe: ProbeConfig | None = None` — docstrings to the new subject; the probe path is
  accepted only here.
- `ServiceConfig` (one dependency service): `name: str`, `kind: str`, `image: str | None =
  None`, `topics: list[TopicConfig] = []`, `probe: ProbeConfig | None = None`, plus the D1
  model validator rejecting `probe.path is not None` with "the probe path is accepted only on
  the instance entry". The kind vocabulary (postgresql/kafka/vault/http) stays loader-validated
  (Task 4) — the model does not re-validate kinds.
- `SandboxConfig`: `instance: InstanceConfig`, `services: dict[str, ServiceConfig] = {}`,
  `data: StartupData = StartupData()`.
- `StartupData`: drop the `kafka` field entirely; field order vault → http → postgres.
- **Migration Ledger note (M-R3.4)**: from this task on, the engines/sandbox/plugin suites are
  known-red (they construct the old shapes) until their own tasks; the authoritative suites
  here are the four model suites (`test_instance.py`, `test_service.py`,
  `test_sandbox_config.py`, `test_startup_data.py`) — `test_loader.py` stays known-red until
  Task 4 (the loader still builds the old model kwargs).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 3 is being executed
- [x] **Contract tests** (rework `tests/sandbox/config/test_instance.py`, `test_service.py`,
  `test_sandbox_config.py`, `test_startup_data.py` — expected to fail now): new constructor
  shapes and property types for all four models; kw_only construction; facade importability
  (written first; failed on the old field sets before implementation — TDD red confirmed)
- [x] **REPL prototype (R4)**: in the venv REPL construct `InstanceConfig(image="my-service:latest",
  env={"A": "{{db.host}}"}, port=8080)` and with `probe=ProbeConfig(path="/healthz")`;
  `ServiceConfig(name="db", kind="postgresql")`, `ServiceConfig(name="events", kind="kafka",
  topics=[TopicConfig(name="orders.events", partitions=6)])`; observe the D1 rejection
  (`ServiceConfig(name="v", kind="vault", probe=ProbeConfig(path="/health"))` → ValidationError
  "the probe path is accepted only on the instance entry"); observe `StartupData.model_fields`
  order (vault, http, postgres) and the absence of a kafka field; then migrate
  (all constructions, defaults, the exact D1 rejection wording, its propagation through
  `SandboxConfig` nesting, and kw_only TypeError observed live in a venv heredoc REPL; then
  migrated)
- [x] **Code**: rewrite `goga_tool_pybuggy/sandbox/config/{instance,service,sandbox_config,startup_data}.py`
  to the shapes above (docstrings to the new subjects; D1 validator in `service.py`)
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/config/test_instance.py
  tests/sandbox/config/test_service.py tests/sandbox/config/test_sandbox_config.py
  tests/sandbox/config/test_startup_data.py -x -v` — all pass
  (44 passed; fresh-interpreter facade check ok — 7 names, field orders verified)
- [x] **Logic tests**: kw_only (positional raises `TypeError`); `env`/`services`/`topics` and
  the data sections default empty; `image`/`probe`/`path` default None; the D1 path rejection
  (message matched via `pytest.raises(..., match=)`); several services of one kind allowed in
  `services`; `StartupData` has no kafka field (`"kafka" not in StartupData.model_fields`)
- [x] **Debugging (authoritative scope, Migration Ledger)**: `.venv/bin/pytest
  tests/sandbox/config/test_instance.py tests/sandbox/config/test_service.py
  tests/sandbox/config/test_sandbox_config.py tests/sandbox/config/test_startup_data.py -x`
  green; `test_loader.py` is known-red until Task 4, engines/sandbox/plugin suites until their
  tasks — do not touch them
  (44 green; blast radius verified against the ledger — full tree still collects 1495 tests,
  loader/engines/sandbox/plugin suites red at runtime only, data suites unaffected at 64 green)
- [x] **Contract re-verification**: the four entity declarations hold — subjects swapped,
  constraints (path only on instance; kinds loader-validated), section order
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files
  (exit 0; one format drift in test_sandbox_config.py corrected via `ruff format` — all 8
  touched files format-clean)
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 4: `load_sandbox_config` rework — new path, top-level diagnostics, inline topics validation; shared fixture flip (TDD)

The loader rework plus the shared test fixture flip. Design test scenarios 1–15 land here.

**Contract entity**: `load_sandbox_config(path: str | None) -> config: SandboxConfig | None`
(`loader.py`) — the 8-step algorithm quoted verbatim in § Contract Surface.

**Usages relevant to this task:**
- `ruamel-yaml`: `YAML()` instance, `yaml.load(path)`, None-for-empty handling; validation on
  the parsed mapping before model construction; every `ValidationError` wrapped by
  `_build_model` into `ValueError(f"{location}: {scope}: {details}")` (D1 surfacing).
- `conventions`: `ValueError` messages naming the document location and the offending entry;
  `tmp_path` + `monkeypatch.chdir` for the document fixture (M-R2.6); parametrized boundaries
  (M-R2.5).

**Design details (binding; keep the helper skeleton `_parse_document`, `_read_*`,
`_build_model`, `_validate_placeholders` and change what follows):**
- `_DOCUMENT_PATH = Path(".goga") / "tools" / "pybuggy" / "sandbox.yml"`; `location =
  Path(path) if path is not None else Path.cwd() / _DOCUMENT_PATH`. Cwd-only, no upward search;
  absent → `None` (fully inert; a stale `.sandbox.yml` at the root is never read — silent by
  grooming decision).
- **Top-level key diagnostics** (new step after parse): `"service" in document` → `ValueError`
  "top-level key 'service' was renamed to 'instance'"; `"instances" in document` → "top-level
  key 'instances' was renamed to 'services'"; any key outside `{instance, services, data}` →
  "unknown top-level key '<key>' (supported keys: instance, services, data)". Every message is
  prefixed with the document location.
- `_read_instance` (was `_read_service`): requires `image`, `env`, `port` present; builds
  `InstanceConfig`; the optional `probe` mapping builds `ProbeConfig` (path allowed here).
- `_read_services` (was `_read_instances`): per name — non-empty string matching the template
  identifier grammar `[A-Za-z_][A-Za-z0-9_]*` (the existing `_INSTANCE_NAME` regex and its
  rationale comment — the placeholder name; a hyphenated name fails); entry mapping;
  `_validate_kind` (postgresql/kafka/vault/http; grpc → explicit "not supported yet"); topics:
  kafka entries require a **non-empty** `topics` list of mappings building `TopicConfig` —
  **D7: duplicate topic names within one entry are rejected** ("duplicate topic '<name>' — each
  topic name must be unique within the service entry"); non-kafka entries with a `topics` key →
  "topics are accepted only on kafka entries". Probe: optional, builds `ProbeConfig`; a probe
  `path` is rejected by the D1 model validator.
- `_read_data`: `_SECTION_KINDS = {"vault": "vault", "http": "http", "postgres": "postgresql"}`
  (kafka gone); a `kafka` key under `data` → "data.kafka was removed — declare topics inline on
  the kafka service entry"; unknown sections list the supported ones; targets must be
  configured services of the matching kind; the vault declaration shape check stays. The kafka
  spec-path resolution helper `_resolve_spec_path` is **deleted**.
- `_validate_placeholders` (renamed vocabulary only): instance env values against configured
  service names, same grammar, same messages modulo instance/services wording.
- Return `_build_model(SandboxConfig, {"instance": ..., "services": ..., "data": ...}, ...)`;
  the `logger.info` "sandbox document loaded" event stays.
- Shared fixture: `tests/sandbox/conftest.py` `sandbox_yaml` writes the document at
  `.goga/tools/pybuggy/sandbox.yml` under `tmp_path` (**creating the parent directories**)
  instead of the former root path; docstring updated (FakeEngine/FakeService vocabulary updates
  happen in their consuming tasks — Tasks 10–12).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 4 is being executed
- [x] **Contract tests** (rework `tests/sandbox/config/test_loader.py`): importable from the
  facade; signature `(path: str | None)`; returns `SandboxConfig | None`
  (reworked first; the logic tests failed against the old loader — TDD red confirmed — the 3
  contract tests pass unchanged since the signature never moved)
- [x] **REPL prototype (R4)**: in the venv REPL (with documents written under `/tmp`): parse a
  full valid document (instance + kafka service with topics + data.postgres) and observe the
  built model; walk each invalid variant (renamed keys, unknown key, kafka-without-topics,
  topics-on-postgresql, duplicate topics, probe path on service, probe bounds, data.kafka,
  unknown placeholder, hyphenated name, grpc kind) and read each `ValueError` message —
  location + offending entry in every one; prototype the empty-document path (parse → None →
  invalid document error naming the location); then migrate
  (fragments observed live first — pydantic error surfacing through the `_build_model` wrap
  (D1 wording, probe-bounds loc shapes, TopicConfig rejections), the diagnostics fragment,
  ruamel empty→None, name grammar; then the migrated loader re-verified against the full valid
  document and all 13 invalid variants + stale-root + defaults in a second heredoc REPL — every
  message carries location + offending entry)
- [x] **Code**: rewrite `goga_tool_pybuggy/sandbox/config/loader.py` per the design details —
  new `_DOCUMENT_PATH`, diagnostics step, `_read_instance`/`_read_services` (name grammar,
  kinds, topics with D7, probe), `_read_data` (no kafka, removed-section diagnostic),
  `_validate_placeholders` vocabulary; delete `_resolve_spec_path`
- [x] **Code**: flip the shared fixture `sandbox_yaml` in `tests/sandbox/conftest.py` to
  `.goga/tools/pybuggy/sandbox.yml` (parents created) with the docstring update
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/config/ -x -v` — pass
  (124 passed across the seven config suites; fresh-interpreter facade check ok — 7 names)
- [x] **Logic tests** (design scenarios 1–15, transferred verbatim — Setup / Input / Assertions):
  1. `test_load_resolves_document_under_tools_home` — tmp_path with the document at the new
     path (instance + one kafka service with topics + data.postgres), `monkeypatch.chdir`;
     `load_sandbox_config(None)` → `SandboxConfig` with `instance.image`,
     `services["events"].topics[0].name == "orders.events"`, `services["events"].topics[1].partitions
     == 6`, `data.postgres["db"] == [...]`; **no kafka attribute anywhere on `data`** (pins the
     new path resolution and the inline partitions default)
  2. `test_load_returns_none_without_document_and_ignores_stale_root_document` — tmp_path
     holding a stale `.sandbox.yml` at the root, no tools-home document → result is `None`;
     the root file is never opened (stale location fully silent — inertness criterion)
  3. `test_load_fails_naming_rename_for_service_key` — document with `service:` + `services:` →
     `pytest.raises(ValueError, match="renamed to 'instance'")`, message contains the document
     path
  4. `test_load_fails_naming_rename_for_instances_key` — same with `instances:` → match
     "renamed to 'services'"
  5. `test_load_fails_on_unknown_top_level_key` — document with `extra:` → match "unknown
     top-level key 'extra'" listing supported keys
  6. `test_load_fails_on_kafka_entry_without_topics` — kafka service entry without `topics` →
     match `services.events` + "topics"; nothing starts (pure load, no docker touched)
  7. `test_load_fails_on_topics_on_non_kafka_entry` — postgresql entry with `topics` → match
     "accepted only on kafka entries"
  8. `test_load_fails_on_duplicate_topic_names` — kafka entry with two `orders.events`
     declarations → match "duplicate topic 'orders.events'" (D7)
  9. `test_load_fails_on_probe_path_on_service` — vault service with `probe: {path: /health}`
     → match "probe path" + the entry scope (D1 surfacing)
  10. `test_load_fails_on_probe_bounds` — parametrized: `timeout: 0`, `interval: -1`,
      `interval: 60 > timeout: 30` → each fails naming the probe field (boundary table per
      M-R2.5); the legal boundary rides along as
      `test_load_accepts_interval_equal_to_timeout` — postgresql service `probe: {timeout:
      30.0, interval: 30.0}` → `config.services["db"].probe.timeout == 30.0` and `.interval ==
      30.0` (pins the legal edge of the validator comparator — prevents a `<=` → `<` regression
      that would reject valid documents)
  11. `test_load_fails_on_removed_kafka_data_section` — `data: {kafka: {...}}` → match
      "data.kafka was removed"
  12. `test_load_fails_on_placeholder_naming_unknown_service` — instance env `"{{nope.host}}"` →
      match "not configured" listing configured services
  13. `test_load_rejects_hyphenated_service_name` — `services: {my-db: ...}` → match the
      template-identifier grammar message (placeholders would break at render)
  14. `test_load_grpc_kind_fails_not_supported_yet` — kind grpc → match "not supported yet"
  15. `test_load_probe_defaults_applied` — instance probe `{}` and service probe `{timeout:
      45.0}` → `config.instance.probe.timeout == 30.0`, `interval == 0.5`, `path is None`;
      `config.services["db"].probe.timeout == 45.0` (defaults reproduce the established wait;
      partial override keeps the rest)

  (all 15 landed by name plus the retained branches — full-document model fidelity, required
  instance fields, missing instance section, unknown kind, data target unknown/wrong-kind,
  unparsable/empty document, malformed-entries table incl. non-list/non-mapping topics, name
  grammar table, placeholder grammar trio, vault declaration shape table)
- [x] **Debugging (authoritative scope)**: `.venv/bin/pytest tests/sandbox/config/ -x` green;
  reproduce any failure in the REPL with the exact fixture content first (M-R4.5); the
  activation/session-lifecycle/plugin suites are known-red until their tasks (Migration Ledger)
  (124 green; ledger blast radius verified — full tree collects 1511 tests, `test_loader.py`
  absent from the red list, data suites unaffected at 64 green, engines/sandbox-cell/plugin
  suites red at runtime only as scheduled)
- [x] **Contract re-verification**: the 8-step algorithm, requirements (validation completes
  before anything starts; every message names location + entry), and constraints (no
  defaulting/repairing; read nothing beyond the named document) hold
  (checked line-by-line against the `load_sandbox_config` CODEMANIFEST annotation; every step
  and requirement observed live in the second REPL pass)
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files
  (two E501s and format drift corrected via `ruff format` on the touched files; both gates
  exit 0; authoritative suite re-run green after the reformat)
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

---

### Task 5: `BaseEngine` — ServiceConfig, readiness bounds, the bounded probe loop; `build_engine`; `DataOperation` vocabulary (TDD)

The engines cell base flips to `ServiceConfig` and gains the two D5/D6 helpers every kind
engine reuses; `runtime.py` and `operation.py` follow the vocabulary. Design scenarios 16 and
23 land here.

**Contract entities**: `BaseEngine(config: ServiceConfig)` + `EngineError()` (`base.py`),
`build_engine(config: ServiceConfig) -> engine: BaseEngine` (`runtime.py`), `DataOperation`
(`operation.py`) — facade unchanged (11 names).

**Usages relevant to this task:**
- `conventions`: structured logging with the D8 extras (M-R1.5), type hints (M-R1.8),
  mock-free unit tests over fakes (M-R2.6).
- `testcontainers`: container lifecycle and the Ryuk cleanup safety net behind the explicit
  stop (journal, `_run_step` machinery, stop safety, `reserve_port` unchanged).

**Design details (binding):**
- Import swap: `from ..config.service import ServiceConfig`; `BaseEngine.__init__(self,
  config: ServiceConfig)`; docstrings/log extras renamed to the service vocabulary per D8:
  engines emit `extra={"service": name, "kind": kind}` and events "service starting" /
  "service ready" / "service stopped"; `DataOperation.instance` docstring and `EngineError`
  message wording "service '<name>'" follow; event names stay stable and unique.
- **D6 — `_readiness_bounds` property**: `from ..config import ProbeConfig`; returns
  `(probe.timeout, probe.interval)` of `self.config.probe or ProbeConfig()`. Single default
  source — no probe declared → 30.0 / 0.5 by construction.
- **D5 — `_probe_until(timeout, interval, attempt, failure)`**: private loop computing
  `deadline = monotonic() + timeout` internally: while `monotonic() < deadline` — run
  `attempt()`; on True return; sleep `interval`. Expiry raises `RuntimeError(f"{failure} within
  {timeout:g}s")`. The lifecycle wrappers (`_run_step("start failed at readiness wait", ...)`,
  `_run_step("reset failed at wipe", ...)`) convert it into `EngineError` naming the service,
  the lifecycle step, the waited check, and the expired deadline.
- `EngineError` docstring gains the deadline-expiry sentence; `start`'s Algorithm step 2
  wording (declared deadline/interval) reflected in the docstring; everything else (journal,
  `_run_step` machinery, `stop` safety, `reserve_port`) unchanged.
- `runtime.py`: `build_engine(config: ServiceConfig)`; `KIND_ENGINES` unchanged; docstring
  vocabulary; the "engine built" debug extra renamed to `service`.
- `operation.py`: docstring only — action set `insert` / `produce` / `put` / `stub`; the
  startup-only postgresql `sql` payload note stays.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 5 is being executed
- [x] **Contract tests** (rework `tests/sandbox/engines/test_base.py`, `test_runtime.py`,
  `test_operation.py`): `BaseEngine(config: ServiceConfig)` signature; `_readiness_bounds`
  returns `(float, float)`; `build_engine(config: ServiceConfig)`; `DataOperation` action
  vocabulary (`instance` = target service name)
  (reworked first; failed against the old code on the `InstanceConfig` constructor annotation —
  TDD red confirmed before implementation)
- [x] **REPL prototype (R4)**: in the venv REPL drive a minimal fake subclass on
  `ServiceConfig(name="db", kind="postgresql")`: read `_readiness_bounds` with and without a
  probe — `(30.0, 0.5)` / `(45.0, 1.0)`; call `_probe_until(0.2, 0.05, attempt=lambda:
  False, failure="db did not become ready")` with a wall-clock assertion (~0.2s) and read the
  expiry message ("within 0.2s"); call it with an attempt succeeding on the 3rd try and count
  sleeps; then migrate
  (observed live in a venv heredoc REPL: bounds (30.0, 0.5) / (45.0, 1.0); expiry message
  "db did not become ready within 0.2s" at 0.212s wall clock; 3 attempts → exactly 2 sleeps of
  the declared 0.05 interval; `{timeout:g}` renders 0.2 → "0.2", 30.0 → "30"; then migrated)
- [x] **Code**: rework `goga_tool_pybuggy/sandbox/engines/base.py` — ServiceConfig import and
  signature, `_readiness_bounds` (D6), `_probe_until` (D5), `EngineError` deadline clause, D8
  log vocabulary
- [x] **Code**: rework `runtime.py` (`build_engine(config: ServiceConfig)`, debug extra) and
  `operation.py` (docstring) to the vocabulary
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/engines/test_base.py
  tests/sandbox/engines/test_runtime.py tests/sandbox/engines/test_operation.py -x -v` — pass
  (54 passed across the three suites; fresh-interpreter facade + signature check ok — both
  `config` annotations are `ServiceConfig`, default bounds (30.0, 0.5) by construction)
- [x] **Logic tests** (scenarios 16, 23, transferred verbatim):
  16. `test_base_readiness_bounds_default_and_override` (test_base.py) — a minimal
      `ServiceConfig(name="db", kind="postgresql")` without probe, and one with
      `probe=ProbeConfig(timeout=45.0, interval=1.0)` on a stub engine → `_readiness_bounds`
      returns `(30.0, 0.5)` / `(45.0, 1.0)` (single default source — the default-equivalence
      criterion by construction); plus `_probe_until` unit coverage: expiry raises naming the
      failure and `{timeout:g}s`; success path returns on the first True attempt; the wrappers
      convert expiry into `EngineError` naming service, step, check, deadline
  23. `test_operation_has_no_spec_action` (test_operation.py) — the documented action set is
      exactly insert/produce/put/stub; asserted at the dispatch level: no `action == "spec"`
      branch and no `"spec"` entry in an `_execute` dispatch mapping anywhere in the engines
      package source (a raw substring grep over the package does NOT work — the retained
      `SPEC_MOUNT_DIR` constant and migration-note docstrings legitimately contain the word)
  (both landed by name plus the retained branches — `_probe_until` expiry wall-clock ≥ 0.2s
  and < 1.0s, first-True immediate return, interval sleep counting via a patched module
  `sleep`, start-wrapper and reset-wrapper `EngineError` conversions; the dispatch scan is an
  AST walk over every `_execute` method of the package with a coverage guard; enabling
  minimal deletion: `KafkaEngine._execute`'s spec no-op branch removed here — scenario 23
  requires no spec dispatch anywhere in the package while test_operation.py is authoritative
  from this task on; the remaining spec plumbing (`_spec_paths`, `_specs`, start's extraction,
  `_patch_specs`) stays untouched until Task 8)
- [x] **Debugging (authoritative scope)**: `.venv/bin/pytest tests/sandbox/config/
  tests/sandbox/engines/test_base.py tests/sandbox/engines/test_runtime.py
  tests/sandbox/engines/test_operation.py -x` green; kind-engine suites are known-red until
  Tasks 6–8 (Migration Ledger)
  (178 green; ledger blast radius verified — full tree collects 1521 tests, red list exactly
  the scheduled suites: kind engines + sandbox cell + plugin, all failing on the old
  constructor shapes at runtime/collection; data suites unaffected at 64 green)
- [x] **Contract re-verification**: base obligations (journal, lifecycle wrappers, stop
  safety), the deadline-expiry clause, and the D8 vocabulary hold
  (checked against the engines CODEMANIFEST annotations — `BaseEngine(config: ServiceConfig)`,
  the EngineError deadline sentence, `build_engine` carrying image/topics/probe, the
  DataOperation action set without spec)
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files
  (one PLW0108, one E501, and format drift in test_operation.py corrected; both gates exit 0;
  authoritative suites re-run green after the fixes)
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 6: `PostgresEngine` — engine-owned readiness bounded by the declared deadline (TDD)

The postgresql kind adopts D3: the module container's internal wait is disabled and the engine
probes psycopg itself inside the D5 loop. Design scenarios 20 and 21 land here.

**Contract entity**: `BaseEngine::PostgresEngine(config: ServiceConfig)` (`postgres.py`).

**Usages relevant to this task:**
- `testcontainers`: the postgres module container (image/env/port semantics, labels); §
  Verified External Facts 2 — `PostgresContainer._connect` constructs its `ExecWaitStrategy`
  internally with global-config bounds (re-confirm in the REPL per M-R4.5).
- `psycopg`: the engine-owned readiness probe `psycopg.connect(host, port, user, password,
  dbname, connect_timeout=2)`; autocommit session connection; `%s`-bound parameters; catalog
  TRUNCATE (unchanged).
- `conventions`: external dependency patched at the import point (M-R2.6).

**Design details (binding, D3):**
- A private `_PostgresContainer(PostgresContainer)` whose `_connect` is a no-op — docstring
  "readiness probing is engine-owned, bounded by the declared deadline".
- A real `PostgresEngine._wait_ready` probing `psycopg.connect(host, port, user, password,
  dbname, connect_timeout=2)` in the D5 loop with the declared bounds (`_readiness_bounds`),
  **closing the probe connection on success** (the session connection opens in `_open_plane`
  as today). This honors both the declared timeout and the declared interval (an
  executor-wrapped blocking `start()` could honor only the timeout), keeps the module
  container, and checks the same condition — the server accepts connections — with the
  data-plane driver. Default equivalence: with no probe the loop runs at 30.0/0.5 (the
  contract fixes the declared default at 30.0 for every target); the success path is unchanged
  and the deadline is uniform across kinds.
- Vocabulary swap in docstrings/logs; `_build_container` builds `_PostgresContainer` with the
  same pinned image/credentials/labels; the rest (symbol stream, `$ref`/`$lookup` resolution,
  catalog-driven truncate wipe) is untouched by this iteration.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 6 is being executed
- [x] **Contract tests** (rework `tests/sandbox/engines/test_postgres.py`): `PostgresEngine`
  importable from the facade; subclasses `BaseEngine`; constructed with `ServiceConfig`
  (reworked first; 8 failures confirmed against the old code — the missing
  `_PostgresContainer`/`_wait_ready` surface and the `InstanceConfig` constructor annotation —
  TDD red before implementation)
- [x] **REPL prototype (R4)**: re-confirm the external fact live (M-R4.5): `.venv/bin/python -c`
  inspecting `testcontainers.postgres.PostgresContainer._connect` source (the internal
  `ExecWaitStrategy` construction); in the REPL drive `_probe_until` with a stubbed
  `psycopg.connect` (monkeypatched in the probe script) always raising vs succeeding on the
  3rd call — count sleeps of the declared interval; then migrate (docker unavailable — the
  live container path is carried by the `requires_docker`-gated tests)
  (external fact re-confirmed against the installed wheel — `_connect` builds its
  `ExecWaitStrategy` from global config; `_PostgresContainer` construction verified
  daemon-safe and the no-op `_connect` observed; expiry message observed at 0.231s wall
  clock over 4 attempts; 3rd-call success produced exactly 2 sleeps of 0.05 with the probe
  connection closed; docker IS available here, so the live path also ran for real — see the
  docker-gated suites below)
- [x] **Code**: rework `goga_tool_pybuggy/sandbox/engines/postgres.py` — `_PostgresContainer`
  subclass with no-op `_connect`, `_wait_ready` on the D5 loop with the psycopg probe
  (connect_timeout=2, close on success), vocabulary swap
  (import/signature swap to `ServiceConfig`; `PROBE_CONNECT_TIMEOUT = 2` constant; D8 log
  extras `{"service": ...}`; `_symbol_value` message now names "the instance under test")
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/engines/test_postgres.py -x
  -v` — pass
  (53 passed incl. the 10 docker-gated live-container cases — the real `_PostgresContainer`
  with disabled internal wait boots and the engine-owned psycopg probe brings it to
  readiness; fresh-interpreter check ok — `ServiceConfig` annotation, default bounds
  (30.0, 0.5) by construction, `_wait_ready` overridden)
- [x] **Logic tests** (scenarios 20, 21, transferred verbatim — docker-gated or monkeypatched
  connect):
  20. `test_postgres_readiness_deadline_expires_as_engine_error` — probe `timeout=0.2,
      interval=0.05`, a `psycopg.connect` stub always raising; `engine.start(...)` →
      `EngineError` (via the step wrapper) naming the service, "readiness", and the 0.2s
      deadline (expiry surfaces as `EngineError`, never a hang)
  21. `test_postgres_bounded_wait_honors_interval` — connect stub succeeding on the 3rd call;
      assert ≥2 sleeps of the declared interval and success (bounds reach the loop)
  (both landed by name plus a third retained branch — a driver-shaped probe failure is one
  failed attempt, not an error; scenario 21 also pins the probe kwargs — mapped address,
  pinned credentials, `connect_timeout=2` — and the closed successful probe connection;
  scenario 20 also asserts the failed start stops the container and clears the reference)
- [x] **Debugging (authoritative scope)**: `.venv/bin/pytest tests/sandbox/config/
  tests/sandbox/engines/ --ignore=tests/sandbox/engines/test_http.py
  --ignore=tests/sandbox/engines/test_kafka.py --ignore=tests/sandbox/engines/test_vault.py -x`
  green (those three suites are known-red until Tasks 7–8, Migration Ledger; without the
  ignores `-x` would stop at `test_http.py` — alphabetically before this task's own
  `test_postgres.py`)
  (271 green; ledger blast radius verified — full tree collects 1527 tests, red files exactly
  the scheduled suites: engines http/kafka/vault + sandbox cell + plugin; data suites
  unaffected)
- [x] **Contract re-verification**: module container semantics preserved; readiness bounded by
  declaration; parameter binding and catalog wipe untouched
  (checked against the `PostgresEngine` CODEMANIFEST annotation — module container with the
  pinned image, readiness within the declared timeout/interval, autocommit session
  connection, catalog-driven truncate, bound parameters; the live docker-gated roundtrip is
  the end-to-end evidence)
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files
  (both gates exit 0 on the first run — no findings, no format drift)
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 7: `VaultEngine` and `HttpEngine` — declared-bounds readiness on the D5 loop (TDD)

Both HTTP-plane engines rewrite `_wait_ready` onto D5 with the declared bounds and delete
their module constants. Design scenario 22 lands here.

**Contract entities**: `BaseEngine::VaultEngine(config: ServiceConfig)` (`vault.py`),
`BaseEngine::HttpEngine(config: ServiceConfig)` (`http.py`).

**Usages relevant to this task:**
- `vault-dev`: dev-mode contract, `/v1/sys/health` readiness, KV v2 paths, restart wipe.
- `wiremock`: admin mappings API, mappings reset, readiness `GET /__admin/health` with the
  404 → `GET /__admin/mappings` fallback (kept).
- `requests`: probe loops via `requests.get(url, timeout=5)`.
- `conventions`: external dependency patched at the import point (M-R2.6); wall-clock
  assertions with tolerance.

**Design details (binding):** `_wait_ready` rewritten onto D5 with declared bounds (health 200
/ admin-ready checks unchanged, including the wiremock 404→mappings fallback); the module
constants `READINESS_TIMEOUT`/`READINESS_INTERVAL` are **deleted** from both files; vocabulary
in docstrings/logs; `address.py` and the cell `__init__.py`: docstring vocabulary only (facade
unchanged); everything else unchanged.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 7 is being executed
- [x] **Contract tests** (rework `tests/sandbox/engines/test_vault.py`, `test_http.py`):
  constructed with `ServiceConfig`; readiness driven by the declared bounds
  (reworked first; 6 readiness/bounds failures confirmed against the old code — TDD red
  before implementation; the docker-gated live cases stayed green throughout)
- [x] **REPL prototype (R4)**: in the REPL drive `_probe_until` with a patched `requests.get`
  returning a failing response object and probe `{timeout: 0.3, interval: 0.05}` — observe
  expiry within ~0.3s and the message naming the endpoint; then migrate
  (observed live in a venv heredoc REPL: expiry at 0.344s wall clock over 6 attempts with the
  full chain "service 'secrets': start failed at readiness wait: health endpoint
  http://…/v1/sys/health did not succeed within 0.3s"; 3rd-call success → exactly 2 sleeps of
  the declared 0.05 interval; then migrated)
- [x] **Code**: rewrite `_wait_ready` in `vault.py` and `http.py` onto the D5 loop; delete the
  `READINESS_*` constants; vocabulary swap; vocabulary touch-ups in `address.py` and the cell
  `__init__.py` docstrings
  (both loops probe at the declared `_readiness_bounds` with the wiremock 404→mappings
  fallback kept; `import time` and both constants removed; D8 extras `{"service": ...}`
  throughout; module/class/attribute docstrings to the service vocabulary)
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/engines/test_vault.py
  tests/sandbox/engines/test_http.py tests/sandbox/engines/test_address.py
  tests/sandbox/engines/test_refs.py -x -v` — pass
  (87 passed, 0 skipped — the docker-gated vault/wiremock live cases ran for real; one
  float-drift arithmetic expectation in the deadline tests fixed after an M-R4.5 REPL
  reproduction: 4 accumulated 0.05 sleeps land at 100.19999… < the 100.2 deadline, so the
  sleep-count assertion now pins "every sleep equals the declared interval, ≥4 sleeps")
- [x] **Logic tests** (scenario 22, transferred verbatim): `test_vault_and_http_wait_use_declared_bounds`
  — with a patched `requests.get` failing: probe `{timeout: 0.3, interval: 0.05}` →
  `EngineError` within ~0.3s (wall clock assertion with tolerance) naming the endpoint —
  expiry clause for both kinds; with no probe the loop constants equal the former 30/0.5
  (regression: default equivalence)
  (landed by name in test_vault.py driving both kinds — wall clock 0.25–2.0s window,
  endpoint-naming `EngineError` matches, `READINESS_*` absence pinned, and
  `_readiness_bounds == (30.0, 0.5)` for both kinds without a probe)
- [x] **Debugging (authoritative scope)**: `.venv/bin/pytest tests/sandbox/config/
  tests/sandbox/engines/ --ignore=tests/sandbox/engines/test_kafka.py -x` green
  (`test_kafka.py` is known-red until Task 8, Migration Ledger; without the ignore `-x` would
  stop there — alphabetically before this task's own `test_vault.py`)
  (318 green; ledger blast radius verified — full tree collects 1532 tests, red files exactly
  the scheduled suites: engines kafka + sandbox cell + plugin; data suites unaffected)
- [x] **Contract re-verification**: dev-mode contract, KV v2 plane, mappings reset, fallback
  readiness — all unchanged except the bounds source
  (checked against the VaultEngine/HttpEngine CODEMANIFEST annotations and re-verified in a
  fresh interpreter — facade byte-stable at 11 names, `ServiceConfig` constructor
  annotations, health/admin readiness within the declared deadline at the declared interval)
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files
  (two PT018s in the scenario-22 test split into single asserts; both gates exit 0;
  authoritative suites re-run green after the fix)
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 8: `KafkaEngine` — inline topics, in-memory AsyncAPI generation, produce gate (TDD)

The largest engine change: the startup spec plumbing is deleted; topics come from the
declaration; the document is generated in memory (D4), transferred through the docker API, and
the produce gate (D9) plus the fail-fast empty-declaration check land. Design scenarios 17,
18, 19 land here.

**Contract entity**: `BaseEngine::KafkaEngine(config: ServiceConfig)` (`kafka.py`).

**Usages relevant to this task:**
- `mokapi`: § Verified External Facts 1 — topics from AsyncAPI channels, partitions from the
  kafka channel binding (default 1); AsyncAPI 2.6 channel key = topic name; no declared
  messages → no validators → arbitrary produced values pass (re-confirm against the mokapi
  cook; live probing docker-gated).
- `testcontainers`: `DockerContainer` + `with_exposed_ports` + `with_command` +
  `with_copy_into_container(document_bytes, target)` (docker-API transfer, Transferable
  bytes); fixed reserved port; restart-based wipe.
- `ruamel-yaml`: serialize the generated document with the existing `YAML()` into `StringIO`,
  encode UTF-8.
- `kafka-python`: producer lifecycle unchanged (`send` + `future.get(timeout=
  DELIVERY_TIMEOUT)`, flush batch boundary, close at stop).

**Design details (binding):**
- The startup spec plumbing is deleted (`_spec_paths`, `_specs`, `start`'s spec extraction,
  the `spec` branch of `_execute`, `_patch_specs`).
- `start` fails fast on an empty declaration **before** the container build:
  `EngineError("service '<name>': no topics declared on the kafka service entry — declare
  topics inline in the sandbox document; without topics the mock opens no kafka listener")`.
  Document validation rejects this first; the engine check is defense in depth (the
  manifest's "empty topic declaration is an invalid state — the engine fails fast").
- `_build_container`: `host = DockerClient().host()`, `port = reserve_port()`,
  `self._container_port = port`; the AsyncAPI document is generated **in memory** from
  `self.config.topics` with the final mapped address; transferred via
  `container.with_copy_into_container(document, target)` with `target =
  f"{SPEC_MOUNT_DIR}/sandbox.asyncapi.yaml"`; `container.with_command([target])`; HTTP port
  exposed, fixed port bound both sides, labels, network attach — the patched-spec pipeline
  (mapped reserved address → servers carry it → transfer → start argument) holds with the
  patch folded into generation.
- **D4 — generated document shape**: AsyncAPI **2.6.0** (channel key = topic name — the
  simplest form mokapi supports, no `address` indirection): `info {title: <service name>,
  version: "1.0.0"}`, one server `kafka: {protocol: kafka, host: "<host>:<reserved port>"}`,
  one channel per topic `<topic name>: {bindings: {kafka: {partitions: <partitions>}}}` — **no
  messages/payload schemas**. Serialized to UTF-8 bytes with the existing ruamel `YAML()` into
  a `StringIO`; never written to disk anywhere. The AsyncAPI version is an implementation
  detail; the docker-gated engine test verifies the topology boots and the partitions arrive.
- `_wait_ready`: the `/health` loop rewritten onto D5 with declared bounds.
- `_execute` (produce): validates the topic first — **D9**: `topic not in {t.name for t in
  self.config.topics}` → `EngineError("service '<name>': topic '<topic>' is not declared on
  the kafka service entry (declared topics: <sorted names>)")`; otherwise send +
  `future.get(timeout=DELIVERY_TIMEOUT)` as today. The flush batch boundary stays.
- `_wipe` restart path: unchanged mechanics; the re-wait runs through the bounded
  `_wait_ready`.
- Serializers, producer lifecycle, constants other than readiness — unchanged.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 8 is being executed
- [x] **Contract tests** (rework `tests/sandbox/engines/test_kafka.py`): `KafkaEngine`
  importable; subclasses `BaseEngine`; constructed with a topics-carrying `ServiceConfig`
  (reworked first; collection failed on the missing `_generate_document` import against the
  old code — TDD red confirmed before implementation)
- [x] **REPL prototype (R4)**: in the venv REPL build the generator over `[("orders.events",
  1), ("payments.events", 6)]` with host `localhost`, port `9093`; serialize with ruamel into
  `StringIO` and parse back — assert the D4 shape (`asyncapi == "2.6.0"`, server entry,
  channel keys, partitions, **no `messages` anywhere**); re-confirm `with_copy_into_container`
  accepts bytes (inspect the installed testcontainers signature, M-R4.5); then migrate
  (generator prototyped and roundtrip-verified live; `with_copy_into_container` signature
  re-confirmed against the installed wheel — `transferable: Transferable` with bytes legal.
  **Live deviation discovered and resolved (M-R4.5 debugging)**: docker-gated runs booted no
  kafka listener — mokapi 0.52 binds the default 9092 and declares no topics under the 2.6
  grammar (`host` field, channel key = topic). Four document variants were probed against the
  live container reading its stderr: 2.6+host, 2.6+host+binding-topic, 2.6+url (boots, but
  `partitions_for_topic` empty — auto-create only), 2.6+url+binding-topic (bootstrap timeout).
  Only the **3.0 grammar** — `servers.<name>.host` (unchanged from D4) + channel `address` =
  topic name (the design's own external-fact 3.0 form) — boots the declared topology with all
  6 partitions arriving. Applied per the design's stated escape hatch "the AsyncAPI version is
  an implementation detail; the docker-gated engine test verifies the topology boots and the
  partitions arrive"; the CODEMANIFEST annotation (in-memory generation, servers rewritten to
  the mapped address) is fully honored)
- [x] **Code**: rework `goga_tool_pybuggy/sandbox/engines/kafka.py` — delete the spec
  plumbing; add the private in-memory document generator (D4); fail-fast empty-topics check;
  `_build_container` with docker-API transfer and command argument; D5 `_wait_ready`; D9
  produce gate; bounded re-wait in `_wipe`
  (`_spec_paths`/`_specs`/`_patch_specs`/`_resolve` plumbing and `pathlib`/`time` imports
  deleted; `READINESS_TIMEOUT`/`READINESS_INTERVAL` deleted; `_generate_document` emits the
  live-verified 3.0 shape with `ASYNCAPI_VERSION`/`DOCUMENT_VERSION`/`DOCUMENT_NAME`
  constants; `start` fails fast with the verbatim message before `super().start()`; the
  target `/data/sandbox.asyncapi.yaml` is both the transfer destination and the command
  argument; D8 extras `{"service": ...}` throughout)
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/engines/test_kafka.py -x
  -v` — pass
  (30 passed, 0 skipped — the docker-gated live cases ran for real: declared topology boots,
  `payments.events` reports exactly partitions {0..5}, produce + restart-reset + baseline
  replay over the generated document; fresh-interpreter check ok — `ServiceConfig`
  constructor annotation, `_wait_ready` overridden, default bounds (30.0, 0.5))
- [x] **Logic tests** (scenarios 17, 18, 19, transferred verbatim):
  17. `test_kafka_generated_document_shape` (unit) — `ServiceConfig` kafka with topics
      `[("orders.events", 1), ("payments.events", 6)]`; call the private generator with host
      `localhost`, port `9093`; assertions on the parsed document: `asyncapi == "2.6.0"`;
      `servers["kafka"] == {protocol: kafka, host: "localhost:9093"}`; channel keys are the
      topic names; `channels["payments.events"]["bindings"]["kafka"]["partitions"] == 6`;
      `orders.events` carries partitions 1; **no `messages` anywhere** (D4 — the no-schema
      rule: schema validation would reject arbitrary produced values)
  18. `test_kafka_produce_into_undeclared_topic_fails` (docker-gated) — started engine with
      declared topics; `apply` of a produce for `nope.topic` → `EngineError` matching "not
      declared" and listing `orders.events` (D9 — readable failure naming service and
      declared topics)
  19. `test_kafka_engine_fails_fast_without_topics` — `ServiceConfig` kafka with `topics=[]`
      (bypassing the loader) → `start` raises `EngineError` mentioning "no topics" **before
      any docker call** (assert via a build-spy if unit, or docker-gated; defense in depth
      behind the loader)
  (all three landed by name plus the retained branches — scenario 17 asserts the 3.0 shape
  with a docstring recording the live 2.6-rejection evidence, plus a never-written-to-disk
  test spying on write-mode `open`; scenario 18 landed both as a unit case (exact D9 message
  with sorted declared topics, producer untouched) and live; scenario 19 via a build spy
  asserting zero container constructions and `_container is None`; also retained — build
  pinned-image/labels/fixed-port/image-override, generated-document transfer + command,
  started-engine producer bootstrap, readiness success/expiry/default-bounds, produce
  send/await, flush boundary incl. empty group, wipe restart/re-wait/producer rebuild/close
  safety, start-journal, reset-replay, stop-twice)
- [x] **Debugging (authoritative scope)**: `.venv/bin/pytest tests/sandbox/config/
  tests/sandbox/engines/ -x` green (engines cell complete; docker-gated cases skip cleanly)
  (348 green — config 124 + engines 224 with every live case executing; two test-side bugs
  fixed after REPL reproduction — an address assertion before start and a missing container
  double in the reset test; ledger blast radius verified — full tree collects 1537 tests, red
  files exactly the scheduled suites: sandbox cell + plugin, all on the old shapes)
- [x] **Contract re-verification**: the KafkaEngine annotation holds — generated document
  internal (never written to the consumer repository), bootstrap = metadata = one address,
  restart wipe with surviving binding + document, delivery confirmed at the batch boundary
  (checked against the engines CODEMANIFEST annotation clause by clause; the in-memory
  guarantee pinned by the write-mode `open` spy; the one-address criterion live-verified —
  producer bootstraps, metadata advertises, and the env placeholders resolve to the same
  reserved mapped host:port)
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files
  (one unused `socket` import removed; both gates exit 0; authoritative suites re-run green
  after the fix)
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

---

### Task 9: Data cell — `services(...)` type tightening and declared-topics vocabulary (TDD)

The data cell changes are annotation- and docstring-level: the preset decorator's value
annotation is corrected to the tightened contract type; `produce` documents the declared-topics
rule; the views/batch docstrings follow the service vocabulary. Design scenario 29 lands here.

**Contract entities**: `services(...presets: dict[str, dict[str, list[dict[str, object]]]])`
(`presets.py`), `KafkaInstance.produce` (`kafka.py`); unchanged-but-touched: `PostgresInstance`
/ `VaultInstance` / `HttpInstance` / `DataBatch` docstrings.

**Usages relevant to this task:**
- `conventions`: type-hint grammar (M-R1.8 — the `**presets` annotation is the documented
  exception), docstring rules (M-R1.7), mock-free unit tests (M-R2.6).

**Design details (binding):** `presets.py`: the decorator's value annotation is
`**presets: dict[str, dict[str, list[dict[str, object]]]]` — the **tightened contract type**
that finally matches the runtime nesting (kind → service name → declaration list, the shape
`activation._enqueue_presets` already iterates); docstring vocabulary (service); validation
logic unchanged (supported kinds, declaration shape, `validate_insert_rows` on postgresql
rows, marker attach). `kafka.py`: `produce` docstring — the topic must be declared on the
kafka service entry of the sandbox document. `postgres.py` / `vault.py` / `http.py` views,
`batch.py`: docstring vocabulary ("started postgresql service", "the value the env
placeholders of the instance under test resolve to", "per service"); no behavior change.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 9 is being executed
- [x] **Contract tests** (rework `tests/sandbox/data/test_presets.py` + views tests where
  docstrings/assert vocabulary changed): `services` accepts the nested dict shape; the four
  view factories keep their signatures
  (annotation contract test added — `parameters["presets"].annotation ==
  dict[str, dict[str, list[dict[str, object]]]]`; TDD red confirmed against the old
  `dict[str, list[...]]` annotation before implementation; the four view suites keep their
  contract signatures untouched; conftest fixture docstring to "service address")
- [x] **REPL prototype (R4)**: in the venv REPL apply `services(postgresql={"db": [{"table":
  "orders", "rows": [...]}]})` to a dummy function and inspect the marker + the validated
  shape; apply an unsupported kind and read the error listing the supported kinds; then
  migrate
  (observed live in a venv heredoc REPL: exactly one `pybuggy_services` marker carrying the
  nested payload unchanged, function intact, unsupported-kind error listing all four kinds;
  the stale annotation read out pre-migration; then migrated)
- [x] **Code**: correct the `presets.py` annotation; docstring vocabulary across
  `presets.py`, `kafka.py` (declared-topics note), `postgres.py`, `vault.py`, `http.py`,
  `batch.py`
  (annotation tightened to the contract nesting; docstrings to "kind -> service name ->
  declaration list", "started <kind> service", "the env placeholders of the instance under
  test resolve to", "per service"; `produce` topic note now "must be declared on the kafka
  service entry of the sandbox document"; decoration-time error wording "must map service
  names"; zero behavior change — validation logic and marker attach untouched)
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/data/ -x -v` — pass
  (66 passed — 64 retained + 2 new; fresh-interpreter check ok — facade 6 names, tightened
  annotation string verified)
- [x] **Logic tests** (scenario 29, transferred verbatim): `test_presets_type_and_enqueue`
  (test_presets.py + the activation loop) — `services(...)` with the nested dict shape marks
  the test; enqueue resolves names against services and orders preset declarations ahead of
  in-test operations (the enqueue half asserts fully in Task 12's activation rework; here the
  decoration-time validation and marker shape)
  (landed by name — the nested postgresql+kafka shape reaches the marker unchanged and the
  marked test still executes; enqueue half deferred to Task 12 as planned)
- [x] **Debugging (authoritative scope)**: `.venv/bin/pytest tests/sandbox/config/
  tests/sandbox/engines/ tests/sandbox/data/ -x` green
  (414 green = 124 config + 224 engines + 66 data, docker-gated live cases executing; ledger
  blast radius verified — full tree collects 1539, and with the scheduled sandbox-cell/plugin
  suites ignored the remaining 1337 all pass)
- [x] **Contract re-verification**: laziness contract intact (nothing executes at declaration
  time); preset nesting matches the contract type
  (checked against the data CODEMANIFEST — services annotation, produce declared-topics note,
  view/property docstring wording matched clause by clause; vocabulary grep over the cell
  clean: only the contract-kept class names, the DataOperation field, and "instance under
  test" remain; laziness pinned by the retained declaration-only suites)
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files
  (both gates exit 0 on the first run — no findings, no format drift across all 8 touched
  files)
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

---

### Task 10: `ServiceContainer` — probe-bounded readiness with the EngineError expiry (TDD)

The instance container flips to the new `InstanceConfig` and the D10 readiness: port-only
default or health-path loop, both bounded by the declared probe, expiring as `EngineError`.
Design scenarios 26 and 27 land here.

**Contract entity**: `ServiceContainer(config: InstanceConfig)` (`service_container.py`) —
properties `host` / `port`; methods `start(env, network)`, `stop()`, `alive()`, `logs()`.

**Usages relevant to this task:**
- `testcontainers`: the generic container, labels, port publish, removal guarantee (unchanged).
- `requests`: health-path probing (`requests.get(url, timeout=5)`, 2xx success).
- `conventions`: external boundaries patched at the import point (M-R2.6) — FakeSocket /
  patched requests in unit tests.

**Design details (binding, D10):** `from ..config import InstanceConfig` (the under-test
entry); `probe = self.config.probe or ProbeConfig()`; path-only semantics: `probe.path is
None` → TCP port loop, else health-endpoint 2xx loop at `http://{host}:{port}{path}`; both
loops run the declared `probe.timeout` / `probe.interval` (the D5 loop is engines-internal —
`ServiceContainer` implements its own bounded loop with the same deadline/interval semantics).
Expiry raises **`EngineError`** directly (imported from `..engines`) — "the instance under
test (image <image>) did not become ready: <check description> within <timeout>s" — an
actionable failure naming the instance, the waited check, and the expired deadline; never a
hang. The `RuntimeError` module constants for readiness are **replaced by the probe values**
(deleted). Everything else (labels, port publish, env application, `alive`/`logs`, stop
safety) unchanged; vocabulary in docstrings/logs ("instance").

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 10 is being executed
- [x] **Contract tests** (rework `tests/sandbox/test_service_container.py`): constructed with
  the new `InstanceConfig`; `EngineError` importable and raised on expiry
  (reworked first; the constructor-annotation test failed against the old
  `ServiceConfig`-typed parameter — TDD red confirmed before implementation)
- [x] **REPL prototype (R4)**: in the REPL (patched socket/requests) drive both loops —
  port-only with the default probe (30.0/0.5 constants asserted) and `path="/healthz"` with a
  2xx stub; drive the expiry `{timeout: 0.2, interval: 0.05}` with a never-opening port and
  read the `EngineError` message (image, port check, deadline); then migrate
  (all legs observed live in venv heredoc REPLs over fakes: default-port expiry at 60
  attempts / 60 sleeps of 0.5 with the "within 30s" message; 3rd-try success with exactly 2
  sleeps; health 2xx at declared 45.0/1.0 bounds with 3 probes of `timeout=5`; health expiry
  at 0.25/0.125; real-wall-clock expiry of 0.2/0.05 at 0.222s raising `EngineError`; then
  migrated and re-verified in a fresh interpreter — annotation, EngineError identity,
  constants gone, both expiry messages reproduced)
- [x] **Code**: rework `goga_tool_pybuggy/sandbox/service_container.py` per D10; delete the
  readiness `RuntimeError` constants
  (`from .config import InstanceConfig, ProbeConfig` + `from .engines import EngineError`;
  `READINESS_TIMEOUT`/`READINESS_INTERVAL` deleted; `_wait_ready` reads
  `probe = self.config.probe or ProbeConfig()` and dispatches on `probe.path is None`; both
  loops bounded by the declared timeout/interval raising the D10 `EngineError`; log events
  "instance starting"/"instance ready"/"instance stopped" with image extras — distinct from
  the engine events, stable and unique)
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/test_service_container.py
  -x -v` — pass
  (26 passed incl. both docker-gated live cases executing for real — default port branch and
  health-path branch against the pinned wiremock image; fresh-interpreter checks ok)
- [x] **Logic tests** (scenarios 26, 27, transferred verbatim):
  26. `test_service_container_port_only_default_and_health_path` — FakeSocket/requests: no
      probe → TCP loop with 30.0/0.5; probe with `path: /healthz` → GET loop until 2xx;
      assertions on probe calls and bounds (the path knob applies only to the instance entry;
      port-only default preserved)
  27. `test_service_container_deadline_expires_as_engine_error` — probe `{timeout: 0.2,
      interval: 0.05}`, port never opens → `EngineError` naming the image, the port check,
      and the deadline; and never a bare `RuntimeError` (assert `isinstance(exc,
      EngineError)`) — the new `ServiceContainer` contract clause
  (both landed by name — scenario 26 pins the default bounds via expiry at 60 sleeps of 0.5
  plus the success path and the declared-bounds GET loop; scenario 27 asserts the full
  escaped D10 message, `type(exc) is EngineError`, and the 0.2–2.0s wall-clock window on the
  real clock; also retained — port/health deadline variants at exact-binary intervals, the
  refused-health-probe-is-one-attempt branch, and the full build/liveness/logs/stop suites
  on the new shapes)
- [x] **Debugging (authoritative scope)**: `.venv/bin/pytest tests/sandbox/config/
  tests/sandbox/engines/ tests/sandbox/data/ tests/sandbox/test_service_container.py -x` green
  (440 green = 124 config + 224 engines + 66 data + 26 service container, live cases
  executing; ledger blast radius verified — full tree collects 1543, red files exactly the
  scheduled suites: sandbox test_sandbox/test_baseline + test_activation + plugin +
  test_session_lifecycle, all on the old shapes)
- [x] **Contract re-verification**: readiness-before-return, never-restart-on-reset,
  died-instance detectability unchanged
  (checked against the ServiceContainer CODEMANIFEST annotation clause by clause —
  InstanceConfig constructor, the EngineError expiry sentence, sandbox labels, removal on
  stop, died-instance detectability; no restart path exists on the container)
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files
  (one N813, one F401, and one format drift corrected in the test file; both gates exit 0;
  authoritative suites re-run green after the fixes)
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 11: `Sandbox` — wiring swap, fixed startup-data order, private rename (TDD)

The session runtime core flips to the new field names, drops the kafka section from
`_startup_operations`, and follows the D8 vocabulary. Design scenarios 24 and 25 land here.

**Contract entity**: `Sandbox(config: SandboxConfig)` (`sandbox.py`) — the `start()`
Algorithm quoted verbatim in § Contract Surface.

**Usages relevant to this task:**
- `sandbox-file` (imported usage): the configuration semantics — startup sections in the
  fixed order vault → http → postgres; kafka services get no startup ops.
- `data-operations` (imported usage): the laziness contract behind `apply_pending`.
- `jinja2`: `Environment(undefined=StrictUndefined)`, context `{service: {"host", "port"}}`,
  per-value render — `render_service_env` takes a vocabulary-only touch here, behavior
  unchanged.
- `conventions`: mock-free unit tests over the conftest fakes (M-R2.6); D8 log extras.

**Design details (binding):**
- Wiring swap: `self.engines = {name: build_engine(service_config) for name, service_config in
  config.services.items()}`; `self.service = ServiceContainer(config.instance)` (the attribute
  keeps its name — private vocabulary; docstrings say "the instance under test").
- `_startup_operations(name)`: vault section → `put` operations, http section → `stub`
  operations, postgres section → `insert`+`sql` operations — **no kafka section**; the fixed
  order is vault → http → postgres within each engine's startup list; kafka services simply
  receive an empty list (their topology comes from the declaration at container build).
- `start` Algorithm unchanged otherwise (check_runtime → network → engines+startup data →
  `render_service_env` → `ServiceContainer.start` → logging); the readiness sentence in the
  docstring reflects the probe-bounded wait.
- `_require_instance` → `_require_service` (private rename; same error shape listing
  configured services); view factories unchanged publicly.
- `ensure_service` / `clear` / `stop` / `apply_pending` / `new_test_batch`: vocabulary only
  ("instance" for the under-test container, "service" for engines); log extras follow D8.
- `base_url` unchanged. `baseline.py` / `env_render.py` / cell `__init__.py`: vocabulary only;
  facade unchanged.
- The `FakeEngine`/`FakeService` doubles in `tests/sandbox/conftest.py` follow the service
  vocabulary (docstrings updated here — they are this task's doubles).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 11 is being executed
- [x] **Contract tests** (rework `tests/sandbox/test_sandbox.py`; vocabulary touch-ups in
  `test_baseline.py`, `test_env_render.py`): `Sandbox(config)` over the new `SandboxConfig`;
  view factories and lifecycle surface unchanged
  (reworked first; the wiring tests failed against the old code on
  `SandboxConfig object has no attribute 'instances'` — TDD red confirmed; the four
  shape-neutral contract tests pass unchanged since the public surface never moved)
- [x] **REPL prototype (R4)**: in the REPL build a `SandboxConfig` with vault + http + kafka +
  postgres services over FakeEngine/FakeService (patched runtime probe and container) and
  drive `start()` — observe engines built from `config.services` in declaration order, the
  container from `config.instance` started last with the rendered env, and each engine's
  startup list ordered put → stub → sql for its kind with kafka empty; then migrate
  (observed live in a venv heredoc REPL over scratch recording fakes: declaration order
  secrets → payments → events → db, container config identity `is config.instance`,
  rendered env with all four placeholders resolved, kafka startup list empty, one name under
  all three data sections assembling put → stub → sql, `StartupData` carrying no kafka
  field, and the `_require_service` error shape "no postgresql service named 'ghost';
  configured services: …"; then migrated and re-verified in a fresh interpreter — facade 6
  names, `_require_service` present / `_require_instance` gone, no `data.kafka` or old
  field reads in the module source)
- [x] **Code**: rework `goga_tool_pybuggy/sandbox/sandbox.py` per the design details; update
  `_startup_operations` (no kafka; fixed order); rename `_require_instance` →
  `_require_service`; D8 vocabulary; vocabulary-only touches in `baseline.py`,
  `env_render.py`, and the conftest doubles' docstrings
  (engines from `config.services`, container from `config.instance` with the `service`
  attribute name kept; kafka section gone from `_startup_operations` with a docstring note
  that the topology comes from the inline declaration; log extras swapped to
  `{"service": ...}` / `{"services": [...]}` with events "instance env rendered" /
  "service reset" / "instance under test died"; the under-test wording follows D10
  ("the instance under test (image …) died"); conftest FakeEngine/FakeService docstrings
  to the service vocabulary, the D8 "service '<name>'" fake failure wording, and the
  FakeService sink prefix flipped to `instance:` — the under-test double)
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/test_sandbox.py
  tests/sandbox/test_baseline.py tests/sandbox/test_env_render.py -x -v` — pass
  (43 passed = 25 sandbox + 9 baseline + 9 env_render)
- [x] **Logic tests** (scenarios 24, 25, transferred verbatim):
  24. `test_sandbox_start_applies_startup_data_in_fixed_order` (unit with FakeEngine
      recording) — config with vault + http + postgres services and all three data sections;
      FakeEngine records `start(startup)`; `sandbox.start()` (runtime probe and container
      patched); assertions: each engine's startup list orders put → stub → sql for its kind;
      kafka engine's list is empty; engines start in declaration order; render called with
      mapped addresses; instance container started last with the rendered env (the vault →
      http → postgres order criterion — integration-level assertion over
      `_startup_operations`)
  25. `test_sandbox_uses_instance_and_services_keys` — `Sandbox(config)` builds engines from
      `config.services` and the container from `config.instance` (FakeEngine/FakeService
      spies); `postgresql("db")` returns the view bound to the current batch; unknown name /
      kind mismatch lists configured services
  (both landed by name — scenario 24 spies on `render_service_env` to pin the mapped-address
  context and asserts the full rendered env hand-off plus `instance:start` last; a retained
  branch pins the intra-engine section order with one service name under all three data
  sections assembling put → stub → sql; scenario 25 asserts the build spy order and the
  container-config identity; also retained — the full lifecycle/teardown/failure suites on
  the four-service harness, grouping/draining, batch replacement, boundary interplay, the
  guarded failing stop, and the died-instance guard)
- [x] **Debugging (authoritative scope)**: `.venv/bin/pytest tests/sandbox/config/
  tests/sandbox/engines/ tests/sandbox/data/ tests/sandbox/test_sandbox.py
  tests/sandbox/test_baseline.py tests/sandbox/test_env_render.py
  tests/sandbox/test_service_container.py -x` green
  (483 green with the docker-gated live cases executing; ledger blast radius verified over
  four full-tree runs — red files exactly the scheduled suites: plugin, test_activation,
  test_session_lifecycle, all failing on the old document keys / old shapes; one transient
  kafka fixed-port bind race appeared in a single back-to-back full run and never
  reproduced across three clean re-runs with zero leaked sandbox-labeled containers —
  environmental, not a regression of this task)
- [x] **Contract re-verification**: the `start()` Algorithm steps and requirements (visible
  progress; tests run only after readiness; stop removes everything) hold
  (checked clause by clause against the Sandbox CODEMANIFEST annotation — the six
  Algorithm steps, the one-network requirement, the per-test batch ownership, both
  constraints, and the view-factory failure wording; public surface unchanged per M-R5.5 —
  same class names, factories, 6-name facade)
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files
  (both gates exit 0 on the first run — one E501 in a test fixed during the TDD phase; all
  7 touched files format-clean)
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 12: `activation.py` — new-path vocabulary and the enqueue rename (TDD)

The activation module texts name the new document path and the preset enqueue resolves names
via `_require_service`. Design scenario 28 lands here.

**Contract entities**: `activate_sandbox(context) -> config: SandboxConfig | None`,
`active_sandbox() -> sandbox: Sandbox | None` (`activation.py`).

**Usages relevant to this task:**
- `pluginator`: the hook registration into the caller namespace (machinery unchanged).
- `sandbox-file` (imported usage): the activation document semantics (new path, cwd-only).
- `conventions`: tmp_path + chdir for the document; inertness assertions.

**Design details (binding):** docstring names the new document path; the inert-debug extra
names `.goga/tools/pybuggy/sandbox.yml`; `_enqueue_presets` calls `sandbox._require_service`;
`_KIND_ACTIONS` unchanged; hook registration machinery unchanged.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 12 is being executed
- [x] **Contract tests** (rework `tests/sandbox/test_activation.py`): `activate_sandbox`
  signature and `active_sandbox` lookup unchanged; arming through the new path
  (documents flipped to the `instance:`/`services:` keys, `fake_sandbox` to the new model
  shapes; TDD red confirmed — the armed path crashed on the swapped-away `config.service`
  field and the enqueue still called the deleted `_require_instance`)
- [x] **REPL prototype (R4)**: in the REPL (tmp cwd with the document under the tools home —
  the Task 4 fixture shape) call `activate_sandbox({})` — observe the returned config and the
  three registered hooks; without the document → `None` and the namespace untouched; then
  migrate
  (observed live in a venv heredoc REPL: no-document and stale-root-only legs both return
  None with the namespace untouched; the current code's armed-leg failure point read;
  the migrated fragments — `config.instance.image` / `list(config.services)` and the
  `_require_service` unknown-name error — exercised; then migrated and re-verified in a
  fresh interpreter: inert, stale-root-unread, armed with the three hooks)
- [x] **Code**: update `goga_tool_pybuggy/sandbox/activation.py` texts per the design
  details; `_enqueue_presets` → `_require_service`
  (docstring names `.goga/tools/pybuggy/sandbox.yml` under the pybuggy tools home; the
  inert-debug extra carries the same path; the armed log reads
  `extra={"image": config.instance.image, "services": list(config.services)}`;
  `_enqueue_presets` calls `sandbox._require_service` with the service-vocabulary Raises
  clause; `_KIND_ACTIONS` and the hook machinery untouched)
- [x] **Interface verification**: `.venv/bin/pytest tests/sandbox/test_activation.py -x -v`
  — pass
  (15 passed; fresh-interpreter facade check ok — 6 names, root re-exports, both
  signatures, `_KIND_ACTIONS` unchanged)
- [x] **Logic tests** (scenario 28, transferred verbatim): `test_activation_arms_from_new_document_path`
  — tmp_path with the document under the tools home; `activate_sandbox(context)` → config
  returned, three hooks registered; without the document → `None`, context untouched
  (inertness); plus the enqueue half of scenario 29 — preset declarations order ahead of
  in-test operations, unknown names list the configured services (over the fakes)
  (landed by name — the scenario-28 test also drops a stale root `.sandbox.yml` and
  observes it never arm, pinning that arming rides the tools-home path only; the enqueue
  half lives in the renamed `test_preset_enqueue_fails_unknown_service_listing_configured`
  and `test_preset_enqueue_prepends_marker_presets_into_fresh_batch` — unknown name raises
  "no postgresql service named 'ghost'; configured services: db (postgresql)", marker
  presets apply ahead of the in-test insert)
- [x] **Debugging (authoritative scope)**: `.venv/bin/pytest tests/sandbox/config/
  tests/sandbox/engines/ tests/sandbox/data/ tests/sandbox/ -x` green except
  `test_session_lifecycle.py` (known-red until Task 14; Migration Ledger)
  (498 green with the docker-gated live cases executing; ledger blast radius verified —
  full tree collects 1547, the runtime red list is exactly the scheduled suites: plugin
  test_install/test_plugin + test_session_lifecycle, all on the old document keys / old
  shapes)
- [x] **Contract re-verification**: presence gate and full inertness hold — no hooks, no
  containers, no side effects without the document
  (checked against the activation CODEMANIFEST annotations — the signature, the lookup
  seam, the constraint that no containers start here; vocabulary grep over the module
  clean: no `.sandbox.yml`, no `_require_instance`, no old field reads)
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files
  (both gates exit 0 on the first run — no findings, no format drift)
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

---

### Task 13: Plugin texts and init hint — the new path in companion surfaces; plugin suite restored (TDD)

The plugin/init changes are text-level (docstrings, fail-fast message, annotation hint); the
plugin test suites are reworked and with them **every suite except
`tests/sandbox/test_session_lifecycle.py` returns green** — the full suite returns green in
Task 14 (Migration Ledger checkpoint). Design scenarios 30 and 31 land here.

**Contract entities**: none changed (plugin CODEMANIFEST carries forward verbatim) — the
touched surfaces are `goga_tool_pybuggy/plugin/__init__.py` `install` docstring,
`goga_tool_pybuggy/plugin/plugin.py` `configure` fail-fast text, and
`goga_tool_pybuggy/commands/init/init.py` `PYBUGGY_ANNOTATIONS["sandbox-file"]`.

**Usages relevant to this task:**
- `conventions`: docstring rules (M-R1.7); exact-message assertions via `pytest.raises(match=)`.
- `sandbox-session` (cell `.usages/`, read-only): the consumer activation patterns the plugin
  texts point at.

**Design details (binding, companion texts):**
- `install` docstring — "`activate_sandbox(context)` reads `.goga/tools/pybuggy/sandbox.yml`
  in the CWD".
- `configure` fail-fast text — "(the sandbox document `.goga/tools/pybuggy/sandbox.yml` is
  present); the sandbox owns the service address".
- `PYBUGGY_ANNOTATIONS["sandbox-file"]` — "Use `pybuggy-sandbox-file` for authoring
  `.goga/tools/pybuggy/sandbox.yml`: the instance entry, dependency services, and startup
  data."

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] **Declaration**: state that Task 13 is being executed
- [x] **Contract tests** (rework `tests/plugin/test_install.py` **and
  `tests/plugin/test_plugin.py`**): arming flows through the new path; the armed-sandbox
  tests of `test_plugin.py` construct the new model shapes (`SandboxConfig(instance=
  InstanceConfig(image=…, env=…, port=…), services={}, data=StartupData())` — replacing the
  old `service=`/`instances=`/`health=` constructions); the fail-fast message names the new
  document path
  (reworked first — exactly the 3 ledger-scheduled red tests; the scenario-31 rename stayed
  red on the old fail-fast text until the plugin.py change landed — TDD red confirmed; the
  `ServiceConfig` → `InstanceConfig` import swap and the died-instance double wording follow
  the Task 11 vocabulary)
- [x] **REPL prototype (R4)**: in the REPL (tmp cwd, patched context) run `install(context=…)`
  with and without the document at the new path; observe `plugin.sandbox_activation` and the
  registered hooks; then migrate the texts
  (observed live in a venv heredoc REPL: armed leg — three hooks registered, activation is
  `SandboxConfig` with `instance.image` / `services=['db']`; inert leg — no lifecycle hooks,
  `sandbox_activation is None`; then the three texts migrated and re-verified in a fresh
  interpreter — docstring, fail-fast source, annotation all carry the new path)
- [x] **Code**: apply the three companion texts (`plugin/__init__.py`, `plugin/plugin.py`,
  `commands/init/init.py`)
  (install docstring names `.goga/tools/pybuggy/sandbox.yml` in the CWD; the configure
  fail-fast reads "(the sandbox document .goga/tools/pybuggy/sandbox.yml is present); the
  sandbox owns the service address"; the annotation reads "…for authoring
  `.goga/tools/pybuggy/sandbox.yml`: the instance entry, dependency services, and startup
  data.")
- [x] **Interface verification**: `.venv/bin/pytest tests/plugin/ -x -v` — pass
  (122 passed across the plugin tree incl. loaders/render; fresh-interpreter checks ok — the
  three texts verified verbatim via inspect)
- [x] **Logic tests** (scenarios 30, 31, transferred verbatim):
  30. `test_install_arms_sandbox_through_new_path` — tmp_path repo with
      `.goga/tools/pybuggy/sandbox.yml`; `monkeypatch.chdir`; `install(context=ctx)`:
      `activate_sandbox` reads the new path → armed → plugin constructed with
      `sandbox_activation` set; assertions: `plugin.sandbox_activation` is the `SandboxConfig`;
      hooks present in `ctx`. Negative: no document → `sandbox_activation is None`, no hooks
      (plugin arming rides the new path)
  31. `test_configure_rejects_base_url_with_active_sandbox` (test_plugin.py, armed-sandbox
      class — where the existing configure fail-fast test lives) — armed plugin + passed
      `--base-url` → `pytest.UsageError` naming the new document path (the companion text
      change)
  (both landed by name — scenario 30 carries both legs in one test with the `_ARMED` reset
  retained; scenario 31 matches `--base-url.*\.goga/tools/pybuggy/sandbox\.yml`; the
  retained armed-sandbox suites reworked to the new shapes — required-option error, guard
  forwarding, base_url substitution — all green)
- [x] **Debugging — full-suite checkpoint**: `.venv/bin/pytest tests/
  --ignore=tests/sandbox/test_session_lifecycle.py -x` — green (the ignored file is the sole
  documented Ledger exception, reworked in Task 14; with plain `-x` the run would stop inside
  `tests/sandbox/` and the later suites — spec, statuses, root — would never execute); any
  OTHER red file is an implementation bug — fix implementation, never tests
  (1543 passed, 0 failed — every suite except the Ledger exception green, docker-gated live
  cases executing; re-run green after the format fix)
- [x] **Contract re-verification**: plugin/init annotations carry forward verbatim — no
  contract change, texts only
  (checked — the plugin CODEMANIFEST is untouched (git diff clean of manifest paths), the
  public surface unchanged, the three texts are the design's companion wording verbatim)
- [x] **Lint gate (pre-commit)**: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files (the full pytest gate resumes at Task 14, M-R3.4)
  (one E501 in the fail-fast message and one format drift in test_install.py corrected —
  the message split across the implicit concatenation, the document literal collapsed by
  `ruff format`; both gates exit 0; plugin suite + full checkpoint re-run green)
- [x] **Completion**: mark checkboxes complete; submit for review → approval → next task

### Task 14: Integration tests — the armed session lifecycle over the new document (integration tests)

Rework `tests/sandbox/test_session_lifecycle.py` — the cross-cell integration suite: the
armed-flow documents move to the `instance:`/`services:` keys with inline topics, and the
probe settings ride the new declarations. The implementation is Tasks 2–13; failures found
here are fixed in the implementation, never in the contract.

**Usages relevant to this task:**
- `sandbox-session` (cell `.usages/`, read-only): the consumer fixture patterns under test
  (activation, session fixture + baseline, autouse reset, api usage).
- `conventions`: integration tests for cross-module interaction (M-R2.2 context); fakes from
  `tests/sandbox/conftest.py`; docker-gated paths via `requires_docker`.

**Interaction flow under test (design stack traces 1, 2, 4, 5):** `activate_sandbox` over the
new path → hooks → `Sandbox.start()` (engines from `services` in declaration order, startup
data vault → http → postgres, env render, instance container last, probe-bounded readiness) →
per-test batch + preset enqueue → `apply_pending` grouping → `clear()` reset flow → `stop()`
teardown.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [x] Rework `tests/sandbox/test_session_lifecycle.py`: armed-flow documents written at
  `.goga/tools/pybuggy/sandbox.yml` (the Task 4 fixture) with the `instance:`/`services:`
  keys, inline kafka topics, and probe declarations; doubles vocabulary per the conftest
  (documents flipped — `instance:` with a `probe: {path: /healthz}` entry, `services:` with
  a kafka entry declaring `orders.events` + `payments.events` partitions 6 and a vault probe
  override; `FailingApplyEngine` wording to "service '<name>'"; the `armed` fixture's seams
  renamed to `service_config` / `_instance_config`)
- [x] Test the armed session over fakes: engines started in declaration order with ordered
  startup lists; instance container last with rendered env; base_url from the instance
  address; preset enqueue ahead of in-test operations; reset flow leaves the instance running
  (the four-service flow test asserts the full lifecycle event sequence, the journaled
  put/stub/sql lists with the kafka engine's empty, the rendered env hand-off, `base_url`
  from the instance address, and preset-before-in-test ordering across three kinds incl. a
  kafka produce; the clear test drives the baseline boundary then asserts one reset with the
  instance still running)
- [x] Test edge cases: activation without the document (fully inert session); unknown service
  name on a view factory lists the configured services; a died instance surfaces through
  `ensure_service` with its output attached
  (all three landed in `TestSessionEdgeCases` — inert context stays empty with the lookup
  None; `postgresql("ghost")` lists `db (postgresql)`; the died guard names the image and
  attaches the fake output)
- [x] Docker-gated lifecycle case (requires_docker): a real armed session over the pinned
  mocks with declared topics and a probe — topology boots, partitions arrive, produce into a
  declared topic succeeds, reset replays the baseline
  (`TestArmedSessionLiveLifecycle` — wiremock instance gated by the declared
  `/__admin/health` probe, mokapi topology with `payments.events` at exactly 6 partitions,
  produce consumed back, `clear()` restart-leaves only the replayed baseline; executed for
  real in this environment)
- [x] Run validation: `.venv/bin/pytest tests/sandbox/test_session_lifecycle.py -v` then
  `.venv/bin/pytest tests/ -x` — **all green**
  (9 passed incl. the live case; full suite 1552 passed, 0 failed — the Migration Ledger
  closes: every suite green from here on)
- [x] Lint gate (pre-commit): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `ruff format --check` on touched files
  (both gates exit 0 on the first run — no findings, no format drift; REPL pass confirmed
  arming reads the new path with probe/topic declarations riding through)

### Task 15: Author docs and cooks sweep — the new path, keys, and vocabulary everywhere (documentation)

The author-facing surfaces follow the relocation: docs rewrite + point edits + the
repo-wide sweep check. Docs must not break test collection.

**Usages relevant to this task:**
- `conventions`: professional concise wording; English content.
- `sandbox-file` / `sandbox-session` / `data-operations` / `enable` (cell `.usages/`,
  read-only): the canonical authoring reference the docs mirror — do not duplicate beyond
  what docs need.

**Design details (binding, from § Companion Work Items):**
- `docs/sandbox.md` — **rewrite**: new path, `instance:`/`services:` keys, inline topics,
  probe settings; a migration pointer that does **not** name the former location — "if the
  sandbox does not activate, verify the document sits at exactly this path".
- Point edits: `docs/configuration.md`, `README.md`, `docs/getting-started.md`,
  `docs/index.md`, `docs/pipelines/api-fix.md`, `docs/plugin/index.md`, `mkdocs.yml`.
- Cooks (hand-authored point edits, not synced copies): `cooks/testcontainers.md` — the
  generic-container bullets about the spec path and volume mount become: the AsyncAPI document
  is generated in memory from the declared topics and transferred through the docker API (no
  bind mount — host paths resolve on the daemon's filesystem), its in-container path passed as
  the start argument; `cooks/wiremock.md` — "Startup mappings from the sandbox document are
  applied the same way" (drop the former document name); `cooks/mokapi.md` — the sandbox-flow
  wording follows the new declaration model (topology generated in memory from inline topics,
  no author spec file; a kafka service without topics is what fails fast; env placeholders
  `{{<service>.host}}` / `{{<service>.port}}` with the instance as the entry under test; "the
  topology is re-created from the generated document on boot"; kafka/service vocabulary
  throughout); `cooks/vault-dev.md` — vocabulary touch-up ("vault service", "the instance
  under test").

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] Rewrite `docs/sandbox.md` per the design details
- [ ] Apply the point edits to `docs/configuration.md`, `README.md`, `docs/getting-started.md`,
  `docs/index.md`, `docs/pipelines/api-fix.md`, `docs/plugin/index.md`, `mkdocs.yml`
- [ ] Apply the four cooks edits (testcontainers, wiremock, mokapi, vault-dev)
- [ ] Repo-wide sweep check: `grep -rn "\.sandbox\.yml"` over `docs/`, `README.md`,
  `mkdocs.yml`, `goga_tool_pybuggy/**/*.usages/`, `.goga/usages/cooks/` → **empty** (the
  `.usages/` files were verified clean by the design; the sweep proves the docs joined them)
- [ ] Run validation: `.venv/bin/pytest tests/ -x` — still green (docs must not break
  collection)
- [ ] Lint gate (pre-commit): `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0

### Task 16: Final validation gate — full suite, facades, contract lint, default equivalence (acceptance)

The plan-level verification of the design's Verification Checklist. Nothing is implemented
here; failures route back to the owning task's implementation.

**Usages relevant to this task:**
- `conventions`: the validation command table (virtualenv, pytest, ruff, facade checks).

- [ ] Run the full suite: `.venv/bin/pytest tests/ -x` — green; docker-gated suites run when
  the runtime is available, skip otherwise
- [ ] Facade checks (fresh interpreter):
  `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.config import SandboxConfig,
  InstanceConfig, ServiceConfig, StartupData, ProbeConfig, TopicConfig, load_sandbox_config"`;
  `... from goga_tool_pybuggy.sandbox.engines import build_engine, BaseEngine, EngineError"`;
  `... from goga_tool_pybuggy.sandbox import Sandbox, activate_sandbox, active_sandbox"`;
  root re-exports `active_sandbox`, `services` unchanged
- [ ] Contract lint: `goga lint` — 23 cells, 0 errors
- [ ] Repo sweep: `grep -rn "\.sandbox\.yml"` over docs, README, mkdocs, usage files, cooks →
  empty
- [ ] Default-equivalence: with no probe declarations, every readiness loop runs at 30.0/0.5 —
  the former constants (D6 single source; scenarios 16/22 assert it; re-run those focused
  tests as the evidence)
- [ ] Lint + format gate: `.venv/bin/ruff check goga_tool_pybuggy/ tests/` — exit 0;
  `.venv/bin/ruff format --check goga_tool_pybuggy/ tests/` — no drift on plan-touched files
- [ ] Commit gate (M-R3.4, full): lint + format + `pytest tests/ -x` green before the final
  commit

---

## Validation Commands

- `.venv/bin/pytest tests/ -x`: Run all tests (the convention's run-all command; fully green
  from Task 14 onward — Migration Ledger)
- `.venv/bin/pytest tests/sandbox/ -x`: Focused sandbox-tree suite (config → engines → data →
  session runtime)
- `.venv/bin/ruff check goga_tool_pybuggy/ tests/`: Lint check (M-R3.1 config; exit 0 required
  at every task end and before every commit)
- `.venv/bin/ruff format --check <touched files>`: Format check on every file a task or commit
  touches (M-R3.3/M-R3.4)
- `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.config import SandboxConfig,
  InstanceConfig, ServiceConfig, StartupData, ProbeConfig, TopicConfig, load_sandbox_config"`:
  Config facade accessibility (7 names)
- `.venv/bin/python -c "from goga_tool_pybuggy.sandbox.engines import build_engine, BaseEngine,
  EngineError"` and `.venv/bin/python -c "from goga_tool_pybuggy.sandbox import Sandbox,
  activate_sandbox, active_sandbox"`: Engines and sandbox facades
- `.venv/bin/python -c "from goga_tool_pybuggy import active_sandbox, services"`: Root
  re-exports unchanged
- `goga lint`: Contract lint — 23 cells, 0 errors
- `grep -rn "\.sandbox\.yml" docs/ README.md mkdocs.yml goga_tool_pybuggy/ .goga/usages/cooks/`:
  Former-path sweep — must return nothing

---

## Completion Criteria

- [ ] Every contract entity change is implemented in the correct `location` (`probe.py` and
      `topic.py` new; all other entities in place)
- [ ] Every contract entity is accessible from its facade (config facade at 7 names; engines /
      data / sandbox / root facades byte-stable)
- [ ] Properties and methods match the declared API; the public Python surface is unchanged
      (same class names, view factories, re-exports — M-R5.5)
- [ ] Descriptions are reflected in behavior — probe bounds and defaults (30.0/0.5), the D1–D10
      decisions, the fixed vault → http → postgres startup order, the EngineError expiry clause
- [ ] Contract dependencies are met (`ServiceConfig` edge config ← engines; `InstanceConfig` /
      `EngineError` edges into the sandbox cell)
- [ ] Every coding task followed the TDD workflow (contract tests → code → interface
      verification → logic tests → debugging → contract re-verification → lint) with the REPL
      loop inside implementation and debugging (R4)
- [ ] All 31 design test scenarios plus the model-level units exist and pass; boundary tables
      include each boundary incl. the legal `interval == timeout` edge
- [ ] The integration suite (`test_session_lifecycle.py`) covers the armed session over the
      new document; docker-gated cases skip cleanly without a runtime
- [ ] No package boundary was expanded; no new cells; no new dependencies
- [ ] `CODEMANIFEST` files were not modified (the working-tree contract committed unchanged in
      Task 1)
- [ ] All validation commands pass — full suite green, ruff clean, facades importable,
      `goga lint` 0 errors, former-path sweep empty, default equivalence (30.0/0.5) asserted
- [ ] Every Usages entry is exercised in at least one task (conventions throughout; ruamel in
      Tasks 4/8; testcontainers in Tasks 5–8/10; psycopg Task 6; kafka-python/mokapi Task 8;
      vault-dev/wiremock/requests Tasks 7/10; jinja2/pluginator Tasks 11–13)
