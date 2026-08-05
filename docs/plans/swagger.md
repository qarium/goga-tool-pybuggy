# Plan: `swagger`

## Purpose

Add **Swagger 2.0** support to endpoint extraction in the `spec` cell (`goga_tool_pybuggy/spec`),
alongside the existing OpenAPI 3.x path. After implementation the cell must:

- expose a new Routine `detect_spec_version(spec) -> str` that classifies a parsed spec as
  `"swagger"` or `"openapi"` from its content (top-level `swagger` vs `openapi` key), raising
  `ValueError` when neither is present;
- make `extract_endpoints(spec)` route field extraction by the detected format and normalize **both**
  the OpenAPI `nullable` and the Swagger `x-nullable` keywords into a single JSON-Schema union shape
  on `Endpoint`;
- re-export `detect_spec_version` from the `goga_tool_pybuggy.spec` facade (4 → 5 exports);
- keep the OpenAPI extraction path **bit-identical** (Swagger support is purely additive).

The most important gaps between contract and code:

- `extract.py` currently only handles OpenAPI 3.x — no version detection, no Swagger branches;
- `_normalize_nullable` only rewrites OpenAPI `nullable`, not Swagger `x-nullable`;
- `_TYPE_FIELDS` does not exist (Swagger query params use inlined type fields, filtered by this
  whitelist, which must include `x-nullable` so the keyword reaches normalization);
- the facade `__init__.py` does not export `detect_spec_version`.

Strategy: implement `detect_spec_version` first (no dependencies), then extend `extract_endpoints`
with version routing + format-specific extractors + the extended normalizer in one cohesive task
(all the additive behavior lives in `extract.py` and is observable only through `extract_endpoints`),
then re-export on the facade, then add/complete tests. The `CODEMANIFEST` already declares the new
and changed entities — it is **read-only** for the implementation agent.

---

## Context

### Contract Surface

**Entity: `detect_spec_version`** (NEW — Routine, `location: extract.py`)
- Signature: `detect_spec_version(spec: dict[str, Any]) -> version: str`
- Facade obligation: must be importable from `goga_tool_pybuggy.spec` (added to `__all__`, 4 → 5).
- Mutations: none.
- Semantic requirements from description:
  - Determines the spec format by inspecting the parsed spec's **content**, independent of the
    declarative config type field.
  - `"swagger"` key present → `"swagger"` (Swagger 2.0); else `"openapi"` key present → `"openapi"`
    (OpenAPI 3.x); else raise `ValueError` (a spec declaring neither contradicts both specs).
  - Pure function — no I/O, no parsing.
- Imported dependencies: none (leaf cell, 0 `Imports`).
- Annotation context (cascade):
  - Global `Annotations` — "Extraction routes each spec by version detected from its content
    (swagger '2.0' vs openapi '3.x') and normalizes both formats to the same JSON-Schema shape on
    `Endpoint`." + `conventions` / `swax-openapi` / `click` usage hints.
  - Type-level `Requirements` — detection by spec content only; a spec with neither top-level key is
    invalid → `ValueError`.
  - Type-level `Constraints` — pure function; raises `ValueError` on an unrecognized format.

**Entity: `extract_endpoints`** (CHANGED — Routine, `location: extract.py`)
- Signature: `extract_endpoints` signature is unchanged: `extract_endpoints(spec: dict[str, Any]) -> endpoints: list[Endpoint]`.
- Facade obligation: already importable (unchanged export); signature unchanged.
- Mutations: none.
- Semantic requirements from description:
  - Algorithm gains: step 2 — detect format via `detect_spec_version`; step 4 — field extraction now
    branches on the detected version.
  - Swagger 2.0 field paths: request from the `in: body` parameter's root `schema`; response from
    `responses[code].schema` directly (no `content` wrapper); query params from each `in: query`
    parameter via its inlined `type/format/items/enum/default/description/x-nullable` fields
    (the canonical `_TYPE_FIELDS` set, which **includes** `x-nullable` so it survives field filtering
    and reaches normalization).
  - Nullable normalization extended: OpenAPI `nullable: true` **and** Swagger `x-nullable: true` both
    become a type list including `"null"` (with an `anyOf` fallback when a single type cannot host the
    union); the originating key is dropped; recursion through `properties`, `items`,
    `additionalProperties`, `anyOf`/`oneOf`/`allOf`.
  - Constraints: format-equivalence (both formats → same normalized shape for equivalent
    operations); invalid-spec `ValueError` propagated from `detect_spec_version` without swallowing;
    no basePath/servers merge; no consumes/produces; no formData/file uploads.
- Imported dependencies: `Endpoint` (same cell, `endpoint.py`).
- Annotation context (cascade):
  - Global `Annotations` (as above).
  - Type-level `Algorithm` (5 steps incl. version detection + per-version field extraction).
  - Type-level `Requirements` (skip non-method keys; inherit+merge path-item params; primary
    `application/json`; absent → `{}`; per-format request/response/query field paths; nullable
    normalization).
  - Type-level `Constraints` (pure logic; format equivalence; `ValueError` propagation; explicit
    out-of-scope items).

**Entity (internal helper): `_normalize_nullable`** (CHANGED — private function, `extract.py`)
- Extended to also consume Swagger `x-nullable` symmetrically with OpenAPI `nullable`, via a single
  combined predicate that drops both originating keys and shares the union-form rewrite logic.

**Entity (internal helper): `_TYPE_FIELDS`** (NEW — module-level constant, `extract.py`)
- `("type", "format", "items", "enum", "default", "description", "x-nullable")` — whitelist used to
  filter Swagger inlined query-param fields; `x-nullable` is intentionally included (review fix) so
  the keyword reaches `_normalize_nullable`.

### Re-exports

- **Name:** `detect_spec_version`
- **Source:** `extract.py` (`from .extract import detect_spec_version`).
- **Facade obligation:** must be importable from `goga_tool_pybuggy.spec`.
- Implementation: add the import line and extend `__all__` to
  `["Endpoint", "build_endpoint_id", "detect_spec_version", "extract_endpoints", "load_spec"]`
  (alphabetical, 4 → 5).

### Usages Context

- **`conventions`** — project-wide Python rules: pydantic `kw_only` models, relative imports inside
  the cell, Google docstrings (`Args`/`Returns`/`Raises`), test structure mirroring src
  (`tests/spec/test_<module>.py`), pytest/ruff tooling, pure-logic tests without mocks. Mandatory
  baseline for every cell.
- **`swax-openapi`** — the `swax.openapi` parse contract (`parse_spec`/`SpecParseError`) and the
  endpoint-extraction field templates for both formats (OpenAPI `requestBody/content` vs Swagger
  `in: body`; `responses[code].content` vs `responses[code].schema`; nested `schema` vs inlined
  `_TYPE_FIELDS`). Authoritative template for the format-specific field paths and the canonical
  `_TYPE_FIELDS` list.
- **`click`** — the CLI facade and the `ClickException` non-zero-exit convention. Used in `loader.py`
  only; `extract.py` does **not** import `click` (boundary isolation).

### Imported Usages

None. The `spec` cell declares 0 `Imports` (it is a leaf). No cross-cell practice is imported.

### Local Usages

- **File path:** `goga_tool_pybuggy/spec/.usages/spec.md`
- **Functional category:** consumer patterns for spec parsing + endpoint extraction (both Swagger
  2.0 and OpenAPI 3.x).
- **Status:** **current** — rewritten by the preceding `apply-architecture` stage to cover both
  formats; documents `load_spec`, `detect_spec_version`, `extract_endpoints`, `Endpoint` fields,
  `build_endpoint_id`; explains content-based version detection, `ValueError` on invalid specs, and
  nullable-normalization for **both** `nullable: true` and `x-nullable: true`.
- **Related entities:** `detect_spec_version`, `extract_endpoints`, `Endpoint`, `load_spec`,
  `build_endpoint_id`.
- **Description:** consumer-facing documentation; no CODEMANIFEST `Usages` reference to itself (per
  cookbook).
- **Creation task reference:** none — `.usages/spec.md` is already consistent; **no new file and no
  update is required** (splitting would violate the one-domain-per-file rule).

### External Dependencies

- `swax.openapi` — `parse_spec`, `SpecParseError` (consumed by `loader.py`; `extract.py` only mirrors
  its documented field templates, does not import it).
- `click` — `ClickException` (`loader.py` only).
- `pydantic` — `Endpoint` model (`ConfigDict(kw_only=True, extra="forbid")`).
- `pytest`, `ruff` — test runner / linter.
- (stdlib) `typing.Any`, `inspect` — type hints / signature introspection in tests.

---

## Facts

- The `spec` cell is a **leaf** (0 `Imports`) — no cross-cell type/practice dependencies.
- `Endpoint` is a pydantic model with `kw_only=True, extra="forbid"`; its constructor takes exactly
  six kwargs: `method`, `path`, `request`, `response`, `query_params`, `description`; `id` is a
  computed field via `build_endpoint_id` (not a constructor input).
- Consumers (`output`, `commands/{list,info,generate}`, `api/asserts`) consume
  `extract_endpoints`/`Endpoint`/`load_spec`/`build_endpoint_id` — none of which change signature;
  **consumers are isolated; no consumer edits are required.**
- `extract.py` is pure logic over the already-dereferenced dict (Prance inlines `$ref` in `load_spec`)
  — no I/O, no `$ref` resolution, no `click` import, no logging.
- `_normalize_nullable` rebuilds dicts/lists (no in-place mutation) → thread-safe; original input is
  not mutated.
- `CODEMANIFEST` already declares `detect_spec_version` and the extended `extract_endpoints`
  (Requirements bullet on Swagger query fields reconciled to the canonical
  `type/format/items/enum/default/description/x-nullable` list, with `x-nullable` intentionally
  included). It is **read-only** for the implementation agent.
- The `.usages/spec.md` consumer doc already covers both formats; no `.usages/` change is planned.
- `goga lint` reports only the 3 baseline `[usage_filepath_exists]` errors (environment limitation —
  usage paths resolved relative to the cell directory, not the project root; identical on every cell)
  and 0 `[annotation_links_exists]` errors.

---

## Gap Analysis

- **Missing contract entities:** `detect_spec_version` routine; `_TYPE_FIELDS` constant.
- **Missing facade exposure:** `detect_spec_version` not in `__init__.py` `__all__`.
- **Incorrect/missing behavior in `extract_endpoints`:** no version detection; request/response/query
  extracted only via the OpenAPI structure; no Swagger branches.
- **Behavioral mismatch in `_normalize_nullable`:** only rewrites OpenAPI `nullable`; does not consume
  Swagger `x-nullable`; the predicate `if "nullable" in result and result.pop("nullable") is True`
  must become a combined predicate that pops **both** `nullable` and `x-nullable`.
- **Existing code that can be reused:** the OpenAPI extraction logic in `extract_endpoints`
  (request/response/query), the existing `_normalize_nullable` `nullable` union logic and `anyOf`
  fallback (both pre-existing sub-cases preserved). The refactor reuses these verbatim in the OpenAPI
  branch.
- **Test coverage gaps:** no Swagger 2.0 tests; no `x-nullable` normalization tests; no
  format-equivalence test; existing fixtures lack a top-level version key and will raise `ValueError`
  once `extract_endpoints` calls `detect_spec_version`.
- **No new cells, no new packages, no new interfaces at cell level.**

---

## Tasks

> **Package ordering rule**: this plan touches a single cell (`goga_tool_pybuggy/spec`); all coding
> tasks for it are completed before the integration-test task. Within each coding task, contract
> tests are written first (TDD workflow). CODEMANIFEST files are **read-only** — if implementation
> does not match the contract, fix the implementation, never the contract.

### Task 1: `detect_spec_version` routine + facade re-export (TDD coding)

**Context.** Implement the NEW Routine `detect_spec_version(spec: dict[str, Any]) -> version: str`
in `location` `goga_tool_pybuggy/spec/extract.py`, and re-export it from the facade
`goga_tool_pybuggy/spec/__init__.py` (4 → 5 exports). This routine has no dependencies and is the
foundation for Task 2 (which wires `extract_endpoints` to route by version). It classifies a parsed
spec by its **content** only — never by the declarative config type field. **Do NOT modify
`extract_endpoints` in this task** (it must remain OpenAPI-only and bit-identical so existing tests
stay green); only add the new routine + the facade re-export.

**Usages relevant to this task:**
- `conventions`: Google docstring with `Args`/`Returns`/`Raises`; type hints mandatory; pure-logic
  test without mocks; test in `tests/spec/test_extract.py` (mirror of `extract.py`); test name shape
  `test_<what>_<scenario>`.
- `swax-openapi`: the version-detection contract — content-based detection by top-level `swagger`
  (Swagger 2.0) vs `openapi` (OpenAPI 3.x) key; `ValueError` on a spec declaring neither.

**Contract trace for `detect_spec_version(spec)` (transfer verbatim from design):**

```
Chain
1. Input: spec: dict[str, Any] — the dereferenced spec dict (output of load_spec); passed by extract_endpoints.
2. Step: check "swagger" in spec → checkpoint: Swagger 2.0 specs carry a top-level swagger key
   (e.g. "swagger": "2.0"). If present, return "swagger".
3. Step: else check "openapi" in spec → checkpoint: OpenAPI 3.x specs carry a top-level openapi key
   (e.g. "openapi": "3.0.3"). If present, return "openapi".
4. Step: else raise ValueError → checkpoint: a spec declaring neither key contradicts both
   specifications and is invalid; the error is the contract's signal.
5. Output: version: str — "swagger" or "openapi" (or ValueError propagates).

Algorithm:
1. IF "swagger" in spec: return "swagger"
2. ELIF "openapi" in spec: return "openapi"
3. ELSE: raise ValueError("spec declares neither a swagger nor an openapi version")

Edge Cases:
- Spec carrying BOTH swagger and openapi keys (malformed) → returns "swagger" (checked first; deterministic).
- Empty dict {} → raises ValueError.
- Spec with a top-level version key but empty/missing paths → returns the format normally (path-lessness
  is extract_endpoints' concern, not the version detector's).
```

**Algorithm behavioral requirements (from CODEMANIFEST annotation):** detection by spec content only;
a spec with neither top-level key is invalid → `ValueError`. **Constraint:** pure function — no I/O,
no parsing; raises `ValueError` on an unrecognized format. **Do not catch** `ValueError` anywhere
local — it is the contract's invalid-spec signal.

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If
implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 (DECLARATION)** — declare this is Task 1: `detect_spec_version` routine + facade re-export.
- [ ] **Contract tests** in `tests/spec/test_extract.py` (expected to fail at this stage — routine + re-export not yet present):
  - [ ] `test_detect_spec_version_import_from_facade` — assert `from goga_tool_pybuggy.spec import detect_spec_version as facade; assert facade is extract.detect_spec_version` (locks the facade re-export required by `.usages/spec.md`).
  - [ ] `test_detect_spec_version_signature` — `import inspect`; assert `list(inspect.signature(detect_spec_version).parameters) == ["spec"]` and return annotation resolves to `str`.
- [ ] **Code**: add Routine `detect_spec_version(spec: dict[str, Any]) -> str` to `goga_tool_pybuggy/spec/extract.py` — implement the Algorithm above verbatim: `if "swagger" in spec: return "swagger"`; `elif "openapi" in spec: return "openapi"`; `else: raise ValueError(...)`. Add a Google docstring (`Args`/`Returns`/`Raises`).
- [ ] **Code (facade re-export)**: in `goga_tool_pybuggy/spec/__init__.py` add `from .extract import detect_spec_version` and extend `__all__` to the alphabetical 5-element list `["Endpoint", "build_endpoint_id", "detect_spec_version", "extract_endpoints", "load_spec"]`; update the module docstring's export sentence to include `detect_spec_version`.
- [ ] **Interface verification**: `python -c "from goga_tool_pybuggy.spec import detect_spec_version; import inspect; assert list(inspect.signature(detect_spec_version).parameters)==['spec']"` — import resolves from the facade and signature matches.
- [ ] **Logic tests** in `tests/spec/test_extract.py` (positive + negative + edge):
  - [ ] `test_detect_spec_version_swagger` — `assert detect_spec_version({"swagger": "2.0", "paths": {}}) == "swagger"`.
  - [ ] `test_detect_spec_version_openapi` — `assert detect_spec_version({"openapi": "3.1.0", "paths": {}}) == "openapi"`.
  - [ ] `test_detect_spec_version_neither_key_raises_value_error` (negative) — `with pytest.raises(ValueError): detect_spec_version({"info": {"title": "T"}, "paths": {}})` and `with pytest.raises(ValueError): detect_spec_version({})`.
- [ ] **Debugging**: `pytest tests/spec/test_extract.py -k detect_spec_version -x` — fix implementation code (not test code) until all `detect_spec_version` tests pass; confirm the **existing** `test_extract.py` tests still pass (`pytest tests/spec/test_extract.py -x`) since `extract_endpoints` is untouched.
- [ ] **Contract re-verification**: `detect_spec_version` is importable from `goga_tool_pybuggy.spec`, signature is `(spec: dict[str, Any]) -> str`, behavior matches the CODEMANIFEST annotation; `extract_endpoints` behavior unchanged (existing tests green).
- [ ] **Lint**: `ruff check goga_tool_pybuggy/spec/` and `ruff check tests/spec/` — fix formatting; apply decomposition if necessary.

### Task 2: Swagger 2.0 support in `extract_endpoints` (version routing + format extractors + `_TYPE_FIELDS` + `_normalize_nullable` `x-nullable` extension) (TDD coding)

**Context.** Extend the CHANGED Routine `extract_endpoints(spec: dict[str, Any]) -> list[Endpoint]`
in `location` `goga_tool_pybuggy/spec/extract.py` to route field extraction by the version detected
via `detect_spec_version` (from Task 1), add Swagger 2.0 request/response/query extraction, add the
module constant `_TYPE_FIELDS`, and extend `_normalize_nullable` to also consume Swagger
`x-nullable`. All these changes live in `extract.py` and are observable only through
`extract_endpoints`, so they form one cohesive task. **Keep the OpenAPI path bit-identical** —
Swagger support is additive; the existing OpenAPI extraction logic and the existing `nullable`
behavior must not change.

**Usages relevant to this task:**
- `conventions`: pure-logic tests without mocks; inline spec dicts as fixtures; test mirror
  `tests/spec/test_extract.py`; `@pytest.mark.parametrize` for boundary cases if useful;
  `pytest.raises` for expected exceptions.
- `swax-openapi`: the authoritative field templates for both formats — OpenAPI
  `requestBody/content/application/json/schema` vs Swagger `in: body` parameter's root `schema`;
  OpenAPI `responses[code].content/application/json/schema` vs Swagger `responses[code].schema` (no
  `content` wrapper); OpenAPI query nested `schema` vs Swagger query inlined `_TYPE_FIELDS`; and the
  canonical `_TYPE_FIELDS = ("type", "format", "items", "enum", "default", "description", "x-nullable")`.

**Interaction diagram (transfer verbatim from design):**

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
```

**Algorithm for `extract_endpoints` (transfer verbatim from design — implement this structure):**

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

**Format-routed extractors (the Requirements field paths — transfer verbatim from design):**

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

**`_normalize_nullable` extension (transfer verbatim from design — combined predicate):**

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

> Key change vs the current code: replace
> `if "nullable" in result and result.pop("nullable") is True:` with the combined predicate
> `nullable_val = result.pop("nullable", None); x_nullable_val = result.pop("x-nullable", None);
>  if nullable_val is True or x_nullable_val is True:` so both originating keys are dropped and the
> union logic is shared. Both keys are popped regardless of value (so `false` drops the key without
> forming a union — see the `nullable:false`/`x-nullable:false` edge case below).

**Critical migration note (from design):** under the new contract `extract_endpoints` calls
`detect_spec_version`, which raises `ValueError` on a spec declaring neither top-level `swagger` nor
`openapi`. **Every existing `test_extract.py` fixture that omits a version key must be augmented with
a top-level `"openapi": "3.0.0"` key** to remain a valid (OpenAPI) spec — otherwise those tests fail
with `ValueError`. `test_extract_endpoints_empty_paths_returns_empty_list` already carries
`"openapi": "3.0.0"` and needs no change; the rest need the key added. **Do not change their expected
values** — the OpenAPI extraction path is unchanged.

**Existing fixtures requiring the `"openapi": "3.0.0"` key (from design note):**
`test_extract_endpoints_builds_endpoint_per_operation`, `..._skips_non_method_keys`,
`..._skips_non_dict_path_item`, `..._no_application_json_returns_empty_fields`,
`..._inherits_shared_path_item_parameters`, `..._description_default_empty_string`,
`..._with_description`, `..._rewrites_openapi_nullable_to_jsonschema_union`,
`..._normalizes_nullable_without_type_via_anyof`.

**Constraints / out-of-scope (from CODEMANIFEST):** pure logic over `spec` (no I/O, no `$ref`
resolution); both formats yield the same normalized shape for equivalent operations; `ValueError`
from `detect_spec_version` propagated uncaught; do **not** merge basePath/servers into the path; do
**not** account for consumes/produces (media-type priority stays `application/json`); do **not**
extract formData/file-upload parameters (outside the query_params model). `extract.py` does **not**
import `click` (boundary isolation).

**CRITICAL: `CODEMANIFEST` files — read-only contract definitions. Do NOT modify them. If
implementation does not match the contract, fix the implementation — never fix the contract.**

- [ ] **STEP 0 (DECLARATION)** — declare this is Task 2: Swagger 2.0 support in `extract_endpoints`.
- [ ] **Contract tests** in `tests/spec/test_extract.py` (the signature is unchanged, so the existing
  `test_extract_endpoints_import_from_facade` and `test_extract_endpoints_signature` already cover the
  contract surface; no new contract tests needed for Task 2 — confirm they still pass after the
  refactor).
- [ ] **Code**: add module constant `_TYPE_FIELDS = ("type", "format", "items", "enum", "default", "description", "x-nullable")` to `goga_tool_pybuggy/spec/extract.py` (with the review-fix comment explaining why `x-nullable` is included).
- [ ] **Code**: extend `_normalize_nullable` with the combined predicate above — pop both `nullable` and `x-nullable`, form the union when either `is True`, drop both keys unconditionally; preserve the existing `anyOf` fallback sub-cases (append to existing `anyOf`, else synthesize `[{"type": "null"}]`).
- [ ] **Code**: refactor `extract_endpoints` to call `version = detect_spec_version(spec)` first (propagates `ValueError`), then route request/response/query extraction through the format-routed extractors above (introduce `_extract_request`/`_extract_responses`/`_extract_query_params` helpers, or inline the branches — keep the OpenAPI branch bit-identical to the current logic), apply `_normalize_nullable` to request, each response schema, and each query-param schema before constructing `Endpoint`.
- [ ] **Code (fixture migration)**: add a top-level `"openapi": "3.0.0"` key to every existing `test_extract.py` fixture listed above that lacks a version key (do NOT change expected values).
- [ ] **Interface verification**: `python -c "from goga_tool_pybuggy.spec import extract_endpoints"` imports cleanly; existing OpenAPI tests still pass — `pytest tests/spec/test_extract.py -k "openapi or nullable or per_operation or non_method or non_dict or application_json or shared_path or description or signature or import or empty_paths" -x`.
- [ ] **Logic tests** in `tests/spec/test_extract.py` (positive + negative + edge — fixtures/trace/assertions transferred verbatim from the design's Test Stack Trace):
  - [ ] `test_extract_endpoints_swagger_body_request` (positive) — Swagger spec `/clients` POST: body param `schema` → request, `responses[201].schema` → response, inlined `in: query` `type: integer` → query. Assert `ep.request == {"type":"object","properties":{"name":{"type":"string"}}}`, `ep.response == {"201":{"type":"object"}}`, `ep.query_params == {"limit":{"type":"integer"}}`, `ep.id == build_endpoint_id("post","/clients")`. (Use the design's exact fixture dict.)
  - [ ] `test_extract_endpoints_swagger_query_inlined_fields` (positive) — Swagger query param `color` carrying `type/format/enum/default/description` + `required`/extra keys; assert `query_params["color"] == {"type":"string","format":"hex","enum":["red","green"],"default":"red","description":"pick a color"}` (`required` and other non-`_TYPE_FIELDS` dropped).
  - [ ] `test_extract_endpoints_rewrites_swagger_x_nullable_to_jsonschema_union` (positive) — Swagger spec with `x-nullable: true` on body property `ref`, response property `err`, and query param `tag`. Assert `ep.request == {"type":"object","properties":{"ref":{"type":["string","null"]}}}`, `ep.query_params["tag"] == {"type":["integer","null"]}`, `ep.response["200"] == {"type":"object","properties":{"err":{"type":["object","null"]}}}`. (This is the review-fix regression test — `x-nullable` must survive `_TYPE_FIELDS` filtering and be normalized.)
  - [ ] `test_extract_endpoints_nullable_false_drops_key_without_union` (edge) — OpenAPI spec (`openapi: 3.0.0`) with `nullable: false` on property `a` and `x-nullable: false` on property `b`. Assert `ep.request == {"type":"object","properties":{"a":{"type":"string"},"b":{"type":"integer"}}}`, `"nullable" not in ...["a"]`, `"x-nullable" not in ...["b"]` (key dropped, no union formed — locks the `false` edge of the combined `is True` predicate).
  - [ ] `test_extract_endpoints_swagger_no_body_parameter_request_empty` (edge) — Swagger POST with no `in: body` param; assert `ep.request == {}`, `ep.response == {"201": {}}`.
  - [ ] `test_extract_endpoints_swagger_inherits_shared_path_item_parameters` (edge) — Swagger path-item with shared `in: query` param + operation-level `in: query` param; assert `qp == {"shared":{"type":"string"},"op":{"type":"integer"}}`.
- [ ] **Debugging**: `pytest tests/spec/test_extract.py -x` — fix implementation code (not test code) until ALL tests pass, including the migrated OpenAPI fixtures and the new Swagger tests.
- [ ] **Contract re-verification**: `extract_endpoints` signature unchanged `(spec: dict[str, Any]) -> list[Endpoint]`; facade importable; OpenAPI behavior bit-identical (existing OpenAPI tests green); Swagger branches produce normalized `Endpoint`s; `ValueError` propagated uncaught.
- [ ] **Lint**: `ruff check goga_tool_pybuggy/spec/` and `ruff check tests/spec/` — fix formatting; apply decomposition if necessary.

### Task 3: Integration tests — format equivalence + invalid-spec propagation + Swagger path-less spec (integration tests)

**Context.** Verify the cross-format and cross-entity invariants of `extract_endpoints` that span
both the Swagger and OpenAPI branches (Task 2) and the version detector (Task 1): the
**format-equivalence** contract invariant (Constraints bullet 2 — equivalent operations in Swagger
2.0 and OpenAPI 3.x yield the same normalized schema shape) and the **invalid-spec `ValueError`
propagation** contract (Constraints bullet 3 — `extract_endpoints` does not swallow the version
error). Plus the valid-but-path-less Swagger edge case (version present, no `paths`). These tests
reside in `tests/spec/test_extract.py` (single-module integration over `extract_endpoints`).

**CRITICAL: `CODEMANIFEST` files are read-only contract definitions.** These integration tests assert the
contract invariants; if a test contradicts the contract, fix the code/implementation — never modify
the `CODEMANIFEST`.

**Usages relevant to this task:**
- `conventions`: pure-logic tests without mocks; inline spec dicts as fixtures; `pytest.raises` for
  expected exceptions; test mirror `tests/spec/test_extract.py`.
- `swax-openapi`: the equivalence template — both formats reduce to the same JSON-Schema fragment
  for equivalent operations; equivalent-operation fixtures (Swagger body/schema/inlined vs OpenAPI
  requestBody/content/nested schema).

**Format-equivalence trace (transfer verbatim from design):**

```
swagger:  detect == "swagger" → body/schema/inlined query paths
openapi:  detect == "openapi" → requestBody/content/nested schema paths
both → _normalize_nullable (no nullable) → identical Endpoint(method,path,request,response,query_params)
```

**Invalid-spec propagation trace (transfer verbatim from design):**

```
extract_endpoints(spec)
  → step 2: detect_spec_version(spec) raises ValueError
  → propagated uncaught out of extract_endpoints
```

**Fixtures (transfer verbatim from design — exact `swagger_spec` / `openapi_spec` dicts, one GET + one POST each):** use the `swagger_spec` and `openapi_spec` fixtures from the design's
`test_extract_endpoints_equivalent_operations_same_normalized_shape` Setup verbatim (GET:
`/r/{id}` with `in: query` `verbose: boolean` + `responses[200]` object-with-`id`; POST:
`in: body`/`requestBody` object-with-`name` + `responses[201]` object).

- [ ] Create/extend tests in `tests/spec/test_extract.py`.
- [ ] `test_extract_endpoints_equivalent_operations_same_normalized_shape` — `sw = extract_endpoints(swagger_spec)`, `oa = extract_endpoints(openapi_spec)`; assert `len(sw) == len(oa) == 2`; GET row: `sw[0].request == oa[0].request == {}`, `sw[0].response == oa[0].response == {"200":{"type":"object","properties":{"id":{"type":"string"}}}}`, `sw[0].query_params == oa[0].query_params == {"verbose":{"type":"boolean"}}`; POST row: `sw[1].request == oa[1].request == {"type":"object","properties":{"name":{"type":"string"}}}`, `sw[1].response == oa[1].response == {"201":{"type":"object"}}`, `sw[1].query_params == oa[1].query_params == {}`; assert `[e.id for e in sw] == [e.id for e in oa]` (the format-equivalence contract invariant).
- [ ] `test_extract_endpoints_invalid_spec_raises_value_error` (negative) — `with pytest.raises(ValueError): extract_endpoints({"paths": {"/x": {"get": {"responses": {}}}}})` (paths present, no version key) — verifies `extract_endpoints` propagates `ValueError` without swallowing.
- [ ] `test_extract_endpoints_swagger_empty_paths_returns_empty_list` (edge) — `assert extract_endpoints({"swagger": "2.0", "info": {"title": "T", "version": "1"}}) == []` (valid Swagger, no `paths` → does not raise).
- [ ] Run validation: `pytest tests/spec/test_extract.py -x` — all tests green; `pytest tests/spec/ -x` — full cell suite green.

---

## Validation Commands

- `pytest tests/spec/test_extract.py -x`: Run the `spec` extraction tests (contract + logic + integration for `extract.py`).
- `pytest tests/spec/ -x`: Run the full `spec` cell test suite.
- `ruff check goga_tool_pybuggy/spec/` and `ruff check tests/spec/`: Lint/format the cell source and its tests.
- `python -c "from goga_tool_pybuggy.spec import detect_spec_version, extract_endpoints, Endpoint, build_endpoint_id, load_spec"`: Verify the facade exposes all 5 contract entities (incl. the new `detect_spec_version`).
- `goga lint goga_tool_pybuggy/spec`: Cell contract lint — expect only the 3 baseline `[usage_filepath_exists]` errors (environment limitation) and **0** `[annotation_links_exists]` errors.
- `python -c "import inspect; from goga_tool_pybuggy.spec import detect_spec_version; print(list(inspect.signature(detect_spec_version).parameters))"`: Pin the `detect_spec_version` signature `['spec']`.

---

## Completion Criteria

- [ ] Every contract entity is implemented in the correct `location` (`detect_spec_version`, `extract_endpoints`, `_normalize_nullable`, `_TYPE_FIELDS` in `extract.py`).
- [ ] Every contract entity is accessible from the facade (`detect_spec_version` added to `__all__`, 4 → 5).
- [ ] `extract_endpoints` API shape matches the declared contract (signature unchanged: `(spec: dict[str, Any]) -> list[Endpoint]`).
- [ ] Descriptions are reflected in behavior (version routing, format-specific field paths, `x-nullable` normalization, format equivalence, `ValueError` propagation).
- [ ] Contract dependencies are met (`Endpoint` constructor kwargs; `detect_spec_version` input from `extract_endpoints`).
- [ ] Re-exports are accessible from the facade (`detect_spec_version` importable).
- [ ] Every coding task followed the TDD workflow (contract tests → code → verification → logic tests → debugging → re-verification → lint).
- [ ] Contract tests and logic tests cover facade, API, and behavior within each coding task.
- [ ] Integration tests exist where cross-entity/cross-format scenarios require them (format equivalence, invalid-spec propagation).
- [ ] No package boundary was expanded (single cell; no new cells/packages; no `click` import in `extract.py`).
- [ ] `CODEMANIFEST` files were not modified (contract is read-only).
- [ ] All validation commands pass (`pytest tests/spec/ -x`, `ruff check`, facade import, `goga lint` baseline only).
- [ ] Every Usages entry is mentioned in at least one task (`conventions`, `swax-openapi`, `click`).
