# goga_tool_pybuggy.commands.list — the endpoint list command

## Domain

Consumption patterns of the cell `goga_tool_pybuggy/commands/list`: print the endpoints grouped by spec. The audience: CLI registration (`list_cmd`) and tests (call `run_list` directly).

## Entry point

`run_list` is the testable entry point. The Click wrapper `list_cmd` binds the options and calls `run_list`:

    from goga_tool_pybuggy.commands.list import run_list

    run_list(spec_name=None)        # all specs
    run_list(spec_name="client")    # a single spec

## Behavior

For each (filtered) spec, the command parses the file at `location`, extracts the endpoints, and prints a text block:

    client (.specs/openapi/client/client-openapi.yaml)
    * clients_startup_get -> [GET] /clients/startup

The command loads the config from a fixed path via `load_config()`.

## Preconditions

- Spec files must reside at `location` (after `pull` or placed manually).
- The config is valid and resides at the fixed path `.goga/tools/pybuggy/config.yml`.
- The command is read-only — it does not modify specs or the config.
