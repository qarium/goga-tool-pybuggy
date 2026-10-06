# Project rules

## Structural invariants over deferred validation

Encode data dependencies and required-data constraints so they hold by construction in the declarative model rather than relying on after-the-fact validation that a soft failure elsewhere can render unenforceable. Express dependencies purely through declaration order: within one service instance, accumulated operations apply in order (preset declarations first, then in-test operations, list order preserved), each write call targets exactly one table, and parent rows are declared before child rows. Anchor required data with a mandatory declared first entry plus leniently parsed optional additions, where malformed input is skipped with a warning while valid input is kept. The product owns deterministic application and constraint resolution, so constraints are never deferred, disabled, or manually sequenced.

## Acyclic cell graph with reference-driven type placement

The cell dependency graph is kept acyclic: integration flows only from consumer to provider and is never reversed. A type that must reference a type belonging to a consuming cell is relocated into that cell rather than permitting an upward import that would create a cycle or an unresolvable reference.

## Manifest import-reference symmetry

Cross-cell references and imports are held in strict bidirectional agreement: every type referenced in a signature or annotation has a corresponding import entry, and every imported type is actually referenced. One-sided inconsistencies — referenced-but-unimported types or imported-but-unreferenced types — are never shipped.

## Grounded option presentation

Before asking the user to choose among design options, ground every option in how the host platform natively solves the analogous problem and in the project's current behavior. Map each option onto those idioms with its concrete consequences, and attach a recommendation. Never present options as abstract pros and cons alone.
