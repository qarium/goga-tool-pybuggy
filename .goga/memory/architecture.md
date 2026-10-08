# Project rules

## Structural invariants over deferred validation

Encode data dependencies and required-data constraints so they hold by construction in the declarative model rather than relying on after-the-fact validation that a soft failure elsewhere can render unenforceable. Express dependencies purely through declaration order: within one service instance, accumulated operations apply in order (preset declarations first, then in-test operations, list order preserved), each write call targets exactly one table, and parent rows are declared before child rows. Anchor required data with a mandatory declared first entry plus leniently parsed optional additions, where malformed input is skipped with a warning while valid input is kept. The product owns deterministic application and constraint resolution, so constraints are never deferred, disabled, or manually sequenced.

## Single canonical declaration form

Each authorable concept keeps exactly one declaration form, the full structured mapping; union forms mixing terse string shortcuts with full mappings are rejected so documentation, validation, and the author error surface remain singular. Every consumer-facing YAML example presents that form in canonical block style — nested mappings on their own lines, one key per line, properly indented — and flow/JSON-like inline mappings never appear in material that authors or users read.

## Document-driven vocabulary alignment

The author-facing document is the source of truth for names and locations. When its vocabulary changes, internal symbols are renamed so name and semantics mirror the document's terms, and the rename is propagated along every existing dependency edge and verified consumer by consumer, leaving no mixed old/new vocabulary in the codebase. Author-facing files reference only the current canonical paths and keys and phrase guidance as verifying the exact current location; superseded paths or key names never appear as migration notes, and renamed-key diagnostics live solely in runtime loader errors.

## Consolidated behavior-preserving configuration models

Related settings are grouped into one optional nested block described by a single shared configuration type rather than scattered flat fields, and field validity is scoped by entry kind: a setting meaningful only on the primary entry is accepted there and rejected at load time everywhere else. New settings ride on the configuration models they parameterize instead of widening existing procedure signatures, so call sites are untouched, and defaults are chosen to reproduce prior behavior exactly, making adoption opt-in and non-breaking.

## Actionable deadline failure

Any bounded wait fails with a typed, actionable error when its deadline expires; an expired deadline never surfaces as an indefinite hang.

## Acyclic cell graph with reference-driven type placement

The cell dependency graph is kept acyclic: integration flows only from consumer to provider and is never reversed. A type that must reference a type belonging to a consuming cell is relocated into that cell rather than permitting an upward import that would create a cycle or an unresolvable reference.

## Manifest import-reference symmetry

Cross-cell references and imports are held in strict bidirectional agreement: every type referenced in a signature or annotation has a corresponding import entry, and every imported type is actually referenced. One-sided inconsistencies — referenced-but-unimported types or imported-but-unreferenced types — are never shipped.

## Grounded option presentation

Before asking the user to choose among design options, ground every option in how the host platform natively solves the analogous problem and in the project's current behavior. Map each option onto those idioms with its concrete consequences, and attach a recommendation. Never present options as abstract pros and cons alone.
