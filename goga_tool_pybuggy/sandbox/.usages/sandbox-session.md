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
would shadow it and feed the reset and the api guard a foreign object). Take the fixture as a
test argument, or let the `@services` preset decorator request it for you:

```python
from goga_tool_pybuggy import services


def test_direct(sandbox):  # requests the sandbox explicitly
    sandbox.postgresql("db").insert("orders", rows=[{"id": 100}])


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
    yield sandbox  # stop is product-owned — do not stop manually
```

Operations inside the baseline boundary apply immediately and become the session baseline: after
every reset the services return to exactly this state. Baseline rows may use `$ref` / `$lookup`
references like any declaration — after every reset the journal replay re-applies and re-resolves
them, so generated keys stay consistent between the baseline and the tests built on top of it.

## Per-test reset

Product-owned: before every sandbox test the plugin's per-test fixture returns each dependency
service to the baseline and enqueues the test's marked presets. Test order cannot change
outcomes, and no consumer autouse reset is needed. Only dependency data resets; the instance
container keeps running (service in-memory state not resetting is an accepted v1 limitation).

## Calling the service

The api fixture binds the sandbox per test: a test whose fixture closure includes the sandbox
fixture — a direct request, a consumer fixture parameter, a `usefixtures` mark (what
`@services` stamps), or an autouse dependency — resolves to the sandbox's service address with
the request guard; every other test uses the configured base_url (`--base-url` / `BASE_URL` /
config) with no guard.

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

- For a sandbox-bound test the sandbox address overrides the configured base_url value; the
  startup output names the source.
- `--base-url` applies to the tests that do not use the sandbox; sandbox-bound tests ignore it.
- Declared operations apply automatically as one batch before the first service call — also the
  moment when `$ref` / `$lookup` row values resolve, so a declaration made after earlier service
  calls may reference rows those calls created (`$lookup`).
- The binding is by declaration: a consumer fixture that reaches the sandbox only through a lazy
  `request.getfixturevalue("sandbox")` call does not appear in the fixture closure — declare the
  dependency as a parameter instead.

## Preconditions and side effects

- The environment running the tests needs a docker-compatible container runtime; the startup
  error names the requirement when it is missing.
- After the session — including failed or interrupted runs — nothing remains; a rerun starts
  fresh.
- A crashed service fails the affected tests with an indication that the service died and where
  its output is.
- If the sandbox does not activate, verify the document sits at exactly
  `.goga/tools/pybuggy/sandbox.yml` — resolution is cwd-only and never searches elsewhere.
