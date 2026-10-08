# Architecture Plan — Sandbox refinement: document relocation, inline Kafka topics, configurable readiness, naming swap

## Topic

Short name: **Sandbox refinement — relocation, inline topics, probes, key swap**.
Plan path: `.goga/history/2026/feature-upd-sandbox/arch.md` (topic directory of `feature-upd-sandbox`).
Scope: second iteration over the sandbox capability of `goga_tool_pybuggy` per `.goga/history/2026/feature-upd-sandbox/adr.md` (accepted 2026-10-08) and `task.md`. One breaking jump, no legacy aliases, no deprecation period.

Settled design decisions (user-approved this pass):
- Full model name swap: `InstanceConfig` = the under-test entry, `ServiceConfig` = a dependency service entry.
- Probe declaration: nested `probe:` block, one shared `ProbeConfig` (`timeout` 30.0, `interval` 0.5, `path` only on the under-test entry); document examples in canonical YAML block style.
- Topics: single declaration form — a list of mappings (`name` required, `partitions` optional, default 1).
- Probe settings reach engines and the service container through the entry models; no signature churn.
- Readiness deadline expiry surfaces as `EngineError`.
- Author-facing artifacts carry no references to any former document location or former keys; renamed-key diagnostics live in the runtime error contract only.

## Implementation Order

| # | Cell | Rationale |
|---|---|---|
| 1 | `goga_tool_pybuggy/sandbox/config` | Leaf — no Imports; every rename, the inline topics, the probe fields, and the new loader semantics land here first; downstream cells consume only validated models. |
| 2 | `goga_tool_pybuggy/sandbox/engines` | Depends on config (`ServiceConfig`); consumes the entry declaration — topics, image override, readiness bounds. |
| 3 | `goga_tool_pybuggy/sandbox/data` | Depends on engines (`DataOperation`, `InstanceAddress`, `validate_insert_rows`); annotation-level updates only. |
| 4 | `goga_tool_pybuggy/sandbox` | Depends on config + engines + data; owns the startup order and the instance container readiness. |
| 5 | `goga_tool_pybuggy/plugin` | Doc-level only — usage file, error text, docstring; imports keep their names. |
| 6 | Companion (non-DSL) | `goga_tool_pybuggy/commands/init` hint string, author docs sweep, two cooks lines, tests — after the DSL artifacts. |

## Artifacts

All cells below are **MODIFIED** (no cell is created anew; `ProbeConfig` and `TopicConfig` are new types inside the modified config cell). Content is the complete target state.

### Cell 1: `goga_tool_pybuggy/sandbox/config` — MODIFIED

Changes vs the current tree: root model fields renamed (`instance`, `services`); `ServiceConfig`/`InstanceConfig` swap names and module subjects (`instance.py` = under-test, `service.py` = dependency entry); `StartupData` loses the kafka section; new types `ProbeConfig` (`probe.py`) and `TopicConfig` (`topic.py`); loader targets `.goga/tools/pybuggy/sandbox.yml` with top-level key diagnostics; usage file rewritten.

#### CODEMANIFEST — `goga_tool_pybuggy/sandbox/config/CODEMANIFEST`

```yaml
Usages:
  conventions: .goga/usages/conventions.md
  ruamel-yaml: .goga/usages/cooks/ruamel-yaml.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `conventions` for the pydantic kw_only data models and the docstring rules.
  Use `ruamel-yaml` for reading the sandbox configuration document.

  Sandbox configuration cell. Owns the declarative model of the sandbox document — the
  instance-under-test entry, the named dependency services, and the startup data layer — and its
  fail-fast reading. An invalid document fails before anything starts, with an error naming the
  document location and the offending entry. Use relative imports inside the cell.

---

"SandboxConfig(instance: InstanceConfig, services: dict[str, ServiceConfig], data: StartupData)":
  location: sandbox_config.py
  annotations: |
    Root model of the sandbox configuration: the instance under test, the dependency services
    keyed by name, and the startup data layer.

    `instance`: the instance-under-test entry.
    `services`: dependency service entries keyed by service name; several services of one kind
    are allowed.
    `data`: the startup data layer declarations.

    Requirements:
    - pydantic model, kw_only; the data sections default empty; the instance entry is required.

    Use `conventions` for the data-model rules.
  properties:
    "instance -> InstanceConfig": |
      The instance-under-test entry.
    "services -> dict[str, ServiceConfig]": |
      Dependency service entries keyed by service name.
    "data -> StartupData": |
      The startup data layer declarations.

"InstanceConfig(image: str, env: dict[str, str], port: int, probe: ProbeConfig | None)":
  location: instance.py
  annotations: |
    Instance-under-test entry.

    `image`: the container image of the instance under test.
    `env`: environment values; values may carry service address placeholders resolved at sandbox
    start.
    `port`: the container port the service serves on.
    `probe`: optional readiness declaration — the health path and the wait bounds; absent keeps
    the default wait — port readiness with the default deadline and interval.

    Requirements:
    - pydantic model, kw_only.

    Constraints:
    - The probe path applies only here — the single readiness check with a configurable path.

    Use `conventions` for the data-model rules.
  properties:
    "image -> str": |
      Container image of the instance under test.
    "env -> dict[str, str]": |
      Environment values; values may carry service address placeholders.
    "port -> int": |
      Container port the service serves on.
    "probe -> ProbeConfig | None": |
      Readiness declaration; None keeps the default wait.

"ServiceConfig(name: str, kind: str, image: str | None, topics: list[TopicConfig], probe: ProbeConfig | None)":
  location: service.py
  annotations: |
    One named dependency service declaration.

    `name`: the service name — the key tests address the service by and the placeholder name
    used inside the instance env values.
    `kind`: the dependency kind — postgresql, kafka, vault, or http.
    `image`: optional image override; absent keeps the product-pinned default of the kind.
    `topics`: the kafka topic declarations — required and non-empty for the kafka kind, rejected
    for every other kind.
    `probe`: optional readiness declaration — the wait bounds for this service's readiness
    check.

    Requirements:
    - pydantic model, kw_only.
    - A kafka entry without topics is invalid — the mock would open no listener.

    Constraints:
    - Do not accept any kind outside the four supported ones.
    - Do not accept a probe path here — the path belongs to the instance-under-test entry only.

    Use `conventions` for the data-model rules.
  properties:
    "name -> str": |
      Service name — the addressable key and the placeholder name.
    "kind -> str": |
      Dependency kind: postgresql, kafka, vault, or http.
    "image -> str | None": |
      Image override; None keeps the product-pinned default.
    "topics -> list[TopicConfig]": |
      The kafka topic declarations of the service entry.
    "probe -> ProbeConfig | None": |
      Readiness declaration; None keeps the default wait.

"StartupData(vault: dict[str, list[dict[str, object]]], http: dict[str, list[dict[str, object]]], postgres: dict[str, list[str]])":
  location: startup_data.py
  annotations: |
    Startup data layer declarations, in the fixed section order — vault secrets, http mappings,
    then postgres init.

    `vault`: service name → secret declarations (path, data).
    `http`: service name → stub mapping declarations (request, response).
    `postgres`: service name → init SQL statements.

    Requirements:
    - Sections default empty; declarations target services by name.
    - Within a section, the declaration order is the application order.

    Constraints:
    - Do not reorder declarations — data dependencies are expressed by declaration order.
    - Do not accept a kafka section — the kafka topology is declared inline on the service entry.

    Use `conventions` for the data-model rules.
  properties:
    "vault -> dict[str, list[dict[str, object]]]": |
      Service name → secret declarations (path, data).
    "http -> dict[str, list[dict[str, object]]]": |
      Service name → stub mapping declarations (request, response).
    "postgres -> dict[str, list[str]]": |
      Service name → init SQL statements; each statement converts to one startup insert operation
      whose payload carries the sql key (executed as given).

"ProbeConfig(timeout: float = 30.0, interval: float = 0.5, path: str | None = None)":
  location: probe.py
  annotations: |
    Per-target readiness declaration.

    `timeout`: the readiness deadline in seconds; an expired deadline fails with an actionable
    error.
    `interval`: the seconds between readiness attempts.
    `path`: the health-check path — accepted only on the instance-under-test entry.

    Requirements:
    - pydantic model, kw_only.
    - The defaults reproduce the established wait exactly: timeout 30.0, interval 0.5.
    - Both bounds are positive; the interval never exceeds the timeout.

    Use `conventions` for the data-model rules.
  properties:
    "timeout -> float": |
      The readiness deadline in seconds.
    "interval -> float": |
      The seconds between readiness attempts.
    "path -> str | None": |
      The health-check path; valid only on the instance-under-test entry.

"TopicConfig(name: str, partitions: int = 1)":
  location: topic.py
  annotations: |
    One kafka topic declaration.

    `name`: the topic name the mock opens and tests produce into.
    `partitions`: the topic partition count; 1 when omitted.

    Requirements:
    - pydantic model, kw_only; a non-empty topic name.
    - `partitions` is a positive integer.

    Use `conventions` for the data-model rules.
  properties:
    "name -> str": |
      The topic name.
    "partitions -> int": |
      The partition count; the tool default is 1.

"load_sandbox_config(path: str | None) -> config: SandboxConfig | None":
  location: loader.py
  annotations: |
    Read and validate the sandbox configuration document .goga/tools/pybuggy/sandbox.yml under
    the pybuggy tools home of the consumer service test repository.

    `path`: explicit document location; None resolves .goga/tools/pybuggy/sandbox.yml in the
    current working directory.
    `config`: the validated configuration model; None when the document is absent — the sandbox
    stays fully inert.

    Algorithm:
    1. Resolve the document location — the current working directory only, no upward search; an
    absent document returns None.
    2. Parse the document; an unparsable document fails with an error naming the location and
    the parse problem.
    3. Apply the top-level key diagnostics — a `service` key fails naming the rename to
    `instance`; an `instances` key fails naming the rename to `services`; any other unknown
    top-level key fails as unknown.
    4. Validate the instance entry — image, env, port are required; the probe is optional with
    the path confined to this entry.
    5. Validate every service entry — a non-empty unique name matching the template identifier
    grammar — letters, digits, underscores, not starting with a digit (it names the
    `{{<name>.host}}` / `{{<name>.port}}` placeholders); a kind of postgresql, kafka,
    vault, or http; the grpc kind fails with an explicit "not supported yet" error; an optional
    image override; kafka entries declare a non-empty topics list; non-kafka entries declare
    none; the probe carries no path.
    6. Validate the startup data sections — every declaration targets an existing service of
    the matching kind; a kafka section fails as removed — the topology is declared inline on
    the service entry.
    7. Validate the instance env values — every service placeholder name references a
    configured service.
    8. Return the model.

    Requirements:
    - Validation completes fully before anything is started — no container is created for an
    invalid document.
    - The instance env placeholder names resolve against the configured services — an unknown
    name fails before any container starts.
    - The probe bounds are validated — a positive timeout and interval, the interval never
    exceeding the timeout.
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
  Sandbox configuration cell — the declarative sandbox document models and their fail-fast
  reading.
```

#### Usage file — `goga_tool_pybuggy/sandbox/config/.usages/sandbox-file.md` — REWRITTEN

````md
# Sandbox file — authoring the sandbox document

## Domain

The declarative description of one service sandbox: the instance under test, its mocked
dependency services, and the data they start with. Target audience: service test authors. The
document lives under the pybuggy tools home of the service test repository; its presence alone
activates the sandbox for every pytest run, and an invalid document fails the run before
anything starts.

## File layout

```yaml
# .goga/tools/pybuggy/sandbox.yml
instance:
  image: my-service:latest          # required — the image under test
  port: 8080                        # required — the container port the service serves on
  probe:                            # optional — readiness declaration
    path: /health                   # health path; omit to wait for the port only
    timeout: 60.0                   # readiness deadline seconds; default 30.0
    interval: 1.0                   # seconds between attempts; default 0.5
  env:                              # required — environment values of the service
    DATABASE_URL: "postgres://{{db.host}}:{{db.port}}/app"
    KAFKA_BOOTSTRAP: "{{events.host}}:{{events.port}}"
    VAULT_ADDR: "http://{{secrets.host}}:{{secrets.port}}"

services:                           # named dependency services; several of one kind are allowed
  db:
    kind: postgresql
    image: postgres:16-alpine       # optional image override
  events:
    kind: kafka
    probe:
      timeout: 45.0                 # wait bounds apply to the fixed probe endpoint
    topics:                         # the mocked kafka topology — inline, on the service entry
      - name: orders.events
      - name: payments.events
        partitions: 6               # optional; default 1
  secrets:
    kind: vault
  payments:
    kind: http

data:                               # startup data layer, applied before the instance starts
  vault:
    secrets:
      - path: payment/api-key
        data:
          api_key: test-key
          ttl: 1h
  http:
    payments:
      - request:
          method: POST
          urlPath: /v1/charge
        response:
          status: 200
          jsonBody:
            status: captured
  postgres:
    db:
      - "CREATE TABLE IF NOT EXISTS orders (id bigint PRIMARY KEY, customer text, total numeric)"
```

## Services

- Every service has a name (the key) and a `kind`: `postgresql`, `kafka`, `vault`, or `http`.
- The name is a template identifier — letters, digits, underscores, not starting with a digit —
  because it names the `{{<name>.host}}` / `{{<name>.port}}` placeholders (a hyphenated name
  such as `my-db` is rejected at load time).
- `image` overrides the product-pinned default image of the kind — omit it for the default:

| kind | product-pinned default image |
|---|---|
| `postgresql` | `postgres:16-alpine` |
| `kafka` | `mokapi/mokapi:0.52.0` |
| `vault` | `hashicorp/vault:1.17` |
| `http` | `wiremock/wiremock:3.13.0` |

- Any subset of kinds may be configured; configure only the dependencies the service needs.
- A `grpc` kind is rejected at document load with an explicit "not supported yet" error.

## Kafka topics

The kafka topology is a property of the kafka service entry — declared inline, like `image` and
`kind`:

- `topics` is required on every kafka entry and holds at least one declaration; an entry
  without topics fails before any container starts.
- Each declaration carries `name` (required) and `partitions` (optional, default 1).
- Topics exist only on kafka entries — a `topics` list on any other kind is rejected.
- The AsyncAPI document the mock consumes is generated internally; no spec file is read or
  written, and nothing generated is exposed to authors.

## Readiness probes

Readiness is declared per target, Kubernetes-probe-like, as an optional `probe` block:

| field | applies to | default | meaning |
|---|---|---|---|
| `timeout` | every target | 30.0 | readiness deadline seconds; expiry fails with an actionable error |
| `interval` | every target | 0.5 | seconds between attempts |
| `path` | the instance entry only | — | health path; omit to wait for the port only |

- The probe endpoints of the kafka/vault/http services are fixed by the tool; `timeout` and
  `interval` are the only knobs they accept — a `path` there is rejected.
- The postgresql service keeps its module readiness wrapped in the declared deadline.
- Omitting the block (or any field) keeps the established behavior — defaults reproduce it
  exactly.
- No global defaults block exists; readiness is declared per target only.

## Wiring the instance to its dependencies

Instance env values are Jinja2 templates over the started service addresses:

- `{{<service>.host}}` and `{{<service>.port}}` resolve to the mapped address of the named
  service — e.g. `{{db.host}}` / `{{db.port}}` for the service named `db`.
- Placeholders resolve only for configured service names; an unknown name fails validation.
- Values without placeholders pass through unchanged.

## Startup data layer

Applied in a fixed order after all services are up and before the instance starts:

| section | target | declarations |
|---|---|---|
| `vault` | vault services | `{path, data}` secret writes |
| `http` | http services | WireMock mapping objects (`request` + `response`) |
| `postgres` | postgresql services | SQL statements (schema/bootstrap SQL) |

- A `kafka` section does not exist — declaring one fails; the kafka topology lives on the
  service entry.
- Within a section, declarations apply in the order written — for dependent rows (foreign keys),
  declare parents before children. Postgres init statements are raw sql: they resolve no
  `$ref` / `$lookup` references and their rows are addressable later only through `$lookup`.
- Postgres init statements replay on every per-test reset — write them idempotent (e.g.
  `CREATE TABLE IF NOT EXISTS`); the TRUNCATE-based reset keeps tables, only data is wiped.

## Locating the document

- The file name and location are fixed: `.goga/tools/pybuggy/sandbox.yml`, resolved from the
  current working directory only — resolution never searches elsewhere.
- If the sandbox does not activate, verify the document sits at exactly this path and that the
  run starts from the repository root.

## Preconditions and constraints

- An invalid document (unknown kind, unknown service reference, missing required field,
  malformed placeholder or declaration, kafka entry without topics, topics on a non-kafka
  entry, probe `path` on a service, unparsable YAML) fails the run before any container
  starts, with an error naming the entry.
- Without the document the product is fully inert — nothing starts, nothing changes.
- A container runtime must be available in the environment running the tests.
````

### Cell 2: `goga_tool_pybuggy/sandbox/engines` — MODIFIED

Changes vs the current tree: import edge renamed (`ServiceConfig`); `DataOperation` drops the startup-only spec action; every engine's readiness wait honors the entry's `probe` declaration; postgres module readiness wrapped in the deadline; `KafkaEngine` consumes the inline topics and generates the AsyncAPI document in memory through the existing patched-spec pipeline; `EngineError` gains the deadline-expiry clause; services vocabulary in prose. No usage files (unchanged).

#### CODEMANIFEST — `goga_tool_pybuggy/sandbox/engines/CODEMANIFEST`

```yaml
Imports:
  - Types:
      - ServiceConfig
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
  Use `testcontainers` for the container lifecycle of every service: the runtime probe, module
  and generic containers, readiness waiting, labels, and the stop guarantee.
  Use `psycopg` for the postgresql data plane.
  Use `kafka-python` for producing into the kafka mock.
  Use `requests` for the HTTP data planes of the vault and http kinds.
  Use `mokapi` for the kafka mock container contract.
  Use `vault-dev` for the vault mock container contract.
  Use `wiremock` for the http mock container contract.

  Per-kind dependency service engines cell. One engine owns one started dependency service: its
  container, its data plane, its baseline journal, and its reset. A common base carries the
  journal replay every kind shares; each kind implements its own wipe. Readiness is bounded —
  every wait honors the target's readiness declaration, and an expired deadline fails with an
  actionable error. Every failure surfaces as a readable error identifying the service and the
  failed operation. Use relative imports inside the cell.

---

"DataOperation(instance: str, kind: str, action: str, payload: dict[str, object])":
  location: operation.py
  annotations: |
    One declared data operation targeted at a named service — the uniform unit of startup data,
    per-test presets, in-test operations, and the baseline journal.

    `instance`: the target service name.
    `kind`: the dependency kind of the target.
    `action`: the operation — insert, produce, put, or stub.
    `payload`: the operation body — the same fields the matching service view operation accepts.

    Requirements:
    - pydantic model, kw_only; payloads are plain serializable data.
    - The action set is fixed per kind: insert for postgresql, produce for kafka, put for vault,
    stub for http. The startup-only postgresql insert carries a raw sql payload key instead of
    table and rows — the statement executes as given, opaque: no reference resolution, no symbol
    capture.
    - Postgresql rows may carry $ref / $lookup dicts as top-level values — plain data here,
    resolved only at execution; the payload is never rewritten, so journal replay re-resolves.

    Use `conventions` for the data-model rules.
  properties:
    "instance -> str": |
      The target service name.
    "kind -> str": |
      The dependency kind of the target.
    "action -> str": |
      The operation: insert, produce, put, or stub.
    "payload -> dict[str, object]": |
      The operation body.

"InstanceAddress(host: str, port: int)":
  location: address.py
  annotations: |
    The mapped address of one started service.

    `host`: the host clients use to reach the service.
    `port`: the published host-side port.

    Requirements:
    - pydantic model, kw_only.
    - Addresses are read back from the container engine after start — a fixed host port is never
    assumed.

    Use `conventions` for the data-model rules.
  properties:
    "host -> str": |
      The host clients use to reach the service.
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

"build_engine(config: ServiceConfig) -> engine: BaseEngine":
  location: runtime.py
  annotations: |
    Build the engine of the configured service kind.

    `config`: the service declaration.
    `engine`: the engine of the service's kind.

    Algorithm:
    1. Map the service kind to its engine — postgresql, kafka, vault, or http.
    2. An unmapped kind fails with the supported kinds listed.

    Requirements:
    - The image override, the topic declarations, and the readiness declaration of `config`
    reach the built engine.

    Use `conventions` for type hints and testing.

"EngineError()":
  location: base.py
  annotations: |
    The failure type of every engine operation — the engine-specific RuntimeError subtype.

    Every engine failure surfaces as this type; the message names the service, the failed
    operation or lifecycle step, and the underlying cause. An expired readiness deadline
    surfaces as this type — the message names the target, the waited check, and the expired
    deadline. Exposed through the cell facade — the session runtime and consumer tests catch it
    by name.

    Use `conventions` for type hints and testing.

"BaseEngine(config: ServiceConfig)":
  location: base.py
  annotations: |
    Common per-service engine contract: start the service, execute operations, hold the baseline
    journal, reset, stop. The reset behavior is shared — wipe to the kind's empty state, then
    replay the journal.

    `config`: the service declaration — name, kind, image override, topic declarations,
    readiness declaration.

    Requirements:
    - The journal records the startup operations and every operation applied inside the baseline
    boundary, in application order — the journal is the full session baseline.
    - Readiness completes before start returns, bounded by the readiness declaration — expiry
    is an actionable failure, never a hang.
    - Stop removes the container and closes the data-plane connection; stopping a stopped
    service is safe.

    Constraints:
    - Do not touch the instance under test — engines own dependency services only.
    - Do not execute operations before start completes.

    Use `testcontainers` for the container lifecycle and the cleanup safety net.
    Use `conventions` for type hints and testing.
  properties:
    "address -> InstanceAddress": |
      The mapped address of the started service, read back from the container engine — the value
      the instance env placeholders and the service views consume.
  methods:
    "start(startup: list[DataOperation], network: Network | None)": |
      Start the service container and bring it to readiness.

      `startup`: the startup data of this service, in declaration order.
      `network`: the sandbox network the container joins under its service-name alias — the
      per-session isolation boundary between parallel sessions; absent keeps the engine
      standalone.

      Algorithm:
      1. Build the kind's container — the product-pinned image unless the config overrides it,
      labeled for sandbox identification, with the service port published, joined to `network`
      when one is given.
      2. Start the container and wait for readiness — within the declared deadline, at the
      declared interval; an expired deadline fails with an actionable error naming the service
      and the waited check.
      3. Open the data-plane connection.
      4. Apply the startup operations in order and record them into the journal as the initial
      baseline entries — the startup data is part of the baseline every reset replays.

      Requirements:
      - Start returns only after the service is ready and the startup data is applied and
      journaled.
      - A failed start surfaces an actionable error and leaves nothing behind.

      Use `testcontainers` for the container start and readiness waiting.
    "apply(operations: list[DataOperation])": |
      Execute operations against the service data plane, in order, as one consistent batch.

      `operations`: operations of this service's kind, in application order.

      Algorithm:
      1. Execute each operation through the kind's data plane.
      2. A failed operation raises a readable error identifying the service, the operation, and
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
      Return the service to its baseline.

      Algorithm:
      1. Wipe the service to the kind's empty state.
      2. Replay the journal through the same execution path as apply.

      Requirements:
      - After reset the service holds exactly the baseline state — no test data remains.
    "stop()": |
      Remove the container and close the data-plane connection.

      Requirements:
      - Safe on an already-stopped service.
      - Removal is guaranteed — the explicit stop plus the cleanup safety net.

"validate_insert_rows(rows: object, context: str)":
  location: refs.py
  annotations: |
    Declaration-time grammar validation of insert rows.

    `rows`: the declared rows of one insert.
    `context`: the declaration location naming the rows in error messages.

    Algorithm:
    1. Rows must be a list of mappings.
    2. Every top-level row value carrying $ref or $lookup must match the reference grammar:
    a $ref value is exactly one key holding a non-empty table.index.column address; a $lookup
    value is exactly one key holding a mapping with the required table and where and the
    optional column, nothing else, where a non-empty mapping of scalars.
    3. Plain dict values pass through — references are recognized only as top-level row values.

    Requirements:
    - Shape only — no I/O, no resolution; resolution belongs to the postgres engine at
    execution time.
    - Every failure names the declaration location: `{context} rows[i].column`.

    Use `conventions` for type hints and testing.

"BaseEngine::PostgresEngine(config: ServiceConfig)":
  location: postgres.py
  annotations: |
    postgresql kind — a real postgres service.

    Container: the postgres module container with the product-pinned default image; module
    readiness wrapped in the declared deadline — start returns after the server accepts
    connections within the declared timeout at the declared interval.
    Data plane: SQL over the postgres driver — a table + rows insert resolves $ref / $lookup
    values, then applies the rows one by one inside one transaction with RETURNING; every
    applied row joins the engine's per-table symbol stream — the address space $ref resolves
    against (the stream covers the data plane's own applied rows since the last wipe: journal,
    presets, in-test declarations, in application order; a later row may reference an earlier
    row of the same insert). A $lookup resolves through one parameterized match query against
    the current database state — exactly one match required, the column defaults to the table's
    primary key discovered from the catalog. Startup raw sql statements execute as given,
    opaque — no resolution, no symbol capture.
    Wipe: clear the symbol stream, discover the user tables from the catalog at reset time,
    then truncate them all with identity restart and cascade — the cascade carries the
    foreign-key ordering; the container is never restarted. The journal replay rebuilds the
    symbol stream and re-resolves the journaled references.

    Requirements:
    - One connection for the session in autocommit mode, closed on stop.
    - Catalog discovery runs at every reset — the table set may change mid-session.
    - One transaction per insert — a failing row leaves nothing applied, and the symbol stream
    rolls back with it.
    - Resolution never rewrites the declared payload.

    Constraints:
    - Do not format SQL with interpolated values — parameters are bound server-side.

    Use `psycopg` for the data plane and the catalog-driven reset.
    Use `testcontainers` for the postgres module container.

"BaseEngine::KafkaEngine(config: ServiceConfig)":
  location: kafka.py
  annotations: |
    kafka kind — the kafka mock service.

    Container: the kafka mock image; the inline topic declarations of `config` are consumed at
    build — the AsyncAPI document is generated in memory from the declared topics, its kafka
    servers are rewritten to the client-reachable mapped address of a reserved fixed port, the
    patched copy travels into the container through the docker api, and its in-container path is
    passed as the start argument — topics come from the declaration, the mock binds and
    advertises the patched address, and bootstrap, metadata and the instance env name one and
    the same address; readiness waits for the HTTP health side within the declared deadline at
    the declared interval. An empty topic declaration is an invalid state — the engine fails
    fast, the mock would open no kafka listener; document validation rejects it first.
    Data plane: the kafka protocol — messages are produced with the producer client against the
    mapped bootstrap address; delivery is confirmed at the batch boundary. A produce into a
    topic not declared on the entry fails with a readable error naming the service and its
    declared topics.
    Wipe: restart the container — all state is in-memory, the fixed port binding and the
    generated document survive the restart, the topology returns on boot, and the baseline
    replays on top.

    Requirements:
    - The producer is created against the mapped address and closed on stop.
    - A broken bootstrap fails within the operation deadline — never hangs.
    - The generated document stays internal — never written to the consumer repository, never
    exposed to authors.

    Use `mokapi` for the container contract and the two planes.
    Use `kafka-python` for producing.
    Use `testcontainers` for the generic container, the reserved fixed port and the
    restart-based wipe.

"BaseEngine::VaultEngine(config: ServiceConfig)":
  location: vault.py
  annotations: |
    vault kind — the secrets mock service in dev mode.

    Container: the official vault image in dev mode — in-memory storage, plain HTTP,
    auto-initialized, auto-unsealed, with the fixed dev root token; the vault port is published
    on a reserved fixed host port, so the mapped address survives the restart-based reset;
    readiness waits for the health endpoint within the declared deadline at the declared
    interval.
    Data plane: KV v2 over HTTP with the token header — put writes a secret at a path; startup
    declarations write the same way.
    Wipe: restart the container (storage is in-memory) and replay the baseline.

    Requirements:
    - The dev token is a fixed test credential — never a real secret, never logged.
    - A failed write maps to a readable error naming the path.

    Use `vault-dev` for the container contract and the KV v2 paths.
    Use `requests` for the HTTP data plane.
    Use `testcontainers` for the generic container and the restart-based wipe.

"BaseEngine::HttpEngine(config: ServiceConfig)":
  location: http.py
  annotations: |
    http kind — the http mock service.

    Container: the http mock image with the admin port published; readiness waits for the admin
    endpoint within the declared deadline at the declared interval.
    Data plane: stub mappings created over the admin API — unmatched requests get a visible
    near-miss response, so wiring mistakes surface in test failures.
    Wipe: reset the mappings over the admin API and replay the baseline journal.

    Requirements:
    - Mapping declarations pass through as mapping objects — matching, priority, delays, and
    faults stay available to authors.

    Use `wiremock` for the admin API and the reset endpoints.
    Use `requests` for the HTTP data plane.
    Use `testcontainers` for the generic container.

---

Author: Goga
CreatedAt: 06/10/26
Description: |
  Per-kind dependency service engines of the sandbox — containers, data planes, baseline
  journals, and resets.
```

### Cell 3: `goga_tool_pybuggy/sandbox/data` — MODIFIED

Changes vs the current tree: services vocabulary in prose; `KafkaInstance.produce` targets the declared topics; usage file references the new document and adds the declared-topics note. Signatures unchanged (the declared presets type tightened).

#### CODEMANIFEST — `goga_tool_pybuggy/sandbox/data/CODEMANIFEST`

```yaml
Imports:
  - Types:
      - DataOperation
      - InstanceAddress
      - validate_insert_rows
    From: goga_tool_pybuggy/sandbox/engines

Usages:
  conventions: .goga/usages/conventions.md

Annotations: |
  Use `conventions` for code writing rules and testing.
  Use `conventions` for the docstring rules.

  Data declaration surface of the sandbox. Instance views declare dependency-data operations
  from tests; presets declare them on the test itself; the batch accumulates the declared
  operations and hands them over as one consistent unit. Declarations are lazy — nothing is
  executed at declaration time. Use relative imports inside the cell.

---

"DataBatch()":
  location: batch.py
  annotations: |
    The accumulated operations of the current test.

    Requirements:
    - One batch per test; the batch empties when taken.
    - The accumulation order is the application order per service — presets precede in-test
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
    Test-facing view of a started postgresql service.

    `name`: the service name from the sandbox document.
    `address`: the mapped address of the started service.
    `batch`: the accumulation target of declared operations.

    Requirements:
    - Operations declare only — execution happens when the session facade applies the batch.
  properties:
    "name -> str": |
      The configured service name.
    "host -> str": |
      The mapped host — the value the env placeholders of the instance under test resolve to.
    "port -> int": |
      The published port — the value the env placeholders of the instance under test resolve to.
  methods:
    "insert(table: str, rows: list[dict[str, object]])": |
      Declare row inserts into one table. One call targets one table; rows apply in list order.
      Foreign-key chains follow the declaration order — parents first — while generated parent
      keys resolve through row values: a $ref addresses the data plane's own applied rows, a
      $lookup matches the current database state. The row grammar is validated by
      `validate_insert_rows` — a malformed reference fails at declaration.

      `table`: the target table.
      `rows`: the rows to insert, in order.

"KafkaInstance(name: str, address: InstanceAddress, batch: DataBatch)":
  location: kafka.py
  annotations: |
    Test-facing view of a started kafka service.

    `name`: the service name from the sandbox document.
    `address`: the mapped address of the started service.
    `batch`: the accumulation target of declared operations.

    Requirements:
    - Operations declare only — execution happens when the session facade applies the batch.
  properties:
    "name -> str": |
      The configured service name.
    "host -> str": |
      The mapped host — the value the env placeholders of the instance under test resolve to.
    "port -> int": |
      The published port — the value the env placeholders of the instance under test resolve to.
  methods:
    "produce(topic: str, value: dict[str, object] | str, key: str | None)": |
      Declare one message produce.

      `topic`: the target topic — it must be declared on the kafka service entry of the sandbox
      document.
      `value`: the message value.
      `key`: the optional partition key.

"VaultInstance(name: str, address: InstanceAddress, batch: DataBatch)":
  location: vault.py
  annotations: |
    Test-facing view of a started vault service.

    `name`: the service name from the sandbox document.
    `address`: the mapped address of the started service.
    `batch`: the accumulation target of declared operations.

    Requirements:
    - Operations declare only — execution happens when the session facade applies the batch.
  properties:
    "name -> str": |
      The configured service name.
    "host -> str": |
      The mapped host — the value the env placeholders of the instance under test resolve to.
    "port -> int": |
      The published port — the value the env placeholders of the instance under test resolve to.
  methods:
    "put(path: str, data: dict[str, object])": |
      Declare one secret write.

      `path`: the secret path.
      `data`: the secret data.

"HttpInstance(name: str, address: InstanceAddress, batch: DataBatch)":
  location: http.py
  annotations: |
    Test-facing view of a started http service.

    `name`: the service name from the sandbox document.
    `address`: the mapped address of the started service.
    `batch`: the accumulation target of declared operations.

    Requirements:
    - Operations declare only — execution happens when the session facade applies the batch.
  properties:
    "name -> str": |
      The configured service name.
    "host -> str": |
      The mapped host — the value the env placeholders of the instance under test resolve to.
    "port -> int": |
      The published port — the value the env placeholders of the instance under test resolve to.
  methods:
    "stub(mapping: dict[str, object])": |
      Declare one stub mapping. Matching, priority, delays, and faults pass through as given.

      `mapping`: the mapping object of the http mock.

"services(...presets: dict[str, dict[str, list[dict[str, object]]]]) -> decorator: Callable":
  location: presets.py
  annotations: |
    Per-test data-preset decorator: kind-named arguments carrying service-targeted declarations.

    `presets`: kind → service name → declaration list; every declaration carries the same fields
    as the matching service view operation.
    `decorator`: the marker applied to the test.

    Algorithm:
    1. Validate the declarations at decoration — only the four supported kinds; anything else
    fails listing the supported kinds. Postgresql rows run the `validate_insert_rows` grammar
    validation — a malformed $ref / $lookup fails naming the declaration location.
    2. Mark the test with the presets.
    3. At the test's start the marked presets enqueue into that test's batch, ahead of any
    in-test operation — service names resolve there against the sandbox document; an unknown
    name fails listing the configured services.

    Requirements:
    - Presets apply only to the test declaring them.
    - Declaration order within one service is the application order — parents before children
    for foreign-key chains; $ref / $lookup row values resolve the generated keys.

    Constraints:
    - Do not execute anything at decoration time.

    Use `conventions` for type hints and testing.

---

Author: Goga
CreatedAt: 06/10/26
Description: |
  Data declaration surface of the sandbox — instance views, the lazy batch, and per-test
  presets.
```

#### Usage file — `goga_tool_pybuggy/sandbox/data/.usages/data-operations.md` — MODIFIED

````md
# Data operations — preparing dependency data in tests

## Domain

Declaring the data a service under test will see: rows in postgres, stub responses of http
dependencies, secrets in vault, messages in kafka topics. Target audience: service test authors.
Operations are declared from tests through instance views, or on the test itself as a preset; they
are lazy — the sandbox applies them as one consistent batch right before the first call to the
service under test.

## Reaching an instance

Every configured service is reachable by name through the session fixture, kind-named:

```python
sandbox.postgresql("db").insert(...)  # a postgresql service named db
sandbox.http("payments").stub(...)  # an http service named payments
sandbox.vault("secrets").put(...)  # a vault service named secrets
sandbox.kafka("events").produce(...)  # a kafka service named events
```

Each view also exposes `name`, `host`, and `port` — `host` and `port` are the mapped address the
env placeholders of the instance under test resolve to.

## Declaring operations

```python
sandbox.postgresql("db").insert("orders", rows=[{"id": 1, "total": 100}])

sandbox.http("payments").stub(
    {
        "request": {"method": "POST", "urlPath": "/v1/charge"},
        "response": {"status": 200, "jsonBody": {"status": "captured"}},
    }
)

sandbox.vault("secrets").put("payment/api-key", {"api_key": "test-key"})

sandbox.kafka("events").produce("orders.events", {"id": 1}, key="1")
```

Nothing is executed at declaration time. The sandbox applies the accumulated batch automatically
before the first call to the service under test — there is no manual apply.

- A produced topic must be declared on the kafka service in the sandbox document — an undeclared
  topic fails the operation.

## Per-test presets

Declare data directly on the test:

```python
from goga_tool_pybuggy import services


@services(
    postgresql={
        "db": [
            {"table": "customers", "rows": [{"id": 1, "name": "Ann"}]},
            {"table": "orders", "rows": [{"id": 100, "customer_id": 1}]},
        ]
    },
    http={
        "payments": [
            {
                "request": {"method": "GET", "urlPath": "/v1/rate"},
                "response": {"status": 200, "jsonBody": {"rate": 0.5}},
            }
        ]
    },
)
def test_checkout(api): ...
```

Each declaration carries the same fields as the matching view operation. Presets apply only to the
test declaring them, on top of the reset state, ahead of the test's own operations.

## Ordering and foreign keys

Operations apply in the order declared, per service: presets first, then in-test operations in
call order; rows within one insert apply in list order. Foreign-key chains follow the declaration
order — parents before children, one `insert` call targeting one table (the database constraint
still needs the parent row applied first). Reset-side cleanup needs no ordering from the author.

## Referencing rows

Explicit literal ids are optional: a row value may reference another row instead of carrying a
hardcoded key. Two reference forms exist, both plain data in the declaration:

- **`$ref`** — addresses the data plane's own applied rows:

  ```python
  sandbox.postgresql("db").insert("customers", rows=[{"name": "Ann"}])  # id generated
  sandbox.postgresql("db").insert("orders", rows=[{"customer_id": {"$ref": "customers.0.id"}, "total": 500}])
  ```

  The address `table.index.column` positions the row in the table's applied-row stream since the
  last reset — journal baseline first, then presets, then in-test declarations, in application
  order. The value is the real applied column value (an autoincrement id resolves to whatever the
  sequence generated; after a reset the values are deterministic — 1, 2, 3 in application order).
  A later row of the same insert may reference an earlier row. Inserting an extra earlier parent
  row shifts the indexes — see `$lookup` for a position-independent reference.

- **`$lookup`** — matches the current database state by predicate, regardless of who created the
  row (the service under test included):

  ```python
  # the service itself created the customer through its API
  response = checkout.post(json={"name": "Ann", "email": "ann@x.io"})

  sandbox.postgresql("db").insert(
      "orders",
      rows=[{"customer_id": {"$lookup": {"table": "customers", "where": {"email": "ann@x.io"}}}}],
  )
  ```

  The predicate must match exactly one row — zero matches fail naming the missing precondition,
  several matches fail naming the ambiguity. The resolved column defaults to the table's primary
  key; pass `"column"` to choose another.

Rules common to both forms:

- References are top-level row values only; a nested dict carrying `$ref` stays plain column
  data.
- The grammar is validated at declaration — a malformed reference fails before anything executes.
- Resolution happens at apply time, right before the first service call; references never rewrite
  the declaration.
- References resolve within one postgres service; rows created by raw sql startup statements are
  addressable only through `$lookup`.

## Preconditions and side effects

- Service names and kinds come from the sandbox document
  (`.goga/tools/pybuggy/sandbox.yml`); an unknown name fails fast.
- A failed operation fails the test with a readable error identifying the operation.
- Read-back of dependency state is not part of this iteration — assert on service responses.
````

### Cell 4: `goga_tool_pybuggy/sandbox` — MODIFIED

Changes vs the current tree: import edge from config renamed (`InstanceConfig`); `EngineError` newly imported from engines — the instance readiness deadline surfaces as it; `Sandbox.start` data order vault → http → postgres and probe-bounded instance readiness; `ServiceContainer` takes `InstanceConfig` and honors its readiness declaration; service vocabulary in prose; usage file updated.

#### CODEMANIFEST — `goga_tool_pybuggy/sandbox/CODEMANIFEST`

```yaml
Imports:
  - Types:
      - SandboxConfig
      - InstanceConfig
      - StartupData
      - load_sandbox_config
    Usages:
      - sandbox-file
    From: goga_tool_pybuggy/sandbox/config
  - Types:
      - BaseEngine
      - build_engine
      - DataOperation
      - EngineError
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
  Use `testcontainers` for the instance container lifecycle: the generic container, readiness
  waiting, labels, and the removal guarantee on every exit path.
  Use `jinja2` for rendering the instance environment values.
  Use `requests` for health-path readiness probing.
  Use `pluginator` for registering the session lifecycle hooks into the caller namespace.

  Session runtime of the sandbox. One sandbox owns one pytest-session environment: the ordered
  startup of the dependency services and the instance under test, the readiness gates, the
  baseline boundary, the per-test reset, and the guaranteed removal on every exit path.
  Activation is presence-gated — without the configuration document nothing is registered and
  nothing runs. Startup progress is visible, and the startup output names the base_url source.
  Use relative imports inside the cell.

---

"Sandbox(config: SandboxConfig)":
  location: sandbox.py
  annotations: |
    The running session sandbox.

    `config`: the validated sandbox configuration.

    Requirements:
    - Stop removes everything on every exit path — success, failure, interruption.
    - The service address is readable as the base_url after start.
    - Start creates one sandbox network — the per-session isolation boundary — and every
    container the session starts (service engines and the instance) joins it; stop removes
    the network after the containers left it. Mapped-address consumption is unchanged: the
    network isolates parallel sessions, the runner keeps using the published host ports.
    - The session lifecycle owns one `DataBatch` per test: the registered per-test hook creates a
    fresh batch before the test, the service views returned by postgresql/kafka/vault/http bind
    to it, and apply_pending takes exactly that batch; a new test never sees a previous test's
    operations.

    Constraints:
    - Do not start anything when the configuration is absent — activation owns the gate.
    - Do not restart the instance container on reset — only dependency service data resets.

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
      2. Create the sandbox network — the per-session isolation boundary every container the
      session starts joins.
      3. Start every configured service engine — built with `build_engine` — with its startup
      data as `DataOperation` entries taken from the `StartupData` sections in the fixed order —
      vault secrets, http mappings, then postgres init.
      4. Render the instance environment values against the started service addresses.
      5. Start the instance container and wait for readiness — the port, or the health path when
      declared — within the readiness declaration's deadline at its interval; an expired
      deadline fails with an actionable error.
      6. Log the startup progress at every step, and the resolved service address with its
      source.

      Requirements:
      - Visible startup progress; tests run only after readiness.
    "stop()": |
      Remove everything the sandbox started.

      Requirements:
      - Runs on every exit path; safe when already stopped.
    "clear()": |
      Return every dependency service to its baseline.

      Algorithm:
      1. Reset every service engine — wipe and journal replay.

      Requirements:
      - After clear the services hold exactly the baseline state; test order cannot change
      outcomes.

      Constraints:
      - The instance container keeps running.
    "baseline() -> boundary: BaselineBoundary": |
      Open the session baseline boundary. Author fixture code runs inside the boundary; the
      boundary semantics belong to `BaselineBoundary`.
    "apply_pending()": |
      Apply the current test's accumulated operations as one consistent batch.

      Algorithm:
      1. Take the accumulated `DataBatch`.
      2. Group the operations by service, preserving accumulation order.
      3. Apply each group to the service's `BaseEngine`.

      Requirements:
      - Runs before the first service call of a test.
      - A failed operation surfaces a readable error identifying it.

      Use `data-operations` for the laziness contract.
    "ensure_service()": |
      Fail fast with a readable error when the instance container has died — the error names the
      died service and attaches its output read from `ServiceContainer`; a no-op while the
      instance runs.

      Requirements:
      - Called on the request path — the api fixture's first-request guard invokes it — so a
      crashed instance surfaces as an explicit died-service indication, never as a hang or an
      opaque connection failure.
    "new_test_batch()": |
      Create the fresh data batch of the next test.

      Called by the registered per-test lifecycle hook before every test, ahead of the preset
      enqueue — a new test never sees a previous test's operations; the service views returned
      afterwards bind to the new batch.
    "postgresql(name: str) -> instance: PostgresInstance": |
      The test-facing view of the named postgresql service.

      `name`: the service name; an unknown name or a kind mismatch fails fast listing the
      configured services.
    "kafka(name: str) -> instance: KafkaInstance": |
      The test-facing view of the named kafka service.

      `name`: the service name; an unknown name or a kind mismatch fails fast listing the
      configured services.
    "vault(name: str) -> instance: VaultInstance": |
      The test-facing view of the named vault service.

      `name`: the service name; an unknown name or a kind mismatch fails fast listing the
      configured services.
    "http(name: str) -> instance: HttpInstance": |
      The test-facing view of the named http service.

      `name`: the service name; an unknown name or a kind mismatch fails fast listing the
      configured services.

"BaselineBoundary(sandbox: Sandbox)":
  location: baseline.py
  annotations: |
    The marked baseline boundary of the session.

    `sandbox`: the session sandbox whose services the boundary governs.

    Requirements:
    - Inside the boundary, declared operations apply immediately and are recorded into the
    `BaseEngine` journals.
    - Closing the boundary freezes the journals as the session baseline.

    Constraints:
    - Do not accumulate lazily inside the boundary — operations apply at declaration time.
  methods:
    "open()": |
      Enter the boundary: service operations switch to immediate apply and journal recording.
    "close()": |
      Leave the boundary: journals freeze as the baseline; operations return to lazy
      accumulation.

"ServiceContainer(config: InstanceConfig)":
  location: service_container.py
  annotations: |
    The running instance under test.

    `config`: the instance entry — image, env, port, readiness declaration.

    Requirements:
    - Readiness completes before start returns — the port, or the health path when declared,
    within the declared deadline at the declared interval; an expired deadline fails as
    `EngineError` — an actionable failure naming the instance and the waited check, never a hang.
    - The container is labeled for sandbox identification and removed on stop.
    - A died instance is detectable and its output is readable for diagnostics.

    Constraints:
    - Do not restart the instance on reset.

    Use `testcontainers` for the generic container and readiness waiting.
    Use `requests` for health-path probing.
  properties:
    "host -> str": |
      The mapped host of the instance.
    "port -> int": |
      The published port of the instance.
  methods:
    "start(env: dict[str, str], network: Network | None)": |
      Start the instance image with the rendered environment.

      `env`: fully rendered values — placeholders already resolved.
      `network`: the sandbox network the instance container joins, side by side with the
      dependency services of the same sandbox; absent keeps the instance standalone.
    "stop()": |
      Remove the container; safe when already stopped.
    "alive() -> alive: bool": |
      Whether the instance container still runs — the input of the died-service indication
      carried by `Sandbox`.
    "logs() -> output: str": |
      The instance output, attached to the died-service indication carried by `Sandbox`.

"render_service_env(env: dict[str, str], addresses: dict[str, InstanceAddress]) -> rendered: dict[str, str]":
  location: env_render.py
  annotations: |
    Render the instance environment values against the started service addresses.

    `env`: the raw environment values of the instance entry.
    `addresses`: service name → mapped address.
    `rendered`: the values with every service placeholder resolved.

    Algorithm:
    1. Build the rendering context — one entry per service name, exposing host and port.
    2. Render every value strictly — an unknown placeholder fails naming the value.

    Use `jinja2` for the rendering engine and the strict undefined behavior.
    Use `sandbox-file` for the placeholder syntax.

"activate_sandbox(context: dict[str, object]) -> config: SandboxConfig | None":
  location: activation.py
  annotations: |
    Activate the sandbox for the pytest session — presence-gated, called from the plugin
    installation entry.

    `context`: the caller namespace the lifecycle hooks land in.
    `config`: the validated configuration — the armed activation; None when the document is
    absent and nothing is registered.

    Algorithm:
    1. Read and validate the configuration document via `load_sandbox_config`; an invalid
    document fails before anything starts.
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
  Session runtime of the sandbox — ordered lifecycle orchestration, the instance container,
  and pytest activation.
```

#### Usage file — `goga_tool_pybuggy/sandbox/.usages/sandbox-session.md` — MODIFIED

````md
# Sandbox session — fixtures, baseline, and reset

## Domain

The pytest integration of the sandbox: how a consumer suite activates it, declares the session
baseline, resets between tests, and reaches the service under test through the api fixture.
Target audience: service test authors.

## Activation

The sandbox activates by presence: the sandbox document at `.goga/tools/pybuggy/sandbox.yml`,
under the pybuggy tools home of the test repository. The same plugin installation call that
enables pybuggy arms the sandbox — nothing else is enabled:

```python
# conftest.py
from goga_tool_pybuggy import plugin

plugin.install()
```

With the document present, every pytest run starts the sandbox before the first test (the
progress is visible in the output); an invalid document fails the run before any container
starts; without the document the suite behaves exactly as it would without the sandbox.

## Session fixture and baseline

```python
# conftest.py
import pytest
from goga_tool_pybuggy import active_sandbox


@pytest.fixture(scope="session")
def sandbox():
    sbx = active_sandbox()
    with sbx.baseline():  # the baseline boundary — author code
        sbx.postgresql("db").insert("customers", rows=[{"id": 1, "name": "Ann"}])
        sbx.vault("secrets").put("payment/api-key", {"api_key": "test-key"})
    yield sbx  # stop is product-owned — do not stop manually
```

Operations inside the baseline boundary apply immediately and become the session baseline: after
every reset the services return to exactly this state. Baseline rows may use `$ref` / `$lookup`
references like any declaration — after every reset the journal replay re-applies and re-resolves
them, so generated keys stay consistent between the baseline and the tests built on top of it.

## Per-test reset

```python
# conftest.py
@pytest.fixture(autouse=True)
def _sandbox_reset(sandbox):
    sandbox.clear()
    yield
```

Reset returns every dependency service to the baseline — test order cannot change outcomes. Only
dependency data resets; the instance container keeps running (service in-memory state not
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
- Declared operations apply automatically as one batch before the first service call — also the
  moment when `$ref` / `$lookup` row values resolve, so a declaration made after earlier service
  calls may reference rows those calls created (`$lookup`).

## Preconditions and side effects

- The environment running the tests needs a docker-compatible container runtime; the startup
  error names the requirement when it is missing.
- After the session — including failed or interrupted runs — nothing remains; a rerun starts
  fresh.
- A crashed service fails the affected tests with an indication that the service died and where
  its output is.
- If the sandbox does not activate, verify the document sits at exactly
  `.goga/tools/pybuggy/sandbox.yml` — resolution is cwd-only and never searches elsewhere.
````

### Cell 5: `goga_tool_pybuggy/plugin` — MODIFIED (doc-level only)

CODEMANIFEST: carries forward verbatim — no signature, import, or annotation changes.

#### Usage file — `goga_tool_pybuggy/plugin/.usages/enable.md` — MODIFIED (Sandbox activation section)

````md
## Sandbox activation

The same `plugin.install()` call also arms the pybuggy sandbox: when the test repository holds
the sandbox document at `.goga/tools/pybuggy/sandbox.yml` (under the pybuggy tools home), the
sandbox starts before the first test of every pytest session (mock dependency services and the
instance under test, with visible progress), and the api fixture's address resolves to the
sandbox's service. Without the document nothing changes — the suite runs exactly as without the
sandbox. A typed `--base-url` flag together with an active sandbox fails fast with an explicit
error: the sandbox owns the service address.
````

(The remainder of `enable.md` carries forward verbatim.)

### Cell 6: `goga_tool_pybuggy/commands/init` — MODIFIED (one string)

CODEMANIFEST: carries forward verbatim. One work item: the registered `sandbox-file` authoring hint (annotation-line payload of `register_annotations`) names the sandbox document by its new location `.goga/tools/pybuggy/sandbox.yml`.

### Companion (non-DSL) work items — required by the task's acceptance criteria

- Plugin implementation texts: the configure-time fail-fast error message and the `install` docstring name the document by its new location.
- Author docs sweep to the new path, keys, inline topics, probe settings, with a migration pointer that does not name any former location: `docs/sandbox.md`, `docs/configuration.md`, `README.md`, `docs/getting-started.md`, `docs/index.md`, `docs/pipelines/api-fix.md`, `docs/plugin/index.md`, `mkdocs.yml`.
- Cooks (hand-authored, two lines): `.goga/usages/cooks/testcontainers.md` — the generated AsyncAPI document instead of an author-declared spec path; `.goga/usages/cooks/wiremock.md` — the new document name.
- Tests: the four sandbox cells' suites updated and extended (new-path resolution and inertness, renamed-key errors, inline topic validation incl. missing topics and default partitions, probe defaults and overrides, vault → http → postgres order, deadline expiry, default-equivalence regression) plus `tests/plugin/test_install.py` arming through the new document path.

## Dependency Map

```
goga_tool_pybuggy/sandbox/config   (leaf — no Imports)
        │ ServiceConfig
        ▼
goga_tool_pybuggy/sandbox/engines
        │ DataOperation, InstanceAddress, validate_insert_rows
        ▼
goga_tool_pybuggy/sandbox/data
        │ DataBatch, PostgresInstance, KafkaInstance, VaultInstance, HttpInstance
        │ + usage data-operations
        ▼
goga_tool_pybuggy/sandbox ◄── config: SandboxConfig, InstanceConfig, StartupData,
        │                    load_sandbox_config + usage sandbox-file
        │                    engines: BaseEngine, build_engine, DataOperation,
        │                    EngineError, InstanceAddress, check_runtime
        ▼
goga_tool_pybuggy/plugin ◄── sandbox: Sandbox, activate_sandbox, active_sandbox
        │                  + usage sandbox-session; config: SandboxConfig
        ▼
goga_tool_pybuggy (root re-exports — unchanged)

Acyclic; leaves → root: config → engines → data → sandbox → plugin.
Edge directions unchanged by this plan; labels swapped only (InstanceConfig ↔ ServiceConfig).
```

## Verification Checklist

After implementing each artifact:

**sandbox/config**
- `goga lint goga_tool_pybuggy/sandbox/config` passes; manifest structure Header/Body/Footer with `---` separators.
- Facade: `python -c "from goga_tool_pybuggy.sandbox.config import SandboxConfig, InstanceConfig, ServiceConfig, StartupData, ProbeConfig, TopicConfig, load_sandbox_config"`.
- Loader tests: new-path resolution cwd-only; absent document → None with zero side effects; stale root document untouched and silent; renamed-key errors (`service`, `instances`) name the offending key and the rename; `data.kafka` section rejected as removed; kafka entry without topics fails; topics on non-kafka kinds fail; probe `path` on a service fails; probe bounds validated (positive, interval ≤ timeout); partitions default 1, non-positive partitions fail.
- Usage file: no references to any former document location or former keys; YAML examples parse and use block style.

**sandbox/engines**
- `goga lint` passes; import edge is `ServiceConfig`.
- Facade: `python -c "from goga_tool_pybuggy.sandbox.engines import build_engine, BaseEngine, EngineError"` (and the kind engines).
- Readiness default-equivalence regression: with no probe overrides, start behavior is byte-identical to the established one (criterion 7).
- Deadline expiry surfaces as `EngineError` naming target, check, and deadline — for every kind engine and the postgres module readiness.
- Kafka: topics consumed from the entry declaration; the AsyncAPI document exists only in memory; no spec file is read or written anywhere in the consumer repository; the patched-spec pipeline contract (mapped reserved address, servers patch, transfer, start argument) holds; empty declaration fails fast; producing into an undeclared topic fails with a readable error naming the declared topics.
- `DataOperation` carries no spec action anywhere in the cell.

**sandbox/data**
- `goga lint` passes; signatures unchanged.
- `produce` annotation and tests address the declared topics; presets resolve service names against the document.
- Usage file: vocabulary, declared-topics note, new document path present; no former references.

**sandbox**
- `goga lint` passes; Imports carry `InstanceConfig` (not the former name) from config.
- `Sandbox.start` applies startup data in the vault → http → postgres order (integration test).
- `ServiceContainer` readiness: port-only default, health path when declared, deadline/interval honored, expiry surfaces as `EngineError` naming the instance and the waited check.
- Facade: `python -c "from goga_tool_pybuggy.sandbox import Sandbox, activate_sandbox, active_sandbox"`.
- Usage file: activation section names the new path; cwd-only pointer present.

**plugin / commands/init / docs / cooks / tests**
- `goga lint` passes for both cells (manifests unchanged).
- Repo-wide sweep: no author-facing file references the former document path or former keys — `grep -r "\.sandbox\.yml"` over docs, README, usage files, and cooks returns nothing.
- `tests/plugin/test_install.py` arms through the new path; the full suite `pytest tests/ -x` passes.

**Cross-cutting**
- `goga lint` over the whole project passes.
- The root `goga_tool_pybuggy` facade still re-exports the sandbox API unchanged (Python API stability, criterion 8).
- Plugin imports (`Sandbox`, `activate_sandbox`, `active_sandbox`, `SandboxConfig`) resolve without changes.
