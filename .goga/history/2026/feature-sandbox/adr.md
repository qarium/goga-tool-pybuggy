# Sandbox: session-scoped isolated service testing inside pybuggy

Status: accepted (2026-10-06)

pybuggy gains a sandbox capability: a pytest-session-scoped environment that runs the service
under test from its image plus mock dependency instances, declared in `.sandbox.yml` at the
service test repository root. Activation is presence-based — the file alone starts the sandbox
for every pytest run (config validated fail-fast before any container starts) — and enablement
rides the existing `plugin.install()` path, fully inert without the file. Presence-based start
was chosen over lazy fixture-triggered start to match the PRD's primary scenario ("run the
ordinary pytest command, the sandbox boots with visible progress") and to preserve fail-fast on
invalid config.

## Settled decisions

- **Activation & enablement**: `.sandbox.yml` present → sandbox starts before the first test of
  each session; same `plugin.install()`, inert without the file; a configured grpc dependency
  fails fast with an explicit "not supported yet".
- **Startup order**: mocks → yaml startup data layer (`vault.secrets`, `http.mappings`,
  `kafka.spec`, `postgres.init`) → service under test → readiness (default: wait for the service
  port; optional `health` path) → author baseline code → tests; stop removes everything on every
  exit path.
- **Per-test isolation**: author-declared session baseline (fixture code; the product marks the
  boundary); an autouse reset fixture from the documented conftest pattern returns instances to
  baseline between tests. Only dependency-instance data resets — the service container is never
  restarted; service in-memory state not resetting is an accepted v1 limitation.
- **Lazy data operations**: per-test presets (`@services(...)` decorator, kind-named arguments;
  inner declaration shapes are a design-stage concern) and in-test operations accumulate and
  apply as one consistent batch automatically before the first call to the service under test;
  the product owns ordering — there is no manual apply.
- **`api` fixture integration**: the product substitutes the resolved base_url after containers
  start; the sandbox wins over config/env; an explicit `--base-url` combined with an active
  sandbox fails fast; startup output names the base_url source.
- **Wiring**: mock addresses are injected via placeholders (`{{instance.host}}`,
  `{{instance.port}}`) in the service env values of `.sandbox.yml`.
- **Instances**: named dependency instances; several of the same kind allowed; `image` overrides
  on top of product-pinned defaults; the service entry requires `image`, `env`, `port`, with
  optional `health`.
- **Naming**: session fixture `sandbox`; preset decorator `services`.
- **Docs**: capability `.usages/` files, distributed by `pybuggy init` into
  `.goga/usages/cooks/pybuggy/` like the existing cookbook files.
- **Runtime**: docker-compatible container runtime (whatever testcontainers supports), checked
  at sandbox start with an actionable error when missing.

## Per-kind mechanics

| kind | tool | data operations | reset between tests |
|---|---|---|---|
| postgresql | real postgres container (testcontainers Postgres module) | real SQL via the postgres driver | `TRUNCATE ... RESTART IDENTITY CASCADE` over catalog-discovered tables + baseline replay, no restart |
| kafka | Mokapi `mokapi/mokapi` (the PRD's "mockapi") | topics from an AsyncAPI spec; produce via kafka client | container restart (in-memory; topics return from the spec) |
| vault | `hashicorp/vault` dev mode | KV v2 over HTTP; fixed dev root token | container restart + baseline replay |
| http | `wiremock/wiremock` | stubs via the `__admin` API | `__admin` reset + baseline replay |

A common engine replays the baseline-operation journal for every kind.

## Considered options — postgres data mechanism

The imposed stack (PRD C1) named pg-wire-mock for postgres. Research (2026-10) established it
cannot carry per-test data: responses are hardcoded in JS handlers, there is no runtime behavior
API, no reset endpoint, no published image, and upstream merges are sporadic. A standalone
postgres wire-protocol mock with a runtime admin API ("WireMock-for-Postgres") does not exist;
every runtime-data-capable alternative found (PGlite+socket, hexclave/pgmock, Memgres) runs real
SQL against a real or WASM engine. Rejected: maintaining our own pg-wire-mock fork (permanent
wire-protocol ownership, brittle query-stubbing — authors would mirror ORM SQL exactly, JOIN and
constraint semantics silently ignored); keeping pg-wire-mock as a protocol-only startup stub
(cannot deliver R4.1 "insert rows"). Chosen: a real postgres container — the only
production-reliable basis for R4.1 today. This is a deliberate amendment of C1 limited to
postgres; vault/kafka/http tooling is unchanged.

## Consequences

- pybuggy gains dependencies: `testcontainers`, a postgres driver (`psycopg`), and a kafka
  client — Mokapi's data plane is the kafka wire protocol (its HTTP side is health/dashboard
  only), so producing a precondition message from the test process requires a protocol client.
  Vault and WireMock are driven over plain HTTP.
- The kafka client serves preconditions only in v1: assertions stay response-only (C7/R4.4);
  messages the service itself produces accumulate in the mock but cannot be asserted on —
  read-back is the first candidate for the next iteration.
- Reset restarts the vault and mokapi containers; services under test must tolerate that
  (secret caching, connection re-establishment) — a cost of the speed-over-fidelity stance.
- Integration with pybuggy internals relies on the documented fact that the `api` fixture reads
  the stored base_url value at fixture time, so a post-start substitution is safe without
  touching the configure-phase Jinja2 rendering.
