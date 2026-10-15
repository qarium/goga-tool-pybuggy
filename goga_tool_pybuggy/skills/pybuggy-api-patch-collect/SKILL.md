---
name: goga-tool-pybuggy-api-patch-collect
description: Collection of patch intents — intake of the user's requested test changes with scope constraints, the topic version (base URL; the spec is local), and the pre-patch baseline run, saved to the path printed by `goga history path -f intent.md` (+ `baseline-log.txt`)
---

# Pybuggy API Patch — Collect Intent

## Identity

You are the orchestrator of patch intent collection: you transform the user's request to
change existing tests into a structured intent document, and you pin the pre-patch
baseline — the red/green state of the suite before any change lands. The patch boundary
is by intent, not by test color — automate writes new tests, fix repairs what broke,
patch changes what the user asks to change; the run may start on red tests, and every
failure it meets is surfaced to the user.

## Pipeline

The steps run strictly in sequence, one step at a time. The pipeline validates each
step's output before the next step starts.

### Step 1. Create the topic

1. Run `goga history ensure` — idempotently creates the topic directory
   `.goga/history/<year>/<topic>/` of the current branch. A failure (not a repository,
   detached HEAD, git missing) — **STOP**: ask the user to run the pipeline from a branch.

Every artifact of the topic is addressed as `goga history path -f <artifact>`.

### Step 2. Intake the intents — WAIT

1. Read `$ARGUMENTS` — the patch request provided by the user. No description — **STOP**:
   request it and wait for the user's reply.
2. Extract every intent — several intents per run are allowed; each becomes its own
   section of the intent document and, later, its own group of the impact dossier and
   the plan.
3. For each intent capture:
   - the requested change, in the user's words (verbatim or close);
   - the category — one of:
     - fixture/tool replacement — replace a data fixture/tool and update its usage
       across tests
     - asserts — update/add/change
     - markers — add markers
     - sandbox re-binding — re-bind tests between sandbox and target env
     - Routine annotations — update
     - case removal — remove obsolete cases
     - usages references — update practices/usages references
     - cell move — structural moves of cells between specs
   - the scope constraints that select the affected tests — spec, directory, marker
     (at least one; several combined narrow the selection).
4. An intent whose scope cannot be resolved — ask the user to narrow it (AskUserQuestion,
   2–4 options); use only a scope the user confirmed.

### Step 3. Fix the topic version — WAIT

The topic version is the base URL of the service under test — mandatory context for
the whole run: every test-run command of the cycle depends on it.

- The spec is local: the run reads the spec files from the tree on disk and never
  pulls a ref.
- Resolution order: `$ARGUMENTS` names the base URL → use it without asking;
  otherwise ask the user:

1. **Base URL** — the service version under test: "Standard (.env / BASE_URL)";
   "Specify URL" — the environment where the version under test is deployed.
   Record the confirmed decision either way. Sandbox-bound tests ignore
   `--base-url`; the flag still governs the unbound tests of the run.

### Step 4. Run the pre-patch baseline

The baseline fixes the red/green state of the suite before any patch change lands — the
accept stage reads it to separate pre-existing reds from patch-caused failures, with no
second run against the starting commit.

1. Run the full suite with the same command the acceptance will use — from the
   directory containing `conftest.py`, with the topic version of Step 3:
   `pytest tests/ -q [--base-url <url>] 2>&1 | tee "$(goga history path -f baseline-log.txt)"`
   (a repeated patch cycle overwrites the log).
2. Parse the outcome: the passed/failed/error counts and the exact list of the failed
   and errored tests (test ids) — they go into the Baseline section of the intent
   document.
3. The environment unavailable (pytest or the plugin fails to start, the SUT does not
   respond, a container-based tool fails to start) — do **not** stop: record
   `unavailable: <reason>` in the Baseline section and proceed; the accept stage then
   falls back to the user's judgment for the pre-existing-red determination.
4. A green baseline is not required — the run may legitimately start on red tests; the
   baseline records them, it does not gate them.

### Step 5. Produce the intent document

1. Save the document to the path printed by `goga history path -f intent.md` (a repeated
   patch cycle in the same topic overwrites it — latest cycle wins, history stays in git).
2. Fill in every section; an empty section = an incomplete step = a pipeline STOP.

```md
# Patch Intents

## Original request

[Verbatim or close to the source text: what the user said]

## Topic version

[Base URL: standard / <url> | source: $ARGUMENTS / user answer]

## Baseline (pre-patch run)

[The command; the outcome: passed / failed / error counts; the list of the failed and
errored tests (test ids) — or `unavailable: <reason>` (the environment failure); the
log at `goga history path -f baseline-log.txt`]

## Intents

### Intent 1: <short name, 2–5 words>

- Category: [fixture/tool replacement | asserts | markers | sandbox re-binding | Routine
  annotations | case removal | usages references | cell move]
- Requested change: [what must change, in the user's words]
- Scope constraints: [spec / directory / marker — at least one; what selects the affected tests]

## Open questions

[What requires clarification at the analyze stage. Write `none` if there is nothing.]
```

### Step 6. Present the intent document for approval — WAIT

The stage's deliverable is the document's content, not its path. Output the full content
of the saved intent document to the user (the baseline appears as its parsed summary —
counts and failed test ids; the raw `baseline-log.txt` is not dumped), then ask for the
approval (AskUserQuestion, 2–4 options):

- **Approve** — the stage ends; the analyze stage starts only now.
- **Request changes** — the user names what to change; apply the changes to the
  document and present it again — the approval loop repeats until an explicit approval.

The pipeline never moves to the next stage on a printed artifact alone — an unapproved
artifact stops it.

## Invariants

### NEVER

- invent an intent or a scope the user did not state
- start without a topic (a branch is mandatory) or without a description
- leave the topic version unresolved — every later run command depends on it
- gate the run on a green baseline — red tests at the start are recorded, never blocked
- run the baseline against an environment other than the topic version of Step 3
- proceed to the analyze stage without the user's approval of the intent document

### ALWAYS

- record several intents as separate sections — one section per intent
- capture scope constraints (spec/directory/marker, at least one) for every intent
- run the pre-patch baseline (the acceptance full-suite command) and record the
  red/green state of every test — or its unavailability with the reason
- address artifacts as `goga history path -f <artifact>`
- present the saved intent document to the user in full and obtain the explicit
  approval — the analyze stage starts only after it
