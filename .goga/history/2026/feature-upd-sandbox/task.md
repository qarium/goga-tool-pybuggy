# Sandbox refinement: config relocation, inline Kafka topics, configurable readiness, naming swap

## Current State

The sandbox capability shipped two days ago (`.goga/history/2026/feature-sandbox/adr.md`, accepted
2026-10-06) and works as follows:

- The configuration document is `.sandbox.yml` at the root of the consumer repository, resolved
  cwd-only. Presence activates the sandbox; absence keeps it fully inert.
- Top-level keys: `service:` (the service under test — image, env, port, optional health path),
  `instances:` (named dependency mock entries — kind postgresql/kafka/vault/http, optional image
  override), `data:` (startup data — vault secrets, http mappings, kafka spec, postgres init).
- Kafka topology comes from an external AsyncAPI spec file whose path is declared in `data.kafka`;
  the engine patches the document servers to the mapped address, transfers it into the Mokapi
  container, and topics come from that spec.
- Readiness is fixed: testcontainers default waits for the mock probe endpoints (Mokapi `/health`,
  vault health, WireMock admin) and the postgres module readiness; the service under test waits
  for its port or the optional health path. Timeout and interval are not configurable.
- Four cells own the capability: `goga_tool_pybuggy/sandbox/config` (document models and the
  fail-fast loader), `goga_tool_pybuggy/sandbox/engines` (per-kind instance engines),
  `goga_tool_pybuggy/sandbox` (session runtime, service container, pytest activation),
  `goga_tool_pybuggy/sandbox/data` (instance views, lazy batch, presets). The plugin cell consumes
  only the Python API.
- Author-facing docs live in `docs/sandbox.md` and `docs/configuration.md`; cell-level usage files:
  `sandbox-file.md`, `sandbox-session.md`, `data-operations.md`.

## Description

Second iteration over the sandbox capability per `.goga/history/2026/feature-upd-sandbox/adr.md`
(accepted 2026-10-08). Four refinements land together as one hard break — no legacy aliases, no
deprecation period:

1. **Document relocation.** The configuration document moves to
   `.goga/tools/pybuggy/sandbox.yml` — one home for all pybuggy configuration next to
   `config.yml`; the filename loses its leading dot. Resolution stays cwd-only with no upward
   search. Presence-based activation is unchanged: no document, no sandbox.
2. **Inline Kafka topics.** Topics are declared inline on the kafka entry inside the services map —
   the topology is a property of the mock service, like image and kind. The `data.kafka` section
   is removed entirely; the startup data order becomes vault → http → postgres. The engine
   generates the AsyncAPI document in memory and feeds the existing consumption pipeline (patch
   servers → transfer into the container → Mokapi); the document is internal mechanics and is
   never exposed to authors. A kafka entry without topics fails fast — the mock would open no
   listener. `partitions` is optional; omitted means the tool default (1).
3. **Configurable readiness probes.** Kubernetes-probe-like, declared per target in the document:
   `timeout` (default 30.0) and `interval` (default 0.5), plus `path`. No `initialDelay`, no
   `failureThreshold`, no document-level global defaults block — per-target overrides only. The
   probe endpoints of the kafka/vault/http mocks are part of the tool contract and stay fixed;
   only `timeout`/`interval` apply to them. `path` stays configurable only where an HTTP check
   with a path already exists — the health path of the service under test. Postgres keeps
   testcontainers module readiness wrapped in the configurable deadline. An expired deadline is an
   actionable error; nothing ever hangs. All current behavior is the default.
4. **Naming swap.** The top-level `service:` key becomes `instance:`; the top-level `instances:`
   map becomes `services:` (the mocks are infrastructure services in docker-compose vocabulary;
   the thing under test is the single running instance of the author's image). Unchanged: the
   `data:` key, section names, the `{{name.host}}/{{name.port}}` placeholder syntax, and the
   Python API (`sandbox.postgresql(...)` and the rest of the instance views, the presets
   decorator).

Compatibility per grooming: a stale document at the old root location is fully silent — no error,
no activation; the only compatibility errors are renamed-key errors inside a document found at the
new path.

## Scope

**In scope:**

- `goga_tool_pybuggy/sandbox/config` — document models for the new path, the renamed top-level
  keys, inline kafka topics with optional partitions, per-target probe fields, the removed kafka
  data section, and the fail-fast loader with renamed-key errors; the `sandbox-file.md` usage file
  rewritten to the new document shape.
- `goga_tool_pybuggy/sandbox/engines` — kafka topology consumed from the inline declaration with
  the AsyncAPI document generated in memory through the existing patched-spec pipeline; readiness
  waiting parameterized by the per-target `timeout`/`interval` across all four engines; the
  postgres module readiness wrapped in the configurable deadline.
- `goga_tool_pybuggy/sandbox` — startup sequence with the vault → http → postgres data order, the
  service container readiness honoring the per-target probe settings, activation unchanged in
  behavior (presence gate, inertness); the `sandbox-session.md` usage file updated.
- `goga_tool_pybuggy/sandbox/data` — annotation-level updates where docs reference the AsyncAPI
  spec (produce targets the instance's declared topics); the `data-operations.md` usage file
  updated.
- Tests of all four cells updated and extended for the new document contract, plus the plugin
  arming tests (`tests/plugin/test_install.py`) that exercise activation through the old document
  path.
- `docs/sandbox.md` and `docs/configuration.md` updated to the new path, keys, inline topics, and
  probe settings, plus a sweep of every remaining author-facing reference to the old path
  (`README.md`, `docs/getting-started.md`, `docs/index.md`, `docs/pipelines/api-fix.md`,
  `docs/plugin/index.md`, `mkdocs.yml`).
- `goga_tool_pybuggy/commands/init` — one-string update of the `sandbox-file` authoring hint to
  the new document path.
- Plugin cell doc-level touch-ups — the `enable.md` usage file, the fail-fast error message text,
  and the install docstring updated to the new document path; no signature or import changes.
- Two-line refresh of hand-authored cooks practices: `cooks/wiremock.md` (the new document name)
  and `cooks/testcontainers.md` (the generated AsyncAPI document instead of the author-declared
  spec path).

**Out of scope:**

- DB migrations via goose — rejected during discovery; schema setup stays idempotent raw SQL under
  `data.postgres`.
- The external AsyncAPI spec path form — the section disappears rather than growing a second
  declaration form.
- A global probe defaults block and `initialDelay`/`failureThreshold` — rejected as YAGNI.
- Any change to the Python API, the placeholder syntax, or the `data:` key and its remaining
  sections.
- The grpc dependency kind (still "not supported yet").
- Structural changes to the plugin cell — its imports (activation entry points, the sandbox type,
  the config type) keep their names.

## Acceptance Criteria

- The sandbox activates only from `.goga/tools/pybuggy/sandbox.yml` resolved cwd-only; an absent
  document keeps everything fully inert; a stale `.sandbox.yml` at the repository root produces no
  error and no activation.
- A document at the new path using the old top-level keys fails validation with an actionable
  renamed-key error naming the offending key; nothing starts for an invalid document.
- Kafka topology is declared inline on the kafka service entry; `partitions` defaults to 1 when
  omitted; a kafka entry without topics fails fast before any container starts.
- Declaring kafka startup data fails — the section no longer exists; the startup data order is
  vault → http → postgres.
- The AsyncAPI document is generated in memory and consumed by the existing pipeline; no spec file
  is read or written anywhere in the consumer repository, and no generated document is exposed to
  authors.
- Readiness honors per-target `timeout` (default 30.0) and `interval` (default 0.5); the service
  under test accepts a configurable health `path`; mock probe endpoints stay fixed; an expired
  deadline surfaces an actionable error rather than hanging.
- With no probe overrides declared, startup behavior is identical to the current one.
- The Python API is unchanged: instance views, the presets decorator, and the
  `{{name.host}}/{{name.port}}` placeholders work as before; the existing consumer-facing env
  rendering semantics are untouched.
- `docs/sandbox.md`, `docs/configuration.md`, and the four cell usage files (including
  `plugin/.usages/enable.md`) describe the new document exclusively, with no references to the old
  path, the old keys, or the kafka spec file; no author-facing file in the repository references
  the old path.
- The full test suite passes and covers: new-path resolution and inertness, renamed-key errors,
  inline topic validation (missing topics, default partitions), probe defaults and overrides, the
  vault → http → postgres order, and deadline expiry.

## Stack

- **Frameworks:** pytest (test runtime), pydantic (configuration models, kw_only dataclasses
  per conventions).
- **Libraries:** ruamel-yaml (document parsing), testcontainers (container lifecycle and readiness
  waiting), requests (HTTP probing and data planes), jinja2 (env rendering), pluginator (pytest
  hook registration), psycopg (postgres data plane), kafka-python (producing).
- **Infrastructure:** Docker-compatible container runtime; mocks — Mokapi (kafka), Vault dev mode,
  WireMock (http); real postgres via the testcontainers module.

No new external dependencies. The in-memory AsyncAPI generation uses plain serializable data
structures — no asyncapi library.

## External Dependencies

| Component     | Usage file                            | Status   |
|---------------|---------------------------------------|----------|
| ruamel-yaml   | `.goga/usages/cooks/ruamel-yaml.md`   | existing |
| testcontainers | `.goga/usages/cooks/testcontainers.md` | existing |
| requests      | `.goga/usages/cooks/requests.md`      | existing |
| jinja2        | `.goga/usages/cooks/jinja2.md`        | existing |
| pluginator    | `.goga/usages/cooks/pluginator.md`    | existing |
| mokapi        | `.goga/usages/cooks/mokapi.md`        | existing |
| vault-dev     | `.goga/usages/cooks/vault-dev.md`     | existing |
| wiremock      | `.goga/usages/cooks/wiremock.md`      | existing |
| psycopg       | `.goga/usages/cooks/psycopg.md`       | existing |
| kafka-python  | `.goga/usages/cooks/kafka-python.md`  | existing |

Synced usage files are managed by `goga usages sync` — reference them read-only, never create or update them in the task.

## Risks and Constraints

- One breaking jump for existing consumer documents: relocation is silent by decision (no
  migration error for the old path), so the docs must carry a clear migration note — a consumer
  with a stale document sees tests fail on a missing sandbox rather than a pointer.
- The generated AsyncAPI document must satisfy the same consumption contract Mokapi already
  consumes through the patched-spec pipeline; the AsyncAPI version choice is an implementation
  detail, not a contract.
- The readiness rework touches every engine's start path; defaults must reproduce the current
  behavior exactly — regression risk concentrates there.
- Python 3.10+ compatibility and the project conventions (pydantic kw_only, relative imports,
  Google-style docstrings, structured logging) apply throughout.
- Exact YAML field names below the settled ones (the probe block shape, the topics entry shape)
  and the internal Python signatures are design-stage concerns.

## Scope Estimate

Single task, no decomposition. The four refinements form one cohesive hard break: the key rename
ripples through config → engines → runtime → docs, and splitting would leave the tree
inconsistent between subtasks. Scale: four sandbox cells (~25 source files plus tests, including
the plugin arming tests), two primary documents plus a sweep of six more author-facing
references, four cell usage files, two cooks lines, one init hint string.

## Existing Architecture

- `goga_tool_pybuggy/sandbox/config` — owns the document contract: the root model (service entry,
  named instances, startup data), the per-kind instance model, the loader. Every rename, the
  inline topics, and the probe fields land here first; downstream cells consume only validated
  models.
- `goga_tool_pybuggy/sandbox/engines` — consumes the instance declaration (name, kind, image
  override) via `build_engine`; the kafka engine currently consumes the startup spec operation at
  container build and switches to the inline topology; every engine's readiness wait becomes
  parameterized.
- `goga_tool_pybuggy/sandbox` — orchestrates the ordered startup from the startup data sections
  and owns the service container readiness; the data order change and the service probe settings
  land here.
- `goga_tool_pybuggy/sandbox/data` — test-facing views and presets; only documentation-level
  references to the kafka spec change.
- `goga_tool_pybuggy/plugin` — imports the activation entry points, the sandbox type, and the
  config type; names are stable, no structural change expected.
- `goga_tool_pybuggy/commands/init` — point-affected: the `PYBUGGY_ANNOTATIONS` authoring hint for
  the `sandbox-file` usage names the document by its old path; imports and structure unchanged.

## Notes

- Grooming decision (user, this session): the old document location is fully silent — the ADR's
  quoted "document not found at the new path" error does not fire for a stale old-location file;
  absence at the new path keeps the sandbox inert, and the only compatibility errors are
  renamed-key errors inside a document at the new path.
- The rejection of goose migrations and of the external AsyncAPI spec path is recorded in the ADR;
  do not reintroduce them.
- Code examples are excluded from this task by stage constraints.
- The cooks files touched by this task are hand-authored practices, not synced copies — updating
  them here does not collide with `goga usages sync`.
