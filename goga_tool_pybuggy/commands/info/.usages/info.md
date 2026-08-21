# goga_tool_pybuggy.commands.info — the endpoint info command

## Domain

Consumption patterns of the cell `goga_tool_pybuggy/commands/info`: print the details of an endpoint by
its id (one or more) as JSON. The audience: CLI registration (`info_cmd`) and tests (call `run_info`
directly).

## Entry point

`run_info` is the testable entry point. The Click wrapper `info_cmd` binds the positional variadic
argument `endpoint-ids` and the `--spec` option, then calls `run_info`:

    from goga_tool_pybuggy.commands.info import run_info

    run_info(["clients_startup_get"])                        # only the specified endpoint; search across all specs
    run_info(["clients_startup_get"], spec_name="client")    # within a single spec
    run_info(["clients_startup_get", "health_get"])          # several endpoints
    run_info()                                               # None/empty — all endpoints of the selected specs

## Behavior

- The command parses every selected spec (all of them, or those filtered by `--spec`), extracts the
  endpoints, and collects the endpoints whose `id` is in `endpoint_ids`.
- No matches → `click.ClickException` ("endpoint not found: <id>").
- One match → a JSON object; several matches (an id collision across different specs, or several
  requested ids) → a JSON array.
- The command loads the config from a fixed path via `load_config()`. The output format is JSON with
  fixed keys (an object or an array — see above).

## Filtering by endpoint id

The positional variadic argument `endpoint-ids` restricts the output to a subset of endpoints by their
ids (`Endpoint.id` is a string such as `clients_startup_get`):

    pybuggy endpoint info clients_startup_get health_get
    pybuggy endpoint info -s client clients_startup_get   # the option precedes the positional ids

The command selects endpoints only among the selected specs (`--spec` or all):

- Argument not passed — the command prints all endpoints of the selected specs.
- An empty list / `None` at the handler — the same behavior (a no-op filter selects everything).
- An id found in at least one selected spec — only the matching endpoints are printed.
- An id not found in any selected spec → `click.ClickException("endpoint not found: <id>")` and a
  non-zero exit code; when several ids are missing, the error lists all of them (sorted), and nothing
  is printed.

The handler `run_info` takes the filter as its first parameter `endpoint_ids: list[str] | None`. Validation
runs before the output, so an unknown id does not print a partial result.

## Preconditions

- Spec files must reside at `location` (after `pull` or placed manually).
- Endpoint ids are built by the `build_endpoint_id` algorithm.
- The config is valid and resides at the fixed path `.goga/tools/pybuggy/config.yml`.
- The command is read-only — it does not modify specs or the config.
