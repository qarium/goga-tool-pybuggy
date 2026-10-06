# Architecture Plan — sandbox

## Topic

**sandbox** — session-scoped isolated service-testing capability inside pybuggy.

Plan path: `.goga/history/2026/feature-sandbox/arch.md` (from `goga history path -f arch.md`).
Source documents: task `.goga/history/2026/feature-sandbox/task.md`, ADR `adr.md` (accepted 2026-10-06), PRD `prd.md`.

## Implementation Order

Cells ordered leaves → root; each step names its reason:

1. **`goga_tool_pybuggy/sandbox/config`** — CREATE. Leaf cell: no Imports. Provides the configuration models every other sandbox cell consumes.
2. **`goga_tool_pybuggy/sandbox/engines`** — CREATE. Depends on `sandbox/config` (imports `InstanceConfig`). Provides the engine contract, the engine factory, the operation/address primitives, and the runtime probe.
3. **`goga_tool_pybuggy/sandbox/data`** — CREATE. Depends on `sandbox/engines` (imports `DataOperation`, `InstanceAddress`).
4. **`goga_tool_pybuggy/sandbox`** — CREATE (subtree root). Depends on `sandbox/config` (`SandboxConfig`, `ServiceConfig`, `StartupData`, `load_sandbox_config`), `sandbox/engines` (`BaseEngine`, `build_engine`, `DataOperation`, `InstanceAddress`, `check_runtime`), `sandbox/data` (`DataBatch` + the four instance views).
5. **`goga_tool_pybuggy/plugin`** — MODIFY. Depends on `goga_tool_pybuggy/sandbox` (new Imports: `activate_sandbox`, `active_sandbox`, `Sandbox`) and `goga_tool_pybuggy/sandbox/config` (`SandboxConfig`); existing Imports (api, plugin/loaders) unchanged.
6. **`goga_tool_pybuggy/commands/init`** — MODIFY. No new type imports; the `run_bootstrap` step-2 scope extension references the sandbox subtree layout created in steps 1–4.
7. **`goga_tool_pybuggy`** — MODIFY (composition root). Depends on `goga_tool_pybuggy/sandbox` and `goga_tool_pybuggy/sandbox/data` (new Imports + embeddings).

Rationale for the whole order: a cell can be assembled only after everything it imports exists (cookbook design order); the root facade closes the chain.

## Artifacts

### 1. `goga_tool_pybuggy/sandbox/config` — CREATE

#### `goga_tool_pybuggy/sandbox/config/CODEMANIFEST`

```yaml
Usages:
  conventions: .goga/usages/conventions.md
  ruamel-yaml: .goga/usages/cooks/ruamel-yaml.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `conventions` for the pydantic kw_only data models and the docstring rules.
  Use `ruamel-yaml` for reading the sandbox configuration document.

  Sandbox configuration cell. Owns the declarative model of .sandbox.yml — the service-under-test
  entry, the named dependency instances, and the startup data layer — and its fail-fast reading.
  An invalid document fails before anything starts, with an error naming the file location and the
  offending entry. Use relative imports inside the cell.

---

"SandboxConfig(service: ServiceConfig, instances: dict[str, InstanceConfig], data: StartupData)":
  location: sandbox_config.py
  annotations: |
    Root model of the sandbox configuration: the service under test, the dependency instances keyed
    by name, and the startup data layer.

    `service`: the service-under-test entry.
    `instances`: dependency instance entries keyed by instance name; several instances of one kind
    are allowed.
    `data`: the startup data layer declarations.

    Requirements:
    - pydantic model, kw_only; the data sections default empty; the service entry is required.

    Use `conventions` for the data-model rules.
  properties:
    "service -> ServiceConfig": |
      The service-under-test entry.
    "instances -> dict[str, InstanceConfig]": |
      Dependency instance entries keyed by instance name.
    "data -> StartupData": |
      The startup data layer declarations.

"ServiceConfig(image: str, env: dict[str, str], port: int, health: str | None)":
  location: service.py
  annotations: |
    Service-under-test entry.

    `image`: the container image of the service under test.
    `env`: environment values; values may carry instance address placeholders resolved at sandbox
    start.
    `port`: the container port the service serves on.
    `health`: optional health path for readiness; None waits for the port only.
  properties:
    "image -> str": |
      Container image of the service under test.
    "env -> dict[str, str]": |
      Environment values; values may carry instance address placeholders.
    "port -> int": |
      Container port the service serves on.
    "health -> str | None": |
      Health path for readiness; None means port readiness only.

"InstanceConfig(name: str, kind: str, image: str | None)":
  location: instance.py
  annotations: |
    One named dependency instance declaration.

    `name`: the instance name — the key tests address the instance by and the placeholder name used
    inside service env values.
    `kind`: the dependency kind — postgresql, kafka, vault, or http.
    `image`: optional image override; absent keeps the product-pinned default of the kind.

    Constraints:
    - Do not accept any kind outside the four supported ones.
  properties:
    "name -> str": |
      Instance name — the addressable key and the placeholder name.
    "kind -> str": |
      Dependency kind: postgresql, kafka, vault, or http.
    "image -> str | None": |
      Image override; None keeps the product-pinned default.

"StartupData(vault: dict[str, list[dict[str, object]]], http: dict[str, list[dict[str, object]]], kafka: dict[str, str], postgres: dict[str, list[str]])":
  location: startup_data.py
  annotations: |
    Startup data layer declarations, in the fixed section order — vault secrets, http mappings, the
    kafka spec, then postgres init.

    `vault`: instance name → secret declarations (path, data).
    `http`: instance name → stub mapping declarations (request, response).
    `kafka`: instance name → AsyncAPI spec file path; the section converts to one startup `spec`
    operation per kafka instance, the payload carrying the document path.
    `postgres`: instance name → init SQL statements.

    Requirements:
    - Sections default empty; declarations target instances by name.
    - Within a section, the declaration order is the application order.

    Constraints:
    - Do not reorder declarations — data dependencies are expressed by declaration order.

    Use `conventions` for the data-model rules.
  properties:
    "vault -> dict[str, list[dict[str, object]]]": |
      Instance name → secret declarations (path, data).
    "http -> dict[str, list[dict[str, object]]]": |
      Instance name → stub mapping declarations (request, response).
    "kafka -> dict[str, str]": |
      Instance name → AsyncAPI spec file path.
    "postgres -> dict[str, list[str]]": |
      Instance name → init SQL statements.

"load_sandbox_config(path: str | None) -> config: SandboxConfig | None":
  location: loader.py
  annotations: |
    Read and validate the sandbox configuration document `.sandbox.yml` at the root of the consumer
    service test repository.

    `path`: explicit document location; None resolves `.sandbox.yml` in the current working
    directory.
    `config`: the validated configuration model; None when the document is absent — the sandbox
    stays fully inert.

    Algorithm:
    1. Resolve the document location; an absent document returns None.
    2. Parse the document; an unparsable document fails with an error naming the location and the
    parse problem.
    3. Validate the service entry — image, env, port are required; health is optional.
    4. Validate every instance entry — a non-empty unique name and a kind of postgresql, kafka,
    vault, or http; the grpc kind fails with an explicit "not supported yet" error; an image
    override is optional.
    5. Validate the startup data sections — every declaration targets an existing instance of the
    matching kind.
    6. Return the model.

    Requirements:
    - Validation completes fully before anything is started — no container is created for an
    invalid document.
    - Every failure message names the document location and the offending entry.

    Constraints:
    - Do not default or repair invalid entries — fail fast.
    - Do not read anything beyond the named document.

    Use `ruamel-yaml` for document parsing.
    Use `conventions` for type hints and testing.

---

Author: Goga
CreatedAt: 06/10/26
Description: |
  Sandbox configuration cell — the declarative .sandbox.yml models and their fail-fast reading.
```

#### `goga_tool_pybuggy/sandbox/config/.usages/sandbox-file.md`

```md
# Sandbox file — authoring `.sandbox.yml`

## Domain

The declarative description of one service sandbox: the service under test, its mocked dependency
instances, and the data they start with. Target audience: service test authors. The file lives at
the root of the service test repository; its presence alone activates the sandbox for every pytest
run, and an invalid file fails the run before anything starts.

## File layout

```yaml
service:
  image: my-service:latest        # required — the image under test
  port: 8080                      # required — the container port the service serves on
  health: /health                 # optional — readiness path; omit to wait for the port only
  env:                            # required — environment values of the service
    DATABASE_URL: "postgres://{{db.host}}:{{db.port}}/app"
    KAFKA_BOOTSTRAP: "{{events.host}}:{{events.port}}"
    VAULT_ADDR: "http://{{secrets.host}}:{{secrets.port}}"

instances:                        # named dependency instances; several of one kind are allowed
  db:       { kind: postgresql, image: postgres:16-alpine }
  events:   { kind: kafka }
  secrets:  { kind: vault }
  payments: { kind: http }

data:                             # startup data layer, applied before the service starts
  vault:
    secrets:
      - { path: "payment/api-key", data: { api_key: "test-key", ttl: "1h" } }
  http:
    payments:
      - request:  { method: POST, urlPath: /v1/charge }
        response: { status: 200, jsonBody: { status: "captured" } }
  kafka:
    events: "asyncapi.yaml"       # AsyncAPI document path — defines the mocked topics
  postgres:
    db:
      - "CREATE TABLE IF NOT EXISTS orders (id bigint PRIMARY KEY, customer text, total numeric)"
```

## Instances

- Every instance has a name (the key) and a `kind`: `postgresql`, `kafka`, `vault`, or `http`.
- `image` overrides the product-pinned default image of the kind — omit it for the default.
- Any subset of kinds may be configured; configure only the dependencies the service needs.
- A `grpc` kind is rejected at startup with an explicit "not supported yet" error.

## Wiring the service to its dependencies

Service env values are Jinja2 templates over the started instance addresses:

- `{{<instance>.host}}` and `{{<instance>.port}}` resolve to the mapped address of the named
  instance — e.g. `{{db.host}}` / `{{db.port}}` for the instance named `db`.
- Placeholders resolve only for configured instance names; an unknown name fails validation.
- Values without placeholders pass through unchanged.

## Startup data layer

Applied in a fixed order after all instances are up and before the service starts:

| section | target | declarations |
|---|---|---|
| `vault` | vault instances | `{path, data}` secret writes |
| `http` | http instances | WireMock mapping objects (`request` + `response`) |
| `kafka` | kafka instances | AsyncAPI spec file path (topics of the mock) |
| `postgres` | postgresql instances | SQL statements (schema/bootstrap SQL) |

Within a section, declarations apply in the order written — for dependent rows (foreign keys),
declare parents before children.

## Preconditions and constraints

- The file name and location are fixed: `.sandbox.yml` at the repository root.
- An invalid file (unknown kind, unknown instance reference, missing required field, unparsable
  YAML) fails the run before any container starts, with an error naming the entry.
- Without the file the product is fully inert — nothing starts, nothing changes.
- A container runtime must be available in the environment running the tests.
```

### 2. `goga_tool_pybuggy/sandbox/engines` — CREATE

#### `goga_tool_pybuggy/sandbox/engines/CODEMANIFEST`

```yaml
Imports:
  - Types:
      - InstanceConfig
    From: goga_tool_pybuggy/sandbox/config

Usages:
  conventions: .goga/usages/conventions.md
  testcontainers: .goga/usages/cooks/testcontainers.md
  psycopg: .goga/usages/cooks/psycopg.md
  kafka-python: .goga/usages/cooks/kafka-python.md
  mokapi: .goga/usages/cooks/mokapi.md
  vault-dev: .goga/usages/cooks/vault-dev.md
  wiremock: .goga/usages/cooks/wiremock.md
  requests: .goga/usages/cooks/requests.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `conventions` for structured logging and the docstring rules.
  Use `testcontainers` for the container lifecycle of every instance: the runtime probe, module and
  generic containers, readiness waiting, labels, and the stop guarantee.
  Use `psycopg` for the postgresql data plane.
  Use `kafka-python` for producing into the kafka mock.
  Use `requests` for the HTTP data planes of the vault and http kinds.
  Use `mokapi` for the kafka mock container contract.
  Use `vault-dev` for the vault mock container contract.
  Use `wiremock` for the http mock container contract.

  Per-kind instance engines cell. One engine owns one started dependency instance: its container,
  its data plane, its baseline journal, and its reset. A common base carries the journal replay
  every kind shares; each kind implements its own wipe. Every failure surfaces as a readable error
  identifying the instance and the failed operation. Use relative imports inside the cell.

---

"DataOperation(instance: str, kind: str, action: str, payload: dict[str, object])":
  location: operation.py
  annotations: |
    One declared data operation targeted at a named instance — the uniform unit of startup data,
    per-test presets, in-test operations, and the baseline journal.

    `instance`: the target instance name.
    `kind`: the dependency kind of the target.
    `action`: the operation — insert, produce, put, or stub.
    `payload`: the operation body — the same fields the matching instance view operation accepts.

    Requirements:
    - pydantic model, kw_only; payloads are plain serializable data.
    - The action set is fixed per kind: insert for postgresql, produce for kafka, put for vault,
    stub for http. The startup-only `spec` action carries the kafka AsyncAPI document path — it
    mounts the document at container start and never executes against the data plane.

    Use `conventions` for the data-model rules.
  properties:
    "instance -> str": |
      The target instance name.
    "kind -> str": |
      The dependency kind of the target.
    "action -> str": |
      The operation: insert, produce, put, stub, or the startup-only spec.
    "payload -> dict[str, object]": |
      The operation body.

"InstanceAddress(host: str, port: int)":
  location: address.py
  annotations: |
    The mapped address of one started instance.

    `host`: the host clients use to reach the instance.
    `port`: the published host-side port.

    Requirements:
    - pydantic model, kw_only.
    - Addresses are read back from the container engine after start — a fixed host port is never
    assumed.

    Use `conventions` for the data-model rules.
  properties:
    "host -> str": |
      The host clients use to reach the instance.
    "port -> int": |
      The published host-side port.

"check_runtime()":
  location: runtime.py
  annotations: |
    Probe the container runtime availability before anything starts.

    Algorithm:
    1. Probe daemon reachability.
    2. An unreachable runtime fails with an actionable error naming the requirement — a
    docker-compatible container runtime must be available in the environment running the tests.

    Requirements:
    - The probe runs before the first container start of a session.
    - The failure is immediate and actionable — tests never hang on a silent connection timeout.

    Constraints:
    - Do not start anything here — probe only.

    Use `testcontainers` for the runtime requirement and the daemon communication.

"build_engine(config: InstanceConfig) -> engine: BaseEngine":
  location: runtime.py
  annotations: |
    Build the engine of the configured instance kind.

    `config`: the instance declaration.
    `engine`: the engine of the instance's kind.

    Algorithm:
    1. Map the instance kind to its engine — postgresql, kafka, vault, or http.
    2. An unmapped kind fails with the supported kinds listed.

    Requirements:
    - The image override of `config` reaches the built engine.

    Use `conventions` for type hints and testing.

"BaseEngine(config: InstanceConfig)":
  location: base.py
  annotations: |
    Common per-instance engine contract: start the instance, execute operations, hold the baseline
    journal, reset, stop. The reset behavior is shared — wipe to the kind's empty state, then
    replay the journal.

    `config`: the instance declaration — name, kind, image override.

    Requirements:
    - The journal records the startup operations and every operation applied inside the baseline
    boundary, in application order — the journal is the full session baseline.
    - Readiness completes before start returns.
    - Stop removes the container and closes the data-plane connection; stopping a stopped instance
    is safe.

    Constraints:
    - Do not touch the service under test — engines own dependency instances only.
    - Do not execute operations before start completes.

    Use `testcontainers` for the container lifecycle and the cleanup safety net.
    Use `conventions` for type hints and testing.
  properties:
    "address -> InstanceAddress": |
      The mapped address of the started instance, read back from the container engine — the value
      the service env placeholders and the instance views consume.
  methods:
    "start(startup: list[DataOperation])": |
      Start the instance container and bring it to readiness.

      `startup`: the startup data of this instance, in declaration order.

      Algorithm:
      1. Build the kind's container — the product-pinned image unless the config overrides it,
      labeled for sandbox identification, with the service port published.
      2. Start the container and wait for readiness.
      3. Open the data-plane connection.
      4. Apply the startup operations in order and record them into the journal as the initial
      baseline entries — the startup data is part of the baseline every reset replays.

      Requirements:
      - Start returns only after the instance is ready and the startup data is applied and
      journaled.
      - A failed start surfaces an actionable error and leaves nothing behind.

      Use `testcontainers` for the container start and readiness waiting.
    "apply(operations: list[DataOperation])": |
      Execute operations against the instance data plane, in order, as one consistent batch.

      `operations`: operations of this instance's kind, in application order.

      Algorithm:
      1. Execute each operation through the kind's data plane.
      2. A failed operation raises a readable error identifying the instance, the operation, and
      the cause.

      Requirements:
      - Order is preserved — data dependencies (for example foreign-key chains) are expressed by
      operation order.

      Constraints:
      - Do not record into the journal here — recording belongs to the baseline boundary.
    "record(operations: list[DataOperation])": |
      Append operations to the baseline journal.

      `operations`: applied operations to remember as the baseline.

      Requirements:
      - The journal order is the application order; replay reproduces the baseline exactly.
    "reset()": |
      Return the instance to its baseline.

      Algorithm:
      1. Wipe the instance to the kind's empty state.
      2. Replay the journal through the same execution path as apply.

      Requirements:
      - After reset the instance holds exactly the baseline state — no test data remains.
    "stop()": |
      Remove the container and close the data-plane connection.

      Requirements:
      - Safe on an already-stopped instance.
      - Removal is guaranteed — the explicit stop plus the cleanup safety net.

"BaseEngine::PostgresEngine(config: InstanceConfig)":
  location: postgres.py
  annotations: |
    postgresql kind — a real postgres instance.

    Container: the postgres module container with the product-pinned default image; module
    readiness applies — start returns after the server accepts connections.
    Data plane: SQL over the postgres driver — insert executes parameterized inserts; startup
    statements execute as given.
    Wipe: discover the user tables from the catalog at reset time, then truncate them all with
    identity restart and cascade — the cascade carries the foreign-key ordering; the container is
    never restarted.

    Requirements:
    - One connection for the session in autocommit mode, closed on stop.
    - Catalog discovery runs at every reset — the table set may change mid-session.

    Constraints:
    - Do not format SQL with interpolated values — parameters are bound server-side.

    Use `psycopg` for the data plane and the catalog-driven reset.
    Use `testcontainers` for the postgres module container.

"BaseEngine::KafkaEngine(config: InstanceConfig)":
  location: kafka.py
  annotations: |
    kafka kind — the kafka mock instance.

    Container: the kafka mock image; the startup `spec` operation mounts the AsyncAPI document and
    passes it as the start argument of the container — topics come from the spec; readiness waits
    for the HTTP health side.
    Data plane: the kafka protocol — messages are produced with the producer client against the
    mapped bootstrap address; delivery is confirmed at the batch boundary.
    Wipe: restart the container — all state is in-memory, the topology returns from the spec on
    boot, and the baseline replays on top. Replaying the journaled startup spec operation after a
    restart is an idempotent no-op — the spec is already mounted and passed at boot.

    Requirements:
    - The producer is created against the mapped address and closed on stop.
    - A broken bootstrap fails within the operation deadline — never hangs.

    Use `mokapi` for the container contract and the two planes.
    Use `kafka-python` for producing.
    Use `testcontainers` for the generic container and the restart-based wipe.

"BaseEngine::VaultEngine(config: InstanceConfig)":
  location: vault.py
  annotations: |
    vault kind — the secrets mock instance in dev mode.

    Container: the official vault image in dev mode — in-memory storage, plain HTTP,
    auto-initialized, auto-unsealed, with the fixed dev root token; readiness waits for the health
    endpoint.
    Data plane: KV v2 over HTTP with the token header — put writes a secret at a path; startup
    declarations write the same way.
    Wipe: restart the container (storage is in-memory) and replay the baseline.

    Requirements:
    - The dev token is a fixed test credential — never a real secret, never logged.
    - A failed write maps to a readable error naming the path.

    Use `vault-dev` for the container contract and the KV v2 paths.
    Use `requests` for the HTTP data plane.
    Use `testcontainers` for the generic container and the restart-based wipe.

"BaseEngine::HttpEngine(config: InstanceConfig)":
  location: http.py
  annotations: |
    http kind — the http mock instance.

    Container: the http mock image with the admin port published; readiness waits for the admin
    endpoint.
    Data plane: stub mappings created over the admin API — unmatched requests get a visible
    near-miss response, so wiring mistakes surface in test failures.
    Wipe: reset the mappings over the admin API and replay the baseline journal.

    Requirements:
    - Mapping declarations pass through as mapping objects — matching, priority, delays, and faults
    stay available to authors.

    Use `wiremock` for the admin API and the reset endpoints.
    Use `requests` for the HTTP data plane.
    Use `testcontainers` for the generic container.

---

Author: Goga
CreatedAt: 06/10/26
Description: |
  Per-kind dependency instance engines of the sandbox — containers, data planes, baseline
  journals, and resets.
```

#### `.usages/` files

None — internal cell; consumer stories live in `sandbox/config`, `sandbox`, `sandbox/data`.

### 3. `goga_tool_pybuggy/sandbox/data` — CREATE

#### `goga_tool_pybuggy/sandbox/data/CODEMANIFEST`

```yaml
Imports:
  - Types:
      - DataOperation
      - InstanceAddress
    From: goga_tool_pybuggy/sandbox/engines

Usages:
  conventions: .goga/usages/conventions.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `conventions` for the docstring rules.

  Data declaration surface of the sandbox. Instance views declare dependency-data operations from
  tests; presets declare them on the test itself; the batch accumulates the declared operations and
  hands them over as one consistent unit. Declarations are lazy — nothing is executed at
  declaration time. Use relative imports inside the cell.

---

"DataBatch()":
  location: batch.py
  annotations: |
    The accumulated operations of the current test.

    Requirements:
    - One batch per test; the batch empties when taken.
    - The accumulation order is the application order per instance — presets precede in-test
    operations.

    Use `conventions` for type hints and testing.
  methods:
    "add(operation: DataOperation)": |
      Append one operation to the batch. Nothing is executed.
    "take() -> operations: list[DataOperation]": |
      Drain the batch in accumulation order; the batch is empty afterwards.

"PostgresInstance(name: str, address: InstanceAddress, batch: DataBatch)":
  location: postgres.py
  annotations: |
    Test-facing view of a started postgresql instance.

    `name`: the instance name from the sandbox configuration.
    `address`: the mapped address of the started instance.
    `batch`: the accumulation target of declared operations.

    Requirements:
    - Operations declare only — execution happens when the session facade applies the batch.
  properties:
    "name -> str": |
      The configured instance name.
    "host -> str": |
      The mapped host — the value the service env placeholders resolve to.
    "port -> int": |
      The published port — the value the service env placeholders resolve to.
  methods:
    "insert(table: str, rows: list[dict[str, object]])": |
      Declare row inserts into one table. One call targets one table; rows apply in list order.
      For foreign-key chains across tables, declare parents first.

      `table`: the target table.
      `rows`: the rows to insert, in order.

"KafkaInstance(name: str, address: InstanceAddress, batch: DataBatch)":
  location: kafka.py
  annotations: |
    Test-facing view of a started kafka instance.

    `name`: the instance name from the sandbox configuration.
    `address`: the mapped address of the started instance.
    `batch`: the accumulation target of declared operations.

    Requirements:
    - Operations declare only — execution happens when the session facade applies the batch.
  properties:
    "name -> str": |
      The configured instance name.
    "host -> str": |
      The mapped host — the value the service env placeholders resolve to.
    "port -> int": |
      The published port — the value the service env placeholders resolve to.
  methods:
    "produce(topic: str, value: dict[str, object] | str, key: str | None)": |
      Declare one message produce.

      `topic`: the target topic — it must exist in the instance's AsyncAPI spec.
      `value`: the message value.
      `key`: the optional partition key.

"VaultInstance(name: str, address: InstanceAddress, batch: DataBatch)":
  location: vault.py
  annotations: |
    Test-facing view of a started vault instance.

    `name`: the instance name from the sandbox configuration.
    `address`: the mapped address of the started instance.
    `batch`: the accumulation target of declared operations.

    Requirements:
    - Operations declare only — execution happens when the session facade applies the batch.
  properties:
    "name -> str": |
      The configured instance name.
    "host -> str": |
      The mapped host — the value the service env placeholders resolve to.
    "port -> int": |
      The published port — the value the service env placeholders resolve to.
  methods:
    "put(path: str, data: dict[str, object])": |
      Declare one secret write.

      `path`: the secret path.
      `data`: the secret data.

"HttpInstance(name: str, address: InstanceAddress, batch: DataBatch)":
  location: http.py
  annotations: |
    Test-facing view of a started http instance.

    `name`: the instance name from the sandbox configuration.
    `address`: the mapped address of the started instance.
    `batch`: the accumulation target of declared operations.

    Requirements:
    - Operations declare only — execution happens when the session facade applies the batch.
  properties:
    "name -> str": |
      The configured instance name.
    "host -> str": |
      The mapped host — the value the service env placeholders resolve to.
    "port -> int": |
      The published port — the value the service env placeholders resolve to.
  methods:
    "stub(mapping: dict[str, object])": |
      Declare one stub mapping. Matching, priority, delays, and faults pass through as given.

      `mapping`: the mapping object of the http mock.

"services(...presets: dict[str, dict[str, list[dict[str, object]]]]) -> decorator: Callable":
  location: presets.py
  annotations: |
    Per-test data-preset decorator: kind-named arguments carrying instance-targeted declarations.

    `presets`: kind → instance name → declaration list; every declaration carries the same fields
    as the matching instance view operation.
    `decorator`: the marker applied to the test.

    Algorithm:
    1. Validate the declarations — only the four supported kinds; instance names must be known to
    the sandbox configuration.
    2. Mark the test with the presets.
    3. At the test's start the marked presets enqueue into that test's batch, ahead of any in-test
    operation.

    Requirements:
    - Presets apply only to the test declaring them.
    - Declaration order within one instance is the application order — parents before children for
    foreign-key chains.

    Constraints:
    - Do not execute anything at decoration time.

    Use `conventions` for type hints and testing.

---

Author: Goga
CreatedAt: 06/10/26
Description: |
  Data declaration surface of the sandbox — instance views, the lazy batch, and per-test presets.
```

#### `goga_tool_pybuggy/sandbox/data/.usages/data-operations.md`

```md
# Data operations — preparing dependency data in tests

## Domain

Declaring the data a service under test will see: rows in postgres, stub responses of http
dependencies, secrets in vault, messages in kafka topics. Target audience: service test authors.
Operations are declared from tests through instance views, or on the test itself as a preset; they
are lazy — the sandbox applies them as one consistent batch right before the first call to the
service under test.

## Reaching an instance

Every configured instance is reachable by name through the session fixture, kind-named:

```python
sandbox.postgresql("db").insert(...)   # a postgresql instance named db
sandbox.http("payments").stub(...)     # an http instance named payments
sandbox.vault("secrets").put(...)      # a vault instance named secrets
sandbox.kafka("events").produce(...)   # a kafka instance named events
```

Each view also exposes `name`, `host`, and `port` — `host` and `port` are the mapped address the
service env placeholders resolved to.

## Declaring operations

```python
sandbox.postgresql("db").insert("orders", rows=[{"id": 1, "total": 100}])

sandbox.http("payments").stub({
    "request": {"method": "POST", "urlPath": "/v1/charge"},
    "response": {"status": 200, "jsonBody": {"status": "captured"}},
})

sandbox.vault("secrets").put("payment/api-key", {"api_key": "test-key"})

sandbox.kafka("events").produce("orders.events", {"id": 1}, key="1")
```

Nothing is executed at declaration time. The sandbox applies the accumulated batch automatically
before the first call to the service under test — there is no manual apply.

## Per-test presets

Declare data directly on the test:

```python
from goga_tool_pybuggy import services

@services(
    postgresql={"db": [{"table": "customers", "rows": [{"id": 1, "name": "Ann"}]},
                       {"table": "orders", "rows": [{"id": 100, "customer_id": 1}]}]},
    http={"payments": [{"request": {"method": "GET", "urlPath": "/v1/rate"},
                        "response": {"status": 200, "jsonBody": {"rate": 0.5}}}]},
)
def test_checkout(api):
    ...
```

Each declaration carries the same fields as the matching view operation. Presets apply only to the
test declaring them, on top of the reset state, ahead of the test's own operations.

## Ordering and foreign keys

Operations apply in the order declared, per instance: presets first, then in-test operations in
call order; rows within one insert apply in list order. Foreign-key chains are expressed by
declaring parents before children — one `insert` call targets one table. Reset-side cleanup
needs no ordering from the author.

## Preconditions and side effects

- Instance names and kinds come from `.sandbox.yml`; an unknown name fails fast.
- A failed operation fails the test with a readable error identifying the operation.
- Read-back of dependency state is not part of this iteration — assert on service responses.
```

### 4. `goga_tool_pybuggy/sandbox` — CREATE (subtree root)

#### `goga_tool_pybuggy/sandbox/CODEMANIFEST`

```yaml
Imports:
  - Types:
      - SandboxConfig
      - ServiceConfig
      - StartupData
      - load_sandbox_config
    Usages:
      - sandbox-file
    From: goga_tool_pybuggy/sandbox/config
  - Types:
      - BaseEngine
      - build_engine
      - DataOperation
      - InstanceAddress
      - check_runtime
    From: goga_tool_pybuggy/sandbox/engines
  - Types:
      - DataBatch
      - PostgresInstance
      - KafkaInstance
      - VaultInstance
      - HttpInstance
    Usages:
      - data-operations
    From: goga_tool_pybuggy/sandbox/data

Usages:
  conventions: .goga/usages/conventions.md
  testcontainers: .goga/usages/cooks/testcontainers.md
  jinja2: .goga/usages/cooks/jinja2.md
  requests: .goga/usages/cooks/requests.md
  pluginator: .goga/usages/cooks/pluginator.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `conventions` for structured logging and the docstring rules.
  Use `testcontainers` for the service container lifecycle: the generic container, readiness
  waiting, labels, and the removal guarantee on every exit path.
  Use `jinja2` for rendering the service environment values.
  Use `requests` for health-path readiness probing.
  Use `pluginator` for registering the session lifecycle hooks into the caller namespace.

  Session runtime of the sandbox. One sandbox owns one pytest-session environment: the ordered
  startup of the dependency instances and the service under test, the readiness gates, the baseline
  boundary, the per-test reset, and the guaranteed removal on every exit path. Activation is
  presence-gated — without the configuration document nothing is registered and nothing runs.
  Startup progress is visible, and the startup output names the base_url source. Use relative
  imports inside the cell.

---

"Sandbox(config: SandboxConfig)":
  location: sandbox.py
  annotations: |
    The running session sandbox.

    `config`: the validated sandbox configuration.

    Requirements:
    - Stop removes everything on every exit path — success, failure, interruption.
    - The service address is readable as the base_url after start.
    - The session lifecycle owns one `DataBatch` per test: the registered per-test hook creates a
    fresh batch before the test, the instance views returned by postgresql/kafka/vault/http bind
    to it, and `apply_pending` takes exactly that batch; a new test never sees a previous test's
    operations.

    Constraints:
    - Do not start anything when the configuration is absent — activation owns the gate.
    - Do not restart the service container on reset — only dependency instance data resets.

    Use `sandbox-file` for the configuration semantics.
    Use `conventions` for type hints and testing.
  properties:
    "base_url -> str": |
      The service address of the running sandbox — the value the api fixture uses while a sandbox
      is active.
  methods:
    "start()": |
      Bring the sandbox up in the ordered sequence.

      Algorithm:
      1. Probe the container runtime availability via `check_runtime`.
      2. Start every configured instance engine — built with `build_engine` — with its startup
      data as `DataOperation` entries taken from the `StartupData` sections in the fixed order —
      vault secrets, http mappings, the kafka spec, then postgres init.
      3. Render the service environment values against the started instance addresses.
      4. Start the service container and wait for readiness — the port, or the health path when
      configured.
      5. Log the startup progress at every step, and the resolved service address with its source.

      Requirements:
      - Visible startup progress; tests run only after readiness.
    "stop()": |
      Remove everything the sandbox started.

      Requirements:
      - Runs on every exit path; safe when already stopped.
    "clear()": |
      Return every dependency instance to its baseline.

      Algorithm:
      1. Reset every instance engine — wipe and journal replay.

      Requirements:
      - After clear the instances hold exactly the baseline state; test order cannot change
      outcomes.

      Constraints:
      - The service container keeps running.
    "baseline() -> boundary: BaselineBoundary": |
      Open the session baseline boundary. Author fixture code runs inside the boundary; the
      boundary semantics belong to `BaselineBoundary`.
    "apply_pending()": |
      Apply the current test's accumulated operations as one consistent batch.

      Algorithm:
      1. Take the accumulated `DataBatch`.
      2. Group the operations by instance, preserving accumulation order.
      3. Apply each group to the instance's `BaseEngine`.

      Requirements:
      - Runs before the first service call of a test.
      - A failed operation surfaces a readable error identifying it.

      Use `data-operations` for the laziness contract.
    "ensure_service()": |
      Fail fast with a readable error when the service container has died — the error names the
      died service and attaches its output (`ServiceContainer.logs()`); a no-op while the service
      runs.

      Requirements:
      - Called on the request path — the api fixture's first-request guard invokes it — so a
      crashed service surfaces as an explicit died-service indication, never as a hang or an
      opaque connection failure.
    "postgresql(name: str) -> instance: PostgresInstance": |
      The test-facing view of the named postgresql instance.

      `name`: the instance name; an unknown name or a kind mismatch fails fast listing the
      configured instances.
    "kafka(name: str) -> instance: KafkaInstance": |
      The test-facing view of the named kafka instance.

      `name`: the instance name; an unknown name or a kind mismatch fails fast listing the
      configured instances.
    "vault(name: str) -> instance: VaultInstance": |
      The test-facing view of the named vault instance.

      `name`: the instance name; an unknown name or a kind mismatch fails fast listing the
      configured instances.
    "http(name: str) -> instance: HttpInstance": |
      The test-facing view of the named http instance.

      `name`: the instance name; an unknown name or a kind mismatch fails fast listing the
      configured instances.

"BaselineBoundary(sandbox: Sandbox)":
  location: baseline.py
  annotations: |
    The marked baseline boundary of the session.

    `sandbox`: the session sandbox whose instances the boundary governs.

    Requirements:
    - Inside the boundary, declared operations apply immediately and are recorded into the
    `BaseEngine` journals.
    - Closing the boundary freezes the journals as the session baseline.

    Constraints:
    - Do not accumulate lazily inside the boundary — operations apply at declaration time.
  methods:
    "open()": |
      Enter the boundary: instance operations switch to immediate apply and journal recording.
    "close()": |
      Leave the boundary: journals freeze as the baseline; operations return to lazy accumulation.

"ServiceContainer(config: ServiceConfig)":
  location: service_container.py
  annotations: |
    The running service under test.

    `config`: the service entry — image, env, port, optional health path.

    Requirements:
    - Readiness completes before start returns — the port, or the health path when configured.
    - The container is labeled for sandbox identification and removed on stop.
    - A died service is detectable and its output is readable for diagnostics.

    Constraints:
    - Do not restart the service on reset.

    Use `testcontainers` for the generic container and readiness waiting.
    Use `requests` for health-path probing.
  properties:
    "host -> str": |
      The mapped host of the service.
    "port -> int": |
      The published port of the service.
  methods:
    "start(env: dict[str, str])": |
      Start the service image with the rendered environment.

      `env`: fully rendered values — placeholders already resolved.
    "stop()": |
      Remove the container; safe when already stopped.
    "alive() -> alive: bool": |
      Whether the service container still runs — the input of the died-service indication carried
      by `Sandbox`.
    "logs() -> output: str": |
      The service output, attached to the died-service indication carried by `Sandbox`.

"render_service_env(env: dict[str, str], addresses: dict[str, InstanceAddress]) -> rendered: dict[str, str]":
  location: env_render.py
  annotations: |
    Render the service environment values against the started instance addresses.

    `env`: the raw environment values of the service entry.
    `addresses`: instance name → mapped address.
    `rendered`: the values with every instance placeholder resolved.

    Algorithm:
    1. Build the rendering context — one entry per instance name, exposing host and port.
    2. Render every value strictly — an unknown placeholder fails naming the value.

    Use `jinja2` for the rendering engine and the strict undefined behavior.
    Use `sandbox-file` for the placeholder syntax.

"activate_sandbox(context: dict[str, object]) -> config: SandboxConfig | None":
  location: activation.py
  annotations: |
    Activate the sandbox for the pytest session — presence-gated, called from the plugin
    installation entry.

    `context`: the caller namespace the lifecycle hooks land in.
    `config`: the validated configuration — the armed activation; None when the document is absent
    and nothing is registered.

    Algorithm:
    1. Read and validate the configuration document via `load_sandbox_config`; an invalid document
    fails before anything starts.
    2. Register the session lifecycle into `context` — start before the first test with visible
    progress, stop at session end on every exit path.
    3. Register the per-test enqueue of marked presets ahead of the test's own operations.
    4. Name the base_url source in the startup output — the sandbox address overrides the
    configured value.

    Requirements:
    - Without the document the call is fully inert — no hooks, no containers, no side effects.

    Constraints:
    - Do not start containers here — start belongs to the registered session lifecycle.

    Use `pluginator` for the hook registration into the caller namespace.
    Use `sandbox-file` for the activation document semantics.
    Use `conventions` for type hints and testing.

"active_sandbox() -> sandbox: Sandbox | None":
  location: activation.py
  annotations: |
    The running session sandbox — the lookup seam.

    `sandbox`: the running sandbox; None before start and when inactive.

    Requirements:
    - Resolves the same session sandbox object on every call within a session.

    Constraints:
    - Do not start anything here — lookup only.

    Use `conventions` for type hints and testing.

---

Author: Goga
CreatedAt: 06/10/26
Description: |
  Session runtime of the sandbox — ordered lifecycle orchestration, the service container, and
  pytest activation.
```

#### `goga_tool_pybuggy/sandbox/.usages/sandbox-session.md`

```md
# Sandbox session — fixtures, baseline, and reset

## Domain

The pytest integration of the sandbox: how a consumer suite activates it, declares the session
baseline, resets between tests, and reaches the service under test through the api fixture.
Target audience: service test authors.

## Activation

The sandbox activates by presence: `.sandbox.yml` at the repository root. The same plugin
installation call that enables pybuggy arms the sandbox — nothing else is enabled:

```python
# conftest.py
from goga_tool_pybuggy import plugin

plugin.install()
```

With the file present, every pytest run starts the sandbox before the first test (the progress is
visible in the output); an invalid file fails the run before any container starts; without the
file the suite behaves exactly as it would without the sandbox.

## Session fixture and baseline

```python
# conftest.py
import pytest
from goga_tool_pybuggy import active_sandbox

@pytest.fixture(scope="session")
def sandbox():
    sbx = active_sandbox()
    with sbx.baseline():                      # the baseline boundary — author code
        sbx.postgresql("db").insert("customers", rows=[{"id": 1, "name": "Ann"}])
        sbx.vault("secrets").put("payment/api-key", {"api_key": "test-key"})
    yield sbx                                 # stop is product-owned — do not stop manually
```

Operations inside the baseline boundary apply immediately and become the session baseline: after
every reset the instances return to exactly this state.

## Per-test reset

```python
# conftest.py
@pytest.fixture(autouse=True)
def _sandbox_reset(sandbox):
    sandbox.clear()
    yield
```

Reset returns every dependency instance to the baseline — test order cannot change outcomes. Only
dependency data resets; the service container keeps running (service in-memory state not
resetting is an accepted v1 limitation).

## Calling the service

Tests use the standard api fixture unchanged — its address resolves from the sandbox:

```python
from goga_tool_pybuggy.api import Api, Endpoint

@pytest.fixture(scope="function")
def checkout(api: Api) -> Endpoint:
    return Endpoint(api, "/checkout", method="POST")

def test_checkout(checkout, sandbox):
    sandbox.postgresql("db").insert("orders", rows=[{"id": 100, "customer_id": 1}])
    response = checkout(json={"customer": 1, "total": 500})
    response.expect.has_status_code(200)
```

- The sandbox address overrides the configured base_url value; the startup output names the
  source.
- A typed `--base-url` flag together with an active sandbox fails fast with an explicit error.
- Declared operations apply automatically as one batch before the first service call.

## Preconditions and side effects

- The environment running the tests needs a docker-compatible container runtime; the startup error
  names the requirement when it is missing.
- After the session — including failed or interrupted runs — nothing remains; a rerun starts
  fresh.
- A crashed service fails the affected tests with an indication that the service died and where
  its output is.
```

### 5. `goga_tool_pybuggy/plugin` — MODIFY (diff)

Existing `goga_tool_pybuggy/plugin/CODEMANIFEST` stands. Changes:

**ADD — Imports entries (after the existing plugin/loaders entry):**

```yaml
  - Types:
      - activate_sandbox
      - active_sandbox
      - Sandbox
    Usages:
      - sandbox-session
    From: goga_tool_pybuggy/sandbox
  - Types:
      - SandboxConfig
    From: goga_tool_pybuggy/sandbox/config
```

**ADD — Global annotation paragraphs (appended to the existing `Annotations` block):**

```yaml
  The plugin carries the sandbox activation: the installation entry arms the sandbox when the
  sandbox configuration document is present, and the api fixture resolves the service address of a
  running sandbox ahead of the configured value. Use `sandbox-session` for the consumer fixture
  patterns of the sandbox.
```

**CHANGE — `install(...kwargs: dict)` annotation:** insert a new algorithm step after the context-resolution step (numbering of the following steps shifts by one); add one requirement:

```yaml
    Algorithm (new step 2):
    2. Arm the sandbox activation — call `activate_sandbox` with `context`. A present sandbox
    document registers the session lifecycle hooks into the same namespace; an absent document
    changes nothing. Keep the returned activation on the plugin as the armed state for the
    configure-time base_url check.

    Requirements (added):
    - The same installation call enables the plugin and arms the sandbox — no new enablement
    surface exists.
```

**ADD — `ApiPlugin` property:**

```yaml
    "sandbox_activation -> SandboxConfig | None": |
      The armed sandbox activation — the validated configuration when the sandbox document armed
      the session; None when inactive. Set by the installation entry; read by the configure-time
      base_url check.
```

**CHANGE — `ApiPlugin.configure()` annotation:** insert a new algorithm step after the CLI-option collection step; add one requirement:

```yaml
    Algorithm (new step):
    3. Fail fast when the user typed the base_url CLI flag and `sandbox_activation` is armed — an
    explicit CLI base URL combined with an active sandbox is a configuration error; the error
    names both facts and the run stops before any test.

    Requirements (added):
    - The fail-fast precedes any container start and any test execution.
```

**CHANGE — `ApiPlugin.api()` fixture annotation:** replace algorithm step 1; insert a new step 3 (the first-request guard) after the yield step; the yield step (2) and the close step (renumbered to 4) stand; add one constraint:

```yaml
    Algorithm (changed steps):
    1. Resolve the base URL: when `active_sandbox` returns a running `Sandbox`, its `base_url`
    wins over the rendered option value; otherwise use the rendered `self.base_url`. Construct
    `Api` with the resolved value (headers, timeout, and the assert options unchanged).
    3. With a running sandbox, guard the request path so the test's first service call applies the
    sandbox's pending data batch before the request leaves and performs the `Sandbox` died-service
    check — a died service surfaces as an explicit error naming the service and where its output
    is; the tests stay unaware of the apply point.

    Constraints (added):
    - Do not render or mutate the base_url option in the fixture — substitution is a read-time
    choice between the rendered value and the sandbox address.
```

**CHANGE — `ApiPlugin.base_url` property annotation:** append one sentence:

```yaml
      When a sandbox is active, the api fixture substitutes the sandbox's service address for this
      option's value at fixture time; the option itself stays required and is rendered in configure
      exactly as before.
```

**MODIFY — `goga_tool_pybuggy/plugin/.usages/enable.md`:** append the self-contained section:

```md
## Sandbox activation

The same `plugin.install()` call also arms the pybuggy sandbox: when the consumer repository root
holds a `.sandbox.yml` document, the sandbox starts before the first test of every pytest session
(mock dependency instances and the service under test, with visible progress), and the api
fixture's address resolves to the sandbox's service. Without the document nothing changes — the
suite runs exactly as without the sandbox. A typed `--base-url` flag together with an active
sandbox fails fast with an explicit error: the sandbox owns the service address.
```

### 6. `goga_tool_pybuggy/commands/init` — MODIFY (diff)

Existing `goga_tool_pybuggy/commands/init/CODEMANIFEST` stands. Changes to the `run_bootstrap(template_mode: bool)` annotation only:

**REPLACE — algorithm step 2:**

```yaml
    2. Discover every .usages/*.md under the packaged usage roots — the api cell and the cells of
    the sandbox subtree that carry usage files; copy each into
    .goga/usages/cooks/pybuggy/<stem>.md — template mode: an existing target is skipped with an
    INFO log; bare mode: an existing target is overwritten.
```

**ADD — requirement:**

```yaml
    - The sandbox capability usage files land in the same cooks directory and register under the
    same pybuggy-<stem> usage keys and annotation lines — one distribution path, one registration
    path.
```

**REPLACE — constraint** (the old text forbade copying beyond `api/.usages` and would block the distribution):

```yaml
    - Do not copy usages beyond the packaged usage roots (the api cell and the sandbox subtree
    cells).
```

**MODIFY — `goga_tool_pybuggy/commands/init/.usages/init.md`:** update the bootstrap artifact-table row to:

```md
| `.goga/usages/cooks/pybuggy/<stem>.md` — the packaged capability usages (the api cell and the sandbox subtree cells) | template: skip existing (INFO); bare: overwrite |
```

### 7. `goga_tool_pybuggy` — MODIFY (diff, composition root)

Existing `goga_tool_pybuggy/CODEMANIFEST` stands. Changes:

**ADD — Imports entries** (after the existing plugin entry):

```yaml
  - Types: [active_sandbox]
    Usages: [sandbox-session]
    From: goga_tool_pybuggy/sandbox
  - Types: [services]
    Usages: [data-operations]
    From: goga_tool_pybuggy/sandbox/data
```

**ADD — Global annotation paragraph** (appended to the existing `Annotations` block):

```yaml
  The facade carries the sandbox capability surface: `active_sandbox` for consumer session fixtures
  and `services` for per-test data presets — one import source beside the plugin installation
  entry. Connected capability practices: `sandbox-session`, `data-operations`.
```

**ADD — Body embeddings** (after the existing `->install: {}` embedding):

```yaml
->active_sandbox: {}

->services: {}
```

**MODIFY — `goga_tool_pybuggy/.usages/assembly.md`:** append the facade-surface note:

```md
The facade also re-exports the sandbox capability surface — `active_sandbox` (the session-fixture
lookup of a running sandbox) and `services` (the per-test data-preset decorator) — so consumer
conftest files and tests import them from the package root: `from goga_tool_pybuggy import
active_sandbox, services`.
```

## Dependency Map

```
goga_tool_pybuggy (root, MODIFY)
├─ active_sandbox, Usages: sandbox-session      ← goga_tool_pybuggy/sandbox
├─ services, Usages: data-operations            ← goga_tool_pybuggy/sandbox/data
├─ (existing imports unchanged)

goga_tool_pybuggy/plugin (MODIFY)
├─ activate_sandbox, active_sandbox, Sandbox,
│  Usages: sandbox-session                      ← goga_tool_pybuggy/sandbox
├─ SandboxConfig                                ← goga_tool_pybuggy/sandbox/config
├─ (existing: Api, api usage ← goga_tool_pybuggy/api)
└─ (existing: BaseLoader, PackageLoader, ModuleLoader ← goga_tool_pybuggy/plugin/loaders)

goga_tool_pybuggy/commands/init (MODIFY)
├─ (existing imports unchanged; no new type imports)
└─ run_bootstrap step-2 scope: sandbox subtree .usages/ directories

goga_tool_pybuggy/sandbox (CREATE)
├─ SandboxConfig, ServiceConfig, StartupData, load_sandbox_config,
│  Usages: sandbox-file                         ← goga_tool_pybuggy/sandbox/config
├─ BaseEngine, build_engine, DataOperation,
│  InstanceAddress, check_runtime               ← goga_tool_pybuggy/sandbox/engines
├─ DataBatch, PostgresInstance, KafkaInstance, VaultInstance,
│  HttpInstance, Usages: data-operations        ← goga_tool_pybuggy/sandbox/data
└─ declares locally: Sandbox, BaselineBoundary, ServiceContainer,
   render_service_env, activate_sandbox, active_sandbox

goga_tool_pybuggy/sandbox/data (CREATE)
└─ DataOperation, InstanceAddress               ← goga_tool_pybuggy/sandbox/engines

goga_tool_pybuggy/sandbox/engines (CREATE)
└─ InstanceConfig                               ← goga_tool_pybuggy/sandbox/config

goga_tool_pybuggy/sandbox/config (CREATE) — leaf, no Imports
```

No cycles: the sandbox subtree imports nothing from `plugin`, `api`, or the root; `config` is the
sole leaf.

## Verification Checklist

After implementing each artifact, verify:

**`sandbox/config`**
- [ ] `goga lint` passes on the new CODEMANIFEST; `goga schema` shows the cell with its 5 types.
- [ ] Absent file → `load_sandbox_config` returns None; unparsable/invalid documents fail with the location and offending entry named; grpc kind → explicit "not supported yet".
- [ ] Unknown instance reference in `data`, duplicate instance names, and missing required service fields all fail fast.

**`sandbox/engines`**
- [ ] All four kinds satisfy the `BaseEngine` contract; reset = kind wipe + journal replay through the apply path; the journal carries the startup operations, so reset reproduces the startup data and the baseline.
- [ ] `build_engine` maps the four kinds to their engines; an unmapped kind fails listing the supported kinds; the image override reaches the built engine.
- [ ] postgres: catalog-discovered `TRUNCATE ... RESTART IDENTITY CASCADE` at every reset; parameterized inserts only.
- [ ] kafka: spec mounted and passed at start; produce confirmed at batch boundary; broken bootstrap fails within deadline.
- [ ] vault: KV v2 writes with the fixed dev token; token never logged.
- [ ] http: mappings created over `__admin`; reset via admin mappings reset + replay.
- [ ] Failed start/operation errors name the instance and the operation.

**`sandbox/data`**
- [ ] Declaration-time execution is absent (nothing runs until the facade applies the batch).
- [ ] Batch order: presets before in-test operations; row/list order preserved.
- [ ] `services` validates kinds/instance names at decoration, executes nothing, marks the test.

**`sandbox` (subtree root)**
- [ ] `start` follows the ordered steps (probe → engines+startup data in section order → env render → service → readiness) and logs progress + base_url source.
- [ ] `stop` removes everything on every exit path; safe when already stopped.
- [ ] `clear` resets engines only; the service container keeps running; `base_url` readable after start.
- [ ] Baseline boundary switches views to immediate apply + journal recording; close freezes journals.
- [ ] `activate_sandbox` fully inert without the document; registers session lifecycle + per-test preset enqueue into `context`.
- [ ] A died service fails the affected tests through the first-request guard — an explicit error naming the service and carrying its output (`ensure_service`).
- [ ] `active_sandbox` resolves the same object per session.

**`plugin` (modify)**
- [ ] Without `.sandbox.yml` the plugin behaves exactly as before (inert path, existing tests green).
- [ ] `--base-url` typed + armed activation → fail-fast in configure before tests/containers.
- [ ] `api` fixture: active sandbox address wins; first-request guard applies the pending batch once before the test's first service call; configure-phase rendering untouched.
- [ ] `enable.md` section added; existing enablement docs unchanged otherwise.

**`commands/init` (modify)**
- [ ] `pybuggy init` copies the sandbox capability usage files into `.goga/usages/cooks/pybuggy/` and registers their keys/annotation lines; idempotent on rerun; gate semantics unchanged (template skip / bare overwrite).
- [ ] `init.md` artifact table updated.

**`goga_tool_pybuggy` (root modify)**
- [ ] Embeddings resolve: `from goga_tool_pybuggy import active_sandbox, services` works.
- [ ] `assembly.md` note added.

**Project-wide**
- [ ] `goga lint` clean across the project; `goga schema` shows the sandbox subtree under the root cell.
- [ ] Cross-import prohibition holds (no sandbox → plugin/api/root imports).
- [ ] `pyproject.toml` main dependency block declares `testcontainers[postgres]`, `psycopg`, `kafka-python`, and `requests` with minimum versions.
- [ ] Conventions hold: Python 3.10+, relative intra-package imports, pydantic kw_only models, Google-style docstrings, structured logging with contextual metadata.
- [ ] Acceptance criteria of the task (`task.md` §Acceptance Criteria) each demonstrable against the implemented result.
