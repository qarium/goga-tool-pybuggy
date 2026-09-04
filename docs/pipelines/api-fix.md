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

| #  | Stage              | Purpose                                                                                          |
|----|--------------------|--------------------------------------------------------------------------------------------------|
| 1  | `collect-failures` | Fix the topic version; capture the failure data (argument, or a local `pytest` run) → `docs/fix/<topic>-collect.md` |
| 2  | `analyze-failures` | Build a per-failure dossier with evidence, then classify the cause *with you* → `docs/fix/<topic>-analysis.md` |
| 3  | `create-fix-plan`  | Group the classified failures into an executable plan of tasks and approve it → `docs/fix/<topic>-plan.md` |
| 4  | `execute-fix-plan` | Run the plan tasks in order, each with its own verification; final full run → `docs/fix/<topic>-execute.md` |
| 5  | `review-fixes`     | Verify the executed plan and the final run, triage findings with you, deliver the cycle verdict → `docs/fix/<topic>-review.md` |
| 6  | `commit-changes`   | Commit all added and modified files (except `docs/<defines|proposals|tasks|arch|design|plans>`) |

## Task classes

The plan tasks are dispatched by cause class, each to a dedicated executor skill:

| Class          | Means                                                                     |
|----------------|---------------------------------------------------------------------------|
| `environment`  | the run environment is broken — restore it                                |
| `spec-drift`   | the spec changed — bring the cell in line with the new contract            |
| `case-defect`  | the test case itself is wrong — fix the Routine annotation and the test    |
| `test-defect`  | the test code is wrong — fix the test per the Routine annotation           |
| `service-bug`  | the service is at fault — record a `BUG-<topic>-<N>` entry in `docs/bugs/<topic>.md` |

Every task gets up to **3 attempts** (one executor call = one attempt = actions plus
verification); a task that still fails after its budget surfaces in the review stage.

## Artifacts

The cycle accumulates its chain under `docs/fix/`:

```
docs/fix/<topic>-log.txt         # captured failure output (collect, local run)
docs/fix/<topic>-collect.md      # failure report + topic version
docs/fix/<topic>-analysis.md     # per-failure evidence and classification
docs/fix/<topic>-plan.md         # approved fix plan (tasks, order, checks)
docs/fix/<topic>-execute.md      # execution report per task
docs/fix/<topic>-log-final.txt   # final full-suite run output
docs/fix/<topic>-review.md       # review findings, decisions, cycle verdict
docs/bugs/<topic>.md             # service bugs recorded along the way
```

## How it relates to the rest

- The cycle continues [`api.automate`](api-automate.md): failures triaged at acceptance
  or in later runs are what `api.fix` repairs, reusing the same cells and artifacts.
- The pipeline stages are goga skills (`goga-tool-pybuggy-api-fix-*`) driven by the
  goga agent in the consumer project.
