# jsonschema — response body validation (Draft7Validator)

## Domain

`jsonschema` validates the JSON body of a response (`resq.http.Response.json()`) against a JSON schema. Cell `goga_tool_pybuggy/api/asserts` uses it: the `Expected.jsonschema_is_valid` method (a single schema dict/path), the `Expected.jsonschemas_is_valid` method (a directory of schemas keyed by status), and auto-validation on the positive path (via the `schemas/<status>*.json` file).

```python
import jsonschema
from pathlib import Path

schema = json.loads(Path("schemas/200.json").read_text(encoding="utf-8"))
jsonschema.Draft7Validator(schema).validate(response.json())  # raises ValidationError on failure
```

---

## Draft7Validator — the base contract

- `jsonschema.Draft7Validator(schema)` builds a validator; `.validate(instance)` raises `jsonschema.exceptions.ValidationError` when `instance` does not conform to the schema.
- In pybuggy, `instance` is always `response.json()` (the parsed response body).
- The schema is a plain dict (JSON Schema keywords: `type`, `properties`, `required`, `items`, etc.).

Load the schema either directly from a dict or from a `.json` file (UTF-8):
```python
if isinstance(schema, str):
    schema = json.loads(Path(schema).read_text(encoding="utf-8"))
jsonschema.Draft7Validator(schema).validate(body)
```

---

## Auto-validation by status

On the positive path, `Expected` loads the **first** file in `schemas_dir` whose name starts with the actual status code string (`str(response.status_code)`), and validates the body against it. The files are sorted — the first match wins:

```python
code = str(response.status_code)
for entry in sorted(schemas_dir.iterdir()):
    if entry.is_file() and entry.name.startswith(code):
        schema = json.loads(entry.read_text(encoding="utf-8"))
        jsonschema.Draft7Validator(schema).validate(response.json())
        return
```

Auto-validation is **silently skipped** — no error — when `schemas_dir` is missing, when it is not a directory, or when it holds no file for the status.

---

## OpenAPI-flavored schemas — the Draft7 limitation

Response schemas are derived from an OpenAPI spec; such schemas may lack a mandatory `$schema` and may carry keywords that `Draft7Validator` does not understand (`nullable`, etc.). The default is exactly `Draft7Validator`. If such discrepancies surface as false errors/misses, switch to `openapi-schema-validator`; the current contract does not do that.
