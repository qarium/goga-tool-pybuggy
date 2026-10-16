# Pipelines

The primary way to create tests with pybuggy is the staged goga pipeline
(`PybuggyApiAutomate`): it automates API-test creation end to end — from topic
requirements to committed, accepted tests. When an accepted suite later breaks,
the companion `PybuggyApiFix` pipeline picks it up: it collects the failures,
classifies each cause with you, and drives the fixes to a reviewed, passing state.
When you want existing tests changed on your own request, the third line,
`PybuggyApiPatch`, carries the change: it collects your intents, analyzes their
impact, and drives the change to committed, accepted tests.

## Launch

```bash
goga pipeline pybuggy:api.automate   # create the tests
goga pipeline pybuggy:api.fix        # repair them when they break
goga pipeline pybuggy:api.patch      # change existing tests
```

Prerequisites: pybuggy installed (`goga install pybuggy`) and the environment
initialized (`goga tool pybuggy init` — see [Getting Started](../getting-started.md)).
Each pipeline works on the current git branch as its topic and drives the chain; every
artifact it produces lives in the topic's history directory
(`.goga/history/<year>/<topic>/`), addressed by `goga history path -f <artifact>`.

## In this section

- [The `api.automate` pipeline](api-automate.md) — the stage chain, the artifacts it
  produces, and how the test code gets built.
- [The `api.fix` pipeline](api-fix.md) — the repair cycle for failing suites: failure
  collection, cause classification, the fix plan, and the review verdict.
- [The `api.patch` pipeline](api-patch.md) — the change cycle for existing tests:
  intent collection, impact analysis, manifest application, and the plan-driven rework
  of the test code.
- [Workflows](workflows.md) — override or extend the
  pipeline for your project with a `.goga/workflows/pybuggy:<pipeline>.yml` file.