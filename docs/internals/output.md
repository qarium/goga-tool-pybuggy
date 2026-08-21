# Internals — Output Formatting

The `goga_tool_pybuggy.output` module formats endpoints for the `list` and `info`
commands. The formatters are **pure functions** — no I/O; the calling command does all
stdout printing.

## `list` output (text)

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

- Header line: `<name> (<location>)`.
- Per endpoint: `* <id> -> [METHOD] <path>` — METHOD uppercase, path raw (with braces).

## `info` output (JSON)

```python
from goga_tool_pybuggy.output import render_info

print(render_info(endpoints))   # a single object, or an array on multiple matches
```

The keys are fixed (PascalCase): `Method` (lowercase), `Path` (`{param}` → `:param`),
`Request`, `Response`, `QueryParams`, `Description`. When multiple endpoints match, the
result is a JSON array of objects.

Date values from the specification (e.g. `format: date`/`date-time` examples that Prance
converts to `datetime.date`/`datetime.datetime`) are serialized as ISO 8601 strings —
serialization never fails on them.

## Preconditions

- Pass already extracted [`Endpoint`](spec.md) instances (from `extract_endpoints`).
- The formatters never write to stdout — the caller decides where to print.
