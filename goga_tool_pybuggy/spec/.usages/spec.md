# goga_tool_pybuggy.spec — spec parsing and endpoint extraction

## Domain

Consumption patterns of the cell `goga_tool_pybuggy.spec`: parsing a spec file into a dict and extracting endpoints (method+path plus expanded schemas) for **Swagger 2.0 and OpenAPI 3.x** specifications. The cell detects the format automatically from the spec content. Target audience: consumer teams and the formatting cell.

## Spec file parsing

```python
from goga_tool_pybuggy.spec import load_spec

spec = load_spec(spec_path)  # pathlib.Path; $ref already inlined by Prance
```

On a parse error, `load_spec` raises `click.ClickException` (a mapping of `SpecParseError` from swax).

## Version detection

```python
from goga_tool_pybuggy.spec import detect_spec_version

version = detect_spec_version(spec)  # "swagger" (Swagger 2.0) | "openapi" (OpenAPI 3.x)
```

The version is detected by the presence of a top-level `swagger` key versus `openapi` — not by the declarative `SpecEntry.type`. A spec with neither key is invalid — `detect_spec_version` raises `ValueError`. This version drives the choice of the extraction path inside `extract_endpoints`; the consumer usually does not need to call `detect_spec_version` manually.

## Endpoint extraction

```python
from goga_tool_pybuggy.spec import extract_endpoints

endpoints = extract_endpoints(spec)  # list[Endpoint], one per method+path
for ep in endpoints:
    ep.id  # 'clients_startup_get' — computed via build_endpoint_id
    ep.method  # 'get' (lowercase)
    ep.path  # '/clients/{id}'
    ep.request  # expanded request body schema (or {})
    ep.response  # {status: schema}
    ep.query_params  # {name: schema}
```

The output semantics are identical across formats: for OpenAPI 3.x, the cell extracts request/response/query from the `requestBody`/`responses[code].content`/`parameters[].schema` structure; for Swagger 2.0 — from the `in: body` parameter/`responses[code].schema`/inline fields of the `in: query` parameter. Given the same operation semantics, both formats produce the same normalized `Endpoint` model.

## Nullable normalization

The schemas in `request`, `response`, and `query_params` are already **nullable-normalized** for JSON-Schema: OpenAPI `nullable: true` and Swagger `x-nullable: true` are rewritten into union form (`type` as a list that includes `"null"`, with an `anyOf` fallback when a single `type` cannot express the union), and the `nullable`/`x-nullable` keys are removed. The `jsonschema` validator ignores both keywords, so the cell performs the normalization once, at the parsing boundary — the consumer does not need to normalize the schemas again.

## Endpoint identifier

`build_endpoint_id(method, path)` is a pure function; `Endpoint.id` is computed from it. It is deterministic: the same method+path yields the same id; collisions are handled by the consumer.

`Endpoint.id` is guaranteed to be a **valid Python identifier**: path hyphens are normalized to `_` (for example, `/clients/payment-details` → `clients_payment_details_post`). This guarantee matters because the fixture generator uses the id as the pytest fixture name and as the package directory name during fixture generation — without the normalization, the generated module would be syntactically invalid.

## Preconditions

- `spec` must be fully dereferenced (use `load_spec`; do not dereference `$ref` manually).
- Extraction is pure logic over a dict, tested without mocks.
