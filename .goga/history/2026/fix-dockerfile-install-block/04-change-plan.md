# Change Plan

## Task Classification

**bugfix** (breaking — user override recorded in breaking-escalation.md, q2 option A, 2026-10-30)

## Affected Cells

| Cell | Files to Modify | What Changes |
|---|---|---|
| `goga_tool_pybuggy/commands/init` | `bootstrap.py`, `CODEMANIFEST`, `.usages/init.md`, `.usages/config-build.md`, `session.py` (docstring only) | `install_pybuggy` writes the root-user copy-and-install block (no `-v`); `install_playwright` anchors inside the root section; contract/usages mirrors move in lockstep |
| — (docs mirrors, same change) | `docs/cli/init.md`, `docs/getting-started.md` | artifact-table rows and the install-derivation paragraph describe the block |
| — (tests, same change) | `tests/commands/init/test_bootstrap.py`, `test_init.py`, `test_init_integration.py` | pinning tests rewritten to the block contract |

## Root Cause Analysis

`install_pybuggy` (bootstrap.py:325) encodes a defective install step: a single
`RUN goga install pybuggy -v <N.M>.x` appended as the image's default unprivileged (`goga`) user, with a
redundant init-time version derivation. The goga-python base image runs as `goga`, so the pip-based install
cannot succeed there; and the bulk `goga install` (no name) reads the `tools:` record from the copied
project's `.goga/config.yml` — the session amendment already pins `pybuggy: "<N.M>.x"` there, so the Dockerfile
needs no `-v`. Fix: write `USER root` / `COPY . /tmp/project` / `RUN cd /tmp/project && goga install &&
rm -rf /tmp/project` / `USER goga` (03-investigation.md, HIGH confidence).

## Trace Summary

Defect site: `run_bootstrap` step 6 → `install_pybuggy` (bootstrap.py:325-379). Derivative interaction:
step 6c → `install_playwright` (bootstrap.py:408-461) appends at end-of-file — with the block's trailing
`USER goga` it must instead insert inside the root section. Version flow: `_pybuggy_version_axis`
(session.py:328) → `.goga/config.yml` `tools:` — the single version source, unchanged (02-trace.md).

## Change Strategy

1. **`bootstrap.py` — `install_pybuggy`** (TDD: tests first):
   - New module constants: `_INSTALL_RUN = "RUN cd /tmp/project && goga install && rm -rf /tmp/project"`,
     `_INSTALL_BLOCK = "USER root\nCOPY . /tmp/project\n{_INSTALL_RUN}\nUSER goga"`. `_INSTALL_LINE`
     (old-shape prefix regex) stays — it now recognizes previous releases' single lines for in-place
     replacement.
   - Algorithm: file absent → `None`; `_INSTALL_RUN` already present → `None` (idempotent — tolerant of the
     playwright line sitting inside the block); `_INSTALL_LINE` match → replace that span with the block
     (INFO `pybuggy install block replaced in Dockerfile`); else append with the newline guard (INFO
     `pybuggy install block added to Dockerfile`). Return `_INSTALL_BLOCK`.
   - The `importlib.metadata` derivation and its `ValueError` branch are **removed** (no version in the
     block); the `importlib.metadata` import stays only if still used (it is not — drop it).
2. **`bootstrap.py` — `install_playwright`**:
   - Keep the lenient browser read, the `_PLAYWRIGHT_LINE` prefix match, the line text.
   - Insertion anchors inside the root section: find the `_INSTALL_RUN` line, then the next `USER goga`
     line after it; the playwright line is inserted immediately before that anchor. An existing playwright
     line elsewhere (stranded after `USER goga`, the pre-fix layout) is removed and re-inserted at the
     anchor (repair in place); an existing anchored line with a different browser is repinned. No anchor
     found (no block — defensive) → append at end (previous behavior). Idempotent at the current browser
     and position.
3. **`session.py`**: `_pybuggy_version_axis` docstring — replace the "Mirrors the Dockerfile install pin of
   `install_pybuggy`" sentence with the new relationship (the recorded x-range is the pin the image-build
   bulk install reads; the Dockerfile block carries no version). Code unchanged.
4. **CODEMANIFEST** (`commands/init`): `install_pybuggy` signature label `-> block:str | None`; annotations
   rewritten (purpose, algorithm, requirements, constraints — block form, no version derivation, in-place
   replacement of any previous single-line shape); `install_playwright` algorithm gains the anchor/relocate
   steps; `run_bootstrap` step 6/6c wording + global annotation "the Dockerfile install line" → "install
   block". Keys, locations, footers untouched.
5. **Usages**: `.usages/init.md` artifact-table rows (install block, playwright placement) + the
   mandatory-Dockerfile paragraph wording; `.usages/config-build.md` tools-amendment sentence drops the
   "same x-range the Dockerfile install line pins" cross-reference.
6. **Docs**: `docs/cli/init.md` (table row, the "install line is derived…" paragraph, the
   mandatory-Dockerfile sentence), `docs/getting-started.md` (table row).
7. **Tests**: rewrite the pins (details in Test Strategy); run the full suite + ruff; `goga lint` stays
   25 cells 0 errors.
8. **Closing gate**: repo-wide `grep -rn "goga install pybuggy -v" goga_tool_pybuggy/ tests/ docs/
   README.md` → empty (history/changelogs excluded); `grep -rn "install line"` over the touched mirrors →
   no stale single-line phrasing.

## Specification Impact

- `install_pybuggy` body section: signature label (`line` → `block`), full annotation rewrite
  (algorithm 4 steps, requirements, constraints — `Do not hardcode the version` becomes `Do not derive or
  pin a version — the project config tools record is the single version source`).
- `install_playwright` body section: algorithm extended with the root-section anchor, the stranded-line
  relocation, and the append fallback; requirements note the placement.
- `run_bootstrap` body section: step 6 "augment it via `install_pybuggy` (the root-user install block)";
  step 6c "(…the line lands inside the root section, before the block's `USER goga`)"; the web requirement
  bullet gains the placement; global annotation wording ("the Dockerfile install block").
- No Imports/Usages/footer changes; no other type signatures change.

## Usage Impact

- `.usages/init.md`: row "the pybuggy install RUN line … `RUN goga install pybuggy -v <major.minor>.x`" →
  the four-line block with its gates (appended when absent / replaces a previous release's single line in
  place / idempotent at the current block; the bulk install follows the project `tools:` pin — no `-v`);
  playwright row gains "inserted inside the root section before the block's `USER goga`; a stranded line
  from a previous layout is relocated on the next run"; "carry its install line" → "carry its install
  block" (two places).
- `.usages/config-build.md`: "the same x-range the Dockerfile install line pins, a floating patch form" →
  the x-range the image-build bulk install reads from this record (the Dockerfile block carries no
  version).
- `docs/cli/init.md` + `docs/getting-started.md`: same corrections in the artifact tables; the
  derivation paragraph ("The install line is derived from the installed pybuggy version — e.g. an
  installed `2.0.3` yields `RUN goga install pybuggy -v 2.0.x`…") is replaced by the block description.

## Compatibility Verification

**Not backward compatible** — generated Dockerfile content, `install_pybuggy` return text, and the
manifest guarantee change for identical inputs (03-investigation.md, all six assessment questions answered).
**Proceeding under the explicit user override** (q2, option A, 2026-10-30), recorded in
breaking-escalation.md and to be cited in the compatibility report and the final change report. Rollout is
staged per the project rule: existing consumer projects keep their prior Dockerfile until the next
bootstrap re-run replaces the old line with the block in place; fresh initializations emit the block
immediately.

## Test Strategy

Per `conventions` (structure mirrors source, no mocks for file I/O — `tmp_path`, `monkeypatch.chdir`):

- `tests/commands/init/test_bootstrap.py::TestInstallPybuggy` (rewritten):
  - `test_install_pybuggy_writes_the_root_install_block_and_is_idempotent` — fresh file → the exact
    4-line block appended, INFO log, return value = block; immediate re-run → `None`, file unchanged.
  - `test_install_pybuggy_ensures_newline_separator` — no trailing newline → block still on fresh lines.
  - `test_install_pybuggy_replaces_a_stale_single_line_instead_of_appending` — parametrized over the old
    shapes (`-v 2.0`, `-v 2.0.x`) → the block replaces the line in place, single occurrence, idempotent
    after.
  - `test_install_pybuggy_noop_without_file` — unchanged behavior.
  - `test_install_pybuggy_derives_nothing_from_the_installed_version` — metadata lookup made to raise →
    the block is still written (the derivation is gone).
  - `TestInstallPlaywright` (updated/added):
    - `test_install_playwright_inserts_inside_the_root_section` — file with the block → the line lands
      between `_INSTALL_RUN` and `USER goga`; idempotent; browser change repins in place.
    - `test_install_playwright_relocates_a_stranded_line` — pre-fix layout (old single line + playwright
      after it) after a block replacement → the line moves inside the root section.
    - `test_install_playwright_appends_without_a_block` — no install block → end-of-file append
      (defensive path); existing noop paths (absent file, unreadable web.yml) stay covered.
- `tests/commands/init/test_init.py`: `_INSTALL_LINE` → `_INSTALL_BLOCK`; endswith-asserts adjusted
  (`…block\n`); web-kind asserts → `endswith("RUN playwright install --with-deps firefox\nUSER goga\n")`
  / `…chromium\nUSER goga\n` (the root-section placement at the orchestration level).
- `tests/commands/init/test_init_integration.py`: the two literal pins → the block form.
- Full gates: `.venv` pytest `tests/` green; `ruff check goga_tool_pybuggy/ tests/` 0 errors;
  `ruff format --check` on touched files; `goga lint` 25 cells 0 errors.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Playwright anchor misses (no block in file) | low | web Dockerfile line lands at end (old behavior) | defensive append path kept + pinned test |
| Hybrid/stale Dockerfiles (old line + user edits) double-write | low | duplicate install steps | `_INSTALL_RUN` presence check runs before the old-line replacement; replacement is span-exact; pinned tests |
| Stale mirror fragments left behind | medium | doc/contract drift (project rule) | lockstep edit list + repo-wide grep gate (old line text, "install line" phrasing) |
| Over-reach into the session/tools amendment | low | scope creep | amendment code untouched — only the `_pybuggy_version_axis` docstring sentence changes |
| Test double assumptions break (`importlib.metadata` monkeypatches) | medium | red suite | the derivation tests are removed/replaced in the same change; full-suite gate before finish |
