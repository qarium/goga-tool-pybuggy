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
