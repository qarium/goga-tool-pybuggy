# goga-tool-pybuggy

**pybuggy** is a **goga**(<https://github.com/qarium/goga>) tool for testing: **API** —
it turns OpenAPI/Swagger specifications into ready-made pytest fixtures — HTTP client,
endpoint fixtures, response schemas — and wires everything into the consumer's test
suite. The package contains a pytest plugin and a CLI.

## What you get

- **CLI `goga tool pybuggy`** — initialize the environment (`goga tool pybuggy init`), pull specs from git
  (`goga tool pybuggy endpoint pull`), inspect endpoints (`list`, `info`) and scaffold fixtures
  (`goga tool pybuggy endpoint generate`).
- **pytest plugin** — a function-scoped `api` fixture (an HTTP client built from
  configuration), automatic recursive loading of the generated endpoint fixtures, CLI
  options for the test run, and flaky-rerun wiring.
- **Assert layer** — `Expect` (response-level dispatcher) and `AssertField`
  (field-level asserts) on top of the **matchcrest** matcher library.
- **API-test lifecycle** — a staged goga pipeline (requirements → testcases → test cells →
  design → plan → acceptance) that automates test creation end to end.

## Quickstart

Three commands in the target project root:

```bash
goga install pybuggy              # 1. install pybuggy into the goga environment
goga tool pybuggy init            # 2. bootstrap: goga project + tool config + conftest.py
goga pipeline pybuggy:api.automate   # 3. run the automated API-test lifecycle
```

The pipeline asks for the feature under test and drives the whole chain — requirements,
test cases, test code — until accepted `test_*.py` suites land in `tests/` (see
[Pipelines](pipelines.md)). The CLI and the manual workflow remain available for
fine-grained control: [CLI Reference](cli/init.md).

## Where to go next

- [Getting Started](getting-started.md) — end-to-end walkthrough.
- [Pipelines](pipelines.md) — the automated API-test lifecycle.
- [CLI Reference](cli/init.md) — every command with options and behavior.
- [Configuration](configuration.md) — `.goga/tools/pybuggy/config.yml`.
- [Matchers](matchers/index.md) — assertions, the matcher catalog, helpers.
- [Pytest Plugin](plugin/index.md) — enabling, fixtures, options.
