# Test Lifecycle — the `api.automate` pipeline

Beyond the CLI and the plugin, pybuggy ships a staged goga pipeline
(`PybuggyApiAutomate`) that automates API-test creation end to end: from feature
requirements to committed, accepted tests. Each stage is a dedicated goga skill; stages
marked *communication* involve the user.

## Stages

| # | Stage | Purpose |
|---|-------|---------|
| 1 | `create-requirements` | Collect detailed requirements for the feature under test → `docs/requirements/<feature>.md` |
| 2 | `requirements-audit` | Review the requirements artifact |
| 3 | `test-design` | Design integration test cases (TC-`<N>`, FR→TC traceability) → `docs/testcases/<feature>.md` |
| 4 | `test-audit` | Review the test cases |
| 5 | `prepare-testcases` | Design the test cells (CODEMANIFEST per Routine) → `docs/arch/<feature>.md` |
| 6 | `review-testcases` | Review the test-cells plan |
| 7 | `create-testcases` | Materialize the test cells into `tests/<spec>/<id>/` |
| 8 | `code-design` | Design the test code (materialization of `test_*.py` from the cells) → `docs/design/<feature>.md` |
| 9 | `design-review` | Review the test design |
| 10 | `coding-plan` | Compile the execution plan (with `pytest` as validation) → `docs/plans/<feature>.md` |
| 11 | `plan-review` | Review the plan |
| 12 | `commit-changes` | Commit the work; ask the user whether the tests are ready for acceptance |
| 13 | `accept-result` | Accept the test results: consistency check, `pytest` run, triage of failures with the user, bug records in `docs/bugs/<feature>.md` |

## Artifacts

The pipeline accumulates one artifact per design stage:

```
docs/requirements/<feature>.md   # detailed requirements (FR-<N>)
docs/testcases/<feature>.md      # test cases (TC-<N>) + coverage matrix
docs/arch/<feature>.md           # test-cells architecture plan
docs/design/<feature>.md         # test-code design document
docs/plans/<feature>.md          # ralphex execution plan
docs/bugs/<feature>.md           # triaged service bugs found at acceptance
tests/<spec>/<id>/               # the materialized test code
```

## How it relates to the rest

- The generated [`api/`](cli/generate.md) fixtures and the
  [`Api` runtime](api/index.md) are what the materialized tests consume.
- The pipeline stages are goga skills (`goga-tool-pybuggy-api-automate-*`) driven by the
  goga agent in the consumer project — the same project `pybuggy init` bootstraps
  (usage keys `pybuggy-api` / `pybuggy-asserts` teach the consumer's agent the runtime
  contracts).
