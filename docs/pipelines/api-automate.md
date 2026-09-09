# The `api.automate` lifecycle

The staged pipeline automates API-test creation end to end — from topic requirements
to committed, accepted tests. Each stage is a dedicated goga skill; every stage except
`create-testcases` is a *communication* stage that involves you.

Need to adjust the pipeline for your project without forking it? See
[Workflows](workflows.md).

## Stages

| #  | Stage                 | Purpose                                                                                                              |
|----|-----------------------|----------------------------------------------------------------------------------------------------------------------|
| 1  | `create-requirements` | Collect detailed requirements for the topic under test → `requirements.md`                                           |
| 2  | `requirements-audit`  | Review the requirements artifact                                                                                     |
| 3  | `test-design`         | Design integration test cases (TC-`<N>`, REQ→TC traceability) → `testcases.md`                                       |
| 4  | `test-audit`          | Review the test cases                                                                                                |
| 5  | `prepare-testcases`   | Design the test cells (CODEMANIFEST per Routine) → `arch.md`                                                         |
| 6  | `review-testcases`    | Review the test-cells plan                                                                                           |
| 7  | `create-testcases`    | Materialize the test cells into `tests/<spec>/<id>/`                                                                 |
| 8  | `code-design`         | Design the test code (materialization of `test_*.py` from the cells) → `design.md`                                   |
| 9  | `design-review`       | Review the test design                                                                                               |
| 10 | `coding-plan`         | Compile the execution plan (with `pytest` as validation) → `plan.md`                                                 |
| 11 | `plan-review`         | Review the plan                                                                                                      |
| 12 | `commit-changes`      | Commit the work; ask the user whether the tests are ready for acceptance                                             |
| 13 | `accept-result`       | Accept the test results: consistency check, `pytest` run, triage of failures with the user, bug records in `bugs.md` |

The `create-requirements` stage opens the topic: once the testing subject is clarified, its intake runs
one idempotent `goga history ensure` — the topic is the current git branch. Every later stage addresses
artifacts with `goga history path -f <artifact>`.

> **Building the tests:** the design stages produce documents only. After `plan-review`
> approves `plan.md`, the test code is built with
> `goga build <path-to-plan>` — [goga](https://github.com/qarium/goga) executes the
> ralphex plan, writing each `test_*.py` from the plan's Tasks and running the Validation
> Commands (`pytest`). Stage 7 (`create-testcases`) materializes the test *cells*
> (CODEMANIFESTs under `tests/<spec>/<id>/`), not the test code — the `test_*.py` files
> appear only at build time.

## Artifacts

The pipeline accumulates one artifact per design stage in the topic's history directory —
the path printed by `goga history path -f <artifact>`
(`.goga/history/<year>/<topic>/`; the topic is the current git branch, created by the requirements
stage via `goga history ensure`):

```
requirements.md   # detailed requirements (REQ-<N>)
testcases.md      # test cases (TC-<N>) + coverage matrix
arch.md           # test-cells architecture plan
design.md         # test-code design document
plan.md           # ralphex execution plan
bugs.md           # triaged service bugs found at acceptance
tests/<spec>/<id>/  # the materialized test code (in the project tree)
```

## Topic status

Every artifact of the chain marks a status on the goga topic status scale — the package
registers one `pybuggy.*` status per artifact, so a pybuggy topic reports its latest
reached stage under its own name instead of the built-in axis:

| Artifact            | Status                                 |
|---------------------|----------------------------------------|
| `requirements.md`   | `pybuggy.automate.requirements-created`|
| `testcases.md`      | `pybuggy.automate.testcases-designed`  |
| `arch.md`           | `pybuggy.automate.arch-prepared`       |
| `design.md`         | `pybuggy.automate.code-designed`       |
| `plan.md`           | `pybuggy.automate.coding-planned`      |
| `completed/plan.md` | `pybuggy.automate.done`                |

Each automate status anchors above its built-in twin (`automate.done` above the built-in `done`), and
`goga history status` shows the latest reached stage of the topic. Read the scale with
`goga history status`; filter topics by any registered name with `goga history status -s <name>`.
Service bugs recorded in `bugs.md` are history records — they mark no status on the scale.

## How it relates to the rest

- When accepted suites break — now or later — the [`api.fix` lifecycle](api-fix.md)
  collects the failures and drives the repair cycle.
- The generated [`api/`](../cli/generate.md) fixtures are what the materialized tests consume.
- The pipeline stages are goga skills (`goga-tool-pybuggy-api-automate-*`) driven by the
  goga agent in the consumer project — the same project `goga tool pybuggy init` bootstraps
  (usage keys `pybuggy-api` / `pybuggy-asserts` teach the consumer's agent the runtime
  contracts).
