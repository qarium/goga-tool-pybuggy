# TODO — 3-0-x (usages re-sync from goga 2.1.x)

## Task

Source: user answer to `autonomous_execution.q1` (2026-11-24).

Run `goga usages sync -f` — the command re-syncs cell-level usages from the declared
git dependency (`github/goga` → `git@github.com:qarium/goga.git`, ref `2.1.x`, root `goga`)
into `.goga/usages/github/goga/`. The remote has many updates.

Then determine whether anything in pybuggy (code or manifests) must change because
of the goga update.

## Acceptance

- `goga usages sync -f` executed; `.goga/usages/github/goga/` reflects the remote
  2.1.x state; `cooks/` and root files of `.goga/usages/` are preserved.
- Every CODEMANIFEST reference into the synced subtree still resolves (no dangling
  practice paths after the update).
- Every semantic change in the re-synced practices that pybuggy implements is traced
  to the implementation; required code/manifest changes are either applied with
  triple consistency (CODEMANIFEST / implementation / .usages) or explicitly
  reported as not needed.
