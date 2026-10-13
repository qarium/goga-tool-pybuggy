# Specification Drift Analysis

## Manifest Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| commands/generate | Algorithm/requirements described raw `<name>` paths while the importability guarantee required sanitized segments (pre-existing latent drift exposed by the bug) | YES — steps 7.1–7.6, 6.6, and Requirements now state the sanitized segment; verified against generate.py:397-401, 486-495 |
| commands/diff | Step 7.1 and one requirement assumed the raw-name tree location; `sanitize_id` annotation was endpoint-id-only while the implementation now applies it to spec names | YES — 7.1, requirement, and `sanitize_id` annotations updated; residual `api/<name>/` wording in `orphan_artifact_dirs` aligned to `<sanitized name>` |
| commands/list | Step 3.5 assumed the raw-name tree location | YES — 3.5 now derives the segment via `sanitize_id` |

## Usage Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| commands/generate | generate.md documented `<spec>` without a sanitization rule; collision paragraph covered endpoint ids only | YES — `<spec.dir>` defined with the shared rule, hyphen example added, spec-collision covered |
| commands/diff | diff.md never stated where the tree is read | YES — Subject domain defines `api/<spec.dir>/` and the stale-tree caveat |
| commands/list | list.md `api/<name>/` mentions undefined | YES — defining bullet added; remaining mentions inherit it |
| config | configuration.md implied no constraint on name keys while filesystem consumers need identifier segments | YES — free-form-key note with the derivation rule |
| plugin / api / init usages | Verified: `api/<spec>/<id>/api.py` claims and free-form `name` descriptions remain accurate | YES — no drift (no change needed) |

## Behavioral Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| commands/generate | Hyphenated/digit-leading spec names now write importable `api/<spec.dir>/…`, `tests/<spec.dir>/…`; new pre-write error on spec-segment collision | YES — intended change under the user's breaking-change override (q2=A); pinned by 7 new tests |
| commands/diff, commands/list | Reads locate the sanitized root; pre-fix raw trees are outside it (endpoints ADD, no REMOVED line) | YES — documented in diff.md and the test report; intended under the same override |

## Algorithmic Drift

| Cell | Drift Description | Resolved? |
|---|---|---|
| commands/generate | Phase order preserved (validate → 5.5 endpoint-collision → 5.6 spec-collision → write); no algorithm stage added or reordered beyond the planned guard | YES — matches Change Plan §Change Strategy 1 |
| commands/diff, commands/list | Read-only flows unchanged apart from the segment derivation | YES |

## Resolution Status

All drift resolved. Verification: `goga lint` 24 cells / 0 errors; full suite 1724 passed, 18 skipped; facades importable; no raw-name path sites remain in code (`"api" / name` / `"tests" / name` grep clean); base practices (`conventions`) present and applied in all reconciled manifests.
