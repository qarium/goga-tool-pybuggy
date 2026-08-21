---
name: goga-tool-pybuggy-api-automate-requirements-review
description: Verification of the test requirements artifact docs/requirements/<feature>.md — section completeness, FR-<N> functional requirement identifiers in §3 (uniqueness and continuity), endpoint/contract/path realness (cross-check against the live spec via the pybuggy CLI and the disk), behavior completeness (main + error behavior)
---
# Pybuggy API Feature Requirements Review

## Identity

You are the reviewer of the "Detailed Requirements for a Feature" artifact. You verify
`docs/requirements/<feature>.md` — the output of the `goga-tool-pybuggy-api-automate-requirements`
pipeline. The artifact describes the **behavior** of the feature under test for subsequent test case
and cell generation; it **contains no test code**.

## Objective

Verify `docs/requirements/<feature>.md` for **completeness, realness, consistency, and
test orientation** — ensure the requirements are sufficient for the `testcases` pipeline to derive
concrete test cases from them, and for `cells` to derive Routines for those cases. You **analyze**
the artifact, **report** findings, and **fix** them (with user approval).

## Core Principle

**Requirements must be real and self-sufficient.** Every endpoint, contract, and path must trace to
the service's live specification and actual on-disk artifacts — never to guesses. Any fact that
cannot be verified through the `pybuggy` CLI or the file system is a finding. Any description that
admits ambiguity is a finding.

### User Interaction Rule

**Always offer answer options.** Whenever you request a decision or confirmation from the user,
provide concrete options (AskUserQuestion). Do not ask open-ended questions without a choice.

---

## Verifiable Artifact

- `docs/requirements/<feature>.md` — detailed requirements for the feature (output of the
  `requirements` pipeline).

**`<feature>` resolution:** from `$ARGUMENTS` (feature name); on empty arguments, scan
`docs/requirements/`: one file → its name (without extension); several → AskUserQuestion with the
list. Hold the resolution for the entire session.

---

## Phases

### Phase 1. Load Context

1. Read the artifact at `docs/requirements/<feature>.md` (by the resolution). If the file is missing,
   stop and inform the user.
2. Load the pybuggy runtime reference via **Skill tool** `goga-tool-pybuggy-api-usage` — to know the
   actual `Request` model, the `api.py` fixture, and response contracts (the source of truth for
   behavior contracts).
3. Load the test cell principles via **Skill tool** `goga-tool-pybuggy-api-cookbook` — to understand
   what the downstream pipelines (`testcases`/`cells`) need from the requirements: behavior (main and
   error), business preconditions, contract status codes.
4. Collect **ground truth** from the live spec (no side effects — read-only):
   - Run `goga tool pybuggy endpoint list` — build the registry of all endpoints: `endpoint-id |
     spec | method | path`.
   - For **every** endpoint mentioned in the artifact, run `goga tool pybuggy endpoint info
     <endpoint-id>` and parse the JSON: `Method`, `Path`, `Request`, `Response`, `QueryParams`,
     `Description`.
5. Verify that the **generated artifacts exist** on disk (the artifact must record their paths in
   section 2): `api/<spec>/<id>/api.py`, `api/<spec>/<id>/schemas/<status>.json`, and the
   `tests/<spec>/<id>/` directory.

> If `endpoint list`/`info` are unavailable (specs not downloaded) — this is a separate finding:
> the requirements cannot be cross-checked against the live spec. Do not run `pull`/`generate` (they
> have side effects) — suggest that the user restart the `requirements` pipeline.

---

### Phase 2. Structure Completeness

Verify that the artifact contains **all mandatory sections**:

1. **Context and goal** — the service, the user's verbatim feature description, and the refined goal.
   An empty verbatim description is **High** (the `elaborate` step of the `testcases` pipeline relies
   on it for API matching).
2. **Feature endpoints** — a table of `endpoint-id | spec | method | path | role in the feature` plus
   the generated artifact paths (`api.py`, `schemas`, the `tests/` directory).
3. **Functional requirements** — main behavior, error behavior (contract), acceptance criteria,
   constraints and boundaries; every requirement carries an `FR-<N>` identifier. A requirement
   without an identifier is **High** (invisible to case traceability in `testcases`).
4. **Business preconditions and environment** — business preconditions (entities/roles/states as a
   need), the environment.
5. **Roles and access** — who may and may not call the endpoints.
6. **Integration aspects** — interaction with components, mocks, external dependencies.
7. **Links and resources** — specs (location), design, API docs, etc.
8. **Available project usages** — a table of `key | path | role | purpose` — the `.goga/usages/` scan
   registry (a reference for the `testcases` stage; there is no per-lib API here — the `tools` step
   collects it during agreement).
9. **Already covered by tests** — a table of `endpoint-id | status (not covered / partial / full) |
   existing `test_*` Routines | action (reuse / extend / check drift)`.

- A section is missing — **Critical**.
- A section exists but is empty or contains a placeholder (TBD, TODO, "…", «далее»/"later") —
  **High**.
- Sections 6 ("Integration aspects") and 9 ("Already covered by tests") may be intentionally empty
  when the feature is isolated / no coverage exists — then this is acceptable and **not a finding**,
  but only if explicitly marked «нет» / «покрытие отсутствует» (none / no coverage).
- Section 8 mirrors the disk scan: if `.goga/usages/` is empty — an explicit «usages отсутствуют»
  mark (no usages) — not a finding; an empty section without the mark is **High**.

---

### Phase 3. Endpoint and Artifact Realness

**Goal:** ensure that every claim about endpoints and artifacts is true, not invented.

1. **Endpoint existence** — every `endpoint-id` from section 2 is present in the `goga tool pybuggy
   endpoint list` registry. A non-existent identifier is **Critical** (the test factory cannot
   generate the fixture).
2. **Method and path accuracy** — `method`/`path` in section 2 match `endpoint info`. A mismatch is
   **High**.
3. **Spec membership** — `spec` is correct for every endpoint. An error is **High**.
4. **Artifact path realness** — the `api.py`, `schemas/<status>.json`, `tests/<spec>/<id>/` paths
   from section 2 **exist on disk**. A non-existent path is **Critical** (generation was not run, or
   the path was recorded incorrectly).
5. **Response schema completeness** — every status code from section 6 has a corresponding
   `schemas/<status>.json`. A missing schema for a declared contract is **High**.
6. **Request without code** — the "Endpoints" section contains **only** descriptions and paths; any
   implementation code (`def test_`, `assert`, `@pytest`, pytest fixtures) is **Critical**.
7. **Existing coverage realness (§9)** — cross-check via `goga schema tests/`: every endpoint
   declared in §9 as partially/fully covered has the listed `test_*` Routines in the output (a cell
   may be named by endpoint-id or combine several endpoints — search for Routines across the whole
   tree). A declared "covered" endpoint without a Routine in `goga schema` is **High**. The reverse:
   an endpoint from §2 is covered by a Routine in `goga schema`, but §9 does not mention it (without
   the «покрытие отсутствует»/"no coverage" mark) — **Medium**.

---

### Phase 4. Behavior Consistency

**Goal:** internal consistency of the requirements — no self-contradictions.

1. **Behavior ↔ endpoint** — every behavior (main and error) in section 3 references only endpoints
   from section 2. A reference to a foreign or non-existent endpoint is **High**.
2. **Error contracts ↔ info/schemas** — the codes and nature of errors in "Error behavior" match the
   `Response`/`schemas` from `endpoint info`. A non-existent status code is **High**; invented
   behavior is **High**.
3. **Error behavior completeness** — every significant endpoint describes the conditions of its main
   errors (invalid input / missing rights / violated precondition), wherever this is meaningful per
   the spec. A missing description on a significant endpoint is **High**.
4. **Acceptance criteria** — every criterion (section 3) is unambiguously checkable (a "yes/no"
   answer) and grounded in the described behavior/contracts. An ambiguous criterion is **High**; a
   criterion without a contractual basis is **Medium**.
5. **Invariants and side effects** — the declared invariants do not contradict the main behavior and
   the integration aspects. A contradiction is **High**.
6. **Constraints** — the "Constraints and boundaries" section describes what the feature **does not
   do**. Empty generic phrases are **Medium**.
7. **Usage registry (§8)** — cross-check against the disk: every table key corresponds to an existing
   `.goga/usages/**/<key>.md` file (the table path matches the actual one); the role classification
   (runtime reference / data-mocks-utilities / other) is meaningful. A file under `.goga/usages/`
   missing from §8 is **Medium** (incomplete registry); a key without a file is **High** (a dangling
   reference for `testcases`); a path mismatch is **Medium**.
8. **FR identifiers** — every item of §3 (all four subsections) has an `FR-<N>`; the identifiers are
   unique (a duplicate is **High** — an ambiguous reference for cases) and continuous from 1 in
   subsection order (a gap/break is **Medium**); `FR-<N>` appears only in §3 (outside §3 —
   **Medium**).

---

### Phase 5. Test Orientation and Coverage

**Goal:** ensure the artifact is ready for elaboration into tests, not into production code.

1. **Behavior only, no code** — the artifact contains **no** test or production code (`pytest`,
   `assert`, `def test_`, framework imports). Any occurrence is **Critical** (a violation of the
   `requirements` pipeline invariant).
2. **Behavior completeness** — the artifact describes **both** main behavior **and** error behavior.
   The absence of either kind is **High**.
3. **Roles and access** — for endpoints with `auth`, the artifact states who may call them and who
   may not (a foreign session, missing auth). An omission is **Medium** (or **High** if auth is a
   key part of the feature).
4. **Business preconditions** — the preconditions (entities/roles/states) are concrete, not "prepare
   data". Vague preconditions are **Medium**.
5. **Integrations and mocks** — if the feature touches several endpoints or external components,
   this is reflected (chains, mocks, side effects). An omission in the presence of such dependencies
   is **Medium**.
6. **Links** — section 7 points to real spec `location`s. A non-existent/empty link is **Medium**.

---

### Phase 6. Report and Fix Findings (Interactive)

Collect all findings from Phases 2–5 **before** presenting them. Sort them by severity:
**Critical → High → Medium**.

Present findings **one at a time**. For each finding:

#### Step 1. Present the finding

- **Severity** (Critical / High / Medium)
- **Area** (Structure / Realness / Consistency / Test-Orientation)
- **Location** — an exact reference to the artifact's section/line/endpoint
- **Issue** — a clear description of the problem
- **Evidence** — the confirmation source (`pybuggy` CLI output, a missing file on disk, etc.)
- **Suggested fix** — a concrete change, not general advice

#### Step 2. Request a decision (AskUserQuestion)

1. **Apply suggested fix** — apply the fix now
2. **Propose alternative** — the user offers a different option
3. **Skip** — skip the finding

#### Step 3. Apply the decision

- **Apply**: update `docs/requirements/<feature>.md`, then re-verify that the fix introduced no new
  problems (re-run the relevant checks). Report the re-verification result briefly.
- **Skip**: mark the finding as "skipped" and continue.
- **Propose alternative**: discuss, agree, apply, re-verify.

#### Step 4. Next finding

Repeat from Step 1. Show a counter: "Finding 3 of 12".

After all findings — a summary:
- **Fixed**: N (by severity and area)
- **Skipped**: N (by severity and area)
- **Artifact status**: updated / unchanged

> **Fix rule:** modify **only** the requirements artifact `docs/requirements/<feature>.md`. Do not
> modify the generated `api.py`/`schemas`/`tests/` and do not run `pull`/`generate` — those belong
> to the `requirements` pipeline's domain. If realness is broken because generation is missing,
> direct the user to restart `requirements`.

---

## Output

- Findings summary: fixed / skipped by severity and area
- The updated `docs/requirements/<feature>.md` (if fixes were applied)
- Verdict: passed / failed

---

## Final Self-Check

Before you finish, verify:

1. Did you read the artifact `docs/requirements/<feature>.md` (using the resolution)?
2. Did you load `goga-tool-pybuggy-api-usage` and `goga-tool-pybuggy-api-cookbook`?
3. Did you collect ground truth via `goga tool pybuggy endpoint list` and `endpoint info` for every
   endpoint?
4. Did you check the generated artifact paths (`api.py`/`schemas`/`tests/`) on disk?
5. Did you check structural completeness (all mandatory sections, no placeholders; §6/§9 optional,
   §8 — a registry with an explicit mark when usages are empty)?
6. Did you check the §3 numbering (`FR-<N>` on every requirement of all subsections, uniqueness,
   continuity in subsection order)?
7. Did you check the realness of endpoints/methods/paths/schemas?
8. Did you check consistency (behavior↔endpoint, error contracts↔schemas, acceptance criteria)? Did
   you cross-check the §8 usage registry against the disk (key ↔ file, roles)?
9. Did you check test orientation (no code, main behavior + error behavior present, roles, business
   preconditions)?
10. Did you present every finding one at a time with an Apply/Alternative/Skip choice?
11. Did you apply the approved fixes with re-verification?

If at least one answer is "no" — complete the unfinished check before you return.
