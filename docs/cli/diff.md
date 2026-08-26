# CLI — `goga tool pybuggy endpoint diff`

Read-only drift report between the specifications and the generated artifacts: for every compared
unit it prints one JSON document with the structural difference between the endpoint contract taken
from the current spec and the artifacts previously written by [generate](generate.md) under `api/`.
An endpoint whose artifacts match the spec prints an empty diff — `{}`.

```bash
goga tool pybuggy endpoint diff                          # all specs, every endpoint
goga tool pybuggy endpoint diff -s shop                  # single spec, every endpoint
goga tool pybuggy endpoint diff clients_startup_get      # only the listed endpoints
```

## Options and arguments

| Element | Meaning |
|---------|---------|
| `endpoint-ids` (positional, variadic) | Restrict the comparison to endpoints with these ids (raw `clients_startup_get`-style ids, not directory segments); an empty/absent filter — every endpoint of the selected specs |
| `-s/--spec <name>` | Restrict the report to a single spec; unknown name → `ClickException("spec not found: <name>")` |

Filtering semantics:

- Argument not passed (or an empty list) — a no-op filter: all endpoints of the selected specs
  are compared.
- An id found in at least one selected spec — only the matching endpoints are compared.
- An id not found in any selected spec → `click.ClickException("endpoint not found: <id>")`,
  non-zero exit. Several missing ids — all are listed (sorted); nothing is printed.

Validation runs **before** any output, so an unknown id never produces a partial report. The
`endpoint-ids` filter narrows only the spec side: removed artifact directories are still discovered
over the whole `api/<spec>/` tree of every selected spec (see below).

## Output format

One JSON document per compared unit, one line each, keyed by the unit's identifier:

```
{"clients_startup_get": {}}
{"clients_startup_get": {"values_changed": {"root['request_body']['properties']['note']['type']": {"old_value": "integer", "new_value": "string"}}}}
{"clients_startup_get": {"dictionary_item_added": ["root['schemas']['418']"]}}
{"legacy_endpoint_get": {"values_changed": {"root": {"new_value": {}, "old_value": {"parameters": {}, "request_body": {}, "vars": {}, "schemas": {"200": {"type": "object"}}}}}}}
```

- The key is the raw endpoint id for spec-side entries and the sanitized artifact directory segment
  for removed directories.
- An endpoint with no drift prints an empty diff value — every compared endpoint prints a document,
  with or without an endpoint-id filter.
- Order is deterministic: specs in config order, endpoints in extraction order, removed directories
  sorted by segment.
- The categories and `old_value`/`new_value` pairs come from `deepdiff` verbatim; the command does
  not filter, rename or reorder them. The comparison direction is fixed — the generated side is the
  old/left value, the spec side the new/right one — so `old_value` always describes the artifacts
  and `new_value` the current spec.

## One-sided endpoints

- An endpoint of the spec without an artifact directory is reported as **added**: the spec side is
  compared against an empty contract, and adding a contract as a whole surfaces as a
  `values_changed` entry on `root` (an empty `old_value`, the full contract as the `new_value`).
- An artifact directory under `api/<spec>/` whose segment matches no endpoint of the spec is
  reported as **removed**: an empty contract is compared against the directory's artifacts, which
  likewise surfaces as a `values_changed` entry on `root` (the full artifact contract as the
  `old_value`, an empty `new_value`).
- Per-key `dictionary_item_added` / `dictionary_item_removed` categories appear for **nested** keys
  under shared ancestors — e.g. a status code present on only one side under a common `schemas`
  key; one-sided comparisons of the contract as a whole do not decompose per key.
- Removed-side discovery scans the whole `api/<spec>/` tree of each selected spec in every run — it
  is not narrowed by `endpoint-ids`.
- A spec with no `api/<spec>/` tree at all reports every endpoint as added and fails nothing.

## What is compared

Both sides are normalized to the same four-key structure before comparing:

| Key | Spec side | Generated side |
|-----|-----------|----------------|
| `parameters` | `Endpoint.query_params` | `meta.json` → `parameters` |
| `request_body` | `Endpoint.request` | `meta.json` → `request_body` |
| `vars` | `Endpoint.path_params` | `meta.json` → `vars` |
| `schemas` | `Endpoint.response` (`{status_code: schema}`) | `schemas/<status_code>.json` |

Only `meta.json` and `schemas/*.json` take part — `api.py`, `__init__.py` markers and `tests/`
directories are never compared. Schema values are read as plain JSON without interpretation, and
spec-side values are normalized to JSON-native ones first (e.g. a YAML date becomes an ISO 8601
string, the same convention generate used when writing the artifacts), so a matching pair of sides
never reports spurious `type_changes`.

## Special cases

| Case | Behavior |
|------|----------|
| Spec without `paths`, not a mapping, or without an `openapi`/`swagger` version key | `click.ClickException` |
| Spec without operations | No per-endpoint output; every artifact directory of that spec is reported as removed |
| Missing, unreadable or corrupt `meta.json` / schema JSON | `click.ClickException` |
| Two ids sanitizing to the same segment | Both endpoints are compared against the one directory; not an error |
| Any successful run | Exit 0 — drift is a result, not a failure |
| Whole run | Read-only — the artifact tree is left byte-identical |

## Preconditions

- Spec files must be present in `location` (after [pull](pull.md) or placed manually).
- The config must be valid and reside at the fixed path.
- Artifacts live under the current working directory (`api/<spec>/<segment>/`) and are generated by
  the [generate](generate.md) command.
