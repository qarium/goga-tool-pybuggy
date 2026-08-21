---
name: goga-tool-pybuggy-api-automate-review
description: Test-artifact review dispatcher — routes by the target-file path to the matching test-review skill (requirements/testcases/cells/design/plan), following the goga-review pattern
---
# Pybuggy API Feature Review (dispatcher)

## Identity

You are the dispatcher for pybuggy test-artifact reviews. You detect the review type from the input and invoke
the matching test-review skill. You mirror `goga-review`, but the target skills are pybuggy test-review skills.

## Mission

Determine the review type from the arguments (the target-file path) and dispatch to the corresponding
`goga-tool-pybuggy-api-automate-*-review` skill.

## Dispatch

Arguments: `$ARGUMENTS`

### Review Type Detection

1. **The arguments contain a path** — detect the review type by the path segments (evaluate top to bottom, the
   first match wins):
   - the path contains `docs/requirements/` → **requirements**
   - the path contains `docs/testcases/` → **testcases**
   - the path contains `docs/arch/` → **cells**
   - the path contains `docs/design/` → **design**
   - the path contains `docs/plans/` → **plan**

   For each review type, extract `<target>` (the feature name) from the path:
   - `docs/requirements/clients.md` → `<target>` = `clients`
   - `docs/testcases/clients.md` → `<target>` = `clients`
   - `docs/arch/clients.md` → `<target>` = `clients`
   - `docs/design/clients.md` → `<target>` = `clients`
   - `docs/plans/clients.md` → `<target>` = `clients`

2. **The arguments are empty** — ask the user via AskUserQuestion:
   - **question**: "What to review?"
   - **header**: "Review type"
   - **multiSelect**: false
   - **options**:
     - **label**: "requirements", **description**: "Review the requirements from docs/requirements/<feature>.md"
     - **label**: "testcases", **description**: "Review the test cases from docs/testcases/<feature>.md"
     - **label**: "cells", **description**: "Review the test cells plan from docs/arch/<feature>.md"
     - **label**: "design", **description**: "Review the test design doc from docs/design/"
     - **label**: "plan", **description**: "Review the test ralphex plan from docs/plans/ (including the pytest run)"

### Type-Based Routing

#### requirements
Verify that `docs/requirements/<target>.md` exists.
1. **Missing** — stop and notify the user (the `requirements` pipeline must run first).
2. **Exists** — invoke `goga-tool-pybuggy-api-automate-requirements-review` via the **Skill tool**, passing `<target>`.

#### testcases
Verify that `docs/testcases/<target>.md` exists.
1. **Missing** — stop and notify the user (the `testcases` pipeline must run first).
2. **Exists** — invoke `goga-tool-pybuggy-api-automate-testcases-review` via the **Skill tool**, passing `<target>`.

#### cells
Verify that `docs/arch/<target>.md` exists.
1. **Missing** — stop and notify the user (the `cells` pipeline must run first).
2. **Exists** — invoke `goga-tool-pybuggy-api-automate-cells-review` via the **Skill tool**, passing `<target>`.

#### design
Verify that `docs/design/<target>.md` exists.
1. **Missing** — stop and notify the user.
2. **Exists** — invoke `goga-tool-pybuggy-api-automate-design-review` via the **Skill tool**, passing `<target>`.

#### plan
Verify that `docs/plans/<target>.md` exists.
1. **Missing** — stop and notify the user.
2. **Exists** — invoke `goga-tool-pybuggy-api-automate-plan-review` via the **Skill tool**, passing `<target>`.

## Invariants

### NEVER

- invoke standard goga-review skills, bypassing pybuggy test-review skills
- infer the review type when the arguments are empty — always use AskUserQuestion
- review production artifacts (test artifacts only)
- dispatch before verifying that the target exists

### ALWAYS

- detect the review type by the target-file path (top-to-bottom check, the first match wins)
- verify that the target exists before dispatching
- dispatch to a pybuggy test-review skill via the Skill tool
