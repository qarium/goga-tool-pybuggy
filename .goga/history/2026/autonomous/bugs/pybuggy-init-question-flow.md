# Change Plan + Change Execution Report — pybuggy init question flow

Task classification: **bugfix** (user-reported defects in the `pybuggy init` onboarding flow).
Date: 05/10/26. Pipeline: Bugfix/hotfix. User approvals: task q1; plan refinement q2.

## User-Reported Defects

1. The session asks about the Dockerfile — it must always exist (never asked whether to create it).
2. The session asks which tools to record in the goga config — pybuggy must always be recorded by default
   (the question itself stays for other tools).
3. The autonomy confirm is asked between the first spec and the additional specs — the spec survey must
   complete first, then autonomy.

## Root Cause

- The goga onboarding engine's core `docker_image` section asks "Create Dockerfile?" with a default of No;
  a declined gate leaves no Dockerfile and the bootstrap's mandatory-Dockerfile invariant then fails the
  command — a question trap for a tool that requires the file. The engine's skip mechanism cannot remove the
  gate alone: skipping only the `dockerfile` child collapses to the pull-image branch (no Dockerfile);
  skipping only `base_image` leaves the generator without the dockerfile+base_image pair it needs.
- The core `tools` question records name→version pairs manually; nothing guarantees the invited tool itself
  is recorded.
- The autonomy confirm was declared as the last item of the pybuggy block, while the additional specs are
  surveyed later — at the amendment moment. The resulting interactive order was: first spec → autonomy →
  "Add another spec?" — the autonomy question interleaved the spec survey.

## Change Strategy (as approved with user refinements)

- Skip the whole core `docker_image` section (the gate, the path, and the engine's own image asks disappear);
  declare two own questions in the pybuggy block instead — `base_image` (FROM; the prompt embeds the
  goga-python family hints completed with the runtime goga minor tag, newest member as the default) and
  `image` (built-image name; `{project}:latest` from the git origin, required input when not derivable).
  The Dockerfile is delivered through the amendments: the fixed `.goga/Dockerfile` path plus the answered
  FROM — the pair the engine generator writes the file from. The FROM defaults to the python family because
  the pybuggy test runtime is pytest; the platform does not export its per-language hint table.
- Keep the core `tools` question; amend `tools` with `pybuggy: <installed-minor>.x` (the same minor x-range
  the Dockerfile install line pins; `latest` fallback in a metadata-less run). The platform amend merge
  folds the record into any user-collected tools — pybuggy is always recorded, user tools are kept, a
  user-typed pybuggy entry is overridden by the installed line.
- Remove the autonomy confirm from the declarative block; ask it at the amendment moment after
  `survey_extra_specs` (new routine `survey_autonomy`, default disabled). `build_config_data` takes the
  answer as an explicit `autonomous` parameter.

## Modified Cells

| Cell | Files Modified |
|------|----------------|
| `goga_tool_pybuggy/commands/init` | `session.py`, `__init__.py`, `CODEMANIFEST`, `.usages/init.md`, `.usages/config-build.md` |
| tests (mirror) | `tests/commands/init/test_session.py`, `tests/commands/init/test_init_integration.py`, `tests/test_autonomy_integration.py` |
| docs (outside cells) | `docs/cli/init.md`, `docs/getting-started.md` |

## Implemented Changes

| Change | File | Description |
|--------|------|-------------|
| image questions in the block | `session.py` | `pybuggy_questions` now opens with `base_image` + `image` inputs (python-family hints + runtime tag, newest default; `{project}:latest` or required) |
| autonomy moved | `session.py` | the `autonomous` confirm removed from the block; new `survey_autonomy()` asks it at the amendment moment after the extras |
| docker skip | `session.py` | `declare_pybuggy_session` skips `docker_image` in addition to `convention` |
| richer amendments | `session.py` | `build_config_amendments(answers)` returns `build.review.skip`, the Dockerfile pair + image name, and the `tools` pybuggy record (`_pybuggy_version_axis` helper with the `latest` fallback) |
| explicit autonomy param | `session.py` | `build_config_data(answers, extra_specs, autonomous=False)` — the axis no longer reads an answers key |
| facade | `__init__.py` | 20 routines — `survey_autonomy` exported |
| manifest | `CODEMANIFEST` | global annotations, `declare_pybuggy_session`, `amend_pybuggy_config`, `pybuggy_questions`, `build_config_data`, `build_config_amendments` updated; `survey_autonomy` declared |
| usages | `.usages/init.md`, `.usages/config-build.md` | the session flow, the skips, the amendments, the question order, the mandatory-Dockerfile safety net |
| docs | `docs/cli/init.md`, `docs/getting-started.md` | the new interactive flow; removed the declined-Dockerfile branch; fixed the stale compact `extra_specs` fragment in `cli/init.md` |

## Tests Added

| Test | File | What It Validates |
|------|------|-------------------|
| `test_pybuggy_questions_declares_no_autonomy_item` | `test_session.py` | no autonomy record in the block |
| `test_pybuggy_questions_base_image_hints_follow_runtime_tag` | `test_session.py` | the FROM hints equal the family constants + runtime minor tag; default = newest |
| `TestSurveyAutonomy` (2) | `test_session.py` | the confirm prompt, the disabled default, the enabling answer |
| `test_build_config_amendments_carry_all_five_entries` | `test_session.py` | the exact five amendments in order |
| `test_build_config_amendments_skip_dockerfile_pair_without_base_image` | `test_session.py` | the pair drops together when FROM is absent |
| `test_build_config_amendments_tools_record_falls_back_to_latest` | `test_session.py` | the metadata-less fallback |
| `test_amendments_merge_pybuggy_into_user_collected_tools` | `test_session.py` | the real `SessionAnswers.amend` merge keeps user tools and forces the pybuggy record |
| `test_amend_pybuggy_config_surveys_specs_before_autonomy` | `test_session.py` | the extras complete before the autonomy confirm |
| smoke test (reworked) | `test_init_integration.py` | full real-engine session: no Dockerfile gate, no Dockerfile-path ask, Dockerfile always written (`FROM qarium/goga-python-3.N:<tag>`), `tools: {pybuggy: N.M.x}` in the config, autonomy confirm after the spec loop |

## Specification Updates

| Cell | CODEMANIFEST Changes | Usage Changes |
|------|---------------------|---------------|
| `commands/init` | two skips described; `survey_autonomy` declared; `build_config_data` + `build_config_amendments` signatures extended; `pybuggy_questions` algorithm rewritten (image inputs, no autonomy item) | `init.md`, `config-build.md` — the flow, the skips, the amendments, the safety net |

## Validation Results

- `pytest tests/` — **1029 passed** (was 1028 before the change; one net new test).
- `ruff check goga_tool_pybuggy/ tests/` — clean.
- Manifest YAML parses; declared signatures match the implementation annotations (asserted by the
  signature-contract tests).
- Engine smoke (real registry, real hooks, scripted TTY) confirms the new ask order end to end.

## Compatibility Status

- The interactive behavior change is the requested fix (user-approved in q1/q2).
- Within the package no consumer breaks: `statuses.py` imports only `init_cmd`, `declare_pybuggy_session`,
  `amend_pybuggy_config` (unchanged signatures); `build_config_amendments` gained a required parameter but
  has no callers outside the cell and the tests.
- The tool-config file contract and the `pipelines` axis are unchanged; the `config` and `autonomous` cells
  are untouched.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| The goga-python family constant ages as new images ship | low | visible-by-design constant (the platform hint table is not exported); the image of the running minor line keeps working |
| The FROM defaults to the python family regardless of the surveyed language | low | the pybuggy test runtime is pytest — the python family is the required runtime for every pybuggy project |
| A metadata-less source-tree run records `pybuggy: latest` in tools | low | the bootstrap fails loudly in that environment anyway (`install_pybuggy` raises); the session contribution stays soft |
| `goga schema` fails on this workspace (`AST parsing failed with 958 error(s)`) — pre-existing at HEAD, unrelated to this change | info | reported to the user; not touched by this hotfix |

## Updated Files

- goga_tool_pybuggy/commands/init/session.py
- goga_tool_pybuggy/commands/init/__init__.py
- goga_tool_pybuggy/commands/init/CODEMANIFEST
- goga_tool_pybuggy/commands/init/.usages/init.md
- goga_tool_pybuggy/commands/init/.usages/config-build.md
- tests/commands/init/test_session.py
- tests/commands/init/test_init_integration.py
- tests/test_autonomy_integration.py
- docs/cli/init.md
- docs/getting-started.md
