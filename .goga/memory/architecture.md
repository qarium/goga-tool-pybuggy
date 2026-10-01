# Project rules

## Grounded option presentation

Before asking the user to choose among design options, ground every option in how the host platform natively solves the analogous problem and in the project's current behavior. Map each option onto those idioms with its concrete consequences, and attach a recommendation. Never present options as abstract pros and cons alone.

## Structural invariants over deferred validation

Encode required-data constraints so they hold by construction in the declarative model rather than relying on after-the-fact validation that a soft failure elsewhere can render unenforceable. Use a mandatory declared first entry plus leniently parsed optional additions, where malformed input is skipped with a warning while valid input is kept.
