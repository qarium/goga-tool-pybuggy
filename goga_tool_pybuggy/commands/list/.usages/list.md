# goga_tool_pybuggy.commands.list — the endpoint list command

## Domain

Consumption patterns of the cell `goga_tool_pybuggy.commands.list`: print the endpoints grouped by spec, optionally annotated with each line's artifact synchronization status. The audience: CLI registration (`list_cmd`) and tests (call `run_list` directly).

## Entry point

`run_list` is the testable entry point. The Click wrapper `list_cmd` binds the options and calls `run_list`:

    from goga_tool_pybuggy.commands.list import run_list

    run_list(spec_name=None)                        # all specs, plain listing
    run_list(spec_name="client")                    # a single spec, plain listing
    run_list(spec_name=None, with_status=True)      # all specs, with statuses
    run_list(spec_name="client", with_status=True)  # a single spec, with statuses

## Helpers

`endpoint_statuses` is callable directly for narrow checks:

    from goga_tool_pybuggy.commands.list import endpoint_statuses

    statuses, removed = endpoint_statuses(api_spec_dir, endpoints)
    # statuses: {endpoint_id: "ADD" | "UPD" | "OK"}; removed: [segment, ...]

## Behavior

For each (filtered) spec, the command parses the file at `location`, extracts the endpoints, and prints a text block:

    client (.specs/openapi/client/client-openapi.yaml)
    * clients_startup_get -> [GET] /clients/startup

With `with_status=True`, every line carries its synchronization status against the generated artifacts, and removed artifact directories join the listing:

    client (.specs/openapi/client/client-openapi.yaml)
    * clients_startup_get -> [GET] /clients/startup — STATUS: OK
    * clients_startup_post -> [POST] /clients/startup — STATUS: ADD
    * clients_update_put -> [PUT] /clients — STATUS: UPD
    * legacy_endpoint_get — STATUS: REMOVED

- Statuses: `ADD` — the endpoint has no artifact directory; `UPD` — the directory exists and drifted; `OK` — the directory exists and matches; `REMOVED` — an artifact directory matching no endpoint, printed as `* <segment> — STATUS: REMOVED` with no method/path part.
- Endpoint lines and removed lines form one list sorted by line name (`<id>` / `<segment>`) — deterministic across runs.
- The status mode reads the artifact tree under `api/<name>/` of the working directory; the plain mode touches no artifact file.
- A spec that parses but declares no endpoints logs a warning; in the plain mode its header-only block still prints (byte-identical to the previous behavior); in the status mode a spec prints its block when it has at least one line (removed segments count as lines).

## The --spec and --status options

`--spec <name>` restricts the listing to a single spec; a non-existent name causes `click.ClickException("spec not found: <name>")` and a non-zero exit. `--status` (long form only, no short form) turns on the status mode. The two options combine freely.

## Error channel

An invalid spec — not a mapping, no `paths` mapping, no `swagger`/`openapi` version key, or a response key outside the legal status-key shapes — → `click.ClickException` ("invalid spec file …"), never a traceback. In the status mode, a missing or corrupt `meta.json` / schema JSON file under `api/<name>/` — including inside a removed-side directory — is equally a `click.ClickException` (non-zero exit). In the status mode, two endpoints of one spec sharing a raw id (distinct paths whose `-` and `/` both collapse in the id) are also a `click.ClickException` naming both paths — the report is keyed by id, so one of the two would be silently misreported. A spec with no `api/<name>/` tree is not an error: every endpoint prints `ADD`. A successful run exits 0 — drift is a result, not a failure.

## Preconditions

- Spec files must reside at `location` (after `pull` or placed manually).
- The config is valid and resides at the fixed path `.goga/tools/pybuggy/config.yml`.
- In the status mode, generated artifacts live under the working directory (`api/<name>/<segment>/`); tests isolate via `tmp_path` and a `cwd` override.
- The command is read-only — it does not modify specs, the config, or artifacts.
