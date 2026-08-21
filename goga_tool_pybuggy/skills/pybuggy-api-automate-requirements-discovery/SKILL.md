---
name: goga-tool-pybuggy-api-automate-requirements-discovery
description: Feature endpoint discovery and filtering, existing test coverage detection, code generation
---

## Identity

You are responsible for discovering and selecting the endpoints of the service under test that are relevant to the feature, and for generating the artifacts: fixtures, request models, response schemas, and test directories.

## User Interaction Rule

At the endpoint selection stage, always ask the user to confirm the selection (2–4 options) before generating any artifacts.

---

## Algorithm

### Step 1. Pull specifications (pull)

1. Run: `goga tool pybuggy endpoint pull`.
2. Specs without a `git:` block (local) are skipped with a WARNING status — this is normal; record the status of every spec.
3. Record the pulled `specs` and their `location`.

### Step 2. Scan project usages

1. Recursively enumerate `.goga/usages/` in the target project (`*.md`): base usages (`conventions` and others) and cooks files (`.goga/usages/cooks/**`, including subdirectories such as `pybuggy/`).
2. For each file, record: the key (file name without `.md`; for nested files, `<folder>-<name>`), the path, and a brief purpose (from the first lines of the file — the subject domain, not a full summary).
3. Classify each file by its testing role: **runtime reference** (how to invoke the tools — e.g. `pybuggy-api`, `pybuggy-asserts`), **data setup / mocks / utilities** (data setup libraries), **other**.
4. The usage registry feeds section §8 of the requirements and is consumed later by the `testcases` stage: that stage identifies the tool needs of the test cases and either finds a tool among the existing usages or negotiates a new one (the usage file is created at that stage). Ask the user nothing at this step — this step is a scan only.

### Step 3. List endpoints (list)

1. Run: `goga tool pybuggy endpoint list` (or with `-s/--spec` if the scope is already limited to one spec).
2. The output consists of lines of the form `* <endpoint-id> -> [METHOD] <path>`.
3. Build the complete endpoint registry (endpoint-id, spec, method, path).

### Step 4. Filter endpoints by feature

1. Match the endpoints to the feature using the Feature Intake Report (by path, name, description).
2. Account for chains: a feature may require several endpoints (for example, action initiation plus a status check by `id`).
3. When several `specs` exist, determine which spec each relevant endpoint belongs to.

### Step 5. Detect existing test coverage

1. Run `goga schema tests/` (or `goga schema`) in the target project. The output is a JSON tree: every cell `tests/<spec>/<id>/` carries a `types` field (Routine/Entity names).
2. For every filtered endpoint `<spec>/<endpoint-id>`, find its Routine: a cell may be named after the endpoint-id (`tests/<spec>/<endpoint-id>/`), or one cell may combine several endpoints — search the entire `goga schema` output for cells whose `test_*` Routines reference the fixture of this endpoint (`api/<spec>/<endpoint-id>/api.py`). The Routines found are the existing covered test cases.
3. For every existing `test_*` Routine, read the annotation in the CODEMANIFEST of its cell and record:
    - the Routine name (`test_<name>`);
    - the type (Flow / Positive / Negative) and a brief summary from `Purpose` / `Precondition:` / `Data:` / `Steps:`.
4. Record the coverage status of every endpoint:
    - **not covered** — no Routines of the endpoint are found;
    - **partially covered** — some of the expected scenarios are represented by Routines; list the existing `test_*` Routines;
    - **fully covered** — all expected scenarios of the endpoint are already represented by Routines.
5. Record the adjacent cells for reference: neighboring `tests/<spec>/...` cells from `goga schema` with ready data setup patterns / lib-usages / mocks.

### Step 6. Confirm the selection with the user

1. Present the selected endpoints: id, method, path, the intended role in the feature, **and the coverage status** (not covered / partially covered with the list of existing Routines / fully covered).
2. For fully covered endpoints, offer to exclude them from further generation (the existing tests are reused), subject to user agreement.
3. Offer the choice via AskUserQuestion: confirm / extend / narrow the selection / exclude the already covered endpoints.

### Step 7. Extract endpoint details (info)

For every confirmed endpoint:

1. Run: `goga tool pybuggy endpoint info <endpoint-id>`.
2. Parse the JSON: `Method`, `Path`, `Request`, `Response`, `QueryParams`, `Description`.
3. Record the contracts: the request body (`Request`), the response codes and schemas (`Response`), the parameters (`QueryParams` / path parameters), and the description.

### Step 8. Generate artifacts (generate)

1. Run: `goga tool pybuggy endpoint generate <endpoint-id> [<endpoint-id> ...] -f` for the endpoints kept in the selection (including partially covered ones — their `api/` fixtures are updated from the spec; fully covered ones can be skipped if the user decided to exclude them).
2. Record the paths of the created artifacts:
    - fixture: `api/<spec>/<endpoint-id>/api.py` (fixture name, importable `Request` model);
    - schemas: `api/<spec>/<endpoint-id>/schemas/<status>.json`;
    - test directory: `tests/<spec>/<endpoint-id>/`.
3. After generation, verify that the existing `tests/<spec>/<endpoint-id>/CODEMANIFEST` files and their Routines remain intact.

### Step 9. Assemble the [DISCOVERY_REPORT]

STOP if:

- `pull` failed and the specifications are unavailable locally;
- `list` returned an empty result;
- filtering by feature produced 0 endpoints;
- the user confirmed no endpoint;
- `generate` failed (for example, the `endpoint-id` is not found in the spec).

---

## Output Format

Fill in every section. Empty sections are prohibited.

```md
# [DISCOVERY_REPORT]

## Specs (pull)

[Table: spec | location | source (git/local) | pull status]

## Project usages (.goga/usages/ scan)

[Table: key | path | role (runtime reference / data-mocks-utilities / other) | brief purpose.
If .goga/usages/ is missing or empty — state "usages are missing".]

## Endpoint registry (list)

[Table: endpoint-id | spec | method | path — the complete list]

## Selected feature endpoints

[Table: endpoint-id | spec | method | path | role in the feature (initiator/verification/side-effect) | coverage status
(not covered / partial / full)]

## Existing coverage

[Table: endpoint-id | status (not covered / partial / full) | existing test_* Routines
(name → Flow/Positive/Negative type, brief summary) | adjacent cells for reference (data setup patterns / lib-usages / mocks)]
If no endpoint is covered — state "no coverage".]

## Endpoint details (info)

[Per endpoint: Request (body) | QueryParams/path parameters | Response (codes and schemas) | Description]

## Generated artifacts

[Table: endpoint-id | api.py (path, fixture name, Request model) | schemas (codes) | tests/ directory]

## Notes

[Local specs without git, warnings about existing artifacts, etc. Empty if none.]
```
