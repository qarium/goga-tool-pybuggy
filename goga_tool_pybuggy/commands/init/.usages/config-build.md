# goga_tool_pybuggy.commands.init — building .goga/tools/pybuggy/config.yml

## Domain

The `pybuggy init` command step that interactively builds the tool configuration file
`.goga/tools/pybuggy/config.yml` (plugin options + the specs section) — when the file is missing. Via the CLI this is
always the case in bare mode (an existing `.goga/` is refused up front by the already-initialized guard); in template
mode an existing file is skipped (see Overwriting). The audience is the integrator wiring pybuggy in, and the
consumer's goga agent.

## What is prompted

- Scalar plugin keys (sourced from `PluginConfigKeys`, the scalar members): base_url (required, a Jinja2 template),
  timeout, retries, assert_timeout, assert_delay, assert_field_class, assert_response_class.
  Each key is prompted one at a time; optional keys can be skipped (Enter).
- headers and loader are NOT prompted — they are written as commented examples.
- specs — interactively: name, type (swagger|openapi), location (required), and an optional git block
  (url, location, ref); multiple specs are supported; at least one is required.

## Overwriting

The rebuild decision lives in the onboarding orchestrator, not in the builder:

- bare mode via the CLI — the file can only be missing: a repeat invocation is refused by the already-initialized
  guard before this step (an existing `.goga/` → `Project already initialized`, exit 1, no rebuild).
- template mode — when the file exists after scaffolding it is silently skipped with an INFO log (no confirmation);
  when absent it is built through the normal interactive flow.
- `run_onboarding(template_mode=False)` called directly (the programmatic seam) — when the file exists, the pipeline
  asks via `click.confirm` (default `no`) and rebuilds only on `yes`; on refusal the step is skipped and the rest of
  the pipeline continues (exit 0).

The testable seam `build_pybuggy_config` itself always overwrites the file with no checks and no confirmations — a
direct programmatic call always (over)writes.

## Programmatic usage (tests/scripts)

The interactive flow is isolated in `build_pybuggy_config` (a testable seam, exported in `__all__`): it returns an
exit code and never raises. Tests monkeypatch the call point. Test the pure emission (active values + commented
entries) directly through `write_pybuggy_config` (no TTY): pass `scalar_values` (with skips) and `specs`, then assert
on the YAML.

## Preconditions and side effects

- Writes to `<cwd>/.goga/tools/pybuggy/config.yml` (creates the parent directory).
- The generated file is valid for configuration loading: specs is present with the required entry fields; scalar
  plugin keys are ignored on loading (extra=ignore).
- The key list is data-driven from `PluginConfigKeys` — no duplication.
