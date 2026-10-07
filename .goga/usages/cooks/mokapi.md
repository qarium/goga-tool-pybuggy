# mokapi — the sandbox kafka mock

## Domain

`mokapi` (image `mokapi/mokapi`, Go, MIT — github.com/marle3003/mokapi) is the kafka dependency
mock of the pybuggy sandbox capability. It is a spec-driven, local-first mock tool: the kafka
topology (topics and their partitions) is described by an **AsyncAPI** document, and the data plane
is a real kafka wire-protocol listener that ordinary kafka clients (kafka-python producer) connect
to directly.

Product pin: `mokapi/mokapi:0.52.0`. kafka clients negotiate ApiVersionsRequest v4
(kafka-python >= 3); mokapi releases before ~0.5x answer `kafka: unsupported version 4` and the
bootstrap hangs — do not downgrade the pin without re-checking client compatibility.

---

## The spec's server entry is load-bearing

`servers.<name>.host` in the AsyncAPI document decides **both** where mokapi binds its kafka
listener and **what address it advertises to clients** in metadata responses:

- a kafka client bootstraps on the address it was given, then follows the broker address of the
  metadata answer — the advertised address must be reachable from the client, or every produce
  hangs;
- the listener port is parsed from the same `host:port` string — the published port mapping must
  target exactly that in-container port.

This is why the sandbox never mounts the author's document as-is: it reserves a free host port,
rewrites every kafka-protocol `servers.*.host` of a spec copy to the client-reachable
`{docker-host}:{reserved-port}`, transfers the copy into the container through the docker API
(no bind mount — host paths resolve on the daemon's filesystem and break when the engine itself
runs inside a container), and publishes the reserved port on both sides. Bootstrap, advertised
metadata and the `{{instance.host}}`/`{{instance.port}}` service-env placeholders then name one
and the same address.

```bash
# the equivalent manual run — spec advertising exactly the reachable address, same port both sides
docker run --rm -p 8080:8080 -p 9092:9092 \
  -v $(pwd):/data mokapi/mokapi /data/asyncapi.yaml   # spec server host: localhost:9092
```

- The AsyncAPI document defines the mocked topics (kafka bindings); without a kafka server entry
  mokapi opens no kafka listener at all — the sandbox rejects a spec-less kafka instance at start.
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
  re-created from the spec on boot.
- This is exactly why the sandbox resets a kafka instance by restarting the container: after the
  restart the instance is in its pristine startup state, and the baseline journal replay
  re-establishes the author-declared preconditions on top.
- The fixed port binding and the transferred spec survive the restart — the mapped address stays
  valid across resets (a dynamically assigned published port would be re-rolled by the restart).
- Services under test must tolerate the broker reconnecting (the accepted speed-over-fidelity
  trade-off of the reset strategy).
