# goga_tool_pybuggy.config — Configuration Loading

## Domain

Cell `goga_tool_pybuggy/config` provides consumption patterns for loading `.goga/tools/pybuggy/config.yml` into typed models and accessing spec entries. Target audience: consumer commands and the CLI facade.

## Loading the configuration

```python
from goga_tool_pybuggy.config import load_config

config = load_config(path)  # path is project-root-relative; None → fixed path .goga/tools/pybuggy/config.yml
```

The `load_config` function reads the YAML file via `yaml.safe_load` and validates the result into the `Config` model. If the configuration is invalid, `load_config` raises a pydantic validation error.

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

- The configuration path is resolved relative to the project root (cwd); the default value is `.goga/tools/pybuggy/config.yml`.
- The `type` field is declarative — it does not affect parsing (Prance auto-detects the version).
