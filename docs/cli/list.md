# CLI — `goga tool pybuggy endpoint list`

Prints the endpoints of the configured specs, grouped by spec. With `--status` every printed line
is additionally annotated with its artifact synchronization status (`ADD`/`UPD`/`OK`/`REMOVED`).

```bash
goga tool pybuggy endpoint list                           # all specs, plain listing
goga tool pybuggy endpoint list --spec client             # a single spec, plain listing
goga tool pybuggy endpoint list --status                  # all specs, with statuses
goga tool pybuggy endpoint list --spec client --status    # a single spec, with statuses
```

## Options and arguments

| Element | Meaning |
|---------|---------|
| `--spec <name>` | Restrict the listing to a single spec; unknown name → `ClickException("spec not found: <name>")`, non-zero exit |
| `--status` | Turn on the status mode: annotate every line with its artifact synchronization status and let removed artifact directories join the listing. Long form only (no short form), boolean flag, default off |

The two options combine freely: `--spec` narrows which specs are listed, `--status` changes what
each line carries. Without `--status` the plain listing prints — the flag is off by default, so the
previous behavior is unchanged.

## Output format

For each (filtered) spec the command parses the file at `location`, extracts the
endpoints and prints a text block:

```
client (.specs/openapi/client/client-openapi.yaml)
* clients_startup_get -> [GET] /clients/startup
```

Header line: `<name> (<location>)`; per endpoint: `id -> [METHOD] path`. METHOD is uppercase, the
path is raw (with braces). Order is deterministic: specs in config order, endpoint lines sorted by
id.

### Status output

With `--status` every line carries its status against the generated artifacts, and removed artifact
directories join the listing:

```
client (.specs/openapi/client/client-openapi.yaml)
* clients_startup_get -> [GET] /clients/startup — STATUS: OK
* clients_startup_post -> [POST] /clients/startup — STATUS: ADD
* clients_update_put -> [PUT] /clients/update — STATUS: UPD
* legacy_endpoint_get — STATUS: REMOVED
```

- Endpoint lines: `* <id> -> [<METHOD>] <path> — STATUS: <X>`; the separator before `STATUS:` is an
  em dash with one space on each side.
- Removed lines: `* <segment> — STATUS: REMOVED` — no method/path part; `<segment>` is the artifact
  directory name.
- Endpoint lines and removed lines form ONE list sorted by line name (`<id>` / `<segment>`) —
  deterministic across runs.

Status semantics:

| Status | Meaning |
|--------|---------|
| `ADD` | The endpoint has no artifact directory under `api/<spec>/` |
| `UPD` | The directory exists and drifted: a non-empty strict comparison of the generated side (read from the artifacts) against the spec side |
| `OK` | The directory exists and matches: the comparison is empty |
| `REMOVED` | An artifact directory under `api/<spec>/` matching no endpoint of the spec |

The comparison is the same one [diff](diff.md) runs — the generated side is the old/left value, the
spec side the new/right one, strict, no relaxations — so a line's `UPD`/`OK` verdict agrees with the
endpoint's `diff` verdict by construction.

## Behavior

- The config is loaded from the fixed path `.goga/tools/pybuggy/config.yml`.
- The command is read-only — it does not modify specs, the config, or artifacts. The artifact tree
  is read only in the status mode; the plain mode touches no artifact file.
- Removed-side discovery scans the whole `api/<spec>/` tree of each listed spec in every status-mode
  run — it is not narrowed by `--spec` beyond the spec selection itself, and skips `__pycache__` and
  hidden directories.

## Special cases

| Case | Behavior |
|------|----------|
| Spec that is not a mapping, has no `paths` mapping (absent or null), declares no `openapi`/`swagger` version key, or carries an invalid response status key | `click.ClickException` ("invalid spec file …"), non-zero exit — never a traceback; fires in both modes |
| Two distinct paths mapping to the *identical* endpoint id (e.g. `/a-b/x` and `/a/b/x`) | `click.ClickException` naming both paths — the status report is keyed by id, so it refuses rather than misreport one of the two |
| No `api/<spec>/` tree (e.g. a fresh workspace) | Every endpoint prints `ADD`; no `REMOVED` lines; exit 0 — not an error |
| Missing, unreadable or corrupt `meta.json` / schema JSON under `api/<spec>/` (including inside a removed-side directory) | `click.ClickException`, non-zero exit — never a traceback |
| Spec that parses but declares no endpoints | A warning is logged; the plain mode still prints the header-only block; the status mode prints nothing unless removed segments exist |
| Two ids sanitizing to the same artifact segment | Both endpoints classify against the one directory; not an error |
| Any successful run | Exit 0 — drift is a result, not a failure |

## Preconditions

- Spec files must reside at `location` (after
  [pull](pull.md) or placed manually).
- The config is valid and resides at the fixed path.
- In the status mode, artifacts live under the current working directory
  (`api/<spec>/<segment>/`) and are generated by the [generate](generate.md) command.
