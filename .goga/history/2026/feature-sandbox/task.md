# Sandbox — session-scoped isolated service testing inside pybuggy

## Current State

pybuggy is a spec-driven API testing tool: it generates endpoint fixtures from OpenAPI specs,
executes HTTP calls through the function-scoped `api` fixture with the matchcrest assert layer,
is enabled per consumer suite via an explicit `goga_tool_pybuggy.plugin.install()` call from
conftest.py, and bootstraps consumer projects via `pybuggy init` (which also distributes capability
usages into `.goga/usages/cooks/pybuggy/`).

Isolation of a service's own logic does not exist at all today:

- no container lifecycle anywhere in the product; no container-runtime awareness;
- no sandbox configuration — a `.sandbox.yml` file does not exist as a concept;
- no dependency mocks (postgresql / kafka / vault / http) and no data operations against them;
- no per-test isolation: no reset, no baseline, no lazy accumulate-then-apply;
- the `api` fixture's base_url is resolved once at pytest configphase (config → env → CLI) and
  rendered there, so it cannot point at a service container that starts later within the session;
- pyproject declares no testcontainers / psycopg / kafka client; `.goga/usages/cooks/` had no
  usages for the new tools until this task's formulation created the six capability usage files
  (see External Dependencies).

## Description

Add a sandbox capability to pybuggy: a pytest-session-scoped environment that runs the service
under test from its image together with mock dependency instances, fully described by a declarative
`.sandbox.yml` at the root of the consumer service test repository. The capability is designed for
fast isolated testing of a service's own business logic — dependencies are mocked, per-test state
is deterministic, and the service is exercised through the existing standard pybuggy `api` fixture
with its address resolved from the sandbox. The design follows the accepted ADR
(`.goga/history/2026/feature-sandbox/adr.md`); behavior requirements follow the PRD
(`.goga/history/2026/feature-sandbox/prd.md`).

Essence, per the settled ADR decisions:

- **Activation & enablement.** Presence of `.sandbox.yml` starts the sandbox before the first test
  of each pytest session; without the file the product is fully inert. Configuration is validated
  fail-fast before any container starts. A configured grpc dependency fails fast with an explicit
  "not supported yet". Enablement rides the existing `plugin.install()` path — no new enablement
  surface.
- **Startup order.** Mock instances → yaml startup data layer (vault secrets, http mappings, kafka
  AsyncAPI spec, postgres init) → service under test → readiness (default: wait for the service
  port; optional health path) → author baseline code → tests. Stop removes everything on every
  exit path.
- **Per-kind mechanics.** postgresql — a real postgres container (the deliberate, user-approved
  amendment of PRD constraint C1; pg-wire-mock cannot carry runtime data), data operations via the
  postgres driver, reset by truncating catalog-discovered tables with identity restart and
  replaying the baseline; kafka — Mokapi with topics from an AsyncAPI spec, produce via the kafka
  client, reset by container restart (in-memory; topics return from the spec); vault — official
  image in dev mode, KV v2 over HTTP with the fixed dev root token, reset by restart plus baseline
  replay; http — WireMock, stubs over the admin API, reset via the admin reset endpoint plus
  baseline replay. A common engine replays the baseline-operation journal for every kind.
- **Per-test isolation.** Author-declared session baseline (fixture code; the product marks the
  boundary); an autouse reset fixture from the documented conftest pattern returns instances to
  baseline between tests. Only dependency-instance data resets — the service container is never
  restarted; service in-memory state not resetting is an accepted v1 limitation.
- **Lazy data operations.** Per-test presets via the `services` decorator (kind-named arguments;
  inner declaration shapes are a design-stage concern) and in-test operations accumulate and apply
  as one consistent batch automatically before the first call to the service under test. The
  product owns ordering — there is no manual apply.
- **`api` fixture integration.** The product substitutes the resolved base_url after containers
  start; the sandbox wins over config/env; an explicit `--base-url` combined with an active sandbox
  fails fast; startup output names the base_url source. The base_url option stays required exactly
  as today — a consumer repository always carries one (`pybuggy init` surveys it as a required
  input); tests are unchanged and address-agnostic: the `api` fixture goes to base_url whether it
  resolves to the sandbox service or a real one, and with an active sandbox the configured value is
  overridden by the sandbox address (the author never points base_url at the sandbox manually). The
  substitution exploits the documented fact that the `api` fixture reads the stored base_url value
  at fixture time — the configure-phase Jinja2 rendering is untouched.
- **Wiring & instances.** Mock addresses are injected via `{{instance.host}}` / `{{instance.port}}`
  placeholders in the service env values of `.sandbox.yml`. Dependency instances are named; several
  of the same kind are allowed; `image` overrides sit on top of product-pinned defaults. The service
  entry requires `image`, `env`, `port`, with optional `health`.
- **Naming & docs.** Session fixture `sandbox`; preset decorator `services`. Capability
  documentation lives in the capability's usage files and is distributed by `pybuggy init` into
  `.goga/usages/cooks/pybuggy/` like the existing cookbook files.
- **Runtime.** A docker-compatible container runtime (whatever testcontainers supports) is required
  in the environment running the tests; it is checked at sandbox start with an actionable error
  when missing.

## Scope

**In scope:**

- Discovery, parsing, and fail-fast validation of `.sandbox.yml` (service entry with image, env,
  port, optional health; named dependency instances of kinds postgresql, kafka, vault, http; image
  overrides over product-pinned defaults; grpc rejected with an explicit error).
- Placeholder-based wiring of the service env to started mock instance addresses.
- Sandbox lifecycle: ordered startup (mocks → yaml data layer → service → readiness → baseline),
  visible startup progress, guaranteed stop and removal on every exit path, container-runtime
  availability check with an actionable error.
- Per-kind instance engines on testcontainers: real postgres container, Mokapi (AsyncAPI-driven
  topics), vault dev mode, WireMock.
- Yaml startup data layer: vault secrets, http mappings, kafka spec, postgres init applied at
  startup in the defined order.
- Lazy accumulate-then-apply data operations API reachable in tests by instance name (insert rows,
  stub http responses, put vault secrets, produce kafka messages), with the batch applied
  automatically before the first service call.
- Per-test data presets via the `services` decorator on a test.
- Author-declared session baseline; per-test reset to baseline per kind (truncate+replay, restart,
  restart, admin reset+replay) driven by a common journal-replay engine; documented conftest
  autouse reset pattern.
- `api` fixture integration: post-start base_url substitution, sandbox precedence over config/env,
  fail-fast on `--base-url` combined with an active sandbox, base_url source in startup output.
- New product dependencies declared in the main dependency block: testcontainers, psycopg,
  kafka-python; explicit declaration of the already-imported requests.
- Capability usage files plus their distribution through the existing `pybuggy init` path.
- Failure behavior per PRD R6: fail-fast invalid config, actionable container errors with cleanup,
  service-death indication, readable failed-operation errors, fresh state on reruns.

**Out of scope:**

- grpc mock support (explicit error only).
- Dependency-state read-back or call verification for assertions (v1 asserts on service responses
  only; kafka consumer usage is a deliberate non-goal of this iteration).
- Integration into the agent development cycle as a gate.
- Parallel test execution (pytest-xdist or multiple simultaneous sandboxes) — a single sandbox
  with sequential tests.
- `pybuggy init` scaffolding of sandbox artifacts — authors create `.sandbox.yml` and fixtures
  manually per documentation.
- Creating, replacing, or managing integration tests against real dependencies or stands.
- Fidelity parity with real engines — speed and simplicity over behavioral equivalence.
- Non-HTTP services under test — v1 targets services callable through the `api` fixture.
- New cell/architecture design — structure is the concern of the prototype/design stages, not this
  task.

## Acceptance Criteria

- A consumer service repository with only `.sandbox.yml` and documented conftest fixtures can write
  a sandbox test exercising the service's business logic against mocked dependencies, run it with
  the ordinary pytest command, and get a pass/fail result.
- A sandbox suite for a service with, e.g., postgres and http dependencies runs green in an
  environment where only a container runtime is available — no database, kafka, or external
  integrations installed.
- Without `.sandbox.yml`, an installed pybuggy behaves exactly as today (inert capability); with an
  invalid file, the run fails before any container starts with an error pointing at the config
  problem.
- Within one session, test order does not change outcomes: reset returns instances to the baseline,
  and a per-test preset applies only to the test declaring it.
- After a session — including failed or interrupted runs — no sandbox containers remain, and an
  immediate rerun starts fresh and behaves identically.
- An invalid config, an unavailable container runtime, a crashing service, and a failing mock
  operation each produce a clear, actionable error identifying the cause — never a hang or an
  opaque assertion failure.
- A test using only the existing `api` fixture reaches the service under test with its address
  resolved from the sandbox; `--base-url` plus an active sandbox fails fast with an explicit error.
- A configured grpc dependency produces an explicit "not supported yet" error at startup.
- `pybuggy init` distributes the capability usage files into the consumer's
  `.goga/usages/cooks/pybuggy/`.

## Stack

- **Frameworks:** pytest (existing plugin surface), pluginator (existing plugin framework), pydantic
  (configuration models, per project conventions).
- **Libraries:** testcontainers (core + postgres module) — container lifecycle for the service and
  all mock instances; psycopg (v3) — postgres SQL driver; kafka-python — producing precondition
  messages into Mokapi; requests — HTTP driving of vault KV v2, WireMock admin API, readiness
  probes; jinja2 (existing) — placeholder rendering in service env values; ruamel.yaml/pyyaml
  (existing) — `.sandbox.yml` parsing.
- **Infrastructure (container images):** postgres (via the testcontainers postgres module) — real
  postgres instance; mokapi/mokapi — kafka mock (topics from an AsyncAPI spec); hashicorp/vault —
  dev mode secrets mock; wiremock/wiremock — http mock (stubs over the admin API). Product-pinned
  default image tags with per-instance overrides.

## External Dependencies

| Component | Usage file | Status |
|-----------|------------|--------|
| testcontainers | `.goga/usages/cooks/testcontainers.md` | created |
| psycopg | `.goga/usages/cooks/psycopg.md` | created |
| kafka-python | `.goga/usages/cooks/kafka-python.md` | created |
| wiremock | `.goga/usages/cooks/wiremock.md` | created |
| mokapi | `.goga/usages/cooks/mokapi.md` | created |
| vault (dev mode) | `.goga/usages/cooks/vault-dev.md` | created |
| requests | `.goga/usages/cooks/requests.md` | existing |
| jinja2 | `.goga/usages/cooks/jinja2.md` | existing |
| pluginator | `.goga/usages/cooks/pluginator.md` | existing |
| ruamel.yaml | `.goga/usages/cooks/ruamel-yaml.md` | existing |
| goga platform | `.goga/usages/github/goga/` | existing (synced) |

Synced usage files are managed by `goga usages sync` — reference them read-only, never create or update them in the task.

## Risks and Constraints

- The postgres deviation from the imposed stack (real container instead of pg-wire-mock, ADR
  amendment of C1) is accepted and settled — reopening it is out of the question.
- Reset restarts the vault and Mokapi containers; services under test must tolerate that (secret
  caching, connection re-establishment) — a cost of the speed-over-fidelity stance.
- The kafka client is preconditions-only in v1; assertions stay response-only. Read-back (consumer
  usage, WireMock journal) is the first candidate for the next iteration, not this one.
- base_url integration leans on the documented plugin behavior (configure renders once; the fixture
  reads the stored value) — any change to that plugin contract during implementation must preserve
  the substitution seam.
- The container runtime is an external requirement of the environment (developer machine / CI);
  unavailability must surface as an actionable error, never a hang.
- New dependencies land in the main `[project.dependencies]` block (per PRD R7.1 — no separate
  installation), with minimum versions per project conventions.
- Project conventions apply throughout: Python 3.10+, relative intra-package imports, pydantic
  kw_only models, Google-style docstrings, structured logging, declared dependencies.

## Scope Estimate

Single task — the full sandbox capability in one task document (user decision during formulation;
decomposition into core+lifecycle and data-control subtasks was considered and rejected in favor of
one coherent prototype pass).

## Existing Architecture

Affected existing cells and integration seams:

- `goga_tool_pybuggy/plugin` — the enablement path (`install()`) carries the sandbox activation;
  the `api` fixture base_url semantics gain the post-start substitution with sandbox precedence and
  the `--base-url` fail-fast; the required base_url resolution is unchanged — with an active
  sandbox the resolved value is overridden. The configure-phase Jinja2 rendering contract is
  untouched.
- `goga_tool_pybuggy/commands/init` — the usage-distribution path (`pybuggy init` writing into
  `.goga/usages/cooks/pybuggy/`) extends to distribute the new capability usage files.
- `goga_tool_pybuggy` (composition root) — facade re-exports if the capability surface requires
  them, per the existing facade pattern.

New functionality lives inside pybuggy (no separate package, PRD C6); its internal cell structure
is deliberately not fixed here — it is the concern of the prototype/design stages that consume this
task.

## Notes

- Input documents: ADR `.goga/history/2026/feature-sandbox/adr.md` (accepted 2026-10-06, the single
  authoritative design record), PRD `.goga/history/2026/feature-sandbox/prd.md`.
- Stack decisions made during task formulation: kafka-python as the kafka client (portable, pure
  Python, sufficient for produce-only v1; consumer capability exists but stays unused this
  iteration); new dependencies in the main dependency block; six new cooks usage files created
  (testcontainers, psycopg, kafka-python, wiremock, mokapi, vault-dev).
- Inner declaration shapes of the `services(...)` decorator arguments and the exact `.sandbox.yml`
  schema field forms are design-stage concerns (per the ADR's no-contracts constraint); this task
  fixes semantics and boundaries only.
- No code examples are included in this task by stage constraint.
