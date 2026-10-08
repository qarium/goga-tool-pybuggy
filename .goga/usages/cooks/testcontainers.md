# testcontainers — container lifecycle for the sandbox

## Domain

`testcontainers` (the `testcontainers-python` package) is the container engine of the pybuggy sandbox
capability. It starts and removes the instance under test and every mocked dependency service
(postgres, mokapi, vault, wiremock), checks container-runtime availability before the first start,
and provides the crash-safe cleanup guarantee ("no leftover containers on any exit path").

Import in code:
```python
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for
```

Install: the core package plus module extras — `testcontainers[postgres]`.

---

## Container runtime requirement

testcontainers talks to a docker-compatible daemon through the `docker` python SDK. The runtime is
an external requirement of the environment running the tests (developer machine or CI):

- `DOCKER_HOST` selects the daemon endpoint (local socket, remote docker, docker-in-docker).
- `TESTCONTAINERS_HOST_OVERRIDE` rewrites the host clients use to reach published ports (needed
  inside docker-in-docker and some CI setups).
- When no runtime is reachable, the first container start raises a low-level docker SDK error.
  The sandbox must probe the daemon explicitly before starting anything and convert the failure
  into an actionable error naming the requirement ("a docker-compatible container runtime must be
  available") — never let tests hang on a silent connection timeout.

---

## Postgres module container

The postgres service is a real postgres container (ADR decision) started through the dedicated
module — it pins the image, sets user/password/dbname env, and waits for the server to accept
connections before `start()` returns:

```python
postgres = PostgresContainer("postgres:16-alpine")
postgres.start()

host = postgres.get_container_host_ip()
port = postgres.get_exposed_port(5432)
url = postgres.get_connection_url()  # SQLAlchemy-style: postgresql+psycopg://user:pass@host:port/db
```

- The connection URL carries a SQLAlchemy dialect prefix (`postgresql+psycopg://`). When feeding a
  plain driver (psycopg), take host/port/credentials from the container accessors instead of
  parsing the dialect prefix out of the URL.
- User/password/dbname default to `test`/`test`/`test` unless overridden via constructor env
  (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` are applied by the module).
- Module containers have built-in readiness: `start()` returns only after the server accepts
  connections — no extra wait loop is needed for postgres. The sandbox nonetheless disables this
  internal wait and runs its own probe loop, so the declared readiness deadline and interval reach
  the postgres wait too.

---

## Generic containers (mokapi, vault, wiremock, service under test)

Mock services and the instance under test use the generic container:

```python
container = (
    DockerContainer("wiremock/wiremock:3.13.0")
    .with_exposed_ports(8080)
    .with_env("VAR", "value")
    .with_command("--verbose")
)
container.start()

host = container.get_container_host_ip()
port = container.get_exposed_port(8080)
```

- `with_exposed_ports(...)` publishes the container port on a random free host port — always read
  the mapped port back via `get_exposed_port(...)`; never assume a fixed host port.
- `with_env(...)` / `with_command(...)` set container env and the entrypoint arguments (this is how
  the generated AsyncAPI document's in-container path, vault dev flags, and wiremock options are
  passed).
- The AsyncAPI document is generated in memory from the topics declared inline on the kafka
  service entry and transferred through the docker API (no bind mount — host paths resolve on the
  daemon's filesystem and break when the engine itself runs inside a container); its in-container
  path is passed as the start argument.
- `with_labels(...)` stamps containers with identification labels — useful to find and clean up
  sandbox containers.

### Readiness for generic containers

A generic container is "started" when its process runs, not when it serves. Readiness is the
consumer's concern — the sandbox applies two patterns:

```python
wait_for(container=container, condition=lambda c: probe_is_ready(c), timeout=30, interval=0.5)
```

- `wait_for(...)` polls the condition with a timeout — use it for log-based or socket-based checks.
- HTTP readiness (vault `/v1/sys/health`, wiremock admin, the instance health path) is a plain
  retry-loop over the mapped host/port — the sandbox already owns HTTP probing; prefer an explicit
  probe loop with a deadline over open-ended waiting.

---

## Lifecycle and stop semantics

- `container.start()` blocks until the container runs (module containers: until ready).
- `container.stop()` removes the container (testcontainers removes on stop by default). Stop is the
  sandbox's per-session teardown action and must run on every exit path.
- Context-manager form — `with DockerContainer(...) as c:` — starts on entry and stops on exit; use
  it only where the lifecycle is lexically scoped. The sandbox session lifecycle spans fixtures, so
  explicit start/stop under a try/finally is the right shape.
- Stopping a container that is already stopped is safe.

---

## Ryuk — the cleanup safety net

testcontainers starts a small sidecar container ("Ryuk") that watches the client connection and
kills every container started in the session when the client process dies — crash, interrupt,
`kill -9`. It is the last-resort guarantee behind the sandbox's explicit stop:

- Ryuk is enabled by default; never run the sandbox with `TESTCONTAINERS_RYUK_DISABLED=true` —
  that converts a crashed run into leaked containers (violates the "no leaks" requirement).
- Ryuk covers abnormal exits; normal exits still require the explicit stop (Ryuk fires with a
  delay, and an immediate rerun must start fresh without waiting for it).
