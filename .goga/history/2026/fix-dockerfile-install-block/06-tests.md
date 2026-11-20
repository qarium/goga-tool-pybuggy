# Test Report

## Changes Requiring Coverage

| Change | Type |
|---|---|
| `install_pybuggy` writes the root-user copy-and-install block (fresh append) | behavior |
| `install_pybuggy` idempotency at the current block (incl. a playwright line riding inside) | behavior |
| `install_pybuggy` replaces any previous single-line install shape in place (`-v 2.0`, `-v 2.0.x`) | regression/repair |
| `install_pybuggy` no-op on absent file; no version derivation (metadata-less run succeeds) | regression/edge |
| `install_pybuggy` newline guard on a newline-less Dockerfile | edge |
| `install_playwright` inserts inside the root section (before the block's `USER goga`) | behavior |
| `install_playwright` idempotent at the current browser/position; browser change repins in place | behavior/regression |
| `install_playwright` relocates a stranded pre-fix line into the root section | regression/repair |
| `install_playwright` defensive end-of-file append without a block (with and without trailing newline) | edge |
| `run_bootstrap` orchestration: api-kind block, web-kind placement, both-kind layout | manifest/integration |
| Contract surface: both writers remain module callables with `str | None` returns | manifest |

## Tests Added

| Test Name | File | What It Validates |
|---|---|---|
| `test_install_pybuggy_writes_the_root_install_block_and_is_idempotent` | tests/commands/init/test_bootstrap.py | exact block append, INFO log, return value, second call no-op |
| `test_install_pybuggy_ensures_newline_separator` | tests/commands/init/test_bootstrap.py | newline-less file gains the block on fresh lines |
| `test_install_pybuggy_replaces_a_stale_install_line_instead_of_appending` (parametrized: concrete/x-range) | tests/commands/init/test_bootstrap.py | both old single-line shapes replaced in place, single install step remains, idempotent after |
| `test_install_pybuggy_noop_without_file` | tests/commands/init/test_bootstrap.py | absent Dockerfile never created |
| `test_install_pybuggy_derives_nothing_from_the_installed_version` | tests/commands/init/test_bootstrap.py | metadata lookup raising still writes the block; no `-v` in the artifact |
| `test_install_playwright_inserts_inside_the_root_section` | tests/commands/init/test_bootstrap.py | anchored placement, idempotency, `install_pybuggy` no-op with the line inside, browser repin in place |
| `test_install_playwright_relocates_a_stranded_line` | tests/commands/init/test_bootstrap.py | pre-fix layout (line after `USER goga`) repaired into the root section, then idempotent |
| `test_install_playwright_noop_paths` (extended tail) | tests/commands/init/test_bootstrap.py | absent file / unreadable web.yml no-ops; no-block fallback append with and without trailing newline |
| `_INSTALL_BLOCK` pins + web-layout asserts (7 sites) | tests/commands/init/test_init.py | orchestration-level block and root-section placement (api, web, both kinds) |
| `_INSTALL_BLOCK` pins + structural asserts (2 sites) | tests/commands/init/test_init_integration.py | end-to-end session smoke: block in the Dockerfile, playwright inside the root section |

Removed with the retired derivation: `test_install_pybuggy_derives_x_range_line_and_is_idempotent`,
`test_install_pybuggy_missing_metadata_raises_clean_value_error`, the version monkeypatches in the
`TestRunBootstrap` setup (inert after the change), and the old append-at-end playwright test
(superseded by the anchored and relocation tests).

## Test Results

| Test | Status | Details |
|---|---|---|
| `tests/commands/init/test_bootstrap.py` | PASS | 53 passed |
| `tests/commands/init/test_init.py` | PASS | 71 passed |
| `tests/commands/init/test_init_integration.py` | PASS | 5 passed |
| `tests/commands/init/` (all) | PASS | 166 passed |
| full suite `tests/` | PASS | 1973 passed, 21 skipped |
| coverage `bootstrap.py` (changed module) | PASS | 237 stmts, 0 miss; 106 branches, 0 miss — 100% |
| `ruff check goga_tool_pybuggy/ tests/` | PASS | 0 errors |
| `ruff format --check` (touched files) | PASS | all formatted |
| `goga lint` | PASS | 25 cells, 0 errors |

## Coverage Gaps

| Changed Behavior | Covered? | Notes |
|---|---|---|
| block write / replace / idempotency | yes | — |
| no-version derivation | yes | — |
| playwright anchor / repin / relocate / fallback | yes | the fallback append branch gained a trailing-newline case after the first coverage pass |
| orchestration and integration layouts | yes | — |
| manifest contract surface | yes | callable-signature contract test retained |

## Missing Coverage Analysis

Nothing remains uncovered in the changed behavior: the changed module reaches 100% statement and branch
coverage over the full init test tree, and every plan-listed behavior has an explicit pin. The retired
`ValueError`-on-metadata branch has a negative successor (`derives_nothing_from_the_installed_version`)
instead of a removal-only gap.
