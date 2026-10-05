# goga_tool_pybuggy.config — Pipeline Autonomy Resolution

## Domain

Cell `goga_tool_pybuggy/config` resolves the `pipelines` axis of `.goga/tools/pybuggy/config.yml`: which pipeline names run unattended. Target audience: workflow-amendment consumers that gate their contribution on the autonomy flag.

## The config axis

```yaml
pipelines:
  api.automate:
    autonomous: true
```

- The key axis is per pipeline name; an entry carries exactly one boolean member `autonomous`.
- Absent file, absent `pipelines` section, absent name, and `autonomous: false` all mean disabled.

## Resolve autonomy for the running pipeline

```python
from goga_tool_pybuggy.config import resolve_autonomy

enabled = resolve_autonomy("api.automate")  # bool
```

- The whole axis is validated on every call; a structural violation (a non-mapping file root, a non-mapping `pipelines` or entry, a record not matching the entry shape) raises a clean error naming pybuggy — call it from the amendment moment so the failure surfaces as the platform's clean stop.
- Unknown pipeline names are ignored, but every entry in the axis is validated — a
  malformed record for **any** pipeline (not just the requested one) raises the clean
  error above.
- No caching: each call obtains a fresh raw parse.

## Preconditions

- The raw file content is obtained through the goga tool-config facade; interpreting the axis is this cell's consumer-side contract.
