# Internals — Spec Parsing

The `goga_tool_pybuggy.spec` module parses a specification file into a dict and extracts
endpoints (method + path plus expanded schemas) for **Swagger 2.0 and OpenAPI 3.x** —
the format is detected automatically from the spec content.

## Parsing a spec

```python
from goga_tool_pybuggy.spec import load_spec

spec = load_spec(spec_path)   # pathlib.Path; $ref already inlined by Prance
```

On a parse error `load_spec` raises `click.ClickException` (a mapping of
`SpecParseError` from swax). The parsed dict is fully dereferenced — never dereference
`$ref` manually.

## Version detection

```python
from goga_tool_pybuggy.spec import detect_spec_version

version = detect_spec_version(spec)   # "swagger" (Swagger 2.0) | "openapi" (OpenAPI 3.x)
```

The version is detected by the presence of a top-level `swagger` key versus `openapi` —
**not** by the declarative `type` field in the config. A spec with neither key is
invalid (`ValueError`). This drives the extraction path inside `extract_endpoints`; you
rarely need to call it manually.

## Endpoint extraction

```python
from goga_tool_pybuggy.spec import extract_endpoints

endpoints = extract_endpoints(spec)   # list[Endpoint], one per method+path
for ep in endpoints:
    ep.id           # 'clients_startup_get' — via build_endpoint_id
    ep.method       # 'get' (lowercase)
    ep.path         # '/clients/{id}'
    ep.request      # expanded request body schema (or {})
    ep.response     # {status: schema}
    ep.query_params # {name: schema}
```

The output semantics are identical across formats: OpenAPI 3.x extracts from
`requestBody` / `responses[code].content` / `parameters[].schema`; Swagger 2.0 — from
the `in: body` parameter / `responses[code].schema` / inline fields of the `in: query`
parameter. Given the same operation semantics, both produce the same normalized
`Endpoint` model. Extraction routes by the detected version, keeps only HTTP methods in
path-items, and merges path-item parameters into operations when present.

## Nullable normalization

The schemas in `request`, `response`, and `query_params` are already
**nullable-normalized** for JSON-Schema: OpenAPI `nullable: true` and Swagger
`x-nullable: true` are rewritten into union form (`type` as a list including `"null"`,
with an `anyOf` fallback when a single `type` cannot express the union), and the
`nullable`/`x-nullable` keys are removed. The `jsonschema` validator ignores both
keywords — the normalization happens once, at the parsing boundary; consumers never
re-normalize.

## Endpoint identifier

```python
from goga_tool_pybuggy.spec import build_endpoint_id

build_endpoint_id("POST", "/v1/API/{name}")   # 'v1_api_name_post'
```

`build_endpoint_id(method, path)` is pure and deterministic: the method is lowercased,
the leading slash and braces are stripped. `Endpoint.id` is computed from it.

`Endpoint.id` is guaranteed to be a **valid Python identifier** — path hyphens are
normalized to `_` (`/clients/payment-details` → `clients_payment_details_post`). This
matters because [generate](../cli/generate.md) uses the id as the pytest fixture name
and the package directory name; without the normalization the generated module would be
syntactically invalid. Collisions (the same id from different operations) are handled by
the consumer.

## Preconditions

- The spec must be fully dereferenced (use `load_spec`).
- Extraction is pure logic over a dict — testable without mocks.
