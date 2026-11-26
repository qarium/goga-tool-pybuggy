---
name: goga-tool-pybuggy-web-automate-testcases-intake
description: Input validation and context load — checks requirements.md, prints it verbatim, loads the goga context (goga-cell DSL, python rules, web cookbook, runtime reference) and the base Header block via goga-codemanifest-base with key resolution
---

# Pybuggy Web Topic Testcases — Intake

## Identity

You are responsible for loading the input data: you validate the requirements artifact, load it
into the context verbatim, and bring up the entire goga design context.

## Core Principle

requirements.md is already structured with stable identifiers (PAGE-<N>, REQ-<N>) — every subsequent
step of the pipeline reads it directly. The goga context (the DSL, the base Header block, the web
runtime reference) is loaded exactly once, here.

---

## Algorithm

### Step 1. Validate the input

1. Read the path printed by `goga history path -f requirements.md`. If the file is missing or empty —
   **STOP**: run the `goga-tool-pybuggy-web-automate-requirements` pipeline first.
2. Validate the structure: §2 (Topic pages) is non-empty; §3 (Functional requirements) contains `REQ-<N>`.
   If either check fails — **STOP**: return to the requirements pipeline.

### Step 2. Load the goga context

Load via the **Skill tool**:

- **`goga-cell`** — the DSL specification for cells and CODEMANIFEST.
- **`goga-cell-python`** — Python rules (snake_case, `location`).
- **`goga-tool-pybuggy-web-cookbook`** — principles of web test cells.
- **`goga-codemanifest-base`** — base usages/annotations from `.goga/config.yml`; capture the
  base Header block **verbatim**: `Usages` (`conventions`, `pybuggy-web` with paths) + `Annotations`.
- **`goga-tool-pybuggy-web-usage`** — the web runtime reference (page fixtures, step suggestions, cache).

Key resolution:

1. For each base `Usages` key, verify that the file at the path exists and is not empty
   (`pybuggy-web` → `.goga/usages/cooks/pybuggy/pybuggy-web.md`).
2. If a base key fails to resolve — **STOP** (ask the user to run
   `goga tool pybuggy init` kind web/both).

### Step 3. Load requirements into context

Load requirements.md into the context **verbatim** under the [TESTCASES_INTAKE] heading — it is the
input for all subsequent steps.

---

## Output Format

Fill in every section. Empty sections are forbidden.

```md
# [TESTCASES_INTAKE]

## Base Header Block

    Usages:
      conventions: .goga/usages/conventions.md
      pybuggy-web: .goga/usages/cooks/pybuggy/pybuggy-web.md
    Annotations: |
      [verbatim from .goga/config.yml]

[The base block is identical for all web cells of the topic; cell-specific usages are layered on top —
existing files only.]

## Key Resolution

| key         | path                                      | status   |
|-------------|-------------------------------------------|----------|
| pybuggy-web | .goga/usages/cooks/pybuggy/pybuggy-web.md | resolves |

## Requirements

[requirements.md, printed verbatim. Do not create a new format.]
```
