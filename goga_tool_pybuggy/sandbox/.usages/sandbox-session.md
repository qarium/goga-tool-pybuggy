# Sandbox session — the product fixture, baseline, and reset

## Domain

The pytest integration of the sandbox: how a consumer suite activates it, declares the session
baseline, and reaches the service under test through the api fixture. Target audience: service
test authors.

## Activation

The sandbox activates by presence: the sandbox document at `.goga/tools/pybuggy/sandbox.yml`,
under the pybuggy tools home of the test repository. The same plugin installation call that
enables pybuggy installs the sandbox plugin — nothing else is enabled:

```python
# conftest.py
from goga_tool_pybuggy import plugin

plugin.install()
```

With the document present, the product `sandbox` fixture exists; the sandbox starts lazily, on
the first test that requests the fixture (the progress is visible in the output), and stops at
session finalization. An invalid document fails the run at configphase — before any collection
or container. Without the document the suite behaves exactly as it would without the sandbox:
no fixture exists, and a test requesting it fails with pytest's standard
`fixture 'sandbox' not found`.

## The product sandbox fixture

Do not define your own `sandbox` fixture — the product owns the name (a consumer definition
would shadow it and feed the reset and the api pre-flight a foreign object). Take the fixture
as a test argument, or let the `@services` preset decorator request it for you:

```python
from goga_tool_pybuggy import services


def test_direct(sandbox):  # requests the sandbox explicitly
    sandbox.postgresql("db").insert("orders", rows=[{"id": 100}])
    sandbox.redis("cache").set("feature-flag/a", "enabled")


@services(postgresql={"db": [{"table": "customers", "rows": [{"id": 1}]}]})
def test_marked(api):  # the decorator's usefixtures mark pulls the sandbox in
    ...
```

## Session baseline

A session-scoped consumer fixture depending on the product one establishes the code-declared
baseline:

```python
# conftest.py
import pytest


@pytest.fixture(scope="session")
def seeded(sandbox):
    with sandbox.baseline():  # the baseline boundary — author code
        sandbox.postgresql("db").insert("customers", rows=[{"id": 1, "name": "Ann"}])
        sandbox.vault("secrets").put("payment/api-key", {"api_key": "test-key"})
        sandbox.redis("cache").set("feature-flag/a", "enabled")
    yield sandbox  # stop is product-owned — do not stop manually
```

Operations inside the baseline boundary apply immediately and become the session baseline: after
every reset the services return to exactly this state. Baseline rows may use `$ref` / `$lookup`
references like any declaration — after every reset the journal replay re-applies and re-resolves
them, so generated keys stay consistent between the baseline and the tests built on top of it.
Redis baseline operations journal the same way — the reset replays them onto the flushed
database.

## Per-test reset

Product-owned: before every sandbox test the plugin's per-test fixture returns each dependency
service to the baseline and enqueues the test's marked presets. Test order cannot change
outcomes, and no consumer autouse reset is needed. Only dependency data resets; the instance
container keeps running (service in-memory state not resetting is an accepted v1 limitation).
A redis service resets by `FLUSHDB` of its declared logical database plus the baseline replay —
the container keeps running through the reset.

## Calling the service

Binding the api to the sandbox is explicit — call `endpoint.bind(sandbox)` (or
`api.bind(sandbox)`) once in the test body. The bind replaces the client address with the
sandbox's service address and installs the request pre-flight (the pending data batch applies
and the service liveness is ensured before every request); every other test uses the
configured base_url (`--base-url` / `BASE_URL` / config) with no pre-flight.

```python
from goga_tool_pybuggy.api import Api, Endpoint


@pytest.fixture(scope="function")
def checkout(api: Api) -> Endpoint:
    return Endpoint(api, "/checkout", method="POST")


def test_checkout(checkout, sandbox):
    checkout.bind(sandbox)
    sandbox.postgresql("db").insert("orders", rows=[{"id": 100, "customer_id": 1}])
    response = checkout(json={"customer": 1, "total": 500})
    response.expect.has_status_code(200)
```

- All endpoints of one test share one `Api` — one `bind(sandbox)` rebinds them together.
- `--base-url` applies to the tests that do not bind; a bound test uses the sandbox address.
- Declared operations apply automatically as one batch before the first service call — also the
  moment when `$ref` / `$lookup` row values resolve, so a declaration made after earlier service
  calls may reference rows those calls created (`$lookup`).
- A `@services`-marked test that calls the service takes the `sandbox` argument and binds
  explicitly — the mark alone pulls the sandbox in for the presets and the reset, not for the
  address.

## Preconditions and side effects

- The environment running the tests needs a docker-compatible container runtime; the startup
  error names the requirement when it is missing.
- Both run topologies work out of the box — pytest on the host and pytest inside a container:
  at install time the product defaults `TESTCONTAINERS_HOST_OVERRIDE` to the one address every
  consumer reaches (`host.docker.internal` in a container, the host's own routable IP on a
  host run); an explicit value in the environment always wins.
- After the session — including failed or interrupted runs — nothing remains; a rerun starts
  fresh.
- A crashed service fails the affected tests with an indication that the service died and where
  its output is.
- If the sandbox does not activate, verify the document sits at exactly
  `.goga/tools/pybuggy/sandbox.yml` — resolution is cwd-only and never searches elsewhere.
