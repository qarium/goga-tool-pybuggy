# Project rules

## Phase-matched semantic validation

Each semantic check (a name that must resolve against live state) runs in the lifecycle phase where its inputs actually exist: statically decidable facts are verified at definition/registration time, context-dependent facts at the moment the context becomes live. Contracts never assign a check to a phase lacking its inputs, which keeps components from reaching for state they cannot access without creating dependency cycles.

## Full-grammar validation before side effects

The complete accepted syntax of declarative values is enforced at load time — not a subset of it — with diagnostics naming the offending key, value, and location, so malformed input aborts the run before the first external side effect (such as starting a service). Strict runtime checks remain only as defense in depth, never as the primary guard.

## Load-time reference resolution

Relative references in a configuration document are resolved exactly once, at load time, against the document's own directory — a purely lexical operation that reads nothing beyond the named document — and only fully resolved values travel downstream. Consumers never re-resolve and never depend on the process working directory, so behavior is independent of where the process is started.

## Honest and normatively complete specifications

Contract declarations, usage documentation, and specifications describe only what the engine actually consumes and enforces: declarations that can never execute are dropped, signatures are narrowed to live parameters, the real enforcement point is named when the engine silently discards a declared value, and flows that bypass the tooling entirely document the gap, so no reader is promised a delivery that never happens. Fixed per-category sets, deviations from uniform payload or behavior rules, and author-facing constraints implied by runtime mechanics (initialization that re-executes after every reset must be written idempotently) are recorded as explicit rules and exceptions in the specification itself — never as uniform claims contradicted in practice, undocumented exceptions, or implications buried in a single example.

## Authoritative signatures over schematic forms

Declared signatures and construction conventions bind every piece of code, tests included: objects are built exactly per the defined surface, constraints are honored, and fields that are not constructor parameters are assigned after construction rather than passed in. Pseudocode and scenario shorthand in design documents are schematic and never override the declared surface.

## Exclusive ownership of registration and output slots

Every shared namespace has exactly one owner, established before anything is written: framework markers and hooks are registered in a lifecycle phase that both precedes their first use and cannot be overwritten by other parties injecting hooks into the same namespace, with the injection order of those parties established before the phase is chosen. Likewise, each generated output slot has exactly one writer — when the generic engine writer would fill a slot first and thereby defeat a component's skip-if-exists gate, the session declares that slot skipped so the engine never writes it and the owning component's packaged asset lands instead. Relying on a gate to win a double-writer race, or on registration surviving a clobber, is rejected.

## Documentation grounded in code and observed behavior

Factual statements in design documents must match the code they describe: dependency lists must exclude modules the code never calls, exception-handling claims must reflect the actual catch tuples and exception inheritance, and module layouts must include every constant the code reads; a consistency fix must remain purely textual and never smuggle in a behavioral change. Measurable statements in a design and its tests — counts, uniqueness, enumerations — are taken from the observed behavior of the real mechanism rather than from assumption, so an implementer verifying them never meets a false discrepancy. Whenever a cell's behavior changes, three surfaces move in lockstep: the cell manifest, the cell-level usage files, and the public docs. Because stale fragments of old behavior hide in unexpected documents, a repository-wide text search for strings naming the old behavior is mandatory afterward; reviewing only the touched files is insufficient.

## Real-environment coverage for infrastructure adapters

An adapter that manages external services carries at least one integration test against a real environment (gated on its availability), exercising the full lifecycle — startup, readiness by port and by health endpoint, liveness, log retrieval, idempotent shutdown — in addition to fake-based unit paths.

## Explicit scope governance

Approval covers only what was clearly confirmed and explicitly approved: single-item emphasis in an approval reply is treated as a mandate for that item alone and resolved with one short, option-scoped follow-up question before implementation. Once the scope is approved, remediation is complete and single-pass: when every review finding is fixable within the design artifact itself and no governing contract is violated, all findings — including minor test-gap findings — are applied in one pass, the affected chains are then re-verified against the live stack, nothing is deferred or recorded as skipped, and the contracts stay unchanged; edits remain confined to the explicitly approved minimal set of spec-level value edits, leaving keys, annotations, signatures, footers, and runtime code untouched, with confirmation through the project's standard validation gates plus the full regression suite rather than by widening the change. When a proposed remedy is rejected as too aggressive, the rework removes only the confirmed defect and preserves the legitimate interactions entangled with it — collapsing a flawed prompt into total silent automation with zero remaining questions is over-correction, not a fix. Once scope is settled, discovered drift outside it is left untouched and flagged as a recommended follow-up in the final report rather than silently absorbed into the change.

## Confirm-gated imperative interaction flows

Within the project's init command, artifacts that are structural invariants of the bootstrap are never surfaced as yes/no gates, since declining could only guarantee a later failure; the flow asks only for values that are genuinely configurable — such as the base image version and the build image name — and the artifact is always produced from those answers. Scope-wide confirmations, such as the autonomy flag, are asked only after the specification survey has fully completed, meaning after the first entry plus the entire "add another entry?" cycle; asking them inside the cycle because of declaration order is the defect being corrected, and the resulting configuration key and its contract stay unchanged. Fixed fields stay as declarative survey records, while any confirm-gated, branched, or repeated prompting — inexpressible in the engine's flat, one-level question model — is implemented as imperative code invoked from the amendment-time participation hook, with its results fed into the config payload; encoding such flows as static question trees is rejected because they flatten into plain sequential records. When such a flow collects repeating multi-field records, each record is gated behind a confirm prompt, then every field is asked individually in the same order as the primary record (required fields re-asked until valid, trailing optional fields skippable), looping back to the gate until declined; compressing repeated records into a single hand-typed delimited line is rejected.

## Explicit failure-branch decisions

When a redesign silently changes product behavior, most notably an optional-component decline that ends in an error exit while leaving partially initialized state that the re-entry guard then refuses, the branch must be owned as a deliberate, documented design decision: recorded in the design's environment and edge-case sections, presented as a normal outcome in usage documentation, noted in migration notes when it diverges from the previous major version, and covered by a negative test variant; it must never be left implicit or softened into a warning that defers the breakage to a later, mysterious failure.

## Pinned interaction scripts

Executable validation steps described in design documents must pin the exact scripted answer map for interactive flows: which prompts lack a default and require an explicit value, which confirmations default to declining, and which gates must be declined to keep the run offline and deterministic; a vague "accept the defaults" instruction is invalid because defaults silently depend on the environment.

## Implicit tool registration

The project's own runtime tool is always recorded in the generated configuration no matter how the optional-tools question is answered; that question exists solely for adding other tools, so manually typed duplicates of the implicit entry are overridden while user-entered additional tools are preserved.

## Post-hoc comment restoration for generated configs

Config serialized through a data-only buffer cannot carry documentation comments, so commented examples for absent or optional members are re-inserted after writing by the owning side: idempotently via marker detection, in canonical key order anchored before the next active key, never touching active entries, and a no-op when the file is absent; emitting plain serialized data and dropping the examples is rejected.

## Config-rename reference reconciliation

Renaming a usage group or dependency in the project config physically relocates the synced usage files but never rewrites the manifest references to them, so the manifest path entries must always be updated by hand after such a rename.
