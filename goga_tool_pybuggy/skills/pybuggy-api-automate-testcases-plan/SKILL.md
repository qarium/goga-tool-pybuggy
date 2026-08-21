---
name: goga-tool-pybuggy-api-automate-testcases-plan
description: Feature test plan and test case matrix (Flow/Positive/Negative) linking cases to requirements FR-<N>
---

## Identity

You build two artifacts: the feature test plan and the test case matrix. Both artifacts define integration points, testing goals, case types, and severity.

## Core Principle

You **synthesize** three inputs — [TESTCASES_INTAKE], [TESTCASES_DISCOVERY], and [TESTCASES_ELABORATION] — into an
integration testing strategy that assigns each test case a type (`Flow / Positive / Negative`) and a severity.

---

## Algorithm

### Step 1. Load context

Load three inputs:

1. [TESTCASES_INTAKE] supplies: requirements, declared behavior (mainline and error paths), business
   preconditions, roles, and the functional requirements registry §3 (`FR-<N>`).
2. [TESTCASES_DISCOVERY] supplies: actual endpoint contracts, the verification catalog, the severity
   scale, and the confirmed coverage scope.
3. [TESTCASES_ELABORATION] supplies: approved feature traces (each trace = Call → Effect → Verification)
   and the results of mapping the description to the API.

### Step 2. Description of the feature under test

Keep it brief (1–3 paragraphs): core functionality and business value, derived from the requirements plus
service context. Do not restate the requirements verbatim — summarize them.

### Step 3. Feature integration points

Identify ALL in-service relationships the feature touches. Present a table:

`Endpoint` | `Data mutation/Read` | `Criticality for the feature`

For each integration point, account for three aspects: the initiating call, status checks by `id`, and
side-effect reads/mutations.

### Step 4. Integration testing goals

State concrete goals as a numbered list of action verbs (Verify / Ensure /
Confirm) derived from the description (Step 2) and the integration points (Step 3). Focus on the
feature's correctness in integration — not on unit-level details.

### Step 5. Test case matrix (skeleton)

Derive test cases from the [TESTCASES_ELABORATION] traces and the declared behavior using these rules:
the trace's mainline scenario → a Flow case; the trace's contractual Verifications → Positive cases;
error-path behavior (requirements §3) and boundaries → Negative cases. The discovery contracts (`Request`
model, `schemas`) supply concrete data for the cases.

For each endpoint / chain within the confirmed coverage scope, provision:

1. ≥1 **Flow** (happy path): a sequence of actions with state transitions — following the end-to-end
   trace.
2. ≥1 **Positive** (contract-based): validate the values/structure of key response fields and normal
   operation with valid data — per the trace's Verifications.
3. ≥1 **Negative**: invalid data, missing permissions, violated preconditions → expected error (code/body
   from `schemas` 4xx/5xx).

Test types:
- **Flow** — complex business processes and state transitions; a Flow case checks only the fields its
  scenario touches.
- **Positive** — the response contract and the values of key fields.
- **Negative** — error handling and exceptional situations.

Traceability rule: every Verification of every trace must land in the "affected fields/statuses" of at
least one test case — none is lost. Assign each test case a source trace `TR-<N>` from
[TESTCASES_ELABORATION] and a preliminary `severity` from the discovery scale (based on the integration
point's criticality).

Requirements mapping: map each test case to the §3 registry requirements (`FR-<N>`) it verifies — one or
more per case. Then reconcile the registry against the matrix: every `FR-<N>` is covered by at least one
case or is explicitly excluded by the user. Resolve each gap via `AskUserQuestion` (2–4 options: add a
case / exclude the requirement from scope with a reason / go back to requirements) and record the user's
decision in the "Requirements coverage decisions" section. Any FR left without a case enters the
artifact with the status "not covered" — an honest marker that `testcases-review` will flag.

### Step 6. Produce [TESTCASES_PLAN]

STOP if:

- a critical ambiguity in data or preconditions prevents building even one concrete scenario
  (after clarifying with the user).

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [TESTCASES_PLAN]

## Description of the feature under test

[1–3 paragraphs: functionality and business value]

## Feature integration points

[Table: Endpoint | Data mutation/Read | Criticality for the feature]

## Integration testing goals

1. Verify ...
2. Ensure ...
3. Confirm ...

## Test case matrix

[Table: case (name) | type (Flow/Positive/Negative) | requirements (FR-<N> — one or more) |
endpoints | trace (TR-<N>) | affected fields/statuses | severity (blocker/critical/normal/minor/trivial)]

## Requirements coverage decisions

[For each FR without cases: FR | reason | user decision (AskUserQuestion). Empty if all FRs
are covered by matrix cases.]
```
