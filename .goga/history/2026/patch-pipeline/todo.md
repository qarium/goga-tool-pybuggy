# TODO — patch-pipeline (Patch flow, cycle 2)

## Task

Source: user answer to `autonomous_execution.q1` (Patch flow, 2026-10-15).

The `init` command asks about autonomous runs only for `api.automate` and writes a single
axis entry into `.goga/tools/pybuggy/config.yml`. The `api.patch` pipeline now ships its own
autonomy axis but is never offered during onboarding.

Requirement: when the user opts into autonomy during `init`, ask about it the same way as for
`api.automate` and create the config entries for both pipelines:

```yaml
pipelines:
  api.automate:
    autonomous: true
  api.patch:
    autonomous: true
```

Keeping CODEMANIFEST/implementation/.usages triple consistency.

## Acceptance

- An onboarding run with autonomy confirmed writes both `api.automate` and `api.patch`
  axes with `autonomous: true`; a declined run writes no `pipelines` section (unchanged).
- `resolve_autonomy("api.patch")` returns True on the config produced by the enabling path.
