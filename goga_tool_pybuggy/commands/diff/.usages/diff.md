# goga_tool_pybuggy.commands.diff — the endpoint diff command

## Subject domain

The cell `goga_tool_pybuggy.commands.diff` provides the drift report: it compares, per endpoint, the
endpoint contract taken from the current spec with the previously generated artifacts under `api/` and
prints one JSON document per compared unit to the console. Consumers: CLI registration (`diff_cmd`)
and tests (`run_diff` directly; the helpers `spec_contract`, `artifact_contract`, `sanitize_id`,
`orphan_artifact_dirs` directly).

## Handler function invocation

`run_diff` is the testable entry point; the Click wrapper `diff_cmd` binds the options and calls
`run_diff`:

    from goga_tool_pybuggy.commands.diff import run_diff

    run_diff(spec_name=None)                            # all specs, every endpoint
    run_diff(spec_name="shop")                          # one spec, every endpoint
    run_diff(None, ["clients_startup_get"])             # filter by endpoint ids
    run_diff(None, [])                                  # empty/None filter — every endpoint

The helpers are callable directly for narrow checks:

    from goga_tool_pybuggy.commands.diff import spec_contract, sanitize_id, artifact_contract, orphan_artifact_dirs

    contract = spec_contract(endpoint)            # unified structure of the spec side
    segment = sanitize_id("clients_startup_get")   # artifact directory segment
    generated = artifact_contract(artifact_dir)    # unified structure of the generated side
    orphans = orphan_artifact_dirs(api_spec_dir, endpoints)  # removed-side directories

## Output

Each compared unit prints exactly one JSON document on one line, keyed by the unit's identifier:

    {"clients_startup_get": {}}
    {"clients_startup_get": {"values_changed": {"root['request_body']['properties']['note']['type']": {"old_value": "string", "new_value": "integer"}}}}
    {"clients_startup_get": {"dictionary_item_added": ["root['schemas']['418']"]}}
    {"legacy_endpoint_get": {"values_changed": {"root": {"new_value": {}, "old_value": {"parameters": {}, "request_body": {}, "vars": {}, "schemas": {"200": {"type": "object"}}}}}}}

- The key is the raw endpoint id for spec-side entries and the sanitized artifact segment for removed
  artifact directories.
- An endpoint with no drift prints an empty diff value — every compared endpoint prints a document,
  with or without an endpoint-id filter.
- Order is deterministic: specs in config order, endpoints in extraction order, removed directories
  sorted by segment.
- The command exits 0 after any successful run — drift is a normal result, not a failure.

## One-sided endpoints

- An endpoint of the spec without an artifact directory is reported as **added**: the spec side is
  compared against an empty contract, and adding a contract as a whole surfaces as a `values_changed`
  entry on `root` (an empty `old_value` on the generated side, the full contract as the `new_value`).
- An artifact directory under `api/<spec>/` whose segment matches no endpoint of the spec is reported
  as **removed**: an empty contract is compared against the directory's artifacts, which likewise
  surfaces as a `values_changed` entry on `root` (the full artifact contract as the `old_value`, an
  empty `new_value`).
- Per-key `dictionary_item_added` / `dictionary_item_removed` categories appear for **nested** keys
  under shared ancestors (e.g. a status code present on only one side under a common `schemas` key) —
  one-sided comparisons of the contract as a whole do not decompose per key.
- Removed-side discovery scans the whole `api/<spec>/` tree of each selected spec in every run — it is
  NOT narrowed by endpoint-ids; the endpoint-id filter selects only which spec endpoints are compared
  as the added side.
- A spec with no `api/<spec>/` tree at all reports every selected endpoint as added and fails nothing.

## The --spec flag

`-s/--spec <name>` restricts the report to a single spec. A non-existent name causes
`click.ClickException("spec not found: <name>")` and a non-zero exit.

## Endpoint-id filter

The positional variadic argument `endpoint-ids` restricts the compared spec endpoints by their raw
ids (`Endpoint.id` is a string such as `clients_startup_get`):

    pybuggy endpoint diff clients_startup_get health_get
    pybuggy endpoint diff -s shop clients_startup_get   # options precede the positional ids

- Argument not passed / empty list / `None` — every endpoint of the selected specs is compared.
- An id found in at least one selected spec — only the matching endpoints are compared.
- An id not found in any selected spec — `click.ClickException("endpoint not found: <id>")` before any
  output; several missing ids are listed sorted.

## Error channel

Operational failures map uniformly to `click.ClickException` (non-zero exit): an unknown `--spec`
value, an unknown endpoint id, an unparseable spec file, and a missing or corrupt `meta.json` /
schema JSON file.

## Preconditions

- Spec files must reside at `location` (after `pull` or placed manually); the config is valid and
  resides at the fixed path `.goga/tools/pybuggy/config.yml`.
- Generated artifacts live under the current working directory (`api/<spec>/<segment>/`); tests
  isolate via `tmp_path` and a `cwd` override.
- The command is read-only — it never writes, creates, or deletes anything; a run over an existing
  artifact tree leaves every file byte-identical.
