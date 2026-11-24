# Scope Resolution Report

## Task Summary

The user requested two things: (1) run `goga usages sync -f` to force re-sync the
cell-level usages deployed from the declared git dependency `github/goga`
(`git@github.com:qarium/goga.git`, ref `2.1.x`, root `goga`) into
`.goga/usages/github/goga/` — the remote branch carries many updates; (2) determine
whether pybuggy (code or manifests) needs any change because of the goga update.
The local goga CLI is 2.1.2; the remote `2.1.x` head is `32d25c6`. The current synced
tree (113 tracked md files) is committed and the working tree is clean, so the re-sync
result is directly diffable via git.

## Candidate Cells

| Cell | Reason | Priority |
|------|--------|----------|
| `goga_tool_pybuggy` (root) | Manifest `Usages:` binds `goga-hooks` → `hooks/registering-hooks.md` and `goga-onboarding-hooks` → `onboarding/registering-hooks.md` | 1 — direct manifest reference |
| `goga_tool_pybuggy/config` | Binds `goga-tool-config` → `config/tool-configuration.md` | 1 — direct manifest reference |
| `goga_tool_pybuggy/autonomous` | Binds `goga-pipeline-hooks`, `goga-workflow-document`, `goga-compile-flow` → `pipeline/registering-hooks.md`, `pipeline/workflow/parse-workflow.md`, `pipeline/compiler/compile-flow.md` | 1 — direct manifest reference |
| `goga_tool_pybuggy/commands/init` | Binds `goga-scaffold`, `goga-onboarding`, `goga-onboarding-hooks`, `goga-onboarding-questions`, `goga-onboarding-generator` → `scaffold/*`, `onboarding/*` | 1 — direct manifest reference |
| `goga_tool_pybuggy/statuses` | Binds `goga-statuses` → `history/registering-hooks.md` | 1 — direct manifest reference |

## Included Dependencies

| Cell | Behavioral Relevance |
|------|---------------------|
| Implementation files of the five candidate cells | The bound practices describe goga-side protocols (hook registration, tool configuration, workflow documents/compilation, scaffold/onboarding, status history) that these cells implement or consume — semantic changes in the practices are the only channel through which the goga update can oblige a pybuggy change |

## Excluded Dependencies

| Cell | Exclusion Reason |
|------|------------------|
| `goga_tool_pybuggy/web`, `plugins`, `spec`, `output`, `lifecycle`, `sandbox/*`, `api/*`, `matchcrest/*`, `commands/{page,pull,diff,info,list,generate}` | No manifest reference into the synced subtree; no behavioral participation in goga usages sync — only `cooks/` library practices, which the sync does not touch |
| `.goga/usages/cooks/`, `.goga/usages/conventions.md` | Preserved by the force clean — goga 2.1.2 `clean_usages_dir` removes only non-`cooks` subdirectories and leaves root files; not part of the git dependency |

## Usage Relationships

| Usage (manifest key → synced path) | Relevance |
|---|---|
| root: `goga-hooks` → `hooks/registering-hooks.md` | Hook registration protocol used by root cell |
| root: `goga-onboarding-hooks` → `onboarding/registering-hooks.md` | Onboarding hook registration |
| config: `goga-tool-config` → `config/tool-configuration.md` | `.goga/tools/pybuggy/config.yml` schema/semantics |
| autonomous: `goga-pipeline-hooks` → `pipeline/registering-hooks.md` | Pipeline hook registration |
| autonomous: `goga-workflow-document` → `pipeline/workflow/parse-workflow.md` | Workflow document format parsed by autonomous cell |
| autonomous: `goga-compile-flow` → `pipeline/compiler/compile-flow.md` | Compile flow contract |
| init: `goga-scaffold` → `scaffold/scaffold-usage.md` | Scaffold API consumed by init |
| init: `goga-onboarding` → `onboarding/onboarding-usage.md` | Onboarding API consumed by init |
| init: `goga-onboarding-hooks` → `onboarding/registering-hooks.md` | Onboarding hook registration |
| init: `goga-onboarding-questions` → `onboarding/questions/question-records.md` | Question record format |
| init: `goga-onboarding-generator` → `onboarding/generator/artifact-generation.md` | Artifact generation flow |
| statuses: `goga-statuses` → `history/registering-hooks.md` | Status history hook registration |

## Semantic Participation Summary

Five cells participate: their CODEMANIFEST headers bind twelve practices deployed from
the goga git dependency, and their implementations realize the goga-integration
behaviors those practices document (registering hooks into the goga platform, reading
and writing tool configuration, parsing/compiling workflow documents, driving scaffold
and onboarding during `init`, registering status history). The goga update reaches
pybuggy only through semantic changes in these practices or through additions/removals
of files in the synced subtree.

## Final Investigation Scope

1. Execute `goga usages sync -f`; capture the resulting diff of `.goga/usages/github/`
   (old state is committed in git).
2. Verify all twelve bound usage paths still resolve after the sync; detect new,
   renamed or removed files in the synced tree.
3. For every changed bound practice, extract semantic deltas (protocol, schema, hook
   names, config keys, flows) and trace each delta to the pybuggy implementation.
4. Decide per delta: code change required, manifest change required, or no change
   (documentation-only, no contractual obligation — per cookbook, imported practices
   create no contractual obligations).

## Scope Risks

- Under-scoping: new files in the synced tree may introduce new goga practices pybuggy
  should adopt; removed/renamed files would dangle the twelve manifest references.
- Over-scoping: usages are consumer documentation, not contract — only semantic
  protocol changes that pybuggy implements oblige changes; wholesale rework driven by
  wording drift would violate scope minimization.

## Notes

- The `-f` (force) clean removes every non-`cooks` subdirectory of `.goga/usages/`;
  with only `github/` deployed, the blast radius equals a full re-deploy of
  `github/goga/`. Verified against goga 2.1.2 source (`usages/sync/clean.py::_clean_all`).
- The sync clones via SSH; auth verified (`Hi SerjNikitin`), remote `2.1.x` head
  `32d25c68b1b6f514f1310ddded6e58131534e889`.
