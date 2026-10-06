# mokapi — the sandbox kafka mock

## Domain

`mokapi` (image `mokapi/mokapi`, Go, MIT — github.com/marle3003/mokapi) is the kafka dependency
mock of the pybuggy sandbox capability. It is a spec-driven, local-first mock tool: the kafka
topology (topics and their partitions) is described by an **AsyncAPI** document, and the data plane
is a real kafka wire-protocol listener that ordinary kafka clients (kafka-python producer) connect
to directly.

---

## Running with an AsyncAPI spec

Specs are passed as positional file arguments; config files reach the container through a volume
mount:

```bash
docker run --rm -p 8080:8080 -p 9092:9092 \
  -v $(pwd):/data mokapi/mokapi /data/asyncapi.yaml
```

- The AsyncAPI document defines the mocked topics (kafka bindings); mokapi serves them on its kafka
  listener (default port `9092` unless configured otherwise).
- The sandbox starts the container with the spec path as a command argument and reads back the
  mapped host/port of the kafka listener — that address is the bootstrap the producer uses and the
  value the `{{instance.host}}`/`{{instance.port}}` placeholders inject into the service env.
- Spec patching/config files can override parts of a spec without touching the original — not used
  by the sandbox (the spec path comes from `.sandbox.yml` as-is).
- JavaScript scripting (`on('kafka', ...)`) can customize behavior — deliberately unused: the
  sandbox drives data through the kafka protocol, not through mock-internal scripts.

---

## Two planes, one tool

- **Kafka data plane** (the wire-protocol listener): producers and consumers connect like to a
  real broker. The sandbox produces precondition messages here with `kafka-python`; messages the
  service itself produces accumulate in the mock.
- **HTTP side**: dashboard and health only (default HTTP port `8080`, health at `/health`) — it is
  not a data API. Readiness probing goes through the HTTP health endpoint; data operations go
  through the kafka protocol.

---

## Reset — container restart

All state is in-memory:

- A restart of the container empties everything — produced messages are gone, and the topology is
  re-created from the AsyncAPI spec on boot.
- This is exactly why the sandbox resets a kafka instance by restarting the container: after the
  restart the instance is in its pristine startup state, and the baseline journal replay
  re-establishes the author-declared preconditions on top.
- Services under test must tolerate the broker reconnecting (the accepted speed-over-fidelity
  trade-off of the reset strategy).
