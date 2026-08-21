---
name: goga-tool-pybuggy-api-automate-testcases-discovery
description: Collect real feature endpoint details and define the severity scale
---

## Identity

You are the executor of this skill. You collect verifiable endpoint contracts and the severity scale for test cases.

## Core Principle

You **reuse** the requirements artifacts. When the artifacts lack details, you fetch the details through the
`pybuggy` CLI. You lock in the severity scale. You confirm the coverage scope with the user.

---

## Algorithm

### Step 1. Reuse the generated requirements artifacts

Take the artifact paths for each endpoint from [TESTCASES_INTAKE]:

1. `api/<spec>/<endpoint-id>/api.py` — read:
    - the fixture name (`<method>_<id>`);
    - the `Request(BaseModel)` model — fields, types, and requiredness (optional = `X | None = None`); if the
      `Request` class is absent, the request body is empty.
2. `api/<spec>/<endpoint-id>/schemas/<status>.json` — response body schemas per status code (resolved JSON-schema).

If the requirements contain no paths or the files are missing, proceed to Step 2; otherwise you may skip Step 2.

### Step 2. Fetch details via the CLI (when the artifacts are insufficient)

For each endpoint that lacks full details:

1. Run: `goga tool pybuggy endpoint info <endpoint-id>`.
2. Parse the JSON output: `Method`, `Path` (`{param}`→`:param`), `Request` (body), `Response` (`{status: schema}`),
   `QueryParams`, `Description`.
3. If you need the full endpoint registry: `goga tool pybuggy endpoint list` → lines `* <endpoint-id> -> [METHOD] <path>`.

### Step 3. Lock in the endpoint contracts

For each endpoint, assemble:

1. **Request body** — fields of the `Request` model with types and requiredness.
2. **Parameters** — path parameters (from `Path`) and query parameters (from `QueryParams`).
3. **Responses** — status codes and schemas (success and 4xx/5xx errors) from `schemas`/`Response`.
4. **Description** — the `Description` field.

### Step 4. Severity scale

Lock in the scale (the source for all subsequent steps):

| Level | When to assign |
|---|---|
| `blocker` | the feature's main happy-path/flow fails; the endpoint is critical and unavailable or breaks its contract |
| `critical` | severe negative case: missing permissions, violated preconditions, 5xx, data loss |
| `normal` | contractual positive checks of key field values/structure |
| `minor` | edge-case/secondary fields that do not break the business scenario |
| `trivial` | cosmetics/optional response fields |

### Step 5. Confirm the coverage with the user

Use `AskUserQuestion` (2–4 options) to confirm with the user:

1. Which endpoints and chains (flows) the test cases will cover.
2. The negative coverage depth (minimal / standard / exhaustive).

### Step 6. Form [TESTCASES_DISCOVERY]

STOP if:

- no endpoint has produced contracts (the artifacts are missing and `endpoint info` returned no data);
- the user has not confirmed any endpoint for coverage.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [TESTCASES_DISCOVERY]

## Endpoint contracts

[Per endpoint: endpoint-id | fixture | Request (fields/types/requiredness) | path/query parameters | Response (codes and schemas) | Description]

## Severity scale

[A table of 5 levels with criteria]

## Confirmed coverage

[Endpoints and chains taken into coverage; negative depth — after the user confirms it]

## Notes

[Missing artifacts, WARNINGS, etc. Empty if none.]
```
