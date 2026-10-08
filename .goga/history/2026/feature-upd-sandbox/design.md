# Design Document: Sandbox refinement — document relocation, inline Kafka topics, configurable readiness, naming swap

Topic directory: `.goga/history/2026/feature-upd-sandbox/`. Sources: `task.md`, `adr.md` (accepted
2026-10-08), the architecture plan `arch.md` (materialized into the cells by the apply-architecture
stage), the CODEMANIFEST tree of branch `feature/upd-sandbox` (working tree, uncommitted), and the
current implementation at HEAD `2906069`. Every contract statement below traces to a CODEMANIFEST
annotation or a usage file; every design decision the contracts leave open is marked
**[decision]** and justified. External API facts (mokapi AsyncAPI shape, testcontainers 4.15 wait
strategy internals) were verified against the actual library sources and documentation during
tracing — see § Verified External Facts.

Static contract validation before tracing: `goga lint` over the whole project — 23 cells,
0 errors; `goga schema` dependency map matches the plan exactly (config ← engines ← data ←
sandbox ← plugin, labels swapped to `ServiceConfig` / `InstanceConfig`). The four consistency
dimensions (Interface↔Type, Type↔Mutation, Interface↔Interface, Annotations↔Entity) check clean —
no CODEMANIFEST defects were found, so no manifest edits were applied during this design.

## Contract Changes

### Changed CODEMANIFEST Files

- `goga_tool_pybuggy/sandbox/config/CODEMANIFEST` (modified): `SandboxConfig` fields renamed
  (`instance: InstanceConfig`, `services: dict[str, ServiceConfig]`); `InstanceConfig`/`ServiceConfig`
  swap subjects — `instance.py` now carries the under-test entry (with `probe: ProbeConfig | None`
  replacing `health: str | None`), `service.py` the dependency entry (with `topics:
  list[TopicConfig]` and `probe`); new types `ProbeConfig` (`probe.py`, timeout 30.0 / interval
  0.5 / optional path) and `TopicConfig` (`topic.py`, name + partitions default 1); `StartupData`
  loses the kafka section; `load_sandbox_config` targets `.goga/tools/pybuggy/sandbox.yml`
  (cwd-only) with top-level key diagnostics and the extended validation algorithm.
- `goga_tool_pybuggy/sandbox/engines/CODEMANIFEST` (modified): Imports edge renamed
  (`ServiceConfig` from config); `DataOperation` drops the startup-only `spec` action;
  `EngineError` gains the deadline-expiry clause; `BaseEngine`/`build_engine`/all four kind
  engines take `ServiceConfig` and honor the readiness declaration; `PostgresEngine` wraps module
  readiness in the declared deadline; `KafkaEngine` consumes inline topics and generates the
  AsyncAPI document in memory (undeclared-topic produce failure); vocabulary instance → service.
- `goga_tool_pybuggy/sandbox/data/CODEMANIFEST` (modified, annotation-level): `services` presets
  type tightened to `dict[str, dict[str, list[dict[str, object]]]]`; `KafkaInstance.produce`
  targets topics declared on the service entry; vocabulary.
- `goga_tool_pybuggy/sandbox/CODEMANIFEST` (modified): Imports — `InstanceConfig` (renamed edge)
  from config, `EngineError` newly from engines; `Sandbox.start` data order vault → http →
  postgres and probe-bounded instance readiness; `ServiceContainer(config: InstanceConfig)`
  commits deadline expiry to `EngineError`; vocabulary.
- `goga_tool_pybuggy/plugin/CODEMANIFEST` — carries forward verbatim (no contract change).
- `goga_tool_pybuggy/commands/init/CODEMANIFEST`, `goga_tool_pybuggy/CODEMANIFEST` (root) —
  carry forward verbatim.

### Entity Deltas vs the Current Implementation

New types: `ProbeConfig` (config/probe.py), `TopicConfig` (config/topic.py). Changed shapes:
`SandboxConfig` (field swap), `InstanceConfig` (under-test entry: image/env/port/probe),
`ServiceConfig` (dependency entry: name/kind/image/topics/probe), `StartupData` (no kafka),
`load_sandbox_config` (new path + diagnostics), `DataOperation` (action set without `spec`),
`BaseEngine` family (`ServiceConfig`, probe-bounded readiness), `ServiceContainer`
(`InstanceConfig`, probe-bounded readiness, `EngineError` expiry), `services` (tightened presets
type). The Python API surface is unchanged: same class names, same view factories, same
`active_sandbox`/`services` re-exports.

### Usages and Annotations Changes

- Cell `.usages/` files (already materialized by apply-architecture, verified against the
  manifests for this design): `sandbox/config/.usages/sandbox-file.md` (rewritten — new document
  layout, inline topics, probe tables, document-locating section), `sandbox/data/.usages/
  data-operations.md` (declared-topics note, new path), `sandbox/.usages/sandbox-session.md`
  (activation by new path, cwd-only pointer), `plugin/.usages/enable.md` (Sandbox activation
  section). All use canonical block-style YAML; none references the former path or former keys.
- Project cooks (deferred to implementation, hand-authored — point edits):
  `.goga/usages/cooks/testcontainers.md`, `.goga/usages/cooks/wiremock.md`,
  `.goga/usages/cooks/mokapi.md`, `.goga/usages/cooks/vault-dev.md` — see
  § Companion Work Items.

## Verified External Facts

Tracing-time verification of the external libraries the contract depends on (do not assume —
verify):

1. **mokapi topics and partitions.** mokapi derives kafka topics from AsyncAPI channels and the
   partition count from the **kafka channel binding** `partitions` ("Sets the number of partition
   for the channel. Default value is 1" — mokapi kafka configuration docs). In AsyncAPI 2.6 the
   channel key is the topic name; in 3.0 the channel carries `address` with the topic name. The
   kafka server entry stays `servers.<name>` with `protocol: kafka` and the load-bearing
   `host:port` — the fact the existing `_patch_specs` pipeline already exploits. mokapi validates
   produced messages against declared payload schemas — a generated document must therefore
   declare **no** message payloads, or arbitrary test values get rejected.
2. **testcontainers 4.15 postgres module readiness.** `PostgresContainer.start()` (via
   `DbContainer.start`) runs `self._connect()` after the container runs — a fresh internal
   `ExecWaitStrategy` (psql exec probe) whose timeout/interval come from the global
   `testcontainers_config` defaults and **cannot be re-parameterized from outside** (the strategy
   object is constructed inside `_connect`). `DockerContainer.waiting_for(...)` does not reach
   it. Bounding the module wait by declared values therefore requires either an executor-wrapped
   `start()` or disabling `_connect` — see [decision] D3.

## Implementation Design

Ordered leaves → root: config → engines → data → sandbox → plugin/init/docs/cooks → tests.
All changes are working-tree modifications on `feature/upd-sandbox`; no new dependencies in
`pyproject.toml` (in-memory AsyncAPI generation uses plain serializable structures + ruamel).

### Cell 1 — `goga_tool_pybuggy/sandbox/config`

**`probe.py` (new).** `ProbeConfig(BaseModel)` kw_only: `timeout: float = 30.0`,
`interval: float = 0.5`, `path: str | None = None`. Validation: `timeout`/`interval` strictly
positive (`Field(gt=0)`), `interval <= timeout` (a `model_validator(mode="after")` raising
"the probe interval (default 0.5) must not exceed the timeout — declare a smaller interval
alongside a sub-second timeout"). The defaults reproduce the established wait
exactly (30.0 / 0.5 — the constants every engine loop uses today).

**[decision] D1 — probe/topic constraints live in the models, surfaced with document scope by the
loader.** Field bounds and the service-probe `path` rejection are pydantic validators
(`ProbeConfig` bounds; `ServiceConfig` model validator rejecting `probe.path is not None` with
"the probe path is accepted only on the instance entry"). The loader's existing
`_build_model` wraps any `ValidationError` into `ValueError(f"{location}: {scope}: {details}")`,
so every failure names the document location and the offending entry — the contract's error
shape — with a single enforcement point per rule.

**`topic.py` (new).** `TopicConfig(BaseModel)` kw_only: `name: str` (`Field(min_length=1)`),
`partitions: int = 1` (`Field(gt=0)`).

**`instance.py` (repurposed).** `InstanceConfig` = the under-test entry: `image: str`,
`env: dict[str, str] = {}`, `port: int`, `probe: ProbeConfig | None = None`. Docstrings to the
new subject.

**`service.py` (repurposed).** `ServiceConfig` = one dependency service: `name: str`,
`kind: str`, `image: str | None = None`, `topics: list[TopicConfig] = []`,
`probe: ProbeConfig | None = None`, plus the D1 model validator rejecting a probe path. The kind
vocabulary (postgresql/kafka/vault/http) stays loader-validated.

**`sandbox_config.py`.** Fields `instance: InstanceConfig`, `services:
dict[str, ServiceConfig] = {}`, `data: StartupData = StartupData()`.

**`startup_data.py`.** Drop the `kafka` field; section order vault → http → postgres is the
field order (the application order at start).

**`loader.py`.** Keep the helper skeleton (`_parse_document`, `_read_*`, `_build_model`,
`_validate_placeholders`) with these changes:

- `_DOCUMENT_PATH = Path(".goga") / "tools" / "pybuggy" / "sandbox.yml"`; `location = Path(path)
  if path is not None else Path.cwd() / _DOCUMENT_PATH`. Cwd-only, no upward search; absent →
  `None` (fully inert; a stale `.sandbox.yml` at the root is never read — silent by grooming
  decision).
- **Top-level key diagnostics** (new step after parse): `"service" in document` →
  `ValueError` "top-level key 'service' was renamed to 'instance'"; `"instances" in document` →
  "top-level key 'instances' was renamed to 'services'"; any key outside
  `{instance, services, data}` → "unknown top-level key '<key>' (supported keys: instance,
  services, data)". Every message is prefixed with the document location.
- `_read_instance` (was `_read_service`): requires `image`, `env`, `port` present; builds
  `InstanceConfig`; the optional `probe` mapping builds `ProbeConfig` (path allowed here).
- `_read_services` (was `_read_instances`): per name — non-empty string matching the template
  identifier grammar `[A-Za-z_][A-Za-z0-9_]*` (the `{{<name>.host}}`/`{{<name>.port}}`
  placeholder name; a hyphenated name fails); entry mapping; `_validate_kind` (postgresql/
  kafka/vault/http; grpc → explicit "not supported yet"); topics: kafka entries require a
  non-empty `topics` list of mappings building `TopicConfig` — **[decision] D7: duplicate topic
  names within one entry are rejected** ("duplicate topic '<name>' — each topic name must be
  unique within the service entry"): duplicates would silently collapse the generated AsyncAPI
  channels, and the contract forbids defaulting or repairing invalid entries; non-kafka entries
  with a `topics` key → "topics are accepted only on kafka entries". Probe: optional, builds
  `ProbeConfig`; a probe `path` is rejected by the D1 model validator.
- `_read_data`: `_SECTION_KINDS = {"vault": "vault", "http": "http", "postgres": "postgresql"}`;
  a `kafka` key under `data` → "data.kafka was removed — declare topics inline on the kafka
  service entry" (the removed-section diagnostic); unknown sections list the supported ones;
  targets must be configured services of the matching kind; the vault declaration shape check
  stays. The kafka spec-path resolution helper `_resolve_spec_path` is deleted.
- `_validate_placeholders` (renamed vocabulary only): instance env values against configured
  service names, same grammar, same messages modulo instance/services wording.
- Return `_build_model(SandboxConfig, {"instance": ..., "services": ..., "data": ...}, ...)`;
  the `logger.info` "sandbox document loaded" event stays.

**`__init__.py`.** Facade exports add `ProbeConfig` and `TopicConfig`:
`__all__ = ["InstanceConfig", "ProbeConfig", "SandboxConfig", "ServiceConfig", "StartupData",
"TopicConfig", "load_sandbox_config"]`.

### Cell 2 — `goga_tool_pybuggy/sandbox/engines`

**`operation.py`.** Docstring only: action set `insert` / `produce` / `put` / `stub`; the
startup-only postgresql `sql` payload note stays.

**`base.py`.**

- Import swap: `from ..config.service import ServiceConfig`; `BaseEngine.__init__(self, config:
  ServiceConfig)`; docstrings/log extras renamed to the service vocabulary
  (**[decision] D8 — structured-log extras swap with the contract vocabulary**: engines emit
  `extra={"service": name, "kind": kind}` and events "service starting" / "service ready" /
  "service stopped"; `DataOperation.instance` and `EngineError` message wording "service '<name>'"
  follow. Event names stay stable and unique across the sandbox).
- **Readiness bounds accessor** — **[decision] D6**: `from ..config import ProbeConfig`; a
  `_readiness_bounds` property returns `(probe.timeout, probe.interval)` of
  `self.config.probe or ProbeConfig()`. Single default source (`ProbeConfig`), so the
  default-equivalence criterion holds by construction: no probe declared → 30.0 / 0.5 — the
  exact constants every engine loop uses today.
- **Bounded probe loop helper** — **[decision] D5**: a private `_probe_until(timeout, interval,
  attempt, failure)` loop computing `deadline = monotonic() + timeout` internally: while
  `monotonic() < deadline` — run `attempt()`; on True return; sleep `interval`. Expiry raises
  `RuntimeError(f"{failure} within {timeout:g}s")`. The
  lifecycle wrappers (`_run_step("start failed at readiness wait", ...)`,
  `_run_step("reset failed at wipe", ...)`) convert it into `EngineError` naming the service,
  the lifecycle step, the waited check, and the expired deadline — the contract's expiry clause.
  Kind engines keep per-kind attempt callables; three divergent hand-rolled loops collapse into
  one.
- `EngineError` docstring gains the deadline-expiry sentence; `start`'s Algorithm annotation 2
  wording (declared deadline/interval) is reflected in the docstring; everything else (journal,
  `_run_step` machinery, `stop` safety, `reserve_port`) is unchanged.

**`runtime.py`.** `build_engine(config: ServiceConfig)`; `KIND_ENGINES` unchanged; docstring
vocabulary; the "engine built" debug extra renamed to `service`.

**`postgres.py`.**

- **[decision] D3 — bounded module readiness via a private module subclass + engine-owned
  psycopg probe.** testcontainers 4.15 constructs its psql-exec wait strategy inside
  `PostgresContainer._connect` with global-config bounds that cannot be re-parameterized from
  outside (§ Verified External Facts 2). Design: a private `_PostgresContainer(PostgresContainer)`
  whose `_connect` is a no-op ("readiness probing is engine-owned, bounded by the declared
  deadline"), and a real `PostgresEngine._wait_ready` that probes
  `psycopg.connect(host, port, user, password, dbname, connect_timeout=2)` in the D5 loop with
  the declared bounds, closing the probe connection on success (the session connection opens in
  `_open_plane` as today). This honors **both** the declared timeout and the declared interval
  (an executor-wrapped blocking `start()` could honor only the timeout), keeps the module
  container (image/env/port semantics), and checks the same condition — the server accepts
  connections — with the data-plane driver. Default equivalence: with no probe the loop runs at
  30.0/0.5 instead of the testcontainers global default (60 s) — the contract fixes the declared
  default at 30.0 for every target (engines manifest PostgresEngine annotation and the
  sandbox-file defaults table); the success path is unchanged and the deadline is uniform across
  kinds.
- Vocabulary swap in docstrings/logs; `_build_container` builds `_PostgresContainer` with the
  same pinned image/credentials/labels; the rest (symbol stream, `$ref`/`$lookup` resolution,
  catalog-driven truncate wipe) is untouched by this iteration.

**`kafka.py`.** The largest change.

- The startup spec plumbing is deleted (`_spec_paths`, `_specs`, `start`'s spec extraction,
  the `spec` branch of `_execute`, `_patch_specs`).
- `start` fails fast on an empty declaration before the container build:
  `EngineError("service '<name>': no topics declared on the kafka service entry — declare topics
  inline in the sandbox document; without topics the mock opens no kafka listener")`. Document
  validation rejects this first; the engine check is defense in depth (the manifest's "empty
  topic declaration is an invalid state — the engine fails fast").
- `_build_container`: `host = DockerClient().host()`, `port = reserve_port()`,
  `self._container_port = port`; the AsyncAPI document is generated **in memory** from
  `self.config.topics` with the final mapped address; transferred via
  `container.with_copy_into_container(document, target)` with `target =
  f"{SPEC_MOUNT_DIR}/sandbox.asyncapi.yaml"`; `container.with_command([target])`; HTTP port
  exposed, fixed port bound both sides, labels, network attach — the patched-spec pipeline
  (mapped reserved address → servers carry it → transfer → start argument) holds with the patch
  folded into generation.
- **[decision] D4 — generated document shape.** AsyncAPI **2.6.0** (channel key = topic name —
  the simplest form mokapi supports, no `address` indirection): `info {title: <service name>,
  version: "1.0.0"}`, one server `kafka: {protocol: kafka, host: "<host>:<reserved port>"}`, one
  channel per topic `<topic name>: {bindings: {kafka: {partitions: <partitions>}}}` — **no
  messages/payload schemas** (mokapi validates produced messages against declared schemas;
  produced values are arbitrary test data — declaring schemas would reject them; § Verified
  External Facts 1). Serialized to UTF-8 bytes with the existing ruamel `YAML()` into a
  `StringIO`; never written to disk anywhere. The AsyncAPI version is an implementation detail
  (ADR); the docker-gated engine test verifies the topology boots and the partitions arrive.
- `_wait_ready`: the `/health` loop rewritten onto D5 with declared bounds.
- `_execute` (produce): validates the topic first —
  **[decision] D9**: `topic not in {t.name for t in self.config.topics}` →
  `EngineError("service '<name>': topic '<topic>' is not declared on the kafka service entry
  (declared topics: <sorted names>)")`; otherwise send + `future.get(timeout=DELIVERY_TIMEOUT)`
  as today. The flush batch boundary stays.
- `_wipe` restart path: unchanged mechanics; the re-wait runs through the bounded `_wait_ready`.
- Serializers, producer lifecycle, constants other than readiness — unchanged.

**`vault.py` / `http.py`.** `_wait_ready` rewritten onto D5 with declared bounds (health 200 /
admin ready checks unchanged, including the wiremock 404→mappings fallback); the module
constants `READINESS_TIMEOUT`/`READINESS_INTERVAL` are deleted; vocabulary in docstrings/logs;
everything else unchanged.

**`address.py`, `__init__.py`.** Docstring vocabulary; facade exports unchanged.

### Cell 3 — `goga_tool_pybuggy/sandbox/data`

- `presets.py`: the decorator's value annotation is corrected to
  `**presets: dict[str, dict[str, list[dict[str, object]]]]` — the **tightened contract type**
  that finally matches the runtime nesting (`kind → service name → declaration list`, the shape
  `activation._enqueue_presets` already iterates); docstring vocabulary (service); validation
  logic unchanged (supported kinds, declaration shape, `validate_insert_rows` on postgresql
  rows, marker attach).
- `kafka.py`: `produce` docstring — the topic must be declared on the kafka service entry of the
  sandbox document.
- `postgres.py` / `vault.py` / `http.py` views, `batch.py`: docstring vocabulary
  ("started postgresql service", "the value the env placeholders of the instance under test
  resolve to", "per service"); no behavior change.

### Cell 4 — `goga_tool_pybuggy/sandbox`

**`sandbox.py`.**

- Wiring swap: `self.engines = {name: build_engine(service_config) for name, service_config in
  config.services.items()}`; `self.service = ServiceContainer(config.instance)` (the attribute
  keeps its name — it is private vocabulary; docstrings say "the instance under test").
- `_startup_operations(name)`: vault section → `put` operations, http section → `stub`
  operations, postgres section → `insert`+`sql` operations — **no kafka section**; the fixed
  order is vault → http → postgres within each engine's startup list; kafka services simply
  receive an empty list (their topology comes from the declaration at container build).
- `start` Algorithm unchanged otherwise (check_runtime → network → engines+startup data →
  `render_service_env` → `ServiceContainer.start` → logging); the readiness sentence in the
  docstring reflects the probe-bounded wait.
- `_require_instance` → `_require_service` (private rename; same error shape listing configured
  services); view factories unchanged publicly.
- `ensure_service` / `clear` / `stop` / `apply_pending` / `new_test_batch`: vocabulary only
  ("instance" for the under-test container, "service" for engines); log extras follow D8.
- `base_url` unchanged.

**`service_container.py`.**

- `from ..config import InstanceConfig` (under-test entry) — `ServiceContainer(config:
  InstanceConfig)`.
- Readiness — **[decision] D10**: `probe = self.config.probe or ProbeConfig()`; path-only
  semantics: `probe.path is None` → TCP port loop, else health-endpoint 2xx loop at
  `http://{host}:{port}{path}`; both loops run the declared `probe.timeout`/`probe.interval`.
  Expiry raises **`EngineError`** directly (imported from `..engines`) —
  `"the instance under test (image <image>) did not become ready: <check description> within
  <timeout>s"` — an actionable failure naming the instance, the waited check, and the expired
  deadline; never a hang. The `RuntimeError` module constants for readiness are replaced by the
  probe values.
- Everything else (labels, port publish, env application, `alive`/`logs`, stop safety)
  unchanged; vocabulary in docstrings/logs ("instance").

**`activation.py`.** Docstring names the new document path; the inert-debug extra names
`.goga/tools/pybuggy/sandbox.yml`; `_enqueue_presets` calls `sandbox._require_service`;
`_KIND_ACTIONS` unchanged; hook registration machinery unchanged.

**`env_render.py`, `baseline.py`, `__init__.py`.** Vocabulary only; facade unchanged.

### Companion Work Items (non-DSL, required by the task)

- **Plugin texts**: `goga_tool_pybuggy/plugin/__init__.py` `install` docstring —
  "`activate_sandbox(context)` reads `.goga/tools/pybuggy/sandbox.yml` in the CWD";
  `goga_tool_pybuggy/plugin/plugin.py` `configure` fail-fast text — "(the sandbox document
  `.goga/tools/pybuggy/sandbox.yml` is present); the sandbox owns the service address".
- **Init hint**: `goga_tool_pybuggy/commands/init/init.py` `PYBUGGY_ANNOTATIONS["sandbox-file"]`
  — "Use `pybuggy-sandbox-file` for authoring `.goga/tools/pybuggy/sandbox.yml`: the instance
  entry, dependency services, and startup data."
- **Author docs sweep** (new path, `instance:`/`services:` keys, inline topics, probe settings;
  a migration pointer that does **not** name the former location — "if the sandbox does not
  activate, verify the document sits at exactly this path"): `docs/sandbox.md` (rewrite),
  `docs/configuration.md`, `README.md`, `docs/getting-started.md`, `docs/index.md`,
  `docs/pipelines/api-fix.md`, `docs/plugin/index.md`, `mkdocs.yml`.
- **Cooks (hand-authored, not synced copies)**: `cooks/testcontainers.md` — the generic-container
  bullet "this is how the AsyncAPI spec path, vault dev flags, and wiremock options are passed"
  and the "Spec/config files reach the container through a volume mount" bullet become: the
  AsyncAPI document is generated in memory from the declared topics and transferred through the
  docker API (no bind mount — host paths resolve on the daemon's filesystem), its in-container
  path passed as the start argument; `cooks/wiremock.md` — "Startup mappings from the sandbox
  document are applied the same way" (drop the former document name); `cooks/mokapi.md` — the
  sandbox-flow wording follows the new declaration model: the topology is generated in memory
  from the topics declared inline on the kafka service entry (no author spec file exists), a
  kafka service without topics is what fails fast (was "a spec-less kafka instance"), the env
  placeholders are `{{<service>.host}}` / `{{<service>.port}}` (the instance is the entry under
  test), "the topology is re-created from the generated document on boot", and the kafka/service
  vocabulary swap throughout; `cooks/vault-dev.md` — vocabulary touch-up only ("vault service",
  "the instance under test").
- **Repo-wide sweep check**: after the sweep, `grep -r "\.sandbox\.yml"` over docs, README,
  usage files, and cooks returns nothing.

### Tests (updated and extended; suites mirror the source tree)

Existing suites to rework: `tests/sandbox/config/*` (loader, models), `tests/sandbox/engines/*`
(base, runtime, kafka, postgres, vault, http, operation), `tests/sandbox/data/*` (presets,
views), `tests/sandbox/*` (sandbox, service_container, activation, baseline, env_render,
test_session_lifecycle — its armed-flow documents move to the `instance:`/`services:` keys),
`tests/plugin/test_install.py` (arming through the new path). The shared `tests/sandbox/conftest.py`
`sandbox_yaml` fixture writes the document at `.goga/tools/pybuggy/sandbox.yml` under `tmp_path`
(creating the parent directories) instead of the former root path; its docstring and the
`FakeEngine`/`FakeService` doubles follow the service vocabulary. Docker-gated suites keep the
`requires_docker` skip pattern from `tests/sandbox/conftest.py`; unit suites stay mock-free.
Full scenarios — § Test Scenarios.

## Code Stack Traces (Phase 4 checkpoints)

Traced entry points with the target design; all checkpoints passed:

1. **`activate_sandbox(context)`** → `load_sandbox_config(None)` → resolves
   `cwd/.goga/tools/pybuggy/sandbox.yml` → absent → `None` → inert return, no hooks (✓ presence
   gate; stale root document never read). Present → parse → top-level diagnostics → instance
   entry (image/env/port/probe) → services (name grammar, kind, topics incl. duplicates and
   non-kafka rejection, probe without path) → data sections (no kafka; targets resolve; vault
   shape) → placeholders (env names ⊆ services) → `SandboxConfig` → hooks registered → config
   kept armed. Type flow: `SandboxConfig` → `Sandbox(config)` constructor — ✓ shapes match.
2. **`Sandbox.start()`** → `check_runtime` → network → per service (declaration order):
   `build_engine(ServiceConfig)` → `engine.start(startup ops, network)` → container (image
   override / labels / port / network alias) → readiness within declared bounds (D5/D3/D4 paths)
   → data plane open → startup ops applied + journaled (vault → http → postgres per engine) →
   `addresses[name] = engine.address` → `render_service_env(config.instance.env, addresses)`
   (strict Jinja2; defense in depth) → `ServiceContainer.start(rendered, network)` → probe-
   bounded readiness (D10) → logs. Checkpoint: `StartupData` section payload shapes match the
   `DataOperation` payload contracts (`put` {path,data}, `stub` mapping, `insert` {sql}) — ✓.
3. **`KafkaEngine` build/produce/reset** — topics from `config.topics` (validated non-empty at
   load, re-checked at start) → generated 2.6.0 document with the reserved mapped address →
   docker-API transfer → command argument → `/health` bounded wait → producer against the same
   address; `produce` topic gate (D9); reset restarts, binding+document survive, re-wait
   bounded, baseline replays. Checkpoint: bootstrap = metadata = `{{events.host}}:{{events.port}}`
   — one address — ✓ (the existing pipeline property preserved).
4. **Per-test flow** — `pytest_runtest_setup` → `new_test_batch()` → preset enqueue (names via
   `_require_service`) → view declarations lazy → first api request → `apply_pending` → batch
   take → group by service → `engine.apply` (postgres insert resolves `$ref`/`$lookup` at
   execution; payload never rewritten) → request proceeds. Checkpoint: preset nesting
   `kind → name → declarations` matches the tightened `services` type and the enqueue loop — ✓.
5. **Reset flow** — `clear()` → per engine `reset()` → wipe (truncate / restart / mappings
   reset) → journal replay rebuilds state; instance container untouched — ✓.

No contract defects surfaced during tracing (the postgres-default-deadline reading is resolved
by the manifest + usage-file majority over the checklist phrase — recorded in D3).

## Cross-Cutting Concerns

- **Error handling.** Two failure families, unchanged in shape: declaration/load failures are
  `ValueError` naming the document location and the offending entry (fail-fast, nothing
  started); runtime engine failures are `EngineError` naming the service, the failed step or
  operation, and the cause — now including readiness deadline expiry for every engine and the
  instance container (the new clause). `check_runtime` keeps its plain `RuntimeError` naming the
  requirement (pre-engine step, contract text).
- **Validation.** Layers stay: document validation at load (complete before anything starts);
  declaration-time grammar (`validate_insert_rows`, preset shapes, topic gate at produce);
  execution-time resolution only in the postgres engine. Probe bounds and topic shapes validate
  at load through the pydantic models (D1).
- **Logging.** Structured `logging` with `extra` metadata per conventions; vocabulary swap per
  D8 (engines: service; under-test container: instance); stable lowercase event names; no
  secrets in logs (the vault dev token is a fixture credential and is never logged — unchanged).
- **Caching.** None introduced. `ProbeConfig()` default construction per access is negligible;
  no memoization of readiness bounds.
- **Concurrency.** No new concurrency. The reserved-port race window and the Ryuk safety net
  stay as-is; the kafka restart wipe keeps its bounded rebuild path.

## Test Scenarios

Written into the design as deliverables. Unit suites are mock-free (tmp_path for documents);
docker-gated suites use `requires_docker` and the real mocks.

### `tests/sandbox/config/test_loader.py`

1. **`test_load_resolves_document_under_tools_home`** — Setup: `tmp_path` with
   `.goga/tools/pybuggy/sandbox.yml` (instance + one kafka service with topics + data.postgres),
   `monkeypatch.chdir(tmp_path)`. Input: `load_sandbox_config(None)`. Trace: cwd join →
   is_file → parse → diagnostics pass → models built. Assertions: returned `SandboxConfig`
   with `instance.image`, `services["events"].topics[0].name == "orders.events"`,
   `services["events"].topics[1].partitions == 6`, `data.postgres["db"] == [...]`; no kafka
   attribute anywhere on `data`. Sufficiency: pins the new path resolution and the inline
   partitions default (acceptance: relocation + default partitions).
2. **`test_load_returns_none_without_document_and_ignores_stale_root_document`** — Setup:
   `tmp_path` holding a stale `.sandbox.yml` at the root, no tools-home document. Input:
   `load_sandbox_config(None)`. Trace: new path absent → return None; the root file is never
   opened. Assertions: result is `None`; zero side effects. Sufficiency: the grooming decision —
   stale location fully silent; inertness criterion.
3. **`test_load_fails_naming_rename_for_service_key`** — Setup: document with `service:` +
   `services:`. Input: `load_sandbox_config`. Trace: top-level diagnostics hit `service`.
   Assertions: `pytest.raises(ValueError, match="renamed to 'instance'")`, message contains the
   document path. Sufficiency: renamed-key error criterion.
4. **`test_load_fails_naming_rename_for_instances_key`** — same with `instances:` → match
   "renamed to 'services'".
5. **`test_load_fails_on_unknown_top_level_key`** — document with `extra:` → match "unknown
   top-level key 'extra'" listing supported keys.
6. **`test_load_fails_on_kafka_entry_without_topics`** — kafka service entry without `topics` →
   match `services.events` + "topics"; nothing starts (pure load, no docker touched).
   Sufficiency: acceptance — kafka entry without topics fails before any container.
7. **`test_load_fails_on_topics_on_non_kafka_entry`** — postgresql entry with `topics` → match
   "accepted only on kafka entries".
8. **`test_load_fails_on_duplicate_topic_names`** — kafka entry with two `orders.events`
   declarations → match "duplicate topic 'orders.events'" (D7).
9. **`test_load_fails_on_probe_path_on_service`** — vault service with `probe: {path: /health}` →
   match "probe path" + the entry scope (D1 surfacing).
10. **`test_load_fails_on_probe_bounds`** — parametrized: `timeout: 0`, `interval: -1`,
    `interval: 60 > timeout: 30` → each fails naming the probe field (boundary table per
    conventions). The legal boundary rides along as
    **`test_load_accepts_interval_equal_to_timeout`** — Setup: document with a postgresql
    service `probe: {timeout: 30.0, interval: 30.0}`; Input: `load_sandbox_config(None)`;
    Trace: probe builds `ProbeConfig(30.0, 30.0)` → `interval <= timeout` passes at the
    boundary → `ServiceConfig` (no path) → `SandboxConfig`; Assertions:
    `config.services["db"].probe.timeout == 30.0` and `.interval == 30.0`; Sufficiency: pins
    the legal edge of the validator comparator — prevents a `<=` → `<` regression that would
    reject valid documents while every negative test stays green.
11. **`test_load_fails_on_removed_kafka_data_section`** — `data: {kafka: {...}}` → match
    "data.kafka was removed".
12. **`test_load_fails_on_placeholder_naming_unknown_service`** — instance env
    `"{{nope.host}}"` → match "not configured" listing configured services.
13. **`test_load_rejects_hyphenated_service_name`** — `services: {my-db: ...}` → match the
    template-identifier grammar message (placeholders would break at render).
14. **`test_load_grpc_kind_fails_not_supported_yet`** — kind grpc → match "not supported yet".
15. **`test_load_probe_defaults_applied`** — instance probe `{}` and service probe `{timeout:
    45.0}` → `config.instance.probe.timeout == 30.0`, `interval == 0.5`, `path is None`;
    `config.services["db"].probe.timeout == 45.0`. Sufficiency: defaults reproduce the
    established wait; partial override keeps the rest.

`test_probe.py` / `test_topic.py`: model-level units — defaults (30.0/0.5/None; partitions 1),
bound rejections, path-free construction; `test_instance.py` / `test_service.py` /
`test_sandbox_config.py` / `test_startup_data.py`: field shapes, kw_only, defaults empty,
StartupData has no kafka field.

### `tests/sandbox/engines/`

16. **`test_base_readiness_bounds_default_and_override`** (test_base.py) — Setup: a minimal
    `ServiceConfig(name="db", kind="postgresql")` without probe, and one with
    `probe=ProbeConfig(timeout=45.0, interval=1.0)` on a stub engine. Input: `_readiness_bounds`.
    Assertions: `(30.0, 0.5)` / `(45.0, 1.0)`. Sufficiency: single default source — the
    default-equivalence criterion by construction.
17. **`test_kafka_generated_document_shape`** (test_kafka.py, unit) — Setup: `ServiceConfig`
    kafka with topics `[("orders.events", 1), ("payments.events", 6)]`; call the private
    generator with host `localhost`, port `9093`. Assertions: parsed document `asyncapi ==
    "2.6.0"`; `servers["kafka"] == {protocol: kafka, host: "localhost:9093"}`; channel keys are
    the topic names; `channels["payments.events"]["bindings"]["kafka"]["partitions"] == 6`;
    `orders.events` carries partitions 1; **no `messages` anywhere**. Sufficiency: D4 — the
    generated topology and the no-schema rule (schema validation would reject arbitrary
    produced values).
18. **`test_kafka_produce_into_undeclared_topic_fails`** (test_kafka.py) — Setup: started engine
    (docker-gated) with declared topics; Input: `apply` of a produce for `nope.topic`.
    Assertions: `EngineError` matching "not declared" and listing `orders.events`. Sufficiency:
    D9 — readable failure naming service and declared topics.
19. **`test_kafka_engine_fails_fast_without_topics`** — `ServiceConfig` kafka with `topics=[]`
    (bypassing the loader) → `start` raises `EngineError` mentioning "no topics" before any
    docker call (assert via a build-spy if unit, or docker-gated). Sufficiency: defense in
    depth behind the loader.
20. **`test_postgres_readiness_deadline_expires_as_engine_error`** (test_postgres.py,
    docker-gated or monkeypatched connect) — Setup: probe `timeout=0.2, interval=0.05`, a
    psycopg.connect stub always raising. Input: `engine.start(...)`. Trace: container start →
    `_wait_ready` loop → deadline. Assertions: `EngineError` (via the step wrapper) naming the
    service, "readiness", and the 0.2s deadline. Sufficiency: expiry surfaces as `EngineError`,
    never a hang (postgres path).
21. **`test_postgres_bounded_wait_honors_interval`** — connect stub succeeding on the 3rd call;
    assert ≥2 sleeps of the declared interval and success (bounds reach the loop).
22. **`test_vault_and_http_wait_use_declared_bounds`** (test_vault.py / test_http.py) — with a
    patched `requests.get` failing: probe `{timeout: 0.3, interval: 0.05}` → `EngineError`
    within ~0.3s (wall clock assertion with tolerance) naming the endpoint — expiry clause for
    both kinds; with no probe the loop constants equal the former 30/0.5 (regression: default
    equivalence).
23. **`test_operation_has_no_spec_action`** (test_operation.py) — docstring/contract-level:
    the documented action set is exactly insert/produce/put/stub; constructing a spec-typed
    payload op is ordinary data (no special branch anywhere — grep-level assertion in the test
    suite's contract test).

### `tests/sandbox/`

24. **`test_sandbox_start_applies_startup_data_in_fixed_order`** (test_sandbox.py, unit with
    FakeEngine recording) — Setup: config with vault + http + postgres services and all three
    data sections; FakeEngine records `start(startup)`. Input: `sandbox.start()` (runtime probe
    and container patched). Assertions: each engine's startup list orders put → stub → sql for
    its kind; kafka engine's list is empty; engines start in declaration order; render called
    with mapped addresses; instance container started last with the rendered env. Sufficiency:
    vault → http → postgres order criterion (integration-level assertion over `_startup_operations`).
25. **`test_sandbox_uses_instance_and_services_keys`** — `Sandbox(config)` builds engines from
    `config.services` and the container from `config.instance` (FakeEngine/FakeService spies);
    `postgresql("db")` returns the view bound to the current batch; unknown name / kind mismatch
    lists configured services.
26. **`test_service_container_port_only_default_and_health_path`** (test_service_container.py) —
    FakeSocket/requests: no probe → TCP loop with 30.0/0.5; probe with `path: /healthz` → GET
    loop until 2xx. Assertions on probe calls and bounds. Sufficiency: the path knob applies
    only to the instance entry; port-only default preserved.
27. **`test_service_container_deadline_expires_as_engine_error`** — probe
    `{timeout: 0.2, interval: 0.05}`, port never opens → `EngineError` naming the image, the
    port check, and the deadline; and never a
    bare `RuntimeError` (assert `isinstance(exc, EngineError)`). Sufficiency: the new
    `ServiceContainer` contract clause.
28. **`test_activation_arms_from_new_document_path`** (test_activation.py) — tmp_path with the
    document under the tools home; `activate_sandbox(context)` → config returned, three hooks
    registered; without the document → `None`, context untouched (inertness).
29. **`test_presets_type_and_enqueue`** (test_presets.py + activation loop) — `services(...)`
    with the nested dict shape marks the test; enqueue resolves names against services and
    orders preset declarations ahead of in-test operations.

### `tests/plugin/test_install.py`

30. **`test_install_arms_sandbox_through_new_path`** — Setup: tmp_path repo with
    `.goga/tools/pybuggy/sandbox.yml`; `monkeypatch.chdir`; `install(context=ctx)`. Trace:
    `activate_sandbox` reads the new path → armed → plugin constructed with
    `sandbox_activation` set. Assertions: `plugin.sandbox_activation` is the `SandboxConfig`;
    hooks present in `ctx`. Negative: no document → `sandbox_activation is None`, no hooks.
    Sufficiency: plugin arming rides the new path (task scope).
31. **`test_configure_rejects_base_url_with_active_sandbox`** — armed plugin + passed
    `--base-url` → `pytest.UsageError` naming the new document path (the companion text
    change).

## Usages / `.usages/` Consistency (Phase 4 Step 6)

The four cell-level `.usages/` files were materialized by apply-architecture and re-verified
here against the manifests: APIs named match the signatures (`SandboxConfig(instance, services,
data)`, `probe` blocks, inline `topics`, `produce` topic note, activation path); block-style
YAML throughout; no references to the former path or former keys (grep-verified); each file
covers one functional domain. No further `.usages/` changes are needed from this design — the
remaining author-facing sweep lives in docs/README/mkdocs (§ Companion Work Items). Per the DSL:
no CODEMANIFEST `Usages` references point at own `.usages/` files (they are consumer docs).

Practices audit (every connected practice referenced in ≥1 annotation, bridging via annotations
only): config — `conventions`, `ruamel-yaml` ✓; engines — `conventions`, `testcontainers`,
`psycopg`, `kafka-python`, `requests`, `mokapi`, `vault-dev`, `wiremock` ✓; data —
`conventions` ✓; sandbox — `conventions`, `testcontainers`, `jinja2`, `requests`, `pluginator`
+ imported `sandbox-file`, `data-operations` ✓. External interactions route through the
declared practices (no bypass imports): container lifecycle via testcontainers, HTTP planes via
requests, kafka via kafka-python/mokapi, YAML via ruamel.

## Verification Checklist

- `goga lint` — 0 errors (already true pre-implementation; manifests untouched by this design).
- Facades: `python -c "from goga_tool_pybuggy.sandbox.config import SandboxConfig,
  InstanceConfig, ServiceConfig, StartupData, ProbeConfig, TopicConfig, load_sandbox_config"`;
  `... from goga_tool_pybuggy.sandbox.engines import build_engine, BaseEngine, EngineError"`;
  `... from goga_tool_pybuggy.sandbox import Sandbox, activate_sandbox, active_sandbox"`;
  root re-exports `active_sandbox`, `services` unchanged.
- `pytest tests/ -x` green; docker-gated suites run when the runtime is available, skip
  otherwise.
- Repo sweep: `grep -rn "\.sandbox\.yml"` over `docs/`, `README.md`, `mkdocs.yml`,
  `goga_tool_pybuggy/**/*.usages/`, `.goga/usages/cooks/` → empty.
- Default-equivalence: with no probe declarations, every readiness loop runs at 30.0/0.5 —
  the former constants (D6 single source; scenario 16/22).
