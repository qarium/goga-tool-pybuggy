# goga_tool_pybuggy.config — Configuration Loading

## Domain

Cell `goga_tool_pybuggy/config` provides consumption patterns for loading `.goga/tools/pybuggy/config.yml` into typed models and accessing spec entries. Target audience: consumer commands and the CLI facade.

## Loading the configuration

```python
from goga_tool_pybuggy.config import load_config

config = load_config()  # the fixed location .goga/tools/pybuggy/config.yml
```

The `load_config` function obtains the raw parse of the tool config file through the goga tool-config facade and validates the result into the `Config` model. An absent file fails with a clean error naming the tool config location; an invalid configuration raises a pydantic validation error.

## Accessing spec entries

```python
for name, entry in config.specs.items():
    location = entry.location  # project-root-relative path to the spec file
    git = entry.git  # Optional[GitEntry]; None → local spec
    clone_url = git.url  # clone URL (no embedded tokens)
    repo_path = git.location  # path inside the repository
    repo_ref = git.ref  # Optional[str]; branch/tag to clone; None → default branch
```

- `name` (the dict key) is used by consumers for output and for the `--spec` filter.
- `entry.git` can be `None` — the consumer treats such a spec as local and skips it with a WARNING.
- `git.ref` is the default ref for cloning; the consumer can override it with the `--ref` option (priority order: `--ref` > `git.ref` > default branch).

## Preconditions

- The file location follows the platform path standard for tool configs (`.goga/tools/<tool>/<filename>`); the platform resolves it.
- The `type` field is declarative — it does not affect parsing (Prance auto-detects the version).
