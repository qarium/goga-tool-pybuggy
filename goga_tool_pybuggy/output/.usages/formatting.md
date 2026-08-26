# goga_tool_pybuggy.output — command output formatting

## Domain

Consumption patterns of the cell `goga_tool_pybuggy.output`: formatting endpoints into text (`list`) and JSON (`info`), and formatting a comparison result into a JSON document (`diff`). The audience: the `list`, `info`, and `diff` commands. Formatters are pure functions; the calling command does all stdout printing.

## list output (text)

```python
from goga_tool_pybuggy.output import render_list

block = render_list(name, location, endpoints)
print(block)
```

Block format:
```
client (.specs/openapi/client/client-openapi.yaml)
* clients_startup_get -> [GET] /clients/startup
```
- Header line: `<name> (<location>)`; METHOD in uppercase; path is raw (with braces).

## info output (JSON)

```python
from goga_tool_pybuggy.output import render_info

print(render_info(endpoints))  # a single object, or an array on multiple matches
```

The keys are fixed (PascalCase): `Method` (lowercase), `Path` (`{param}`→`:param`), `Request`, `Response`, `QueryParams`, `Description`. When multiple endpoints match, the result is a JSON array of objects.

Date values from the specification (for example, `format: date`/`date-time` examples that Prance converts to `datetime.date`/`datetime.datetime`) are serialized into the JSON as ISO 8601 strings — serialization does not fail for them.

## diff output (JSON document per compared unit)

```python
from goga_tool_pybuggy.output import render_diff

print(render_diff("clients_startup_get", diff.to_dict()))
# {"clients_startup_get": {"values_changed": {"root['request_body']": {...}}}}

print(render_diff("clients_startup_get", {}))
# {"clients_startup_get": {}}
```

- One call — one compared unit (endpoint); the caller prints each returned line.
- `endpoint_id` is the caller-supplied key: the raw endpoint id for spec-side entries, the sanitized artifact segment for removed artifact directories.
- `diff` is an already-converted plain mapping (the caller converts the comparison result); an empty mapping means no drift and serializes as `{}`.
- The formatter does not interpret or filter diff categories — every entry passes through unchanged.

## Preconditions

- Pass already extracted `Endpoint` instances to `render_list`/`render_info`, and a plain mapping to `render_diff`.
- Formatters do not write to stdout — the caller decides where to print.
