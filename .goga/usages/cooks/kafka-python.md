# kafka-python — producing sandbox preconditions into kafka topics

## Domain

`kafka-python` is the kafka client of the pybuggy sandbox capability. Its v1 job is narrow:
produce precondition messages from the test process into the topics of the kafka mock (Mokapi),
which speaks the kafka wire protocol. `KafkaConsumer` exists in the library, but read-back is out
of the v1 scope (response-only assertions) — the consumer is deliberately unused.

Version floor: kafka-python >= 3 (`kafka-python>=3.0` in the pybuggy dependencies). v3 negotiates
the wire protocol with ApiVersionsRequest v4 — older mokapi releases cannot answer it, and the
sandbox's mokapi pin (>= 0.52) matches the v3 client.

Import in code:
```python
from kafka import KafkaProducer
from kafka.serializer import Serializer
```

---

## Producer — construct against the mock's bootstrap address

```python
class ValueSerializer(Serializer):
    def serialize(self, topic, headers, value):       # the Serializer interface (v3)
        return json.dumps(value).encode("utf-8")

producer = KafkaProducer(
    bootstrap_servers=f"{host}:{port}",   # mapped host/port of the mock container
    acks="all",
    retries=3,
    value_serializer=ValueSerializer(),
)
```

- `bootstrap_servers` takes the mapped address of the container (host + published port from the
  container engine), not the in-container address.
- Connection problems surface lazily: the producer fetches metadata on first use, so a bad
  bootstrap address raises on the first `send`/`flush`, not on construction. The sandbox applies
  batches with a deadline so a broken bootstrap fails the test fast instead of hanging.
- Serializers implement the `Serializer` interface (`serialize(topic, headers, value)`) —
  kafka-python 3 deprecates plain callables with a `DeprecationWarning` on every construction,
  and consumer projects routinely run pytest with `filterwarnings = error`, which would turn the
  data-plane bootstrap into a failure. Keep encoding in the serializer as the single place where
  message encoding happens (raw `bytes` are also accepted without serializers).
- After bootstrap the client follows the **advertised** broker address of the metadata answer —
  the bootstrap address and the broker's advertised address must agree (the mokapi cookbook
  explains how the sandbox guarantees that).

---

## Produce and flush — the batch boundary

```python
future = producer.send("orders.events", key=order_id, value=payload)
future.get(timeout=10)          # per-message delivery result (raises on failure)

producer.flush(timeout=30)      # everything buffered is delivered when it returns
```

- `send(...)` is asynchronous — it buffers; it does not mean "delivered".
- `future.get(timeout=...)` raises on delivery failure (`kafka.errors.KafkaError`) — use it (or
  relying on flush + a subsequent check) to convert a failed precondition into a readable test
  error naming the failed operation.
- `flush(timeout=...)` is the boundary of "the batch is applied": when it returns, every buffered
  message of the accumulated batch has been acknowledged. The sandbox applies one batch per test —
  produce all messages, then flush once.
- A message `key` decides the partition; without a key the round-robin partitioner is used.

---

## Lifecycle

- `producer.close()` releases the connection — close it in the session teardown (after the last
  batch; `close()` implies a final flush with its timeout).
- `producer.partitions_for(topic)` triggers metadata resolution — usable as an explicit
  bootstrap/health probe without sending a message.

---

## Errors

- `kafka.errors.KafkaTimeoutError` — delivery or metadata deadline exceeded.
- `kafka.errors.KafkaError` — broker-reported failures (unknown topic, record too large).
- `future.get(timeout=...)` re-raises the delivery exception in the caller — the sandbox maps it
  onto the failed-operation error for the author.
