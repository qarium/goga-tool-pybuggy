# Project rules

## Explicit failure-branch decisions

When a redesign silently changes product behavior, most notably an optional-component decline that ends in an error exit while leaving partially initialized state that the re-entry guard then refuses, the branch must be owned as a deliberate, documented design decision: recorded in the design's environment and edge-case sections, presented as a normal outcome in usage documentation, noted in migration notes when it diverges from the previous major version, and covered by a negative test variant; it must never be left implicit or softened into a warning that defers the breakage to a later, mysterious failure.

## Honest contract surface

Contract declarations and usage documentation must describe only what the engine actually consumes and enforces: drop declarations that can never execute, narrow signatures to live parameters, name the real enforcement point when the engine silently discards a declared value, and document the gap for flows that bypass the tooling entirely, so no reader is promised a delivery that never happens.

## Documentation–code consistency

Factual statements in design documents must match the code they describe: dependency lists must exclude modules the code never calls, exception-handling claims must reflect the actual catch tuples and exception inheritance, and module layouts must include every constant the code reads; a consistency fix must remain purely textual and never smuggle in a behavioral change.

## Pinned interaction scripts

Executable validation steps described in design documents must pin the exact scripted answer map for interactive flows: which prompts lack a default and require an explicit value, which confirmations default to declining, and which gates must be declined to keep the run offline and deterministic; a vague "accept the defaults" instruction is invalid because defaults silently depend on the environment.
