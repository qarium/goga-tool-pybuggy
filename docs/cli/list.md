# CLI — `goga tool pybuggy endpoint list`

Prints the endpoints of the configured specs, grouped by spec.

```bash
goga tool pybuggy endpoint list                  # all specs
goga tool pybuggy endpoint list --spec client    # a single spec
```

## Output

For each (filtered) spec the command parses the file at `location`, extracts the
endpoints and prints a text block:

```
client (.specs/openapi/client/client-openapi.yaml)
* clients_startup_get -> [GET] /clients/startup
```

Header line: `<name> (<location>)`; per endpoint: `id -> [METHOD] path`.

## Behavior

- The config is loaded from the fixed path `.goga/tools/pybuggy/config.yml` via
  `load_config()`.
- The command is read-only — it does not modify specs or the config.

## Preconditions

- Spec files must reside at `location` (after
  [pull](pull.md) or placed manually).
- The config is valid and resides at the fixed path.

## Programmatic usage

```python
from goga_tool_pybuggy.commands.list import run_list

run_list(spec_name=None)        # all specs
run_list(spec_name="client")    # a single spec
```
