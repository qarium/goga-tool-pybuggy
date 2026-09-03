# The `api.automate` lifecycle

The staged pipeline automates API-test creation end to end — from topic requirements
to committed, accepted tests. Each stage is a dedicated goga skill; every stage except
`create-testcases` is a *communication* stage that involves you.

Need to adjust the pipeline for your project without forking it? See
[Workflows](workflows.md).

## Stages

| #  | Stage                 | Purpose                                                                                                                           |
|----|-----------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| 1  | `create-requirements` | Collect detailed requirements for the topic under test → `docs/requirements/<topic>.md`                                           |
| 2  | `requirements-audit`  | Review the requirements artifact                                                                                                  |
| 3  | `test-design`         | Design integration test cases (TC-`<N>`, REQ→TC traceability) → `docs/testcases/<topic>.md`                                        |
| 4  | `test-audit`          | Review the test cases                                                                                                             |
| 5  | `prepare-testcases`   | Design the test cells (CODEMANIFEST per Routine) → `docs/arch/<topic>.md`                                                         |
| 6  | `review-testcases`    | Review the test-cells plan                                                                                                        |
| 7  | `create-testcases`    | Materialize the test cells into `tests/<spec>/<id>/`                                                                              |
| 8  | `code-design`         | Design the test code (materialization of `test_*.py` from the cells) → `docs/design/<topic>.md`                                   |
| 9  | `design-review`       | Review the test design                                                                                                            |
| 10 | `coding-plan`         | Compile the execution plan (with `pytest` as validation) → `docs/plans/<topic>.md`                                                |
| 11 | `plan-review`         | Review the plan                                                                                                                   |
| 12 | `commit-changes`      | Commit the work; ask the user whether the tests are ready for acceptance                                                          |
| 13 | `accept-result`       | Accept the test results: consistency check, `pytest` run, triage of failures with the user, bug records in `docs/bugs/<topic>.md` |

> **Building the tests:** the design stages produce documents only. After `plan-review`
> approves `docs/plans/<topic>.md`, the test code is built with
> `goga build <path-to-plan>` — [goga](https://github.com/qarium/goga) executes the
> ralphex plan, writing each `test_*.py` from the plan's Tasks and running the Validation
> Commands (`pytest`). Stage 7 (`create-testcases`) materializes the test *cells*
> (CODEMANIFESTs under `tests/<spec>/<id>/`), not the test code — the `test_*.py` files
> appear only at build time.

## Artifacts

The pipeline accumulates one artifact per design stage:

```
docs/requirements/<topic>.md   # detailed requirements (REQ-<N>)
docs/testcases/<topic>.md      # test cases (TC-<N>) + coverage matrix
docs/arch/<topic>.md           # test-cells architecture plan
docs/design/<topic>.md         # test-code design document
docs/plans/<topic>.md          # ralphex execution plan
docs/bugs/<topic>.md           # triaged service bugs found at acceptance
tests/<spec>/<id>/               # the materialized test code
```

## How it relates to the rest

- When accepted suites break — now or later — the [`api.fix` lifecycle](api-fix.md)
  collects the failures and drives the repair cycle.
- The generated [`api/`](../cli/generate.md) fixtures are what the materialized tests consume.
- The pipeline stages are goga skills (`goga-tool-pybuggy-api-automate-*`) driven by the
  goga agent in the consumer project — the same project `goga tool pybuggy init` bootstraps
  (usage keys `pybuggy-api` / `pybuggy-asserts` teach the consumer's agent the runtime
  contracts).
