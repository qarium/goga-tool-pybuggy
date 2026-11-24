# Investigation Report

## Task Summary

The user requested running `goga usages sync -f` (the goga git dependency carries many updates)
and then determining whether pybuggy needs any change because of the goga update. The sync was
executed (exit 0): 25 tracked usage files under `.goga/usages/github/goga/` changed content,
18 new files/directories appeared, nothing was removed, and `cooks/` plus the root
`conventions.md` were preserved (verified against goga 2.1.2 `clean_usages_dir` semantics).
All twelve CODEMANIFEST references into the synced subtree still resolve. The investigation
then traced every semantic delta of the re-synced practices into the pybuggy implementation.

## Candidate Cells

| Cell | Reason | Priority |
|------|--------|----------|
| `goga_tool_pybuggy/autonomous` | 3 of its 3 bound goga usages changed (pipeline hooks, workflow document, compile flow) | 1 |
| `goga_tool_pybuggy/config` | bound `goga-tool-config` changed (!ENV section added) | 1 |
| `goga_tool_pybuggy` (root) | bound `goga-hooks` unchanged; participates through `reg_hooks` subscriptions | 2 |
| `goga_tool_pybuggy/statuses`, `commands/init` | all bound usages unchanged by the sync | 3 |

## Tracing Summary

See `02-trace.md`. Three flows carry the goga update into pybuggy: the autonomy contribution
(`amend_workflow` → `resolve_autonomy` → `build_autonomous_workflow` → `contribute`), the
config facade reads (`load_tool_config`), and the root hook registration (7 subscriptions).
Verified against the local goga 2.1.2 platform source: `WorkflowAmendment` carries the new
`profile` member, `render_contribution` exists, the 13 stage-transition + 2 run-level bridge
actions exist, and `load_tool_config` resolves `!ENV` inside the platform loader.

## Data Flow Analysis

The pybuggy contribution strings (`"Build tests"`, the `python3 -P -m goga.build …` script,
`rm -rf .ralphex`, `"8h"`, `approve="auto"`) contain no `{{ }}` template syntax, so the
platform's intended behavior change (contributed strings are now rendered as templates)
leaves pybuggy's contribution composing "exactly as before". The `!ENV` resolution happens
inside the platform facade before pybuggy's pydantic validation — pybuggy applies its own
semantics to resolved strings (strict validation, clean errors naming pybuggy), which is the
documented division of responsibility.

## Manifest Algorithm Analysis

Every manifest algorithm step of the affected cells maps to the code as written (see
`02-trace.md` table). No manifest-defined algorithm depends on a practice section that the
sync changed semantically: the approve directive, the extend-entry keys
(`title`/`script`/`after_script`/`timeout`), string script payloads, and the seven hook
subscription addresses all remain valid 2.1 vocabulary.

## Affected Usages

| Usage | Cell | Classification | Reason |
|---|---|---|---|
| `goga-tool-config` (config/tool-configuration.md) | config | DIRECTLY AFFECTED | `!ENV` section added — platform-side; pybuggy reads resolved values through the facade |
| `goga-pipeline-hooks` (pipeline/registering-hooks.md) | autonomous | DIRECTLY AFFECTED | 18 actions (was 3), `profile` member, `{{ }}` template rendering — pybuggy consumes none of the new surface and emits no template syntax |
| `goga-workflow-document` (pipeline/workflow/parse-workflow.md) | autonomous | DIRECTLY AFFECTED | vocabulary growth (profile/build/assistants/delegation/repeat/gates/agent/env; per-stage env/assistants/gates; `env`+`assistants` forbidden in extend) — pybuggy uses only the still-valid subset |
| `goga-compile-flow` (pipeline/compiler/compile-flow.md) | autonomous | DIRECTLY AFFECTED | repeat compilation, list-form script payloads, gates→verify, collaboration emission — all additive; string script payloads pass verbatim |
| `goga-hooks`, `goga-onboarding-hooks` (root), `goga-statuses` (statuses), `goga-scaffold`, `goga-onboarding`, `goga-onboarding-questions`, `goga-onboarding-generator` (init) | root, statuses, init | NOT AFFECTED | files unchanged by the sync |
| ~21 unbound files under the synced subtree | — | NOT AFFECTED | new or changed platform practices not referenced by any pybuggy manifest — optional adoption, out of scope |

## Rejected Hypotheses

| Hypothesis | Rejection evidence |
|---|---|
| "The extend-entry keys pybuggy emits were forbidden by the new workflow grammar" | parse-workflow diff forbids only `env`, `notes`, `memory`, `assistants` in extend-entries; pybuggy emits `title`, `script`, `after_script`, `timeout` — all legal |
| "The `{{ }}` rendering breaks the build-stage script (it contains `$(…)}` shell syntax)" | The rendering surface is `{{ … }}` Jinja-style expressions only; the script string contains none (verified `autonomous/workflow.py:46`) |
| "The `!ENV` empty-string resolution breaks `PipelineAutonomy` bool validation" | Only when a consumer authors `autonomous: !ENV UNSET` — that fails as pybuggy's own documented clean error ("a record not validatable into PipelineAutonomy fails with a clean error naming pybuggy"); a tool applying its own semantics to resolved strings is the documented contract, not a defect |
| "The 18-action pipeline domain obliges new pybuggy subscriptions" | Practices create no contractual obligations (cookbook boundary rule); the root manifest constrains subscriptions to the seven named hooks; new platform actions are optional adoption |
| "The local goga 2.1.2 lags the synced docs, so tests validate the wrong platform" | Local platform implements `profile` (`WorkflowAmendment`), `render_contribution`, the mid-run bridge actions, and the `!ENV` loader — it matches the synced docs |
| "pybuggy code needs behavioral changes for 2.1" | Full suite (2152 tests) passes identically with goga 2.0.5, 2.1.0, 2.1.2, and 2.1.4 — no version-specific behavior difference is exercised |

## Confirmed Root Cause

The goga update itself requires **no pybuggy code change** — every semantic delta in the
re-synced practices is either platform-side (facade `!ENV` resolution), additive (new actions,
new vocabulary, `profile` member), or neutralized by pybuggy's template-free contribution.
The single required change is an environment-consistency defect exposed by the update: the
`test` extra in `pyproject.toml` pins `goga>=2.0.1,<2.1` (resolves to 2.0.5) although the
project moved to the 2.1 platform on 2026-11-09 (commit 2702d4d1 bumped the Dockerfile base to
`qarium/goga-python-3.13:2.1` and the usages ref to `2.1.x`) without touching the pin. The pin
entry's own comment defines its purpose — "runtime dep of the target env (installed next to
goga), needed here only to import the package in tests" — so it must track the target-env
line. Evidence chain: pyproject comment → Dockerfile base `:2.1` → usages ref `2.1.x` →
local platform 2.1.2 → PyPI line head 2.1.4 → suite green across 2.1.0/2.1.2/2.1.4.

## Confidence Level

HIGH — deterministic evidence chain: the sync diff is fully enumerated (git), every bound
usage path resolves, the four changed bound usages were diffed line-by-line, the local
platform source was checked for each new behavior, and the full test suite passes on both
sides of the pin boundary (2.0.5 and the whole 2.1 line).

## Breaking Change Assessment

1. Will existing function call with same arguments produce different behavior? **NO** — no
   pybuggy code or contract changes; the only proposed change is the test-environment pin in
   `pyproject.toml`.
2. Will existing file paths change? **NO**.
3. Will output format change? **NO**.
4. Will return value semantics change? **NO**.
5. Will manifest-defined guarantees be altered? **NO** — no CODEMANIFEST edits required.
6. Will existing tests break? **NO** — the suite passes with goga 2.0.5, 2.1.0, 2.1.2, 2.1.4
   (2152 passed, 21 environment-gated skips in each run).

No breaking change detected — the pipeline may proceed without escalation.
