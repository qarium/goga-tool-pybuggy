---
name: goga-tool-pybuggy-api-fix-collect-intake
description: Determine the failure-data source and run tests locally, saving the output to the path printed by `goga history path -f fix-log.txt`
---
# Pybuggy API Fix Collect — Intake

## Identity

You determine the source of failure data: either a problem description supplied by the user, or a local test run. If the local test run is the chosen source, you execute that run yourself.

## Algorithm

### Step 1. Read the problem description

1. `$ARGUMENTS` contains the description — record it verbatim (it goes into the report exactly as given).
2. No description — ask the user (AskUserQuestion, 2 options):
   - provide a problem description;
   - run the tests locally.

### Step 2. Assess data sufficiency

1. The description contains failure data (pytest output, CI log, traceback) — source: description.
2. A description exists but contains no failure data — ask: supplement the description with the output, or run the tests locally.

### Step 3. Determine the topic version — WAIT

The spec branch (ref) and the run environment (base URL) are mandatory context for the entire fix cycle: the run command, drift analysis, and task verification all depend on them. Resolution order: `$ARGUMENTS` names the branch and/or the environment → use those values without asking; otherwise ask the user:

1. **Spec branch (ref)**:
   - "Default branch" — pull without `--ref`;
   - "Feature branch" — enter a ref (pull with `--ref <ref>`; multiple specs — `--ref <spec>:<ref>`);
   - "Local spec, no pull".
2. **Run environment (base URL)** — the service version under test:
   - "Standard (.env / BASE_URL)";
   - "Specify URL" — the environment where the version under test is deployed.
   Feature branch + standard environment — re-ask with a warning (the branch contract vs the default SUT); record the confirmed decision.

Offer hints extracted from the failure data (the host in connection-error tracebacks; the CI job branch in the log header) as a ready-made question option ("<url> (found in the log)") — a hint, not a decision: the topic version is selected for the current cycle, not taken from the previous run. If the traces point to a different environment/branch than the selected version — record that discrepancy in the "Topic version" section.

The recorded topic version applies to the whole cycle: write it into [FIX_INTAKE] and into the collect artifact (the "Topic version" section).

### Step 4. Execute the local test run

This step runs when a local run was selected (Step 1 or Step 2); with the "description" source, skip this step.

1. Run root — the directory containing `conftest.py` (pytest runs from it).
2. Scope — from the description: the specific tests/directories it names; if undefined — all tests.
3. Target environment — from the topic version (Step 3): non-standard base URL — add `--base-url <url>` to the command (the service version under test lives there; the standard `.env`/`BASE_URL` would send the requests to the wrong target). Standard — no flag.
4. Execute: `pytest <paths> -q [--base-url <url>] 2>&1 | tee "$(goga history path -f fix-log.txt)"` (run
   `goga history ensure` first if the topic directory does not exist; a re-run overwrites the log).
5. Record: the command (with the environment), the log path, the exit code, the summary line (passed/failed/errors/skipped).

### Step 5. Produce [FIX_INTAKE]

STOP:

- the user provided no description and declined the local run;
- pytest or the plugin does not start, or the SUT does not respond — ask the user: restore the environment and continue / finish the collection.

---

## Output format

Fill in every section. Empty sections are forbidden.

```md
# [FIX_INTAKE]

## Data source

[description / local run]

## Problem description (verbatim)

[$ARGUMENTS; "not provided" — if empty]

## Failure data in the description

[output/logs/traceback, if any; "none" — if absent]

## Topic version

[Spec branch: default / <ref> (per-spec if different) / local | Environment: standard / <url> | source: $ARGUMENTS / user answer (hint option from the log) | Discrepancy with the log: none / <what was found>]

## Run

[Command: ... (with
`--base-url <url>` — if the topic environment is non-standard) | Log: the path printed by `goga history path -f fix-log.txt` | Exit code: ... | Summary: passed/failed/errors/skipped. "run not performed" — if the source was description only]

## Open questions

[what is missing for the collection. Empty if nothing]
```
