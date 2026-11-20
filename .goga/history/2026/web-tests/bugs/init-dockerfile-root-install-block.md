# Change Execution Report — `init` Dockerfile root install block

**Run**: Bugfix 2026-10-30 (branch `web-tests`) · **Pipeline**: goga-change (11 steps, all complete)
**Artifacts**: `.goga/history/2026/fix-dockerfile-install-block/` (01-scope … 10-validation, breaking-escalation)

## Summary

The `goga init` bootstrap wrote a broken pybuggy-install step into the consumer project Dockerfile — a
single `RUN goga install pybuggy -v <major.minor>.x` line executed as the image's default unprivileged
`goga` user, with a redundant init-time version derivation. The fix replaces it with the root-user
project-copy block (`USER root` / `COPY . /tmp/project` / `RUN cd /tmp/project && goga install &&
rm -rf /tmp/project` / `USER goga`): the bulk `goga install` reads the project's own `tools:` pin from
the copied `.goga/config.yml`, so the block carries no version. The playwright browser line now lands
inside the root section (before `USER goga`), a stranded pre-fix line is relocated on the next run, and
every mirror of the contract (CODEMANIFEST, two cell usages, two docs pages, three test modules) moved
in the same lockstep change.

## Root Cause

Design defect in the `install_pybuggy` contract (bootstrap.py:325): the encoded install step assumed the
image's default user can pip-install, while the goga-python base image runs as the unprivileged `goga`
user, and it re-derived the version pin at init time instead of letting the image build read the
project's `tools:` record (`goga install` with no name = BULK path over `.goga/config.yml` — verified
against the installed CLI). Confidence: HIGH (03-investigation.md).

## Modified Cells

| Cell | Files Modified |
|---|---|
| `goga_tool_pybuggy/commands/init` | `bootstrap.py`, `CODEMANIFEST`, `.usages/init.md`, `.usages/config-build.md`, `session.py` (docstring only) |
| — (mirrors, same change) | `docs/cli/init.md`, `docs/getting-started.md` |
| — (tests, same change) | `tests/commands/init/test_bootstrap.py`, `test_init.py`, `test_init_integration.py` |

## Implemented Changes

| Change | File | Description |
|---|---|---|
| block writer | `goga_tool_pybuggy/commands/init/bootstrap.py` | `install_pybuggy` writes the 4-line root-user block; no-op on absent file or present block; replaces any previous single-line install in place; version derivation and its `ValueError` branch removed (`importlib.metadata` import dropped) |
| anchored playwright | `goga_tool_pybuggy/commands/init/bootstrap.py` | new `_root_section_anchor` helper; `install_playwright` inserts before the block's `USER goga`, relocates a stranded line, repins on browser change, falls back to end-of-file append without a block |
| docstring correction | `goga_tool_pybuggy/commands/init/session.py` | `_pybuggy_version_axis` docstring: the recorded x-range is what the image-build bulk install reads; the Dockerfile block carries no version (code unchanged) |
| contract lockstep | `goga_tool_pybuggy/commands/init/CODEMANIFEST` | `install_pybuggy` signature label `-> block:str | None` + rewritten algorithm/requirements/constraints; `install_playwright` anchor semantics; `run_bootstrap` steps 6/6c + web requirement + global annotation wording |
| usage lockstep | `.usages/init.md`, `.usages/config-build.md` | artifact-table rows and cross-references describe the block and the root-section placement |
| docs lockstep | `docs/cli/init.md`, `docs/getting-started.md` | table rows, the derivation paragraph, side-effect bullets, mandatory-Dockerfile wording |

## Tests Added

| Test | File | What It Validates |
|---|---|---|
| `test_install_pybuggy_writes_the_root_install_block_and_is_idempotent` | tests/commands/init/test_bootstrap.py | exact block, log, return, idempotent re-run |
| `test_install_pybuggy_ensures_newline_separator` | tests/commands/init/test_bootstrap.py | newline-less file handled |
| `test_install_pybuggy_replaces_a_stale_install_line_instead_of_appending` (parametrized) | tests/commands/init/test_bootstrap.py | both old pin shapes replaced in place, once |
| `test_install_pybuggy_noop_without_file` | tests/commands/init/test_bootstrap.py | file never created |
| `test_install_pybuggy_derives_nothing_from_the_installed_version` | tests/commands/init/test_bootstrap.py | metadata-less run still writes; no `-v` |
| `test_install_playwright_inserts_inside_the_root_section` | tests/commands/init/test_bootstrap.py | anchored placement, idempotency, block-idempotency with the line inside, browser repin |
| `test_install_playwright_relocates_a_stranded_line` | tests/commands/init/test_bootstrap.py | pre-fix layout repaired |
| `test_install_playwright_noop_paths` (extended) | tests/commands/init/test_bootstrap.py | lenient no-ops + no-block fallback (both newline states) |
| `_INSTALL_BLOCK` + web-layout pins (9 sites) | test_init.py, test_init_integration.py | orchestration and end-to-end layouts |

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|---|---|---|
| `commands/init` | `install_pybuggy` (label + algorithm + requirements + constraints), `install_playwright` (algorithm + requirements), `run_bootstrap` (steps 6/6c, web requirement, global annotation) | `init.md` (2 table rows + invariant wording), `config-build.md` (tools-record cross-reference) |

## Validation Results

**VERIFIED** (10-validation.md): full suite 1973 passed / 21 skipped; `bootstrap.py` 100% statement and
branch coverage; `ruff check` 0 errors; `ruff format` clean; `goga lint` 25 cells / 0 errors; repo-wide
search for the retired line form empty outside its intentional replacement-test input; live REPL check
reproduces the user's prescribed Dockerfile byte-for-byte for api, web, and pre-fix-repair layouts.

## Compatibility Status

**Breaking — authorized.** Same-arguments behavior, output format, return semantics, manifest
guarantees, and pinning tests all changed (05-compatibility.md). Detected at Step 2, escalated
(breaking-escalation.md), overridden by the user (q2, 2026-10-30, option A: block without `-v`,
playwright inside the root section), plan approved (q3). Rollout is staged: existing consumer projects
keep their prior Dockerfile until the next bootstrap re-run repairs it in place; fresh initializations
emit the block immediately.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| consumer Dockerfiles without the install block (playwright fallback) | low | end-of-file append fallback kept and pinned |
| hybrid/stale Dockerfile layouts | low | presence check precedes replacement; replacement is span-exact; repair path pinned |
| mirror drift recurrence | low | lockstep list + repo-wide grep gate executed; lint green |

## Updated Files

- `.goga/history/2026/fix-dockerfile-install-block/01-scope.md` … `10-validation.md`, `breaking-escalation.md` (run artifacts)
- `docs/cli/init.md`
- `docs/getting-started.md`
- `goga_tool_pybuggy/commands/init/.usages/config-build.md`
- `goga_tool_pybuggy/commands/init/.usages/init.md`
- `goga_tool_pybuggy/commands/init/CODEMANIFEST`
- `goga_tool_pybuggy/commands/init/bootstrap.py`
- `goga_tool_pybuggy/commands/init/session.py`
- `tests/commands/init/test_bootstrap.py`
- `tests/commands/init/test_init.py`
- `tests/commands/init/test_init_integration.py`
- `.goga/history/2026/web-tests/bugs/init-dockerfile-root-install-block.md` (this report)
