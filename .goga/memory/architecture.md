# Project rules

## Structural invariants over deferred validation

Encode data dependencies and required-data constraints so they hold by construction in the declarative model rather than relying on after-the-fact validation that a soft failure elsewhere can render unenforceable. Express dependencies purely through declaration order: within one service instance, accumulated operations apply in order (preset declarations first, then in-test operations, list order preserved), each write call targets exactly one table, and parent rows are declared before child rows. Anchor required data with a mandatory declared first entry plus leniently parsed optional additions, where malformed input is skipped with a warning while valid input is kept. The product owns deterministic application and constraint resolution, so constraints are never deferred, disabled, or manually sequenced.

## Data-driven variation records

Knowledge that generalizes a capability across instances of the same kind lives in compile-time declarative records, exactly one per qualifying instance and keyed by the runtime-discovered instance identity. Behavior is derived wholesale from the record: no per-instance branching, no I/O inside the derivation, and heavy platform dependencies imported only at call time so the package imports standalone.

## Behavior-preserving evolution

When extending or generalizing capability that already ships and is pinned by an existing suite, shipped behavior stays effect-identical: existing assertions are kept unchanged, the green suite serves as the regression guard for the change, and only call sites adapt to the new shape. Related settings are grouped into one optional nested block described by a single shared configuration type rather than scattered flat fields, with field validity scoped by entry kind — a setting meaningful only on the primary entry is accepted there and rejected at load time everywhere else. New settings ride on the configuration models they parameterize instead of widening existing procedure signatures, so call sites are untouched, and defaults are chosen to reproduce prior behavior exactly, making adoption opt-in and non-breaking.

## Acyclic cell graph with reference-driven placement

The dependency graph over cells and units is kept acyclic: integration flows only from consumer to provider and is never reversed. A type that must reference a type belonging to a consuming cell is relocated into that cell rather than permitting an upward import that would create a cycle or an unresolvable reference. New functionality lands by extending existing responsibility zones, not by creating new cells; a genuinely new subsystem spanning several distinct concerns gets its own leaf unit with a single coherent responsibility that imports nothing from the rest of the project, and neighboring units extend by importing from the leaf instead of absorbing heterogeneous modules. Convention artifacts that are data by nature — pipeline definitions, skill documents, docs pages, tests — remain package data outside the cell graph, because a cell for data contradicts the package structure.

## Manifest declaration hygiene

Every declaration in a cell manifest stays resolvable and in strict bidirectional sync with the structure it describes. Cross-cell references and imports agree from both sides: every type referenced in a signature or annotation has a corresponding import entry, every imported type is actually referenced, and one-sided inconsistencies — referenced-but-unimported or imported-but-unreferenced types — are never shipped. Backticked terms reference only what the linter can resolve in the annotated scope — the annotated type's own signature parameters, usage keys, and type names — while properties of another type are referred to in plain words. A structural addition updates its dependent declarations, import entries, and count-bearing constraints in the same change rather than leaving them stale.

## Normative registration ordering

Registrations follow the normative table exactly and completely: independent chains anchor at built-in entries and stack in forward order; where the table prescribes a reversed order for one line, that order is preserved; every anchor names an entry registered earlier in the run or a built-in; registered names carry no tool prefix, leaving qualification to the platform; an unresolvable anchor logs a warning and never aborts; and a new registration takes its normative position within the established sequence rather than being appended or reordering existing entries.

## Uniform naming convention

One approved naming scheme governs every artifact family of a new line — artifact file names, skill directory prefixes, identity casing, config axis — and is held consistently across plans, skills, docs, and statuses. Prefixes are not mirrored from unrelated lines, and mixed or inconsistent prefixing is rejected.

## Self-sufficient generic documentation

Documentation for an already-generic mechanism does not grow per instance: when the configuration resolver is generic over arbitrary instance names in its axis, adding an instance requires no new usage examples and the practice document stays untouched.

## Bounded autonomy envelope

Automated approval covers exactly the execution window through the commit step and the build step that follows it. The acceptance stage is never auto-approved — it stays interactive and manually launched — and the autonomous contribution emits no directives for stage prompts, descriptions, or skills.

## No-op versus error propagation

A contribution hook is silent only for well-defined non-applicability: no record for the run's instance, or the feature axis disabled — contribute nothing, raise nothing. Any other error propagates and halts the command with a clean, attributable failure; errors are never suppressed to force the no-op branch, so the feature never disables itself silently.

## Single canonical declaration form

Each authorable concept keeps exactly one declaration form, the full structured mapping; union forms mixing terse string shortcuts with full mappings are rejected so documentation, validation, and the author error surface remain singular. Every consumer-facing YAML example presents that form in canonical block style — nested mappings on their own lines, one key per line, properly indented — and flow/JSON-like inline mappings never appear in material that authors or users read.

## Document-driven vocabulary alignment

The author-facing document is the source of truth for names and locations. When its vocabulary changes, internal symbols are renamed so name and semantics mirror the document's terms, and the rename is propagated along every existing dependency edge and verified consumer by consumer, leaving no mixed old/new vocabulary in the codebase. Author-facing files reference only the current canonical paths and keys and phrase guidance as verifying the exact current location; superseded paths or key names never appear as migration notes, and renamed-key diagnostics live solely in runtime loader errors.

## Deferred network I/O with idempotent fetch

Configuration loading performs only cheap structural validation of source references; cloning, content inspection, and other network operations are deferred to the point of use rather than performed at load, and transient artifacts are discarded after use, keeping document loading free of network I/O. Downloading an external resource into a local target folder always removes any pre-existing folder first, so a fetch is idempotent and yields exactly the fetched state: retrieved content never merges with leftovers from a previous download, and stale artifacts cannot survive into the new result.

## Actionable deadline failure

Any bounded wait fails with a typed, actionable error when its deadline expires; an expired deadline never surfaces as an indefinite hang.

## Grounded option presentation

Before asking the user to choose among design options, ground every option in how the host platform natively solves the analogous problem and in the project's current behavior. Map each option onto those idioms with its concrete consequences, and attach a recommendation. Never present options as abstract pros and cons alone.
