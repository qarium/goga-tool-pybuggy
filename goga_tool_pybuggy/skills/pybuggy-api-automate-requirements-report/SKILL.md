---
name: goga-tool-pybuggy-api-automate-requirements-report
description: Assemble the final "Detailed feature requirements" artifact and save it to docs/requirements/<feature>.md
---

## Identity

You synthesize the final [FEATURE_SPEC] artifact from the outputs of all preceding steps and save it to a file.

## Algorithm

1. Collect the outputs of all preceding steps: [INTAKE_REPORT], [DISCOVERY_REPORT], [ELABORATION_REPORT].
2. Synthesize these outputs into the unified [FEATURE_SPEC] artifact.
3. Assign each §3 requirement a stable `FR-<N>` identifier — test cases and the requirements
   coverage matrix reference it. Rules:
    - number sequentially within §3, starting at 1, with no gaps or duplicates;
    - order the numbering by subsection: "Main behavior" → "Error behavior (contract)" →
      "Acceptance criteria" → "Constraints and boundaries";
    - introduce identifiers in §3 only — §4 (preconditions) and §5 (roles) remain textual.
4. Include verified facts only — facts from the service spec and facts confirmed by the user.
   Do not guess.
5. Copy the feature description from the "Original request" section of [INTAKE_REPORT] into §1
   verbatim — the `elaborate` stage of the `testcases` pipeline matches this description against
   the API.
6. Copy the usages registry from the "Project usages" section of [DISCOVERY_REPORT] into §8
   (key | path | role | purpose — a reference of available assets, with no tool selection).
7. Copy the coverage status from the "Existing coverage" section of [DISCOVERY_REPORT] into §9:
   which endpoints are already covered, which Routines exist, and the action for each —
   reuse / extend / check drift.
8. Verify completeness: every section is filled in.
9. Save [FEATURE_SPEC] to `docs/requirements/<feature>.md` (create the `docs/requirements/`
   directory if it does not exist; overwrite the file on repeated runs). The pipeline orchestrator
   supplies the target path (Artifact Path Resolution).

---

## Output Format

Save the result to `docs/requirements/<feature>.md` (the path comes from the orchestrator). The file
content follows the format below. Fill in every section. Empty sections are forbidden.

```md
### Detailed feature requirements: [Feature name]

**1. Context and goal:**

- **Service:** [Brief description of the service]
- **Feature description (verbatim):** [User's original request — from the intake section "Original request"]
- **Feature goal:** [Refined goal]

**2. Feature endpoints:**

[Table: endpoint-id | spec | method | path | role in the feature]

Paths of generated artifacts:

- fixture: `api/<spec>/<id>/api.py` (fixture name, `Request` model)
- schemas: `api/<spec>/<id>/schemas/<status>.json`
- test directory: `tests/<spec>/<id>/`

**3. Functional requirements:**

Every requirement carries a stable identifier `FR-<N>` (sequential numbering within §3 in
subsection order, no gaps, no duplicates) — the registry for test case traceability.

- **Main behavior:**
    - `FR-1` — [Business rule / state transition / chain: condition → service response]
- **Error behavior (contract):**
    - `FR-<N>` — [Error condition (invalid input / missing permissions / violated precondition /
       unavailable dependency) → expected code and error nature from the spec]
- **Acceptance criteria:**
    - `FR-<N>` — [Criterion]
- **Constraints and boundaries:**
    - `FR-<N>` — [What the feature does not do]

**4. Business preconditions and environment:**

- Business preconditions (entities/roles/states — stated as a need): [...]
- Environment (env/version): [...]

**5. Roles and permissions:**

[Who can / cannot call the endpoints]

**6. Integration aspects:**

- [Interaction with other components, mocks, external dependencies]

**7. Links and resources:**

- [Specs (location), design, API docs, etc.]

**8. Available project usages:**

| key     | path             | role                                              | purpose                             |
|---------|------------------|---------------------------------------------------|-------------------------------------|
| `<key>` | [.goga/usages/…] | [runtime reference / data-mocks-utilities / other] | [subject area — one phrase] |

The registry is the result of scanning the target project's `.goga/usages/` directory (from
discovery). It is a **reference of available assets**, not a tool selection: the pipeline identifies
test case needs and agrees them with tools (existing or new) at the `testcases` stage — where usage
files for new libraries (`.goga/usages/cooks/<key>.md`) are also created. If `.goga/usages/` is
empty, state "no usages".

**9. Already covered by tests:**

[Table: endpoint-id | status (not covered / partial / full) | existing `test_*` Routines
(name → Flow/Positive/Negative type) | action (reuse / extend the missing ones / check contract-drift)]
This section is **optional**: if no endpoint is covered, state "no coverage" (as in §6/§8).
```
