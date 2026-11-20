# Test Report

## Changes Requiring Coverage

| Change | Type |
|---|---|
| Manifest body declarations removed/reworded in three CODEMANIFEST files | manifest — carried by the deterministic gates (no executable behavior changed) |

No code function, algorithm step, or data flow changed (`git diff` touches exactly three CODEMANIFEST
files), so no regression/behavior/edge test surface exists for this change.

## Tests Added

None — per the approved plan: the change alters no executable behavior, and no existing test reads
the manifests. Acceptance is asserted by the deterministic specification gates below (repo practice:
no pytest module shells out to or imports the goga tooling; the goga gates run as CLI commands in
the change pipeline).

## Test Results

| Gate | Status | Details |
|---|---|---|
| `goga drift` | **PASS** | `[]` — the report is empty (was: 4 entries / 7 types) |
| `goga lint` | **PASS** | 26 cells, 0 errors |
| `goga schema` parity | **PASS** | every cell's declared types == its `__init__.py` facade (programmatic AST comparison over all cells: no mismatch) |
| `ruff check goga_tool_pybuggy/` | **PASS (no new findings)** | 2 pre-existing PLR0917 in `api/api.py`, `api/endpoint.py` — byte-identical result on the pre-change tree with the same ruff binary |
| `ruff format --check` | **PASS (no new findings)** | 1 pre-existing hit (`web/.usages/pybuggy-web.md` — the venv's newer ruff formats markdown code blocks); identical pre-change |
| `pytest tests/ -x` (full suite) | **BLOCKED — pre-existing environment gap** | The package cannot be imported with the index-served prettyplay 0.0.3 (`web_plugin.py:285` KeyError `request_max_tokens`; the project pins `prettyplay>=0.0.4,<0.1.0`). Proven pre-existing: the identical failure occurs on the unmodified tree (`git stash` run). The prior patch report (browser-endpoint, 2026-11-02) documents this: 0.0.4 is unreleased and test envs must install the 0.0.x checkout, which is absent on this machine |

## Coverage Gaps

| Changed Behavior | Covered? | Notes |
|---|---|---|
| Declared view == code-derived view (the task's subject) | Yes | `goga drift` empty + schema/facade parity check |
| DSL validity of the edited manifests (links, imports, mutations, embeddings) | Yes | `goga lint` 0 errors |
| Runtime behavior of the seven internal types | Yes (unchanged) | No code modified; behavior coverage belongs to the existing suite (which runs green in a complete environment — 2003 passed at the last full validation) |

## Missing Coverage Analysis

Nothing new is untested. Two notes for the owner (not acted on — outside the approved plan):

- The empty drift report could be pinned as a repository test (goga is already a `test` extra), making
  manifest↔facade parity a CI gate rather than a manually run command.
- The prettyplay 0.0.4 environment gap keeps the full suite unrunnable here; a published 0.0.4 or a
  vendored 0.0.x checkout in CI would restore the full gate.
