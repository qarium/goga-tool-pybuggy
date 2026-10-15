# The `api.patch` lifecycle

The staged pipeline changes existing tests on your request — from a patch intent to
committed, accepted tests. It is the third line beside
[`api.automate`](api-automate.md), which writes new tests, and [`api.fix`](api-fix.md),
which repairs what broke: the boundary is drawn by intent, not by test color. The run
may start on red tests, and every failure it meets is surfaced to you, never masked.
Each stage is a dedicated goga skill; every stage except `apply-manifests` is a
*communication* stage that involves you (see
[Autonomous runs](#autonomous-runs) for the unattended window).

Need to adjust the pipeline for your project without forking it? See
[Workflows](workflows.md).

## Launch

```bash
goga pipeline pybuggy:api.patch
```

Prerequisites: an initialized pybuggy environment (see
[Getting Started](../getting-started.md)) and the change you want made to existing
tests. Describe the requested change in the pipeline argument — what must change and,
if you already know, which tests it reaches. Several intents per run are allowed: each
becomes its own section of the intent document and, later, its own group of the impact
dossier and the plan.

## Topic version

Before any collection, the pipeline fixes the **topic version** for the whole cycle —
the environment under test. The specification is local: the run reads the spec files
from the tree on disk and never pulls a ref (unlike [`api.automate`](api-automate.md)
and [`api.fix`](api-fix.md), which select a spec branch). It uses the value from the
pipeline argument when it names an environment; otherwise it asks you:

1. **Run environment (base URL)** — which service version is tested:
   - *standard* — the `.env` / `BASE_URL` default;
   - *explicit URL* — the environment where the version under test is deployed.

The confirmed choice is recorded and holds for the entire cycle. Non-standard base URLs
are passed to every run as `pytest --base-url <url>` — the flag governs the tests that
do not use the sandbox; the sandbox-bound tests take the sandbox address (see
[Sandbox](../sandbox/index.md)).

## Stages

| #  | Stage             | Purpose                                                                                        |
|----|-------------------|------------------------------------------------------------------------------------------------|
| 1  | `collect-intent`  | Collect the patch intents (each with its scope constraints), fix the topic version, and pin the pre-patch baseline → `intent.md` |
| 2  | `analyze-impact`  | Settle the dependency usages (`goga usages sync` / `status`), then build the per-intent impact dossier: affected tests, fixtures, manifests, usages deltas (new tools, API updates, Header wiring) → `impact.md` |
| 3  | `review-impact`   | Review the dossier with you; confirm every selection and delta                                  |
| 4  | `apply-manifests` | Apply the confirmed deltas to the CODEMANIFESTs and the tool usage files (`.goga/usages/cooks/`) — the silent stage → `apply.md` |
| 5  | `code-design`     | Design the code changes over the applied deltas; deletions become explicit deletion tasks → `rework.md` |
| 6  | `design-review`   | Review the code design                                                                          |
| 7  | `coding-plan`     | Compile the ralphex execution plan (convention rules as mandatory rules) → `workplan.md`        |
| 8  | `plan-review`     | Review the plan                                                                                |
| 9  | `commit-changes`  | Commit all added and modified files                                                             |
| 10 | `accept-result`   | Accept the patch results — *manual trigger*: consistency check, final full-suite run, failure triage with you → `accept.md` |

The `collect-intent` stage opens the topic: once the patch request is read, its intake runs
one idempotent `goga history ensure` — the topic is the current git branch. Every later
stage addresses artifacts with `goga history path -f <artifact>`.

The `collect-intent` stage also pins the **pre-patch baseline**: the full suite runs once
with the topic version before any change lands (`baseline-log.txt`). The acceptance
triage reads it to separate pre-existing reds from patch-caused failures; a green
baseline is not required — the baseline records reds, it does not gate them.

The `analyze-impact` stage first settles the dependency usages exactly as
[`api.automate`](api-automate.md) does: `goga usages sync` materializes missing
dependency usages, `goga usages status` reports drift, and a drift relevant to the topic
is decided with you — refresh via `goga usages -g <group> -d <dep> sync --force` or
continue with the local state — with the decision recorded in the dossier.

Tools follow the automate line's mechanic: for every tool an intent introduces or
re-binds — the sandbox included — the existing usages are looked up first; an existing
usage is wired into the cell as is, and a tool without one becomes a new
`.goga/usages/cooks/<key>.md` (the key, purpose, and API source — yours or the
dependency file — agreed at `review-impact`, the content never invented); a tool whose
API the patch changes has its usage file updated. `apply-manifests` writes the files
and wires the keys into the cell Headers — a key is never wired before its file
exists, and the base Header block stays untouched.

> **Building the changed tests:** the design and plan stages produce documents only.
> The defining rule of the line is that every change lands in the CODEMANIFEST and in
> the test code together — `apply-manifests` writes the manifest half, and after
> `plan-review` approves `workplan.md` the code half is built with
> `goga build <path-to-workplan>` — [goga](https://github.com/qarium/goga) executes the
> ralphex plan, writing each changed `test_*.py` from the plan's Tasks and running the
> validation commands (`pytest`). The tree is consciously out of sync between the two
> halves — the apply report names every file awaiting its code half.

## Artifacts

The cycle accumulates its chain in the topic's history directory — the path printed by
`goga history path -f <artifact>` (`.goga/history/<year>/<topic>/`; the topic is the
current git branch, ensured by the collect stage's intake via `goga history ensure`):

```
intent.md        # the patch request: intents, scope constraints, topic version, pre-patch baseline
baseline-log.txt # pre-patch baseline full-suite run output (collect)
impact.md        # per-intent impact dossier (tests, fixtures, manifests, usages)
apply.md         # the applied deltas (changed CODEMANIFESTs and usage files)
rework.md        # code-change design over the applied deltas
workplan.md      # ralphex execution plan
accept.md        # acceptance report: consistency, run results, triage, verdict
accept-log.txt   # final full-suite run output
bugs.md          # service bugs triaged at acceptance (shared with the other lines)
```

A repeated patch cycle in the same topic overwrites the chain — the latest cycle wins,
the history stays in git.

## Topic status

Every artifact of the chain marks a status on the **patch line** of the goga topic
status scale — an independent chain anchored at the built-in `empty`, so it never
reorders the automate or fix lines:

| Artifact               | Status                    |
|------------------------|---------------------------|
| `intent.md`            | `pybuggy.patch.intended`  |
| `impact.md`            | `pybuggy.patch.analyzed`  |
| `apply.md`             | `pybuggy.patch.applied`   |
| `rework.md`            | `pybuggy.patch.designed`  |
| `workplan.md`          | `pybuggy.patch.planned`   |
| `completed/workplan.md`| `pybuggy.patch.done`      |

A topic mid-patch therefore shows one maximal status per line — e.g.
`[pybuggy.patch.planned] [pybuggy.automate.done]`. Read the scale with
`goga history status`; see
[api.automate — Topic status](api-automate.md#topic-status) for the scale itself.

## Autonomous runs

The pipeline can run unattended from the impact review onward. Autonomy is opt-in per
pipeline through the `pipelines` section of the tool config — set it by hand or through
the `api.patch` autonomy confirm of [`pybuggy init`](../cli/init.md):

```yaml
# .goga/tools/pybuggy/config.yml
pipelines:
  api.patch:
    autonomous: true
```

With the entry enabled, pybuggy contributes a fixed workflow document (the
[Workflows](workflows.md) mechanism) to every `api.patch` run:

- The seven-stage auto-approval window `review-impact` → `commit-changes` (stages 3–9
  of the table above): every stage of the window is approved automatically — the
  communication stages no longer pause for your review.
- A `build` stage appended after `commit-changes`: the same `goga build` step as the
  *Building the changed tests* note above, run on the topic's `workplan.md` with an
  eight-hour timeout and the `.ralphex` scratch tree removed afterwards — the changed
  tests are built without a manual build step.

Everything outside the window stays with you: the intent-shaping stages
(`collect-intent`, `analyze-impact`) run interactively, and `accept-result` is never
part of the contribution — it keeps its manual trigger, so accepting the results (the
full-suite run and the failure triage) remains an interactive step.

The contribution is a silent no-op for every pipeline outside the automate and patch
lines — the window shape is carried per pipeline record — and for every disabled
state: an absent file, an absent
`pipelines` section, an absent `api.patch` entry, and `autonomous: false` all mean a
normal interactive run. Autonomy never disables silently on a malformed config: a
structural violation of the section (a file root or `pipelines` value that is not a
mapping, an entry shaped other than exactly `autonomous: <boolean>`) stops the command
with a clean error naming pybuggy, and the whole contribution is discarded.

An authored project workflow wins per slot over the contribution — a
`.goga/workflows/pybuggy:api.patch.yml` can re-enable interaction for any window stage
or displace the `build` entry.

## How it relates to the rest

- New testing subjects start at [`api.automate`](api-automate.md); broken accepted
  suites are repaired by [`api.fix`](api-fix.md). Patch is the line in between: it
  carries the changes you ask for — a re-bound fixture, new asserts, added markers,
  removed cases — through manifests and code to accepted tests.
- The pipeline stages are goga skills (`goga-tool-pybuggy-api-patch-*`) driven by the
  goga agent in the consumer project.
