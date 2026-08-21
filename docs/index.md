# goga-tool-pybuggy

**pybuggy** is a pytest plugin and CLI that bootstrap a goga-project for API testing:
they turn OpenAPI/Swagger specifications into ready-made pytest fixtures —
HTTP client, endpoint fixtures, response schemas — and wire everything into the
consumer's test suite.

## What you get

- **CLI `goga tool pybuggy`** — initialize the environment (`goga tool pybuggy init`), pull specs from git
  (`goga tool pybuggy endpoint pull`), inspect endpoints (`list`, `info`) and scaffold fixtures
  (`goga tool pybuggy endpoint generate`).
- **pytest plugin** — a function-scoped `api` fixture (an `Api` HTTP client built from
  configuration), automatic recursive loading of the generated endpoint fixtures, CLI
  options for the test run, and flaky-rerun wiring.
- **HTTP runtime** — `Api` (a composition over `resq.Session`), `Endpoint`
  (a callable route), `ResponseWrapper` (a context manager over the response).
- **Assert layer** — `Expected` (response-level dispatcher) and `AssertField`
  (field-level asserts) on top of the **matchcrest** matcher library.
- **API-test lifecycle** — a staged goga pipeline (requirements → testcases → test cells →
  design → plan → acceptance) that automates test creation end to end.

## Quickstart

```bash
# in the target project root
goga tool pybuggy init                    # goga project + tool config + root conftest.py
goga tool pybuggy endpoint pull           # download specs from git sources
goga tool pybuggy endpoint list           # inspect available endpoints
goga tool pybuggy endpoint generate -s shop   # scaffold api/<spec>/<endpoint>/ fixtures
pytest                          # run the suite (plugin auto-loads fixtures)
```

## Where to go next

- [Getting Started](getting-started.md) — end-to-end walkthrough.
- [CLI Reference](cli/init.md) — every command with options and behavior.
- [Configuration](configuration.md) — `.goga/tools/pybuggy/config.yml`.
- [HTTP API](api/index.md) — `Api`, `Endpoint`, `ResponseWrapper`.
- [Assertions](api/asserts.md) — `Expected` and `AssertField` check catalog.
- [Matchers (matchcrest)](matchcrest/index.md) — the matcher library.
- [Pytest Plugin](plugin/index.md) — enabling, fixtures, options.
- [Test Lifecycle](lifecycle.md) — the automated API-test pipeline.
- [Internals](internals/spec.md) — spec parsing and output formatting.

## Running the CLI

The console command and the module form are equivalent:

```bash
goga tool pybuggy endpoint list
python -m goga_tool_pybuggy endpoint list
```

A global option `--env-file` loads environment variables **before** any subcommand runs
(the flag must precede the subcommand):

```bash
goga tool pybuggy --env-file ./my.env endpoint list   # explicit file (must exist)
goga tool pybuggy endpoint list                       # implicit .env from CWD (absence is fine)
```

Loaded values never override variables already set in the environment (`override=False`).

## Test reruns

For a flaky individual test, apply the `retries` decorator (built on the `flaky` package):

```python
from goga_tool_pybuggy import retries

@retries(max_runs=3)
def test_something(): ...

@retries(max_runs=5, min_passes=2, delay=1)
def test_flaky_endpoint(): ...
```

For suite-wide reruns driven by configuration, see
[Pytest Plugin — flaky reruns](plugin/index.md#what-enabling-wires).
