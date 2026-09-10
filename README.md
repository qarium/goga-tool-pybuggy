# goga-tool-pybuggy

**pybuggy** is a **goga**(<https://github.com/qarium/goga>) tool for testing:
**API** — it turns OpenAPI/Swagger specifications into ready-made pytest fixtures — HTTP client,
endpoint fixtures, response schemas, per-endpoint `meta.json` input contracts (query
parameters, request body, URL variables) — and wires everything into the consumer's test
suite. The package contains a pytest plugin and a CLI.

**Documentation**: <https://qarium.github.io/goga-tool-pybuggy/>

## Quickstart

Three commands in the target project root:

```bash
goga install pybuggy                 # 1. install pybuggy into the goga environment
goga tool pybuggy init               # 2. bootstrap: goga project + tool config + conftest.py
goga pipeline pybuggy:api.automate   # 3. run the automated API-test lifecycle
```

The pipeline asks for the testing subject (the topic is the current git branch) and
drives the whole chain — requirements, test cases, test code — until accepted
`test_*.py` suites land in `tests/`. The full stage list and artifact chain:
[the `api.automate` lifecycle](https://qarium.github.io/goga-tool-pybuggy/pipelines/).
