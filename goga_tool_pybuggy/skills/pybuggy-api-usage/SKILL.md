---
name: goga-tool-pybuggy-api-usage
description: Loads and provides pybuggy documentation (api, asserts) from .goga/usages/cooks/pybuggy/ — the reference for skills and tasks that work with pybuggy
---
# Pybuggy Runtime Usage

## Purpose

This skill provides documentation on consuming the pybuggy runtime. The documentation covers two cells:
`pybuggy/api` (HTTP requests from test fixtures and response handling) and `pybuggy/api/asserts`
(response-level and field-level response checks). This skill is the single source of context on the real pybuggy API.

Other skills and tasks (for example, the test automation stage) invoke this skill to obtain the current
reference for the API and the asserts. The reference is grounded in the project's cooks files, not in guesswork.

---

## Behavior

1. Check the directory `.goga/usages/cooks/pybuggy/`. If this directory is missing or empty, the pybuggy
   cooks files are not loaded: tell the user to run `goga tool pybuggy init` (this command copies the pybuggy
   usages documentation and registers it in `.goga/config.yml` under `pybuggy-<stem>`), and stop.

2. List all `*.md` files in `.goga/usages/cooks/pybuggy/` (recursively when subdirectories appear) and read
   every file. Each file maps to the usage key `pybuggy-<stem>` (e.g. `api` → `pybuggy-api`,
   `asserts` → `pybuggy-asserts`).

3. If `$ARGUMENTS` is passed (topic: `api` / `asserts` / any other stem), use only the files relevant to that
   topic; otherwise use all files.

4. Apply the documentation you have read to the caller's context: provide entities, methods, signatures, and
   consumption examples (`Api`, `Endpoint`, `ResponseWrapper`, `Expected`, `AssertField`, `Auth`, and the assert layer).
   Use only the actual content of the files as the source — never invent API details. Do not retell the files
   verbatim; provide an applicable reference instead.

5. Reference file paths so that the caller can read the full details when needed.
