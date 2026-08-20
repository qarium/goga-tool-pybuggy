# goga-tool-pybuggy

pytest plugin and CLI that bootstrap a goga-project for API testing with pybuggy.

## Getting started: `pybuggy init`

Run `pybuggy init` in the target project root. It interactively initializes the
goga-project, builds the tool config, and generates the wiring the plugin needs
(`.goga/config.yml`, `.goga/Dockerfile`, `.goga/tools/pybuggy/config.yml`, root
`conftest.py`).

Behavior notes:

- **Init runs offline** — the goga "Download base convention" question is never
  asked and no network requests are made during initialization.
- **`.goga/usages/conventions.md` is package-owned** — on every successful run
  it is overwritten with the test convention shipped inside this package
  (pytest configuration, logging, Allure reporting). Local edits to that file
  are not preserved; keep project-specific rules elsewhere. A legacy
  goga-downloaded convention in the slot migrates automatically.
- Existing files (`.goga/config.yml`, `.goga/tools/pybuggy/config.yml`,
  `conftest.py`) are only overwritten after an explicit confirmation
  (default: no); the conventions slot above is the one exception.
- Usage keys `conventions`, `pybuggy-api`, and `pybuggy-asserts` and their
  annotation lines are registered in `.goga/config.yml` under
  `codemanifest` (idempotent; pre-existing user-defined keys are never
  overwritten).
