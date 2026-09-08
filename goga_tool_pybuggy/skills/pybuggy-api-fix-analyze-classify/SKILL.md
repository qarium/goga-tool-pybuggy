---
name: goga-tool-pybuggy-api-fix-analyze-classify
description: Classify the root cause of each test failure jointly with the user
---
# Pybuggy API Fix Analyze — Classify

## Identity

For every failed test, you determine the root cause of the failure and assign it to exactly one class. You make each decision together with the user.

## Algorithm

### Step 1. Cause classes

| Class         | Symptom                                                                                        | Plan direction                                               |
|---------------|------------------------------------------------------------------------------------------------|--------------------------------------------------------------|
| `spec-drift`  | the spec has changed: `endpoint diff` is non-empty                                             | regenerate the artifacts + update the Routine and the tests   |
| `service-bug` | diff is empty; the Routine and the test comply with the contract; the service deviates from the spec | file a bug record in `goga history path -f bugs.md`                |
| `test-defect` | the test distorts the Routine: data, assert, import, materialization                           | fix `test_*.py`                                              |
| `case-defect` | the Routine (annotation) contradicts the spec/schemas                                          | update the Routine in the CODEMANIFEST                       |
| `environment` | SUT/env/network/tools                                                                          | restore the environment/dependencies                         |

The classes form an exhaustive set: every failure maps to exactly one of them.

### Step 2. Analyze each failure — WAIT

Process each failure from [FIX_EVIDENCE], one failure per message:

1. Present the dossier, the evidence, and the class hypothesis.
2. Ask the user to confirm the hypothesis or select a different class from the table.
3. Continue the analysis of the same failure — additional questions and further evidence requests — until the class is concrete (one of the five).
4. Record the class, the rationale, and the user decision.

### Step 3. Produce [FIX_CLASSIFICATION]

Assemble the [FIX_CLASSIFICATION] artifact from the recorded classifications.

---

## Output format

Fill in every section. Empty sections are prohibited.

```md
# [FIX_CLASSIFICATION]

## Classification
[Table: test | class | rationale | user decision | plan direction]

## Distribution by classes
[Class → count]
```
