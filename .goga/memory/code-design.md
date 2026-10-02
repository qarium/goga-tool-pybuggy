# Project rules

## Confirm-gated imperative interaction flows

Fixed fields stay as declarative survey records, while any confirm-gated, branched, or repeated prompting — inexpressible in the engine's flat, one-level question model — is implemented as imperative code invoked from the amendment-time participation hook, with its results fed into the config payload; encoding such flows as static question trees is rejected because they flatten into plain sequential records. When such a flow collects repeating multi-field records, each record is gated behind a confirm prompt, then every field is asked individually in the same order as the primary record (required fields re-asked until valid, trailing optional fields skippable), looping back to the gate until declined; compressing repeated records into a single hand-typed delimited line is rejected.

## Exclusive output-slot ownership

Each generated output slot has exactly one writer: when the generic engine writer would fill a slot first and thereby defeat a component's skip-if-exists gate, the session declares that slot skipped so the engine never writes it and the owning component's packaged asset lands instead; relying on the gate to win a double-writer race is rejected.

## Post-hoc comment restoration for generated configs

Config serialized through a data-only buffer cannot carry documentation comments, so commented examples for absent or optional members are re-inserted after writing by the owning side: idempotently via marker detection, in canonical key order anchored before the next active key, never touching active entries, and a no-op when the file is absent; emitting plain serialized data and dropping the examples is rejected.

## Explicit scope governance

Approval covers only what was clearly confirmed: single-item emphasis in an approval reply is treated as a mandate for that item alone and resolved with one short, option-scoped follow-up question before implementation; once scope is settled, discovered drift outside it is left untouched and flagged as a recommended follow-up in the final report rather than silently absorbed into the change.

## Explicit failure-branch decisions

When a redesign silently changes product behavior, most notably an optional-component decline that ends in an error exit while leaving partially initialized state that the re-entry guard then refuses, the branch must be owned as a deliberate, documented design decision: recorded in the design's environment and edge-case sections, presented as a normal outcome in usage documentation, noted in migration notes when it diverges from the previous major version, and covered by a negative test variant; it must never be left implicit or softened into a warning that defers the breakage to a later, mysterious failure.

## Honest contract surface

Contract declarations and usage documentation must describe only what the engine actually consumes and enforces: drop declarations that can never execute, narrow signatures to live parameters, name the real enforcement point when the engine silently discards a declared value, and document the gap for flows that bypass the tooling entirely, so no reader is promised a delivery that never happens.

## Documentation–code consistency

Factual statements in design documents must match the code they describe: dependency lists must exclude modules the code never calls, exception-handling claims must reflect the actual catch tuples and exception inheritance, and module layouts must include every constant the code reads; a consistency fix must remain purely textual and never smuggle in a behavioral change.

## Pinned interaction scripts

Executable validation steps described in design documents must pin the exact scripted answer map for interactive flows: which prompts lack a default and require an explicit value, which confirmations default to declining, and which gates must be declined to keep the run offline and deterministic; a vague "accept the defaults" instruction is invalid because defaults silently depend on the environment.
