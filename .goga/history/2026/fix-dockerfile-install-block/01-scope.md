# Scope Resolution Report

**Task source**: user answer q1 (Bugfix run, branch `web-tests`), 2026-10-30.

## Task Summary

The `goga init` CLI writes a wrong pybuggy-install step into the consumer project Dockerfile. Today the
bootstrap appends a single `RUN goga install pybuggy -v <major.minor>.x` line; the required form is a
project-copy block executed as root:

```dockerfile
FROM qarium/goga-python-3.14:2.0
USER root
COPY . /tmp/project
RUN cd /tmp/project && goga install && rm -rf /tmp/project
USER goga
```

The fix must change the Dockerfile writer (and every mirror of the line's contract) so the init bootstrap
emits the root-user copy-and-install block instead of the floating-pin single line.

## Candidate Cells

| Cell | Reason | Priority |
|---|---|---|
| `goga_tool_pybuggy/commands/init` | Owns `install_pybuggy` / `install_playwright` (bootstrap.py), the `run_bootstrap` step-6/6c orchestration, the CODEMANIFEST contract, and the `.usages` docs of the generated Dockerfile content | 1 (runtime participation) |

## Included Dependencies

| Cell | Behavioral Relevance |
|---|---|
| none | `commands/init` is the sole writer of the Dockerfile install content; no other cell imports or consumes the generated line. `plugins`/`web` cells only supply the config keys already consumed elsewhere in bootstrap.py — untouched by this task. |

## Excluded Dependencies

| Cell | Exclusion Reason |
|---|---|
| `goga_tool_pybuggy/plugins` | No behavioral participation in Dockerfile generation; infrastructural dependency of the init cell only via config keys unrelated to the install line |
| `goga_tool_pybuggy/web` | Same — `WebConfigKeys` is consumed by the example documenter, not by the install writer |
| `goga_tool_pybuggy/sandbox`, `api`, `spec`, `output`, `matchcrest`, `statuses`, other `commands/*` | No manifest semantic involvement, no data-flow participation in the Dockerfile step |

## Usage Relationships

| Usage | Relevance |
|---|---|
| `.goga/usages/conventions.md` (`conventions`) | Mandatory style/testing rules for every touched module and test |
| `goga_tool_pybuggy/commands/init/.usages/init.md` (lines 107–114) | Documents the generated install line and the mandatory-Dockerfile invariant — must move in lockstep |
| `goga_tool_pybuggy/commands/init/.usages/config-build.md` (line 97–101) | References the Dockerfile pair and the x-range pin the install line uses — drift candidate |
| `docs/cli/init.md` (line ~142), `docs/getting-started.md` (line ~84) | Documentation mirrors of the generated line — must move in lockstep (repo-wide text search per project rule) |

## Semantic Participation Summary

`commands/init` is the only cell with behavioral participation: `install_pybuggy` (bootstrap.py:325)
derives and writes the line, `run_bootstrap` step 6/6c (init.py) calls it (then `install_playwright`),
the CODEMANIFEST fixes its contract (single-line x-range pin), `.usages/init.md` + `config-build.md` +
`docs/cli/init.md` + `docs/getting-started.md` mirror it, and `tests/commands/init/test_bootstrap.py`,
`test_init.py`, `test_init_integration.py` pin the exact emitted text.

## Final Investigation Scope

- `goga_tool_pybuggy/commands/init` — `bootstrap.py::install_pybuggy` (+ `_INSTALL_LINE`), the
  `install_playwright` interaction with the new `USER` block, `CODEMANIFEST` (`install_pybuggy`,
  `install_playwright`, `run_bootstrap` step 6/6c annotations)
- Mirrors: `.usages/init.md`, `.usages/config-build.md`, `docs/cli/init.md`, `docs/getting-started.md`
- Tests: `tests/commands/init/test_bootstrap.py`, `test_init.py`, `test_init_integration.py`

## Scope Risks

- **Under-scoping**: `install_playwright` appends after the last line — with the new block ending in
  `USER goga`, the playwright `RUN` would land in the non-root section and fail at build time. The
  placement interaction is in scope.
- **Under-scoping**: stale mirrors (docs/usages/tests) left describing the single-line pin — the project
  rule mandates the lockstep move plus a repo-wide text search for the old form.
- **Over-scoping**: the session questions, config payloads, and writer gates stay untouched; the
  version-metadata derivation may become dead code with the new form — its removal is a contract
  decision resolved in investigation/planning, not an excuse to refactor the cell.

## Notes

- The user-provided target form carries no `-v <pin>`: `goga install` resolves the toolset from the
  copied project config, so the installed-distribution version derivation likely loses its purpose —
  to be confirmed as a contract decision in the plan.
- The example Dockerfile in the task is the api-kind shape; whether the playwright line must slot inside
  the root section (before `USER goga`) is part of the minimal fix proposal.
