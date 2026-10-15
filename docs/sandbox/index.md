# Sandbox

The **sandbox** is pybuggy's session-scoped isolated service testing capability: when the
pybuggy tools home holds a `sandbox.yml` document, the product `sandbox` pytest fixture
exists — the first test that uses it starts the **instance under test** plus its mocked
dependency **services** (**postgresql**, **kafka**, **vault**, **http**) in containers,
wires them into the instance environment; a test binds its api to the sandbox instance
explicitly through `endpoint.bind(sandbox)`. Without the document the product is fully
inert — no fixture, nothing starts, nothing changes.

The sandbox splits into two surfaces: the [sandbox document](configuration.md) — the
declarative description of the instance, its dependency services, and their startup data —
and the [Python API](api.md) — the `sandbox` fixture, the session baseline, and the data
operations tests declare. This page covers the lifecycle: activation, the baseline, the
per-test reset, and the environments the tests run in.

## Activation

The sandbox activates by presence: `.goga/tools/pybuggy/sandbox.yml`, resolved from the
current working directory only — resolution never searches elsewhere. The same plugin
installation call that enables pybuggy installs the sandbox plugin — nothing else is
enabled:

```python
# conftest.py
from goga_tool_pybuggy import plugin

plugin.install()
```

With the document present, the product `sandbox` fixture exists; the sandbox starts
lazily, on the first test that requests the fixture (the progress is visible in the
output), and stops at session finalization — a run without sandbox tests starts no
containers. An invalid document fails the run at configphase, before any collection or
container; without the document the suite behaves exactly as it would without the sandbox
(a test requesting the fixture fails with pytest's standard `fixture 'sandbox' not
found`). If the sandbox does not activate, verify the document sits at exactly this path
and that the run starts from the repository root.

## The sandbox fixture and the baseline

The product owns the `sandbox` fixture (session-scoped): do not define your own — take it
as a test argument, or let the `@services` preset decorator request it for you (see
[Presets](api.md#presets)). The sandbox starts on the first use and stops at session
finalization; the stop is product-owned.

A session-scoped consumer fixture depending on the product one establishes the
code-declared baseline:

```python
# conftest.py
import pytest


@pytest.fixture(scope="session")
def seeded(sandbox):
    with sandbox.baseline():  # the baseline boundary — author code
        sandbox.postgresql("db").insert("customers", rows=[{"id": 1, "name": "Ann"}])
        sandbox.vault("secrets").put("payment/api-key", {"api_key": "test-key"})
    yield sandbox  # stop is product-owned — do not stop manually
```

Operations inside the baseline boundary apply immediately and become the session baseline:
after every reset the services return to exactly this state.

## Per-test reset

Product-owned: before every sandbox test the plugin's per-test fixture returns each
dependency service to the baseline and enqueues the test's marked presets. Test order
cannot change outcomes, and no consumer autouse reset is needed. Only dependency data
resets; the instance container keeps running (instance in-memory state not resetting is
an accepted v1 limitation).

## Preconditions and side effects

- The environment running the tests needs a **docker-compatible container runtime**; the
  startup error names the requirement when it is missing.
- The sandbox pulls the container/DB/Kafka stack into the environment
  (`testcontainers`, `psycopg`, `kafka-python`, `requests` — main dependencies of the
  package).
- The dependency mocks carry fixed test credentials the instance env must match: the
  postgres mock accepts user `test`, password `test`, database `test` (all created by
  the container — connect with `postgres://test:test@{{db.host}}:{{db.port}}/test`); the vault
  mock runs in dev mode with the root token `sandbox-root` (send it as `VAULT_TOKEN` /
  `X-Vault-Token`; secrets live on the default KV v2 `secret/` mount).
- After the session — including failed or interrupted runs — nothing remains; a rerun
  starts fresh.
- `base_url` stays a required plugin option even with the sandbox document present (the
  render contract is unchanged); the tests that bind their api to the sandbox override it
  at bind time with the sandbox address, the other tests use the rendered value.

### Running on the host

A plain host run needs nothing from the test author: at `plugin.install()` (when the sandbox
document is present) pybuggy normalizes the container-host address itself — the sandbox keeps
one shared address space whether pytest runs on the host or in a container:

- the runner is inside a container → `TESTCONTAINERS_HOST_OVERRIDE` defaults to
  `host.docker.internal`;
- the runner is on a host → the override defaults to the host's own routable IP (published
  ports listen on `0.0.0.0`, so the host process and the sibling containers reach the same
  dependency through it);
- an explicit `TESTCONTAINERS_HOST_OVERRIDE` in the environment always wins; a failed
  detection changes nothing (the mapped-`localhost` behavior — set the variable by hand on
  exotic network setups, e.g. a VPN-primary routing table).

### Running the tests inside a container

When pytest itself runs inside a container (a pipeline runner, a CI step image), the sandbox
containers are **siblings** on the host daemon — the engine drives them through the docker API,
nothing runs inside the runner. That topology needs one thing from the runner's launcher —
the address normalization is automatic:

```bash
docker run \
  -v /var/run/docker.sock:/var/run/docker.sock \        # the daemon must be reachable
  ... your-runner-image python -m pytest
```

- The **socket mount** gives the engine a daemon to drive; without it the startup probe fails
  with the runtime-requirement error.
- The **host override** is set by pybuggy itself (`host.docker.internal`); an explicit
  `TESTCONTAINERS_HOST_OVERRIDE` in the runner environment still wins — the escape hatch for
  a plain Linux host, where the Docker Desktop name may need the host's address or
  `host-gateway` instead.
- One shared address space results: the mapped service addresses the tests bootstrap on, the
  kafka broker advertises in metadata, and the `{{<service>.host}}`/`{{<service>.port}}`
  placeholders inject into the instance env are the same `host:port` — every consumer (runner,
  instance container) reaches every dependency through it.
- Every session gets its **own docker network**: all containers the sandbox starts (the
  dependency services and the instance under test) join it, and it is removed at teardown.
  Parallel sandboxes on one daemon are network-isolated from each other; the runner keeps
  consuming the published host ports as before.
- Alternative — a docker-in-docker daemon inside a privileged runner — needs neither the socket
  nor the override, at the cost of `--privileged` and a private image cache; the sandbox works
  unchanged in both topologies.
