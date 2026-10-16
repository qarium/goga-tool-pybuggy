# TODO — release-2-0-1 (Bugfix)

## Task

Source: user answer to `autonomous_execution.q1` (Bugfix flow, 2026-10-13).

When a spec name in `.goga/tools/pybuggy/config.yml` contains a hyphen (e.g. `specs.some-spec:`),
the generated directory keeps the hyphen — `api/some-spec` — and tests are generated the same way.
A hyphenated path is not importable as a Python module, which breaks the generated code/tests.

Requirement: normalize the name so that `-` becomes `_`:

- either at `init` time (when the spec scaffold is created from config),
- or at generation time (always generate `_`-based directories/module names),

keeping CODEMANIFEST/implementation/.usages triple consistency.

## Acceptance

- A config entry `specs.some-spec` produces `api/some_spec/…` (and matching tests) with importable module names.
- No regression for already-valid underscore/alphanumeric spec names.
