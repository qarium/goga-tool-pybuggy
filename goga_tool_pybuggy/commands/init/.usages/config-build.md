# goga_tool_pybuggy.commands.init — building .goga/tools/pybuggy/config.yml

## Domain

The `pybuggy init` command step that interactively builds the tool configuration file
`.goga/tools/pybuggy/config.yml` (plugin options + the specs section) — immediately when the file is missing,
after confirmation when it exists (see "Overwriting"). The audience is the integrator wiring pybuggy in, and the
consumer's goga agent.

## What is prompted

- Scalar plugin keys (sourced from `PluginConfigKeys`, the scalar members): base_url (required, a Jinja2 template),
  timeout, data_key, error_key, retries, assert_timeout, assert_delay, assert_field_class, assert_response_class.
  Each key is prompted one at a time; optional keys can be skipped (Enter).
- headers and loader are NOT prompted — they are written as commented examples.
- specs — interactively: name, type (swagger|openapi), location (required), and an optional git block
  (url, location, ref); multiple specs are supported.

## Overwriting

When `.goga/tools/pybuggy/config.yml` **does not exist**, `run_init` builds it without asking. When the file
**exists**, `run_init` asks via `click.confirm` (default `no`) whether to rebuild the file, and rebuilds it only
on `yes`; on refusal the step is skipped and the rest of `init` continues (exit 0). The testable seam
`build_pybuggy_config` itself always overwrites the file with no checks and no confirmations — the rebuild
decision lives in the `run_init` orchestrator, not in the builder (a direct programmatic call to
`build_pybuggy_config` always overwrites).

## Programmatic usage (tests/scripts)

The interactive flow is isolated in `build_pybuggy_config` (a testable seam, exported in `__all__`): it returns
an exit code and never raises. Tests monkeypatch the call point, the same pattern as `run_goga_init`. Test the
pure emission (active values + commented entries) directly through `write_pybuggy_config` (no TTY): pass
`scalar_values` (with skips) and `specs`, then assert on the YAML.

## Preconditions and side effects

- Writes to `<cwd>/.goga/tools/pybuggy/config.yml` (creates the parent directory).
- The generated file is valid for configuration loading: specs is present with the required entry fields; scalar
  plugin keys are ignored on loading (extra=ignore).
- The key list is data-driven from `PluginConfigKeys` — no duplication.
