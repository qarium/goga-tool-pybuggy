# Pipelines

The primary way to create tests with pybuggy is the staged goga pipeline
(`PybuggyApiAutomate`): it automates API-test creation end to end — from topic
requirements to committed, accepted tests.

## Launch

```bash
goga pipeline pybuggy:api.automate
```

Prerequisites: pybuggy installed (`goga install pybuggy`) and the environment
initialized (`goga tool pybuggy init` — see [Getting Started](../getting-started.md)).
The pipeline asks for the topic under test and drives the chain; `<topic>` names
every artifact it produces.

## In this section

- [The `api.automate` pipeline](api-automate.md) — the stage chain, the artifacts it
  produces, and how the test code gets built.
- [Workflows](workflows.md) — override or extend the
  pipeline for your project with a `.goga/workflows/pybuggy:<pipeline>.yml` file.