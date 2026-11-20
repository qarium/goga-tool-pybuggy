# Investigation Report

## Task Summary

The `goga init` bootstrap writes a broken pybuggy-install step into the consumer project Dockerfile: a single
`RUN goga install pybuggy -v <major.minor>.x` line. The required form is a root-user project-copy block —
`USER root` / `COPY . /tmp/project` / `RUN cd /tmp/project && goga install && rm -rf /tmp/project` /
`USER goga` — so the install runs with the permissions it needs and follows the project's own `tools:` pin
(the bulk `goga install` path) instead of a second, init-time version derivation.

## Candidate Cells

| Cell | Reason | Priority |
|---|---|---|
| `goga_tool_pybuggy/commands/init` | Sole owner of the Dockerfile writers (`install_pybuggy`, `install_playwright`), their contract, orchestration (step 6/6c), usages, and pinning tests | 1 |

## Tracing Summary

See 02-trace.md. Call path: `init_cmd` → `run_init` → `run_bootstrap` step 6 → `install_pybuggy` (the defect
site), step 6c → `install_playwright` (derivative interaction). Both writers are file-level leaves inside the
single cell; the only external semantics are `importlib.metadata.version` (version derivation) and the
consumer's Dockerfile itself. The `goga install` no-argument BULK semantics (reads `.goga/config.yml`
`tools:` from the working directory) were resolved against the installed goga CLI.

## Data Flow Analysis

Two independent derivations of the same x-range pin exist today: the session's `_recorded_version()`
(session.py:338) → `.goga/config.yml` `tools: {pybuggy: "2.0.x"}`, and the bootstrap's `install_pybuggy` →
Dockerfile `RUN … -v 2.0.x`. Inside the built image the bulk `goga install` reads the project's `tools:`
record — making the Dockerfile `-v` pin redundant the moment the project is copied in. The playwright line
(`--with-deps` = OS packages) is appended at end-of-file and therefore interacts with the new trailing
`USER goga` boundary.

## Manifest Algorithm Analysis

The CODEMANIFEST (`install_pybuggy`, bootstrap.py location, lines 720-752) prescribes exactly the defective
behavior: derive the pin from the installed distribution (`ValueError` on a metadata-less run), write the
single `RUN` line (repin-in-place on prefix match, append when absent, idempotent). `install_playwright`
(754-783) prescribes append-at-end. `run_bootstrap` step 6/6c (155-229) orchestrates both. The manifest
matches the implementation and the tests — this is a requirement-level defect in the contract itself, not
manifest-code drift: the contract must be corrected together with the code.

## Affected Usages

| Usage | Cell | Classification | Reason |
|---|---|---|---|
| `.goga/usages/conventions.md` | project | INDIRECTLY AFFECTED | mandatory style/testing rules for the rewritten writer and tests |
| `.usages/init.md` (lines 107-108, 112-115) | commands/init | DIRECTLY AFFECTED | documents the generated install line and playwright line verbatim |
| `.usages/config-build.md` (lines 97-104) | commands/init | DIRECTLY AFFECTED | "the same x-range the Dockerfile install line pins" cross-reference breaks |
| `docs/cli/init.md` (artifact table + "install line is derived…" paragraph) | docs mirror | DIRECTLY AFFECTED | pins the single-line form and the derivation story |
| `docs/getting-started.md` (artifact table row) | docs mirror | DIRECTLY AFFECTED | pins `RUN goga install pybuggy -v <N.M>.x` |

## Rejected Hypotheses

- **"The writer appends to the wrong file / wrong path"** — rejected: `_resolve_dockerfile_path` resolves the
  config `dockerfile` field with the documented fallback; tests pin the resolution; the user's complaint is the
  line's *content*, not its location.
- **"The x-range pin is wrong (should be concrete/other form)"** — rejected: the user's target form drops the
  `-v` argument entirely; the pin form itself is not the issue — the install *pattern* (user + project copy) is.
- **"The engine's Dockerfile generator owns the line"** — rejected: the engine writes only the
  FROM/image pair from the session amendments; the install line is solely the pybuggy bootstrap's writer
  (init.md:85-86, CODEMANIFEST run_bootstrap step 6).
- **"Manifest-code drift caused the wrong line"** — rejected: manifest, code, tests, and docs are mutually
  consistent today; the defect is in the shared design they all encode.

## Confirmed Root Cause

**Design defect in the `install_pybuggy` contract**: the bootstrap-encoded install step assumes the image's
default user can pip-install (`RUN goga install pybuggy -v <pin>` appended as-is), while the goga-python base
image runs as the unprivileged `goga` user, and it re-derives the version pin at init time instead of letting
the image build read the project's own `.goga/config.yml` `tools:` record. Evidence chain:
1. User report (q1): the single-line form "уже не правильно"; the required block is
   `USER root` / `COPY . /tmp/project` / `RUN cd /tmp/project && goga install && rm -rf /tmp/project` / `USER goga`.
2. `bootstrap.py:359` — `line = f"RUN goga install pybuggy -v {pin}"`; no `USER` handling anywhere in the writer.
3. `goga install --help` (installed CLI) — no-name = BULK path over `.goga/config.yml` `tools:`, proving the
   copied-project block needs no `-v` and uses the session-recorded pin (`session.py:338`).
4. Derivative: `install_playwright` appends at end-of-file (`bootstrap.py:458`), which the block's trailing
   `USER goga` would strand in the non-root section.

## Confidence Level

**HIGH** — deterministic causality with a complete evidence chain: the defect site, its exact emitted text,
the external installer semantics, the derivative playwright interaction, and the full mirror inventory
(manifest, 2 usage files, 2 docs pages, 3 test modules) are all confirmed on the live stack.

## Breaking Change Assessment

| # | Question | Verdict | Evidence |
|---|---|---|---|
| 1 | Same-arguments different behavior? | **YES** | `install_pybuggy(dockerfile_path)` on the same input file writes a 4-line root block instead of the single `RUN` line |
| 2 | Existing file paths change? | NO | the written artifact path (consumer Dockerfile) is unchanged |
| 3 | Output format change? | **YES** | generated artifact content changes: `RUN goga install pybuggy -v <N.M>.x` → the USER root/COPY/RUN/USER goga block |
| 4 | Return value semantics change? | **YES** | `line: str | None` (single line) → the written block text (multi-line); the contract label changes |
| 5 | Manifest-defined guarantees altered? | **YES** | CODEMANIFEST Requirements pin the single-line x-range form and the metadata-derived pin; the ValueError-on-metadata-less guarantee disappears with the version derivation |
| 6 | Existing tests break? | **YES** | `TestInstallPybuggy` (5 tests), `test_init.py` `_INSTALL_LINE` pins (5 asserts + `_PLAYWRIGHT_LINE` ordering asserts), `test_init_integration.py` (2 asserts) |

**BREAKING CHANGE DETECTED** — pipeline STOPPED before planning per the goga-change breaking-change policy and
the project rule (a defect fix that alters generated artifact content for identical inputs is formally breaking
regardless of corrective intent). Escalation: `breaking-escalation.md`; implementation proceeds only after the
user's explicit override.
