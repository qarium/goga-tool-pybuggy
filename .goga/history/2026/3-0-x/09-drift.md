# Specification Drift Analysis

## Manifest Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| all 27 cells | None — no CODEMANIFEST and no implementation file was modified by this change; every manifest algorithm, signature, guarantee, and bound-practice reference verified against the post-sync state (see `07-manifests.md`) | n/a (no drift) |
| base practices | `conventions` (`.goga/usages/conventions.md`) unchanged by the sync (force-clean skips root files and `cooks/`), still bound in every manifest that referenced it | n/a (no drift) |

## Usage Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| `autonomous`, root, `config` | None — the consumer recipes and platform references in the cell usages remain valid under the 2.1 platform (verified example-by-example in `08-usages.md`) | n/a (no drift) |
| `.goga/usages/github/goga/**` | Pre-sync drift: the deployed practice tree lagged the declared dependency ref `2.1.x` (the state the user asked to fix) | RESOLVED — `goga usages sync -f` deployed the remote 2.1.x head (`32d25c6`) content; the working tree now matches the declared ref |

## Behavioral Drift

| Surface | Drift Description | Resolved? |
|---|---|---|
| autonomy contribution | Platform's intended behavior change (contributed `{{ }}` strings now render) vs pybuggy's contribution — no drift: the contribution is template-free, verified byte-level (`autonomous/workflow.py` constants) | n/a (no drift) |
| config reads | Platform `!ENV` resolution vs pybuggy's strict validation — no drift: resolution happens inside the facade; pybuggy's documented semantics (fail-loud on non-validatable records) unchanged | n/a (no drift) |
| hook subscriptions | Platform pipeline domain grew 3 → 18 actions vs pybuggy's 7 subscriptions — no drift: all seven addresses remain valid; new actions impose no obligation (boundary isolation) | n/a (no drift) |
| test environment | The `test` extra pinned goga to the 2.0 line while the target env (Dockerfile `:2.1`, usages ref `2.1.x`) is the 2.1 line — the pin's own comment declares it a mirror of the target env | RESOLVED — pin bumped to `goga>=2.1,<2.2`; fresh-env resolution selects 2.1.4; suite green across the line |

## Algorithmic Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| all cells | None — no algorithm specified in any CODEMANIFEST deviates from the implementation; execution orders, side effects, and no-op branches are untouched | n/a ( no drift) |

## Resolution Status

**All drift resolved.** The two drifts this task existed to close — the stale deployed
usages tree (fixed by the sync) and the stale test-env goga pin (fixed by the pin bump) —
are both resolved. No unresolved manifest, usage, behavioral, or algorithmic drift remains.
