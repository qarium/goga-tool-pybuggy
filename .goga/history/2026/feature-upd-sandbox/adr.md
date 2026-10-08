# Sandbox refinement: config relocation, inline Kafka topics, configurable readiness, naming swap

Status: accepted (2026-10-08)

The second iteration over the sandbox capability (see `.goga/history/2026/feature-sandbox/adr.md`,
accepted 2026-10-06) refines four points settled in discovery: the configuration document moves
under the pybuggy tools home, Kafka topics become an inline declaration with the AsyncAPI document
generated in memory, readiness probes become configurable per target, and the two top-level keys
swap names. A fifth candidate — DB migrations via goose — was rejected during discovery.

## Settled decisions

- **Document relocation.** `.sandbox.yml` at the consumer repository root moves to
  `.goga/tools/pybuggy/sandbox.yml` — one home for all pybuggy configuration next to `config.yml`.
  The filename loses its leading dot. Resolution stays cwd-only with no upward search, exactly as
  today. Presence-based activation is unchanged: no document, no sandbox.
- **Inline Kafka topics.** Topics are declared only inline, on the Kafka entry inside `services` —
  the topology is a property of the mock service, like `image` and `kind`. The `data.kafka`
  section is removed entirely; the startup data order becomes vault → http → postgres. The engine
  generates the AsyncAPI document in memory and feeds the existing consumption pipeline (patch
  servers → transfer into the container → Mokapi); the document is internal mechanics and is never
  exposed to authors. A Kafka entry without topics fails fast — the mock would open no listener.
  `partitions` is optional; omitted means the tool default (1).
- **Configurable readiness probes.** Kubernetes-probe-like, declared per target in the document:
  `timeout` (default 30.0), `interval` (default 0.5), and `path`. No `initialDelay`, no
  `failureThreshold`, no document-level global defaults block — per-target overrides only. The
  probe endpoints of the Kafka/vault/http mocks (Mokapi `/health`, vault health, WireMock admin)
  are part of the tool contract and stay fixed; only `timeout`/`interval` apply to them. `path`
  stays configurable only where an HTTP check with a path already exists — the health path of the
  service under test. Postgres keeps testcontainers module readiness wrapped in the configurable
  deadline. An expired deadline is an actionable error; nothing ever hangs. All current behavior
  is the default.
- **Naming swap.** The top-level `service:` key (service under test) becomes `instance:`; the
  top-level `instances:` map (dependency mocks) becomes `services:`. Vocabulary rationale: the
  mocks are infrastructure services (docker-compose vocabulary); the thing under test is the single
  running instance of the author's image. Unchanged: the `data:` key, section names, the
  `{{name.host}}/{{name.port}}` placeholder syntax, and the Python API (`sandbox.postgresql(...)`).
- **Compatibility.** Hard break, no legacy aliases, no deprecation period: the old location and
  the old keys stop working with clear errors ("document not found at the new path" / "key
  renamed"). The feature is two days old with few consumers.

## Considered options

- **DB migrations via goose** (originally voiced as "goos"): rejected by the user during discovery.
  Schema setup stays idempotent raw SQL under `data.postgres`, replayed from the baseline journal
  after every per-test reset.
- **Keeping the external AsyncAPI spec path** as an alternative to inline topics: rejected — inline
  is the single declaration way; the section disappears rather than growing a second form.
- **Literal `tools/pybuggy/` anchor**: rejected in favor of `.goga/tools/pybuggy/` — the existing
  pybuggy tool configuration already lives there.
- **`initialDelay`/`failureThreshold` and a global defaults block** in probes: rejected as YAGNI;
  the stated pain was timeout/interval/path only.

## Consequences

- One breaking jump for existing consumer documents: location move, key renames, and the
  Kafka-spec-to-inline conversion land together with actionable error messages.
- The generated AsyncAPI document must satisfy the same consumption contract Mokapi already
  consumes through the patched-spec pipeline; the AsyncAPI version choice is an implementation
  detail, not a contract.
- Documentation updates ride along: `docs/sandbox.md`, `docs/configuration.md`, and the capability
  usage files.
- Exact YAML field names, Python signatures, and cell changes are design-stage concerns outside
  this record.
