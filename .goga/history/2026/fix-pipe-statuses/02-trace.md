# Trace Report

## Call Flow

```
goga pipeline run (any pipeline)
  └─ goga/pipeline/run_pipeline.py:411  assemble_status_scale()          [platform]
       ├─ HookRegistry → enumerate_tool_packages() → goga_tool_pybuggy    [platform]
       ├─ emit_hook_event("statuses", "register_statuses", context_for)
       │    └─ goga_tool_pybuggy/reg_hooks.py register_hooks()            [subscribed x3]
       │         ├─ register_automate_statuses(context)  → statuses/automate.py  ← DEFECT
       │         ├─ register_fix_statuses(context)       → statuses/fix.py       (ok)
       │         └─ register_patch_statuses(context)     → statuses/patch.py     (ok)
       └─ per entry: _placement_index(stages, entry) → ValueError → logger.warning(
            "skipping status registration", extra={status, reason})          ×4
```

## Data Flow

`register_automate_statuses` pushes six `Stage(qualified_name, filepath, after, before)`
entries into the per-tool `StatusRegistry` (add-only; no anchor resolution at register time).
Assembly then resolves each entry's anchors against the list built so far: the built-in axis
plus earlier-accepted entries. `automate.done` (after `done`) and `automate.coding-planned`
(after `planned`) resolve; `automate.code-designed` (after `specified`) raises
`unknown after anchor 'specified'` and is skipped; the three entries chained below it via
`before="pybuggy.automate.<predecessor>"` then raise `unknown before anchor` and are skipped
in cascade. The surviving scale reaches `goga history status`, topic boards, and switching.

## Manifest Algorithm Mapping

| CODEMANIFEST step (`register_automate_statuses`) | Code path | Match |
|---|---|---|
| 1. register `automate.done` above built-in `done` | `automate.py:15` | ✓ |
| 2. middle statuses in reverse order, each above its built-in twin, below the previous | `automate.py:17-32` | ✗ row 3 anchors `code-designed` after `specified` — no such built-in |
| Requirement: every anchor names an earlier entry or a built-in status | `automate.py:19` | ✗ violated by the contract table itself |

## Cross-Cell Traversals

| Source Cell | Target Cell | Type | Path |
|---|---|---|---|
| goga_tool_pybuggy (root) | goga_tool_pybuggy/statuses | call | `reg_hooks.py` → `statuses/{automate,fix,patch}.py` |
| goga_tool_pybuggy/statuses | goga platform (external) | data | `context.register(...)` → `StatusRegistry._entries` → scale assembly |
| tests/statuses | goga_tool_pybuggy/statuses | usage | `test_automate.py` asserts the literal six calls (incl. the defective anchor) |

## Inconsistencies

| Type | Location | Expected | Actual |
|---|---|---|---|
| manifest ↔ platform axis | `statuses/CODEMANIFEST` automate table row 3 | anchor names a built-in status | `after specified` — never existed in any goga 2.0.x axis |
| code ↔ manifest | `statuses/automate.py:19` | resolvable anchor | mirrors the defective table verbatim |
| usage ↔ code | `goga_tool_pybuggy/.usages/assembly.md:132` | resolvable anchor | documents `after specified` |
| test ↔ platform | `tests/statuses/test_automate.py:37` | anchors validated against the real axis | asserts the literal string `specified`; nothing resolves anchors — the defect is unobservable by the suite |

## Trace Graph

```
built-in axis: empty·todo·defined·discovered·backlog·prototyped·designed·planned·done
                                                      (no "specified" anywhere)
automate line: done ✓ → coding-planned ✓ → code-designed ✗("specified")
                                           → arch-prepared ✗(before code-designed)
                                           → testcases-designed ✗(before arch-prepared)
                                           → requirements-created ✗(before testcases-designed)
fix line:    empty ✓ → collected → analyzed → planned → executed → reviewed   (all ✓)
patch line:  empty ✓ → intended → analyzed → applied → designed → planned → done (all ✓)
```
