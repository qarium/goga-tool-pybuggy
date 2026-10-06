# Data operations — preparing dependency data in tests

## Domain

Declaring the data a service under test will see: rows in postgres, stub responses of http
dependencies, secrets in vault, messages in kafka topics. Target audience: service test authors.
Operations are declared from tests through instance views, or on the test itself as a preset; they
are lazy — the sandbox applies them as one consistent batch right before the first call to the
service under test.

## Reaching an instance

Every configured instance is reachable by name through the session fixture, kind-named:

```python
sandbox.postgresql("db").insert(...)  # a postgresql instance named db
sandbox.http("payments").stub(...)  # an http instance named payments
sandbox.vault("secrets").put(...)  # a vault instance named secrets
sandbox.kafka("events").produce(...)  # a kafka instance named events
```

Each view also exposes `name`, `host`, and `port` — `host` and `port` are the mapped address the
service env placeholders resolved to.

## Declaring operations

```python
sandbox.postgresql("db").insert("orders", rows=[{"id": 1, "total": 100}])

sandbox.http("payments").stub(
    {
        "request": {"method": "POST", "urlPath": "/v1/charge"},
        "response": {"status": 200, "jsonBody": {"status": "captured"}},
    }
)

sandbox.vault("secrets").put("payment/api-key", {"api_key": "test-key"})

sandbox.kafka("events").produce("orders.events", {"id": 1}, key="1")
```

Nothing is executed at declaration time. The sandbox applies the accumulated batch automatically
before the first call to the service under test — there is no manual apply.

## Per-test presets

Declare data directly on the test:

```python
from goga_tool_pybuggy import services


@services(
    postgresql={
        "db": [
            {"table": "customers", "rows": [{"id": 1, "name": "Ann"}]},
            {"table": "orders", "rows": [{"id": 100, "customer_id": 1}]},
        ]
    },
    http={
        "payments": [
            {
                "request": {"method": "GET", "urlPath": "/v1/rate"},
                "response": {"status": 200, "jsonBody": {"rate": 0.5}},
            }
        ]
    },
)
def test_checkout(api): ...
```

Each declaration carries the same fields as the matching view operation. Presets apply only to the
test declaring them, on top of the reset state, ahead of the test's own operations.

## Ordering and foreign keys

Operations apply in the order declared, per instance: presets first, then in-test operations in
call order; rows within one insert apply in list order. Foreign-key chains are expressed by
declaring parents before children — one `insert` call targets one table. Reset-side cleanup
needs no ordering from the author.

## Preconditions and side effects

- Instance names and kinds come from `.sandbox.yml`; an unknown name fails fast.
- A failed operation fails the test with a readable error identifying the operation.
- Read-back of dependency state is not part of this iteration — assert on service responses.
