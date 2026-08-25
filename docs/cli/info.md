# CLI — `goga tool pybuggy endpoint info`

Prints endpoint details as JSON — by endpoint id (one or more).

```bash
goga tool pybuggy endpoint info clients_startup_get                   # one id, search across all specs
goga tool pybuggy endpoint info -s client clients_startup_get         # within a single spec
goga tool pybuggy endpoint info clients_startup_get health_get        # several ids
goga tool pybuggy endpoint info                                       # all endpoints of the selected specs
```

## Options and arguments

| Element | Meaning |
|---------|---------|
| `endpoint-ids` (positional, variadic) | Restrict the output to endpoints with these ids (`clients_startup_get`-style) |
| `-s/--spec <name>` | Restrict the search to a single spec |

Filtering semantics:

- Argument not passed (or an empty list) — a no-op filter: all
  endpoints of the selected specs are printed.
- An id found in at least one selected spec — only the matching endpoints are printed.
- An id not found in any selected spec → `click.ClickException("endpoint not found: <id>")`,
  non-zero exit. Several missing ids — all are listed (sorted); nothing is printed.

Validation runs **before** the output, so an unknown id never produces a partial result.

## Output format

JSON with fixed keys (PascalCase): `Method` (lowercase), `Path` (`{param}` → `:param`),
`Request`, `Response`, `QueryParams`, `Description`.

- One match → a JSON object.
- Several matches (an id collision across specs, or several requested ids) → a JSON array.

URL path variables are not part of this output — `QueryParams` covers query parameters
only. The `{name: schema}` of URL path variables is available in the `vars` key of the
per-endpoint `meta.json` written by [generate](generate.md).

## Preconditions

- Spec files must reside at `location` (after [pull](pull.md) or placed manually).
- Endpoint ids are built from the method and path — `POST /v1/API/{name}` becomes
  `v1_api_name_post`; the same id is used by [generate](generate.md) for fixture and
  directory names.
- The command is read-only.
