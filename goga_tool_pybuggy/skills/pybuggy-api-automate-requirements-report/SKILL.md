---
name: goga-tool-pybuggy-api-automate-requirements-report
description: Assemble the final "Detailed topic requirements" artifact and save it to docs/requirements/<topic>.md
---

## Identity

You synthesize the final [TOPIC_SPEC] artifact from the outputs of all preceding steps and save it to a file.

## Algorithm

1. Collect the outputs of all preceding steps: [INTAKE_REPORT], [DISCOVERY_REPORT], [ELABORATION_REPORT].
2. Synthesize these outputs into the unified [TOPIC_SPEC] artifact.
3. Assign each §3 requirement a stable `REQ-<N>` identifier — test cases and the requirements
   coverage matrix reference it. Rules:
    - number sequentially within §3, starting at 1, with no gaps or duplicates;
    - order the numbering by subsection: "Main behavior" → "Error behavior (contract)" →
      "Acceptance criteria" → "Constraints and boundaries";
    - introduce identifiers in §3 only — §4 (preconditions) and §5 (roles) remain textual.
4. Include verified facts only — facts from the service spec and facts confirmed by the user.
   Do not guess.
5. Copy the topic version context from [INTAKE_REPORT] into the artifact: the spec ref (§1
   "Spec version") and the target environment (§4 "Target environment") — verbatim, with the
   user's confirmed decision. Downstream pipelines (testcases → cells → apply → design → plan →
   accept → fix) read the version from here; every recorded test run command for a non-standard
   environment carries `pytest ... --base-url <url>`.
6. Copy the topic description from the "Original request" section of [INTAKE_REPORT] into §1
   verbatim — the `elaborate` stage of the `testcases` pipeline matches this description against
   the API.
7. Copy the usages registry from the "Project usages" section of [DISCOVERY_REPORT] into §8
   (key | path | role | purpose — a reference of available assets, with no tool selection).
8. Copy the coverage status from the "Existing coverage" section of [DISCOVERY_REPORT] into §9:
   which endpoints are already covered, which Routines exist, and the action for each —
   reuse / extend / regenerate (drifted) / keep stale contract (user decision) — grounding the
   action in the drift status from the "Contract drift (diff)" section of [DISCOVERY_REPORT]:
   an in-sync covered endpoint is reused, a drifted one carries the recorded user decision.
9. Verify completeness: every section is filled in.
10. Save [TOPIC_SPEC] to `docs/requirements/<topic>.md` (create the `docs/requirements/`
   directory if it does not exist; overwrite the file on repeated runs). The pipeline orchestrator
   supplies the target path (Artifact Path Resolution).

---

## Output Format

Save the result to `docs/requirements/<topic>.md` (the path comes from the orchestrator). The file
content follows the format below. Fill in every section. Empty sections are forbidden.

```md
### Detailed topic requirements: [Topic name]

**1. Context and goal:**

- **Service:** [Brief description of the service]
- **Topic description (verbatim):** [User's original request — from the intake section "Original request"]
- **Topic goal:** [Refined goal]
- **Spec version:** [default branch | `ref <ref>` (per spec when they differ) | local spec, no pull —
  the confirmed version context; pull/generate/diff commands of this topic use it]
- **Target environment:** [standard (.env / QA_BASE_URL) | `<url>` of the environment under test —
  test run commands of this topic carry `--base-url <url>`]

**2. Topic endpoints:**

[Table: endpoint-id | spec | method | path | role in the topic]

Paths of generated artifacts:

- fixture: `api/<spec>/<id>/api.py` (fixture name, `Request` model)
- schemas: `api/<spec>/<id>/schemas/<status>.json`
- test directory: `tests/<spec>/<id>/`

**3. Functional requirements:**

Every requirement carries a stable identifier `REQ-<N>` (sequential numbering within §3 in
subsection order, no gaps, no duplicates) — the registry for test case traceability.

- **Main behavior:**
    - `REQ-1` — [Business rule / state transition / chain: condition → service response]
- **Error behavior (contract):**
    - `REQ-<N>` — [Error condition (invalid input / missing permissions / violated precondition /
       unavailable dependency) → expected code and error nature from the spec]
- **Acceptance criteria:**
    - `REQ-<N>` — [Criterion]
- **Constraints and boundaries:**
    - `REQ-<N>` — [What the topic does not do]

**4. Business preconditions and environment:**

- Business preconditions (entities/roles/states — stated as a need): [...]
- Environment (env/version): [...]
- Target environment (base URL): [standard `.env`/`QA_BASE_URL` | `<url>` where the SUT of this
  topic is deployed — recorded run commands use `pytest ... --base-url <url>`]

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

[Table: endpoint-id | status (not covered / partial / full) | drift (in sync / drifted / ADD /
REMOVED) | existing `test_*` Routines
(name → Flow/Positive/Negative type) | action (reuse / extend the missing ones / regenerate
(drifted) / keep stale contract — the recorded user decision)]
This section is **optional**: if no endpoint is covered, state "no coverage" (as in §6/§8).
```
