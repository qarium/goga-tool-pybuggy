# Investigation Report — Patch cycle 2 (init autonomy for api.patch)

## Task Summary

Extend the `pybuggy init` onboarding so the autonomy opt-in covers `api.patch` the same
way it covers `api.automate`: the confirm is asked during the amendment moment, and an
enabling answer writes the per-pipeline axis entries into the fresh
`.goga/tools/pybuggy/config.yml` — `api.automate` and `api.patch` with `autonomous: true`.
Requested by the user (Patch flow, `autonomous_execution.q1`, 2026-10-15); recorded in
`todo.md`.

## Candidate Cells

| Cell | Reason | Priority |
|------|--------|----------|
| `goga_tool_pybuggy/commands/init` | Owns `survey_autonomy`, `build_config_data`, `amend_pybuggy_config` — the whole behavioral change | 1 |
| `goga_tool_pybuggy/config` | Axis contract (`resolve_autonomy`, entry shape); acceptance reads it back | 2 |
| `goga_tool_pybuggy/autonomous` | `PATCH_CONTRIBUTION.axis == "api.patch"` — the consumer the new entry enables | 3 |

## Tracing Summary

The onboarding session is engine-owned; the tool participates through two hook moments.
The declaration moment (`declare_pybuggy_session`) emits the declarative block without any
autonomy question (a manifest constraint). The amendment moment (`amend_pybuggy_config`)
surveys extras, then `survey_autonomy()` — one click.confirm naming only `api.automate`,
default No — and buffers the tool config through `build_config_data`, whose enabling branch
writes `{"api.automate": {"autonomous": True}}` (session.py:225-226). The engine serializes
the payload verbatim into a fresh config (an existing `.goga/config.yml` ends the session
before any tool moment — the file set is never rewritten). At pipeline-run time,
`amend_workflow` resolves the record's axis via `resolve_autonomy`, which validates every
entry of the `pipelines` mapping (one boolean member `autonomous`) and accepts any
pipeline-name key — `api.patch` is an existing, resolver-valid axis consumed by
`PATCH_CONTRIBUTION`. Full graph in `02-trace.md`.

## Data Flow Analysis

- Producer: `survey_autonomy() → bool` → `build_config_data(answers, extra_specs, bool) → payload dict` → `context.write_config` → engine `yaml.dump` → `.goga/tools/pybuggy/config.yml`.
- Consumer: `resolve_autonomy("api.patch")` (raw parse via platform facade → whole-axis validation → per-name boolean) → `amend_workflow` gates `build_autonomous_workflow(PATCH_CONTRIBUTION)`.
- The axis keys are string literals on both sides (producer: session.py:226; consumer: contributions.py). The resolver contract (`config/.usages/autonomy.md`) is per-pipeline-name and already covers both keys — no contract change, only the producer's literal set grows.

## Manifest Algorithm Analysis

- `survey_autonomy` (commands/init CODEMANIFEST): Algorithm step 1 fixes the prompt verbatim — "Run the api.automate pipeline unattended (autonomous mode)?" — and the Requirement pins verbatim prompt/default; the annotation must be updated with the prompt change (cell convention: current state, not changelogs).
- `build_config_data` (commands/init CODEMANIFEST): Algorithm step 3 — "add the pipelines axis entry — the api.automate record with autonomous true" — becomes the two-record entry set; Requirements (schema-compatible, absent on disabling answer, plain serializable) all continue to hold.
- `amend_pybuggy_config`: step 4 references `survey_autonomy` generically — no text change needed (it never names automate).
- `pybuggy_questions` constraint "Do not declare an autonomy question" — unaffected.

## Affected Usages

| Usage | Cell | Classification | Reason |
|---|---|---|---|
| `.usages/autonomy.md` | goga_tool_pybuggy/config | INDIRECTLY AFFECTED | The contract (per-name axis, single boolean member) is unchanged and already covers `api.patch`; its example shows only the automate entry — cosmetic candidate only, no semantic drift |
| `.goga/usages/conventions.md` | base | DIRECTLY AFFECTED (as rules) | Governs the code/test edits (relative imports, docstrings, test structure, validation commands) |
| `.usages/configuration.md` | goga_tool_pybuggy/config | NOT AFFECTED | `load_config` path untouched |

## Rejected Hypotheses

1. **"Derive the surveyed axes from `CONTRIBUTIONS` to avoid literal duplication"** — rejected: adds a new init→autonomous cell dependency (`Imports` + facade reach-through) for two stable string literals; the package style keeps the axis keys as literals on each side (mirrors the existing code and the just-shipped design); the drift risk is guarded by the new acceptance test reading the payload through the real resolver.
2. **"The resolver or config schema needs work"** — rejected: `resolve_autonomy` validates any per-name entry; `tests/config/test_storage.py` proves unknown names are ignored and the entry shape enforced; `api.patch` is already valid.
3. **"The session must also handle existing configs"** — rejected: the engine ends the session on an existing `.goga/config.yml` before any tool moment; onboarding writes only fresh trees, so no migration or merge path exists or is needed.
4. **"Docs alone suffice / behavior already exists"** — rejected: the prompt and payload literals pin automate-only (session.py:187, 226); docs/configuration.md already promises both axes — the code is the gap.

## Confirmed Root Cause

The onboarding autonomy path predates the `api.patch` pipeline: `survey_autonomy`'s prompt
and `build_config_data`'s enabling branch hardcode the single `api.automate` axis
(session.py:187, 225-226), and the init CODEMANIFEST pins that behavior verbatim. A newly
initialized project therefore cannot opt into patch autonomy through init, although the
consumer chain (`resolve_autonomy` ← `PATCH_CONTRIBUTION.axis`) and the configuration docs
already support it. Evidence chain: trace (02-trace.md) → literals at session.py:187/226 →
CODEMANIFEST texts → docs/getting-started.md:40 + docs/cli/init.md:170-183 → the three
test suites pinning the old strings (test_session.py:373, test_session.py:493-497,
test_init_integration.py:30/44/190/203).

## Confidence Level

**HIGH** — deterministic causality with a full evidence chain: producer literals, consumer
records, resolver contract, manifest texts, docs, and pinning tests all read; the change
surface is closed (one prompt literal, one payload literal, their manifest texts, the
pinning tests, two docs pages).

## Breaking Change Assessment

| # | Question | Answer | Evidence |
|---|----------|--------|----------|
| 1 | Existing call with same arguments produces different behavior? | **YES** | `build_config_data(…, True)` gains the `api.patch` entry; `survey_autonomy()` asks a reworded confirm (same signature, same bool semantics) |
| 2 | Existing file paths change? | NO | Same `config.yml` target through `context.write_config` |
| 3 | Output format change? | **YES** (content, not schema) | The enabling payload gains one mapping entry under the existing `pipelines` key — schema-identical, resolver-valid |
| 4 | Return value semantics change? | NO | `survey_autonomy` → bool "autonomy enabled"; `build_config_data` → payload mapping |
| 5 | Manifest-defined guarantees altered? | NO | Every existing guarantee holds (schema compatibility, absent-on-disable, plain serializability, never rewriting an existing config); the manifest *texts* evolve with the requested behavior |
| 6 | Existing tests break? | **YES** | Three suites pin the old prompt/payload (test_session.py, test_init_integration.py, test_autonomy_integration.py expectations) |

**BREAKING CHANGE DETECTED** by the letter of the policy (1, 3, 6 = YES). The pipeline
does not proceed on its own authority: the change is the user's explicit request (their
`q1` answer defines the new payload verbatim), affects only **freshly created** config
trees (existing projects are never rewritten — the session refuses an existing
`.goga/config.yml` before any tool moment), and is additive on the consumer side (the
resolver treats `api.patch` as a first-class axis). The STOP is overridden by the user's
mandate and is surfaced again explicitly in the plan-approval question before any code
is touched.
