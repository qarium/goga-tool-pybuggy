# Autonomous runs of the `api.automate` pipeline

Status: accepted

The `api.automate` pipeline is interactive end to end — communication on every
stage, manual acceptance at the end. We decided to make the stretch from
`review-testcases` through `commit-changes` run unattended: pybuggy itself
subscribes one hook to the goga `pipeline / amend_workflow` action and, when the
run's pipeline is `api.automate` and autonomy is enabled in the tool config,
contributes a declarative workflow amendment before compilation. The early
stages (requirements → prepare-testcases) and the acceptance stay with the
human; the test plan and the test code are produced without a human in the
loop.

## The configuration contract

`.goga/tools/pybuggy/config.yml`, read via goga's `load_tool_config`:

```yaml
pipelines:
  api.automate:
    autonomous: true
```

- The key is per pipeline name — an extensible axis; only `api.automate` is
  implemented. Unknown pipeline names are ignored (forward compatibility);
  structural violations (`pipelines` or `pipelines.<name>` not a mapping,
  `autonomous` not a bool) fail the run with a clean error naming the tool — a
  typo must fail loudly, not silently disable autonomy.
- Absent file, absent section, absent key, or `autonomous: false` all mean off;
  the run composes identically to a project without the feature.
- The onboarding session (`pybuggy init`) asks one confirm question
  (default: disabled) and writes the key into the tool config only when
  enabled.

## The contribution

When enabled, for the fixed stage window `review-testcases`,
`create-testcases`, `code-design`, `design-review`, `coding-plan`,
`plan-review`, `commit-changes`:

- every stage of the window gets `approve: auto` — the runner-level
  interaction is suppressed;
- no per-stage prompt/description directive is contributed and the stage
  skills are not modified — autonomy is purely the workflow-level instruction;
- `accept-result` is not touched: it stays `communication: true` and
  `trigger: manual`. Acceptance (test-failure triage, `bugs.md` records, test
  fixes, the commit after fixes) remains a human-driven step;
- a `build` extend stage ("Build tests") is added after `commit-changes` —
  `python3 -P -m goga.build "$(python3 -m goga history path -f plan.md)"`,
  timeout 8h, `.ralphex` cleanup after the script. The test code, which the
  interactive flow builds by hand between plan review and acceptance, is
  materialized inside the run; it stays uncommitted — the commit belongs to
  the acceptance step that follows.

## Consequences

- An authored project workflow wins per slot over the contribution — a project
  can re-enable interaction for any stage or displace the build stage; the
  contribution applies in the run form and the card form alike.
- The stage window and the build entry are compile-time constants of the
  package; the recipe and the pipeline file evolve together. A renamed
  pipeline stage surfaces as the compiler's structural error — visible, not
  silent.
- In autonomous stages the review skills' ask-the-user mandates find no dialog;
  the stage agent resolves findings on its own and records them in its stage
  output. The acceptance gate that catches residual mistakes stays interactive
  by design.
- Docs to update with the feature: `docs/pipelines/api-automate.md` (an
  "Autonomous runs" section) and the onboarding docs (`docs/cli/init.md`).

## Considered options (rejected)

- Making `accept-result` autonomous (`manual: false`, autonomous failure
  triage) — rejected: triaging test failures without a human was judged
  premature; autonomy ends at `commit-changes`.
- Carrying autonomy into the stage text (an appended `description` directive)
  or editing the review skills — rejected: the workflow-level instruction is
  sufficient; skills stay untouched.
- A separate tool package owning the autonomy contribution — rejected: the
  feature is pybuggy's own pipeline behavior and is configured in pybuggy's
  tool config.
- Hand-editing as the only way to enable (no onboarding question) — rejected:
  the onboarding session must ask (confirm, default off).
