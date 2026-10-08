# Data operations — preparing dependency data in tests

## Domain

Declaring the data a service under test will see: rows in postgres, stub responses of http
dependencies, secrets in vault, messages in kafka topics. Target audience: service test authors.
Operations are declared from tests through instance views, or on the test itself as a preset; they
are lazy — the sandbox applies them as one consistent batch right before the first call to the
service under test.

## Reaching an instance

Every configured service is reachable by name through the session fixture, kind-named:

```python
sandbox.postgresql("db").insert(...)  # a postgresql service named db
sandbox.http("payments").stub(...)  # an http service named payments
sandbox.vault("secrets").put(...)  # a vault service named secrets
sandbox.kafka("events").produce(...)  # a kafka service named events
```

Each view also exposes `name`, `host`, and `port` — `host` and `port` are the mapped address the
env placeholders of the instance under test resolve to.

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

- A produced topic must be declared on the kafka service in the sandbox document — an undeclared
  topic fails the operation.

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

Operations apply in the order declared, per service: presets first, then in-test operations in
call order; rows within one insert apply in list order. Foreign-key chains follow the declaration
order — parents before children, one `insert` call targeting one table (the database constraint
still needs the parent row applied first). Reset-side cleanup needs no ordering from the author.

## Referencing rows

Explicit literal ids are optional: a row value may reference another row instead of carrying a
hardcoded key. Two reference forms exist, both plain data in the declaration:

- **`$ref`** — addresses the data plane's own applied rows:

  ```python
  sandbox.postgresql("db").insert("customers", rows=[{"name": "Ann"}])  # id generated
  sandbox.postgresql("db").insert("orders", rows=[{"customer_id": {"$ref": "customers.0.id"}, "total": 500}])
  ```

  The address `table.index.column` positions the row in the table's applied-row stream since the
  last reset — journal baseline first, then presets, then in-test declarations, in application
  order. The value is the real applied column value (an autoincrement id resolves to whatever the
  sequence generated; after a reset the values are deterministic — 1, 2, 3 in application order).
  A later row of the same insert may reference an earlier row. Inserting an extra earlier parent
  row shifts the indexes — see `$lookup` for a position-independent reference.

- **`$lookup`** — matches the current database state by predicate, regardless of who created the
  row (the service under test included):

  ```python
  # the service itself created the customer through its API
  response = checkout.post(json={"name": "Ann", "email": "ann@x.io"})

  sandbox.postgresql("db").insert(
      "orders",
      rows=[{"customer_id": {"$lookup": {"table": "customers", "where": {"email": "ann@x.io"}}}}],
  )
  ```

  The predicate must match exactly one row — zero matches fail naming the missing precondition,
  several matches fail naming the ambiguity. The resolved column defaults to the table's primary
  key; pass `"column"` to choose another.

Rules common to both forms:

- References are top-level row values only; a nested dict carrying `$ref` stays plain column
  data.
- The grammar is validated at declaration — a malformed reference fails before anything executes.
- Resolution happens at apply time, right before the first service call; references never rewrite
  the declaration.
- References resolve within one postgres service; rows created by raw sql startup statements are
  addressable only through `$lookup`.

## Preconditions and side effects

- Service names and kinds come from the sandbox document
  (`.goga/tools/pybuggy/sandbox.yml`); an unknown name fails fast.
- A failed operation fails the test with a readable error identifying the operation.
- Read-back of dependency state is not part of this iteration — assert on service responses.
