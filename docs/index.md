# goga-tool-pybuggy

**pybuggy** is a **goga**(<https://github.com/qarium/goga>) tool for testing: **API** —
it turns OpenAPI/Swagger specifications into ready-made pytest fixtures — HTTP client,
endpoint fixtures, response schemas, per-endpoint `meta.json` input contracts (query
parameters, request body, URL variables) — and wires everything into the consumer's test
suite. The package contains a pytest plugin and a CLI.

## What you get

- **CLI `goga tool pybuggy`** — initialize the environment (`goga tool pybuggy init`), pull specs from git
  (`goga tool pybuggy endpoint pull`), inspect endpoints (`list`, `info`), scaffold fixtures
  (`goga tool pybuggy endpoint generate` — response schemas, a per-endpoint `meta.json`
  input contract, and `api.py` fixtures) and report drift between the specs and those artifacts
  (`goga tool pybuggy endpoint diff` — read-only, one JSON document per endpoint, `{}` when they match).
- **pytest plugin** — a function-scoped `api` fixture (an HTTP client built from
  configuration), automatic recursive loading of the generated endpoint fixtures, CLI
  options for the test run, and flaky-rerun wiring.
- **Assert layer** — `Expect` (response-level dispatcher) and `AssertField`
  (field-level asserts) on top of the **matchcrest** matcher library.
- **API-test lifecycle** — staged goga pipelines that automate the suite end to end:
  `api.automate` (requirements → testcases → test cells → design → plan → acceptance)
  creates the tests, `api.fix` repairs them when they break.
- **Topic statuses** — every pipeline artifact marks a `pybuggy.*` status on the goga
  topic status scale: `goga history status` shows the latest reached stage of the
  automate line, the fix line, and the shared `pybuggy.bugs` marker — one status per
  line.

## Quickstart

Three commands in the target project root:

```bash
goga install pybuggy              # 1. install pybuggy into the goga environment
goga tool pybuggy init            # 2. bootstrap: goga project + tool config + conftest.py
goga pipeline pybuggy:api.automate   # 3. run the automated API-test lifecycle
```

The pipeline asks for the testing subject (the topic is the current git branch) and
drives the whole chain — requirements,
test cases, test code — until accepted `test_*.py` suites land in `tests/` (see
[Pipelines](pipelines/index.md)). The CLI and the manual workflow remain available for
fine-grained control: [CLI Reference](cli/init.md).

## Where to go next

- [Getting Started](getting-started.md) — end-to-end walkthrough.
- [Pipelines](pipelines/index.md) — the automated API-test lifecycle.
- [CLI Reference](cli/init.md) — every command with options and behavior.
- [Configuration](configuration.md) — `.goga/tools/pybuggy/config.yml`.
- [Matchers](matchers/index.md) — assertions and the matcher catalog.
- [Pytest Plugin](plugin/index.md) — enabling, fixtures, options.
