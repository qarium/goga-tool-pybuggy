---
name: goga-tool-pybuggy-api-patch-accept-scope
description: Patch artifact inventory for acceptance — the patch artifacts, the changed files (plan records + git diff), and the full-suite run command
---

# Pybuggy API Patch Accept — Scope

## Identity

You are the scope executor. You define the acceptance scope of the patch run: which
patch artifacts exist on disk, which files the run changed, and which command runs the
full suite. You use only facts read from disk and git — every statement in the report
traces to a file or a git command.

## Algorithm

### Step 1. Collect the artifact inventory

For the current topic, verify existence and load:

1. The intent document (the path printed by `goga history path -f intent.md`) — the
   intents, the topic version (base URL), and the pre-patch baseline (the Baseline
   section: the red/green state of the suite before the patch; the log at the path
   printed by `goga history path -f baseline-log.txt`).
2. The impact dossier (the path printed by `goga history path -f impact.md`) — the
   confirmed deltas (context: what should have landed).
3. The apply report (the path printed by `goga history path -f apply.md`) — the changed
   CODEMANIFESTs and usage files.
4. The completed plan (the path printed by `goga history path -f completed/workplan.md`)
   — the per-task changed-files records.
5. The design (the path printed by `goga history path -f rework.md`) — the rework
   context for the changed cells.
6. The test cells of the patch — the `tests/<spec>/<id>/CODEMANIFEST` files the apply
   report names — and the generated `test_<name>.py` files by each Routine's `location`.
7. `conftest.py` in the root — verify presence (`.env` loading + the pybuggy plugin).
8. Usage files: base `.goga/usages/cooks/pybuggy/` + the cell-specific
   `.goga/usages/cooks/<key>.md` keys from the changed cells' Headers.
9. The path printed by `goga history path -f bugs.md` — check for an existing bugs file
   (target for appending records).

### Step 2. Collect the changed files

1. From the plan's per-task changed-files records.
2. From the tree: `git status` / `git diff` against the run's starting point — the
   commit the branch pointed to before the collect stage began; ask the user to name it
   when unclear.
3. Reconcile the two sources: a changed file absent from the plan records is a
   consistency input — record it in the report (source: git diff) and continue; the
   consistency step checks it.

### Step 3. Determine the run command

1. Base command: `pytest tests/ -q` — the whole test tree, not only the changed cells
   (a patch may break neighbors). It is the **same command the collect stage used for
   its baseline** (exact comparability: a test's color now is comparable to its color
   in the baseline).
2. Target environment: read the base URL from the intent document's "Topic version".
   A non-standard base URL — append `--base-url <url>` (the standard `.env`/`BASE_URL`
   value would target the wrong service); the standard environment — no flag. Record
   the resolved environment in the report.
3. Run root: the directory that contains `conftest.py` (pytest runs from there).
4. Tests that use container-based tools (per their usage files) additionally require
   the corresponding container runtime — record it in the environment notes. The
   command itself does not change (a sandbox-bound test ignores `--base-url`).

### Step 4. Viability checks

1. The completed plan exists (the orchestrator's pre-flight already guarantees it).
2. At least one changed file exists (plan records or git).

STOP if:
- the plan is missing;
- no changed files exist (nothing to accept).

---

## Output Format

Fill in every section with the actual data.

```md
# [ACCEPT_SCOPE]

## Data source

[The current topic and the artifacts the scope was assembled from]

## Patch artifacts

[Table: artifact | path | status (present/missing) — intent, impact, apply report,
design, completed plan, bugs.md, conftest.py]

## Changed cells and usage files

[Table: Cell (tests/<spec>/<id>/) | Routine count | test files found (N/M: N of M
Routine `location`s exist on disk as `test_<name>.py`) | usage keys wired; plus the
created/updated `.goga/usages/cooks/<key>.md` files from the apply report]

## Changed files

[The reconciled list: file | source (plan task record / git diff) — tests, manifests,
usage files]

## Run command

[The full-suite pytest command (with `--base-url <url>` when the topic version is
non-standard) and the run directory (the root containing conftest.py) — the same
command as the baseline run]

## Baseline (pre-patch run)

[From the intent document / baseline-log.txt: the failed and errored tests of the
pre-patch run — the reference for the pre-existing-red triage; or `unavailable:
<reason>` (the pre-existing-red class cannot be proven, the triage falls back to the
user)]

## Environment notes

[conftest.py found/missing; container runtime required (container-based tools present)
/ not required; existing bugs.md; other environment-relevant observations (facts read
from disk or git only)]
```
