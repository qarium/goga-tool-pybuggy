# Sandbox

The **sandbox** is pybuggy's session-scoped service isolation for integration tests: when
a `sandbox.yml` document is present, the built-in `sandbox` pytest fixture becomes
available. The first test that requests it starts the **service under test** and its
mocked dependency **services** (**postgresql**, **kafka**, **vault**, **http**) in
containers and injects their addresses into the service's environment; the test targets
the running instance with `endpoint.bind(sandbox)`. Without the document nothing
sandbox-related is registered — no fixture, no containers.

The sandbox has two surfaces: the [sandbox document](configuration.md) — the declarative
description of the service under test, its dependencies, and their startup data — and the
[Python API](api.md) — the `sandbox` fixture, the session baseline, and the data
operations tests declare. This page covers the lifecycle: activation, the baseline, the
per-test reset, and the runtime environments.

## Activation

The sandbox activates by file presence: `.goga/tools/pybuggy/sandbox.yml`, resolved from
the current working directory only — no upward search. The same `plugin.install()` call
that enables pybuggy also enables the sandbox plugin:

```python
# conftest.py
from goga_tool_pybuggy import plugin

plugin.install()
```

With the document present the built-in `sandbox` fixture exists. The sandbox starts
lazily on the first test that requests the fixture (progress is logged) and stops at
session finalization — a run without sandbox tests starts no containers. An invalid
document fails the run during pytest configuration, before any collection or container
starts. Without the document the suite behaves exactly as it would without the sandbox —
a test requesting the fixture fails with pytest's standard `fixture 'sandbox' not found`.
If the sandbox does not activate, check that the document sits at exactly this path and
that the run starts from the repository root.

## Using the sandbox

Do not define your own `sandbox` fixture — request the built-in one as a test argument.
A typical test declares an endpoint fixture, seeds data (inline declarations or the
`@services` decorator), and binds the api to the running instance:

```python
# test_checkout.py
import pytest

from goga_tool_pybuggy import services
from goga_tool_pybuggy.api import Api, Endpoint


@pytest.fixture(scope="function")
def checkout(api: Api) -> Endpoint:
    return Endpoint(api, "/checkout", method="POST")


@services(postgresql={"db": [{"table": "customers", "rows": [{"id": 1, "name": "Ann"}]}]})
def test_checkout(checkout, sandbox):
    checkout.bind(sandbox)  # the api now targets the sandbox instance
    sandbox.postgresql("db").insert("orders", rows=[{"id": 100, "customer_id": 1}])
    response = checkout(json={"customer": 1, "total": 500})
    response.expect.has_status_code(200)
```

Starting and stopping are automatic — the sandbox starts on first use and stops at
session finalization.

Seed data shared by many tests can be declared once as the session **baseline** — a
session-scoped fixture wrapping `with sandbox.baseline()`; the pattern and its reset
semantics are covered in the [Python API reference](api.md#session-baseline).

## Per-test reset

Before every sandbox test pybuggy resets each dependency service to the baseline and
enqueues the test's marked presets. Test order cannot change outcomes; no custom
autouse reset is needed. Only dependency data resets — the service under test keeps
running for the whole session (its in-memory state is not reset; accepted v1
limitation).

## Preconditions and side effects

- The test environment needs a **docker-compatible container runtime**; the startup
  error names the requirement when it is missing.
- The sandbox pulls the container/DB/Kafka stack into the environment
  (`testcontainers`, `psycopg`, `kafka-python`, `requests` — package dependencies).
- The dependency mocks use fixed test credentials that the instance env must match:
  postgres accepts user `test`, password `test`, database `test` (connect with
  `postgres://test:test@{{db.host}}:{{db.port}}/test`); vault runs in dev mode with the
  root token `sandbox-root` (send it as `VAULT_TOKEN` / `X-Vault-Token`; secrets live on
  the default KV v2 `secret/` mount).
- After the session — including failed or interrupted runs — nothing remains; a rerun
  starts fresh.
- `base_url` remains a required plugin option even with the sandbox document present
  (the render contract is unchanged); tests that bind to the sandbox override it at bind
  time, the rest use the rendered value.

### Running on the host

A plain host run needs nothing from the test author: at `plugin.install()` (with the
document present) pybuggy normalizes the container-host address itself, keeping one
shared address space whether pytest runs on the host or in a container:

- runner inside a container → `TESTCONTAINERS_HOST_OVERRIDE` defaults to
  `host.docker.internal`;
- runner on a host → the override defaults to the host's routable IP (published ports
  listen on `0.0.0.0`, so the host process and the sibling containers reach the same
  dependency through it);
- an explicit `TESTCONTAINERS_HOST_OVERRIDE` in the environment always wins; a failed
  detection changes nothing (set the variable by hand on exotic network setups, e.g. a
  VPN-primary routing table).

### Running the tests inside a container

When pytest itself runs inside a container (a pipeline runner, a CI step image), the
sandbox containers are **siblings** on the host daemon — the engine drives them through
the docker API, nothing runs inside the runner. This topology needs one thing from the
runner's launcher; the address normalization is automatic:

```bash
# the docker socket must be reachable inside the runner
docker run \
  -v /var/run/docker.sock:/var/run/docker.sock \
  ... your-runner-image python -m pytest
```

- The **socket mount** gives the engine a daemon to drive; without it the startup probe
  fails with the runtime-requirement error.
- The **host override** is set by pybuggy itself (`host.docker.internal`); an explicit
  `TESTCONTAINERS_HOST_OVERRIDE` in the runner environment still wins — the escape
  hatch for a plain Linux host, where the Docker Desktop name may need the host's
  address or `host-gateway` instead.
- One shared address space results: the mapped service addresses the tests bootstrap
  on, the address the kafka broker advertises in metadata, and the
  `{{<service>.host}}`/`{{<service>.port}}` values injected into the instance env are
  the same `host:port` — every consumer (runner, instance container) reaches every
  dependency through it.
- Every session gets its **own docker network**: all containers the sandbox starts (the
  dependency services and the service under test) join it, and it is removed at
  teardown. Parallel sandboxes on one daemon are network-isolated from each other; the
  runner keeps using the published host ports as before.
- Alternative — docker-in-docker inside a privileged runner — needs no socket mount, at
  the cost of `--privileged` and a private image cache. The runner still looks like a
  container to the detection, so the automatic override stays `host.docker.internal`
  while the inner daemon publishes its ports inside the runner — on this topology set
  `TESTCONTAINERS_HOST_OVERRIDE` explicitly (typically `localhost`).

### Forwarding the socket through goga pipelines

When the tests run through a **goga pipeline**, the runner is the pipeline's own
container and the launcher command is not yours to write — declare the socket in the
goga config in the home directory, as a `docker.run` argument:

```yaml
# ~/.goga/config.yml
docker:
  run:
    - '--volume=/var/run/docker.sock:/var/run/docker.sock'
```

The same rule applies: without the forwarded socket the sandbox startup probe fails with
the runtime-requirement error; with it, the pipeline container drives the host daemon
and the sandbox containers come up as siblings.
