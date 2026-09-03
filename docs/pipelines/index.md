# Pipelines

The primary way to create tests with pybuggy is the staged goga pipeline
(`PybuggyApiAutomate`): it automates API-test creation end to end — from topic
requirements to committed, accepted tests. When an accepted suite later breaks,
the companion `PybuggyApiFix` pipeline picks it up: it collects the failures,
classifies each cause with you, and drives the fixes to a reviewed, passing state.

## Launch

```bash
goga pipeline pybuggy:api.automate   # create the tests
goga pipeline pybuggy:api.fix        # repair them when they break
```

Prerequisites: pybuggy installed (`goga install pybuggy`) and the environment
initialized (`goga tool pybuggy init` — see [Getting Started](../getting-started.md)).
Each pipeline asks for the topic under test and drives the chain; `<topic>` names
every artifact it produces.

## In this section

- [The `api.automate` pipeline](api-automate.md) — the stage chain, the artifacts it
  produces, and how the test code gets built.
- [The `api.fix` pipeline](api-fix.md) — the repair cycle for failing suites: failure
  collection, cause classification, the fix plan, and the review verdict.
- [Workflows](workflows.md) — override or extend the
  pipeline for your project with a `.goga/workflows/pybuggy:<pipeline>.yml` file.