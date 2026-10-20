# Architecture Plan: sandbox-redis

redis as the fifth sandbox dependency kind — one vertical kind-slice through the four
existing sandbox cells. All behavioral decisions per `.goga/history/2026/sandbox-redis/adr.md`
(the authoritative source); this plan is the contract-level materialization.

## Topic

- Short name: **sandbox-redis**
- Plan path: `.goga/history/2026/sandbox-redis/arch.md`
- All four cells are **modified** (extend, not create — the fifth kind adds no new
  responsibility zone). Two new types (`RedisEngine`, `RedisInstance`), seven modified types,
  three updated cell `.usages` files, one newly connected usage cook.

## Implementation Order

Leaves → root — the established dependency direction of the sandbox:

| # | Cell | Status | Order rationale |
|---|---|---|---|
| 1 | `goga_tool_pybuggy/sandbox/config` | modified | Leaf of the slice: imports only the unchanged migrations cell; provides `ServiceConfig` (password/db) and `StartupData` (redis section) that every downstream cell consumes. |
| 2 | `goga_tool_pybuggy/sandbox/engines` | modified | Depends on config (`ServiceConfig`) and migrations (unchanged); provides `RedisEngine`, the extended `build_engine` and `DataOperation`. |
| 3 | `goga_tool_pybuggy/sandbox/data` | modified | Depends on engines (`DataOperation`, `InstanceAddress`, `validate_insert_rows`); provides `RedisInstance` and the extended `services` preset. |
| 4 | `goga_tool_pybuggy/sandbox` (root) | modified | Depends on config + engines + data; consumes `RedisInstance`, gains the `redis(name)` accessor and the last startup-data section. |

No cycles: migrations → config → engines → data → root → plugin (plugin untouched).

## Artifacts

For every changed CODEMANIFEST block the exact new text is given — paste-ready; everything
not listed stays verbatim. Cell `.usages` files are given as complete updated contents.

---

### 1. Cell: `goga_tool_pybuggy/sandbox/config` — MODIFIED

#### CODEMANIFEST changes

**Header** — no changes (Imports: migrations unchanged; `Usages: conventions` unchanged;
global `Annotations` unchanged).

**Body — `ServiceConfig`** — CHANGE the signature, the type annotation, and ADD two
properties (kind property text changes; all other properties verbatim):

```yaml
"ServiceConfig(name: str, kind: str, image: str | None, topics: list[TopicConfig], probe: ProbeConfig | None, migrations: MigrationsConfig | None, password: str | None = None, db: int = 0)":
  location: service.py
  annotations: |
    One named dependency service declaration.

    `name`: the service name — the key tests address the service by and the placeholder name
    used inside the instance env values.
    `kind`: the dependency kind — postgresql, kafka, vault, http, or redis.
    `image`: optional image override; absent keeps the product-pinned default of the kind.
    `topics`: the kafka topic declarations — required and non-empty for the kafka kind, rejected
    for every other kind.
    `probe`: optional readiness declaration — the wait bounds for this service's readiness
    check.
    `migrations`: the optional migrations declaration — accepted on the postgresql kind only;
    a declaration on any other kind fails at document load with the entry named.
    `password`: the redis auth password — optional, accepted on the redis kind only; absent
    starts the service without authentication; present starts it with --requirepass.
    `db`: the redis logical database index — optional, accepted on the redis kind only; 0 by
    default; the valid range is 0-15.

    Requirements:
    - pydantic model, kw_only.
    - A kafka entry without topics is invalid — the mock would open no listener.

    Constraints:
    - Do not accept any kind outside the five supported ones.
    - Do not accept a probe path here — the path belongs to the instance-under-test entry only.

    Use `conventions` for the data-model rules.
  properties:
    "name -> str": |
      Service name — the addressable key and the placeholder name.
    "kind -> str": |
      Dependency kind: postgresql, kafka, vault, http, or redis.
    "image -> str | None": |
      Image override; None keeps the product-pinned default.
    "topics -> list[TopicConfig]": |
      The kafka topic declarations of the service entry.
    "probe -> ProbeConfig | None": |
      Readiness declaration; None keeps the default wait.
    "migrations -> MigrationsConfig | None": |
      The migrations declaration; None — no migrations.
    "password -> str | None": |
      The redis auth password; None — the service starts without authentication.
    "db -> int": |
      The redis logical database index; 0 by default; valid range 0-15.
```

**Body — `StartupData`** — CHANGE the signature, the type annotation, and ADD one property:

```yaml
"StartupData(vault: dict[str, list[dict[str, object]]], http: dict[str, list[dict[str, object]]], postgres: dict[str, list[str]], redis: dict[str, list[dict[str, object]]] = {})":
  location: startup_data.py
  annotations: |
    Startup data layer declarations, in the fixed section order — vault secrets, http mappings,
    postgres init, then redis data.

    `vault`: service name → secret declarations (path, data).
    `http`: service name → stub mapping declarations (request, response).
    `postgres`: service name → init SQL statements.
    `redis`: service name → data declarations; each declaration carries the action key — set,
    hset, rpush, or sadd — plus the fields of the matching view operation (key with
    value/values/members), and converts to one startup operation.

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
    "redis -> dict[str, list[dict[str, object]]]": |
      Service name → data declarations; each carries the action key (set, hset, rpush, sadd)
      plus the matching view operation fields, and converts to one startup operation.
```

**Body — `validate_sandbox_config`** — CHANGE the annotation only (signature unchanged).
Inside the Algorithm, step 3 gains one trailing block after the `MigrationError` wrapping
sentence, and step 4 gains one trailing sentence; Requirements gains one bullet:

```yaml
    (Algorithm step 3 — append after the MigrationError wrapping sentence:)
    A password and a db are accepted on the redis kind only — either on any other kind fails
    naming the entry; db must be an integer within 0-15 — anything else fails at document load
    naming the entry.

    (Algorithm step 4 — append:)
    ; redis declarations carry the action key (set, hset, rpush, or sadd) plus the matching
    view operation fields — anything else fails naming the entry.

    (Requirements — add:)
    - The redis db index is validated at load — an integer within 0-15.
```

Full assembled text of the changed steps and all unchanged types:
`reports/08_cell_config_CODEMANIFEST.yaml` (stage directory).

**Footer** — no changes.

#### `.usages/` file — `goga_tool_pybuggy/sandbox/config/.usages/sandbox-file.md`

Complete updated content: `reports/07_contracts_config_sandbox-file.md` (stage directory).
Delta summary: redis service entry + `password`/`db` keys in the file layout and the new
"Redis keys" subsection; `redis:8-alpine` row in the default-image table; redis PING-readiness
row; `{{cache.host}}`/`{{cache.port}}` + password-as-env-literal wiring; `data.redis` section
row (`{action, key, value/values/members}`) and example; preconditions list extended
(password/db on non-redis entries, db outside 0–15).

---

### 2. Cell: `goga_tool_pybuggy/sandbox/engines` — MODIFIED

#### CODEMANIFEST changes

**Header — `Usages`** — ADD one entry (after `requests`):

```yaml
  redis: .goga/usages/cooks/redis.md
```

**Header — `Annotations`** — ADD one line (after the wiremock line):

```yaml
  Use `redis` for the redis data plane and container.
```

Imports — no changes.

**Body — `DataOperation`** — CHANGE the type annotation and the `action` property text:

```yaml
  annotations: |
    One declared data operation targeted at a named service — the uniform unit of startup data,
    per-test presets, in-test operations, and the baseline journal.

    `instance`: the target service name.
    `kind`: the dependency kind of the target.
    `action`: the operation — insert, produce, put, stub, set, hset, rpush, or sadd.
    `payload`: the operation body — the same fields the matching service view operation accepts.

    Requirements:
    - pydantic model, kw_only; payloads are plain serializable data.
    - The action set is fixed per kind: insert for postgresql, produce for kafka, put for vault,
    stub for http, set, hset, rpush, or sadd for redis. The startup-only postgresql insert
    carries a raw sql payload key instead of table and rows — the statement executes as given,
    opaque: no reference resolution, no symbol capture. A redis operation's payload carries the
    key plus value, values, or members — the fields of the matching view operation.
    - Postgresql rows may carry $ref / $lookup dicts as top-level values — plain data here,
    resolved only at execution; the payload is never rewritten, so journal replay re-resolves.

    Use `conventions` for the data-model rules.
  properties:
    "action -> str": |
      The operation: insert, produce, put, stub, set, hset, rpush, or sadd.
```

(other properties verbatim)

**Body — `build_engine`** — CHANGE step 1 of the Algorithm and one Requirements bullet:

```yaml
    (Algorithm step 1 — replace:)
    1. Map the service kind to its engine — postgresql, kafka, vault, http, or redis.

    (Requirements — replace the first bullet:)
    - The image override, the topic declarations, the readiness declaration, the migrations
    declaration, and the redis password and db declarations of `config` reach the built engine.
```

**Body — `BaseEngine`** — CHANGE the `config` parameter description (append one clause):

```yaml
    (in the annotations block, after "(consumed by the postgres kind)":)
    , password and db
    declarations (consumed by the redis kind)
```

**Body — ADD the new type** (after `HttpEngine`, before the footer separator):

```yaml
"BaseEngine::RedisEngine(config: ServiceConfig)":
  location: redis.py
  annotations: |
    redis kind — a real redis service.

    Container: the community redis module container with the product-pinned default image
    (redis:8-alpine, the postgres:16-alpine precedent) unless the config overrides it; the
    module's built-in wait strategy is replaced through the core container's waiting_for —
    readiness is the engine's PING probe bounded by the declared deadline at the declared
    interval (the same principle by which the postgres engine disables its module's internal
    wait); an expired deadline or a wrong password surfaces as the engine error naming the
    service and the waited check — never a hang. A declared password reaches the container
    command through the module constructor (--requirepass); an absent password starts redis
    without authentication — the primary mode.
    Data plane: the official redis client over one connection to the declared logical database,
    opened after readiness, held for the session, closed on stop. The four v1 operations apply
    as their redis commands — set, hset, rpush, sadd — with values serialized to the wire form
    at execution; the declared payload is never rewritten, so journal replay is deterministic.
    The migrate hook stays the no-op default — migrations are rejected on the redis kind at
    document load.
    Wipe: FLUSHDB of the declared database — one cheap command against the open connection —
    then journal replay; the container never restarts and the data-plane connection survives
    the reset.

    Requirements:
    - One connection to the declared db for the session, closed on stop.
    - The wipe and the seed address the declared db only — FLUSHDB wipes no other logical
    database.
    - A failed command surfaces as the engine error naming the service, the operation, and
    the cause.

    Use `redis` for the container module, the client, readiness, operations, and the reset.
    Use `testcontainers` for the container lifecycle and the stop guarantee.
```

All other types (InstanceAddress, check_runtime, normalize_container_host, EngineError,
BaseEngine methods, validate_insert_rows, PostgresEngine, KafkaEngine, VaultEngine,
HttpEngine) — verbatim. Footer — no changes.

Full assembled manifest: `reports/08_cell_engines_CODEMANIFEST.yaml` (stage directory).

#### `.usages/` files — none

The engines cell exposes no consumer usage surface (deliberate; its consumers are internal —
the sandbox root; the consumer-facing redis documentation lives in the config/data/root cells
and the `redis` cook).

---

### 3. Cell: `goga_tool_pybuggy/sandbox/data` — MODIFIED

#### CODEMANIFEST changes

**Header** — no changes.

**Body — ADD the new type** (after `HttpInstance`, before `services`):

```yaml
"RedisInstance(name: str, address: InstanceAddress, batch: DataBatch)":
  location: redis.py
  annotations: |
    Test-facing view of a started redis service.

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
    "set(key: str, value: object)": |
      Declare one string value write — the GET reader's key.

      `key`: the target key.
      `value`: a string or JSON-serializable plain data — serialized to the wire form at
      execution; the declared payload is never rewritten.
    "hset(key: str, values: dict[str, object])": |
      Declare one hash write — the HGET / HGETALL readers' key.

      `key`: the target key.
      `values`: the field-to-value mapping of the hash.
    "rpush(key: str, values: list[object])": |
      Declare one list tail append — the LRANGE readers' key.

      `key`: the target key.
      `values`: the values appended, in list order.
    "sadd(key: str, members: list[object])": |
      Declare one set members add — the SMEMBERS readers' key.

      `key`: the target key.
      `members`: the members added to the set.
```

**Body — `services`** — CHANGE Algorithm step 1 (five kinds + redis shape validation):

```yaml
    1. Validate the declarations at decoration — only the five supported kinds; anything else
    fails listing the supported kinds. Postgresql rows run the `validate_insert_rows` grammar
    validation — a malformed $ref / $lookup fails naming the declaration location. Redis
    declarations carry the action key — set, hset, rpush, or sadd — plus the matching fields
    (key with value, values, or members); anything else fails naming the declaration.
```

All other types (DataBatch, PostgresInstance, KafkaInstance, VaultInstance, HttpInstance) —
verbatim. Footer — no changes.

Full assembled manifest: `reports/08_cell_data_CODEMANIFEST.yaml` (stage directory).

#### `.usages/` file — `goga_tool_pybuggy/sandbox/data/.usages/data-operations.md`

Complete updated content: `reports/07_contracts_data_data-operations.md` (stage directory).
Delta summary: "keys and values in redis" in the domain; `sandbox.redis("cache").set(...)` in
the reaching example; four redis operation examples; type-correct-writers rule
(GET/HGET/HGETALL/LRANGE/SMEMBERS mapping), plain-data values rule, declared-db alignment
rule; redis preset example with the `action` key; ordering note (second `set` overwrites,
`rpush`/`sadd` append); references note (postgres-only surface); reset preconditions note.

---

### 4. Cell: `goga_tool_pybuggy/sandbox` (root) — MODIFIED

#### CODEMANIFEST changes

**Header — Imports** — CHANGE the data import's Types list (ADD `RedisInstance`):

```yaml
  - Types:
      - DataBatch
      - PostgresInstance
      - KafkaInstance
      - VaultInstance
      - HttpInstance
      - RedisInstance
    Usages:
      - data-operations
    From: goga_tool_pybuggy/sandbox/data
```

Usages and Annotations — no changes.

**Body — `Sandbox`** — CHANGE one Requirements clause and one Algorithm step; ADD one method
(after `http`):

```yaml
    (Requirements — replace the clause:)
    ... the service views
    returned by postgresql/kafka/vault/http/redis bind to it ...

    (start() Algorithm step 3 — replace the tail:)
    ... taken from the `StartupData` sections in the fixed order —
    vault secrets, http mappings, postgres init, then redis data.

    (ADD method:)
    "redis(name: str) -> instance: RedisInstance": |
      The test-facing view of the named redis service.

      `name`: the service name; an unknown name or a kind mismatch fails fast listing the
      configured services.
```

**Indentation normalization** — in the `Sandbox` annotations, the continuation lines of three
unchanged bullets (both Requirements bullets and the first Constraints bullet) shift from
4-space to the 6-space house style; text content unchanged.

All other types and methods — verbatim. Footer — no changes.

Full assembled manifest: `reports/08_cell_root_CODEMANIFEST.yaml` (stage directory).

#### `.usages/` file — `goga_tool_pybuggy/sandbox/.usages/sandbox-session.md`

Complete updated content: `reports/07_contracts_root_sandbox-session.md` (stage directory).
Delta summary: `sandbox.redis("cache").set("feature-flag/a", "enabled")` in the direct-use and
baseline examples; "Redis baseline operations journal the same way — the reset replays them
onto the flushed database"; per-test reset note "A redis service resets by FLUSHDB of its
declared logical database plus the baseline replay — the container keeps running through the
reset."

---

## Dependency Map

```
migrations [unchanged]
   │ (MigrationError, check_local_migrations, check_git_url → config;
   │  run_migrations, MigrationError, migration-set → engines)
   ▼
config [M] ──(ServiceConfig)──────────────────────────▶ engines [M]
                                                        │ (DataOperation, InstanceAddress,
                                                        │  validate_insert_rows)
                                                        ▼
                     data [M] ◀── new types consumed ───┘
                        │
                        │ (DataBatch, PostgresInstance, KafkaInstance, VaultInstance,
                        │  HttpInstance, RedisInstance[NEW on this edge], data-operations)
                        ▼
                     sandbox root [M] ──(Sandbox, SandboxConfig, ...)──▶ plugin [unchanged]

M = modified; the only inter-cell import delta: RedisInstance on root ← data. No cycles.
```

Usage-cook connection: engines header `Usages` gains `redis: .goga/usages/cooks/redis.md`
(file already exists — created with the task; connect, do not rewrite).

## Verification Checklist

Per artifact, after implementation:

1. **config CODEMANIFEST** — `goga lint` clean; five kinds everywhere a kind list appears;
   `password`/`db` accepted on redis only; db 0–15 validated at load; `data.redis` section
   validated (targets + action-key shape); every error message names the document location
   and the entry; unchanged types byte-identical to the pre-change manifest.
2. **engines CODEMANIFEST** — `goga lint` clean; `redis` cook connected and referenced in
   annotations; `RedisEngine` mutation present with `location: redis.py`; `build_engine` maps
   redis with password/db passthrough; action registry includes the four redis actions; other
   types byte-identical.
3. **data CODEMANIFEST** — `goga lint` clean; `RedisInstance` declares only (no execution in
   the view); `services` validates five kinds + redis action-key shape; other types
   byte-identical.
4. **root CODEMANIFEST** — `goga lint` clean; `RedisInstance` imported and returned by
   `redis(name)`; start order ends with redis data; other members byte-identical (except the
   declared continuation-indent normalization of the `Sandbox` annotation blocks).
5. **Cell `.usages` files** — self-contained, no cross-references to other practices, no
   duplication of CODEMANIFEST annotations; the three files mention and cover the redis kind.
6. **Cross-cell** — `goga schema` shows the expected delta (RedisInstance in engines-free
   cells, one new type in engines and data, import edge root ← data carrying RedisInstance);
   no import cycles.
7. **Acceptance mapping** — all ten acceptance-criteria blocks of the task file trace to the
   contract blocks listed in `[CELL_ASSEMBLY_REPORT]` → Acceptance Criteria Check (10/10).

Out-of-plan implementation notes (non-contract scope, tracked by the task file — no artifacts
in this plan): pyproject entries `testcontainers[postgres,redis]>=4.15` and `redis>=7.0`;
re-pointing the four unsupported-kind negative tests; the three documentation pages; the
implementation modules `engines/redis.py` and `data/redis.py` materialized from the contracts
above.
