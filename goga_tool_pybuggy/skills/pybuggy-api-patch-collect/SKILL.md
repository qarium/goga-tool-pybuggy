---
name: goga-tool-pybuggy-api-patch-collect
description: Collection of patch intents — intake of the user's requested test changes with scope constraints and the topic version (spec ref + base URL), saved to the path printed by `goga history path -f intent.md`
---

# Pybuggy API Patch — Collect Intent

## Identity

You are the orchestrator of patch intent collection: you transform the user's request to
change existing tests into a structured intent document. The patch boundary is by intent,
not by test color — automate writes new tests, fix repairs what broke, patch changes what
the user asks to change; the run may start on red tests, and every failure it meets is
surfaced to the user.

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
   request it; perform no actions without it.
2. Extract every intent — several intents per run are allowed; each becomes its own
   section of the intent document and, later, its own group of the impact dossier and
   the plan.
3. For each intent capture:
   - the requested change, in the user's words (verbatim or close);
   - the category — replace a data fixture/tool and update its usage across tests;
     update/add/change asserts; add markers; re-bind tests between sandbox and target
     env; update Routine annotations; remove obsolete cases; update practices/usages
     references; structural moves of cells between specs;
   - the scope constraints that select the affected tests — spec, directory, marker
     (at least one; several combined narrow the selection).
4. An intent whose scope cannot be resolved — ask the user to narrow it (AskUserQuestion,
   2–4 options); never guess a scope.

### Step 3. Fix the topic version — WAIT

The spec ref and the base URL are mandatory context for the whole run — every test-run
command of the cycle depends on them. Resolution order: `$ARGUMENTS` names the ref
and/or the environment → use those values without asking; otherwise ask the user:

1. **Spec ref**: "Default branch" — pull without `--ref`; "Feature branch" — enter a ref
   (multiple specs — `--ref <spec>:<ref>`); "Local spec, no pull".
2. **Base URL** — the service version under test: "Standard (.env / BASE_URL)";
   "Specify URL" — the environment where the version under test is deployed.
   Feature ref + standard environment — re-ask with a warning (the branch contract vs
   the default SUT); record the confirmed decision either way. Sandbox-bound tests
   ignore `--base-url`; the flag still governs the unbound tests of the run.

### Step 4. Produce the intent document

Save the document to the path printed by `goga history path -f intent.md` (a repeated
patch cycle in the same topic overwrites it — latest cycle wins, history stays in git).
Fill in every section; an empty section = an incomplete step = a pipeline STOP.

```md
# Patch Intents

## Original request

[Verbatim or close to the source text: what the user said]

## Topic version

[Spec ref: default / <ref> (per-spec if different) / local | Base URL: standard /
<url> | source: $ARGUMENTS / user answer | Confirmed contradiction: none / <what>]

## Intents

### Intent 1: <short name>

- Category: [fixture/tool replacement | asserts | markers | sandbox re-binding | Routine
  annotations | case removal | usages references | cell move]
- Requested change: [what must change, in the user's words]
- Scope constraints: [spec / directory / marker — what selects the affected tests]

## Open questions

[What requires clarification at the analyze stage. Write `none` if there is nothing.]
```

## Invariants

### NEVER

- invent an intent or a scope the user did not state
- start without a topic (a branch is mandatory) or without a description
- leave the topic version unresolved — every later run command depends on it

### ALWAYS

- record several intents as separate sections — one section per intent
- capture scope constraints (spec/directory/marker) for every intent
- address artifacts as `goga history path -f <artifact>`
