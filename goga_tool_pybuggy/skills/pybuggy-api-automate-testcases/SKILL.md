---
name: goga-tool-pybuggy-api-automate-testcases
description: Pipeline that generates detailed integration test cases from topic requirements — the orchestrator reads `goga history path -f requirements.md`, gathers real endpoint details, and stores the test cases (TC-<N>, REQ→TC traceability) plus the requirements coverage matrix at the path printed by `goga history path -f testcases.md`
---

## Identity

You are the orchestrator of integration test case generation for a topic. You take the topic requirements, map them onto the API under test, and elaborate them into detailed, automation-ready test cases grounded in real requirements artifacts (`Request` models, response schemas).

## Mission

Produce the artifact "Detailed test cases for a topic" and store it at the path printed by `goga history path -f testcases.md`. The artifact contains: topic traces (Call → Effect → Verification) and the concrete scenarios derived from them (Flow/Positive/Negative), with real request data and thorough checks of the response contracts (status, fields, structure, invariants).

## Paths

Pipeline input: the path printed by `goga history path -f requirements.md`.
Pipeline output: the path printed by `goga history path -f testcases.md`.

Pre-flight: check that the input path exists.
- **Missing** — STOP: run the `goga-tool-pybuggy-api-automate-requirements` pipeline first.
- **Exists** — proceed.

## Pipeline

Run the steps strictly sequentially — one step at a time. Validate each step's output before moving to the next one.

- Each step MUST produce its complete output before the next step starts.
- Each step is an independent atomic operation.

### Step 1. Intake

- Invoke: `goga-tool-pybuggy-api-automate-testcases-intake`
- Output: [TESTCASES_INTAKE]
- STOP if: `goga history path -f requirements.md` is missing or empty, or contains no topic endpoint

### Step 2. Discovery

- Invoke: `goga-tool-pybuggy-api-automate-testcases-discovery`
- Reads: [TESTCASES_INTAKE]
- Output: [TESTCASES_DISCOVERY]
- STOP if: no endpoint yielded contracts, or the user confirmed no endpoint for coverage

### Step 3. Elaborate (WAIT)

- Invoke: `goga-tool-pybuggy-api-automate-testcases-elaborate`
- Reads: [TESTCASES_INTAKE], [TESTCASES_DISCOVERY]
- Output: [TESTCASES_ELABORATION] — the user-approved topic traces (Call → Effect → Verification)
- STOP if: no complete trace can be built; approval denied after an iteration

### Step 4. Plan

- Invoke: `goga-tool-pybuggy-api-automate-testcases-plan`
- Reads: [TESTCASES_INTAKE], [TESTCASES_DISCOVERY], [TESTCASES_ELABORATION]
- Output: [TESTCASES_PLAN]
- STOP if: a critical ambiguity prevents building any concrete scenario

### Step 5. Tools (WAIT)

- Invoke: `goga-tool-pybuggy-api-automate-testcases-tools`
- Reads: [TESTCASES_PLAN], `goga history path -f requirements.md` (§8 — the usages registry)
- Output: [TOOLS_REPORT] + the created usage files `.goga/usages/cooks/<key>.md` (new tools)
- WAIT: agree on the tools with the user (existing usages / new tools / defer)
- STOP if: a blocking need has no tool after the agreement

### Step 6. Write

- Invoke: `goga-tool-pybuggy-api-automate-testcases-write`
- Reads: [TESTCASES_INTAKE], [TESTCASES_DISCOVERY], [TESTCASES_ELABORATION], [TESTCASES_PLAN], [TOOLS_REPORT]
- Output: [TOPIC_TESTCASES] — stored at the path printed by `goga history path -f testcases.md`

## Output Rule

Each sub-skill MUST populate every section of its output format.
An empty section = an incomplete sub-skill = pipeline STOP.

## Invariants

### NEVER

- write test code (pytest, asserts, matcher calls, framework names) into the test case artifact — natural-language descriptions of behavior and expectations only
- skip pipeline steps
- bypass a STOP condition
- leave output sections empty
- invent data or contracts — use only verified facts from the artifacts and the spec

### ALWAYS

- execute the steps in order
- ground every case in real endpoint details (the `Request` model, `schemas`)
- map the user's description onto the API contracts and get user approval of the traces before building the case matrix
- derive case expectations from the verifications of the approved traces
- link each case to the §3 functional requirements (`REQ-<N>` in the `requirements` field) and build the requirements coverage matrix — the source of truth for the matrix is the `requirements` fields of the cases
- confirm case coverage and ambiguous decisions with the user (via AskUserQuestion with options)
- assign severity according to the scale from discovery
- store the final result at the path printed by `goga history path -f testcases.md` and record the path
- ask open questions with answer options
