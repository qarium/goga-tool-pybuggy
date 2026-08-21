# swax.openapi — spec parsing and endpoint extraction

## Domain

Consumption patterns for the parsing cell `swax.openapi` in the `pybuggy` CLI. pybuggy uses **only** this swax module — for parsing specifications. `pybuggy` does NOT use `swax.git`, `swax.fs`, `swax.config`, `swax.cli`.

Public API (facade `swax.openapi`):
- `parse_spec(spec_path: Path) -> dict` — a fully dereferenced spec (Prance inlines `$ref`).
- `discover_specs(root: Path) -> list[Path]` — cheap enumeration of spec files in a directory.
- `extract_paths` / `extract_schemas` — **not used** (see below).
- `SpecParseError` — the domain parsing error.

---

## The main rule: extract_paths discards methods

`swax.openapi.extract_paths` deliberately returns **only** path templates, without HTTP methods — the swax traceability graph operates on paths. `pybuggy`, in contrast, works with endpoints of the form method+path and builds `endpoint_id` from both parts. Therefore **pybuggy extracts operations itself**, on top of the dict returned by `parse_spec`; pybuggy never calls `extract_paths`/`extract_schemas`.

---

## Parsing a specification

`parse_spec` returns a dict with `$ref` already inlined — no manual reference resolution is needed. The parser handles Swagger 2.0 and OpenAPI 3.x transparently; the `type` field in the `pybuggy` config is declarative and does not affect parsing.

```python
from pathlib import Path
from swax.openapi import parse_spec

def load_spec(spec_location: str, project_root: Path) -> dict:
    return parse_spec(project_root / spec_location)
```

Consumer conventions:
- `spec_location` — the project-root-relative path to the spec file (the `specs.<name>.location` value from the config).
- Accepts `.yaml`, `.yml`, `.json`.
- On a parsing error it raises `SpecParseError(path=..., reason=...)` — the CLI handler maps it to `click.ClickException`.

---

## Determining the specification version

The format is determined **from the spec's content**, not from the declarative config field `SpecEntry.type`. Cell `spec` governs this rule through `detect_spec_version`.

```python
def detect_spec_version(spec: dict) -> str:
    # Swagger 2.0: top-level "swagger": "2.0"; OpenAPI 3.x: top-level "openapi": "3.x"
    if "swagger" in spec:
        return "swagger"
    if "openapi" in spec:
        return "openapi"
    raise ValueError("spec declares neither a swagger nor an openapi version")
```

Consumer conventions:
- Detect by the presence of the top-level `swagger` key (Swagger 2.0) versus `openapi` (OpenAPI 3.x).
- A spec without a top-level `swagger` or `openapi` key is invalid — the function raises ValueError (a valid spec must declare a version).
- Never use `SpecEntry.type` to choose the extraction path.

---

## Endpoint extraction (pybuggy's own, on top of the parsed spec)

Operations live in `spec["paths"][path][method]`, where `method` is `get`/`post`/`put`/`delete`/`patch`/`options`/`head`. Prance has already inlined the schemas, so `$ref` is never resolved manually. Operation fields are extracted per the structure that `detect_spec_version` selects; both formats are normalized to an identical form.

```python
HTTP_METHODS = ("get", "post", "put", "delete", "patch", "options", "head")

def iter_operations(spec: dict):
    for path, item in spec.get("paths", {}).items():
        for method in HTTP_METHODS:
            operation = item.get(method)
            if operation is not None:
                yield method, path, operation
```

Consumer conventions:
- Non-method keys (`parameters`, `summary` at the path-item level) are skipped.
- Path-item parameters (`item["parameters"]`) are inherited by all operations; merge them with `operation["parameters"]`.

### Operation fields — OpenAPI 3.x

```python
def extract_request_schema_openapi(operation: dict) -> dict:
    content = operation.get("requestBody", {}).get("content", {})
    return content.get("application/json", {}).get("schema", {})

def extract_response_schemas_openapi(operation: dict) -> dict:
    return {
        code: resp.get("content", {}).get("application/json", {}).get("schema", {})
        for code, resp in operation.get("responses", {}).items()
    }

def extract_query_params_openapi(operation: dict) -> dict:
    return {p["name"]: p.get("schema", {}) for p in operation.get("parameters", []) if p.get("in") == "query"}
```

### Operation fields — Swagger 2.0

Swagger 2.0 structures the same data differently: the request body is a parameter with `in: body` carrying a root `schema`; the response is `responses[code].schema` directly, without a `content` wrapper; type fields are inlined into the parameter itself (no nested `schema`); nullability is expressed via `x-nullable`.

```python
def extract_request_schema_swagger(operation: dict) -> dict:
    for p in operation.get("parameters", []):
        if p.get("in") == "body":
            return p.get("schema", {})
    return {}

def extract_response_schemas_swagger(operation: dict) -> dict:
    return {code: resp.get("schema", {}) for code, resp in operation.get("responses", {}).items()}

_TYPE_FIELDS = ("type", "format", "items", "enum", "default", "description", "x-nullable")
# `x-nullable` is included deliberately: field filtering would otherwise drop the keyword before
# nullable-normalization, and the query parameter's nullability would be lost (see cell spec / design review).
def extract_query_params_swagger(operation: dict) -> dict:
    result = {}
    for p in operation.get("parameters", []):
        if p.get("in") == "query":
            result[p["name"]] = {k: v for k, v in p.items() if k in _TYPE_FIELDS}
    return result
```

Consumer conventions (both formats):
- `Request` / `Response` / `QueryParams` in the `info` output are already **expanded** schemas (Prance has inlined everything).
- The primary content type is `application/json`; when absent, the fields are empty (`{}`).
- `Description` = `operation.get("description", "")`.
- Both formats are normalized to an identical form before the data reaches `Endpoint` (nullable-normalization runs inside cell `spec`).

---

## Error mapping in the CLI

```python
import click
from swax.openapi import SpecParseError, parse_spec

def safe_parse(spec_path: Path) -> dict:
    try:
        return parse_spec(spec_path)
    except SpecParseError as exc:
        raise click.ClickException(f"failed to parse spec {exc.path}: {exc.reason}") from exc
```

---

## Testing

- Test parsing/extraction against spec fixtures in `tmp_path` (no mocks — pure logic over a dict).
- Swagger 2.0 and OpenAPI 3.x cases — inline specs as dicts, asserting the equivalence of the normalized schemas for operations with the same semantics.
