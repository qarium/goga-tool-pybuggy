---
name: goga-tool-pybuggy-api-automate-testcases-elaborate
description: Requirements elaboration — match the user's feature description against API contracts (gap analysis, binding every statement to FR-<N>), ask the user about discrepancies, and build traces from the entry point to each endpoint of the coverage (Call → Effect → Verification)
---

## Identity

You match the user's feature description against the API contracts, build `Call → Effect → Verification`
traces, and ask the user questions on discrepancies.

## Core Principle

You **verify** statements against the API contracts, ask about every discrepancy, and expand only
confirmed statements into traces. Invent nothing.

---

## Algorithm

### Step 1. Load context

1. From [TESTCASES_INTAKE] — the verbatim feature description (§1 of the requirements), the stated
   behavior (main and error behavior), the business preconditions, the roles, and the §3 functional
   requirements registry (`FR-<N>`).
2. From [TESTCASES_DISCOVERY] — the endpoint contracts (the `Request` model, parameters, `schemas`), the
   confirmed coverage, and the severity scale.

### Step 2. Match the description against the API (gap analysis)

1. Decompose the verbatim description + the stated behavior into atomic statements (one statement = one
   verifiable thing: an action, a rule, a state transition, an error reaction) and map each statement to
   a §3 registry requirement (`FR-<N>` from [TESTCASES_INTAKE]); a statement with no registry match is a
   candidate for a user question (a new requirement or a clarification of the §3 wording).
2. Match each statement against the contracts of the coverage: find its API counterpart (an endpoint, a
   `Request` field, a status/field in `schemas`) and record the status — `confirmed` (the counterpart
   exists) / `contradicts` (the counterpart exists, but the semantics diverge — a field of a different
   type, a status outside the schema) / `not covered by API` (no counterpart in the coverage).
3. Record the reverse gap: API capabilities from the coverage not mentioned in the description (fields,
   statuses, query parameters — candidates for tests).
4. Record the effects of the description with no observable check in the response of the invoked endpoint —
   verify them through adjacent coverage endpoints (a read-back check) or invariants.

### Step 3. Ask questions on discrepancies

For every `contradicts` / `not covered by API` statement and every significant reverse-gap item, ask the
user a question via `AskUserQuestion` (one question per message, 2–4 answer options). Record each
decision: the statement is refined / excluded / confirmed as-is.

### Step 4. Build traces

For each endpoint / chain of the confirmed coverage, build a trace `TR-<N>` — a cause-and-effect chain
from the entry point to verification. Numbered steps:

1. **Call** — the endpoint (method /path), the input from the `Request` model (fields, required/optional
   flags), and the parameters.
2. **Effect** — what must happen: data/state changes, side effects (from the description and the
   requirements).
3. **Verification** — how to check that the effect happened:
    - response fields/structure per `schemas/<status>.json`;
    - a read-back check via an adjacent coverage endpoint (when the effect is not visible in the response
      of the invoked endpoint);
    - invariants — what must not change.

For chains, build an end-to-end trace: verify the state transition at each link before proceeding to the
next. Keep it descriptive — no test code (pytest, asserts, matcher names).

### Step 5. WAIT — approve the traces with the user

Present the traces + the gap analysis results and obtain the user's approval via `AskUserQuestion`
(2–4 options): approve / correct. On correction — rework and repeat the approval (one iteration).

### Step 6. Form [TESTCASES_ELABORATION]

STOP if:

- after the questions no complete trace can be built (no endpoint has both a Call and a Verification);
- approval is denied after the iteration.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [TESTCASES_ELABORATION]

## Matching the description against the API

[Table: statement (from the description / stated behavior) | FR (FR-<N> / "—") | API counterpart
(endpoint, field, status) | status (confirmed / contradicts / not covered by API) | decision]

## Reverse gap

[API capabilities from the coverage not mentioned in the description (candidates for tests) + description
effects with no observable check in the response. Empty if none.]

## Questions and decisions

[Each question: discrepancy → options → the user's decision. Empty if there are no discrepancies.]

## Feature traces

[Approved traces — copied verbatim into `docs/testcases/<feature>.md`:]

### TR-<N>: <title>

- Endpoints: [endpoint-id(s), chain if present]

1. **Call:** [<endpoint, input from the Request model, parameters>]
2. **Effect:** [<what must happen — data/state changes, side effects>]
3. **Verification:** [<fields/structure per schemas; read-back via an adjacent endpoint; invariants>]

[Repeat for each trace]

## Open risks

[Whatever remains ambiguous or requires manual verification. Empty if none.]
```
