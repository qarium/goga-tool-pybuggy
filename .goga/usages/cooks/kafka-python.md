# kafka-python — producing sandbox preconditions into kafka topics

## Domain

`kafka-python` is the kafka client of the pybuggy sandbox capability. Its v1 job is narrow:
produce precondition messages from the test process into the topics of the kafka mock (Mokapi),
which speaks the kafka wire protocol. `KafkaConsumer` exists in the library, but read-back is out
of the v1 scope (response-only assertions) — the consumer is deliberately unused.

Import in code:
```python
from kafka import KafkaProducer
```

---

## Producer — construct against the mock's bootstrap address

```python
producer = KafkaProducer(
    bootstrap_servers=f"{host}:{port}",   # mapped host/port of the mock container
    acks="all",
    retries=3,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: k.encode("utf-8"),
)
```

- `bootstrap_servers` takes the mapped address of the container (host + published port from the
  container engine), not the in-container address.
- Connection problems surface lazily: the producer fetches metadata on first use, so a bad
  bootstrap address raises on the first `send`/`flush`, not on construction. The sandbox applies
  batches with a deadline so a broken bootstrap fails the test fast instead of hanging.
- Serializers convert python values to bytes once, at the producer level — keep them as the single
  place where message encoding happens (raw `bytes` are also accepted without serializers).

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
