# Trace Report — Patch cycle 2 (init autonomy for api.patch)

## Call Flow

```
goga onboarding session (engine-owned)
├─ declaration moment
│   hooks.subscribe("onboarding", "declare_session", "declare")  [reg_hooks.py:26]
│   └─ declare_pybuggy_session(context)                [commands/init/session.py:409]
│       ├─ pybuggy_questions()                         [session.py:71]  — declarative block, NO autonomy question
│       └─ context.skip("convention"), context.skip("docker_image")
└─ amendment moment
    hooks.subscribe("onboarding", "amend_config", "amend")        [reg_hooks.py:28]
    └─ amend_pybuggy_config(context)                   [session.py:430]
        ├─ survey_extra_specs()  → list[dict]          [session.py:142]  — click confirm/prompt loop
        ├─ survey_autonomy()     → bool                [session.py:174]  — ONE confirm, api.automate only
        ├─ build_config_amendments(answers) → dict     [session.py:248]
        └─ context.write_config("config.yml",
              build_config_data(answers, extra_specs, autonomous))   [session.py:454]
```

`build_config_data` enabling branch (session.py:225-226):

```python
if autonomous:
    data["pipelines"] = {"api.automate": {"autonomous": True}}
```

## Data Flow

```
survey_autonomy() ──bool──► build_config_data(answers, extra_specs, autonomous)
                              │ plain-serializable payload
                              ▼
                    context.write_config("config.yml", payload)
                              │ engine yaml.dump (fresh session only)
                              ▼
                .goga/tools/pybuggy/config.yml  (consumer tree)
                              │ platform tool-config facade (raw parse)
                              ▼
                config/storage.py :: resolve_autonomy(axis)   [config cell]
                              │ bool
                              ▼
                autonomous/amendment.py :: amend_workflow     [autonomous cell]
                  ├─ CONTRIBUTIONS lookup by PipelineIdentity.name
                  ├─ resolve_autonomy(record.axis)
                  └─ enabled → context.contribute(build_autonomous_workflow(record))
```

The axis keys are duplicated as literals on both sides: `"api.automate"` in
`session.py:226` (producer) and `"api.automate"`/`"api.patch"` in
`autonomous/contributions.py` (consumer records). The resolver accepts any
pipeline-name key; `api.patch` is already a first-class axis on the consumer side.

## Manifest Algorithm Mapping

| CODEMANIFEST (commands/init) | Algorithm step | Actual code path | Match |
|---|---|---|---|
| `survey_autonomy` step 1 | Ask "Run the api.automate pipeline unattended (autonomous mode)?" confirm (default no), return the answer | session.py:187 — verbatim prompt, `default=False` | ✅ |
| `build_config_data` step 3 | When `autonomous` enables, add the pipelines axis entry — the api.automate record with autonomous true | session.py:225-226 — exactly the automate record | ✅ |
| `amend_pybuggy_config` steps 1–6 | invited gate → answers → `survey_extra_specs` → `survey_autonomy` → amendments → `write_config` | session.py:444-454 — same order | ✅ |
| `pybuggy_questions` constraint | "Do not declare an autonomy question — surveyed by `survey_autonomy` at the amendment moment" | no autonomy Question in the block | ✅ |

The manifest faithfully describes the current single-axis behavior — code and manifest
must change **together** (the cell convention: ensure the current state, not changelogs).

## Cross-Cell Traversals

| Source Cell | Target Cell | Type | Path |
|---|---|---|---|
| commands/init | goga_tool_pybuggy/config | usage import | `Imports.Usages: autonomy` → `config/.usages/autonomy.md` (axis shape the payload must satisfy) |
| commands/init | goga_tool_pybuggy/config | data | payload → config.yml → `resolve_autonomy(axis)` reads it back at amend time |
| commands/init | goga_tool_pybuggy/plugin | type import | `PluginConfigKeys` — scalar key walk, untouched by the change |
| autonomous | goga_tool_pybuggy/config | call | `amend_workflow` → `resolve_autonomy(record.axis)` |
| root (goga_tool_pybuggy) | commands/init | subscription | `hooks.subscribe("onboarding", "amend_config", "amend", amend_pybuggy_config)` |

## Inconsistencies

| Type | Location | Expected | Actual |
|---|---|---|---|
| Feature gap (not code/manifest drift) | `session.py:187` prompt; `session.py:226` payload | api.patch offered beside api.automate (per the shipped `PATCH_CONTRIBUTION` axis and docs/configuration.md "api.automate or api.patch") | Only api.automate is surveyed/written |
| Doc gap | docs/getting-started.md:40, docs/cli/init.md:170-183 | The survey description mirrors the prompts | Describes the automate-only confirm and single-entry payload |

No manifest↔code inconsistency exists — both sides consistently implement the OLD
single-axis behavior; the change updates both in lockstep.

## Trace Graph

```
[init cell]                                [config cell]                 [autonomous cell]
survey_autonomy ─bool─┐                    resolve_autonomy ◄────────── amend_workflow
                      ▼                          ▲  ▲                      │
build_config_data ─ payload ─► config.yml ────────┘  │                      ▼
                      │          (fresh sessions     │ axis literal    build_autonomous_workflow
                      │           only — never       │ "api.automate"      per PipelineContribution
                      │           rewritten)         │ "api.patch"     (automate / patch records)
                      └─ "pipelines": {"api.automate": …}   ◄─ THE GAP: api.patch never written by init
```
