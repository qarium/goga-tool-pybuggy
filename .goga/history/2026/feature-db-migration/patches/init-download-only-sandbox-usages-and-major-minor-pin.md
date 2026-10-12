# Change Execution Report

## Summary
Narrowed the `pybuggy init` bootstrap's config registration and re-pinned the recorded version, per user
request (2026-10-12): the four sandbox capability usages (`pybuggy-sandbox-session`, `pybuggy-sandbox-file`,
`pybuggy-data-operations`, `pybuggy-migration-set`) are now download-only — copied to
`.goga/usages/cooks/pybuggy/` but never registered in `codemanifest.usages`/`codemanifest.annotations` of the
consumer `.goga/config.yml`, because they may or may not apply to a given cell while config-level usages bind
every cell; and the pybuggy version is pinned to the installed major.minor line (`2.0`) instead of the minor
x-range (`2.0.x`) — both in the Dockerfile install line (`RUN goga install pybuggy -v 2.0`) and the session
`tools` amendment (`tools.pybuggy: '2.0'`, a quoted YAML string).

## Root Cause
Specification change, not a defect: `run_bootstrap` derived its registration dictionaries from every
discovered usage stem (init.py), and both version derivations (`install_pybuggy`, `_pybuggy_version_axis`)
appended `.x`. Implementation, manifest, tests, and docs all consistently carried the old semantics; all four
layers were changed together.

## Modified Cells
| Cell | Files Modified |
|------|----------------|
| `goga_tool_pybuggy/commands/init` | `init.py`, `bootstrap.py`, `session.py`, `CODEMANIFEST`, `.usages/init.md`, `.usages/config-build.md` |
| docs | `docs/cli/init.md`, `docs/getting-started.md` |
| tests | `tests/commands/init/{test_init,test_bootstrap,test_session,test_init_integration}.py` |

## Implemented Changes
| Change | File | Description |
|--------|------|-------------|
| Registration split | `init.py` | `_REGISTERED_USAGE_ROOTS = ("goga_tool_pybuggy.api",)`; `_discover_packaged_usages()` returns `(discovered, registered)`; `run_bootstrap` builds `usage_keys`/`annotation_lines` from the registered stems only (+ `conventions`); the four sandbox entries removed from `PYBUGGY_ANNOTATIONS` |
| Install pin | `bootstrap.py` | `line = f"RUN goga install pybuggy -v {minor}"` — no `.x` suffix |
| Tools record | `session.py` | `_pybuggy_version_axis()` returns `".".join(version.split(".")[:2])`; docstrings updated |
| Manifest | `CODEMANIFEST` | header annotation scope sentence; `run_bootstrap` step 7 + Requirements; `install_pybuggy` pin wording; `build_config_amendments` step 3 + Requirements |
| Usage docs | `.usages/init.md`, `.usages/config-build.md`, `docs/cli/init.md`, `docs/getting-started.md` | registration tables/bullets and version examples |

## Tests Added
| Test | File | What It Validates |
|------|------|-------------------|
| `test_bootstrap_contract_distributes_six_stems_registers_api_pair_only` | test_bootstrap.py | Six files copied; only api pair + conventions registered; sandbox keys/annotations absent |
| `test_bootstrap_copies_all_and_registers_only_api_usages` | test_bootstrap.py | Byte-identical copies; api registered+annotated; sandbox absent |
| `_assert_bootstrap_registration_split` (smoke) | test_init_integration.py | Real-engine end-to-end split + string-typed `tools.pybuggy` (`\d+\.\d+`, `isinstance str`) |
| Strengthened full-pass test | test_init.py | Registered set equality; four files copied; four annotation references absent |

## Specification Updates
| Cell | CODEMANIFEST Changes | Usage Changes |
|-------|----------------------|---------------|
| commands/init | registration set narrowed (step 7 + Requirements + header scope); pin wording → major.minor quoted string | init.md + config-build.md updated to the new forms |

## Validation Results
VERIFIED — full suite 1716 passed / 18 skipped; `ruff check` + `format` clean; `goga lint` 24 cells 0 errors;
scratch-consumer end-to-end run produced exactly the requested artifacts; cell coverage 99%
(bootstrap/session 100%). Triple consistency holds.

## Compatibility Status
Formally BREAKING (observable bootstrap output changes) — the user's explicit task order and plan approval
(q2) are the recorded override of the STOP. Signatures, paths, exit codes, and error semantics unchanged;
`resolve_version("2.0")` → `==2.0` is a valid goga install form. Existing consumer configs are never rewritten
— stale sandbox keys in already-initialized projects remain as inert documentation entries.

## Risks
| Risk | Severity | Mitigation |
|------|----------|------------|
| Earlier-initialized consumer projects keep inert sandbox usage keys | low | By design — `register_usages` never overwrites/removes; docs note the semantics |
| Legacy `-v 2.0.x` line in an existing consumer Dockerfile is joined (not replaced) by the new `-v 2.0` line | low | Append-only contract of `install_pybuggy`; the stale line is inert |
| Engine emitter uses single quotes (`'2.0'`) | none | Semantically identical YAML string; type preserved (verified through `yaml.safe_load`) |

## Updated Files
- goga_tool_pybuggy/commands/init/init.py
- goga_tool_pybuggy/commands/init/bootstrap.py
- goga_tool_pybuggy/commands/init/session.py
- goga_tool_pybuggy/commands/init/CODEMANIFEST
- goga_tool_pybuggy/commands/init/.usages/init.md
- goga_tool_pybuggy/commands/init/.usages/config-build.md
- docs/cli/init.md
- docs/getting-started.md
- tests/commands/init/test_init.py
- tests/commands/init/test_bootstrap.py
- tests/commands/init/test_session.py
- tests/commands/init/test_init_integration.py

Saved to: `.goga/history/2026/feature-db-migration/patches/init-download-only-sandbox-usages-and-major-minor-pin.md`
(classification: enhancement → `patches/`; `completed/plan.md` already existed).
