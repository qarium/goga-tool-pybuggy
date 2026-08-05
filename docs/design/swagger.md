# Design Document: Swagger 2.0 support in endpoint extraction (`spec` cell)

## Contract Changes

### Changed CODEMANIFEST Files
- `goga_tool_pybuggy/spec/CODEMANIFEST` (working-tree change vs `0.0.x`): endpoint extraction cell gains
  support for **Swagger 2.0** alongside the existing OpenAPI 3.x path. A new Routine `detect_spec_version`
  routes each parsed spec by format; `extract_endpoints` is extended to extract fields per format and to
  normalize both the OpenAPI `nullable` and the Swagger `x-nullable` keywords into the JSON-Schema union
  form. The `Endpoint`/`build_endpoint_id`/`load_spec` contracts are **unchanged** (verified identical to
  the prior file) — the change is purely additive to the extraction routine.

### New Entities
- `detect_spec_version(spec: dict[str, Any]) -> version: str` — Routine, `location: extract.py`.
  Inspects the parsed spec's content (top-level `swagger` vs `openapi` key) and returns the format
  identifier `"swagger"` or `"openapi"`, raising `ValueError` when neither is present.

### Changed Entities
- `extract_endpoints(spec: dict[str, Any]) -> endpoints: list[Endpoint]` — Routine, `location: extract.py`.
  - **Algorithm**: new step 2 — detect format via `detect_spec_version`; field extraction in step 4 now
    branches on the detected version.
  - **Requirements**: Swagger 2.0 field paths added (`in: body` body parameter for request;
    `responses[code].schema` without a `content` wrapper for response; inlined `type/format/items/enum`
    fields of `in: query` parameters for query); nullable normalization extended to also rewrite
    Swagger `x-nullable: true` (with the `anyOf` fallback already present for type-less fragments).
  - **Constraints**: format-equivalence (both formats → same normalized schema shape for equivalent
    operations); invalid-spec `ValueError` propagation from `detect_spec_version`; explicit out-of-scope
    items (no basePath/servers merge, no consumes/produces, no formData/file uploads).

### Deleted Entities
- None.

### Usages and Annotations Changes
- Global `Annotations` — now describes endpoint-extraction **patterns** (plural) over the parsed dict for
  both Swagger 2.0 and OpenAPI 3.x, and states the version-routed normalization to a single JSON-Schema
  shape on `Endpoint`.
- `Footer Description` — now mentions endpoint extraction for Swagger 2.0 and OpenAPI 3.x.
- No new `Usages` keys, no new `Imports` (the cell remains a leaf — 0 `Imports`).

## Applied Fixes

### Fixed CODEMANIFEST Defects
- **Review fix (Critical) — Swagger query-param `x-nullable` dropped before normalization.** The
  CODEMANIFEST `extract_endpoints` Requirements had an internal contradiction: the Swagger-query bullet
  ("via its inlined type/format/items/enum fields") excluded `x-nullable`, while the normalization bullet
  required "each extracted schema … Swagger x-nullable: true … become a type list including 'null'".
  Tracing the design's `_extract_query_params` Swagger branch revealed that the `_TYPE_FIELDS` whitelist
  (without `x-nullable`) drops the keyword **before** `_normalize_nullable` runs, so a Swagger query
  param's nullability is silently lost — and the design's own test
  `test_extract_endpoints_rewrites_swagger_x_nullable_to_jsonschema_union` asserted
  `query_params["tag"] == {"type": ["integer", "null"]}`, which was unreachable under the documented
  algorithm. **Fix applied (approved by user):** (1) design `extract.py` `_TYPE_FIELDS` extended with
  `"x-nullable"`; (2) CODEMANIFEST Swagger-query Requirements bullet reconciled to the canonical
  `type/format/items/enum/default/description/x-nullable` list; (3) `swax-openapi.md` usage `_TYPE_FIELDS`
  updated for consistency. Re-trace: `request`/`response` (taken from `schema`) are unaffected; the
  `tag` query param now survives filtering as `{"type":"integer","x-nullable":true}` and normalizes to
  `{"type":["integer","null"]}` — the test assertion is now reachable. The OpenAPI path is untouched.
- Pre-existing contract cleanliness: all backtick references resolve within the document context (the
  earlier `query_params` backtick defect was resolved by the preceding `apply-architecture` stage — the
  contract now reads "outside the query_params model" without backticks, since `query_params` is an
  `Endpoint` property, not a resolvable link target). `goga lint` reports only the 3 baseline
  `[usage_filepath_exists]` errors (an environment limitation — the linter resolves usage paths relative
  to the cell directory rather than the project root; identical on every other cell) and zero
  `[annotation_links_exists]` errors.

## Entity Interaction and Data Flow

### Interaction Diagram

```
                consumer cells (info / list / generate / output / api.asserts)
                          |
                          | spec = load_spec(spec_path)      # dict, $ref inlined by Prance
                          v
                 +---------------------+
                 |   load_spec         |  (loader.py) -- unchanged; SpecParseError -> ClickException
                 +---------------------+
                          |
                          | endpoints = extract_endpoints(spec)
                          v
                 +---------------------+
                 | extract_endpoints   |  (extract.py) -- the changed routine
                 +---------------------+
                    |         |        |
                    |         |        +-- _normalize_nullable(schema)  [extended: nullable + x-nullable]
                    |         +-- build_endpoint_id(method, path)  (endpoint_id.py) -- unchanged
                    +-- detect_spec_version(spec)  (extract.py) -- NEW; may raise ValueError
                          |
                          v
                 +---------------------+
                 |   Endpoint(...)     |  (endpoint.py) -- unchanged model
                 +---------------------+
                          |
                          | ep.id (computed via build_endpoint_id)
                          v
                      returned to consumer
```

### Data Flows

- **Parse → extract (OpenAPI 3.x spec)**: `load_spec` → dereferenced dict → `extract_endpoints` detects
  `"openapi"` → reads `requestBody.content.application/json.schema`, `responses[code].content.application/json.schema`,
  query params' nested `schema` → `_normalize_nullable` (rewrites `nullable`) → builds `Endpoint`.
- **Parse → extract (Swagger 2.0 spec)**: `load_spec` → dereferenced dict → `extract_endpoints` detects
  `"swagger"` → reads the `in: body` parameter's `schema`, `responses[code].schema` (no content wrapper),
  query params' inlined type fields → `_normalize_nullable` (rewrites `x-nullable`) → builds `Endpoint`.
- **Invalid spec (no version)**: `extract_endpoints` → `detect_spec_version` raises `ValueError` →
  propagated uncaught out of `extract_endpoints` (pure-logic boundary; CLI mapping to a non-zero exit is
  the consumer's responsibility, per contract-boundary isolation).

### Entity Dependencies
- `spec` is a **leaf** cell (0 `Imports`) — no cross-cell type/practice dependencies to design.
- Dependency direction is one-way: `output`, `commands/list`, `commands/info`, `commands/generate`,
  `api/asserts` import from `spec`. None of them import `detect_spec_version` directly (it is an internal
  routing helper re-exported on the facade for completeness); all of them consume `extract_endpoints` /
  `Endpoint` / `load_spec` / `build_endpoint_id` — none of which changed signature. **Consumers are
  isolated; no consumer edits are required.**

## Code Stack Trace

### Trace: `detect_spec_version(spec)`

#### Chain
1. **Input**: `spec: dict[str, Any]` — the dereferenced spec dict (output of `load_spec`); passed by
   `extract_endpoints`.
2. **Step**: check `"swagger" in spec` → checkpoint: Swagger 2.0 specs carry a top-level `swagger` key
   (e.g. `"swagger": "2.0"`) per the Swagger 2.0 specification. If present, return `"swagger"`.
3. **Step**: else check `"openapi" in spec` → checkpoint: OpenAPI 3.x specs carry a top-level `openapi`
   key (e.g. `"openapi": "3.0.3"`) per the OpenAPI 3.x specification. If present, return `"openapi"`.
4. **Step**: else raise `ValueError` → checkpoint: a spec declaring neither key contradicts both
   specifications and is invalid; the error is the contract's signal.
5. **Output**: `version: str` — `"swagger"` or `"openapi"` (or `ValueError` propagates).

#### Checkpoint Summary
- Input type match with `extract_endpoints`' `spec` arg: **passed** — both `dict[str, Any]`.
- Logic correctness (key presence, not value): **passed** — detection is by content only, never by the
  declarative config type field (see `Requirements`).
- `ValueError` on unrecognized format: **passed** — matches the contract's invalid-spec rule; not
  swallowed by the caller.

### Trace: `extract_endpoints(spec)`

#### Chain
1. **Input**: `spec: dict[str, Any]` — dereferenced spec from `load_spec`.
2. **Step**: `version = detect_spec_version(spec)` → checkpoint: routing decision; may raise `ValueError`
   for an invalid spec (propagated, see the invalid-spec data flow). Returns `"swagger"` | `"openapi"`.
3. **Step**: `paths = spec.get("paths", {})` → checkpoint: absent `paths` yields `{}`; iteration below
   then produces no endpoints (for a valid, path-less spec).
4. **Step**: for each `(path, path_item)` in `paths.items()`:
   - skip when `path_item` is not a dict (malformed/null path-item) → checkpoint: graceful skip, no crash.
   - `shared_params = path_item.get("parameters", [])` (inherited by every operation).
   - for each `method` in `HTTP_METHODS = (get, post, put, delete, patch, options, head)`:
     - `operation = path_item.get(method)`; skip if `None` (non-method keys like `parameters`/`summary`
       naturally excluded) → checkpoint: only HTTP methods extracted.
     - `all_params = [*shared_params, *operation.get("parameters", [])]`.
     - **request** (branched by `version`):
       - `"openapi"` → `operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})`.
       - `"swagger"` → the `schema` of the first parameter whose `in == "body"` (or `{}` if none).
     - **response** (branched by `version`):
       - `"openapi"` → `{code: resp.get("content", {}).get("application/json", {}).get("schema", {}) for code, resp in operation.get("responses", {}).items()}`.
       - `"swagger"` → `{code: resp.get("schema", {}) for code, resp in operation.get("responses", {}).items()}`.
     - **query_params** (branched by `version`, from `all_params` so path-item params are inherited):
       - `"openapi"` → `{name: param.get("schema", {}) for each param whose in == "query" and name present}`.
       - `"swagger"` → `{name: {k: v for k, v in param.items() if k in _TYPE_FIELDS} for each param whose in == "query" and name present}`,
         where `_TYPE_FIELDS = ("type", "format", "items", "enum", "default", "description", "x-nullable")`.
     - apply `_normalize_nullable` to request, to each response schema, and to each query-param schema
       → checkpoint: every extracted schema is nullable-normalized at the boundary (handles both
       `nullable` and `x-nullable`).
     - `description = operation.get("description", "")`.
     - build `Endpoint(method=method, path=path, request=..., response=..., query_params=..., description=...)`.
5. **Output**: `endpoints: list[Endpoint]` — one per operation; each `ep.id` computed via
   `build_endpoint_id` (computed field, lazily).

#### Checkpoint Summary
- Version routing feeds field extraction: **passed** — `detect_spec_version` return selects the branch.
- `Endpoint` constructor compatibility: **passed** — `Endpoint` is `kw_only=True`; the six kwargs
  (`method`, `path`, `request`, `response`, `query_params`, `description`) exactly match the constructor.
- `ValueError` propagation: **passed** — not caught inside `extract_endpoints`.
- Normalization coverage: **passed** — applied to all three schema-bearing fields before construction.
- Equivalence invariant: **passed** — for equivalent operations, the format-specific branches produce the
  same normalized schema shape (type-bearing query fields map 1:1; the OpenAPI nested `schema` and the
  Swagger inlined type fields both reduce to the same JSON-Schema fragment).

### Trace: `_normalize_nullable(node)` (extended private helper)

#### Chain
1. **Input**: `node: Any` — a resolved schema fragment (dict / list / scalar).
2. **Step**: if `node` is a dict, recurse into every value, then inspect the (now-recursed) result:
   - read-and-remove `nullable` (`result.pop("nullable", None)`) and `x-nullable`
     (`result.pop("x-nullable", None)`) — both keys are dropped regardless of value;
   - if either equals `True`, rewrite to the JSON-Schema union form:
     - existing `type` is a scalar → `type = [type, "null"]`;
     - existing `type` is a list → append `"null"` if absent;
     - otherwise fall back to `anyOf` (append `{"type": "null"}` to an existing `anyOf`, else synthesize
       `[{"type": "null"}]`).
3. **Step**: if `node` is a list, recurse elementwise; otherwise return `node` unchanged.
4. **Output**: a normalized copy (original is not mutated — dict/list rebuilt).

#### Checkpoint Summary
- `x-nullable` handled symmetrically with `nullable`: **passed** — single combined predicate.
- Both originating keys dropped: **passed** — `pop` removes them even when `False`.
- Recursion covers `properties`/`items`/`additionalProperties`/`anyOf`/`oneOf`/`allOf`: **passed** —
  the value-wise recursion descends into every nested container.

## Algorithm Design

### `detect_spec_version`

**Responsibility**: classify a parsed spec by format, from content only.

**Algorithm:**
```
1. IF "swagger" in spec: return "swagger"
2. ELIF "openapi" in spec: return "openapi"
3. ELSE: raise ValueError("spec declares neither a swagger nor an openapi version")
```

**Errors:**
- `ValueError` → raised on a spec declaring neither top-level key; **not handled locally** — propagates
  to and through `extract_endpoints`. The CLI consumer decides how to surface it (its own contract's
  concern — boundary isolation).

**Edge Cases:**
- Spec carrying **both** `swagger` and `openapi` keys (malformed) → returns `"swagger"` (Swagger checked
  first). Acceptable; such a spec is ill-formed and the choice is deterministic.
- Empty dict `{}` → raises `ValueError`.
- Spec with a top-level version key but empty/missing `paths` → returns the format normally
  (path-lessness is `extract_endpoints`' concern, not the version detector's).

### `extract_endpoints` (changed)

**Responsibility**: walk a parsed spec's operations and build one `Endpoint` per method+path, routing
field extraction by the detected format and normalizing both nullability keywords.

**Algorithm:**
```
1. version = detect_spec_version(spec)            # may raise ValueError (propagated)
2. result = []
3. FOR (path, path_item) IN spec.get("paths", {}).items():
   a. IF path_item is not a dict: CONTINUE
   b. shared_params = path_item.get("parameters", [])
   c. FOR method IN HTTP_METHODS:
      i.   operation = path_item.get(method)
      ii.  IF operation is None: CONTINUE
      iii. all_params = [*shared_params, *operation.get("parameters", [])]
      iv.  request = _normalize_nullable(_extract_request(operation, version))
      v.   response = {code: _normalize_nullable(s) for code, s in _extract_responses(operation, version).items()}
      vi.  query_params = {name: _normalize_nullable(s) for name, s in _extract_query_params(all_params, version).items()}
      vii. description = operation.get("description", "")
      viii.ENDPOINT = Endpoint(method, path, request, response, query_params, description)
      ix.  result.append(ENDPOINT)
4. RETURN result
```

Where the format-routed extractors (the `Requirements` field paths):

```
_extract_request(operation, version):
  IF version == "openapi":
      RETURN operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema", {})
  ELSE  # swagger
      FOR p IN operation.get("parameters", []):
          IF p.get("in") == "body": RETURN p.get("schema", {})
      RETURN {}

_extract_responses(operation, version):
  IF version == "openapi":
      RETURN {code: resp.get("content", {}).get("application/json", {}).get("schema", {})
              for code, resp in operation.get("responses", {}).items()}
  ELSE:  # swagger — no content wrapper
      RETURN {code: resp.get("schema", {}) for code, resp in operation.get("responses", {}).items()}

_extract_query_params(all_params, version):
  result = {}
  FOR p IN all_params:
      IF p.get("in") != "query": CONTINUE
      name = p.get("name")
      IF not name: CONTINUE
      IF version == "openapi":
          result[name] = p.get("schema", {})
      ELSE:  # swagger — inlined type fields (`x-nullable` is in `_TYPE_FIELDS` so it survives to `_normalize_nullable`)
          result[name] = {k: v for k, v in p.items() if k in _TYPE_FIELDS}
  RETURN result

_TYPE_FIELDS = ("type", "format", "items", "enum", "default", "description", "x-nullable")
# `x-nullable` is intentionally included so the Swagger query-param nullable keyword reaches
# `_normalize_nullable`; without it the keyword is dropped before normalization and the query
# param's nullability is silently lost (review fix).
```

**Errors:**
- `ValueError` (from `detect_spec_version`) → propagated uncaught; the consumer observes the raw
  exception at the pure-logic boundary.

**Edge Cases:**
- Malformed/null path-item → skipped (step 3a).
- Operation with no `application/json` content (OpenAPI) / no `in: body` parameter (Swagger) → `request`
  defaults to `{}`.
- Operation with no `responses` → `response` defaults to `{}`.
- Query parameter without a name → skipped (step vi, `IF not name: CONTINUE`).
- Shared path-item parameters merged **before** operation parameters (operation-level wins on name
  collision by dict overwrite — last-write-wins; matches existing behavior and the contract's "merge
  with operation parameters" wording).

### `_normalize_nullable` (extended)

**Responsibility**: rewrite OpenAPI 3.0 `nullable` and Swagger `x-nullable` into JSON-Schema union types
at the parse boundary.

**Algorithm:**
```
1. IF node is a dict:
   a. result = {key: _normalize_nullable(value) for key, value in node.items()}
   b. nullable_val    = result.pop("nullable", None)
      x_nullable_val = result.pop("x-nullable", None)
   c. IF nullable_val is True OR x_nullable_val is True:
      - existing = result.get("type")
      - IF existing is a str:      result["type"] = [existing, "null"]
      - ELIF existing is a list:   IF "null" not in existing: result["type"] = [*existing, "null"]
      - ELSE:                      branches = result.get("anyOf")
                                   IF branches is a list: result["anyOf"] = [*branches, {"type": "null"}]
                                   ELSE:                 result["anyOf"] = [{"type": "null"}]
   d. RETURN result
2. IF node is a list: RETURN [_normalize_nullable(item) for item in node]
3. RETURN node   # scalar — unchanged
```

**Edge Cases:**
- `nullable: false` / `x-nullable: false` → key dropped, no union added (correct — neither is JSON-Schema).
- Type-less nullable fragment → `anyOf` fallback (both pre-existing sub-cases preserved).
- `additionalProperties` as a boolean `false` → returned unchanged (scalar branch).
- Scalars (`"string"`, numbers, `None`) → returned unchanged.

## Cross-cutting Concerns

- **Error handling**: layered by boundary. `load_spec` (loader.py) maps `SpecParseError →
  click.ClickException` for CLI consumers. `detect_spec_version` raises `ValueError` for invalid specs;
  `extract_endpoints` propagates it without swallowing (pure logic does not invent a CLI-facing error).
  The cell's pure-logic routines (`extract.py`, `endpoint_id.py`, `endpoint.py`) never import `click` —
  boundary isolation is preserved.
- **Logging**: none. Per `conventions`, pure logic carries no logging; `extract.py`/`endpoint_id.py`/
  `endpoint.py` have no `logging` import and acquire none. (`loader.py` similarly logs nothing — it maps
  errors to exceptions.)
- **Validation**: input shape (derefenced dict from `load_spec`) is trusted; structural robustness
  guards against malformed fragments — non-dict path-items skipped, non-method path-item keys ignored,
  nameless query params skipped, missing content/schema default to `{}`. No schema validation is
  performed (the runtime `jsonschema` validator, mentioned in the nullable rationale, lives in the
  `generate` consumer, not here).
- **Caching**: none. Stateless functions.
- **Concurrency**: thread-safe by construction — stateless, no shared mutable state, dicts rebuilt (not
  mutated in place).

## Usages Analysis

### `conventions`
- **What it provides**: project-wide Python rules (pydantic `kw_only` models, relative imports, Google
  docstrings, test structure mirroring src, pytest/ruff tooling).
- **Where used**: global `Annotations`; the `Endpoint` pydantic model; all routine docstrings and tests.
- **Why chosen**: mandatory project baseline for every cell.
- **How exactly**: `Endpoint` uses `ConfigDict(kw_only=True, extra="forbid")`; routines carry Google
  docstrings with `Args`/`Returns`/`Raises`; tests live in `tests/spec/test_<module>.py` mirroring
  `goga_tool_pybuggy/spec/<module>.py`; pure logic is tested without mocks.

### `swax-openapi`
- **What it provides**: the `swax.openapi` parse contract (`parse_spec`/`SpecParseError`) and the
  endpoint-extraction field templates for both formats (OpenAPI `requestBody/content` vs Swagger
  `in: body`; `responses[code].content` vs `responses[code].schema`; nested `schema` vs inlined
  `_TYPE_FIELDS`).
- **Where used**: global `Annotations`, `load_spec`, `extract_endpoints`.
- **Why chosen**: the sole parsing dependency; the authoritative template for the format-specific
  field paths and the canonical `_TYPE_FIELDS` list.
- **How exactly**: `loader.py` imports `parse_spec`/`SpecParseError` from `swax.openapi`;
  `extract_endpoints` mirrors the openapi/swagger extractor templates verbatim (paths documented above).

### `click`
- **What it provides**: the CLI facade and the `ClickException` non-zero-exit convention.
- **Where used**: global `Annotations`, `load_spec`.
- **Why chosen**: uniform error surfacing for CLI consumers.
- **How exactly**: `loader.py` raises `click.ClickException(f"failed to parse spec {exc.path}: {exc.reason}")`
  on `SpecParseError`. `extract.py` does **not** import `click` (boundary isolation).

### Imported Usages
- None. The `spec` cell declares 0 `Imports` (it is a leaf). No cross-cell practice is imported.

## `.usages/` Update

### Cell: `goga_tool_pybuggy/spec`

#### Existing Files — Consistency
- **`spec`** → `goga_tool_pybuggy/spec/.usages/spec.md`
  - Status: **current** (rewritten by the preceding `apply-architecture` stage to cover both formats).
  - Verified consistent with the contract:
    - documents `load_spec`, `detect_spec_version` (importable from the facade), `extract_endpoints`,
      `Endpoint` fields, `build_endpoint_id`;
    - "Определение версии" section explains content-based detection and `ValueError` on invalid specs;
    - "Nullable-нормализация" section covers **both** `nullable: true` and `x-nullable: true` → union
      form with `anyOf` fallback;
    - per-format semantics (OpenAPI `requestBody/responses[code].content/parameters[].schema` vs
      Swagger `in: body/responses[code].schema/inlined query fields`) match the contract's `Requirements`.
  - Additions needed: none.
  - Updates needed: none.
  - Note: `.usages/spec.md` is consumer documentation; it correctly does **not** add a CODEMANIFEST
    `Usages` reference to itself (per cookbook — `.usages/` is not a source of contractual requirements).

#### New Files
- None. The single-domain `spec.md` already covers the (extended) extraction responsibility; splitting
  would violate the one-domain-per-file rule.

## Test Stack Trace

### General Setup
- **Test root**: `tests/spec/test_extract.py` (mirror of `goga_tool_pybuggy/spec/extract.py`) plus a new
  companion for the new routine. Two structurally valid options:
  - (A) keep all `detect_spec_version` + Swagger tests inside `tests/spec/test_extract.py` (same module
    under test, `extract.py`), or
  - (B) add a dedicated `tests/spec/test_extract.py` section + leave `detect_spec_version` tests there
    too (it lives in the same `extract.py`).
  - **Recommended**: add to `tests/spec/test_extract.py` — both routines share the `extract.py` location,
    so a single mirror file is the convention-faithful choice (`<src>/module/file.py` →
    `tests/module/test_file.py`).
- **Fixtures**: inline spec dicts (pure logic over dicts — no mocks, no `tmp_path`, per `conventions`).
- **Critical migration note**: under the new contract `extract_endpoints` calls `detect_spec_version`,
  which raises `ValueError` on a spec declaring neither top-level `swagger` nor `openapi`. **Every
  existing fixture in `test_extract.py` that currently omits a version key must be augmented with a
  top-level `"openapi": "3.0.0"` key** to remain a valid (OpenAPI) spec — otherwise those tests fail
  with `ValueError`. The existing `test_extract_endpoints_empty_paths_returns_empty_list` already carries
  `"openapi": "3.0.0"` and needs no change; the rest need the key added.

### Source File Registry
- `goga_tool_pybuggy/spec/extract.py` — `detect_spec_version`, `extract_endpoints`, `_normalize_nullable`
  (extended), `_TYPE_FIELDS`.
- `goga_tool_pybuggy/spec/__init__.py` — facade; must add `detect_spec_version` to `__all__` and its
  import (4 → 5 exports).
- `goga_tool_pybuggy/spec/endpoint.py`, `endpoint_id.py`, `loader.py` — unchanged.

---

### Positive Tests

#### `test_detect_spec_version_import_from_facade`
**Setup**: none.
**Input**: facade import.
**Trace**:
```
from goga_tool_pybuggy.spec import detect_spec_version as f
  → __init__.py exports detect_spec_version (after 4→5 change)
  → f is extract.detect_spec_version
```
**Assertions**:
```
from goga_tool_pybuggy.spec import detect_spec_version as facade
assert facade is extract.detect_spec_version
```
**Sufficiency**: locks the facade re-export required by `spec.md` usage doc.

#### `test_detect_spec_version_signature`
**Setup**: `import inspect`.
**Input**: `inspect.signature(detect_spec_version)`.
**Trace**:
```
sig = inspect.signature(detect_spec_version)
  → params == ["spec"]; return annotation resolvable to str
```
**Assertions**:
```
assert list(sig.parameters) == ["spec"]
assert sig.return_annotation is str or sig.return_annotation == str
```
**Sufficiency**: pins the contract signature `(spec: dict[str, Any]) -> str`.

#### `test_detect_spec_version_swagger`
**Setup**: `spec = {"swagger": "2.0", "info": {...}, "paths": {}}`.
**Input**: `detect_spec_version(spec)`.
**Trace**:
```
detect_spec_version(spec)
  → "swagger" in spec == True
  → return "swagger"
```
**Assertions**:
```
assert detect_spec_version({"swagger": "2.0", "paths": {}}) == "swagger"
```
**Sufficiency**: Swagger 2.0 branch.

#### `test_detect_spec_version_openapi`
**Setup**: `spec = {"openapi": "3.1.0", "paths": {}}`.
**Input**: `detect_spec_version(spec)`.
**Trace**:
```
detect_spec_version(spec)
  → "swagger" in spec == False
  → "openapi" in spec == True
  → return "openapi"
```
**Assertions**:
```
assert detect_spec_version({"openapi": "3.1.0", "paths": {}}) == "openapi"
```
**Sufficiency**: OpenAPI 3.x branch.

#### `test_extract_endpoints_swagger_body_request`
**Setup**:
```
spec = {
    "swagger": "2.0",
    "paths": {
        "/clients": {
            "post": {
                "parameters": [
                    {"name": "b", "in": "body", "schema": {"type": "object", "properties": {"name": {"type": "string"}}}},
                    {"name": "limit", "in": "query", "type": "integer"},
                ],
                "responses": {"201": {"description": "created", "schema": {"type": "object"}}},
            }
        }
    },
}
```
**Input**: `extract_endpoints(spec)`.
**Trace**:
```
extract_endpoints(spec)
  → detect_spec_version(spec) == "swagger"
  → /clients / post
    → request: body param schema {"type":"object","properties":{"name":{"type":"string"}}}
    → response: {"201": {"type":"object"}}
    → query_params: {"limit": {"type":"integer"}}   # inlined type field
    → _normalize_nullable (no nullable/x-nullable) → unchanged
    → Endpoint(method="post", path="/clients", ...)
```
**Assertions**:
```
assert len(endpoints) == 1
ep = endpoints[0]
assert ep.request == {"type": "object", "properties": {"name": {"type": "string"}}}
assert ep.response == {"201": {"type": "object"}}
assert ep.query_params == {"limit": {"type": "integer"}}
assert ep.id == build_endpoint_id("post", "/clients")
```
**Sufficiency**: Swagger 2.0 request/response/query extraction paths.

#### `test_extract_endpoints_swagger_query_inlined_fields`
**Setup**: Swagger query param carrying `type`/`format`/`enum`/`default`/`description`.
```
spec = {
    "swagger": "2.0",
    "paths": {"/s": {"get": {
        "parameters": [{"name": "color", "in": "query", "type": "string",
                        "format": "hex", "enum": ["red", "green"],
                        "default": "red", "description": "pick a color",
                        "required": False, "in": "query"}],
        "responses": {"200": {"description": "ok", "schema": {}}},
    }}},
}
```
**Input**: `extract_endpoints(spec)`.
**Trace**:
```
→ swagger branch; color param inlined fields filtered to _TYPE_FIELDS
→ query_params["color"] == {"type":"string","format":"hex","enum":["red","green"],
                            "default":"red","description":"pick a color"}
   # "required" and other non-_TYPE_FIELDS dropped
```
**Assertions**:
```
assert endpoints[0].query_params["color"] == {
    "type": "string", "format": "hex", "enum": ["red", "green"],
    "default": "red", "description": "pick a color",
}
```
**Sufficiency**: `_TYPE_FIELDS` filtering for Swagger inlined query params.

#### `test_extract_endpoints_equivalent_operations_same_normalized_shape`
**Setup**: one GET + one POST declared identically in two minimal specs — one Swagger 2.0, one OpenAPI 3.x
(exact fixtures, values derived from the assertions below):
```python
swagger_spec = {
    "swagger": "2.0",
    "paths": {
        "/r/{id}": {
            "get": {
                "parameters": [{"name": "verbose", "in": "query", "type": "boolean"}],
                "responses": {"200": {"description": "ok",
                    "schema": {"type": "object", "properties": {"id": {"type": "string"}}}}},
            },
            "post": {
                "parameters": [{"name": "b", "in": "body",
                    "schema": {"type": "object", "properties": {"name": {"type": "string"}}}}],
                "responses": {"201": {"description": "created", "schema": {"type": "object"}}},
            },
        }
    },
}
openapi_spec = {
    "openapi": "3.0.3",
    "paths": {
        "/r/{id}": {
            "get": {
                "parameters": [{"name": "verbose", "in": "query", "schema": {"type": "boolean"}}],
                "responses": {"200": {"content": {"application/json": {
                    "schema": {"type": "object", "properties": {"id": {"type": "string"}}}}}}},
            },
            "post": {
                "requestBody": {"content": {"application/json": {
                    "schema": {"type": "object", "properties": {"name": {"type": "string"}}}}}},
                "responses": {"201": {"content": {"application/json": {"schema": {"type": "object"}}}}},
            },
        }
    },
}
```
**Input**: `extract_endpoints(swagger_spec)` and `extract_endpoints(openapi_spec)`.
**Trace**:
```
swagger:  detect == "swagger" → body/schema/inlined query paths
openapi:  detect == "openapi" → requestBody/content/nested schema paths
both → _normalize_nullable (no nullable) → identical Endpoint(method,path,request,response,query_params)
```
**Assertions**:
```
sw = extract_endpoints(swagger_spec)
oa = extract_endpoints(openapi_spec)
assert len(sw) == len(oa) == 2
# GET: request {}, response {"200": {id-object}}, query {"verbose": {"type":"boolean"}}
assert sw[0].request == oa[0].request == {}
assert sw[0].response == oa[0].response == {"200": {"type": "object", "properties": {"id": {"type": "string"}}}}
assert sw[0].query_params == oa[0].query_params == {"verbose": {"type": "boolean"}}
# POST: request {name-object}, response {"201": {object}}
assert sw[1].request == oa[1].request == {"type": "object", "properties": {"name": {"type": "string"}}}
assert sw[1].response == oa[1].response == {"201": {"type": "object"}}
assert sw[1].query_params == oa[1].query_params == {}
assert [e.id for e in sw] == [e.id for e in oa]
```
**Sufficiency**: the format-equivalence contract invariant (Constraints bullet 2).

#### `test_extract_endpoints_rewrites_swagger_x_nullable_to_jsonschema_union`
**Setup**: Swagger spec with `x-nullable: true` on a body schema property, a response, and a query param.
```
spec = {
    "swagger": "2.0",
    "paths": {"/n": {"post": {
        "parameters": [
            {"name": "b", "in": "body",
             "schema": {"type": "object", "properties": {"ref": {"type": "string", "x-nullable": True}}}},
            {"name": "tag", "in": "query", "type": "integer", "x-nullable": True},
        ],
        "responses": {"200": {"description": "ok",
            "schema": {"type": "object", "properties": {"err": {"type": "object", "x-nullable": True}}}}},
    }}},
}
```
**Input**: `extract_endpoints(spec)`.
**Trace**:
```
→ swagger branch
→ _normalize_nullable rewrites each x-nullable:true → type union, drops x-nullable
```
**Assertions**:
```
ep = endpoints[0]
assert ep.request == {"type": "object", "properties": {"ref": {"type": ["string", "null"]}}}
assert ep.query_params["tag"] == {"type": ["integer", "null"]}
assert ep.response["200"] == {"type": "object", "properties": {"err": {"type": ["object", "null"]}}}
```
**Sufficiency**: `x-nullable` handled symmetrically with OpenAPI `nullable` (Requirements last bullet).

#### `test_extract_endpoints_nullable_false_drops_key_without_union`
**Setup**: OpenAPI spec (`openapi: 3.0.0`) with `nullable: false` on one schema and `x-nullable: false` on another.
```python
spec = {
    "openapi": "3.0.0",
    "paths": {"/f": {"post": {
        "requestBody": {"content": {"application/json": {
            "schema": {"type": "object", "properties": {
                "a": {"type": "string", "nullable": False},
                "b": {"type": "integer", "x-nullable": False}}}}}},
        "responses": {"200": {"content": {"application/json": {"schema": {}}}}},
    }}},
}
```
**Input**: `extract_endpoints(spec)`.
**Trace**:
```
extract_endpoints(spec)
  → detect_spec_version(spec) == "openapi"
  → /f / post
    → request: requestBody.content.application/json.schema
      {"type":"object","properties":{"a":{"type":"string","nullable":False},"b":{"type":"integer","x-nullable":False}}}
    → _normalize_nullable recurses into properties a and b:
        a: pop("nullable") -> False  → no union, key dropped → {"type":"string"}
        b: pop("x-nullable") -> False → no union, key dropped → {"type":"integer"}
    → Endpoint(method="post", path="/f", request={...normalized...}, ...)
```
**Assertions**:
```python
endpoints = extract_endpoints(spec)
assert len(endpoints) == 1
assert endpoints[0].request == {
    "type": "object",
    "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
}
# no nullable / x-nullable keys; no union formed
assert "nullable" not in endpoints[0].request["properties"]["a"]
assert "x-nullable" not in endpoints[0].request["properties"]["b"]
```
**Sufficiency**: locks the `false` edge case of the combined predicate — catches regressions where `false`
accidentally adds a union (e.g. a truthy `if nullable_val or x_nullable_val:` mistake) or fails to drop the
key. Covers the behavior changed by the combined `nullable`/`x-nullable` predicate rewrite.

---

### Negative Tests

#### `test_detect_spec_version_neither_key_raises_value_error`
**Setup**: `spec = {"info": {"title": "T", "version": "1.0"}, "paths": {}}` (no `swagger`/`openapi`).
**Input**: `detect_spec_version(spec)`.
**Trace**:
```
detect_spec_version(spec)
  → "swagger" not in spec, "openapi" not in spec
  → raise ValueError
```
**Assertions**:
```
with pytest.raises(ValueError):
    detect_spec_version({"info": {"title": "T"}, "paths": {}})
with pytest.raises(ValueError):
    detect_spec_version({})
```
**Sufficiency**: invalid-spec detection rule (Requirements bullet).

#### `test_extract_endpoints_invalid_spec_raises_value_error`
**Setup**: `spec = {"paths": {"/x": {"get": {...}}}}` (paths present, no version key).
**Input**: `extract_endpoints(spec)`.
**Trace**:
```
extract_endpoints(spec)
  → step 2: detect_spec_version(spec) raises ValueError
  → propagated uncaught out of extract_endpoints
```
**Assertions**:
```
with pytest.raises(ValueError):
    extract_endpoints({"paths": {"/x": {"get": {"responses": {}}}}})
```
**Sufficiency**: the propagation contract (Constraints bullet 3) — `extract_endpoints` does not swallow
the version error.

---

### Edge Case Tests

#### `test_extract_endpoints_swagger_empty_paths_returns_empty_list`
**Setup**: `spec = {"swagger": "2.0", "info": {...}}` (valid Swagger, no `paths`).
**Input**: `extract_endpoints(spec)`.
**Trace**:
```
→ detect == "swagger"; paths = {} → no iterations
→ return []
```
**Assertions**:
```
assert extract_endpoints({"swagger": "2.0", "info": {"title": "T", "version": "1"}}) == []
```
**Sufficiency**: valid-but-pathless Swagger spec does not raise (version present).

#### `test_extract_endpoints_swagger_no_body_parameter_request_empty`
**Setup**: Swagger POST with no `in: body` parameter.
```
spec = {"swagger": "2.0", "paths": {"/p": {"post": {
    "responses": {"201": {"description": "created"}}}}}}
```
**Input**: `extract_endpoints(spec)`.
**Trace**:
```
→ swagger request extractor: no body param → request == {}
→ response == {"201": {}}
```
**Assertions**:
```
ep = endpoints[0]
assert ep.request == {}
assert ep.response == {"201": {}}
```
**Sufficiency**: the `absent fields default to {}` requirement for the Swagger branch.

#### `test_extract_endpoints_swagger_inherits_shared_path_item_parameters`
**Setup**: Swagger path-item with shared `in: query` param + operation-level `in: query` param.
```
spec = {"swagger": "2.0", "paths": {"/c/{id}": {
    "parameters": [{"name": "shared", "in": "query", "type": "string"}],
    "get": {"parameters": [{"name": "op", "in": "query", "type": "integer"}],
            "responses": {"200": {"description": "ok", "schema": {}}}}}}}
```
**Input**: `extract_endpoints(spec)`.
**Trace**:
```
→ shared_params merged with op params
→ query_params == {"shared": {"type":"string"}, "op": {"type":"integer"}}
```
**Assertions**:
```
qp = endpoints[0].query_params
assert qp == {"shared": {"type": "string"}, "op": {"type": "integer"}}
```
**Sufficiency**: path-item parameter inheritance on the Swagger branch (parity with the OpenAPI test).

> Note for the implementation agent: the **existing** OpenAPI-only tests in `test_extract.py`
> (`test_extract_endpoints_builds_endpoint_per_operation`, `..._skips_non_method_keys`,
> `..._skips_non_dict_path_item`, `..._no_application_json_returns_empty_fields`,
> `..._inherits_shared_path_item_parameters`, `..._description_default_empty_string`,
> `..._with_description`, `..._rewrites_openapi_nullable_to_jsonschema_union`,
> `..._normalizes_nullable_without_type_via_anyof`) must each get a top-level `"openapi": "3.0.0"` key
> added to their fixture dict so they remain valid specs under the new version-detection contract. Their
> expected values are otherwise unchanged (the OpenAPI extraction path is unchanged).

## Additional Instructions for the Implementation Agent

- **Order**: implement `detect_spec_version` first (no deps), then extend `_normalize_nullable` to also
  consume `x-nullable`, then branch `extract_endpoints` by version, then re-export `detect_spec_version`
  on the facade, then add/update tests.
- **Facade**: `goga_tool_pybuggy/spec/__init__.py` — add `from .extract import detect_spec_version` and
  extend `__all__` to `["Endpoint", "build_endpoint_id", "detect_spec_version", "extract_endpoints",
  "load_spec"]` (alphabetical, 4 → 5).
- **Keep the OpenAPI path bit-identical**: the existing `extract_endpoints` OpenAPI branches and the
  existing `_normalize_nullable` `nullable` behavior must not change — Swagger support is additive. The
  existing nullable tests must keep passing.
- **`_TYPE_FIELDS`**: define as a module-level tuple `("type", "format", "items", "enum", "default",
  "description", "x-nullable")` — the canonical list from `swax-openapi.md` **extended with `x-nullable`** so the
  Swagger query-param nullable keyword survives filtering and reaches `_normalize_nullable` (without it,
  `x-nullable` is dropped before normalization and the query param's nullability is silently lost — see the
  review fix below). Filter Swagger query params by it.
- **`_normalize_nullable` extension**: use a single combined predicate —
  `nullable_val = result.pop("nullable", None); x_nullable_val = result.pop("x-nullable", None);
  if nullable_val is True or x_nullable_val is True: <existing union logic>` — so both originating keys
  are dropped and the union logic is shared.
- **No new deps**: pure-stdlib + existing `Endpoint`. Do not import `click` in `extract.py` (boundary
  isolation). `jsonschema` is referenced only in the nullable rationale; it is not imported here.
- **Existing fixture migration**: add `"openapi": "3.0.0"` to every existing `test_extract.py` fixture
  that lacks a version key (see the test-stack-trace note). Do not change their expected values.
- **`ValueError` is intentional**: do not catch it inside `extract_endpoints`; the propagation is the
  contract. CLI-facing error mapping (if any) is the consumer's concern, not this cell's.
- **Consumers need no changes**: `commands/{info,list,generate}` and `output`/`api.asserts` call
  `extract_endpoints(spec)`; the signature is unchanged and the OpenAPI behavior is preserved, so their
  tests are unaffected.
- **Validation**: `pytest tests/spec/ -x` (green), `ruff check goga_tool_pybuggy/spec/`,
  `python -c "from goga_tool_pybuggy.spec import detect_spec_version, extract_endpoints, Endpoint,
  build_endpoint_id, load_spec"`, and `goga lint goga_tool_pybuggy/spec` (expect only the 3 baseline
  `[usage_filepath_exists]` errors — no `[annotation_links_exists]`).
