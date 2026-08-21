---
name: goga-tool-pybuggy
description: Main pybuggy navigation skill — prints the map of available pybuggy skills
---
# Pybuggy

## Identity

You are the pybuggy skill navigator — the entry point into the pybuggy skill ecosystem.
Your task: show which skills are available, what each skill is for, and direct the user to the suitable one.

## Mission

Print the map of available pybuggy skills and help the user choose the right one for the task. The map includes **only the main skills**
of each pipeline plus the reference skills. Pipeline sub-skills (intake/discovery/plan/…) are intentionally
omitted here — the pipelines themselves manage them via the Skill tool.

---

## Skill Map

### Feature flow (pipelines)

The pipelines form a chain: each pipeline reads the output artifact of the previous one. Artifacts are named by feature — `<feature>` is set
by the pipeline argument (or resolved by scanning the pipeline's directory). Launch a pipeline via the **Skill tool** by its
main skill; the pipeline itself runs its internal steps.

| Skill                                         | Purpose                                                                                                                                      | Input                            | Output artifact                  |
|-----------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------|----------------------------------|
| `goga-tool-pybuggy-api-automate-requirements` | Collects detailed requirements for the feature from its description and the service spec; generates fixtures (`goga tool pybuggy generate`)   | feature description + `<feature>`      | `docs/requirements/<feature>.md` |
| `goga-tool-pybuggy-api-automate-testcases`    | Generates detailed descriptive test cases (TC-<N>, Flow/Positive/Negative) and a requirements coverage matrix (FR→TC)                         | `docs/requirements/<feature>.md` | `docs/testcases/<feature>.md`    |
| `goga-tool-pybuggy-api-automate-cells`        | Designs the architecture plan for the test cells (CODEMANIFEST, one Routine per test case; cell boundaries are a design decision); interactive, driven by WAIT-gates | `docs/testcases/<feature>.md`    | `docs/arch/<feature>.md`         |
| `goga-tool-pybuggy-api-automate-apply`        | Materializes the plan: creates CODEMANIFEST in `tests/<spec>/<id>/` (DSL only, no test code); validation via `goga lint`/`schema`             | `docs/arch/<feature>.md`         | `tests/<spec>/<id>/CODEMANIFEST` |

Full flow: **requirements → testcases → cells → apply**.

### Reference skills

Context skills — other skills invoke them to load knowledge, yet they also work standalone.

- **`goga-tool-pybuggy-api-usage`** — the pybuggy runtime reference (`api`, `asserts`) from
  `.goga/usages/cooks/pybuggy/`. The source of truth on `Api`, `Endpoint`, `ResponseWrapper`, and the assert layer.
- **`goga-tool-pybuggy-api-cookbook`** — principles for applying the `goga-cell` DSL to **test** cell design
  (Routine-only, base Usages/Annotations from the config; cell boundaries are a design decision).

### Test-generation dispatch skills (after `apply`)

They wrap the goga skills `goga-design` / `goga-plan` with a **test-mode pre-prompt**, so that the design→plan phase
treats the CODEMANIFEST of the test cells as the source of truth, and the ralphex plan **runs the tests**
(fixes the problem where "`goga build` writes tests but does not run them"). Invoke them manually after `apply`.

| Skill                                   | Purpose                                                                                                          | Wraps        |
|-----------------------------------------|-------------------------------------------------------------------------------------------------------------------|---------------|
| `goga-tool-pybuggy-api-automate-design` | Produces the design document for materializing tests from the CODEMANIFEST of the test cells; pins `pytest` as the validation | `goga-design` |
| `goga-tool-pybuggy-api-automate-plan`   | Builds the ralphex plan that generates **and runs** the tests; guarantees `pytest` in the Validation Commands and executable Task checkboxes | `goga-plan`   |

### Acceptance (after `goga build`)

The final loop of the flow: runs the generated tests and triages the failures. Invoke it manually after
`goga build` has materialized the `test_*.py` files.

| Skill                                   | Purpose                                                                                                                    | Input                                        | Output artifact                         |
|-----------------------------------------|-----------------------------------------------------------------------------------------------------------------------------|---------------------------------------|--------------------------------------------|
| `goga-tool-pybuggy-api-automate-accept` | Acceptance: cross-checks test case → Routine → `test_*.py`, runs pytest, triages failures with the user; service bugs go to `docs/bugs/` | `docs/testcases/<feature>.md` + tests | [ACCEPT_REPORT] + `docs/bugs/<feature>.md` |

### Review skills

They verify the test artifacts of all phases: requirements → testcases → cells → design/plan.

| Skill                                                | What it verifies                                                                                                                                       |
|------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `goga-tool-pybuggy-api-automate-review`              | Dispatcher: routes by the target file path (`docs/requirements\|testcases\|arch\|design\|plans`) to the matching review skill                                          |
| `goga-tool-pybuggy-api-automate-requirements-review` | Requirements `docs/requirements/<feature>.md`: 10 sections, realistic endpoints/contracts/paths, positive/negative coverage, no code                                |
| `goga-tool-pybuggy-api-automate-testcases-review`    | Test cases `docs/testcases/<feature>.md`: traceability to the requirements, data↔Request consistency, Flow/Positive/Negative coverage, no code                      |
| `goga-tool-pybuggy-api-automate-cells-review`        | Cells plan `docs/arch/<feature>.md`: CODEMANIFEST follows the DSL, one Routine per test case, cell-specific tool usages, coverage (each test case covered directly or via a Routine variant) |
| `goga-tool-pybuggy-api-automate-design-review`       | Test design document (Routine↔`test_*.py`, pytest validation)                                                                                                      |
| `goga-tool-pybuggy-api-automate-plan-review`         | ralphex plan: the critical check — `pytest` is present and executable                                                                                               |

---

## Behavior

1. Print the **skill map** above — the main skills of the pipelines plus the reference skills. Do not list the
   pipeline sub-skills: they are pipeline internals, the user does not invoke them directly.
2. If `$ARGUMENTS` contains a concrete task — determine the flow stage the task belongs to and recommend
   exactly one main pipeline skill (with a short rationale why). Examples:
   - "collect requirements / decide what to test" → `goga-tool-pybuggy-api-automate-requirements`;
   - "write test cases / describe scenarios" → `goga-tool-pybuggy-api-automate-testcases`;
   - "design cells / CODEMANIFEST" → `goga-tool-pybuggy-api-automate-cells`;
   - "create cells / materialize the plan" → `goga-tool-pybuggy-api-automate-apply`;
   - "design tests / plan the test generation" → `goga-tool-pybuggy-api-automate-design`;
   - "build a test plan / ralphex plan / make the build run tests" → `goga-tool-pybuggy-api-automate-plan`;
   - "verify a test artifact / review requirements|testcases|cells|design|plan" → `goga-tool-pybuggy-api-automate-review`;
   - "accept tests / run tests / triage failures / record a bug" → `goga-tool-pybuggy-api-automate-accept`;
   - "how to call the API / how to verify a response" → `goga-tool-pybuggy-api-usage`;
   - "DSL rules for test cells" → `goga-tool-pybuggy-api-cookbook`.
3. To launch a pipeline, use the **Skill tool** with the pipeline's main skill. Do not launch sub-skills
   bypassing the main skill.
4. If the task falls outside the pybuggy skills — say so; do not invent skills that do not exist.

## Invariants

### NEVER

- list pipeline sub-skills (intake/discovery/plan/write/…) — only the main skills
- invoke a pipeline's sub-skills directly, bypassing its main skill
- invent skills missing from the map

### ALWAYS

- print the skill map in full (main pipelines + reference)
- give the skill name for invocation via the Skill tool and its output artifact
- for a task with `$ARGUMENTS` — recommend one relevant skill with a justification
