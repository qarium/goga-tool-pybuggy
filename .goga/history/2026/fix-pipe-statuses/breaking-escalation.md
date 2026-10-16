# Breaking Change Escalation Report

## Verdict

BREAKING CHANGE DETECTED at Investigation (Step 2). Pipeline halted pending user override.
The breakage restores intended, documented behavior — classification stands regardless of
intent (project policy: a defect fix altering same-arguments behavior is a breaking change).

## What Breaks

- `register_automate_statuses(context)` — identical call, different delivered outcome:
  six accepted registrations instead of two accepted + four skipped.
- `goga history status` for pybuggy automate topics carrying `requirements.md`,
  `testcases.md`, `arch.md`, or `design.md`: the reported status migrates from the built-in
  fallback names to `pybuggy.automate.requirements-created` / `testcases-designed` /
  `arch-prepared` / `code-designed`. Consumers filtering by built-in names for such topics
  stop matching them at the next status resolution.
- Run logs: the four `skipping status registration` warnings disappear (the reported defect).
- `tests/statuses/test_automate.py` literal-anchor expectation breaks and is updated with
  the fix.

## What Does Not Break

- Artifact paths, registration order, the other 11 pybuggy statuses, the built-in axis,
  the platform package, and every public API signature — untouched.
- Nothing stored or generated carries the old form: the scale is assembled fresh each run;
  the change applies from the next pipeline run. No staged rollout is applicable.

## Requested Decision

Override the STOP and proceed with the minimal fix (anchor `after="specified"` →
`after="designed"` mirrored across code, manifest table, package usage table, test
expectation, plus a real-axis regression test), or halt with no changes.
