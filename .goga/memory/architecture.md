# Project rules

## Structural invariants over deferred validation

Encode data dependencies and required-data constraints so they hold by construction in the declarative model rather than relying on after-the-fact validation that a soft failure elsewhere can render unenforceable. Express dependencies purely through declaration order: within one service instance, accumulated operations apply in order (preset declarations first, then in-test operations, list order preserved), each write call targets exactly one table, and parent rows are declared before child rows. Anchor required data with a mandatory declared first entry plus leniently parsed optional additions, where malformed input is skipped with a warning while valid input is kept. Where document keys are kind-specific, they are validated when the document is loaded and invalid combinations are rejected early with errors that name the offending entry and its location, never deferred to anonymous later failures. The product owns deterministic application and constraint resolution, so constraints are never deferred, disabled, or manually sequenced.

## Acyclic cell graph with reference-driven placement

The dependency graph over cells and units is kept acyclic: integration flows only from consumer to provider and is never reversed. A type that must reference a type belonging to a consuming cell is relocated into that cell rather than permitting an upward import that would create a cycle or an unresolvable reference. New functionality lands by extending existing responsibility zones, not by creating new cells: a new capability kind is added as a slice through the existing responsibility zones rather than as a new parallel structure, keeping the dependency graph stable and the cross-boundary surface delta minimal. A genuinely new subsystem spanning several distinct concerns gets its own leaf unit with a single coherent responsibility that imports nothing from the rest of the project, and neighboring units extend by importing from the leaf instead of absorbing heterogeneous modules. Third-party clients and container modules are wired only inside the layer that operates them; consumer layers see only views and facades and gain no new external usages. Convention artifacts that are data by nature — pipeline definitions, skill documents, docs pages, tests — remain package data outside the cell graph, because a cell for data contradicts the package structure.

## Single canonical declaration form

Each authorable concept keeps exactly one declaration form, the full structured mapping; union forms mixing terse string shortcuts with full mappings are rejected so documentation, validation, and the author error surface remain singular. New declaration shapes and payload annotations reuse the document's established plain-data conventions instead of introducing per-feature type forms or nested variants. Every consumer-facing YAML example presents the canonical form in block style — nested mappings on their own lines, one key per line, properly indented — and flow/JSON-like inline mappings never appear in material that authors or users read.

## Deterministic registration and composition ordering

Orderings that arise from many contributors are fixed and declared, not emergent. Registrations follow the normative table exactly and completely: independent chains anchor at built-in entries and stack in forward order; where the table prescribes a reversed order for one line, that order is preserved; every anchor names an entry registered earlier in the run or a built-in; registered names carry no tool prefix, leaving qualification to the platform; an unresolvable anchor logs a warning and never aborts; and a new registration takes its normative position within the established sequence rather than being appended or reordering existing entries. Sections contributed by multiple kinds are likewise applied in a fixed, declared order, with a new kind's section appended after the existing ones so ordering stays defined as the document grows.

## Deterministic replay and scoped reset

Declared payloads are never coerced or normalized on the declaration or apply path; serialization to the wire form happens only at execution, so a replay stays byte-equal with the original apply. Per-test reset builds on this determinism while staying scoped: it wipes only the declared logical unit and replays the baseline, without restarting the backing service or breaking live connections to it.

## Actionable deadline failure

Any bounded wait fails with a typed, actionable error when its deadline expires; an expired deadline never surfaces as an indefinite hang. Inherited default wait behavior is replaced with an explicit readiness probe bounded by the declared timeout and interval, and an expired deadline or wrong credential surfaces as an error naming the service and the waited check.

## Single-homed documentation

Consumer guidance lives at consumer-facing surfaces, exactly once. Documentation for an already-generic mechanism does not grow per instance: when the configuration resolver is generic over arbitrary instance names in its axis, adding an instance requires no new usage examples and the practice document stays untouched. Pre-existing practice documents are linked as-is, and internal layers get no usage files that would duplicate that content.

## Aligned dependency floors

When one library is required through two different routes, its version floors are pinned to a single consistent resolution so the two requirements cannot drift and resolve differently.

## Settled decisions, grounded options

Behavioral choices already fixed in an authoritative decision record are resolved against that record instead of being re-opened as questions; only residual low-level detailing points are carried forward. For decisions that are genuinely open, ground every option in how the host platform natively solves the analogous problem and in the project's current behavior, map each option onto those idioms with its concrete consequences, and attach a recommendation. Never present options as abstract pros and cons alone.

## Behavior-preserving evolution

When extending or generalizing capability that already ships and is pinned by an existing suite, shipped behavior stays effect-identical: existing assertions are kept unchanged, the green suite serves as the regression guard for the change, and only call sites adapt to the new shape. Related settings are grouped into one optional nested block described by a single shared configuration type rather than scattered flat fields, with field validity scoped by entry kind — a setting meaningful only on the primary entry is accepted there and rejected at load time everywhere else. New settings ride on the configuration models they parameterize instead of widening existing procedure signatures, so call sites are untouched, and defaults are chosen to reproduce prior behavior exactly, making adoption opt-in and non-breaking.

## Data-driven variation records

Knowledge that generalizes a capability across instances of the same kind lives in compile-time declarative records, exactly one per qualifying instance and keyed by the runtime-discovered instance identity. Behavior is derived wholesale from the record: no per-instance branching, no I/O inside the derivation, and heavy platform dependencies imported only at call time so the package imports standalone.

## Manifest declaration hygiene

Every declaration in a cell manifest stays resolvable and in strict bidirectional sync with the structure it describes. Cross-cell references and imports agree from both sides: every type referenced in a signature or annotation has a corresponding import entry, every imported type is actually referenced, and one-sided inconsistencies — referenced-but-unimported or imported-but-unreferenced types — are never shipped. Backticked terms reference only what the linter can resolve in the annotated scope — the annotated type's own signature parameters, usage keys, and type names — while properties of another type are referred to in plain words. A structural addition updates its dependent declarations, import entries, and count-bearing constraints in the same change rather than leaving them stale.

## Document-driven vocabulary alignment

The author-facing document is the source of truth for names and locations. When its vocabulary changes, internal symbols are renamed so name and semantics mirror the document's terms, and the rename is propagated along every existing dependency edge and verified consumer by consumer, leaving no mixed old/new vocabulary in the codebase. Author-facing files reference only the current canonical paths and keys and phrase guidance as verifying the exact current location; superseded paths or key names never appear as migration notes, and renamed-key diagnostics live solely in runtime loader errors.

## No-op versus error propagation

A contribution hook is silent only for well-defined non-applicability: no record for the run's instance, or the feature axis disabled — contribute nothing, raise nothing. Any other error propagates and halts the command with a clean, attributable failure; errors are never suppressed to force the no-op branch, so the feature never disables itself silently.

## Bounded autonomy envelope

Automated approval covers exactly the execution window through the commit step and the build step that follows it. The acceptance stage is never auto-approved — it stays interactive and manually launched — and the autonomous contribution emits no directives for stage prompts, descriptions, or skills.
