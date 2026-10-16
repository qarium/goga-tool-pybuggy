# Sandbox — Isolated Service-Logic Testing in pybuggy

## Problem

Engineers in service teams — and, alongside them, the agent-driven development cycle —
need to verify a service's own business logic in isolation. Every service, however,
depends on external systems: a database, kafka, vault, and external HTTP integrations.

Today the only practical option is integration tests that run the service against real
dependencies raised locally or on a stand. Such tests are slow, heavy, and brittle, so
teams write few of them. As a result:

- a service's own logic is tested late and sparsely;
- feedback cycles are long;
- there is no fast, reliable, isolated test layer that engineers — or later the agent
  development cycle — can lean on as a gate.

The primary pain is engineers' ability to write and run isolated service-logic tests
quickly. Integration tests against real dependencies are not going away; the goal is to
sharply reduce how many of them are needed.

## Users

### Primary user — service test author

An engineer in a consumer team who writes pytest tests for a service owned by that team.
The service is packaged as a docker image and depends on external systems (postgresql,
kafka, vault, external HTTP services). The author works in the service repository, runs
the team's ordinary pytest suite locally and in CI, knows pytest well, and should not
need to know the internals of each dependency mock.

**Goal:** verify the service's own business logic quickly and in isolation — write a
test in minutes, run it fast, predefine the data the service will see, and never
maintain real dependencies for it.

**What matters:** speed of writing and running a test; deterministic behavior; easy
per-test data setup and cleanup.

### Secondary actor — autonomous development agent

Generates and runs tests during the automated development lifecycle in the consumer
project (goga pipelines). Will consume the same sandbox tests as a quality gate.
Problem-relevant now — sandbox tests must be ordinary, machine-friendly pytest tests by
design — but deep agent-cycle integration is explicitly deferred and is not an active
goal of this change.

## Goals

1. **Primary — fast isolated testing.** A test author can quickly write and run a test
   of a service's own business logic in an isolated sandbox, without a real database,
   kafka, vault, or external integrations.
2. **Supporting — deterministic per-test state.** Per-test data presets and reset
   between tests give repeatable, order-independent isolated tests.
3. **Supporting — fewer integration tests.** Isolated sandbox tests substantially reduce
   the number of required integration tests against real dependencies (integration
   tests remain for the future, but in much smaller volume).
4. **Foundation only — agent gate.** Sandbox tests are shaped so they can later serve as
   a gate in the agent development cycle. The integration itself is outside this change.

## User Experience

### Entry point

The test author describes the sandbox once, declaratively, in a yaml file at the root
of the service test repository — `.sandbox.yml`: the service image under test, the
service's environment variables, and the set of mocked dependency instances
(postgresql, kafka, vault, http) with per-instance settings.

### Primary scenario

1. The author runs the ordinary pytest command in the service repository.
2. A session-scoped pytest fixture builds the `Sandbox` with the configured services and
   starts it: the service under test is launched from its image, and each configured
   dependency is launched as a mock instance. Startup progress is visible; when ready,
   the service under test is reachable and its dependencies point at the mocks.
3. Before each test, the sandbox resets to its initial state — quickly and without the
   author's attention. Every test starts from the same known state.
4. Inside a test, the author reaches any configured dependency instance by name through
   the sandbox and prepares the data the service will see: insert rows (postgresql),
   prepare stub responses for outgoing HTTP calls (http), put secrets (vault), produce
   messages to topics the service consumes (kafka). The author then exercises the
   service through the standard pybuggy `api` fixture — its address is resolved from the
   sandbox — and asserts on the service's responses.
5. Operations issued through the sandbox API are lazy: they accumulate and are applied
   as a consistent batch, so authoring stays fast and ordering is handled by the product
   rather than by the author.
6. Alternatively (or additionally), a test declares its per-test data preset directly on
   the test itself — a decorator carrying per-service presets — applied for that test on
   top of the reset state.
7. At session end, the sandbox stops and everything it started is removed.

### Alternative scenarios

- **Partial dependency set** — the author configures only the dependencies the service
  actually needs (e.g. only postgresql and http). The sandbox starts exactly those.
- **Session-level initial state** — beyond the yaml instance settings, the session
  fixture may define the initial state of service instances; after each reset the
  sandbox returns to that state.
- **grpc dependency** — not available in this iteration. An author configuring a grpc
  service gets an explicit, clear "not supported yet" signal at startup rather than
  silent breakage.

### Failure scenarios

- **Invalid or missing `.sandbox.yml`** — the run fails fast before anything starts,
  with a clear message pointing at the config problem.
- **Container infrastructure unavailable or a container fails to start** — the sandbox
  fails fast with an actionable error (no hanging tests); already-started containers are
  cleaned up.
- **Service under test crashes during the run** — affected tests fail with an indication
  that the service died and how to see its output, not an opaque assertion error.
- **A mock operation applied on behalf of a test fails** — the test fails with a
  readable error identifying the failed operation.
- **Cleanup is guaranteed on any exit path** — stopping the sandbox removes the
  containers it started; rerunning the suite always starts fresh.

### States

- **starting** — containers bootstrapping; progress visible.
- **running** — service and mocks up; tests execute.
- **per-test reset** — brief, silent return to the initial state between tests.
- **stopped** — containers removed.

### Feedback

The author always understands: whether the sandbox started; which services are in it;
whether a failure comes from the environment or from the test logic; and that state was
reset between tests.

## Requirements

### R1. Declarative sandbox configuration

- **R1.1** The author must be able to describe a sandbox declaratively in a yaml file at
  the root of the service test repository, named `.sandbox.yml`: the service image under
  test, the service's environment variables, and the set of dependency instances with
  per-instance settings.
- **R1.2** Supported dependency kinds in this iteration: postgresql, kafka, vault, http.
  Configuring a grpc dependency must produce an explicit "not supported yet" error at
  startup.
- **R1.3** Any subset of the supported dependency kinds may be configured.

### R2. Sandbox lifecycle

- **R2.1** The product must provide a pytest-integrated way to start the sandbox for a
  test session: launch the service under test from its configured image and each
  configured dependency as a mock instance.
- **R2.2** On start, the service under test must be wired to its mocked dependencies per
  the configuration, and the service must be reachable by tests when the session begins.
- **R2.3** Startup progress must be visible, and tests must not run before the sandbox
  is ready.
- **R2.4** At session end the sandbox must stop and remove everything it started — on
  every exit path (success, failure, interruption).

### R3. Per-test isolation

- **R3.1** The product must support resetting the sandbox to its initial state between
  tests, so each test starts from the same known state.
- **R3.2** The reset must happen automatically between tests when the author uses the
  provided fixture pattern, without the author's attention.
- **R3.3** The author may define a session-level initial state of dependency instances
  (distinct from the yaml instance settings); after each reset the sandbox returns to
  that state.

### R4. Dependency data control (preparation only in this iteration)

- **R4.1** Inside a test, the author must be able to reach each configured dependency
  instance through the sandbox by its name and prepare the data the service will see:
  insert rows (postgresql), prepare stub responses for outgoing HTTP calls (http), put
  secrets (vault), produce messages to topics the service consumes (kafka).
- **R4.2** The author must be able to declare per-test data presets on a test (a
  decorator carrying per-service presets), applied for that test on top of the reset
  state.
- **R4.3** The dependency API must be lazy: operations accumulate and are applied as a
  consistent batch; the product handles ordering — the author does not manage apply
  order manually.
- **R4.4** Read-back of dependency state for assertions is not part of this iteration:
  v1 assertions are made on the service's responses.

### R5. Calling the service under test

- **R5.1** The address of the running service under test must be available to the
  existing pybuggy `api` fixture (base_url resolved from the sandbox), so tests call the
  service the standard pybuggy way without custom client wiring.

### R6. Failure behavior

- **R6.1** Invalid or missing configuration: fail fast before anything starts, with a
  clear error pointing at the problem.
- **R6.2** Container infrastructure unavailable or a container fails to start: fail fast
  with an actionable error; already-started containers are cleaned up; tests never hang.
- **R6.3** Service under test dies mid-run: affected tests fail with an indication that
  the service died and how to see its output.
- **R6.4** An accumulated mock operation that fails on apply: the test fails with a
  readable error identifying the failed operation.
- **R6.5** Any rerun of the suite starts fresh, with no leftover state from a previous
  run.

### R7. Distribution and enablement

- **R7.1** The capability must be delivered as part of pybuggy: available to consumer
  test suites through the pybuggy distribution path, enableable consistently with the
  existing pybuggy plugin enable pattern, with no separate installation.
- **R7.2** The capability must come with user documentation sufficient for an author to
  create `.sandbox.yml` and the sandbox fixtures without product-side scaffolding.

## Constraints

- **C1. Fixed infrastructure stack** (explicitly imposed): the sandbox runs on
  testcontainers; dependency mocks use the specified tools — the official Vault image in
  Dev mode, pg-wire-mock for postgres, mockapi for kafka, wiremock for http (grpc will
  also use wiremock later).
- **C2. grpc mocking is excluded** in this iteration; the product must signal this
  explicitly instead of failing silently.
- **C3. Configuration surface**: yaml file named `.sandbox.yml` at the root of the
  service test repository.
- **C4. Python API shape** (explicitly imposed): fixture-driven — a session-scoped
  fixture managing the `Sandbox` object (`start`/`stop`/`clear`), a per-test data-preset
  decorator, and a lazy accumulate-then-apply services API.
- **C5. Complements, not replaces**: integration tests against real dependencies remain
  a separate future concern; the sandbox coexists with them.
- **C6. In-product placement**: the capability lives inside pybuggy (no separate
  package); distribution and enablement follow pybuggy's existing patterns.
- **C7. Assertions in v1 are response-only**: no dependency-state read-back.
- **C8. Container runtime dependency**: the environment running the tests (developer
  machine or CI) must have a container runtime available; this requirement is visible to
  the user and must be surfaced clearly when it is not met.

## Scope

### In Scope

- Declarative `.sandbox.yml` configuration (service image, env, dependency instances
  with per-instance settings) for the supported kinds: postgresql, kafka, vault, http.
- Sandbox lifecycle managed from a pytest session fixture: start (service container from
  image + mock dependency instances), readiness before tests, stop and full cleanup on
  every exit path.
- Wiring the service under test to its mocked dependencies per the configuration.
- Per-test isolation: automatic reset to the initial state between tests; author-defined
  session-level initial state.
- Dependency data-preparation API reachable in tests by service name (insert rows /
  stub http responses / put vault secrets / produce kafka messages), with lazy
  accumulate-then-apply semantics.
- Per-test data presets via a decorator on the test.
- Integration with the existing pybuggy `api` fixture (base_url resolved from the
  sandbox).
- Distribution inside pybuggy through the existing plugin enable pattern, plus user
  documentation.
- Fail-fast failure behavior with actionable errors and guaranteed cleanup; fresh state
  on reruns.
- Explicit "not supported yet" signal for a configured grpc dependency.

### Out of Scope

- grpc mock support (deferred).
- Dependency-state read-back or call verification for assertions (v1 asserts on service
  responses only).
- Integration into the agent development cycle as a gate (tests are shaped to be usable
  later; no wiring into the autonomous pipeline now).
- Parallel test execution support (pytest-xdist or multiple simultaneous sandboxes) —
  v1 is a single sandbox with sequential tests.
- `pybuggy init` scaffolding of sandbox artifacts — in v1 the author creates
  `.sandbox.yml` and the fixtures manually, per documentation.
- Creating, replacing, or managing integration tests against real dependencies or real
  dependency stands.
- Fidelity parity with real engines — the mocks are accepted as approximations; the
  product optimizes speed and simplicity, not behavioral equivalence.
- Specific support for non-HTTP services under test — v1 targets services callable the
  pybuggy-native way through the `api` fixture.

## Success Criteria

1. **Isolated logic test, end-to-end.** In a consumer service repository, an author —
   using only `.sandbox.yml` and the documented pytest fixtures — can write a test that
   exercises the service's business logic against mocked dependencies, run it with the
   ordinary pytest command, and get a pass/fail result.
2. **No real dependencies required.** A sandbox test suite for a service with, e.g.,
   postgres and http dependencies runs green in an environment where only a container
   runtime is available — no database, kafka, or external integrations installed.
3. **New tests are cheap.** Writing a new isolated test for an already-configured
   sandbox requires only test code — no product, config, or tooling changes.
4. **Per-test determinism.** Within one session, test order does not change outcomes:
   the reset returns the sandbox to the initial state, and a per-test preset applies
   only to the test that declares it.
5. **No leaks.** After a session — including failed or interrupted runs — no sandbox
   containers remain, and an immediate rerun starts fresh and behaves identically.
6. **Actionable failures.** An invalid config, an unavailable container runtime, or a
   crashing service produces a clear, actionable error identifying the cause — never a
   hang or an opaque assertion failure.
7. **pybuggy-native service access.** A test that uses only the existing `api` fixture
   reaches the service under test running in the sandbox, with its address resolved from
   the sandbox.
