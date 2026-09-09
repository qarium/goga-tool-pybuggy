# The `api.fix` lifecycle

The staged pipeline repairs a failing test suite — from a failure report to reviewed,
passing tests. It is the counterpart of [`api.automate`](api-automate.md): once that
lifecycle has landed accepted `test_*.py` suites, `api.fix` picks them up when they
break. Each stage is a dedicated goga skill; every stage except `execute-fix-plan` is
a *communication* stage that involves you.

Need to adjust the pipeline for your project without forking it? See
[Workflows](workflows.md).

## Launch

```bash
goga pipeline pybuggy:api.fix
```

Prerequisites: an initialized pybuggy environment (see
[Getting Started](../getting-started.md)) and failing tests to work on. Describe the
failures in the pipeline argument (a pytest output, a CI log, a traceback) — or let
the pipeline run the suite locally for you and capture the output.

## Topic version

Before any collection, the pipeline fixes the **topic version** for the whole cycle —
the spec branch and the environment under test. It uses the values from the pipeline
argument when they name a branch and/or an environment; otherwise it asks you:

1. **Spec branch (`ref`)** — which spec version the tests must follow:
   - *default branch* — `pull` without `--ref`;
   - *feature branch* — enter the ref (`pull --ref <ref>`; several specs —
     `--ref <spec>:<ref>`);
   - *local spec* — no `pull` at all.
2. **Run environment (base URL)** — which service version is tested:
   - *standard* — the `.env` / `BASE_URL` default;
   - *explicit URL* — the environment where the version under test is deployed.

A feature branch combined with the standard environment triggers a warning question
(the branch contract may not match the default SUT); the confirmed choice is recorded
and holds for the entire cycle. Non-standard base URLs are passed to every run as
`pytest --base-url <url>`.

## Stages

| # | Stage              | Purpose                                                                                                                        |
|---|--------------------|--------------------------------------------------------------------------------------------------------------------------------|
| 1 | `collect-failures` | Fix the topic version; capture the failure data (argument, or a local `pytest` run) → `fix-collect.md`                         |
| 2 | `analyze-failures` | Build a per-failure dossier with evidence, then classify the cause *with you* → `fix-analysis.md`                              |
| 3 | `create-fix-plan`  | Group the classified failures into an executable plan of tasks and approve it → `fix-plan.md`                                  |
| 4 | `execute-fix-plan` | Run the plan tasks in order, each with its own verification; final full run → `fix-execute.md`                                 |
| 5 | `review-fixes`     | Verify the executed plan and the final run, triage findings with you, deliver the cycle verdict → `fix-review.md`              |
| 6 | `commit-changes`   | Commit all added and modified files                                                                                            |

## Task classes

The plan tasks are dispatched by cause class, each to a dedicated executor skill:

| Class         | Means                                                                               |
|---------------|-------------------------------------------------------------------------------------|
| `environment` | the run environment is broken — restore it                                          |
| `spec-drift`  | the spec changed — bring the cell in line with the new contract                     |
| `case-defect` | the test case itself is wrong — fix the Routine annotation and the test             |
| `test-defect` | the test code is wrong — fix the test per the Routine annotation                    |
| `service-bug` | the service is at fault — record a `BUG-<topic>-<N>` entry in the topic's `bugs.md` |

Every task gets up to **3 attempts** (one executor call = one attempt = actions plus
verification); a task that still fails after its budget surfaces in the review stage.

## Artifacts

The cycle accumulates its chain in the topic's history directory — the path printed by
`goga history path -f <artifact>` (`.goga/history/<year>/<topic>/`; the topic is the current git
branch, ensured by the collect stage's intake via `goga history ensure`):

```
fix-log.txt         # captured failure output (collect, local run)
fix-collect.md      # failure report + topic version
fix-analysis.md     # per-failure evidence and classification
fix-plan.md         # approved fix plan (tasks, order, checks)
fix-execute.md      # execution report per task
fix-log-final.txt   # final full-suite run output
fix-review.md       # review findings, decisions, cycle verdict
bugs.md             # service bugs recorded along the way
```

## Topic status

Every artifact of the cycle marks a status on the **fix line** of the goga topic status
scale — an independent chain anchored at the bottom of the scale, so it never reorders
the automate line:

| Artifact         | Status                    |
|------------------|---------------------------|
| `fix-collect.md` | `pybuggy.fix.collect`     |
| `fix-analysis.md`| `pybuggy.fix.analysis`    |
| `fix-plan.md`    | `pybuggy.fix.plan`        |
| `fix-execute.md` | `pybuggy.fix.execute`     |
| `fix-review.md`  | `pybuggy.fix.review`      |

A topic mid-repair therefore shows one maximal status per line — e.g.
`[pybuggy.fix.analysis] [pybuggy.automate.done]`. Service bugs recorded in `bugs.md`
mark the shared `pybuggy.bugs` marker (see
[api.automate — Topic status](api-automate.md#topic-status)).

## How it relates to the rest

- The cycle continues [`api.automate`](api-automate.md): failures triaged at acceptance
  or in later runs are what `api.fix` repairs, reusing the same cells and artifacts.
- The pipeline stages are goga skills (`goga-tool-pybuggy-api-fix-*`) driven by the
  goga agent in the consumer project.
