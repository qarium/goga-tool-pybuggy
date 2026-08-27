# goga_tool_pybuggy.output — command output formatting

## Domain

Consumption patterns of the cell `goga_tool_pybuggy.output`: formatting endpoints into text (`list`, optionally with artifact-sync statuses), JSON (`info`), and formatting a comparison result into a JSON document (`diff`). The audience: the `list`, `info`, and `diff` commands. Formatters are pure functions; the calling command does all stdout printing.

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

## status list output (text)

```python
from goga_tool_pybuggy.output import render_status_list

block = render_status_list(name, location, endpoints, statuses, removed)
print(block)
```

Block format:
```
client (.specs/openapi/client/client-openapi.yaml)
* clients_startup_get -> [GET] /clients/startup — STATUS: OK
* legacy_endpoint_get — STATUS: REMOVED
```
- Header line: `<name> (<location>)`, as in the plain list block.
- Endpoint lines: `* <id> -> [<METHOD>] <path> — STATUS: <X>`; METHOD uppercase; path raw (with braces); `<X>` is `ADD`, `UPD`, or `OK`.
- Removed lines: `* <segment> — STATUS: REMOVED` — no method/path part; `<segment>` is the artifact directory name.
- The separator before `STATUS:` is an em dash with one space on each side.
- Endpoint lines and removed lines form one list sorted by line name (`<id>` / `<segment>`); the order is deterministic across runs.
- `statuses` maps endpoint id → status; `removed` lists artifact segments. The formatter consumes both as given — it computes no status and reads no file.

## info output (JSON)

```python
from goga_tool_pybuggy.output import render_info

print(render_info(endpoints))  # a single object, or an array on multiple matches
```

The keys are fixed (PascalCase): `Method` (lowercase), `Path` (`{param}`→`:param`), `Request`, `Response`, `QueryParams`, `Description`. When multiple endpoints match, the result is a JSON array of objects.

Date values from the specification (for example, `format: date`/`date-time` examples that Prance converts to `datetime.date`/`datetime.datetime`) are serialized into the JSON as ISO 8601 strings — serialization does not fail for them.

## diff output (JSON document per compared unit)

```python
import json

from goga_tool_pybuggy.output import render_diff

print(render_diff("clients_startup_get", json.loads(diff.to_json())))
# {"clients_startup_get": {"values_changed": {"root['request_body']": {...}}}}

print(render_diff("clients_startup_get", {}))
# {"clients_startup_get": {}}
```

- One call — one compared unit (endpoint); the caller prints each returned line.
- `endpoint_id` is the caller-supplied key: the raw endpoint id for spec-side entries, the sanitized artifact segment for removed artifact directories.
- `diff` is an already-converted plain mapping (the caller converts the comparison result); an empty mapping means no drift and serializes as `{}`.
- `json.loads(diff.to_json())` is the only JSON-native conversion of a comparison result — the mappings of `to_dict()` hold set-like values (`SetOrdered`) that `json.dumps` cannot serialize.
- The formatter does not interpret or filter diff categories — every entry passes through unchanged.

## Preconditions

- Pass already extracted `Endpoint` instances to `render_list`/`render_info`/`render_status_list`, and a plain mapping to `render_diff`.
- For `render_status_list`, the caller computes `statuses` and `removed` beforehand and passes complete structures — the formatter trusts them.
- Formatters do not write to stdout — the caller decides where to print.
